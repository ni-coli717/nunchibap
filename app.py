"""눈치밥 nunchi-bap — 학생 앱 (Streamlit)
실행: streamlit run app.py

시연 모드(기본): 최종 시안의 데모용 예시 그대로. 보는 사람마다 따로 처음부터 체험한다.
실시간 모드: 관리자 → 학교 설정에서 시연 모드를 끄면 nb_core 계산 · AI 엔진 · 공유 저장 데이터를 쓴다.
"""
from __future__ import annotations

import re
from datetime import datetime

import streamlit as st

import nb_core as nb
import nb_demo as dm
import nb_ui as ui

st.set_page_config(page_title="눈치밥", page_icon="🍚", layout="centered", initial_sidebar_state="collapsed")
ui.inject(phone=True)

S = nb.load()
DEMO = bool(S["settings"].get("demo", True))
ss = st.session_state
ss.setdefault("d", {"user": None, "booked": dm.DEFAULT_BOOKED[0], "kind": dm.DEFAULT_BOOKED[1], "points": dm.POINTS,
                    "fb_out": set(dm.FB_OUT), "team_out": set(dm.TEAM_OUT), "period": "1개월", "notif1": True, "notif2": True})
D = ss.d
for k, v in {"screen": "splash", "intro": 0, "intro_from": "signup", "picked": None, "just_sent": False, "email": "",
             "code": "", "grade": dm.GRADE, "cls": dm.CLS, "fb": {"a1": "예", "a2": "예약대로", "a3": None}}.items():
    ss.setdefault(k, v)
if ss.screen == "splash" and not DEMO and S["user"] and S["user"].get("introDone"):
    ss.screen = "home"


def go(screen: str, **extra) -> None:
    ss.screen = screen
    for k, v in extra.items():
        ss[k] = v
    st.rerun()


# ---------------- 데이터: 시연 / 실시간 ----------------
def user() -> dict | None:
    return D["user"] if DEMO else S["user"]


def target():
    return nb.target_date(S)


def when() -> str:
    return "오늘" if DEMO or nb.is_today(target()) else "내일"


def rows(with_me: bool = True) -> list[dict]:
    if DEMO:
        return dm.slot_rows()
    return nb.queue(S, target()) if with_me else nb.queue(S, target(), booking=None)


def booking() -> dict | None:
    if DEMO:
        return {"slot": D["booked"], "kind": D["kind"]} if D["booked"] else None
    return nb.current_booking(S, target())


def book(slot: str, kind: str) -> None:
    if DEMO:
        D["booked"], D["kind"] = slot, kind
    else:
        nb.book(S, target(), slot, kind)


def team_n() -> int:
    return dm.TEAM_SIZE if DEMO else nb.team_count(S)


def date_label() -> str:
    return dm.DATE if DEMO else nb.fmt_date(datetime.now().date())


def recs(picked: dict) -> list[dict]:
    if DEMO:
        by = {r["time"]: r for r in dm.slot_rows()}
        return [{"time": t, "tag": tag, "wait": by[t]["wait"], "save": max(0, picked["wait"] - by[t]["wait"]), "pt": pt, "rot": rot, "pa": None}
                for t, tag, pt, rot in dm.RECS]
    out = []
    for i, r in enumerate(nb.recommend(S, target(), picked["time"])):
        out.append({"time": r["time"], "tag": r["tag"], "wait": r["wait"], "save": max(0, picked["wait"] - r["wait"]),
                    "pt": f"+{r['pt']}P", "rot": [-2.5, 2, -1][i], "pa": r.get("pa")})
    return out


def points() -> int:
    return D["points"] if DEMO else (S["user"] or {}).get("points", 0)


def add_points(n: int) -> None:
    if DEMO:
        D["points"] += n
    else:
        S["user"]["points"] = S["user"].get("points", 0) + n
        nb.save(S)


def email_kind(email: str) -> tuple[str, str, str]:
    em = (email or "").strip().lower()
    at = em.find("@")
    dom = em[at + 1:] if at > 0 else ""
    school = next((S["settings"]["schoolName"] for d in S["settings"]["domains"] if d["ok"] and d["name"] == dom), "")
    if not em:
        kind = "idle"
    elif at < 1 or "." not in dom or dom.endswith("."):
        kind = "typing"
    elif school:
        kind = "ok"
    elif re.search(r"\.(hs|ms|es|sc)\.kr$|\.go\.kr$|\.ac\.kr$", dom):
        kind = "missing"
    else:
        kind = "bad"
    return kind, dom, school


# ---------------- 공용 조각 ----------------
def cta(label: str | None, wait_text: str = "", key: str = "cta_btn") -> bool:
    with st.container(key="ph_cta"):
        if label:
            return st.button(label, key=key, type="primary", use_container_width=True)
        st.markdown(f'<div class="ph-wait">{ui.e(wait_text)}</div>', unsafe_allow_html=True)
    return False


def back(label: str, screen: str) -> None:
    with st.container(key="ph_link"):
        if st.button(label, key=f"back_{screen}"):
            go(screen, picked=None)


def nav(cur: str) -> None:
    tabs = [("home", "오늘"), ("recurring", "정기"), ("team", "팀"), ("record", "기록"), ("settings", "설정")]
    with st.container(key="ph_nav"):
        cols = st.columns(5)
        for c, (k, label) in zip(cols, tabs):
            with c:
                if st.button(label, key=f"nav_{k}", type="primary" if cur == k else "secondary", use_container_width=True):
                    go(k, just_sent=False, picked=None)


