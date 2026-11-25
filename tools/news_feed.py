"""Жаңылыктар / Новости: RSS-булактардан башкы жаңылыктар, атактуулардын пикири, техникалык анализ.

    python tools/news_feed.py              # site/assets/data/news.json'ду жаңыртат
    python tools/news_feed.py --dry-run    # эч нерсе жазбайт, табылганын көрсөтөт
    python tools/news_feed.py --no-translate

Эрежелер (автордун талабы):
  - Ар бир жаңылык — чыныгы булактан (RSS), түп нускасына шилтеме менен. Эч нерсе ойлоп табылбайт.
  - Кыргызча котормо: ANTHROPIC_API_KEY болсо, Claude аталышты которот (сандар так ошол бойдон калат —
    текшерилет; дал келбесе котормо жарыяланбайт). Ачкыч жок болсо — түп нуска (орусча) «RU» белгиси менен.
  - «Пикирлер» — белгилүү инвесторлордун/атактуулардын сөзүн келтирген макалалар (аты + «заявил/считает…»).
  - «Техникалык анализ» — TradingView'дун расмий RSS'индеги идеялар жана FXStreet'тин талдоолору.
    Бул — авторлордун пикири, сигнал эмес.
Иштетүү: GitHub Actions (.github/workflows/daily-update.yml) ар 2 саатта.
"""
import argparse
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "site", "assets", "data", "news.json")
MODEL = "claude-opus-5-5"
UA = "Mozilla/5.0 (compatible; AITRADING.KG news reader; +https://aitrading-kg.pages.dev)"
MAX_AGE_H = 72          # мындан эски жаңылыктар көрсөтүлбөйт
LIMITS = {"main": 60, "opinions": 24, "ta": 24}

# ---------- Булактар (баары расмий RSS) ----------
# kind: main — башкы лента (жана пикирлер), op — пикирлер гана (англисче, котормо болсо гана), ta — теханализ
FEEDS = [
    {"id": "forklog", "name": "ForkLog", "url": "https://forklog.com/feed", "lang": "ru", "kind": "main", "cat": "crypto"},
    {"id": "bits", "name": "Bits.media", "url": "https://bits.media/rss2/", "lang": "ru", "kind": "main", "cat": "crypto"},
    {"id": "fxstreet", "name": "FXStreet", "url": "https://www.fxstreet.ru.com/rss/news", "lang": "ru", "kind": "main", "cat": "fx"},
    {"id": "rbc", "name": "РБК", "url": "https://rssexport.rbc.ru/rbcnews/news/30/full.rss", "lang": "ru", "kind": "main", "cat": None,
     "only_cats": {"Бизнес", "Экономика", "Финансы", "Инвестиции", "Крипто", "Технологии и медиа"}},
    {"id": "kommersant", "name": "Коммерсантъ", "url": "https://www.kommersant.ru/RSS/section-economics.xml", "lang": "ru", "kind": "main", "cat": None},
    {"id": "cnbc", "name": "CNBC", "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html", "lang": "en", "kind": "op", "cat": "stock"},
    {"id": "marketwatch", "name": "MarketWatch", "url": "https://feeds.content.dowjones.io/public/rss/mw_topstories", "lang": "en", "kind": "op", "cat": "stock"},
    {"id": "coindesk", "name": "CoinDesk", "url": "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml", "lang": "en", "kind": "op", "cat": "crypto"},
    {"id": "cointelegraph", "name": "Cointelegraph", "url": "https://cointelegraph.com/rss", "lang": "en", "kind": "op", "cat": "crypto"},
    {"id": "tradingview", "name": "TradingView", "url": "https://ru.tradingview.com/feed/", "lang": "ru", "kind": "ta", "cat": None},
    {"id": "fxstreet_ta", "name": "FXStreet", "url": "https://www.fxstreet.ru.com/rss/analysis", "lang": "ru", "kind": "ta", "cat": "fx"},
]

