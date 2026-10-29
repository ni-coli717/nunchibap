"""눈치밥 AI 엔진 — 발표 슬라이드 10~13장의 'AI 2개 + 계산 2개'를 실제로 돌리는 모듈.

  AI ①  칸별 유입 인원 예측   그래디언트 부스팅 회귀 (기본 통계보다 나을 때만 교체)
  계산 ① 예상 대기시간        대기행렬 (nb_core.queue)
  AI ②  추천 수락 확률        로지스틱 회귀
  계산 ② 팀별 추천 · 배정     예약이 들어올 때마다 다시 계산하는 순차 배정 (simulate)

실측 데이터가 아직 없으므로 학습 데이터는 '시연용 가상 데이터'다.
가상 데이터의 규칙은 make_history()에 모두 적혀 있고, 11월 실측 후 같은 표 형식으로 교체한다.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from datetime import date, timedelta

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import mean_absolute_error

# ---------- 공통 ----------
SLOT_SHAPE = [0.32, 0.72, 1.0, 0.9, 0.76, 0.5, 0.36, 0.25, 0.17, 0.1, 0.06, 0.04]  # nb_core.base_demand와 같은 모양
WD_SCALE = [52, 56, 50, 54, 58, 56, 56]
WEATHER = ["맑음", "비", "폭염"]
MSG_TYPES = ["숫자형", "신호등형", "보상형"]
FEATURES = ["wd", "slot", "reserved", "recurring", "teams", "menu_pop", "rain", "hot", "event", "grades_out", "last_week"]
FEATURE_KO = {"wd": "요일", "slot": "5분 칸", "reserved": "예약 인원", "recurring": "정기 예약 인원", "teams": "팀 수",
              "menu_pop": "메뉴 인기도", "rain": "비", "hot": "폭염", "event": "학사 일정(시험·단축)",
              "grades_out": "4교시 끝난 학년 수", "last_week": "지난주 같은 칸 실제 인원"}
STAGES = [
    ("STEP 01", "계산 운영", "예약 인원 × 기본 비율로 신호등과 추천을 계산해요"),
    ("STEP 02", "자동 보정", "하교 후 피드백으로 칸별 실제 인원과 배식 속도를 매일 밤 다시 맞춰요"),
    ("STEP 03", "AI 전환", "AI 모델이 기본 통계보다 정확할 때만 교체해요"),
]


def grades_out(slot_idx: int, end_times: dict | None = None, lunch_start: int = 730, slot_len: int = 5) -> int:
    """이 칸 시작 시각까지 4교시가 끝난 학년 수."""
    end_times = end_times or {"1": "12:10", "2": "12:10", "3": "12:05"}
    t = lunch_start + slot_idx * slot_len
    return sum(1 for v in end_times.values() if int(v[:2]) * 60 + int(v[3:5]) <= t)


# ---------- 시연용 가상 데이터 ----------
def make_history(weeks: int = 8, n_slots: int = 10, seed: int = 7, start: date = date(2026, 9, 1)) -> pd.DataFrame:
    """날짜 × 5분 칸 단위 학습 표.

    가상 규칙 (실제 학교에서 확인해야 할 가설):
      - 예약 인원: 요일별 규모 × 칸 모양 × 메뉴 인기도
      - 실제 인원 = 예약 인원 × (1.05 ~ 1.10)  ← '기본 통계'가 잡는 부분
                  + 비 오는 날 매점 대신 급식 (+12%), 폭염 날 앞쪽 칸 쏠림
                  + 시험·단축 수업 날 앞쪽 칸 +35%, 뒤쪽 칸 −45%
                  + 인기 메뉴 날 앞쪽 칸 쏠림 (줄 서서 먼저 먹으려는 학생)
                  + 3학년이 먼저 끝나는 날 첫 칸 증가
      - 이런 상호작용이 있어서 AI가 기본 통계보다 나아질 여지가 생긴다.
    """
    rng = np.random.default_rng(seed)
    rows, d, last = [], start, {}
    days = 0
    while days < weeks * 5:
        if d.weekday() < 5:
            wd = d.weekday()
            menu = int(rng.integers(3, 11))
            w = rng.choice(3, p=[0.72, 0.18, 0.10])
            event = int(rng.random() < 0.08)
            third_early = rng.random() < 0.5
            ends = {"1": "12:10", "2": "12:10", "3": "12:05" if third_early else "12:10"}
            boost = 1 + (menu - 7) * 0.02
            for s in range(n_slots):
                shape = SLOT_SHAPE[s]
                reserved = int(rng.poisson(max(0.5, shape * WD_SCALE[wd] * boost)))
                recurring = int(round(reserved * rng.uniform(0.45, 0.7)))
                teams = max(1, round(reserved / 3.6)) if reserved else 0
                early = s < 4
                mult = rng.uniform(1.05, 1.10)
                if w == 1:
                    mult += 0.12
                if w == 2:
                    mult += 0.10 if early else -0.12
                if event:
                    mult += 0.35 if early else -0.45
                mult += (menu - 7) * (0.03 if early else -0.025)
                go = grades_out(s, ends)
                extra = 6 if (s == 0 and third_early) else 0
                actual = max(0, int(round(reserved * mult + 2 + extra + rng.normal(0, 2.2))))
                key = (wd, s)
                rows.append({"date": d.isoformat(), "wd": wd, "slot": s, "reserved": reserved, "recurring": recurring,
                             "teams": teams, "menu_pop": menu, "rain": int(w == 1), "hot": int(w == 2), "event": event,
                             "grades_out": go, "last_week": last.get(key, reserved), "actual": actual})
                last[key] = actual
            days += 1
        d += timedelta(days=1)
    return pd.DataFrame(rows)


# ---------- AI ① 칸별 유입 인원 ----------
@dataclass
class ArrivalModel:
    stage: int                 # 0 계산 운영 · 1 자동 보정 · 2 AI 전환
    use_ai: bool
    days: int
    ratio: float               # 기본 통계: 실제 ≈ ratio × 예약 + bias
    bias: float
    mae_base: float | None
    mae_ai: float | None
    importance: list[tuple[str, float]]
    test: pd.DataFrame | None
    model: HistGradientBoostingRegressor | None

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        if self.use_ai and self.model is not None:
            return np.maximum(0, self.model.predict(X[FEATURES]))
        return np.maximum(0, X["reserved"].to_numpy() * self.ratio + self.bias)

    @property
    def gain(self) -> float | None:
        if self.mae_base and self.mae_ai is not None:
            return 1 - self.mae_ai / self.mae_base
        return None


def train_arrivals(df: pd.DataFrame, test_days: int = 10, min_ai_days: int = 20, need_gain: float = 0.05) -> ArrivalModel:
    """슬라이드 11장 규칙: 1~2주 계산 → 3~4주 보정 → 5주~ AI 평가, 기본 통계보다 나을 때만 교체."""
    dates = sorted(df["date"].unique())
    n = len(dates)
    if n < 10:  # STEP 01 — 실측 없음: 시연 기본값
        return ArrivalModel(0, False, n, 1.08, 2.0, None, None, [], None, None)
    lin = LinearRegression().fit(df[["reserved"]], df["actual"])
    ratio, bias = float(lin.coef_[0]), float(lin.intercept_)
    if n < min_ai_days:  # STEP 02 — 피드백으로 비율만 보정
        return ArrivalModel(1, False, n, ratio, bias, None, None, [], None, None)
    cut = dates[-test_days]
    tr, te = df[df["date"] < cut], df[df["date"] >= cut].copy()
    base = LinearRegression().fit(tr[["reserved"]], tr["actual"])
    m = HistGradientBoostingRegressor(max_iter=250, learning_rate=0.06, max_leaf_nodes=15, min_samples_leaf=8,
                                      l2_regularization=0.5, random_state=0).fit(tr[FEATURES], tr["actual"])
    te["pred_base"] = base.predict(te[["reserved"]])
    te["pred_ai"] = m.predict(te[FEATURES])
    mb = float(mean_absolute_error(te["actual"], te["pred_base"]))
    ma = float(mean_absolute_error(te["actual"], te["pred_ai"]))
    imp = _importance(m, te)
    use_ai = ma < mb * (1 - need_gain)
    if use_ai:  # 검증을 통과하면 전체 데이터로 다시 학습
        m = HistGradientBoostingRegressor(max_iter=250, learning_rate=0.06, max_leaf_nodes=15, min_samples_leaf=8,
                                          l2_regularization=0.5, random_state=0).fit(df[FEATURES], df["actual"])
    return ArrivalModel(2, use_ai, n, ratio, bias, mb, ma, imp, te, m if use_ai else None)


def _importance(m, te: pd.DataFrame) -> list[tuple[str, float]]:
    """순열 중요도 (특성 하나를 섞으면 오차가 얼마나 커지나)."""
    rng = np.random.default_rng(0)
    base = mean_absolute_error(te["actual"], m.predict(te[FEATURES]))
    out = []
    for f in FEATURES:
        X = te[FEATURES].copy()
        X[f] = rng.permutation(X[f].to_numpy())
        out.append((FEATURE_KO[f], max(0.0, float(mean_absolute_error(te["actual"], m.predict(X)) - base))))
    out.sort(key=lambda x: -x[1])
    return out


def features_for_day(reserved: list[int], wd: int, menu_pop: int, weather: str, event: bool,
                     end_times: dict, last_week: list[int] | None = None) -> pd.DataFrame:
    rows = []
    for s, r in enumerate(reserved):
        rows.append({"wd": wd, "slot": s, "reserved": r, "recurring": round(r * 0.6), "teams": max(1, round(r / 3.6)) if r else 0,
                     "menu_pop": menu_pop, "rain": int(weather == "비"), "hot": int(weather == "폭염"), "event": int(event),
                     "grades_out": grades_out(s, end_times), "last_week": (last_week or reserved)[s] if s < len(last_week or reserved) else r})
    return pd.DataFrame(rows)


# ---------- AI ② 추천 수락 확률 ----------
def make_rec_log(n: int = 700, seed: int = 11) -> pd.DataFrame:
    """가상 추천 기록. 가설: 덜 기다리는 시간이 클수록, 시간 이동이 작을수록, 팀이 작을수록 잘 받아들인다."""
    rng = np.random.default_rng(seed)
    saved = rng.integers(0, 13, n)
    shift = rng.choice([5, 10, 15, 20, 25, 30], n)
    team = rng.integers(1, 6, n)
    msg = rng.choice(MSG_TYPES, n)
    rec = rng.integers(0, 2, n)
    logit = -0.1 + 0.30 * saved - 0.07 * shift - 0.22 * (team - 1) + np.select([msg == "신호등형", msg == "보상형"], [-0.25, 0.4], 0) - 0.3 * rec
    p = 1 / (1 + np.exp(-logit))
    return pd.DataFrame({"saved": saved, "shift": shift, "team": team, "msg": msg, "recurring": rec, "accepted": (rng.random(n) < p).astype(int)})


def _rec_X(df: pd.DataFrame) -> pd.DataFrame:
    X = df[["saved", "shift", "team", "recurring"]].astype(float).copy()
    for m in MSG_TYPES[1:]:
        X[m] = (df["msg"] == m).astype(float)
    return X


@dataclass
class AcceptModel:
    model: LogisticRegression
    acc: float
    base_rate: float
    coefs: list[tuple[str, float]]

    def prob(self, saved: float, shift: float, team: int, msg: str = "숫자형", recurring: int = 0) -> float:
        x = np.array([saved, shift, team, recurring, msg == "신호등형", msg == "보상형"], dtype=float)
        z = float(self.model.intercept_[0] + self.model.coef_[0] @ x)
        return 1 / (1 + math.exp(-z))


def train_accept(df: pd.DataFrame) -> AcceptModel:
    cut = int(len(df) * 0.8)
    m = LogisticRegression(max_iter=500).fit(_rec_X(df.iloc[:cut]), df["accepted"].iloc[:cut])
    acc = float((m.predict(_rec_X(df.iloc[cut:])) == df["accepted"].iloc[cut:]).mean())
    m = LogisticRegression(max_iter=500).fit(_rec_X(df), df["accepted"])
    names = {"saved": "덜 기다리는 시간(분)", "shift": "시간 이동(분)", "team": "팀 인원", "recurring": "정기 예약 팀",
             "신호등형": "신호등형 메시지", "보상형": "보상형 메시지"}
    coefs = [(names[c], float(v)) for c, v in zip(_rec_X(df.head(1)).columns, m.coef_[0])]
    return AcceptModel(m, acc, float(df["accepted"].mean()), coefs)


# ---------- 하교 후 피드백 → 칸별 실제 인원 ----------
def estimate_actual(responses: list[int], response_rate: float, team_avg: float = 1.0) -> list[int]:
    """응답 ÷ 응답률. 응답은 팀 대표가 하므로 팀 평균 인원을 곱한다."""
    r = max(0.05, min(1.0, response_rate))
    return [int(round(x * team_avg / r)) for x in responses]


# ---------- 대기행렬 (사람 단위) ----------
def queue_stats(arrivals: list[int], rate: float, slot_len: int = 5) -> dict:
    """칸 안에서는 도착 순서대로 줄을 선다고 보고, 사람마다 대기시간을 계산."""
    carry, waits, slot_wait = 0.0, [], []
    per_slot = rate * slot_len
    for a in arrivals:
        k = np.arange(1, a + 1)
        waits.extend(((carry + k) / rate).tolist())
        slot_wait.append(round((carry + a) / rate))
        carry = max(0.0, carry + a - per_slot)
    w = np.array(waits) if waits else np.zeros(1)
    return {"avg": float(w.mean()), "p90": float(np.percentile(w, 90)), "max": float(w.max()), "slot_wait": slot_wait, "left_over": carry}


# ---------- 계산 ② 팀별 추천 · 배정 시뮬레이션 ----------
NATURAL_SHAPE = [0.10, 0.40, 1.0, 0.66, 0.30, 0.18, 0.12, 0.08, 0.05, 0.03]  # 앱 없이 4교시 끝나자마자 몰리는 모양 (가설)


def simulate(total: int = 300, res_rate: float = 0.5, cap: int = 52, rate: float = 12.4, slot_len: int = 5,
             n_slots: int = 10, accept: AcceptModel | None = None, msg: str = "숫자형", dynamic: bool = True,
             seed: int = 0, shape: list[float] | None = None, accept_all: bool = False, board_follow: float = 0.15,
             priority: bool = True) -> dict:
    """팀 단위 배정 시뮬레이션.

    1. 팀(1~5명)마다 원래 가고 싶은 칸이 있다 (앱 없을 때의 쏠림 = NATURAL_SHAPE).
    2. 예약하는 팀은 아침에 한 팀씩 들어온다. 고른 칸의 예상 인원(예약 + 예약 안 한 학생 예측)이
       정원을 넘으면 팀이 다 들어가는 가까운 칸을 추천하고, AI ② 확률로 받아들인다.
    3. dynamic=True면 예약이 들어올 때마다 예상 인원을 다시 계산한다 (발표 12장).
       False면 아침 첫 계산 그대로 모두에게 같은 칸을 추천한다 → 추천 칸에 새 줄이 생긴다.
    4. priority=True면 07:30 마감 뒤 아직 넘치는 칸의 팀에게 수락 확률이 높은 순서로 한 번 더 추천한다
       (AI ② '받아들일 학생에게 먼저'). 한 팀은 하루에 추천을 최대 두 번 받는다.
    5. 예약 안 한 학생도 교실 배정표에서 '꽉 참'을 보면 board_follow 확률로 가까운 여유 칸으로 옮긴다.
    accept_all=True는 추천을 모두 받아들인다고 가정한 상한선.
    """
    rng = np.random.default_rng(seed)
    shape = np.array((shape or NATURAL_SHAPE)[:n_slots], dtype=float)
    shape /= shape.sum()
    teams, people = [], 0
    while people < total:
        size = int(min(total - people, rng.choice([1, 2, 3, 4, 5], p=[0.15, 0.25, 0.25, 0.2, 0.15])))
        w = int(rng.choice(n_slots, p=shape))
        teams.append({"size": size, "want": w, "slot": w, "reserve": bool(rng.random() < res_rate), "recs": 0})
        people += size
    before = np.zeros(n_slots, int)
    for t in teams:
        before[t["want"]] += t["size"]
    walk_pred = (1 - res_rate) * total * shape  # 예약 안 한 학생 예측 (AI ① 몫)
    booked = np.zeros(n_slots, float)
    order = [t for t in teams if t["reserve"]]
    rng.shuffle(order)
    sent = acc_n = 0

    def p_accept(saved, shift, sz):
        if accept_all:
            return 1.0
        if accept:
            return accept.prob(saved, shift, sz, msg)
        return 1 / (1 + math.exp(-(-0.1 + 0.3 * saved - 0.07 * shift - 0.22 * (sz - 1))))

    def pick(load, p, sz):
        waits = queue_stats([int(round(x)) for x in load], rate, slot_len)["slot_wait"]
        cands = [s for s in range(n_slots) if s != p and load[s] + sz <= cap]
        if not cands:
            return None, 0, 0
        c = min(cands, key=lambda s: waits[s] * 2 + abs(s - p))
        return c, max(0, waits[p] - waits[c]), abs(c - p) * slot_len

    static_load = walk_pred + res_rate * total * shape  # 아침 첫 계산
    for t in order:
        load = (walk_pred + booked) if dynamic else static_load
        p, sz = t["want"], t["size"]
        if load[p] + sz > cap:
            c, saved, shift = pick(load, p, sz)
            if c is not None:
                sent += 1
                t["recs"] += 1
                if rng.random() < p_accept(saved, shift, sz):
                    acc_n += 1
                    t["slot"] = c
        booked[t["slot"]] += sz
    if priority and dynamic:
        load = walk_pred + booked
        for s in np.argsort(-load):
            if load[s] <= cap:
                continue
            here = [t for t in order if t["slot"] == s and t["recs"] < 2]
            scored = []
            for t in here:
                c, saved, shift = pick(load, s, t["size"])
                if c is not None:
                    scored.append((p_accept(saved, shift, t["size"]), t))
            scored.sort(key=lambda x: -x[0])
            for _, t in scored:
                if load[s] <= cap:
                    break
                c, saved, shift = pick(load, s, t["size"])
                if c is None:
                    continue
                sent += 1
                t["recs"] += 1
                if rng.random() < p_accept(saved, shift, t["size"]):
                    acc_n += 1
                    load[s] -= t["size"]
                    load[c] += t["size"]
                    booked[s] -= t["size"]
                    booked[c] += t["size"]
                    t["slot"] = c
    # 예약 안 한 학생: 교실 배정표에서 꽉 찬 칸을 보고 일부가 옮긴다
    load = walk_pred + booked
    walk = np.zeros(n_slots, int)
    moved = 0
    for t in teams:
        if t["reserve"]:
            continue
        p, sz = t["want"], t["size"]
        if load[p] > cap and rng.random() < board_follow:
            room = [s for s in range(n_slots) if load[s] + sz <= cap]
            if room:
                c = min(room, key=lambda s: (abs(s - p), s < p))
                load[c] += sz
                load[p] -= sz
                walk[c] += sz
                moved += sz
                continue
        walk[p] += sz
    after = walk + np.round(booked).astype(int)
    qb, qa = queue_stats(before.tolist(), rate, slot_len), queue_stats(after.tolist(), rate, slot_len)
    return {"before": before.tolist(), "after": after.tolist(), "q_before": qb, "q_after": qa,
            "sent": sent, "accepted": acc_n, "board_moved": moved, "teams": len(teams), "reserved_teams": len(order)}


def sweep(rates: list[float], runs: int = 12, **kw) -> pd.DataFrame:
    """예약률별 효과 (발표 Q&A: '예약률 30%만 되어도 피크가 깎인다'를 숫자로)."""
    base = [simulate(res_rate=0.0, seed=i, **{**kw, "board_follow": 0.0}) for i in range(runs)]
    out = [{"예약률": "앱 없음", "피크 유입": float(np.mean([max(s["before"]) for s in base])),
            "평균 대기": float(np.mean([s["q_before"]["avg"] for s in base])),
            "상위 10% 대기": float(np.mean([s["q_before"]["p90"] for s in base])),
            "최대 대기": float(np.mean([s["q_before"]["max"] for s in base])), "수락률": None}]
    for r in rates:
        sims = [simulate(res_rate=r, seed=i, **kw) for i in range(runs)]
        sent = sum(s["sent"] for s in sims)
        out.append({"예약률": f"{int(round(r * 100))}%", "수락률": (sum(s["accepted"] for s in sims) / sent) if sent else None,
                    "피크 유입": float(np.mean([max(s["after"]) for s in sims])),
                    "평균 대기": float(np.mean([s["q_after"]["avg"] for s in sims])),
                    "상위 10% 대기": float(np.mean([s["q_after"]["p90"] for s in sims])),
                    "최대 대기": float(np.mean([s["q_after"]["max"] for s in sims]))})
    return pd.DataFrame(out)


# ---------- 앱에서 쓰는 진입점 ----------
@lru_cache(maxsize=16)
def engine(weeks: int = 8) -> tuple[ArrivalModel, AcceptModel]:
    """쌓인 데이터 기간(주)에 맞춰 학습한 AI ①·② (프로세스 안에서 캐시)."""
    weeks = max(1, min(8, int(weeks)))
    return train_arrivals(make_history(weeks=weeks)), train_accept(make_rec_log())


def predict_day(reserved: list[int], wd: int, menu_pop: int, weather: str, event: bool, end_times: dict,
                weeks: int = 8, mode: str = "자동") -> tuple[list[int], ArrivalModel]:
    am, _ = engine(weeks)
    if mode == "계산" or (mode == "자동" and not am.use_ai) or am.model is None:
        r = np.array(reserved, dtype=float)
        return [int(round(x)) for x in np.maximum(0, r * am.ratio + am.bias)], am
    last = [int(round(x * am.ratio + am.bias)) for x in reserved]
    X = features_for_day(reserved, wd, menu_pop, weather, event, end_times, last)
    return [int(round(x)) for x in am.model.predict(X[FEATURES]).clip(0)], am