# ---------------- 가입 흐름 ----------------
def v_splash() -> None:
    st.markdown(f'<div style="padding:70px 0 0">{ui.bowl("glance", 150)}</div>'
                '<h1 style="font-size:56px;letter-spacing:-2.5px;margin:6px 0 0;line-height:1">눈치밥</h1>'
                '<div class="mono" style="font-size:15px;font-weight:600">nunchi-bap</div>', unsafe_allow_html=True)
    ui.postit('<div style="font-size:20px;font-weight:900">눈치 보지 말고, 눈치 있게</div><div style="font-size:14px;margin-top:4px">밥 먹을 타이밍, 눈치밥이 알려 줄게!</div>', rot=-2)
    with st.container(key="ph_cta"):
        if st.button("학교 이메일로 시작하기", type="primary", use_container_width=True):
            go("email")
        st.markdown('<p class="nb-note" style="text-align:center;margin:6px 0 0">학교에서 받은 이메일만 쓸 수 있어요</p>', unsafe_allow_html=True)


def v_email() -> None:
    back("← 처음으로", "splash")
    ui.ph_head("학교 이메일로 가입", "이메일 주소로 우리 학교가 눈치밥을 쓰는지 바로 확인해요")
    ss.email = st.text_input("학교 이메일", value=ss.email, placeholder="학번@학교도메인", key=f"email_in_{ss.get('email_v', 0)}")
    kind, dom, school = email_kind(ss.email)
    if kind == "ok":
        st.markdown(f'<div class="ph-card" style="display:flex;gap:12px;align-items:center;padding:12px 14px"><span style="width:22px;height:22px;background:#111;color:#FFE14D;display:inline-flex;align-items:center;justify-content:center;font-weight:900">✓</span><span><b>{ui.e(school)}</b><br><span class="nb-note">등록된 학교예요 · {ui.e(dom)}</span></span></div>', unsafe_allow_html=True)
    elif kind == "missing":
        st.markdown(f'<div class="ph-card" style="border-style:dashed;padding:12px 14px"><b>아직 눈치밥을 쓰지 않는 학교예요</b><br><span class="nb-note">{ui.e(dom)} · 선생님께 도입을 요청할 수 있어요</span></div>', unsafe_allow_html=True)
    elif kind == "bad":
        st.markdown('<div class="ph-card" style="border-color:#B42318;color:#B42318;font-weight:700;padding:12px 14px">학교에서 받은 이메일만 쓸 수 있어요</div>', unsafe_allow_html=True)
    elif kind == "typing":
        st.caption("@ 뒤 학교 주소까지 입력해 주세요")
    st.markdown('<div style="font-size:12px;font-weight:700;margin-top:8px">데모용 예시</div>', unsafe_allow_html=True)
    for em, label in [("s25012@masong.hs.kr", "등록된 학교"), ("student@sample.hs.kr", "미등록 학교"), ("abc@gmail.com", "학교 메일 아님")]:
        if ui.tile(f"demo_{label}", f'<div class="ph-row" style="background:#fff;border:2px solid #111;margin-bottom:-2px"><span class="mono" style="font-size:13px;font-weight:600">{em}</span><span class="nb-note">{label}</span></div>', label):
            ss.email = em
            ss.email_v = ss.get("email_v", 0) + 1
            st.rerun()
    if kind == "ok":
        if cta("인증 코드 받기"):
            go("code", code="")
    elif kind == "missing":
        with st.container(key="ph_cta"):
            if st.button("우리 학교에 도입 요청하기", use_container_width=True):
                go("nope")
    else:
        cta(None, "학교 이메일을 입력해 주세요")


def v_nope() -> None:
    _, dom, _ = email_kind(ss.email)
    st.markdown(f'<div style="padding-top:50px">{ui.bowl("sad", 96)}</div><h1 style="font-size:28px;line-height:1.3">우리 학교는<br>아직 눈치밥이 없어요</h1>'
                f'<p><b class="mono">{ui.e(dom)}</b> 학교가 목록에 없어요. 요청이 모이면 학교와 교육청에 도입을 제안해요.</p>', unsafe_allow_html=True)
    ui.postit('<div style="font-size:14px;font-weight:900">선생님께 이렇게 전해 주세요</div><div style="font-size:13px;line-height:1.55;margin-top:4px">"급식 줄이 너무 길어요. 눈치밥으로 시간을 나눠 가면 덜 기다릴 수 있대요!"</div>', rot=1.5, block=True)
    with st.container(key="ph_cta"):
        if st.button("도입 요청 보내기", type="primary", use_container_width=True):
            if not DEMO:
                S["requests"].append({"domain": dom, "at": datetime.now().isoformat()})
                nb.save(S)
            go("email")
        if st.button("다른 이메일로 다시 하기", use_container_width=True):
            go("email")


def v_code() -> None:
    back("← 이메일 바꾸기", "email")
    ui.ph_head("인증 코드 입력", f'<b class="mono">{ui.e(ss.email)}</b>로 6자리 코드를 보냈어요')
    code = st.text_input("6자리 코드", value=ss.code, max_chars=6, key=f"code_in_{ss.get('code_v', 0)}")
    ss.code = re.sub(r"\D", "", code or "")[:6]
    with st.container(key="ph_dashed"):
        if st.button("데모: 메일에서 코드 붙여넣기"):
            ss.code = "482913"
            ss.code_v = ss.get("code_v", 0) + 1
            st.rerun()
    st.caption("코드가 안 왔나요? 스팸함을 확인하거나 1분 뒤 다시 보내기")
    if len(ss.code) == 6:
        if cta("확인"):
            go("profile")
    else:
        cta(None, "코드 6자리를 입력해 주세요")