# ---------- Белгилүү адамдар (пикирлер бөлүмү) ----------
# (id, аты орусча, аты кыргызча, регекс)
PEOPLE = [
    ("buffett", "Уоррен Баффет", "Уоррен Баффет", r"Баффет\w*|Buffett"),
    ("musk", "Илон Маск", "Илон Маск", r"Илон\w* Маск\w*|Маск(?:а|у|ом|е)?|Elon Musk|Musk"),
    ("trump", "Дональд Трамп", "Дональд Трамп", r"Трамп(?:а|у|ом|е)?|Trump"),
    ("powell", "Джером Пауэлл", "Джером Пауэлл", r"Пауэлл\w*|Powell"),
    ("saylor", "Майкл Сэйлор", "Майкл Сэйлор", r"Сэйлор\w*|Saylor"),
    ("dalio", "Рэй Далио", "Рэй Далио", r"Далио|Dalio"),
    ("wood", "Кэти Вуд", "Кэти Вуд", r"Кэти Вуд\w*|Cathie Wood"),
    ("dimon", "Джейми Даймон", "Джейми Даймон", r"Даймон\w*|Dimon"),
    ("fink", "Ларри Финк", "Ларри Финк", r"Ларри Финк\w*|Larry Fink"),
    ("burry", "Майкл Бьюрри", "Майкл Бьюрри", r"Бьюрри|Бэрри|Michael Burry|Burry"),
    ("huang", "Дженсен Хуанг", "Дженсен Хуанг", r"Хуанг\w*|Jensen Huang"),
    ("bessent", "Скотт Бессент", "Скотт Бессент", r"Бессент\w*|Bessent"),
    ("lagarde", "Кристин Лагард", "Кристин Лагард", r"Лагард|Lagarde"),
    ("cz", "Чанпэн Чжао (CZ)", "Чанпэн Чжао (CZ)", r"Чанпэн\w* Чжао|Changpeng Zhao"),
    ("buterin", "Виталик Бутерин", "Виталик Бутерин", r"Бутерин\w*|Buterin"),
    ("hayes", "Артур Хейс", "Артур Хейс", r"Артур\w* Хейс\w*|Arthur Hayes"),
    ("kiyosaki", "Роберт Кийосаки", "Роберт Кийосаки", r"Кийосаки|Kiyosaki"),
    ("schiff", "Питер Шифф", "Питер Шифф", r"Питер\w* Шифф\w*|Peter Schiff"),
    ("ackman", "Билл Экман", "Билл Экман", r"Экман\w*|Ackman"),
    ("novogratz", "Майк Новограц", "Майк Новограц", r"Новограц\w*|Novogratz"),
    ("altman", "Сэм Альтман", "Сэм Альтман", r"Альтман\w*|Sam Altman"),
    ("nabiullina", "Эльвира Набиуллина", "Эльвира Набиуллина", r"Набиуллин\w*"),
    ("zuckerberg", "Марк Цукерберг", "Марк Цукерберг", r"Цукерберг\w*|Zuckerberg"),
]
PEOPLE_RE = [(pid, ru, ky, re.compile(r"(?<![\w-])(?:%s)(?![\w-])" % rx)) for pid, ru, ky, rx in PEOPLE]
OPINION_RE = re.compile(
    r"заяв\w*|счита\w*|предупред\w*|предсказ\w*|прогноз\w*|назвал\w*|допуст\w*|ожида\w*|уверен\w*|оценил\w*|"
    r"рассказал\w*|прокомментир\w*|раскритик\w*|призвал\w*|пообещал\w*|объяснил\w*|высказал\w*|увидел\w*|ответил\w*|"
    r"\b(?:says?|said|warns?|predicts?|thinks?|believes?|calls?|expects?|sees|bets?|argues?|urges?|slams?|touts?)\b", re.I)

CAT_RX = [
    ("crypto", re.compile(r"биткоин|bitcoin|\bBTC\b|крипт|crypto|токен|token|блокчейн|blockchain|стейблкоин|stablecoin|эфир\w*|ethereum|\bETH\b|Solana|\bSOL\b|XRP|DeFi|NFT|майнер|Binance|BingX|Coinbase|Strategy", re.I)),
    ("fx", re.compile(r"доллар|евро\b|евро |рубл|юан|иен|франк|фунт|EUR/|GBP/|USD/|/USD|/JPY|ФРС|ЕЦБ|Банк Англии|\bставк|инфляц|золот|серебр|нефт|Brent|XAU|XAG|PMI|ВВП|Fed\b|ECB", re.I)),
    ("stock", re.compile(r"акци|индекс|S&P|Nasdaq|Dow|IPO|капитализац|отчет|отчёт|дивиденд|бирж|Nvidia|Apple|Tesla|Microsoft|Amazon|Meta|stocks?|shares|earnings", re.I)),
]

