"""Telegram-бот: «⭐ Азыр эң мыкты» сигналдары телефонго / сигналы «⭐ Лучшее сейчас» в Telegram.

    python tools/tg_signals.py --dry-run           # скан + даяр билдирүүлөр экранга, эч нерсе жөнөтүлбөйт
    python tools/tg_signals.py --dry-run --loop    # ошол эле, ар мүнөт (✓/✗ жыйынтыгы да көрүнөт)
    python tools/tg_signals.py                     # бир жолу: скан → Telegram (cron / планировщик үчүн)
    python tools/tg_signals.py --loop              # ПКда токтобой иштейт (Телеграм_бот.bat)
    python tools/tg_signals.py --chat-id           # ботко /start жазгандан кийин chat_id'ни көрсөтөт
    python tools/tg_signals.py --test              # Telegram'га текшерүү билдирүүсү
    python tools/tg_signals.py --compare-js        # Python модели = сайттын JS модели (Node.js керек)

Логика сайттагыдай: ai-analyst.js → scan(), rank(), judge(); ai-engine.js → features(), model(), liveFX().
Сигнал — ыктымалдык. Жөнөтүлөт: тесттеги тактык «жөнөкөй болжолдон» 1 п.п.дан жогору ЖАНА p ≥ 55% (▲) же ≤ 45% (▼).
Антиспам сайттагыдай: 3 мүнөттө 1 билдирмеден көп эмес, ошол эле сигнал — 15 мүнөттөн кийин гана.

Токен жана чат — чөйрө өзгөрмөлөрүнөн гана (же GitHub Secrets): TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID.
Кошумча (милдеттүү эмес): TG_EXP=1,5  TG_MARKETS=binodex,bingx  TG_LANG=kg|ru  TG_STATE=<файл>  SITE_URL=https://aitrading.kg
"""
import argparse
import html
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

try:
    if os.environ.get("TG_NO_NUMPY"):
        raise ImportError
    import numpy as np                       # тездетүү үчүн гана; жок болсо — таза Python (жыйынтык ошол эле)
except ImportError:
    np = None

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "site", "assets", "data")
ENGINE_JS = os.path.join(ROOT, "site", "assets", "js", "ai-engine.js")
SITE_URL = (os.environ.get("SITE_URL") or "https://aitrading.kg").rstrip("/")
BISHKEK = timezone(timedelta(hours=6))
UA = "Mozilla/5.0 (aitrading signals bot)"

# ---- Булактар: ai-engine.js менен бирдей ----
BINANCE = ["https://api.binance.com/api/v3/klines", "https://data-api.binance.vision/api/v3/klines"]
KRAKEN = {"EURUSD": "EURUSD", "GBPUSD": "GBPUSD", "USDCAD": "USDCAD", "AUDUSD": "AUDUSD", "USDCHF": "USDCHF", "EURGBP": "EURGBP", "EURCHF": "EURCHF"}
BN_FX = {"EURUSD": "EURUSDT", "XAUUSD": "PAXGUSDT"}
BN_IV = {1: "1m", 5: "5m", 15: "15m", 60: "1h"}
FX_DEFAULT = [("EURUSD", "EUR/USD"), ("GBPUSD", "GBP/USD"), ("AUDUSD", "AUD/USD"), ("USDCAD", "USD/CAD"), ("USDCHF", "USD/CHF"),
              ("EURGBP", "EUR/GBP"), ("EURCHF", "EUR/CHF"), ("XAUUSD", "XAU/USD")]   # bingx.json жок болсо гана
# ai-analyst.js → POP
POP = ["BTC", "ETH", "SOL", "XRP", "BNB", "DOGE", "TON", "ADA", "AVAX", "LINK", "SUI", "NEAR", "TAO", "FET", "PEPE", "PAXG"]

ANTISPAM_ANY = 3 * 60000      # 3 мүнөттө 1 билдирмеден көп эмес
ANTISPAM_SAME = 8 * 60000     # ошол эле сунуш (жуп+багыт) — 8 мүнөттө 1 жолу (5 мүн сигнал жабылгандан кийин)
LOSS_STREAK = int(os.environ.get("TG_LOSS_STREAK", "3"))   # ушунча минус катары менен болсо — тыныгуу
COOL_MS = int(os.environ.get("TG_COOL_MIN", "3")) * 60000
SESSIONS = os.environ.get("TG_SESSIONS", "08:00-11:00,19:00-close")   # BinoDex соода сессиялары (Бишкек); close — рынок жабылганда; бош — күнү-түнү

T = {
    "kg": {
        "best_fx": "Азыр эң мыкты сигнал · {m} мүн",
        "best_bx": "Азыр сатып алууга эң мыкты",
        "up": "ӨЙДӨ", "dn": "ЫЛДЫЙ",
        "acc": "тест {a} / жөнөкөй {b}",
        "fx_line": "BinoDex · экспирация {m} мүнөт",
        "bx_line": "BingX спот · 1 саатка болжол",
        "entry": "Кирүү баасы", "price": "Баа",
        "quote": "котировка: {p}, {iv} мүн шамдар",
        "quote_bx": "маалымат: {p}, 1 саат шамдар",
        "honest": "Ыктымалдык — кепилдик эмес.",
        "risk_fx": "18+ · Кыска мөөнөттүү соода — эң тобокелдүү. Адегенде демо-эсепте текшериңиз.",
        "dg_head": "🔁 ПЕРЕКРЫТИЕ (догон) · 2-кирүү",
        "dg_note": "Мурунку сигнал минус болду. Ушул эле багытта экинчи кирүү — сумма 2 эседен ашпасын. Догон тобокелди көбөйтөт: жоготууга даяр болбосоңуз, кирбеңиз.",
        "dg_res": "перекрытие",
        "ta_w": "Тех. анализ", "ta_names": {"trend": "тренд", "rsi": "RSI", "macd": "MACD", "levels": "деңгээлдер"},
        "ss_open": "СООДА СЕССИЯСЫ №{n} БАШТАЛДЫ", "ss_close": "СООДА СЕССИЯСЫНЫН ЖЫЙЫНТЫГЫ №{n}",
        "ss_l1": "BinoDex сигналдары: {exp} мүн, тех. анализ ырастаганда гана", "ss_l2": "Минустан кийин — 2–3 мүн перекрытие; 3 минус катары болсо — 3 мүн тыныгуу",
        "ss_l3": "Сигнал боюнча гана кириңиз, сумма — депозиттин 1–2%",
        "ss_none": "Бул сессияда сигнал болгон жок: рынок модельдин эрежесине туура келген жок.",
        "ss_sum": "Плюс: {w} · Минус: {l} · Нөл: {t}", "ss_acc": "Сессиянын тактыгы: {pc}% ({n} сигнал)",
        "ss_next": "Кийинки сессия: {t} (Бишкек)",
        "risk_bx": "18+ · Соода тобокелдиктүү · Киреше кепилденбейт",
        "min": "мүнөт", "h1": "1 саат",
        "win": "сигнал туура чыкты", "loss": "сигнал туура эмес чыкты", "tie": "баа өзгөргөн жок",
        "nodata": "экспирациядагы баа табылган жок — эсепке кирбейт",
        "stats": "Боттун статистикасы (акыркы {n}): ✓{w} ✗{l} ({pc}%)",
        "stats_few": "Боттун статистикасы: ✓{w} ✗{l} (азырынча аз, пайыз 10 сигналдан кийин)",
        "test": "✅ AITRADING.KG боту туташты. ⭐ сигналдар ушул чатка келет.\nЫктымалдык — кепилдик эмес. 18+",
        "gold": "Алтын (PAXG)",
        "sig_h_fx": "СИГНАЛ · BinoDex · {m} мүн", "sig_h_bx": "СИГНАЛ · BingX спот · 1 саат",
        "dir_w": "Багыт", "prob_w": "ыктымалдык", "time_w": "Убакыт", "model_w": "Модель", "open": "Графикти сайттан ачуу",
        "r_win": "ПЛЮС", "r_loss": "МИНУС", "r_tie": "НӨЛ", "r_nodata": "ЭСЕПКЕ КИРБЕЙТ",
    },
    "ru": {
        "best_fx": "Лучший сигнал сейчас · {m} мин",
        "best_bx": "Лучшее для покупки сейчас",
        "up": "ВВЕРХ", "dn": "ВНИЗ",
        "acc": "тест {a} / угадывание {b}",
        "fx_line": "BinoDex · экспирация {m} мин",
        "bx_line": "BingX спот · прогноз на 1 час",
        "entry": "Цена входа", "price": "Цена",
        "quote": "котировки: {p}, свечи {iv} мин",
        "quote_bx": "данные: {p}, свечи 1 час",
        "honest": "Это вероятность, а не гарантия.",
        "risk_fx": "18+ · Краткосрочная торговля — самая рискованная. Сначала проверьте на демо-счёте.",
        "dg_head": "🔁 ПЕРЕКРЫТИЕ (догон) · вход №2",
        "dg_note": "Прошлый сигнал ушёл в минус. Второй вход в ту же сторону — сумма не больше 2× от первой. Догон увеличивает риск: не входите, если не готовы потерять эту сумму.",
        "dg_res": "перекрытие",
        "ta_w": "Тех. анализ", "ta_names": {"trend": "тренд", "rsi": "RSI", "macd": "MACD", "levels": "уровни"},
        "ss_open": "ТОРГОВАЯ СЕССИЯ №{n} НАЧАЛАСЬ", "ss_close": "ИТОГ ТОРГОВОЙ СЕССИИ №{n}",
        "ss_l1": "Сигналы BinoDex: {exp} мин, только с подтверждением тех. анализа", "ss_l2": "После минуса — перекрытие на 2–3 мин; после 3 минусов подряд — пауза 3 мин",
        "ss_l3": "Входите только по сигналу, сумма — 1–2% депозита",
        "ss_none": "В этой сессии сигналов не было: рынок не дал условий по правилам модели.",
        "ss_sum": "Плюс: {w} · Минус: {l} · Ноль: {t}", "ss_acc": "Точность сессии: {pc}% ({n} сигналов)",
        "ss_next": "Следующая сессия: {t} (Бишкек)",
        "risk_bx": "18+ · Торговля рискованна · Доход не гарантирован",
        "min": "мин", "h1": "1 час",
        "win": "сигнал сработал", "loss": "сигнал не сработал", "tie": "цена не изменилась",
        "nodata": "цену на момент экспирации получить не удалось — в статистику не входит",
        "stats": "Статистика бота (последние {n}): ✓{w} ✗{l} ({pc}%)",
        "stats_few": "Статистика бота: ✓{w} ✗{l} (пока мало, процент — после 10 сигналов)",
        "test": "✅ Бот AITRADING.KG подключён. Сигналы ⭐ будут приходить в этот чат.\nЭто вероятность, а не гарантия. 18+",
        "gold": "Золото (PAXG)",
        "sig_h_fx": "СИГНАЛ · BinoDex · {m} мин", "sig_h_bx": "СИГНАЛ · BingX спот · 1 час",
        "dir_w": "Направление", "prob_w": "вероятность", "time_w": "Время", "model_w": "Модель", "open": "Открыть график на сайте",
        "r_win": "ПЛЮС", "r_loss": "МИНУС", "r_tie": "НОЛЬ", "r_nodata": "НЕ В СТАТИСТИКЕ",
    },
}