def v_profile() -> None:
    ui.ph_head("몇 학년 몇 반이에요?", "반을 알면 4교시가 끝나는 시간에 맞춰 추천해요", eyebrow=f"{S['settings']['schoolName']} · 인증 완료")
    st.markdown("**학년**")
    g = ui.seg("grade", ["1학년", "2학년", "3학년"], f"{ss.grade}학년")
    if g:
        ss.grade = g[0]
        st.rerun()
    st.markdown("**반**")
    with st.container(key="grid_cls"):
        for r in (range(1, 6), range(6, 11)):
            cs = st.columns(5)
            for c, i in zip(cs, r):
                with c:
                    if st.button(str(i), key=f"cls_{i}", type="primary" if ss.cls == str(i) else "secondary", use_container_width=True):
                        ss.cls = str(i)
                        st.rerun()
    name = st.text_input("이름 (선택, 팀원에게만 보여요)", value=dm.NAME if DEMO else "")
    st.caption("학교, 학년, 반, 팀만 저장해요. 위치나 사진은 모으지 않고, 개인 기록은 학기가 끝나면 지워요.")
    if cta("다음"):
        u = {"email": ss.email.strip().lower() or "s25012@masong.hs.kr", "grade": ss.grade, "cls": ss.cls, "name": name.strip(),
             "points": dm.POINTS if DEMO else 0, "notif1": True, "notif2": True, "introDone": False, "createdAt": datetime.now().isoformat()}
        if DEMO:
            D["user"] = u
        else:
            S["user"] = u
            S["team"]["members"] = []
            nb.ensure_team(S)
            nb.save(S)
        go("intro", intro=0, intro_from="signup")


def v_intro() -> None:
    i = ss.intro
    mini = '<div style="display:grid;grid-template-columns:repeat(5,1fr);border-top:2px solid #111;border-left:2px solid #111;width:240px;margin:0 auto">' + "".join(
        f'<span style="display:block;height:40px;border-right:2px solid #111;border-bottom:2px solid #111;{ {"f": "background:#fff", "m": "background:repeating-linear-gradient(135deg,#fff 0,#fff 7px,#C9C9C9 7px,#C9C9C9 8.5px)", "b": "background:#111", "y": "background:#FFE14D"}[k]}"></span>' for k in dm.INTRO_MINI) + "</div>"
    pages = [
        ("아침, 휴대폰 내기 전에<br>급식 시간을 골라요", f"{S['settings']['deadline']}까지 칸 하나만 누르면 끝. 정기 예약을 해두면 매일 알아서 잡혀요. 팀 대표가 고르면 팀 전원이 같이 예약돼요.",
         mini + '<div style="text-align:center"><div class="nb-postit mono" style="font-size:22px;font-weight:600;padding:10px 18px"><div class="nb-tape"></div>12:35 예약 ✓</div></div>'),
        ("꽉 찬 시간은<br>눈치밥이 피해 줘요", "검정 칸은 이미 꽉 찬 시간이에요. 누르면 우리 팀이 다 들어가는 가까운 시간을 포스트잇으로 붙여 줘요.",
         '<div style="display:flex;justify-content:space-between;align-items:center;padding:12px 14px;background:#111;color:#FFF;width:230px;margin:0 auto"><span class="mono" style="font-size:18px;font-weight:600">12:20</span><b style="font-size:13px">꽉 참 · 11분</b></div>'
         '<div style="text-align:center"><div class="nb-postit" style="--r:-4deg;padding:10px 16px"><div class="nb-tape"></div><div class="mono" style="font-size:18px;font-weight:600">12:35</div><b style="font-size:12px">대기 2분</b></div> &nbsp;'
         '<div class="nb-postit" style="--r:3deg;padding:10px 16px"><div class="nb-tape"></div><div class="mono" style="font-size:18px;font-weight:600">12:10</div><b style="font-size:12px">대기 1분</b></div></div>'),
        ("점심엔 고른 시간에<br>가기만 하면 돼요", "휴대폰이 없어도 괜찮아요. 교실 화면에 지금 갈 팀이 떠요. 점심시간엔 아무것도 누를 필요 없어요.",
         '<div class="nb-board" style="max-width:270px;margin:0 auto"><div class="bh" style="font-size:11px;padding:8px 12px"><span>교실 화면 · 2학년 3반</span><span class="mono">12:34</span></div><div class="nb-brow go" style="padding:10px 12px;font-size:14px"><span class="mono">12:35</span><b style="font-size:12px">A팀 지금 가세요 →</b></div><div class="nb-brow" style="padding:10px 12px;font-size:14px;border-bottom:0"><span class="mono">12:40</span><b style="font-size:12px">E팀 · 5분 뒤</b></div></div>'),
        ("하교 후 30초,<br>오늘 어땠는지 알려 줘요", "휴대폰을 돌려받으면 세 번만 눌러 주세요. 모두의 답이 모여 내일 혼잡 예측이 더 정확해져요.",
         '<div style="text-align:center">' + "".join(f'<span style="display:inline-block;padding:9px 12px;background:#111;color:#FFF;font-weight:700;font-size:12px;margin:2px">{w}</span>' for w in ["먹었어요", "예약대로", "0~3분"])
         + '<br><div class="nb-postit" style="--r:2deg;font-size:14px;font-weight:900;padding:10px 14px"><div class="nb-tape"></div>+5P · 내일 예측이 더 정확해져요</div></div>'),
    ]
    title, text, art = pages[i]
    c1, c2 = st.columns([3, 1])
    c1.markdown(f'<div class="mono" style="font-size:13px;font-weight:600;padding-top:14px">사용법 {i + 1}/4</div>', unsafe_allow_html=True)
    with c2:
        with st.container(key="ph_link"):
            if st.button("닫기" if ss.intro_from == "settings" else "건너뛰기", key="skip"):
                end_intro()
    st.markdown(f'<div class="ph-card" style="background:#F4F3EF;height:250px;display:flex;flex-direction:column;justify-content:center;gap:14px;padding:16px">{art}</div>'
                f'<h2 style="font-size:23px;line-height:1.35;margin:18px 0 8px">{title}</h2><p style="font-size:14px;color:#333;line-height:1.6">{text}</p>', unsafe_allow_html=True)
    dots = "".join(f'<span style="display:inline-block;width:{24 if j == i else 10}px;height:10px;margin-right:6px;background:{"#111" if j == i else "#D2D2CC"}"></span>' for j in range(4))
    with st.container(key="ph_cta"):
        a, b = st.columns([2, 1])
        a.markdown(f'<div style="padding-top:18px">{dots}</div>', unsafe_allow_html=True)
        with b:
            label = "다음" if i < 3 else ("다 봤어요" if ss.intro_from == "settings" else "시작하기")
            if st.button(label, type="primary", use_container_width=True, key="intro_next"):
                if i < 3:
                    ss.intro += 1
                    st.rerun()
                end_intro()


