"""학생 앱 · 관리자 웹 화면 흐름 (python -m pytest tests)"""
import json
import os
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


def click(at, label=None, key=None):
    for b in at.button:
        if (key and b.key == key) or (label and b.label == label):
            b.click()
            at.run()
            return
    raise AssertionError(f"button not found: {label or key} in {[x.label for x in at.button]}")


def text(at):
    return " ".join(m.value for m in at.markdown)


def signup(at):
    click(at, "학교 이메일로 시작하기")
    click(at, key="tb_demo_등록된 학교")
    click(at, "인증 코드 받기")
    click(at, "데모: 메일에서 코드 붙여넣기")
    click(at, "확인")
    click(at, "다음")
    click(at, key="skip")


def test_demo_flow_matches_prototype():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    signup(at)
    assert not at.exception
    t = text(at)
    assert "좋은 아침, 유건" in t and "10.27 TUE · 2-3" in t and "12:35" in t and "대기 약 2분" in t and "1시간 12분 전" in t
    click(at, "오늘만 바꾸기")
    click(at, key="tb_slot_1220")
    assert "12:20은 꽉 찼어요 · 지금 가면 약 11분" in text(at)
    click(at, "덜 붐비는 시간 추천 받기")
    t = text(at)
    assert "9분 덜 기다림 · +10P" in t and "10분 덜 기다림 · +10P" in t and "6분 덜 기다림 · +5P" in t
    click(at, key="tb_rec_0")
    t = text(at)
    assert "10.27 TUE · 07:24" in t and "점심시간 시작하고 25분 뒤" in t
    click(at, "확인했어요")
    click(at, key="tb_step3")
    assert "16:35 · 팀 대표가" in text(at)
    click(at, "보내기 · +5P")
    t = text(at)
    assert "345P" in t and "47분" in t and "오늘 3분 기다렸어요" in t
    click(at, "팀")
    assert "박유건" in text(at) and "MS-4K2P" in text(at)
    click(at, "정기")
    assert "NOV 2026 · 팀 4명" in text(at)
    click(at, "설정")
    assert "유건 · 2학년 3반" in text(at)
    assert not at.exception
    # 시연 모드는 공유 파일에 아무것도 쓰지 않는다
    assert not (Path(os.environ["NB_DATA_DIR"]) / "state.json").exists() or json.loads((Path(os.environ["NB_DATA_DIR"]) / "state.json").read_text())["user"] is None


def test_live_mode_flow(data_dir):
    import nb_core
    st_ = nb_core.defaults()
    st_["settings"]["demo"] = False
    nb_core.save(st_)
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    signup(at)
    assert not at.exception
    click(at, key="nav_settings")
    assert not at.exception
    saved = json.loads((data_dir / "state.json").read_text())
    assert saved["user"]["grade"] == "2"


@pytest.mark.parametrize("demo", [True, False])
def test_admin_pages(demo, data_dir):
    import nb_core
    st_ = nb_core.defaults()
    st_["settings"]["demo"] = demo
    nb_core.save(st_)
    at = AppTest.from_file(str(ROOT / "pages" / "1_관리자.py"), default_timeout=90).run()
    assert not at.exception
    labels = [t.label for t in at.tabs]
    assert labels[:5] == ["01 학교 설정", "02 오늘 대시보드", "03 교실 배정표", "04 운영 규칙", "05 리포트"]
    if demo:
        t = text(at)
        assert "541명" in t and "피크 예고 12:20~12:30" in t and "A팀 · 박유건 외 3명" in t and "도입 9일째" in t
    b = AppTest.from_file(str(ROOT / "pages" / "2_교실_배정표.py"), default_timeout=60).run()
    assert not b.exception
