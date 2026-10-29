"""눈치밥 관리자 웹 — 화면은 frontend/admin, 데이터는 학생 앱과 같은 서버 상태"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
st.set_page_config(page_title="눈치밥 관리자", page_icon="🍚", layout="wide", initial_sidebar_state="collapsed")

import nb_bridge as br  # noqa: E402

br.mount("admin", view="admin")