def end_intro() -> None:
    u = user()
    if u and not u.get("introDone"):
        u["introDone"] = True
        if not DEMO:
            nb.save(S)
    go("settings" if ss.intro_from == "settings" else "home", intro=0)


# ---------------- 본 화면 ----------------
def deadline_text() -> str:
    s = S["settings"]
    if DEMO:
        return f"{s['deadline']} · {dm.DEADLINE_LEFT}"
    left = nb.deadline_left(S)
    if when() == "내일":
        return f"내일 {s['deadline']}"
    return f"{s['deadline']} · {left // 60}시간 {left % 60}분 전" if left > 0 else "마감"


def mini_cell(time: str, kind: str) -> str:
    bg = {"f": "background:#FFFFFF;color:#111", "m": "background:repeating-linear-gradient(135deg,#FFFFFF 0px,#FFFFFF 7px,#C9C9C9 7px,#C9C9C9 8.5px);color:#111",
          "b": "background:#111111;color:#FFF", "y": "background:#FFE14D;color:#111"}[kind]
    return (f'<div style="{bg};height:48px;border-right:2px solid #111;border-bottom:2px solid #111;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px">'
            f'<span class="mono" style="font-size:13px;font-weight:600">{time}</span><span style="font-size:10px;font-weight:700">{nb.KIND_WORD[kind]}</span></div>')


def v_home() -> None:
    u, s = user(), S["settings"]
    rs, b = rows(), booking()
    w = when()
    st.markdown(f'<div style="display:flex;align-items:center;gap:10px;margin:0 -20px;padding:16px 20px 10px">{ui.LOGO}<div><div style="font-size:18px;font-weight:900">좋은 아침, {ui.e(u.get("name") or "친구")}</div>'
                f'<div class="mono" style="font-size:12px;color:#555">{date_label()} · {ui.e(u["grade"])}-{ui.e(u["cls"])}</div></div></div>', unsafe_allow_html=True)
    fb_done = (not DEMO) and any(f["date"] == nb.date_key(datetime.now().date()) for f in S["feedback"])
    step3 = f'3 하교 후 기록<br><span style="font-weight:500;text-decoration:underline">{"보냈어요 ✓" if fb_done else "미리 보기 →"}</span>'
    if ui.tile("step3", f'<div class="nb-steps" style="margin:0 -20px;border-left:0;border-right:0"><div class="on">1 시간 고르기<br><span style="font-weight:500">{s["deadline"]}까지</span></div>'
                        f'<div>2 점심에 가기<br><span style="font-weight:500">고른 시간에</span></div><div>{step3}</div></div>', "하교 후 기록 미리 보기"):
        go("feedback")
    st.markdown(f'<div style="display:grid;grid-template-columns:1fr 1fr;margin:-10px -20px 0;border-bottom:2px solid #111;background:#fff">'
                f'<div style="padding:12px 20px;border-right:2px solid #111"><div style="font-size:11px;font-weight:700;color:#555">{w} 메뉴 · 인기 {s["menu"]["pop"]}/10</div><div style="font-size:15px;font-weight:900">{ui.e(s["menu"]["name"])}</div></div>'
                f'<div style="padding:12px 14px"><div style="font-size:11px;font-weight:700;color:#555">예약 마감</div><div class="mono ph-red" style="font-size:15px">{deadline_text()}</div></div></div>', unsafe_allow_html=True)
    st.markdown(f'<div style="display:flex;justify-content:space-between;align-items:baseline;margin-top:10px"><b style="font-size:15px">{w} 예상 혼잡</b><span class="nb-note" style="font-size:11px">흰 칸 여유 · 빗금 보통 · 검정 꽉 참</span></div>', unsafe_allow_html=True)
    mine = b["slot"] if b else None
    cells = "".join(mini_cell(r["time"], "y" if r["time"] == mine else r["kind"]) for r in rs)
    st.markdown(f'<div style="display:grid;grid-template-columns:repeat(5,minmax(0,1fr));border-top:2px solid #111;border-left:2px solid #111;background:#fff">{cells}</div>', unsafe_allow_html=True)
    if b:
        br = nb.slot_row(rs, b["slot"])
        ui.postit(f'<div style="display:flex;justify-content:space-between"><b style="font-size:12px">내 예약 · {ui.e(b["kind"])}</b><b style="font-size:12px">팀 {team_n()}명</b></div>'
                  f'<div style="margin-top:4px"><span class="mono" style="font-size:44px;font-weight:600;line-height:1">{b["slot"]}</span> &nbsp;<b style="font-size:13px">대기 약 {br["wait"] if br else 0}분</b></div>', rot=-1.5, block=True)
    else:
        ui.postit(f'<b style="font-size:13px">{w} 예약이 아직 없어요</b><div style="font-size:13px;margin-top:4px">칸을 골라 두면 팀 {team_n()}명이 같이 잡혀요</div>', rot=-1.5, block=True)
    c1, c2 = st.columns(2)
    if c1.button(f"{w}만 바꾸기" if b else "시간 고르기", type="primary", use_container_width=True):
        go("reserve", picked=None)
    if c2.button("팀원 참석 확인", use_container_width=True):
        go("team")
    nav("home")


