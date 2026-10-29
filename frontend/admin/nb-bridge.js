/* 눈치밥 ↔ Streamlit 연결
   - Streamlit 안에서 열리면: 데이터는 서버(state.json)에 저장되고, 4초마다 최신 상태를 받아 온다.
   - 그냥 브라우저에서 열리면: 기존처럼 이 기기 저장소를 쓴다. */
(function (global) {
  'use strict';
  var inFrame = false;
  try { inFrame = global.parent && global.parent !== global; } catch (e) { inFrame = true; }

  function post(type, extra) {
    var msg = { isStreamlitMessage: true, type: type };
    if (extra) Object.keys(extra).forEach(function (k) { msg[k] = extra[k]; });
    try { global.parent.postMessage(msg, '*'); } catch (e) { /* 무시 */ }
  }
  function snapshot(s) { var o = {}; Object.keys(s || {}).forEach(function (k) { o[k] = JSON.stringify(s[k]); }); return o; }

  var rev = -1, synced = {}, seq = 0, started = false, firstDone = false;
  var unacked = {}, lastNonce = null, timer = null, listeners = [];
  function pending() { return Object.keys(unacked).length > 0; }

  function fit() {
    var h = 0;
    try { h = global.parent.innerHeight; } catch (e) { h = 0; }
    if (!h || h < 320) h = Math.max(640, (global.screen && global.screen.availHeight ? global.screen.availHeight - 140 : 760));
    post('streamlit:setFrameHeight', { height: h });
  }
  function emit(extra) {
    seq++; lastNonce = Date.now() + '-' + seq;
    var v = { nonce: lastNonce, baseRev: rev };
    if (pending()) v.patch = unacked;
    if (extra) Object.keys(extra).forEach(function (k) { v[k] = extra[k]; });
    post('streamlit:setComponentValue', { value: v, dataType: 'json' });
  }
  /* 바뀐 묶음은 서버가 받았다고 알려 줄 때(ack)까지 모아 두고, 못 받았으면 다시 보낸다 */
  function flush() { timer = null; if (pending()) emit(); }

  var Sync = {
    active: inFrame,
    ready: false,
    nav: function (page) { if (inFrame) { clearTimeout(timer); timer = null; emit({ nav: page }); } },
    onRender: function (fn) { listeners.push(fn); },
    /* rerender(first, args) 는 서버 상태를 받은 뒤 화면을 다시 그리는 함수 */
    init: function (rerender) {
      if (!Sync.active || started) return false;
      started = true;
      NB.setPersist(function (s) {
        var snap = snapshot(s), any = false;
        Object.keys(snap).forEach(function (k) { if (k !== '_rev' && snap[k] !== synced[k]) { unacked[k] = JSON.parse(snap[k] === undefined ? 'null' : snap[k]); any = true; } });
        if (!any) return;
        synced = snap;
        clearTimeout(timer); timer = setTimeout(flush, 120);
      });
      global.addEventListener('message', function (e) {
        var d = e.data;
        if (!d || d.type !== 'streamlit:render') return;
        var a = d.args || {};
        if (a.ai) NB.setAI(a.ai);
        listeners.forEach(function (f) { try { f(a); } catch (x) { /* 무시 */ } });
        if (lastNonce && a.ack === lastNonce) unacked = {};
        else if (pending() && !timer) timer = setTimeout(flush, 400);
        var r = typeof a.rev === 'number' ? a.rev : parseInt(a.rev, 10) || 0;
        var fresh = a.state && r > rev && !pending() && !timer;
        if (fresh) {
          rev = r;
          NB.hydrate(JSON.parse(JSON.stringify(a.state)));
          synced = snapshot(NB.load());
        }
        if (fresh || !firstDone) {
          var first = !firstDone; firstDone = true; Sync.ready = true;
          rerender(first, a);
        }
        fit();
      });
      try { global.parent.addEventListener('resize', fit); } catch (e) { /* 무시 */ }
      global.addEventListener('resize', fit);
      post('streamlit:componentReady', { apiVersion: 1 });
      fit();
      return true;
    }
  };
  global.NBSync = Sync;
})(window);
