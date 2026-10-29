"""눈치밥 nunchi-bap — 공용 데이터 모델 · 대기행렬 계산 · 저장 (Streamlit 버전)

학생 앱(app.py)과 관리자 웹(pages/)이 같은 JSON 파일을 공유한다.
Streamlit Community Cloud에서는 앱 인스턴스 한 대가 파일을 들고 있으므로
노트북과 휴대폰에서 같은 데이터가 보인다. (재배포하면 초기화됨)
"""
from __future__ import annotations

import json
import os
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

DATA_DIR = Path(os.environ.get("NB_DATA_DIR", Path(__file__).parent / "data"))
DATA_FILE = DATA_DIR / "state.json"
_LOCK = threading.Lock()

WD = ["월", "화", "수", "목", "금", "토", "일"]  # date.weekday() 기준
WD_EN = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
KIND_WORD = {"f": "여유", "m": "보통", "b": "꽉 참", "y": "내 예약"}
BUCKETS = {"0~3분": 1.5, "3~6분": 4.5, "6~10분": 8.0, "10분+": 12.0}


def defaults() -> dict:
    return {
        "settings": {
            "schoolName": "마송고등학교", "region": "경기",
            "domains": [{"name": "masong.hs.kr", "ok": True}],
            "lines": 2, "slotLen": 5, "factor": 0.85, "mu": 6.2, "muHistory": [],
            "lunchStart": "12:10", "lunchEnd": "13:00",
            "deadline": "07:30", "ratio": 0.7, "mode": "수거",
            "penalty": True, "waitlist": True, "examPause": True, "msg": "숫자형",
            "students": 612, "perGrade": [208, 204, 200],
            "endTimes": {"1": "12:10", "2": "12:10", "3": "12:05"},
            "menu": {"name": "치킨마요덮밥", "pop": 9},
            "weather": "맑음", "event": False,
            "aiWeeks": 8, "aiMode": "자동", "responseRate": 0.64,
            "savedAt": None,
        },
        "user": None,
        "team": {"code": "MS-4K2P", "members": []},
        "bookings": {},
        "recurring": {"period": "1개월", "days": {
            "월": ["12:15", "12:35", "12:45"], "화": ["12:15", "12:35", "12:45"], "수": ["12:40", "12:45", "12:50"],
            "목": ["12:15", "12:35", "12:45"], "금": ["12:15", "12:35", "12:45"]}},
        "waitlist": {},
        "feedback": [],
        "recLog": [],
        "requests": [],
    }


# ---------- 저장 ----------
def load() -> dict:
    with _LOCK:
        try:
            if DATA_FILE.exists():
                st = json.loads(DATA_FILE.read_text(encoding="utf-8"))
                d = defaults()
                for k, v in d.items():
                    st.setdefault(k, v)
                for k, v in d["settings"].items():
                    st["settings"].setdefault(k, v)
                return st
        except Exception:
            pass
        return defaults()


def save(st: dict) -> None:
    with _LOCK:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = DATA_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(DATA_FILE)


def reset() -> dict:
    st = defaults()
    save(st)
    return st


# ---------- 시간 ----------
def mins(t: str) -> int:
    return int(t[:2]) * 60 + int(t[3:5])


