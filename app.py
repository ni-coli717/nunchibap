"""눈치밥 학생 앱 — 화면은 frontend/student (시안 HTML), 데이터는 서버 data/state.json"""
import streamlit as st

st.set_page_config(page_title="눈치밥", page_icon="🍚", layout="wide", initial_sidebar_state="collapsed")

import nb_bridge as br  # noqa: E402

br.mount("student", view="student")
