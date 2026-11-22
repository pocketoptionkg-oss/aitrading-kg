"""AITRADING.KG Telegram-бот: меню бөлүмдөрү, брокерде катталуу (окуу менен), ID + толуктоо + баланс текшерүү,
40 күн эрежеси, ADMIN PANEL (баскычтуу рассылка, заявкалар, трейдерлер, статистика) жана ⭐ сигналдар доступу ачыктарга.

    python tools/tg_bot.py               # бот (ПКда: Телеграм_бот.bat)
    python tools/tg_bot.py --setup       # бир жолу: Telegram токени, админ чаты, BingX Agent API ачкычтары
    python tools/tg_bot.py --no-signals  # сигнал сканерисиз (меню жана админка гана)

Чөйрө өзгөрмөлөрү (кодго жана файлдарга жазылбайт):
  TELEGRAM_BOT_TOKEN   — @BotFather берген токен
  TELEGRAM_CHAT_ID     — админдин жеке чаты (оң сан) же сигнал каналы (-100…)
  TELEGRAM_ADMIN_IDS   — кошумча админдер, үтүр менен (милдеттүү эмес)
  BINGX_API_KEY / BINGX_API_SECRET — BingX Agent API (окуу гана): UID, толуктоо, таза актив
  TG_MIN_BALANCE       — BingX'те доступ үчүн минималдуу таза актив, USDT (демейки 0: толуктоо болсо жетиштүү)
BinoDex'тин API'си азырынча жок: BinoDex ID'лерин админ ✅/❌ менен ырастайт (binodex_check() — заглушка).
"""
import argparse
import base64
import hashlib
import hmac
import html
import json
import secrets
import os
import re
import sqlite3
import sys
import threading
import time
import traceback
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tg_signals as S  # noqa: E402

HERE = S.HERE
DB_PATH = os.environ.get("TG_DB") or os.path.join(HERE, "tg_bot.db")
CONFIG_JS = os.path.join(S.ROOT, "site", "assets", "js", "config.js")
ACCESS_DAYS, WARN_DAYS = 40, 35
DAY = 86400000
E = html.escape


