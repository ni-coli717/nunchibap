"""눈치밥 화면(HTML) ↔ Streamlit 서버 연결.

화면은 frontend/ 의 시안 HTML을 그대로 쓰고, 데이터는 서버의 data/state.json 하나에 모은다.
- 화면에서 무언가 바뀌면 바뀐 묶음(patch)만 보내고, 서버는 rev를 1 올려 저장한다.
- 4초마다 최신 상태(rev)를 화면에 다시 보내서, 폰에서 예약한 내용이 노트북 관리자 화면에 뜬다.
- 혼잡 예측(AI ①)은 파이썬 AI 엔진(nb_ai)이 계산해서 같이 보낸다.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st
import streamlit.components.v1 as components

import nb_core as nb

ROOT = Path(__file__).resolve().parent / "frontend"
_COMPONENTS: dict = {}

PAGES = {"student": "app.py", "admin": "pages/1_관리자.py", "board": "pages/2_교실_배정표.py", "ai": "pages/3_AI_엔진.py"}

CHROME = """
<style>
header[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"], footer,
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"],
[data-testid="stSidebarNav"] {display:none!important}
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {background:#F4F3EF!important}
.block-container, [data-testid="stMainBlockContainer"] {padding:0!important; max-width:100%!important}
[data-testid="stVerticalBlock"] {gap:0!important}
[data-testid="stElementContainer"]:has(> .stMarkdown style), .element-container:has(style) {display:none}
iframe[title*="nunchibap"] {display:block; width:100%; border:0; height:100vh!important; height:100dvh!important}
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {overflow:hidden!important}
[data-testid="stMain"] {padding:0!important}
</style>
"""


def _component(name: str):
    if name not in _COMPONENTS:
        _COMPONENTS[name] = components.declare_component(f"nunchibap_{name}", path=str(ROOT / name))
    return _COMPONENTS[name]


def ai_payload(S: dict) -> dict | None:
    """대상 급식일의 칸별 예측 인원(예약 안 한 학생 포함). 실패하면 화면이 기본 통계식으로 계산한다."""
    try:
        kst = datetime.now(ZoneInfo("Asia/Seoul")).replace(tzinfo=None)  # 서버는 UTC라서 한국 시간으로 맞춘다
        t = nb.target_date(S, kst)
        base = nb.base_demand(S, t)
        pred = nb.predict(S, t, base)
        return {"key": nb.date_key(t), "pred": [int(round(p)) for p in pred], "label": nb.engine_label(S)}
    except Exception:
        return None


def apply_patch(patch: dict) -> dict:
    cur = nb.load()
    allowed = set(nb.defaults().keys())
    for k, v in (patch or {}).items():
        if k not in allowed:
            continue
        if k == "settings" and isinstance(v, dict) and isinstance(cur.get(k), dict):
            cur[k] = {**cur[k], **v}  # 화면이 모르는 서버 전용 설정(AI 엔진 등)은 남긴다
        else:
            cur[k] = v
    nb.save(cur)  # save가 _rev를 올린다
    return cur


def mount(name: str, view: str, key: str | None = None, every: int = 4) -> None:
    """name: frontend/ 아래 폴더(student·admin), view: 처음 보여 줄 화면."""
    key = key or f"nb_{view}"
    st.markdown(CHROME, unsafe_allow_html=True)

    nav = st.session_state.pop("_nb_nav", None)
    if nav:
        st.switch_page(PAGES.get(nav, nav))

    comp = _component(name)

    @st.fragment(run_every=every)
    def _live() -> None:
        S = nb.load()
        if "_rev" not in S:
            nb.save(S)
        val = comp(state=S, rev=int(S["_rev"]), view=view, ai=ai_payload(S), key=key, default=None)
        if isinstance(val, dict) and val.get("nonce") and val["nonce"] != st.session_state.get(f"{key}_nonce"):
            st.session_state[f"{key}_nonce"] = val["nonce"]
            if isinstance(val.get("patch"), dict) and val["patch"]:
                apply_patch(val["patch"])
            if val.get("nav"):
                st.session_state["_nb_nav"] = val["nav"]
                st.rerun(scope="app")
            st.rerun(scope="fragment")

    _live()
