"""학교 한 학기를 팀 단위로 흘려 보내는 시뮬레이터.

실측 기간(약 9일)만으로는 모델 1(약 900행)과 모델 2를 학습할 수 없어서,
실측으로 보정한 시뮬레이터로 한 학기 분량을 만들고 실측으로 검증한다 (발표 문구 그대로).

하루 흐름 (휴대폰 수거 모드):
  07:30 전  정기 예약 자동 배정 → 당일 아침 예약 → 꽉 찬 칸이면 추천 → 수락/거절   ← 추천 기록 = 모델 2 데이터
  점심       예약한 팀은 예약 칸에(가끔 노쇼), 예약 안 한 팀은 습관대로 도착 → 대기행렬
  하교 후    앱 쓰는 팀 대표 일부가 피드백 (먹었는지, 몇 시 칸, 대기 구간)      ← 응답 ÷ 응답률 = 모델 1 정답

출력
  slots: 날짜 × 칸 한 행 (모델 1 입력 피처 + 정답 2종: 피드백 추정치 actual_fb, 진짜 인원 actual_true)
  recs : 추천 한 번 = 한 행 (모델 2 입력 피처 + accepted)
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

from . import config as C

BUCKETS = [(0, 3, "0~3분"), (3, 6, "3~6분"), (6, 10, "6~10분"), (10, 99, "10분+")]
MSGS = ["숫자형", "신호등형", "보상형"]


@dataclass
class Team:
    tid: int
    size: int
    grade: str
    delay_scale: float      # 도착 습관 (작을수록 빨리 감)
    trait: float            # 추천을 잘 받아들이는 성향 (정규분포)
    noshow: float           # 예약 안 지킬 확률
    adopt_rank: float       # 앱을 쓰기 시작하는 순서 (작을수록 먼저)
    recurring: bool
    prefs: list[int]        # 정기 예약 희망 1~3순위 칸 (요일 무관 단순화)


def school_days(p: dict) -> list[date]:
    d, out = date.fromisoformat(p["start"]), []
    hol = set(p["holidays"])
    while len(out) < p["days"]:
        if d.weekday() < 5 and d.isoformat() not in hol:
            out.append(d)
        d += timedelta(days=1)
    return out


def make_teams(p: dict, rng: np.random.Generator) -> list[Team]:
    teams, tid = [], 0
    for g, n in zip(["1", "2", "3"], p["per_grade"]):
        left = n
        while left > 0:
            size = int(min(left, rng.choice(np.arange(1, 7), p=p["team_size_p"])))
            scale = float(rng.lognormal(math.log(p["delay_mean"]), 0.45))
            pref1 = int(np.clip(round(scale / p["slot_len"]), 0, p["slots"] - 1))
            prefs = [pref1, min(p["slots"] - 1, pref1 + 1), max(0, pref1 - 1)]
            teams.append(Team(tid, size, g, scale, float(rng.normal(0, 1)), float(np.clip(rng.normal(p["noshow"], 0.05), 0, 0.4)),
                              float(rng.random()), bool(rng.random() < p["recurring_share"]), prefs))
            left -= size
            tid += 1
    return teams


def queue_waits(arr: np.ndarray, rate: float, slot_len: int) -> tuple[np.ndarray, np.ndarray]:
    """칸별 평균 대기(분)와 칸 마지막 사람 대기(분). rate = 분당 처리 인원(전체 라인)."""
    carry, avg, last = 0.0, [], []
    for a in arr:
        avg.append((carry + a / 2) / rate if a else carry / rate)
        last.append((carry + a) / rate)
        carry = max(0.0, carry + a - rate * slot_len)
    return np.array(avg), np.array(last)


def bucket_of(w: float) -> str:
    return next(b for lo, hi, b in BUCKETS if lo <= w < hi)


def simulate(p: dict | None = None, seed: int = 0) -> dict[str, pd.DataFrame]:
    p = p or C.load()
    rng = np.random.default_rng(seed)
    teams = make_teams(p, rng)
    days = school_days(p)
    S, L = p["slots"], p["slot_len"]
    start = C.hm(p["lunch_start"])
    n_students = sum(p["per_grade"])
    slot_rows, rec_rows, fb_rows = [], [], []
    last_week: dict[tuple[int, int], float] = {}
    team_hist: dict[int, list[int]] = {t.tid: [] for t in teams}
    hot_until = date.fromisoformat(p["hot_until"])
    measure_days = p["measure_days"]          # 앞 며칠은 실측 기간: 예약 안 한 학생의 도착 모양을 잰다
    non_shape_acc = np.zeros(S)

    for di, d in enumerate(days):
        wd = d.weekday()
        frac = di / max(1, len(days) - 1)
        adopt = p["adopt_start"] + (p["adopt_end"] - p["adopt_start"]) * frac
        menu = int(rng.integers(2, 11))
        rain = int(rng.random() < p["rain_p"])
        hot = int(d <= hot_until and rng.random() < p["hot_p"])
        ev = p["events"].get(d.isoformat(), "")
        event = int(bool(ev))
        mu = max(4.0, rng.normal(p["mu"], p["mu_sd"]) * (1 - p["mu_menu_slow"] * (menu >= 8)))
        rate = mu * p["lines"]
        cap = C.capacity(p, mu=p["mu"])  # 앱은 오늘 배식 속도를 모른다 → 기준값으로 정원 계산
        ends = {g: C.hm(p["end_times"][g][wd]) for g in ["1", "2", "3"]}

        # 1) 오늘 먹는 팀과 '원래 가고 싶은 칸'
        today = []
        for t in teams:
            skip = p["skip_base"] + 0.03 * (menu <= 3) - 0.02 * rain + 0.10 * (ev == "시험")
            if rng.random() < skip:
                continue
            walk = rng.uniform(*p["walk_min"])
            delay = (p["base_delay"] + rng.gamma(2.0, t.delay_scale / 2) - p["menu_rush"] * (menu - 6) * 0.5
                     - 1.5 * rain + 1.0 * hot)
            if ev == "시험":
                delay *= 0.4      # 시험 날은 빨리 먹고 들어감
            if ev == "행사":
                delay += rng.uniform(0, 10)
            arrive = ends[t.grade] + walk + max(0.0, delay)
            want = int(np.clip((arrive - start) // L, 0, S - 1))
            uses = t.adopt_rank < adopt
            today.append((t, want, uses))

        # 2) 아침 예약: 정기 예약 먼저(정원 70%), 그다음 당일 예약 + 추천
        booked = np.zeros(S)
        recurring_n = np.zeros(S)
        res = {}
        walk_pred = np.zeros(S)
        for t, want, uses in today:
            if not uses:
                walk_pred[want] += t.size
        rec_cap = p["recurring_cap"] * cap
        for t, want, uses in today:
            if uses and t.recurring and not event:
                for s_ in t.prefs:
                    if recurring_n[s_] + t.size <= rec_cap:
                        res[t.tid] = s_
                        recurring_n[s_] += t.size
                        booked[s_] += t.size
                        break
        order = [x for x in today if x[2] and x[0].tid not in res]
        rng.shuffle(order)
        for t, want, uses in order:
            load = booked + walk_pred
            if load[want] + t.size <= cap:
                res[t.tid] = want
                booked[want] += t.size
                continue
            _, last = queue_waits(load, rate=p["mu"] * p["lines"], slot_len=L)
            cands = [s_ for s_ in range(S) if s_ != want and load[s_] + t.size <= cap]
            if not cands:
                res[t.tid] = want
                booked[want] += t.size
                continue
            c = min(cands, key=lambda s_: last[s_] * 2 + abs(s_ - want))
            saved = float(max(0.0, last[want] - last[c]))
            shift = abs(c - want) * L
            msg = MSGS[int(rng.integers(0, 3))]        # A/B 실험: 추천마다 메시지 형태와 포인트를 무작위로
            points_on = int(rng.random() < 0.5)
            past = team_hist[t.tid]
            past_rate = (sum(past) + 1) / (len(past) + 2)   # 라플라스 보정
            a = p["acc_logit"]
            z = (a["intercept"] + a["saved"] * saved + a["shift"] * shift + a["points"] * points_on
                 + a.get(f"msg_{msg}", 0.0) + a["menu"] * (menu - 6) + a["team"] * (t.size - 1) + a["trait"] * t.trait)
            acc = int(rng.random() < 1 / (1 + math.exp(-z)))
            rec_rows.append({"date": d.isoformat(), "team": t.tid, "want_slot": want, "rec_slot": c, "shift_min": shift,
                             "saved_min": round(saved, 1), "points": points_on, "msg": msg, "menu_pop": menu,
                             "team_size": t.size, "team_past_rate": round(past_rate, 3), "accepted": acc})
            team_hist[t.tid].append(acc)
            res[t.tid] = c if acc else want
            booked[res[t.tid]] += t.size

        # 3) 점심: 실제 도착
        arr = np.zeros(S)
        went = {}
        for t, want, uses in today:
            if t.tid in res:
                s_ = res[t.tid] if rng.random() > t.noshow else int(np.clip(want + rng.integers(-1, 2), 0, S - 1))
            else:
                s_ = want
            went[t.tid] = s_
            arr[s_] += t.size
        avg_w, last_w = queue_waits(arr, rate, L)

        # 실측 기간: 예약 안 한(앱 안 쓰는) 학생 도착 모양을 직접 센다
        non_arr = np.zeros(S)
        for t, want, uses in today:
            if not uses:
                non_arr[went[t.tid]] += t.size
        if di < measure_days and non_arr.sum():
            non_shape_acc += non_arr / non_arr.sum()

        # 4) 하교 후 피드백 (앱 쓰는 팀 대표만, 일부만 답함)
        resp_p = p["resp_rate"] - 0.08 * (wd == 4)
        fb_people = np.zeros(S)
        answered = 0
        users_signed = sum(t.size for t in teams if t.adopt_rank < adopt)
        teams_answered = 0
        for t, want, uses in today:
            if not uses or rng.random() > resp_p:
                continue
            s_true = went[t.tid]
            s_rep = int(np.clip(s_true + rng.choice([-1, 1]), 0, S - 1)) if rng.random() < p["recall_noise"] else s_true
            w = max(0.0, avg_w[s_true] + rng.normal(0, 1.2))
            fb_people[s_rep] += t.size
            answered += t.size
            teams_answered += 1
            fb_rows.append({"date": d.isoformat(), "team": t.tid, "slot": s_rep, "team_size": t.size,
                            "as_reserved": int(t.tid in res and went[t.tid] == res[t.tid]), "bucket": bucket_of(w)})
        # 정답 추정 = 앱 사용자(응답 ÷ 응답률) + 앱 안 쓰는 학생(인원 × 실측 기간 도착 모양)
        r_hat = teams_answered / max(1, sum(1 for t in teams if t.adopt_rank < adopt)) if answered else np.nan
        shape = non_shape_acc / non_shape_acc.sum() if non_shape_acc.sum() else np.full(S, 1 / S)
        non_n = (n_students - users_signed) * (1 - p["skip_base"])
        est = fb_people / r_hat + non_n * shape if answered else np.full(S, np.nan)

        for s_ in range(S):
            key = (wd, s_)
            slot_rows.append({
                "date": d.isoformat(), "wd": wd, "slot": s_, "time": f"{(start + s_ * L) // 60:02d}:{(start + s_ * L) % 60:02d}",
                "reserved": int(booked[s_]), "recurring": int(recurring_n[s_]),
                "reserved_prev": int(booked[s_ - 1]) if s_ > 0 else 0, "reserved_next": int(booked[s_ + 1]) if s_ < S - 1 else 0,
                "menu_pop": menu, "rain": rain, "hot": hot, "event": event, "exam": int(ev == "시험"),
                "grades_out": sum(1 for g in ends.values() if g <= start + s_ * L),
                "adopt": round(adopt, 3), "last_week": last_week.get(key, np.nan),
                "actual_fb": round(float(est[s_]), 1) if answered else np.nan, "actual_true": int(arr[s_]),
                "wait_avg": round(float(avg_w[s_]), 2), "wait_last": round(float(last_w[s_]), 2), "mu_day": round(mu, 2),
            })
            last_week[key] = float(est[s_]) if answered else last_week.get(key, np.nan)

    slots = pd.DataFrame(slot_rows)
    slots["last_week"] = slots["last_week"].fillna(slots["reserved"] * 1.1)
    return {"slots": slots, "recs": pd.DataFrame(rec_rows), "feedback": pd.DataFrame(fb_rows),
            "teams": pd.DataFrame([t.__dict__ for t in teams])}


if __name__ == "__main__":
    out = simulate()
    for k, v in out.items():
        print(k, v.shape)
    print(out["slots"].groupby("slot")[["reserved", "actual_true", "actual_fb", "wait_avg"]].mean().round(1))
