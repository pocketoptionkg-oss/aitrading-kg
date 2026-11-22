/* «Куралдар» бети:
   1) Коркуу жана ач көздүк индекси — alternative.me (ачык API, CORS бар), күнүнө 1 жолу жаңырат.
   2) Ликвиддүүлүк картасы — Binance заказдар китеби (api/v3/depth, limit 5000), ар 15 секундда.
      Активдер — BingX'те да бар болгондор гана (assets/data/bingx.json → binance).
   3) Рыноктун жылуулук картасы — TradingView виджети. */
(function () {
  "use strict";
  if (!window.AT) return;
  var T = AT.t;
  function fmt(t, v) { return String(t).replace(/\{(\w+)\}/g, function (_, k) { return v && k in v ? v[k] : ""; }); }
  function getJSON(u, ms) {
    var ctl = "AbortController" in window ? new AbortController() : null;
    var tm = ctl && setTimeout(function () { ctl.abort(); }, ms || 8000);
    return fetch(u, ctl ? { signal: ctl.signal } : {}).then(function (r) {
      if (tm) clearTimeout(tm);
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    });
  }
  function usd(v) {
    var a = Math.abs(v);
    return "$" + (a >= 1e9 ? (v / 1e9).toFixed(2) + "B" : a >= 1e6 ? (v / 1e6).toFixed(a >= 1e7 ? 1 : 2) + "M" : a >= 1e3 ? Math.round(v / 1e3) + "K" : Math.round(v));
  }
  /* Браузерлерде кыргызча ай аттары көбүнчө жок — өзүбүз жазабыз: «22-ноябрь» */
  var KY_M = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"];
  function dayMonth(d) { return AT.lang() === "ru" ? d.toLocaleDateString("ru-RU", { day: "numeric", month: "long" }) : d.getDate() + "-" + KY_M[d.getMonth()]; }
  function price(p) {
    var d = p >= 1000 ? 1 : p >= 100 ? 2 : p >= 1 ? 3 : p >= 0.01 ? 5 : 7;
    return p.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
  }

  /* ================= 1. Коркуу жана ач көздүк ================= */
  var ZCOL = ["#ff5c5c", "#ff9a3d", "#c9d2df", "#9be15d", "#5ce8aa"];
  var ZMAP = { "extreme fear": 0, "fear": 1, "neutral": 2, "greed": 3, "extreme greed": 4 };
  function zoneOf(d) {
    var z = ZMAP[String(d.value_classification || "").toLowerCase()];
    if (z !== undefined) return z;
    var v = +d.value;
    return v < 25 ? 0 : v < 45 ? 1 : v <= 55 ? 2 : v <= 75 ? 3 : 4;
  }
  function pt(v, r) {
    var a = Math.PI * (1 - v / 100);
    return [110 + r * Math.cos(a), 112 - r * Math.sin(a)];
  }
  function arc(v1, v2, r) {
    var a = pt(v1, r), b = pt(v2, r);
    return "M" + a[0].toFixed(1) + " " + a[1].toFixed(1) + " A" + r + " " + r + " 0 0 1 " + b[0].toFixed(1) + " " + b[1].toFixed(1);
  }
  var fngData = null;
  function renderFng() {
    var box = document.querySelector("[data-fng]");
    if (!box || !fngData) return;
    var d = fngData, now = d[0], v = +now.value, z = zoneOf(now);
    var segs = [[0, 24], [25, 44], [45, 55], [56, 75], [76, 100]];
    var tip = pt(v, 74), sv = '<g fill="none" stroke-width="16">';
    segs.forEach(function (s, i) { sv += '<path d="' + arc(s[0] + (i ? 0.8 : 0), s[1] - (i < 4 ? 0.8 : 0), 90) + '" stroke="' + ZCOL[i] + '" stroke-opacity="' + (i === z ? 1 : 0.35) + '"/>'; });
    sv += "</g>" +
      '<line x1="110" y1="112" x2="' + tip[0].toFixed(1) + '" y2="' + tip[1].toFixed(1) + '" stroke="#fff" stroke-width="4" stroke-linecap="round"/>' +
      '<circle cx="110" cy="112" r="7" fill="#fff"/>' +
      '<text x="14" y="126" fill="#6d7a8f" font-size="11" font-family="Inter,sans-serif">0</text><text x="196" y="126" fill="#6d7a8f" font-size="11" font-family="Inter,sans-serif">100</text>';
    box.querySelector("[data-fng-svg]").innerHTML = sv;
    var num = box.querySelector("[data-fng-num]");
    num.textContent = v;
    num.style.color = ZCOL[z];
    box.querySelector("[data-fng-cls]").textContent = T("tl.z" + z);
    box.setAttribute("data-zone", z);
    // Мурунку маанилер
    var hist = [[1, "tl.yday"], [7, "tl.week"], [30, "tl.month"]].filter(function (h) { return d[h[0]]; }).map(function (h) {
      var x = d[h[0]], zz = zoneOf(x);
      return '<div class="fng-h"><small>' + T(h[1]) + '</small><b style="color:' + ZCOL[zz] + '">' + x.value + "</b><span>" + T("tl.z" + zz) + "</span></div>";
    }).join("");
    box.querySelector("[data-fng-hist]").innerHTML = hist;
    // 30 күндүк сызык
    var pts = d.slice(0, 31).reverse(), n = pts.length;
    var xy = pts.map(function (p, i) { return [(i / Math.max(1, n - 1)) * 300, 66 - (+p.value / 100) * 62]; });
    var line = xy.map(function (q, i) { return (i ? "L" : "M") + q[0].toFixed(1) + " " + q[1].toFixed(1); }).join(" ");
    box.querySelector("[data-fng-spark]").innerHTML =
      '<line x1="0" x2="300" y1="35" y2="35" stroke="rgba(255,255,255,.12)" stroke-dasharray="4 4"/>' +
      '<path d="' + line + " L300 70 L0 70 Z" + '" fill="' + ZCOL[z] + '" fill-opacity=".12"/>' +
      '<path d="' + line + '" fill="none" stroke="' + ZCOL[z] + '" stroke-width="2.2" vector-effect="non-scaling-stroke"/>';
    var upd = document.querySelector("[data-fng-upd]");
    if (upd) {
      var dt = new Date(+now.timestamp * 1000);
      var next = +now.time_until_update > 0 ? " · " + fmt(T("tl.next"), { h: Math.max(1, Math.round(+now.time_until_update / 3600)) }) : "";
      upd.textContent = fmt(T("tl.upd"), { d: dayMonth(dt) }) + next;
    }
  }
  function initFng() {
    if (!document.querySelector("[data-fng]")) return;
    getJSON("https://api.alternative.me/fng/?limit=31", 9000).then(function (j) {
      if (!j || !j.data || !j.data.length) throw new Error("empty");
      fngData = j.data;
      renderFng();
    }).catch(function () {
      var c = document.querySelector("[data-fng-cls]");
      if (c) c.textContent = T("tl.err");
    });
    AT.onLang(renderFng);
  }

  /* ================= 2. Ликвиддүүлүк картасы ================= */
  var SYMS = ["BTC", "ETH", "SOL", "XRP", "BNB", "DOGE", "TON", "ADA", "LINK", "AVAX", "SUI"];
  var ROWS = 20, EVERY = 15;
  var L = { sym: "BTC", rng: 2, book: null, timer: null, left: EVERY, busy: false };

  function loadBook() {
    if (L.busy) return;
    L.busy = true;
    var sym = L.sym;
    getJSON("https://api.binance.com/api/v3/depth?symbol=" + sym + "USDT&limit=5000", 9000).then(function (b) {
      if (sym !== L.sym) return;
      L.book = { bids: b.bids.map(function (r) { return [+r[0], +r[1]]; }), asks: b.asks.map(function (r) { return [+r[0], +r[1]]; }), t: Date.now() };
      renderLiq();
    }).catch(function () {
      if (!L.book) document.querySelector("[data-liq-map]").innerHTML = '<p class="liq-wait">' + T("tl.err") + "</p>";
    }).then(function () { L.busy = false; L.left = EVERY; });
  }

  function renderLiq() {
    var B = L.book;
    if (!B || !B.bids.length || !B.asks.length) return;
    var bb = B.bids[0][0], ba = B.asks[0][0], mid = (bb + ba) / 2;
    var span = mid * L.rng / 100, step = span / ROWS;
    var low = B.bids[B.bids.length - 1][0], high = B.asks[B.asks.length - 1][0];   // китептин чеги
    var asks = [], bids = [], i;
    for (i = 0; i < ROWS; i++) { asks.push({ lo: mid + i * step, hi: mid + (i + 1) * step, v: 0, nd: mid + (i + 1) * step > high }); bids.push({ lo: mid - (i + 1) * step, hi: mid - i * step, v: 0, nd: mid - (i + 1) * step < low }); }
    B.asks.forEach(function (r) { var k = Math.floor((r[0] - mid) / step); if (k >= 0 && k < ROWS) asks[k].v += r[0] * r[1]; });
    B.bids.forEach(function (r) { var k = Math.floor((mid - r[0]) / step); if (k >= 0 && k < ROWS) bids[k].v += r[0] * r[1]; });
    var all = asks.concat(bids), max = Math.max.apply(null, all.map(function (x) { return x.v; })) || 1;
    var sumB = bids.reduce(function (a, x) { return a + x.v; }, 0), sumA = asks.reduce(function (a, x) { return a + x.v; }, 0);
    var walls = all.map(function (x, k) { return { x: x, side: k < ROWS ? "s" : "b" }; }).sort(function (a, b) { return b.x.v - a.x.v; }).slice(0, 5);
    var wallSet = walls.map(function (w) { return w.x; });
    var nd = false;
    function row(x, side) {
      if (x.nd) nd = true;
      var w = Math.max(0.5, x.v / max * 100), p = (x.lo + x.hi) / 2, big = wallSet.indexOf(x) >= 0;
      return '<div class="lr ' + side + (big ? " wall" : "") + (x.nd ? " nd" : "") + '"><span class="lp">' + price(p) + '</span><span class="lb"><i style="width:' + w.toFixed(1) + '%"></i></span><span class="lv">' + (x.v ? usd(x.v) : x.nd ? "·" : "") + "</span></div>";
    }
    var html = asks.slice().reverse().map(function (x) { return row(x, "ask"); }).join("") +
      '<div class="lr mid"><span class="lp">' + price(mid) + '</span><span class="lb"><em>' + T("tl.price") + "</em></span><span class=\"lv\"></span></div>" +
      bids.map(function (x) { return row(x, "bid"); }).join("");
    if (nd) html += '<p class="liq-nd">' + T("tl.nodata") + "</p>";
    document.querySelector("[data-liq-map]").innerHTML = html;
    document.querySelector("[data-liq-price]").textContent = "$" + price(mid);
    var tot = sumB + sumA || 1, pb = sumB / tot * 100;
    document.querySelector("[data-imb-buy]").style.width = pb.toFixed(1) + "%";
    document.querySelector("[data-imb-sell]").style.width = (100 - pb).toFixed(1) + "%";
    document.querySelector("[data-imb-buy-t]").textContent = "▲ " + T("tl.buyers") + " " + Math.round(pb) + "% · " + usd(sumB);
    document.querySelector("[data-imb-sell-t]").textContent = "▼ " + T("tl.sellers") + " " + Math.round(100 - pb) + "% · " + usd(sumA);
    document.querySelector("[data-liq-walls]").innerHTML = walls.filter(function (w) { return w.x.v > 0; }).map(function (w) {
      var p = (w.x.lo + w.x.hi) / 2, dist = (p - mid) / mid * 100;
      return '<li class="' + (w.side === "b" ? "up" : "down") + '"><b>' + usd(w.x.v) + "</b><span>" + T(w.side === "b" ? "tl.wall_b" : "tl.wall_s") + " · $" + price(p) + "</span><small>" + (dist > 0 ? "+" : "") + dist.toFixed(2) + "%</small></li>";
    }).join("");
  }

  function initLiq() {
    var map = document.querySelector("[data-liq-map]");
    if (!map) return;
    var symsBox = document.querySelector("[data-liq-syms]");
    function drawSyms(list) {
      symsBox.innerHTML = list.slice(0, 8).map(function (s) { return '<button type="button" data-sym="' + s + '" aria-pressed="' + (s === L.sym) + '">' + s + "</button>"; }).join("");
    }
    drawSyms(SYMS);
    fetch("assets/data/bingx.json").then(function (r) { return r.json(); }).then(function (bx) {
      var ok = {};
      (bx.binance || []).forEach(function (b) { ok[b] = 1; });
      var list = SYMS.filter(function (s) { return ok[s]; });
      if (list.length) { if (!ok[L.sym]) L.sym = list[0]; drawSyms(list); }
    }).catch(function () { /* тизме жүктөлбөсө — демейки тизме */ });
    symsBox.addEventListener("click", function (e) {
      var b = e.target.closest("[data-sym]");
      if (!b || b.getAttribute("data-sym") === L.sym) return;
      L.sym = b.getAttribute("data-sym");
      L.book = null;
      symsBox.querySelectorAll("[data-sym]").forEach(function (x) { x.setAttribute("aria-pressed", String(x === b)); });
      map.innerHTML = '<p class="liq-wait">' + T("tl.loading") + "</p>";
      AT.track("liq_symbol", { s: L.sym });
      loadBook();
    });
    document.querySelectorAll("[data-rng]").forEach(function (b) {
      b.addEventListener("click", function () {
        L.rng = +b.getAttribute("data-rng");
        document.querySelectorAll("[data-rng]").forEach(function (x) { x.setAttribute("aria-pressed", String(x === b)); });
        renderLiq();
      });
    });
    var cd = document.querySelector("[data-liq-cd]");
    AT.lazy(map, function () {
      loadBook();
      L.timer = setInterval(function () {
        if (document.hidden) return;              // фондо — Binance'ке бекер суроо жибербейбиз
        L.left -= 1;
        if (cd) cd.textContent = Math.max(0, L.left);
        if (L.left <= 0) loadBook();
      }, 1000);
    });
    AT.onLang(renderLiq);
  }

  /* ================= 3. Жылуулук картасы ================= */
  function initHeatmap() {
    var el = document.querySelector("[data-heatmap]");
    if (!el) return;
    AT.lazy(el, function () {
      AT.mountTV(el, "crypto-coins-heatmap", {
        dataSource: "Crypto", blockSize: "market_cap_calc", blockColor: "change", locale: "ru", symbolUrl: "",
        colorTheme: "dark", hasTopBar: false, isDataSetEnabled: false, isZoomEnabled: true, hasSymbolTooltip: true,
        isMonoSize: false, width: "100%", height: "100%"
      }, { fallbackUrl: "https://ru.tradingview.com/heatmap/crypto/" });
    });
  }

  function init() { initFng(); initLiq(); initHeatmap(); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
