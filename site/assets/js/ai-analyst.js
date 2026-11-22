/* ИИ-аналитик: ИИ-паук графикте жөрмөлөп, «жиптер» менен чекиттерди белгилейт, индикаторлорду коёт,
   агент-карточкаларды толтурат жана сигналдын ыктымалдыктарын берет.
   График — TradingView Lightweight Charts (Apache-2.0). Эсептөөлөр — ai-engine.js. Паук — ai-spider.js. Үн — ai-voice.js.
   Колдонуу: <div data-ai-analyst data-mode="hero|full" data-symbol="BTC" data-tf="1h"></div> */
(function () {
  "use strict";
  if (!window.AT || !window.AIENG || !window.LightweightCharts || !window.AISpider) return;
  var LWC = window.LightweightCharts;
  var T = function (k) { return AT.t(k); };
  var POP = ["BTC", "ETH", "SOL", "XRP", "BNB", "DOGE", "TON", "ADA", "AVAX", "LINK", "SUI", "NEAR", "TAO", "FET", "PEPE", "PAXG"];
  var TFS = [["15m", "aia.tf15m"], ["1h", "aia.tf1h"], ["4h", "aia.tf4h"], ["1d", "aia.tf1d"]];
  var AGENTS = [["trend", "aia.c_trend", "yellow"], ["rsi", "RSI", "pink"], ["macd", "MACD", "blue"], ["bb", "aia.c_bb", "pink"],
    ["levels", "aia.c_levels", "mint"], ["vol", "aia.c_vol", "blue"], ["ml", "aia.c_ml", "yellow"], ["signal", "aia.c_signal", "mint"]];

  function fmt(t, v) { return String(t).replace(/\{(\w+)\}/g, function (_, k) { return v && k in v ? v[k] : ""; }); }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function prec(p) { return p < 0.0001 ? 10 : p < 0.01 ? 7 : p < 1 ? 5 : p < 100 ? 3 : 2; }
  var FX = false;   // учурдагы актив валюта жубубу (BinoDex бөлүмү)
  function fxPrec(p) { return p < 20 ? 5 : 3; }
  function money(p) { if (p == null) return "—"; if (FX) return p.toFixed(fxPrec(p)); return "$" + (p >= 1000 ? p.toLocaleString("en-US", { maximumFractionDigits: 2 }) : p.toFixed(prec(p))); }
  function short(p) { if (p == null) return "—"; if (FX) return p.toFixed(fxPrec(p)); return p >= 1000 ? Math.round(p).toLocaleString("en-US") : p.toFixed(Math.min(prec(p), 6)); }
  function pct(x) { return Math.round(x * 100) + "%"; }
  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  function sfx(n) { if (window.AIVOICE && AIVOICE.sfx) AIVOICE.sfx(n); }

  function Analyst(root) {
    this.root = root;
    this.mode = root.getAttribute("data-mode") || "full";
    this.base = (root.getAttribute("data-symbol") || "BTC").toUpperCase();
    this.mkt = this.base.indexOf("FX_") === 0 ? "binodex" : "bingx";
    this.tf = root.getAttribute("data-tf") || "1h";
    this.speed = this.mode === "hero" ? 0.62 : 0.75;
    this.baseSpeed = this.speed;
    this.exp = 1;          // сигналдын экспирациясы (мүнөт), BinoDex бөлүмү
    this.auto = false;
    this.sigTimer = null;
    this.run_id = 0;
    this.res = null;
    this.on = {};
    this.dropped = false;
    this.scan_id = 0;      // «⭐ Азыр эң мыкты» сканери
    this.best = null;
    this.build();
  }

  Analyst.prototype.build = function () {
    var self = this, r = this.root;
    r.classList.add("aia", "aia-" + this.mode);
    r.innerHTML =
      '<div class="aia-bar">' +
      '<div class="aia-mkt" role="group"><button type="button" data-mkt="bingx">BingX</button><button type="button" data-mkt="binodex">BinoDex</button></div>' +
      '<div class="aia-symwrap"><button type="button" class="aia-sym" aria-haspopup="listbox"><span class="aia-sym-name"></span><span class="aia-src"></span><svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="m6 9 6 6 6-6" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg></button>' +
      '<div class="aia-pop" hidden><input class="aia-search" type="search" autocomplete="off"><div class="aia-list" role="listbox"></div></div></div>' +
      '<div class="aia-tf">' + TFS.map(function (t) { return '<button type="button" data-tf="' + t[0] + '" data-k="' + t[1] + '"></button>'; }).join("") + "</div>" +
      '<div class="aia-exp" hidden><span class="aia-exp-l" data-k="aia.exp"></span>' +
      [1, 3, 5, 15].map(function (m) { return '<button type="button" data-exp="' + m + '">' + m + '<small data-k="aia.mn"></small></button>'; }).join("") +
      '<label class="aia-expn"><input type="number" min="1" max="240" step="1" value="2" aria-label="N"><small data-k="aia.mn"></small></label>' +
      '<button type="button" class="aia-auto" aria-pressed="false"><span data-k="aia.auto"></span></button></div>' +
      '<div class="aia-ctl"><button type="button" class="btn btn-ghost btn-sm aia-sound" aria-pressed="false"><span class="aia-sound-ico">🔇</span><span class="aia-sound-txt" data-k="aia.sound"></span></button>' +
      '<button type="button" class="btn btn-mint btn-sm aia-run"><span class="aia-run-ico">▶</span><span data-k="aia.run"></span></button>' +
      '<button type="button" class="btn btn-ghost btn-sm aia-fast" data-k-title="aia.fast" title="">⏩</button></div>' +
      "</div>" +
      '<div class="aia-best" data-st="idle"><div class="best-head"><span class="best-ttl"><i aria-hidden="true">⭐</i><b class="best-h"></b></span><span class="best-meta"></span>' +
      '<button type="button" class="best-bell" aria-pressed="false"><span class="bell-ico">🔕</span><span class="bell-txt" data-k="aia.notify"></span></button></div>' +
      '<div class="best-list"></div></div>' +
      '<div class="aia-agents">' + AGENTS.map(function (a) {
        return '<button type="button" class="aia-ag" data-ind="' + a[0] + '" data-col="' + a[2] + '" data-st="idle">' +
          '<span class="ag-top"><i class="ag-dot"></i><span class="ag-name" data-k="' + a[1] + '"></span></span>' +
          '<span class="ag-val">—</span><span class="ag-bar"><i></i></span></button>';
      }).join("") + "</div>" +
      '<div class="aia-stage"><div class="aia-chart"></div><div class="aia-sub" hidden></div><div class="aia-scan" hidden></div><div class="aia-msg" hidden></div></div>' +
      '<div class="aia-result" hidden></div>' +
      '<div class="aia-say" hidden></div>';
    this.el = {
      sym: r.querySelector(".aia-sym"), symName: r.querySelector(".aia-sym-name"), src: r.querySelector(".aia-src"),
      pop: r.querySelector(".aia-pop"), search: r.querySelector(".aia-search"), list: r.querySelector(".aia-list"),
      run: r.querySelector(".aia-run"), fast: r.querySelector(".aia-fast"), sound: r.querySelector(".aia-sound"),
      chart: r.querySelector(".aia-chart"), sub: r.querySelector(".aia-sub"), stage: r.querySelector(".aia-stage"),
      scan: r.querySelector(".aia-scan"), msg: r.querySelector(".aia-msg"), result: r.querySelector(".aia-result"),
      say: r.querySelector(".aia-say"),
      best: r.querySelector(".aia-best"), bestList: r.querySelector(".best-list"), bestMeta: r.querySelector(".best-meta"),
      bestH: r.querySelector(".best-h"), bell: r.querySelector(".best-bell")
    };
    this.texts();
    this.updateSound();
    this.updateBell();

    /* Паук */
    this.spider = new AISpider(r, { scale: this.mode === "hero" ? 0.82 : 1 });
    this.spider.onFrame = function (x, y) { self.placeSay(x, y); };

    /* График */
    var opts = {
      autoSize: true,
      layout: { background: { type: "solid", color: "transparent" }, textColor: "#9aa6b8", fontFamily: "Inter, Segoe UI, sans-serif", attributionLogo: true },
      grid: { vertLines: { color: "rgba(255,255,255,0.035)" }, horzLines: { color: "rgba(255,255,255,0.035)" } },
      rightPriceScale: { borderColor: "rgba(255,255,255,0.08)" },
      timeScale: { borderColor: "rgba(255,255,255,0.08)", timeVisible: true, secondsVisible: false, rightOffset: 4 },
      crosshair: { mode: 0 },
      localization: { locale: "ru-RU" }
    };
    this.chart = LWC.createChart(this.el.chart, opts);
    this.candle = this.chart.addCandlestickSeries({ upColor: "#5ce8aa", downColor: "#ff6b6b", wickUpColor: "#5ce8aa", wickDownColor: "#ff6b6b", borderVisible: false });
    this.subChart = LWC.createChart(this.el.sub, Object.assign({}, opts, { layout: Object.assign({}, opts.layout, { attributionLogo: false }), timeScale: Object.assign({}, opts.timeScale, { visible: false }) }));
    this.chart.timeScale().subscribeVisibleLogicalRangeChange(function (rg) { if (rg && !self.el.sub.hidden) self.subChart.timeScale().setVisibleLogicalRange(rg); });
    this.extra = {};
    this.subSeries = [];

    /* Окуялар */
    this.el.sym.addEventListener("click", function () { self.togglePop(); });
    this.el.search.addEventListener("input", function () { self.fillList(); });
    this.el.search.addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        var first = self.el.list.querySelector("[data-base]");
        var v = self.el.search.value.trim().toUpperCase().replace(/[/\-]?USDT$/, "");
        self.pick(first ? first.getAttribute("data-base") : v);
      }
      if (e.key === "Escape") self.togglePop(false);
    });
    document.addEventListener("click", function (e) { if (!self.el.pop.hidden && !e.target.closest(".aia-symwrap")) self.togglePop(false); });
    r.querySelectorAll(".aia-tf button").forEach(function (b) {
      b.addEventListener("click", function () { if (b.disabled) return; self.tf = b.getAttribute("data-tf"); self.start(); });
    });
    r.querySelectorAll(".aia-exp [data-exp]").forEach(function (b) {
      b.addEventListener("click", function () { self.exp = +b.getAttribute("data-exp"); AT.track("signal_exp", { exp: self.exp }); self.start(); });
    });
    var expIn = r.querySelector(".aia-expn input");
    expIn.addEventListener("change", function () {
      var v = Math.max(1, Math.min(240, Math.round(+expIn.value || 1)));
      expIn.value = v; self.exp = v; AT.track("signal_exp", { exp: v }); self.start();
    });
    r.querySelector(".aia-auto").addEventListener("click", function () {
      self.auto = !self.auto;
      this.setAttribute("aria-pressed", String(self.auto));
    });
    r.querySelectorAll(".aia-mkt button").forEach(function (b) {
      b.addEventListener("click", function () {
        var m = b.getAttribute("data-mkt");
        if (m === self.mkt) return;
        self.mkt = m;
        AT.track("ai_market", { market: m });
        self.pick(m === "binodex" ? "FX_EURUSD" : "BTC");
      });
    });
    this.el.run.addEventListener("click", function () { self.start(); });
    this.el.fast.addEventListener("click", function () {
      self.speed = self.speed === self.baseSpeed ? 0.22 : self.baseSpeed;
      self.el.fast.classList.toggle("on", self.speed !== self.baseSpeed);
    });
    this.el.sound.addEventListener("click", function () {
      if (!window.AIVOICE) return;
      var on = !AIVOICE.isOn();
      AIVOICE.setEnabled(on);
      self.updateSound();
      AT.track("bot_voice", { on: on });
      if (on && !self.busy) self.speakNow("hello").then(function () { if (!self.busy) self.start(); });
    });
    r.querySelectorAll(".aia-ag").forEach(function (c) {
      c.addEventListener("click", function () {
        var k = c.getAttribute("data-ind");
        if (!self.res || self.busy || k === "signal") return;
        if (self.on[k]) self.hide(k); else self.show(k);
      });
    });
    /* ⭐ тизмесинен же карточкадагы сунуштан активди ачуу */
    r.addEventListener("click", function (e) {
      var b = e.target.closest && e.target.closest("[data-pick]");
      if (!b) return;
      AT.track("best_pick", { asset: b.getAttribute("data-pick"), market: self.mkt });
      self.pick(b.getAttribute("data-pick"));
    });
    this.el.bell.addEventListener("click", function () {
      var on = !AT.notifyOn();
      self.el.bell.disabled = true;
      AT.setNotify(on).then(function () {
        self.el.bell.disabled = false;
        self.updateBell();
        AT.track("notify_toggle", { on: AT.notifyOn() });
        if (!AT.notifyOn()) return;
        AT.toast(T("ntf.enabled"));
        self._lastNtf = null;
        if (self.best && self.best.top.length) self.notifyBest(true);
      });
    });
    document.addEventListener("visibilitychange", function () {
      if (document.hidden || !self.scanKey) return;
      if (!self.best || Date.now() - self.best.t > self.scanEvery()) self.scanSoon(400);
    });
    AT.onLang(function () { self.texts(); self.refreshSymLabel(); self.updateBell(); self.renderBest(); if (self.res && !self.busy) { if (self.data && self.data.source === "live") self.renderSignal(true); else self.renderResult(); self.fillAgents(); } });

    AIENG.bingx().then(function (bx) { self.bx = bx; return AIENG.snapshot(); }).then(function (snap) {
      self.snap = snap;
      self.refreshSymLabel();
      self.fillList();
      self.renderBest();
    });
  };

  Analyst.prototype.texts = function () {
    var r = this.root;
    r.querySelectorAll("[data-k]").forEach(function (el) { el.textContent = T(el.getAttribute("data-k")); });
    r.querySelectorAll("[data-k-title]").forEach(function (el) { el.title = T(el.getAttribute("data-k-title")); });
    this.el.search.placeholder = T("aia.search");
  };

  /* ---------- Үн ---------- */
  Analyst.prototype.updateSound = function () {
    var on = !!(window.AIVOICE && AIVOICE.isOn());
    this.el.sound.setAttribute("aria-pressed", String(on));
    this.el.sound.classList.toggle("on", on);
    this.el.sound.querySelector(".aia-sound-ico").textContent = on ? "🔊" : "🔇";
    this.el.sound.title = T(on ? "aia.sound_off" : "aia.sound_on");
    if (!window.AIVOICE || !AIVOICE.canSpeak()) this.el.sound.hidden = true;
  };
  Analyst.prototype.speakNow = function (key) {
    if (!window.AIVOICE || !AIVOICE.isOn() || this.speed < 0.3) return Promise.resolve();
    var sp = this.spider;
    sp.talking = true;
    var long = key === "hello" || key.indexOf("done") === 0;
    return AIVOICE.speak(key, long ? 6000 : 2400).then(function () { sp.talking = false; });
  };
  Analyst.prototype.speak = function (key) { this._vp = this.speakNow(key); return this._vp; };

  /* ---------- 🔔 Билдирмелер ---------- */
  Analyst.prototype.updateBell = function () {
    var on = AT.notifyOn(), b = this.el.bell;
    b.setAttribute("aria-pressed", String(on));
    b.classList.toggle("on", on);
    b.querySelector(".bell-ico").textContent = on ? "🔔" : "🔕";
    b.title = T(on ? "aia.notify_off" : "aia.notify_on");
  };

  /* ---------- ⭐ Азыр эң мыкты: бардык жуптарды/активдерди тез сканерлөө ---------- */
  function hm(ms) { return new Date(ms).toLocaleTimeString("ru-RU", { timeZone: "Asia/Bishkek", hour: "2-digit", minute: "2-digit" }); }
  var LAST_NTF = "aitrading-ntf-last";

  Analyst.prototype.scanCands = function () {
    var bx = this.bx, self = this, hero = this.mode === "hero";
    if (!bx) return [];
    if (this.mkt === "binodex") {
      return (bx.forex || []).filter(function (f) { return AIENG.hasLive(f.code); }).map(function (f) { return "FX_" + f.code; });
    }
    var pop = POP.filter(function (b) { return self.canUse(b); }).slice(0, hero ? 8 : 16);
    var grow = (bx.growing || []).map(function (g) { return g.base; }).filter(function (b) { return self.canUse(b); }).slice(0, 6);
    var stocks = (bx.stocks || []).filter(function (s) { return self.canUse(s.base); }).slice(0, hero ? 4 : 10).map(function (s) { return s.base; });
    return pop.concat(grow, stocks).filter(function (b, i, a) { return a.indexOf(b) === i; });
  };
  /* Канча убакытта бир жаңыртуу: 1–3 мүн → 60 с, 5–15 мүн → 2 мүн, андан узун → 5 мүн; BingX (1 саат) → 10 мүн */
  Analyst.prototype.scanEvery = function () {
    if (this.mkt !== "binodex") return 600000;
    return this.exp <= 3 ? 60000 : this.exp <= 15 ? 120000 : 300000;
  };
  Analyst.prototype.scanSoon = function (ms) {
    var self = this;
    clearTimeout(this.scanT);
    this.scanT = setTimeout(function () {
      // Барак жашырылган жана билдирме өчүк болсо — тармакты бекер жүктөбөйбүз
      if (document.hidden && !AT.notifyOn()) { self.scanSoon(); return; }
      self.scan();
    }, ms === undefined ? this.scanEvery() : ms);
  };
  Analyst.prototype.fresh = function () {
    var B = this.best;
    return !!B && B.mkt === this.mkt && (this.mkt !== "binodex" || B.exp === this.exp);
  };
  Analyst.prototype.rank = function (all, mkt) {
    // BingX — спот: акча табуу үчүн сатып алуу гана (▲). BinoDex — эки багыт тең (▲ Жогору / ▼ Төмөн).
    var ok = all.filter(function (x) { return mkt === "binodex" ? x.dir !== 0 : x.dir > 0; });
    ok.sort(function (a, b) { return Math.abs(b.p - 0.5) - Math.abs(a.p - 0.5) || b.edge - a.edge; });
    return ok.slice(0, 3);
  };
  function judge(ml) {
    var edge = ml.acc - ml.base;
    return { edge: edge, dir: edge > 0.01 ? (ml.p >= 0.55 ? 1 : ml.p <= 0.45 ? -1 : 0) : 0 };
  }
  Analyst.prototype.scan = function () {
    var self = this, id = ++this.scan_id, mkt = this.mkt, exp = this.exp;
    var list = this.scanCands(), out = [], i = 0;
    clearTimeout(this.scanT);
    if (!list.length) return;
    this.scanning = true;
    this.el.best.setAttribute("data-st", "work");
    this.renderBest();
    function next() {
      if (id !== self.scan_id) return;                 // жаңы скан башталып калды
      if (i >= list.length) return done();
      var b = list[i++], fx = b.indexOf("FX_") === 0;
      var ld = fx ? AIENG.liveFX(b.replace("FX_", ""), exp) : AIENG.load(b, "1h");
      ld.then(function (d) {
        var R = AIENG.analyze(d.candles, { horizon: d.horizon || 1 });
        if (!R.ml) return;
        var j = judge(R.ml);
        out.push({ base: b, name: self.nameOf(b), p: R.ml.p, acc: R.ml.acc, bl: R.ml.base, edge: j.edge, dir: j.dir });
      }).catch(function () { /* бул жуп азыр жеткиликсиз — өткөрүп жиберебиз */ }).then(function () {
        setTimeout(next, fx ? 1000 : 120);               // Kraken: секундасына ~1 суроо
      });
    }
    function done() {
      self.scanning = false;
      self.best = { mkt: mkt, exp: exp, t: Date.now(), n: out.length, all: out, top: self.rank(out, mkt) };
      // Ачык турган активдин жаңы эле чыккан жыйынтыгы — карточка менен ⭐ тизмеси бири-бирине каршы келбесин
      if (!self.busy && self.resT && Date.now() - self.resT < 45000) self.syncBest();
      self.el.best.setAttribute("data-st", "done");
      self.renderBest();
      self.updateBestRow();
      self.notifyBest();
      self.scanSoon();
    }
    next();
  };
  /* Негизги анализ бүткөндө — анын жыйынтыгын сканердин тизмесине кошобуз (сандар бирдей болсун) */
  Analyst.prototype.syncBest = function () {
    var B = this.best, ml = this.res && this.res.ml, self = this;
    if (!ml || !this.fresh()) return;
    var j = judge(ml), row = { base: this.base, name: this.nameOf(this.base), p: ml.p, acc: ml.acc, bl: ml.base, edge: j.edge, dir: j.dir };
    var all = B.all.filter(function (x) { return x.base !== self.base; });
    if (this.scanCands().indexOf(this.base) >= 0) all.push(row);
    B.all = all;
    B.n = all.length;
    B.top = this.rank(all, B.mkt);
    this.renderBest();
  };
  function dirTxt(x) { return x.dir > 0 ? "▲ " + T("aia.sig_up") : "▼ " + T("aia.sig_dn"); }
  function dirP(x) { return pct(x.dir > 0 ? x.p : 1 - x.p); }
  Analyst.prototype.renderBest = function () {
    var B = this.best, el = this.el, self = this, fresh = this.fresh(), fx = this.mkt === "binodex";
    el.bestH.textContent = fx ? fmt(T("aia.best_t_fx"), { m: this.exp }) : T("aia.best_t");
    el.bestMeta.textContent = fresh ? fmt(T("aia.best_meta"), { n: B.n, t: hm(B.t) }) + (this.scanning ? " · ↻" : "") : "";
    if (!fresh) {
      el.bestList.innerHTML = '<p class="best-wait"><i class="best-spin" aria-hidden="true"></i>' + esc(fmt(T("aia.best_scan"), { n: this.scanCands().length || "…" })) + "</p>";
      return;
    }
    if (!B.top.length) {
      el.bestList.innerHTML = '<p class="best-none">' + esc(fmt(T(fx ? "aia.best_none_fx" : "aia.best_none"), { n: B.n })) + "</p>";
      return;
    }
    el.bestList.innerHTML = B.top.map(function (x, k) {
      var cur = x.base === self.base;
      return '<button type="button" class="best-it ' + (k === 0 ? "top " : "") + (x.dir > 0 ? "up" : "down") + (cur ? " cur" : "") + '" data-pick="' + esc(x.base) + '">' +
        '<span class="best-rank">' + (k === 0 ? "★" : k + 1) + "</span>" +
        '<span class="best-name"><b>' + esc(x.name) + "</b>" + (k === 0 ? '<small>' + esc(T(fx ? "aia.best_buy_fx" : "aia.best_buy")) + "</small>" : "") + "</span>" +
        '<span class="best-dir">' + esc(dirTxt(x)) + "</span>" +
        '<span class="best-p">' + dirP(x) + "</span>" +
        '<small class="best-acc">' + esc(fmt(T("aia.best_acc"), { a: pct(x.acc), b: pct(x.bl) })) + "</small>" +
        (cur ? '<small class="best-cur">' + esc(T("aia.best_open")) + "</small>" : '<span class="best-go" aria-hidden="true">→</span>') +
        "</button>";
    }).join("") + '<p class="best-note">' + esc(T("aia.best_note")) + "</p>";
  };
  /* Сигнал/прогноз карточкасынын аталышынын астындагы «⭐ эң мыкты» сабы */
  Analyst.prototype.bestRow = function () {
    var B = this.best, top = this.fresh() && B.top[0];
    if (!this.fresh()) return '<div class="sig-best wait" data-bestrow><i aria-hidden="true">⭐</i><span>' + esc(T("aia.best_scan_s")) + "</span></div>";
    if (!top) return '<div class="sig-best none" data-bestrow><i aria-hidden="true">⭐</i><span>' + esc(T(this.mkt === "binodex" ? "aia.best_none_s_fx" : "aia.best_none_s")) + "</span></div>";
    if (top.base === this.base) return '<div class="sig-best me ' + (top.dir > 0 ? "up" : "down") + '" data-bestrow><i aria-hidden="true">⭐</i><span>' + esc(fmt(T("aia.best_me"), { n: B.n })) + "</span><b>" + esc(dirTxt(top)) + " " + dirP(top) + "</b></div>";
    return '<button type="button" class="sig-best go ' + (top.dir > 0 ? "up" : "down") + '" data-bestrow data-pick="' + esc(top.base) + '"><i aria-hidden="true">⭐</i><span>' + esc(T("aia.best_now")) + "</span><b>" + esc(top.name) + " " + esc(dirTxt(top)) + " " + dirP(top) + '</b><em>' + esc(T("aia.best_go")) + " →</em></button>";
  };
  Analyst.prototype.updateBestRow = function () {
    var row = this.el.result.querySelector("[data-bestrow]");
    if (row) row.outerHTML = this.bestRow();
  };
  Analyst.prototype.notifyBest = function (force) {
    var B = this.best, top = B && B.top[0];
    if (!top || !AT.notifyOn()) return;
    var fx = B.mkt === "binodex", key = top.base + ":" + top.dir + ":" + (fx ? B.exp : "1h"), now = Date.now(), L;
    try { L = JSON.parse(localStorage.getItem(LAST_NTF) || "{}"); } catch (e) { L = {}; }
    if (!force) {
      if (key === L.key && now - L.t < 15 * 60000) return;   // ошол эле сунуш — 15 мүнөттө бир жолу
      if (now - (L.t || 0) < 3 * 60000) return;               // спам болбосун: 3 мүнөттө 1 билдирмеден көп эмес
    }
    try { localStorage.setItem(LAST_NTF, JSON.stringify({ key: key, t: now })); } catch (e) { /* */ }
    AT.notify("⭐ " + top.name + " · " + dirTxt(top) + " · " + dirP(top),
      (fx ? "BinoDex · " + B.exp + " " + T("aia.min") : "BingX · " + T("aia.h_1h")) + " · " + fmt(T("aia.best_acc"), { a: pct(top.acc), b: pct(top.bl) }) + ". " + T("ntf.honest"),
      "forecast.html?s=" + encodeURIComponent(top.base) + (fx ? "&exp=" + B.exp : ""), "aitrading-best");
  };

  /* ---------- Сүйлөм көбүгү (паукка жабышып жүрөт) ---------- */
  Analyst.prototype.say = function (txt) {
    var b = this.el.say;
    b.hidden = !txt;
    b.textContent = txt || "";
    b.classList.remove("pop"); void b.offsetWidth; b.classList.add("pop");
  };
  Analyst.prototype.placeSay = function (x, y) {
    var b = this.el.say;
    if (b.hidden) return;
    var W = this.root.clientWidth, bw = b.offsetWidth, bh = b.offsetHeight;
    var left = x + 22, top = y - bh - 18;
    if (left + bw > W - 8) left = x - bw - 22;
    if (left < 8) left = 8;
    if (top < 6) top = y + 26;
    b.style.transform = "translate(" + Math.round(left) + "px," + Math.round(top) + "px)";
  };

  /* ---------- Агент-карточкалар ---------- */
  Analyst.prototype.agent = function (k, st, val, dir) {
    var c = this.root.querySelector('.aia-ag[data-ind="' + k + '"]');
    if (!c) return;
    c.setAttribute("data-st", st);
    c.classList.remove("up", "down", "flat");
    if (dir !== undefined) c.classList.add(dir > 0 ? "up" : dir < 0 ? "down" : "flat");
    c.querySelector(".ag-val").textContent = st === "work" ? T("aia.ag_work") : st === "idle" ? "—" : (val || "✓");
    if (st === "done") sfx("blip");
  };
  Analyst.prototype.fillAgents = function () {
    var R = this.res, I = R.ind, p = R.ml ? R.ml.p : 0.5, arr = function (d) { return d > 0 ? "▲ " : d < 0 ? "▼ " : "● "; };
    this.agent("trend", "done", arr(I.trend.dir) + T(I.trend.dir > 0 ? "aia.v_up" : I.trend.dir < 0 ? "aia.v_dn" : "aia.v_flat"), I.trend.dir);
    this.agent("rsi", "done", arr(I.rsi.dir) + Math.round(I.rsi.v), I.rsi.dir);
    this.agent("macd", "done", arr(I.macd.dir) + T(I.macd.v >= 0 ? "aia.v_plus" : "aia.v_minus"), I.macd.dir);
    this.agent("bb", "done", arr(I.bb.dir) + Math.round(I.bb.v * 100) + "%", I.bb.dir);
    this.agent("levels", "done", "S " + short(R.levels.support && R.levels.support.price) + " · R " + short(R.levels.resistance && R.levels.resistance.price), 0);
    this.agent("vol", "done", I.vol.v == null ? "—" : (I.vol.v >= 1 ? "+" : "") + Math.round((I.vol.v - 1) * 100) + "%", 0);
    this.agent("ml", "done", R.ml ? pct(p) + " ▲" : "—", p >= 0.55 ? 1 : p <= 0.45 ? -1 : 0);
    this.agent("signal", "done", "▲" + pct(p) + " ▼" + pct(1 - p), p >= 0.55 ? 1 : p <= 0.45 ? -1 : 0);
  };

  /* ---------- Актив тандоо ---------- */
  Analyst.prototype.fxOf = function (b) {
    return this.bx && (this.bx.forex || []).filter(function (f) { return "FX_" + f.code === b; })[0];
  };
  Analyst.prototype.nameOf = function (b) {
    var fx = this.fxOf(b);
    if (fx) return fx.name;
    var s = this.bx && this.bx.stocks.filter(function (x) { return x.base === b; })[0];
    if (s) return s.name;
    if (b === "PAXG") return T("aia.gold");
    return b;
  };
  Analyst.prototype.isSnap = function (b) { return !!this.bx && AIENG.source(this.bx, b) !== "binance"; };
  Analyst.prototype.canUse = function (b) { return !!this.bx && !!AIENG.source(this.bx, b) && (b.indexOf("FX_") !== 0 || !!this.fxOf(b)); };
  Analyst.prototype.refreshSymLabel = function () {
    var n = this.nameOf(this.base), self = this, snap = this.isSnap(this.base), fx = this.base.indexOf("FX_") === 0;
    this.el.symName.textContent = fx ? n : (n !== this.base ? n + " · " : "") + this.base + "/USDT";
    this.el.src.textContent = fx ? "BinoDex" : "BingX";
    this.el.src.classList.toggle("bnx", fx);
    this.mkt = fx ? "binodex" : "bingx";
    this.root.querySelectorAll(".aia-mkt button").forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-mkt") === self.mkt)); });
    this.root.querySelectorAll(".aia-tf button").forEach(function (b) {
      var tf = b.getAttribute("data-tf");
      b.disabled = snap && tf !== "1h";
      b.setAttribute("aria-pressed", String(tf === (snap ? "1h" : self.tf)));
    });
    var live = fx && AIENG.hasLive(this.base.replace("FX_", ""));
    this.root.querySelector(".aia-tf").hidden = live;
    this.root.querySelector(".aia-exp").hidden = !live;
    this.root.querySelectorAll(".aia-exp [data-exp]").forEach(function (b) { b.setAttribute("aria-pressed", String(+b.getAttribute("data-exp") === self.exp)); });
    var ei = this.root.querySelector(".aia-expn");
    ei.classList.toggle("on", [1, 3, 5, 15].indexOf(this.exp) < 0);
    if ([1, 3, 5, 15].indexOf(this.exp) < 0) ei.querySelector("input").value = this.exp;
  };
  Analyst.prototype.togglePop = function (open) {
    var p = this.el.pop;
    p.hidden = open === undefined ? !p.hidden : !open;
    if (!p.hidden) { this.el.search.value = ""; this.fillList(); this.el.search.focus(); }
  };
  Analyst.prototype.fillList = function () {
    if (!this.bx) return;
    var q = this.el.search.value.trim().toUpperCase().replace(/[/\-]/g, ""), self = this, bx = this.bx;
    var stocks = bx.stocks.filter(function (s) { return self.canUse(s.base); }).map(function (s) { return s.base; });
    var stockSet = {}; stocks.forEach(function (b) { stockSet[b] = 1; });
    var groups;
    if (this.mkt === "binodex") {
      var fx = (bx.forex || []).map(function (f) { return "FX_" + f.code; });
      groups = [["aia.g_fx", fx.filter(function (b) { return !/^FX_X(AU|AG)/.test(b); })], ["aia.g_metal", fx.filter(function (b) { return /^FX_X(AU|AG)/.test(b); })]];
    } else {
      var crypto = (bx.binance || []).concat(bx.kfiles || []).filter(function (b) { return !stockSet[b]; });
      crypto = crypto.filter(function (b, i) { return crypto.indexOf(b) === i; }).sort();
      groups = [
        ["aia.g_pop", POP.filter(function (b) { return self.canUse(b); })],
        ["aia.g_stocks", stocks],
        ["aia.g_grow", (bx.growing || []).map(function (g) { return g.base; }).filter(function (b) { return self.canUse(b); })],
        ["aia.g_crypto", crypto]
      ];
    }
    var html = "", hidden = 0;
    groups.forEach(function (g) {
      var items = g[1].filter(function (b) {
        if (!q) return true;
        var n = self.nameOf(b).toUpperCase().replace(/[/\-]/g, "");
        return b.replace("FX_", "").indexOf(q) >= 0 || n.indexOf(q) >= 0;
      });
      if (!items.length) return;
      var lim = q ? 80 : g[0] === "aia.g_crypto" ? 30 : 60;
      if (items.length > lim) { hidden += items.length - lim; items = items.slice(0, lim); }
      html += '<div class="aia-grp">' + esc(T(g[0])) + " · " + g[1].length + "</div>" + items.map(function (b) {
        var n = self.nameOf(b), code = b.replace("FX_", "");
        return '<button type="button" role="option" data-base="' + esc(b) + '"><b>' + esc(b.indexOf("FX_") === 0 ? n : code) + "</b><span>" + esc(b.indexOf("FX_") === 0 ? "BinoDex" : n !== b ? n : "") + "</span></button>";
      }).join("");
    });
    if (hidden) html += '<p class="aia-none">' + esc(fmt(T("aia.more"), { n: hidden })) + "</p>";
    if (!html) html = '<p class="aia-none">' + esc(T("aia.none")) + "</p>";
    this.el.list.innerHTML = html;
    this.el.list.querySelectorAll("[data-base]").forEach(function (b) {
      b.addEventListener("click", function () { self.pick(b.getAttribute("data-base")); });
    });
  };
  Analyst.prototype.pick = function (b) {
    if (!b) return;
    if (this.bx && !this.canUse(b)) { AT.toast(T("aia.none")); return; }
    this.base = b;
    this.togglePop(false);
    if (this.isSnap(b)) this.tf = "1h";
    this.refreshSymLabel();
    this.root.dispatchEvent(new CustomEvent("aia:symbol", { bubbles: true, detail: { base: b } }));
    AT.track("ai_analyze", { asset: b, tf: this.tf });
    this.start();
  };

  /* ---------- Координаттар (компоненттин ичинде) ---------- */
  Analyst.prototype.box = function (el) {
    var a = this.root.getBoundingClientRect(), r = el.getBoundingClientRect();
    return { x: r.left - a.left, y: r.top - a.top, w: r.width, h: r.height };
  };
  Analyst.prototype.pt = function (time, price, series, chart, el) {
    var x = (chart || this.chart).timeScale().timeToCoordinate(time), y = (series || this.candle).priceToCoordinate(price);
    if (x == null || y == null) return null;
    var b = this.box(el || this.el.chart);
    return { x: b.x + x, y: b.y + y };
  };
  Analyst.prototype.goPt = function (p, dx, dy) {
    if (!p) return Promise.resolve();
    return this.spider.moveTo(p.x + (dx || 0), p.y + (dy || 0), 1 / Math.max(0.25, this.speed));
  };

  /* ---------- Индикаторлорду тартуу ---------- */
  Analyst.prototype.line = function (vals, color, width, style) {
    var cs = this.cs, s = this.chart.addLineSeries({ color: color, lineWidth: width || 2, lineStyle: style || 0, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
    s.setData(vals.map(function (v, i) { return v == null ? null : { time: cs[i].time, value: v }; }).filter(Boolean));
    return s;
  };
  Analyst.prototype.showSub = function (kind) {
    var self = this, cs = this.cs, R = this.res.series;
    this.subSeries.forEach(function (s) { self.subChart.removeSeries(s); });
    this.subSeries = [];
    this.el.sub.hidden = false;
    if (kind === "rsi") {
      var s = this.subChart.addLineSeries({ color: "#ff5caa", lineWidth: 2, priceLineVisible: false, lastValueVisible: true });
      s.setData(R.rsi.map(function (v, i) { return v == null ? null : { time: cs[i].time, value: v }; }).filter(Boolean));
      s.createPriceLine({ price: 70, color: "rgba(255,107,107,.6)", lineWidth: 1, lineStyle: 2, axisLabelVisible: false });
      s.createPriceLine({ price: 30, color: "rgba(92,232,170,.6)", lineWidth: 1, lineStyle: 2, axisLabelVisible: false });
      this.subSeries.push(s);
    } else {
      var M = R.macd;
      var h = this.subChart.addHistogramSeries({ priceLineVisible: false, lastValueVisible: false });
      h.setData(M.hist.map(function (v, i) { return v == null ? null : { time: cs[i].time, value: v, color: v >= 0 ? "rgba(92,232,170,.6)" : "rgba(255,107,107,.6)" }; }).filter(Boolean));
      var l1 = this.subChart.addLineSeries({ color: "#6ea0ff", lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
      l1.setData(M.line.map(function (v, i) { return v == null ? null : { time: cs[i].time, value: v }; }).filter(Boolean));
      var l2 = this.subChart.addLineSeries({ color: "#ffcc15", lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
      l2.setData(M.signal.map(function (v, i) { return v == null ? null : { time: cs[i].time, value: v }; }).filter(Boolean));
      this.subSeries.push(h, l1, l2);
    }
    this.subChart.timeScale().setVisibleLogicalRange(this.chart.timeScale().getVisibleLogicalRange());
    this.on.rsi = kind === "rsi"; this.on.macd = kind === "macd";
    this.cardOn("rsi", kind === "rsi"); this.cardOn("macd", kind === "macd");
  };
  Analyst.prototype.cardOn = function (k, v) {
    var c = this.root.querySelector('.aia-ag[data-ind="' + k + '"]');
    if (c) c.classList.toggle("on", !!v);
    this.on[k] = !!v;
  };
  Analyst.prototype.show = function (k) {
    var R = this.res, cs = this.cs;
    if (k === "trend") this.extra.trend = [this.line(R.series.ma20, "#ffcc15", 2), this.line(R.series.ma50, "#6ea0ff", 2)];
    if (k === "bb") this.extra.bb = [this.line(R.series.bb.up, "rgba(255,92,170,.7)", 1, 2), this.line(R.series.bb.lo, "rgba(255,92,170,.7)", 1, 2)];
    if (k === "levels") {
      var L = R.levels, pl = [];
      if (L.support) pl.push(this.candle.createPriceLine({ price: L.support.price, color: "#5ce8aa", lineWidth: 2, lineStyle: 2, axisLabelVisible: true, title: T("aia.sup") }));
      if (L.resistance) pl.push(this.candle.createPriceLine({ price: L.resistance.price, color: "#ff8a3d", lineWidth: 2, lineStyle: 2, axisLabelVisible: true, title: T("aia.res") }));
      this.extra.levels = pl;
    }
    if (k === "vol") {
      var v = this.chart.addHistogramSeries({ priceScaleId: "vol", priceLineVisible: false, lastValueVisible: false });
      this.chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
      v.setData(cs.map(function (c) { return { time: c.time, value: c.volume, color: c.close >= c.open ? "rgba(92,232,170,.35)" : "rgba(255,107,107,.35)" }; }));
      this.extra.vol = [v];
    }
    if (k === "rsi" || k === "macd") return this.showSub(k);
    if (k === "ml") this.mark(true);
    this.cardOn(k, true);
  };
  Analyst.prototype.hide = function (k) {
    var self = this;
    if (k === "rsi" || k === "macd") {
      this.subSeries.forEach(function (s) { self.subChart.removeSeries(s); });
      this.subSeries = [];
      this.el.sub.hidden = true;
      this.cardOn("rsi", false); this.cardOn("macd", false);
      return;
    }
    if (k === "levels") (this.extra.levels || []).forEach(function (p) { self.candle.removePriceLine(p); });
    else (this.extra[k] || []).forEach(function (s) { self.chart.removeSeries(s); });
    if (k === "ml") this.mark(false);
    delete this.extra[k];
    this.cardOn(k, false);
  };
  Analyst.prototype.mark = function (on) {
    var R = this.res, last = this.cs[this.cs.length - 1];
    if (!on || !R.ml) { this.candle.setMarkers([]); return; }
    var up = R.ml.p >= 0.5;
    this.candle.setMarkers([{ time: last.time, position: up ? "belowBar" : "aboveBar", color: up ? "#5ce8aa" : "#ff6b6b", shape: up ? "arrowUp" : "arrowDown", text: "AI " + pct(up ? R.ml.p : 1 - R.ml.p) }]);
  };
  Analyst.prototype.clearAll = function () {
    var self = this;
    Object.keys(this.extra).forEach(function (k) { self.hide(k); });
    this.hide("rsi");
    this.mark(false);
    AGENTS.forEach(function (a) { self.cardOn(a[0], false); self.agent(a[0], "idle"); });
    this.spider.clear();
  };

  /* ---------- Анализдин сценарийи ---------- */
  Analyst.prototype.start = function () {
    var self = this, my = ++this.run_id;
    var alive = function () { return my === self.run_id; };
    this.busy = true;
    this.root.classList.add("busy");
    this.el.result.hidden = true;
    this.el.msg.hidden = true;
    this.refreshSymLabel();
    FX = this.base.indexOf("FX_") === 0;
    var name = this.nameOf(this.base), symTxt = FX ? name : name !== this.base ? name + " (" + this.base + ")" : this.base + "/USDT";
    var tf = this.isSnap(this.base) ? "1h" : this.tf;
    var cb = this.box(this.el.chart);
    var code = this.base.replace("FX_", ""), live = FX && AIENG.hasLive(code);
    clearInterval(this.sigTimer);
    this.speed = this.el.fast.classList.contains("on") ? 0.22 : live ? 0.38 : this.baseSpeed;
    var loader = live ? AIENG.liveFX(code, this.exp).catch(function () { return AIENG.load(self.base, "1h"); }) : AIENG.load(this.base, tf);

    this.el.scan.hidden = false;
    sfx("sweep");
    var arrive = this.dropped ? this.spider.moveTo(cb.x + cb.w * 0.12, cb.y + 50) : this.spider.dropTo(cb.x + cb.w * 0.12, cb.y + 50);
    this.dropped = true;
    this.say(fmt(T("aia.s_load"), { s: symTxt }));
    this.speak("load");

    return Promise.all([loader, arrive]).then(function (all) {
      if (!alive()) return;
      var d = all[0];
      self.data = d;
      self.cs = d.candles;
      self.clearAll();
      var lp = self.cs[self.cs.length - 1].close, p = FX ? fxPrec(lp) : prec(lp);
      self.candle.applyOptions({ priceFormat: { type: "price", precision: p, minMove: Math.pow(10, -p) } });
      self.candle.setData(self.cs);
      var n = self.cs.length;
      self.chart.timeScale().setVisibleLogicalRange({ from: Math.max(0, n - (self.mode === "hero" ? 110 : 160)), to: n + 3 });
      self.res = AIENG.analyze(self.cs, { horizon: d.horizon || 1 });
      self.resT = Date.now();
      return sleep(250);
    }).then(function () {
      if (!alive() || !self.res) return;
      self.el.scan.hidden = true;
      return self.script(alive);
    }).catch(function (e) {
      if (!alive()) return;
      if (e !== "stop") console.error(e);
      self.el.scan.hidden = true;
      self.say(T("aia.err"));
      self.speak("err");
      self.el.msg.hidden = false;
      self.el.msg.textContent = T("aia.err");
    }).then(function () {
      if (!alive()) return;
      self.busy = false;
      self.root.classList.remove("busy");
      // Рынок же экспирация алмашса — «⭐ эң мыктыны» кайра издейбиз
      var key = self.mkt + ":" + (self.mkt === "binodex" ? self.exp : "1h");
      if (self.scanKey !== key) { self.scanKey = key; self.renderBest(); self.scanSoon(600); }
    });
  };

  /* Деңгээлге жакын чокулар/түптөр (жиптер ошолорго тартылат) */
  Analyst.prototype.touches = function (price, isHigh) {
    var cs = this.cs, out = [], tol = price * 0.004;
    for (var i = cs.length - 2; i >= Math.max(0, cs.length - 150) && out.length < 4; i--) {
      var v = isHigh ? cs[i].high : cs[i].low;
      if (Math.abs(v - price) <= tol) { out.push(cs[i]); i -= 6; }
    }
    return out;
  };

  Analyst.prototype.script = function (alive) {
    var self = this, R = this.res, I = R.ind, sp = this.spider, cs = this.cs, n = cs.length, last = cs[n - 1];
    var wait = function (ms) { return sleep(ms * self.speed); };
    var chk = function () { if (!alive()) throw "stop"; };
    var hold = function () { chk(); return Promise.all([wait(700), self._vp]); };
    var thread = function (p, color, label) { if (p) { sp.thread(p.x, p.y, { color: color, label: label, life: 3200 }); sfx("pip"); } };

    var chain = Promise.resolve();
    function step(fn) { chain = chain.then(function () { chk(); self._vp = null; return fn(); }).then(hold); }

    /* 0. Скан: паук свечалардын чокуларын/түптөрүн аралап чыгат */
    step(function () {
      self.say(T("aia.s_scan"));
      var idx = [n - 95, n - 72, n - 50, n - 30, n - 12].filter(function (i) { return i > 0; });
      var c = Promise.resolve();
      idx.forEach(function (i, k) {
        c = c.then(function () {
          chk();
          var hi = k % 2 === 0, v = hi ? cs[i].high : cs[i].low, p = self.pt(cs[i].time, v);
          return self.goPt(p, 0, hi ? -16 : 16).then(function () { thread(p, "white", short(v)); return wait(90); });
        });
      });
      return c;
    });
    /* 1. Тренд */
    step(function () {
      self.agent("trend", "work");
      self.show("trend");
      var p20 = self.pt(last.time, I.trend.ma20), p50 = self.pt(last.time, I.trend.ma50);
      return self.goPt(p20, -70, -22).then(function () {
        thread(p20, "yellow", "MA20"); thread(p50, "blue", "MA50");
        self.say(fmt(T(I.trend.dir > 0 ? "aia.s_trend_up" : I.trend.dir < 0 ? "aia.s_trend_dn" : "aia.s_trend_flat"), { a: money(I.trend.ma20), b: money(I.trend.ma50) }));
        self.speak(I.trend.dir > 0 ? "trend_up" : I.trend.dir < 0 ? "trend_dn" : "trend_flat");
        self.agent("trend", "done", (I.trend.dir > 0 ? "▲ " : I.trend.dir < 0 ? "▼ " : "● ") + T(I.trend.dir > 0 ? "aia.v_up" : I.trend.dir < 0 ? "aia.v_dn" : "aia.v_flat"), I.trend.dir);
      });
    });
    /* 2. RSI */
    step(function () {
      self.agent("rsi", "work");
      self.show("rsi");
      return sleep(60).then(function () {
        var p = self.pt(last.time, I.rsi.v, self.subSeries[0], self.subChart, self.el.sub);
        return self.goPt(p, -60, -10).then(function () {
          thread(p, "pink", "RSI " + Math.round(I.rsi.v));
          self.say(fmt(T("aia.s_rsi_" + I.rsi.zone), { v: Math.round(I.rsi.v) }));
          self.speak(I.rsi.zone === "low" ? "rsi_low" : I.rsi.zone === "high" ? "rsi_high" : "rsi_mid");
          self.agent("rsi", "done", (I.rsi.dir > 0 ? "▲ " : I.rsi.dir < 0 ? "▼ " : "● ") + Math.round(I.rsi.v), I.rsi.dir);
        });
      });
    });
    /* 3. MACD */
    step(function () {
      self.agent("macd", "work");
      self.show("macd");
      return sleep(60).then(function () {
        var p = self.pt(last.time, I.macd.v, self.subSeries[0], self.subChart, self.el.sub);
        return self.goPt(p, -80, -14).then(function () {
          thread(p, "blue", "MACD");
          self.say(T(I.macd.v >= 0 ? (I.macd.rising ? "aia.s_macd_pu" : "aia.s_macd_pd") : (I.macd.rising ? "aia.s_macd_nu" : "aia.s_macd_nd")));
          self.speak(I.macd.v >= 0 && I.macd.rising ? "macd_up" : I.macd.v < 0 && !I.macd.rising ? "macd_dn" : "macd_mix");
          self.agent("macd", "done", (I.macd.dir > 0 ? "▲ " : "▼ ") + T(I.macd.v >= 0 ? "aia.v_plus" : "aia.v_minus"), I.macd.dir);
        });
      });
    });
    /* 4. Боллинджер */
    step(function () {
      self.agent("bb", "work");
      self.show("bb");
      var up = R.series.bb.up[n - 1], lo = R.series.bb.lo[n - 1];
      var pu = self.pt(last.time, up), pl = self.pt(last.time, lo);
      return self.goPt(self.pt(last.time, R.last), -90, 0).then(function () {
        thread(pu, "pink", "BB↑"); thread(pl, "pink", "BB↓");
        self.say(T(I.bb.v < 0.15 ? "aia.s_bb_lo" : I.bb.v > 0.85 ? "aia.s_bb_hi" : "aia.s_bb_mid"));
        self.speak(I.bb.v < 0.15 ? "bb_lo" : I.bb.v > 0.85 ? "bb_hi" : "bb_mid");
        self.agent("bb", "done", (I.bb.dir > 0 ? "▲ " : I.bb.dir < 0 ? "▼ " : "● ") + Math.round(I.bb.v * 100) + "%", I.bb.dir);
      });
    });
    /* 5. Деңгээлдер: паук чокуларды жип менен байлап, сызык тартат */
    step(function () {
      self.agent("levels", "work");
      var L = R.levels, c = Promise.resolve();
      [[L.resistance, true, "yellow"], [L.support, false, "mint"]].forEach(function (lv) {
        if (!lv[0]) return;
        c = c.then(function () {
          chk();
          var pts = self.touches(lv[0].price, lv[1]).map(function (k) { return self.pt(k.time, lv[1] ? k.high : k.low); }).filter(Boolean);
          var go = pts.length ? self.goPt(pts[0], 0, lv[1] ? -18 : 18) : Promise.resolve();
          return go.then(function () {
            var prev = null;
            pts.forEach(function (p) { thread(p, lv[2], ""); if (prev) sp.thread(p.x, p.y, { from: prev, color: lv[2], life: 3200 }); prev = p; });
          });
        });
      });
      return c.then(function () {
        self.show("levels");
        self.say(fmt(T("aia.s_levels"), { s: L.support ? money(L.support.price) : "—", r: L.resistance ? money(L.resistance.price) : "—" }));
        self.speak("levels");
        self.agent("levels", "done", "S " + short(L.support && L.support.price) + " · R " + short(L.resistance && L.resistance.price), 0);
      });
    });
    /* 6. Көлөм */
    step(function () {
      self.agent("vol", "work");
      if (I.vol.v == null) {
        self.say(T("aia.s_vol_na"));
        return wait(250).then(function () { self.agent("vol", "done", "—", 0); });
      }
      self.show("vol");
      var prevBar = cs[n - 2];
      return sleep(60).then(function () {
        var p = self.pt(prevBar.time, prevBar.volume, self.extra.vol[0]);
        return self.goPt(p, -50, -24).then(function () {
          thread(p, "blue", "VOL");
          var d = Math.round((I.vol.v - 1) * 100);
          self.say(fmt(T(d >= 0 ? "aia.s_vol_up" : "aia.s_vol_dn"), { v: Math.abs(d) }));
          self.speak(d >= 0 ? "vol_up" : "vol_dn");
          self.agent("vol", "done", (d >= 0 ? "+" : "") + d + "%", 0);
        });
      });
    });
    /* 7. ИИ-модель: паук акыркы свечага барып, «тор» жаят */
    step(function () {
      self.agent("ml", "work");
      var p = self.pt(last.time, last.close);
      return self.goPt(p, -40, -30).then(function () {
        self.say(fmt(T("aia.s_ml"), { n: R.ml ? R.ml.n : 0 }));
        self.speak("ml");
        sfx("sweep");
        // тор: акыркы 40 свечадан туш келди чекиттерге жиптер
        for (var k = 0; k < 12; k++) {
          var i = n - 2 - Math.floor(Math.random() * 40), c = cs[i], q = self.pt(c.time, Math.random() > 0.5 ? c.high : c.low);
          if (q) sp.thread(q.x, q.y, { color: k % 3 ? "mint" : "yellow", life: 1800 });
        }
        return wait(650).then(function () {
          self.show("ml");
          var pp = R.ml ? R.ml.p : 0.5;
          self.agent("ml", "done", R.ml ? pct(pp) : "—", pp >= 0.55 ? 1 : pp <= 0.45 ? -1 : 0);
        });
      });
    });

    return chain.then(function () {
      chk();
      var pp = R.ml ? R.ml.p : 0.5;
      self.agent("signal", "work");
      return wait(350).then(function () {
        self.agent("signal", "done", "▲" + pct(pp) + " ▼" + pct(1 - pp), pp >= 0.55 ? 1 : pp <= 0.45 ? -1 : 0);
        if (self.data.source === "live") self.renderSignal(); else self.renderResult();
        self.el.result.hidden = false;
        sfx("done");
        self.say(T("aia.s_done"));
        self.speak(pp >= 0.55 ? "done_up" : pp <= 0.45 ? "done_dn" : "done_flat");
        var rb = self.box(self.el.result);
        return sp.moveTo(rb.x + rb.w - 40, rb.y + 26).then(function () { sp.burst(10, 70); });
      });
    });
  };

  /* ---------- Кыска мөөнөттүү сигнал (BinoDex) ---------- */
  var SIG_KEY = "aitrading-signals";
  function sigLoad() { try { return JSON.parse(localStorage.getItem(SIG_KEY) || "[]"); } catch (e) { return []; } }
  function sigSave(a) { try { localStorage.setItem(SIG_KEY, JSON.stringify(a.slice(-60))); } catch (e) { /* */ } }
  function hms(ms) { var d = new Date(ms); return d.toLocaleTimeString("ru-RU", { timeZone: "Asia/Bishkek", hour: "2-digit", minute: "2-digit", second: "2-digit" }); }
  function mmss(ms) { ms = Math.max(0, ms); var m = Math.floor(ms / 60000), s2 = Math.floor(ms % 60000 / 1000); return (m < 10 ? "0" : "") + m + ":" + (s2 < 10 ? "0" : "") + s2; }

  Analyst.prototype.renderSignal = function (redraw) {
    var self = this, R = this.res, ml = R.ml, d = this.data, code = this.base.replace("FX_", "");
    var p = ml ? ml.p : 0.5, edge = ml ? (ml.acc - ml.base) : -1;
    var dir = edge > 0.01 ? (p >= 0.55 ? 1 : p <= 0.45 ? -1 : 0) : 0;
    var last = this.cs[this.cs.length - 1].close;
    if (!redraw) {
      this.sig = { id: Date.now(), code: code, name: this.nameOf(this.base), exp: this.exp, dir: dir, p: p, entry: last, t0: Date.now(), tEnd: Date.now() + this.exp * 60000, res: null, exit: null };
      if (dir !== 0) { var all = sigLoad(); all.push(this.sig); sigSave(all); }
      this.syncBest();
      // Авто-режимде телефон чөнтөктө болсо — жаңы сигнал жөнүндө билдирме
      if (dir !== 0 && document.hidden && AT.notifyOn()) {
        AT.notify((dir > 0 ? "▲ " : "▼ ") + this.sig.name + " · " + this.exp + " " + T("aia.min") + " · " + pct(dir > 0 ? p : 1 - p),
          fmt(T("aia.sig_why"), { a: pct(ml.acc), b: pct(ml.base) }),
          "forecast.html?s=FX_" + code + "&exp=" + this.exp, "aitrading-sig");
      }
    }
    var sg = this.sig;
    var verdict = dir > 0 ? "▲ " + T("aia.sig_up") : dir < 0 ? "▼ " + T("aia.sig_dn") : "● " + T("aia.sig_none");
    var why = dir !== 0 ? fmt(T("aia.sig_why"), { a: pct(ml.acc), b: pct(ml.base) })
      : !ml ? T("aia.no_ml") : edge <= 0.01 ? fmt(T("aia.sig_noedge"), { a: pct(ml.acc), b: pct(ml.base) }) : T("aia.sig_weak");
    var hist = sigLoad().filter(function (x) { return x.res !== null; });
    var mine = hist.filter(function (x) { return x.code === code; });
    var stat = function (a) { var w = a.filter(function (x) { return x.res === 1; }).length, l = a.filter(function (x) { return x.res === 0; }).length; return { w: w, l: l, pc: w + l ? Math.round(w / (w + l) * 100) : null }; };
    var sAll = stat(hist.slice(-50)), sMine = stat(mine.slice(-20));
    var rows = sigLoad().slice(-8).reverse().map(function (x) {
      var r = x.res === 1 ? '<b class="up">✓</b>' : x.res === 0 ? '<b class="down">✗</b>' : x.res === 2 ? "<b>=</b>" : x.res === 3 ? "<b>—</b>" : '<b class="wait">…</b>';
      return "<li>" + r + "<span>" + esc(x.name) + " · " + (x.dir > 0 ? "▲" : "▼") + " · " + x.exp + T("aia.mn") + "</span><small>" + hms(x.t0) + "</small></li>";
    }).join("");
    this.el.result.innerHTML =
      '<div class="sig-head"><span class="badge badge-mint">' + esc(T("aia.sig_title")) + '</span><span class="muted">' + esc(sg.name) + " · " + sg.exp + " " + esc(T("aia.min")) + '</span><span class="sig-prov">' + esc(d.provider || "") + " · " + esc(T("aia.live")) + "</span></div>" +
      this.bestRow() +
      '<div class="sig-main">' +
      '<div class="sig-verdict ' + (dir > 0 ? "up" : dir < 0 ? "down" : "flat") + '">' + esc(verdict) + "</div>" +
      '<div class="sig-timer"><div class="sig-ring"><svg viewBox="0 0 44 44"><circle cx="22" cy="22" r="19" class="bg"/><circle cx="22" cy="22" r="19" class="fg" data-ring/></svg><b data-cd>' + mmss(sg.tEnd - Date.now()) + "</b></div>" +
      '<div><div class="muted" style="font-size:.78rem">' + esc(T("aia.sig_entry")) + '</div><b class="sig-entry">' + money(sg.entry) + '</b><div class="muted" style="font-size:.78rem">' + hms(sg.t0) + " → " + hms(sg.tEnd) + "</div></div></div>" +
      "</div>" +
      '<div class="aia-pbar"><span class="up" style="width:' + (p * 100).toFixed(0) + '%">▲ ' + pct(p) + '</span><span class="down" style="width:' + ((1 - p) * 100).toFixed(0) + '%">▼ ' + pct(1 - p) + "</span></div>" +
      '<p class="sig-status" data-st>' + esc(dir === 0 ? "" : T("aia.sig_wait")) + "</p>" +
      '<p class="aia-honest">' + esc(why) + "</p>" +
      '<div class="sig-stats"><span>' + esc(T("aia.sig_pair")) + ": <b>" + (sMine.pc === null ? "—" : "✓" + sMine.w + " ✗" + sMine.l + " (" + sMine.pc + "%)") + "</b></span><span>" + esc(T("aia.sig_all")) + ": <b>" + (sAll.pc === null ? "—" : "✓" + sAll.w + " ✗" + sAll.l + " (" + sAll.pc + "%)") + "</b></span></div>" +
      (rows ? '<ul class="sig-hist">' + rows + "</ul>" : "") +
      '<div class="aia-actions"><a class="btn btn-mint btn-sm" data-ref="binodex" href="#">' + esc(T("cta.reg_binodex")) + '</a><button type="button" class="btn btn-ghost btn-sm aia-again">↻ ' + esc(T("aia.sig_new")) + "</button></div>" +
      '<p class="aia-note">' + esc(T("aia.sig_risk")) + "</p>";
    this.el.result.querySelector(".aia-again").addEventListener("click", function () { self.start(); });
    AT.applyRefLinks();
    this.tick();
    this.resolvePending();
  };

  /* Мурунку, мөөнөтү бүткөн сигналдар: экспирация учурундагы 1 мүнөттүк свечанын жабылышы боюнча текшерилет */
  Analyst.prototype.resolvePending = function () {
    var self = this, now = Date.now(), cur = this.sig && this.sig.id;
    var pend = sigLoad().filter(function (x) { return x.res === null && x.id !== cur && x.tEnd < now - 5000; });
    var codes = pend.map(function (x) { return x.code; }).filter(function (c, i, a) { return a.indexOf(c) === i; });
    if (!codes.length || this._resolving) return;
    this._resolving = true;
    Promise.all(codes.map(function (c) {
      return AIENG.liveFX(c, 1).then(function (d) { return { c: c, cs: d.candles }; }).catch(function () { return null; });
    })).then(function (list) {
      var all = sigLoad(), changed = false;
      list.forEach(function (L) {
        if (!L) return;
        all.forEach(function (x) {
          if (x.code !== L.c || x.res !== null || x.id === cur || x.tEnd >= now - 5000) return;
          var k = L.cs.filter(function (c) { return c.time * 1000 <= x.tEnd - 60000; }).pop();
          if (!k || x.tEnd - 60000 - k.time * 1000 > 120000) { x.res = 3; return; }   // маалымат жок — эсепке кирбейт
          x.exit = k.close;
          x.res = k.close === x.entry ? 2 : (k.close > x.entry) === (x.dir > 0) ? 1 : 0;
          changed = true;
        });
      });
      sigSave(all);
      self._resolving = false;
      if (changed && self.data && self.data.source === "live" && !self.el.result.hidden) self.renderSignal(true);
    });
  };

  Analyst.prototype.tick = function () {
    var self = this;
    clearInterval(this.sigTimer);
    var sg = this.sig;
    if (!sg) return;
    var ring = this.el.result.querySelector("[data-ring]"), cd = this.el.result.querySelector("[data-cd]"), st = this.el.result.querySelector("[data-st]");
    var C = 2 * Math.PI * 19;
    var upd = function () {
      var left = sg.tEnd - Date.now(), tot = sg.exp * 60000;
      if (cd) cd.textContent = mmss(left);
      if (ring) { ring.style.strokeDasharray = C; ring.style.strokeDashoffset = C * (1 - Math.max(0, left) / tot); }
      if (left > 0 || sg.res !== null) return;
      clearInterval(self.sigTimer);
      if (sg.dir === 0) { if (self.auto) self.start(); return; }
      if (st) st.textContent = T("aia.sig_check");
      AIENG.livePrice(sg.code).then(function (px) {
        sg.exit = px;
        sg.res = px === sg.entry ? 2 : (px > sg.entry) === (sg.dir > 0) ? 1 : 0;
        var all = sigLoad();
        all.forEach(function (x) { if (x.id === sg.id) { x.exit = px; x.res = sg.res; } });
        sigSave(all);
        AT.track("signal_result", { pair: sg.code, exp: sg.exp, res: sg.res });
        sfx(sg.res === 1 ? "done" : "blip");
        if (AT.notifyOn()) {
          AT.notify((sg.res === 1 ? "✓ " : sg.res === 0 ? "✗ " : "= ") + sg.name + " · " + T(sg.res === 1 ? "ntf.win" : sg.res === 0 ? "ntf.loss" : "ntf.tie"),
            (sg.dir > 0 ? "▲ " : "▼ ") + money(sg.entry) + " → " + money(px) + " · " + sg.exp + " " + T("aia.min"),
            "forecast.html?s=FX_" + sg.code + "&exp=" + sg.exp, "aitrading-res");
        }
        self.renderSignal(true);
        var s2 = self.el.result.querySelector("[data-st]");
        if (s2) {
          s2.className = "sig-status " + (sg.res === 1 ? "up" : sg.res === 0 ? "down" : "");
          s2.textContent = fmt(T(sg.res === 1 ? "aia.sig_win" : sg.res === 0 ? "aia.sig_loss" : "aia.sig_tie"), { a: money(sg.entry), b: money(px) });
        }
        if (self.auto) setTimeout(function () { self.start(); }, 2500);
      }).catch(function () { if (st) st.textContent = T("aia.err"); });
    };
    upd();
    this.sigTimer = setInterval(upd, 500);
  };

  /* ---------- Жыйынтык ---------- */
  Analyst.prototype.renderResult = function () {
    var R = this.res, I = R.ind, ml = R.ml, self = this;
    var p = ml ? ml.p : 0.5;
    var cls = p >= 0.55 ? "up" : p <= 0.45 ? "down" : "flat";
    var dirTxt = T(p >= 0.55 ? "fc.v_up" : p <= 0.45 ? "fc.v_down" : "fc.v_flat");
    var hz = T("aia.h_" + this.data.tf);
    var ang = -90 + p * 180;
    var sig = [
      ["aia.c_trend", I.trend.dir], ["RSI", I.rsi.dir], ["MACD", I.macd.dir], ["aia.c_bb", I.bb.dir], ["aia.c_ml", p >= 0.55 ? 1 : p <= 0.45 ? -1 : 0]
    ].map(function (s) {
      var d = s[1];
      return '<li class="' + (d > 0 ? "up" : d < 0 ? "down" : "flat") + '"><i>' + (d > 0 ? "▲" : d < 0 ? "▼" : "●") + "</i>" + esc(T(s[0])) + "</li>";
    }).join("");
    var honest = !ml ? T("aia.no_ml") : (ml.acc - ml.base) * 100 > 1
      ? fmt(T("aia.hon_ok"), { a: pct(ml.acc), b: pct(ml.base) })
      : fmt(T("aia.hon_bad"), { a: pct(ml.acc), b: pct(ml.base) });
    var upd = (this.data.updated || "").replace("T", " ").replace("Z", " UTC");
    var src = this.data.source === "fx" ? fmt(T("aia.src_fx"), { t: upd }) : this.data.source === "bingx" ? fmt(T("aia.src_bx"), { t: upd }) : T("aia.src_bn");
    this.syncBest();
    this.el.result.innerHTML =
      this.bestRow() +
      '<div class="aia-res-main">' +
      '<svg class="aia-gauge" viewBox="0 0 120 70" aria-hidden="true"><path d="M10 64 A50 50 0 0 1 110 64" stroke="url(#gg' + this.run_id + ')" stroke-width="10" fill="none" stroke-linecap="round"/>' +
      '<defs><linearGradient id="gg' + this.run_id + '" x1="0" x2="1"><stop offset="0" stop-color="#ff6b6b"/><stop offset=".5" stop-color="#9aa6b8"/><stop offset="1" stop-color="#5ce8aa"/></linearGradient></defs>' +
      '<g transform="rotate(' + ang.toFixed(1) + ' 60 64)"><line x1="60" y1="64" x2="60" y2="22" stroke="#fff" stroke-width="3" stroke-linecap="round"/></g><circle cx="60" cy="64" r="5" fill="#fff"/></svg>' +
      '<div class="aia-res-prob"><div class="aia-res-label">' + esc(fmt(T("aia.r_title"), { h: hz })) + "</div>" +
      '<div class="aia-pbar"><span class="up" style="width:' + (p * 100).toFixed(0) + '%">▲ ' + pct(p) + '</span><span class="down" style="width:' + ((1 - p) * 100).toFixed(0) + '%">▼ ' + pct(1 - p) + "</span></div>" +
      '<div class="aia-res-dir ' + cls + '">' + esc(dirTxt) + "</div></div>" +
      "</div>" +
      '<div class="aia-res-grid">' +
      '<div><div class="aia-res-h">' + esc(fmt(T("aia.r_tally"), { u: R.tally.up, d: R.tally.down, f: R.tally.flat })) + '</div><ul class="aia-sig">' + sig + "</ul></div>" +
      '<div><div class="aia-res-h">' + esc(T("aia.c_levels")) + '</div><p class="aia-lv"><span class="up">' + esc(T("aia.sup")) + ": " + (R.levels.support ? money(R.levels.support.price) : "—") + '</span><span class="down">' + esc(T("aia.res")) + ": " + (R.levels.resistance ? money(R.levels.resistance.price) : "—") + "</span></p></div>" +
      "</div>" +
      '<p class="aia-honest">' + esc(honest) + "</p>" +
      '<div class="aia-actions">' + (FX ? '<a class="btn btn-mint btn-sm" data-ref="binodex" href="#">' + esc(T("cta.reg_binodex")) + "</a>" : '<a class="btn btn-blue btn-sm" data-ref="bingx" href="#">' + esc(T("cta.reg_bingx")) + "</a>") + '<button type="button" class="btn btn-ghost btn-sm aia-again">↻ ' + esc(T("aia.again")) + "</button>" +
      (this.mode === "hero" ? '<a class="btn btn-ghost btn-sm" href="forecast.html?s=' + encodeURIComponent(this.base) + '">' + esc(T("aia.full")) + " →</a>" : "") + "</div>" +
      '<p class="aia-note">' + esc(src) + " · " + esc(T("aia.risk")) + "</p>";
    this.el.result.querySelector(".aia-again").addEventListener("click", function () { self.start(); });
    AT.applyRefLinks();
  };

  /* ---------- Ишке киргизүү ---------- */
  function init() {
    document.querySelectorAll("[data-ai-analyst]").forEach(function (el) {
      var qs = new URLSearchParams(location.search), q = qs.get("s"), ex = Math.round(+qs.get("exp") || 0);
      if (el.getAttribute("data-mode") !== "hero") {
        if (q) el.setAttribute("data-symbol", q.toUpperCase());
        else if (qs.get("m") === "binodex") el.setAttribute("data-symbol", "FX_EURUSD");   // тиркеменин «Сигналдар» ярлыгы
      }
      var a = new Analyst(el);
      if (ex >= 1 && ex <= 240 && a.base.indexOf("FX_") === 0) a.exp = ex;
      el._aia = a;
      AT.lazy(el, function () { setTimeout(function () { a.start(); }, 300); });
    });
  }
  init();
})();
