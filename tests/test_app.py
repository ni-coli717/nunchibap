"""화면(HTML) ↔ 서버 연결과 페이지 실행 확인 (python -m pytest tests)"""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("NB_DATA_DIR", str(tmp_path))
    import nb_core
    nb_core.DATA_DIR = tmp_path
    nb_core.DATA_FILE = tmp_path / "state.json"
    yield tmp_path


def test_save_bumps_rev():
    import nb_core as nb
    S = nb.load()
    nb.save(S)
    r1 = nb.load()["_rev"]
    nb.save(nb.load())
    assert nb.load()["_rev"] == r1 + 1


def test_patch_merges_settings_and_ignores_unknown_keys():
    import nb_bridge as br
    import nb_core as nb
    before = nb.load()
    before["settings"]["aiWeeks"] = 3
    nb.save(before)
    rev = nb.load()["_rev"]
    user = {"email": "s25012@masong.hs.kr", "grade": "2", "cls": "3", "name": "", "introDone": True}
    br.apply_patch({"user": user, "settings": {"deadline": "07:40"}, "evil": 1})
    S = nb.load()
    assert S["user"]["email"] == "s25012@masong.hs.kr"
    assert S["settings"]["deadline"] == "07:40"
    assert S["settings"]["aiWeeks"] == 3  # 서버 전용 설정은 그대로
    assert "evil" not in S
    assert S["_rev"] == rev + 1


def test_ai_payload_matches_slots():
    import nb_bridge as br
    import nb_core as nb
    S = nb.load()
    a = br.ai_payload(S)
    assert a and len(a["key"]) == 10
    assert all(isinstance(x, int) for x in a["pred"]) and len(a["pred"]) > 0
    assert a["label"]


@pytest.mark.parametrize("name", ["student", "admin"])
def test_frontend_bundle(name):
    d = ROOT / "frontend" / name
    html = (d / "index.html").read_text(encoding="utf-8")
    assert html.lstrip().lower().startswith("<!doctype html>")
    assert 'src="nb-core.js"' in html and 'src="nb-bridge.js"' in html
    assert (d / "nb-core.js").exists() and (d / "nb-bridge.js").exists()


@pytest.mark.parametrize("page", ["app.py", "pages/1_관리자.py", "pages/2_교실_배정표.py", "pages/3_AI_엔진.py"])
def test_pages_run(page):
    at = AppTest.from_file(str(ROOT / page), default_timeout=60).run()
    assert not at.exception, at.exception
