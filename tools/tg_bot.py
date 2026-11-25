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
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tg_signals as S  # noqa: E402
try:                                                  # ИИ-жардамчы (дожим + жооптор)
    import tg_agent as AG  # noqa: E402
except Exception:  # noqa: BLE001
    AG = None
try:                                                  # сүрөттөр (Pillow + DejaVu шрифти); жок болсо — текст гана
    import tg_cards as CARDS  # noqa: E402
    if not CARDS.available():
        CARDS = None
except Exception:  # noqa: BLE001
    CARDS = None

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
                             "Бул аккаунт башка партнёрго байланган — аны которууга болбойт.\n"
                             "👉 <b>ЖАҢЫ почта менен</b> биздин шилтеме аркылуу кайра катталыңыз, анан кайра текшериңиз.",
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
                       "Бул аккаунт башка партнёрго байланган.\n👉 <b>ЖАҢЫ почта менен</b> биздин шилтеме аркылуу жаңы аккаунт ачып, жаңы UID'ни жөнөтүңүз.",
        "wait_dep": "✓ Катталуу ырасталды.\n💳 Эми эсепти толуктаңыз{min}. Толуктагандан кийин «🔄 Кайра текшерүү» баскычын басыңыз.",
        "min_txt": " (кеминде {v} USDT таза актив)",
        "ask_proof": "📷 Толуктоонун скриншотун жөнөтүңүз (BinoDex → тарых же баланс). Скриншот жок болсо — «Өткөрүү».",
        "btn_skip": "Өткөрүү",
        "sent_review": "⏳ Заявка админге жөнөтүлдү. Текшерилгенде бот өзү жазат.",
        "api_down": "⏳ Брокердин API'си азыр жооп бербей жатат. Заявка админге жөнөтүлдү — кол менен текшерилет.",
        "activated": "✅ <b>Доступ ачылды!</b>\n⭐ Сигналдар ушул чатка келет. Ар бир сигнал — ыктымалдык, кепилдик эмес.\n"
                     "Адегенде кичине суммалар менен текшериңиз. Сигналдарды өчүрүү: «⭐ Сигналдар» → 🔕.",
        "rejected": "❌ Заявка ырасталган жок: бул ID биздин командада табылган жок — балким, аккаунт башка партнёр аркылуу ачылган.\n"
                    "👉 <b>ЖАҢЫ почта менен</b> төмөнкү шилтеме аркылуу кайра катталыңыз, толуктаңыз жана жаңы ID'ни жөнөтүңүз.\nСуроо болсо — «💬 Колдоо».",
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
                             "Этот аккаунт привязан к другому партнёру — перенести его нельзя.\n"
                             "👉 Зарегистрируйтесь заново по нашей ссылке <b>на НОВУЮ почту</b> и проверьте снова.",
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
                       "Этот аккаунт привязан к другому партнёру.\n👉 Откройте новый аккаунт по нашей ссылке <b>на НОВУЮ почту</b> и пришлите новый UID.",
        "wait_dep": "✓ Регистрация подтверждена.\n💳 Теперь пополните счёт{min}. После пополнения нажмите «🔄 Проверить снова».",
        "min_txt": " (не меньше {v} USDT чистых активов)",
        "ask_proof": "📷 Пришлите скриншот пополнения (BinoDex → история или баланс). Нет скриншота — «Пропустить».",
        "btn_skip": "Пропустить",
        "sent_review": "⏳ Заявка отправлена админу. После проверки бот напишет сам.",
        "api_down": "⏳ API брокера сейчас не отвечает. Заявка отправлена админу — проверит вручную.",
        "activated": "✅ <b>Доступ открыт!</b>\n⭐ Сигналы будут приходить в этот чат. Каждый сигнал — вероятность, а не гарантия.\n"
                     "Начните с небольших сумм. Выключить сигналы: «⭐ Сигналы» → 🔕.",
        "rejected": "❌ Заявка не подтверждена: этот ID не найден в нашей команде — возможно, аккаунт открыт через другого партнёра.\n"
                    "👉 Зарегистрируйтесь заново по ссылке ниже <b>на НОВУЮ почту</b>, пополните счёт и пришлите новый ID.\nВопросы — «💬 Поддержка».",
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


FREE_SIGNALS = int(os.environ.get("TG_FREE_SIGNALS") or 2)       # катталбагандарга акысыз сигнал
SITE_ACCESS_DAYS = 7                                                # сайттагы доступ шилтемеси канча күн жарактуу
TX_GATE = {
    "kg": {
        "free_tag": "🎁 Акысыз сигнал {n}/{m}",
        "free_last": "🔒 <b>Акысыз сигналдар бүттү ({m}/{m}).</b>\nБардык сигналдарды алуу үчүн:\n1. Биздин шилтеме менен брокерде катталыңыз\n"
                     "2. Эсепти толуктаңыз (милдеттүү)\n3. ID'ңизди ушул ботко жибериңиз — текшерилгенден кийин сигналдар ачылат.",
        "free_left": "🎁 Сизде дагы <b>{n}</b> акысыз сигнал бар — «⭐ Азыр эң мыкты» же жаңы сигнал келгенде.",
        "free_none": "🔒 Акысыз {m} сигнал колдонулду. Андан ары — катталуу + толуктоо милдеттүү.",
        "btn_site_sig": "🌐 Сайтта ачуу (сигналдар)",
        "ask_wa": "📱 Катталуудан мурун <b>WhatsApp номериңизди</b> жазыңыз (мисалы +996 700 123 456).\n"
                  "Команда катталуу жана толуктоо боюнча жардам берет. Почта жана сырсөз керек эмес.",
        "bad_wa": "Номер туура эмес. Толук жазыңыз, мисалы +996 700 123 456.",
        "wa_ok": "✓ Рахмат! Номер сакталды. Эми брокерди тандаңыз:",
    },
    "ru": {
        "free_tag": "🎁 Бесплатный сигнал {n}/{m}",
        "free_last": "🔒 <b>Бесплатные сигналы закончились ({m}/{m}).</b>\nЧтобы получать все сигналы:\n1. Зарегистрируйтесь у брокера по нашей ссылке\n"
                     "2. Пополните счёт (обязательно)\n3. Отправьте ID в этот бот — после проверки сигналы откроются.",
        "free_left": "🎁 У вас ещё <b>{n}</b> бесплатных сигнала — «⭐ Лучшее сейчас» или когда придёт новый сигнал.",
        "free_none": "🔒 Бесплатные {m} сигнала использованы. Дальше — регистрация + пополнение обязательно.",
        "btn_site_sig": "🌐 Открыть на сайте (сигналы)",
        "ask_wa": "📱 Перед регистрацией напишите <b>номер WhatsApp</b> (например +996 700 123 456).\n"
                  "Команда поможет с регистрацией и пополнением. Почта и пароль не нужны.",
        "bad_wa": "Неверный номер. Введите полностью, например +996 700 123 456.",
        "wa_ok": "✓ Спасибо! Номер сохранён. Теперь выберите брокера:",
    },
}
for _l, _d in TX_GATE.items():
    TX[_l].update(_d)
TX_CH = {
    "kg": {"btn_channel": "🔐 Жабык каналга кирүү", "ch_invite": "🔐 <b>{b} жабык каналы</b> сиз үчүн ачык.\nШилтеме жеке жана бир жолку (24 саат). Аны эч кимге бербеңиз.",
           "ch_none": "Жабык канал азырынча даярдалып жатат — сигналдар ушул чатка келет."},
    "ru": {"btn_channel": "🔐 Войти в закрытый канал", "ch_invite": "🔐 <b>Закрытый канал {b}</b> открыт для вас.\nСсылка личная и одноразовая (24 часа). Никому её не передавайте.",
           "ch_none": "Закрытый канал ещё готовится — сигналы будут приходить в этот чат."},
}
for _l, _d in TX_CH.items():
    TX[_l].update(_d)
