/* AITRADING.KG — символдун өз терезеси (TradingView маалыматы сайттын ичинде).
   Колдонуучу сайттан кетпейт: бегущая строка / мини-график басылганда TradingView
   биздин бетке «#tv?tvwidgetsymbol=FX:EURUSD» дарегин берет (бет кайра жүктөлбөйт),
   main.js аны кармап ушул файлды жүктөйт жана ATChart.open() чакырат.
   Терезе ачылганда тарыхка «#chart» кошулат — телефондогу «Артка» баскычы терезени жабат. */
(function () {
  "use strict";
  if (window.ATChart || !window.AT) return;

  var TXT = {
    ky: {
      chart: "График",
      ta: "Техникалык анализ",
      profile: "Компания",
      ai: "✦ ИИ-анализ",
      close: "Жабуу",
      token: "токен",
      note: "<b>Маалымат TradingView'дан.</b> Бул сигнал эмес. Соода тобокелдиктүү: жоготууга даяр болбогон акчаны салбаңыз. Брокер баскычтары — өнөктөштүк шилтемелер.",
      note_nopartner: "<b>Маалымат TradingView'дан.</b> Бул сигнал эмес. Соода тобокелдиктүү: жоготууга даяр болбогон акчаны салбаңыз."
    },
    ru: {
      chart: "График",
      ta: "Технический анализ",
      profile: "Компания",
      ai: "✦ ИИ-анализ",
      close: "Закрыть",
      token: "токен",
      note: "<b>Данные TradingView.</b> Это не сигнал. Торговля рискованна: не вкладывайте деньги, которые не готовы потерять. Кнопки брокеров — партнёрские ссылки.",
      note_nopartner: "<b>Данные TradingView.</b> Это не сигнал. Торговля рискованна: не вкладывайте деньги, которые не готовы потерять."
    }
  };
  function L() { return AT.lang() === "ru" ? "ru" : "ky"; }
  function tx(k) { return (TXT[L()] && TXT[L()][k]) || TXT.ky[k] || k; }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  /* Стиль — өзүнчө файл, жүктөлгөнчө күтөбүз (терезе «жылаңач» көрүнбөсүн) */
  var cssReady = new Promise(function (res) {
    var l = document.createElement("link");
    l.rel = "stylesheet";
    l.href = "assets/css/chartbox.css";
    l.onload = res;
    l.onerror = res;
    document.head.appendChild(l);
    setTimeout(res, 1500);
  });

  /* BingX / BinoDex'те барбы — bingx.json'дон (күнүгө жаңыланат) */
  var bx = null, bxP = null;
  function getBx() {
    if (!bxP) {
      bxP = fetch("assets/data/bingx.json", { cache: "no-cache" })
        .then(function (r) { return r.json(); })
        .then(function (j) { bx = j; return j; })
        .catch(function () { return null; });
    }
    return bxP;
  }

  function kind(sym) {
    var ex = sym.split(":")[0];
    if (/^(BINANCE|BINGX|BYBIT|OKX|COINBASE|KRAKEN|BITSTAMP|CRYPTO|CRYPTOCAP)$/.test(ex)) return "crypto";
    if (/^(FX|OANDA|FX_IDC|FOREXCOM|SAXO|PEPPERSTONE|FXCM|TVC)$/.test(ex)) return "fx";
    if (/^(NASDAQ|NYSE|AMEX|NYSEARCA|BATS|OTC)$/.test(ex)) return "stock";
    return "other";
  }

  function market(sym) {
    var k = kind(sym), tk = sym.split(":").pop(), r = { kind: k };
    if (!bx) return r;
    if (k === "crypto") {
      var m = /^([A-Z0-9]+?)(USDT|USDC|USD)$/.exec(tk);
      if (m && (bx.spot || []).indexOf(m[1]) >= 0) { r.bingx = m[1] + "/USDT"; r.ai = m[1]; }
    } else if (k === "stock") {
      // Бир акцияга бир нече токен болушу мүмкүн — тизме көлөм боюнча иреттелген, биринчиси эң активдүү
      var s = (bx.stocks || []).filter(function (x) { return x.under === sym; })[0];
      if (s) { r.bingx = s.base; r.token = true; r.ai = s.base; }
    } else if (k === "fx") {
      var f = (bx.forex || []).filter(function (x) { return x.tv === sym || x.code === tk; })[0];
      if (f) { r.binodex = true; r.ai = "FX_" + f.code; }
    }
    return r;
  }

  /* ---------- Терезе ---------- */
  var box = null, cur = null, mounted = {}, lastFocus = null;

  function ensure() {
    if (box) return box;
    box = document.createElement("div");
    box.className = "cbx";
    box.hidden = true;
    box.setAttribute("role", "dialog");
    box.setAttribute("aria-modal", "true");
    box.setAttribute("aria-labelledby", "cbx-title");
    box.innerHTML =
      '<div class="cbx-back" data-cbx-close></div>' +
      '<div class="cbx-win">' +
      '<header class="cbx-head"><div class="cbx-ttl"><h2 id="cbx-title"></h2><div class="cbx-tags"></div></div>' +
      '<button type="button" class="cbx-x" data-cbx-close>×</button></header>' +
      '<div class="cbx-body">' +
      '<div class="cbx-info"></div>' +
      '<div class="cbx-tabs" role="tablist">' +
      '<button type="button" role="tab" data-tab="chart" aria-selected="true"></button>' +
      '<button type="button" role="tab" data-tab="ta" aria-selected="false"></button>' +
      '<button type="button" role="tab" data-tab="profile" aria-selected="false"></button>' +
      "</div>" +
      '<div class="cbx-pane" data-pane="chart" role="tabpanel"></div>' +
      '<div class="cbx-pane" data-pane="ta" role="tabpanel" hidden></div>' +
      '<div class="cbx-pane" data-pane="profile" role="tabpanel" hidden></div>' +
      '<div class="cbx-act"></div>' +
      '<p class="cbx-note"></p>' +
      "</div></div>";
    document.body.appendChild(box);
    box.addEventListener("click", function (e) {
      if (e.target.closest("[data-cbx-close]")) { close(); return; }
      var tb = e.target.closest("[data-tab]");
      if (tb) showTab(tb.getAttribute("data-tab"));
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && box && !box.hidden) close();
    });
    AT.onLang(function () { if (box && !box.hidden && cur) labels(); });
    return box;
  }

  function isOpen() { return !!(box && !box.hidden); }

  function labels() {
    box.querySelector(".cbx-x").setAttribute("aria-label", tx("close"));
    box.querySelector(".cbx-x").title = tx("close");
    ["chart", "ta", "profile"].forEach(function (k) {
      box.querySelector('[data-tab="' + k + '"]').textContent = tx(k);
    });
    actions();
  }

  function actions() {
    var m = market(cur.sym), html = "";
    var tags = "";
    if (m.bingx) tags += '<span class="badge badge-blue">BingX ✓ ' + esc(m.bingx) + (m.token ? " · " + esc(tx("token")) : "") + "</span>";
    box.querySelector(".cbx-tags").innerHTML = tags;
    if (m.ai) html += '<a class="btn btn-ghost btn-sm" href="forecast.html?s=' + encodeURIComponent(m.ai) + '">' + esc(tx("ai")) + " →</a>";
    if (m.bingx) html += '<a class="btn btn-blue btn-sm" data-ref="bingx" href="#">' + esc(AT.t("cta.reg_bingx")) + "</a>";
    else if (m.binodex) html += '<a class="btn btn-mint btn-sm" data-ref="binodex" href="#">' + esc(AT.t("cta.reg_binodex")) + "</a>";
    var act = box.querySelector(".cbx-act");
    act.innerHTML = html;
    act.hidden = !html;
    box.querySelector(".cbx-note").innerHTML = (m.bingx || m.binodex) ? tx("note") : tx("note_nopartner");
    if (m.bingx || m.binodex) AT.applyRefLinks();
  }

  function mountPane(k) {
    if (mounted[k]) return;
    mounted[k] = true;
    var sym = cur.sym, kd = kind(sym), el = box.querySelector('[data-pane="' + k + '"]');
    var narrow = window.innerWidth < 640;
    var page = "https://ru.tradingview.com/symbols/" + sym.replace(":", "-") + "/";
    if (k === "chart") {
      // TradingView «Asia/Bishkek» билбейт (UTC+3 көрсөтөт) — Дакка да UTC+6, жайкы убакыт жок
      AT.mountTV(el, "advanced-chart", {
        autosize: true, symbol: sym, interval: kd === "stock" ? "D" : "60", timezone: "Asia/Dhaka", theme: "dark", style: "1",
        locale: "ru", allow_symbol_change: false, hide_side_toolbar: narrow, hide_volume: kd === "fx",
        withdateranges: !narrow, details: false, calendar: false, support_host: "https://www.tradingview.com"
      }, { fallbackUrl: page });
    } else if (k === "ta") {
      AT.mountTV(el, "technical-analysis", {
        interval: kd === "stock" ? "1D" : "1h", width: "100%", height: "100%", isTransparent: true, symbol: sym,
        showIntervalTabs: true, displayMode: "single", locale: "ru", colorTheme: "dark", largeChartUrl: AT.chartUrl()
      }, { fallbackUrl: page });
    } else if (k === "profile") {
      AT.mountTV(el, "symbol-profile", {
        width: "100%", height: "100%", isTransparent: true, colorTheme: "dark", symbol: sym, locale: "ru"
      }, { fallbackUrl: page });
    }
  }

  function showTab(k) {
    box.querySelectorAll("[data-tab]").forEach(function (b) { b.setAttribute("aria-selected", String(b.getAttribute("data-tab") === k)); });
    box.querySelectorAll("[data-pane]").forEach(function (p) { p.hidden = p.getAttribute("data-pane") !== k; });
    mountPane(k);
    AT.track("chart_tab", { tab: k, symbol: cur.sym });
  }

  function render(sym, title) {
    ensure();
    var same = cur && cur.sym === sym && !box.hidden;
    cur = { sym: sym, title: title || sym.split(":").pop() };
    if (!same) {
      mounted = {};
      box.querySelectorAll("[data-pane]").forEach(function (p) { p.innerHTML = ""; });
    }
    box.querySelector("#cbx-title").innerHTML = esc(cur.title) + "<small>" + esc(sym) + "</small>";
    box.querySelector('[data-tab="profile"]').hidden = kind(sym) !== "stock";
    labels();
    if (box.hidden) lastFocus = document.activeElement;
    box.hidden = false;
    document.documentElement.classList.add("no-scroll");
    if (!same) {
      AT.mountTV(box.querySelector(".cbx-info"), "symbol-info", {
        symbol: sym, width: "100%", locale: "ru", colorTheme: "dark", isTransparent: true
      }, { copyright: false, loader: false });
      showTab("chart");
    }
    getBx().then(function () { if (cur && cur.sym === sym && !box.hidden) actions(); });
    try { box.querySelector(".cbx-x").focus({ preventScroll: true }); } catch (e) { /* */ }
  }

  function hide() {
    if (!box || box.hidden) return;
    box.hidden = true;
    document.documentElement.classList.remove("no-scroll");
    box.querySelectorAll("[data-pane]").forEach(function (p) { p.innerHTML = ""; });
    box.querySelector(".cbx-info").innerHTML = "";
    mounted = {};
    cur = null;
    if (lastFocus && lastFocus.focus && document.contains(lastFocus)) { try { lastFocus.focus({ preventScroll: true }); } catch (e) { /* */ } }
  }

  /* ---------- Тарых: «Артка» терезени жабат ---------- */
  function base() { return location.pathname + location.search; }

  /* from: "tv" — TradingView өзү «#tv?…» жазуусун кошкон, аны «#chart» кылып алмаштырабыз;
           "load" — бет «#tv?…» менен ачылды (мисалы, URL өзгөргөндөн кийин) — тазалап, жаңы жазуу кошобуз;
           башка — кодтон чакырылды. */
  function open(sym, o) {
    o = o || {};
    if (!/^[A-Z0-9_.!]+:[A-Z0-9_.!\-]+$/i.test(sym || "")) return;
    sym = sym.toUpperCase();
    var st = { cbx: 1, sym: sym, title: o.title || "" };
    try {
      if (o.from === "tv") history.replaceState(st, "", base() + "#chart");
      else if (o.from === "load") { history.replaceState(null, "", base()); history.pushState(st, "", base() + "#chart"); }
      else if (isOpen() && history.state && history.state.cbx) history.replaceState(st, "", base() + "#chart");
      else history.pushState(st, "", base() + "#chart");
    } catch (e) { /* */ }
    AT.track("chart_open", { symbol: sym, from: o.from || "code" });
    cssReady.then(function () { render(sym, o.title); });
  }

  function close() {
    if (history.state && history.state.cbx) { history.back(); setTimeout(hide, 400); }   // popstate жабат; камдык убакыт менен
    else hide();
  }

  /* Бет «#chart» менен кайра жүктөлсө: тарыхтагы символ менен ачабыз, болбосо тазалайбыз */
  function restore() {
    var st = history.state;
    if (st && st.cbx && st.sym) cssReady.then(function () { render(st.sym, st.title); });
    else { try { history.replaceState(null, "", base()); } catch (e) { /* */ } }
  }

  window.addEventListener("popstate", function () {
    var st = history.state;
    if (location.hash === "#chart" && st && st.cbx && st.sym) { cssReady.then(function () { render(st.sym, st.title); }); return; }
    hide();
  });

  window.ATChart = { open: open, close: close, restore: restore, isOpen: isOpen };
})();
