"""한 번에 실행: 보정 → 시뮬레이션 → 모델 1 · 2 학습 → 실측 검증 → artifacts/results.json

    python -m model.run_all            # 기본
    python -m model.run_all --seeds 5  # 시뮬레이션 5번 돌려 결과가 흔들리는 폭까지
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime

import numpy as np
import pandas as pd

from . import calibrate, config as C, train_accept, train_arrivals, validate_real
from .simulate import simulate


def main(seeds: int = 1) -> dict:
    cal = calibrate.run()
    p = C.load()
    sim = simulate(p, seed=0)
    out_sim = C.ROOT / "data" / "sim"
    out_sim.mkdir(parents=True, exist_ok=True)
    for k in ["slots", "recs", "feedback"]:
        sim[k].to_csv(out_sim / f"{k}.csv", index=False)
    m1 = train_arrivals.run(sim["slots"], p)
    m1.pop("_pred", None)
    m2 = train_accept.run(sim["recs"], p)
    val = validate_real.run(sim, p)
    spread = None
    if seeds > 1:
        g, lin = [], []
        for s in range(1, seeds):
            o = train_arrivals.run(simulate(p, seed=s)["slots"], p, save=False)
            g.append(o["results"]["XGBoost"]["gain_vs_base"])
            lin.append(o["results"]["선형회귀"]["gain_vs_base"])
        spread = {"xgb_gain_mean": round(float(np.mean(g + [m1["results"]["XGBoost"]["gain_vs_base"]])), 3),
                  "xgb_gain_min": round(float(min(g + [m1["results"]["XGBoost"]["gain_vs_base"]])), 3),
                  "lin_gain_mean": round(float(np.mean(lin + [m1["results"]["선형회귀"]["gain_vs_base"]])), 3), "seeds": seeds}
    # 피드백 응답률이 오르면 정답(라벨)이 정확해지고 → 모델도 정확해진다 (응답률 올리는 넛지의 근거)
    sens = []
    for rr in [0.4, 0.62, 0.8]:
        q = dict(p, resp_rate=rr)
        maes, labs = [], []
        for sd in range(3):
            sl = simulate(q, seed=sd)["slots"]
            o = train_arrivals.run(sl, q, save=False)
            maes.append(o["results"]["XGBoost"]["mae_true"])
            x = sl[sl["date"].isin(sorted(sl["date"].unique())[q["measure_days"]:])]
            labs.append(float((x["actual_fb"] - x["actual_true"]).abs().sum() / x["actual_true"].sum()))
        sens.append({"resp_rate": rr, "label_rel_err": round(float(np.mean(labs)), 3), "xgb_mae": round(float(np.mean(maes)), 2)})
    s = sim["slots"]
    summary = {
        "made_at": datetime.now().isoformat(timespec="minutes"),
        "calibrated_from": cal.get("_sources", []),
        "params": {k: p[k] for k in ["mu", "lines", "delay_mean", "base_delay", "adopt_start", "adopt_end", "resp_rate"]},
        "sim": {"days": int(s["date"].nunique()), "slot_rows": len(s), "recs": len(sim["recs"]), "feedback": len(sim["feedback"]),
                "teams": len(sim["teams"]), "accept_rate": round(float(sim["recs"]["accepted"].mean()), 3),
                "shape_true": s.groupby("slot")["actual_true"].mean().round(1).tolist(),
                "wait_by_slot": s.groupby("slot")["wait_avg"].mean().round(1).tolist()},
        "model1": m1, "model2": m2, "validation": val, "seed_spread": spread, "resp_sensitivity": sens,
    }
    (C.ART / "results.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=1)
    r = main(ap.parse_args().seeds)
    print("보정:", r["calibrated_from"] or "실측 파일 없음 → 가정값")
    print("\n[모델 1] 칸별 유입 인원 (테스트 20일)")
    print(pd.DataFrame(r["model1"]["results"]).T.to_string())
    print("중요 변수:", r["model1"]["importance"][:5])
    print("\n[모델 2] 추천 수락")
    print(pd.DataFrame(r["model2"]["results"]).T.to_string())
    print("\n[검증]", r["validation"])
    print("[응답률 민감도]", r["resp_sensitivity"])
    if r["seed_spread"]:
        print("[시드별]", r["seed_spread"])
