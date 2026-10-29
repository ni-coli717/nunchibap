"""눈치밥 관리자 웹 — 학교 설정 · 오늘 대시보드 · 운영 규칙 · 리포트"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import nb_core as nb  # noqa: E402
import nb_ui as ui  # noqa: E402

st.set_page_config(page_title="눈치밥 관리자", page_icon="🍚", layout="wide")
ui.inject()
S = nb.load()
s = S["settings"]

st.sidebar.markdown(f'<div style="display:flex;align-items:center;gap:10px;padding:6px 0 14px">{ui.LOGO}<div><b style="font-size:16px">눈치밥 관리자</b><br><span style="font-size:11px;color:#BDBDB8">{ui.e(s["schoolName"])} · 영양교사</span></div></div>', unsafe_allow_html=True)
st.sidebar.markdown(f'<div style="font-size:12px;line-height:1.7;color:#BDBDB8">운영 모드 <b style="color:#FFE14D">{"휴대폰 수거" if s["mode"] == "수거" else "휴대폰 자유"}</b><br>배식 속도 {s["mu"]}명/분/라인 (자동 보정 중)<br>정원 {nb.capacity(S)}명 / {s["slotLen"]}분</div>', unsafe_allow_html=True)

tab_setup, tab_dash, tab_rules, tab_report = st.tabs(["01 학교 설정", "02 오늘 대시보드", "04 운영 규칙", "05 리포트"])


def save_settings(msg: str = "저장했어요. 학생 앱의 혼잡 계산에 바로 반영돼요") -> None:
    s["savedAt"] = datetime.now().isoformat()
    nb.save(S)
    st.toast(msg)


with tab_setup:
    ui.head("01 · SETUP", "학교 설정", "학교를 검색하면 공공데이터로 채워져요. 직접 입력은 이메일 도메인과 급식 정보뿐이에요")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**학생 가입 이메일 도메인** <span class='nb-note'>이 주소로 끝나는 메일만 가입돼요</span>", unsafe_allow_html=True)
        for i, d in enumerate(list(s["domains"])):
            a, b, c = st.columns([3, 2, 1])
            a.markdown(f"<div style='padding-top:8px' class='mono'><b>@{ui.e(d['name'])}</b> &nbsp;<span class='nb-chip' style='font-size:11px;padding:2px 6px;{'background:#111;color:#FFE14D' if d['ok'] else 'border-style:dashed'}'>{'인증됨' if d['ok'] else '확인 중'}</span></div>", unsafe_allow_html=True)
            if not d["ok"] and b.button("학교 목록과 대조", key=f"verify_{i}"):
                s["domains"][i]["ok"] = True
                save_settings("학교 목록과 대조했어요 · 인증됨")
                st.rerun()
            if c.button("삭제", key=f"del_{i}"):
                s["domains"].pop(i)
                save_settings()
                st.rerun()
        nd = st.text_input("도메인 추가 (예: 교직원 메일)", placeholder="masong.go.kr")
        if st.button("추가"):
            n = nd.strip().lower().lstrip("@")
            if not n or "." not in n:
                st.error("도메인 형식을 확인해 주세요 (예: masong.go.kr)")
            elif any(d["name"] == n for d in s["domains"]):
                st.warning("이미 있는 도메인이에요")
            else:
                s["domains"].append({"name": n, "ok": False})
                save_settings()
                st.rerun()
        te = st.text_input("학생 이메일로 가입 테스트", value="s25012@masong.hs.kr")
        td = te.strip().lower().split("@")[-1] if "@" in te else ""
        hit = next((d for d in s["domains"] if d["name"] == td), None)
        if not td:
            st.caption("이메일을 넣으면 가입 가능 여부를 보여줘요")
        elif hit and hit["ok"]:
            st.success(f"✓ 가입 가능 · {s['schoolName']} 학생으로 등록돼요")
        elif hit:
            st.warning("도메인 확인 중이라 아직 가입할 수 없어요")
        else:
            st.error('목록에 없는 도메인이에요 · 학생에게 "아직 눈치밥이 없어요" 화면이 보여요')
        if S["requests"]:
            ui.rows_card("도입 요청 (학생 앱에서)", [(r["domain"], r["at"][:16].replace("T", " ")) for r in S["requests"][-5:]])
    with c2:
        ui.rows_card("공공데이터에서 자동으로 채운 값", [
            ("학교", f"{s['schoolName']} · {s['region']}  (나이스 학교정보)"),
            ("전교생", f"{s['students']}명 · 학년별 {' / '.join(map(str, s['perGrade']))}  (학교알리미)"),
            ("급식 메뉴", f"매일 자동 연동 · 오늘 {s['menu']['name']} (인기 {s['menu']['pop']}/10)"),
            ("학사일정", "체육대회 11/7 · 기말고사 12/9~12  (나이스 학사일정)"),
            ("4교시 종료", f"1·2학년 {s['endTimes']['1']} · 3학년 {s['endTimes']['3']}  (나이스 시간표)"),
        ])
        st.markdown("**급식 정보 (직접 입력)**")
        a, b, c = st.columns(3)
        lines = a.number_input("배식 라인", 1, 6, int(s["lines"]))
        ls = b.text_input("점심 시작", s["lunchStart"])
        le = c.text_input("점심 끝", s["lunchEnd"])
        mode = st.radio("휴대폰 정책", ["수거", "자유"], index=0 if s["mode"] == "수거" else 1, horizontal=True,
                        format_func=lambda m: "휴대폰 수거 학교 · 등교 전 예약, 하교 후 피드백" if m == "수거" else "휴대폰 자유 학교 · 점심 직전까지 예약")
        if st.button("저장", type="primary"):
            s["lines"] = int(lines)
            if len(ls) == 5 and len(le) == 5:
                s["lunchStart"], s["lunchEnd"] = ls, le
            s["mode"] = mode
            save_settings()
            st.rerun()
        ui.postit(f'<b style="font-size:14px">배식 속도는 입력하지 않아요</b><br><span style="font-size:13px;line-height:1.6">기본값 1분에 6.2명으로 시작해서, 학생 하교 후 피드백으로 우리 학교 속도를 스스로 찾아요. 지금 <b class="mono">{s["mu"]}명/분/라인</b>{" · 보정 " + str(len(s.get("muHistory") or [])) + "회" if s.get("muHistory") else ""}</span>', rot=-1.5, block=True)
    st.divider()
    if st.button("시연 데이터 초기화"):
        nb.reset()
        st.toast("시연 데이터를 초기화했어요")
        st.rerun()
    st.caption("학생 앱 가입, 예약, 피드백, 설정이 모두 기본값으로 돌아가요")

with tab_dash:
    t = nb.target_date(S)
    rows = nb.queue(S, t)
    cap = nb.capacity(S)
    sum_res = sum(r["arrivals"] for r in rows)
    peak = max(rows, key=lambda r: r["arrivals"])
    pi = rows.index(peak)
    peak_end = rows[min(len(rows) - 1, pi + 1)]
    max_wait = max(r["wait"] for r in rows)
    ui.head("02 · TODAY", f"{'오늘' if nb.is_today(t) else '내일'} 대시보드", f"{nb.fmt_date_ko(t)} · {s['menu']['name']} (인기 {s['menu']['pop']}/10) · {s['deadline']} 예약 마감, 08:00 예측 확정")
    ui.kpis([("예약 완료", f"{sum_res}명", f"{round(sum_res / 3.6)}팀 · 전교생 {round(sum_res / s['students'] * 100)}%"),
             ("예상 피크", f"{peak['time']}~{peak_end['time'][3:]}", f"정원 대비 {round(peak['pred'] / cap * 100)}%"),
             ("예상 최대 대기", f"{max_wait}분", f"정원 {cap}명/칸"),
             ("배식 속도", f"{s['mu']}", "명/분/라인 · " + (f"어제 {s['muHistory'][-1]['from']}" if s.get("muHistory") else "기본값"))])
    mx = max([70, cap + 10] + [r["pred"] + 5 for r in rows])
    bars = "".join(
        f'<div class="nb-bar" style="flex-direction:row;align-items:flex-end;gap:3px"><i style="width:40%;height:{round(r["arrivals"] / mx * 100)}%;background:#111;border:0" title="예약 {r["arrivals"]}"></i><i class="k-m" style="width:40%;height:{round(r["pred"] / mx * 100)}%" title="예측 {r["pred"]}"></i></div>' for r in rows)
    labels = "".join(f'<span class="mono" style="text-align:center;font-size:11px;font-weight:600">{r["time"][3:]}</span>' for r in rows)
    n = len(rows)
    st.markdown(f'<div class="nb-card"><b>슬롯별 예약 인원과 AI 예측</b> <span class="nb-note">■ 예약 &nbsp; ▨ AI 예측(예약 안 한 학생 포함) &nbsp; <span style="color:#B42318">- - 정원 {cap}명</span></span><div style="position:relative"><div style="position:absolute;left:0;right:0;bottom:{min(100, round(cap / mx * 100))}%;border-top:2px dashed #B42318;z-index:1"></div><div class="nb-bars" style="grid-template-columns:repeat({n},minmax(0,1fr));height:220px">{bars}</div></div><div style="display:grid;grid-template-columns:repeat({n},minmax(0,1fr));gap:10px;margin-top:6px">{labels}</div></div>', unsafe_allow_html=True)
    b = nb.current_booking(S, t) if S["user"] else None
    st.caption(f"학생 앱의 우리 팀 예약: {b['slot']} ({b['kind']}, {b['teamSize']}명)이 포함돼 있어요" if b else "학생 앱에서 예약하면 여기에 바로 더해져요")
    c1, c2 = st.columns(2)
    with c1:
        ui.postit(f'<div style="display:flex;gap:12px;align-items:flex-start">{ui.bowl("shock", 56)}<div><b style="font-size:15px">피크 예고 {peak["time"]}~{peak_end["time"]}</b><div style="font-size:13px;line-height:1.55;margin-top:4px">약 {peak["pred"] + peak_end["pred"]}명이 몰릴 예정이에요. {s["lunchStart"]}부터 {str(s["lines"]) + "라인 모두" if s["lines"] > 1 else "라인"} 배식 준비를 권해요.</div></div></div>', rot=1.5, block=True)
    with c2:
        sent = len(S["recLog"])
        acc = sum(1 for r in S["recLog"] if r["accepted"])
        ui.rows_card("추천 결과 (학생 앱 기준)", [("추천 보낸 팀", f"{sent}팀"), ("수락한 팀", f"{acc}팀" + (f" ({round(acc / sent * 100)}%)" if sent else "")), ("대기 명단", f"{len(S['waitlist'])}건"), ("피드백 응답", f"{len(S['feedback'])}건")])

with tab_rules:
    ui.head("04 · RULES", "운영 규칙", "바꾸면 다음 예약부터 바로 적용돼요")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**슬롯과 정원**")
        slot_len = st.radio("슬롯 길이", [5, 10], index=[5, 10].index(int(s["slotLen"])), horizontal=True, format_func=lambda v: f"{v}분")
        factor = st.radio("안전계수 (여유를 얼마나 둘지)", [0.8, 0.85, 0.9], index=[0.8, 0.85, 0.9].index(float(s["factor"])), horizontal=True, format_func=lambda v: f"{v:.2f}")
        cap_preview = int(s["mu"] * s["lines"] * slot_len * factor)
        st.markdown(f'<div class="nb-card"><span class="nb-note">계산된 슬롯 정원</span><div class="mono" style="font-size:18px;font-weight:600">{s["mu"]} × {s["lines"]} × {slot_len} × {factor:.2f} = {cap_preview}명</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown("**예약**")
        deadline = st.radio("당일 예약 마감 (휴대폰 수거 전)", ["07:00", "07:30", "08:00"], index=["07:00", "07:30", "08:00"].index(s["deadline"]), horizontal=True)
        ratio = st.radio("정기 예약에 쓰는 자리", [0.6, 0.7, 0.8], index=[0.6, 0.7, 0.8].index(float(s["ratio"])), horizontal=True, format_func=lambda v: f"{round(v * 100)}%")
        penalty = st.toggle("예약 안 지킨 팀 순위 낮추기 · 다음 달 정기 예약 우선순위만 낮아져요", value=s["penalty"])
        waitlist = st.toggle(f"꽉 찬 시간 대기 명단 · 자리가 나면 {s['deadline']} 전에 알려줘요", value=s["waitlist"])
        exam = st.toggle("시험·행사 날 자동 쉬기 · 학사일정과 연동돼요", value=s["examPause"])
    with c3:
        st.markdown("**추천 메시지와 포인트**")
        msg = st.radio("추천 메시지 형태 (파일럿 결과로 정해요)", ["숫자형", "신호등형", "보상형"], index=["숫자형", "신호등형", "보상형"].index(s["msg"]), horizontal=True)
        preview = {"숫자형": "12:35에 가면 대기 약 2분 (9분 덜 기다려요)", "신호등형": "12:20 꽉 참 → 12:35 여유", "보상형": "12:35로 옮기면 포인트 +10"}[msg]
        ui.postit(f'<div style="font-size:11px;font-weight:700">학생에게 보이는 추천 미리보기</div><div style="font-size:15px;font-weight:900;margin-top:6px">{preview}</div>', rot=-2, block=True)
    if st.button("규칙 저장", type="primary"):
        s.update({"slotLen": int(slot_len), "factor": float(factor), "deadline": deadline, "ratio": float(ratio), "penalty": penalty, "waitlist": waitlist, "examPause": exam, "msg": msg})
        for k in list(S["bookings"].keys()):
            if S["bookings"][k].get("auto"):
                del S["bookings"][k]
        save_settings()
        st.rerun()

with tab_report:
    fb = S["feedback"]
    avg = sum(f["wait"] for f in fb) / len(fb) if fb else None
    rl = S["recLog"]
    ui.head("05 · REPORT", "리포트", "도입 전후 비교 · 학교와 교육청 제출용 (예시로 표시된 숫자는 시뮬레이션이에요)")
    ui.kpis([("평균 대기", f"{avg:.1f}분" if avg is not None else "4.1분", f"피드백 {len(fb)}건" if avg is not None else "시뮬레이션 예시 · 도입 전 9.6분"),
             ("피크 대기", "7분", "시뮬레이션 예시 · 도입 전 16분"),
             ("추천 수락", f"{round(sum(1 for r in rl if r['accepted']) / len(rl) * 100)}%" if rl else "71%", f"{len(rl)}건" if rl else "시뮬레이션 예시"),
             ("1인당 1년 절약", "약 17시간", "50분 수업 약 21교시 · 시뮬레이션")])
    wk = [("9/1주", 10.2, 9.8), ("9/2주", 9.4, 7.1), ("9/3주", 9.9, 5.6), ("9/4주", 9.6, 4.8), ("10/1주", 10.1, 4.3), ("10/2주", 9.3, 4.0), ("10/3주", 9.7, 4.1)]
    bars = "".join(f'<div class="nb-bar" style="flex-direction:row;align-items:flex-end;gap:4px"><i class="k-m" style="width:36%;height:{round(b / 12 * 100)}%"></i><i style="width:36%;height:{round(a / 12 * 100)}%;background:#111;border:0"></i></div>' for _, b, a in wk)
    labels = "".join(f'<span style="text-align:center;font-size:11px;font-weight:700">{w[0]}</span>' for w in wk)
    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown(f'<div class="nb-card"><b>주간 평균 대기시간 (분) · 시뮬레이션 예시</b> <span class="nb-note">▨ 도입 전 &nbsp; ■ 도입 후</span><div class="nb-bars" style="grid-template-columns:repeat(7,minmax(0,1fr));height:200px">{bars}</div><div style="display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:10px;margin-top:6px">{labels}</div></div>', unsafe_allow_html=True)
    with c2:
        mh = s.get("muHistory") or []
        ui.rows_card("운영 지표", [("예약 이행률", "89% (예시)"), ("피드백 응답률", "64% (예시)"), ("정기 예약 팀", "62% (예시)"),
                                ("급식 안 먹음 응답", f"{round(sum(1 for f in fb if f['ate'] == '아니오') / len(fb) * 100)}%" if fb else "3.1% (예시)"),
                                ("배식 속도 자동 보정", f"{len(mh)}회 · 지금 {s['mu']}명/분" if mh else "아직 피드백 없음")])
        if mh:
            ui.rows_card("배식 속도 보정 기록 (μ오늘 = 0.8·μ어제 + 0.2·μ추정)", [(m["date"], f"{m['from']} → {m['to']}") for m in mh[-7:]])
