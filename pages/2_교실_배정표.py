"""교실 전자칠판용 배정표 (전체 화면)"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
st.set_page_config(page_title="눈치밥 교실 배정표", page_icon="🍚", layout="wide", initial_sidebar_state="collapsed")

import nb_bridge as br  # noqa: E402

br.mount("admin", view="board", key="nb_board", every=15)