def slot_label(r: dict) -> str:
    return f'대기 {r["wait"]}분 · {"남은 자리 " + str(r["left"]) if r["left"] > 0 else "마감"}'


def slot_grid(rs: list[dict], b: dict | None, clickable: bool = True, dim: bool = False) -> None:
    mine = b["slot"] if b else None
    if not clickable:
        cells = "".join(ui.cell_html(r["time"], nb.KIND_WORD["y" if r["time"] == mine else r["kind"]], "y" if r["time"] == mine else r["kind"],
                                     slot_label(r), ring=ss.picked == r["time"]) for r in rs)
        st.markdown(f'<div style="display:grid;grid-template-columns:1fr 1fr;border-top:2px solid #111;border-left:2px solid #111;{"opacity:.45" if dim else ""}">{cells}</div>', unsafe_allow_html=True)
        return
    with st.container(key="grid_slots"):
        for i in range(0, len(rs), 2):
            cs = st.columns(2)
            for c, r in zip(cs, rs[i:i + 2]):
                k = "y" if r["time"] == mine else r["kind"]
                with c:
                    if ui.tile(f"slot_{r['time'].replace(':', '')}", ui.cell_html(r["time"], nb.KIND_WORD[k], k, slot_label(r), ring=ss.picked == r["time"]), f"{r['time']} 고르기"):
                        ss.picked = r["time"]
                        st.rerun()


def v_reserve() -> None:
    s = S["settings"]
    rs, b, ts, w = rows(with_me=False), booking(), team_n(), when()
    back(f"← {w}", "home")
    ui.ph_head(f"{w}만 시간 바꾸기", "칸마다 예상 대기시간과 남은 자리예요", right=f"마감 {s['deadline']}", right_red=True)
    slot_grid(rs, b)
    p = nb.slot_row(rs, ss.picked) if ss.picked else None
    with st.container(key="ph_cta"):
        if not p:
            st.markdown('<div class="ph-wait">바꿀 시간을 위에서 골라 주세요</div>', unsafe_allow_html=True)
        elif p["kind"] == "b" or p["left"] < ts:
            st.markdown(f'<b style="font-size:14px">{p["time"]}은 꽉 찼어요 · 지금 가면 약 {p["wait"]}분</b>', unsafe_allow_html=True)
            if st.button("덜 붐비는 시간 추천 받기", type="primary", use_container_width=True):
                go("rec")
        else:
            st.markdown(f'<b style="font-size:14px">{p["time"]} · 대기 약 {p["wait"]}분 · 팀 {ts}명</b>', unsafe_allow_html=True)
            if st.button(f"{p['time']}로 예약하기", type="primary", use_container_width=True):
                book(p["time"], f"{w}만 변경")
                go("confirm", picked=None)


def v_rec() -> None:
    rs, b, ts, w = rows(with_me=False), booking(), team_n(), when()
    p = nb.slot_row(rs, ss.picked) if ss.picked else None
    if not p:
        go("reserve")
    st.markdown(f'<div style="margin:0 -20px;padding:16px 20px 8px;opacity:.45"><span class="nb-note">← {w}</span><h1 style="font-size:24px;margin:6px 0 2px">{w}만 시간 바꾸기</h1></div>', unsafe_allow_html=True)
    slot_grid(rs[:6], b, clickable=False, dim=True)
    st.markdown(f'<div style="display:flex;justify-content:space-between;margin:-10px -20px 0;padding:12px 20px;background:#111;color:#FFF;font-weight:900;font-size:13px"><span>고른 시간</span><span class="mono">{p["time"]} · 꽉 참</span></div>'
                f'<div style="display:flex;align-items:center;gap:12px;margin-top:10px">{ui.bowl("shock", 54)}<h3 style="margin:0;font-size:20px">헉, {p["time"]}은 꽉 찼어요</h3></div>'
                f'<p style="font-size:13px;margin:4px 0 0">지금 가면 약 <b>{p["wait"]}분</b> 줄을 서요. 우리 팀 {ts}명이 다 들어가는 시간을 붙여 뒀어요.</p>', unsafe_allow_html=True)
    rl = recs(p)
    if not rl:
        st.warning("지금은 팀이 다 들어가는 칸이 없어요. 대기 명단에 올려 두세요.")
    for i, r in enumerate(rl):
        html = (f'<div class="nb-postit block" style="--r:{r["rot"]}deg;display:grid;grid-template-columns:76px 1fr auto;align-items:center;gap:10px;padding:14px 14px 10px;margin:14px 0 4px">'
                f'<div class="nb-tape"></div><span class="mono" style="font-size:24px;font-weight:600">{r["time"]}</span><span><b style="font-size:13px">{r["tag"]} · 대기 {r["wait"]}분</b><br>'
                f'<span style="font-size:11px">{r["save"]}분 덜 기다림 · {r["pt"]}</span></span><span>→</span></div>')
        if ui.tile(f"rec_{i}", html, f"{r['time']}로 바꾸기"):
            book(r["time"], f"{w}만 변경" if DEMO else "추천 수락")
            if not DEMO:  # 시안: 추천 수락 포인트는 화면에만 표시
                add_points(int(r["pt"].strip("+P")))
                S["recLog"].append({"date": nb.date_key(target()), "from": p["time"], "to": r["time"], "accepted": True, "pa": r.get("pa")})
                nb.save(S)
            go("confirm", picked=None)
    if st.button(f"그래도 {p['time']} 대기 명단에 올리기", use_container_width=True):
        if not DEMO:
            S["waitlist"][nb.date_key(target())] = p["time"]
            S["recLog"].append({"date": nb.date_key(target()), "from": p["time"], "to": None, "accepted": False, "pa": rl[0].get("pa") if rl else None})
            nb.save(S)
        go("reserve")


