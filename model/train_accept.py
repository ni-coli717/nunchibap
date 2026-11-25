"""모델 2: 추천 수락 예측 — "이 팀한테 12:35를 추천하면 받아들일까?"

한 행 = 추천 1번. 정답 = 수락(1) / 거절(0).
로지스틱 회귀(해석용: 각 요인이 수락 확률을 몇 배 바꾸는지) vs XGBoost(정확도용).
분할: 날짜 순서로 앞 75% 학습, 뒤 25% 테스트.
"""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, roc_auc_score

from . import config as C

NUM = ["saved_min", "shift_min", "points", "menu_pop", "team_size", "team_past_rate"]
MSG = ["신호등형", "보상형"]          # 숫자형이 기준
FEATURES = NUM + [f"msg_{m}" for m in MSG]
KO = {"saved_min": "줄어드는 대기 (분)", "shift_min": "시간 이동 (분)", "points": "포인트 지급", "menu_pop": "메뉴 인기도",
      "team_size": "팀 인원", "team_past_rate": "팀 과거 수락률", "msg_신호등형": "신호등형 메시지", "msg_보상형": "보상형 메시지"}


def prep(df: pd.DataFrame) -> pd.DataFrame:
    X = df[NUM].astype(float).copy()
    for m in MSG:
        X[f"msg_{m}"] = (df["msg"] == m).astype(float)
    return X


def nudge_table(logit: LogisticRegression, base_row: dict) -> pd.DataFrame:
    """발표용: '대기 5분 줄면 수락률 X%, 포인트까지 주면 Y%'."""
    rows = []
    for saved in [2, 5, 9]:
        for pts in [0, 1]:
            for msg in ["숫자형", "신호등형", "보상형"]:
                r = dict(base_row, saved_min=saved, points=pts, msg=msg)
                pr = float(logit.predict_proba(prep(pd.DataFrame([r])))[0, 1])
                rows.append({"줄어드는 대기": f"{saved}분", "포인트": "있음" if pts else "없음", "메시지": msg, "수락 확률": round(pr, 3)})
    return pd.DataFrame(rows)


def run(recs: pd.DataFrame, p: dict | None = None, save: bool = True) -> dict:
    p = p or C.load()
    dates = sorted(recs["date"].unique())
    cut = dates[int(len(dates) * 0.75)]
    tr, te = recs[recs["date"] < cut], recs[recs["date"] >= cut]
    Xtr, Xte = prep(tr), prep(te)
    logit = LogisticRegression(C=10.0, max_iter=2000).fit(Xtr, tr["accepted"])
    xg = xgb.XGBClassifier(n_estimators=300, learning_rate=0.05, max_depth=3, subsample=0.9, colsample_bytree=0.9,
                           random_state=0, eval_metric="logloss").fit(Xtr, tr["accepted"])
    res = {}
    for name, m in [("로지스틱 회귀", logit), ("XGBoost", xg)]:
        pr = m.predict_proba(Xte)[:, 1]
        res[name] = {"auc": round(float(roc_auc_score(te["accepted"], pr)), 3),
                     "accuracy": round(float(accuracy_score(te["accepted"], pr >= 0.5)), 3),
                     "brier": round(float(brier_score_loss(te["accepted"], pr)), 3)}
    res["기준 (항상 다수 답)"] = {"auc": 0.5, "accuracy": round(float(max(te["accepted"].mean(), 1 - te["accepted"].mean())), 3),
                            "brier": round(float(((te["accepted"] - tr["accepted"].mean()) ** 2).mean()), 3)}
    # 보정 곡선 (예측 확률 구간별 실제 수락률)
    pr = logit.predict_proba(Xte)[:, 1]
    bins = pd.cut(pr, [0, .2, .4, .6, .8, 1.0], include_lowest=True)
    calib = te.assign(pred=pr, bin=bins).groupby("bin", observed=True).agg(pred=("pred", "mean"), real=("accepted", "mean"), n=("accepted", "size"))
    calib = [{"bin": str(i), "pred": round(float(r.pred), 3), "real": round(float(r.real), 3), "n": int(r.n)} for i, r in calib.iterrows()]
    coefs = [{"feature": KO[f], "key": f, "coef": round(float(c), 4), "odds_x": round(math.exp(float(c)), 3)} for f, c in zip(FEATURES, logit.coef_[0])]
    truth = p["acc_logit"]
    true_map = {"saved_min": truth["saved"], "shift_min": truth["shift"], "points": truth["points"], "menu_pop": truth["menu"],
                "team_size": truth["team"], "msg_신호등형": truth.get("msg_신호등형", 0), "msg_보상형": truth.get("msg_보상형", 0)}
    for c in coefs:
        c["true"] = true_map.get(c["key"])
    base_row = {"shift_min": 10, "menu_pop": 6, "team_size": 4, "team_past_rate": float(recs["team_past_rate"].median())}
    nudge = nudge_table(logit, base_row)
    out = {"n_train": len(tr), "n_test": len(te), "accept_rate": round(float(recs["accepted"].mean()), 3), "results": res,
           "coefs": coefs, "intercept": round(float(logit.intercept_[0]), 4), "calibration": calib,
           "nudge": nudge.to_dict(orient="records"), "features": FEATURES}
    if save:
        C.ART.mkdir(parents=True, exist_ok=True)
        (C.ART / "accept_meta.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        (C.ART / "accept_logit.json").write_text(json.dumps({"features": FEATURES, "coef": [c["coef"] for c in coefs], "intercept": out["intercept"]}, ensure_ascii=False, indent=1), encoding="utf-8")
        xg.save_model(C.ART / "accept_xgb.json")
    return out


if __name__ == "__main__":
    from .simulate import simulate
    o = run(simulate()["recs"])
    print(pd.DataFrame(o["results"]).T)
    print(pd.DataFrame(o["coefs"]))
    print(pd.DataFrame(o["nudge"]).pivot_table(index=["줄어드는 대기", "포인트"], columns="메시지", values="수락 확률"))
