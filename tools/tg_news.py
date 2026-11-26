"""Шашылыш жаңылыктар жана твиттер: Telegram-бот → канал → сайт (/api/live) → тиркеме (Web Push).

tools/tg_bot.py ичинде иштейт (App.news). Үч булак:
  1. Рынок эрежеси (tools/market_pulse.py, ар 2 мүнөттө): 10 ири монетанын медианасы 24 с ±5% же 1 с ±3% →
     канал + ботто жазылгандар (news=1) + сайттагы плашка + тиркемеге push. Бир эле окуя 6 саатта бир жолу.
  2. Админ: ADMIN PANEL → «🚨 Шашылыш жаңылык» — өз текстиңиз (кыргызча, «---» дан кийин орусча), ырастоо менен.
  3. Админ: ADMIN PANEL → «🐦 Твит» же твиттин шилтемесин жөн эле ботко жөнөтүү. Твит X'тин расмий oEmbed'инен
     текшерилет (бар экени, тексти, автору, күнү). Тартип: АЛГАЧ Telegram-каналга, ийгиликтүү болсо ГАНА сайтка.

Чөйрө өзгөрмөлөрү:
  TELEGRAM_CHANNEL  — автордун каналы: @username же -100…; бот каналда админ болушу керек (твит жана шашылыш үчүн)
  LIVE_URL, LIVE_KEY — сайттын /api/live дареги жана сыры (node tools/live_keys.mjs). Жок болсо — сайтка/тиркемеге жазылбайт.
  ANTHROPIC_API_KEY — (каалоо боюнча) твитти, жаңылыкты кыргызча/орусчага которуу жана кыска мазмун; жок болсо орусча калат.

25.11 кошулду (автордун өтүнүчү: «жаңылыктар күн сайын, анонстор, блогерлердин теханализи сайтка дароо, маанилүүлөрү ботко»):
  4. Жаңылык агымы (ар 10 мүн, өз агымында): tools/news_feed.py'дин RSS булактары → жаңылары сайтка дароо (/api/live «fresh»).
     Маанилүүсү (news_feed.importance: «hot» — ставка, ETF, бузуп кирүү…, «top» — 3+ басылма) → кооз пост:
     канал/тема (KG+RU) → ботто жазылгандар (ар бири өз тилинде) → «hot» болсо сайттагы плашка + push. Күнүнө ≤6, ортосу ≥20 мүн.
  5. Экономикалык анонстор (site/assets/data/calendar.json, tools/econ_calendar.py): 08:00 Бишкек — бүгүнкү маанилүү (●●●)
     окуялар; ар бир маанилүү окуядан ~15 мүн мурун — эскертүү.
  Кайда жазат: форумдун темасында админ /news жазса — ошол тема; болбосо TELEGRAM_CHANNEL; болбосо TELEGRAM_CHAT_ID (канал болсо).
  Колдонуучу профилинде «📰 Жаңылыктар жана анонстор» баскычы менен өчүрө алат.
"""
import datetime as dt
import html
import json
import os
import re
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request

import market_pulse as MP

UA = "Mozilla/5.0 (compatible; AITRADING.KG bot)"
TWEET_RE = re.compile(r"https?://(?:www\.|mobile\.)?(?:x|twitter)\.com/([A-Za-z0-9_]{1,15})/status/(\d{1,25})", re.I)
COOLDOWN_MS = 6 * 3600 * 1000      # бир эле рынок окуясы (мис. «24 с өсүү») — 6 саатта бир жолу
REFRESH_MS = 30 * 60 * 1000        # окуя улантылып жатса, сайттагы плашканы 30 мүнөттө жаңыртуу (push'суз)
TICK_S = 120
FEED_TICK_S = 600                  # жаңылык агымы — ар 10 мүнөттө
FRESH_MAX_AGE_MS = 6 * 3600 * 1000 # мындан эски жаңылык «жаңы» эмес (бот кайра иштегенде эскилери чыкпайт)
HOT_MAX_AGE_MS = 90 * 60 * 1000    # «шашылыш» пост — жаңылык 90 мүнөттөн эски болбосо гана
TOP_MAX_AGE_MS = 6 * 3600 * 1000
POST_GAP_MS = 20 * 60 * 1000       # автоматтык жаңылык посттордун ортосу (hot'тон башкасы)
DAY_CAP = 6                        # күнүнө ≤6 автоматтык жаңылык посту (анонстор өзүнчө)
DIGEST_H = 8                       # 08:00 Бишкек — бүгүнкү анонстор
REMIND_MIN = 15                    # маанилүү окуядан ~15 мүнөт мурун эскертүү
CAL_REFRESH_S = 1800
BISHKEK = dt.timezone(dt.timedelta(hours=6))
HERE = os.path.dirname(os.path.abspath(__file__))
CAL_FILE = os.path.join(os.path.dirname(HERE), "site", "assets", "data", "calendar.json")
MAJOR = ("USD", "EUR", "GBP", "JPY", "CNY")


def E(s):
    return html.escape(str(s or ""), quote=False)