def v_confirm() -> None:
    b = booking()
    rs = rows()
    r = nb.slot_row(rs, b["slot"]) if b else None
    after = nb.mins(b["slot"]) - nb.mins(S["settings"]["lunchStart"]) if b else 0
    at = f"{dm.DATE} · {dm.CONFIRM_AT}" if DEMO else f"{nb.fmt_date(target())} · {nb.now_hhmm()}"
    st.markdown(f'<div style="display:flex;justify-content:space-between;align-items:flex-start;padding-top:18px"><div><div class="mono nb-note">{at}</div><h1 style="margin:4px 0 2px;font-size:26px">{when()} 예약 확정</h1>'
                f'<div class="nb-note">휴대폰 내기 전에 기억해 두세요</div></div>{ui.bowl("happy", 72)}</div>', unsafe_allow_html=True)
    ui.postit(f'<div style="text-align:center;padding:10px 0"><b style="font-size:14px">{when()} 급식 시간</b><div class="mono" style="font-size:76px;font-weight:600;line-height:1;margin-top:8px">{b["slot"] if b else "--:--"}</div>'
              f'<b style="font-size:16px">점심시간 시작하고 {after}분 뒤</b></div><div style="position:absolute;right:16px;top:18px" class="nb-stamp">확정</div>', rot=-2, block=True)
    st.markdown(f'<table class="ph-tbl"><tr><th>우리 팀</th><td>{team_n()}명 같이 예약됨</td></tr><tr><th>예상 대기</th><td>약 {r["wait"] if r else 0}분</td></tr>'
                f'<tr><th>교실 화면</th><td>{b["slot"] if b else ""}에 "지금 갈 팀"으로 떠요</td></tr></table>', unsafe_allow_html=True)
    if cta("확인했어요"):
        go("home")


def v_feedback() -> None:
    w = when()
    back(f"← {w}", "home")
    at = dm.FEEDBACK_AT if DEMO else nb.now_hhmm()
    ui.ph_head("오늘 급식 어땠어?", f"{at} · 팀 대표가 팀 대신 답해요 · 30초면 끝")
    fb = ss.fb
    for key, title, opts in [("a1", "1. 오늘 급식 먹었어?", ["예", "아니오"]), ("a2", "2. 몇 시쯤 줄 섰어?", ["예약대로", "더 일찍", "더 늦게"]),
                             ("a3", "3. 줄에서 얼마나 기다렸어?", list(nb.BUCKETS.keys()))]:
        st.markdown(f'<b style="font-size:14px">{title}</b>', unsafe_allow_html=True)
        v = ui.seg(f"fb_{key}", opts, fb[key])
        if v:
            fb[key] = v
            st.rerun()
    st.markdown('<b style="font-size:14px">4. 오늘 같이 먹은 팀원</b> <span class="nb-note">(안 온 사람은 눌러서 빼기)</span>', unsafe_allow_html=True)
    u = user()
    if DEMO:
        names = [u.get("name") or "나"] + dm.FB_TEAM
        out = D["fb_out"]
    else:
        names = [m["name"] for m in S["team"]["members"]]
        out = ss.setdefault("fb_out_live", set())
    with st.container(key="seg_team"):
        cs = st.columns(len(names))
        for c, n in zip(cs, names):
            with c:
                here = n not in out
                if st.button(f"{'✓' if here else '—'} {n}", key=f"fbm_{n}", type="primary" if here else "secondary", use_container_width=True):
                    out.symmetric_difference_update({n})
                    st.rerun()
    if cta("보내기 · +5P"):
        if DEMO:
            D["points"] += 5
        else:
            nb.send_feedback(S, datetime.now().date(), {"ate": fb["a1"], "timing": fb["a2"], "bucket": fb["a3"] or "3~6분", "present": [n for n in names if n not in out]})
        go("record", just_sent=True)


