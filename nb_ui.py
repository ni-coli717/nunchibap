"""눈치밥 공용 UI — 시간표 스타일(검정 칸 · 종이 바탕 · 형광 노랑 포스트잇)."""
from __future__ import annotations

import html

import streamlit as st

CSS = """
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@500;600&family=Noto+Sans+KR:wght@400;500;700;900&display=swap">
<style>
:root{--paper:#F4F3EF;--ink:#111111;--yellow:#FFE14D;--grey:#555555;--red:#B42318}
html,body,[class*="st-"]{font-family:'Noto Sans KR',Arial,sans-serif}
[data-testid="stIconMaterial"],.material-symbols-rounded,span[class*="material-symbols"]{font-family:'Material Symbols Rounded'!important}
.stApp{background:#F4F3EF;color:#111111}
.block-container{padding-top:1.2rem;padding-bottom:3rem;max-width:860px}
section[data-testid="stSidebar"]{background:#111111;color:#FFFFFF}
section[data-testid="stSidebar"] *{color:#FFFFFF}
section[data-testid="stSidebar"] a[aria-current="page"]{background:#FFE14D!important}
section[data-testid="stSidebar"] a[aria-current="page"] *{color:#111111!important;font-weight:900}
h1,h2,h3{font-weight:900!important;letter-spacing:-.5px;color:#111111}
.stButton>button{border:2px solid #111111!important;border-radius:0!important;background:#FFFFFF;color:#111111;font-weight:700;min-height:46px;box-shadow:none!important}
.stButton>button:hover{background:#FFE14D;color:#111111;border-color:#111111}
.stButton>button[kind="primary"]{background:#111111!important;color:#FFFFFF!important}
.stButton>button[kind="primary"]:hover{background:#333333!important}
.stButton>button:disabled{opacity:.45}
.stTextInput input,.stNumberInput input{border:2px solid #111111!important;border-radius:0!important;background:#FFFFFF!important;color:#111111!important;font-family:'IBM Plex Mono',monospace}
div[data-baseweb="select"]>div{border:2px solid #111111!important;border-radius:0!important;background:#FFFFFF!important}
.stRadio [role="radiogroup"] label{border:2px solid #111111;padding:6px 10px;margin:0 6px 6px 0;background:#FFFFFF}
.mono{font-family:'IBM Plex Mono','Courier New',monospace}
.nb-eyebrow{font-family:'IBM Plex Mono',monospace;font-size:12px;color:#555555}
.nb-head{padding:12px 0 10px;border-bottom:2px solid #111111;margin-bottom:14px}
.nb-head h1{margin:2px 0 0;font-size:26px}
.nb-head .sub{font-size:13px;color:#555555;margin-top:2px}
.nb-postit{position:relative;display:inline-block;background:#FFE14D;border:3px solid #111111;color:#111111;padding:18px 18px 14px;transform:rotate(var(--r,-2deg));transform-origin:50% 0;box-shadow:4px 6px 0 rgba(0,0,0,.12);margin:16px 0 10px;max-width:100%}
.nb-postit.block{display:block}
.nb-tape{position:absolute;top:-14px;left:50%;width:64px;height:22px;margin-left:-32px;background:rgba(226,219,198,.9);transform:rotate(-4deg)}
.nb-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));border-top:2px solid #111111;border-left:2px solid #111111;background:#FFFFFF;margin:6px 0 10px}
.nb-cell{height:54px;border-right:2px solid #111111;border-bottom:2px solid #111111;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;font-size:11px;font-weight:700}
.nb-cell .t{font-family:'IBM Plex Mono',monospace;font-size:13px;font-weight:600}
.k-f{background:#FFFFFF;color:#111111}.k-m{background:repeating-linear-gradient(135deg,#FFFFFF 0px,#FFFFFF 7px,#C9C9C9 7px,#C9C9C9 8.5px);color:#111111}.k-b{background:#111111;color:#FFFFFF}.k-y{background:#FFE14D;color:#111111}
.nb-card{border:2px solid #111111;background:#FFFFFF;padding:12px 14px;margin:8px 0}
.nb-row{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:2px solid #111111}
.nb-row:last-child{border-bottom:0}
.nb-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));border-top:2px solid #111111;border-left:2px solid #111111;background:#FFFFFF;margin:10px 0}
.nb-kpi{padding:12px 14px;border-right:2px solid #111111;border-bottom:2px solid #111111}
.nb-kpi .l{font-size:12px;font-weight:700;color:#555555}.nb-kpi .v{font-family:'IBM Plex Mono',monospace;font-size:24px;font-weight:600;margin-top:4px}.nb-kpi .s{font-size:12px;color:#444444;margin-top:2px}
.nb-steps{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));border:2px solid #111111;background:#FFFFFF;margin:8px 0}
.nb-steps div{padding:8px 10px;border-right:1px solid #111111;color:#6B6B6B;font-size:12px;font-weight:700;line-height:1.35}
.nb-steps div:last-child{border-right:0}.nb-steps div.on{background:#111111;color:#FFFFFF}
.nb-bars{display:grid;gap:10px;align-items:end;height:160px;border-bottom:2px solid #111111;margin-top:10px}
.nb-bar{display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%}
.nb-bar span{font-family:'IBM Plex Mono',monospace;font-size:11px;font-weight:600;margin-bottom:3px}
.nb-bar i{display:block;width:70%;border:2px solid #111111;border-bottom:0}
.nb-stamp{display:inline-block;border:3px solid #B42318;color:#B42318;font-weight:900;padding:6px 10px;transform:rotate(-12deg)}
.nb-board{border:3px solid #111111;background:#FFFFFF;margin:10px 0}
.nb-board .bh{display:flex;justify-content:space-between;align-items:center;padding:14px 22px;background:#111111;color:#FFFFFF;font-weight:900;font-size:18px}
.nb-brow{display:flex;justify-content:space-between;align-items:center;padding:14px 22px;border-bottom:2px solid #111111;font-size:18px;font-weight:700}
.nb-brow.go{background:#FFE14D}.nb-brow.past{color:#8A8A86}
.nb-chip{font-size:14px;font-weight:900;padding:6px 12px;border:2px solid #111111}
.nb-brow.go .nb-chip{background:#111111;color:#FFE14D}.nb-brow.past .nb-chip{border-color:#C9C9C9;color:#8A8A86}
.nb-note{font-size:12px;color:#555555}
</style>
"""


