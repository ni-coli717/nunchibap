"""실측으로 검증 — 발표의 "점심시간에 아무도 측정하지 않아도 충분히 정확합니다" 장면.

  1) 피드백 추정 vs 실측 유입: feedback.csv(응답) ÷ 응답률  vs  queue_counts.csv로 센 칸별 유입
  2) 대기행렬 계산 vs 실제 대기: wait_samples.csv의 실제 대기  vs  같은 시각 줄 길이 ÷ (μ × 라인)
실측 파일이 없으면 시뮬레이션의 실측 기간(앞 9일)으로 같은 검증을 해 둔다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from .calibrate import _read, mu_from_serving


def _slot(t: str, p: dict) -> int:
    return (C.hm(t) - C.hm(p["lunch_start"])) // p["slot_len"]


def measured_inflow(qc: pd.DataFrame, mu: float, p: dict) -> pd.DataFrame:
    rows = []
    L, start = p["slot_len"], C.hm(p["lunch_start"])
    for d, g in qc.groupby("date"):
        q = g.groupby("time")["queue_len"].sum()
        for s in range(p["slots"]):
            t0 = f"{(start + s * L) // 60:02d}:{(start + s * L) % 60:02d}"
            t1 = f"{(start + (s + 1) * L) // 60:02d}:{(start + (s + 1) * L) % 60:02d}"
            if t0 in q and t1 in q:
                served = min(mu * p["lines"] * L, q[t0] + max(0, q[t1] - q[t0]) + mu * p["lines"] * L)
                rows.append({"date": d, "slot": s, "measured": max(0.0, q[t1] - q[t0] + served)})
    return pd.DataFrame(rows)


def run(sim: dict | None = None, p: dict | None = None) -> dict:
    p = p or C.load()
    out: dict = {"source": None}
    sv, qc, fb, ws = _read("serving.csv"), _read("queue_counts.csv"), _read("feedback.csv"), _read("wait_samples.csv")
    mu = mu_from_serving(sv) if sv is not None and len(sv) else p["mu"]
    if qc is not None and len(qc) and fb is not None and len(fb):
        out["source"] = "실측"
        meas = measured_inflow(qc, mu, p)
        teams_file = C.REAL / "pilot_teams.txt"
        n_teams = int(teams_file.read_text().strip()) if teams_file.exists() else None
        fb = fb.assign(slot=fb["slot_time"].map(lambda t: _slot(t, p)))
        rows = []
        for d, g in fb.groupby("date"):
            r = g.shape[0] / n_teams if n_teams else np.nan
            est = g.groupby("slot")["team_size"].sum() / r
            for s, v in est.items():
                rows.append({"date": d, "slot": int(s), "fb_est": float(v)})
        cmp_ = pd.DataFrame(rows).merge(meas, on=["date", "slot"])
        if len(cmp_):
            out["fb_vs_measured"] = {"n": len(cmp_), "mae": round(float((cmp_["fb_est"] - cmp_["measured"]).abs().mean()), 2),
                                     "rel_err": round(float((cmp_["fb_est"] - cmp_["measured"]).abs().sum() / cmp_["measured"].sum()), 3)}
    elif sim is not None:
        out["source"] = "시뮬레이션 실측 기간 (실측 파일 없음)"
        s = sim["slots"]
        days = sorted(s["date"].unique())[p["measure_days"]:]
        x = s[s["date"].isin(days)]
        out["fb_vs_measured"] = {"n": len(x), "mae": round(float((x["actual_fb"] - x["actual_true"]).abs().mean()), 2),
                                 "rel_err": round(float((x["actual_fb"] - x["actual_true"]).abs().sum() / x["actual_true"].sum()), 3)}
        peak = x.loc[x.groupby("date")["actual_true"].idxmax()]
        out["peak_example"] = {"measured": round(float(peak["actual_true"].mean()), 1), "fb_est": round(float(peak["actual_fb"].mean()), 1)}
    if ws is not None and len(ws) and qc is not None and len(qc):
        q = qc.groupby(["date", "time"])["queue_len"].sum()
        errs = []
        for _, r in ws.iterrows():
            jm = C.hm(r["join_time"][:5])
            t = f"{(jm // 5 * 5) // 60:02d}:{(jm // 5 * 5) % 60:02d}"
            if (r["date"], t) in q:
                pred = q[(r["date"], t)] / (mu * p["lines"])
                real = (pd.to_datetime(r["served_time"]) - pd.to_datetime(r["join_time"])).total_seconds() / 60
                errs.append(abs(pred - real))
        if errs:
            out["queue_formula"] = {"n": len(errs), "mae_min": round(float(np.mean(errs)), 2)}
    out["mu"] = round(mu, 2)
    return out