TX["kg"].update({"join_need": "🔐 <b>{b} жабык каналы</b> — команданын мүчөлөрү үчүн гана.\nКирүү үчүн: биздин шилтеме менен {b}'де катталыңыз, эсепти толуктаңыз жана ID'ни ботко жибериңиз — текшерилгенден кийин бот өзү шилтеме берет.",
                 "btn_open_bot": "🤖 Ботту ачуу"})
TX["ru"].update({"join_need": "🔐 <b>Закрытый канал {b}</b> — только для участников команды.\nЧтобы войти: зарегистрируйтесь в {b} по нашей ссылке, пополните счёт и отправьте ID в бот — после проверки бот сам даст ссылку.",
                 "btn_open_bot": "🤖 Открыть бота"})


def channel_kind(title):
    """Каналдын аталышынан: BinoDex же BingX (фьючерс) каналыбы."""
    low = (title or "").lower()
    if any(w in low for w in ("binodex", "бинодекс", "бинодэкс", "bino")):
        return "binodex"
    if any(w in low for w in ("bingx", "бингх", "бингикс", "фьючерс", "futures", "фьюч")):
        return "bingx"
    return None
try:
    import tg_futures as FUT  # noqa: E402  — BingX фьючерс сигналдары
except Exception:  # noqa: BLE001
    FUT = None


def _multipart(fields, files):
    """Telegram'га файл жүктөө үчүн multipart/form-data."""
    import io as _io
    b = "----aitrading" + secrets.token_hex(8)
    out = _io.BytesIO()
    for k, v in fields.items():
        out.write(('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n' % (b, k)).encode("utf-8"))
        out.write(str(v).encode("utf-8") + b"\r\n")
    for k, (fn, data, ct) in files.items():
        out.write(('--%s\r\nContent-Disposition: form-data; name="%s"; filename="%s"\r\nContent-Type: %s\r\n\r\n' % (b, k, fn, ct)).encode("utf-8"))
        out.write(data + b"\r\n")
    out.write(("--%s--\r\n" % b).encode("utf-8"))
    return out.getvalue(), "multipart/form-data; boundary=" + b


def norm_wa(s):
    """WhatsApp номери: +996700123456. Кыргызстандын кыска жазылышы да кабыл алынат."""
    s = str(s or "").strip()
    plus = s.startswith("+") or s.startswith("00")
    d = re.sub(r"\D", "", s)
    if s.startswith("00"):
        d = d[2:]
    if not plus and re.match(r"^0\d{9}$", d):
        d = "996" + d[1:]
    if not plus and re.match(r"^\d{9}$", d):
        d = "996" + d
    return "+" + d if re.match(r"^\d{10,15}$", d) else None


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
            cols = {r[1] for r in self.c.execute("PRAGMA table_info(users)").fetchall()}
            for col, typ in (("free_sent", "INTEGER DEFAULT 0"), ("wa", "TEXT")):
                if col not in cols:
                    self.c.execute("ALTER TABLE users ADD COLUMN %s %s" % (col, typ))
            self.c.execute("CREATE TABLE IF NOT EXISTS leads(id TEXT PRIMARY KEY, t INTEGER, wa TEXT, name TEXT, broker TEXT, lang TEXT, "
                           "page TEXT, country TEXT, src TEXT, tg_id INTEGER)")
            self.c.commit()

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


def binodex_status():
    """BinoDex: кирүү OAuth аркылуу (сайт + бот бир LINK_SECRET), котировкалар — Kraken/Binance (BinoDex'те котировка API жок)."""
    return "✓ OAuth (вход через BinoDex)" if oauth_ready() else "❌ OAuth не настроен (BINODEX_CLIENT_ID / LINK_SECRET)"


def mask_wa(wa):
    wa = str(wa or "")
    return (wa[:7] + "•••" + wa[-2:]) if len(wa) > 9 else "•••"


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


def site_access_url(tg_id, path="/forecast.html"):
    """Сайттагы сигналдарга доступ: functions/api/access.js ушул колду текшерет."""
    if not link_secret():
        return None
    tg36, exp36 = b36(tg_id), b36(int(time.time()) + SITE_ACCESS_DAYS * 86400)
    return "%s%s#acc=%s.%s.%s" % (S.SITE_URL, path, tg36, exp36, link_sig("acc|%s|%s" % (tg36, exp36), 22))


MIN_DEP_BD = os.environ.get("TG_MIN_DEP_BINODEX", "20")          # BinoDex: минималдуу толуктоо, $
DEP_TX = {
    "kg": "💳 <b>Сигналдар толуктоодон кийин ачылат.</b>\nBinoDex эсебиңизди <b>кеминде ${m}</b> толуктаңыз.\n\n"
          "Толуктагандан кийин:\n🔐 «BinoDex аркылуу текшерүү» — бот өзү текшерет (скриншотсуз)\n📷 же толуктоонун скриншотун жөнөтүңүз.",
    "ru": "💳 <b>Сигналы открываются после пополнения.</b>\nПополните счёт BinoDex <b>минимум на ${m}</b>.\n\n"
          "После пополнения:\n🔐 «Проверить через BinoDex» — бот проверит сам (без скриншота)\n📷 или пришлите скриншот пополнения.",
}