def inject() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def e(s) -> str:
    return html.escape(str(s if s is not None else ""))


def head(eyebrow: str, title: str, sub: str = "") -> None:
    st.markdown(f'<div class="nb-head"><div class="nb-eyebrow">{e(eyebrow)}</div><h1>{e(title)}</h1><div class="sub">{e(sub)}</div></div>', unsafe_allow_html=True)


def postit(inner_html: str, rot: float = -2, block: bool = False) -> None:
    st.markdown(f'<div class="nb-postit{" block" if block else ""}" style="--r:{rot}deg"><div class="nb-tape"></div>{inner_html}</div>', unsafe_allow_html=True)


def bowl(kind: str = "glance", w: int = 96) -> str:
    h = round(w * 0.75)
    if kind == "shock":
        eyes = '<rect x="40" y="36" width="20" height="22" fill="#FFF" stroke="#111" stroke-width="5"/><rect x="70" y="36" width="20" height="22" fill="#FFF" stroke="#111" stroke-width="5"/><rect x="46" y="43" width="8" height="8" fill="#111"/><rect x="76" y="43" width="8" height="8" fill="#111"/><rect x="58" y="62" width="12" height="10" fill="#FFF" stroke="#111" stroke-width="5"/>'
    elif kind == "happy":
        eyes = '<path d="M40 54 L50 42 L60 54" fill="none" stroke="#111" stroke-width="6"/><path d="M70 54 L80 42 L90 54" fill="none" stroke="#111" stroke-width="6"/><rect x="44" y="62" width="40" height="8" fill="#FFE14D"/><rect x="22" y="56" width="10" height="5" fill="#FFB8A8"/><rect x="96" y="56" width="10" height="5" fill="#FFB8A8"/>'
    elif kind == "sad":
        eyes = '<rect x="40" y="40" width="20" height="16" fill="#FFF" stroke="#111" stroke-width="4"/><rect x="70" y="40" width="20" height="16" fill="#FFF" stroke="#111" stroke-width="4"/><rect x="46" y="48" width="8" height="6" fill="#111"/><rect x="76" y="48" width="8" height="6" fill="#111"/>'
    else:
        eyes = '<rect x="40" y="40" width="20" height="16" fill="#FFF" stroke="#111" stroke-width="4"/><rect x="70" y="40" width="20" height="16" fill="#FFF" stroke="#111" stroke-width="4"/><rect x="50" y="42" width="8" height="12" fill="#111"/><rect x="80" y="42" width="8" height="12" fill="#111"/><rect x="44" y="62" width="40" height="6" fill="#FFE14D"/>'
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 128 96" role="img" aria-label="밥그릇 마스코트">'
            '<path d="M14 30 H114 L102 78 H26 Z" fill="#FFF" stroke="#111" stroke-width="4"/><path d="M22 30 C30 10, 98 10, 106 30" fill="#FFF" stroke="#111" stroke-width="4"/>'
            f'<rect x="38" y="80" width="52" height="12" fill="#111"/>{eyes}</svg>')