# Темалар (TradingView'дагыдай чыпкалар): рынок кыймылы, ETF, жөнгө салуу, технология, макро.
# Бир жаңылыкта бир нече тема болушу мүмкүн. Сөздүн башы \b менен (Python'до кириллица да сөз белгиси).
TOPIC_RX = [
    ("move", re.compile(r"\b(?:вырос|выросл|рост[аеу]?\b|подорож|подешев|упал|упад|пада|падени|снизил|снижени|сократил|сокращ|потерял|прибавил|подскоч|"
                        r"укрепил|ослаб|продал|обвал|рухн|обруш|ралли|взл[её]т|скач[ео]к|"
                        r"максимум|минимум|рекорд|ликвидац|отскоч|отскок|распродаж|surge|soar|jump|rall(?:y|ies)|plunge|slump|tumble|drops?\b|"
                        r"falls?\b|rises?\b|record|all-time|ATH\b|sell-?off)", re.I)),
    ("etf", re.compile(r"\b(?:ETF|ETP|биржев\w* фонд|BlackRock|iShares|Grayscale)", re.I)),
    ("reg", re.compile(r"\b(?:регулир|регулятор|закон|запрет|лиценз|санкц|SEC\b|CFTC|MiCA|суд\b|суд[аеу]\b|иск\b|штраф|налог|Минфин|Госдум|задерж|уголовн|мошенн|инсайдер|расследов|"
                       r"Конгресс|Сенат|прокур|арест|регистрац|bill\b|lawsuit|regulat|ban\b|court|tax|sanction)", re.I)),
    ("tech", re.compile(r"\b(?:технолог|обновлени|апгрейд|хардфорк|форк\b|блокчейн|протокол|запуст|запуск|ИИ\b|искусственн\w* интеллект|AI\b|"
                        r"нейросет|кош[её]л|layer|upgrade|launch|mainnet|testnet|смарт-контракт|квантов|токенизац|stablecoin|стейблкоин)", re.I)),
    ("macro", re.compile(r"\b(?:ставк|инфляц|ВВП|ФРС|ЕЦБ|Банк России|ЦБ\b|ЦБ РФ|занятост|безработ|PMI|рецесс|госдолг|облигац|доходност|"
                         r"Fed\b|ECB|CPI|GDP|payrolls?|treasur|yields?\b|tariffs?|пошлин|нефт|OPEC|ОПЕК)", re.I)),
]

# Маанилүүлүк (бот ушул эреже менен гана автоматтык жазат; сайтта «🔥» белгиси):
#   hot — борбордук банктын чен боюнча чечими, SEC'тин ETF'ти жактырышы, биржанын/протоколдун бузулушу ($ суммасы менен),
#         акча чыгарууну токтотуу, банкроттук;
#   top — 3+ басылма бир окуяны жазды, же биткоиндин тарыхый максимуму / рыноктун кулашы.
HOT_RX = re.compile(
    r"(?:ФРС|ЕЦБ|Банк\w* (?:Англии|Японии|России|Канады)|ЦБ РФ|Нацбанк\w*|НБКР|\bFed\b|\bECB\b|\bBoE\b|\bBoJ\b)[^.]{0,70}?"
    r"\b(?:повысил\w*|понизил\w*|снизил\w*|сохранил\w*|оставил\w*|raises?|raised|cuts?|holds?|held|keeps?|kept)\b[^.]{0,40}?(?:ставк|rates?\b)"
    r"|\b(?:SEC|КЦББ)\b[^.]{0,60}?\b(?:одобрил\w*|утвердил\w*|approv\w*)[^.]{0,40}?ETF"
    r"|\b(?:взлом\w*|хакер\w*|эксплойт\w*|exploit\w*|hack(?:ed|ers?)?|drain\w*|украл\w*|похитил\w*|похищ\w*|stolen)\b[^.]{0,90}?(?:\$|долл|млн|млрд|million|billion)"
    r"|\b(?:приостановил\w*|заморозил\w*|halt(?:s|ed)?|suspend\w*|freez\w*)\b[^.]{0,40}?(?:вывод|withdrawals?)"
    r"|\b(?:банкротств\w*|bankrupt\w*|Chapter 11)", re.I)
