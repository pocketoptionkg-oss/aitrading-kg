/* AITRADING.KG — жалпы логика: шапка/футер, тил, «Катталуу» шилтемелери, меню, TradingView виджеттери. */
(function () {
  "use strict";

  var CFG = window.AITRADING_CONFIG || {};
  var DICT = window.AITRADING_I18N || { ky: {}, ru: {} };
  var LANG_KEY = "aitrading-lang";
  var IS_LOCAL = /^(localhost|127\.0\.0\.1|\[::1\]|)$/.test(location.hostname);
  var lang = "ky";
  var listeners = [];
  var htmlOriginals = new WeakMap();
  var attrOriginals = new WeakMap();

  /* Брокерлер: data-ref="..." → config.js'теги константа */
  var BROKERS = {
    binodex: { name: "BinoDex", key: "BINODEX_REF_URL" },
    bingx: { name: "BingX", key: "BINGX_REF_URL" }
  };

  function store(key, val) {
    try {
      if (val === undefined) return localStorage.getItem(key);
      localStorage.setItem(key, val);
    } catch (e) { return null; }
    return null;
  }

  /* ---------- Иконкалар, шапка, футер (бардык беттерге бирдей) ---------- */
  var SPRITE =
    '<svg width="0" height="0" style="position:absolute" aria-hidden="true">' +
    '<symbol id="i-check" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9.5"/><path d="m8 12.5 2.7 2.7L16.5 9"/></symbol>' +
    '<symbol id="i-warn" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.3 3.9 2.4 17.5A2 2 0 0 0 4.1 20.5h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4.5M12 17h.01"/></symbol>' +
    '<symbol id="i-ext" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 17 17 7M8 7h9v9"/></symbol>' +
    '<symbol id="i-chart" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3v3M6 15v6M18 3v5M18 16v5M12 6v2M12 14v4"/><rect x="4" y="6" width="4" height="9" rx="1"/><rect x="16" y="8" width="4" height="8" rx="1"/><rect x="10" y="8" width="4" height="6" rx="1"/></symbol>' +
    '<symbol id="i-shield" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 21s7.5-3.6 7.5-9.6V5.6L12 3 4.5 5.6v5.8C4.5 17.4 12 21 12 21Z"/><path d="m9 12 2.2 2.2L15.5 10"/></symbol>' +
    '<symbol id="i-layers" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 13 9 5 9-5"/></symbol>' +
    '<symbol id="i-chat" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 15a2 2 0 0 1-2 2H8l-4 4V6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2Z"/><path d="M8 9h8M8 12.5h5"/></symbol>' +
    '<symbol id="i-info" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9.5"/><path d="M12 11v5.5M12 7.5h.01"/></symbol>' +
    '<symbol id="i-globe" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9.5"/><path d="M2.5 12h19M12 2.5c2.6 2.6 3.8 6 3.8 9.5s-1.2 6.9-3.8 9.5c-2.6-2.6-3.8-6-3.8-9.5S9.4 5.1 12 2.5Z"/></symbol>' +
    '<symbol id="i-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></symbol>' +
    '<symbol id="i-news" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="15" height="16" rx="2"/><path d="M18 8h2a1 1 0 0 1 1 1v9a2 2 0 0 1-2 2H5M7 8h7M7 12h7M7 16h4"/></symbol>' +
    '<symbol id="i-ai" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="5" width="14" height="14" rx="3"/><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/><path d="M9.5 15 11 9h2l1.5 6M10 13h4"/></symbol>' +
    '<symbol id="i-book" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5Z"/><path d="M4 20.5A2.5 2.5 0 0 0 6.5 23H20v-5"/><path d="M8 7h8M8 11h6"/></symbol>' +
    '<symbol id="i-users" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16 4.6a3.5 3.5 0 0 1 0 6.8M18 14a6.5 6.5 0 0 1 3.5 6"/></symbol>' +
    '<symbol id="i-swap" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8h13l-3-3M20 16H7l3 3"/></symbol>' +
    '<symbol id="i-megaphone" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10v4a1 1 0 0 0 1 1h3l6 4V5L7 9H4a1 1 0 0 0-1 1Z"/><path d="M17 9a4 4 0 0 1 0 6M19.5 6.5a7.5 7.5 0 0 1 0 11"/></symbol>' +
    '<symbol id="i-star" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9Z"/></symbol>' +
    '<symbol id="i-fire" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22c4 0 7-2.8 7-6.8 0-3.6-2.4-6-4.3-8.2-.5 2-1.6 3.3-3 3.8.3-2.9-.8-5.7-3.2-7.8C8.7 6.5 5 9.6 5 15.2 5 19.2 8 22 12 22Z"/><path d="M12 22c-1.7 0-3-1.3-3-3.1 0-1.9 1.5-3.1 3-4.9 1.5 1.8 3 3 3 4.9 0 1.8-1.3 3.1-3 3.1Z"/></symbol>' +
    '<symbol id="i-cal" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3.5" y="5" width="17" height="15.5" rx="2.5"/><path d="M3.5 10h17M8 3v4M16 3v4M8 14h2M14 14h2M8 17.5h2"/></symbol>' +
    '<symbol id="i-userplus" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9.5" cy="8" r="3.8"/><path d="M2.5 20.5a7 7 0 0 1 14 0M19 8v6M16 11h6"/></symbol>' +
    '<symbol id="i-tg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.5 4 2.8 11.3c-.8.3-.8 1.4 0 1.7l4.7 1.6 1.8 5.5c.2.7 1.1.9 1.6.3l2.6-2.9 4.9 3.6c.6.4 1.4.1 1.6-.6L22.9 5.3c.2-.9-.6-1.6-1.4-1.3Z"/><path d="m7.5 14.6 10.3-6.7-7.9 8.4"/></symbol>' +
    '<symbol id="i-phone" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6.5" y="2.5" width="11" height="19" rx="2.5"/><path d="M11 18h2"/></symbol>' +
    '<symbol id="i-grid" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3.5" y="3.5" width="7" height="7" rx="2"/><rect x="13.5" y="3.5" width="7" height="7" rx="2"/><rect x="3.5" y="13.5" width="7" height="7" rx="2"/><rect x="13.5" y="13.5" width="7" height="7" rx="2"/></symbol>' +
    '<symbol id="i-gauge" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 17a8.5 8.5 0 1 1 17 0"/><path d="m12 17 4.2-5.2"/><circle cx="12" cy="17" r="1.4"/><path d="M7 12.5l-.9-.6M12 8.5V7.4M17 12.5l.9-.6"/></symbol>' +
    "</svg>";

  /* ---------- Негизги бөлүмдөр: сол жактагы тилке (ПК), ылдыйкы панель жана «Баары» (телефон) ---------- */
  var SIGNALS_URL = "forecast.html?s=FX_EURUSD&exp=1";
  var SECTIONS = [
    { id: "forecast", href: "forecast.html", icon: "i-ai", k: "rail.ai", kg: "ИИ-анализ", cls: "is-ai" },
    { id: "signals", href: SIGNALS_URL, icon: "i-star", k: "rail.signals", kg: "Сигналдар" },
    { id: "trends", href: "trends.html", icon: "i-fire", k: "rail.trends", kg: "Тренддер" },
    { id: "news", href: "news.html", icon: "i-news", k: "rail.news", kg: "Жаңылыктар" },
    { id: "calendar", panel: "calendar", icon: "i-cal", k: "rail.calendar", kg: "Календарь" },
    { id: "analyzer", href: "analyzer.html", icon: "i-chart", k: "rail.analyzer", kg: "Анализатор" },
    { id: "learn", href: "learn.html", icon: "i-book", k: "rail.learn", kg: "Окуу" },
    { id: "register", href: "register.html", icon: "i-userplus", k: "rail.register", kg: "Катталуу", cls: "is-reg" },
    { id: "marketing", href: "marketing.html", icon: "i-megaphone", k: "rail.marketing", kg: "Маркетинг" },
    { id: "tools", href: "tools.html", icon: "i-gauge", k: "rail.tools", kg: "Куралдар" },
    { id: "security", href: "security.html", icon: "i-shield", k: "rail.security", kg: "Коопсуздук" },
    { id: "traders", href: "traders.html", icon: "i-users", k: "rail.traders", kg: "Трейдерлер" }
  ];
  var EXTRA = [
    { id: "bot", panel: "bot", icon: "i-tg", k: "rail.bot", kg: "Бот" },
    { id: "app", install: true, icon: "i-phone", k: "rail.app", kg: "Тиркеме" }
  ];
  function item(s) {
    var inner = '<svg aria-hidden="true"><use href="#' + s.icon + '"/></svg><span data-i18n="' + s.k + '">' + s.kg + "</span>";
    var cls = s.cls ? ' class="' + s.cls + '"' : "";
    if (s.panel) return '<button type="button" data-panel="' + s.panel + '" aria-pressed="false"' + cls + ">" + inner + "</button>";
    if (s.install) return '<a href="#" data-install' + cls + ">" + inner + "</a>";
    return '<a href="' + s.href + '" data-sec="' + s.id + '"' + cls + ">" + inner + "</a>";
  }
  var RAIL =
    '<aside class="rail" aria-label="Бөлүмдөр" data-i18n-attr="aria-label:a.sections">' +
    '<a class="rail-logo" href="index.html" aria-label="AITRADING.KG"><span class="brand-ai">AI</span></a>' +
    '<nav class="rail-nav">' + SECTIONS.map(item).join("") + "</nav>" +
    '<div class="rail-foot">' + EXTRA.map(item).join("") + "</div></aside>";
  var TABBAR =
    '<nav class="tabbar" aria-label="Бөлүмдөр" data-i18n-attr="aria-label:a.sections">' +
    [SECTIONS[0], SECTIONS[1], SECTIONS[2], SECTIONS[7]].map(item).join("") +
    '<button type="button" class="tab-more" aria-expanded="false" aria-controls="msheet"><svg aria-hidden="true"><use href="#i-grid"/></svg><span data-i18n="tab.more">Баары</span></button></nav>' +
    '<div class="msheet" id="msheet" hidden><div class="ms-back" data-ms-x></div><div class="ms-card" role="dialog" aria-label="Бөлүмдөр">' +
    '<div class="ms-head"><b data-i18n="tab.all">Бардык бөлүмдөр</b><button type="button" class="ms-x" data-ms-x aria-label="×">×</button></div>' +
    '<div class="ms-grid">' + SECTIONS.concat(EXTRA).map(item).join("") + "</div></div></div>";
  var SPANEL =
    '<div class="sp-back" data-sp-x hidden></div>' +
    '<aside class="spanel" id="spanel" hidden aria-label="Панель">' +
    '<div class="sp-head"><div class="sp-tabs" role="tablist">' +
    '<button type="button" role="tab" data-sp="calendar" aria-selected="true"><svg aria-hidden="true"><use href="#i-cal"/></svg><span data-i18n="sp.cal">Календарь</span></button>' +
    '<button type="button" role="tab" data-sp="bot" aria-selected="false"><svg aria-hidden="true"><use href="#i-tg"/></svg><span data-i18n="sp.bot">Telegram-бот</span></button>' +
    '</div><button type="button" class="sp-x" data-sp-x aria-label="×">×</button></div>' +
    '<div class="sp-body" data-sp-body="calendar"><p class="sp-note" data-i18n="sp.cal_note">Экономикалык календарь: маанилүү окуялар (АКШ, Евробиримдик, Улуу Британия, Япония, Кытай). Убакыт — сиздин түзмөгүңүздүкү.</p><div class="sp-cal" data-sp-cal></div></div>' +
    '<div class="sp-body" data-sp-body="bot" hidden><div class="sp-bot">' +
    '<div class="sp-bot-ico"><svg aria-hidden="true"><use href="#i-tg"/></svg></div>' +
    '<h3 data-i18n="sp.bot_h">⭐ ИИ сигналдары телефонго — сайт жабык болсо да</h3>' +
    '<ul class="sp-list">' +
    '<li data-i18n="sp.bot_1">BinoDex (1 мүн…) жана BingX спот сигналдары, ар биринен кийин ✓/✗ жыйынтыгы</li>' +
    '<li data-i18n="sp.bot_2">Брокерде катталуу кадам-кадам жана кыска сабактар</li>' +
    '<li data-i18n="sp.bot_3">ID\'ңизди жөнөтөсүз — бот текшерип, сигналдарды ачат</li>' +
    "</ul>" +
    '<p class="sp-honest" data-i18n="sp.bot_honest">Сигнал — ыктымалдык, кепилдик эмес: ар биринин жанында тесттеги тактык көрсөтүлөт. 18+</p>' +
    '<a class="btn btn-mint btn-sm" data-bot href="#"><svg aria-hidden="true"><use href="#i-tg"/></svg><span data-i18n="sp.bot_go">Ботко кирүү</span></a>' +
    '<a class="btn btn-ghost btn-sm" href="register.html"><span data-i18n="sp.bot_reg">Катталуу кадамдары</span></a>' +
    "</div></div></aside>";

  var HEADER =
    '<a class="skip-link" href="#main" data-i18n="skip">Мазмунга өтүү</a>' +
    '<header class="site-header"><div class="container header-row">' +
    '<a class="brand" href="index.html" aria-label="AITRADING.KG"><span class="brand-ai">AI</span><span class="brand-name">TRADING<span class="hl">.KG</span></span></a>' +
    '<nav class="nav" id="nav" aria-label="Навигация" data-i18n-attr="aria-label:a.nav">' +
    '<a href="forecast.html" data-nav="forecast" class="nav-ai" data-i18n="nav.forecast">ИИ-анализ</a>' +
    '<a href="trends.html" data-nav="trends" class="nav-hot" data-i18n="nav.trends">Тренддер</a>' +
    '<a href="' + "forecast.html?s=FX_EURUSD&amp;exp=1" + '" data-nav="signals" class="nav-sig" data-i18n="rail.signals">Сигналдар</a>' +
    '<a href="news.html" data-nav="news" data-i18n="nav.news">Жаңылыктар</a>' +
    '<a href="learn.html" data-nav="learn" data-i18n="nav.learn">Окуу</a>' +
    '<a href="marketing.html" data-nav="marketing" data-i18n="nav.marketing">Маркетинг</a>' +
    "</nav>" +
    '<div class="header-actions">' +
    '<div class="lang" role="group" aria-label="Тил / Язык">' +
    '<button type="button" data-lang="ky" aria-pressed="true" title="Кыргызча">KG</button>' +
    '<button type="button" data-lang="ru" aria-pressed="false" title="Русский">RU</button>' +
    "</div>" +
    '<a class="btn btn-mint btn-sm header-cta" href="register.html" data-i18n="cta.register_short">Катталуу</a>' +
    '<button class="burger" type="button" aria-expanded="false" aria-controls="nav" aria-label="Меню" data-i18n-attr="aria-label:a.menu"><span></span></button>' +
    "</div></div></header>" +
    '<div class="ticker" data-tv-ticker></div>';

  var FOOTER =
    '<footer class="site-footer"><div class="container">' +
    '<div class="footer-grid"><div>' +
    '<a class="brand" href="index.html"><span class="brand-ai">AI</span><span class="brand-name">TRADING<span class="hl">.KG</span></span></a>' +
    '<p style="margin-top:16px" data-i18n="footer.about">AITRADING.KG — TRADER KG (Нурсултан) автордук долбоору: трейдингдеги окуяларды талдоо, жаңылыктар, ИИ-прогноз жана окуу.</p>' +
    '<nav class="footer-links">' +
    '<a href="trends.html" data-i18n="nav.trends">Тренддер</a>' +
    '<a href="news.html" data-i18n="nav.news">Жаңылыктар</a>' +
    '<a href="forecast.html" data-i18n="nav.forecast">ИИ-анализ</a>' +
    '<a href="analyzer.html" data-i18n="nav.analyzer">Анализатор</a>' +
    '<a href="learn.html" data-i18n="nav.learn">Окуу</a>' +
    '<a href="index.html#brokers" data-i18n="nav.brokers">Брокерлер</a>' +
    '<a href="marketing.html" data-i18n="nav.marketing">Маркетинг</a>' +
    '<a href="tools.html" data-i18n="rail.tools">Куралдар</a>' +
    '<a href="security.html" data-i18n="rail.security">Коопсуздук</a>' +
    '<a href="traders.html" data-i18n="rail.traders">Трейдерлер</a>' +
    '<a href="#" data-install data-i18n="nav.app">📲 Телефонго орнотуу</a>' +
    "</nav>" +
    '<div class="social" data-social></div>' +
    "</div>" +
    '<div class="disclaimer">' +
    '<h3><svg aria-hidden="true"><use href="#i-warn"/></svg><span data-i18n="footer.risk_title">Тобокелдик жөнүндө эскертүү</span></h3>' +
    '<p data-i18n="footer.risk1">Каржы рынокторунда соода кылуу — анын ичинде акциялар, токенделген акциялар, санарип контракттар, бинардык опциондор, CFD, фьючерстер жана криптовалюталар — жогорку тобокелдикке ээ жана баарына эле туура келбейт. Салган каражатыңыздын баарын жоготуп алышыңыз мүмкүн. Өткөн натыйжалар келечектеги кирешеге кепилдик бербейт.</p>' +
    '<p data-i18n="footer.risk2">Бул сайттагы маалымат, анын ичинде ИИ-прогноз, инвестициялык кеңеш же соода сигналы эмес — ыктымалдык баа гана. Чечимдерди өзүңүз кабыл аласыз жана алар үчүн өзүңүз жооп бересиз. AITRADING.KG — BinoDex\'тин, BingX\'тин же TradingView\'дун расмий сайты эмес. «Катталуу» шилтемелери партнёрдук болушу мүмкүн. Платформалардын кызматтары сиздин өлкөдө мыйзамдуу жана жеткиликтүү экенин өзүңүз текшериңиз. 18 жаштан жогорку адамдар үчүн гана.</p>' +
    "</div></div>" +
    '<div class="copyright"><span><span class="age">18+</span>© <span data-year>2026</span> AITRADING.KG · TRADER KG</span>' +
    '<span data-i18n="footer.data">Графиктер, жаңылыктар жана рынок маалыматтары: TradingView, Binance.</span></div>' +
    "</div></footer>";

  function renderChrome() {
    document.body.insertAdjacentHTML("afterbegin", SPRITE);
    var h = document.querySelector("[data-site-header]");
    if (h) {
      h.outerHTML = HEADER;
      document.body.insertAdjacentHTML("beforeend", RAIL + SPANEL + TABBAR);
      document.documentElement.classList.add("has-rail");
    }
    var f = document.querySelector("[data-site-footer]");
    if (f) f.outerHTML = FOOTER;
    var page = document.body.getAttribute("data-page");
    if (page === "forecast" && /[?&]s=FX_/i.test(location.search)) page = "signals";   // BinoDex сигналдары — өз бөлүмү
    if (page) {
      document.querySelectorAll('.nav a[data-nav="' + page + '"], [data-sec="' + page + '"]').forEach(function (a) {
        a.setAttribute("aria-current", "page");
      });
    }
  }

  /* ---------- Каптал панель: экономикалык календарь жана Telegram-бот ----------
     Кең экранда (≥1600 px: тилке + панель + толук үстүнкү меню батат) мазмунду жылдырып турат,
     кичине экранда үстүнөн ачылат, телефондо — толук экран. */
  var PANEL_KEY = "aitrading-panel", calMounted = false;
  function isWide() { return window.innerWidth >= 1600; }
  function panelOpen(which, persist) {
    var sp = document.getElementById("spanel");
    if (!sp) return;
    which = which === "bot" ? "bot" : "calendar";
    sp.hidden = false;
    document.querySelector(".sp-back").hidden = isWide();
    document.documentElement.classList.add("sp-open");
    document.documentElement.classList.toggle("sp-dock", isWide());
    sp.setAttribute("data-tab", which);
    sp.querySelectorAll("[data-sp]").forEach(function (b) { b.setAttribute("aria-selected", String(b.getAttribute("data-sp") === which)); });
    sp.querySelectorAll("[data-sp-body]").forEach(function (b) { b.hidden = b.getAttribute("data-sp-body") !== which; });
    document.querySelectorAll("[data-panel]").forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-panel") === which)); });
    if (which === "calendar" && !calMounted) {
      calMounted = true;
      mountTV(sp.querySelector("[data-sp-cal]"), "events", {
        colorTheme: "dark", isTransparent: true, width: "100%", height: "100%", locale: "ru",
        importanceFilter: "0,1", countryFilter: "us,eu,gb,jp,cn,ru"
      }, { fallbackUrl: "https://ru.tradingview.com/economic-calendar/" });
    }
    if (persist !== false && isWide()) store(PANEL_KEY, which);
    track("panel_open", { p: which });
  }
  function panelClose() {
    var sp = document.getElementById("spanel");
    if (!sp || sp.hidden) return;
    sp.hidden = true;
    document.querySelector(".sp-back").hidden = true;
    document.documentElement.classList.remove("sp-open", "sp-dock");
    document.querySelectorAll("[data-panel]").forEach(function (b) { b.setAttribute("aria-pressed", "false"); });
    if (isWide()) store(PANEL_KEY, "none");
  }
  function sheet(open) {
    var ms = document.getElementById("msheet"), b = document.querySelector(".tab-more");
    if (!ms) return;
    ms.hidden = !open;
    if (b) b.setAttribute("aria-expanded", String(open));
    document.documentElement.classList.toggle("no-scroll", open);
  }
  function initPanels() {
    if (!document.getElementById("spanel")) return;
    document.addEventListener("click", function (e) {
      // Баскычтар гана (forecast.html'деги <section data-panel="ai|pro"> бул эмес — алар каалаган басууда календарды ачып жатчу)
      var p = e.target.closest('button[data-panel="calendar"], button[data-panel="bot"], a[data-panel="calendar"], a[data-panel="bot"]');
      if (p) {
        e.preventDefault();
        sheet(false);
        var sp = document.getElementById("spanel");
        if (!sp.hidden && sp.getAttribute("data-tab") === p.getAttribute("data-panel")) panelClose();
        else panelOpen(p.getAttribute("data-panel"));
        return;
      }
      var tab = e.target.closest("[data-sp]");
      if (tab) { panelOpen(tab.getAttribute("data-sp")); return; }
      if (e.target.closest("[data-sp-x]")) { panelClose(); return; }
      if (e.target.closest(".tab-more")) { sheet(document.getElementById("msheet").hidden); return; }
      if (e.target.closest("[data-ms-x]") || e.target.closest(".ms-grid a")) sheet(false);
    });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") { panelClose(); sheet(false); } });
    window.addEventListener("resize", function () {
      var sp = document.getElementById("spanel");
      if (sp.hidden) return;
      document.documentElement.classList.toggle("sp-dock", isWide());
      document.querySelector(".sp-back").hidden = isWide();
    });
    // Панель өзү ачылбайт: «Календарь» же «Бот» баскычын басканда гана (мурун кең экранда ар бир бетте өзү ачылчу)
  }

  /* Telegram-бот шилтемеси (config.js → TELEGRAM_BOT_URL). Бош болсо — «жакында». */
  function botUrl(src) {
    var u = String(CFG.TELEGRAM_BOT_URL || "").trim();
    if (!/^https:\/\/t\.me\/[A-Za-z0-9_]{5,}\/?$/i.test(u)) return null;
    return u.replace(/\/$/, "") + "?start=" + (src || "site");
  }

  /* ---------- Тил / Язык ---------- */
  function t(key) {
    var d = DICT[lang] || {};
    if (Object.prototype.hasOwnProperty.call(d, key)) return d[key];
    return (DICT.ky && DICT.ky[key]) || key;
  }

  function applyLang(next, silent) {
    lang = next === "ru" ? "ru" : "ky";
    var ru = DICT.ru || {};
    document.documentElement.lang = lang;

    document.querySelectorAll("[data-i18n]").forEach(function (el) {
      if (!htmlOriginals.has(el)) htmlOriginals.set(el, el.innerHTML);
      var key = el.getAttribute("data-i18n");
      if (lang === "ru" && !(key in ru) && IS_LOCAL) console.warn("[i18n] ru котормо жок:", key);
      el.innerHTML = lang === "ru" && key in ru ? ru[key] : htmlOriginals.get(el);
    });

    document.querySelectorAll("[data-i18n-attr]").forEach(function (el) {
      var saved = attrOriginals.get(el) || {};
      el.getAttribute("data-i18n-attr").split(";").forEach(function (pair) {
        var p = pair.split(":");
        if (p.length < 2) return;
        var attr = p[0].trim();
        var key = p[1].trim();
        if (!(attr in saved)) saved[attr] = el.getAttribute(attr);
        el.setAttribute(attr, lang === "ru" && key in ru ? ru[key] : saved[attr]);
      });
      attrOriginals.set(el, saved);
    });

    document.querySelectorAll("[data-lang]").forEach(function (b) {
      b.setAttribute("aria-pressed", String(b.getAttribute("data-lang") === lang));
    });

    if (!silent) store(LANG_KEY, lang);
    applyRefLinks();
    fillYear();
    listeners.forEach(function (fn) { try { fn(lang); } catch (e) { console.error(e); } });
  }

  function initialLang() {
    var q = new URLSearchParams(location.search).get("lang");
    if (q === "ru" || q === "ky") return q;
    return store(LANG_KEY) === "ru" ? "ru" : "ky";
  }

  /* ---------- «Катталуу» → брокерлер (константалар: config.js) ---------- */
  function refUrl(broker) {
    var b = BROKERS[broker];
    if (!b) return null;
    var u = String(CFG[b.key] || "").trim();
    return /^https:\/\/[^\s]+$/i.test(u) ? u : null;
  }

  function applyRefLinks() {
    document.querySelectorAll("a[data-ref]").forEach(function (a) {
      var url = refUrl(a.getAttribute("data-ref"));
      if (url) {
        a.setAttribute("href", url);
        a.setAttribute("target", "_blank");
        a.setAttribute("rel", "sponsored noopener");
        a.removeAttribute("data-ref-missing");
      } else {
        a.setAttribute("href", "#");
        a.removeAttribute("target");
        a.setAttribute("data-ref-missing", "");
      }
    });
    document.querySelectorAll("a[data-bot]").forEach(function (a) {
      var url = botUrl(a.getAttribute("data-bot") || "site");
      if (url) {
        a.setAttribute("href", url);
        a.setAttribute("target", "_blank");
        a.setAttribute("rel", "noopener");
        a.removeAttribute("data-ref-missing");
      } else {
        a.setAttribute("href", "#");
        a.setAttribute("data-ref-missing", "");
      }
    });
    applyRefCodes();
  }

  /* ---------- Реферал коду (config.js → REF_CODES): катталуу баскычтарынын астында «Көчүрүү» менен ---------- */
  var RC_WRAP = ".actions, .cta-row, .center-cta, .ract, .aia-actions";
  function refCode(broker) {
    var c = String((CFG.REF_CODES || {})[broker] || "").trim();
    return /^[A-Za-z0-9_-]{2,40}$/.test(c) ? c : null;
  }
  function fillRefBox(box) {
    var b = box.getAttribute("data-refcode"), code = refCode(b), name = (BROKERS[b] || {}).name || b;
    if (!code) { box.remove(); return; }
    box.innerHTML = "";
    var l = document.createElement("b"); l.textContent = t("rc.label");
    var c = document.createElement("code"); c.textContent = code;
    var btn = document.createElement("button"); btn.type = "button"; btn.setAttribute("data-copy", code); btn.textContent = t("rc.copy");
    var s = document.createElement("small"); s.textContent = t("rc.hint").replace("{b}", name);
    box.appendChild(l); box.appendChild(c); box.appendChild(btn); box.appendChild(s);
  }
  function applyRefCodes() {
    document.querySelectorAll("a[data-ref]").forEach(function (a) {
      var b = a.getAttribute("data-ref");
      if (!refCode(b) || a.hasAttribute("data-rc")) return;
      a.setAttribute("data-rc", "");
      var host = a.closest(RC_WRAP) || a, next = host.nextElementSibling;
      if (next && next.classList.contains("refcode") && next.getAttribute("data-refcode") === b) return;   // бир катарга бир гана
      var box = document.createElement("div");
      box.className = "refcode";
      box.setAttribute("data-refcode", b);
      host.insertAdjacentElement("afterend", box);
    });
    document.querySelectorAll(".refcode[data-refcode]").forEach(fillRefBox);
  }
  function fallbackCopy(s) {
    var ta = document.createElement("textarea");
    ta.value = s; ta.setAttribute("readonly", ""); ta.style.cssText = "position:fixed;left:-9999px;opacity:0";
    document.body.appendChild(ta); ta.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    ta.remove();
    return ok;
  }
  function copyText(s) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(s).then(function () { return true; }, function () { return fallbackCopy(s); });
    }
    return Promise.resolve(fallbackCopy(s));
  }

  /* ---------- Аналитика (config.js → ANALYTICS): конверсияны өлчөө ---------- */
  var AN = CFG.ANALYTICS || {};
  function loadScript(src) {
    var s = document.createElement("script");
    s.async = true;
    s.src = src;
    document.head.appendChild(s);
  }
  function initAnalytics() {
    var ga = String(AN.ga4 || "").trim();
    if (/^G-[A-Z0-9]+$/i.test(ga)) {
      window.dataLayer = window.dataLayer || [];
      window.gtag = function () { window.dataLayer.push(arguments); };
      window.gtag("js", new Date());
      window.gtag("config", ga, { anonymize_ip: true });
      loadScript("https://www.googletagmanager.com/gtag/js?id=" + encodeURIComponent(ga));
    }
    var ym = String(AN.yandex || "").trim();
    if (/^\d+$/.test(ym)) {
      window.ym = window.ym || function () { (window.ym.a = window.ym.a || []).push(arguments); };
      window.ym.l = Date.now();
      loadScript("https://mc.yandex.ru/metrika/tag.js");
      window.ym(+ym, "init", { clickmap: true, trackLinks: true, accurateTrackBounce: true });
    }
  }
  function track(name, params) {
    params = params || {};
    try {
      if (window.gtag) window.gtag("event", name, params);
      if (window.ym && /^\d+$/.test(String(AN.yandex || ""))) window.ym(+AN.yandex, "reachGoal", name, params);
      if (IS_LOCAL) console.info("[track]", name, params);
    } catch (e) { /* аналитика сайтты бузбашы керек */ }
  }

  document.addEventListener("click", function (e) {
    var tb = e.target.closest && e.target.closest("a[data-bot]");
    if (tb) {
      track("bot_click", { page: document.body.getAttribute("data-page") || "" });
      if (!botUrl()) { e.preventDefault(); toast(t("js.bot_missing")); }
      return;
    }
    var cp = e.target.closest && e.target.closest("[data-copy]");
    if (cp) {
      var code = cp.getAttribute("data-copy");
      copyText(code).then(function (ok) {
        if (!ok) {                                     // браузер уруксат бербесе — кодду белгилеп коёбуз (Ctrl+C / узун басуу)
          var el = cp.parentElement && cp.parentElement.querySelector("code");
          if (el && window.getSelection) { var r = document.createRange(); r.selectNodeContents(el); var s = getSelection(); s.removeAllRanges(); s.addRange(r); }
          return;
        }
        cp.textContent = t("rc.copied");
        setTimeout(function () { cp.textContent = t("rc.copy"); }, 2200);
      });
      track("refcode_copy", { page: document.body.getAttribute("data-page") || "" });
      return;
    }
    var a = e.target.closest && e.target.closest("a[data-ref]");
    if (!a) return;
    var broker = a.getAttribute("data-ref");
    track("register_click", { broker: broker, page: document.body.getAttribute("data-page") || "" });
    if (!refUrl(broker)) {
      e.preventDefault();
      var b = BROKERS[broker];
      toast((b ? b.name + ": " : "") + t("js.ref_missing"));
      return;
    }
    // Катталуу баскычы басылганда реферал коду өзү көчүрүлөт — брокердин формасына коюуга даяр
    var rc = refCode(broker);
    if (rc) {
      copyText(rc);
      toast(t("rc.toast").replace("{c}", rc).replace("{b}", BROKERS[broker].name));
    }
  });

  function devBar() {
    if (!IS_LOCAL || /[?&]nodev\b/.test(location.search)) return;
    var missing = Object.keys(BROKERS).filter(function (k) { return !refUrl(k); }).map(function (k) { return BROKERS[k].key; });
    if (!missing.length) return;
    var bar = document.createElement("div");
    bar.className = "dev-bar";
    bar.innerHTML = "⚠ Локалдык текшерүү: партнёрдук шилтемелер коюла элек — <code>assets/js/config.js → " + missing.join(", ") + "</code>. (Бул тилке сайтта көрүнбөйт.)";
    document.body.insertBefore(bar, document.body.firstChild);
    console.warn("[AITRADING] Заглушки в config.js: " + missing.join(", "));
  }

  /* ---------- Toast ---------- */
  var toastEl, toastTimer;
  function toast(msg) {
    if (!toastEl) {
      toastEl = document.createElement("div");
      toastEl.className = "toast";
      toastEl.setAttribute("role", "status");
      document.body.appendChild(toastEl);
    }
    toastEl.textContent = msg;
    toastEl.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toastEl.classList.remove("show"); }, 2600);
  }

  /* ---------- Меню ---------- */
  function initNav() {
    var burger = document.querySelector(".burger");
    var nav = document.getElementById("nav");
    if (!burger || !nav) return;
    burger.addEventListener("click", function () {
      var open = burger.getAttribute("aria-expanded") !== "true";
      burger.setAttribute("aria-expanded", String(open));
      nav.classList.toggle("open", open);
    });
    nav.addEventListener("click", function (e) {
      if (e.target.closest("a")) {
        burger.setAttribute("aria-expanded", "false");
        nav.classList.remove("open");
      }
    });
  }

  function fillYear() {
    document.querySelectorAll("[data-year]").forEach(function (el) { el.textContent = new Date().getFullYear(); });
  }

  /* ---------- Соцтармактар (config.js → SOCIAL): футерде иконкалар + «Жазылыңыз» блогу ---------- */
  var SOC_ICON = {
    youtube: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M23 7.2a3 3 0 0 0-2.1-2.1C19 4.6 12 4.6 12 4.6s-7 0-8.9.5A3 3 0 0 0 1 7.2 31 31 0 0 0 .5 12a31 31 0 0 0 .5 4.8 3 3 0 0 0 2.1 2.1c1.9.5 8.9.5 8.9.5s7 0 8.9-.5a3 3 0 0 0 2.1-2.1 31 31 0 0 0 .5-4.8 31 31 0 0 0-.5-4.8zM9.7 15.1V8.9l5.8 3.1-5.8 3.1z"/></svg>',
    telegram: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M21.9 4.3 18.6 19.8c-.2 1.1-.9 1.4-1.8.9l-5-3.7-2.4 2.3c-.3.3-.5.5-1 .5l.4-5.1 9.3-8.4c.4-.4-.1-.6-.6-.2L6 13.3l-5-1.6c-1.1-.3-1.1-1.1.2-1.6L20.4 2.7c.9-.3 1.7.2 1.5 1.6z"/></svg>',
    instagram: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10zm0 8.2a3.2 3.2 0 1 1 0-6.4 3.2 3.2 0 0 1 0 6.4zM17.3 5.5a1.2 1.2 0 1 0 0 2.4 1.2 1.2 0 0 0 0-2.4zM12 2.2c-2.7 0-3 0-4 .1-1 0-1.8.2-2.4.5-.7.3-1.2.6-1.8 1.2-.6.6-.9 1.1-1.2 1.8-.3.6-.5 1.4-.5 2.4-.1 1-.1 1.3-.1 4s0 3 .1 4c0 1 .2 1.8.5 2.4.3.7.6 1.2 1.2 1.8.6.6 1.1.9 1.8 1.2.6.3 1.4.5 2.4.5 1 .1 1.3.1 4 .1s3 0 4-.1c1 0 1.8-.2 2.4-.5.7-.3 1.2-.6 1.8-1.2.6-.6.9-1.1 1.2-1.8.3-.6.5-1.4.5-2.4.1-1 .1-1.3.1-4s0-3-.1-4c0-1-.2-1.8-.5-2.4a4.9 4.9 0 0 0-3-3c-.6-.3-1.4-.5-2.4-.5-1-.1-1.3-.1-4-.1zm0 1.8c2.6 0 2.9 0 4 .1.9 0 1.5.2 1.8.3.5.2.8.4 1.1.7.3.3.6.7.7 1.1.1.3.3.9.3 1.8.1 1 .1 1.4.1 4s0 2.9-.1 4c0 .9-.2 1.5-.3 1.8-.2.5-.4.8-.7 1.1-.3.3-.7.6-1.1.7-.3.1-.9.3-1.8.3-1 .1-1.4.1-4 .1s-2.9 0-4-.1c-.9 0-1.5-.2-1.8-.3a3 3 0 0 1-1.1-.7 3 3 0 0 1-.7-1.1c-.1-.3-.3-.9-.3-1.8-.1-1-.1-1.4-.1-4s0-2.9.1-4c0-.9.2-1.5.3-1.8.2-.5.4-.8.7-1.1.3-.3.7-.6 1.1-.7.3-.1.9-.3 1.8-.3 1-.1 1.4-.1 4-.1z"/></svg>',
    tiktok: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M16.6 2h-3.3v13.2a2.9 2.9 0 1 1-2.9-2.9c.3 0 .6 0 .9.1V9a6.3 6.3 0 1 0 5.3 6.2V8.6a7.9 7.9 0 0 0 4.4 1.4V6.7a4.6 4.6 0 0 1-4.4-4.7z"/></svg>'
  };
  var SOC_ORDER = ["youtube", "telegram", "instagram", "tiktok"];
  var SOC_NAME = { youtube: "YouTube", telegram: "Telegram", instagram: "Instagram", tiktok: "TikTok" };
  var SOC_TXT = {
    ky: { title: "Бизди ээрчиңиз", sub: "Түз эфирлер, сигналдар, сабактар жана рыноктун жаңылыктары — ар күнү.",
          youtube: "Түз эфирлер жана сабактар", telegram: "Сигналдар жана жаңылыктар", instagram: "Күнүмдүк постор жана сторис", tiktok: "Кыска видеолор" },
    ru: { title: "Подписывайтесь", sub: "Прямые эфиры, сигналы, уроки и новости рынка — каждый день.",
          youtube: "Прямые эфиры и уроки", telegram: "Сигналы и новости", instagram: "Посты и сторис каждый день", tiktok: "Короткие видео" }
  };
  function socLinks() {
    var social = CFG.SOCIAL || {};
    return SOC_ORDER.filter(function (k) { return /^https:\/\//i.test(String(social[k] || "").trim()); })
      .map(function (k) { return { k: k, u: String(social[k]).trim() }; });
  }
  function socBand() {
    var L = SOC_TXT[lang === "ru" ? "ru" : "ky"], links = socLinks();
    if (!links.length) return "";
    return '<div class="container"><div class="soc-band-in"><div class="soc-band-head"><h2>' + L.title + "</h2><p>" + L.sub + "</p></div>" +
      '<div class="soc-cards">' + links.map(function (x) {
        return '<a class="soc-card soc-' + x.k + '" href="' + x.u + '" target="_blank" rel="noopener" data-track="social_' + x.k + '">' +
          '<span class="soc-ico">' + SOC_ICON[x.k] + "</span><span><b>" + SOC_NAME[x.k] + "</b><small>" + L[x.k] + "</small></span></a>";
      }).join("") + "</div></div></div>";
  }
  function initSocial() {
    var links = socLinks();
    document.querySelectorAll("[data-social]").forEach(function (box) {
      box.innerHTML = "";
      links.forEach(function (x) {
        var a = document.createElement("a");
        a.href = x.u;
        a.target = "_blank";
        a.rel = "noopener";
        a.className = "soc-" + x.k;
        a.setAttribute("aria-label", SOC_NAME[x.k]);
        a.innerHTML = SOC_ICON[x.k] + "<span>" + SOC_NAME[x.k] + "</span>";
        box.appendChild(a);
      });
      if (!box.children.length) box.hidden = true;
    });
    if (!links.length) return;
    // «Жазылыңыз» блогу: башкы бетте hero'дон кийин, калган беттерде футердин алдында
    var spots = [];
    var hero = document.querySelector("main > section.hero, section.hero");
    if (hero) spots.push(["after", hero]);
    var foot = document.querySelector("[data-site-footer]") || document.querySelector("footer");
    if (foot && !hero) spots.push(["before", foot]);
    spots.forEach(function (sp) {
      var el = document.createElement("section");
      el.className = "soc-band";
      el.setAttribute("data-soc-band", "");
      el.innerHTML = socBand();
      if (sp[0] === "after") sp[1].parentNode.insertBefore(el, sp[1].nextSibling);
      else sp[1].parentNode.insertBefore(el, sp[1]);
    });
    if (window.AT && AT.onLang) AT.onLang(function () { document.querySelectorAll("[data-soc-band]").forEach(function (b) { b.innerHTML = socBand(); }); });
    document.addEventListener("click", function (e) {
      var a = e.target.closest && e.target.closest("a.soc-card, [data-social] a");
      if (a && window.AT && AT.track) AT.track("social_click", { to: (a.className.match(/soc-(\w+)/) || [])[1] || "" });
    }, true);
  }

  /* ---------- TradingView виджеттери ---------- */
  var TV_SRC = "https://s3.tradingview.com/external-embedding/embed-widget-";

  function mountTV(host, type, config, opts) {
    opts = opts || {};
    host.innerHTML = "";
    host.classList.add("tv-box");

    var wrap = document.createElement("div");
    wrap.className = "tradingview-widget-container";
    var inner = document.createElement("div");
    inner.className = "tradingview-widget-container__widget";
    inner.style.height = opts.copyright !== false ? "calc(100% - 28px)" : "100%";
    wrap.appendChild(inner);

    if (opts.copyright !== false) {
      var copy = document.createElement("div");
      copy.className = "tradingview-widget-copyright";
      copy.innerHTML = '<a href="https://ru.tradingview.com/" rel="noopener nofollow" target="_blank">TradingView</a>';
      wrap.appendChild(copy);
    }

    var loader = document.createElement("div");
    loader.className = "tv-loading";
    loader.setAttribute("aria-hidden", "true");
    host.appendChild(wrap);
    if (opts.loader !== false) host.appendChild(loader);

    var script = document.createElement("script");
    script.type = "text/javascript";
    script.async = true;
    script.src = TV_SRC + type + ".js";
    script.text = JSON.stringify(config);
    var failed = false;
    function fail() {
      if (failed) return;
      failed = true;
      loader.remove();
      var link = opts.fallbackUrl || "https://ru.tradingview.com/markets/";
      var fb = document.createElement("div");
      fb.className = "tv-fallback";
      fb.innerHTML = "<p>" + t("js.tv_fail") + "</p><a href=\"" + link + "\" target=\"_blank\" rel=\"noopener nofollow\">" + t("js.tv_open") + " ↗</a>";
      host.appendChild(fb);
    }
    script.onerror = fail;
    wrap.appendChild(script);

    var started = Date.now();
    var timer = setInterval(function () {
      var frame = wrap.querySelector("iframe");
      if (frame) {
        clearInterval(timer);
        var done = function () { loader.remove(); };
        frame.addEventListener("load", done);
        setTimeout(done, 2500);
      } else if (Date.now() - started > 15000 || failed) {
        clearInterval(timer);
        fail();
      }
    }, 250);
  }

  /* Экранга жакындаганда гана жүктөө / Ленивая загрузка */
  function lazy(el, fn) {
    if (!("IntersectionObserver" in window)) return fn();
    var io = new IntersectionObserver(function (entries) {
      if (entries.some(function (e) { return e.isIntersecting; })) {
        io.disconnect();
        fn();
      }
    }, { rootMargin: "400px 0px" });
    io.observe(el);
  }

  var TICKER = [
    { proName: "FX:EURUSD", title: "EUR/USD" },
    { proName: "OANDA:XAUUSD", title: "XAU/USD" },
    { proName: "BINANCE:BTCUSDT", title: "BTC/USDT" },
    { proName: "NASDAQ:AAPL", title: "Apple" },
    { proName: "BINANCE:ETHUSDT", title: "ETH/USDT" },
    { proName: "NASDAQ:TSLA", title: "Tesla" },
    { proName: "FX:GBPUSD", title: "GBP/USD" },
    { proName: "NASDAQ:NVDA", title: "NVIDIA" },
    { proName: "BINANCE:SOLUSDT", title: "SOL/USDT" }
  ];

  function initTicker() {
    var el = document.querySelector("[data-tv-ticker]");
    if (!el) return;
    mountTV(el, "ticker-tape", {
      symbols: TICKER,
      showSymbolLogo: true,
      isTransparent: true,
      displayMode: "adaptive",
      colorTheme: "dark",
      locale: "ru",
      largeChartUrl: chartUrl()   // басканда — өз терезебиз (chartbox.js), TradingView'га кетпейт
    }, { copyright: false, loader: false });
  }

  /* ---------- Символдун өз терезеси (assets/js/chartbox.js) ----------
     TradingView виджеттери символ басылганда largeChartUrl'га «?tvwidgetsymbol=…» кошуп өтөт.
     largeChartUrl = ушул беттин дареги + «#tv» болгондо, өтүү хэш гана болуп калат: бет кайра
     жүктөлбөйт, биз hashchange'ди кармап, терезени ачабыз. */
  function chartUrl() { return location.href.split("#")[0] + "#tv"; }
  function titleFor(sym) {
    var x = TICKER.filter(function (s) { return s.proName === sym; })[0];
    return x ? x.title : "";
  }
  var cbxP = null;
  function withChartbox(fn) {
    if (!cbxP) {
      cbxP = new Promise(function (res, rej) {
        var s = document.createElement("script");
        s.src = "assets/js/chartbox.js";
        s.onload = function () { window.ATChart ? res(window.ATChart) : rej(); };
        s.onerror = function () { cbxP = null; rej(); };
        document.head.appendChild(s);
      });
    }
    cbxP.then(fn).catch(function () { toast(t("js.tv_fail")); });
  }
  function openChart(sym, o) {
    o = o || {};
    if (!o.title) o.title = titleFor(String(sym).toUpperCase());
    withChartbox(function (C) { C.open(sym, o); });
  }
  /* Көпчүлүк браузерде TradingView largeChartUrl'ду ЖАҢЫ өтмөктө ачат. Ошондо жаңы өтмөк
     басылган өтмөккө (BroadcastChannel) «ушул символду ач» деп айтат да, өзү жабылат —
     колдонуучу ошол эле бетте калат. Жооп болбосо (мисалы, шилтеме түз ачылса) — терезе ушул жерде ачылат. */
  var chartCh = null, lastTvClick = 0;
  function chartChannel() {
    if (chartCh === null) { try { chartCh = new BroadcastChannel("aitrading-chart"); } catch (e) { chartCh = false; } }
    return chartCh;
  }
  function chartHandoff(sym) {
    var c = chartChannel();
    if (!c || history.length > 1) return Promise.resolve(false);
    var id = Math.random().toString(36).slice(2);
    return new Promise(function (res) {
      var done = false;
      function on(e) {
        var d = e.data || {};
        if (d.type === "ack" && d.id === id) { done = true; c.removeEventListener("message", on); res(true); }
      }
      c.addEventListener("message", on);
      c.postMessage({ type: "open", sym: sym, id: id });
      setTimeout(function () { if (!done) { c.removeEventListener("message", on); res(false); } }, 700);
    });
  }
  /* WhatsApp заявкасы (брокерде катталуудан мурун) жана сигналдарга доступ — assets/js/access.js */
  function initAccessGate() {
    if (window.ATGate || document.querySelector('script[src$="access.js"]')) return;
    var s = document.createElement("script");
    s.src = "assets/js/access.js";
    document.head.appendChild(s);
  }
  function initChartLinks() {
    // Басылган өтмөк: TradingView iframe'ин басканда бет «blur» болот, фокус ошол iframe'де
    window.addEventListener("blur", function () {
      var a = document.activeElement;
      if (a && a.tagName === "IFRAME" && /tradingview/i.test(a.src || "")) lastTvClick = Date.now();
    });
    var c = chartChannel();
    if (c) c.addEventListener("message", function (e) {
      var d = e.data || {};
      if (d.type === "open" && d.sym && Date.now() - lastTvClick < 10000) {
        lastTvClick = 0;
        c.postMessage({ type: "ack", id: d.id });
        openChart(d.sym, {});
      }
    });
    function route(initial) {
      var h = location.hash;
      if (/^#tv\b/.test(h)) {
        var m = /[?&]tvwidgetsymbol=([^&#]+)/.exec(h);
        if (m && initial) {
          var sym = decodeURIComponent(m[1]);
          chartHandoff(sym).then(function (ok) {
            if (ok) { window.close(); setTimeout(function () { openChart(sym, { from: "load" }); }, 400); }   // жабылбаса — ушул жерде ачабыз
            else openChart(sym, { from: "load" });
          });
        } else if (m) openChart(decodeURIComponent(m[1]), { from: "tv" });
        else { try { history.replaceState(null, "", location.pathname + location.search); } catch (e) { /* */ } }
      } else if (initial && h === "#chart") {
        withChartbox(function (C) { C.restore(); });
      }
    }
    window.addEventListener("hashchange", function () { route(false); });
    route(true);
  }

  /* ---------- Телефон: тиркеме (PWA) жана билдирмелер ----------
     Орнотуу жана билдирмелер https сайтта гана иштейт (localhost — текшерүү үчүн). */
  var SECURE = !!window.isSecureContext;
  var NOTIFY_KEY = "aitrading-notify", PWA_KEY = "aitrading-pwa-hide";
  var deferredPrompt = null, pwaEl = null;
  function isStandalone() { return (window.matchMedia && matchMedia("(display-mode: standalone)").matches) || navigator.standalone === true; }
  function isIOS() { return /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1); }
  function isPhone() { return (window.matchMedia && matchMedia("(pointer: coarse)").matches) || window.innerWidth < 760; }

  function initPWA() {
    if ("serviceWorker" in navigator && SECURE && !/[?&]nosw\b/.test(location.search)) {
      window.addEventListener("load", function () {
        navigator.serviceWorker.register("sw.js").catch(function (e) { if (IS_LOCAL) console.warn("[sw]", e); });
      });
    }
    window.addEventListener("beforeinstallprompt", function (e) {
      e.preventDefault();
      deferredPrompt = e;
      maybeShowInstall();
    });
    window.addEventListener("appinstalled", function () {
      deferredPrompt = null;
      if (pwaEl) pwaEl.remove();
      track("pwa_installed", {});
      toast(t("pwa.done"));
    });
    if (/[?&]src=app\b/.test(location.search) || isStandalone()) document.documentElement.classList.add("is-app");
    // iPhone'до орнотуу баскычы жок — кыска нускама көрсөтөбүз
    if (isIOS() && !isStandalone() && isPhone()) setTimeout(maybeShowInstall, 4000);
    document.addEventListener("click", function (e) {
      var b = e.target.closest && e.target.closest("[data-install]");
      if (!b) return;
      e.preventDefault();
      openInstall(true);
    });
  }

  function hiddenRecently() { var v = +store(PWA_KEY) || 0; return Date.now() - v < 7 * 864e5; }
  function maybeShowInstall() {
    if (isStandalone() || hiddenRecently() || !isPhone()) return;
    openInstall(false);
  }
  /* full=true — футердеги «Тиркеме» шилтемесинен: толук нускама */
  function openInstall(full) {
    if (isStandalone()) { toast(t("pwa.already")); return; }
    if (pwaEl) pwaEl.remove();
    var how;
    if (deferredPrompt) how = '<button type="button" class="btn btn-mint btn-sm" data-pwa-go>' + t("pwa.install") + "</button>";
    else if (isIOS()) how = '<p class="pwa-how">' + t("pwa.ios") + "</p>";
    else how = '<p class="pwa-how">' + t("pwa.android") + "</p>";
    pwaEl = document.createElement("div");
    pwaEl.className = "pwa-card" + (full ? " full" : "");
    pwaEl.setAttribute("role", "dialog");
    pwaEl.innerHTML =
      '<img src="assets/img/icon-192.png" alt="" width="44" height="44">' +
      '<div class="pwa-txt"><b>' + t("pwa.title") + "</b><span>" + t("pwa.sub") + "</span>" + how +
      (!SECURE ? '<p class="pwa-warn">' + t("pwa.insecure") + "</p>" : "") + "</div>" +
      '<button type="button" class="pwa-x" aria-label="×" data-pwa-x>×</button>';
    document.body.appendChild(pwaEl);
    requestAnimationFrame(function () { pwaEl && pwaEl.classList.add("show"); });
    pwaEl.addEventListener("click", function (e) {
      if (e.target.closest("[data-pwa-x]")) { store(PWA_KEY, String(Date.now())); pwaEl.remove(); pwaEl = null; return; }
      if (e.target.closest("[data-pwa-go]") && deferredPrompt) {
        deferredPrompt.prompt();
        deferredPrompt.userChoice.then(function (c) { track("pwa_prompt", { outcome: c.outcome }); deferredPrompt = null; if (pwaEl) { pwaEl.remove(); pwaEl = null; } });
      }
    });
    track("pwa_card", { full: !!full });
  }

  /* Билдирмелер. Абал: unsupported | insecure | ios-home | default | granted | denied */
  function notifyState() {
    if (!SECURE) return "insecure";
    if (!("Notification" in window)) return isIOS() && !isStandalone() ? "ios-home" : "unsupported";
    return Notification.permission;
  }
  function notifyOn() { return store(NOTIFY_KEY) === "1" && notifyState() === "granted"; }
  function setNotify(on) {
    if (!on) { store(NOTIFY_KEY, "0"); return Promise.resolve(false); }
    var st = notifyState();
    var ask = st === "default" ? Promise.resolve(Notification.requestPermission()) : Promise.resolve(st);
    return ask.then(function (p) {
      track("notify_perm", { p: p });
      if (p === "granted") {
        store(NOTIFY_KEY, "1");
        notify(t("ntf.on_t"), t("ntf.on_b"), "forecast.html", "aitrading-hello");
        return true;
      }
      store(NOTIFY_KEY, "0");
      toast(t("ntf.st_" + (p === "denied" ? "denied" : p === "insecure" ? "insecure" : p === "ios-home" ? "ios" : "unsupported")));
      return false;
    });
  }
  function notify(title, body, url, tag) {
    if (notifyState() !== "granted") return Promise.resolve(false);
    var opts = { body: body || "", icon: "assets/img/icon-192.png", badge: "assets/img/icon-192.png", tag: tag || "aitrading", renotify: true, vibrate: [90, 50, 90], data: { url: url || "forecast.html" } };
    function viaPage() {
      try {
        var n = new Notification(title, opts);
        n.onclick = function () { window.focus(); if (url) location.href = url; n.close(); };
        return true;
      } catch (e) { return false; }   // Android'до бул жол жок — SW керек
    }
    if (!("serviceWorker" in navigator)) return Promise.resolve(viaPage());
    return navigator.serviceWorker.getRegistration().then(function (r) {
      if (r && r.showNotification) return r.showNotification(title, opts).then(function () { return true; });
      return viaPage();
    }).catch(viaPage);
  }

  /* ---------- Старт ---------- */
  function init() {
    renderChrome();
    initPWA();
    initAnalytics();
    document.querySelectorAll("[data-lang]").forEach(function (b) {
      b.addEventListener("click", function () { applyLang(b.getAttribute("data-lang")); track("lang_switch", { lang: b.getAttribute("data-lang") }); });
    });
    initNav();
    initSocial();
    devBar();
    applyLang(initialLang(), true);
    initTicker();
    initChartLinks();
    initAccessGate();
    initPanels();
    initAlerts();
  }

  /* «⚠️ Шашылыш» плашкасы жана билдирмелер (assets/js/alerts.js) — бардык беттерде */
  function initAlerts() {
    if (window.ATAlerts || document.querySelector('script[src$="alerts.js"]')) return;
    var s = document.createElement("script");
    s.src = "assets/js/alerts.js";
    s.async = true;
    document.body.appendChild(s);
  }


  window.AT = {
    t: t,
    lang: function () { return lang; },
    onLang: function (fn) { listeners.push(fn); },
    mountTV: mountTV,
    chartUrl: chartUrl,
    openChart: openChart,
    lazy: lazy,
    toast: toast,
    track: track,
    refUrl: refUrl,
    botUrl: botUrl,
    applyRefLinks: applyRefLinks,
    store: store,
    notify: notify,
    notifyOn: notifyOn,
    notifyState: notifyState,
    setNotify: setNotify,
    openInstall: openInstall
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