def hhmm(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def date_key(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def fmt_date(d: date) -> str:
    return f"{d.month}.{d.day:02d} {WD_EN[d.weekday()]}"


def fmt_date_ko(d: date) -> str:
    return f"{d.month}월 {d.day}일 {WD[d.weekday()]}"


def now_hhmm(now: datetime | None = None) -> str:
    now = now or datetime.now()
    return now.strftime("%H:%M")


def target_date(st: dict, now: datetime | None = None) -> date:
    """예약 대상 급식일: 마감 전이면 오늘, 지났으면 다음 등교일."""
    now = now or datetime.now()
    d = now.date()
    if mins(now_hhmm(now)) >= mins(st["settings"]["deadline"]):
        d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def is_today(d: date, now: datetime | None = None) -> bool:
    now = now or datetime.now()
    return d == now.date()


def deadline_left(st: dict, now: datetime | None = None) -> int:
    now = now or datetime.now()
    return mins(st["settings"]["deadline"]) - mins(now_hhmm(now))


# ---------- 슬롯과 수요 ----------
def slots(st: dict) -> list[str]:
    s = st["settings"]
    out, m = [], mins(s["lunchStart"])
    while m < mins(s["lunchEnd"]) and len(out) < 12:
        out.append(hhmm(m))
        m += int(s["slotLen"])
    return out


def capacity(st: dict) -> int:
    s = st["settings"]
    return int(s["mu"] * s["lines"] * s["slotLen"] * s["factor"])


def base_demand(st: dict, d: date) -> list[int]:
    """다른 학생들의 예약 수요 (시연용 기준값, 요일별로 조금씩 다르다)."""
    shape = [0.32, 0.72, 1.0, 0.9, 0.76, 0.5, 0.36, 0.25, 0.17, 0.1, 0.06, 0.04]
    scale = [52, 56, 50, 54, 58, 56, 56][d.weekday()]
    boost = 1 + ((st["settings"]["menu"].get("pop", 7)) - 7) * 0.02
    return [round(shape[i] * scale * boost) for i in range(len(slots(st)))]


def team_count(st: dict) -> int:
    n = sum(1 for m in st["team"]["members"] if m.get("present", True))
    return max(1, n)


def predict(st: dict, d: date, arrivals: list[int]) -> list[int]:
    """AI ① 칸별 유입 인원 (예약 안 한 학생 포함). 데이터가 부족하거나 AI가 기본 통계보다 못하면 계산으로 돌린다."""
    s = st["settings"]
    try:
        import nb_ai
        preds, _ = nb_ai.predict_day(arrivals, d.weekday(), int(s["menu"].get("pop", 7)), s.get("weather", "맑음"),
                                     bool(s.get("event")), s["endTimes"], int(s.get("aiWeeks", 8)), s.get("aiMode", "자동"))
        return preds
    except Exception:  # scikit-learn이 없어도 앱은 돌아가야 한다
        return [round(a * 1.08 + (2 if i < 5 else 1)) for i, a in enumerate(arrivals)]


def engine_label(st: dict) -> str:
    s = st["settings"]
    try:
        import nb_ai
        am, _ = nb_ai.engine(int(s.get("aiWeeks", 8)))
        on = s.get("aiMode") == "AI" or (s.get("aiMode", "자동") == "자동" and am.use_ai)
        return "AI 예측" if on and am.model is not None else "계산 예측"
    except Exception:
        return "계산 예측"


def accept_prob(st: dict, saved: float, shift: float, team: int) -> float | None:
    """AI ② 추천 수락 확률."""
    try:
        import nb_ai
        _, acc = nb_ai.engine(int(st["settings"].get("aiWeeks", 8)))
        return acc.prob(saved, shift, team, st["settings"].get("msg", "숫자형"))
    except Exception:
        return None


def queue(st: dict, d: date, booking: dict | None | str = "auto") -> list[dict]:
    """슬롯별 유입과 대기행렬 계산. wait = (누적 대기 + 이 칸 도착) ÷ 분당 처리."""
    s = st["settings"]
    sl, cap, demand = slots(st), capacity(st), base_demand(st, d)
    mine = st["bookings"].get(date_key(d)) if booking == "auto" else booking
    ts = team_count(st)
    rate = s["mu"] * s["lines"]
    arr = [demand[i] + (ts if mine and mine.get("slot") == t else 0) for i, t in enumerate(sl)]
    preds = predict(st, d, arr)
    carry, rows = 0.0, []
    for i, t in enumerate(sl):
        arrivals = arr[i]
        pred = preds[i]
        in_queue = carry + pred
        wait = max(0, round(in_queue / rate))
        served = min(in_queue, rate * s["slotLen"])
        carry = max(0.0, in_queue - served)
        left = cap - arrivals
        if left <= 0 or wait >= max(6, s["slotLen"] + 1):
            kind = "b"
        elif left <= cap * 0.3 or wait >= 4:
            kind = "m"
        else:
            kind = "f"
        rows.append({"time": t, "arrivals": arrivals, "pred": pred, "wait": wait, "left": max(0, left), "cap": cap, "kind": kind})
    return rows


def slot_row(rows: list[dict], t: str) -> dict | None:
    return next((r for r in rows if r["time"] == t), None)


def recommend(st: dict, d: date, picked: str) -> list[dict]:
    rows = queue(st, d, booking=None)
    ts, pm = team_count(st), mins(picked)
    cands = [r for r in rows if r["time"] != picked and r["left"] >= ts and r["kind"] != "b"]
    cands.sort(key=lambda r: r["wait"] * 2 + abs(mins(r["time"]) - pm) / 5)
    out = []
    pw = next((r["wait"] for r in rows if r["time"] == picked), 0)
    for i, r in enumerate(cands[:3]):
        pa = accept_prob(st, max(0, pw - r["wait"]), abs(mins(r["time"]) - pm), ts)
        out.append({"time": r["time"], "wait": r["wait"], "left": r["left"], "pa": pa,
                    "tag": "추천" if i == 0 else ("여유" if r["kind"] == "f" else "보통"), "pt": 10 if i == 0 else 5})
    return out


# ---------- 팀 ----------
def ensure_team(st: dict) -> None:
    if not st["team"]["members"] and st["user"]:
        u = st["user"]
        me = u.get("name") or "나"
        st["team"]["members"] = [
            {"name": me, "cls": f"{u['grade']}-{u['cls']}", "lead": True, "present": True},
            {"name": "김민수", "cls": "2-3", "lead": False, "present": True},
            {"name": "이지호", "cls": "2-5", "lead": False, "present": True},
            {"name": "최서연", "cls": "2-3", "lead": False, "present": True},
        ]


# ---------- 예약 ----------
def current_booking(st: dict, d: date) -> dict | None:
    key = date_key(d)
    if key in st["bookings"]:
        return st["bookings"][key]
    prefs = st["recurring"]["days"].get(WD[d.weekday()], [])
    if prefs:
        rows, ts = queue(st, d, booking=None), team_count(st)
        for p in prefs:
            r = slot_row(rows, p)
            if r and r["left"] >= ts:
                b = {"slot": p, "kind": "정기 예약", "teamSize": ts, "auto": True}
                st["bookings"][key] = b
                save(st)
                return b
    return None


def book(st: dict, d: date, slot: str, kind: str) -> dict:
    key = date_key(d)
    b = {"slot": slot, "kind": kind, "teamSize": team_count(st), "at": datetime.now().isoformat()}
    st["bookings"][key] = b
    st["waitlist"].pop(key, None)
    save(st)
    return b


# ---------- 피드백과 자동 보정 ----------
def send_feedback(st: dict, d: date, fb: dict) -> dict:
    s, key = st["settings"], date_key(d)
    b = st["bookings"].get(key) or current_booking(st, d)
    rows = queue(st, d)
    r = slot_row(rows, b["slot"]) if b else None
    expected = r["wait"] if r else 0
    reported = BUCKETS.get(fb.get("bucket"), expected)
    rec = {"date": key, "slot": b["slot"] if b else None, "ate": fb.get("ate"), "timing": fb.get("timing"),
           "bucket": fb.get("bucket"), "present": fb.get("present", []), "wait": reported, "expected": expected,
           "at": datetime.now().isoformat()}
    st["feedback"] = [f for f in st["feedback"] if f["date"] != key] + [rec]
    # μ오늘 = 0.8·μ어제 + 0.2·μ추정 — 대기가 예상보다 짧으면 배식이 더 빠른 것
    if fb.get("ate") == "예" and expected > 0 and reported > 0:
        est = max(3.0, min(12.0, s["mu"] * (expected / reported)))
        mu = round(0.8 * s["mu"] + 0.2 * est, 2)
        s["muHistory"] = (s.get("muHistory") or [])[-29:] + [{"date": key, "from": s["mu"], "to": mu}]
        s["mu"] = mu
    st["user"]["points"] = st["user"].get("points", 0) + 5
    save(st)
    return rec


def week_records(st: dict, now: datetime | None = None) -> list[dict]:
    now = now or datetime.now()
    out, d = [], now.date()
    while len(out) < 5:
        if d.weekday() < 5:
            f = next((x for x in st["feedback"] if x["date"] == date_key(d)), None)
            out.insert(0, {"day": WD[d.weekday()], "wait": f["wait"] if f else None, "expected": f["expected"] if f else None})
        d -= timedelta(days=1)
    return out


def class_board(st: dict, d: date, cls: str) -> list[tuple]:
    seed = {
        "2학년 1반": [("12:10", "B팀 · 김하늘 외 2명"), ("12:15", "D팀 · 정우진 외 4명"), ("12:40", "A팀 · 이도윤 외 3명"), ("12:50", "C팀 · 한지우 외 1명")],
        "2학년 3반": [("12:10", "B팀 · 김하늘 외 2명"), ("12:15", "D팀 · 정우진 외 4명"), ("12:35", "C팀 · 송민아 외 1명"), ("12:40", "E팀 · 오세훈 외 2명"), ("12:45", "F팀 · 한지우 외 3명")],
        "2학년 5반": [("12:20", "A팀 · 이지호 외 3명"), ("12:30", "B팀 · 문서윤 외 2명"), ("12:45", "C팀 · 강하준 외 4명")],
    }
    rows = [(t, n, False) for t, n in seed.get(cls, [])]
    u = st.get("user")
    if u and f"{u['grade']}학년 {u['cls']}반" == cls:
        b = current_booking(st, d)
        if b:
            rows.append((b["slot"], f"우리 팀 · {u.get('name') or '나'} 외 {team_count(st) - 1}명", True))
    rows.sort(key=lambda r: mins(r[0]))
    return rows
