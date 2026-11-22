/* Рынок анализатору: жуп тандоо, график, техникалык анализ, рынок көрүнүшү, календарь, сессиялар. */
(function () {
  "use strict";
  if (!window.AT) return;

  var DEFAULT_SYMBOL = "OANDA:XAUUSD";
  var SYMBOL_KEY = "aitrading-symbol";
  var BISHKEK = "Asia/Bishkek";
  var current = null;

  function store(key, val) {
    try {
      if (val === undefined) return localStorage.getItem(key);
      localStorage.setItem(key, val);
    } catch (e) { /* жеке режим */ }
    return null;
  }

  function buttons() { return Array.prototype.slice.call(document.querySelectorAll(".pair[data-symbol]")); }

  function labelFor(symbol) {
    var b = buttons().filter(function (x) { return x.getAttribute("data-symbol") === symbol; })[0];
    return b ? b.textContent.trim() : symbol.split(":").pop();
  }

  function tvSymbolUrl(symbol) {
    return "https://ru.tradingview.com/symbols/" + symbol.replace(":", "-") + "/";
  }

  /* ---------- График жана техникалык анализ ---------- */
  function renderChart(symbol) {
    var el = document.querySelector("[data-tv-chart]");
    if (!el) return;
    var narrow = window.innerWidth < 640;
    AT.mountTV(el, "advanced-chart", {
      autosize: true,
      symbol: symbol,
      interval: "15",
      timezone: BISHKEK,
      theme: "dark",
      style: "1",
      locale: "ru",
      backgroundColor: "rgba(15, 23, 37, 1)",
      gridColor: "rgba(255, 255, 255, 0.04)",
      allow_symbol_change: false,
      hide_side_toolbar: narrow,
      hide_volume: true,
      withdateranges: !narrow,
      calendar: false,
      studies: ["STD;RSI"],
      support_host: "https://www.tradingview.com"
    }, { fallbackUrl: tvSymbolUrl(symbol) });
  }

  function renderTA(symbol) {
    var el = document.querySelector("[data-tv-ta]");
    if (!el) return;
    AT.mountTV(el, "technical-analysis", {
      interval: "15m",
      width: "100%",
      height: "100%",
      isTransparent: true,
      symbol: symbol,
      showIntervalTabs: true,
      displayMode: "single",
      locale: "ru",
      colorTheme: "dark"
    }, { fallbackUrl: tvSymbolUrl(symbol) });
  }

  function select(symbol, opts) {
    opts = opts || {};
    if (!symbol || symbol === current) return;
    current = symbol;
    buttons().forEach(function (b) {
      b.setAttribute("aria-pressed", String(b.getAttribute("data-symbol") === symbol));
    });
    var lab = document.querySelector("[data-sym-label]");
    if (lab) lab.textContent = labelFor(symbol);
    renderChart(symbol);
    renderTA(symbol);
    store(SYMBOL_KEY, symbol);
    if (!opts.keepUrl) {
      var url = new URL(location.href);
      url.searchParams.delete("tvwidgetsymbol");
      url.searchParams.set("symbol", symbol);
      history.replaceState(null, "", url.pathname + url.search + url.hash);
    }
  }

  function initialSymbol() {
    var q = new URLSearchParams(location.search);
    var s = q.get("symbol") || q.get("tvwidgetsymbol");
    if (s && /^[A-Z0-9_]+:[A-Z0-9._!]+$/i.test(s)) return s.toUpperCase();
    return store(SYMBOL_KEY) || DEFAULT_SYMBOL;
  }

  /* ---------- Рынок көрүнүшү ---------- */
  function renderOverview() {
    var el = document.querySelector("[data-tv-overview]");
    if (!el) return;
    var selfUrl = new URL("analyzer.html", location.href).href;
    AT.mountTV(el, "market-overview", {
      colorTheme: "dark",
      dateRange: "1D",
      showChart: true,
      locale: "ru",
      width: "100%",
      height: "100%",
      largeChartUrl: selfUrl,
      isTransparent: true,
      showSymbolLogo: true,
      showFloatingTooltip: false,
      plotLineColorGrowing: "rgba(92, 232, 170, 1)",
      plotLineColorFalling: "rgba(255, 99, 99, 1)",
      gridLineColor: "rgba(255, 255, 255, 0.04)",
      scaleFontColor: "rgba(154, 166, 184, 1)",
      belowLineFillColorGrowing: "rgba(92, 232, 170, 0.12)",
      belowLineFillColorFalling: "rgba(255, 99, 99, 0.12)",
      belowLineFillColorGrowingBottom: "rgba(92, 232, 170, 0)",
      belowLineFillColorFallingBottom: "rgba(255, 99, 99, 0)",
      symbolActiveColor: "rgba(255, 204, 21, 0.12)",
      tabs: [
        {
          title: AT.t("tab.fx"),
          symbols: [
            { s: "FX:EURUSD", d: "EUR/USD" },
            { s: "FX:GBPUSD", d: "GBP/USD" },
            { s: "FX:USDJPY", d: "USD/JPY" },
            { s: "FX:AUDUSD", d: "AUD/USD" },
            { s: "FX:USDCHF", d: "USD/CHF" },
            { s: "FX:USDCAD", d: "USD/CAD" }
          ]
        },
        {
          title: AT.t("tab.metals"),
          symbols: [
            { s: "OANDA:XAUUSD", d: "XAU/USD" },
            { s: "OANDA:XAGUSD", d: "XAG/USD" }
          ]
        },
        {
          title: AT.t("tab.crypto"),
          symbols: [
            { s: "BINANCE:BTCUSDT", d: "BTC/USDT" },
            { s: "BINANCE:ETHUSDT", d: "ETH/USDT" },
            { s: "BINANCE:SOLUSDT", d: "SOL/USDT" },
            { s: "BINANCE:XRPUSDT", d: "XRP/USDT" }
          ]
        },
        {
          title: AT.t("tab.stocks"),
          symbols: [
            { s: "NASDAQ:AAPL", d: "Apple" },
            { s: "NASDAQ:TSLA", d: "Tesla" },
            { s: "NASDAQ:NVDA", d: "NVIDIA" },
            { s: "NASDAQ:MSFT", d: "Microsoft" },
            { s: "NASDAQ:AMZN", d: "Amazon" }
          ]
        }
      ]
    }, { fallbackUrl: "https://ru.tradingview.com/markets/" });
  }

  /* ---------- Экономикалык календарь ---------- */
  function renderCalendar() {
    var el = document.querySelector("[data-tv-calendar]");
    if (!el) return;
    AT.mountTV(el, "events", {
      colorTheme: "dark",
      isTransparent: true,
      width: "100%",
      height: "100%",
      locale: "ru",
      importanceFilter: "0,1",
      countryFilter: "us,eu,gb,jp,cn,ru"
    }, { fallbackUrl: "https://ru.tradingview.com/economic-calendar/" });
  }

  /* ---------- Соода сессиялары (Бишкек убактысы) ---------- */
  var SESSIONS = [
    { name: "Сидней", tz: "Australia/Sydney", open: 7 * 60, close: 16 * 60 },
    { name: "Токио", tz: "Asia/Tokyo", open: 9 * 60, close: 18 * 60 },
    { name: "Лондон", tz: "Europe/London", open: 8 * 60, close: 17 * 60 },
    { name: "Нью-Йорк", tz: "America/New_York", open: 8 * 60, close: 17 * 60 }
  ];
  var WD = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 };

  function zoned(date, tz) {
    var parts = {};
    new Intl.DateTimeFormat("en-US", {
      timeZone: tz, hourCycle: "h23", weekday: "short",
      year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit"
    }).formatToParts(date).forEach(function (p) { parts[p.type] = p.value; });
    var h = Number(parts.hour) % 24;
    var mi = Number(parts.minute);
    return { wd: WD[parts.weekday], min: h * 60 + mi, y: +parts.year, mo: +parts.month, d: +parts.day, h: h, mi: mi };
  }

  function offsetMin(date, tz) {
    var z = zoned(date, tz);
    var base = Math.floor(date.getTime() / 60000) * 60000;
    return Math.round((Date.UTC(z.y, z.mo - 1, z.d, z.h, z.mi) - base) / 60000);
  }

  function hhmm(m) {
    m = ((m % 1440) + 1440) % 1440;
    return String(Math.floor(m / 60)).padStart(2, "0") + ":" + String(m % 60).padStart(2, "0");
  }

  function dur(m) {
    var h = Math.floor(m / 60);
    var mm = m % 60;
    return (h ? h + " " + AT.t("js.h") + " " : "") + mm + " " + AT.t("js.m");
  }

  function renderSessions() {
    var box = document.querySelector("[data-sessions]");
    if (!box) return;
    var now = new Date();
    var bk;
    try { bk = offsetMin(now, BISHKEK); } catch (e) { bk = 360; }
    var clock = document.querySelector("[data-bishkek-clock]");
    try { if (clock) clock.textContent = hhmm(zoned(now, BISHKEK).min); } catch (e) { /* */ }

    box.innerHTML = "";
    SESSIONS.forEach(function (s) {
      var z, off;
      try { z = zoned(now, s.tz); off = offsetMin(now, s.tz); } catch (e) { return; }
      var weekday = z.wd >= 1 && z.wd <= 5;
      var open = weekday && z.min >= s.open && z.min < s.close;
      var wait;
      if (open) {
        wait = s.close - z.min;
      } else if (weekday && z.min < s.open) {
        wait = s.open - z.min;
      } else {
        var k = 1;
        while (k <= 7 && !((z.wd + k) % 7 >= 1 && (z.wd + k) % 7 <= 5)) k++;
        wait = (1440 - z.min) + (k - 1) * 1440 + s.open;
      }
      var from = hhmm(s.open - off + bk);
      var to = hhmm(s.close - off + bk);

      var row = document.createElement("div");
      row.className = "sess";
      var name = document.createElement("b");
      name.textContent = s.name;
      var state = document.createElement("span");
      state.className = "state " + (open ? "open" : "closed");
      state.textContent = open ? AT.t("js.open") : AT.t("js.closed");
      var time = document.createElement("span");
      time.className = "time";
      time.textContent = from + "–" + to;
      var left = document.createElement("span");
      left.className = "wait";
      left.textContent = (open ? AT.t("js.closes_in") : AT.t("js.opens_in")) + ": " + dur(wait);
      row.appendChild(name);
      row.appendChild(state);
      row.appendChild(time);
      row.appendChild(left);
      box.appendChild(row);
    });
  }

  /* ---------- Старт ---------- */
  buttons().forEach(function (b) {
    b.setAttribute("aria-pressed", "false");
    b.addEventListener("click", function () { select(b.getAttribute("data-symbol")); });
  });
  select(initialSymbol(), { keepUrl: true });

  renderSessions();
  setInterval(renderSessions, 30000);

  var overviewEl = document.querySelector("[data-tv-overview]");
  var calendarEl = document.querySelector("[data-tv-calendar]");
  var overviewMounted = false;
  if (overviewEl) AT.lazy(overviewEl, function () { overviewMounted = true; renderOverview(); });
  if (calendarEl) AT.lazy(calendarEl, renderCalendar);

  AT.onLang(function () {
    renderSessions();
    if (overviewMounted) renderOverview();   // таб аттары тилге жараша
  });
})();
