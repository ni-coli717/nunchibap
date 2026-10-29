/* 눈치밥 nunchi-bap — 공용 데이터 모델 · 대기행렬 계산 · 저장
   학생 앱(index.html)과 관리자 웹(admin.html)이 같은 브라우저 저장소를 공유한다. */
(function (global) {
  'use strict';
  var KEY = 'nunchibap.v1';

  var DEFAULTS = function () {
    return {
      settings: {
        schoolName: '마송고등학교',
        region: '경기',
        domains: [{ name: 'masong.hs.kr', ok: true }],
        lines: 2, slotLen: 5, factor: 0.85, mu: 6.2, muHistory: [],
        lunchStart: '12:10', lunchEnd: '13:00',
        deadline: '07:30', ratio: 0.7, mode: '수거',
        penalty: true, waitlist: true, examPause: true, msg: '숫자형',
        students: 612, perGrade: [208, 204, 200],
        endTimes: { '1': '12:10', '2': '12:10', '3': '12:05' },
        menu: { name: '치킨마요덮밥', pop: 9 },
        savedAt: null
      },
      user: null, /* {email, grade, cls, name, points, notif1, notif2, introDone, createdAt} */
      team: { code: 'MS-4K2P', members: [] }, /* members: [{name, cls, lead, present}] */
      bookings: {}, /* dateKey -> {slot, kind, teamSize} */
      recurring: { period: '1개월', days: { '월': ['12:15', '12:35', '12:45'], '화': ['12:15', '12:35', '12:45'], '수': ['12:40', '12:45', '12:50'], '목': ['12:15', '12:35', '12:45'], '금': ['12:15', '12:35', '12:45'] } },
      waitlist: {}, /* dateKey -> slot */
      feedback: [], /* {date, slot, ate, timing, bucket, present:[names], wait, expected} */
      recLog: [], /* {date, from, to, accepted} */
      requests: [] /* 도입 요청 {domain, at} */
    };
  };

  var state = null;
  var persistHook = null; /* Streamlit 서버 저장으로 보낼 때 */
  var aiData = null;      /* 파이썬 AI 엔진이 보낸 칸별 예측 {key, pred, label} */
  function fillDefaults(s) {
    var d = DEFAULTS();
    Object.keys(d).forEach(function (k) { if (s[k] === undefined || s[k] === null && k !== 'user') s[k] = d[k]; });
    if (!s.settings || typeof s.settings !== 'object') s.settings = d.settings;
    Object.keys(d.settings).forEach(function (k) { if (s.settings[k] === undefined) s.settings[k] = d.settings[k]; });
    if (!s.team || !Array.isArray(s.team.members)) s.team = d.team;
    return s;
  }
  function hydrate(s) { state = fillDefaults(s || DEFAULTS()); return state; }
  function setPersist(fn) { persistHook = fn; }
  function setAI(a) { aiData = a && a.pred ? a : null; }
  function engineLabel() { return aiData && aiData.label ? aiData.label : '계산 예측'; }
  function load() {
    if (state) return state;
    var d = DEFAULTS();
    try {
      var raw = global.localStorage.getItem(KEY);
      if (raw) {
        var s = JSON.parse(raw);
        state = s;
        /* 새 필드 보강 */
        Object.keys(d).forEach(function (k) { if (state[k] === undefined) state[k] = d[k]; });
        Object.keys(d.settings).forEach(function (k) { if (state.settings[k] === undefined) state.settings[k] = d.settings[k]; });
        return state;
      }
    } catch (e) { /* 저장소 없음 */ }
    state = d;
    return state;
  }
  function save() {
    if (persistHook) { try { persistHook(state); } catch (e) { /* 무시 */ } }
    else { try { global.localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) { /* 무시 */ } }
    try { global.dispatchEvent(new CustomEvent('nb:change')); } catch (e) { /* 무시 */ }
  }
  function reload() { state = null; return load(); }
  function reset() {
    state = DEFAULTS();
    try { global.localStorage.removeItem(KEY); } catch (e) { /* 무시 */ }
    save();
    return state;
  }

  /* ---------- 시간 ---------- */
  var WD = ['일', '월', '화', '수', '목', '금', '토'];
  var WD_EN = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];
  function mins(t) { return parseInt(t.slice(0, 2), 10) * 60 + parseInt(t.slice(3), 10); }
  function hhmm(m) { var h = Math.floor(m / 60), n = m % 60; return (h < 10 ? '0' : '') + h + ':' + (n < 10 ? '0' : '') + n; }
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function dateKey(d) { return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); }
  function fmtDate(d) { return (d.getMonth() + 1) + '.' + pad(d.getDate()) + ' ' + WD_EN[d.getDay()]; }
  function fmtDateKo(d) { return (d.getMonth() + 1) + '월 ' + d.getDate() + '일 ' + WD[d.getDay()]; }
  function nowHHMM(now) { now = now || new Date(); return pad(now.getHours()) + ':' + pad(now.getMinutes()); }

  /* 예약 대상 급식일: 마감 전이면 오늘, 지났으면 다음 등교일 (주말 건너뜀) */
  function targetDate(now) {
    now = now || new Date();
    var s = load().settings;
    var d = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    var past = mins(nowHHMM(now)) >= mins(s.deadline);
    if (past) d.setDate(d.getDate() + 1);
    while (d.getDay() === 0 || d.getDay() === 6) d.setDate(d.getDate() + 1);
    return d;
  }
  function isToday(d, now) { now = now || new Date(); return dateKey(d) === dateKey(now); }
  function deadlineLeft(now) {
    now = now || new Date();
    var s = load().settings;
    var left = mins(s.deadline) - mins(nowHHMM(now));
    return left; /* 분, 음수면 마감 지남 */
  }

  /* ---------- 슬롯과 수요 ---------- */
  function slots() {
    var s = load().settings, out = [];
    for (var m = mins(s.lunchStart); m < mins(s.lunchEnd) - 0; m += s.slotLen) { out.push(hhmm(m)); if (out.length >= 12) break; }
    return out;
  }
  function capacity() { var s = load().settings; return Math.floor(s.mu * s.lines * s.slotLen * s.factor); }

  /* 다른 학생들의 예약 수요 (시연용 기준값: 요일별로 조금씩 다르다) */
  function baseDemand(d) {
    var sl = slots(), n = sl.length, out = [];
    var shape = [0.32, 0.72, 1.0, 0.9, 0.76, 0.5, 0.36, 0.25, 0.17, 0.1, 0.06, 0.04];
    var wd = d ? d.getDay() : 2;
    var scale = [0, 52, 56, 50, 54, 58, 0][wd] || 56; /* 피크 인원 */
    var menuBoost = 1 + ((load().settings.menu.pop || 7) - 7) * 0.02;
    for (var i = 0; i < n; i++) out.push(Math.round(shape[i] * scale * menuBoost));
    return out;
  }

  /* 우리 팀 예약까지 더한 슬롯별 유입과 대기행렬 계산
     wait = (앞선 누적 대기 인원 + 이 칸 도착 인원) ÷ (분당 처리 인원) */
  function queue(d, opts) {
    opts = opts || {};
    var st = load(), s = st.settings, sl = slots(), cap = capacity();
    var demand = baseDemand(d);
    var key = dateKey(d);
    var mine = opts.booking !== undefined ? opts.booking : st.bookings[key];
    var teamSize = teamCount();
    var rate = s.mu * s.lines; /* 명/분 */
    var carry = 0, rows = [];
    var ai = aiData && aiData.key === key && aiData.pred && aiData.pred.length === sl.length ? aiData.pred : null;
    for (var i = 0; i < sl.length; i++) {
      var add = mine && mine.slot === sl[i] ? teamSize : 0;
      var arrivals = demand[i] + add;
      /* 예약 안 한 학생 포함 예측: 서버 AI 엔진(AI ①) 값이 있으면 그것을, 없으면 기본 통계식 */
      var pred = ai ? Math.round(ai[i] + add * 1.08) : Math.round(arrivals * 1.08 + (i < 5 ? 2 : 1));
      var inQueue = carry + pred;
      var wait = Math.max(0, Math.round(inQueue / rate));
      var served = Math.min(inQueue, rate * s.slotLen);
      carry = Math.max(0, inQueue - served);
      var left = cap - arrivals;
      var kind = left <= 0 || wait >= Math.max(6, s.slotLen + 1) ? 'b' : left <= cap * 0.3 || wait >= 4 ? 'm' : 'f';
      rows.push({ time: sl[i], arrivals: arrivals, pred: pred, wait: wait, left: Math.max(0, left), cap: cap, kind: kind, carry: carry });
    }
    return rows;
  }
  function slotRow(rows, t) { for (var i = 0; i < rows.length; i++) if (rows[i].time === t) return rows[i]; return null; }

  /* 꽉 찬 칸을 골랐을 때 추천: 팀이 다 들어가고 대기가 짧은 가까운 칸 3개 */
  function recommend(d, picked) {
    var rows = queue(d, { booking: null });
    var teamSize = teamCount();
    var pm = mins(picked);
    var cands = rows.filter(function (r) { return r.time !== picked && r.left >= teamSize && r.kind !== 'b'; });
    cands.sort(function (a, b) {
      var sa = a.wait * 2 + Math.abs(mins(a.time) - pm) / 5, sb = b.wait * 2 + Math.abs(mins(b.time) - pm) / 5;
      return sa - sb;
    });
    return cands.slice(0, 3).map(function (r, i) {
      var diff = mins(r.time) - pm;
      return { time: r.time, wait: r.wait, left: r.left, tag: i === 0 ? '추천' : r.kind === 'f' ? '여유' : '보통', pt: i === 0 ? 10 : 5, diff: diff };
    });
  }

  /* ---------- 팀 ---------- */
  function teamCount() { var t = load().team; var n = 0; (t.members || []).forEach(function (m) { if (m.present !== false) n++; }); return Math.max(1, n); }
  function ensureTeam() {
    var st = load();
    if (st.team.members.length === 0 && st.user) {
      var me = st.user.name ? st.user.name : '나';
      st.team.members = [
        { name: me, cls: st.user.grade + '-' + st.user.cls, lead: true, present: true },
        { name: '김민수', cls: '2-3', lead: false, present: true },
        { name: '이지호', cls: '2-5', lead: false, present: true },
        { name: '최서연', cls: '2-3', lead: false, present: true }
      ];
    }
  }

  /* ---------- 예약 ---------- */
  function currentBooking(d) {
    var st = load(), key = dateKey(d);
    if (st.bookings[key]) return st.bookings[key];
    /* 정기 예약 자동 적용 */
    var wd = WD[d.getDay()], prefs = st.recurring.days[wd];
    if (prefs && prefs.length) {
      var rows = queue(d, { booking: null }), ts = teamCount();
      for (var i = 0; i < prefs.length; i++) { var r = slotRow(rows, prefs[i]); if (r && r.left >= ts) { var b = { slot: prefs[i], kind: '정기 예약', teamSize: ts, auto: true }; st.bookings[key] = b; save(); return b; } }
    }
    return null;
  }
  function book(d, slot, kind, extra) {
    var st = load(), key = dateKey(d);
    var b = { slot: slot, kind: kind || '오늘만 변경', teamSize: teamCount(), at: new Date().toISOString() };
    if (extra) Object.keys(extra).forEach(function (k) { b[k] = extra[k]; });
    st.bookings[key] = b; delete st.waitlist[key]; save(); return b;
  }

  /* ---------- 피드백과 자동 보정 ---------- */
  var BUCKETS = { '0~3분': 1.5, '3~6분': 4.5, '6~10분': 8, '10분+': 12 };
  function sendFeedback(d, fb) {
    var st = load(), key = dateKey(d), s = st.settings;
    var b = st.bookings[key] || currentBooking(d);
    var rows = queue(d);
    var r = b ? slotRow(rows, b.slot) : null;
    var expected = r ? r.wait : 0;
    var reported = BUCKETS[fb.bucket] !== undefined ? BUCKETS[fb.bucket] : expected;
    var rec = { date: key, slot: b ? b.slot : null, ate: fb.ate, timing: fb.timing, bucket: fb.bucket, present: fb.present || [], wait: reported, expected: expected, at: new Date().toISOString() };
    st.feedback = st.feedback.filter(function (f) { return f.date !== key; });
    st.feedback.push(rec);
    /* 배식 속도 자동 보정: μ오늘 = 0.8·μ어제 + 0.2·μ추정 (대기가 예상보다 짧으면 속도가 더 빠른 것) */
    if (fb.ate === '예' && expected > 0 && reported > 0) {
      var est = Math.max(3, Math.min(12, s.mu * (expected / reported)));
      var mu = Math.round((0.8 * s.mu + 0.2 * est) * 100) / 100;
      s.muHistory = (s.muHistory || []).concat([{ date: key, from: s.mu, to: mu }]).slice(-30);
      s.mu = mu;
    }
    st.user.points = (st.user.points || 0) + 5;
    save();
    return rec;
  }

  /* 최근 등교일 5일의 대기 기록 (피드백이 있으면 실제, 없으면 비어 있음) */
  function weekRecords(now) {
    now = now || new Date();
    var out = [], d = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    while (out.length < 5) {
      if (d.getDay() !== 0 && d.getDay() !== 6) {
        var key = dateKey(d), f = null;
        load().feedback.forEach(function (x) { if (x.date === key) f = x; });
        out.unshift({ day: WD[d.getDay()], key: key, wait: f ? f.wait : null, expected: f ? f.expected : null });
      }
      d.setDate(d.getDate() - 1);
    }
    return out;
  }

  /* 교실 배정표용: 우리 반 팀 목록 (시연용 다른 팀 + 우리 팀) */
  function classBoard(d, cls) {
    var st = load();
    var seed = {
      '2학년 1반': [['12:10', 'B팀 · 김하늘 외 2명'], ['12:15', 'D팀 · 정우진 외 4명'], ['12:40', 'A팀 · 이도윤 외 3명'], ['12:50', 'C팀 · 한지우 외 1명']],
      '2학년 3반': [['12:10', 'B팀 · 김하늘 외 2명'], ['12:15', 'D팀 · 정우진 외 4명'], ['12:35', 'C팀 · 송민아 외 1명'], ['12:40', 'E팀 · 오세훈 외 2명'], ['12:45', 'F팀 · 한지우 외 3명']],
      '2학년 5반': [['12:20', 'A팀 · 이지호 외 3명'], ['12:30', 'B팀 · 문서윤 외 2명'], ['12:45', 'C팀 · 강하준 외 4명']]
    };
    var rows = (seed[cls] || []).slice();
    if (st.user) {
      var mine = st.user.grade + '학년 ' + st.user.cls + '반';
      if (mine === cls) {
        var b = currentBooking(d);
        if (b) rows.push([b.slot, '우리 팀 · ' + (st.user.name || '나') + ' 외 ' + (teamCount() - 1) + '명', true]);
      }
    }
    rows.sort(function (a, b) { return mins(a[0]) - mins(b[0]); });
    return rows;
  }

  global.NB = {
    KEY: KEY, load: load, reload: reload, save: save, reset: reset,
    hydrate: hydrate, setPersist: setPersist, setAI: setAI, engineLabel: engineLabel,
    WD: WD, mins: mins, hhmm: hhmm, pad: pad, dateKey: dateKey, fmtDate: fmtDate, fmtDateKo: fmtDateKo, nowHHMM: nowHHMM,
    targetDate: targetDate, isToday: isToday, deadlineLeft: deadlineLeft,
    slots: slots, capacity: capacity, baseDemand: baseDemand, queue: queue, slotRow: slotRow, recommend: recommend,
    teamCount: teamCount, ensureTeam: ensureTeam, currentBooking: currentBooking, book: book,
    sendFeedback: sendFeedback, weekRecords: weekRecords, classBoard: classBoard, BUCKETS: BUCKETS,
    KIND_WORD: { f: '여유', m: '보통', b: '꽉 참', y: '내 예약' }
  };
})(window);
