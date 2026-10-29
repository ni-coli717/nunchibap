"""눈치밥 교실 배정표 — 교실 전자칠판에 띄우는 화면"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import nb_core as nb  # noqa: E402
import nb_demo as dm  # noqa: E402
import nb_ui as ui  # noqa: E402

st.set_page_config(page_title="눈치밥 교실 배정표", page_icon="🍚", layout="wide")
ui.inject()
S = nb.load()
t = nb.target_date(S)
DEMO = bool(S["settings"].get("demo", True))

ui.head("03 · CLASSROOM", "교실 배정표", "교실 전자칠판에 띄우는 화면이에요. 지금 시각에 맞춰 갈 팀이 바뀌어요")
classes = list(dm.BOARD_CLASSES)
if S["user"] and not DEMO:
    mine = f"{S['user']['grade']}학년 {S['user']['cls']}반"
    if mine not in classes:
        classes.append(mine)
c1, c2, c3 = st.columns([2, 2, 1])
cls = c1.selectbox("반", classes, index=1 if "2학년 3반" in classes else 0)
now_opts = dm.BOARD_NOW if DEMO else ["지금"] + nb.slots(S)[::2]
preview = c2.selectbox("미리보기 시각", now_opts, index=now_opts.index(dm.BOARD_DEFAULT[1]) if DEMO else 0)
auto = c3.toggle("30초마다 새로고침", value=False)
now_t = nb.now_hhmm() if preview == "지금" else preview
now_m = nb.mins(now_t)

rows_html = ""
board = [(a, b_, False) for a, b_ in dm.BOARD.get(cls, [])] if DEMO else nb.class_board(S, t, cls)
for time, team, mine_flag in board:
    d = nb.mins(time) - now_m
    go = -4 <= d <= 0
    past = d < -4
    state = "지금 가세요 →" if go else ("다녀왔어요" if past else f"{d}분 뒤")
    tag = ' <span style="font-size:12px;padding:2px 6px;border:2px solid #111">학생 앱 예약</span>' if mine_flag else ""
    rows_html += f'<div class="nb-brow {"go" if go else "past" if past else ""}"><span><span class="mono" style="font-size:26px;font-weight:600">{time}</span> &nbsp; {ui.e(team)}{tag}</span><span class="nb-chip">{state}</span></div>'
if not rows_html:
    rows_html = '<div class="nb-brow">이 반은 아직 예약이 없어요</div>'
st.markdown(f'<div class="nb-board"><div class="bh"><span>{ui.e(cls)} · {dm.DATE_KO if DEMO else nb.fmt_date_ko(t)}</span><span class="mono">NOW {now_t}</span></div>{rows_html}</div>', unsafe_allow_html=True)
st.caption("전자칠판에서는 브라우저 전체 화면(F11)으로 띄우고, 왼쪽 메뉴를 접어 두세요.")

if auto and preview == "지금":
    import time as _time
    _time.sleep(30)
    st.rerun()
