"""data/real/의 실측 · 설문으로 시뮬레이터를 보정해 artifacts/calibration.json을 만든다.

  serving.csv       → 배식 속도 μ
  queue_counts.csv  → 칸별 유입 인원 모양 → 도착 지연(delay_mean, base_delay) 격자 탐색
  survey.csv        → 팀 크기 분포, 체감 대기 분포(도착 모양이 없을 때 보정 목표), 추천 수락 곡선
"""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from . import config as C

WAIT_BUCKETS = {"5분 미만": 0, "5~10분": 1, "10분 이상": 2}


def _read(name: str) -> pd.DataFrame | None:
    f = C.REAL / name
    return pd.read_csv(f) if f.exists() else None


def mu_from_serving(df: pd.DataFrame) -> float:
    return float(df["people"].sum() / (df["seconds"].sum() / 60))


def inflow_from_queue(df: pd.DataFrame, mu: float, p: dict) -> np.ndarray:
    """칸 유입 ≈ (다음 줄 길이 − 지금 줄 길이) + 5분간 배식 인원. 날짜별로 구해 평균 모양을 돌려준다."""
    L, S, start = p["slot_len"], p["slots"], C.hm(p["lunch_start"])
    shapes = []
    for _, g in df.groupby("date"):
        q = g.groupby("time")["queue_len"].sum()
        times = [f"{(start + i * L) // 60:02d}:{(start + i * L) % 60:02d}" for i in range(S + 1)]
        qs = np.array([q.get(t, np.nan) for t in times], dtype=float)
        if np.isnan(qs).all():
            continue
        qs = np.nan_to_num(qs, nan=0.0)
        served = mu * p["lines"] * L
        inflow = np.maximum(0, qs[1:] - qs[:-1] + np.minimum(served, qs[:-1] + np.maximum(0, qs[1:] - qs[:-1]) + served))
        if inflow.sum():
            shapes.append(inflow / inflow.sum())
    return np.mean(shapes, axis=0) if shapes else np.array([])


def fit_arrival(p: dict, target_shape: np.ndarray | None, target_wait: np.ndarray | None) -> dict:
    from .simulate import simulate
    best, best_err = None, math.inf
    for dm in [6, 8, 10, 12, 14, 16]:
        for bd in [0, 2, 4, 6]:
            q = dict(p, delay_mean=dm, base_delay=bd, days=12)
            o = simulate(q, seed=1)["slots"]
            err = 0.0
            if target_shape is not None and len(target_shape):
                sh = o.groupby("slot")["actual_true"].mean().to_numpy()
                err += float(np.abs(sh / sh.sum() - target_shape).sum())
            if target_wait is not None:
                w = o["wait_avg"].to_numpy()
                n = o["actual_true"].to_numpy()
                share = np.array([n[w < 5].sum(), n[(w >= 5) & (w < 10)].sum(), n[w >= 10].sum()]) / n.sum()
                err += float(np.abs(share - target_wait).sum()) * (0.5 if target_shape is not None and len(target_shape) else 1)
            if err < best_err:
                best, best_err = {"delay_mean": dm, "base_delay": bd}, err
    best["_fit_error"] = round(best_err, 3)
    return best


def accept_from_survey(df: pd.DataFrame, base: dict) -> dict:
    """'몇 분 덜 기다리면 바꿀래?' → 절약 분별 수락 비율 → 로지스틱 절편·기울기 (이동 10분 기준)."""
    m = {"5분": 5, "10분": 10, "15분": 15}
    need = df["switch_if_saved"].map(m)
    xs, ys = [], []
    for saved in [5, 10, 15]:
        share = float(((need <= saved) & need.notna()).mean())
        share = min(max(share, 0.02), 0.98)
        xs.append(saved)
        ys.append(math.log(share / (1 - share)))
    slope, inter = np.polyfit(xs, ys, 1)
    a = dict(base)
    a["saved"] = round(float(slope), 3)
    a["intercept"] = round(float(inter - a["shift"] * 10), 3)
    return a


def run() -> dict:
    p = C.DEFAULTS.copy()
    cal, src = {}, []
    sv = _read("serving.csv")
    if sv is not None and len(sv):
        cal["mu"] = round(mu_from_serving(sv), 2)
        src.append(f"serving.csv ({len(sv)}줄) → μ {cal['mu']}")
    mu = cal.get("mu", p["mu"])
    shape = None
    qc = _read("queue_counts.csv")
    if qc is not None and len(qc):
        shape = inflow_from_queue(qc, mu, p)
        if len(shape):
            cal["_measured_shape"] = [round(float(x), 4) for x in shape]
            src.append(f"queue_counts.csv ({qc['date'].nunique()}일) → 칸별 유입 모양")
    wait_target = None
    sy = _read("survey.csv")
    if sy is not None and len(sy):
        ts = sy["team_size"].clip(1, 6).round().astype(int).value_counts(normalize=True)
        cal["team_size_p"] = [round(float(ts.get(i, 0.0)), 4) for i in range(1, 7)]
        s_ = sum(cal["team_size_p"])
        cal["team_size_p"] = [x / s_ for x in cal["team_size_p"]]
        wb = sy["wait_bucket"].map(WAIT_BUCKETS).dropna()
        if len(wb):
            wait_target = np.bincount(wb.astype(int), minlength=3) / len(wb)
            cal["_survey_wait_share"] = [round(float(x), 3) for x in wait_target]
        if "switch_if_saved" in sy:
            cal["acc_logit"] = accept_from_survey(sy, p["acc_logit"])
        src.append(f"survey.csv ({len(sy)}명) → 팀 크기, 체감 대기, 수락 곡선")
    if shape is not None or wait_target is not None:
        cal.update(fit_arrival(dict(p, **{k: v for k, v in cal.items() if not k.startswith("_")}), shape, wait_target))
        src.append(f"도착 지연 격자 탐색 → delay_mean {cal['delay_mean']}, base_delay {cal['base_delay']}")
    cal["_sources"] = src
    C.ART.mkdir(parents=True, exist_ok=True)
    f = C.ART / "calibration.json"
    if src:
        f.write_text(json.dumps(cal, ensure_ascii=False, indent=1), encoding="utf-8")
    elif f.exists():
        f.unlink()
    return cal


if __name__ == "__main__":
    out = run()
    print(json.dumps(out, ensure_ascii=False, indent=1) if out.get("_sources") else "실측 파일이 없어서 기본값(가정)을 써요")
