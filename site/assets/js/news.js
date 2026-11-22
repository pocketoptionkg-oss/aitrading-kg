/* Жаңылыктар: TradingView «Top Stories» лентасы + экономикалык календарь. */
(function () {
  "use strict";
  if (!window.AT) return;
  var KEY = "aitrading-news-feed";
  var feed = "all";
  try { feed = localStorage.getItem(KEY) || "all"; } catch (e) { /* */ }

  function renderFeed() {
    var el = document.querySelector("[data-tv-news]");
    if (!el) return;
    var cfg = { displayMode: "regular", feedMode: "all_symbols", colorTheme: "dark", isTransparent: true, locale: "ru", width: "100%", height: "100%" };
    if (feed !== "all") { cfg.feedMode = "market"; cfg.market = feed; }
    AT.mountTV(el, "timeline", cfg, { fallbackUrl: "https://ru.tradingview.com/news/" });
    document.querySelectorAll("[data-news-tabs] button").forEach(function (b) {
      b.setAttribute("aria-pressed", String(b.getAttribute("data-feed") === feed));
    });
  }

  document.querySelectorAll("[data-news-tabs] button").forEach(function (b) {
    b.addEventListener("click", function () {
      feed = b.getAttribute("data-feed");
      try { localStorage.setItem(KEY, feed); } catch (e) { /* */ }
      renderFeed();
    });
  });
  renderFeed();

  var ev = document.querySelector("[data-tv-events]");
  if (ev) {
    AT.lazy(ev, function () {
      AT.mountTV(ev, "events", {
        colorTheme: "dark", isTransparent: true, width: "100%", height: "100%", locale: "ru",
        importanceFilter: "0,1", countryFilter: "us,eu,gb,jp,cn,ru"
      }, { fallbackUrl: "https://ru.tradingview.com/economic-calendar/" });
    });
  }
})();
