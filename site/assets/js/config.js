/* ==========================================================================
   AITRADING.KG — сайттын жөндөөлөрү (настройки сайта)
   Шилтемелерди ушул файлда гана алмаштырыңыз.
   Ссылки меняйте только в этом файле.
   ========================================================================== */

window.AITRADING_CONFIG = {
  /* ⚠️ ПАРТНЁРДУК ШИЛТЕМЕЛЕР / ПАРТНЁРСКИЕ ССЫЛКИ
     «BinoDex'те катталуу» баскычтары → BINODEX_REF_URL
     «BingX'те катталуу» баскычтары  → BINGX_REF_URL
     Шилтемени партнёрдук кабинеттен толук көчүрүп, тырмакчанын ичине коюңуз
     (https:// менен башталышы керек). Пока здесь заглушки — кнопки показывают
     «ссылка скоро появится» и никуда не ведут. */
  BINODEX_REF_URL: "https://bdclick.app/smart/qsu6g8",       // → binodex.app?r=qsu6g8 (текшерилди 22.11.2026)
  BINGX_REF_URL: "https://bingxdao.com/partner/TRADERKG",    // → bingx.com/partner/TRADERKG (текшерилди 22.11.2026)

  /* РЕФЕРАЛ КОДУ: катталуу формасында жазылуучу код. Сайтта «Көчүрүү» баскычы менен көрүнөт,
     катталуу баскычын басканда өзү көчүрүлөт, ботто да айтылат. Бош болсо — көрсөтүлбөйт.
     Реферальный код для формы регистрации: показывается с кнопкой «Копировать», копируется при нажатии. */
  REF_CODES: {
    binodex: "traderkg",
    bingx: ""
  },

  /* АНАЛИТИКА (конверсияны өлчөө): ID коюлса гана иштейт.
     ga4: Google Analytics 4 — "G-XXXXXXX"; yandex: Яндекс Метрика — сан, мисалы "98765432".
     Окуялар: register_click (брокер баскычы), asset_open (тренд блогу), asset_share, tg_copy, lang_switch.
     Аналитика: если вставить ID, будут считаться клики по регистрации и другие события. */
  ANALYTICS: {
    ga4: "",
    yandex: ""
  },

  /* BinoDex API (котировкалар үчүн). Документация келгенде толтурулат. Ачкыч (key) бул жерге ЖАЗЫЛБАЙТ —
     ал прокси-сервердин сырларында сакталат. Бош болсо: Kraken/Binance ачык маалыматы колдонулат. */
  BINODEX_API: "",

  /* «⚠️ ШАШЫЛЫШ» ПЛАШКАСЫ / ПЛАШКА «СРОЧНО» (бардык беттердин үстүндө, ботто жана тиркемеде да).
     Эреже: себеттеги монеталардын 24 сааттык же 1 сааттык өзгөрүүсүнүн МЕДИАНАСЫ (Binance, запасы BingX).
     |медиана 24 с| ≥ move24 % же |медиана 1 с| ≥ move1h % болсо — плашка жана билдирме.
     Правило: медиана изменения монет корзины за 24 ч или за 1 ч (Binance, запасной — BingX).
     Сайт (assets/js/alerts.js) жана бот (tools/market_pulse.py) ушул жерден окушат. */
  ALERTS: {
    basket: ["BTC", "ETH", "XRP", "BNB", "SOL", "DOGE", "TRX", "ADA", "LINK", "AVAX"],
    move24: 5,
    move1h: 3
  },

  /* БЕЛГИЛҮҮ АДАМДАР (X / Twitter) — «Жаңылыктар» бетинде «кимдерди көзөмөлдөйбүз» тизмеси.
     Твиттин өзүн бот аркылуу жарыялайсыз: ADMIN PANEL → 🐦 Твит (алгач Telegram-каналга, анан сайтка).
     Известные люди в X: список «за кем следим». Сам твит публикуется через бота (сначала канал, потом сайт). */
  FAMOUS_X: [
    { handle: "elonmusk", name: "Илон Маск" },
    { handle: "realDonaldTrump", name: "Дональд Трамп" },
    { handle: "saylor", name: "Майкл Сэйлор" },
    { handle: "CathieDWood", name: "Кэти Вуд" },
    { handle: "RayDalio", name: "Рэй Далио" },
    { handle: "federalreserve", name: "ФРС США" },
    { handle: "cz_binance", name: "Чанпэн Чжао (CZ)" },
    { handle: "VitalikButerin", name: "Виталик Бутерин" },
    { handle: "BillAckman", name: "Билл Экман" },
    { handle: "PeterSchiff", name: "Питер Шифф" }
  ],

  /* Сайттын дареги / адрес сайта */
  SITE_URL: "https://aitrading.kg",

  /* TELEGRAM-БОТ: @BotFather'де түзгөн ботуңуздун шилтемеси, мисалы "https://t.me/aitrading_kg_bot".
     Бош болсо — «Ботко кирүү» баскычтары «бот жакында ачылат» дейт.
     Ссылка на вашего бота, например "https://t.me/aitrading_kg_bot". Пусто — кнопки пишут «бот скоро откроется». */
  TELEGRAM_BOT_URL: "https://t.me/TRADERKG_AI_Bot",

  /* ВИДЕО-НУСКАМАЛАР / ВИДЕОИНСТРУКЦИИ — ар бир кадамдын астында кыска видео («Окуу» жана «Катталуу» беттеринде, ботто да).
     Кое турган нерсе: YouTube шилтемеси (https://youtu.be/…, https://www.youtube.com/watch?v=…, …/shorts/…)
     же сайттын ичиндеги файл, мисалы "assets/video/bingx-register.mp4". Бош болсо — «Видео жакында» деген белги.
     Вставьте ссылку на YouTube или путь к файлу mp4. Пусто — плашка «видео скоро».
     ЭКИ ТИЛ / ДВА ЯЗЫКА: орусча версиясы — ошол эле ачкыч + "@ru" (мисалы "binodex-register@ru").
     Ал бош болсо, орусча режимде да кыргызча видео көрсөтүлөт.
     Русская версия — тот же ключ + "@ru". Если её нет, в русском режиме показывается кыргызская. */
  VIDEOS: {
    "learn-main": "https://youtu.be/h1hzmkeARuA",   // Окуу: башкы чоң видео-сабак (BingX нөлдөн: каттоо, P2P, спот, фьючерс)
    "basics": "",               // Окуу 1: негизги сөздөр
    "bingx-register": "",       // BingX: катталуу (шилтеме менен)
    "bingx-2fa": "",            // BingX: аккаунтту коргоо (2FA)
    "bingx-kyc": "",            // BingX: KYC
    "bingx-usdt": "",           // BingX: USDT менен толуктоо (P2P / карта)
    "bingx-spot": "",           // BingX: USDT'ни спот эсебине которуу
    "bingx-find": "",           // BingX: акцияны (токенди) табуу
    "bingx-buy": "",            // BingX: 50 долларга сатып алуу
    "bingx-sell": "",           // BingX: текшерүү жана сатуу
    "bingx-uid": "",            // BingX: UID'ни көчүрүү
    "binodex-register": "assets/video/binodex-register.mp4",   // BinoDex: катталуу + реферал коду traderkg
    "binodex-demo": "",         // BinoDex: демо-эсепке өтүү
    "binodex-asset": "",        // BinoDex: активди тандоо
    "binodex-amount": "",       // BinoDex: сумма жана мөөнөт
    "binodex-direction": "",    // BinoDex: багытты тандоо (өйдө/ылдый)
    "binodex-journal": "",      // BinoDex: натыйжаны талдоо, дептер
    "binodex-real": "assets/video/binodex-real.mp4",           // BinoDex: реалдуу эсеп жана толуктоо
    "binodex-id": "assets/video/binodex-id.mp4",               // BinoDex: ID кайда
    "signals": "",              // ⭐ Сигналды кантип окуу жана демодо текшерүү
    "bot-id": "assets/video/bot-id.mp4",                       // ID'ни Telegram-ботко жөнөтүү (текшерүү: катталуу + толуктоо)
    "sec-antiphishing": "",   // Коопсуздук: анти-фишинг коду
    "sec-whitelist": "",      // Коопсуздук: чыгаруу даректеринин ак тизмеси
    "sec-cold-wallet": "",    // Коопсуздук: муздак капчыкты орнотуу
    "sec-withdraw": "",       // Коопсуздук: биржадан муздак капчыкка которуу
    "sec-scam": "",           // Коопсуздук: алдамчыны таануу
    "rules": "",                // Тобокелдиктин эрежелери

    /* Орусча версиялар (үн жана жазуулар орусча) */
    "binodex-register@ru": "assets/video/binodex-register-ru.mp4",
    "binodex-id@ru": "assets/video/binodex-id-ru.mp4",
    "binodex-real@ru": "assets/video/binodex-real-ru.mp4",
    "bot-id@ru": "assets/video/bot-id-ru.mp4"
  },

  /* МУЗДАК КАПЧЫКТАР («Коопсуздук» бети): өндүрүүчүнүн партнёрдук шилтемеси. Бош болсо — расмий сайт ачылат.
     Холодные кошельки: партнёрская ссылка производителя. Пусто — открывается официальный сайт. */
  WALLET_REF_URLS: {
    tangem: "",
    ledger: "",
    trezor: "",
    keystone: ""
  },

  /* Соцтармактар: шилтеме коюлса, футерде жана «Маркетинг» бетинде баскыч пайда болот.
     Соцсети: если вставить ссылку, появится кнопка в футере и на странице «Маркетинг». */
  SOCIAL: {
    youtube: "https://www.youtube.com/@TRADER_KG",
    telegram: "https://t.me/+kGTaMnkOHGxjMjk6",
    instagram: "https://www.instagram.com/kg.million_/",
    tiktok: "https://www.tiktok.com/@manimenkg_official"
  }
};
