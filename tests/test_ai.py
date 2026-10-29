"""python -m pytest tests"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import nb_ai as ai  # noqa: E402
import nb_core as nb  # noqa: E402


def test_stages_follow_data_weeks():
    assert ai.train_arrivals(ai.make_history(weeks=1)).stage == 0
    assert ai.train_arrivals(ai.make_history(weeks=3)).stage == 1
    m = ai.train_arrivals(ai.make_history(weeks=8))
    assert m.stage == 2 and m.use_ai and m.mae_ai < m.mae_base


def test_ai_only_replaces_when_better():
    m = ai.train_arrivals(ai.make_history(weeks=5))
    assert m.use_ai == (m.mae_ai < m.mae_base * 0.95)


def test_accept_prob_direction():
    a = ai.train_accept(ai.make_rec_log())
    assert a.prob(10, 5, 2) > a.prob(1, 5, 2)
    assert a.prob(6, 5, 2) > a.prob(6, 30, 2)


def test_estimate_actual():
    assert ai.estimate_actual([5, 10], 0.5, 2.0) == [20, 40]


def test_simulation_cuts_peak_and_dynamic_beats_static_herding():
    a = ai.train_accept(ai.make_rec_log())
    s = ai.simulate(res_rate=0.7, accept=a)
    assert max(s["after"]) < max(s["before"]) and sum(s["after"]) == sum(s["before"])
    dyn = ai.simulate(res_rate=0.7, accept_all=True, dynamic=True)
    sta = ai.simulate(res_rate=0.7, accept_all=True, dynamic=False)
    assert max(dyn["after"]) < max(sta["after"])


def test_queue_uses_engine_and_falls_back():
    S = nb.defaults()
    rows = nb.queue(S, date(2026, 11, 2))
    assert len(rows) == len(nb.slots(S)) and all(r["pred"] >= 0 for r in rows)
    S["settings"]["aiMode"] = "계산"
    assert nb.engine_label(S) == "계산 예측"
