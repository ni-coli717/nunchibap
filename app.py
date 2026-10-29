"""눈치밥 nunchi-bap — 학생 앱 (Streamlit)
실행: streamlit run app.py
"""
from __future__ import annotations

import re
from datetime import datetime

import streamlit as st

import nb_core as nb
import nb_ui as ui

st.set_page_config(page_title="눈치밥", page_icon="🍚", layout="centered", initial_sidebar_state="collapsed")
ui.inject()

S = nb.load()
ss = st.session_state
ss.setdefault("screen", "home" if S["user"] and S["user"].get("introDone") else "splash")
ss.setdefault("intro", 0)
ss.setdefault("intro_from", "signup")
ss.setdefault("picked", None)
ss.setdefault("rec", False)
ss.setdefault("just_sent", False)
ss.setdefault("email", "")
ss.setdefault("edit_day", None)


def go(screen: str) -> None:
    ss.screen = screen
    ss.picked = None
    ss.rec = False
    if screen != "record":
        ss.just_sent = False
    st.rerun()


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


def tabbar(cur: str) -> None:
    tabs = [("home", "오늘"), ("recurring", "정기"), ("team", "팀"), ("record", "기록"), ("settings", "설정")]
    st.markdown("<hr style='border:0;border-top:2px solid #111;margin:18px 0 8px'>", unsafe_allow_html=True)
    cols = st.columns(5)
    for c, (k, label) in zip(cols, tabs):
        with c:
            if st.button(label, key=f"tab_{k}", type="primary" if cur == k else "secondary", use_container_width=True):
                go(k)


# ---------------- 가입 흐름 ----------------
def v_splash() -> None:
    st.markdown(f'<div style="padding:30px 0 6px">{ui.bowl("glance", 150)}</div>', unsafe_allow_html=True)
    st.markdown('<h1 style="font-size:56px;letter-spacing:-2.5px;margin:0">눈치밥</h1><div class="mono" style="font-size:15px;font-weight:600">nunchi-bap</div>', unsafe_allow_html=True)
    ui.postit('<div style="font-size:20px;font-weight:900">눈치 보지 말고, 눈치 있게</div><div style="font-size:14px;margin-top:4px">밥 먹을 타이밍, 눈치밥이 알려 줄게!</div>')
    if st.button("학교 이메일로 시작하기", type="primary", use_container_width=True):
        go("email")
    st.markdown('<p class="nb-note" style="text-align:center">학교에서 받은 이메일만 쓸 수 있어요</p>', unsafe_allow_html=True)


def v_email() -> None:
    ui.head("가입", "학교 이메일로 가입", "이메일 주소로 우리 학교가 눈치밥을 쓰는지 바로 확인해요")
    ss.email = st.text_input("학교 이메일", value=ss.email, placeholder="학번@학교도메인", key="email_in")
    kind, dom, school = email_kind(ss.email)
    if kind == "ok":
        st.markdown(f'<div class="nb-card">✓ <b>{ui.e(school)}</b> · 등록된 학교예요 · {ui.e(dom)}</div>', unsafe_allow_html=True)
    elif kind == "missing":
        st.markdown(f'<div class="nb-card" style="border-style:dashed"><b>아직 눈치밥을 쓰지 않는 학교예요</b><br><span class="nb-note">{ui.e(dom)} · 선생님께 도입을 요청할 수 있어요</span></div>', unsafe_allow_html=True)
    elif kind == "bad":
        st.markdown('<div class="nb-card" style="border-color:#B42318;color:#B42318;font-weight:700">학교에서 받은 이메일만 쓸 수 있어요</div>', unsafe_allow_html=True)
    elif kind == "typing":
        st.caption("@ 뒤 학교 주소까지 입력해 주세요")
    st.markdown("**데모용 예시**")
    c1, c2, c3 = st.columns(3)
    for c, em, label in [(c1, "s25012@masong.hs.kr", "등록된 학교"), (c2, "student@sample.hs.kr", "미등록 학교"), (c3, "abc@gmail.com", "학교 메일 아님")]:
        with c:
            if st.button(label, key=f"demo_{em}", use_container_width=True):
                ss.email = em
                ss.pop("email_in", None)
                st.rerun()
    st.write("")
    if kind == "ok":
        if st.button("인증 코드 받기", type="primary", use_container_width=True):
            go("code")
    elif kind == "missing":
        if st.button("우리 학교에 도입 요청하기", use_container_width=True):
            go("nope")
    if st.button("← 처음으로", key="back_splash"):
        go("splash")