# ---------- Сайт: /api/live ----------
class Live:
    def __init__(self, url=None, key=None):
        self.url = (url if url is not None else os.environ.get("LIVE_URL") or "").strip()
        self.key = (key if key is not None else os.environ.get("LIVE_KEY") or "").strip()

    def ok(self):
        return self.url.startswith("http") and bool(self.key)

    def _post(self, payload):
        req = urllib.request.Request(self.url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                                     headers={"Content-Type": "application/json", "X-Live-Key": self.key, "User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return {"error": "HTTP %d" % e.code}
        except Exception as e:  # noqa: BLE001
            return {"error": str(e)[:120]}

    def post(self, payload):
        """Жазат; push болсо — бардык жазылуучуларга бөлүк-бөлүк (cursor) жеткирет. Жыйынтык: {ok, pushed, failed, error}"""
        if not self.ok():
            return {"error": "LIVE_URL/LIVE_KEY жок"}
        r = self._post(payload)
        tot = {"ok": bool(r.get("ok")), "pushed": r.get("pushed", 0), "failed": r.get("failed", 0), "error": r.get("error"), "item": r.get("item")}
        cur, n = r.get("cursor"), 0
        while cur and n < 200:
            n += 1
            r = self._post({"type": "push", "cursor": cur})
            tot["pushed"] += r.get("pushed", 0)
            tot["failed"] += r.get("failed", 0)
            cur = r.get("cursor")
        return tot


# ---------- X / Twitter: расмий oEmbed (бекер, ачкычсыз) ----------
def oembed(url):
    m = TWEET_RE.search(url or "")
    if not m:
        raise ValueError("bad-url")
    canon = "https://x.com/%s/status/%s" % (m.group(1), m.group(2))
    q = urllib.parse.urlencode({"url": canon, "omit_script": "1", "dnt": "true"})
    req = urllib.request.Request("https://publish.x.com/oembed?" + q, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            j = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise ValueError("not-found" if e.code in (403, 404) else "http-%d" % e.code)
    h = j.get("html") or ""
    p = re.search(r"<p[^>]*>(.*?)</p>", h, re.S)
    text = re.sub(r"<br\s*/?>", "\n", p.group(1)) if p else ""
    text = html.unescape(re.sub(r"<[^>]+>", "", text)).strip()
    date = re.findall(r'<a href="https://(?:x|twitter)\.com/[^"]+/status/\d+[^"]*">([^<]+)</a>', h)
    handle = (re.search(r"\(@([A-Za-z0-9_]{1,15})\)", h) or [None, m.group(1)])[1]
    if not text:
        raise ValueError("empty")
    return {"url": canon, "handle": handle, "name": html.unescape(j.get("author_name") or handle), "date": html.unescape(date[-1]) if date else "", "text": text}


def translate_tweet(text):
    """Claude аркылуу (ачкыч болсо): {ky, ru}. Сандар текшерилет (news_feed.same_numbers)."""
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        return None
    import news_feed as NF
    item = {"id": "tw", "lang": "en", "orig": text, "desc": ""}
    try:
        res, _ = NF.translate([item])
    except Exception as e:  # noqa: BLE001
        print("! твит котормосу: %s" % e)
        return None
    r = res.get("tw")
    if not r or not NF.same_numbers(text, r["ky"]) or not NF.same_numbers(text, r["ru"]):
        return None
    return {"ky": r["ky"].strip(), "ru": r["ru"].strip()}


def split_kg_ru(text):
    """Админдин тексти: «кыргызча\\n---\\nорусча». Орусчасы жок болсо — экөө тең бирдей."""
    parts = re.split(r"\n\s*-{3,}\s*\n", (text or "").strip(), maxsplit=1)
    ky = parts[0].strip()
    ru = parts[1].strip() if len(parts) > 1 else ky
    return ky, ru


# ---------- Билдирмелердин тексттери ----------
FOOT = {
    "kg": "⚠️ Мындай учурда баа бир нече мүнөттө кескин өзгөрөт — жаңы баштагандарга күтүп туруу коопсузураак. Бул сунуш эмес. 18+",
    "ru": "⚠️ В такие моменты цена может резко меняться за минуты — новичкам безопаснее подождать. Это не рекомендация. 18+",
}
RULE = {
    "kg": "Эреже: {n} ири монетанын медианасы 24 саатта ±{a}% же 1 саатта ±{b}% (Binance, запасы BingX).",
    "ru": "Правило: медиана {n} крупнейших монет за 24 ч ±{a}% или за 1 ч ±{b}% (Binance, запасной — BingX).",
}
HEAD = {"kg": "⚡ <b>Шашылыш</b>", "ru": "⚡ <b>Срочно</b>"}
NEWS_BTN = {"kg": ("📰 Жаңылыктар жана анонстор: 🔔 күйүк", "📰 Жаңылыктар жана анонстор: 🔕 өчүк"),
            "ru": ("📰 Новости и анонсы: 🔔 вкл", "📰 Новости и анонсы: 🔕 выкл")}


def market_msg(a, p, lang, site):
    l = "ru" if lang == "ru" else "kg"
    return "%s\n\n%s\n\n📊 <a href=\"%s\">TradingView</a> · <a href=\"%s/news.html#pulse\">AITRADING.KG</a>" % (
        HEAD[l], E(a["ky"] if l == "kg" else a["ru"]), a.get("verify") or MP.VERIFY_URL, site)


def urgent_msg(d, lang, site):
    l = "ru" if lang == "ru" else "kg"
    src = ("\n🔗 <a href=\"%s\">%s</a>" % (E(d["url"]), "Булак" if l == "kg" else "Источник")) if d.get("url") else ""
    return "%s\n\n%s%s\n\n📰 <a href=\"%s/news.html\">AITRADING.KG</a>" % (HEAD[l], E(d["ky"] if l == "kg" else d["ru"]), src, site)


def tweet_msg(d, lang):
    l = "ru" if lang == "ru" else "kg"
    who = "<b>%s</b> (@%s)" % (E(d["name"]), E(d["handle"]))
    said = " X'те жазды" if l == "kg" else " написал(а) в X"
    lines = ["🐦 %s%s%s:" % (who, said, (" · " + E(d["date"])) if d.get("date") else ""), "", "«%s»" % E(d["text"])]
    if d.get("ky"):
        lines += ["", "🇰🇬 " + E(d["ky"])]
    if d.get("ru") and d.get("ru") != d.get("text"):
        lines += ["🇷🇺 " + E(d["ru"])]
    lines += ["", "🔗 " + E(d["url"])]
    return "\n".join(lines)


# ---------- Жаңылык посттору (кооз, сабаттуу; ар бир тил өзүнчө блок) ----------
CAT_NAME = {"crypto": ("Крипто", "Крипто"), "fx": ("Валюта, алтын", "Валюта, золото"), "stock": ("Акциялар", "Акции")}
TOPIC_NAME = {"move": ("рынок кыймылы", "движения рынка"), "etf": ("ETF", "ETF"), "reg": ("жөнгө салуу", "регулирование"),
              "tech": ("технология", "технологии"), "macro": ("макроэкономика", "макроэкономика")}
NEWS_HEAD = {"hot": ("⚡ <b>Шашылыш</b>", "⚡ <b>Срочно</b>", "⚡ <b>Шашылыш · Срочно</b>"),
             "top": ("🔥 <b>Маанилүү</b>", "🔥 <b>Важно</b>", "🔥 <b>Маанилүү · Важно</b>")}
NEWS_FOOT = {"kg": "ℹ️ Жаңылык — маалымат үчүн, соода сунушу эмес. Чоң жаңылыкта баа бир нече мүнөттө кескин өзгөрүшү мүмкүн.",
             "ru": "ℹ️ Новость — для информации, не торговая рекомендация. На крупных новостях цена может резко измениться за минуты."}
FLAG = {"USD": "🇺🇸", "EUR": "🇪🇺", "GBP": "🇬🇧", "JPY": "🇯🇵", "CNY": "🇨🇳", "CHF": "🇨🇭", "CAD": "🇨🇦", "AUD": "🇦🇺", "NZD": "🇳🇿"}
CUR_NAME = {"USD": ("АКШ", "США"), "EUR": ("Евроаймак", "Еврозона"), "GBP": ("Улуу Британия", "Великобритания"), "JPY": ("Япония", "Япония"),
            "CNY": ("Кытай", "Китай"), "CHF": ("Швейцария", "Швейцария"), "CAD": ("Канада", "Канада"), "AUD": ("Австралия", "Австралия"),
            "NZD": ("Жаңы Зеландия", "Новая Зеландия")}


def hhmm(t):
    return dt.datetime.fromtimestamp(t / 1000, BISHKEK).strftime("%H:%M")


def _li(l):
    return 1 if l == "ru" else 0


def news_block(x, l):
    """Бир тилдеги бөлүк: калың аталыш + өзүбүздүн кыска мазмуну (болсо)."""
    k = "ru" if l == "ru" else "ky"
    title = x.get(k) or x.get("ru") or x["orig"]
    summ = x.get("sum_" + k) or ""
    return "<b>%s</b>%s" % (E(title), ("\n" + E(summ)) if summ else "")


def news_msg(x, lang, both=False):
    """both=True — канал/тема үчүн: кыргызча + орусча бир постто. Шилтемелер — баскычтарда (news_kb)."""
    l = "ru" if lang == "ru" else "kg"
    lvl = x.get("imp") if x.get("imp") in NEWS_HEAD else "top"
    cat = CAT_NAME.get(x.get("cat"))
    tps = [TOPIC_NAME[t] for t in (x.get("tp") or []) if t in TOPIC_NAME][:2]
    if both:
        head = NEWS_HEAD[lvl][2] + (" · %s" % E(cat[0] if cat[0] == cat[1] else cat[0] + " / " + cat[1]) if cat else "")
        body = ["🇰🇬 " + news_block(x, "kg"), "", "🇷🇺 " + news_block(x, "ru")] if x.get("ky") else [news_block(x, "ru")]
    else:
        head = NEWS_HEAD[lvl][_li(l)] + (" · %s" % E(cat[_li(l)]) if cat else "")
        body = [news_block(x, l)]
    n = x.get("n") or 1
    if both:
        src = "📰 %s%s · 🕒 %s (Бишкек)" % (E(x["src"]), (" +%d" % (n - 1)) if n > 1 else "", hhmm(x["t"]))
    elif l == "ru":
        src = "📰 %s%s · 🕒 %s (Бишкек)" % (E(x["src"]), (" и ещё %d изд." % (n - 1)) if n > 1 else "", hhmm(x["t"]))
    else:
        src = "📰 %s%s · 🕒 %s (Бишкек)" % (E(x["src"]), (" жана дагы %d басылма" % (n - 1)) if n > 1 else "", hhmm(x["t"]))
    tag = ("🏷 " + " ".join("#" + re.sub(r"\W+", "_", t[0 if both else _li(l)]).strip("_") for t in tps)) if tps else ""
    foot = NEWS_FOOT["kg"] if (both or l == "kg") else NEWS_FOOT["ru"]
    if both and x.get("ky"):
        foot = NEWS_FOOT["kg"] + "\n" + NEWS_FOOT["ru"]
    return "\n".join([head, ""] + body + ["", src] + ([tag] if tag else []))


def news_kb(x, lang, site, both=False):
    l = "ru" if lang == "ru" else "kg"
    read = "📖 Толук окуу · Читать" if both else ("📖 Читать полностью" if l == "ru" else "📖 Толук окуу")
    alln = "📰 Бардык жаңылыктар · Все новости" if both else ("📰 Все новости AITRADING.KG" if l == "ru" else "📰 Бардык жаңылыктар AITRADING.KG")
    return {"inline_keyboard": [[{"text": read, "url": x["url"]}], [{"text": alln, "url": site + "/news.html#feed"}]]}


def cal_title(e, l):
    return (e.get("ru") if l == "ru" else e.get("ky")) or e.get("en") or ""


def cal_vals(e, l):
    v = []
    if e.get("fc"):
        v.append(("прогноз %s" if l == "ru" else "болжол %s") % E(e["fc"]))
    if e.get("pv"):
        v.append(("пред. %s" if l == "ru" else "мурунку %s") % E(e["pv"]))
    return " · ".join(v)


def cal_line(e, l, both=False):
    cur = CUR_NAME.get(e["cur"], (e["cur"], e["cur"]))
    t = "🏖" if e["imp"] == 0 else ("🔴 " + hhmm(e["t"]))
    who = "%s %s" % (FLAG.get(e["cur"], "🌐"), E(cur[_li(l)] if not both else cur[0]))
    if both:
        ky, ru = cal_title(e, "kg"), cal_title(e, "ru")
        title = "<b>%s</b>%s" % (E(ky), ("\n      " + E(ru)) if ru and ru != ky else "")
    else:
        title = "<b>%s</b>" % E(cal_title(e, l))
    vals = cal_vals(e, "kg" if both else l)
    return "%s %s — %s%s" % (t, who, title, ("\n      " + vals) if vals else "")


def cal_digest_msg(evs, lang, site, both=False):
    l = "ru" if lang == "ru" else "kg"
    day = dt.datetime.now(BISHKEK).strftime("%d.%m")
    if both:
        head = "📅 <b>Бүгүнкү окуялар · События сегодня</b>\n%s · Бишкек" % day
        foot = "🔥 Бул мүнөттөрдө рынок жанданат · В эти минуты рынок оживает"
    elif l == "ru":
        head, foot = "📅 <b>Важные события сегодня</b>\n%s · время бишкекское" % day, "🔥 В эти минуты рынок оживает — будьте готовы."
    else:
        head, foot = "📅 <b>Бүгүнкү маанилүү окуялар</b>\n%s · убакыт Бишкек боюнча" % day, "🔥 Бул мүнөттөрдө рынок жанданат — даяр болуңуз."
    rows = "\n\n".join(cal_line(e, l, both) for e in evs)
    src = "Булак: Forex Factory · %s/news.html#calendar" % site
    return "%s\n\n%s\n\n%s\n%s" % (head, rows, foot, src)


def cal_remind_msg(evs, lang, site, both=False, now=None):
    l = "ru" if lang == "ru" else "kg"
    m = max(1, round((evs[0]["t"] - (now or time.time() * 1000)) / 60000))
    if both:
        head = "⏰ <b>%d МҮНӨТТӨН КИЙИН · ЧЕРЕЗ %d МИН</b> · %s (Бишкек)" % (m, m, hhmm(evs[0]["t"]))
        foot = "Чыккан маанини TradingView'дон караңыз · Факт — на TradingView"
    elif l == "ru":
        head, foot = "⏰ <b>ЧЕРЕЗ %d МИН</b> · %s (Бишкек)" % (m, hhmm(evs[0]["t"])), "Факт смотрите на TradingView."
    else:
        head, foot = "⏰ <b>%d МҮНӨТТӨН КИЙИН</b> · %s (Бишкек)" % (m, hhmm(evs[0]["t"])), "Чыккан маанини TradingView'дон караңыз."
    rows = "\n\n".join(cal_line(e, l, both) for e in evs)
    return "%s\n\n%s\n\n%s\n%s" % (head, rows, foot, "https://ru.tradingview.com/economic-calendar/")


# ---------- Claude: жаңылыктын котормосу + өзүбүздүн кыска мазмуну (ачкыч болсо) ----------
SUM_SYSTEM = """Сен AITRADING.KG'дин редакторусуң. Жаңылыктын аталышы жана булактын кыска сыпаттамасы берилет.
Жаз: ky — аталыштын кыргызча котормосу; ru — орусча аталыш (түп нуска орусча болсо — өзгөрүүсүз);
sum_ky / sum_ru — жаңылыктын маңызын ӨЗ СӨЗҮҢ МЕНЕН 1–2 сүйлөм (220 белгиге чейин) кыргызча жана орусча.
Эрежелер: жаңы факт кошпо, баа берип, кеңеш же болжол жазба; сандар, пайыздар, $, тикерлер түп нускадагыдай гана;
булактын текстин көчүрбө — кайра айтып бер. Кыргызча — адабий (ң, ө, ү), орусча — катасыз жаңылык стилинде."""
SUM_SCHEMA = {"type": "object", "properties": {k: {"type": "string"} for k in ("ky", "ru", "sum_ky", "sum_ru")},
              "required": ["ky", "ru", "sum_ky", "sum_ru"], "additionalProperties": False}


def summarize(x):
    """x'ке ky/ru/sum_ky/sum_ru кошот (сандар текшерилет). Ийгиликтүү болсо True."""
    import news_feed as NF
    if not NF.has_key():
        return False
    import anthropic
    src = {"lang": x.get("lang") or "ru", "title": x["orig"], "desc": NF.clean(x.get("desc") or "")[:700]}
    try:
        resp = anthropic.Anthropic().beta.messages.create(
            model=NF.MODEL, max_tokens=2000, system=SUM_SYSTEM,
            messages=[{"role": "user", "content": json.dumps(src, ensure_ascii=False)}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SUM_SCHEMA}},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        if resp.stop_reason in ("refusal", "max_tokens"):
            return False
        r = json.loads(next(b.text for b in resp.content if b.type == "text"))
    except Exception as e:  # noqa: BLE001
        print("! жаңылыктын мазмуну: %s" % e)
        return False
    pool = set(NF.nums(src["title"] + " " + src["desc"]))
    if not x.get("ky") and NF.same_numbers(x["orig"], r["ky"]):
        x["ky"] = r["ky"].strip()
    if not x.get("ru") and (src["lang"] == "ru" or NF.same_numbers(x["orig"], r["ru"])):
        x["ru"] = x["orig"] if src["lang"] == "ru" else r["ru"].strip()
    for k in ("sum_ky", "sum_ru"):
        v = (r.get(k) or "").strip()
        if v and set(NF.nums(v)) <= pool and len(v) <= 400:     # мазмундагы ар бир сан булакта болушу керек
            x[k] = v
    return True


class NewsDesk:
    """tg_bot.App менен иштейт: app.send/api/db/admins/is_admin."""

    def __init__(self, app, enabled=True):
        self.app, self.db, self.enabled = app, app.db, enabled
        self.live = Live()
        ch = (os.environ.get("TELEGRAM_CHANNEL") or "").strip()
        self.channel = ch if (ch.startswith("@") or ch.startswith("-")) else app.channel
        self.channel_user = ch[1:] if ch.startswith("@") else None
        self.last_pulse = None
        self.cal_cache, self.cal_t = None, 0
        self.feed_state = "күтүүдө"
        try:                                       # жаңы талаа: колдонуучу шашылыш жаңылыктарды алабы (демейки — ооба)
            self.db.x("ALTER TABLE users ADD COLUMN news INTEGER DEFAULT 1")
        except Exception:  # noqa: BLE001 — мурунтан бар
            pass

    @property
    def site(self):
        import tg_signals as S
        return S.SITE_URL

    # ---------- Жөнөтүү: канал/тема → колдонуучулар → сайт/тиркеме ----------
    def dest(self):
        """(chat, thread): форумдагы /news темасы → TELEGRAM_CHANNEL → TELEGRAM_CHAT_ID (канал болсо)."""
        ch = self.db.kv("ch:news")
        if ch:
            return ch, self.db.kv("th:news")
        return self.channel, None

    def dest_name(self):
        ch, th = self.dest()
        if not ch:
            return "жок (/news же TELEGRAM_CHANNEL)"
        return "%s%s" % (ch, (" · тема #%s" % th) if th else "")

    def to_channel(self, text, preview=False, kb=None):
        chat, th = self.dest()
        if not chat:
            return None
        r = self.app.send(chat, text, kb, preview=preview, thread=th)
        if not r:
            return None
        mid = r.get("message_id")
        user = self.channel_user if chat == self.channel else None
        if not user and str(chat).startswith("@"):
            user = str(chat)[1:]
        if not user:
            info = self.app.api("getChat", {"chat_id": chat}) or {}
            user = info.get("username") or ""
        if chat == self.channel:
            self.channel_user = user
        if user and mid:
            url = "https://t.me/%s/%s" % (user, mid)
        elif str(chat).startswith("-100") and mid:
            url = "https://t.me/c/%s/%s" % (str(chat)[4:], mid)       # жабык топ: мүчөлөр гана ачат
        else:
            url = ""
        return {"mid": mid, "url": url}

    def to_users(self, make, kb=None, preview=False):
        n = 0
        for u in self.db.q("SELECT * FROM users WHERE status<>'blocked' AND COALESCE(news,1)=1"):
            l = u.get("lang") or "kg"
            if self.app.send(u["id"], make(l), kb(l) if kb else None, preview=preview):
                n += 1
            time.sleep(0.04)
        return n

    # ---------- 1. Рынок эрежеси (фондо) ----------
    def tick(self):
        if self.db.kv("urgent_paused"):
            return None
        p = MP.pulse()
        self.last_pulse = p
        a = MP.alert_of(p)
        st = self.db.kv("urgent_state") or {}
        now = int(time.time() * 1000)
        if not a:
            if st.get("active"):
                self.live.post({"type": "alert_clear"}) if self.live.ok() else None
                st["active"] = None
                self.db.kv_set("urgent_state", st)
            return None
        if now - st.get(a["id"], 0) < COOLDOWN_MS:
            if st.get("active") == a["id"] and now - st.get("site_t", 0) > REFRESH_MS and self.live.ok():
                self.live.post({"type": "alert", "item": a, "push": False})          # плашканын сандарын жаңыртуу
                st["site_t"] = now
                self.db.kv_set("urgent_state", st)
            return None
        lang = os.environ.get("TG_LANG", "kg")
        ch = self.to_channel(market_msg(a, p, lang, self.site))
        n = self.to_users(lambda l: market_msg(a, p, l, self.site))
        site = self.live.post({"type": "alert", "item": a, "push": True}) if self.live.ok() else {"error": "LIVE_KEY жок"}
        st.update({a["id"]: now, "active": a["id"], "site_t": now})
        self.db.kv_set("urgent_state", st)
        print("⚠️ ШАШЫЛЫШ: %s → канал %s · бот %d · сайт %s · push %s" % (
            a["ky"], "✓" if ch else "—", n, "✓" if site.get("ok") else site.get("error"), site.get("pushed", 0)))
        self.app.notify_admins("⚠️ Шашылыш автоматтык жөнөтүлдү: %s\nКанал: %s · ботто: %d · сайт: %s · тиркемеге push: %s" % (
            E(a["ky"]), "✓" if ch else "жок (TELEGRAM_CHANNEL)", n, "✓" if site.get("ok") else E(site.get("error")), site.get("pushed", 0)))
        return a

    def loop(self):
        threading.Thread(target=self.loop_feed, daemon=True).start()     # RSS ~30 с — рынок эрежесин кармабасын
        while True:
            for name, fn in (("рынок пульсу", self.tick), ("анонстор", self.cal_tick)):
                try:
                    fn()
                except Exception as e:  # noqa: BLE001
                    print("! %s: %s" % (name, self.app.tg.redact(e)))
            time.sleep(TICK_S)

    def loop_feed(self):
        time.sleep(20)
        while True:
            try:
                self.feed_tick()
            except Exception as e:  # noqa: BLE001
                self.feed_state = "ката: %s" % str(e)[:80]
                print("! жаңылык агымы: %s" % self.app.tg.redact(e))
            time.sleep(FEED_TICK_S)

    # ---------- 4. Жаңылык агымы: RSS → сайт дароо; маанилүүсү → кооз пост ----------
    def feed_tick(self, now=None, snap=None):
        import news_feed as NF
        errors = []
        snap = snap or NF.snapshot(errors)
        now = now or int(time.time() * 1000)
        items = [dict(x, kind=k) for k in ("main", "opinions", "ta") for x in snap[k]]
        seen_list = self.db.kv("nf_seen") or []
        seen = set(seen_list)
        if not seen_list:                         # биринчи жолу: азыркыларды «көрүлдү» деп белгилейбиз, эч нерсе жөнөтпөйбүз
            ids = [i for x in items for i in NF.member_ids(x)]
            self.db.kv_set("nf_seen", ids[-1500:])
            self.feed_state = "✓ башталды (%d жаңылык белгиленди)" % len(ids)
            return {"seeded": len(ids)}
        new = [x for x in items if not any(i in seen for i in NF.member_ids(x)) and now - x["t"] < FRESH_MAX_AGE_MS]
        for x in new:
            for i in NF.member_ids(x):
                if i not in seen:
                    seen.add(i)
                    seen_list.append(i)
        self.db.kv_set("nf_seen", seen_list[-1500:])
        out = {"new": len(new), "site": None, "posted": None}
        if new:
            uniq = {}
            for x in new:
                uniq.setdefault(x["id"], x)
            todo = [x for x in uniq.values() if not x.get("ky")]
            if NF.has_key() and todo:
                NF.translate_into(todo, log=lambda m: print("  " + m))
            for x in new:
                c = uniq[x["id"]]
                if c is not x:
                    for k in ("ky", "ru", "desc_ky", "desc_ru"):
                        if c.get(k) and not x.get(k):
                            x[k] = c[k]
                if x.get("lang") == "ru":
                    x.setdefault("ru", x["orig"])
                    if x.get("desc"):
                        x.setdefault("desc_ru", NF.short(x["desc"], 220))
            if self.live.ok():
                r = self.live.post({"type": "fresh", "items": [self.slim(x) for x in new]})
                out["site"] = bool(r.get("ok"))
        out["posted"] = self.maybe_post(items, new, now)
        self.feed_state = "✓ %s: жаңы %d%s" % (time.strftime("%H:%M"), len(new), (" · ката: " + "; ".join(errors)[:60]) if errors else "")
        return out

    @staticmethod
    def slim(x):
        keep = ("id", "kind", "src", "url", "t", "orig", "ru", "ky", "desc_ru", "desc_ky", "cat", "tp", "imp", "n", "sym", "author", "img", "who", "who_ru", "who_ky")
        return {k: x[k] for k in keep if x.get(k) not in (None, "", [])}

    def maybe_post(self, items, new, now):
        """Маанилүү жаңылык: hot (жаңы, ≤90 мүн) же top (3+ басылма, ≤6 с). Бир окуя — бир пост, күнүнө ≤DAY_CAP."""
        import news_feed as NF
        if self.db.kv("feed_posts_paused"):
            return None
        posted = set(self.db.kv("nf_posted") or [])
        day = dt.datetime.fromtimestamp(now / 1000, BISHKEK).strftime("%Y-%m-%d")
        st = self.db.kv("nf_day") or {}
        if st.get("d") != day:
            st = {"d": day, "n": 0, "last": st.get("last", 0)}
        if st["n"] >= DAY_CAP:
            return None

        def ok(x, lim):
            return (now - x["t"] < lim and not any(i in posted for i in NF.member_ids(x))
                    and (x.get("lang", "ru") == "ru" or x.get("ru")))          # англисчеси — котормосу болсо гана
        hot = [x for x in new if x.get("imp") == "hot" and x["kind"] in ("main", "opinions") and ok(x, HOT_MAX_AGE_MS)]
        top = [x for x in items if x.get("imp") == "top" and x["kind"] == "main" and ok(x, TOP_MAX_AGE_MS)]
        if not hot and (not top or now - st.get("last", 0) < POST_GAP_MS):
            return None
        x = (hot or sorted(top, key=lambda y: (-(y.get("n") or 1), -y["t"])))[0]
        res = self.post_news(x)
        posted.update(NF.member_ids(x))
        self.db.kv_set("nf_posted", list(posted)[-600:])
        st["n"] += 1
        st["last"] = now
        self.db.kv_set("nf_day", st)
        return res

    def post_news(self, x, admin_only=None):
        """Кооз пост: канал/тема (KG+RU) → ботто жазылгандар (өз тилинде) → hot болсо сайт плашкасы + push."""
        summarize(x)
        site = self.site
        pic = x.get("url") or False      # макаланын өз сүрөтү (og:image) — Telegram аны тексттин үстүнө чоң кылып көрсөтөт
        if admin_only:
            self.app.send(admin_only, news_msg(x, "kg", both=True), news_kb(x, "kg", site, both=True), preview=pic)
            self.app.send(admin_only, news_msg(x, "ru"), news_kb(x, "ru", site), preview=pic)
            return {"preview": True}
        ch = self.to_channel(news_msg(x, "kg", both=True), kb=news_kb(x, "kg", site, both=True), preview=pic)
        n = self.to_users(lambda l: news_msg(x, l), kb=lambda l: news_kb(x, l, site), preview=pic)
        live = {}
        if x.get("imp") == "hot" and self.live.ok():
            live = self.live.post({"type": "urgent", "push": True, "item": {
                "ky": x.get("ky") or x.get("ru") or x["orig"], "ru": x.get("ru") or x["orig"], "url": x["url"]}})
        print("📰 Жаңылык посту (%s): %s → канал %s · бот %d · сайт %s" % (x.get("imp"), x["orig"][:70], "✓" if ch else "—", n, "✓" if live.get("ok") else "—"))
        self.app.notify_admins("📰 Авто-пост (%s): %s\nКанал: %s · ботто: %d%s" % (
            "⚡ шашылыш" if x.get("imp") == "hot" else "🔥 маанилүү", E((x.get("ky") or x.get("ru") or x["orig"])[:120]),
            E(ch["url"] or "✓") if ch else "жок (/news)", n, (" · сайт плашкасы ✓ · push %s" % live.get("pushed", 0)) if live.get("ok") else ""))
        return {"channel": bool(ch), "users": n, "site": bool(live.get("ok"))}

    def sample_post(self, aid):
        """Админге гана: акыркы маанилүү (же эң жаңы) жаңылык каналга кандай чыгарын көрсөтөт."""
        import news_feed as NF
        self.app.send(aid, "🔎 Жаңылыктар окулууда…")
        snap = NF.snapshot([])
        lst = [x for x in snap["main"] if x.get("imp")] or snap["main"]
        if not lst:
            return self.app.send(aid, "Жаңылык алынган жок (булактар жеткиликсиз).")
        x = dict(sorted(lst, key=lambda y: (y.get("imp") != "hot", -(y.get("n") or 1), -y["t"]))[0])
        x.setdefault("imp", "top")
        if x.get("lang") == "ru":
            x.setdefault("ru", x["orig"])
        if NF.has_key() and not x.get("ky"):
            NF.translate_into([x], log=lambda m: None)
        self.app.send(aid, "👀 <b>Үлгү</b> — каналга/темага (KG+RU) жана ботто (ар бири өз тилинде) ушундай чыгат. Эч кимге жөнөтүлгөн жок.")
        return self.post_news(x, admin_only=aid)

    # ---------- 5. Экономикалык анонстор ----------
    def calendar(self):
        """calendar.json: сайттан (ар 30 мүн), болбосо репозиторийдеги файлдан."""
        if self.cal_cache is not None and time.time() - self.cal_t < CAL_REFRESH_S:
            return self.cal_cache
        data = None
        try:
            req = urllib.request.Request(self.site + "/assets/data/calendar.json?b=%d" % (time.time() // 600), headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read().decode("utf-8"))
        except Exception:  # noqa: BLE001 — сайт жеткиликсиз же файл али жок
            data = None
        if not (data or {}).get("events"):
            try:
                with open(CAL_FILE, encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, ValueError):
                data = None
        self.cal_cache, self.cal_t = (data or {}).get("events") or [], time.time()
        return self.cal_cache

    def today_events(self, now=None):
        now_dt = dt.datetime.fromtimestamp((now or time.time() * 1000) / 1000, BISHKEK)
        a = int(now_dt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
        b = a + 86400000
        return [e for e in self.calendar() if a <= e["t"] < b and (e["imp"] == 3 or (e["imp"] == 0 and e["cur"] in MAJOR))]

    def cal_tick(self, now=None):
        if self.db.kv("cal_paused"):
            return None
        now = now or int(time.time() * 1000)
        evs = self.calendar()
        if not evs:
            return None
        bk = dt.datetime.fromtimestamp(now / 1000, BISHKEK)
        day = bk.strftime("%Y-%m-%d")
        site = self.site
        out = {}
        if DIGEST_H <= bk.hour < 12 and self.db.kv("cal_digest") != day:
            self.db.kv_set("cal_digest", day)
            lst = [e for e in self.today_events(now) if e["imp"] == 0 or e["t"] > now]
            if any(e["imp"] == 3 for e in lst):
                def kb(l):
                    return {"inline_keyboard": [[{"text": "📅 Весь календарь" if l == "ru" else "📅 Толук календарь", "url": site + "/news.html#calendar"}]]}
                ch = self.to_channel(cal_digest_msg(lst, "kg", site, both=True), kb=kb("kg"))
                n = self.to_users(lambda l: cal_digest_msg(lst, l, site), kb=kb)
                out["digest"] = {"events": len(lst), "channel": bool(ch), "users": n}
                print("📅 Бүгүнкү анонстор: %d окуя → канал %s · бот %d" % (len(lst), "✓" if ch else "—", n))
        rem = self.db.kv("cal_rem") or []
        soon = [e for e in evs if e["imp"] == 3 and 0 < e["t"] - now <= REMIND_MIN * 60000 + 90000 and e["id"] not in rem]
        if soon:
            t0 = min(e["t"] for e in soon)
            group = [e for e in soon if e["t"] == t0]
            rem += [e["id"] for e in group]
            self.db.kv_set("cal_rem", rem[-300:])
            ch = self.to_channel(cal_remind_msg(group, "kg", site, both=True, now=now))
            n = self.to_users(lambda l: cal_remind_msg(group, l, site, now=now))
            out["remind"] = {"events": len(group), "channel": bool(ch), "users": n}
            print("⏰ Анонс эскертүүсү: %s → канал %s · бот %d" % (", ".join(e["en"] for e in group)[:80], "✓" if ch else "—", n))
        return out or None

    # ---------- Форумдагы тема: админ /news жазса — жаңылыктар ошол темага ----------
    def on_group_cmd(self, chat, th, cmd):
        if cmd not in ("/news", "/жаңылыктар", "/новости"):
            return False
        cid = chat.get("id")
        self.db.kv_set("ch:news", cid)
        self.db.kv_set("th:news", th)
        self.app.send(cid, "✅ AITRADING.KG: жаңылыктар жана экономикалык анонстор ушул жерге чыгат.\n"
                           "✅ Новости и экономические анонсы будут публиковаться здесь.", thread=th)
        self.app.notify_admins("📰 Жаңылыктар туташты: <b>%s</b>%s" % (E(chat.get("title") or cid), (" · тема #%s" % th) if th else ""))
        return True

    # ---------- Колдонуучу: күйгүзүү/өчүрүү ----------
    def user_row(self, u):
        l = "ru" if u.get("lang") == "ru" else "kg"
        on = u.get("news", 1) != 0
        return [(NEWS_BTN[l][0 if on else 1], "nws:off" if on else "nws:on")]

    def on_user_cb(self, u, data):
        self.db.upd(u["id"], news=1 if data == "nws:on" else 0)
        return self.app.show_profile(self.db.user(u["id"]))

    # ---------- Админ ----------
    def admin_rows(self):
        paused = self.db.kv("urgent_paused")
        fp, cp = self.db.kv("feed_posts_paused"), self.db.kv("cal_paused")
        return [[("🚨 Шашылыш жаңылык", "nw:urg"), ("🐦 Твит (X)", "nw:tw")],
                [("▶️ Рынок плашкасын улантуу" if paused else "⏸ Рынок плашкасын токтотуу", "nw:auto"), ("📈 Рынок азыр", "nw:now")],
                [("▶️ Авто-жаңылыктар" if fp else "⏸ Авто-жаңылыктар", "nw:feed"), ("▶️ Анонстор" if cp else "⏸ Анонстор", "nw:cal")],
                [("👀 Пост үлгүсү", "nw:sample"), ("📅 Бүгүнкү анонстор", "nw:today")]]

    def status_line(self):
        return "Жаңылыктар → %s · Сайт/тиркеме: %s · Агым: %s · Котормо: %s" % (
            E(self.dest_name()), "✓" if self.live.ok() else "LIVE_KEY жок", E(self.feed_state), "✓ Claude" if self._has_key() else "жок (орусча)")

    @staticmethod
    def _has_key():
        return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))

    def on_admin_cb(self, u, data, msg):
        aid = u["id"]
        if data == "nw:urg":
            self.db.kv_set("nw:%d" % aid, {"stage": "urg"})
            return self.app.send(aid, "🚨 <b>Шашылыш жаңылык</b>\nТекстти жазыңыз — кыргызча. Орусчасын кошсоңуз, өзүнчө сапка <code>---</code> коюп, андан кийин жазыңыз.\n"
                                      "Булактын шилтемесин (https://…) акыркы сапка коюңуз — ал «Булак» болуп чыгат.\n"
                                      "Ырастагандан кийин: канал → ботто жазылгандар → сайттагы плашка → тиркемеге билдирме.",
                                 {"inline_keyboard": [[{"text": "❌ Жокко чыгаруу", "callback_data": "nw:cancel"}]]})
        if data == "nw:tw":
            self.db.kv_set("nw:%d" % aid, {"stage": "tw"})
            return self.app.send(aid, "🐦 X'теги твиттин шилтемесин жөнөтүңүз (мисалы https://x.com/elonmusk/status/…).\n"
                                      "Бот твиттин бар экенин X'тин расмий oEmbed'инен текшерет. Алгач Telegram-каналга, анан сайтка чыгат.",
                                 {"inline_keyboard": [[{"text": "❌ Жокко чыгаруу", "callback_data": "nw:cancel"}]]})
        if data == "nw:cancel":
            self.db.kv_set("nw:%d" % aid, None)
            return self.app.send(aid, "Жокко чыгарылды.")
        if data in ("nw:auto", "nw:feed", "nw:cal"):
            k = {"nw:auto": "urgent_paused", "nw:feed": "feed_posts_paused", "nw:cal": "cal_paused"}[data]
            self.db.kv_set(k, None if self.db.kv(k) else True)
            return self.app.adm_home(u, msg.get("message_id"))
        if data == "nw:sample":
            return self.sample_post(aid)
        if data == "nw:today":
            lst = self.today_events()
            if not lst:
                return self.app.send(aid, "📅 Бүгүн маанилүү (●●●) анонс жок. Календарь: %s/news.html#calendar" % self.site)
            return self.app.send(aid, "👀 Эртең мененки пост ушундай чыгат (08:00):\n\n" + cal_digest_msg(lst, "kg", self.site, both=True))
        if data == "nw:now":
            try:
                p = MP.pulse()
            except Exception as e:  # noqa: BLE001
                return self.app.send(aid, "Рынок маалыматы алынган жок: %s" % E(e))
            a = MP.alert_of(p)
            rows = "\n".join("%s 24с %s · 1с %s" % (k, MP.pct(v.get("c24", 0)), MP.pct(v.get("c1h", 0))) for k, v in p["rows"].items())
            return self.app.send(aid, "📈 <b>Рынок азыр</b> (%s)\nМедиана: 24с <b>%s</b> (чек ±%g%%) · 1с <b>%s</b> (чек ±%g%%)\n<code>%s</code>\n\nШашылыш: %s\n%s" % (
                p["src"], MP.pct(p["m24"]), p["th24"], MP.pct(p["m1h"]), p["th1h"], E(rows), E(a["ky"]) if a else "жок", self.status_line()))
        d = self.db.kv("nw:%d" % aid) or {}
        if data == "nw:urg_go" and d.get("stage") == "urg_ok":
            self.db.kv_set("nw:%d" % aid, None)
            return self.publish_urgent(u, d)
        if data == "nw:tw_go" and d.get("stage") == "tw_ok":
            self.db.kv_set("nw:%d" % aid, None)
            return self.publish_tweet(u, d)
        if data == "nw:tw_tr" and d.get("stage") == "tw_ok":
            d["stage"] = "tw_tr"
            self.db.kv_set("nw:%d" % aid, d)
            return self.app.send(aid, "✏️ Котормону жазыңыз: кыргызча, анан өзүнчө сапка <code>---</code> жана орусча.")
        return None

    def on_admin_text(self, u, m, text):
        """Админдин билдирүүсү: шашылыш текст, твиттин шилтемеси же котормо. Колдонулса — True."""
        aid = u["id"]
        d = self.db.kv("nw:%d" % aid) or {}
        st = d.get("stage")
        if st == "urg" and text:
            ky, ru = split_kg_ru(text)
            url = ""
            for part in (ky, ru):
                mm = re.search(r"(https://\S+)\s*$", part)
                if mm:
                    url = mm.group(1)
            ky = re.sub(r"\s*https://\S+\s*$", "", ky).strip()
            ru = re.sub(r"\s*https://\S+\s*$", "", ru).strip() or ky
            if not ky:
                self.app.send(aid, "Текст бош. Кайра жазыңыз.")
                return True
            d = {"stage": "urg_ok", "ky": ky[:700], "ru": ru[:700], "url": url[:600]}
            self.db.kv_set("nw:%d" % aid, d)
            n = (self.db.one("SELECT COUNT(*) n FROM users WHERE status<>'blocked' AND COALESCE(news,1)=1") or {}).get("n", 0)
            self.app.send(aid, "👀 <b>Алдын ала көрүү</b>\n\n" + urgent_msg(d, "kg", self.site) + "\n\n— — —\n🇷🇺 " + E(d["ru"]) +
                          "\n\nАлуучулар: канал %s · ботто %d · сайт жана тиркеме %s" % ("✓" if self.channel else "жок", n, "✓" if self.live.ok() else "жок (LIVE_KEY)"),
                          {"inline_keyboard": [[{"text": "🚨 Жөнөтүү", "callback_data": "nw:urg_go"}, {"text": "❌ Жокко чыгаруу", "callback_data": "nw:cancel"}]]})
            return True
        if st == "tw_tr" and text:
            d["ky"], d["ru"] = split_kg_ru(text)
            d["stage"] = "tw_ok"
            self.db.kv_set("nw:%d" % aid, d)
            return self.preview_tweet(u, d)
        if TWEET_RE.search(text or "") and st in (None, "tw"):
            self.app.send(aid, "🔎 Твит текшерилүүдө…")
            try:
                tw = oembed(TWEET_RE.search(text).group(0))
            except ValueError as e:
                self.db.kv_set("nw:%d" % aid, None)
                self.app.send(aid, "❌ Твит табылган жок же жабык аккаунттан (%s). Шилтемени текшериңиз." % E(e))
                return True
            except Exception as e:  # noqa: BLE001
                self.app.send(aid, "❌ X'ке туташкан жок: %s" % E(e))
                return True
            tr = translate_tweet(tw["text"]) or {}
            tw.update(stage="tw_ok", ky=tr.get("ky", ""), ru=tr.get("ru", ""))
            self.db.kv_set("nw:%d" % aid, tw)
            return self.preview_tweet(u, tw)
        return False

    def preview_tweet(self, u, d):
        note = "" if d.get("ky") else "\n\n(Котормо жок: ANTHROPIC_API_KEY коюлган эмес. «✏️ Котормо» менен өзүңүз кошсоңуз болот.)"
        warn = "" if self.channel else "\n\n⚠️ TELEGRAM_CHANNEL коюлган эмес — твит алгач каналга чыгышы керек, ошондуктан жарыялоо мүмкүн эмес."
        self.app.send(u["id"], "👀 <b>Алдын ала көрүү</b> (каналга ушундай чыгат)\n\n" + tweet_msg(d, os.environ.get("TG_LANG", "kg")) + note + warn,
                      {"inline_keyboard": [[{"text": "📣 Каналга, анан сайтка", "callback_data": "nw:tw_go"}],
                                           [{"text": "✏️ Котормо", "callback_data": "nw:tw_tr"}, {"text": "❌ Жокко чыгаруу", "callback_data": "nw:cancel"}]]})
        return True

    def publish_tweet(self, u, d):
        aid = u["id"]
        if not self.channel:
            return self.app.send(aid, "❌ TELEGRAM_CHANNEL коюлган эмес. Твит алгач каналга чыгышы керек — сайтка да жарыяланган жок.")
        ch = self.to_channel(tweet_msg(d, os.environ.get("TG_LANG", "kg")))
        if not ch:
            return self.app.send(aid, "❌ Каналга жөнөтүлгөн жок (бот каналда админби?). Сайтка да жарыяланган жок.")
        item = {k: d.get(k, "") for k in ("url", "handle", "name", "date", "text", "ky", "ru")}
        item["tg_url"] = ch["url"]
        site = self.live.post({"type": "tweet", "item": item, "push": False}) if self.live.ok() else {"error": "LIVE_KEY жок"}
        return self.app.send(aid, "✅ Твит жарыяланды.\n1) Канал: %s\n2) Сайт: %s" % (
            E(ch["url"] or "✓"), "✓ news.html#tweets" if site.get("ok") else "✗ " + E(site.get("error"))))

    def publish_urgent(self, u, d):
        aid = u["id"]
        lang = os.environ.get("TG_LANG", "kg")
        ch = self.to_channel(urgent_msg(d, lang, self.site))
        n = self.to_users(lambda l: urgent_msg(d, l, self.site))
        site = self.live.post({"type": "urgent", "item": {"ky": d["ky"], "ru": d["ru"], "url": d.get("url", "")}, "push": True}) if self.live.ok() else {"error": "LIVE_KEY жок"}
        return self.app.send(aid, "✅ Шашылыш жаңылык жөнөтүлдү.\nКанал: %s · ботто: %d · сайт: %s · тиркемеге push: %s" % (
            E(ch["url"] or "✓") if ch else "жок", n, "✓" if site.get("ok") else "✗ " + E(site.get("error")), site.get("pushed", 0)))


if __name__ == "__main__":
    # Текшерүү: python tools/tg_news.py https://x.com/jack/status/20
    import sys
    try:
        print(json.dumps(oembed(sys.argv[1]), ensure_ascii=False, indent=1) if len(sys.argv) > 1 else "URL керек")
    except Exception:  # noqa: BLE001
        traceback.print_exc()