LOGO = '<svg width="54" height="24" viewBox="0 0 150 66" role="img" aria-label="눈치밥"><g fill="#FFF" stroke="#111" stroke-width="7"><rect x="4" y="4" width="28" height="29"/><rect x="32" y="4" width="29" height="29" fill="#111"/><rect x="61" y="4" width="29" height="29" fill="#111"/><rect x="90" y="4" width="29" height="29"/><rect x="119" y="4" width="27" height="29"/><rect x="4" y="33" width="28" height="29"/><rect x="32" y="33" width="29" height="29"/><rect x="61" y="33" width="29" height="29"/><rect x="90" y="33" width="29" height="29" fill="#FFE14D"/><rect x="119" y="33" width="27" height="29"/></g></svg>'


def grid(rows: list[dict], mine: str | None = None) -> None:
    cells = []
    for r in rows:
        k = "y" if mine and r["time"] == mine else r["kind"]
        word = {"f": "여유", "m": "보통", "b": "꽉 참", "y": "내 예약"}[k]
        cells.append(f'<div class="nb-cell k-{k}"><span class="t">{r["time"]}</span><span>{word}</span></div>')
    st.markdown('<div class="nb-grid">' + "".join(cells) + "</div>", unsafe_allow_html=True)


def kpis(items: list[tuple]) -> None:
    st.markdown('<div class="nb-kpis">' + "".join(f'<div class="nb-kpi"><div class="l">{e(l)}</div><div class="v">{e(v)}</div><div class="s">{e(s)}</div></div>' for l, v, s in items) + "</div>", unsafe_allow_html=True)


def rows_card(title: str, rows: list[tuple]) -> None:
    body = "".join(f'<div class="nb-row"><span style="color:#444">{e(k)}</span><b>{e(v)}</b></div>' for k, v in rows)
    st.markdown(f'<div class="nb-card"><b style="font-size:14px">{e(title)}</b><div style="margin-top:6px">{body}</div></div>', unsafe_allow_html=True)


def hbars(title: str, items: list[tuple], unit: str = "", note: str = "", hi: int | None = None, cap: float | None = None, label_w: int = 64) -> None:
    """가로 막대 (슬라이드 12장 스타일). items = [(라벨, 값)]. hi번째까지 노랑, cap을 넘으면 검정, 음수는 빗금."""
    mx = max([abs(v) for _, v in items] + [cap or 0, 1e-9])
    rows = []
    for i, (lab, v) in enumerate(items):
        over = cap is not None and v > cap
        bg = "#111111" if over else ("repeating-linear-gradient(135deg,#FFFFFF 0px,#FFFFFF 5px,#9A9A96 5px,#9A9A96 6.5px)" if v < 0 else ("#FFE14D" if hi is not None and i < hi else "#FFFFFF"))
        w = max(1.5, abs(v) / mx * 100)
        rows.append(f'<div style="display:grid;grid-template-columns:{label_w}px 1fr 56px;align-items:center;gap:8px;margin:4px 0">'
                    f'<span class="mono" style="font-size:12px;font-weight:600">{e(lab)}</span>'
                    f'<span style="position:relative;height:16px"><i style="position:absolute;left:0;top:0;bottom:0;width:{w:.1f}%;background:{bg};border:2px solid #111111"></i>'
                    + (f'<i style="position:absolute;top:-3px;bottom:-3px;left:{cap / mx * 100:.1f}%;border-left:2px dashed #B42318"></i>' if cap else "")
                    + f'</span><span class="mono" style="font-size:12px;font-weight:600;text-align:right">{v:g}{e(unit)}</span></div>')
    st.markdown(f'<div class="nb-card"><b style="font-size:14px">{e(title)}</b>{"<div class=nb-note>" + e(note) + "</div>" if note else ""}<div style="margin-top:8px">{"".join(rows)}</div></div>', unsafe_allow_html=True)


def stages(cur: int, items: list[tuple]) -> None:
    cells = "".join(f'<div class="{"on" if i == cur else ""}" style="padding:12px 14px"><span class="mono" style="font-size:11px">{e(a)}</span><br><b style="font-size:15px">{e(b)}</b><br><span style="font-weight:500">{e(c)}</span></div>' for i, (a, b, c) in enumerate(items))
    st.markdown(f'<div class="nb-steps">{cells}</div>', unsafe_allow_html=True)
