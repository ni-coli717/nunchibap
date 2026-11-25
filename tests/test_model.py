"""모델 파이프라인 (python -m pytest tests/test_model.py)"""
import shutil

import numpy as np
import pytest

from model import calibrate, config as C, train_accept, train_arrivals
from model.simulate import queue_waits, simulate


@pytest.fixture(scope="module")
def sim():
    return simulate(C.DEFAULTS, seed=0)


def test_simulation_shapes(sim):
    s = sim["slots"]
    assert len(s) == C.DEFAULTS["days"] * C.DEFAULTS["slots"]
    assert s["actual_true"].sum() > 0.85 * sum(C.DEFAULTS["per_grade"]) * C.DEFAULTS["days"]
    assert s.groupby("slot")["actual_true"].mean().idxmax() in (1, 2)        # 12:15~12:25 피크
    assert 0.4 < sim["recs"]["accepted"].mean() < 0.9


def test_queue_carry_over():
    avg, last = queue_waits(np.array([100, 0, 0]), rate=10, slot_len=5)
    assert last[0] == 10 and last[1] == 5 and last[2] == 0


def test_model1_beats_baseline(sim):
    o = train_arrivals.run(sim["slots"], C.DEFAULTS, save=False)
    r = o["results"]
    assert r["XGBoost"]["mae_true"] < r["기본 통계"]["mae_true"] * 0.8
    assert r["XGBoost"]["signal_acc"] > r["기본 통계"]["signal_acc"]
    assert o["selected"] in r


def test_model2_learns_direction(sim):
    o = train_accept.run(sim["recs"], C.DEFAULTS, save=False)
    co = {c["key"]: c["coef"] for c in o["coefs"]}
    assert o["results"]["로지스틱 회귀"]["auc"] > 0.65
    assert co["saved_min"] > 0 and co["shift_min"] < 0 and co["points"] > 0


def test_calibration_from_templates(tmp_path, monkeypatch):
    real = tmp_path / "real"
    shutil.copytree(C.REAL, real)
    for f in real.glob("*.template.csv"):
        f.rename(real / f.name.replace(".template", ""))
    monkeypatch.setattr(C, "REAL", real)
    monkeypatch.setattr(C, "ART", tmp_path / "art")
    cal = calibrate.run()
    assert cal["mu"] > 0 and cal["_sources"]
    assert abs(sum(cal["team_size_p"]) - 1) < 1e-6