def v_record() -> None:
    ui.ph_head("내 기록", eyebrow="2026 2학기" if DEMO else f"{datetime.now().year} 2학기")
    if DEMO:
        k1, k2 = dm.RECORD_KPIS
        week = list(dm.WEEK)
        sent = dm.RECORD_SENT
        badges = dm.BADGES
    else:
        wk = nb.week_records(S)
        done = [d for d in wk if d["wait"] is not None]
        k1 = f"{round(sum(max(0, max(d['expected'] or 0, 10) - d['wait']) for d in done))}분"
        k2 = f"{sum(d['wait'] for d in done) / len(done):.1f}분" if done else "—"
        week = [(d["day"], d["wait"] if d["wait"] is not None else 0, "f" if d["wait"] is None else "b" if d["wait"] >= 10 else "m" if d["wait"] >= 4 else "f") for d in wk]
        last = S["feedback"][-1] if S["feedback"] else None
        sent = f'오늘 {last["wait"]:g}분 기다렸어요. 평소 시간에 갔다면 약 {max(last["expected"], 10)}분.' if last else ""
        acc = sum(1 for r in S["recLog"] if r.get("accepted"))
        badges = [(f"피드백 {len(S['feedback'])}번", False), (f"추천 {acc}번 수락", False)]
    if ss.just_sent:
        ui.postit(f'<b style="font-size:16px">+5P · 고마워요!</b><div style="font-size:12px;margin-top:2px">{sent}</div>', rot=1.5, block=True)
    st.markdown('<div style="display:grid;grid-template-columns:repeat(3,1fr);border:2px solid #111;background:#fff;text-align:center">'
                + "".join(f'<div style="padding:12px 4px;{"border-right:2px solid #111" if j < 2 else ""}"><div class="mono" style="font-size:20px;font-weight:600">{v}</div><div style="font-size:11px;color:#555">{l}</div></div>'
                          for j, (v, l) in enumerate([(k1, "이번 주 아낀 시간"), (k2, "주 평균 대기"), (f"{points()}P", "포인트")])) + "</div>", unsafe_allow_html=True)
    mx = max([11] + [v for _, v, _ in week])
    bg = {"f": "background:#fff", "m": "background:repeating-linear-gradient(135deg,#fff 0,#fff 7px,#C9C9C9 7px,#C9C9C9 8.5px)", "b": "background:#111"}
    bars = "".join(f'<div style="display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%"><span class="mono" style="font-size:12px;font-weight:600;margin-bottom:3px">{v:g}</span>'
                   f'<i style="display:block;width:100%;border:2px solid #111;border-bottom:0;height:{max(6, round(v / mx * 86))}px;{bg[k]}"></i></div>' for _, v, k in week)
    st.markdown(f'<div class="ph-card" style="padding:14px 16px"><b style="font-size:14px">이번 주 대기시간 (분)</b><div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px;height:120px;align-items:end;border-bottom:2px solid #111;margin-top:10px">{bars}</div>'
                f'<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-top:4px;text-align:center;font-size:12px;font-weight:700">{"".join(f"<span>{d}</span>" for d, _, _ in week)}</div></div>', unsafe_allow_html=True)
    st.markdown("".join(f'<span class="ph-badge{" dash" if dsh else ""}">{ui.e(t)}</span>' for t, dsh in badges), unsafe_allow_html=True)
    nav("record")


def v_team() -> None:
    u = user()
    if DEMO:
        members = [(f"{dm.SURNAME}{u.get('name')}" if u.get("name") else "나", "대표", f"{u['grade']}-{u['cls']}")] + list(dm.MEMBERS)
        out = D["team_out"]
        code = dm.INVITE
    else:
        members = [(m["name"], "대표" if m.get("lead") else "", m["cls"]) for m in S["team"]["members"]]
        out = {m["name"] for m in S["team"]["members"] if not m.get("present", True)}
        code = S["team"]["code"]
    st.markdown(f'<div style="display:flex;justify-content:space-between;align-items:center;padding-top:18px;margin-bottom:-14px"><span class="nb-note">초대코드</span><span class="mono" style="border:2px solid #111;padding:2px 8px;font-size:16px;font-weight:600;background:#fff">{code}</span></div>', unsafe_allow_html=True)
    ui.ph_head(f"우리 팀 · {len(members)}명", "대표가 예약하면 팀원 모두 같은 시간으로 잡혀요")
    with st.container(key="team_list", border=False):
        for i, (n, role, cls) in enumerate(members):
            here = n not in out
            c1, c2 = st.columns([3, 1], vertical_alignment="center")
            c1.markdown(f'<div style="padding:6px 2px"><b style="font-size:15px">{ui.e(n)}</b> <span class="nb-note">{role}</span><br><span class="mono nb-note">{ui.e(cls)}</span></div>', unsafe_allow_html=True)
            with c2:
                if st.button("참석" if here else "불참", key=f"present_{i}", type="secondary" if here else "primary", use_container_width=True):
                    if DEMO:
                        out.symmetric_difference_update({n})
                    else:
                        m = S["team"]["members"][i]
                        m["present"] = not m.get("present", True)
                        nb.save(S)
                    st.rerun()
    c1, c2 = st.columns(2)
    if c1.button("팀원 초대", type="primary", use_container_width=True):
        ss.inviting = not ss.get("inviting", False)
        st.rerun()
    if c2.button("대표 바꾸기", use_container_width=True) and not DEMO:
        ms = S["team"]["members"]
        if len(ms) > 1:
            li = next((i for i, m in enumerate(ms) if m.get("lead")), 0)
            for m in ms:
                m["lead"] = False
            ms[(li + 1) % len(ms)]["lead"] = True
            nb.save(S)
            st.rerun()
    if ss.get("inviting"):
        st.caption(f"초대코드 {code}를 알려 주면 친구가 직접 들어와요.")
        if not DEMO:
            nm = st.text_input("친구 이름 (시연용 바로 추가)", key="invite_name")
            if st.button("추가", disabled=not nm.strip()):
                S["team"]["members"].append({"name": nm.strip(), "cls": f"{u['grade']}-{u['cls']}", "lead": False, "present": True})
                nb.save(S)
                st.rerun()
    nav("team")