def app_url(u, admin=False):
    """Mini App шилтемеси: доступу барларга ?acc=<кол коюлган токен> (сайттагы access.js текшерет)."""
    base = S.SITE_URL + "/forecast.html"
    if (admin or u.get("status") == "active") and link_secret():
        tg36, exp36 = b36(u["id"]), b36(int(time.time()) + SITE_ACCESS_DAYS * 86400)
        return "%s?acc=%s.%s.%s" % (base, tg36, exp36, link_sig("acc|%s|%s" % (tg36, exp36), 22))
    return base


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
        own = (os.environ.get("TG_OWNER_ID") or (chat if re.match(r"^\d+$", chat) else "")).strip()
        self.owner = int(own) if re.match(r"^\d+$", own) else (min(self.admins) if self.admins else None)
        self.channel = chat if chat.startswith("-") or chat.startswith("@") else None
        self.exp = exp or [1]
        self.engine = None
        if signals:
            a = argparse.Namespace(dry_run=False, lang=os.environ.get("TG_LANG", "kg"), state=os.path.join(HERE, "tg_state.json"),
                                   exp=self.exp, markets={"binodex"} | ({"bingx"} if os.environ.get("TG_SPOT_BINGX") == "1" else set()),
                                   force=False, verbose=False)   # BingX — фьючерс гана (tg_futures); спот: TG_SPOT_BINGX=1
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

    def photo(self, chat, img, caption, kb=None, thread=None):
        """img: PNG байттары (биринчи жолу жүктөлөт) же Telegram file_id (кайра колдонуу). Кайтарат: file_id же None."""
        try:
            if isinstance(img, (bytes, bytearray)):
                fields = {"chat_id": chat, "caption": caption, "parse_mode": "HTML"}
                if thread:
                    fields["message_thread_id"] = thread
                if kb is not None:
                    fields["reply_markup"] = json.dumps(kb, ensure_ascii=False)
                body, ct = _multipart(fields, {"photo": ("aitrading.png", bytes(img), "image/png")})
                req = urllib.request.Request("https://api.telegram.org/bot%s/sendPhoto" % self.tg.token, data=body,
                                             headers={"Content-Type": ct, "User-Agent": S.UA})
                with urllib.request.urlopen(req, timeout=40) as r:
                    j = json.loads(r.read().decode("utf-8"))
                res = j.get("result") if j.get("ok") else None
            else:
                pl = {"chat_id": chat, "photo": img, "caption": caption, "parse_mode": "HTML"}
                if thread:
                    pl["message_thread_id"] = thread
                if kb is not None:
                    pl["reply_markup"] = kb
                res = self.api("sendPhoto", pl, chat=chat)
            if res and res.get("photo"):
                return res["photo"][-1]["file_id"]
        except Exception as e:  # noqa: BLE001 — сүрөт өтпөсө текст жөнөтүлөт
            print("! sendPhoto: %s" % self.tg.redact(e))
        return None

    def send_card(self, chat, kind, lang, caption, kb=None):
        """Туруктуу сүрөттөр (доступ ачылды / акысыз бүттү): ар бир тилге бир жолу тартылат, анан file_id."""
        key = "card:%s:%s" % (kind, lang)
        if not hasattr(self, "_cards"):
            self._cards = {}
        img = self._cards.get(key)
        if img is None and CARDS is not None:
            try:
                img = CARDS.card_access(lang) if kind == "access" else CARDS.card_free_end(lang, FREE_SIGNALS)
            except Exception as e:  # noqa: BLE001
                print("! card %s: %s" % (kind, e))
                img = None
        if img is not None and len(caption) <= 1024:
            fid = self.photo(chat, img, caption, kb)
            if fid:
                self._cards[key] = fid
                return True
        return self.send(chat, caption, kb)

    def send(self, chat, text, kb=None, preview=False, thread=None):
        p = {"chat_id": chat, "text": text, "parse_mode": "HTML", "link_preview_options": {"is_disabled": not preview}}
        if thread:
            p["message_thread_id"] = thread
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

    def report_err(self, where, e=None, tb=None):
        """Ката: бир түрү саатына бир жолу — ээсине кабар + сайттагы журналга (functions/api/errlog.js)."""
        try:
            msg = ("%s: %s" % (type(e).__name__, self.tg.redact(str(e))) if e is not None else "error")[:300]
            sig = hashlib.sha1((where + "|" + msg[:80]).encode("utf-8")).hexdigest()[:10]
            n = int(self.db.kv("errn:" + sig) or 0) + 1
            self.db.kv_set("errn:" + sig, n)
            if time.time() - int(self.db.kv("errt:" + sig) or 0) < 3600:
                return
            self.db.kv_set("errt:" + sig, int(time.time()))
            if tb is None and e is not None and e.__traceback__ is not None:
                tb = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            tb = self.tg.redact(tb or "")[-2500:]
            if self.owner:
                self.send(self.owner, "⚠️ <b>Ошибка бота</b> · %s\n<code>%s</code>\nПовторов: %d · отчёт передан на исправление." % (E(where), E(msg), n))
            item = {"where": where, "msg": msg, "sig": sig, "n": n, "t": S.now_ms(), "tb": tb}
            threading.Thread(target=self.push_err, args=(item,), daemon=True).start()
        except Exception as e2:  # noqa: BLE001 — журнал ботту токтотпосун
            print("! report_err: %s" % e2)

    def push_err(self, item):
        if not link_secret():
            return
        ts = str(S.now_ms())
        body = json.dumps(item, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(S.SITE_URL + "/api/errlog", data=body, method="POST",
                                     headers={"content-type": "application/json", "x-ts": ts, "x-sig": link_sig("err|" + ts, 22), "User-Agent": S.UA})
        try:
            urllib.request.urlopen(req, timeout=15).read()
        except Exception as e:  # noqa: BLE001
            print("! errlog push: %s" % e)

    def menu_btn(self, u, force=False):
        """Ар бир колдонуучунун «Меню» ордуна — Mini App баскычы. Токен 7 күн: 3 күндө бир же статус өзгөргөндө жаңыртылат."""
        uid = u["id"]
        st = "a" if (u.get("status") == "active" or self.is_admin(uid)) else "f"
        k = "mb:%d" % uid
        old = self.db.kv(k) or ""
        if not force and old.startswith(st + ":") and time.time() - int(old.split(":")[1]) < 3 * 86400:
            return None
        self.db.kv_set(k, "%s:%d" % (st, int(time.time())))
        return self.api("setChatMenuButton", {"chat_id": uid, "menu_button": {
            "type": "web_app", "text": "📱 AITRADING", "web_app": {"url": app_url(u, self.is_admin(uid))}}})

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
        if self.is_admin(uid) and (u["status"] != "active" or u.get("broker") != "admin"):
            kw.update(status="active", broker="admin")      # админ — дайыма толук доступ
        if u["status"] == "blocked":                          # ботту кайра ачты
            kw["status"] = u.get("prev_status") or "new"
        return self.db.upd(uid, **kw)

    # ---------- Жаңыртууларды иштетүү ----------
    def handle(self, upd):
        if "callback_query" in upd:
            return self.on_callback(upd["callback_query"])
        mcm = upd.get("my_chat_member")
        if mcm and mcm.get("chat", {}).get("type") in ("channel", "supergroup"):
            return self.on_channel(mcm)
        if upd.get("chat_join_request"):
            return self.on_join_request(upd["chat_join_request"])
        if upd.get("channel_post"):
            cp = upd["channel_post"].get("chat") or {}
            if cp.get("id") and cp["id"] not in (self.db.kv("ch:bingx"), self.db.kv("ch:binodex")) and (channel_kind(cp.get("title")) or not self.db.kv("chask:%s" % cp["id"])):
                self.on_channel({"chat": cp, "new_chat_member": {"status": "administrator"}})
            return None
        if mcm and mcm.get("chat", {}).get("type") == "private":
            st = (mcm.get("new_chat_member") or {}).get("status")
            u = self.db.user(mcm["chat"]["id"])
            if u and st == "kicked" and u["status"] != "blocked":
                self.db.upd(u["id"], prev_status=u["status"], status="blocked")
            return None
        m = upd.get("message")
        gch = (m or {}).get("chat") or {}
        if gch.get("type") in ("group", "supergroup"):          # топ (группа): админ жазса — кайсы сигналдар экенин сурайт
            gid = (m.get("from") or {}).get("id")
            th = m.get("message_thread_id") if m.get("is_topic_message") else None
            here = (gch.get("id"), th)
            linked = [(self.db.kv("ch:" + k), self.db.kv("th:" + k)) for k in ("bingx", "binodex")]
            gk = "gask:%s:%s" % (gch.get("id"), th or 0)
            cmd = (m.get("text") or "").strip().lower().split("@")[0]
            if gid and self.is_admin(gid) and (cmd == "/link" or (cmd in ("тест", "test") and here not in linked)):
                self.db.kv_set(gk, 1)
                return self.ask_channel(gid, gch, th)
            return None
        if not m or m.get("chat", {}).get("type") != "private" or not m.get("from"):
            return None
        text = (m.get("text") or "").strip()
        start_arg = text.split(" ", 1)[1].strip() if text.startswith("/start ") else ""
        src = start_arg[:32] if start_arg and not start_arg.startswith("bx_") else None
        u = self.ensure_user(m["from"], src)
        uid = u["id"]
        try:
            self.menu_btn(u)
        except Exception as e:  # noqa: BLE001 — меню баскычы милдеттүү эмес
            print("! menu_btn: %s" % e)
        fo = m.get("forward_origin") or {}
        fch = (fo.get("chat") if fo.get("type") == "channel" else None) or m.get("forward_from_chat")
        if fch and fch.get("type") == "channel" and self.is_admin(uid):
            return self.ask_channel(uid, fch)
        if start_arg.startswith("ld_"):                    # сайтта WhatsApp калтырып, ботко келди
            self.link_lead(u, start_arg[3:40])
            u = self.db.user(uid)
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
        if cmd in ("/kanal", "/channels") and self.is_admin(uid):
            return self.adm_channels(u)
        act = CMDS.get(cmd) if cmd else ACTIONS.get(text)
        if act == "find" and self.is_admin(uid):
            return self.adm_find(u, text.split(" ", 1)[1] if " " in text else "")
        if act:
            return self.open(u, act)
        b = u.get("broker") if u.get("broker") in ("bingx", "binodex") else self.db.kv("regb:%d" % uid)
        if b in ("bingx", "binodex") and u.get("status") != "active" and re.match(r"^\s*\d{5,15}\s*$", text or ""):
            u = self.db.upd(uid, step="id:" + b)             # «Отправить ID» баспай эле ID жазды
            return self.on_step(u, m, text)
        if AG is not None and text and not text.startswith("/") and AG.ai_on():
            r = self.ai_answer(u, text)
            if r:
                return r
        return self.send(uid, T(u, "menu_hint"), self.menu_kb(u))

    def ai_answer(self, u, text):
        uid = u["id"]
        dk = "ai:%d:%s" % (uid, S.datetime.now(S.BISHKEK).strftime("%Y%m%d"))
        n = int(self.db.kv(dk) or 0)
        if n >= AG.AI_DAILY:
            return None
        hk = "aih:%d" % uid
        try:
            hist = json.loads(self.db.kv(hk) or "[]")
        except ValueError:
            hist = []
        self.api("sendChatAction", {"chat_id": uid, "action": "typing"})
        r = AG.reply(u, text, self.free_left(u), hist)
        if not r:
            return None
        self.db.kv_set(dk, n + 1)
        self.db.kv_set(hk, json.dumps((hist + [{"role": "user", "content": text[:800]}, {"role": "assistant", "content": r[:1500]}])[-8:], ensure_ascii=False))
        return self.api("sendMessage", {"chat_id": uid, "text": r[:4000], "reply_markup": self.menu_kb(u)}, chat=uid)

    def open(self, u, act, mid=None):
        uid = u["id"]
        if act == "start":
            return self.send(uid, T(u, "welcome", name=E(u.get("first_name") or ""), days=ACCESS_DAYS), self.menu_kb(u))
        if act == "lang":
            u = self.db.upd(uid, lang="ru" if u.get("lang") == "kg" else "kg")
            return self.send(uid, T(u, "lang_set"), self.menu_kb(u))
        if act == "register":
            if not u.get("wa") and not self.is_admin(uid):
                self.db.upd(uid, step="wa")
                return self.send(uid, T(u, "ask_wa"))
            return self.send(uid, T(u, "reg_choose"), ik([[("BingX", "reg:bingx"), ("BinoDex", "reg:binodex")]]))
        if act == "signals":
            return self.show_signals(u)
        if act == "learn":
            L = T(u, "lessons")
            return self.send(uid, T(u, "learn"), ik([[(L[i], "learn:%d" % i)] for i in range(len(L))] + [[(T(u, "btn_lesson"), S.SITE_URL + "/learn.html")]]))
        if act == "profile":
            return self.show_profile(u)
        if act == "site":
            self.menu_btn(u, force=True)
            return self.send(uid, T(u, "site"), {"inline_keyboard": [
                [{"text": "📱 Открыть в Telegram" if (u.get("lang") == "ru") else "📱 Telegram ичинде ачуу", "web_app": {"url": app_url(u, self.is_admin(uid))}}],
                [{"text": T(u, "btn_site"), "url": S.SITE_URL + "/"}]]})
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
        if step == "wa":
            c = m.get("contact") or {}
            wa = norm_wa(c.get("phone_number") or text)
            if not wa:
                return self.send(uid, T(u, "bad_wa"))
            u = self.db.upd(uid, wa=wa, step=None)
            lid = "bot-%d" % uid
            self.db.x("INSERT OR IGNORE INTO leads(id,t,wa,name,broker,lang,page,country,src,tg_id) VALUES(?,?,?,?,?,?,?,?,?,?)",
                      (lid, S.now_ms(), wa, u.get("first_name") or "", "", u.get("lang") or "kg", "bot", "", "bot", uid))
            self.lead_note(lid, "бот", "%s · %s" % (E(mask_wa(wa)), self.user_link(u)))
            return self.send(uid, T(u, "wa_ok"), ik([[("BingX", "reg:bingx"), ("BinoDex", "reg:binodex")]]))
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

    def need_deposit(self, u):
        uid = u["id"]
        u = self.db.upd(uid, status="wait_dep", step=None)
        rows = []
        if oauth_ready():
            rows.append([(T(u, "btn_oauth"), oauth_url(uid))])
        rows.append([(T(u, "btn_proof"), "proofbd")])
        if self.refs.get("binodex"):
            rows.append([("💳 Пополнить BinoDex" if u.get("lang") == "ru" else "💳 BinoDex толуктоо", self.refs.get("binodex"))])
        return self.send(uid, DEP_TX.get(u.get("lang") or "kg", DEP_TX["kg"]).replace("{m}", MIN_DEP_BD), ik(rows))

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
        self.send_card(uid, "access", u.get("lang") or "kg", T(u, "activated"), self.menu_kb(u))
        self.send_invite(u)
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
            left = self.free_left(u)
            extra = "\n\n" + (T(u, "free_left", n=left) if left > 0 else T(u, "free_none", m=FREE_SIGNALS))
            return self.send(uid, T(u, "sig_locked") + extra + tail,
                             ik([[(T(u, "btn_now"), "sig:now")] if left > 0 else [], [(T(u, "btn_register"), "menu:register")]]))
        head = T(u, "sig_on", exp=",".join(map(str, self.exp))) if u.get("signals") else T(u, "sig_off")
        if self.db.kv("signals_paused"):
            head += "\n" + T(u, "paused")
        return self.send(uid, head + tail, ik([[(T(u, "btn_now"), "sig:now"), (T(u, "btn_off"), "sig:off") if u.get("signals") else (T(u, "btn_on"), "sig:on")],
                                               [(T(u, "btn_site_sig"), site_access_url(uid))],
                                               [(T(u, "btn_channel"), "chinv")] if self.channel_for(u) else []]))

    def show_now(self, u):
        uid = u["id"]
        free = u["status"] != "active"
        if free and self.free_left(u) <= 0:
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
        if free:
            u = self.db.upd(uid, free_sent=(u.get("free_sent") or 0) + 1)
            lines.append("\n" + T(u, "free_tag", n=u["free_sent"], m=FREE_SIGNALS))
        self.send(uid, "\n".join(lines))
        if free and self.free_left(u) <= 0:
            self.send_card(uid, "free", u.get("lang") or "kg", T(u, "free_last", m=FREE_SIGNALS), ik([[(T(u, "btn_register"), "menu:register")]]))
        return True

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
        if data.startswith("nb:"):
            return self.notebook(uid, data, msg)
        if data.startswith("chset:") and self.is_admin(uid):
            _, kind, rest = data.split(":", 2)
            cid, _, th = rest.partition(":")
            if kind in ("bingx", "binodex") and re.match(r"^-?\d+$", cid) and re.match(r"^\d*$", th):
                self.db.kv_set("ch:" + kind, int(cid))
                self.db.kv_set("th:" + kind, int(th) if th else None)
                self.db.kv_set("gask:%s:%s" % (cid, th or 0), None)
                return self.send(uid, "✅ Канал → %s ✓" % ("BingX (фьючерс)" if kind == "bingx" else "BinoDex"))
            return None
        if data == "chinv":
            return self.send_invite(u)
        if data.startswith("reg:"):
            self.db.kv_set("regb:%d" % uid, data[4:])
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
        if data == "fu:off":
            k = "fu:%d" % uid
            try:
                st = json.loads(self.db.kv(k) or "{}")
            except ValueError:
                st = {}
            st["off"] = 1
            self.db.kv_set(k, json.dumps(st))
            return self.send(uid, "🔕 Хорошо, напоминаний больше не будет." if u.get("lang") == "ru" else "🔕 Макул, мындан ары эскертпейм.")
        if data == "skipproof":
            if u.get("step") != "proof":
                return None
            if u.get("broker") == "binodex":
                return self.need_deposit(u)
            return self.to_review(u, None)
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
                "BingX API: %s · BinoDex: %s · Сигналдар: %s") % (
            sum(c.values()), c.get("active", 0), pend, c.get("wait_dep", 0), c.get("suspended", 0),
            "✓" if self.bingx.ok() else "ачкыч жок (кол менен)", binodex_status(), "⏸ токтотулган" if paused else ("▶️ иштеп жатат" if self.engine else "өчүк (--no-signals)"))
        kb = ik([[("📣 Рассылка", "adm:bc"), ("🧾 Заявкалар (%d)" % pend, "adm:queue")],
                 [("👥 Трейдерлер", "adm:users"), ("📊 Статистика", "adm:stats")],
                 [("▶️ Сигналдарды улантуу" if paused else "⏸ Сигналдарды токтотуу", "adm:sig")]] + ([[("📒 Блокнот заявок", "nb:p:0"), ("👥 Клиенты бота", "nb:c:in:0")], [("📥 Скачать PDF (заявки + клиенты)", "nb:pdf")]] if u["id"] == self.owner else []))
        if mid:
            return self.edit(u["id"], mid, text, kb)
        return self.send(u["id"], text, kb)

    def card(self, t):
        bal = (" · %.2f USDT" % t["balance"]) if t.get("balance") is not None else ""
        bal += (" · WA %s" % E(mask_wa(t["wa"]))) if t.get("wa") else ""
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
                b = t.get("broker") if t.get("broker") in ("bingx", "binodex") else None
                rows = [[(T(t, "btn_ref", b="BingX" if b == "bingx" else "BinoDex"), self.refs.get(b))], [(T(t, "btn_sendid_" + b), "sendid:" + b)]] if b and self.refs.get(b) else None
                self.send(tid, T(t, "rejected"), ik(rows) if rows else self.menu_kb(t))
                return self.send(aid, "❌ Четке кагылды: " + self.card(self.db.user(tid)))
            if act == "stop":
                self.db.upd(tid, status="suspended")
                self.kick(t)
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
    def session_card(self, kind, info, hist, lang):
        if CARDS is None:
            return None
        L = S.T[lang]
        rng = "%s–%s (%s)" % (S.hms(info["t0"], False), S.hms(info["tEnd"], False), "Бишкек")
        try:
            if kind == "session_open":
                return CARDS.card_session_open(L["ss_open"].format(n=info["n"]), rng,
                                               [L["ss_l1"].format(exp=" / ".join(map(str, info.get("exp") or [5]))), L["ss_l2"], L["ss_l3"]], lang)
            xs, w, l, t = S.session_stats(info, hist)
            rows = [(x["res"], "%s %s · %d %s%s" % (x["name"], "▲" if x["dir"] > 0 else "▼", x["exp"], L["min"], " · догон" if x.get("dogon") else "")) for x in xs]
            return CARDS.card_session_close(L["ss_close"].format(n=info["n"]), rng, w, l, t, rows, lang,
                                            (L["r_win"], L["r_loss"], L["r_tie"]), L["ss_none"])
        except Exception as e:  # noqa: BLE001
            print("! session card: %s" % e)
            return None

    def publish_session(self, kind, info, hist):
        """Сессия: BinoDex каналы/темасы бар болсо — ошого; жок болсо — активдүү BinoDex колдонуучуларына (админ да)."""
        if self.db.kv("signals_paused"):
            return False
        chan = self.db.kv("ch:binodex") or self.channel
        targets = []
        if chan:
            targets.append((chan, os.environ.get("TG_CH_LANG", "ru"), self.db.kv("th:binodex") if self.db.kv("ch:binodex") else None))
        else:
            for u in self.db.q("SELECT * FROM users WHERE signals=1 AND status='active' AND broker IN ('binodex','admin')"):
                targets.append((u["id"], u.get("lang") or "kg", None))
        pics, sent = {}, 0
        for chat, lang, th in targets:
            text = S.msg_session(kind, info, hist, lang)
            if lang not in pics:
                pics[lang] = self.session_card(kind, info, hist, lang)
            ok = None
            if pics[lang] is not None and len(text) <= 1024:
                fid = self.photo(chat, pics[lang], text, thread=th)
                if fid:
                    pics[lang], ok = fid, True
            if not ok:
                ok = self.send(chat, text, thread=th)
            sent += 1 if ok else 0
            time.sleep(0.04)
        print("  → %s: %d алуучу" % (kind, sent))
        return sent > 0

    def publish(self, kind, sg, hist):
        if kind in ("session_open", "session_close"):
            return self.publish_session(kind, sg, hist)
        if kind == "signal":
            if self.db.kv("signals_paused"):
                return False
            ch_on = 1 if self.db.kv("ch:" + sg["mkt"]) else 0     # канал бар — активдүүлөр сигналды каналдан алат
            users = self.db.q("SELECT * FROM users WHERE signals=1 AND ((status='active' AND (broker=? OR broker='admin') AND ?=0) "
                              "OR (status IN ('new','wait_dep','pending','rejected') AND COALESCE(free_sent,0)<?))", (sg["mkt"], ch_on, FREE_SIGNALS))
        else:
            users = self.db.q("SELECT u.* FROM users u JOIN sig_sent s ON s.user_id=u.id WHERE s.sig_id=? AND u.status<>'blocked'", (sg["id"],))
        sent = 0
        pics = {}                                        # тил → PNG же file_id (бир жолу тартылат)

        def pic(lang):
            if lang not in pics:
                pics[lang] = None
                if CARDS is not None and (kind == "signal" or sg.get("res") in (0, 1, 2)):
                    try:
                        pics[lang] = CARDS.card_signal(sg, sg.get("_cs"), lang) if kind == "signal" else CARDS.card_result(sg, hist, lang)
                    except Exception as e:  # noqa: BLE001
                        print("! card %s: %s" % (kind, e))
            return pics[lang]

        def deliver(chat, lang, text, th=None):
            img = pic(lang)
            if img is not None and len(text) <= 1024:
                fid = self.photo(chat, img, text, thread=th)
                if fid:
                    pics[lang] = fid
                    return True
            return self.send(chat, text, thread=th)

        for u in users:
            lang = u.get("lang") or "kg"
            text = S.msg_signal(sg, lang) if kind == "signal" else S.msg_result(sg, hist, lang)
            free = kind == "signal" and u["status"] != "active"
            if free:
                text += "\n\n" + T(u, "free_tag", n=(u.get("free_sent") or 0) + 1, m=FREE_SIGNALS)
            if deliver(u["id"], lang, text):
                sent += 1
                if kind == "signal":
                    self.db.x("INSERT OR IGNORE INTO sig_sent(sig_id,user_id) VALUES(?,?)", (sg["id"], u["id"]))
                if free:
                    u2 = self.db.upd(u["id"], free_sent=(u.get("free_sent") or 0) + 1)
                    if self.free_left(u2) <= 0:
                        self.send_card(u["id"], "free", lang, T(u2, "free_last", m=FREE_SIGNALS), ik([[(T(u2, "btn_register"), "menu:register")]]))
            time.sleep(0.04)
        chan = self.db.kv("ch:" + sg.get("mkt", "")) or self.channel
        if chan:
            lang = os.environ.get("TG_CH_LANG", "ru")
            if deliver(chan, lang, S.msg_signal(sg, lang) if kind == "signal" else S.msg_result(sg, hist, lang), self.db.kv("th:" + sg.get("mkt", ""))):
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
                self.kick(u)
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
                self.report_err("signals", e)
                w = 30
            time.sleep(w)

    # ---------- Жабык каналдар ----------
    def on_channel(self, mcm):
        ch = mcm.get("chat") or {}
        cid, title = ch.get("id"), (ch.get("title") or "")
        st = (mcm.get("new_chat_member") or {}).get("status")
        low = title.lower()
        kind = channel_kind(title)
        self.db.kv_set("chseen:%s" % cid, 1)
        if st in ("administrator", "creator") and kind:
            self.db.kv_set("ch:" + kind, cid)
            self.notify_admins("📢 Канал туташты: <b>%s</b> → %s сигналдары. Бот админ ✓" % (E(title), "BingX" if kind == "bingx" else "BinoDex"))
        elif st in ("left", "kicked", "member") and kind and self.db.kv("ch:" + kind) == cid:
            self.db.kv_set("ch:" + kind, None)
            self.notify_admins("⚠️ Бот <b>%s</b> каналынан чыгарылды же админ эмес — канал өчүрүлдү." % E(title))
        elif st in ("administrator", "creator"):
            self.db.kv_set("chask:%s" % cid, 1)
            self.notify_admins("📢 Бот <b>%s</b> каналында админ. Бул канал кайсы сигналдар үчүн? / Для каких сигналов этот канал?" % E(title),
                               ik([[("📈 BingX (фьючерс)", "chset:bingx:%s" % cid), ("⚡ BinoDex", "chset:binodex:%s" % cid)]]))
        return True

    def on_join_request(self, rq):
        """Кошулуу өтүнүчү: текшерүүдөн өткөн (катталуу + толуктоо) жана брокери туура келсе — ырастоо, болбосо — четке кагуу + түшүндүрмө."""
        cid = (rq.get("chat") or {}).get("id")
        fr = rq.get("from") or {}
        uid = fr.get("id")
        kinds = [k for k in ("bingx", "binodex") if self.db.kv("ch:" + k) == cid]
        if not cid or not uid or not kinds:
            return None
        u = self.db.user(uid)
        kind = (u or {}).get("broker") if (u or {}).get("broker") in kinds else kinds[0]
        ok = bool(u) and (self.is_admin(uid) or (u["status"] == "active" and u.get("broker") in kinds))
        if ok:
            self.api("approveChatJoinRequest", {"chat_id": cid, "user_id": uid})
            return True
        self.api("declineChatJoinRequest", {"chat_id": cid, "user_id": uid})
        lang = (u or {}).get("lang") or ("ru" if (fr.get("language_code") or "").startswith("ru") else "kg")
        b = "BingX" if kind == "bingx" else "BinoDex"
        text = TX[lang]["join_need"].format(b=b)
        kb = ik([[(TX[lang]["btn_open_bot"], "https://t.me/%s?start=join_%s" % (self.username or "", kind))]]) if self.username else None
        self.api("sendMessage", {"chat_id": uid, "text": text, "parse_mode": "HTML", "reply_markup": kb} if kb else
                 {"chat_id": uid, "text": text, "parse_mode": "HTML"}, chat=uid)
        return False

    def ask_channel(self, uid, ch, thread=None):
        """Админ каналдан билдирүүнү пересылка кылды: бот андагы укугун текшерип, кайсы сигналдар экенин сурайт."""
        cid, title = ch.get("id"), ch.get("title") or ""
        me = int(str(self.tg.token).split(":")[0]) if self.tg.token else 0
        mem = self.api("getChatMember", {"chat_id": cid, "user_id": me}) or {}
        st = mem.get("status")
        if st not in ("administrator", "creator"):
            return self.send(uid, "⚠️ <b>%s</b>: бот бул каналда админ эмес (статус: %s). Каналдын админдерине @%s кошуп, «пригласительные ссылки» укугун бериңиз, анан кайра пересылка кылыңыз." % (
                E(title), E(st or "жок"), E(self.username or "бот")))
        rights = "✓ посты" if (mem.get("can_post_messages") or ch.get("type") != "channel") else "✗ посты"
        rights += " · " + ("✓ ссылки/заявки" if mem.get("can_invite_users") else "✗ ссылки/заявки")
        suf = (":%s" % thread) if thread else ""
        where = (" (тема #%s)" % thread) if thread else ""
        return self.send(uid, "📢 <b>%s</b>%s — бот админ (%s).\nДля каких сигналов этот канал/тема?" % (E(title), where, rights),
                         ik([[("📈 BingX (фьючерс)", "chset:bingx:%s%s" % (cid, suf)), ("⚡ BinoDex", "chset:binodex:%s%s" % (cid, suf))]]))

    def adm_channels(self, u):
        lines = []
        for kind, nm in (("bingx", "BingX (фьючерс)"), ("binodex", "BinoDex")):
            cid = self.db.kv("ch:" + kind)
            if not cid:
                lines.append("❌ %s: канал туташкан жок" % nm)
                continue
            th = self.db.kv("th:" + kind)
            pl = {"chat_id": cid, "text": "✅ AITRADING.KG: здесь будут сигналы %s. Тестовое сообщение." % nm}
            if th:
                pl["message_thread_id"] = th
            r = self.api("sendMessage", pl)
            info = self.api("getChat", {"chat_id": cid}) or {}
            nm2 = E(info.get("title") or str(cid)) + ((" · тема #%s" % th) if th else "")
            lines.append(("✅ %s: <b>%s</b> — тест отправлен" if r else "⚠️ %s: <b>%s</b> — не отправлено (проверьте права бота)") % (nm, nm2))
        return self.send(u["id"], "📢 <b>Каналдар</b>\n" + "\n".join(lines))

    def channel_for(self, u):
        b = u.get("broker")
        return self.db.kv("ch:" + b) if b in ("bingx", "binodex") else None

    def invite_link(self, u):
        cid = self.channel_for(u)
        if not cid:
            return None
        r = self.api("createChatInviteLink", {"chat_id": cid, "name": "u%d" % u["id"], "member_limit": 1, "expire_date": int(time.time()) + 86400})
        return (r or {}).get("invite_link")

    def send_invite(self, u):
        if u.get("status") != "active":
            return None
        link = self.invite_link(u)
        b = "BingX" if u.get("broker") == "bingx" else "BinoDex"
        if not link:
            return self.send(u["id"], T(u, "ch_none")) if u.get("broker") in ("bingx", "binodex") else None
        return self.send(u["id"], T(u, "ch_invite", b=b), ik([[(T(u, "btn_channel"), link)]]))

    def kick(self, u):
        cid = self.channel_for(u)
        if cid:
            self.api("banChatMember", {"chat_id": cid, "user_id": u["id"], "until_date": int(time.time()) + 60})
            self.api("unbanChatMember", {"chat_id": cid, "user_id": u["id"], "only_if_banned": True})

    # ---------- BingX фьючерс сигналдары ----------
    def fut_publish(self, kind, tr, extra):
        lang = os.environ.get("TG_CH_LANG", "ru")                # каналдар — орусча (автордун өтүнүчү)
        chan = self.db.kv("ch:bingx")
        targets = [chan] if chan else [a for a in self.admins]          # канал жок болсо — админге көрүү үчүн
        th = self.db.kv("th:bingx") if chan else None
        for chat in targets:
            if kind == "signal":
                text = FUT.msg_signal(tr, lang)
                mid = None
                if CARDS is not None and extra.get("cs"):
                    try:
                        img = CARDS.card_futures(tr, extra["cs"], lang, FUT.label(tr["sym"]))
                        if len(text) <= 1024:
                            fid = self.photo(chat, img, text, thread=th)
                            mid = fid and True
                    except Exception as e:  # noqa: BLE001
                        print("! fut card: %s" % e)
                if not mid:
                    self.send(chat, text, thread=th)
            else:
                self.send(chat, FUT.msg_update(tr, extra["kind"], extra["price"], extra.get("hist") or [], lang), thread=th)

    def loop_futures(self):
        desk = FUT.Desk(lambda: self.db.kv("fut"), lambda st: self.db.kv_set("fut", st), self.fut_publish)
        while True:
            try:
                if not self.db.kv("signals_paused"):
                    desk.tick()
            except Exception as e:  # noqa: BLE001
                print("! futures: %s" % self.tg.redact(e))
                self.report_err("futures", e)
            time.sleep(60)

    def free_left(self, u):
        return max(0, FREE_SIGNALS - int(u.get("free_sent") or 0))

    def link_lead(self, u, lid):
        lid = re.sub(r"[^0-9a-z-]", "", str(lid))[:20]
        if not lid:
            return
        ld = self.db.one("SELECT * FROM leads WHERE id=?", (lid,))
        if ld:
            self.db.x("UPDATE leads SET tg_id=? WHERE id=?", (u["id"], lid))
            if not u.get("wa"):
                self.db.upd(u["id"], wa=ld["wa"])
        else:
            self.db.kv_set("lead_tg:" + lid, u["id"])         # заявка али келе элек — кийин байланат

    def lead_note(self, lid, where, line):
        """Жаңы заявка — ээсине гана, номер маска менен."""
        if not self.owner:
            return None
        return self.send(self.owner, "📱 <b>Новая заявка WhatsApp</b> (%s): %s" % (where, line),
                         ik([[("👁 Показать номер", "nb:v:%s" % lid), ("📒 Блокнот", "nb:p:0")]]))

    def notebook(self, uid, data, msg):
        """📒 Блокнот: ээсинин гана. Тизмеде маска; «👁» — толук номер 60 секундга, анан билдирүү өчөт."""
        if uid != self.owner:
            return None
        parts = data.split(":")
        if parts[1] == "c":
            return self.clients(uid, parts, msg)
        if parts[1] == "pdf":
            return self.export_pdf(uid)
        if parts[1] == "v" and len(parts) > 2:
            ld = self.db.one("SELECT * FROM leads WHERE id=?", (re.sub(r"[^0-9a-z-]", "", parts[2])[:20],))
            if not ld:
                return self.send(uid, "Заявка не найдена.")
            r = self.send(uid, "🔒 <b>%s</b> · %s\n<code>%s</code>\n<i>Сообщение удалится через 60 секунд.</i>" % (
                E(ld.get("name") or "—"), E(S.hms(ld.get("t") or S.now_ms(), False)), E(ld["wa"])),
                ik([[("💬 WhatsApp", "https://wa.me/" + ld["wa"].lstrip("+"))]]))
            if r and r.get("message_id"):
                import threading
                t = threading.Timer(60, lambda: self.api("deleteMessage", {"chat_id": uid, "message_id": r["message_id"]}))
                t.daemon = True
                t.start()
            return True
        page = max(0, int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0)
        tot = (self.db.one("SELECT COUNT(*) n FROM leads") or {}).get("n", 0)
        rows = self.db.q("SELECT * FROM leads ORDER BY t DESC LIMIT 8 OFFSET ?", (page * 8,))
        lines = ["📒 <b>Блокнот заявок</b> · всего %d (видите только вы)" % tot]
        kb = []
        for i, ld in enumerate(rows, 1 + page * 8):
            br = {"bingx": "BingX", "binodex": "BinoDex"}.get(ld.get("broker"), "—")
            day = S.datetime.fromtimestamp((ld.get("t") or 0) / 1000, S.BISHKEK).strftime("%d.%m %H:%M") if ld.get("t") else "—"
            lines.append("%d. %s · %s · %s · %s%s" % (i, E(mask_wa(ld["wa"])), E(ld.get("name") or "—"), br, day, " · TG ✓" if ld.get("tg_id") else ""))
            kb.append(("👁 %d" % i, "nb:v:%s" % ld["id"]))
        rows_kb = [kb[j:j + 4] for j in range(0, len(kb), 4)]
        nav = []
        if page > 0:
            nav.append(("⬅️", "nb:p:%d" % (page - 1)))
        if (page + 1) * 8 < tot:
            nav.append(("➡️", "nb:p:%d" % (page + 1)))
        if nav:
            rows_kb.append(nav)
        rows_kb.append([("👥 Клиенты бота", "nb:c:in:0"), ("📥 PDF", "nb:pdf")])
        if not rows:
            lines.append("Пока пусто.")
        mid = msg.get("message_id") if parts[1] == "p" and msg.get("text", "").startswith("📒") else None
        text = "\n".join(lines)
        return self.edit(uid, mid, text, ik(rows_kb)) if mid else self.send(uid, text, ik(rows_kb) if rows_kb else None)

    def export_pdf(self, uid):
        """Бардык заявкалар жана колдонуучулар — PDF файл, ээсинин жеке чатына гана."""
        try:
            import tg_export
            leads = self.db.q("SELECT l.*, u.username FROM leads l LEFT JOIN users u ON u.id=l.tg_id ORDER BY l.t DESC")
            users = self.db.q("SELECT * FROM users WHERE broker IS NOT 'admin' ORDER BY created DESC")
            st = {k: re.sub(r"^[^0-9A-Za-zА-Яа-яЁё]+", "", v) for k, v in TX["ru"]["st"].items()}
            pdf = tg_export.build(leads, users, st)
        except Exception as e:  # noqa: BLE001
            print("! pdf: %s" % e)
            return self.send(uid, "⚠️ PDF не получилось: %s" % E(str(e)[:120]))
        name = "aitrading_klienty_%s.pdf" % S.datetime.now(S.BISHKEK).strftime("%Y-%m-%d_%H%M")
        cap = "📥 Заявки: %d · клиенты бота: %d\n🔒 Конфиденциально — не пересылайте." % (len(leads), len(users))
        try:
            body, ct = _multipart({"chat_id": uid, "caption": cap}, {"document": (name, pdf, "application/pdf")})
            req = urllib.request.Request("https://api.telegram.org/bot%s/sendDocument" % self.tg.token, data=body,
                                         headers={"Content-Type": ct, "User-Agent": S.UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8")).get("ok")
        except Exception as e:  # noqa: BLE001
            print("! sendDocument: %s" % self.tg.redact(e))
            return self.send(uid, "⚠️ Не удалось отправить PDF.")

    def clients(self, uid, parts, msg):
        """parts: nb:c:<in|all>:<page>. in — каттоосу/толуктоосу бүтө электер (кол менен жазуу үчүн)."""
        flt = parts[2] if len(parts) > 2 and parts[2] in ("in", "all") else "in"
        page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
        where = "broker IS NOT 'admin'" + (" AND status IN ('new','wait_dep','pending','rejected','suspended','blocked')" if flt == "in" else "")
        tot = (self.db.one("SELECT COUNT(*) n FROM users WHERE " + where) or {}).get("n", 0)
        rows = self.db.q("SELECT * FROM users WHERE " + where + " ORDER BY last_seen DESC LIMIT 10 OFFSET ?", (page * 10,))
        st = TX["ru"]["st"]
        lines = ["👥 <b>Клиенты бота</b> · %s · %d (видите только вы)" % ("не активные" if flt == "in" else "все", tot),
                 "<i>Нажмите @ник или имя — откроется чат с человеком.</i>"]
        btn = []
        for i, t in enumerate(rows, 1 + page * 10):
            at = ("@%s" % E(t["username"])) if t.get("username") else "без @"
            name = E(t.get("first_name") or "—")
            seen = S.datetime.fromtimestamp((t.get("last_seen") or 0) / 1000, S.BISHKEK).strftime("%d.%m") if t.get("last_seen") else "—"
            br = {"bingx": "BingX", "binodex": "BinoDex"}.get(t.get("broker"), "—")
            lines.append('%d. %s · <a href="tg://user?id=%d">%s</a> · ID <code>%d</code>\n    %s · %s · был %s%s' % (
                i, at, t["id"], name, t["id"], st.get(t.get("status"), t.get("status") or "—"), br, seen,
                (" · WA " + E(mask_wa(t["wa"]))) if t.get("wa") else ""))
            if t.get("status") != "blocked":
                btn.append(("💬 %d" % i, "adm:rep:%d" % t["id"]))
        if not rows:
            lines.append("Пока никого.")
        kb = [btn[j:j + 5] for j in range(0, len(btn), 5)]
        nav = []
        if page > 0:
            nav.append(("⬅️", "nb:c:%s:%d" % (flt, page - 1)))
        if (page + 1) * 10 < tot:
            nav.append(("➡️", "nb:c:%s:%d" % (flt, page + 1)))
        if nav:
            kb.append(nav)
        kb.append([("Все" if flt == "in" else "Не активные", "nb:c:%s:0" % ("all" if flt == "in" else "in")), ("📒 Блокнот", "nb:p:0")])
        text = "\n".join(lines)
        mid = msg.get("message_id") if (msg.get("text") or "").startswith("👥") else None
        return self.edit(uid, mid, text, ik(kb)) if mid else self.send(uid, text, ik(kb))

    def pull_leads(self):
        if not link_secret():
            return 0
        ts = str(S.now_ms())
        after = self.db.kv("leads_after", "") or ""
        req = urllib.request.Request(S.SITE_URL + "/api/leads?after=" + urllib.parse.quote(after),
                                     headers={"x-ts": ts, "x-sig": link_sig("leads|" + ts, 22), "User-Agent": S.UA})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                items = (json.loads(r.read().decode("utf-8")) or {}).get("items") or []
        except urllib.error.HTTPError as e:   # сайттын JSON жообун (error/detail) катага кошобуз
            try:
                body = e.read().decode("utf-8", "replace")[:200]
            except Exception:  # noqa: BLE001
                body = ""
            raise RuntimeError("HTTP %s %s" % (e.code, body.strip())) from None
        for it in items:
            lid = str(it.get("id") or "")
            wa = norm_wa(it.get("wa"))
            if not lid or not wa:
                continue
            tg = self.db.kv("lead_tg:" + lid)
            self.db.x("INSERT OR IGNORE INTO leads(id,t,wa,name,broker,lang,page,country,src,tg_id) VALUES(?,?,?,?,?,?,?,?,?,?)",
                      (lid, int(it.get("t") or 0), wa, str(it.get("name") or "")[:60], str(it.get("broker") or ""), str(it.get("lang") or ""),
                       str(it.get("page") or ""), str(it.get("country") or ""), "site", tg))
            if tg:
                self.db.kv_set("lead_tg:" + lid, None)
                tu = self.db.user(tg)
                if tu and not tu.get("wa"):
                    self.db.upd(tg, wa=wa)
            br = {"bingx": "BingX", "binodex": "BinoDex"}.get(it.get("broker"), "—")
            self.lead_note(lid, "сайт", "%s%s · %s · %s%s" % (
                E(mask_wa(wa)), (" · " + E(it.get("name"))) if it.get("name") else "", br, E(it.get("page") or ""),
                (" · " + E(it.get("country"))) if it.get("country") else ""))
            self.db.kv_set("leads_after", lid)
            time.sleep(0.05)
        return len(items)

    def agent_kb(self, u, stg):
        uid, ru = u["id"], u.get("lang") == "ru"
        rows = []
        if stg in ("register", "rereg"):
            rows.append([(T(u, "btn_ref", b="BinoDex"), self.refs.get("binodex")), (T(u, "btn_ref", b="BingX"), self.refs.get("bingx"))])
            rows.append([("📝 Регистрация" if ru else "📝 Катталуу", "menu:register")])
        elif stg == "try_free":
            rows.append([("⭐ Сигналы" if ru else "⭐ Сигналдар", "menu:signals")])
        elif stg == "deposit":
            if u.get("broker") == "binodex" and oauth_ready():
                rows.append([(T(u, "btn_oauth"), oauth_url(uid))])
            rows.append([("👤 Профиль", "menu:profile")])
        elif stg == "comeback":
            rows.append([("👤 Профиль", "menu:profile")])
        rows.append([("🔕 Не напоминать" if ru else "🔕 Эскертпе", "fu:off")])
        return ik(rows)

    def loop_agent(self):
        """2 күндө 1 жолу: катталуу/толуктоо бүтө электерге жеке эскертме (10:00–20:00 Бишкек)."""
        time.sleep(90)
        while True:
            try:
                if not self.db.kv("agent_paused"):
                    sent, now = 0, S.now_ms()
                    for u in self.db.q("SELECT * FROM users WHERE status NOT IN ('active','blocked','pending') AND broker IS NOT 'admin' ORDER BY last_seen DESC"):
                        if sent >= 25 or self.is_admin(u["id"]):
                            continue
                        stg = AG.stage(u, self.free_left(u))
                        if not stg or now - (u.get("last_seen") or 0) < 86400000:
                            continue                      # акыркы суткада өзү кирген — тынчсыздандырбайбыз
                        k = "fu:%d" % u["id"]
                        try:
                            st = json.loads(self.db.kv(k) or "{}")
                        except ValueError:
                            st = {}
                        if not AG.due(st):
                            continue
                        text = AG.followup_text(u, stg, self.free_left(u))
                        ok = self.api("sendMessage", {"chat_id": u["id"], "text": text[:4000], "reply_markup": self.agent_kb(u, stg)}, chat=u["id"])
                        st.update(n=st.get("n", 0) + 1, t=int(time.time()), last=stg)
                        self.db.kv_set(k, json.dumps(st))
                        sent += 1 if ok else 0
                        time.sleep(0.5)
                    if sent:
                        print("  → ИИ-жардамчы: %d эскертме" % sent)
            except Exception as e:  # noqa: BLE001
                print("! agent: %s" % self.tg.redact(e))
                self.report_err("agent", e)
            time.sleep(900)

    def loop_leads(self):
        while True:
            try:
                self.pull_leads()
            except Exception as e:  # noqa: BLE001
                print("! leads: %s" % self.tg.redact(e))
                self.report_err("leads", e)
            time.sleep(45)

    def loop_maint(self):
        while True:
            try:
                self.maintenance()
            except Exception as e:  # noqa: BLE001
                print("! maintenance: %s" % self.tg.redact(e))
                self.report_err("maintenance", e)
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
        print("AITRADING.KG бот: @%s · админдер: %d · BingX API: %s · BinoDex: %s · сигналдар: %s · база: %s" % (
            self.username, len(self.admins), "✓" if self.bingx.ok() else "жок", binodex_status(), "✓ BinoDex %s мүн + BingX фьючерс" % ",".join(map(str, self.exp)) if self.engine else "өчүк", DB_PATH))
        if not self.admins:
            print("! Админ жок: TELEGRAM_CHAT_ID же TELEGRAM_ADMIN_IDS'ке өзүңүздүн Telegram ID'ңизди коюңуз (Телеграм_бот_туташтыруу.bat).")
        if S.keep_awake(True):
            print("Компьютер бот иштеп жатканда уктабайт. Ноутбуктун капкагын жаппаңыз.")
        if self.engine:
            threading.Thread(target=self.loop_signals, daemon=True).start()
        threading.Thread(target=self.loop_maint, daemon=True).start()
        threading.Thread(target=self.loop_leads, daemon=True).start()
        if AG is not None and os.environ.get("TG_AGENT", "1") != "0":
            threading.Thread(target=self.loop_agent, daemon=True).start()
        if FUT is not None and self.engine and os.environ.get("TG_FUTURES", "1") != "0":
            threading.Thread(target=self.loop_futures, daemon=True).start()
        threading.excepthook = lambda a: self.report_err("thread:%s" % getattr(a.thread, "name", "?"), a.exc_value)
        offset = int(self.db.kv("offset") or 0)
        while True:
            try:
                r = self.tg.call("getUpdates", {"offset": offset, "timeout": 25, "allowed_updates": ["message", "callback_query", "my_chat_member", "channel_post", "chat_join_request"]}, timeout=40)
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
                except Exception as e:  # noqa: BLE001 — бир ката ботту токтотпойт
                    print(self.tg.redact(traceback.format_exc()))
                    self.report_err("handle", e)
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
    ap.add_argument("--exp", default=os.environ.get("TG_EXP", "5"), help="BinoDex экспирациясы: 5 (догон — 3/2 өзү)")
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
