"""시뮬레이터 기본값과 실측 보정값.

기본값은 마송고 학교 정보(612명, 2라인, 12:10~13:00)와 발표에서 쓴 가정(배식 속도 6.2명/분/라인)이다.
`python -m model.calibrate`가 data/real/의 실측·설문으로 artifacts/calibration.json을 만들면 그 값이 기본값을 덮어쓴다.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REAL = ROOT / "data" / "real"
ART = ROOT / "artifacts"

DEFAULTS: dict = {
    # 학교
    "per_grade": [208, 204, 200],
    "lines": 2,
    "lunch_start": "12:10",
    "slots": 10,
    "slot_len": 5,
    "safety": 0.85,
    # 4교시 종료 (요일별, 0=월). 수요일 2학년은 체육이라 늦게 끝난다는 가정
    "end_times": {
        "1": ["12:10", "12:10", "12:10", "12:10", "12:10"],
        "2": ["12:10", "12:10", "12:20", "12:10", "12:10"],
        "3": ["12:05", "12:05", "12:05", "12:05", "12:05"],
    },
    "walk_min": [2.0, 4.0],          # 교실 → 급식실 (분)
    # 배식
    "mu": 6.2,                       # 명/분/라인
    "mu_sd": 0.35,                   # 날마다 흔들림
    "mu_menu_slow": 0.06,            # 손 많이 가는 메뉴(인기 8 이상)면 6% 느려짐
    # 팀
    "team_size_p": [0.12, 0.22, 0.26, 0.22, 0.12, 0.06],   # 1~6명
    "skip_base": 0.04,               # 급식 안 먹음 기본 확률
    # 도착 습관: 4교시 종료 + 걷는 시간 + 최소 지연 + 감마분포 지연(분). 팀마다 평균이 다르다
    "delay_mean": 12.0,
    "base_delay": 4.0,               # 손 씻기 · 줄 서기 전 최소 지연
    "menu_rush": 0.9,                # 인기 메뉴 1점당 평균 지연 감소(분)
    # 앱
    "adopt_start": 0.35,             # 학기 초 앱 사용 팀 비율
    "adopt_end": 0.70,               # 학기 말
    "recurring_share": 0.55,         # 앱 사용 팀 중 정기 예약 팀
    "recurring_cap": 0.70,           # 정원의 70%까지만 정기 예약
    "noshow": 0.08,                  # 예약하고 안 지키는 확률(팀 평균)
    # 추천 수락 (진짜 행동 규칙 — 모델 2가 맞혀야 할 대상)
    "acc_logit": {"intercept": 0.1, "saved": 0.28, "shift": -0.07, "points": 0.55, "msg_신호등형": -0.15,
                  "msg_보상형": 0.35, "menu": -0.12, "team": -0.18, "trait": 1.0},
    # 피드백
    "resp_rate": 0.62,               # 앱 쓰는 팀 대표가 하교 후 답할 확률
    "measure_days": 9,               # 실측 기간 (학기 앞 9일로 둔다)
    "recall_noise": 0.15,            # 실제와 다른 칸을 답할 확률
    # 달력 (2026 2학기)
    "start": "2026-09-01",
    "days": 90,
    "holidays": ["2026-09-24", "2026-09-25", "2026-10-05", "2026-10-09"],
    "events": {"2026-10-19": "시험", "2026-10-20": "시험", "2026-10-21": "시험", "2026-10-22": "시험",
               "2026-11-06": "행사", "2026-12-09": "시험", "2026-12-10": "시험", "2026-12-11": "시험"},
    "rain_p": 0.18,
    "hot_until": "2026-09-20",
    "hot_p": 0.5,
}


def load() -> dict:
    p = dict(DEFAULTS)
    f = ART / "calibration.json"
    if f.exists():
        cal = json.loads(f.read_text(encoding="utf-8"))
        p.update({k: v for k, v in cal.items() if not k.startswith("_")})
        p["_calibrated_from"] = cal.get("_sources", [])
    return p


def hm(t: str) -> int:
    return int(t[:2]) * 60 + int(t[3:5])


def capacity(p: dict, mu: float | None = None) -> int:
    return int((mu or p["mu"]) * p["lines"] * p["slot_len"] * p["safety"])