def v_nope() -> None:
    _, dom, _ = email_kind(ss.email)
    st.markdown(ui.bowl("sad", 96), unsafe_allow_html=True)
    st.markdown("## 우리 학교는 아직 눈치밥이 없어요")
    st.markdown(f'<span class="mono"><b>{ui.e(dom)}</b></span> 학교가 목록에 없어요. 요청이 모이면 학교와 교육청에 도입을 제안해요.', unsafe_allow_html=True)
    ui.postit('<div style="font-size:14px;font-weight:900">선생님께 이렇게 전해 주세요</div><div style="font-size:13px;line-height:1.55;margin-top:4px">"급식 줄이 너무 길어요. 눈치밥으로 시간을 나눠 가면 덜 기다릴 수 있대요!"</div>', rot=1.5)
    if st.button("도입 요청 보내기", type="primary", use_container_width=True):
        S["requests"].append({"domain": dom, "at": datetime.now().isoformat()})
        nb.save(S)
        st.success("도입 요청을 보냈어요. 선생님께 전해 주세요!")
    if st.button("다른 이메일로 다시 하기", use_container_width=True):
        go("email")


def v_code() -> None:
    ui.head("가입", "인증 코드 입력", f"{ss.email}로 6자리 코드를 보냈어요")
    ss.setdefault("code_val", "")
    code = st.text_input("6자리 코드", value=ss.code_val, max_chars=6, placeholder="000000")
    if st.button("데모: 메일에서 코드 붙여넣기"):
        ss.code_val = "482913"
        st.rerun()
    st.caption("코드가 안 왔나요? 스팸함을 확인하거나 1분 뒤 다시 보내기")
    if len(re.sub(r"\D", "", code or "")) == 6:
        if st.button("확인", type="primary", use_container_width=True):
            go("profile")
    if st.button("← 이메일 바꾸기"):
        go("email")


def v_profile() -> None:
    ui.head(f"{S['settings']['schoolName']} · 인증 완료", "몇 학년 몇 반이에요?", "반을 알면 4교시가 끝나는 시간에 맞춰 추천해요")
    grade = st.radio("학년", ["1", "2", "3"], index=1, horizontal=True, format_func=lambda g: f"{g}학년")
    cls = st.radio("반", [str(i) for i in range(1, 11)], index=2, horizontal=True)
    name = st.text_input("이름 (선택, 팀원에게만 보여요)")
    st.caption("학교, 학년, 반, 팀만 저장해요. 위치나 사진은 모으지 않고, 개인 기록은 학기가 끝나면 지워요.")
    if st.button("다음", type="primary", use_container_width=True):
        S["user"] = {"email": ss.email.strip().lower(), "grade": grade, "cls": cls, "name": name.strip(), "points": 0,
                     "notif1": True, "notif2": True, "introDone": False, "createdAt": datetime.now().isoformat()}
        S["team"]["members"] = []
        nb.ensure_team(S)
        nb.save(S)
        ss.intro, ss.intro_from = 0, "signup"
        go("intro")


