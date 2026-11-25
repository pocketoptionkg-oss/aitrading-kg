/* AITRADING.KG — «⚠️ Шашылыш» плашкасы (бардык беттердин үстүндө) жана билдирмелер.
   1) Рынок эрежеси — браузер өзү эсептейт, жандуу маалымат: Binance (запасы data-api.binance.vision, анан BingX).
      Себет жана чектер: config.js → ALERTS. Бүт рынок = себеттеги монеталардын өзгөрүүсүнүн МЕДИАНАСЫ.
      |медиана 24 с| ≥ move24 %  же  |медиана 1 с| ≥ move1h %  → плашка.  Ботто да ушундай: tools/market_pulse.py
   2) Админдин шашылыш жаңылыгы жана твиттер — /api/live (Telegram-бот алгач каналга жазат, анан бул жерге).
   3) Билдирме: сайт/тиркеме ачык болсо — ушул жерден; жабык болсо — сервердик Web Push (sw.js → /api/live). */
(function () {
  "use strict";
  if (!window.AT || window.ATAlerts) return;

  var CFG = window.AITRADING_CONFIG || {}, A = CFG.ALERTS || {};
  var BASKET = (A.basket && A.basket.length ? A.basket : ["BTC", "ETH", "XRP", "BNB", "SOL", "DOGE", "TRX", "ADA", "LINK", "AVAX"]).slice(0, 30);
  var TH24 = +A.move24 || 5, TH1 = +A.move1h || 3;
  var IS_LOCAL = /^(localhost|127\.0\.0\.1|\[::1\]|)$/.test(location.hostname);
  var VERIFY = "https://ru.tradingview.com/symbols/CRYPTOCAP-TOTAL/";
  var DISMISS_KEY = "aitrading-urgent-x", SEEN_KEY = "aitrading-urgent-seen", PUSH_KEY = "aitrading-push";
  var REPEAT_MS = 6 * 3600 * 1000;

  /* ---------- Тексттер (KY / RU) ---------- */
  var D = window.AITRADING_I18N || (window.AITRADING_I18N = { ky: {}, ru: {} });
  var T = {
    ky: {
      "ur.badge": "Шашылыш", "ur.more": "Кененирээк", "ur.check": "TradingView'дон текшерүү", "ur.close": "Жабуу",
      "ur.src": "Булак", "ur.news": "Шашылыш жаңылык",
      "ur.up24": "Бүт крипто рыногу 24 саатта өстү: {v}", "ur.dn24": "Бүт крипто рыногу 24 саатта түштү: {v}",
      "ur.up1": "Крипто рыногу кескин өстү: 1 саатта {v1}, 24 саатта {v24}", "ur.dn1": "Крипто рыногу кескин түштү: 1 саатта {v1}, 24 саатта {v24}",
      "ur.turn": "Крипто рыногу бурулду: 1 саатта {v1} (24 саатта {v24})",
      "ur.note": "{n} ири монетанын медианасы, {src}", "ur.ntf_t": "⚠️ Шашылыш · AITRADING.KG", "ur.test": "ТЕСТ"
    },
    ru: {
      "ur.badge": "Срочно", "ur.more": "Подробнее", "ur.check": "Проверить на TradingView", "ur.close": "Закрыть",
      "ur.src": "Источник", "ur.news": "Срочная новость",
      "ur.up24": "Весь крипторынок вырос за 24 ч: {v}", "ur.dn24": "Весь крипторынок упал за 24 ч: {v}",
      "ur.up1": "Крипторынок резко вырос: {v1} за час, {v24} за 24 ч", "ur.dn1": "Крипторынок резко упал: {v1} за час, {v24} за 24 ч",
      "ur.turn": "Крипторынок развернулся: {v1} за час (за 24 ч {v24})",
      "ur.note": "медиана {n} крупнейших монет, {src}", "ur.ntf_t": "⚠️ Срочно · AITRADING.KG", "ur.test": "ТЕСТ"
    }
  };
  Object.keys(T).forEach(function (l) { D[l] = D[l] || {}; Object.keys(T[l]).forEach(function (k) { if (!(k in D[l])) D[l][k] = T[l][k]; }); });
  function tt(key, vars) {
    return String(AT.t(key)).replace(/\{(\w+)\}/g, function (m, k) { return vars && k in vars ? vars[k] : m; });
  }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function pct(v) { return (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v).toFixed(1) + "%"; }
  function median(a) { var s = a.slice().sort(function (x, y) { return x - y; }), m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; }
  function L() { return AT.lang() === "ru" ? "ru" : "ky"; }
  function getJ(k) { try { return JSON.parse(AT.store(k) || "null"); } catch (e) { return null; } }
  function setJ(k, v) { AT.store(k, JSON.stringify(v)); }

  function getJSON(url, ms) {
    var ctl = window.AbortController ? new AbortController() : null;
    var timer = setTimeout(function () { if (ctl) ctl.abort(); }, ms || 8000);
    return fetch(url, { cache: "no-store", signal: ctl ? ctl.signal : undefined }).then(function (r) {
      clearTimeout(timer);
      if (!r.ok) throw new Error(r.status);
      return r.json();
    }, function (e) { clearTimeout(timer); throw e; });
  }

  /* ---------- 1. Рынок пульсу ---------- */
  var BINANCE = ["https://api.binance.com", "https://data-api.binance.vision"];
  function fromBinance(i) {
    var base = BINANCE[i || 0];
    var syms = encodeURIComponent(JSON.stringify(BASKET.map(function (b) { return b + "USDT"; })));
    function win(w) { return getJSON(base + "/api/v3/ticker?type=MINI&windowSize=" + w + "&symbols=" + syms, 8000); }
    return Promise.all([win("1d"), win("1h")]).then(function (res) {
      var rows = {};
      res.forEach(function (list, j) {
        list.forEach(function (r) {
          var o = +r.openPrice, c = +r.lastPrice, s = r.symbol.replace(/USDT$/, "");
          if (!(o > 0)) return;
          rows[s] = rows[s] || {};
          rows[s][j ? "c1h" : "c24"] = (c / o - 1) * 100;
          rows[s].last = c;
        });
      });
      return { rows: rows, src: "Binance" };
    }).catch(function (e) {
      if ((i || 0) + 1 < BINANCE.length) return fromBinance((i || 0) + 1);
      throw e;
    });
  }
  /* Запас: BingX'тин маалыматы сайттын өзүндө (assets/data/bingx.json, GitHub Actions ар 2 саатта) — 24 саат гана */
  function fromBingxFile() {
    return getJSON("assets/data/bingx.json", 8000).then(function (j) {
      var rows = {};
      (j.top || []).forEach(function (r) { if (BASKET.indexOf(r.base) >= 0) rows[r.base] = { c24: +r.chg, last: +r.last }; });
      if (Object.keys(rows).length < (BASKET.length >> 1) + 1) throw new Error("bingx");
      return { rows: rows, src: "BingX", stale: j.updated };
    });
  }

  var demo = IS_LOCAL && (new URLSearchParams(location.search).get("alertdemo") || "");
  function demoPulse() {
    var d = /dn|down/.test(demo) ? -1 : 1, rows = {};
    BASKET.forEach(function (b, i) { rows[b] = { c24: d * (4 + i * 0.6), c1h: (/turn/.test(demo) ? -d : d) * (2.5 + i * 0.3), last: 1 }; });
    return Promise.resolve({ rows: rows, src: "Binance", demo: true });
  }

  function pulse() {
    return (demo ? demoPulse() : fromBinance(0).catch(fromBingxFile)).then(function (p) {
      var c24 = [], c1 = [];
      Object.keys(p.rows).forEach(function (k) {
        if (isFinite(p.rows[k].c24)) c24.push(p.rows[k].c24);
        if (isFinite(p.rows[k].c1h)) c1.push(p.rows[k].c1h);
      });
      if (c24.length < (BASKET.length >> 1) + 1) throw new Error("few");
      p.n = c24.length;
      p.m24 = Math.round(median(c24) * 100) / 100;
      p.m1h = c1.length ? Math.round(median(c1) * 100) / 100 : null;
      p.up = c24.filter(function (x) { return x > 0; }).length;
      p.dn = c24.filter(function (x) { return x < 0; }).length;
      p.th24 = TH24; p.th1h = TH1; p.basket = BASKET; p.t = Date.now();
      return p;
    });
  }

  function marketAlert(p) {
    if (!p) return null;
    var v = { v: pct(p.m24), v24: pct(p.m24), v1: p.m1h == null ? "" : pct(p.m1h) };
    var note = tt("ur.note", { n: p.n, src: p.src });
    if (p.m1h != null && Math.abs(p.m1h) >= TH1) {
      var d1 = p.m1h > 0 ? 1 : -1, turned = p.m24 * p.m1h < 0 && Math.abs(p.m24) >= 1;
      return { id: "m1h:" + (d1 > 0 ? "up" : "dn"), kind: "market", dir: d1,
        text: tt(turned ? "ur.turn" : d1 > 0 ? "ur.up1" : "ur.dn1", v), note: note, verify: VERIFY, demo: p.demo };
    }
    if (Math.abs(p.m24) >= TH24) {
      var d = p.m24 > 0 ? 1 : -1;
      return { id: "m24:" + (d > 0 ? "up" : "dn"), kind: "market", dir: d, text: tt(d > 0 ? "ur.up24" : "ur.dn24", v), note: note, verify: VERIFY, demo: p.demo };
    }
    return null;
  }

  /* ---------- 2. /api/live: админдин шашылыш жаңылыктары, твиттер ---------- */
  var live = null, liveOk = null, liveFail = 0;
  function loadLive() {
    if (liveOk === false && Date.now() - liveFail < 10 * 60000) return Promise.resolve(null);
    return getJSON("/api/live", 6000).then(function (j) {
      liveOk = !!(j && j.ok);
      live = j && j.ok ? j : null;
      if (!liveOk) liveFail = Date.now();
      return live;
    }).catch(function () { liveOk = false; liveFail = Date.now(); live = null; return null; });   // статикалык хостинг же KV жок — рынок эрежеси баары бир иштейт
  }
  function urgentAlerts() {
    if (!live || !live.urgent) return [];
    var l = L();
    return live.urgent.slice(0, 2).map(function (u) {
      return { id: u.id, kind: "news", dir: -1, text: u[l] || u.ky || u.ru, url: u.url, t: u.t };
    });
  }

  /* ---------- Плашка ---------- */
  var state = { pulse: null, alerts: [], err: null };
  var subs = [];
  function dismissed() { var d = getJ(DISMISS_KEY) || {}; var now = Date.now(); Object.keys(d).forEach(function (k) { if (now - d[k] > REPEAT_MS) delete d[k]; }); return d; }

  function render() {
    var host = document.querySelector("[data-urgent-bar]");
    var dis = dismissed();
    var list = state.alerts.filter(function (a) { return !dis[a.id]; });
    if (!list.length) { if (host) host.remove(); document.documentElement.classList.remove("has-urgent"); return; }
    if (!host) {
      host = document.createElement("div");
      host.setAttribute("data-urgent-bar", "");
      host.className = "urgent-bar";
      host.setAttribute("role", "alert");
      var anchor = document.querySelector(".ticker") || document.querySelector(".site-header");
      if (anchor && anchor.parentNode) anchor.parentNode.insertBefore(host, anchor.nextSibling);
      else document.body.insertBefore(host, document.body.firstChild);
      host.addEventListener("click", function (e) {
        var x = e.target.closest("[data-ur-x]");
        if (!x) return;
        var d = dismissed(); d[x.getAttribute("data-ur-x")] = Date.now(); setJ(DISMISS_KEY, d);
        AT.track("urgent_close", {});
        render();
      });
    }
    document.documentElement.classList.add("has-urgent");
    host.innerHTML = list.map(function (a) {
      var more = a.kind === "news" && a.url
        ? '<a class="ur-link" href="' + esc(a.url) + '" target="_blank" rel="noopener">' + esc(AT.t("ur.src")) + " ↗</a>"
        : '<a class="ur-link" href="news.html#pulse">' + esc(AT.t("ur.more")) + " →</a>";
      var check = a.verify ? '<a class="ur-link ur-ghost" href="' + esc(a.verify) + '" target="_blank" rel="noopener">' + esc(AT.t("ur.check")) + " ↗</a>" : "";
      return '<div class="ur-row ' + (a.dir > 0 ? "is-up" : "is-dn") + '">' +
        '<div class="container ur-in">' +
        '<span class="ur-badge"><i class="ur-dot"></i>' + esc(a.demo ? AT.t("ur.test") : a.kind === "news" ? AT.t("ur.news") : AT.t("ur.badge")) + "</span>" +
        '<p class="ur-text"><b>' + esc(a.text) + "</b>" + (a.note ? ' <span class="ur-note">(' + esc(a.note) + ")</span>" : "") + "</p>" +
        '<span class="ur-acts">' + more + check +
        '<button type="button" class="ur-x" data-ur-x="' + esc(a.id) + '" aria-label="' + esc(AT.t("ur.close")) + '">×</button></span>' +
        "</div></div>";
    }).join("");
  }

  /* ---------- 3. Билдирме (сайт ачык турганда) ---------- */
  function maybeNotify() {
    if (!AT.notifyOn()) return;
    var seen = getJ(SEEN_KEY) || {}, now = Date.now(), changed = false;
    state.alerts.forEach(function (a) {
      if (a.demo) return;
      if (seen[a.id] && now - seen[a.id] < REPEAT_MS) return;
      seen[a.id] = now; changed = true;
      AT.notify(AT.t("ur.ntf_t"), a.text + (a.note ? " (" + a.note + ")" : ""), a.kind === "news" && a.url ? a.url : "news.html#pulse", "aitrading-urgent");
    });
    if (changed) setJ(SEEN_KEY, seen);
  }
  /* Биринчи ачылганда эски эскертүүнү билдирме кылбайбуз — «көрүлдү» деп белгилейбиз */
  var first = true;

  function update() {
    return Promise.all([
      pulse().then(function (p) { state.pulse = p; state.err = null; }, function (e) { state.err = e; }),
      loadLive()
    ]).then(function () {
      var a = [];
      urgentAlerts().forEach(function (u) { a.push(u); });
      var m = marketAlert(state.pulse);
      if (m) a.push(m);
      state.alerts = a;
      if (first) {
        first = false;
        if (!AT.notifyOn()) { var seen = getJ(SEEN_KEY) || {}; a.forEach(function (x) { seen[x.id] = seen[x.id] || Date.now(); }); setJ(SEEN_KEY, seen); }
      }
      render();
      maybeNotify();
      subs.forEach(function (fn) { try { fn(state, live); } catch (e) { console.error(e); } });
    });
  }

  var timer = null;
  function schedule() {
    clearTimeout(timer);
    // Көрүнүп турганда — 2 мүнөт; фондо — билдирме күйүк болсо гана, 5 мүнөт
    var ms = document.hidden ? (AT.notifyOn() ? 5 * 60000 : 0) : 2 * 60000;
    if (ms) timer = setTimeout(function () { update().then(schedule, schedule); }, ms);
  }
  document.addEventListener("visibilitychange", function () { if (!document.hidden) update().then(schedule, schedule); else schedule(); });
  AT.onLang(function () { if (state.pulse || live) { var m = marketAlert(state.pulse); state.alerts = urgentAlerts().concat(m ? [m] : []); render(); subs.forEach(function (fn) { fn(state, live); }); } savePrefLang(); });

  /* ---------- Сервердик Web Push (тиркеме жабык болсо да) ---------- */
  function b64uToBytes(s) {
    s = s.replace(/-/g, "+").replace(/_/g, "/");
    while (s.length % 4) s += "=";
    var bin = atob(s), out = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }
  var pushInfo = null;
  function pushInfoP() {
    if (pushInfo) return pushInfo;
    if (!("serviceWorker" in navigator) || !("PushManager" in window) || !window.isSecureContext) return (pushInfo = Promise.resolve({ ready: false, why: "unsupported" }));
    pushInfo = getJSON("/api/push", 6000).then(function (j) { return j && j.ready ? j : { ready: false, why: "server" }; }, function () { return { ready: false, why: "server" }; });
    return pushInfo;
  }
  function savePrefLang() {
    if (!window.caches) return;
    try { caches.open("aitrading-prefs").then(function (c) { return c.put("lang", new Response(L())); }).catch(function () {}); } catch (e) { /* */ }
  }
  function swReg() {
    return navigator.serviceWorker.getRegistration().then(function (r) { return r || navigator.serviceWorker.register("sw.js"); }).then(function () { return navigator.serviceWorker.ready; });
  }
  function pushState() {
    return pushInfoP().then(function (info) {
      if (!info.ready) return { ready: false, on: false, why: info.why };
      return navigator.serviceWorker.getRegistration().then(function (r) {
        return r && r.pushManager ? r.pushManager.getSubscription() : null;
      }).then(function (s) { return { ready: true, on: !!s }; });
    });
  }
  function subscribePush() {
    return pushInfoP().then(function (info) {
      if (!info.ready) return false;
      return swReg().then(function (reg) {
        return reg.pushManager.getSubscription().then(function (s) {
          return s || reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64uToBytes(info.publicKey) });
        });
      }).then(function (sub) {
        savePrefLang();
        return fetch("/api/push", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ subscription: sub.toJSON(), lang: L() }) });
      }).then(function (r) { AT.store(PUSH_KEY, r.ok ? "1" : "0"); AT.track("push_sub", { ok: r.ok }); return r.ok; });
    }).catch(function (e) { if (IS_LOCAL) console.warn("[push]", e); return false; });
  }
  function unsubscribePush() {
    if (!("serviceWorker" in navigator)) return Promise.resolve(false);
    return navigator.serviceWorker.getRegistration().then(function (r) { return r && r.pushManager ? r.pushManager.getSubscription() : null; }).then(function (s) {
      AT.store(PUSH_KEY, "0");
      if (!s) return true;
      var ep = s.endpoint;
      return s.unsubscribe().then(function () {
        return fetch("/api/push", { method: "DELETE", headers: { "content-type": "application/json" }, body: JSON.stringify({ endpoint: ep }) }).then(function () { return true; }, function () { return true; });
      });
    });
  }

  window.ATAlerts = {
    state: function () { return state; },
    live: function () { return live; },
    liveOk: function () { return liveOk; },
    update: update,
    onUpdate: function (fn) { subs.push(fn); if (state.pulse || state.err) fn(state, live); },
    pushState: pushState,
    subscribePush: subscribePush,
    unsubscribePush: unsubscribePush,
    rule: { basket: BASKET, move24: TH24, move1h: TH1, verify: VERIFY },
    fmt: pct
  };

  update().then(schedule, schedule);
})();
