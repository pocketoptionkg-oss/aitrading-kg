/* Жаңылыктар:
   - башкы лента, пикирлер, теханализ — assets/data/news.json (tools/news_feed.py, RSS-булактар, ар 2 саатта);
   - твиттер — /api/live (Telegram-бот алгач каналга жарыялайт, анан бул жерге);
   - рынок пульсу жана билдирмелер — assets/js/alerts.js (window.ATAlerts);
   - TradingView: техникалык анализ виджети, жандуу лента жана экономикалык календарь. */
(function () {
  "use strict";
  if (!window.AT) return;
  var CFG = window.AITRADING_CONFIG || {};
  var FEED_KEY = "aitrading-news-feed2", TA_KEY = "aitrading-news-ta", TOPIC_KEY = "aitrading-news-topic", PAGE = 12;
  var CAL_KEY = "aitrading-cal-tab", CAL_IMP_KEY = "aitrading-cal-imp";
  var feed = AT.store(FEED_KEY) || "all", topic = AT.store(TOPIC_KEY) || "all", shown = PAGE, data = null, failed = false;
  var fresh = [];   // /api/live → fresh: бот RSS'тен ар 10 мүнөттө алган жаңы жаңылыктар (news.json ар 2 саатта)
  var NEW_MS = 60 * 60000;

  function L() { return AT.lang() === "ru" ? "ru" : "ky"; }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function tt(key, vars) { return String(AT.t(key)).replace(/\{(\w+)\}/g, function (m, k) { return vars && k in vars ? vars[k] : m; }); }
  function safeUrl(u) { return /^https:\/\/[^\s"<>]+$/i.test(String(u || "")) ? u : "#"; }
  function ago(t) {
    var m = Math.max(0, Math.round((Date.now() - t) / 60000));
    if (m < 2) return AT.t("nf.now");
    if (m < 60) return tt("nf.ago_m", { n: m });
    if (m < 48 * 60) return tt("nf.ago_h", { n: Math.round(m / 60) });
    return tt("nf.ago_d", { n: Math.round(m / 1440) });
  }
  function fullDate(t) {
    try { return new Date(t).toLocaleString(L() === "ru" ? "ru-RU" : "ky-KG", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }); } catch (e) { return ""; }
  }
  /* Аталыш: KG режиминде котормо, жок болсо орусча түп нуска «RU» белгиси менен */
  function head(x) {
    if (L() === "ru") return { text: x.ru || x.orig, ruOnly: false };
    return x.ky ? { text: x.ky, ruOnly: false } : { text: x.ru || x.orig, ruOnly: true };
  }
  function body(x) {
    if (L() === "ru") return x.desc_ru || x.desc || "";
    if (x.desc_ky) return x.desc_ky;
    return x.ky ? "" : x.desc_ru || x.desc || "";   // аталыш кыргызча болсо — орусча сыпаттаманы аралаштырбайбыз
  }
  var AVATAR = '<img class="nf-ava" src="assets/img/author-avatar.webp" width="20" height="20" alt="" loading="lazy">';

  function card(x, kind) {
    var h = head(x), d = kind === "main" ? "" : body(x);
    var who = kind === "opinions" && x.who_ky ? '<span class="nf-who">' + esc(L() === "ru" ? x.who_ru : x.who_ky) + "</span>" : "";
    var sym = kind === "ta" && x.sym ? '<span class="nf-sym">' + esc(x.sym.replace(/^[A-Z_]+:/, "")) + "</span>" : "";
    var flags = (x.imp ? '<span class="nf-imp imp-' + esc(x.imp) + '" title="' + esc(AT.t("nf.imp_" + x.imp + "_t")) + '">' + esc(AT.t("nf.imp_" + x.imp)) + "</span>" : "") +
      (Date.now() - x.t < NEW_MS ? '<span class="nf-new">' + esc(AT.t("nf.new")) + "</span>" : "");
    var meta =
      '<div class="nf-meta">' + flags + who + sym +
      '<span class="nf-src">' + esc(x.src) + "</span>" +
      (x.cat ? '<span class="nf-cat cat-' + esc(x.cat) + '">' + esc(AT.t("nf.cat_" + x.cat)) + "</span>" : "") +
      '<time datetime="' + new Date(x.t).toISOString() + '" title="' + esc(fullDate(x.t)) + '">' + esc(ago(x.t)) + "</time>" +
      (x.n > 1 ? '<span class="nf-n">' + esc(tt("nf.n_src", { n: x.n })) + "</span>" : "") +
      "</div>";
    var img = kind === "ta" && x.img ? '<a class="nf-img" href="' + esc(safeUrl(x.url)) + '" target="_blank" rel="noopener nofollow"><img src="' + esc(x.img) + '" alt="" loading="lazy" referrerpolicy="no-referrer"></a>' : "";
    var by = kind === "ta" && x.author
      ? '<span class="nf-auth">' + esc(AT.t("nf.author")) + ": <b>" + esc(x.author) + "</b></span>"
      : '<span class="nf-tag" title="' + esc(AT.t("nf.by_t")) + '">' + AVATAR + "<b>" + esc(AT.t("nf.by")) + "</b></span>";
    var also = (x.also || []).map(function (a) { return '<a href="' + esc(safeUrl(a.url)) + '" target="_blank" rel="noopener nofollow">' + esc(a.src) + "</a>"; }).join(", ");
    return '<article class="nf-item' + (img ? " has-img" : "") + '">' + img + '<div class="nf-main">' + meta +
      '<h3 class="nf-h"><a href="' + esc(safeUrl(x.url)) + '" target="_blank" rel="noopener nofollow">' + esc(h.text) + "</a>" +
      (h.ruOnly ? ' <abbr class="nf-ru" title="' + esc(AT.t("nf.ru_only_t")) + '">' + esc(AT.t("nf.ru_only")) + "</abbr>" : "") + "</h3>" +
      (d ? '<p class="nf-d">' + esc(d) + "</p>" : "") +
      '<div class="nf-by">' + by +
      '<a class="nf-go" href="' + esc(safeUrl(x.url)) + '" target="_blank" rel="noopener nofollow">' + esc(AT.t("nf.src")) + ": " + esc(x.src) + " ↗</a>" +
      (also ? '<span class="nf-also">' + esc(AT.t("nf.also")) + " " + also + "</span>" : "") +
      "</div></div></article>";
  }

  function renderList(kind) {
    var box = document.querySelector('[data-nf="' + kind + '"]');
    if (!box) return;
    if (failed) { box.innerHTML = '<p class="nf-empty">' + esc(AT.t("nf.err")) + "</p>"; return; }
    if (!data) return;
    var list = listOf(kind);
    if (kind === "main" && feed !== "all") list = list.filter(function (x) { return x.cat === feed; });
    if (kind === "main" && topic !== "all") list = list.filter(function (x) { return (x.tp || []).indexOf(topic) >= 0; });
    var more = document.querySelector("[data-nf-more]");
    if (kind === "main") {
      if (more) more.hidden = list.length <= shown;
      list = list.slice(0, shown);
    } else if (kind === "ta") list = list.slice(0, 8);
    box.innerHTML = list.length ? list.map(function (x) { return card(x, kind); }).join("") : '<p class="nf-empty">' + esc(AT.t("nf.empty")) + "</p>";
  }

  /* news.json + боттон келген жаңылары (ошол эле шилтеме эки жолу чыкпайт) */
  function listOf(kind) {
    var base = (data && data[kind]) || [];
    if (!fresh.length) return base;
    var seen = {};
    base.forEach(function (x) { seen[x.id] = seen[x.url] = 1; (x.also || []).forEach(function (a) { seen[a.url] = 1; }); });
    var add = fresh.filter(function (x) { return x.kind === kind && !seen[x.id] && !seen[x.url]; });
    return add.length ? add.concat(base).sort(function (a, b) { return b.t - a.t; }) : base;
  }

  /* ---------- Күндүн негизги фактылары ---------- */
  function keyScore(x) { return (x.imp === "hot" ? 30 : x.imp === "top" ? 20 : 0) + Math.min(x.n || 1, 6) * 3; }
  function renderKey() {
    var box = document.querySelector("[data-nkey]");
    if (!box) return;
    if (failed) { box.innerHTML = '<li class="nf-empty">' + esc(AT.t("nf.err")) + "</li>"; return; }
    if (!data) return;
    var day = Date.now() - 24 * 3600000;
    var list = listOf("main").filter(function (x) { return x.t > day && (x.imp || (x.n || 1) > 1); })
      .sort(function (a, b) { return keyScore(b) - keyScore(a) || b.t - a.t; }).slice(0, 6);
    if (list.length < 3) list = list.concat(listOf("main").filter(function (x) { return list.indexOf(x) < 0; }).slice(0, 3 - list.length));
    box.innerHTML = list.map(function (x) {
      var h = head(x);
      return '<li><a href="' + esc(safeUrl(x.url)) + '" target="_blank" rel="noopener nofollow">' + esc(h.text) + "</a>" +
        (h.ruOnly ? ' <abbr class="nf-ru" title="' + esc(AT.t("nf.ru_only_t")) + '">RU</abbr>' : "") +
        '<small>' + (x.imp ? '<span class="nf-imp imp-' + esc(x.imp) + '">' + esc(AT.t("nf.imp_" + x.imp)) + "</span> " : "") +
        esc(x.src) + ((x.n || 1) > 1 ? " · " + esc(tt("nf.n_src", { n: x.n })) : "") + " · " + esc(ago(x.t)) + "</small></li>";
    }).join("") || '<li class="nf-empty">' + esc(AT.t("nf.empty")) + "</li>";
    var c = document.querySelector("[data-nkey-cal]");
    if (c && cal) {
      var now = Date.now(), end = dayStart(1);
      var today = (cal.events || []).filter(function (e) { return e.imp === 3 && e.t >= now - 3600000 && e.t < end; });
      c.hidden = !today.length;
      if (today.length) {
        var e0 = today[0];
        c.innerHTML = "📅 " + esc(tt("n.key_cal", { n: today.length })) + " <b>" + esc(hm(e0.t)) + " " + esc(e0.cur) + " — " + esc(evTitle(e0).text) + "</b>";
      }
    }
  }

  /* ---------- Дүйнөлүк экономикалык анонстор (assets/data/calendar.json — Forex Factory) ---------- */
  var cal = null, calTab = AT.store(CAL_KEY) || "today", calImp = AT.store(CAL_IMP_KEY) !== "0";
  var CUR = { USD: ["АКШ", "США"], EUR: ["Евроаймак", "Еврозона"], GBP: ["Улуу Британия", "Великобритания"], JPY: ["Япония", "Япония"],
    CNY: ["Кытай", "Китай"], CHF: ["Швейцария", "Швейцария"], CAD: ["Канада", "Канада"], AUD: ["Австралия", "Австралия"], NZD: ["Жаңы Зеландия", "Новая Зеландия"] };
  function dayStart(off) { var d = new Date(); d.setHours(0, 0, 0, 0); d.setDate(d.getDate() + off); return d.getTime(); }
  function hm(t) { var d = new Date(t); return ("0" + d.getHours()).slice(-2) + ":" + ("0" + d.getMinutes()).slice(-2); }
  /* Күндүн аты — өзүбүз: браузерлердин баарында эле кыргызча (ky) даталар жок, орусчага түшүп калат */
  var WD = { ky: ["Жекшемби", "Дүйшөмбү", "Шейшемби", "Шаршемби", "Бейшемби", "Жума", "Ишемби"],
             ru: ["Воскресенье", "Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"] };
  var MO = { ky: ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"],
             ru: ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"] };
  function dayName(t) {
    var d = new Date(t), l = L();
    return l === "ru" ? WD.ru[d.getDay()] + ", " + d.getDate() + " " + MO.ru[d.getMonth()] : WD.ky[d.getDay()] + ", " + d.getDate() + "-" + MO.ky[d.getMonth()];
  }
  function evTitle(e) { var v = L() === "ru" ? e.ru : e.ky; return v ? { text: v, en: false } : { text: e.en, en: true }; }
  function inLeft(t) {
    var m = Math.round((t - Date.now()) / 60000);
    if (m < 60) return tt("cal.in_m", { m: Math.max(1, m) });
    return tt("cal.in_h", { h: Math.floor(m / 60), m: m % 60 });
  }
  function calRow(e, nextId) {
    var ti = evTitle(e), now = Date.now(), past = e.t < now - 60000, cn = CUR[e.cur];
    var vals = [];
    if (e.fc) vals.push(esc(AT.t("cal.fc")) + ": <b>" + esc(e.fc) + "</b>");
    if (e.pv) vals.push(esc(AT.t("cal.pv")) + ": " + esc(e.pv));
    return '<div class="cal-row imp' + e.imp + (past ? " past" : "") + (e.id === nextId ? " next" : "") + '">' +
      '<time class="cal-t" datetime="' + new Date(e.t).toISOString() + '">' + esc(e.imp === 0 ? AT.t("cal.allday") : hm(e.t)) + "</time>" +
      '<span class="cal-cur" title="' + esc(cn ? cn[L() === "ru" ? 1 : 0] : e.cur) + '">' + esc(e.cur) + "</span>" +
      '<span class="cal-dots" title="' + esc(AT.t("cal.imp" + e.imp)) + '" aria-label="' + esc(AT.t("cal.imp" + e.imp)) + '">' + (e.imp === 0 ? "🏖" : "<i></i><i></i><i></i>") + "</span>" +
      '<div class="cal-ev"><b>' + esc(ti.text) + "</b>" + (ti.en ? ' <abbr class="nf-ru" title="' + esc(AT.t("cal.en_t")) + '">EN</abbr>' : "") +
      (e.id === nextId ? ' <span class="cal-in">⏰ ' + esc(inLeft(e.t)) + "</span>" : "") +
      (vals.length ? "<small>" + vals.join(" · ") + "</small>" : "") + "</div></div>";
  }
  function renderCal() {
    var box = document.querySelector("[data-cal]");
    document.querySelectorAll("[data-cal-tabs] button").forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-cal-tab") === calTab)); });
    var chk = document.querySelector("[data-cal-imp]");
    if (chk) chk.checked = calImp;
    if (!box || !cal) return;
    var ev = cal.events || [], a = 0, b = Infinity, now = Date.now();
    if (calTab === "today") { a = dayStart(0); b = dayStart(1); } else if (calTab === "tomorrow") { a = dayStart(1); b = dayStart(2); }
    var list = ev.filter(function (e) { return e.t >= a && e.t < b && (calImp ? e.imp === 3 || e.imp === 0 : true); });
    var next = ev.filter(function (e) { return e.imp >= 2 && e.t > now; })[0];
    var nextId = next && next.t - now < 24 * 3600000 ? next.id : null;
    if (!list.length) {
      box.innerHTML = '<p class="nf-empty">' + esc(AT.t(ev.length ? (calTab === "week" ? "cal.none_w" : "cal.none") : "cal.err")) + "</p>";
    } else if (calTab === "week") {
      var html = "", day = null;
      list.forEach(function (e) {
        var d = new Date(e.t); d.setHours(0, 0, 0, 0);
        if (d.getTime() !== day) { day = d.getTime(); html += '<h4 class="cal-day' + (day === dayStart(0) ? " today" : "") + '">' + esc(dayName(e.t)) + "</h4>"; }
        html += calRow(e, nextId);
      });
      box.innerHTML = html;
    } else box.innerHTML = list.map(function (e) { return calRow(e, nextId); }).join("");
    var f = document.querySelector("[data-cal-foot]");
    if (f) f.innerHTML = esc(tt("cal.foot", { d: cal.updated ? fullDate(Date.parse(cal.updated)) : "—" })) +
      ' <a href="' + esc(safeUrl(cal.source_url || "https://www.forexfactory.com/calendar")) + '" target="_blank" rel="noopener nofollow">Forex Factory ↗</a> · ' +
      '<a href="' + esc(safeUrl(cal.verify || "https://ru.tradingview.com/economic-calendar/")) + '" target="_blank" rel="noopener nofollow">' + esc(AT.t("cal.verify")) + " ↗</a>";
  }
  document.querySelectorAll("[data-cal-tabs] button").forEach(function (b) {
    b.addEventListener("click", function () { calTab = b.getAttribute("data-cal-tab"); AT.store(CAL_KEY, calTab); renderCal(); AT.track("cal_tab", { t: calTab }); });
  });
  var calChk = document.querySelector("[data-cal-imp]");
  if (calChk) calChk.addEventListener("change", function () { calImp = calChk.checked; AT.store(CAL_IMP_KEY, calImp ? "1" : "0"); renderCal(); });
  fetch("assets/data/calendar.json", { cache: "no-cache" }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(function (j) { cal = j; }, function () { cal = { events: [] }; }).then(function () { renderCal(); renderKey(); });

  function renderFoot() {
    var f = document.querySelector("[data-nf-foot]");
    if (!f || !data) return;
    var all = (data.main || []).concat(data.opinions || [], data.ta || []);
    var hasKy = all.some(function (x) { return x.ky; });
    var names = [];
    (data.sources || []).forEach(function (s) { if (names.indexOf(s.name) < 0) names.push(s.name); });
    f.innerHTML = esc(tt("nf.upd", { d: fullDate(Date.parse(data.updated)) })) + " · " + esc(tt("nf.sources", { s: names.join(", ") })) + " " +
      esc(AT.t(hasKy ? "nf.tr_ai" : "nf.tr_none"));
  }

  function renderAll() {
    ["main", "opinions", "ta"].forEach(renderList);
    renderKey();
    renderFoot();
    document.querySelectorAll("[data-news-tabs] button").forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-feed") === feed)); });
    document.querySelectorAll("[data-nf-topics] button").forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-tp") === topic)); });
  }
  document.querySelectorAll("[data-nf-topics] button").forEach(function (b) {
    b.addEventListener("click", function () {
      topic = b.getAttribute("data-tp");
      shown = PAGE;
      AT.store(TOPIC_KEY, topic);
      renderAll();
      AT.track("news_topic", { t: topic });
    });
  });
  function setFresh(live) {
    var f = (live && live.fresh) || [];
    var sig = f.map(function (x) { return x.id; }).join(",");
    if (sig === setFresh.sig) return;
    setFresh.sig = sig;
    fresh = f;
    if (data) renderAll();
  }

  document.querySelectorAll("[data-news-tabs] button").forEach(function (b) {
    b.addEventListener("click", function () {
      feed = b.getAttribute("data-feed");
      shown = PAGE;
      AT.store(FEED_KEY, feed);
      renderAll();
      AT.track("news_tab", { f: feed });
    });
  });
  var moreBtn = document.querySelector("[data-nf-more]");
  if (moreBtn) moreBtn.addEventListener("click", function () { shown += PAGE; renderList("main"); });

  fetch("assets/data/news.json", { cache: "no-cache" }).then(function (r) {
    if (!r.ok) throw new Error(r.status);
    return r.json();
  }).then(function (j) { data = j; }, function () { failed = true; }).then(renderAll);

  /* ---------- Твиттер (/api/live) ---------- */
  function renderAccounts() {
    var box = document.querySelector("[data-tw-acc]");
    if (!box) return;
    box.innerHTML = (CFG.FAMOUS_X || []).map(function (a) {
      return '<a class="tw-chip" href="https://x.com/' + encodeURIComponent(a.handle) + '" target="_blank" rel="noopener nofollow"><b>' + esc(a.name) + "</b> @" + esc(a.handle) + "</a>";
    }).join("");
  }
  function tgChannel() {
    var u = String((CFG.SOCIAL || {}).telegram || "").trim();
    return /^https:\/\/t\.me\/[A-Za-z0-9_]{4,}\/?$/i.test(u) ? u : null;
  }
  function renderTweets(live) {
    var box = document.querySelector("[data-tweets]");
    if (!box) return;
    var list = (live && live.tweets) || [];
    if (!list.length) {
      var ch = tgChannel();
      box.innerHTML = '<div class="tw-empty"><p>' + esc(AT.t("tw.empty")) + "</p>" +
        (ch ? '<a class="btn btn-ghost btn-sm" href="' + esc(ch) + '" target="_blank" rel="noopener"><svg aria-hidden="true"><use href="#i-tg"/></svg><span>' + esc(AT.t("tw.channel")) + "</span></a>" : "") + "</div>";
      return;
    }
    box.innerHTML = list.slice(0, 10).map(function (w) {
      var l = L(), text = w[l] || "", orig = w.text || "";
      return '<article class="nf-item tw">' +
        '<div class="nf-meta"><span class="nf-who">' + esc(w.name || "@" + w.handle) + "</span><span class=\"nf-src\">@" + esc(w.handle) + "</span>" +
        "<time>" + esc(w.date || ago(w.t)) + "</time></div>" +
        (text ? '<p class="tw-text">' + esc(text) + "</p><details class=\"tw-orig\"><summary>" + esc(AT.t("tw.orig")) + "</summary><p>" + esc(orig) + "</p></details>"
              : '<p class="tw-text">' + esc(orig) + "</p>") +
        '<div class="nf-by"><span class="nf-tag" title="' + esc(AT.t("tw.first")) + '">' + AVATAR + "<b>" + esc(AT.t("nf.by")) + "</b></span>" +
        '<a class="nf-go" href="' + esc(safeUrl(w.url)) + '" target="_blank" rel="noopener nofollow">' + esc(AT.t("tw.x")) + " ↗</a>" +
        (w.tg_url ? '<a class="nf-go" href="' + esc(safeUrl(w.tg_url)) + '" target="_blank" rel="noopener">' + esc(AT.t("tw.tg")) + " ↗</a>" : "") +
        "</div></article>";
    }).join("");
  }

  /* ---------- Рынок пульсу (alerts.js) ---------- */
  function renderPulse(st) {
    var p = st && st.pulse, fmt = window.ATAlerts ? ATAlerts.fmt : function (v) { return v.toFixed(1) + "%"; };
    function set(sel, html, cls) { var el = document.querySelector(sel); if (el) { el.innerHTML = html; if (cls != null) el.className = cls; } }
    if (!p) {
      if (st && st.err) set("[data-pulse-upd]", esc(AT.t("pl.err")));
      return;
    }
    var r = ATAlerts.rule;
    set("[data-p24]", esc(fmt(p.m24)), Math.abs(p.m24) >= r.move24 ? (p.m24 > 0 ? "is-up hot" : "is-dn hot") : p.m24 > 0 ? "is-up" : p.m24 < 0 ? "is-dn" : "");
    set("[data-p1h]", p.m1h == null ? AT.t("pl.no1h") : esc(fmt(p.m1h)), p.m1h == null ? "" : Math.abs(p.m1h) >= r.move1h ? (p.m1h > 0 ? "is-up hot" : "is-dn hot") : p.m1h > 0 ? "is-up" : p.m1h < 0 ? "is-dn" : "");
    set("[data-p24th]", esc(tt("pl.th", { v: r.move24 })));
    set("[data-p1hth]", esc(tt("pl.th", { v: r.move1h })));
    set("[data-pbr]", p.up + " / " + p.dn);
    var src = p.stale ? tt("pl.stale", { d: fullDate(Date.parse(p.stale)) }) : p.src;
    set("[data-psrc]", esc(src));
    set("[data-pulse-upd]", esc(tt("pl.upd", { t: fullDate(p.t), src: src })) + (p.demo ? " · ТЕСТ" : ""));
    set("[data-pcoins]", r.basket.map(function (b) {
      var v = p.rows[b];
      if (!v || !isFinite(v.c24)) return "";
      return '<span class="pcoin ' + (v.c24 > 0 ? "is-up" : v.c24 < 0 ? "is-dn" : "") + '"><b>' + esc(b) + "</b>" + esc(fmt(v.c24)) + "</span>";
    }).join(""));
  }

  /* ---------- Билдирмелер: сайт / тиркеме (Web Push) ---------- */
  function ntfRender() {
    var lab = document.querySelector("[data-ntf-label]"), st = document.querySelector("[data-ntf-st]");
    var on = AT.notifyOn();
    if (lab) lab.textContent = AT.t(on ? "ntf.off2" : "ntf.on2");
    if (!st) return;
    if (!on) { st.textContent = AT.t("ntf.st_off"); return; }
    if (!window.ATAlerts) { st.textContent = AT.t("ntf.st_on_page"); return; }
    ATAlerts.pushState().then(function (s) { st.textContent = AT.t(s.on ? "ntf.st_on_push" : "ntf.st_on_page"); });
  }
  var nb = document.querySelector("[data-ntf-toggle]");
  if (nb) nb.addEventListener("click", function () {
    nb.disabled = true;
    var job = AT.notifyOn()
      ? AT.setNotify(false).then(function () { return window.ATAlerts && ATAlerts.unsubscribePush(); })
      : AT.setNotify(true).then(function (ok) { return ok && window.ATAlerts ? ATAlerts.subscribePush() : ok; });
    job.catch(function () {}).then(function () { nb.disabled = false; ntfRender(); AT.track("urgent_ntf", { on: AT.notifyOn() }); });
  });

  /* alerts.js'ти main.js кийин жүктөйт — даяр болгончо күтөбүз */
  var tries = 0;
  (function wait() {
    if (window.ATAlerts) {
      ATAlerts.onUpdate(function (st, live) { renderPulse(st); renderTweets(live); setFresh(live); });
      ntfRender();
      return;
    }
    if (++tries < 60) setTimeout(wait, 200);
    else renderTweets(null);
  })();

  /* ---------- Техникалык анализ (TradingView виджети) ---------- */
  var taSym = AT.store(TA_KEY) || "BINANCE:BTCUSDT";
  function mountTA() {
    var el = document.querySelector("[data-ta-widget]");
    if (!el) return;
    AT.mountTV(el, "technical-analysis", {
      interval: /BINANCE/.test(taSym) ? "1h" : "4h", width: "100%", height: "100%", isTransparent: true, symbol: taSym,
      showIntervalTabs: true, displayMode: "single", locale: "ru", colorTheme: "dark"
    }, { fallbackUrl: "https://ru.tradingview.com/symbols/" + taSym.replace(":", "-") + "/technicals/" });
    document.querySelectorAll("[data-ta-tabs] button").forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-ta") === taSym)); });
  }
  document.querySelectorAll("[data-ta-tabs] button").forEach(function (b) {
    b.addEventListener("click", function () { taSym = b.getAttribute("data-ta"); AT.store(TA_KEY, taSym); mountTA(); });
  });
  var taEl = document.querySelector("[data-ta-widget]");
  if (taEl) AT.lazy(taEl, mountTA);

  /* ---------- TradingView: жандуу лента (орусча) жана календарь ---------- */
  var tv = document.querySelector("[data-tv-news]");
  if (tv) AT.lazy(tv, function () {
    AT.mountTV(tv, "timeline", { displayMode: "regular", feedMode: "all_symbols", colorTheme: "dark", isTransparent: true, locale: "ru", width: "100%", height: "100%" },
      { fallbackUrl: "https://ru.tradingview.com/news/" });
  });
  var ev = document.querySelector("[data-tv-events]");
  if (ev) AT.lazy(ev, function () {
    AT.mountTV(ev, "events", {
      colorTheme: "dark", isTransparent: true, width: "100%", height: "100%", locale: "ru",
      importanceFilter: "0,1", countryFilter: "us,eu,gb,jp,cn,ru"
    }, { fallbackUrl: "https://ru.tradingview.com/economic-calendar/" });
  });

  renderAccounts();
  AT.onLang(function () {
    renderAll();
    renderCal();
    ntfRender();
    if (window.ATAlerts) { renderPulse(ATAlerts.state()); renderTweets(ATAlerts.live()); }
  });
  // «Х мүн мурун» жана «⏰ … кийин» эскирбесин
  setInterval(function () { if (!document.hidden) { ["main", "opinions", "ta"].forEach(renderList); renderKey(); renderCal(); } }, 60000);
})();