def v_intro() -> None:
    i = ss.intro
    dl = S["settings"]["deadline"]
    pages = [
        ("아침, 휴대폰 내기 전에 급식 시간을 골라요", f"{dl}까지 칸 하나만 누르면 끝. 정기 예약을 해두면 매일 알아서 잡혀요. 팀 대표가 고르면 팀 전원이 같이 예약돼요.",
         '<div class="nb-grid" style="max-width:260px">' + "".join(f'<div class="nb-cell k-{k}" style="height:40px"></div>' for k in "fmbbmyffff") + '</div><div class="nb-postit mono" style="font-size:20px;font-weight:600;padding:12px 16px"><div class="nb-tape"></div>12:35 예약 ✓</div>'),
        ("꽉 찬 시간은 눈치밥이 피해 줘요", "검정 칸은 이미 꽉 찬 시간이에요. 누르면 우리 팀이 다 들어가는 가까운 시간을 포스트잇으로 붙여 줘요.",
         '<div style="display:inline-block;padding:12px 14px;background:#111;color:#FFF"><span class="mono" style="font-size:18px;font-weight:600">12:20</span> &nbsp;<b>꽉 참 · 11분</b></div><br><div class="nb-postit" style="--r:-4deg"><div class="nb-tape"></div><div class="mono" style="font-size:18px;font-weight:600">12:35</div><b style="font-size:12px">대기 2분</b></div> <div class="nb-postit" style="--r:3deg"><div class="nb-tape"></div><div class="mono" style="font-size:18px;font-weight:600">12:10</div><b style="font-size:12px">대기 1분</b></div>'),
        ("점심엔 고른 시간에 가기만 하면 돼요", "휴대폰이 없어도 괜찮아요. 교실 화면에 지금 갈 팀이 떠요. 점심시간엔 아무것도 누를 필요 없어요.",
         '<div class="nb-board" style="max-width:300px"><div class="bh" style="font-size:12px;padding:8px 12px"><span>교실 화면 · 2학년 3반</span><span class="mono">12:34</span></div><div class="nb-brow go" style="padding:10px 12px;font-size:14px"><span class="mono">12:35</span><b>A팀 지금 가세요 →</b></div><div class="nb-brow" style="padding:10px 12px;font-size:14px"><span class="mono">12:40</span><b>E팀 · 5분 뒤</b></div></div>'),
        ("하교 후 30초, 오늘 어땠는지 알려 줘요", "휴대폰을 돌려받으면 세 번만 눌러 주세요. 모두의 답이 모여 내일 혼잡 예측이 더 정확해져요.",
         '<span style="display:inline-block;padding:10px 12px;background:#111;color:#FFF;font-weight:700;margin:2px">먹었어요</span><span style="display:inline-block;padding:10px 12px;background:#111;color:#FFF;font-weight:700;margin:2px">예약대로</span><span style="display:inline-block;padding:10px 12px;background:#111;color:#FFF;font-weight:700;margin:2px">0~3분</span><br><div class="nb-postit" style="--r:2deg;font-size:15px;font-weight:900"><div class="nb-tape"></div>+5P · 내일 예측이 더 정확해져요</div>'),
    ]
    title, text, art = pages[i]
    st.markdown(f'<div class="nb-eyebrow">사용법 {i + 1}/4</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="nb-card" style="padding:24px 16px;background:#F4F3EF">{art}</div>', unsafe_allow_html=True)
    st.markdown(f"## {title}")
    st.write(text)
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("닫기" if ss.intro_from == "settings" else "건너뛰기", use_container_width=True):
            end_intro()
    with c2:
        if st.button("다음" if i < 3 else ("다 봤어요" if ss.intro_from == "settings" else "시작하기"), type="primary", use_container_width=True):
            if i < 3:
                ss.intro += 1
                st.rerun()
            else:
                end_intro()


def end_intro() -> None:
    if not S["user"].get("introDone"):
        S["user"]["introDone"] = True
        nb.save(S)
    go("settings" if ss.intro_from == "settings" else "home")


