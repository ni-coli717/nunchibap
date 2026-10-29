"""눈치밥 AI 엔진 · 시뮬레이션 (파이썬 AI 엔진 화면)"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import nb_core as nb  # noqa: E402
import nb_demo as dm  # noqa: E402
import nb_ui as ui  # noqa: E402

st.set_page_config(page_title="눈치밥 AI 엔진", page_icon="🍚", layout="wide", initial_sidebar_state="collapsed")
ui.inject()
S = nb.load()
s = S["settings"]
DEMO = bool(s.get("demo", True))

st.sidebar.markdown(f'<div style="display:flex;align-items:center;gap:10px;padding:6px 0 14px">{ui.LOGO}<div><b style="font-size:16px">눈치밥 관리자</b><br><span style="font-size:11px;color:#BDBDB8">{ui.e(s["schoolName"])} · 영양교사</span></div></div>', unsafe_allow_html=True)
st.sidebar.markdown(f'<div style="font-size:12px;line-height:1.7;color:#BDBDB8">운영 모드 <b style="color:#FFE14D">{"휴대폰 수거" if s["mode"] == "수거" else "휴대폰 자유"}</b><br>배식 속도 {s["mu"]}명/분/라인 (자동 보정 중)<br>정원 {nb.capacity(S)}명 / {s["slotLen"]}분<br>{"<b style=\'color:#FFE14D\'>시연 모드</b> · 시안 데이터" if DEMO else "실시간 모드"}</div>', unsafe_allow_html=True)



def save_settings(msg: str = "저장했어요. 학생 앱의 혼잡 계산에 바로 반영돼요") -> None:
    s["savedAt"] = datetime.now().isoformat()
    nb.save(S)
    st.toast(msg)

import nb_ai  # noqa: E402
import pandas as pd  # noqa: E402

st.markdown("<style>.block-container{max-width:1280px!important}</style>", unsafe_allow_html=True)
n1, n2, _ = st.columns([1, 1, 4])
n1.page_link("pages/1_관리자.py", label="← 관리자 웹")
n2.page_link("app.py", label="학생 앱")
tab_ai, tab_sim = st.tabs(["06 AI 엔진", "07 시뮬레이션"])

with tab_ai:
    ui.head("06 · AI ENGINE", "AI 엔진", "AI 2개 + 계산 2개 · 학습 데이터는 날짜 × 5분 칸 · 지금은 시연용 가상 데이터예요 (11월 실측 후 교체)")
    am, acc = nb_ai.engine(int(s.get("aiWeeks", 8)))
    c1, c2 = st.columns([2, 1])
    with c1:
        weeks = st.select_slider("쌓인 데이터 기간 (시연: 바꿔 보면 단계가 바뀌어요)", options=list(range(1, 9)), value=int(s.get("aiWeeks", 8)), format_func=lambda w: f"{w}주")
    with c2:
        mode = st.radio("예측 엔진", ["자동", "계산", "AI"], index=["자동", "계산", "AI"].index(s.get("aiMode", "자동")), horizontal=True,
                        help="자동: 검증에서 AI가 기본 통계보다 5% 이상 정확할 때만 AI를 써요")
    if weeks != s.get("aiWeeks") or mode != s.get("aiMode"):
        s["aiWeeks"], s["aiMode"] = int(weeks), mode
        save_settings("엔진 설정을 바꿨어요 · 학생 앱 혼잡 예측에 바로 반영돼요")
        st.rerun()
    ui.stages(am.stage, nb_ai.STAGES)
    using = nb.engine_label(S)
    if am.stage < 2:
        why = f"데이터 {am.days}일 · AI 평가는 20일(약 4주)부터예요"
    elif am.use_ai:
        why = f"검증 오차 {am.mae_base:.2f}명 → {am.mae_ai:.2f}명 · {am.gain * 100:.0f}% 더 정확해서 교체했어요"
    else:
        why = f"AI가 기본 통계보다 {'덜' if (am.gain or 0) < 0 else '충분히 더'} 정확하지 않아서 계산을 유지해요 ({(am.gain or 0) * 100:+.0f}%)"
    ui.kpis([("지금 쓰는 엔진", using, why),
             ("학습 데이터", f"{am.days}일", f"{am.days * 10}칸 · 날짜 × 5분 칸"),
             ("기본 통계", f"{am.ratio:.2f}×예약{am.bias:+.1f}", "실제 인원 ≈ 이 식 · 피드백으로 매일 밤 보정"),
             ("검증 평균 오차", f"{am.mae_ai:.2f}명" if am.mae_ai is not None else "—", f"기본 통계 {am.mae_base:.2f}명" if am.mae_base else "마지막 10일로 검증")])

    st.markdown("### AI ① 칸별 유입 인원")
    c1, c2 = st.columns([3, 2])
    with c1:
        if am.test is not None:
            te = am.test.copy()
            te["칸"] = te["date"].str[5:] + " " + te["slot"].map(lambda i: nb.slots(S)[i] if i < len(nb.slots(S)) else str(i))
            ch = te.set_index("칸")[["actual", "pred_base", "pred_ai"]].rename(columns={"actual": "실제", "pred_base": "기본 통계", "pred_ai": "AI"})
            st.markdown("**검증 기간 (마지막 10일) · 칸별 실제 인원과 예측**")
            st.line_chart(ch, height=260, color=["#111111", "#9A9A96", "#E0B800"])
            ev = te[te["event"] == 1]
            if len(ev):
                from sklearn.metrics import mean_absolute_error as _mae
                st.caption(f"시험·단축 수업 날만 보면 오차 기본 통계 {_mae(ev['actual'], ev['pred_base']):.1f}명 · AI {_mae(ev['actual'], ev['pred_ai']):.1f}명 — 예약 인원만으로는 못 보는 날을 AI가 잡아요")
        else:
            st.markdown('<div class="nb-card" style="border-style:dashed">데이터가 20일 이상 쌓이면 마지막 10일로 AI와 기본 통계를 비교해요. 그 전에는 예약 인원 × 기본 비율로 신호등을 계산해요.</div>', unsafe_allow_html=True)
    with c2:
        if am.importance:
            ui.hbars("무엇이 예측에 중요했나 (순열 중요도)", [(k, round(v, 2)) for k, v in am.importance[:7]], unit="", note="이 입력을 섞으면 오차가 몇 명 커지는지", hi=1, label_w=120)
        else:
            ui.rows_card("입력 피처", [(nb_ai.FEATURE_KO[f], "") for f in nb_ai.FEATURES[:7]])

    t = nb.target_date(S)
    st.markdown(f"**{nb.fmt_date_ko(t)} 입력값** <span class='nb-note'>평소엔 나이스 급식·학사일정, 기상청 예보로 자동 · 시연에서는 직접 바꿔 볼 수 있어요</span>", unsafe_allow_html=True)
    a, b, c = st.columns(3)
    w = a.radio("날씨", nb_ai.WEATHER, index=nb_ai.WEATHER.index(s.get("weather", "맑음")), horizontal=True)
    ev_on = b.toggle("시험·단축 수업 날", value=bool(s.get("event")))
    pop = c.slider("메뉴 인기도", 1, 10, int(s["menu"]["pop"]))
    if w != s.get("weather") or ev_on != bool(s.get("event")) or pop != s["menu"]["pop"]:
        s["weather"], s["event"], s["menu"]["pop"] = w, ev_on, int(pop)
        save_settings("오늘 입력값을 바꿨어요")
        st.rerun()
    rows = nb.queue(S, t)
    base_pred, _ = nb_ai.predict_day([r["arrivals"] for r in rows], t.weekday(), int(s["menu"]["pop"]), s["weather"], bool(s["event"]), s["endTimes"], int(s["aiWeeks"]), "계산")
    df = pd.DataFrame({"칸": [r["time"] for r in rows], "예약": [r["arrivals"] for r in rows], "기본 통계": base_pred,
                       using: [r["pred"] for r in rows], "예상 대기(분)": [r["wait"] for r in rows],
                       "신호등": [nb.KIND_WORD[r["kind"]] for r in rows]})
    st.dataframe(df, hide_index=True, use_container_width=True)

    st.markdown("### AI ② 추천 수락 확률")
    c1, c2 = st.columns([2, 3])
    with c1:
        ui.kpis([("검증 정확도", f"{acc.acc * 100:.0f}%", "로지스틱 회귀 · 추천 기록 700건(가상)"), ("평균 수락률", f"{acc.base_rate * 100:.0f}%", "11/16~20 파일럿에서 실측")])
        ui.hbars("수락에 미치는 영향 (계수)", [(k, round(v, 2)) for k, v in acc.coefs], note="+면 더 잘 받아들이고, −(빗금)면 덜 받아들여요", hi=0, label_w=130)
    with c2:
        st.markdown("**수락 확률 계산기** <span class='nb-note'>확률이 높은 팀에게 먼저 추천해요</span>", unsafe_allow_html=True)
        a, b = st.columns(2)
        saved = a.slider("덜 기다리는 시간 (분)", 0, 12, 6)
        shift = b.select_slider("시간 이동 (분)", [5, 10, 15, 20, 25, 30], value=15)
        team = a.slider("팀 인원", 1, 5, 4)
        msg = b.radio("메시지 형태", nb_ai.MSG_TYPES, index=nb_ai.MSG_TYPES.index(s.get("msg", "숫자형")), horizontal=True)
        rec = st.toggle("정기 예약 팀", value=False)
        pa = acc.prob(saved, shift, team, msg, int(rec))
        ui.postit(f'<div style="font-size:12px;font-weight:700">이 팀이 추천을 받아들일 확률</div><div class="mono" style="font-size:44px;font-weight:600;line-height:1.1">{pa * 100:.0f}%</div><div style="font-size:12px">{saved}분 덜 기다림 · {shift}분 이동 · {team}명 · {msg}</div>', rot=-1.5, block=True)

    st.markdown("### 하교 후 피드백 → 칸별 실제 인원")
    st.caption("응답은 팀 대표만 하고, 모두가 답하지 않아요. 그래서 칸별 응답 수 ÷ 응답률 × 팀 평균 인원으로 실제 인원을 추정해요")
    a, b = st.columns(2)
    rr = a.slider("응답률", 0.2, 1.0, float(s.get("responseRate", 0.64)), 0.01, format="%.2f")
    tavg = b.slider("팀 평균 인원", 1.0, 5.0, 3.6, 0.1)
    if abs(rr - float(s.get("responseRate", 0.64))) > 1e-9:
        s["responseRate"] = rr
        save_settings("응답률을 바꿨어요")
    resp = [max(0, round(r["pred"] / tavg * rr)) for r in rows]
    est = nb_ai.estimate_actual(resp, rr, tavg)
    st.dataframe(pd.DataFrame([resp, est, [r["pred"] for r in rows]], index=["피드백 응답(팀)", "추정 실제 인원", "예측했던 인원"],
                              columns=[r["time"] for r in rows]), use_container_width=True)
    st.caption("추정값이 예측보다 계속 크면 기본 비율이 올라가고, 대기 구간 답으로 배식 속도 μ가 함께 보정돼요 (μ오늘 = 0.8·μ어제 + 0.2·μ추정). 정확도는 일부 시간대 직접 관찰로 검증해요.")

# ---------------- 07 시뮬레이션 ----------------
with tab_sim:
    ui.head("07 · SIMULATION", "학생 한 팀의 선택이, 전체의 줄을 바꾼다", "팀 단위 가상 시뮬레이션 · 예약이 들어올 때마다 추천을 다시 계산해요 · 모델 실측 결과가 아니에요")
    _, acc = nb_ai.engine(int(s.get("aiWeeks", 8)))
    cap = nb.capacity(S)
    rate = s["mu"] * s["lines"]
    n_slots = len(nb.slots(S))
    c1, c2, c3 = st.columns(3)
    total = c1.slider("급식 인원 (한 학년 기준)", 100, 600, 300, 10)
    rr = c2.slider("예약률", 0, 100, 50, 5, format="%d%%") / 100
    follow = c3.slider("예약 안 한 학생이 교실 배정표를 따르는 비율", 0, 50, 15, 5, format="%d%%") / 100
    a, b, c = st.columns(3)
    dyn_label = a.radio("추천 방식", ["매번 다시 계산 (눈치밥)", "아침 한 번 계산 (비교용)"], horizontal=False)
    acc_label = b.radio("추천 수락", ["AI ② 예측 확률", "모두 수락 (상한선)"], horizontal=False)
    msg = c.radio("추천 메시지", nb_ai.MSG_TYPES, index=nb_ai.MSG_TYPES.index(s.get("msg", "숫자형")), horizontal=True)
    kw = dict(total=total, cap=cap, rate=rate, slot_len=int(s["slotLen"]), n_slots=n_slots, accept=acc, msg=msg,
              dynamic=dyn_label.startswith("매번"), accept_all=acc_label.startswith("모두"), board_follow=follow)
    runs = [nb_ai.simulate(res_rate=rr, seed=i, **kw) for i in range(10)]
    ex = runs[0]
    labels = nb.slots(S)
    c1, c2, c3 = st.columns([5, 5, 4])
    with c1:
        ui.hbars("기존 분포 (앱 없음)", list(zip(labels, ex["before"])), cap=cap, note=f"정원 {cap}명 넘는 칸은 검정")
    with c2:
        ui.hbars("시간 분산 (눈치밥)", list(zip(labels, ex["after"])), cap=cap, hi=len(labels), note=f"추천 {ex['sent']}번 · 수락 {ex['accepted']}팀 · 배정표 보고 이동 {ex['board_moved']}명")
    with c3:
        import numpy as _np
        pb = _np.mean([max(r["before"]) for r in runs])
        pa_ = _np.mean([max(r["after"]) for r in runs])
        wb = _np.mean([r["q_before"]["avg"] for r in runs])
        wa = _np.mean([r["q_after"]["avg"] for r in runs])
        tb = _np.mean([r["q_before"]["p90"] for r in runs])
        ta = _np.mean([r["q_after"]["p90"] for r in runs])
        st.markdown(f'<div class="nb-board" style="margin-top:8px"><div class="bh" style="font-size:13px">최대 유입 (10회 평균)</div><div class="nb-brow" style="font-size:30px"><span class="mono">{pb:.0f}명 → {pa_:.0f}명</span></div></div>', unsafe_allow_html=True)
        ui.kpis([("평균 대기", f"{wb:.1f} → {wa:.1f}분", f"{(1 - wa / wb) * 100:.0f}% 감소" if wb else ""),
                 ("상위 10% 대기", f"{tb:.1f} → {ta:.1f}분", "가장 오래 기다린 학생")])
    if not kw["dynamic"] and kw["accept_all"]:
        st.warning("모두에게 같은 칸을 추천하면 그 칸에 새 줄이 생겨요. 그래서 예약이 들어올 때마다 추천을 다시 계산해요.")

    st.markdown("### 예약률별 효과")
    st.caption("발표 질문 대비: '예약을 안 하는 학생이 많으면 소용없지 않나요?' — 예약률을 바꿔 가며 10번씩 돌린 평균이에요")

    @st.cache_data(show_spinner="시뮬레이션 중…")
    def _sweep(key: tuple) -> pd.DataFrame:
        k = dict(key)
        return nb_ai.sweep([0.1, 0.2, 0.3, 0.5, 0.7, 1.0], runs=10, accept=acc, **k)

    key = tuple(sorted({k: v for k, v in kw.items() if k != "accept"}.items()))
    sw = _sweep(key)
    c1, c2 = st.columns([3, 2])
    with c1:
        ui.hbars("피크 유입 (5분 최대 인원)", [(r["예약률"], round(r["피크 유입"])) for _, r in sw.iterrows()], unit="명", cap=cap, hi=len(sw), note=f"빨간 점선 = 정원 {cap}명")
        ui.hbars("상위 10% 학생의 대기", [(r["예약률"], round(r["상위 10% 대기"], 1)) for _, r in sw.iterrows()], unit="분", hi=len(sw))
    with c2:
        show = sw.copy()
        show["수락률"] = show["수락률"].map(lambda v: "—" if pd.isna(v) else f"{v * 100:.0f}%")
        for col in ["피크 유입", "평균 대기", "상위 10% 대기", "최대 대기"]:
            show[col] = show[col].round(1)
        st.dataframe(show[["예약률", "평균 대기", "최대 대기", "수락률"]], hide_index=True, use_container_width=True)
        r30 = sw[sw["예약률"] == "30%"].iloc[0]
        r0 = sw.iloc[0]
        st.markdown(f'<div class="nb-card"><b>예약률 30%만 되어도</b><br>피크 {r0["피크 유입"]:.0f}명 → {r30["피크 유입"]:.0f}명 · 평균 대기 {r0["평균 대기"]:.1f}분 → {r30["평균 대기"]:.1f}분</div>', unsafe_allow_html=True)
    st.caption("가정: 팀 1~5명, 앱 없을 때 12:20 쏠림 모양, 칸 정원 = 배식 속도 × 라인 × 5분 × 안전계수. 칸 안에서는 도착 순서대로 줄을 선다고 계산해요. 모든 수치는 11월 실측으로 바꿀 가설이에요.")