def _config_js():
    try:
        with open(CONFIG_JS, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def _js_map(js, name):
    """config.js'теги жөнөкөй объект: NAME: { "key": "value", key2: "…" } → dict."""
    m = re.search(name + r"\s*:\s*\{([^}]*)\}", js)
    return {k: v for k, v in re.findall(r'"?([A-Za-z0-9_@-]+)"?\s*:\s*"([^"]*)"', m.group(1))} if m else {}


def ref_links():
    """Партнёрдук шилтемелер сайттагы config.js'тен (бир булак). Заглушка болсо — None."""
    js = _config_js()
    out = {"bingx": None, "binodex": None}
    for k, name in (("bingx", "BINGX_REF_URL"), ("binodex", "BINODEX_REF_URL")):
        m = re.search(name + r'\s*:\s*"([^"]*)"', js)
        if m and m.group(1).startswith("https://"):
            out[k] = m.group(1)
    return out


def ref_codes():
    """config.js → REF_CODES: катталуу формасына жазылуучу реферал коддору."""
    return {k: v.strip() for k, v in _js_map(_config_js(), "REF_CODES").items() if re.match(r"^[A-Za-z0-9_-]{2,40}$", v.strip())}


def video_links():
    """config.js → VIDEOS: видео-нускамалар. Сайттын ичиндеги файл болсо — толук дарекке айландырылат."""
    out = {}
    for k, v in _js_map(_config_js(), "VIDEOS").items():
        v = v.strip()
        if v.startswith("https://"):
            out[k] = v
        elif re.match(r"^(\./|/)?assets/.+\.(mp4|webm|mov)$", v, re.I):
            out[k] = S.SITE_URL + "/" + re.sub(r"^\./|^/", "", v)
    return out


def video_for(key, lang):
    """Колдонуучунун тилиндеги видео: орусча — "key@ru", жок болсо кыргызчасы."""
    if not key:
        return None
    v = video_links()
    return (v.get(key + "@ru") if lang == "ru" else None) or v.get(key)


# ======================================================================
#  Тексттер (KG / RU)
# ======================================================================
MENU = {
    "kg": [["⭐ Сигналдар", "📝 Катталуу"], ["📚 Окуу", "👤 Профиль"], ["🌐 Сайт", "💬 Колдоо", "🌍 Тил / Язык"]],
    "ru": [["⭐ Сигналы", "📝 Регистрация"], ["📚 Обучение", "👤 Профиль"], ["🌐 Сайт", "💬 Поддержка", "🌍 Тил / Язык"]],
}
ADMIN_BTN = "🛠 ADMIN PANEL"
ACTIONS = {}
for _lang, rows in MENU.items():
    for _act, _txt in zip(["signals", "register", "learn", "profile", "site", "support", "lang"], [b for r in rows for b in r]):
        ACTIONS[_txt] = _act
ACTIONS[ADMIN_BTN] = "admin"
CMDS = {"/start": "start", "/signals": "signals", "/register": "register", "/learn": "learn", "/profile": "profile",
        "/help": "support", "/lang": "lang", "/admin": "admin", "/find": "find"}

TX = {
    "kg": {
        "welcome": "Салам, {name}! 👋\nБул — <b>AITRADING.KG</b> боту (TRADER KG).\n\n"
                   "⭐ <b>ИИ сигналдары</b>: BinoDex (кыска мөөнөт, ▲/▼) жана BingX спот (▲ сатып алуу). "
                   "Сигнал — ыктымалдык, кепилдик эмес: ар биринин жанында тесттеги тактык жана «жөнөкөй болжол» көрсөтүлөт.\n\n"
                   "🔐 <b>Сигналдар кантип ачылат</b>: BingX же BinoDex'те биздин шилтеме менен катталып, эсепти толуктайсыз → "
                   "ID'ңизди ботко жөнөтөсүз → бот текшерет.\n"
                   "🤝 Биз бул брокерлердин өнөктөшүбүз: сиз биздин шилтеме менен катталсаңыз, брокер бизге партнёрдук сыйакы төлөйт.\n"
                   "⏳ Ботко {days} күн кирбесеңиз, доступ токтотулат (кайра ачуу — бир баскыч).\n\n"
                   "18+ · Соода тобокелдиктүү · Киреше кепилденбейт\n\nТөмөнкү менюдан бөлүмдү тандаңыз 👇",
        "menu_hint": "Менюдан бөлүмдү тандаңыз 👇",
        "lang_set": "Тил: кыргызча ✓",
        # Катталуу
        "reg_choose": "📝 <b>Брокерде катталуу</b>\n\nКайсы брокерде соода кыласыз?\n"
                      "• <b>BingX</b> — крипто жана акция токендери (спот). Узак мөөнөткө сатып алуу.\n"
                      "• <b>BinoDex</b> — кыска мөөнөттүү соода (1–15 мүн), ▲/▼. Адегенде демо-эсеп.\n\n"
                      "Кадамдар жөнөкөй, ар биринде кыска сабак бар.",
        "reg_bingx": "📝 <b>BingX'те катталуу — 5 кадам</b>\n\n"
                     "1️⃣ «🔗 BingX'те катталуу» баскычын басып, email же телефон менен аккаунт ачыңыз. "
                     "Маанилүү: биздин шилтеме аркылуу катталсаңыз гана бот сизди тааный алат.\n"
                     "2️⃣ Профилден 2FA коргоону күйгүзүңүз. Сырсөз жана коддорду эч кимге айтпаңыз — BingX кызматкерлери да сурабайт.\n"
                     "3️⃣ KYC: Профиль → Идентификация (паспорт же ID-карта жана селфи).\n"
                     "4️⃣ Эсепти USDT менен толуктаңыз (P2P же карта). Жоготууга даяр болгон сумма гана.\n"
                     "5️⃣ Профилдеги <b>UID</b>'ни (сандар) көчүрүп, «✅ UID жөнөтүү» баскычын басыңыз. "
                     "Бот BingX'тен өзү текшерет: шилтеме, толуктоо, таза актив.",
        "reg_binodex": "📝 <b>BinoDex'те катталуу — 5 кадам</b>\n\n"
                       "1️⃣ «🔗 BinoDex'те катталуу» баскычы менен email жана сырсөз аркылуу аккаунт ачып, email'ди ырастаңыз.\n"
                       "2️⃣ Адегенде <b>демо-эсепте</b> машыгыңыз — бекер, реалдуу акча өзгөрбөйт.\n"
                       "3️⃣ Реалдуу эсепти толуктаңыз — жоготсоңуз жашооңузга таасир этпеген кичине сумма гана.\n"
                       "4️⃣ Профилдеги <b>ID</b>'ңизди көчүрүңүз.\n"
                       "5️⃣ «✅ ID жөнөтүү» баскычын басып, ID жана толуктоонун скриншотун жөнөтүңүз. "
                       "BinoDex'тин API'си азырынча жок, ошондуктан админ кол менен текшерет.",
        "no_ref": "⚠️ Катталуу шилтемеси жакында кошулат.",
        "ref_code": "🔑 <b>Реферал коду: <code>{c}</code></b>\n«🔗 Катталуу» баскычын баскандан кийин {b}'тин катталуу формасындагы «реферал коду» талаасына ушул кодду жазыңыз (кодду басып көчүрсө болот). Ошондо бот сизди тааныйт.",
        "btn_video": "📺 Видео-нускама",
        "btn_oauth": "🔐 BinoDex аркылуу текшерүү",
        "oauth_hint": "⚡ Эң оңой жол: «🔐 BinoDex аркылуу текшерүү» — BinoDex'ке кирип, ботко кайра кайтасыз. Бот ID'ни жана эсепти өзү текшерет, скриншот керек эмес. "
                      "Бот сырсөзүңүздү жана почтаңызды көрбөйт, соода кылууга укугу жок.",
        "oauth_bad": "Шилтеме туура эмес же башка адамдыкы. «🔐 BinoDex аркылуу текшерүү» баскычын кайра басыңыз.",
        "oauth_old": "Шилтеменин мөөнөтү бүттү. «🔐 BinoDex аркылуу текшерүү» баскычын кайра басыңыз.",
        "oauth_off": "BinoDex аркылуу текшерүү азырынча өчүк. ID'ни кол менен жөнөтүңүз: «📝 Катталуу» → BinoDex.",
        "oauth_not_partner": "❌ BinoDex аккаунтуңуз (ID {id}) биздин шилтеме же traderkg коду менен катталган эмес.\n"
                             "Шилтеме менен катталып, кайра текшериңиз. Ката болсо — «💬 Колдоо».",
        "oauth_wait_dep": "✓ BinoDex аккаунтуңуз табылды (ID {id}) жана биздин шилтеме менен катталган.\n"
                          "💳 Эсепте реалдуу баланс көрүнгөн жок. Толуктагандан кийин «🔐 Кайра текшерүү» басыңыз. "
                          "Толуктап, бирок баланс 0 болуп калса — «📷 Скриншот менен» тандаңыз.",
        "btn_oauth_again": "🔐 Кайра текшерүү", "btn_proof": "📷 Скриншот менен",
        "btn_ref": "🔗 {b}'те катталуу", "btn_lesson": "📖 Толук сабак", "btn_sendid_bingx": "✅ UID жөнөтүү", "btn_sendid_binodex": "✅ ID жөнөтүү",
        "ask_id_bingx": "BingX <b>UID</b>'ңизди жазыңыз (сандар гана).\n\n🔒 Бот BingX'тен гана текшерет: биздин шилтеме менен катталганыңызды, "
                        "толуктоо болгонун жана таза активиңиздин суммасын (USDT). Бул маалымат доступ үчүн гана колдонулат.",
        "ask_id_binodex": "BinoDex <b>ID</b>'ңизди жазыңыз.",
        "bad_id": "Бул ID'ге окшобойт. {hint}",
        "hint_bingx": "BingX UID — 5–15 сан, профилде жазылган.", "hint_binodex": "ID — 3–32 белги (тамга/сан).",
        "id_taken": "Бул ID башка Telegram аккаунтка байланган. Ката болсо — «💬 Колдоо» аркылуу жазыңыз.",
        "checking": "⏳ Текшерип жатам…",
        "not_invited": "❌ Бул UID биздин шилтеме аркылуу катталган эмес (BingX ушинтип жооп берди).\n"
                       "Шилтеме менен жаңы аккаунт ачып, жаңы UID'ни жөнөтүңүз. Суроо болсо — «💬 Колдоо».",
        "wait_dep": "✓ Катталуу ырасталды.\n💳 Эми эсепти толуктаңыз{min}. Толуктагандан кийин «🔄 Кайра текшерүү» баскычын басыңыз.",
        "min_txt": " (кеминде {v} USDT таза актив)",
        "ask_proof": "📷 Толуктоонун скриншотун жөнөтүңүз (BinoDex → тарых же баланс). Скриншот жок болсо — «Өткөрүү».",
        "btn_skip": "Өткөрүү",
        "sent_review": "⏳ Заявка админге жөнөтүлдү. Текшерилгенде бот өзү жазат.",
        "api_down": "⏳ Брокердин API'си азыр жооп бербей жатат. Заявка админге жөнөтүлдү — кол менен текшерилет.",
        "activated": "✅ <b>Доступ ачылды!</b>\n⭐ Сигналдар ушул чатка келет. Ар бир сигнал — ыктымалдык, кепилдик эмес.\n"
                     "Адегенде кичине суммалар менен текшериңиз. Сигналдарды өчүрүү: «⭐ Сигналдар» → 🔕.",
        "rejected": "❌ Заявка ырасталган жок: ID табылган жок же толуктоо көрүнгөн жок.\nСуроо болсо — «💬 Колдоо».",
        "btn_recheck": "🔄 Кайра текшерүү",
        # Сигналдар
        "sig_locked": "⭐ <b>Сигналдар</b>\n\nСигналдар брокерде биздин шилтеме менен катталып, эсепти толуктагандан кийин ачылат.\n"
                      "Кадамдар: «📝 Катталуу».",
        "sig_on": "⭐ <b>Сигналдар</b>: 🔔 күйүк\nBinoDex (экспирация {exp} мүн) жана BingX спот. Ар бир сигналдан кийин ✓/✗ жыйынтыгы келет.",
        "sig_off": "⭐ <b>Сигналдар</b>: 🔕 өчүк",
        "btn_now": "⭐ Азыр эң мыкты", "btn_off": "🔕 Өчүрүү", "btn_on": "🔔 Күйгүзүү", "btn_register": "📝 Катталуу",
        "now_none": "Азыр эрежеге туура келген сигнал жок (тест жөнөкөй болжолдон жогору эмес же ыктымалдык 45–55%). Бот бош сигнал бербейт.",
        "now_head": "⭐ <b>Акыркы скан</b> ({t}, Бишкек):",
        "paused": "⏸ Сигналдар убактылуу токтотулган.",
        "suspended": "⛔ Доступ токтотулган: {days} күн ботко кирген жоксуз.\nКайра ачуу — «🔄 Кайра ачуу» баскычы.",
        "btn_reactivate": "🔄 Кайра ачуу",
        "warn": "⏳ {d} күндөн кийин доступ токтойт — ботко {days} күн кирилген жок. Сактап калуу үчүн каалаган бөлүмдү ачыңыз.",
        "susp_now": "⛔ Доступ токтотулду: {days} күн ботко кирилген жок. Кайра ачуу: «👤 Профиль» → «🔄 Кайра ачуу».",
        # Профиль
        "st": {"new": "🆕 Катталуу бүтө элек", "wait_dep": "💳 Толуктоо күтүлүүдө", "pending": "⏳ Текшерилүүдө",
               "active": "✅ Активдүү", "suspended": "⛔ Токтотулган", "rejected": "❌ Четке кагылды", "blocked": "🚫 Бот бөгөттөлгөн"},
        "profile": "👤 <b>Профиль</b>\nСтатус: {st}\nБрокер: {br}\n{api}Сигналдар: {sig}\nАкыркы кирүү: бүгүн · {days} күн кирбесеңиз доступ токтойт",
        "no_broker": "тандала элек",
        "api_line": "BingX: шилтеме {i} · толуктоо {d} · KYC {k} · соода {tr}\nТаза актив: <b>{bal} USDT</b> ({t} жаңыртылды)\n",
        "btn_change": "📝 Брокер/ID өзгөртүү",
        # Окуу
        "learn": "📚 <b>Окуу</b> — кыска сабактар. Толугу сайтта.",
        "lessons": ["1. Негизги сөздөр", "2. BingX: катталуу жана USDT", "3. BinoDex: демо-эсеп", "4. Тобокелдик эрежелери", "5. Сигналды кантип окуу"],
        "l_basics": "<b>Негизги сөздөр</b>\n• <b>Брокер, биржа</b> — акчаңыз турган соода платформасы.\n• <b>USDT</b> — баасы 1 долларга жакын стейблкоин, биржада доллардын ордуна.\n"
                    "• <b>Демо-эсеп</b> — виртуалдык акча менен машыгуу.\n• <b>Рыноктук ордер</b> — азыркы баада ошол замат; <b>лимиттик</b> — сиз жазган баага жеткенде.\n"
                    "• <b>Тобокелдик</b> — акчанын бир бөлүгүн же баарын жоготуу мүмкүнчүлүгү. Трейдингде ал дайыма бар.",
        "l_bingx": "<b>BingX: катталуу жана USDT</b>\n1) Шилтеме менен катталыңыз, 2FA күйгүзүңүз.\n2) KYC: паспорт/ID жана селфи.\n"
                   "3) USDT: P2P (рейтинги жогору сатуучу, акчаны которгондон кийин гана «Төлөдүм») же карта.\n"
                   "4) Активдер → Которуу: USDT'ни «Спот» эсебине.\n5) Соода → Спот → тикер (мис. AAPLX) → Рыноктук ордер.\n"
                   "Тармакты (мис. TRC20) эки жакта бирдей тандаңыз — ката болсо, акча жоголушу мүмкүн.",
        "l_binodex": "<b>BinoDex: демо-эсеп</b>\n1) Катталып, email'ди ырастаңыз.\n2) Демо-эсепке которулуңуз — виртуалдык баланс.\n"
                     "3) Активди, сумманы жана мөөнөттү тандаңыз; багыт: өйдө же ылдый.\n4) Ар бир сооданы дептерге жазыңыз: себеп жана натыйжа.\n"
                     "Демодо туруктуу натыйжа болмоюнча реалдуу акча салбаңыз. Кыска мөөнөттө жоготуу тез болот.",
        "l_rules": "<b>Тобокелдиктин 6 эрежеси</b>\n1) Ашыкча акча менен гана — үй-бүлөнүн акчасын салбаңыз.\n2) Карызга соода кылбаңыз.\n3) Адегенде демо.\n"
                   "4) «Кепилденген киреше» — алдамчылыктын белгиси.\n5) Акчаңызды эч кимге «башкарууга» бербеңиз.\n"
                   "6) Ачууланып «кайтарып алам» деп соода кылбаңыз. Утулганда сумманы эселеп коюу (мартингейл) — тез жоготуунун жолу.",
        "l_signal": "<b>Сигналды кантип окуу</b>\n• <b>▲ ӨЙДӨ 63%</b> — ИИ моделинин баа өсөт деген ыктымалдыгы. 63% — 10 жолудан болжол менен 6сы, бирок ар бир соода өзүнчө.\n"
                    "• <b>тест 58% / жөнөкөй 52%</b> — модель акыркы маалыматта 58% туура болду; «дайыма көбүрөөк болгон тарапты тандоо» 52% берет. Айырма аз болсо — сигнал алсыз.\n"
                    "• Бот сигнал берет, эгер тест жөнөкөй болжолдон 1 п.п.дан жогору жана ыктымалдык 55%дан жогору (же 45%дан төмөн) болсо. Болбосо — «сигнал жок».\n"
                    "• <b>Экспирация</b> — сигнал канча мүнөткө. Андан кийин бот ✓/✗ жыйынтыгын жана жалпы статистиканы жөнөтөт.",
        # Колдоо
        "support": "💬 Суроону же көйгөйдү бир билдирүү менен жазыңыз (сүрөт тиркесе болот) — админге жөнөтүлөт.",
        "support_sent": "✓ Жөнөтүлдү. Админ ушул чатка жооп берет.",
        "admin_reply": "💬 <b>Админден жооп:</b>\n{t}",
        "site": "🌐 Сайт: анализатор, сигналдар, тренддер жана сабактар.",
        "btn_site": "🌐 AITRADING.KG ачуу",
        "stats_title": "📊 Боттун сигнал статистикасы",
    },
    "ru": {
        "welcome": "Привет, {name}! 👋\nЭто бот <b>AITRADING.KG</b> (TRADER KG).\n\n"
                   "⭐ <b>ИИ-сигналы</b>: BinoDex (короткие сделки, ▲/▼) и спот BingX (▲ покупка). "
                   "Сигнал — вероятность, а не гарантия: рядом всегда точность на тесте и «простое угадывание».\n\n"
                   "🔐 <b>Как открыть сигналы</b>: регистрируетесь на BingX или BinoDex по нашей ссылке и пополняете счёт → "
                   "присылаете боту свой ID → бот проверяет.\n"
                   "🤝 Мы партнёры этих брокеров: если вы регистрируетесь по нашей ссылке, брокер платит нам партнёрское вознаграждение.\n"
                   "⏳ Если {days} дней не заходить в бота, доступ приостанавливается (вернуть — одна кнопка).\n\n"
                   "18+ · Торговля рискованна · Доход не гарантирован\n\nВыберите раздел в меню ниже 👇",
        "menu_hint": "Выберите раздел в меню 👇",
        "lang_set": "Язык: русский ✓",
        "reg_choose": "📝 <b>Регистрация у брокера</b>\n\nГде будете торговать?\n"
                      "• <b>BingX</b> — крипта и токены акций (спот). Покупка на долгий срок.\n"
                      "• <b>BinoDex</b> — короткие сделки (1–15 мин), ▲/▼. Сначала демо-счёт.\n\n"
                      "Шаги простые, к каждому есть короткий урок.",
        "reg_bingx": "📝 <b>Регистрация на BingX — 5 шагов</b>\n\n"
                     "1️⃣ Нажмите «🔗 Регистрация на BingX» и откройте аккаунт по email или телефону. "
                     "Важно: бот узнает вас, только если вы зарегистрировались по нашей ссылке.\n"
                     "2️⃣ Включите в профиле 2FA. Пароль и коды никому не сообщайте — сотрудники BingX их не спрашивают.\n"
                     "3️⃣ KYC: Профиль → Верификация (паспорт или ID-карта и селфи).\n"
                     "4️⃣ Пополните счёт в USDT (P2P или карта). Только ту сумму, которую готовы потерять.\n"
                     "5️⃣ Скопируйте <b>UID</b> из профиля (цифры) и нажмите «✅ Отправить UID». "
                     "Бот сам проверит у BingX: ссылку, пополнение, чистые активы.",
        "reg_binodex": "📝 <b>Регистрация на BinoDex — 5 шагов</b>\n\n"
                       "1️⃣ Нажмите «🔗 Регистрация на BinoDex», откройте аккаунт по email и паролю, подтвердите email.\n"
                       "2️⃣ Сначала потренируйтесь на <b>демо-счёте</b> — бесплатно, реальные деньги не меняются.\n"
                       "3️⃣ Пополните реальный счёт — только небольшой суммой, потеря которой не повлияет на вашу жизнь.\n"
                       "4️⃣ Скопируйте свой <b>ID</b> из профиля.\n"
                       "5️⃣ Нажмите «✅ Отправить ID» и пришлите ID и скриншот пополнения. "
                       "API у BinoDex пока нет, поэтому проверяет админ вручную.",
        "no_ref": "⚠️ Ссылка для регистрации скоро появится.",
        "ref_code": "🔑 <b>Реферальный код: <code>{c}</code></b>\nПосле нажатия «🔗 Регистрация» введите этот код в поле «реферальный код» в форме регистрации {b} (код копируется нажатием). Так бот вас узнает.",
        "btn_video": "📺 Видеоинструкция",
        "btn_oauth": "🔐 Проверить через BinoDex",
        "oauth_hint": "⚡ Самый простой путь: «🔐 Проверить через BinoDex» — войдёте в BinoDex и вернётесь в бот. Бот сам проверит ID и счёт, скриншот не нужен. "
                      "Бот не видит ваш пароль и почту и не может торговать.",
        "oauth_bad": "Ссылка недействительна или чужая. Нажмите «🔐 Проверить через BinoDex» ещё раз.",
        "oauth_old": "Ссылка устарела. Нажмите «🔐 Проверить через BinoDex» ещё раз.",
        "oauth_off": "Проверка через BinoDex пока выключена. Отправьте ID вручную: «📝 Регистрация» → BinoDex.",
        "oauth_not_partner": "❌ Ваш аккаунт BinoDex (ID {id}) зарегистрирован не по нашей ссылке и не с кодом traderkg.\n"
                             "Зарегистрируйтесь по ссылке и проверьте снова. Если это ошибка — «💬 Поддержка».",
        "oauth_wait_dep": "✓ Аккаунт BinoDex найден (ID {id}) и зарегистрирован по нашей ссылке.\n"
                          "💳 Реального баланса на счёте не видно. После пополнения нажмите «🔐 Проверить снова». "
                          "Если пополняли, но баланс уже 0 — выберите «📷 Со скриншотом».",
        "btn_oauth_again": "🔐 Проверить снова", "btn_proof": "📷 Со скриншотом",
        "btn_ref": "🔗 Регистрация на {b}", "btn_lesson": "📖 Полный урок", "btn_sendid_bingx": "✅ Отправить UID", "btn_sendid_binodex": "✅ Отправить ID",
        "ask_id_bingx": "Напишите свой <b>UID</b> BingX (только цифры).\n\n🔒 Бот проверяет только у BingX: что вы зарегистрированы по нашей ссылке, "
                        "было ли пополнение и сумму чистых активов (USDT). Эти данные нужны только для доступа.",
        "ask_id_binodex": "Напишите свой <b>ID</b> BinoDex.",
        "bad_id": "Это не похоже на ID. {hint}",
        "hint_bingx": "UID BingX — 5–15 цифр, указан в профиле.", "hint_binodex": "ID — 3–32 символа (буквы/цифры).",
        "id_taken": "Этот ID уже привязан к другому аккаунту Telegram. Если это ошибка — напишите в «💬 Поддержка».",
        "checking": "⏳ Проверяю…",
        "not_invited": "❌ Этот UID зарегистрирован не по нашей ссылке (так ответил BingX).\n"
                       "Откройте новый аккаунт по ссылке и пришлите новый UID. Вопросы — «💬 Поддержка».",
        "wait_dep": "✓ Регистрация подтверждена.\n💳 Теперь пополните счёт{min}. После пополнения нажмите «🔄 Проверить снова».",
        "min_txt": " (не меньше {v} USDT чистых активов)",
        "ask_proof": "📷 Пришлите скриншот пополнения (BinoDex → история или баланс). Нет скриншота — «Пропустить».",
        "btn_skip": "Пропустить",
        "sent_review": "⏳ Заявка отправлена админу. После проверки бот напишет сам.",
        "api_down": "⏳ API брокера сейчас не отвечает. Заявка отправлена админу — проверит вручную.",
        "activated": "✅ <b>Доступ открыт!</b>\n⭐ Сигналы будут приходить в этот чат. Каждый сигнал — вероятность, а не гарантия.\n"
                     "Начните с небольших сумм. Выключить сигналы: «⭐ Сигналы» → 🔕.",
        "rejected": "❌ Заявка не подтверждена: ID не найден или пополнение не видно.\nВопросы — «💬 Поддержка».",
        "btn_recheck": "🔄 Проверить снова",
        "sig_locked": "⭐ <b>Сигналы</b>\n\nСигналы открываются после регистрации у брокера по нашей ссылке и пополнения счёта.\n"
                      "Шаги: «📝 Регистрация».",
        "sig_on": "⭐ <b>Сигналы</b>: 🔔 включены\nBinoDex (экспирация {exp} мин) и спот BingX. После каждого сигнала приходит результат ✓/✗.",
        "sig_off": "⭐ <b>Сигналы</b>: 🔕 выключены",
        "btn_now": "⭐ Лучшее сейчас", "btn_off": "🔕 Выключить", "btn_on": "🔔 Включить", "btn_register": "📝 Регистрация",
        "now_none": "Сейчас нет сигнала, который проходит правила (тест не выше угадывания или вероятность 45–55%). Бот не даёт пустых сигналов.",
        "now_head": "⭐ <b>Последний скан</b> ({t}, Бишкек):",
        "paused": "⏸ Сигналы временно остановлены.",
        "suspended": "⛔ Доступ приостановлен: вы не заходили в бота {days} дней.\nВернуть — кнопка «🔄 Вернуть доступ».",
        "btn_reactivate": "🔄 Вернуть доступ",
        "warn": "⏳ Через {d} дн. доступ приостановится — вы не заходили {days} дней. Чтобы сохранить, откройте любой раздел.",
        "susp_now": "⛔ Доступ приостановлен: {days} дней без захода в бота. Вернуть: «👤 Профиль» → «🔄 Вернуть доступ».",
        "st": {"new": "🆕 Регистрация не завершена", "wait_dep": "💳 Ждём пополнение", "pending": "⏳ На проверке",
               "active": "✅ Активен", "suspended": "⛔ Приостановлен", "rejected": "❌ Отклонено", "blocked": "🚫 Бот заблокирован"},
        "profile": "👤 <b>Профиль</b>\nСтатус: {st}\nБрокер: {br}\n{api}Сигналы: {sig}\nПоследний заход: сегодня · без заходов {days} дней доступ приостановится",
        "no_broker": "не выбран",
        "api_line": "BingX: ссылка {i} · пополнение {d} · KYC {k} · сделки {tr}\nЧистые активы: <b>{bal} USDT</b> (обновлено {t})\n",
        "btn_change": "📝 Сменить брокера/ID",
        "learn": "📚 <b>Обучение</b> — короткие уроки. Полная версия на сайте.",
        "lessons": ["1. Основные слова", "2. BingX: регистрация и USDT", "3. BinoDex: демо-счёт", "4. Правила риска", "5. Как читать сигнал"],
        "l_basics": "<b>Основные слова</b>\n• <b>Брокер, биржа</b> — платформа, где лежат ваши деньги.\n• <b>USDT</b> — стейблкоин ≈ 1 доллар, на бирже вместо долларов.\n"
                    "• <b>Демо-счёт</b> — тренировка на виртуальных деньгах.\n• <b>Рыночный ордер</b> — сразу по текущей цене; <b>лимитный</b> — когда цена дойдёт до вашей.\n"
                    "• <b>Риск</b> — возможность потерять часть или все деньги. В трейдинге он есть всегда.",
        "l_bingx": "<b>BingX: регистрация и USDT</b>\n1) Регистрация по ссылке, включите 2FA.\n2) KYC: паспорт/ID и селфи.\n"
                   "3) USDT: P2P (продавец с высоким рейтингом, «Оплачено» — только после перевода) или карта.\n"
                   "4) Активы → Перевод: USDT на «Спот».\n5) Торговля → Спот → тикер (напр. AAPLX) → рыночный ордер.\n"
                   "Сеть (напр. TRC20) выбирайте одинаковую с обеих сторон — при ошибке деньги можно потерять.",
        "l_binodex": "<b>BinoDex: демо-счёт</b>\n1) Зарегистрируйтесь и подтвердите email.\n2) Переключитесь на демо-счёт — виртуальный баланс.\n"
                     "3) Выберите актив, сумму и срок; направление: вверх или вниз.\n4) Записывайте каждую сделку: причина и результат.\n"
                     "Пока на демо нет стабильного результата, реальные деньги не вносите. На коротких сроках потери быстрые.",
        "l_rules": "<b>6 правил риска</b>\n1) Только свободные деньги — не семейные.\n2) Не торгуйте в долг.\n3) Сначала демо.\n"
                   "4) «Гарантированный доход» — признак мошенничества.\n5) Не отдавайте деньги «в управление».\n"
                   "6) Не отыгрывайтесь. Удваивать ставку после проигрыша (мартингейл) — быстрый путь к потере всего.",
        "l_signal": "<b>Как читать сигнал</b>\n• <b>▲ ВВЕРХ 63%</b> — вероятность роста по ИИ-модели. 63% — примерно 6 из 10, но каждая сделка отдельна.\n"
                    "• <b>тест 58% / угадывание 52%</b> — на последних данных модель была права в 58%; «всегда ставить на более частое» даёт 52%. Маленькая разница — слабый сигнал.\n"
                    "• Бот даёт сигнал, только если тест выше угадывания больше чем на 1 п.п. и вероятность выше 55% (или ниже 45%). Иначе — «сигнала нет».\n"
                    "• <b>Экспирация</b> — на сколько минут сигнал. Потом бот присылает ✓/✗ и общую статистику.",
        "support": "💬 Опишите вопрос или проблему одним сообщением (можно с фото) — оно уйдёт админу.",
        "support_sent": "✓ Отправлено. Админ ответит в этот чат.",
        "admin_reply": "💬 <b>Ответ админа:</b>\n{t}",
        "site": "🌐 Сайт: анализатор, сигналы, тренды и уроки.",
        "btn_site": "🌐 Открыть AITRADING.KG",
        "stats_title": "📊 Статистика сигналов бота",
    },
}
LESSON_KEYS = [("l_basics", "basics"), ("l_bingx", "bingx"), ("l_binodex", "binodex"), ("l_rules", "rules"), ("l_signal", "")]
LESSON_VIDEO = {"l_basics": "basics", "l_bingx": "bingx-register", "l_binodex": "binodex-demo", "l_rules": "rules", "l_signal": "signals"}   # config.js → VIDEOS


def T(u, key, **kw):
    lang = (u or {}).get("lang") or "kg"
    v = TX.get(lang, TX["kg"]).get(key, TX["kg"].get(key, key))
    return v.format(**kw) if kw and isinstance(v, str) else v


def ik(rows):
    """Inline баскычтар: (текст, callback же https/tg шилтеме)."""
    kb = []
    for r in rows:
        row = []
        for t, v in r:
            if v is None:
                continue
            row.append({"text": t, "url": v} if re.match(r"^(https?|tg)://", v) else {"text": t, "callback_data": v})
        if row:
            kb.append(row)
    return {"inline_keyboard": kb}


def ago_days(ms):
    return int((S.now_ms() - (ms or 0)) // DAY)


# ======================================================================
#  Маалымат базасы (SQLite, tools/tg_bot.db — .gitignore'до)
# ======================================================================
SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, lang TEXT DEFAULT 'kg', created INTEGER, last_seen INTEGER, src TEXT,
  status TEXT DEFAULT 'new', broker TEXT, trader_id TEXT, verified_at INTEGER,
  invited INTEGER, deposit INTEGER, kyc INTEGER, traded INTEGER, balance REAL, check_t INTEGER,
  signals INTEGER DEFAULT 1, warned INTEGER DEFAULT 0, step TEXT, prev_status TEXT);
CREATE INDEX IF NOT EXISTS users_tid ON users(broker, trader_id);
CREATE TABLE IF NOT EXISTS broadcasts(id INTEGER PRIMARY KEY AUTOINCREMENT, created INTEGER, admin INTEGER, from_chat INTEGER,
  msg_id INTEGER, buttons TEXT, audience TEXT, total INTEGER, sent INTEGER, failed INTEGER, status TEXT);
CREATE TABLE IF NOT EXISTS sig_sent(sig_id INTEGER, user_id INTEGER, PRIMARY KEY(sig_id, user_id));
CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT);
"""


class DB:
    def __init__(self, path):
        self.c = sqlite3.connect(path, check_same_thread=False, timeout=30)
        self.c.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.lock:
            self.c.executescript(SCHEMA)

    def q(self, sql, args=()):
        with self.lock:
            return [dict(r) for r in self.c.execute(sql, args).fetchall()]

    def one(self, sql, args=()):
        r = self.q(sql, args)
        return r[0] if r else None

    def x(self, sql, args=()):
        with self.lock:
            cur = self.c.execute(sql, args)
            self.c.commit()
            return cur

    def user(self, uid):
        return self.one("SELECT * FROM users WHERE id=?", (uid,))

    def upd(self, uid, **kw):
        if kw:
            self.x("UPDATE users SET " + ",".join(k + "=?" for k in kw) + " WHERE id=?", tuple(kw.values()) + (uid,))
        return self.user(uid)

    def kv(self, k, default=None):
        r = self.one("SELECT v FROM kv WHERE k=?", (k,))
        return json.loads(r["v"]) if r else default

    def kv_set(self, k, v):
        if v is None:
            self.x("DELETE FROM kv WHERE k=?", (k,))
        else:
            self.x("INSERT INTO kv(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, json.dumps(v, ensure_ascii=False)))


# ======================================================================
#  BingX Agent API (окуу гана): UID чакырылганбы, толуктоо, KYC, соода, таза актив
# ======================================================================
class BingXAgent:
    BASES = ["https://open-api.bingx.com", "https://open-api.bingx.pro"]
    FATAL = {100001, 100004, 100403, 100410, 100412, 100413, 100419, 100421, 100500, 80001, 80014}   # API/ачкыч көйгөйү

    def __init__(self, key=None, secret=None):
        self.key = (key if key is not None else os.environ.get("BINGX_API_KEY") or "").strip()
        self.secret = (secret if secret is not None else os.environ.get("BINGX_API_SECRET") or "").strip()

    def ok(self):
        return bool(self.key and self.secret)

    def get(self, path, params):
        p = dict(params, timestamp=S.now_ms(), recvWindow=5000)
        qs = "&".join("%s=%s" % (k, p[k]) for k in sorted(p))       # BingX: ASCII тартибинде, URL-encode жок
        sig = hmac.new(self.secret.encode(), qs.encode(), hashlib.sha256).hexdigest()
        err = None
        for base in self.BASES:
            req = urllib.request.Request(base + path + "?" + qs + "&signature=" + sig, headers={"X-BX-APIKEY": self.key, "User-Agent": S.UA})
            try:
                with urllib.request.urlopen(req, timeout=12) as r:
                    j = json.loads(r.read().decode("utf-8"))
            except Exception as e:  # noqa: BLE001 — запастагы дарек
                err = S.Fetch("BingX: %s" % str(e).replace(self.key, "<KEY>"))
                continue
            code = int(j.get("code") or 0)
            if code:
                raise S.Fetch("BingX %d: %s" % (code, j.get("msg") or ""), ) if code in self.FATAL else LookupError("BingX %d: %s" % (code, j.get("msg") or ""))
            return j.get("data")
        raise err or S.Fetch("BingX: no answer")

    def check(self, uid):
        """inviteRelationCheck: None — UID биздин шилтеме менен эмес же табылган жок; S.Fetch — API иштебей жатат."""
        try:
            d = self.get("/openApi/agent/v1/account/inviteRelationCheck", {"uid": int(uid)}) or {}
        except LookupError:
            return None
        if not d.get("inviteResult"):
            return None
        return {"invited": True, "direct": bool(d.get("directInvitation")), "deposit": bool(d.get("deposit")),
                "kyc": str(d.get("kycResult")).lower() == "true", "traded": bool(d.get("trade")),
                "balance": S.num(d.get("balanceVolume"))}

    def invited_total(self):
        d = self.get("/openApi/agent/v1/account/inviteAccountList", {"pageIndex": 1, "pageSize": 1}) or {}
        return d.get("total")


# ======================================================================
#  «Войти через BinoDex» (OAuth): бот шилтеме берет, сайттагы functions/oauth/callback.js кодду алмаштырат,
#  колдонуучу ботко кол коюлган белги менен кайтат: /start bx_<tg36>_<id36>_<flags>_<ts36>_<sig>
# ======================================================================
OAUTH_AUTHORIZE = "https://binodex.app/oauth/authorize"
OAUTH_MAX_AGE = 1800


def link_secret():
    return (os.environ.get("LINK_SECRET") or "").strip()


def oauth_ready():
    return bool((os.environ.get("BINODEX_CLIENT_ID") or "").strip() and link_secret())


def link_sig(msg, n):
    raw = hmac.new(link_secret().encode(), msg.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")[:n]


def b36(n):
    n, s = int(n), ""
    while True:
        n, r = divmod(n, 36)
        s = "0123456789abcdefghijklmnopqrstuvwxyz"[r] + s
        if not n:
            return s


def oauth_url(tg_id):
    """BinoDex'ке кирүү шилтемеси. state — ушул Telegram колдонуучусуна байланган жана кол коюлган."""
    tg36, ts36 = b36(tg_id), b36(int(time.time()))
    q = {"client_id": os.environ.get("BINODEX_CLIENT_ID", "").strip(),
         "redirect_uri": (os.environ.get("OAUTH_REDIRECT") or S.SITE_URL + "/oauth/callback").strip(),
         "state": "%s.%s.%s" % (tg36, ts36, link_sig("st|%s|%s" % (tg36, ts36), 22))}
    ref = (os.environ.get("BINODEX_OAUTH_REF") or ref_codes().get("binodex") or "").strip()
    if ref:
        q["ref"] = ref                                   # жаңы катталуу биздин шилтемеге жазылат
    return OAUTH_AUTHORIZE + "?" + urllib.parse.urlencode(q)