# ---------------- 본 화면 ----------------
def v_home() -> None:
    u, s = S["user"], S["settings"]
    t = nb.target_date(S)
    rows = nb.queue(S, t)
    b = nb.current_booking(S, t)
    today = nb.is_today(t)
    left = nb.deadline_left(S)
    when = "오늘" if today else "내일"
    h = datetime.now().hour
    greet = "좋은 아침" if h < 11 else "안녕" if h < 17 else "수고했어"
    st.markdown(f'<div style="display:flex;align-items:center;gap:10px;padding:6px 0 10px;border-bottom:2px solid #111">{ui.LOGO}<div><div style="font-size:18px;font-weight:900">{greet}, {ui.e(u.get("name") or "친구")}</div><div class="mono" style="font-size:12px;color:#555">{nb.fmt_date(datetime.now().date())} · {ui.e(u["grade"])}-{ui.e(u["cls"])}</div></div></div>', unsafe_allow_html=True)
    fb_done = any(f["date"] == nb.date_key(datetime.now().date()) for f in S["feedback"])
    st.markdown(f'<div class="nb-steps"><div class="on">1 시간 고르기<br><span style="font-weight:500">{s["deadline"]}까지</span></div><div>2 점심에 가기<br><span style="font-weight:500">고른 시간에</span></div><div>3 하교 후 기록<br><span style="font-weight:500">{"보냈어요 ✓" if fb_done else "휴대폰 받으면"}</span></div></div>', unsafe_allow_html=True)
    dl = (f"{s['deadline']} · {left // 60}시간 {left % 60}분 전" if left > 0 else "마감") if today else f"내일 {s['deadline']}"
    ui.kpis([(f"{when} 메뉴 · 인기 {s['menu']['pop']}/10", s["menu"]["name"], "나이스 급식식단"), ("예약 마감", dl, "휴대폰 수거 전")])
    st.markdown(f"**{when} 예상 혼잡** <span class='nb-note'>흰 칸 여유 · 빗금 보통 · 검정 꽉 참</span>", unsafe_allow_html=True)
    ui.grid(rows, b["slot"] if b else None)
    if b:
        br = nb.slot_row(rows, b["slot"])
        ui.postit(f'<div style="display:flex;justify-content:space-between;gap:20px"><b style="font-size:12px">{when} 예약 · {ui.e(b["kind"])}</b><b style="font-size:12px">팀 {nb.team_count(S)}명</b></div><div style="margin-top:4px"><span class="mono" style="font-size:40px;font-weight:600;line-height:1">{b["slot"]}</span> &nbsp;<b style="font-size:13px">대기 약 {br["wait"] if br else 0}분</b></div>', rot=-1.5, block=True)
    else:
        ui.postit(f'<b style="font-size:13px">{when} 예약이 아직 없어요</b><div style="font-size:13px;margin-top:4px">칸을 골라 두면 팀 {nb.team_count(S)}명이 같이 잡혀요</div>', rot=-1.5, block=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button(f"{when}만 바꾸기" if b else "시간 고르기", type="primary", use_container_width=True):
            go("reserve")
    with c2:
        if st.button("팀원 참석 확인", use_container_width=True):
            go("team")
    with c3:
        if st.button("하교 후 기록", use_container_width=True, disabled=fb_done):
            go("feedback")
    tabbar("home")


def v_reserve() -> None:
    s = S["settings"]
    t = nb.target_date(S)
    rows = nb.queue(S, t, booking=None)
    b = nb.current_booking(S, t)
    ts = nb.team_count(S)
    when = "오늘" if nb.is_today(t) else "내일"
    ui.head(f"마감 {s['deadline']} · {nb.fmt_date_ko(t)}", f"{when}만 시간 바꾸기", "칸마다 예상 대기시간과 남은 자리예요 · 칸을 눌러 고르기")
    for i in range(0, len(rows), 2):
        cols = st.columns(2)
        for c, r in zip(cols, rows[i:i + 2]):
            k = "y" if b and b["slot"] == r["time"] else r["kind"]
            word = nb.KIND_WORD[k]
            with c:
                st.markdown(f'<div class="nb-cell k-{k}" style="height:auto;padding:6px 10px;align-items:flex-start;border:2px solid #111;border-bottom:0"><span class="t" style="font-size:16px">{r["time"]} &nbsp;<span style="font-size:11px">{word}</span></span><span style="font-weight:500">대기 {r["wait"]}분 · {"남은 자리 " + str(r["left"]) if r["left"] > 0 else "마감"}</span></div>', unsafe_allow_html=True)
                if st.button("고르기" if ss.picked != r["time"] else "✓ 골랐어요", key=f"slot_{r['time']}", use_container_width=True, type="primary" if ss.picked == r["time"] else "secondary"):
                    ss.picked, ss.rec = r["time"], False
                    st.rerun()
    st.markdown("<hr style='border:0;border-top:2px solid #111'>", unsafe_allow_html=True)
    p = nb.slot_row(rows, ss.picked) if ss.picked else None
    if not p:
        st.markdown('<div class="nb-card" style="border-style:dashed;text-align:center;color:#6B6B6B;font-weight:700">바꿀 시간을 위에서 골라 주세요</div>', unsafe_allow_html=True)
    elif p["kind"] == "b" or p["left"] < ts:
        st.markdown(f"**{p['time']}은 꽉 찼어요 · 지금 가면 약 {p['wait']}분**")
        if not ss.rec and st.button("덜 붐비는 시간 추천 받기", type="primary", use_container_width=True):
            ss.rec = True
            st.rerun()
        if ss.rec:
            st.markdown(f'<div style="display:flex;align-items:center;gap:12px;margin-top:8px">{ui.bowl("shock", 60)}<h3 style="margin:0">헉, {p["time"]}은 꽉 찼어요</h3></div><p>지금 가면 약 <b>{p["wait"]}분</b> 줄을 서요. 우리 팀 {ts}명이 다 들어가는 시간을 붙여 뒀어요.</p>', unsafe_allow_html=True)
            recs = nb.recommend(S, t, p["time"])
            if not recs:
                st.warning("지금은 팀이 다 들어가는 칸이 없어요. 대기 명단에 올려 두세요.")
            for i, r in enumerate(recs):
                rot = [-2.5, 2, -1][i]
                ui.postit(f'<span class="mono" style="font-size:22px;font-weight:600">{r["time"]}</span> &nbsp; <b>{r["tag"]} · 대기 {r["wait"]}분</b> · {max(0, p["wait"] - r["wait"])}분 덜 기다림 · +{r["pt"]}P', rot=rot, block=True)
                if st.button(f"{r['time']}로 바꿀래요", key=f"rec_{r['time']}", type="primary", use_container_width=True):
                    nb.book(S, t, r["time"], "추천 수락")
                    S["recLog"].append({"date": nb.date_key(t), "from": p["time"], "to": r["time"], "accepted": True, "pa": r.get("pa")})
                    S["user"]["points"] = S["user"].get("points", 0) + r["pt"]
                    nb.save(S)
                    go("confirm")
            if st.button(f"그래도 {p['time']} 대기 명단에 올리기", use_container_width=True):
                S["waitlist"][nb.date_key(t)] = p["time"]
                S["recLog"].append({"date": nb.date_key(t), "from": p["time"], "to": None, "accepted": False, "pa": recs[0].get("pa") if recs else None})
                nb.save(S)
                ss.picked, ss.rec = None, False
                st.success(f"{p['time']} 대기 명단에 올렸어요. 자리가 나면 {s['deadline']} 전에 알려 줄게요.")
    else:
        st.markdown(f"**{p['time']} · 대기 약 {p['wait']}분 · 팀 {ts}명**")
        if st.button(f"{p['time']}로 예약하기", type="primary", use_container_width=True):
            nb.book(S, t, p["time"], f"{when}만 변경")
            go("confirm")
    if st.button(f"← {when}"):
        go("home")


def v_confirm() -> None:
    t = nb.target_date(S)
    b = nb.current_booking(S, t)
    rows = nb.queue(S, t)
    r = nb.slot_row(rows, b["slot"]) if b else None
    after = nb.mins(b["slot"]) - nb.mins(S["settings"]["lunchStart"]) if b else 0
    st.markdown(f'<div style="display:flex;justify-content:space-between;align-items:flex-end"><div><div class="nb-eyebrow">{nb.fmt_date(t)} · {nb.now_hhmm()}</div><h1 style="margin:4px 0 0">{"오늘" if nb.is_today(t) else "내일"} 예약 확정</h1><div class="nb-note">휴대폰 내기 전에 기억해 두세요</div></div>{ui.bowl("happy", 76)}</div>', unsafe_allow_html=True)
    ui.postit(f'<div style="text-align:center"><b style="font-size:14px">급식 시간</b><div class="mono" style="font-size:72px;font-weight:600;line-height:1;margin-top:8px">{b["slot"] if b else "--:--"}</div><b style="font-size:17px">점심시간 시작하고 {after}분 뒤</b></div><div style="position:absolute;right:14px;top:14px" class="nb-stamp">확정</div>', rot=-2, block=True)
    ui.rows_card("예약 내용", [("우리 팀", f"{nb.team_count(S)}명 같이 예약됨"), ("예상 대기", f"약 {r['wait'] if r else 0}분"), ("교실 화면", f"{b['slot'] if b else ''}에 \"지금 갈 팀\"으로 떠요")])
    if st.button("확인했어요", type="primary", use_container_width=True):
        go("home")


def v_feedback() -> None:
    today = datetime.now().date()
    b = S["bookings"].get(nb.date_key(today))
    ui.head(f"{nb.now_hhmm()} · {'예약 ' + b['slot'] if b else '예약 없이 다녀옴'}", "오늘 급식 어땠어?", "팀 대표가 팀 대신 답해요 · 30초면 끝")
    ate = st.radio("1. 오늘 급식 먹었어?", ["예", "아니오"], horizontal=True)
    timing = st.radio("2. 몇 시쯤 줄 섰어?", ["예약대로", "더 일찍", "더 늦게"], horizontal=True)
    bucket = st.radio("3. 줄에서 얼마나 기다렸어?", list(nb.BUCKETS.keys()), index=None, horizontal=True)
    names = [m["name"] for m in S["team"]["members"]]
    present = st.multiselect("4. 오늘 같이 먹은 팀원 (안 온 사람은 빼기)", names, default=names)
    if st.button("보내기 · +5P", type="primary", use_container_width=True, disabled=bucket is None):
        nb.send_feedback(S, today, {"ate": ate, "timing": timing, "bucket": bucket, "present": present})
        ss.just_sent = True
        ss.screen = "record"
        st.rerun()
    if st.button("← 오늘"):
        go("home")


def v_record() -> None:
    ui.head(f"{datetime.now().year} 2학기", "내 기록")
    wk = nb.week_records(S)
    done = [d for d in wk if d["wait"] is not None]
    saved = sum(max(0, max(d["expected"] or 0, 10) - d["wait"]) for d in done)
    avg = f"{sum(d['wait'] for d in done) / len(done):.1f}분" if done else "—"
    if ss.just_sent and S["feedback"]:
        last = S["feedback"][-1]
        ui.postit(f'<b style="font-size:16px">+5P · 고마워요!</b><div style="font-size:12px;margin-top:2px">오늘 약 {last["wait"]}분 기다렸어요. 피크 시간에 갔다면 약 {max(last["expected"], 10)}분.</div>', rot=2)
    ui.kpis([("이번 주 아낀 시간", f"{round(saved)}분", ""), ("주 평균 대기", avg, ""), ("포인트", f"{S['user'].get('points', 0)}P", "")])
    mx = max([11] + [d["wait"] for d in done])
    bars = "".join(
        f'<div class="nb-bar"><span>{"·" if d["wait"] is None else d["wait"]}</span><i class="k-{"f" if d["wait"] is None else "b" if d["wait"] >= 10 else "m" if d["wait"] >= 4 else "f"}" style="height:{4 if d["wait"] is None else max(6, round(d["wait"] / mx * 120))}px;{"border-style:dashed;background:transparent" if d["wait"] is None else ""}"></i></div>' for d in wk)
    labels = "".join(f'<span style="text-align:center;font-size:12px;font-weight:700">{d["day"]}</span>' for d in wk)
    st.markdown(f'<div class="nb-card"><b>이번 주 대기시간 (분)</b><div class="nb-bars" style="grid-template-columns:repeat(5,minmax(0,1fr))">{bars}</div><div style="display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin-top:4px">{labels}</div>{"" if done else "<div class=nb-note style=margin-top:8px>하교 후 기록을 보내면 여기에 쌓여요</div>"}</div>', unsafe_allow_html=True)
    tabbar("record")


def v_team() -> None:
    tm = S["team"]
    ui.head(f"초대코드 {tm['code']}", f"우리 팀 · {len(tm['members'])}명", "대표가 예약하면 참석 팀원 모두 같은 시간으로 잡혀요")
    for i, m in enumerate(tm["members"]):
        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown(f'<div style="padding:10px 0"><b style="font-size:15px">{ui.e(m["name"])}</b> <span class="nb-note">{"대표" if m.get("lead") else ""}</span><br><span class="mono nb-note">{ui.e(m["cls"])}</span></div>', unsafe_allow_html=True)
        with c2:
            here = m.get("present", True)
            if st.button("참석" if here else "불참", key=f"present_{i}", type="secondary" if here else "primary", use_container_width=True):
                m["present"] = not here
                nb.save(S)
                st.rerun()
    with st.expander("팀원 초대"):
        st.caption(f"초대코드 {tm['code']}를 알려 주면 친구가 직접 들어와요. 시연에서는 이름을 바로 추가해요.")
        nm = st.text_input("친구 이름", key="invite_name")
        if st.button("추가", disabled=not nm.strip()):
            tm["members"].append({"name": nm.strip(), "cls": f"{S['user']['grade']}-{S['user']['cls']}", "lead": False, "present": True})
            nb.save(S)
            st.rerun()
    if st.button("대표 바꾸기 (다음 사람에게)"):
        ms = tm["members"]
        if len(ms) > 1:
            li = next((i for i, m in enumerate(ms) if m.get("lead")), 0)
            for m in ms:
                m["lead"] = False
            ms[(li + 1) % len(ms)]["lead"] = True
            nb.save(S)
            st.rerun()
    tabbar("team")


def v_recurring() -> None:
    rc = S["recurring"]
    ui.head(f"{datetime.now():%Y.%m} · 팀 {nb.team_count(S)}명", "정기 예약", "한 번 정하면 매일 아침 자동으로 예약돼요")
    rc["period"] = st.radio("기간", ["1주", "1개월", "학기"], index=["1주", "1개월", "학기"].index(rc.get("period", "1개월")), horizontal=True)
    opts = ["—"] + nb.slots(S)
    changed = False
    hdr = st.columns([1, 2, 2, 2])
    for c, h in zip(hdr, ["요일", "1순위", "2순위", "3순위"]):
        c.markdown(f"**{h}**")
    for d in ["월", "화", "수", "목", "금"]:
        prefs = (rc["days"].get(d) or ["", "", ""]) + ["", "", ""]
        cols = st.columns([1, 2, 2, 2])
        cols[0].markdown(f"<div style='padding-top:8px;font-weight:900'>{d}</div>", unsafe_allow_html=True)
        new = []
        for j in range(3):
            cur = prefs[j] if prefs[j] in opts else "—"
            v = cols[j + 1].selectbox(f"{d}{j}", opts, index=opts.index(cur), key=f"rc_{d}_{j}", label_visibility="collapsed")
            new.append("" if v == "—" else v)
        if new != (rc["days"].get(d) or ["", "", ""])[:3]:
            rc["days"][d] = new
            changed = True
    if changed:
        for k in list(S["bookings"].keys()):
            if S["bookings"][k].get("auto"):
                del S["bookings"][k]
        nb.save(S)
    ui.postit(f'<b style="font-size:13px">이렇게 배정돼요</b><br><span style="font-size:12px;line-height:1.6">자리의 {round(S["settings"]["ratio"] * 100)}%까지만 정기 예약으로 채워요 · 1순위를 못 받은 달은 다음 달 먼저 · 시험과 행사 날은 자동으로 쉬어요</span>', rot=1, block=True)
    tabbar("recurring")


def v_settings() -> None:
    u = S["user"]
    ui.head("", "설정")
    st.markdown(f'<div class="nb-card" style="display:flex;align-items:center;gap:12px"><span style="width:44px;height:44px;display:inline-flex;align-items:center;justify-content:center;background:#FFE14D;border:2px solid #111;font-size:18px;font-weight:900">{ui.e((u.get("name") or "나")[:1])}</span><div><b style="font-size:15px">{ui.e(u.get("name") or "친구")} · {ui.e(u["grade"])}학년 {ui.e(u["cls"])}반</b><br><span class="mono nb-note">{ui.e(u["email"])}</span></div></div>', unsafe_allow_html=True)
    n1 = st.toggle("전날 밤 예약 알림 · 21:00 내일 메뉴와 혼잡 예상", value=u.get("notif1", True))
    n2 = st.toggle("마감 알림 · 07:00 휴대폰 내기 30분 전", value=u.get("notif2", True))
    if n1 != u.get("notif1") or n2 != u.get("notif2"):
        u["notif1"], u["notif2"] = n1, n2
        nb.save(S)
    if st.button("사용법 다시 보기", type="primary", use_container_width=True):
        ss.intro, ss.intro_from = 0, "settings"
        go("intro")
    c1, c2 = st.columns(2)
    if c1.button("정기 예약 관리", use_container_width=True):
        go("recurring")
    if c2.button("팀 관리", use_container_width=True):
        go("team")
    with st.expander("개인정보 처리 안내"):
        st.markdown("저장: 학교 이메일(가입 확인용), 학년·반, 팀, 예약 칸, 하교 후 응답  \n저장하지 않음: 위치, 사진, 연락처, 실명(선택)  \n보관: 학기 종료 시 개인 기록 삭제, 통계만 남김  \n도입: 학교운영위원회 심의 후 운영")
    if st.button("로그아웃"):
        S["user"] = None
        nb.save(S)
        ss.email = ""
        go("splash")
    st.caption("눈치밥 nunchi-bap · 마송고등학교 모의창업 · 관리자 웹은 왼쪽 위 메뉴(>)에서 열 수 있어요")
    tabbar("settings")


VIEWS = {"splash": v_splash, "email": v_email, "nope": v_nope, "code": v_code, "profile": v_profile, "intro": v_intro,
         "home": v_home, "reserve": v_reserve, "confirm": v_confirm, "feedback": v_feedback, "record": v_record,
         "team": v_team, "recurring": v_recurring, "settings": v_settings}

if not S["user"] and ss.screen not in ("splash", "email", "nope", "code", "profile"):
    ss.screen = "splash"
if S["user"]:
    nb.ensure_team(S)
VIEWS[ss.screen]()
