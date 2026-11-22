/* Тренддер: BingX'те БАР активдер гана.
   Маалымат:
   - assets/data/bingx.json — BingX'тин спот тизмеси жана көлөмдөр (tools/update_bingx.py жаңыртат);
   - CoinGecko (ачкычсыз, жандуу) — эң көп изделген монеталар жана ИИ сектору;
   - IPO фактылары — StockTitan «Biggest IPOs of 2026» (20.11.2026 жаңыртылган).
   Ар бир карточка басылганда өзүнчө блок (drawer) ачылат: TradingView графиги, тех. анализ, маалымат, кантип сатып алуу. */
(function () {
  "use strict";
  if (!window.AT) return;

  var CG = "https://api.coingecko.com/api/v3";
  var STABLE = { USDT: 1, USDC: 1, FDUSD: 1, DAI: 1, USDE: 1, TUSD: 1, PYUSD: 1, USD1: 1, USDS: 1, BUSD: 1, WBTC: 1, WETH: 1, STETH: 1 };
  var IPO_SRC = "https://www.stocktitan.net/articles/biggest-ipos-2026-us-list";
  var IPO_RISK_SRC = "https://fourweekmba.com/ai-9-of-11-big-2026-ipos-trade-below-their-first-day-close/";

  /* ---------- Кол менен толтурулган маалымат (фактылар булактан) ---------- */
  var IPO = [
    { under: "NASDAQ:ANT", name: "Anthropic", sector: "ai", date: "2026-11-18", price: "$83.00", raised: "$81.34B", exch: "Nasdaq · ANT" },
    { under: "NASDAQ:SKHY", name: "SK hynix", sector: "chips", date: "2026-07", price: "$149 / ADS", raised: "≈$26.5B", exch: "Nasdaq · SKHY (ADS)" },
    { under: "NASDAQ:SPCX", name: "SpaceX", sector: "space", date: "2026-06-11", price: "$135.00", raised: "$75.00B", exch: "Nasdaq · SPCX" }
  ];

  var DESC = {
    "Anthropic": { ky: "Жасалма интеллект компаниясы, Claude ИИ-ассистентин жасайт. 2026-жылдын ноябрында Nasdaq'та IPO өткөрдү.", ru: "Компания в сфере искусственного интеллекта, разработчик ассистента Claude. Провела IPO на Nasdaq в ноябре 2026 года." },
    "SK hynix": { ky: "Түштүк Кореянын эс тутум чиптерин (DRAM, HBM) өндүрүүчүсү — ИИ серверлери үчүн маанилүү. Nasdaq'тагы 1 ADS = 1/10 кадимки акция.", ru: "Южнокорейский производитель чипов памяти (DRAM, HBM), важных для ИИ-серверов. 1 ADS на Nasdaq = 1/10 обычной акции." },
    "SpaceX": { ky: "Илон Маскка таандык космос компаниясы: Falcon ракеталары, Starship жана Starlink спутник интернети.", ru: "Космическая компания Илона Маска: ракеты Falcon, Starship и спутниковый интернет Starlink." },
    "NVIDIA": { ky: "ИИ үчүн видеочиптердин (GPU) эң ири өндүрүүчүсү.", ru: "Крупнейший производитель видеочипов (GPU) для ИИ." },
    "Microsoft": { ky: "Windows, Azure булуту жана ИИ кызматтары.", ru: "Windows, облако Azure и ИИ-сервисы." },
    "Alphabet (Google)": { ky: "Google'дун башкы компаниясы: издөө, YouTube, Gemini ИИ.", ru: "Материнская компания Google: поиск, YouTube, ИИ Gemini." },
    "Meta": { ky: "Facebook, Instagram, WhatsApp жана ИИ моделдери.", ru: "Facebook, Instagram, WhatsApp и ИИ-модели." },
    "Palantir": { ky: "Маалыматты талдоо жана ИИ программалары.", ru: "Программы для анализа данных и ИИ." },
    "Broadcom": { ky: "Чиптер жана тармак жабдуулары, ИИ үчүн атайын чиптер.", ru: "Чипы и сетевое оборудование, специализированные чипы для ИИ." },
    "Micron": { ky: "АКШнын эс тутум чиптерин (DRAM, HBM) өндүрүүчүсү.", ru: "Американский производитель чипов памяти (DRAM, HBM)." },
    "Intel": { ky: "Компьютер процессорлорун өндүрүүчү.", ru: "Производитель компьютерных процессоров." },
    "Tesla": { ky: "Электромобилдер, батареялар жана өзү айдаган унаалар.", ru: "Электромобили, батареи и автопилот." },
    "Apple": { ky: "iPhone, Mac жана башка түзмөктөр.", ru: "iPhone, Mac и другие устройства." },
    "Amazon": { ky: "Онлайн дүкөн жана AWS булуту.", ru: "Онлайн-магазин и облако AWS." },
    "Coinbase": { ky: "АКШнын эң ири крипто биржаларынын бири.", ru: "Одна из крупнейших криптобирж США." },
    "Circle": { ky: "USDC стейблкоинин чыгарган компания.", ru: "Компания-эмитент стейблкоина USDC." },
    "Robinhood": { ky: "Акция жана крипто сатып алуучу тиркеме.", ru: "Приложение для покупки акций и криптовалют." },
    "Strategy": { ky: "Биткойнду өз балансында көп кармаган компания.", ru: "Компания, держащая много биткоинов на балансе." },
    "S&P 500 ETF": { ky: "АКШнын 500 ири компаниясынын индекс фонду — бир токенде көп компания.", ru: "Индексный фонд 500 крупнейших компаний США — много компаний в одном токене." },
    "Nasdaq-100 ETF": { ky: "Nasdaq'тагы 100 ири компаниянын (көбү технология) индекс фонду.", ru: "Индексный фонд 100 крупнейших компаний Nasdaq (в основном технологии)." },
    "Silver ETF": { ky: "Күмүштүн баасын кайталаган фонд.", ru: "Фонд, повторяющий цену серебра." },
    "Tether Gold": { ky: "1 токен = 1 трой унция физикалык алтынга байланган (Tether чыгарган).", ru: "1 токен привязан к 1 тройской унции физического золота (эмитент Tether)." },
    "PAX Gold": { ky: "1 токен = 1 трой унция физикалык алтынга байланган (Paxos чыгарган).", ru: "1 токен привязан к 1 тройской унции физического золота (эмитент Paxos)." }
  };

  /* ---------- Жардамчылар ---------- */
  function L() { return AT.lang() === "ru" ? "ru" : "ky"; }
  function T(k) { return AT.t(k); }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function money(v) {
    if (v == null || isNaN(v)) return "—";
    if (v >= 1e9) return "$" + (v / 1e9).toFixed(2) + "B";
    if (v >= 1e6) return "$" + (v / 1e6).toFixed(1) + "M";
    if (v >= 1e3) return "$" + (v / 1e3).toFixed(0) + "K";
    return "$" + v.toFixed(0);
  }
  function price(v) {
    if (v == null || isNaN(v)) return "—";
    return "$" + (v >= 100 ? v.toLocaleString("en-US", { maximumFractionDigits: 2 }) : v >= 1 ? v.toFixed(3) : v.toPrecision(4));
  }
  function pctTxt(v) { return v == null || isNaN(v) ? "—" : (v > 0 ? "+" : "") + v.toFixed(2) + "%"; }
  function dateTxt(s) {
    if (!s) return "—";
    var p = s.split("-");
    return p.length === 3 ? p[2] + "." + p[1] + "." + p[0] : p.length === 2 ? p[1] + "." + p[0] : s;
  }
  function fromMs(ms) {
    if (!ms) return "—";
    var d = new Date(ms);
    return String(d.getUTCDate()).padStart(2, "0") + "." + String(d.getUTCMonth() + 1).padStart(2, "0") + "." + d.getUTCFullYear();
  }

  /* ---------- Маалымат жүктөө ---------- */
  var bx = null;
  var bxPromise = fetch("assets/data/bingx.json", { cache: "no-cache" }).then(function (r) { return r.json(); }).then(function (j) {
    bx = j;
    bx.set = {};
    j.spot.forEach(function (s) { bx.set[s] = 1; });
    return j;
  });

  function cg(path) {
    return fetch(CG + path).then(function (r) { if (!r.ok) throw new Error("cg " + r.status); return r.json(); });
  }

  /* Бир компаниянын бир нече токени болсо — эң көп соодалангыны */
  function groupStocks() {
    var best = {};
    bx.stocks.forEach(function (s) {
      var k = s.name;
      if (!best[k] || s.vol > best[k].vol) best[k] = s;
    });
    return Object.keys(best).map(function (k) { return best[k]; }).sort(function (a, b) { return b.vol - a.vol; });
  }
  function tvFor(s) {
    var fresh = s.listed && Date.now() - s.listed < 10 * 864e5;   // жаңы листинг — TradingView'до али жок болушу мүмкүн
    return fresh && s.under ? s.under : "BINGX:" + s.base + "USDT";
  }
  function stockAsset(s, extra) {
    var others = bx.stocks.filter(function (o) { return o.name === s.name && o.base !== s.base; }).map(function (o) { return o.base + "/USDT"; });
    var a = {
      kind: s.sector === "metals" && !s.under ? "crypto" : "stock",
      name: s.name, base: s.base, pair: s.base + "/USDT", alt: others, tv: tvFor(s), sector: s.sector,
      desc: DESC[s.name], listed: s.listed,
      facts: [["d.f_last", price(s.last)], ["d.f_chg", pctTxt(s.chg)], ["d.f_vol", money(s.vol)], ["d.f_listed", fromMs(s.listed)]],
      why: { key: "w.volume", v: money(s.vol) }
    };
    if (s.under) a.facts.push(["d.f_under", s.under.split(":")[1] + " (" + s.under.split(":")[0] + ")"]);
    if (extra) Object.keys(extra).forEach(function (k) { a[k] = extra[k]; });
    return a;
  }
  function coinAsset(c, why) {
    var sym = String(c.symbol).toUpperCase();
    return {
      kind: "crypto", name: c.name, base: sym, pair: sym + "/USDT", alt: [], tv: "BINGX:" + sym + "USDT", sector: why.sector || "crypto",
      descFn: function () { return c.rank ? fmt(T("d.coin_desc"), { r: "#" + c.rank }) : fmt(T("d.coin_desc2"), { pair: sym + "/USDT" }); },
      facts: [["d.f_last", price(c.price)], ["d.f_chg", pctTxt(c.chg)], ["d.f_vol", c.vol != null ? money(c.vol) : (c.volTxt || "—")], ["d.f_rank", c.rank ? "#" + c.rank : "—"]],
      why: why
    };
  }
  function fmt(t, v) { return String(t).replace(/\{(\w+)\}/g, function (_, k) { return v && k in v ? v[k] : ""; }); }

  /* Категориялар */
  var cache = {};
  function getCat(cat) {
    if (cache[cat]) return cache[cat];
    cache[cat] = bxPromise.then(function () {
      var grouped = groupStocks();
      if (cat === "ipo") {
        return IPO.map(function (ipo) {
          var s = grouped.filter(function (g) { return g.under === ipo.under; })[0];
          if (!s) return null;
          var a = stockAsset(s, { ipo: ipo, sector: ipo.sector });
          a.facts = [["d.f_ipo_date", dateTxt(ipo.date)], ["d.f_ipo_price", ipo.price], ["d.f_raised", ipo.raised], ["d.f_exch", ipo.exch], ["d.f_listed", fromMs(s.listed)], ["d.f_vol", money(s.vol)]];
          a.why = { key: "w.ipo", v: dateTxt(ipo.date), p: ipo.price };
          return a;
        }).filter(Boolean);
      }
      if (cat === "crypto") {
        return cg("/search/trending").then(function (j) {
          var out = [];
          (j.coins || []).forEach(function (x, i) {
            var it = x.item, sym = String(it.symbol).toUpperCase();
            if (!bx.set[sym] || STABLE[sym]) return;
            var d = it.data || {};
            out.push(coinAsset({
              name: it.name, symbol: sym, rank: it.market_cap_rank,
              price: d.price, chg: d.price_change_percentage_24h ? d.price_change_percentage_24h.usd : null, volTxt: d.total_volume
            }, { key: "w.trend", v: i + 1, sector: "crypto" }));
          });
          return out;
        });
      }
      if (cat === "ai") {
        var aiStocks = grouped.filter(function (g) { return g.sector === "ai"; }).map(function (s) { return stockAsset(s); });
        return cg("/coins/markets?vs_currency=usd&category=artificial-intelligence&order=volume_desc&per_page=40&page=1&price_change_percentage=24h").then(function (list) {
          var coins = [];
          list.forEach(function (c) {
            var sym = String(c.symbol).toUpperCase();
            if (!bx.set[sym] || STABLE[sym] || coins.length >= 6) return;
            coins.push(coinAsset({ name: c.name, symbol: sym, rank: c.market_cap_rank, price: c.current_price, chg: c.price_change_percentage_24h, vol: c.total_volume },
              { key: "w.ai_coin", v: money(c.total_volume), sector: "ai" }));
          });
          var out = [], i = 0;
          while (out.length < 8 && (i < aiStocks.length || i < coins.length)) {
            if (aiStocks[i]) out.push(aiStocks[i]);
            if (coins[i]) out.push(coins[i]);
            i++;
          }
          return out;
        }).catch(function () { return aiStocks; });
      }
      if (cat === "grow") {
        return (bx.growing || []).map(function (g) {
          var a;
          if (g.kind === "stock") {
            var st = bx.stocks.filter(function (x) { return x.base === g.base; })[0] ||
              { base: g.base, under: g.under, name: g.name, sector: g.sector, last: g.last, chg: g.chg24, vol: g.vol, listed: g.listed };
            a = stockAsset(st);
          } else {
            a = coinAsset({ name: g.base, symbol: g.base, price: g.last, chg: g.chg24, vol: g.vol }, { sector: "crypto" });
          }
          a.why = { key: "w.grow", v: "+" + g.chg7.toFixed(1) + "%", d: g.up, c: pctTxt(g.chg24) };
          a.facts = [["d.f_last", price(g.last)], ["d.f_chg7", "+" + g.chg7.toFixed(1) + "%"], ["d.f_chg", pctTxt(g.chg24)],
            ["d.f_up", g.up + " / 7"], ["d.f_vol", money(g.vol)], ["d.f_listed", fromMs(g.listed)]];
          return a;
        });
      }
      if (cat === "mixed") {
        var ipoUnder = IPO.map(function (x) { return x.under; });
        return grouped.filter(function (g) { return g.sector !== "ai" && ipoUnder.indexOf(g.under) < 0; }).slice(0, 8).map(function (s) { return stockAsset(s); });
      }
      return [];
    });
    return cache[cat];
  }

  /* ---------- Карточкалар ---------- */
  var SECTOR_KEY = { stock: "sec_stock", ai: "sec_ai", chips: "sec_chips", space: "sec_space", auto: "sec_auto", tech: "sec_tech", fintech: "sec_fintech", index: "sec_index", metals: "sec_metals", crypto: "sec_crypto" };

  function whyText(w) {
    return fmt(T(w.key), w);
  }

  function card(a, i, cat) {
    var el = document.createElement("article");
    el.className = "acard acard-" + cat;
    el.innerHTML =
      '<div class="acard-top"><span class="arank">' + (i + 1) + '</span>' +
      '<span class="atag">' + esc(T("cat." + cat)) + " · " + esc(T(SECTOR_KEY[a.sector] || "sec_crypto")) + "</span>" +
      '<span class="abingx" title="BingX">BingX ✓</span></div>' +
      '<div class="acard-chart"><div class="acard-tv"></div><button type="button" class="acard-hit" aria-label="' + esc(a.name) + '"></button></div>' +
      '<h3>' + esc(a.name) + ' <small>' + esc(a.pair) + "</small></h3>" +
      '<p class="awhy">' + esc(whyText(a.why)) + "</p>" +
      '<div class="aact"><button type="button" class="btn btn-ghost btn-sm" data-open>' + esc(T("d.more")) + "</button></div>";
    var open = function () { openAsset(a); };
    el.querySelector(".acard-hit").addEventListener("click", open);
    el.querySelector("[data-open]").addEventListener("click", open);
    AT.lazy(el, function () {
      AT.mountTV(el.querySelector(".acard-tv"), "mini-symbol-overview", {
        symbol: a.tv, width: "100%", height: "100%", locale: "ru", dateRange: "1M", colorTheme: "dark", isTransparent: true, autosize: true, noTimeScale: false
      }, { copyright: false });
    });
    return el;
  }

  function renderInto(box) {
    var cat = box.getAttribute("data-trend");
    var limit = +box.getAttribute("data-limit") || 6;
    box.innerHTML = '<p class="muted">' + esc(T("js.loading")) + "</p>";
    getCat(cat).then(function (list) {
      box.innerHTML = "";
      if (cat === "grow") growNote(list.length);
      if (!list.length) {
        box.innerHTML = '<div class="callout" style="grid-column:1/-1"><svg aria-hidden="true"><use href="#i-info"/></svg><p>' + esc(T(cat === "grow" ? "g.empty" : "t.empty")) + "</p></div>";
        return;
      }
      list.slice(0, limit).forEach(function (a, i) { box.appendChild(card(a, i, cat)); });
    }).catch(function (e) {
      console.error(e);
      box.innerHTML = '<p class="muted">' + esc(T("t.err")) + "</p>";
    });
  }

  /* «Өсүп жатат» блогунун эрежелери жана эскертүүсү (bingx.json'дон) */
  function growNote(n) {
    var r = (bx && bx.growing_rules) || {};
    document.querySelectorAll("[data-grow-rules]").forEach(function (el) {
      el.innerHTML = [
        fmt(T("g.r1"), { a: r.chg7_min, b: r.chg7_max_crypto }),
        fmt(T("g.r2"), { d: r.up_days_min }),
        fmt(T("g.r3"), { m: r.chg24_max }),
        fmt(T("g.r4"), { v: money(r.vol_min_crypto || 0) }),
        fmt(T("g.r5"), { d: r.fresh_days })
      ].map(function (t) { return '<span class="rule">' + esc(t) + "</span>"; }).join("");
    });
    document.querySelectorAll("[data-grow-note]").forEach(function (el) {
      var t = bx ? bx.updated.replace("T", " ").replace("Z", " UTC") : "";
      el.textContent = fmt(T("g.note"), { c: bx ? bx.growing_checked : "—", n: n, t: t }) + (n > 0 && n < 3 ? " " + fmt(T("g.few"), { n: n }) : "");
    });
  }

  /* ---------- Өзүнчө блок (drawer) ---------- */
  var dr;
  function ensureDrawer() {
    if (dr) return dr;
    dr = document.createElement("div");
    dr.className = "drawer";
    dr.hidden = true;
    dr.setAttribute("role", "dialog");
    dr.setAttribute("aria-modal", "true");
    dr.setAttribute("aria-labelledby", "dr-title");
    dr.innerHTML =
      '<div class="drawer-backdrop" data-close></div>' +
      '<div class="drawer-panel">' +
      '<header class="drawer-head"><div><h2 id="dr-title"></h2><div class="dr-tags"></div></div>' +
      '<div class="dr-actions"><button type="button" class="btn btn-ghost btn-sm" data-share><span data-k="d.share"></span></button>' +
      '<button type="button" class="dr-close" data-close aria-label="×">×</button></div></header>' +
      '<div class="drawer-body">' +
      '<div class="dr-chart"></div>' +
      '<div class="dr-grid">' +
      '<section class="dr-info"><h3 class="dr-h" data-k="d.what"></h3><p class="dr-desc"></p><h3 class="dr-h" data-k="d.why"></h3><p class="dr-why"></p><dl class="dr-facts"></dl><p class="dr-src"></p></section>' +
      '<section class="dr-ta-wrap"><h3 class="dr-h" data-k="p.ta"></h3><div class="dr-ta"></div></section>' +
      "</div>" +
      '<section class="dr-buy"><h3 class="dr-h" data-k="d.how"></h3><ol class="gsteps gsteps-blue dr-steps"></ol>' +
      '<div class="cta-row" style="margin:14px 0 0"><a class="btn btn-blue btn-lg" data-ref="bingx" href="#"><span data-k="cta.reg_bingx"></span><svg aria-hidden="true"><use href="#i-ext"/></svg></a>' +
      '<a class="btn btn-ghost btn-lg" href="learn.html#bingx"><span data-k="d.full"></span></a></div></section>' +
      '<div class="risk" role="note"><svg aria-hidden="true"><use href="#i-warn"/></svg><div><strong data-k="d.risk_t"></strong><p data-k="d.risk_p"></p></div></div>' +
      "</div></div>";
    document.body.appendChild(dr);
    dr.addEventListener("click", function (e) {
      if (e.target.closest("[data-close]")) closeAsset();
      if (e.target.closest("[data-share]") && current) shareAsset(current);
    });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !dr.hidden) closeAsset(); });
    return dr;
  }

  var current = null, lastFocus = null;
  function fillDrawer(a) {
    var d = ensureDrawer();
    d.querySelectorAll("[data-k]").forEach(function (el) { el.textContent = T(el.getAttribute("data-k")); });
    d.querySelector("#dr-title").innerHTML = esc(a.name) + ' <small>' + esc(a.pair) + "</small>";
    d.querySelector(".dr-tags").innerHTML =
      '<span class="badge badge-blue">BingX ✓ ' + esc(a.pair) + "</span>" +
      '<span class="badge badge-yellow">' + esc(T(SECTOR_KEY[a.sector] || "sec_crypto")) + "</span>" +
      (a.alt && a.alt.length ? '<span class="badge badge-mint">' + esc(T("d.also")) + " " + esc(a.alt.join(", ")) + "</span>" : "");
    var desc = a.descFn ? a.descFn() : a.desc ? a.desc[L()] || a.desc.ky : T("d.no_desc");
    if (a.kind === "stock") desc += " " + T("d.token_note");
    d.querySelector(".dr-desc").textContent = desc;
    d.querySelector(".dr-why").textContent = whyText(a.why);
    d.querySelector(".dr-facts").innerHTML = a.facts.map(function (f) {
      return "<div><dt>" + esc(T(f[0])) + "</dt><dd>" + esc(f[1]) + "</dd></div>";
    }).join("");
    var src = [];
    if (a.ipo) src.push('<a href="' + IPO_SRC + '" target="_blank" rel="noopener nofollow">StockTitan</a>');
    if (a.kind === "crypto" && !a.ipo) src.push('<a href="https://www.coingecko.com/" target="_blank" rel="noopener nofollow">CoinGecko</a>');
    src.push("BingX API · " + esc(bx ? bx.updated.replace("T", " ").replace("Z", " UTC") : ""));
    d.querySelector(".dr-src").innerHTML = esc(T("d.src")) + " " + src.join(" · ");
    if (a.tv.indexOf("BINGX:") !== 0) d.querySelector(".dr-src").innerHTML += "<br>" + esc(T("d.chart_under"));
    var steps = [
      ["d.s1t", "d.s1p"], ["d.s2t", "d.s2p"], ["d.s3t", "d.s3p"], ["d.s4t", "d.s4p"]
    ];
    d.querySelector(".dr-steps").innerHTML = steps.map(function (s) {
      return "<li><h3>" + esc(T(s[0])) + "</h3><p>" + esc(fmt(T(s[1]), { pair: a.pair, base: a.base })) + "</p></li>";
    }).join("");
    AT.applyRefLinks();
  }

  function shareAsset(a) {
    var url = location.href.replace(/[#?].*$/, "").replace(/[^/]*$/, "") + "trends.html#a=" + encodeURIComponent(a.base);
    var text = a.name + " (" + a.pair + ") — " + T("d.share_text");
    AT.track("asset_share", { asset: a.base });
    if (navigator.share) {
      navigator.share({ title: a.name + " — AITRADING.KG", text: text, url: url }).catch(function () {});
    } else {
      window.open("https://t.me/share/url?url=" + encodeURIComponent(url) + "&text=" + encodeURIComponent(text), "_blank", "noopener");
    }
  }

  function openAsset(a) {
    var d = ensureDrawer();
    current = a;
    AT.track("asset_open", { asset: a.base });
    try { history.replaceState(null, "", "#a=" + encodeURIComponent(a.base)); } catch (e) { /* */ }
    lastFocus = document.activeElement;
    fillDrawer(a);
    d.hidden = false;
    document.documentElement.classList.add("no-scroll");
    var narrow = window.innerWidth < 640;
    AT.mountTV(d.querySelector(".dr-chart"), "advanced-chart", {
      // «D» интервалы жана көлөм панели BingX токендеринде графикти жүктөбөй калат — 1 саат туруктуу иштейт
      autosize: true, symbol: a.tv, interval: "60", timezone: "Asia/Bishkek", theme: "dark", style: "1", locale: "ru",
      allow_symbol_change: false, hide_side_toolbar: narrow, hide_volume: true, support_host: "https://www.tradingview.com"
    }, { fallbackUrl: "https://ru.tradingview.com/symbols/" + a.tv.replace(":", "-") + "/" });
    AT.mountTV(d.querySelector(".dr-ta"), "technical-analysis", {
      interval: a.kind === "crypto" ? "1h" : "1D", width: "100%", height: "100%", isTransparent: true, symbol: a.tv,
      showIntervalTabs: true, displayMode: "single", locale: "ru", colorTheme: "dark"
    });
    d.querySelector(".dr-close").focus();
  }

  function closeAsset() {
    if (!dr) return;
    dr.hidden = true;
    current = null;
    try { if (/^#a=/.test(location.hash)) history.replaceState(null, "", location.pathname + location.search); } catch (e) { /* */ }
    document.documentElement.classList.remove("no-scroll");
    dr.querySelector(".dr-chart").innerHTML = "";
    dr.querySelector(".dr-ta").innerHTML = "";
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  /* ---------- Табдар (башкы бет) жана бөлүмдөр ---------- */
  function initTabs() {
    document.querySelectorAll("[data-trend-tabs]").forEach(function (tabs) {
      var box = document.querySelector(tabs.getAttribute("data-trend-tabs"));
      if (!box) return;
      var btns = tabs.querySelectorAll("button[data-cat]");
      function pick(cat) {
        btns.forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-cat") === cat)); });
        box.setAttribute("data-trend", cat);
        renderInto(box);
      }
      btns.forEach(function (b) { b.addEventListener("click", function () { pick(b.getAttribute("data-cat")); }); });
      pick(btns[0].getAttribute("data-cat"));
    });
  }

  function renderAll() {
    document.querySelectorAll("[data-trend]").forEach(function (box) {
      if (box.closest("[data-tabbed]")) return;   // табдар өздөрү чыгарат
      renderInto(box);
    });
  }

  /* BingX'те эң көп соодаланган жуптар (snapshot) */
  function renderTop() {
    var tb = document.querySelector("[data-bx-top]");
    if (!tb) return;
    bxPromise.then(function () {
      tb.innerHTML = bx.top.slice(0, 10).map(function (r, i) {
        var cls = r.chg > 0 ? "up" : r.chg < 0 ? "down" : "";
        return '<tr data-sym="' + esc(r.base) + '"><td>' + (i + 1) + "</td><td><b>" + esc(r.base) + "</b>/USDT</td><td>" + price(r.last) + '</td><td class="' + cls + '">' + pctTxt(r.chg) + "</td><td>" + money(r.vol) + "</td></tr>";
      }).join("");
      tb.querySelectorAll("tr").forEach(function (tr, i) {
        tr.addEventListener("click", function () {
          var r = bx.top[i];
          openAsset(coinAsset({ name: r.base, symbol: r.base, price: r.last, chg: r.chg, vol: r.vol }, { key: "w.top", v: i + 1, sector: "crypto" }));
        });
      });
      var u = document.querySelector("[data-bx-updated]");
      if (u) u.textContent = bx.updated.replace("T", " ").replace("Z", " UTC");
    });
  }

  /* Шилтеме аркылуу ачуу: trends.html#a=SPCXB */
  function openFromHash() {
    var m = /^#a=([A-Za-z0-9_]+)/.exec(location.hash);
    if (!m) return;
    var want = decodeURIComponent(m[1]).toUpperCase();
    Promise.all(["grow", "ipo", "ai", "mixed", "crypto"].map(function (c) { return getCat(c).catch(function () { return []; }); })).then(function (lists) {
      var all = [].concat.apply([], lists);
      var a = all.filter(function (x) { return x.base === want; })[0];
      if (!a && bx) {
        var s = bx.stocks.filter(function (x) { return x.base === want; })[0];
        if (s) a = stockAsset(s);
        else if (bx.set[want]) a = coinAsset({ name: want, symbol: want }, { key: "w.top", v: "—", sector: "crypto" });
      }
      if (a) openAsset(a);
    });
  }

  initTabs();
  renderAll();
  renderTop();
  openFromHash();

  AT.onLang(function () {
    document.querySelectorAll("[data-trend]").forEach(renderInto);
    if (current) fillDrawer(current);
  });

  window.AT.openAsset = openAsset;
})();
