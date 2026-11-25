"""Экономикалык календарь (дүйнөлүк анонстор) → site/assets/data/calendar.json, кыргызча жана орусча.

Булак: Forex Factory'нин расмий жумалык экспорту (https://www.forexfactory.com/calendar → Export):
  https://nfs.faireconomy.media/ff_calendar_thisweek.json — ушул жуманын окуялары: убакыт, валюта, маанилүүлүгү,
  болжол (forecast) жана мурунку маани (previous). Чыныгы чыккан маани (actual) экспортто жок — аны TradingView'дон текшериңиз.
Аталыштар сөздүк менен которулат (CPI, NFP, ставкалар, PMI…). Сөздүктө жок аталыш — ANTHROPIC_API_KEY болсо Claude
менен (кэште сакталат), болбосо англисче калат («EN» белгиси менен).

Иштетүү: python tools/econ_calendar.py [--dry-run] [--no-translate]
Тиркеме: GitHub Actions (daily-update.yml, ар 2 саатта) жана Telegram-бот (tools/tg_news.py — эртең мененки тизме, эскертүүлөр).
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "site", "assets", "data", "calendar.json")
SRC = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
SRC_PAGE = "https://www.forexfactory.com/calendar"
VERIFY = "https://ru.tradingview.com/economic-calendar/"
UA = "Mozilla/5.0 (compatible; AITRADING.KG calendar; +https://aitrading-kg.pages.dev)"
IMPACT = {"High": 3, "Medium": 2, "Low": 1, "Holiday": 0, "Non-Economic": 0}

# валюта → (орусча, кыргызча, желек)
CUR = {
    "USD": ("США", "АКШ", "🇺🇸"), "EUR": ("Еврозона", "Евроаймак", "🇪🇺"), "GBP": ("Великобритания", "Улуу Британия", "🇬🇧"),
    "JPY": ("Япония", "Япония", "🇯🇵"), "CNY": ("Китай", "Кытай", "🇨🇳"), "CHF": ("Швейцария", "Швейцария", "🇨🇭"),
    "CAD": ("Канада", "Канада", "🇨🇦"), "AUD": ("Австралия", "Австралия", "🇦🇺"), "NZD": ("Новая Зеландия", "Жаңы Зеландия", "🇳🇿"),
    "All": ("Весь мир", "Бүт дүйнө", "🌐"),
}

# ---------- Котормо сөздүгү ----------
REGION = {"German": ("Германия", "Германия"), "French": ("Франция", "Франция"), "Italian": ("Италия", "Италия"),
          "Spanish": ("Испания", "Испания"), "Tokyo": ("Токио", "Токио"), "Belgian": ("Бельгия", "Бельгия"),
          "Chinese": ("Китай", "Кытай"), "Swiss": ("Швейцария", "Швейцария")}
INST = {"BOE": ("Банк Англии", "Англия банкы"), "ECB": ("ЕЦБ", "ЕЦБ"), "BOJ": ("Банк Японии", "Япония банкы"),
        "RBA": ("РБА", "Австралия РБ"), "BOC": ("Банк Канады", "Канада банкы"), "SNB": ("ШНБ", "Швейцария УБ"),
        "RBNZ": ("РБНЗ", "Жаңы Зеландия РБ"), "Fed": ("ФРС", "ФРС"), "FOMC": ("FOMC", "FOMC")}
PERIOD = {"m/m": ("м/м", "айлык"), "y/y": ("г/г", "жылдык"), "q/q": ("кв/кв", "кварталдык"), "3m/y": ("3м/г", "3 ай/жыл")}
STAGE = {"Flash": ("предв.", "алдын ала"), "Prelim": ("предв.", "алдын ала"), "Final": ("оконч.", "акыркы"),
         "Advance": ("первая оценка", "биринчи баа"), "Revised": ("пересмотр", "кайра каралган")}
BASE = {
    "CPI": ("Индекс потребительских цен (CPI)", "Керектөө баа индекси (CPI)"),
    "Core CPI": ("Базовый индекс потребительских цен", "Негизги керектөө баа индекси"),
    "Trimmed Mean CPI": ("Усечённый средний CPI", "Кыркылган орточо CPI"),
    "Median CPI": ("Медианный CPI", "Медианалык CPI"),
    "HICP": ("Гармонизированный индекс цен (HICP)", "Шайкештирилген баа индекси (HICP)"),
    "PPI": ("Индекс цен производителей (PPI)", "Өндүрүүчүлөрдүн баа индекси (PPI)"),
    "Core PPI": ("Базовый индекс цен производителей", "Негизги өндүрүүчүлөр баа индекси"),
    "PCE Price Index": ("Ценовой индекс PCE", "PCE баа индекси"),
    "Core PCE Price Index": ("Базовый ценовой индекс PCE", "Негизги PCE баа индекси"),
    "GDP": ("ВВП", "Ички дүң продукт (ИДП)"),
    "GDP Price Index": ("Ценовой индекс ВВП", "ИДПнын баа индекси"),
    "Retail Sales": ("Розничные продажи", "Чекене соода"),
    "Core Retail Sales": ("Базовые розничные продажи", "Негизги чекене соода"),
    "Non-Farm Employment Change": ("Занятость вне сельского хозяйства (NFP)", "Айыл чарбадан тышкаркы жумуш орундары (NFP)"),
    "ADP Non-Farm Employment Change": ("Занятость в частном секторе (ADP)", "Жеке сектордогу жумуш орундары (ADP)"),
    "ADP Weekly Employment Change": ("Недельная занятость (ADP)", "Жумалык жумуш орундары (ADP)"),
    "Unemployment Rate": ("Уровень безработицы", "Жумушсуздук деңгээли"),
    "Unemployment Claims": ("Заявки на пособие по безработице", "Жумушсуздук жөлөкпулуна арыздар"),
    "Unemployment Change": ("Изменение числа безработных", "Жумушсуздардын санынын өзгөрүшү"),
    "Claimant Count Change": ("Число получателей пособия", "Жөлөкпул алуучулардын санынын өзгөрүшү"),
    "Employment Change": ("Изменение занятости", "Жумуш орундарынын өзгөрүшү"),
    "Average Hourly Earnings": ("Средняя почасовая зарплата", "Орточо сааттык эмгек акы"),
    "Average Earnings Index": ("Индекс средней зарплаты", "Орточо эмгек акы индекси"),
    "JOLTS Job Openings": ("Вакансии JOLTS", "Бош жумуш орундары (JOLTS)"),
    "Federal Funds Rate": ("Решение ФРС по ставке", "ФРСтин пайыздык чени боюнча чечим"),
    "FOMC Statement": ("Заявление FOMC (ФРС)", "FOMC (ФРС) билдирүүсү"),
    "FOMC Press Conference": ("Пресс-конференция ФРС", "ФРСтин пресс-конференциясы"),
    "FOMC Meeting Minutes": ("Протокол заседания FOMC", "FOMC жыйынынын протоколу"),
    "FOMC Economic Projections": ("Экономические прогнозы FOMC", "FOMCтин экономикалык болжолдору"),
    "Beige Book": ("«Бежевая книга» ФРС", "ФРСтин «Бежевая книга» баяндамасы"),
    "Main Refinancing Rate": ("Решение ЕЦБ по ставке", "ЕЦБнын пайыздык чени боюнча чечим"),
    "Monetary Policy Statement": ("Заявление по денежно-кредитной политике", "Акча-кредит саясаты боюнча билдирүү"),
    "ECB Press Conference": ("Пресс-конференция ЕЦБ", "ЕЦБнын пресс-конференциясы"),
    "ECB Monetary Policy Meeting Accounts": ("Протокол заседания ЕЦБ", "ЕЦБ жыйынынын протоколу"),
    "Official Bank Rate": ("Решение Банка Англии по ставке", "Англия банкынын пайыздык чени боюнча чечим"),
    "MPC Official Bank Rate Votes": ("Голосование MPC по ставке", "MPCтин чен боюнча добуш берүүсү"),
    "BOJ Policy Rate": ("Решение Банка Японии по ставке", "Япония банкынын пайыздык чени боюнча чечим"),
    "Cash Rate": ("Решение РБА по ставке", "Австралия резерв банкынын чени боюнча чечим"),
    "Official Cash Rate": ("Решение РБНЗ по ставке", "Жаңы Зеландия резерв банкынын чени боюнча чечим"),
    "Overnight Rate": ("Решение Банка Канады по ставке", "Канада банкынын чени боюнча чечим"),
    "SNB Policy Rate": ("Решение ШНБ по ставке", "Швейцария улуттук банкынын чени боюнча чечим"),
    "Manufacturing PMI": ("Индекс деловой активности в промышленности (PMI)", "Өнөр жайдагы ишкердик активдүүлүк (PMI)"),
    "Services PMI": ("Индекс деловой активности в сфере услуг (PMI)", "Кызмат көрсөтүүдөгү ишкердик активдүүлүк (PMI)"),
    "Composite PMI": ("Композитный PMI", "Жалпы PMI"),
    "ISM Manufacturing PMI": ("ISM: деловая активность в промышленности", "ISM: өнөр жайдагы ишкердик активдүүлүк"),
    "ISM Services PMI": ("ISM: деловая активность в сфере услуг", "ISM: кызмат көрсөтүүдөгү ишкердик активдүүлүк"),
    "Caixin Manufacturing PMI": ("Caixin: PMI в промышленности", "Caixin: өнөр жай PMI"),
    "Caixin Services PMI": ("Caixin: PMI в сфере услуг", "Caixin: кызмат көрсөтүү PMI"),
    "Crude Oil Inventories": ("Запасы нефти (EIA)", "Нефть запастары (EIA)"),
    "Natural Gas Storage": ("Запасы природного газа", "Жаратылыш газынын запастары"),
    "API Weekly Statistical Bulletin": ("Запасы нефти по данным API", "API маалыматы боюнча нефть запастары"),
    "CB Consumer Confidence": ("Доверие потребителей (Conference Board)", "Керектөөчүлөрдүн ишеними (Conference Board)"),
    "Consumer Confidence": ("Доверие потребителей", "Керектөөчүлөрдүн ишеними"),
    "UoM Consumer Sentiment": ("Настроения потребителей (Мичиган)", "Керектөөчүлөрдүн маанайы (Мичиган)"),
    "UoM Inflation Expectations": ("Инфляционные ожидания (Мичиган)", "Инфляциялык күтүүлөр (Мичиган)"),
    "Building Permits": ("Разрешения на строительство", "Курулушка уруксаттар"),
    "Housing Starts": ("Начало строительства жилья", "Турак жай курулушунун башталышы"),
    "New Home Sales": ("Продажи новых домов", "Жаңы үйлөрдүн сатылышы"),
    "Existing Home Sales": ("Продажи вторичного жилья", "Экинчилик турак жайдын сатылышы"),
    "Pending Home Sales": ("Незавершённые сделки с жильём", "Аяктай элек турак жай келишимдери"),
    "Durable Goods Orders": ("Заказы на товары длительного пользования", "Узак колдонулуучу товарларга буйрутмалар"),
    "Core Durable Goods Orders": ("Базовые заказы на товары длительного пользования", "Негизги узак колдонулуучу товарларга буйрутмалар"),
    "Industrial Production": ("Промышленное производство", "Өнөр жай өндүрүшү"),
    "Personal Income": ("Личные доходы", "Жеке кирешелер"),
    "Personal Spending": ("Личные расходы", "Жеке чыгашалар"),
    "Trade Balance": ("Торговый баланс", "Соода балансы"),
    "Goods Trade Balance": ("Торговый баланс по товарам", "Товарлар боюнча соода балансы"),
    "Current Account": ("Счёт текущих операций", "Учурдагы операциялар эсеби"),
    "Bank Holiday": ("Выходной: банки закрыты", "Дем алыш: банктар иштебейт"),
    "Corporate Profits": ("Прибыль корпораций", "Корпорациялардын пайдасы"),
    "HPI": ("Индекс цен на жильё", "Турак жай баа индекси"),
    "S&P/CS Composite-20 HPI": ("Индекс цен на жильё Case-Shiller", "Case-Shiller турак жай баа индекси"),
    "Richmond Manufacturing Index": ("Промышленный индекс ФРБ Ричмонда", "Ричмонд ФРБнын өнөр жай индекси"),
    "Philly Fed Manufacturing Index": ("Промышленный индекс ФРБ Филадельфии", "Филадельфия ФРБнын өнөр жай индекси"),
    "Empire State Manufacturing Index": ("Промышленный индекс Нью-Йорка", "Нью-Йорктун өнөр жай индекси"),
    "Chicago PMI": ("PMI Чикаго", "Чикаго PMI"),
    "ifo Business Climate": ("Деловой климат Ifo", "Ifo бизнес-климаты"),
    "GfK Consumer Climate": ("Потребительский климат GfK", "GfK керектөө климаты"),
    "ZEW Economic Sentiment": ("Экономические настроения ZEW", "ZEW экономикалык маанайы"),
    "Wholesale Inventories": ("Оптовые запасы", "Дүң соода запастары"),
    "Private Capital Expenditure": ("Частные капиталовложения", "Жеке капиталдык салымдар"),
    "Private Loans": ("Кредиты частному сектору", "Жеке секторго кредиттер"),
    "M3 Money Supply": ("Денежная масса M3", "M3 акча массасы"),
    "Construction Work Done": ("Объём строительных работ", "Курулуш иштеринин көлөмү"),
    "Consumer Spending": ("Потребительские расходы", "Керектөө чыгашалары"),
    "Private Payrolls": ("Занятость в частном секторе", "Жеке сектордогу жумуш орундары"),
    "10-y Bond Auction": ("Аукцион 10-летних облигаций", "10 жылдык облигациялар аукциону"),
    "30-y Bond Auction": ("Аукцион 30-летних облигаций", "30 жылдык облигациялар аукциону"),
    "Financial Stability Report": ("Доклад о финансовой стабильности", "Каржылык туруктуулук боюнча баяндама"),
    "FPC Meeting Minutes": ("Протокол Комитета по финстабильности (FPC)", "Каржылык туруктуулук комитетинин (FPC) протоколу"),
    "FPC Statement": ("Заявление Комитета по финстабильности (FPC)", "Каржылык туруктуулук комитетинин (FPC) билдирүүсү"),
    "Bulletin": ("Бюллетень", "Бюллетень"),
    "UBS Economic Expectations": ("Экономические ожидания UBS", "UBS экономикалык күтүүлөрү"),
    "NBB Business Climate": ("Деловой климат NBB", "NBB бизнес-климаты"),
    "CBI Realized Sales": ("Фактические продажи (CBI)", "Иш жүзүндөгү сатуулар (CBI)"),
    "SPPI": ("Индекс цен на услуги для бизнеса (SPPI)", "Бизнес кызматтарынын баа индекси (SPPI)"),
    "CB Leading Index": ("Индекс опережающих индикаторов (CB)", "Алдыңкы көрсөткүчтөр индекси (CB)"),
    "Industrial Profits": ("Прибыль промышленных предприятий", "Өнөр жай ишканаларынын пайдасы"),
    "Retail Sales Monitor": ("Мониторинг розничных продаж", "Чекене сооданын мониторинги"),
    "Labor Cost Index": ("Индекс стоимости труда", "Эмгек наркынын индекси"),
    "Wage Price Index": ("Индекс заработной платы", "Эмгек акы индекси"),
    "Employment Cost Index": ("Индекс стоимости занятости", "Жумуш күчүнүн нарк индекси"),
    "Prelim Nonfarm Productivity": ("Производительность труда (предв.)", "Эмгек өндүрүмдүүлүгү (алдын ала)"),
    "Unit Labor Costs": ("Удельные затраты на труд", "Бирдик эмгек чыгымдары"),
    "Treasury Currency Report": ("Валютный доклад Минфина США", "АКШ Каржы министрлигинин валюта баяндамасы"),
}
ROLE = [  # «X Speaks»: кызматы
    ("Fed Chair", "глава ФРС", "ФРСтин башчысы"), ("FOMC Member", "член FOMC", "FOMC мүчөсү"),
    ("ECB President", "президент ЕЦБ", "ЕЦБнын президенти"), ("ECB Vice President", "вице-президент ЕЦБ", "ЕЦБнын вице-президенти"),
    ("ECB Chief Economist", "главный экономист ЕЦБ", "ЕЦБнын башкы экономисти"), ("ECB Member", "член ЕЦБ", "ЕЦБ мүчөсү"),
    ("BOE Gov", "глава Банка Англии", "Англия банкынын башчысы"), ("MPC Member", "член MPC Банка Англии", "Англия банкынын MPC мүчөсү"),
    ("BOJ Gov", "глава Банка Японии", "Япония банкынын башчысы"), ("BOC Gov", "глава Банка Канады", "Канада банкынын башчысы"),
    ("RBA Gov", "глава РБА", "Австралия РБнын башчысы"), ("RBNZ Gov", "глава РБНЗ", "Жаңы Зеландия РБнын башчысы"),
    ("SNB Chairman", "глава ШНБ", "Швейцария УБнын башчысы"), ("Buba President", "президент Бундесбанка", "Бундесбанктын президенти"),
    ("Treasury Secretary", "министр финансов США", "АКШнын каржы министри"), ("President", "президент", "президент"),
]
NAMES = {"Powell": "Пауэлл", "Lagarde": "Лагард", "Bailey": "Бейли", "Ueda": "Уэда", "Macklem": "Маклем", "Bullock": "Буллок",
         "Nagel": "Нагель", "Williams": "Уильямс", "Bowman": "Боуман", "Waller": "Уоллер", "Jefferson": "Джефферсон", "Cook": "Кук",
         "Barr": "Барр", "Goolsbee": "Гулсби", "Daly": "Дейли", "Logan": "Логан", "Hammack": "Хаммак", "Musalem": "Мусалем",
         "Kashkari": "Кашкари", "Bostic": "Бостик", "Schmid": "Шмид", "Collins": "Коллинз", "Barkin": "Баркин", "Greene": "Грин",
         "Pill": "Пилл", "Mann": "Манн", "Dhingra": "Дингра", "Lombardelli": "Ломбарделли", "Breeden": "Бриден", "Ramsden": "Рамсден",
         "Taylor": "Тейлор", "Schnabel": "Шнабель", "Lane": "Лейн", "de Guindos": "де Гиндос", "Bessent": "Бессент", "Trump": "Трамп",
         "Miran": "Миран", "Hauser": "Хаузер", "Hawkesby": "Хоксби", "Schlegel": "Шлегель", "Himino": "Химино", "Uchida": "Утида",
         "Rogers": "Роджерс", "Breman": "Бреман", "Hunter": "Хантер", "Jones": "Джонс", "Paulson": "Полсон", "Kugler": "Куглер"}


def _speech(who):
    for en, ru, ky in ROLE:
        m = re.match(r"^(?:German |French |Italian )?%s\s+(.+)$" % re.escape(en), who)
        if m:
            nm = NAMES.get(m.group(1), m.group(1))
            return "Выступление: %s %s" % (ru, nm), "%s %s сөз сүйлөйт" % (ky, nm)
    return None


def translate_title(en):
    """(ru, ky) же None (сөздүктө жок)."""
    s = en.strip()
    m = re.match(r"^(.+?)\s+Speaks$", s)
    if m:
        return _speech(m.group(1))
    period = None
    m = re.search(r"\s+(m/m|y/y|q/q|3m/y)$", s)
    if m:
        period, s = m.group(1), s[:m.start()]
    region = None
    for k in REGION:
        if s.startswith(k + " "):
            region, s = k, s[len(k) + 1:]
            break
    stage = None
    for k in STAGE:
        if s.startswith(k + " "):
            stage, s = k, s[len(k) + 1:]
            break
    inst = None
    if s not in BASE:
        for k in INST:
            if s.startswith(k + " ") and s[len(k) + 1:] in BASE:
                inst, s = k, s[len(k) + 1:]
                break
    if s not in BASE:
        return None
    ru, ky = BASE[s]
    if inst:
        ru, ky = "%s: %s" % (INST[inst][0], ru), "%s: %s" % (INST[inst][1], ky)
    if region:
        ru, ky = "%s: %s" % (REGION[region][0], ru), "%s: %s" % (REGION[region][1], ky)
    extra_ru = [x for x in (STAGE[stage][0] if stage else None, PERIOD[period][0] if period else None) if x]
    extra_ky = [x for x in (STAGE[stage][1] if stage else None, PERIOD[period][1] if period else None) if x]
    if extra_ru:
        ru, ky = _paren(ru, extra_ru), _paren(ky, extra_ky)
    return ru, ky


def _paren(s, extra):
    """«CPI (CPI)» + [м/м] → «… (CPI, м/м)»: кашаалар эки жолу кайталанбасын."""
    if s.endswith(")"):
        return s[:-1] + ", " + ", ".join(extra) + ")"
    return s + " (" + ", ".join(extra) + ")"


# ---------- Claude: сөздүктө жок аталыштар ----------
SYSTEM = ("Сен экономикалык календардын окуяларынын аталыштарын которосуң (Forex Factory). Кыска, расмий стилде. "
          "Аббревиатуралар (CPI, PMI, GDP→ВВП/ИДП, FOMC, ECB→ЕЦБ) жана ысымдар туура болсун. Кыргызча — адабий, ң ө ү менен. "
          "Эч нерсе кошпо, түшүндүрмө жазба.")
SCHEMA = {"type": "object", "properties": {"items": {"type": "array", "items": {
    "type": "object", "properties": {"en": {"type": "string"}, "ru": {"type": "string"}, "ky": {"type": "string"}},
    "required": ["en", "ru", "ky"], "additionalProperties": False}}}, "required": ["items"], "additionalProperties": False}


def translate_ai(titles):
    import anthropic

    client = anthropic.Anthropic()
    resp = client.beta.messages.create(
        model="claude-opus-5-5", max_tokens=8000, system=SYSTEM,
        messages=[{"role": "user", "content": "Ар бир аталышты орусча (ru) жана кыргызча (ky) котор:\n" + json.dumps(titles, ensure_ascii=False)}],
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",
    )
    if resp.stop_reason in ("refusal", "max_tokens"):
        raise RuntimeError(resp.stop_reason)
    text = next(b.text for b in resp.content if b.type == "text")
    return {r["en"]: (r["ru"].strip(), r["ky"].strip()) for r in json.loads(text)["items"] if r.get("ru") and r.get("ky")}


# ---------- Жыйноо ----------
def fetch():
    req = urllib.request.Request(SRC, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))


def eid(t, cur, en):
    return hashlib.sha1(("%d|%s|%s" % (t, cur, en)).encode("utf-8")).hexdigest()[:10]


def build(do_translate=True, log=print, raw=None):
    raw = raw if raw is not None else fetch()
    try:
        with open(OUT, encoding="utf-8") as f:
            old = json.load(f)
    except (OSError, ValueError):
        old = {}
    cache = dict(old.get("ai") or {})               # {en: [ru, ky]} — Claude которгондор
    events, unknown = [], set()
    for x in raw:
        en = (x.get("title") or "").strip()
        try:
            t = int(dt.datetime.fromisoformat(x["date"]).timestamp() * 1000)
        except (KeyError, ValueError, TypeError):
            continue
        if not en:
            continue
        cur = (x.get("country") or "").strip()
        imp = IMPACT.get(x.get("impact"), 1)
        tr = translate_title(en)
        if not tr and en in cache:
            tr = tuple(cache[en])
        if not tr:
            unknown.add(en)
        events.append({"id": eid(t, cur, en), "t": t, "cur": cur, "imp": imp, "en": en,
                       "ru": tr[0] if tr else "", "ky": tr[1] if tr else "",
                       "fc": (x.get("forecast") or "").strip(), "pv": (x.get("previous") or "").strip()})
    if unknown and do_translate:
        try:
            got = translate_ai(sorted(unknown))
            for e in events:
                if not e["ky"] and e["en"] in got:
                    e["ru"], e["ky"] = got[e["en"]]
            cache.update({k: list(v) for k, v in got.items()})
            log("Claude: %d/%d аталыш которулду" % (len(got), len(unknown)))
        except Exception as e:  # noqa: BLE001
            log("! Claude котормосу: %s" % e)
    left = sorted({e["en"] for e in events if not e["ky"]})
    if left:
        log("Сөздүктө жок (англисче калат): %s" % "; ".join(left))
    events.sort(key=lambda e: (e["t"], -e["imp"], e["cur"]))
    return {"updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "source": "Forex Factory", "source_url": SRC_PAGE,
            "verify": VERIFY, "tz_note": "t — UTC, миллисекунд", "events": events, "ai": cache}


def bishkek(t):
    return dt.datetime.fromtimestamp(t / 1000, dt.timezone(dt.timedelta(hours=6)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-translate", action="store_true")
    a = ap.parse_args()
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
    try:
        data = build(do_translate=has_key and not a.no_translate)
    except Exception as e:  # noqa: BLE001
        print("Календарь алынган жок: %s — эски файл калат." % e)
        return 1
    ev = data["events"]
    print("Окуялар: %d (маанилүү: %d) · котормосу бар: %d" % (len(ev), sum(1 for e in ev if e["imp"] == 3), sum(1 for e in ev if e["ky"])))
    if a.dry_run:
        for e in ev:
            if e["imp"] >= 2:
                print(" ", bishkek(e["t"]).strftime("%a %d.%m %H:%M"), e["cur"], "★" * e["imp"], "|", e["ky"] or e["en"], "|", e["ru"] or "-", "|", e["fc"], e["pv"])
        return 0
    if not ev:
        print("Бош — эски файл калат.")
        return 1
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, OUT)
    print("Сакталды:", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