TOP_RX = re.compile(r"\b(?:биткоин\w*|bitcoin|BTC)\b[^.]{0,50}?(?:историческ\w* максимум|новый рекорд|all-time high|ATH\b)"
                    r"|\b(?:обвал\w*|рухн\w*|обруш\w*|crash\w*|plunge\w*)\b[^.]{0,50}?(?:рын\w*|биткоин\w*|bitcoin|крипт\w*|market|индекс\w*|S&P|Nasdaq)", re.I)


def topics_of(text):
    return [k for k, rx in TOPIC_RX if rx.search(text or "")]


def importance(x):
    text = (x.get("orig") or "") + " " + clean(x.get("desc") or "")[:300]
    if HOT_RX.search(text):
        return "hot"
    if (x.get("n") or 1) >= 3 or TOP_RX.search(text):
        return "top"
    return None


def enrich(x):
    """Тема жана маанилүүлүк талааларын кошот (сайт чыпкалары жана бот үчүн)."""
    text = (x.get("orig") or "") + " " + clean(x.get("desc") or "")[:300]
    tp = topics_of(text)
    if tp:
        x["tp"] = tp
    imp = importance(x)
    if imp:
        x["imp"] = imp
    return x


STOP = set("и в во на по с со из за к о об от до для при что как а но не это его ее её их же ли бы то the a an of to in on for and or is are was be at by with from as после фоне года году млн млрд".split())