def v_recurring() -> None:
    eyebrow = f"{dm.RECURRING_MONTH} · 팀 {team_n()}명" if DEMO else f"{datetime.now():%b %Y}".upper() + f" · 팀 {team_n()}명"
    ui.ph_head("정기 예약", "한 번 정하면 매일 아침 자동으로 예약돼요", eyebrow=eyebrow)
    rc = S["recurring"]
    cur = D["period"] if DEMO else rc.get("period", "1개월")
    v = ui.seg("period", ["1주", "1개월", "학기"], cur)
    if v:
        if DEMO:
            D["period"] = v
        else:
            rc["period"] = v
            nb.save(S)
        st.rerun()
    days = dm.RECURRING if DEMO else [(d, *((rc["days"].get(d) or ["", "", ""]) + ["", "", ""])[:3]) for d in ["월", "화", "수", "목", "금"]]
    th = 'style="background:#111;color:#fff;text-align:center"'
    body = "".join(f'<tr><th style="text-align:center;width:16%">{d}</th><td class="mono" style="text-align:center;background:#FFE14D;font-weight:600">{a or "—"}</td>'
                   f'<td class="mono" style="text-align:center">{b or "—"}</td><td class="mono" style="text-align:center">{c or "—"}</td></tr>' for d, a, b, c in days)
    st.markdown(f'<table class="ph-tbl"><tr><th {th}>요일</th><th {th}>1순위</th><th {th}>2순위</th><th {th}>3순위</th></tr>{body}</table>', unsafe_allow_html=True)
    if not DEMO:
        with st.expander("정기 예약 바꾸기"):
            opts = ["—"] + nb.slots(S)
            changed = False
            for d in ["월", "화", "수", "목", "금"]:
                prefs = (rc["days"].get(d) or ["", "", ""]) + ["", "", ""]
                cols = st.columns([1, 2, 2, 2])
                cols[0].markdown(f"**{d}**")
                new = []
                for j in range(3):
                    cv = prefs[j] if prefs[j] in opts else "—"
                    x = cols[j + 1].selectbox(f"{d}{j}", opts, index=opts.index(cv), key=f"rc_{d}_{j}", label_visibility="collapsed")
                    new.append("" if x == "—" else x)
                if new != (rc["days"].get(d) or ["", "", ""])[:3]:
                    rc["days"][d] = new
                    changed = True
            if changed:
                for k in [k for k, bk in S["bookings"].items() if bk.get("auto")]:
                    del S["bookings"][k]
                nb.save(S)
    ui.postit(f'<b style="font-size:13px">이렇게 배정돼요</b><br><span style="font-size:12px;line-height:1.6">자리의 {round(S["settings"]["ratio"] * 100)}%까지만 정기 예약으로 채워요 · 1순위를 못 받은 달은 다음 달 먼저 · 시험과 행사 날은 자동으로 쉬어요</span>', rot=1, block=True)
    nav("recurring")


def v_settings() -> None:
    u = user()
    ui.ph_head("설정")
    email = u.get("email") or "s25012@masong.hs.kr"
    st.markdown(f'<div class="ph-card" style="display:flex;align-items:center;gap:12px;padding:14px 16px"><span style="width:44px;height:44px;display:inline-flex;align-items:center;justify-content:center;background:#FFE14D;border:2px solid #111;font-size:18px;font-weight:900">{ui.e((u.get("name") or "나")[:1])}</span>'
                f'<div><b style="font-size:15px">{ui.e(u.get("name") or "친구")} · {ui.e(u["grade"])}학년 {ui.e(u["cls"])}반</b><br><span class="mono nb-note">{ui.e(email)}</span></div></div>', unsafe_allow_html=True)
    box = D if DEMO else u
    for key, label, sub in [("notif1", "전날 밤 예약 알림", "21:00 · 내일 메뉴와 혼잡 예상"), ("notif2", "마감 알림", "07:00 · 휴대폰 내기 30분 전")]:
        v = box.get(key, True)
        sw = (f'<span class="ph-sw" style="background:{"#111" if v else "#fff"}"><i style="left:{25 if v else 3}px;background:{"#FFE14D" if v else "#111"}"></i></span>')
        if ui.tile(f"sw_{key}", f'<div class="ph-row" style="background:#fff;border:2px solid #111;margin-bottom:-12px"><span><b style="font-size:14px">{label}</b><br><span class="nb-note">{sub}</span></span>{sw}</div>', label):
            box[key] = not v
            if not DEMO:
                nb.save(S)
            st.rerun()
    for key, label, action in [("intro", "사용법 다시 보기", "intro"), ("rec", "정기 예약 관리", "recurring"), ("team", "팀 관리", "team"), ("privacy", "개인정보 처리 안내", None)]:
        with st.container(key=f"menu_{key}"):
            if st.button(f"{label}  →", key=f"m_{key}", use_container_width=True):
                if action == "intro":
                    go("intro", intro=0, intro_from="settings")
                elif action:
                    go(action)
                else:
                    ss.show_privacy = not ss.get("show_privacy", False)
                    st.rerun()
    if ss.get("show_privacy"):
        st.markdown('<div class="ph-card" style="padding:12px 16px;font-size:13px;line-height:1.7">저장: 학교 이메일(가입 확인용), 학년·반, 팀, 예약 칸, 하교 후 응답<br>저장하지 않음: 위치, 사진, 연락처, 실명(선택)<br>보관: 학기 종료 시 개인 기록 삭제, 통계만 남김<br>도입: 학교운영위원회 심의 후 운영</div>', unsafe_allow_html=True)
    with st.container(key="ph_logout"):
        if st.button("로그아웃", use_container_width=True):
            if DEMO:
                del ss["d"]
            else:
                S["user"] = None
                nb.save(S)
            go("splash", email="", code="", intro=0, fb={"a1": "예", "a2": "예약대로", "a3": None})
    c1, c2 = st.columns(2)
    c1.page_link("pages/1_관리자.py", label="관리자 웹 →")
    c2.page_link("pages/2_교실_배정표.py", label="교실 배정표 →")
    st.caption("눈치밥 nunchi-bap · 마송고등학교 모의창업" + (" · 시연 모드" if DEMO else ""))
    nav("settings")


VIEWS = {"splash": v_splash, "email": v_email, "nope": v_nope, "code": v_code, "profile": v_profile, "intro": v_intro,
         "home": v_home, "reserve": v_reserve, "rec": v_rec, "confirm": v_confirm, "feedback": v_feedback, "record": v_record,
         "team": v_team, "recurring": v_recurring, "settings": v_settings}

if not user() and ss.screen not in ("splash", "email", "nope", "code", "profile"):
    ss.screen = "splash"
if user() and not DEMO:
    nb.ensure_team(S)
VIEWS[ss.screen]()
