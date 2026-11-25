/* ИИ-анализатордун «мээси»: маалымат, индикаторлор, деңгээлдер, ML-модель.
   Маалымат:
   - Binance ачык API (крипто, жандуу) — BingX'те да бар жуптар гана сунушталат;
   - assets/data/bingx_klines.json — BingX акция токендери жана «өсүп жаткандар» (1 саат, ар 4 саатта жаңыланат). */
(function () {
  "use strict";

  var BINANCE = ["https://api.binance.com/api/v3/klines", "https://data-api.binance.vision/api/v3/klines"];
  var snapPromise = null;
  var bxPromise = null;

  function getJSON(url, ms) {
    var ctrl = "AbortController" in window ? new AbortController() : null;
    var t = ctrl ? setTimeout(function () { ctrl.abort(); }, ms || 8000) : null;
    return fetch(url, { cache: "no-store", signal: ctrl ? ctrl.signal : undefined }).then(function (r) {
      clearTimeout(t);
      if (!r.ok) throw new Error("http " + r.status);
      return r.json();
    }, function (e) { clearTimeout(t); throw e; });
  }

  function snapshot() { return bingx(); }   // эски API менен шайкештик үчүн
  function bingx() {
    if (!bxPromise) bxPromise = fetch("assets/data/bingx.json", { cache: "no-cache" }).then(function (r) { return r.json(); }).catch(function () { return { spot: [], stocks: [], growing: [] }; });
    return bxPromise;
  }

  /* ---------- Шамдар ---------- */
  /* Маалымат булагы: FX_* → Yahoo (BinoDex бөлүмү), Binance'те бар → жандуу Binance, калганы → BingX шамдары (k/<BASE>.json) */
  function source(bx, base) {
    if (base.indexOf("FX_") === 0) return "fx";
    if ((bx.binance || []).indexOf(base) >= 0) return "binance";
    if ((bx.kfiles || []).indexOf(base) >= 0) return "bingx";
    return null;
  }
  function file(name, src, updated) {
    return fetch("assets/data/k/" + name + ".json", { cache: "no-cache" }).then(function (r) {
      if (!r.ok) throw new Error("nodata");
      return r.json();
    }).then(function (rows) {
      return { source: src, tf: "1h", updated: updated, candles: rows.map(function (r) { return { time: r[0], open: r[1], high: r[2], low: r[3], close: r[4], volume: r[5] }; }) };
    });
  }
  function load(base, tf) {
    return bingx().then(function (bx) {
      var src = source(bx, base);
      if (src === "fx" || src === "bingx") return file(base, src, bx.updated);
      if (!src) throw new Error("nodata");
      var i = 0;
      function attempt() {
        if (i >= BINANCE.length) return Promise.reject(new Error("nodata"));
        return getJSON(BINANCE[i++] + "?symbol=" + base + "USDT&interval=" + tf + "&limit=1000").catch(attempt);
      }
      return attempt().then(function (k) {
        if (!Array.isArray(k) || k.length < 120) throw new Error("nodata");
        return {
          source: "binance", tf: tf, updated: null,
          candles: k.map(function (r) { return { time: Math.floor(r[0] / 1000), open: +r[1], high: +r[2], low: +r[3], close: +r[4], volume: +r[7] }; })
        };
      });
    });
  }

  /* ---------- Жандуу валюта котировкалары (BinoDex бөлүмү, кыска мөөнөттүү сигналдар үчүн) ----------
     Булактардын тартиби: 1) BinoDex API (config.js → BINODEX_API, документация келгенде туташтырылат)
                         2) Kraken (ачык API, суюктугу бар жуптар)  3) Binance (EUR/USDT, PAXG=алтын). */
  var KRAKEN = { EURUSD: "EURUSD", GBPUSD: "GBPUSD", USDCAD: "USDCAD", AUDUSD: "AUDUSD", USDCHF: "USDCHF", EURGBP: "EURGBP", EURCHF: "EURCHF" };
  var BN_FX = { EURUSD: "EURUSDT", XAUUSD: "PAXGUSDT" };
  function liveInterval(expMin) {
    if (expMin < 5) return { iv: 1, h: Math.max(1, Math.round(expMin)) };
    if (expMin < 15) return { iv: 5, h: Math.max(1, Math.round(expMin / 5)) };
    if (expMin < 60) return { iv: 15, h: Math.max(1, Math.round(expMin / 15)) };
    return { iv: 60, h: Math.max(1, Math.round(expMin / 60)) };
  }
  function krakenCandles(code, iv) {
    return getJSON("https://api.kraken.com/0/public/OHLC?pair=" + KRAKEN[code] + "&interval=" + iv, 7000).then(function (j) {
      if (j.error && j.error.length) throw new Error(j.error[0]);
      var key = Object.keys(j.result).filter(function (k) { return k !== "last"; })[0];
      var rows = j.result[key] || [];
      var last = rows[rows.length - 1], trades = rows.slice(-30).reduce(function (a, r) { return a + (+r[7] || 0); }, 0);
      if (!last || Date.now() / 1000 - last[0] > iv * 60 * 3 || trades === 0) throw new Error("stale");
      return rows.map(function (r) { return { time: +r[0], open: +r[1], high: +r[2], low: +r[3], close: +r[4], volume: +r[6] }; });
    });
  }
  function binanceCandles(sym, iv) {
    var m = { 1: "1m", 5: "5m", 15: "15m", 60: "1h" }[iv];
    return getJSON(BINANCE[0] + "?symbol=" + sym + "&interval=" + m + "&limit=1000", 7000).then(function (k) {
      return k.map(function (r) { return { time: Math.floor(r[0] / 1000), open: +r[1], high: +r[2], low: +r[3], close: +r[4], volume: +r[7] }; });
    });
  }
  /* Yahoo Finance (сайттын /api/fx аркылуу) — BinoDex'теги бардык жуптар: кросстор, иена жуптары ж.б. */
  function yahooCandles(code, iv) {
    return getJSON("api/fx?code=" + code + "&iv=" + iv, 9000).then(function (j) {
      var c = (j && j.candles) || [];
      var last = c[c.length - 1];
      if (!last || Date.now() / 1000 - last.time > iv * 60 * 4) throw new Error("stale");
      return c;
    });
  }
  function binodexCandles(code, iv) {
    var api = (window.AITRADING_CONFIG || {}).BINODEX_API || "";
    if (!api) return Promise.reject(new Error("no-binodex-api"));
    // BinoDex API документациясы келгенде ушул жер толтурулат (endpoint, жооптун форматы).
    return Promise.reject(new Error("binodex-api-pending"));
  }
  function liveFX(code, expMin) {
    var L = liveInterval(expMin);
    var chain = [
      function () { return binodexCandles(code, L.iv).then(function (c) { return { c: c, provider: "BinoDex" }; }); },
      function () { if (!KRAKEN[code]) throw new Error("no"); return krakenCandles(code, L.iv).then(function (c) { return { c: c, provider: "Kraken" }; }); },
      function () { return yahooCandles(code, L.iv).then(function (c) { return { c: c, provider: "Yahoo" }; }); },
      function () { if (!BN_FX[code]) throw new Error("no"); return binanceCandles(BN_FX[code], L.iv).then(function (c) { return { c: c, provider: code === "XAUUSD" ? "Binance (PAXG)" : "Binance" }; }); }
    ];
    var i = 0;
    function next() {
      if (i >= chain.length) return Promise.reject(new Error("nolive"));
      var f = chain[i++];
      return Promise.resolve().then(f).catch(next);
    }
    return next().then(function (r) {
      if (r.c.length < 120) throw new Error("nolive");
      return { source: "live", provider: r.provider, tf: L.iv + "m", interval: L.iv, horizon: L.h, exp: expMin, updated: null, candles: r.c };
    });
  }
  function hasLive(code) { return /^[A-Z]{6}$/.test(code || ""); }   // Kraken → Yahoo (/api/fx) → Binance
  /* Учурдагы баа (сигналды текшерүү үчүн) */
  function livePrice(code) {
    return liveFX(code, 1).then(function (d) { return d.candles[d.candles.length - 1].close; });
  }

  /* ---------- Индикаторлор ---------- */
  function sma(a, n) {
    var out = new Array(a.length).fill(null), s = 0;
    for (var i = 0; i < a.length; i++) {
      s += a[i];
      if (i >= n) s -= a[i - n];
      if (i >= n - 1) out[i] = s / n;
    }
    return out;
  }
  function ema(a, n) {
    var out = new Array(a.length).fill(null), k = 2 / (n + 1), prev = null;
    for (var i = 0; i < a.length; i++) {
      if (i < n - 1) continue;
      if (prev === null) { var s = 0; for (var j = i - n + 1; j <= i; j++) s += a[j]; prev = s / n; }
      else prev = a[i] * k + prev * (1 - k);
      out[i] = prev;
    }
    return out;
  }
  function rsi(c, n) {
    n = n || 14;
    var out = new Array(c.length).fill(null), g = 0, l = 0;
    for (var i = 1; i <= n && i < c.length; i++) { var d = c[i] - c[i - 1]; if (d > 0) g += d; else l -= d; }
    g /= n; l /= n;
    if (c.length > n) out[n] = l === 0 ? 100 : 100 - 100 / (1 + g / l);
    for (var t = n + 1; t < c.length; t++) {
      var dd = c[t] - c[t - 1];
      g = (g * (n - 1) + Math.max(dd, 0)) / n;
      l = (l * (n - 1) + Math.max(-dd, 0)) / n;
      out[t] = l === 0 ? 100 : 100 - 100 / (1 + g / l);
    }
    return out;
  }
  function macd(c) {
    var e12 = ema(c, 12), e26 = ema(c, 26);
    var line = c.map(function (_, i) { return e12[i] != null && e26[i] != null ? e12[i] - e26[i] : null; });
    var start = line.findIndex(function (v) { return v != null; });
    var sig = new Array(c.length).fill(null);
    if (start >= 0) {
      var s9 = ema(line.slice(start), 9);
      s9.forEach(function (v, i) { sig[start + i] = v; });
    }
    var hist = line.map(function (v, i) { return v != null && sig[i] != null ? v - sig[i] : null; });
    return { line: line, signal: sig, hist: hist };
  }
  function bollinger(c, n, k) {
    n = n || 20; k = k || 2;
    var mid = sma(c, n), up = [], lo = [];
    for (var i = 0; i < c.length; i++) {
      if (mid[i] == null) { up.push(null); lo.push(null); continue; }
      var s = 0;
      for (var j = i - n + 1; j <= i; j++) s += (c[j] - mid[i]) * (c[j] - mid[i]);
      var sd = Math.sqrt(s / n);
      up.push(mid[i] + k * sd); lo.push(mid[i] - k * sd);
    }
    return { mid: mid, up: up, lo: lo };
  }
  function atr(cs, n) {
    n = n || 14;
    var tr = cs.map(function (c, i) {
      if (!i) return c.high - c.low;
      var p = cs[i - 1].close;
      return Math.max(c.high - c.low, Math.abs(c.high - p), Math.abs(c.low - p));
    });
    var a = sma(tr, n);
    return a[a.length - 1] || tr[tr.length - 1];
  }

  /* Колдоо жана каршылык: акыркы 200 шамдагы чокулардын/түптөрдүн топтору */
  function levels(cs) {
    var w = 4, from = Math.max(w, cs.length - 200), last = cs[cs.length - 1].close, tol = atr(cs) * 0.8;
    var piv = [];
    for (var i = from; i < cs.length - w; i++) {
      var hi = true, lo = true;
      for (var j = i - w; j <= i + w; j++) {
        if (cs[j].high > cs[i].high) hi = false;
        if (cs[j].low < cs[i].low) lo = false;
      }
      if (hi) piv.push(cs[i].high);
      if (lo) piv.push(cs[i].low);
    }
    var groups = [];
    piv.sort(function (a, b) { return a - b; }).forEach(function (p) {
      var g = groups[groups.length - 1];
      if (g && p - g.max <= tol) { g.sum += p; g.n++; g.max = p; } else groups.push({ sum: p, n: 1, max: p });
    });
    var lv = groups.map(function (g) { return { price: g.sum / g.n, touches: g.n }; });
    var sup = lv.filter(function (x) { return x.price < last; }).sort(function (a, b) { return b.price - a.price; })[0] || null;
    var res = lv.filter(function (x) { return x.price > last; }).sort(function (a, b) { return a.price - b.price; })[0] || null;
    return { support: sup, resistance: res };
  }

  /* ---------- ML: логистикалык регрессия (70% үйрөнүү / 30% текшерүү) ---------- */
  function features(cs, h) {
    h = h || 1;
    var C = cs.map(function (c) { return c.close; }), V = cs.map(function (c) { return c.volume; });
    var R = C.map(function (c, i) { return i ? Math.log(c / C[i - 1]) : 0; });
    var RS = rsi(C, 14), S20 = sma(C, 20), S50 = sma(C, 50), VA = sma(V, 20);
    function f(t) {
      var m = 0, q = 0;
      for (var i = t - 19; i <= t; i++) m += R[i];
      m /= 20;
      for (var j = t - 19; j <= t; j++) q += (R[j] - m) * (R[j] - m);
      return [R[t], Math.log(C[t] / C[t - 3]), Math.log(C[t] / C[t - 12]), (RS[t] - 50) / 50,
        C[t] / S20[t] - 1, C[t] / S50[t] - 1, Math.sqrt(q / 19), Math.log((V[t] + 1e-9) / ((VA[t] || 1) + 1e-9)), (cs[t].high - cs[t].low) / C[t]];
    }
    var X = [], Y = [];
    // Баа өзгөрбөгөн учурлар (экспирацияда «кайтаруу») үйрөнүүгө кирбейт — өйдө же ылдый гана
    for (var t = 50; t < cs.length - h; t++) { if (C[t + h] === C[t]) continue; X.push(f(t)); Y.push(C[t + h] > C[t] ? 1 : 0); }
    return { X: X, Y: Y, last: f(cs.length - 1) };
  }
  function scaler(X) {
    var d = X[0].length, mu = new Array(d).fill(0), sd = new Array(d).fill(0);
    X.forEach(function (x) { for (var j = 0; j < d; j++) mu[j] += x[j]; });
    for (var j = 0; j < d; j++) mu[j] /= X.length;
    X.forEach(function (x) { for (var k = 0; k < d; k++) sd[k] += (x[k] - mu[k]) * (x[k] - mu[k]); });
    for (var q = 0; q < d; q++) sd[q] = Math.sqrt(sd[q] / X.length) || 1;
    return function (x) { return x.map(function (v, i) { return (v - mu[i]) / sd[i]; }); };
  }
  function sig(z) { return 1 / (1 + Math.exp(-z)); }
  function train(X, Y) {
    var d = X[0].length, w = new Array(d).fill(0), b = 0, m = X.length;
    for (var ep = 0; ep < 400; ep++) {
      var gw = new Array(d).fill(0), gb = 0;
      for (var i = 0; i < m; i++) {
        var z = b;
        for (var j = 0; j < d; j++) z += w[j] * X[i][j];
        var e = sig(z) - Y[i];
        gb += e;
        for (var k = 0; k < d; k++) gw[k] += e * X[i][k];
      }
      b -= 0.1 * gb / m;
      for (var q = 0; q < d; q++) w[q] -= 0.1 * (gw[q] / m + 0.02 * w[q]);
    }
    return { w: w, b: b };
  }
  function pred(m, x) { var z = m.b; for (var j = 0; j < x.length; j++) z += m.w[j] * x[j]; return sig(z); }
  function model(cs, h) {
    var F = features(cs, h);
    if (F.X.length < 120) return null;
    var split = Math.floor(F.X.length * 0.7);
    var s1 = scaler(F.X.slice(0, split));
    var m1 = train(F.X.slice(0, split).map(s1), F.Y.slice(0, split));
    var teY = F.Y.slice(split), hit = 0;
    F.X.slice(split).forEach(function (x, i) { if ((pred(m1, s1(x)) > 0.5 ? 1 : 0) === teY[i]) hit++; });
    var up = teY.reduce(function (a, b) { return a + b; }, 0) / teY.length;
    var s2 = scaler(F.X);
    var m2 = train(F.X.map(s2), F.Y);
    return { p: pred(m2, s2(F.last)), acc: hit / teY.length, base: Math.max(up, 1 - up), n: F.X.length, nTest: teY.length };
  }

  /* ---------- Толук анализ ---------- */
  function analyze(cs, opts) {
    opts = opts || {};
    var C = cs.map(function (c) { return c.close; }), V = cs.map(function (c) { return c.volume; });
    var n = C.length - 1, last = C[n];
    var ma20 = sma(C, 20), ma50 = sma(C, 50);
    var R = rsi(C, 14), M = macd(C), B = bollinger(C, 20, 2), VA = sma(V, 20);
    var lv = levels(cs);
    var bbPos = B.up[n] !== B.lo[n] ? (last - B.lo[n]) / (B.up[n] - B.lo[n]) : 0.5;
    var volRatio = VA[n - 1] ? V[n - 1] / VA[n - 1] : null;   // акыркы жабылган шам; форексте көлөм жок
    var res = {
      last: last,
      series: { ma20: ma20, ma50: ma50, rsi: R, macd: M, bb: B },
      levels: lv,
      ind: {
        trend: { v: ma20[n] - ma50[n], dir: ma20[n] > ma50[n] && last > ma20[n] ? 1 : ma20[n] < ma50[n] && last < ma20[n] ? -1 : 0, ma20: ma20[n], ma50: ma50[n] },
        rsi: { v: R[n], dir: R[n] < 30 ? 1 : R[n] > 70 ? -1 : 0, zone: R[n] < 30 ? "low" : R[n] > 70 ? "high" : R[n] >= 50 ? "midup" : "middn" },
        macd: { v: M.hist[n], dir: M.hist[n] > 0 ? 1 : M.hist[n] < 0 ? -1 : 0, rising: M.hist[n] > (M.hist[n - 1] || 0) },
        bb: { v: bbPos, dir: bbPos < 0.15 ? 1 : bbPos > 0.85 ? -1 : 0 },
        vol: { v: volRatio, dir: 0 },
        levels: { sup: lv.support, res: lv.resistance, dir: 0 }
      },
      ml: model(cs, opts.horizon || 1)
    };
    var dirs = ["trend", "rsi", "macd", "bb"].map(function (k) { return res.ind[k].dir; });
    if (res.ml) dirs.push(res.ml.p >= 0.55 ? 1 : res.ml.p <= 0.45 ? -1 : 0);
    res.tally = {
      up: dirs.filter(function (d) { return d > 0; }).length,
      down: dirs.filter(function (d) { return d < 0; }).length,
      flat: dirs.filter(function (d) { return d === 0; }).length
    };
    return res;
  }

  window.AIENG = { load: load, analyze: analyze, sma: sma, bingx: bingx, snapshot: snapshot, source: source, liveFX: liveFX, livePrice: livePrice, hasLive: hasLive };
})();
