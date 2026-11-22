/* Башкы бет: анализатордун мини-виджети (алтын). Басканда ушул эле бетте өз терезебиз ачылат (chartbox.js). */
(function () {
  "use strict";
  var el = document.querySelector("[data-tv-mini]");
  if (!el || !window.AT) return;
  var analyzerUrl = AT.chartUrl ? AT.chartUrl() : new URL("analyzer.html", location.href).href;
  AT.lazy(el, function () {
    AT.mountTV(el, "mini-symbol-overview", {
      symbol: "OANDA:XAUUSD",
      width: "100%",
      height: "100%",
      locale: "ru",
      dateRange: "1D",
      colorTheme: "dark",
      isTransparent: true,
      autosize: true,
      largeChartUrl: analyzerUrl
    }, { fallbackUrl: "https://ru.tradingview.com/symbols/XAUUSD/" });
  });
})();
