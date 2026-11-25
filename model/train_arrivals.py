"""모델 1: 칸별 유입 인원 예측 — "내일 12:30~12:35에 실제로 몇 명이 줄을 설까?"

한 행 = 날짜 × 5분 칸. 정답 = 하교 후 피드백으로 추정한 인원(actual_fb). 진짜 인원(actual_true)은 평가에만 쓴다.
비교 모델 (투르쿠대 Flavoria 연구와 같은 구성): 기본 통계(예약 × 비율) · 선형회귀 · 랜덤포레스트 · XGBoost
분할: 앞 9일 = 실측 기간(학습에서 빼고 검증용), 마지막 20일 = 테스트, 나머지 = 학습 (시간 순서 그대로)
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression

from . import config as C
from .simulate import queue_waits

FEATURES = ["wd", "slot", "reserved", "recurring", "reserved_prev", "reserved_next", "menu_pop", "rain", "hot",
            "event", "exam", "grades_out", "last_week", "adopt"]
KO = {"wd": "요일", "slot": "5분 칸", "reserved": "칸 예약 인원", "recurring": "정기 예약 인원", "reserved_prev": "앞 칸 예약",
      "reserved_next": "뒤 칸 예약", "menu_pop": "메뉴 인기도", "rain": "비", "hot": "폭염", "event": "학사일정(시험·행사)",
      "exam": "시험 날", "grades_out": "4교시 끝난 학년 수", "last_week": "지난주 같은 칸 인원", "adopt": "앱 사용률"}
# 시드 5개 평균으로 고른 값 (깊이 4 → 3, 규제 강화: 학습 행이 700개 안팎이라 얕은 나무가 덜 과적합)
XGB_PARAMS = dict(n_estimators=300, learning_rate=0.05, max_depth=3, subsample=0.8, colsample_bytree=0.8,
                  min_child_weight=5, reg_lambda=5.0, random_state=0)


def split(df: pd.DataFrame, p: dict, test_days: int = 20):
    dates = sorted(df["date"].unique())
    meas = set(dates[: p["measure_days"]])
    test = set(dates[-test_days:])
    tr = df[~df["date"].isin(meas | test)]
    te = df[df["date"].isin(test)]
    va = df[df["date"].isin(meas)]
    return tr, te, va


def signal(load: np.ndarray, cap: int) -> np.ndarray:
    r = load / cap
    return np.where(r < 0.7, 0, np.where(r <= 1.0, 1, 2))   # 여유 · 보통 · 꽉 참


def day_eval(df: pd.DataFrame, pred: np.ndarray, p: dict) -> dict:
    """하루 단위로 대기행렬을 돌려 대기시간 · 신호등까지 비교."""
    d = df.assign(pred=pred)
    rate = p["mu"] * p["lines"]
    cap = C.capacity(p)
    w_err, sig_ok, peak_err, n = [], 0, [], 0
    for _, g in d.groupby("date"):
        _, w_true = queue_waits(g["actual_true"].to_numpy(), rate, p["slot_len"])
        _, w_pred = queue_waits(g["pred"].clip(lower=0).to_numpy(), rate, p["slot_len"])
        w_err.extend(np.abs(w_true - w_pred))
        sig_ok += int((signal(g["actual_true"].to_numpy(), cap) == signal(g["pred"].to_numpy(), cap)).sum())
        n += len(g)
        i = int(g["actual_true"].to_numpy().argmax())
        peak_err.append(abs(g["actual_true"].iloc[i] - g["pred"].iloc[i]))
    return {"wait_mae_min": round(float(np.mean(w_err)), 2), "signal_acc": round(sig_ok / n, 3), "peak_mae": round(float(np.mean(peak_err)), 2)}


def fit_all(tr: pd.DataFrame) -> dict:
    y = tr["actual_fb"]
    base = LinearRegression().fit(tr[["reserved"]], y)
    return {
        "기본 통계": (base, ["reserved"]),
        "선형회귀": (LinearRegression().fit(tr[FEATURES], y), FEATURES),
        "랜덤포레스트": (RandomForestRegressor(n_estimators=300, min_samples_leaf=3, random_state=0, n_jobs=-1).fit(tr[FEATURES], y), FEATURES),
        "XGBoost": (xgb.XGBRegressor(**XGB_PARAMS).fit(tr[FEATURES], y), FEATURES),
    }


def run(slots: pd.DataFrame, p: dict | None = None, save: bool = True) -> dict:
    p = p or C.load()
    df = slots.dropna(subset=["actual_fb"]).copy()
    tr, te, va = split(df, p)
    models = fit_all(tr)
    res = {}
    for name, (m, cols) in models.items():
        pr = m.predict(te[cols])
        pv = m.predict(va[cols])
        res[name] = {
            "mae_fb": round(float(np.abs(te["actual_fb"] - pr).mean()), 2),
            "mae_true": round(float(np.abs(te["actual_true"] - pr).mean()), 2),
            "mae_measured": round(float(np.abs(va["actual_true"] - pv).mean()), 2),   # 실측 기간(학습에 안 씀)
            **day_eval(te, pr, p),
        }
    # 최종 모델 고르기: 학습 기간 마지막 10일을 떼어 검증 (테스트 기간은 보지 않음)
    tr_dates = sorted(tr["date"].unique())
    tr2, vl = tr[tr["date"] < tr_dates[-10]], tr[tr["date"] >= tr_dates[-10]]
    sel = {n: float(np.abs(m.predict(vl[c]) - vl["actual_fb"]).mean()) for n, (m, c) in fit_all(tr2).items()}
    best = min(sel, key=sel.get)
    base_mae = res["기본 통계"]["mae_true"]
    for r in res.values():
        r["gain_vs_base"] = round(1 - r["mae_true"] / base_mae, 3)
    xg = models["XGBoost"][0]
    gain = xg.get_booster().get_score(importance_type="gain")
    tot = sum(gain.values()) or 1
    importance = sorted(((KO[k], round(v / tot, 4)) for k, v in gain.items()), key=lambda x: -x[1])
    use_ai = res["XGBoost"]["mae_true"] < base_mae * 0.95
    pred_te = te[["date", "time", "slot", "reserved", "actual_fb", "actual_true"]].assign(
        xgb=np.round(xg.predict(te[FEATURES]), 1), base=np.round(models["기본 통계"][0].predict(te[["reserved"]]), 1))
    out = {"n_train": len(tr), "n_test": len(te), "n_measured": len(va), "train_days": int(tr["date"].nunique()),
           "results": res, "importance": importance, "use_ai": bool(use_ai), "features": FEATURES,
           "selected": best, "selection_mae": {k: round(v, 2) for k, v in sel.items()},
           "base_coef": [round(float(models["기본 통계"][0].coef_[0]), 3), round(float(models["기본 통계"][0].intercept_), 2)]}
    if save:
        C.ART.mkdir(parents=True, exist_ok=True)
        xgb.XGBRegressor(**XGB_PARAMS).fit(df[~df["date"].isin(va["date"])][FEATURES],
                                           df[~df["date"].isin(va["date"])]["actual_fb"]).save_model(C.ART / "arrivals_xgb.json")
        (C.ART / "arrivals_meta.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        pred_te.to_csv(C.ART / "arrivals_test_pred.csv", index=False)
    out["_pred"] = pred_te
    return out


if __name__ == "__main__":
    from .simulate import simulate
    o = run(simulate()["slots"])
    print(pd.DataFrame(o["results"]).T)
    print(o["importance"][:6], "AI 사용:", o["use_ai"])