class Fetch(Exception):
    pass


def now_ms():
    return int(time.time() * 1000)


def get_json(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


_last_call = {}


def pace(name, sec):
    """Kraken: секундасына ~1 суроо (сайттагыдай)."""
    w = _last_call.get(name, 0) + sec - time.time()
    if w > 0:
        time.sleep(w)
    _last_call[name] = time.time()


def num(x):
    try:
        return float(str(x).replace("%", ""))
    except (TypeError, ValueError):
        return 0.0


def jsround(x):
    """JavaScript Math.round (0.5 өйдө тегеректелет)."""
    return int(math.floor(x + 0.5))


def pct(x):
    return "%d%%" % jsround(x * 100)


# ======================================================================
#  ML: ai-engine.js'тин так көчүрмөсү (features, scaler, train, model)
# ======================================================================
def sma(a, n):
    out, s = [None] * len(a), 0.0
    for i, v in enumerate(a):
        s += v
        if i >= n:
            s -= a[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def rsi(c, n=14):
    out, g, l = [None] * len(c), 0.0, 0.0
    i = 1
    while i <= n and i < len(c):
        d = c[i] - c[i - 1]
        if d > 0:
            g += d
        else:
            l -= d
        i += 1
    g /= n
    l /= n
    if len(c) > n:
        out[n] = 100.0 if l == 0 else 100 - 100 / (1 + g / l)
    for t in range(n + 1, len(c)):
        dd = c[t] - c[t - 1]
        g = (g * (n - 1) + max(dd, 0)) / n
        l = (l * (n - 1) + max(-dd, 0)) / n
        out[t] = 100.0 if l == 0 else 100 - 100 / (1 + g / l)
    return out


def ema_list(a, n):
    out, k, e = [], 2.0 / (n + 1), None
    for v in a:
        e = v if e is None else v * k + e * (1 - k)
        out.append(e)
    return out


TA_MIN = int(os.environ.get("TG_TA_MIN", "0"))     # 0 — сайттагыдай (ИИ эң мыктысы); тех. анализ тартипти жана себептерди гана берет


def ta_check(cs, d):
    """Техникалык ырастоо (d: +1 өйдө / -1 ылдый). Кайтарат: (упай 0–4, себептер).
    1) Тренд: EMA20 vs EMA50 жана EMA20'нун жантаюусу. 2) RSI14: багытка ылайык зона, ашыкча эмес.
    3) MACD гистограммасы: белгиси жана өсүшү багытта. 4) Деңгээлдер: акыркы 30 шамдын диапазонунда баанын жайгашуусу —
       өйдө үчүн каршылыкка жабышпаган (≤0.65), ылдый үчүн колдоого жабышпаган (≥0.35)."""
    C = [c["close"] for c in cs]
    if len(C) < 60 or not d:
        return 0, []
    e20, e50 = ema_list(C, 20), ema_list(C, 50)
    why, sc = [], 0
    if (e20[-1] - e50[-1]) * d > 0 and (e20[-1] - e20[-4]) * d > 0:
        sc += 1
        why.append("trend")
    r = rsi(C, 14)
    rv, rp = r[-1], r[-3]
    if rv is not None and rp is not None and ((d > 0 and (40 <= rv <= 68 and rv > rp or rv < 32)) or (d < 0 and (32 <= rv <= 60 and rv < rp or rv > 68))):
        sc += 1
        why.append("rsi")
    m = [a - b for a, b in zip(ema_list(C, 12), ema_list(C, 26))]
    sig = ema_list(m, 9)
    h = [a - b for a, b in zip(m, sig)]
    if h[-1] * d > 0 and (h[-1] - h[-2]) * d > 0:
        sc += 1
        why.append("macd")
    hi = max(c["high"] for c in cs[-30:])
    lo = min(c["low"] for c in cs[-30:])
    pos = (C[-1] - lo) / (hi - lo) if hi > lo else 0.5
    if (d > 0 and pos <= 0.65) or (d < 0 and pos >= 0.35):
        sc += 1
        why.append("levels")
    return sc, why


def features(cs, h=1):
    C = [c["close"] for c in cs]
    V = [c["volume"] for c in cs]
    if any(not (x > 0) for x in C):
        return None
    R = [0.0] + [math.log(C[i] / C[i - 1]) for i in range(1, len(C))]
    RS, S20, S50, VA = rsi(C, 14), sma(C, 20), sma(C, 50), sma(V, 20)

    def f(t):
        m = 0.0
        for i in range(t - 19, t + 1):
            m += R[i]
        m /= 20
        q = 0.0
        for j in range(t - 19, t + 1):
            q += (R[j] - m) * (R[j] - m)
        return [R[t], math.log(C[t] / C[t - 3]), math.log(C[t] / C[t - 12]), (RS[t] - 50) / 50,
                C[t] / S20[t] - 1, C[t] / S50[t] - 1, math.sqrt(q / 19),
                math.log((V[t] + 1e-9) / ((VA[t] or 1) + 1e-9)), (cs[t]["high"] - cs[t]["low"]) / C[t]]

    X, Y = [], []
    # Баа өзгөрбөгөн учурлар (экспирацияда «кайтаруу») үйрөнүүгө кирбейт — өйдө же ылдый гана
    for t in range(50, len(cs) - h):
        if C[t + h] == C[t]:
            continue
        X.append(f(t))
        Y.append(1 if C[t + h] > C[t] else 0)
    return {"X": X, "Y": Y, "last": f(len(cs) - 1)}


def scaler(X):
    d, n = len(X[0]), len(X)
    mu, sd = [0.0] * d, [0.0] * d
    for x in X:
        for j in range(d):
            mu[j] += x[j]
    for j in range(d):
        mu[j] /= n
    for x in X:
        for k in range(d):
            sd[k] += (x[k] - mu[k]) * (x[k] - mu[k])
    for q in range(d):
        sd[q] = math.sqrt(sd[q] / n) or 1.0
    return lambda x: [(v - mu[i]) / sd[i] for i, v in enumerate(x)]


def sig(z):
    if z < -709:
        return 0.0                           # JS: 1 / (1 + Infinity) = 0
    return 1 / (1 + math.exp(-z))


def train_py(X, Y):
    d, m = len(X[0]), len(X)
    w, b = [0.0] * d, 0.0
    rng = range(d)
    for _ in range(400):
        gw, gb = [0.0] * d, 0.0
        for x, y in zip(X, Y):
            z = b
            for j in rng:
                z += w[j] * x[j]
            e = sig(z) - y
            gb += e
            for k in rng:
                gw[k] += e * x[k]
        b -= 0.1 * gb / m
        for q in rng:
            w[q] -= 0.1 * (gw[q] / m + 0.02 * w[q])
    return w, b


def train_np(X, Y):
    A, y = np.asarray(X, dtype=float), np.asarray(Y, dtype=float)
    m, d = A.shape
    w, b = np.zeros(d), 0.0
    with np.errstate(over="ignore"):
        for _ in range(400):
            e = 1 / (1 + np.exp(-(A @ w + b))) - y
            gb, gw = float(e.sum()), A.T @ e
            b -= 0.1 * gb / m
            w = w - 0.1 * (gw / m + 0.02 * w)
    return [float(v) for v in w], b


def pred(mdl, x):
    w, b = mdl
    z = b
    for j in range(len(x)):
        z += w[j] * x[j]
    return sig(z)


def model(cs, h=1, use_np=None):
    """ai-engine.js → model(): 70% үйрөнүү / 30% текшерүү, анан бардыгына кайра үйрөтүп, акыркы шамга p."""
    train = train_np if (np is not None if use_np is None else use_np) else train_py
    F = features(cs, h)
    if not F or len(F["X"]) < 120:
        return None
    X, Y = F["X"], F["Y"]
    split = int(math.floor(len(X) * 0.7))
    s1 = scaler(X[:split])
    m1 = train([s1(x) for x in X[:split]], Y[:split])
    teY = Y[split:]
    hit = sum(1 for x, y in zip(X[split:], teY) if (1 if pred(m1, s1(x)) > 0.5 else 0) == y)
    up = sum(teY) / len(teY)
    s2 = scaler(X)
    m2 = train([s2(x) for x in X], Y)
    return {"p": pred(m2, s2(F["last"])), "acc": hit / len(teY), "base": max(up, 1 - up), "n": len(X), "nTest": len(teY)}


def judge(ml):
    """ai-analyst.js → judge()"""
    edge = ml["acc"] - ml["base"]
    return edge, ((1 if ml["p"] >= 0.55 else -1 if ml["p"] <= 0.45 else 0) if edge > 0.01 else 0)


def rank(rows, mkt):
    """ai-analyst.js → rank(): BingX — сатып алуу гана (▲), BinoDex — ▲ жана ▼."""
    ok = [x for x in rows if (x["dir"] != 0 and x.get("ta", 0) >= TA_MIN if mkt == "binodex" else x["dir"] > 0)]
    ok.sort(key=lambda x: (-x.get("ta", 0), -abs(x["p"] - 0.5), -x["edge"]))
    return ok[:3]


# ======================================================================
#  Шамдар
# ======================================================================
def live_interval(exp):
    if exp < 5:
        return 1, max(1, jsround(exp))
    if exp < 15:
        return 5, max(1, jsround(exp / 5))
    if exp < 60:
        return 15, max(1, jsround(exp / 15))
    return 60, max(1, jsround(exp / 60))


def kraken_candles(code, iv, check=True):
    pace("kraken", 1.0)
    j = get_json("https://api.kraken.com/0/public/OHLC?pair=%s&interval=%d" % (KRAKEN[code], iv), 7)
    if j.get("error"):
        raise Fetch(j["error"][0])
    key = [k for k in j["result"] if k != "last"][0]
    rows = j["result"][key] or []
    if check:
        last = rows[-1] if rows else None
        trades = sum(num(r[7]) for r in rows[-30:])
        if not last or time.time() - last[0] > iv * 60 * 3 or trades == 0:
            raise Fetch("stale")
    return [{"time": int(r[0]), "open": float(r[1]), "high": float(r[2]), "low": float(r[3]), "close": float(r[4]), "volume": float(r[6])} for r in rows]


def binance_candles(sym, interval, limit=1000):
    err = None
    for host in BINANCE:
        try:
            k = get_json("%s?symbol=%s&interval=%s&limit=%d" % (host, sym, interval, limit), 8)
        except Exception as e:  # noqa: BLE001 — экинчи дарек менен аракет
            err = e
            continue
        if isinstance(k, list):
            return [{"time": int(r[0]) // 1000, "open": float(r[1]), "high": float(r[2]), "low": float(r[3]), "close": float(r[4]), "volume": float(r[7])} for r in k]
        err = Fetch("bad answer")
    raise Fetch(str(err))


def bingx_raw(base, interval, limit):
    j = get_json("https://open-api.bingx.com/openApi/spot/v2/market/kline?symbol=%s-USDT&interval=%s&limit=%d" % (base, interval, limit), 10)
    k = j.get("data")
    if not isinstance(k, list) or not k:
        raise Fetch("nodata")
    return sorted(k, key=lambda r: int(r[0]))


def g6(x):
    return float("%.6g" % num(x))


def bingx_candles(base):
    """Ошол эле BingX 1 саат шамдары, update_bingx.py'дегидей (k/<BASE>.json форматы), бирок жаңы."""
    k = bingx_raw(base, "1h", 300)
    if len(k) < 60:
        raise Fetch("nodata")
    cs = [{"time": int(r[0]) // 1000, "open": g6(r[1]), "high": g6(r[2]), "low": g6(r[3]), "close": g6(r[4]),
           "volume": round(num(r[7]) if len(r) > 7 else num(r[5]))} for r in k]
    return cs, num(k[-1][4])


def kfile_candles(name):
    rows = None
    path = os.path.join(DATA, "k", name + ".json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            rows = json.load(f)
    else:
        rows = get_json(SITE_URL + "/assets/data/k/" + name + ".json", 10)
    return [{"time": r[0], "open": r[1], "high": r[2], "low": r[3], "close": r[4], "volume": r[5]} for r in rows]


def binodex_candles(code, iv):
    # BinoDex API документациясы келгенде ушул жер толтурулат (ai-engine.js'теги binodexCandles() сыяктуу).
    if not os.environ.get("BINODEX_API"):
        raise Fetch("no-binodex-api")
    raise Fetch("binodex-api-pending")


def live_fx(code, exp, cache):
    """ai-engine.js → liveFX(): BinoDex API → Kraken → Binance (EUR/USDT, PAXG = алтын)."""
    iv, h = live_interval(exp)
    if (code, iv) not in cache:
        res, err = None, None
        chain = [("BinoDex", lambda: binodex_candles(code, iv))]
        if code in KRAKEN:
            chain.append(("Kraken", lambda: kraken_candles(code, iv)))
        if code in BN_FX:
            chain.append(("Binance (PAXG)" if code == "XAUUSD" else "Binance", lambda: binance_candles(BN_FX[code], BN_IV[iv])))
        for prov, fn in chain:
            try:
                res = (fn(), prov, now_ms())
                break
            except Exception as e:  # noqa: BLE001
                err = e
        cache[(code, iv)] = res or err
    r = cache[(code, iv)]
    if isinstance(r, Exception) or r is None:
        raise Fetch("nolive: %s" % r)
    cs, prov, t = r
    if len(cs) < 120:
        raise Fetch("nolive: %d candles" % len(cs))
    return {"candles": cs, "provider": prov, "iv": iv, "h": h, "t": t, "entry": cs[-1]["close"]}


def candles_1m(sg):
    """Экспирацияны текшерүү үчүн 1 мүнөттүк шамдар — сигнал алынган булактан."""
    prov, code, base = sg["provider"], sg.get("code"), sg["base"]
    if sg["mkt"] == "binodex":
        if prov == "Kraken":
            return kraken_candles(code, 1, check=False)
        return binance_candles(BN_FX[code], "1m")
    if prov == "Binance":
        return binance_candles(base + "USDT", "1m")
    return [{"time": int(r[0]) // 1000, "close": num(r[4])} for r in bingx_raw(base, "1m", 300)]


# ======================================================================
#  Активдер (bingx.json) жана сканер
# ======================================================================
def load_bx():
    path = os.path.join(DATA, "bingx.json")
    try:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        return get_json(SITE_URL + "/assets/data/bingx.json", 15)
    except Exception as e:  # noqa: BLE001
        print("! bingx.json окулган жок (%s) — BinoDex жуптарынын демейки тизмеси колдонулат." % e)
        return {"spot": [], "binance": [], "kfiles": [], "stocks": [], "forex": [], "growing": []}


def source(bx, base):
    if base.startswith("FX_"):
        return "fx"
    if base in (bx.get("binance") or []):
        return "binance"
    if base in (bx.get("kfiles") or []):
        return "bingx"
    return None


def fx_list(bx):
    fx = [(f["code"], f["name"]) for f in (bx.get("forex") or [])]
    if not fx:
        fx = FX_DEFAULT
    live = os.environ.get("BINODEX_API")
    return [(c, n) for c, n in fx if c in KRAKEN or c in BN_FX or live]


def bingx_cands(bx):
    """ai-analyst.js → scanCands() (толук режим): POP 16 + өсүп жаткандар 6 + акция токендери 10."""
    can = lambda b: source(bx, b) is not None  # noqa: E731
    pop = [b for b in POP if can(b)][:16]
    grow = [g["base"] for g in (bx.get("growing") or []) if can(g["base"])][:6]
    stocks = [s["base"] for s in (bx.get("stocks") or []) if can(s["base"])][:10]
    return list(dict.fromkeys(pop + grow + stocks))


def bx_label(bx, base, lang):
    s = [x for x in (bx.get("stocks") or []) if x["base"] == base]
    name = s[0]["name"] if s else T[lang]["gold"] if base == "PAXG" else base
    return (name + " · " if name != base else "") + base + "/USDT"


class Scanner:
    def __init__(self, bx, lang, verbose, idle=None):
        self.bx, self.lang, self.verbose, self.idle = bx, lang, verbose, idle or (lambda: None)
        self.cache = {}

    def row(self, base, name, mkt, d, ml, exp):
        edge, dr = judge(ml)
        ta, why = ta_check(d["candles"], dr) if mkt == "binodex" else (4, [])
        return {"ta": ta, "ta_why": why, "base": base, "code": base[3:] if base.startswith("FX_") else None, "mkt": mkt, "name": name,
                "p": ml["p"], "acc": ml["acc"], "bl": ml["base"], "edge": edge, "dir": dr, "n": ml["n"], "nTest": ml["nTest"],
                "entry": d["entry"], "t": d["t"], "provider": d["provider"], "iv": d["iv"], "h": d["h"], "exp": exp,
                "_cs": [{"time": c["time"], "open": c["open"], "high": c["high"], "low": c["low"], "close": c["close"]} for c in d["candles"][-64:]]}

    def binodex(self, exp):
        out, skipped = [], []
        for code, name in fx_list(self.bx):
            try:
                d = live_fx(code, exp, self.cache)
                ml = model(d["candles"], d["h"])
                if ml:
                    out.append(self.row("FX_" + code, name, "binodex", d, ml, exp))
                else:
                    skipped.append(name + " (аз маалымат)")
            except Exception as e:  # noqa: BLE001 — бул жуп азыр жеткиликсиз, өткөрүп жиберебиз
                skipped.append("%s (%s)" % (name, str(e)[:40]))
            self.idle()
        return out, skipped

    def bingx(self):
        out, skipped = [], []
        for base in bingx_cands(self.bx):
            try:
                src, t = source(self.bx, base), now_ms()
                if src == "binance":
                    cs, prov = binance_candles(base + "USDT", "1h"), "Binance"
                    if len(cs) < 120:
                        raise Fetch("nodata")
                    entry = cs[-1]["close"]
                    time.sleep(0.12)
                else:
                    prov = "BingX"
                    try:
                        cs, entry = bingx_candles(base)
                        time.sleep(0.12)
                    except Exception:  # noqa: BLE001 — запас: сайттагы k-файл, эгер эскирбесе
                        cs = kfile_candles(base)
                        entry = cs[-1]["close"]
                        if time.time() - cs[-1]["time"] > 2 * 3600:
                            raise Fetch("k-file эскирген")
                d = {"candles": cs, "provider": prov, "iv": 60, "h": 1, "t": t, "entry": entry}
                ml = model(cs, 1)
                if ml:
                    out.append(self.row(base, bx_label(self.bx, base, self.lang), "bingx", d, ml, 60))
                else:
                    skipped.append(base + " (аз маалымат)")
            except Exception as e:  # noqa: BLE001
                skipped.append("%s (%s)" % (base, str(e)[:40]))
            self.idle()
        return out, skipped


# ======================================================================
#  Тексттер
# ======================================================================
def hms(ms, sec=True):
    return datetime.fromtimestamp(ms / 1000, BISHKEK).strftime("%H:%M:%S" if sec else "%H:%M")


def money(x, fx):
    if x is None:
        return "—"
    if fx:
        return ("%.5f" if x < 20 else "%.3f") % x
    if x >= 1000:
        return "$" + ("{:,.2f}".format(x)).rstrip("0").rstrip(".")
    p = 10 if x < 0.0001 else 7 if x < 0.01 else 5 if x < 1 else 3 if x < 100 else 2
    return "$" + ("%." + str(p) + "f") % x


def link(sg):
    fx = sg["mkt"] == "binodex"
    return SITE_URL + "/forecast.html?s=" + urllib.parse.quote(sg["base"], safe="") + ("&exp=%d" % sg["exp"] if fx else "")


def dir_txt(sg, L):
    return ("▲ " + L["up"]) if sg["dir"] > 0 else ("▼ " + L["dn"])


LINE = "━━━━━━━━━━━━━━"


def msg_signal(sg, lang):
    L, fx, e = T[lang], sg["mkt"] == "binodex", html.escape
    up = sg["dir"] > 0
    dp = pct(sg["p"] if up else 1 - sg["p"])
    acc = L["acc"].format(a=pct(sg["acc"]), b=pct(sg["bl"]))
    lines = ["🚀 <b>%s</b>" % e(L["sig_h_fx"].format(m=sg["exp"]) if fx else L["sig_h_bx"]), LINE,
             "💎 <b>%s</b>" % e(sg["name"]),
             "%s %s: <b>%s</b> · %s <b>%s</b>" % ("📈" if up else "📉", e(L["dir_w"]), dir_txt(sg, L), e(L["prob_w"]), dp)]
    if sg.get("dogon"):
        lines[0:0] = ["<b>%s</b>" % e(L["dg_head"])]
        lines.insert(5, "❗️ <i>%s</i>" % e(L["dg_note"]))
    if fx and sg.get("ta_why"):
        lines.append("📐 %s: <b>%d/4</b> ✓ %s" % (e(L["ta_w"]), sg.get("ta", 0), e(", ".join(L["ta_names"].get(w, w) for w in sg["ta_why"]))))
    if fx:
        lines += ["🎯 %s: <b>%s</b>" % (e(L["entry"]), money(sg["entry"], True)),
                  "⏱ %s: <b>%s → %s</b> (Бишкек)" % (e(L["time_w"]), hms(sg["t0"]), hms(sg["tEnd"])),
                  "🧠 %s: %s" % (e(L["model_w"]), e(acc)),
                  "📡 " + e(L["quote"].format(p=sg["provider"], iv=sg["iv"]))]
    else:
        lines += ["🎯 %s: <b>%s</b> · %s (Бишкек)" % (e(L["price"]), money(sg["entry"], False), hms(sg["t0"], False)),
                  "🕐 " + e(L["bx_line"]),
                  "🧠 %s: %s" % (e(L["model_w"]), e(acc)),
                  "📡 " + e(L["quote_bx"].format(p=sg["provider"]))]
    lines += [LINE, '👉 <a href="%s">%s</a>' % (e(link(sg)), e(L["open"])),
              "⚠️ <i>%s %s</i>" % (e(L["honest"]), e(L["risk_fx"] if fx else L["risk_bx"]))]
    return "\n".join(lines)


def stats_line(hist, lang):
    a = [x for x in hist if x.get("res") in (0, 1)][-50:]
    if not a:
        return None
    w = sum(1 for x in a if x["res"] == 1)
    if len(a) < 10:                              # 1–2 сигналдан «100%» жазуу — адаштырат
        return T[lang]["stats_few"].format(w=w, l=len(a) - w)
    return T[lang]["stats"].format(n=len(a), w=w, l=len(a) - w, pc=jsround(w / len(a) * 100))


def msg_result(sg, hist, lang):
    L, fx, e = T[lang], sg["mkt"] == "binodex", html.escape
    res = sg["res"]
    mark = {1: "✅", 0: "❌", 2: "➖", 3: "⚪"}[res]
    head = {1: L["r_win"], 0: L["r_loss"], 2: L["r_tie"], 3: L["r_nodata"]}[res]
    what = {1: L["win"], 0: L["loss"], 2: L["tie"], 3: L["nodata"]}[res]
    dur = ("%d %s" % (sg["exp"], L["min"])) if fx else L["h1"]
    arrow = "▲" if sg["dir"] > 0 else "▼"
    lines = ["%s <b>%s</b> · <b>%s</b>%s" % (mark, e(head), e(sg["name"]), (" · 🔁 " + e(L["dg_res"])) if sg.get("dogon") else ""), LINE]
    if res != 3 and sg.get("exit") and sg.get("entry"):
        ch = (sg["exit"] - sg["entry"]) / sg["entry"] * 100
        lines.append("%s %s → <b>%s</b> (%s) · ⏱ %s" % (arrow, money(sg["entry"], fx), money(sg["exit"], fx),
                                                     ("%+.3f%%" if abs(ch) < 1 else "%+.2f%%") % ch, e(dur)))
    else:
        lines.append("%s %s · ⏱ %s" % (arrow, money(sg["entry"], fx), e(dur)))
    lines.append("🎯 " + e(what))
    s = stats_line(hist, lang)
    if s:
        lines.append("📊 " + e(s))
    lines.append("<i>%s</i>" % e(L["honest"]))
    return "\n".join(lines)


def session_stats(info, hist):
    a, b = info["t0"], info["tEnd"]
    xs = [x for x in hist if x.get("mkt") == "binodex" and a <= x.get("t0", 0) < b + 20 * 60000 and x.get("res") in (0, 1, 2)]
    return xs, sum(1 for x in xs if x["res"] == 1), sum(1 for x in xs if x["res"] == 0), sum(1 for x in xs if x["res"] == 2)


def msg_session(kind, info, hist, lang):
    L, e = T[lang], html.escape
    rng = "%s–%s (Бишкек)" % (hms(info["t0"], False), hms(info["tEnd"], False))
    if kind == "session_open":
        lines = ["🔔 <b>%s</b>" % e(L["ss_open"].format(n=info["n"])), LINE, "🕗 <b>%s</b>" % rng,
                 "⚡ " + e(L["ss_l1"].format(exp=" / ".join(map(str, info.get("exp") or [5])))),
                 "🔁 " + e(L["ss_l2"]), "📌 " + e(L["ss_l3"]), LINE,
                 "⚠️ <i>%s %s</i>" % (e(L["honest"]), e(L["risk_fx"]))]
        return "\n".join(lines)
    xs, w, l, t = session_stats(info, hist)
    lines = ["🏁 <b>%s</b>" % e(L["ss_close"].format(n=info["n"])), LINE, "🕗 %s · %s" % (datetime.fromtimestamp(info["t0"] / 1000, BISHKEK).strftime("%d.%m"), rng)]
    if not xs:
        lines.append("ℹ️ " + e(L["ss_none"]))
    else:
        lines.append("📊 <b>%s</b>" % e(L["ss_sum"].format(w=w, l=l, t=t)))
        if w + l >= 5:
            lines.append("🎯 " + e(L["ss_acc"].format(pc=jsround(w / (w + l) * 100), n=w + l)))
        for x in xs[-12:]:
            m = {1: "✅", 0: "❌", 2: "➖"}[x["res"]]
            lines.append("%s %s %s · %d %s%s" % (m, e(x["name"]), "▲" if x["dir"] > 0 else "▼", x["exp"], e(L["min"]), " · 🔁" if x.get("dogon") else ""))
    nx = next_session(info["tEnd"] + 1000)
    if nx:
        lines += [LINE, "⏭ " + e(L["ss_next"].format(t=hms(nx[1], False)))]
    lines.append("<i>%s</i>" % e(L["honest"]))
    return "\n".join(lines)


def plain(text):
    return html.unescape(re.sub(r"</?b>", "", text))


# ======================================================================
#  Telegram
# ======================================================================
class Telegram:
    def __init__(self, dry):
        self.dry = dry
        self.token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
        self.chat = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()

    def redact(self, s):
        s = str(s)
        return s.replace(self.token, "<TOKEN>") if self.token else s

    def call(self, method, payload=None, timeout=20):
        url = "https://api.telegram.org/bot%s/%s" % (self.token, method)
        data = json.dumps(payload or {}).encode("utf-8")
        for attempt in range(2):
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", "User-Agent": UA})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                try:
                    j = json.loads(e.read().decode("utf-8"))
                except Exception:  # noqa: BLE001
                    j = {"description": "HTTP %d" % e.code}
                wait = (j.get("parameters") or {}).get("retry_after")
                if e.code == 429 and wait and attempt == 0:
                    time.sleep(min(int(wait), 30) + 1)
                    continue
                raise Fetch("Telegram: %s" % self.redact(j.get("description", e.code)))
            except Exception as e:  # noqa: BLE001
                raise Fetch("Telegram: %s" % self.redact(e))
        raise Fetch("Telegram: 429")

    def send(self, text):
        if self.dry:
            print("\n┌─ билдирүү (DRY-RUN, жөнөтүлгөн жок) " + "─" * 30)
            for ln in plain(text).split("\n"):
                print("│ " + ln)
            print("└" + "─" * 66)
            return True
        try:
            r = self.call("sendMessage", {"chat_id": self.chat, "text": text, "parse_mode": "HTML",
                                          "link_preview_options": {"is_disabled": True}})
            return bool(r.get("ok"))
        except Fetch as e:
            print("! " + str(e))
            return False


# ======================================================================
#  Абал (state) — кичине JSON
# ======================================================================
def load_state(path):
    try:
        with open(path, encoding="utf-8") as f:
            st = json.load(f)
    except (OSError, ValueError):
        st = {}
    st.setdefault("last", {})
    st.setdefault("scan_t", {})
    st.setdefault("pending", [])
    st.setdefault("history", [])
    return st


def save_state(path, st):
    st["history"] = st["history"][-200:]
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def key_of(sg):
    return "%s:%d:%s" % (sg["base"], sg["dir"], sg["exp"] if sg["mkt"] == "binodex" else "1h")


def market_close_after(ta):
    """Форекс күнүнүн жабылышы: Нью-Йорк 17:00 (кышында Бишкек 04:00, жайында 03:00)."""
    try:
        from zoneinfo import ZoneInfo
        ny = ZoneInfo("America/New_York")
        t = ta.astimezone(ny)
        c = t.replace(hour=17, minute=0, second=0, microsecond=0)
        if c <= t:
            c += timedelta(days=1)
        return c.astimezone(BISHKEK)
    except Exception:  # noqa: BLE001 — tzdata жок болсо
        c = ta.replace(hour=4, minute=0, second=0, microsecond=0)
        return c if c > ta else c + timedelta(days=1)


def sessions_today(ms):
    """[(n, башы_ms, аягы_ms)] — Бишкек убактысы боюнча ошол күндүн сессиялары."""
    day = datetime.fromtimestamp(ms / 1000, BISHKEK).replace(hour=0, minute=0, second=0, microsecond=0)
    out = []
    for n, part in enumerate([x for x in SESSIONS.split(",") if x.strip()], 1):
        try:
            a, b = [x.strip() for x in part.split("-")]
            ta = day + timedelta(hours=int(a[:2]), minutes=int(a[3:5]))
            if b.lower() == "close":
                tb = market_close_after(ta)
            else:
                tb = day + timedelta(hours=int(b[:2]), minutes=int(b[3:5]))
                if tb <= ta:
                    tb += timedelta(days=1)               # түн ортосунан өтөт
            out.append((n, int(ta.timestamp() * 1000), int(tb.timestamp() * 1000)))
        except (ValueError, IndexError):
            continue
    return out


def session_at(ms):
    if not SESSIONS.strip():
        return (0, 0, 0)
    for x in sessions_today(ms - 86400000) + sessions_today(ms):
        if x[1] <= ms < x[2]:
            return x
    return None


def next_session(ms):
    for x in sessions_today(ms) + sessions_today(ms + 86400000):
        if x[1] > ms:
            return x
    return None


def scan_every(mkt, exp):
    """ai-analyst.js → scanEvery(): 1–3 мүн → 60 с, 5–15 мүн → 2 мүн, андан узун → 5 мүн; BingX → 10 мүн."""
    if mkt != "binodex":
        return 600000
    return 60000 if exp <= 15 else 300000


class Bot:
    def __init__(self, args):
        self.args = args
        self.lang = args.lang
        self.tg = Telegram(args.dry_run)
        self.state_path = args.state
        self.st = load_state(self.state_path)
        self.bx = None
        self.resolving = False

    def publish(self, kind, sg):
        """Сигнал же жыйынтык кайда кетет. Бул жерде — бир чатка; tg_bot.py аны бардык ачык доступтагыларга жөнөтөт."""
        if kind == "signal":
            return self.tg.send(msg_signal(sg, self.lang))
        return self.tg.send(msg_result(sg, self.st["history"], self.lang))

    def latest(self):
        """Акыркы скандардын эң мыктылары (ботто «⭐ Азыр» баскычы үчүн)."""
        out = []
        for c in (self.st.get("cand") or {}).values():
            if c and now_ms() - c["t"] < scan_every(c["mkt"], c["exp"]) + 60000:
                out.append(c)
        return sorted(out, key=lambda x: (-abs(x["p"] - 0.5), -x["edge"]))

    # ---- ✓/✗: экспирация учурундагы баа боюнча ----
    def resolve_due(self):
        if self.resolving:
            return
        now = now_ms()
        due = [p for p in self.st["pending"] if p["tEnd"] <= now - 2000]
        if not due:
            return
        self.resolving = True
        try:
            groups = {}
            for p in due:
                groups.setdefault((p["mkt"], p["provider"], p["base"]), []).append(p)
            for _, items in groups.items():
                try:
                    cs = candles_1m(items[0])
                except Exception as e:  # noqa: BLE001
                    cs = None
                    print("! %s: экспирациядагы баа алынган жок (%s)" % (items[0]["name"], str(e)[:60]))
                now = now_ms()
                for sg in items:
                    if cs is None:
                        if now - sg["tEnd"] < 30 * 60000:
                            continue                      # кийинки жолу кайра аракет
                        sg["res"], sg["exit"] = 3, None
                    else:
                        last = cs[-1] if cs else None
                        if last and now - sg["tEnd"] <= 15000 and last["time"] * 1000 <= now < last["time"] * 1000 + 65000:
                            px = last["close"]                # дал убагында: учурдагы баа (сайттагы tick() сыяктуу)
                        else:                                 # кечиккенде: сайттагы resolvePending() эрежеси
                            lim = sg["tEnd"] - 60000
                            ks = [c for c in cs if c["time"] * 1000 <= lim]
                            k = ks[-1] if ks else None
                            px = None if (not k or lim - k["time"] * 1000 > 120000) else k["close"]
                        if px is None:
                            sg["res"], sg["exit"] = 3, None
                        else:
                            sg["exit"] = px
                            sg["res"] = 2 if px == sg["entry"] else 1 if (px > sg["entry"]) == (sg["dir"] > 0) else 0
                    sg["tRes"] = now
                    self.st["pending"] = [x for x in self.st["pending"] if x["id"] != sg["id"]]
                    self.st["history"].append(sg)
                    self.publish("result", sg)
                    if sg["mkt"] == "binodex" and sg["res"] in (0, 1):
                        self.st["streak"] = (self.st.get("streak", 0) + 1) if sg["res"] == 0 else 0
                    if sg["mkt"] == "binodex" and sg["res"] == 0 and self.st.get("streak", 0) >= LOSS_STREAK:
                        self.st["cool_until"] = now_ms() + COOL_MS           # катары менен минус — 3 мүн тыныгуу, анан эң мыкты 5 мүн
                        self.st["streak"] = 0
                        for sid in list(self.st.get("scan_t", {})):
                            if sid.startswith("binodex:"):
                                self.st["scan_t"][sid] = now_ms() + COOL_MS - scan_every("binodex", 5)   # тыныгуу бүтөөр замат скан
                        print("  ⏸ %d минус катары менен — %d мүн тыныгуу" % (LOSS_STREAK, COOL_MS // 60000))
                    elif sg["mkt"] == "binodex" and sg["res"] == 0 and not sg.get("dogon") and os.environ.get("TG_DOGON", "1") != "0":
                        self.dogon(sg)
            save_state(self.state_path, self.st)
        finally:
            self.resolving = False

    def dogon(self, prev):
        """Минустан кийин бир гана жолу: ошол эле актив, ошол эле багыт, жаңы баа (мартингейл 1 кадам, эскертүү менен)."""
        sg = {k: v for k, v in prev.items() if k not in ("res", "exit", "tRes")}
        best = None
        for ex in (3, 2):                                  # перекрытие: 3 же 2 мүнөт — кайсынысы күчтүүрөөк ырастаса
            try:
                d = live_fx(sg["code"], ex, {})
                ml = model(d["candles"], d["h"])
                if not ml:
                    continue
                pd = ml["p"] if sg["dir"] > 0 else 1 - ml["p"]
                ta, why = ta_check(d["candles"], sg["dir"])
                if pd >= 0.52 and ta >= 2 and (best is None or (ta, pd) > (best[0], best[1])):
                    best = (ta, pd, ex, d, ml, why)
            except Exception as e:  # noqa: BLE001
                print("! догон %s %d мүн: %s" % (sg["name"], ex, str(e)[:60]))
        if not best:
            print("  догон жок: %s — жаңы анализ багытты ырастабады" % sg["name"])
            return
        ta, pd, ex, d, ml, why = best
        sg.update(exp=ex, p=ml["p"], acc=ml["acc"], bl=ml["base"], ta=ta, ta_why=why, h=d["h"], iv=d["iv"])
        sg["entry"], sg["t"], sg["provider"] = d["entry"], d["t"], d["provider"]
        sg["_cs"] = [{"time": c["time"], "open": c["open"], "high": c["high"], "low": c["low"], "close": c["close"]} for c in d["candles"][-64:]]
        sg["dogon"] = 1
        sg["id"] = now_ms()
        sg["t0"] = sg["t"]
        sg["tEnd"] = sg["t0"] + sg["exp"] * 60000
        sg["res"], sg["exit"] = None, None
        ok = self.publish("signal", sg)
        sg.pop("_cs", None)
        if ok:
            self.st["pending"].append(sg)
            self.st["last"] = {"key": key_of(sg), "t": now_ms()}

    def session_tick(self):
        if not SESSIONS.strip():
            return
        now = now_ms()
        ss = self.st.setdefault("sess", {})
        for n, a, b in sessions_today(now) + sessions_today(now - 86400000):
            sid = "%s#%d" % (datetime.fromtimestamp(a / 1000, BISHKEK).strftime("%Y-%m-%d"), n)
            info = {"id": sid, "n": n, "t0": a, "tEnd": b, "mkt": "binodex", "exp": sorted(self.args.exp, reverse=True)}
            ph = ss.get(sid)
            if a <= now < b and not ph:
                ss[sid] = "open"
                if now - a < 30 * 60000:                  # бот кеч иштеп калса — «башталды» жазылбайт
                    self.publish("session_open", info)
            elif now >= b and ph == "open":
                late = [x for x in self.st["pending"] if x["mkt"] == "binodex" and x["t0"] < b + 20 * 60000]
                if late and now < b + 30 * 60000:
                    continue                              # акыркы сигналдардын жыйынтыгын күтөт
                ss[sid] = "closed"
                self.publish("session_close", info)
        for k in [k for k in ss if k < datetime.fromtimestamp((now - 3 * 86400000) / 1000, BISHKEK).strftime("%Y-%m-%d")]:
            ss.pop(k, None)
        save_state(self.state_path, self.st)

    def streams(self):
        out = []
        if "binodex" in self.args.markets and session_at(now_ms()):
            out += [("binodex", e) for e in self.args.exp]
        if "bingx" in self.args.markets:
            out.append(("bingx", 60))
        return out

    def run_once(self):
        self.resolve_due()
        self.session_tick()
        if self.bx is None or now_ms() - self.bx.get("_t", 0) > 3600000:
            self.bx = load_bx()
            self.bx["_t"] = now_ms()
        sc = Scanner(self.bx, self.lang, self.args.verbose, idle=self.resolve_due)
        cand = self.st.setdefault("cand", {})
        for mkt, exp in self.streams():                  # BinoDex (кыска экспирация) биринчи, BingX акырында
            sid = "%s:%s" % (mkt, exp)
            ago = now_ms() - self.st["scan_t"].get(sid, 0)
            if not self.args.force and ago < scan_every(mkt, exp) - 10000:
                if self.args.verbose:
                    print("· %s: кийинки скан %d с кийин" % (sid, (scan_every(mkt, exp) - ago) // 1000))
                continue
            t0 = time.time()
            rows, skipped = sc.binodex(exp) if mkt == "binodex" else sc.bingx()
            self.st["scan_t"][sid] = now_ms()
            top = rank(rows, mkt)
            self.report(mkt, exp, rows, skipped, top, time.time() - t0)
            cand[sid] = top[0] if top else None
            # Ар бир скандан кийин дароо: 1 мүнөттүк сигнал BingX сканын күтүп эскирбесин.
            # Ар бир агымдын эң мыктысы анын кийинки сканына чейин гана жарактуу (BingX — 10 мүн, BinoDex 1 мүн — 60 с).
            live = {"%s:%s" % s for s in self.streams()}
            self.notify([c for k, c in cand.items() if c and k in live
                         and now_ms() - c["t"] < scan_every(c["mkt"], c["exp"])])
        save_state(self.state_path, self.st)

    def report(self, mkt, exp, rows, skipped, top, sec):
        ttl = ("BinoDex · %d мүн" % exp) if mkt == "binodex" else "BingX · 1 саат"
        print("\n=== %s · %s · %d актив, %.0f с ===" % (ttl, hms(now_ms()), len(rows), sec))
        for x in sorted(rows, key=lambda r: (-abs(r["p"] - 0.5), -r["edge"])):
            mark = "▲" if x["dir"] > 0 else "▼" if x["dir"] < 0 else "·"
            why = "" if x["dir"] else ("тест ≤ жөнөкөй+1п.п." if x["edge"] <= 0.01 else "p 45–55%")
            if mkt == "bingx" and x["dir"] < 0:
                why = "▼ — спотто көрсөтүлбөйт"
            print("  %s %-28s p▲ %5.1f%%  тест %4.1f%% / жөнөкөй %4.1f%%  edge %+5.1f  n=%d/%d  %-14s %s" % (
                mark, x["name"][:28], x["p"] * 100, x["acc"] * 100, x["bl"] * 100, x["edge"] * 100, x["n"], x["nTest"], x["provider"], why))
        if skipped:
            print("  өткөрүлдү: " + ", ".join(skipped))
        if top:
            print("  ⭐ " + " | ".join("%s %s %s" % (x["name"], "▲" if x["dir"] > 0 else "▼", pct(x["p"] if x["dir"] > 0 else 1 - x["p"])) for x in top))
        else:
            print("  ⭐ сигнал жок: эрежеге туура келген актив жок (сайт да «сигнал жок» дейт).")

    def notify(self, tops):
        if not tops:
            return
        L, now = self.st["last"], now_ms()
        if now < self.st.get("cool_until", 0):
            tops = [c for c in tops if c["mkt"] != "binodex"]
            if not tops:
                return
        for c in sorted(tops, key=lambda x: (x["mkt"] == "binodex" and x.get("exp") != 5, -abs(x["p"] - 0.5), -x["edge"])):
            k = key_of(c)
            if k == L.get("key") and now - L.get("t", 0) < ANTISPAM_SAME:
                print("  антиспам: %s — ошол эле сигнал 15 мүнөт ичинде, кайталанбайт." % c["name"])
                continue
            if now - L.get("t", 0) < ANTISPAM_ANY:
                print("  антиспам: акыркы билдирмеден 3 мүнөт өтө элек (%d с) — %s кийинчерээк." % ((now - L.get("t", 0)) // 1000, c["name"]))
                return
            sg = dict(c)
            if sg["mkt"] == "binodex":                   # жөнөтүү алдында жаңы баа: кирүү баасы ушул учур
                try:
                    d = live_fx(sg["code"], sg["exp"], {})
                    if d["provider"] == sg["provider"]:
                        sg["entry"], sg["t"] = d["entry"], d["t"]
                        sg["_cs"] = [{"time": c["time"], "open": c["open"], "high": c["high"], "low": c["low"], "close": c["close"]} for c in d["candles"][-64:]]
                except Exception:  # noqa: BLE001 — сканердеги баа калат
                    pass
            sg["id"] = now_ms()
            sg["t0"] = sg["t"]
            sg["tEnd"] = sg["t0"] + sg["exp"] * 60000
            sg["res"], sg["exit"] = None, None
            ok = self.publish("signal", sg)
            sg.pop("_cs", None)                           # шамдар — сүрөт үчүн гана, абал файлына жазылбайт
            if ok:
                self.st["last"] = {"key": k, "t": now_ms()}
                self.st["pending"].append(sg)
                cand = self.st.get("cand", {})
                for sid in [s for s, v in cand.items() if v is c]:
                    cand[sid] = None                      # жөнөтүлдү — кайра сунушталбайт
                save_state(self.state_path, self.st)
            return

    def next_wake(self):
        now, waits = now_ms(), []
        for mkt, exp in self.streams():
            waits.append(self.st["scan_t"].get("%s:%s" % (mkt, exp), 0) + scan_every(mkt, exp) - now)
        waits += [p["tEnd"] + 2000 - now for p in self.st["pending"]]
        if self.st.get("cool_until", 0) > now:
            waits.append(self.st["cool_until"] - now + 500)
        if SESSIONS.strip():
            cur, nx = session_at(now), next_session(now)
            waits += [x for x in ((cur[2] - now + 1000) if cur else None, (nx[1] - now + 1000) if nx else None) if x is not None]
        return max(3.0, min(waits) / 1000) if waits else 60.0


# ======================================================================
#  Кошумча буйруктар
# ======================================================================
def list_chats(tg):
    r = tg.call("getUpdates", {"limit": 100, "timeout": 0})
    seen = {}
    for u in r.get("result", []):
        m = u.get("message") or u.get("channel_post") or u.get("my_chat_member") or {}
        c = m.get("chat") or {}
        if c.get("id") is not None:
            seen[c["id"]] = "%s · %s" % (c.get("type"), c.get("title") or c.get("username") or c.get("first_name") or "")
    return seen


def ask(prompt, secret=False):
    """Терезеден окуу. Токен экранда көрүнбөйт (видео жазып жатканда да)."""
    try:
        if secret and sys.stdin.isatty():
            import getpass
            return getpass.getpass(prompt).strip().lstrip("﻿")
        return input(prompt).strip().lstrip("﻿")
    except EOFError:
        return None


ENV_FILE = os.environ.get("AITRADING_ENV") or "/etc/aitrading/bot.env"


def save_env_file(name, value, path=None):
    """Linux сервер: systemd'дин EnvironmentFile'ы (deploy/server/install.sh). Укугу 600 — ээси гана окуйт."""
    path = path or ENV_FILE
    lines = []
    try:
        with open(path, encoding="utf-8") as f:
            lines = [l for l in f.read().splitlines() if not l.startswith(name + "=")]
    except OSError:
        pass
    lines.append("%s=%s" % (name, value))
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d, mode=0o700, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    os.environ[name] = value


def where_saved():
    return "Windows'ко" if os.name == "nt" else ENV_FILE + " файлына (600)"


def save_user_env(name, value):
    """Windows: колдонуучунун чөйрө өзгөрмөсү (setx сыяктуу, HKCU\\Environment). Linux: ENV_FILE."""
    if os.name != "nt":
        return save_env_file(name, value)
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, name, 0, winreg.REG_SZ, value)
    try:                                         # жаңы ачылган терезелер дароо көрсүн
        import ctypes
        res = ctypes.c_ulong()
        ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "Environment", 0x0002, 5000, ctypes.byref(res))
    except Exception:  # noqa: BLE001
        pass
    os.environ[name] = value


def cmd_setup(lang):
    """Телеграм_бот_туташтыруу.bat: токен → текшерүү (getMe) → chat_id өзү табылат → текшерүү билдирүүсү."""
    print("\n AITRADING.KG — Telegram-ботту туташтыруу (бир жолу)\n " + "-" * 50)
    print(" 1. Telegram'да @BotFather ачыңыз: /newbot, анан ат жана логин (аягы _bot) жазыңыз.")
    print(" 2. BotFather берген ТОКЕНди көчүрүңүз. Аны эч кимге көрсөтпөңүз жана эч бир чатка жазбаңыз.")
    print(" 3. Өзүңүздүн жаңы ботуңузду ачып, Start басыңыз.\n")
    if os.name != "nt":
        print(" Сервер (Linux): ачкычтар %s сакталат, бот systemd аркылуу ошол файлдан окуйт.\n" % ENV_FILE)
    old = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    tok = ask("Токенди коюңуз (оң баскыч же Ctrl+V; экранда көрүнбөйт)%s жана Enter: " % (", Enter — мурункусун калтыруу" if old else ""), secret=True)
    tok = tok or old
    if not tok:
        print("Токен киргизилген жок.")
        return 1
    if not re.match(r"^\d{5,}:[A-Za-z0-9_-]{30,}$", tok):
        print("Бул токенге окшобойт (%d белги). Ал 123456789:AA… түрүндө болот. BotFather'ден кайра көчүрүп, кайра иштетиңиз." % len(tok))
        return 1
    tg = Telegram(False)
    tg.token = tok
    try:
        me = tg.call("getMe")["result"]
    except Fetch as e:
        print("! %s — токен туура эмес же интернет жок. Эч нерсе сакталган жок." % e)
        return 1
    user = me.get("username") or "?"
    print("Бот табылды: @%s ✓  (токен %s…, %d белги)" % (user, tok.split(":")[0], len(tok)))
    if tok != old:
        save_user_env("TELEGRAM_BOT_TOKEN", tok)
        print("Токен %s сакталды (сайттын файлдарына жазылган жок)." % where_saved())
    chats = {}
    for _ in range(10):
        try:
            chats = list_chats(tg)
        except Fetch as e:
            print("! " + str(e))
        if chats:
            break
        a = ask("\nTelegram'да @%s ботун ачып Start басыңыз, анан бул жерде Enter (чыгуу: q): " % user)
        if a is None or a.lower() == "q":
            break
    if not chats:
        old_chat = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
        if not old_chat:
            print("Чат табылган жок. Ботко Start басып, бул файлды кайра иштетиңиз.")
            return 1
        chat = old_chat
    else:
        items = list(chats.items())
        if len(items) == 1:
            chat = str(items[0][0])
        else:
            for i, (cid, info) in enumerate(items, 1):
                print("  %d) %s   %s" % (i, cid, info))
            a = ask("Сигналдар кайсы чатка келсин? Номерин жазыңыз (Enter — 1): ") or "1"
            try:
                chat = str(items[max(1, min(len(items), int(a))) - 1][0])
            except ValueError:
                chat = str(items[0][0])
        print("Чат: %s (%s) ✓" % (chat, chats.get(int(chat), chats.get(chat, ""))))
        save_user_env("TELEGRAM_CHAT_ID", chat)
    tg.chat = chat
    ok = tg.send(T[lang]["test"])
    print("\nТекшерүү билдирүүсү %s" % ("жөнөтүлдү ✓ — Telegram'ды караңыз. Эми Телеграм_бот.bat файлын эки жолу басыңыз." if ok else "жөнөтүлгөн жок ✗"))
    return 0 if ok else 1


def cmd_chat_id():
    tg = Telegram(False)
    if not tg.token:
        print("TELEGRAM_BOT_TOKEN коюлган эмес. ОКУ_МЕНИ.md, 8-бөлүмдү караңыз.")
        return 2
    try:
        seen = list_chats(tg)
    except Fetch as e:
        print("! " + str(e))
        return 1
    if not seen:
        print("Чат табылган жок. Telegram'да ботуңузга /start жазыңыз (канал болсо — ботту админ кылып, каналга бир пост жазыңыз), анан кайра иштетиңиз.")
        return 1
    print("Табылган чаттар (TELEGRAM_CHAT_ID катары керектүүсүн коюңуз):")
    for cid, info in seen.items():
        print("  %s   %s" % (cid, info))
    return 0


def cmd_test(lang):
    tg = Telegram(False)
    if not tg.token or not tg.chat:
        print("TELEGRAM_BOT_TOKEN жана TELEGRAM_CHAT_ID керек. ОКУ_МЕНИ.md, 8-бөлүм.")
        return 2
    ok = tg.send(T[lang]["test"])
    print("Жөнөтүлдү ✓" if ok else "Жөнөтүлгөн жок ✗")
    return 0 if ok else 1


JS_HARNESS = r"""
const fs = require("fs"), vm = require("vm");
const [eng, data] = process.argv.slice(1);
const ctx = { console, Math, Date, Promise, setTimeout, clearTimeout };
ctx.window = { fetch: () => Promise.reject(new Error("offline")) };
ctx.fetch = ctx.window.fetch;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(eng, "utf8"), ctx);
const A = ctx.window.AIENG;
const out = JSON.parse(fs.readFileSync(data, "utf8")).map(it => {
  const r = A.analyze(it.candles, { horizon: it.h });
  return r.ml ? { p: r.ml.p, acc: r.ml.acc, base: r.ml.base, n: r.ml.n, nTest: r.ml.nTest } : null;
});
process.stdout.write(JSON.stringify(out));
"""


def cmd_compare_js():
    """Ошол эле шамдарда Python модели менен сайттын ai-engine.js моделин салыштыруу."""
    node = shutil.which("node")
    if not node:
        print("Node.js табылган жок — салыштыруу үчүн https://nodejs.org орнотуңуз.")
        return 2
    items = []
    # 1) Оффлайн: сайттагы k-файлдар (Yahoo FX, BingX акция токендери) — ар кандай горизонттор
    for name, h in [("FX_EURUSD", 1), ("FX_EURUSD", 3), ("FX_XAUUSD", 1), ("FX_GBPJPY", 2), ("NVDAX", 1), ("PAXG", 1), ("APEPE", 1)]:
        try:
            items.append({"label": "k/%s.json h=%d" % (name, h), "candles": kfile_candles(name), "h": h})
        except Exception as e:  # noqa: BLE001
            print("  (өткөрүлдү %s: %s)" % (name, e))
    # 2) Жандуу: Kraken/Binance (BinoDex) жана Binance/BingX (BingX), ар кандай экспирациялар
    cache = {}
    for code, exp in [("EURUSD", 1), ("EURUSD", 3), ("GBPUSD", 5), ("XAUUSD", 1), ("XAUUSD", 15), ("EURCHF", 1)]:
        try:
            d = live_fx(code, exp, cache)
            items.append({"label": "%s %s exp=%d (iv %d, h %d)" % (code, d["provider"], exp, d["iv"], d["h"]), "candles": d["candles"], "h": d["h"]})
        except Exception as e:  # noqa: BLE001
            print("  (өткөрүлдү %s exp=%d: %s)" % (code, exp, e))
    for base in ["BTC", "ETH"]:
        try:
            items.append({"label": "%s Binance 1h" % base, "candles": binance_candles(base + "USDT", "1h"), "h": 1})
        except Exception as e:  # noqa: BLE001
            print("  (өткөрүлдү %s: %s)" % (base, e))
    try:
        cs, _ = bingx_candles("NVDAX")
        items.append({"label": "NVDAX BingX 1h (жандуу)", "candles": cs, "h": 1})
    except Exception as e:  # noqa: BLE001
        print("  (өткөрүлдү NVDAX BingX: %s)" % e)

    tmp = os.path.join(tempfile.mkdtemp(prefix="tgcmp_"), "candles.json")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump([{"candles": it["candles"], "h": it["h"]} for it in items], f)
    r = subprocess.run([node, "-e", JS_HARNESS, ENGINE_JS, tmp], capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        print("Node катасы:\n" + r.stderr)
        return 1
    js = json.loads(r.stdout)
    modes = [("numpy", True), ("python", False)] if np is not None else [("python", False)]
    worst, bad = 0.0, 0
    print("\n%-38s %-7s %8s %8s %8s %8s %6s  %s" % ("шамдар", "режим", "p py", "p js", "acc py", "acc js", "n", "max|Δ|"))
    for it, j in zip(items, js):
        for mname, use_np in modes:
            py = model(it["candles"], it["h"], use_np=use_np)
            if py is None or j is None:
                print("%-38s %-7s %s" % (it["label"][:38], mname, "модель жок (py=%s, js=%s)" % (py is not None, j is not None)))
                bad += (py is None) != (j is None)
                continue
            dmax = max(abs(py["p"] - j["p"]), abs(py["acc"] - j["acc"]), abs(py["base"] - j["base"]))
            same_n = py["n"] == j["n"] and py["nTest"] == j["nTest"]
            ok = dmax < 0.005 and same_n
            worst = max(worst, dmax)
            bad += not ok
            print("%-38s %-7s %8.4f %8.4f %8.4f %8.4f %6d  %.1e %s" % (it["label"][:38], mname, py["p"], j["p"], py["acc"], j["acc"], py["n"], dmax, "✓" if ok else "✗ АЙЫРМА"))
    print("\nЖыйынтык: %d салыштыруу, эң чоң айырма %.1e → %s" % (len(items) * len(modes), worst, "дал келет ✓" if not bad else "%d айырма ✗" % bad))
    return 0 if not bad else 1


def keep_awake(on):
    """Windows: --loop иштеп турганда компьютер өзү уктап калбасын (видео-плеерлер сыяктуу).
    Жөндөөлөр өзгөрбөйт: процесс жабылганда тыюу өзү эле алынат. Экран өчө берет."""
    if os.name != "nt":
        return False
    try:
        import ctypes
        es_continuous, es_system_required = 0x80000000, 0x00000001
        return bool(ctypes.windll.kernel32.SetThreadExecutionState(es_continuous | (es_system_required if on else 0)))
    except Exception:  # noqa: BLE001
        return False


# ======================================================================
def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)   # лог файлга дароо жазылсын
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="AITRADING.KG: ⭐ сигналдар Telegram'га")
    ap.add_argument("--dry-run", action="store_true", help="эч нерсе жөнөтпөйт, билдирүүлөрдү экранга чыгарат")
    ap.add_argument("--loop", action="store_true", help="токтобой иштөө (ПК / сервер)")
    ap.add_argument("--force", action="store_true", help="скан графигине карабай азыр сканерлөө")
    ap.add_argument("--exp", default=os.environ.get("TG_EXP", "5"), help="BinoDex экспирациясы, мүнөт (демейки 5; догон — 3/2 өзү)")
    ap.add_argument("--markets", default=os.environ.get("TG_MARKETS", "binodex,bingx"), help="binodex,bingx")
    ap.add_argument("--lang", default=os.environ.get("TG_LANG", "kg"), choices=["kg", "ru"])
    ap.add_argument("--state", default=os.environ.get("TG_STATE", ""), help="абал файлы (демейки tools/tg_state.json)")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--setup", action="store_true", help="бир жолу туташтыруу: токен → chat_id → текшерүү (Windows)")
    ap.add_argument("--chat-id", action="store_true", help="chat_id'ни табуу (getUpdates)")
    ap.add_argument("--test", action="store_true", help="текшерүү билдирүүсүн жөнөтүү")
    ap.add_argument("--compare-js", action="store_true", help="Python vs JS моделин салыштыруу")
    args = ap.parse_args()

    if args.setup:
        return cmd_setup(args.lang)
    if args.chat_id:
        return cmd_chat_id()
    if args.test:
        return cmd_test(args.lang)
    if args.compare_js:
        return cmd_compare_js()

    try:
        args.exp = sorted({max(1, min(240, int(float(x)))) for x in str(args.exp).split(",") if x.strip()})
    except ValueError:
        print("--exp туура эмес: мисалы 1,3,5")
        return 2
    args.markets = {m.strip().lower() for m in args.markets.split(",") if m.strip()}
    if not args.state:
        args.state = os.path.join(HERE, "tg_state.dry.json" if args.dry_run else "tg_state.json")

    bot = Bot(args)
    if not args.dry_run and (not bot.tg.token or not bot.tg.chat):
        print("TELEGRAM_BOT_TOKEN жана/же TELEGRAM_CHAT_ID коюлган эмес — эч нерсе жөнөтүлбөйт.\n"
              "Текшерүү үчүн: python tools/tg_signals.py --dry-run\n"
              "Ботту туташтыруу: ОКУ_МЕНИ.md, 8-бөлүм.")
        return 2
    print("AITRADING.KG сигнал-бот · %s · рынок: %s · BinoDex экспирация: %s мүн · модель: %s%s" % (
        "DRY-RUN (жөнөтүлбөйт)" if args.dry_run else "Telegram", ",".join(sorted(args.markets)), ",".join(map(str, args.exp)),
        "numpy" if np is not None else "python", " · токтобой" if args.loop else ""))
    if not args.loop:
        bot.run_once()
        return 0
    if keep_awake(True):
        print("Компьютер бот иштеп жатканда уктабайт (терезе жабылганда кадимкидей). Ноутбуктун капкагын жаппаңыз.")
    while True:
        try:
            bot.run_once()
            bot.args.force = False
        except KeyboardInterrupt:
            raise
        except Exception as e:  # noqa: BLE001 — тармак үзүлсө токтоп калбайт
            print("! ката: %s — 30 с кийин кайра" % bot.tg.redact(e))
            time.sleep(30)
            continue
        w = bot.next_wake()
        if args.verbose:
            print("· уктайт %.0f с" % w)
        try:
            time.sleep(w)
        except KeyboardInterrupt:
            break
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nТоктотулду.")