def oauth_parse(payload, tg_id):
    """bx_… белгисин текшерүү → {"id", "partner", "funded"} же каталык ачкыч (str)."""
    if not oauth_ready():
        return "off"
    parts = payload[3:].split("_", 4)
    if len(parts) != 5 or not all(re.match(r"^[0-9a-z]+$", p) for p in parts[:4]):
        return "bad"
    tg36, id36, fl, ts36, sig = parts
    if not hmac.compare_digest(sig, link_sig("bx|%s_%s_%s_%s" % (tg36, id36, fl, ts36), 16)):
        return "bad"
    if int(tg36, 36) != int(tg_id):
        return "bad"                                     # башка адамдын шилтемеси
    if time.time() - int(ts36, 36) > OAUTH_MAX_AGE:
        return "old"
    f = int(fl, 36)
    return {"id": str(int(id36, 36)), "partner": bool(f & 1), "funded": bool(f & 2)}


def binodex_check(trader_id):
    # BinoDex партнёрдук API документациясы келгенде ушул жер толтурулат (ID, толуктоо, баланс). Азырынча — админ кол менен.
    raise NotImplementedError("binodex-api-pending")


# ======================================================================
#  Бот
# ======================================================================
class Engine(S.Bot):
    """tg_signals сканери: сигналдар бир чатка эмес, бардык ачык доступтагыларга кетет."""

    def __init__(self, args, app):
        super().__init__(args)
        self.app = app

    def publish(self, kind, sg):
        return self.app.publish(kind, sg, self.st["history"])