# ---------- Жардамчылар ----------
def get(url, timeout=20):
    # gzip: айрым серверлер (мис. ForkLog) кысылбаган жоопту HTTP/1.1'де өтө жай берет → таймаут
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, */*",
                                               "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        if (r.headers.get("Content-Encoding") or "").lower() == "gzip" or raw[:2] == b"\x1f\x8b":
            import gzip
            raw = gzip.decompress(raw)
        return raw


def clean(s):
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()


def short(s, n):
    s = clean(s)
    if len(s) <= n:
        return s
    cut = s[:n].rsplit(" ", 1)[0]
    return cut.rstrip(",.;:—-") + "…"


def when(s):
    try:
        return int(parsedate_to_datetime(s).timestamp() * 1000)
    except (TypeError, ValueError, IndexError):
        return None


def iid(url):
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]


def words(t):
    """Аталыштын «уңгулары» (5 тамга): Хуанг/Хуанга бир эле сөз болуп эсептелет."""
    return {w[:5] for w in re.findall(r"[\w$%]+", t.lower()) if len(w) > 2 and w not in STOP}


def cat_of(text, default):
    for c, rx in CAT_RX:
        if rx.search(text):
            return c
    return default


NS = {"content": "http://purl.org/rss/1.0/modules/content/", "dc": "http://purl.org/dc/elements/1.1/"}


def parse_feed(feed):
    raw = get(feed["url"])
    root = ET.fromstring(raw)
    out = []
    for it in root.iter("item"):
        title = clean(it.findtext("title"))
        link = (it.findtext("link") or "").strip()
        if not title or not link.startswith("http"):
            continue
        cats = [clean(c.text) for c in it.findall("category") if c.text]
        out.append({
            "title": title, "url": link, "t": when(it.findtext("pubDate")),
            "desc": it.findtext("description") or "", "content": it.findtext("content:encoded", namespaces=NS) or "",
            "author": clean(it.findtext("dc:creator", namespaces=NS) or it.findtext("author") or ""), "cats": cats,
        })
    return out


# FXStreet'тин «талдоо» лентасынан чыныгы техникалык/рыноктук талдоолор гана
TA_WORDS = re.compile(r"прогноз|анализ|технич|уровн|поддержк|сопротивлен|тренд|сценари|диапазон|RSI|MACD|скользящ|отскак|пробо|"
                      r"лонг|шорт|long|short|коррекц|волн|сетап|setup|зон[аеуы]|цел[иья]|импульс|свеч|фигур|клин|отчет CFTC|позиционир", re.I)

# TradingView идеясы: символ, автор, сүрөт content:encoded ичинде
TV_SKIP = re.compile(r"^(RUS|MOEX|MOEX_DLY|SPBEX|TQBR):", re.I)


def tv_idea(x):
    c = x["content"]
    sym = clean((re.search(r'class="symbol-descr">(.*?)<', c) or [None, ""])[1])
    author = clean((re.search(r'class="chart-author">\s*<a[^>]*>(.*?)</a>', c, re.S) or [None, ""])[1])
    img = (re.search(r'(https://s3\.tradingview\.com/[a-z0-9]/[A-Za-z0-9]+_mid\.png)', c) or [None, None])[1]   # графиктин сүрөтү (аватар эмес)
    if not sym or TV_SKIP.match(sym):
        return None
    body = clean(re.sub(r'<div class="(avatar|chart-name|chart-symbol|chart-author)".*?</div>', " ", c, flags=re.S))
    s = sym.upper()
    if re.search(r"BTC|ETH|USDT|USDC|CRYPTO|BINANCE|BYBIT|COINBASE|OKX|BINGX|BITSTAMP", s):
        cat = "crypto"
    elif re.search(r"^(FX|OANDA|FX_IDC|FOREXCOM|PEPPERSTONE|ICMARKETS|CAPITALCOM|SAXO|FXCM|TVC|COMEX|COMEX_DL|NYMEX|NYMEX_DL):|XAU|XAG|USD|EUR|JPY|GBP|CHF|AUD|NZD|CAD|:(SI|GC|CL|NG|HG)1!", s):
        cat = "fx"
    else:
        cat = "stock"
    return {"sym": sym, "author": author, "img": img, "desc": short(body, 220), "cat": cat}


def collect(errors):
    now = int(time.time() * 1000)
    main, ops, ta = [], [], []
    for f in FEEDS:
        try:
            items = parse_feed(f)
        except Exception as e:  # noqa: BLE001 — бир булак иштебесе, калгандары чыга берет
            errors.append("%s: %s" % (f["name"], e))
            continue
        for x in items:
            if not x["t"] or now - x["t"] > MAX_AGE_H * 3600000 or x["t"] > now + 600000:
                continue
            if f.get("only_cats") and not (set(x["cats"]) & f["only_cats"]):
                continue
            base = {"id": iid(x["url"]), "src": f["name"], "sid": f["id"], "url": x["url"], "t": x["t"], "lang": f["lang"], "orig": x["title"]}
            if f["kind"] == "ta":
                if f["id"] == "tradingview":
                    tv = tv_idea(x)
                    if not tv or not TA_WORDS.search(x["title"] + " " + tv["desc"]):   # идея эмес (жарнама, нускама) — кирбейт
                        continue
                    base.update(tv)
                else:
                    if not TA_WORDS.search(x["title"] + " " + clean(x["desc"])[:300]):   # талдоо эмес макалалар (нускама, жарнама) кирбейт
                        continue
                    base.update({"cat": cat_of(x["title"], f["cat"]) or f["cat"], "desc": short(x["desc"], 220), "author": x["author"] or f["name"]})
                ta.append(base)
                continue
            text = x["title"] + " " + clean(x["desc"])[:300]
            # Жалпы булактар (РБК, Коммерсантъ): рынокко тиешеси жок жаңылыктар (спорт, коом…) кирбейт
            base["cat"] = cat_of(x["title"], f["cat"])
            if not base["cat"]:
                continue
            # Пикир: адамдын аты аталышта + «заявил/считает…» сыяктуу этиш
            who = next(((pid, ru, ky) for pid, ru, ky, rx in PEOPLE_RE if rx.search(x["title"])), None)
            if who and OPINION_RE.search(text):
                o = dict(base, who=who[0], who_ru=who[1], who_ky=who[2])
                ops.append(o)
            if f["kind"] == "main":
                main.append(base)
    return main, ops, ta


def dedupe(items):
    """Окшош аталыштарды бириктирет: эң жаңысы калат, «n» — канча булак жазганы."""
    items = sorted(items, key=lambda x: -x["t"])
    out = []
    for x in items:
        w = words(x["orig"])
        for y in out:
            wy = y["_w"]
            common = len(w & wy)
            if w and wy and common >= 3 and common / len(w | wy) >= 0.34:
                if x["src"] not in y["srcs"]:
                    y["srcs"].append(x["src"])
                    y.setdefault("also", []).append({"src": x["src"], "url": x["url"]})
                break
        else:
            x = dict(x, _w=w, srcs=[x["src"]])
            out.append(x)
    for y in out:
        y["n"] = len(y.pop("srcs"))
        y.pop("_w", None)
    return out


def balance(items, limit, per_src):
    """Бир булак лентаны толтуруп салбасын."""
    cnt, out = {}, []
    for x in items:
        if cnt.get(x["sid"], 0) >= per_src:
            continue
        cnt[x["sid"]] = cnt.get(x["sid"], 0) + 1
        out.append(x)
        if len(out) >= limit:
            break
    return out


# ---------- Котормо (Claude) ----------
SYSTEM = """Сен AITRADING.KG сайтынын котормочусусуң. Каржы жаңылыктарынын аталыштарын жана кыска сыпаттамаларын которосуң.
Эрежелер:
- Мааниси так ошол бойдон калсын: эч нерсе кошпо, алып салба, баа берип же түшүндүрмө жазба.
- Бардык сандар, пайыздар, валюта белгилери, тикерлер ($, %, BTC/USDT, S&P 500) жана ысымдар түп нускадагыдай калсын.
- Кыргызча — адабий, туура орфография (ң, ө, ү). Терминдер: «акция», «биржа», «пайыздык чен», «инфляция», «криптовалюта».
- Орусча (түп нуска англисче болсо) — грамматикалык катасыз, кыска жаңылык стилинде."""

SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "string"}, "ky": {"type": "string"}, "ru": {"type": "string"},
                               "desc_ky": {"type": "string"}, "desc_ru": {"type": "string"}},
                "required": ["id", "ky", "ru", "desc_ky", "desc_ru"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}

NUMS = re.compile(r"\d+(?:[.,]\d+)?")


def nums(s):
    return sorted(n.replace(",", ".") for n in NUMS.findall(s or "") if not re.fullmatch(r"20\d\d", n))


def same_numbers(src, dst):
    """Котормодо түп нускадагы сандардын баары болушу керек (ашык сан да болбосун)."""
    a, b = nums(src), nums(dst)
    return a == b


def translate(batch):
    import anthropic  # котормо жок режимде SDK керек эмес

    client = anthropic.Anthropic()
    rows = [{"id": x["id"], "lang": x["lang"], "title": x["orig"], "desc": x.get("desc") or ""} for x in batch]
    prompt = ("Ар бир жазуу үчүн: ky — аталыштын кыргызча котормосу; ru — орусча (lang=ru болсо — түп нуска өзгөрүүсүз); "
              "desc_ky/desc_ru — desc'тин котормосу (desc бош болсо — бош сап).\n\n" + json.dumps(rows, ensure_ascii=False))
    resp = client.beta.messages.create(
        model=MODEL,
        max_tokens=32000,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if resp.stop_reason in ("refusal", "max_tokens"):
        raise RuntimeError("котормо токтоду: %s" % resp.stop_reason)
    text = next(b.text for b in resp.content if b.type == "text")
    return {r["id"]: r for r in json.loads(text)["items"]}, resp


def apply_translations(all_items, old, do_translate, log):
    """Мурунку котормолорду колдонот; жаңыларын Claude менен которот (ачкыч болсо)."""
    cache = {}
    for sec in ("main", "opinions", "ta"):
        for x in old.get(sec, []):
            if x.get("ky"):
                cache[x["id"]] = x
    todo = []
    for x in all_items:
        c = cache.get(x["id"])
        if c and c.get("orig") == x["orig"]:
            for k in ("ky", "ru", "desc_ky", "desc_ru"):
                if c.get(k):
                    x[k] = c[k]
        if x["lang"] == "ru":
            x.setdefault("ru", x["orig"])
            if x.get("desc"):
                x.setdefault("desc_ru", x["desc"])
        if not x.get("ky"):
            todo.append(x)
    if not todo:
        return 0
    if not do_translate:
        log("Котормо: ачкыч жок же өчүрүлгөн — %d жаңылык түп нускасында калат." % len(todo))
        return 0
    return translate_into(todo, log)


def has_key():
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def translate_into(todo, log=print):
    """Claude менен которуп, x[ky/ru/desc_*] талааларын толтурат (сандар текшерилет). Которулгандардын саны."""
    for x in todo:
        if x.get("lang") == "ru":
            x.setdefault("ru", x["orig"])
    done = 0
    for i in range(0, len(todo), 40):
        batch = todo[i:i + 40]
        try:
            res, resp = translate(batch)
        except Exception as e:  # noqa: BLE001
            log("Котормо катасы: %s" % e)
            break
        for x in batch:
            r = res.get(x["id"])
            if not r:
                continue
            ok_ky = same_numbers(x["orig"], r["ky"])
            ok_ru = x["lang"] == "ru" or same_numbers(x["orig"], r["ru"])
            if not (ok_ky and ok_ru):
                log("  сандар дал келбейт, котормо алынбайт: %s" % x["orig"][:70])
                continue
            x["ky"] = r["ky"].strip()
            if x["lang"] != "ru":
                x["ru"] = r["ru"].strip()
            if x.get("desc") and r.get("desc_ky") and same_numbers(x["desc"], r["desc_ky"]):
                x["desc_ky"] = r["desc_ky"].strip()
                if x["lang"] != "ru" and r.get("desc_ru"):
                    x["desc_ru"] = r["desc_ru"].strip()
            done += 1
        log("Котормо: %d/%d (tokens in/out %d/%d)" % (done, len(todo), resp.usage.input_tokens, resp.usage.output_tokens))
    return done


def snapshot(errors):
    """Азыркы абал (котормосуз): {main, opinions, ta} — дубликаттар бириктирилген, тема/маанилүүлүк менен.
    Бот (tools/tg_news.py) ар 10 мүнөттө ушуну окуйт; build() да ушуну колдонот."""
    main, ops, ta = collect(errors)
    main = [enrich(x) for x in balance(dedupe(main), LIMITS["main"], 18)]
    ops = [enrich(x) for x in balance(dedupe(ops), LIMITS["opinions"] * 2, 8)]
    ta = [enrich(x) for x in balance(sorted(ta, key=lambda x: -x["t"]), LIMITS["ta"], 16)]
    return {"main": main, "opinions": ops, "ta": ta}


def member_ids(x):
    """Окуянын бардык нускаларынын id'лери (бириктирилген булактар менен)."""
    return [x["id"]] + [iid(a["url"]) for a in x.get("also") or []]


def build(do_translate=True, log=print):
    errors = []
    snap = snapshot(errors)
    main, ops, ta = snap["main"], snap["opinions"], snap["ta"]
    for e in errors:
        log("! булак: %s" % e)
    try:
        with open(OUT, encoding="utf-8") as f:
            old = json.load(f)
    except (OSError, ValueError):
        old = {}
    apply_translations(main + ops + ta, old, do_translate, log)
    # Англисче пикирлер — орусча котормосу болсо гана (түшүнүксүз тилде көрсөтпөйбүз)
    ops = [x for x in ops if x["lang"] == "ru" or x.get("ru")][:LIMITS["opinions"]]
    for x in main + ops + ta:
        x.pop("sid", None)
        x.pop("lang", None) if x.get("ru") else None
    return {
        "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sources": [{"name": f["name"], "url": f["url"]} for f in FEEDS],
        "errors": errors,
        "main": main, "opinions": ops, "ta": ta,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-translate", action="store_true")
    args = ap.parse_args()
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
    data = build(do_translate=has_key and not args.no_translate)
    ky = sum(1 for s in ("main", "opinions", "ta") for x in data[s] if x.get("ky"))
    tot = sum(len(data[s]) for s in ("main", "opinions", "ta"))
    print("Башкы: %d · пикирлер: %d · теханализ: %d · кыргызча котормосу бар: %d/%d" % (len(data["main"]), len(data["opinions"]), len(data["ta"]), ky, tot))
    if args.dry_run:
        for s in ("main", "opinions", "ta"):
            print("==", s)
            for x in data[s][:8]:
                print("  [%s|%s] %s%s" % (x["src"], x.get("cat"), x.get("who_ru", "") and x["who_ru"] + ": ", x["orig"][:100]))
        return 0
    if not data["main"] and not data["ta"]:
        print("Бир да жаңылык алынган жок — эски файл калат.")
        return 1
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, OUT)
    print("Сакталды:", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
