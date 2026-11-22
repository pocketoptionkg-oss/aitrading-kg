/* ИИ-анализ бети: «ИИ-аналитик» / «TradingView Pro» табдары. Pro ошол эле активди BingX'тин TradingView графигинде көрсөтөт. */
(function () {
  "use strict";
  if (!window.AT) return;
  var base = "BTC", proOpen = false, bx = null;
  var aiEl = document.querySelector("[data-ai-analyst]");
  if (aiEl) base = (aiEl.getAttribute("data-symbol") || "BTC").toUpperCase();
  fetch("assets/data/bingx.json", { cache: "no-cache" }).then(function (r) { return r.json(); }).then(function (j) { bx = j; }).catch(function () {});

  function tvSymbol(b) {
    var fx = bx && (bx.forex || []).filter(function (f) { return "FX_" + f.code === b; })[0];
    if (fx) return fx.tv;
    var s = bx && bx.stocks.filter(function (x) { return x.base === b; })[0];
    if (s && s.listed && Date.now() - s.listed < 10 * 864e5 && s.under) return s.under;   // жаңы токен — TradingView'до али жок
    return "BINGX:" + b + "USDT";
  }
  function mountPro() {
    var sym = tvSymbol(base);
    var fx = bx && (bx.forex || []).filter(function (f) { return "FX_" + f.code === base; })[0];
    document.querySelector("[data-pro-label]").textContent = fx ? fx.name : base + "/USDT";
    AT.mountTV(document.querySelector("[data-pro-chart]"), "advanced-chart", {
      autosize: true, symbol: sym, interval: "60", timezone: "Asia/Bishkek", theme: "dark", style: "1", locale: "ru",
      allow_symbol_change: false, hide_side_toolbar: window.innerWidth < 640, hide_volume: true, support_host: "https://www.tradingview.com"
    }, { fallbackUrl: "https://ru.tradingview.com/symbols/" + sym.replace(":", "-") + "/" });
    AT.mountTV(document.querySelector("[data-pro-ta]"), "technical-analysis", {
      interval: "1h", width: "100%", height: "100%", isTransparent: true, symbol: sym, showIntervalTabs: true, displayMode: "single", locale: "ru", colorTheme: "dark"
    });
  }
  document.querySelectorAll("[data-tab]").forEach(function (b) {
    b.addEventListener("click", function () {
      var tab = b.getAttribute("data-tab");
      document.querySelectorAll("[data-tab]").forEach(function (x) { x.setAttribute("aria-pressed", String(x === b)); });
      document.querySelectorAll("[data-panel]").forEach(function (p) { p.hidden = p.getAttribute("data-panel") !== tab; });
      proOpen = tab === "pro";
      if (proOpen) mountPro();
      AT.track("ai_tab", { tab: tab });
    });
  });
  document.addEventListener("aia:symbol", function (e) {
    base = e.detail.base;
    if (proOpen) mountPro();
  });
})();