class App:
    def __init__(self, signals=True, exp=None):
        self.tg = S.Telegram(False)
        self.db = DB(DB_PATH)
        self.bingx = BingXAgent()
        self.refs = ref_links()
        self.min_bal = S.num(os.environ.get("TG_MIN_BALANCE") or 0)
        chat = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
        ids = [x.strip() for x in (os.environ.get("TELEGRAM_ADMIN_IDS") or "").split(",") if x.strip()]
        if re.match(r"^\d+$", chat):
            ids.append(chat)
        self.admins = {int(x) for x in ids if re.match(r"^\d+$", x)}
        self.channel = chat if chat.startswith("-") or chat.startswith("@") else None
        self.exp = exp or [1]
        self.engine = None
        if signals:
            a = argparse.Namespace(dry_run=False, lang=os.environ.get("TG_LANG", "kg"), state=os.path.join(HERE, "tg_state.json"),
                                   exp=self.exp, markets={"binodex", "bingx"}, force=False, verbose=False)
            self.engine = Engine(a, self)
        self.username = None

    # ---------- Telegram жардамчылары ----------
    def api(self, method, payload, chat=None, timeout=20):
        try:
            return (self.tg.call(method, payload, timeout=timeout) or {}).get("result")
        except S.Fetch as e:
            m = str(e)
            if chat and re.search(r"blocked|deactivated|chat not found|user is deactivated|Forbidden", m, re.I):
                u = self.db.user(chat)
                if u and u["status"] != "blocked":
                    self.db.upd(chat, prev_status=u["status"], status="blocked")
            elif "message is not modified" not in m:
                print("! %s: %s" % (method, m))
            return None

    def send(self, chat, text, kb=None, preview=False):
        p = {"chat_id": chat, "text": text, "parse_mode": "HTML", "link_preview_options": {"is_disabled": not preview}}
        if kb is not None:
            p["reply_markup"] = kb
        return self.api("sendMessage", p, chat=chat)

    def edit(self, chat, mid, text, kb=None):
        p = {"chat_id": chat, "message_id": mid, "text": text, "parse_mode": "HTML", "link_preview_options": {"is_disabled": True}}
        if kb is not None:
            p["reply_markup"] = kb
        return self.api("editMessageText", p, chat=chat)

    def notify_admins(self, text, kb=None):
        for a in self.admins:
            self.send(a, text, kb)

    def menu_kb(self, u):
        rows = [[{"text": b} for b in r] for r in MENU.get(u.get("lang") or "kg", MENU["kg"])]
        if self.is_admin(u["id"]):
            rows.append([{"text": ADMIN_BTN}])
        return {"keyboard": rows, "resize_keyboard": True, "is_persistent": True}

    def is_admin(self, uid):
        return uid in self.admins

    def user_link(self, u):
        name = E(u.get("first_name") or "") or "user"
        at = ("@%s " % E(u["username"])) if u.get("username") else ""
        return at + '<a href="tg://user?id=%d">%s</a> <code>%d</code>' % (u["id"], name, u["id"])

    # ---------- Колдонуучу ----------
    def ensure_user(self, fr, src=None):
        uid, now = fr["id"], S.now_ms()
        u = self.db.user(uid)
        if not u:
            lang = "ru" if (fr.get("language_code") or "").startswith("ru") else "kg"
            st = "active" if self.is_admin(uid) else "new"
            self.db.x("INSERT INTO users(id,username,first_name,lang,created,last_seen,src,status,broker,verified_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                      (uid, fr.get("username"), fr.get("first_name"), lang, now, now, src, st, "admin" if st == "active" else None, now if st == "active" else None))
            u = self.db.user(uid)
        kw = {"last_seen": now, "warned": 0, "username": fr.get("username"), "first_name": fr.get("first_name")}
        if u["status"] == "blocked":                          # ботту кайра ачты
            kw["status"] = u.get("prev_status") or "new"
        return self.db.upd(uid, **kw)

    # ---------- Жаңыртууларды иштетүү ----------
    def handle(self, upd):
        if "callback_query" in upd:
            return self.on_callback(upd["callback_query"])
        mcm = upd.get("my_chat_member")
        if mcm and mcm.get("chat", {}).get("type") == "private":
            st = (mcm.get("new_chat_member") or {}).get("status")
            u = self.db.user(mcm["chat"]["id"])
            if u and st == "kicked" and u["status"] != "blocked":
                self.db.upd(u["id"], prev_status=u["status"], status="blocked")
            return None
        m = upd.get("message")
        if not m or m.get("chat", {}).get("type") != "private" or not m.get("from"):
            return None
        text = (m.get("text") or "").strip()
        start_arg = text.split(" ", 1)[1].strip() if text.startswith("/start ") else ""
        src = start_arg[:32] if start_arg and not start_arg.startswith("bx_") else None
        u = self.ensure_user(m["from"], src)
        uid = u["id"]
        if start_arg.startswith("bx_"):                    # BinoDex'тен кайтты (OAuth)
            return self.oauth_result(u, start_arg[:80])
        cmd = text.split(" ", 1)[0].split("@", 1)[0].lower() if text.startswith("/") else None

        # админдин кадамдары (рассылка, жооп)
        if self.is_admin(uid) and not (cmd or text in ACTIONS):
            d = self.db.kv("draft:%d" % uid)
            if d and d.get("stage") == "content":
                return self.bc_content(u, m)
            if d and d.get("stage") == "custom":
                return self.bc_custom(u, text)
            rep = self.db.kv("reply:%d" % uid)
            if rep:
                self.db.kv_set("reply:%d" % uid, None)
                tu = self.db.user(rep)
                if tu:
                    self.send(rep, T(tu, "admin_reply", t=E(text or "📎")))
                    if not text:
                        self.api("copyMessage", {"chat_id": rep, "from_chat_id": uid, "message_id": m["message_id"]}, chat=rep)
                    return self.send(uid, "✓ Жооп жөнөтүлдү / Ответ отправлен.")
        # колдонуучунун кадамдары
        if u.get("step") and not (cmd or text in ACTIONS):
            return self.on_step(u, m, text)
        if u.get("step") and (cmd or text in ACTIONS):
            u = self.db.upd(uid, step=None)
        act = CMDS.get(cmd) if cmd else ACTIONS.get(text)
        if act == "find" and self.is_admin(uid):
            return self.adm_find(u, text.split(" ", 1)[1] if " " in text else "")
        if act:
            return self.open(u, act)
        return self.send(uid, T(u, "menu_hint"), self.menu_kb(u))

    def open(self, u, act, mid=None):
        uid = u["id"]
        if act == "start":
            return self.send(uid, T(u, "welcome", name=E(u.get("first_name") or ""), days=ACCESS_DAYS), self.menu_kb(u))
        if act == "lang":
            u = self.db.upd(uid, lang="ru" if u.get("lang") == "kg" else "kg")
            return self.send(uid, T(u, "lang_set"), self.menu_kb(u))
        if act == "register":
            return self.send(uid, T(u, "reg_choose"), ik([[("BingX", "reg:bingx"), ("BinoDex", "reg:binodex")]]))
        if act == "signals":
            return self.show_signals(u)
        if act == "learn":
            L = T(u, "lessons")
            return self.send(uid, T(u, "learn"), ik([[(L[i], "learn:%d" % i)] for i in range(len(L))] + [[(T(u, "btn_lesson"), S.SITE_URL + "/learn.html")]]))
        if act == "profile":
            return self.show_profile(u)
        if act == "site":
            return self.send(uid, T(u, "site"), ik([[(T(u, "btn_site"), S.SITE_URL + "/")]]))
        if act == "support":
            self.db.upd(uid, step="support")
            return self.send(uid, T(u, "support"))
        if act == "admin" and self.is_admin(uid):
            return self.adm_home(u)
        return self.send(uid, T(u, "menu_hint"), self.menu_kb(u))

    # ---------- Катталуу ----------
    def show_broker(self, u, b, mid=None):
        ref = self.refs.get(b)
        name = "BingX" if b == "bingx" else "BinoDex"
        code = ref_codes().get(b)
        oauth = b == "binodex" and oauth_ready()
        text = T(u, "reg_" + b) + ("" if ref else "\n\n" + T(u, "no_ref")) + ("\n\n" + T(u, "ref_code", c=E(code), b=name) if code else "") \
            + ("\n\n" + T(u, "oauth_hint") if oauth else "")
        kb = ik([[(T(u, "btn_ref", b=name), ref)], [(T(u, "btn_video"), video_for(b + "-register", u.get("lang")))],
                 [(T(u, "btn_lesson"), S.SITE_URL + "/learn.html#" + b)],
                 [(T(u, "btn_oauth"), oauth_url(u["id"]) if oauth else None)],
                 [(T(u, "btn_sendid_" + b), "sendid:" + b)]])
        return self.send(u["id"], text, kb)

    def oauth_result(self, u, payload):
        """Сайттан кайткан колдонуучу: /start bx_… → текшерүү → доступ."""
        uid = u["id"]
        r = oauth_parse(payload, uid)
        if not isinstance(r, dict):
            kb = ik([[(T(u, "btn_oauth"), oauth_url(uid))]]) if oauth_ready() else None
            return self.send(uid, T(u, "oauth_" + r), kb)
        tid = r["id"]
        other = self.db.one("SELECT * FROM users WHERE broker='binodex' AND trader_id=? AND id<>? AND status IN ('active','pending','wait_dep','suspended')",
                            (tid, uid))
        if other:
            self.notify_admins("⚠️ BinoDex ID %s (OAuth) экинчи Telegram'дан: %s · мурдагы ээси: %s" % (E(tid), self.user_link(u), self.user_link(other)))
            return self.send(uid, T(u, "id_taken"))
        u = self.db.upd(uid, step=None, broker="binodex", trader_id=tid, invited=int(r["partner"]), deposit=int(r["funded"]),
                        kyc=None, traded=None, balance=None, check_t=S.now_ms())
        if not r["partner"]:
            self.db.upd(uid, status="new")
            return self.send(uid, T(u, "oauth_not_partner", id=E(tid)), ik([[(T(u, "btn_ref", b="BinoDex"), self.refs.get("binodex"))]]))
        if not r["funded"]:
            self.db.upd(uid, status="wait_dep")
            return self.send(uid, T(u, "oauth_wait_dep", id=E(tid)),
                             ik([[(T(u, "btn_oauth_again"), oauth_url(uid))], [(T(u, "btn_proof"), "proofbd")]]))
        return self.activate(u, "BinoDex OAuth")

    def on_step(self, u, m, text):
        uid, step = u["id"], u["step"]
        if step.startswith("id:"):
            b = step[3:]
            tid = re.sub(r"\s+", "", text)
            ok = re.match(r"^\d{5,15}$", tid) if b == "bingx" else re.match(r"^[A-Za-z0-9_-]{3,32}$", tid)
            if not ok:
                return self.send(uid, T(u, "bad_id", hint=T(u, "hint_" + b)))
            other = self.db.one("SELECT * FROM users WHERE broker=? AND trader_id=? AND id<>? AND status IN ('active','pending','wait_dep','suspended')",
                                (b, tid, uid))
            if other:
                self.db.upd(uid, step=None)
                self.notify_admins("⚠️ ID %s (%s) экинчи жолу жөнөтүлдү: %s · мурдагы ээси: %s" % (E(tid), b, self.user_link(u), self.user_link(other)))
                return self.send(uid, T(u, "id_taken"))
            u = self.db.upd(uid, step=None, broker=b, trader_id=tid, invited=None, deposit=None, kyc=None, traded=None, balance=None)
            return self.verify(u)
        if step == "proof":
            if not (m.get("photo") or m.get("document")):
                return self.send(uid, T(u, "ask_proof"), ik([[(T(u, "btn_skip"), "skipproof")]]))
            self.db.upd(uid, step=None)
            return self.to_review(u, m["message_id"])
        if step == "support":
            self.db.upd(uid, step=None)
            for a in self.admins:
                self.send(a, "💬 <b>Колдоо</b> · %s\nСтатус: %s · %s %s" % (self.user_link(u), u["status"], E(u.get("broker") or "—"), E(u.get("trader_id") or "")),
                          ik([[("↩️ Жооп берүү", "adm:rep:%d" % uid)]]))
                self.api("copyMessage", {"chat_id": a, "from_chat_id": uid, "message_id": m["message_id"]})
            return self.send(uid, T(u, "support_sent"), self.menu_kb(u))
        self.db.upd(uid, step=None)
        return self.send(uid, T(u, "menu_hint"), self.menu_kb(u))

    def verify(self, u, quiet=False):
        """BingX: Agent API менен автоматтык. BinoDex (API жок) же BingX ачкычсыз: админ ✅/❌."""
        uid, b = u["id"], u["broker"]
        if b == "bingx" and self.bingx.ok():
            if not quiet:
                self.send(uid, T(u, "checking"))
            try:
                r = self.bingx.check(u["trader_id"])
            except S.Fetch as e:
                self.notify_admins("⚠️ BingX API: %s" % E(str(e)))
                self.db.upd(uid, status="pending")
                self.send(uid, T(u, "api_down"))
                return self.to_review(self.db.user(uid), None)
            if r is None:
                self.db.upd(uid, status="new", invited=0, check_t=S.now_ms())
                return self.send(uid, T(u, "not_invited"), ik([[(T(u, "btn_ref", b="BingX"), self.refs.get("bingx"))]]))
            u = self.db.upd(uid, invited=1, deposit=int(r["deposit"]), kyc=int(r["kyc"]), traded=int(r["traded"]), balance=r["balance"], check_t=S.now_ms())
            if not r["deposit"] or r["balance"] < self.min_bal:
                self.db.upd(uid, status="wait_dep")
                mn = T(u, "min_txt", v=("%g" % self.min_bal)) if self.min_bal > 0 else ""
                return self.send(uid, T(u, "wait_dep", min=mn), ik([[(T(u, "btn_recheck"), "recheck")]]))
            return self.activate(u, "BingX API")
        # Кол менен текшерүү
        self.db.upd(uid, status="pending", step="proof")
        return self.send(uid, T(u, "ask_proof"), ik([[(T(u, "btn_skip"), "skipproof")]]))

    def to_review(self, u, proof_mid):
        uid = u["id"]
        self.db.upd(uid, status="pending", step=None)
        for a in self.admins:
            self.send(a, "🧾 <b>Жаңы заявка</b>\n%s\nБрокер: <b>%s</b> · ID: <code>%s</code>\nТил: %s · Булак: %s" % (
                self.user_link(u), E(u.get("broker") or "—"), E(u.get("trader_id") or "—"), u.get("lang"), E(u.get("src") or "—")),
                ik([[("✅ Ачуу", "adm:ok:%d" % uid), ("❌ Четке кагуу", "adm:no:%d" % uid)], [("💬 Жазуу", "adm:rep:%d" % uid)]]))
            if proof_mid:
                self.api("copyMessage", {"chat_id": a, "from_chat_id": uid, "message_id": proof_mid})
        return self.send(uid, T(u, "sent_review"), self.menu_kb(u))

    def activate(self, u, how):
        uid = u["id"]
        u = self.db.upd(uid, status="active", verified_at=S.now_ms(), warned=0, step=None)
        self.send(uid, T(u, "activated"), self.menu_kb(u))
        bal = (" · таза актив %.2f USDT" % u["balance"]) if u.get("balance") is not None else ""
        self.notify_admins("✅ <b>Доступ ачылды</b> (%s): %s · %s <code>%s</code>%s" % (E(how), self.user_link(u), E(u.get("broker") or ""), E(u.get("trader_id") or ""), bal))
        return True

    # ---------- Сигналдар бөлүмү ----------
    def show_signals(self, u):
        uid = u["id"]
        hist = self.engine.st["history"] if self.engine else []
        stats = S.stats_line(hist, u.get("lang") or "kg")
        tail = ("\n\n" + E(stats)) if stats else ""
        if u["status"] == "suspended":
            return self.send(uid, T(u, "suspended", days=ACCESS_DAYS), ik([[(T(u, "btn_reactivate"), "reactivate")]]))
        if u["status"] != "active":
            return self.send(uid, T(u, "sig_locked") + tail, ik([[(T(u, "btn_register"), "menu:register")]]))
        head = T(u, "sig_on", exp=",".join(map(str, self.exp))) if u.get("signals") else T(u, "sig_off")
        if self.db.kv("signals_paused"):
            head += "\n" + T(u, "paused")
        return self.send(uid, head + tail, ik([[(T(u, "btn_now"), "sig:now"), (T(u, "btn_off"), "sig:off") if u.get("signals") else (T(u, "btn_on"), "sig:on")]]))

    def show_now(self, u):
        uid = u["id"]
        if u["status"] != "active":
            return self.show_signals(u)
        top = self.engine.latest() if self.engine else []
        if not top:
            return self.send(uid, T(u, "now_none"))
        lang = u.get("lang") or "kg"
        L = S.T[lang]
        lines = [T(u, "now_head", t=S.hms(max(x["t"] for x in top), False))]
        for x in top[:3]:
            fx = x["mkt"] == "binodex"
            lines.append("• <b>%s</b> — %s %s · %s · %s" % (E(x["name"]), S.dir_txt(x, L), S.pct(x["p"] if x["dir"] > 0 else 1 - x["p"]),
                                                       ("BinoDex %d %s" % (x["exp"], L["min"])) if fx else "BingX · " + L["h1"],
                                                       E(L["acc"].format(a=S.pct(x["acc"]), b=S.pct(x["bl"])))))
        lines.append("\n" + E(L["honest"]))
        return self.send(uid, "\n".join(lines))

    # ---------- Профиль ----------
    def show_profile(self, u):
        uid = u["id"]
        b = u.get("broker")
        if b in ("bingx", "binodex"):
            br = "%s · <code>%s</code>" % ("BingX" if b == "bingx" else "BinoDex", E(u.get("trader_id") or "—"))
        else:
            br = "admin" if b == "admin" else T(u, "no_broker")
        yn = lambda v: "—" if v is None else ("✓" if v else "✗")  # noqa: E731
        api = T(u, "api_line", i=yn(u.get("invited")), d=yn(u.get("deposit")), k=yn(u.get("kyc")), tr=yn(u.get("traded")),
                bal="%.2f" % (u.get("balance") or 0), t=S.hms(u["check_t"], False) if u.get("check_t") else "—") if u.get("broker") == "bingx" and u.get("check_t") else ""
        text = T(u, "profile", st=T(u, "st").get(u["status"], u["status"]), br=br, api=api, sig="🔔" if u.get("signals") else "🔕", days=ACCESS_DAYS)
        rows = []
        if u["status"] == "suspended":
            rows.append([(T(u, "btn_reactivate"), "reactivate")])
        elif u.get("trader_id") and u["status"] in ("wait_dep", "active", "new"):
            rows.append([(T(u, "btn_recheck"), "recheck")])
        rows.append([(T(u, "btn_change"), "menu:register")])
        return self.send(uid, text, ik(rows))

    # ---------- Callback баскычтар ----------
    def on_callback(self, cq):
        fr, data = cq.get("from") or {}, cq.get("data") or ""
        self.api("answerCallbackQuery", {"callback_query_id": cq["id"]})
        u = self.ensure_user(fr)
        uid = u["id"]
        msg = cq.get("message") or {}
        if data.startswith("adm:") or data.startswith("bc:"):
            if not self.is_admin(uid):
                return None
            return self.on_admin_cb(u, data, msg)
        if data.startswith("reg:"):
            return self.show_broker(u, data[4:])
        if data.startswith("sendid:"):
            b = data[7:]
            self.db.upd(uid, step="id:" + b)
            return self.send(uid, T(u, "ask_id_" + b))
        if data == "recheck":
            if u.get("broker") == "binodex" and oauth_ready():
                return self.send(uid, T(u, "oauth_hint"), ik([[(T(u, "btn_oauth"), oauth_url(uid))]]))
            if u.get("trader_id"):
                return self.verify(u)
            return self.open(u, "register")
        if data == "proofbd":                              # толуктап, бирок баланс 0 — кол менен текшерүү
            self.db.upd(uid, status="pending", step="proof")
            return self.send(uid, T(u, "ask_proof"), ik([[(T(u, "btn_skip"), "skipproof")]]))
        if data == "reactivate":
            if u["status"] != "suspended":
                return self.show_profile(u)
            if u.get("broker") == "bingx" and self.bingx.ok() and u.get("trader_id"):
                return self.verify(u)
            if u.get("verified_at"):                          # мурда админ ырастаган — кайра кирүү жетиштүү
                return self.activate(u, "кайра кирди")
            return self.verify(u)
        if data == "skipproof":
            if u.get("step") == "proof":
                return self.to_review(u, None)
            return None
        if data.startswith("learn:"):
            i = int(data[6:])
            key, anchor = LESSON_KEYS[i]
            return self.send(uid, T(u, key), ik([[(T(u, "btn_video"), video_for(LESSON_VIDEO.get(key), u.get("lang")))],
                                                 [(T(u, "btn_lesson"), S.SITE_URL + "/learn.html" + ("#" + anchor if anchor else ""))]]))
        if data in ("sig:on", "sig:off"):
            self.db.upd(uid, signals=1 if data == "sig:on" else 0)
            return self.show_signals(self.db.user(uid))
        if data == "sig:now":
            return self.show_now(u)
        if data.startswith("menu:"):
            return self.open(u, data[5:])
        return None

    # ======================================================================
    #  ADMIN PANEL
    # ======================================================================
    def counts(self):
        return {r["status"]: r["n"] for r in self.db.q("SELECT status, COUNT(*) n FROM users GROUP BY status")}

    def adm_home(self, u, mid=None):
        c = self.counts()
        pend = c.get("pending", 0)
        paused = self.db.kv("signals_paused")
        text = ("🛠 <b>ADMIN PANEL</b>\n👥 Колдонуучулар: <b>%d</b> · ✅ активдүү %d · ⏳ заявка %d · 💳 толуктоо күтүүдө %d · ⛔ токтотулган %d\n"
                "BingX API: %s · BinoDex API: жок (кол менен) · Сигналдар: %s") % (
            sum(c.values()), c.get("active", 0), pend, c.get("wait_dep", 0), c.get("suspended", 0),
            "✓" if self.bingx.ok() else "ачкыч жок (кол менен)", "⏸ токтотулган" if paused else ("▶️ иштеп жатат" if self.engine else "өчүк (--no-signals)"))
        kb = ik([[("📣 Рассылка", "adm:bc"), ("🧾 Заявкалар (%d)" % pend, "adm:queue")],
                 [("👥 Трейдерлер", "adm:users"), ("📊 Статистика", "adm:stats")],
                 [("▶️ Сигналдарды улантуу" if paused else "⏸ Сигналдарды токтотуу", "adm:sig")]])
        if mid:
            return self.edit(u["id"], mid, text, kb)
        return self.send(u["id"], text, kb)

    def card(self, t):
        bal = (" · %.2f USDT" % t["balance"]) if t.get("balance") is not None else ""
        return "%s · %s · %s <code>%s</code>%s · кирген: %d күн мурун" % (
            self.user_link(t), TX["kg"]["st"].get(t["status"], t["status"]), E(t.get("broker") or "—"), E(t.get("trader_id") or "—"), bal, ago_days(t.get("last_seen")))

    def user_kb(self, t):
        return ik([[("✅ Ачуу", "adm:ok:%d" % t["id"]), ("⛔ Токтотуу", "adm:stop:%d" % t["id"])],
                   [("🔄 API текшерүү", "adm:chk:%d" % t["id"]) if t.get("broker") == "bingx" else ("—", None), ("💬 Жазуу", "adm:rep:%d" % t["id"])]])

    def adm_find(self, u, q):
        q = q.strip().lstrip("@")
        if not q:
            return self.send(u["id"], "Издөө: <code>/find 12345678</code> (трейдер ID, Telegram ID же @username)")
        rows = self.db.q("SELECT * FROM users WHERE trader_id=? OR CAST(id AS TEXT)=? OR lower(username)=lower(?) LIMIT 5", (q, q, q))
        if not rows:
            return self.send(u["id"], "Табылган жок: %s" % E(q))
        for t in rows:
            self.send(u["id"], self.card(t), self.user_kb(t))
        return True

    def on_admin_cb(self, u, data, msg):
        aid, mid = u["id"], msg.get("message_id")
        parts = data.split(":")
        if data == "adm:home":
            return self.adm_home(u, mid)
        if data == "adm:sig":
            self.db.kv_set("signals_paused", None if self.db.kv("signals_paused") else True)
            return self.adm_home(u, mid)
        if data == "adm:queue":
            rows = self.db.q("SELECT * FROM users WHERE status='pending' ORDER BY last_seen DESC LIMIT 15")
            if not rows:
                return self.send(aid, "🧾 Заявка жок.")
            for t in rows:
                self.send(aid, "🧾 " + self.card(t), ik([[("✅ Ачуу", "adm:ok:%d" % t["id"]), ("❌ Четке кагуу", "adm:no:%d" % t["id"])], [("💬 Жазуу", "adm:rep:%d" % t["id"])]]))
            return True
        if data == "adm:users":
            rows = self.db.q("SELECT * FROM users WHERE status IN ('active','wait_dep','suspended') AND broker<>'admin' ORDER BY last_seen DESC LIMIT 15")
            c = self.counts()
            tot_bal = self.db.one("SELECT COUNT(*) n, SUM(balance) s FROM users WHERE broker='bingx' AND status='active'") or {}
            head = "👥 <b>Трейдерлер</b> · %s\nBingX активдүүлөрдүн таза активи: %.2f USDT (%d трейдер)\nИздөө: <code>/find ID</code>\n" % (
                " · ".join("%s %d" % (TX["kg"]["st"].get(k, k), v) for k, v in sorted(c.items())), tot_bal.get("s") or 0, tot_bal.get("n") or 0)
            return self.send(aid, head + "\n".join("• " + self.card(t) for t in rows) if rows else head + "Азырынча жок.")
        if data == "adm:stats":
            c = self.counts()
            new7 = (self.db.one("SELECT COUNT(*) n FROM users WHERE created>?", (S.now_ms() - 7 * DAY,)) or {}).get("n", 0)
            hist = self.engine.st["history"] if self.engine else []
            st = S.stats_line(hist, "kg") or "сигнал статистикасы азырынча жок"
            bc = self.db.one("SELECT COUNT(*) n, SUM(sent) s FROM broadcasts WHERE status='done'") or {}
            src = self.db.q("SELECT COALESCE(src,'—') s, COUNT(*) n FROM users GROUP BY src ORDER BY n DESC LIMIT 5")
            return self.send(aid, "📊 <b>Статистика</b>\nБаары: %d · акыркы 7 күндө жаңы: %d\n%s\n%s\nРассылкалар: %d (жеткен билдирүүлөр: %d)\nБулактар (/start ?): %s" % (
                sum(c.values()), new7, " · ".join("%s %d" % (TX["kg"]["st"].get(k, k), v) for k, v in sorted(c.items())), E(st),
                bc.get("n") or 0, bc.get("s") or 0, ", ".join("%s %d" % (E(r["s"]), r["n"]) for r in src)))
        if parts[0] == "adm" and len(parts) == 3 and parts[2].lstrip("-").isdigit():
            act, tid = parts[1], int(parts[2])
            t = self.db.user(tid)
            if not t:
                return self.send(aid, "Колдонуучу табылган жок.")
            if act == "ok":
                self.activate(t, "админ")
                return self.send(aid, "✅ Ачылды: " + self.card(self.db.user(tid)))
            if act == "no":
                self.db.upd(tid, status="rejected", step=None)
                self.send(tid, T(t, "rejected"), self.menu_kb(t))
                return self.send(aid, "❌ Четке кагылды: " + self.card(self.db.user(tid)))
            if act == "stop":
                self.db.upd(tid, status="suspended")
                return self.send(aid, "⛔ Токтотулду: " + self.card(self.db.user(tid)))
            if act == "chk":
                if not self.bingx.ok():
                    return self.send(aid, "BingX API ачкычы коюлган эмес.")
                try:
                    r = self.bingx.check(t.get("trader_id"))
                except S.Fetch as e:
                    return self.send(aid, "⚠️ " + E(str(e)))
                if r is None:
                    self.db.upd(tid, invited=0, check_t=S.now_ms())
                    return self.send(aid, "BingX: бул UID биздин шилтеме менен эмес / табылган жок.")
                t = self.db.upd(tid, invited=1, deposit=int(r["deposit"]), kyc=int(r["kyc"]), traded=int(r["traded"]), balance=r["balance"], check_t=S.now_ms())
                return self.send(aid, "🔄 BingX: шилтеме ✓ · толуктоо %s · KYC %s · соода %s · таза актив %.2f USDT\n%s" % (
                    "✓" if r["deposit"] else "✗", "✓" if r["kyc"] else "✗", "✓" if r["traded"] else "✗", r["balance"], self.card(t)), self.user_kb(t))
            if act == "rep":
                self.db.kv_set("reply:%d" % aid, tid)
                return self.send(aid, "↩️ %s үчүн жоопту жазыңыз (кийинки билдирүүңүз ага жөнөтүлөт)." % self.user_link(t))
        if parts[0] == "adm" and parts[1] == "bc":
            self.db.kv_set("draft:%d" % aid, {"stage": "content", "btns": [], "aud": "all"})
            return self.send(aid, "📣 <b>Рассылка</b>\nБилдирүүнү жөнөтүңүз: текст, сүрөт же видео (жазуусу менен). Форматтоо жана эмодзи сакталат.\n"
                                  "Баскычтарды кийинки кадамда кошосуз.", ik([[("❌ Жокко чыгаруу", "bc:cancel")]]))
        if parts[0] == "bc":
            return self.bc_action(u, parts[1:], mid)
        return None

    # ---------- Рассылка ----------
    AUD = {"all": ("Баары", "status<>'blocked'"), "active": ("✅ Активдүүлөр", "status='active'"),
           "notactive": ("🆕 Доступу жоктор", "status IN ('new','wait_dep','pending','rejected')"), "suspended": ("⛔ Токтотулгандар", "status='suspended'")}
    AUD_ORDER = ["all", "active", "notactive", "suspended"]

    def bc_count(self, aud):
        return (self.db.one("SELECT COUNT(*) n FROM users WHERE " + self.AUD[aud][1]) or {}).get("n", 0)

    def bc_markup(self, d):
        rows = []
        for b in d.get("btns") or []:
            rows.append([{"text": b["t"], "url": b["u"]} if b.get("u") else {"text": b["t"], "callback_data": b["c"]}])
        return {"inline_keyboard": rows} if rows else None

    def bc_content(self, u, m):
        aid = u["id"]
        d = self.db.kv("draft:%d" % aid) or {}
        d.update(stage="edit", src=aid, mid=m["message_id"])
        self.db.kv_set("draft:%d" % aid, d)
        return self.bc_panel(u)

    def bc_panel(self, u, mid=None):
        aid = u["id"]
        d = self.db.kv("draft:%d" % aid)
        if not d or not d.get("mid"):
            return None
        p = {"chat_id": aid, "from_chat_id": d["src"], "message_id": d["mid"]}
        mk = self.bc_markup(d)
        if mk:
            p["reply_markup"] = mk
        self.api("copyMessage", p, chat=aid)                    # алдын ала көрүү: колдонуучулар так ушундай көрөт
        text = "👆 Алдын ала көрүү.\nКимге: <b>%s</b> (%d) · Баскычтар: %d" % (self.AUD[d["aud"]][0], self.bc_count(d["aud"]), len(d.get("btns") or []))
        kb = ik([[("➕ Баскыч кошуу", "bc:btn"), ("🧹 Баскычтарды тазалоо", "bc:clr")],
                 [("👥 Кимге: " + self.AUD[d["aud"]][0], "bc:aud")],
                 [("✅ Жөнөтүү", "bc:send"), ("❌ Жокко чыгаруу", "bc:cancel")]])
        return self.send(aid, text, kb)

    def bc_presets(self):
        out = [("🔗 BingX'те катталуу", "u", self.refs.get("bingx")), ("🔗 BinoDex'те катталуу", "u", self.refs.get("binodex")),
               ("⭐ Сигналдар", "c", "menu:signals"), ("📝 Катталуу", "c", "menu:register"), ("📚 Окуу", "c", "menu:learn"),
               ("🌐 AITRADING.KG", "u", S.SITE_URL + "/")]
        return [p for p in out if p[2]]

    def bc_custom(self, u, text):
        aid = u["id"]
        d = self.db.kv("draft:%d" % aid) or {}
        added, bad = 0, []
        for line in (text or "").splitlines():
            if "|" not in line:
                if line.strip():
                    bad.append(line.strip())
                continue
            t, url = [x.strip() for x in line.split("|", 1)]
            if t and re.match(r"^(https?|tg)://\S+$", url):
                d.setdefault("btns", []).append({"t": t[:64], "u": url})
                added += 1
            else:
                bad.append(line.strip())
        d["stage"] = "edit"
        self.db.kv_set("draft:%d" % aid, d)
        if bad:
            self.send(aid, "Түшүнүлгөн жок (формат: <code>Текст | https://шилтеме</code>):\n" + E("\n".join(bad)))
        return self.bc_panel(u)

    def bc_action(self, u, parts, mid):
        aid = u["id"]
        d = self.db.kv("draft:%d" % aid)
        act = parts[0] if parts else ""
        if act == "cancel" or not d:
            self.db.kv_set("draft:%d" % aid, None)
            return self.send(aid, "Рассылка жокко чыгарылды.") if act == "cancel" else None
        if act == "btn":
            pre = self.bc_presets()
            rows = [[(p[0], "bc:add:%d" % i)] for i, p in enumerate(pre)] + [[("✏️ Өз баскычым (текст | шилтеме)", "bc:custom")], [("⬅️ Артка", "bc:panel")]]
            note = "" if self.refs.get("bingx") and self.refs.get("binodex") else "\n(Брокер шилтемелери config.js'те заглушка болгондуктан көрүнбөйт.)"
            return self.send(aid, "Кайсы баскычты кошобуз?" + note, ik(rows))
        if act == "add":
            pre = self.bc_presets()
            i = int(parts[1])
            if 0 <= i < len(pre):
                t, kind, v = pre[i]
                d.setdefault("btns", []).append({"t": t, "u": v} if kind == "u" else {"t": t, "c": v})
                self.db.kv_set("draft:%d" % aid, d)
            return self.bc_panel(u)
        if act == "custom":
            d["stage"] = "custom"
            self.db.kv_set("draft:%d" % aid, d)
            return self.send(aid, "Баскычты жазыңыз — ар бир сапка бирден:\n<code>Катталуу | https://bingx.com/...</code>")
        if act == "clr":
            d["btns"] = []
            self.db.kv_set("draft:%d" % aid, d)
            return self.bc_panel(u)
        if act == "aud":
            d["aud"] = self.AUD_ORDER[(self.AUD_ORDER.index(d.get("aud", "all")) + 1) % len(self.AUD_ORDER)]
            self.db.kv_set("draft:%d" % aid, d)
            return self.bc_panel(u)
        if act == "panel":
            return self.bc_panel(u)
        if act == "send":
            n = self.bc_count(d["aud"])
            return self.send(aid, "📣 <b>%d</b> колдонуучуга (%s) жөнөтүлөт. Ырастайсызбы?" % (n, self.AUD[d["aud"]][0]),
                             ik([[("✅ Ооба, жөнөтүү", "bc:go"), ("⬅️ Артка", "bc:panel")]]))
        if act == "go":
            self.db.kv_set("draft:%d" % aid, None)
            ids = [r["id"] for r in self.db.q("SELECT id FROM users WHERE " + self.AUD[d["aud"]][1])]
            cur = self.db.x("INSERT INTO broadcasts(created,admin,from_chat,msg_id,buttons,audience,total,sent,failed,status) VALUES(?,?,?,?,?,?,?,0,0,'sending')",
                            (S.now_ms(), aid, d["src"], d["mid"], json.dumps(d.get("btns") or [], ensure_ascii=False), d["aud"], len(ids)))
            bid = cur.lastrowid
            threading.Thread(target=self.bc_run, args=(bid, aid, d, ids), daemon=True).start()
            return self.send(aid, "📣 Рассылка #%d башталды: %d колдонуучу." % (bid, len(ids)))
        return None

    def bc_run(self, bid, aid, d, ids):
        ok = fail = 0
        mk = self.bc_markup(d)
        for i, cid in enumerate(ids):
            p = {"chat_id": cid, "from_chat_id": d["src"], "message_id": d["mid"]}
            if mk:
                p["reply_markup"] = mk
            if self.api("copyMessage", p, chat=cid):
                ok += 1
            else:
                fail += 1
            if (i + 1) % 25 == 0:
                self.db.x("UPDATE broadcasts SET sent=?, failed=? WHERE id=?", (ok, fail, bid))
            time.sleep(0.05)                                     # Telegram: секундасына ~30 билдирмеден ашпайт
        self.db.x("UPDATE broadcasts SET sent=?, failed=?, status='done' WHERE id=?", (ok, fail, bid))
        self.send(aid, "📣 Рассылка #%d бүттү: ✓ %d · ✗ %d (ботту бөгөттөгөндөр же өчүрүлгөн аккаунттар)" % (bid, ok, fail))

    # ======================================================================
    #  Сигналдар → ачык доступтагыларга
    # ======================================================================
    def publish(self, kind, sg, hist):
        if kind == "signal":
            if self.db.kv("signals_paused"):
                return False
            users = self.db.q("SELECT * FROM users WHERE status='active' AND signals=1")
        else:
            users = self.db.q("SELECT u.* FROM users u JOIN sig_sent s ON s.user_id=u.id WHERE s.sig_id=? AND u.status<>'blocked'", (sg["id"],))
        sent = 0
        for u in users:
            lang = u.get("lang") or "kg"
            text = S.msg_signal(sg, lang) if kind == "signal" else S.msg_result(sg, hist, lang)
            if self.send(u["id"], text):
                sent += 1
                if kind == "signal":
                    self.db.x("INSERT OR IGNORE INTO sig_sent(sig_id,user_id) VALUES(?,?)", (sg["id"], u["id"]))
            time.sleep(0.04)
        if self.channel:
            lang = os.environ.get("TG_LANG", "kg")
            if self.send(self.channel, S.msg_signal(sg, lang) if kind == "signal" else S.msg_result(sg, hist, lang)):
                sent += 1
        print("  → %s: %d алуучу" % ("сигнал" if kind == "signal" else "жыйынтык", sent))
        return sent > 0

    # ======================================================================
    #  Фондогу жумуштар: 40 күн эрежеси, BingX балансын жаңыртуу
    # ======================================================================
    def maintenance(self):
        now = S.now_ms()
        for u in self.db.q("SELECT * FROM users WHERE status='active' AND broker<>'admin'"):
            d = ago_days(u["last_seen"])
            if d >= ACCESS_DAYS:
                self.db.upd(u["id"], status="suspended")
                self.send(u["id"], T(u, "susp_now", days=ACCESS_DAYS))
            elif d >= WARN_DAYS and not u.get("warned"):
                self.db.upd(u["id"], warned=1)
                self.send(u["id"], T(u, "warn", d=ACCESS_DAYS - d, days=d))
        if self.bingx.ok() and now - (self.db.kv("bal_t") or 0) > 6 * 3600000:   # таза активди 6 саатта бир жаңыртуу
            self.db.kv_set("bal_t", now)
            for u in self.db.q("SELECT * FROM users WHERE broker='bingx' AND trader_id IS NOT NULL AND status IN ('active','wait_dep')"):
                try:
                    r = self.bingx.check(u["trader_id"])
                except S.Fetch as e:
                    print("! BingX баланс: %s" % e)
                    break
                if r:
                    u2 = self.db.upd(u["id"], deposit=int(r["deposit"]), kyc=int(r["kyc"]), traded=int(r["traded"]), balance=r["balance"], check_t=S.now_ms())
                    if u["status"] == "wait_dep" and r["deposit"] and r["balance"] >= self.min_bal:
                        self.activate(u2, "BingX API (авто)")
                time.sleep(0.2)

    def loop_signals(self):
        while True:
            try:
                self.engine.run_once()
                w = self.engine.next_wake()
            except Exception as e:  # noqa: BLE001
                print("! сигнал сканери: %s" % self.tg.redact(e))
                w = 30
            time.sleep(w)

    def loop_maint(self):
        while True:
            try:
                self.maintenance()
            except Exception as e:  # noqa: BLE001
                print("! maintenance: %s" % self.tg.redact(e))
            time.sleep(1800)

    def set_commands(self):
        for lang, desc in (("kg", ["Баштоо", "⭐ Сигналдар", "📝 Брокерде катталуу", "📚 Окуу", "👤 Профиль", "💬 Колдоо", "🌍 Тил"]),
                           ("ru", ["Старт", "⭐ Сигналы", "📝 Регистрация у брокера", "📚 Обучение", "👤 Профиль", "💬 Поддержка", "🌍 Язык"])):
            cmds = [{"command": c, "description": d} for c, d in zip(["start", "signals", "register", "learn", "profile", "help", "lang"], desc)]
            p = {"commands": cmds}
            if lang == "ru":
                p["language_code"] = "ru"
            self.api("setMyCommands", p)

    def run(self):
        me = self.api("getMe", {})
        if not me:
            print("Telegram'га туташкан жок: токенди текшериңиз (Телеграм_бот_туташтыруу.bat).")
            return 1
        self.username = me.get("username")
        self.api("deleteWebhook", {"drop_pending_updates": False})
        self.set_commands()
        print("AITRADING.KG бот: @%s · админдер: %d · BingX API: %s · BinoDex API: жок (админ ✅/❌) · сигналдар: %s · база: %s" % (
            self.username, len(self.admins), "✓" if self.bingx.ok() else "жок", "✓ BinoDex %s мүн + BingX" % ",".join(map(str, self.exp)) if self.engine else "өчүк", DB_PATH))
        if not self.admins:
            print("! Админ жок: TELEGRAM_CHAT_ID же TELEGRAM_ADMIN_IDS'ке өзүңүздүн Telegram ID'ңизди коюңуз (Телеграм_бот_туташтыруу.bat).")
        if S.keep_awake(True):
            print("Компьютер бот иштеп жатканда уктабайт. Ноутбуктун капкагын жаппаңыз.")
        if self.engine:
            threading.Thread(target=self.loop_signals, daemon=True).start()
        threading.Thread(target=self.loop_maint, daemon=True).start()
        offset = int(self.db.kv("offset") or 0)
        while True:
            try:
                r = self.tg.call("getUpdates", {"offset": offset, "timeout": 25, "allowed_updates": ["message", "callback_query", "my_chat_member"]}, timeout=40)
            except S.Fetch as e:
                m = str(e)
                if "Conflict" in m:
                    print("! Бул бот башка жерде да иштеп жатат (экинчи терезе?). Бирөөнү жабыңыз.")
                    time.sleep(15)
                elif "timed out" not in m:
                    print("! getUpdates: %s" % m)
                    time.sleep(5)
                continue
            for upd in r.get("result") or []:
                offset = upd["update_id"] + 1
                try:
                    self.handle(upd)
                except Exception:  # noqa: BLE001 — бир ката ботту токтотпойт
                    print(self.tg.redact(traceback.format_exc()))
            self.db.kv_set("offset", offset)


# ======================================================================
def cmd_setup(lang):
    rc = S.cmd_setup(lang)
    if rc != 0:
        return rc
    tg = S.Telegram(False)
    chat = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
    if not re.match(r"^\d+$", chat) and not (os.environ.get("TELEGRAM_ADMIN_IDS") or "").strip():
        try:
            priv = [cid for cid, info in S.list_chats(tg).items() if str(info).startswith("private")]
        except S.Fetch:
            priv = []
        if len(priv) == 1:
            S.save_user_env("TELEGRAM_ADMIN_IDS", str(priv[0]))
            print("Админ (сиздин жеке чат): %s ✓" % priv[0])
        else:
            print("Админ белгисиз: ботко жеке чатта /start жазып, бул файлды кайра иштетиңиз.")
    rc = setup_bingx()
    setup_binodex_oauth(tg)
    print("\nДаяр. Эми Телеграм_бот.bat файлын эки жолу басыңыз.")
    return rc


def setup_bingx():
    print("\n BingX Agent API — UID, толуктоо жана таза активди автоматтык текшерүү үчүн\n " + "-" * 50)
    print(" BingX → Профиль → API Management → API түзүү. Уруксат: окуу гана (Read). Trade жана Withdraw КҮЙГҮЗБӨҢҮЗ.")
    print(" Ачкыч агенттик (партнёрдук) негизги аккаунттан болушу керек. IP чектөө коюлса — ушул компьютердин IP'си.\n")
    old = BingXAgent()
    key = S.ask("API Key (экранда көрүнбөйт; Enter — %s): " % ("мурункусун калтыруу" if old.ok() else "өткөрүп жиберүү"), secret=True)
    if not key:
        print("BingX API: %s." % ("мурункусу калды" if old.ok() else "өткөрүлдү — BingX ID'лерин админ кол менен ырастайт"))
        return 0
    sec = S.ask("Secret Key (экранда көрүнбөйт): ", secret=True) or ""
    ag = BingXAgent(key, sec)
    try:
        n = ag.invited_total()
    except (S.Fetch, LookupError) as e:
        print("! %s — ачкыч сакталган жок. Уруксаттарды текшерип, кайра иштетиңиз." % e)
        return 1
    S.save_user_env("BINGX_API_KEY", key)
    S.save_user_env("BINGX_API_SECRET", sec)
    print("BingX Agent API туташты ✓ · сиздин шилтеме менен катталгандар: %s. Ачкычтар Windows'ко сакталды (файлдарга эмес)." % n)
    return 0


def setup_binodex_oauth(tg):
    """«🔐 BinoDex аркылуу текшерүү»: client_id + бот менен сайттын жалпы сыры (LINK_SECRET)."""
    print("\n BinoDex: «Войти через BinoDex» менен автоматтык текшерүү (милдеттүү эмес)\n " + "-" * 50)
    print(" Керек: BinoDex кабинет → Broker API → клиент (redirect: https://aitrading.kg/oauth/callback) жана")
    print(" сайт Cloudflare Pages'те (functions/oauth/callback.js). Толугу — ОКУ_МЕНИ.md, 8-бөлүм.\n")
    old = (os.environ.get("BINODEX_CLIENT_ID") or "").strip()
    cid = S.ask("Broker API client_id (сыр эмес; Enter — %s): " % ("мурункусун калтыруу" if old else "өткөрүп жиберүү")) or old
    if not cid:
        print("BinoDex OAuth: өткөрүлдү — BinoDex ID'лерин админ кол менен ырастайт.")
        return
    if not re.match(r"^[0-9a-fA-F-]{20,64}$", cid):
        print("! client_id'ге окшобойт (мисалы 3fa85f64-5717-4562-b3fc-2c963f66afa6) — сакталган жок.")
        return
    if cid != old:
        S.save_user_env("BINODEX_CLIENT_ID", cid)
    secret = link_secret()
    if not secret:
        secret = secrets.token_urlsafe(32)
        S.save_user_env("LINK_SECRET", secret)
    try:
        bot = (tg.call("getMe") or {}).get("result", {}).get("username") or "<бот_логини>"
    except S.Fetch:
        bot = "<бот_логини>"
    print("BinoDex OAuth ботто күйдү ✓ (client_id жана LINK_SECRET Windows'ко сакталды).")
    print("\n Cloudflare → Pages → сайтыңыз → Settings → Variables and Secrets — төмөнкү 4 маанини «Secret» катары кошуңуз:")
    print("   BINODEX_CLIENT_ID     = %s" % cid)
    print("   BINODEX_CLIENT_SECRET = <Broker API клиентинин сыры — өзүңүз коюңуз>")
    print("   LINK_SECRET           = %s" % secret)
    print("   TG_BOT_USERNAME       = %s" % bot)
    print(" LINK_SECRET'ти эч кимге көрсөтпөңүз жана чатка жазбаңыз — ал бот менен сайттын ортосундагы кол.")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="AITRADING.KG Telegram-бот")
    ap.add_argument("--setup", action="store_true", help="бир жолу туташтыруу (Telegram + BingX API)")
    ap.add_argument("--no-signals", action="store_true", help="сигнал сканерисиз")
    ap.add_argument("--exp", default=os.environ.get("TG_EXP", "1"), help="BinoDex экспирациялары: 1,5")
    ap.add_argument("--lang", default=os.environ.get("TG_LANG", "kg"), choices=["kg", "ru"])
    a = ap.parse_args()
    if a.setup:
        return cmd_setup(a.lang)
    if not (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip():
        print("TELEGRAM_BOT_TOKEN коюлган эмес — бот иштебейт.\nТуташтыруу: Телеграм_бот_туташтыруу.bat (ОКУ_МЕНИ.md, 8-бөлүм).")
        return 2
    exp = sorted({max(1, min(240, int(float(x)))) for x in str(a.exp).split(",") if x.strip()})
    return App(signals=not a.no_signals, exp=exp).run()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nТоктотулду.")
