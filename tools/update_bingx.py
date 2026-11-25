"""BingX маалыматын жаңыртуу / Обновить данные BingX.

    python tools/update_bingx.py

BingX'тин ачык API'си браузерден түз окулбайт (CORS), ошондуктан бул скрипт
тизмени алдын ала жүктөп, site/assets/data/bingx.json файлына жазат.
Сайт «Тренддер» бөлүмүндө BingX'те БАР активдерди гана ушул файл боюнча көрсөтөт.
Жаңы листингдер чыкканда же жумасына бир жолу кайра иштетиңиз.
"""
import json
import os
import re
import time
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "site", "assets", "data", "bingx.json")
API = "https://open-api.bingx.com/openApi/spot/v1"

# Акция токендери: BingX'теги база → (негизги тикер, аты, сектор)
# Токен суффикстери: X, ON, B — ар кандай чыгаруучулар (шарттарын BingX'тен окуңуз).
STOCKS = {
    "SPCXB": ("NASDAQ:SPCX", "SpaceX", "space"),
    "ANTX": ("NASDAQ:ANT", "Anthropic", "ai"),
    "ANTB": ("NASDAQ:ANT", "Anthropic", "ai"),
    "SKHYB": ("NASDAQ:SKHY", "SK hynix", "chips"),
    "NVDAX": ("NASDAQ:NVDA", "NVIDIA", "ai"),
    "NVDAON": ("NASDAQ:NVDA", "NVIDIA", "ai"),
    "MSFTON": ("NASDAQ:MSFT", "Microsoft", "ai"),
    "GOOGLX": ("NASDAQ:GOOGL", "Alphabet (Google)", "ai"),
    "GOOGLON": ("NASDAQ:GOOGL", "Alphabet (Google)", "ai"),
    "METAX": ("NASDAQ:META", "Meta", "ai"),
    "PLTRON": ("NASDAQ:PLTR", "Palantir", "ai"),
    "AVGOON": ("NASDAQ:AVGO", "Broadcom", "chips"),
    "MUB": ("NASDAQ:MU", "Micron", "chips"),
    "INTCB": ("NASDAQ:INTC", "Intel", "chips"),
    "TSLAX": ("NASDAQ:TSLA", "Tesla", "auto"),
    "TSLAB": ("NASDAQ:TSLA", "Tesla", "auto"),
    "TSLAON": ("NASDAQ:TSLA", "Tesla", "auto"),
    "AAPLX": ("NASDAQ:AAPL", "Apple", "tech"),
    "AAPLON": ("NASDAQ:AAPL", "Apple", "tech"),
    "AMZNON": ("NASDAQ:AMZN", "Amazon", "tech"),
    "COINX": ("NASDAQ:COIN", "Coinbase", "fintech"),
    "COINON": ("NASDAQ:COIN", "Coinbase", "fintech"),
    "CRCLX": ("NYSE:CRCL", "Circle", "fintech"),
    "CRCLON": ("NYSE:CRCL", "Circle", "fintech"),
    "HOODX": ("NASDAQ:HOOD", "Robinhood", "fintech"),
    "MSTRX": ("NASDAQ:MSTR", "Strategy", "fintech"),
    "MSTRON": ("NASDAQ:MSTR", "Strategy", "fintech"),
    "SPYX": ("AMEX:SPY", "S&P 500 ETF", "index"),
    "SPYON": ("AMEX:SPY", "S&P 500 ETF", "index"),
    "QQQB": ("NASDAQ:QQQ", "Nasdaq-100 ETF", "index"),
    "QQQON": ("NASDAQ:QQQ", "Nasdaq-100 ETF", "index"),
    "SLVON": ("AMEX:SLV", "Silver ETF", "metals"),
    "XAUT": ("", "Tether Gold", "metals"),
    "PAXG": ("", "PAX Gold", "metals"),
}


STABLE = {"USDC", "FDUSD", "DAI", "USDE", "TUSD", "PYUSD", "USD1", "USDP", "EURC", "RLUSD", "USDD"}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (site data updater)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def num(x):
    try:
        return float(str(x).replace("%", ""))
    except (TypeError, ValueError):
        return 0.0


# «Реалдуу өсүп жатат, бирок ашыкча хайп эмес» эрежелери (сайтта ушул эле сандар көрсөтүлөт)
GROW_RULES = {
    "chg7_min": 2.0,          # 7 күндө кеминде +2%
    "chg7_max_crypto": 40.0,  # +40%дан ашса — ашыкча хайп
    "chg7_max_stock": 30.0,
    "chg24_max": 12.0,        # 24 саатта плюс, бирок +12%дан ашпайт
    "up_days_min": 4,         # акыркы 7 күндүн кеминде 4ү жашыл
    "vol_min_crypto": 300000, # BingX'те 24 саат көлөм
    "vol_min_stock": 30000,
    "fresh_days": 21,         # жаңы листинг (21 күндөн аз) — хайп, эсепке алынбайт
}
LEVERAGED = re.compile(r"(\d+[LS]|UP|DOWN|BULL|BEAR)$")


def find_growing(online, listed, tick, stock_by_base):
    """BingX'теги жуптардан туруктуу өсүп жаткандарды тандайт (күндүк шамдар боюнча)."""
    r = GROW_RULES
    now = time.time() * 1000
    spot = set(online)
    cands = []
    for b, t in tick.items():
        if b not in spot or b in STABLE or b in ("XAUT", "PAXG") or LEVERAGED.search(b) or b.startswith("TEST"):
            continue
        is_stock = b in stock_by_base
        vol = num(t.get("quoteVolume"))
        if vol < (r["vol_min_stock"] if is_stock else r["vol_min_crypto"]):
            continue
        if listed.get(b) and now - listed[b] < r["fresh_days"] * 864e5:
            continue
        cands.append((b, t, vol, is_stock))

    out = []
    for b, t, vol, is_stock in cands:
        try:
            k = get("https://open-api.bingx.com/openApi/spot/v2/market/kline?symbol=%s-USDT&interval=1d&limit=9" % b)["data"]
        except Exception:  # noqa: BLE001
            continue
        time.sleep(0.08)
        if not isinstance(k, list) or len(k) < 9:
            continue
        closed = k[1:8]                         # акыркы 7 жабылган күн (k[0] — бүгүнкү, бүтө элек)
        last = num(t.get("lastPrice"))
        c7 = num(k[7][4])
        if not c7 or not last:
            continue
        chg7 = (last / c7 - 1) * 100
        chg24 = num(t.get("priceChangePercent"))
        up = sum(1 for c in closed if num(c[4]) > num(c[1]))
        sma7 = sum(num(c[4]) for c in closed) / 7
        cap = r["chg7_max_stock"] if is_stock else r["chg7_max_crypto"]
        if not (r["chg7_min"] <= chg7 <= cap and 0 < chg24 <= r["chg24_max"] and up >= r["up_days_min"] and last > sma7):
            continue
        row = {"base": b, "kind": "stock" if is_stock else "crypto", "last": last, "chg24": round(chg24, 2),
               "chg7": round(chg7, 1), "up": up, "vol": round(vol), "listed": listed.get(b, 0)}
        if is_stock:
            s = stock_by_base[b]
            row.update({"name": s["name"], "sector": s["sector"], "under": s["under"]})
        out.append(row)
    out.sort(key=lambda x: -(x["chg7"] * x["up"] / 7))
    return out[:12], len(cands)


DATA_DIR = os.path.dirname(OUT)
KDIR = os.path.join(DATA_DIR, "k")                      # ар бир активдин 1 сааттык шамдары: k/<BASE>.json
STOCK_CACHE = os.path.join(DATA_DIR, "stocks_map.json")
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/"
STOCK_PAT = re.compile(r"^([A-Z]{1,5})(ON|X|B)$")

# BinoDex бөлүмүнүн валюта жуптары жана металлдар (BinoDex платформасындагы тизме менен салыштырып, керек болсо оңдоңуз).
# (сайттагы код, көрсөтүлүүчү ат, Yahoo символу, TradingView символу)
FX_PAIRS = [
    ("EURUSD", "EUR/USD", "EURUSD=X", "FX:EURUSD"),
    ("GBPUSD", "GBP/USD", "GBPUSD=X", "FX:GBPUSD"),
    ("USDJPY", "USD/JPY", "USDJPY=X", "FX:USDJPY"),
    ("AUDUSD", "AUD/USD", "AUDUSD=X", "FX:AUDUSD"),
    ("USDCAD", "USD/CAD", "USDCAD=X", "FX:USDCAD"),
    ("USDCHF", "USD/CHF", "USDCHF=X", "FX:USDCHF"),
    ("NZDUSD", "NZD/USD", "NZDUSD=X", "FX:NZDUSD"),
    ("EURGBP", "EUR/GBP", "EURGBP=X", "FX:EURGBP"),
    ("EURJPY", "EUR/JPY", "EURJPY=X", "FX:EURJPY"),
    ("GBPJPY", "GBP/JPY", "GBPJPY=X", "FX:GBPJPY"),
    ("AUDJPY", "AUD/JPY", "AUDJPY=X", "FX:AUDJPY"),
    ("EURCHF", "EUR/CHF", "EURCHF=X", "FX:EURCHF"),
    ("EURCAD", "EUR/CAD", "EURCAD=X", "FX:EURCAD"),     # BinoDex
    ("GBPCAD", "GBP/CAD", "GBPCAD=X", "FX:GBPCAD"),     # BinoDex
    ("CHFJPY", "CHF/JPY", "CHFJPY=X", "FX:CHFJPY"),     # BinoDex
    ("GBPAUD", "GBP/AUD", "GBPAUD=X", "FX:GBPAUD"),     # BinoDex
    ("CADJPY", "CAD/JPY", "CADJPY=X", "FX:CADJPY"),     # BinoDex
    ("EURAUD", "EUR/AUD", "EURAUD=X", "FX:EURAUD"),     # BinoDex
    ("AUDCAD", "AUD/CAD", "AUDCAD=X", "FX:AUDCAD"),     # BinoDex
    ("GBPCHF", "GBP/CHF", "GBPCHF=X", "FX:GBPCHF"),     # BinoDex
    ("CADCHF", "CAD/CHF", "CADCHF=X", "FX:CADCHF"),     # BinoDex
    ("XAUUSD", "XAU/USD", "GC=F", "OANDA:XAUUSD"),     # алтын: Yahoo'до фьючерс боюнча
    ("XAGUSD", "XAG/USD", "SI=F", "OANDA:XAGUSD"),     # күмүш
]


def detect_stocks(online, tick):
    """BingX'теги акция токендерин табат: ...X / ...ON / ...B аттуу жуптарды Yahoo'догу чыныгы акциянын баасы менен салыштырат.
    Натыйжа 24 саатка кэштелет (stocks_map.json)."""
    try:
        with open(STOCK_CACHE, encoding="utf-8") as f:
            cache = json.load(f)
        if time.time() - cache.get("ts", 0) < 86400:
            return cache["map"]
    except (OSError, ValueError):
        pass
    found = {}
    for b in online:
        m = STOCK_PAT.match(b)
        last = num(tick.get(b, {}).get("lastPrice"))
        if not m or not last:
            continue
        stem = m.group(1)
        try:
            meta = get(YAHOO + "%s?interval=1d&range=5d" % stem)["chart"]["result"][0]["meta"]
        except Exception:  # noqa: BLE001
            continue
        px = meta.get("regularMarketPrice") or 0
        if meta.get("instrumentType") in ("EQUITY", "ETF") and px and 0.85 <= last / px <= 1.15:
            ex = meta.get("exchangeName", "")
            tv = ("NASDAQ:" if ex in ("NMS", "NGM", "NCM", "NAS") else "AMEX:" if ex in ("PCX", "ASE") else "NYSE:") + stem
            found[b] = {"stem": stem, "name": (meta.get("shortName") or meta.get("longName") or stem).strip(), "etf": meta.get("instrumentType") == "ETF", "tv": tv}
        time.sleep(0.05)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(STOCK_CACHE, "w", encoding="utf-8") as f:
        json.dump({"ts": time.time(), "map": found}, f, ensure_ascii=False)
    return found


def bingx_klines(base, limit=300):
    k = get("https://open-api.bingx.com/openApi/spot/v2/market/kline?symbol=%s-USDT&interval=1h&limit=%d" % (base, limit))["data"]
    if not isinstance(k, list) or len(k) < 60:
        return None
    return [[int(r[0]) // 1000, float("%.6g" % num(r[1])), float("%.6g" % num(r[2])), float("%.6g" % num(r[3])), float("%.6g" % num(r[4])),
             round(num(r[7]) if len(r) > 7 else num(r[5]))] for r in reversed(k)]


def yahoo_klines(sym, n=700):
    r = get(YAHOO + "%s?interval=1h&range=60d" % sym)["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    rows = []
    for i, t in enumerate(r["timestamp"]):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if None in (o, h, l, c):
            continue
        rows.append([int(t), float("%.6g" % o), float("%.6g" % h), float("%.6g" % l), float("%.6g" % c), int(q["volume"][i] or 0)])
    return rows[-n:]


def save_k(name, rows):
    with open(os.path.join(KDIR, name + ".json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, separators=(",", ":"))


def main():
    symbols = get(API + "/common/symbols")["data"]["symbols"]
    online = sorted({s["symbol"][:-5] for s in symbols if s.get("status") == 1 and s["symbol"].endswith("-USDT")})
    listed = {s["symbol"][:-5]: s.get("timeOnline", 0) for s in symbols if s["symbol"].endswith("-USDT")}

    tick = get(API + "/ticker/24hr?timestamp=%d" % int(time.time() * 1000))["data"]
    tick = {t["symbol"][:-5]: t for t in tick if t["symbol"].endswith("-USDT")}

    # 1) Акция токендери: кол менен жазылгандар + автоматтык табылгандар
    auto = detect_stocks(online, tick)
    stocks = []
    for base in sorted(set(STOCKS) | set(auto)):
        if base not in online or base not in tick:
            continue
        if base in STOCKS:
            under, name, sector = STOCKS[base]
        else:
            a = auto[base]
            under, name, sector = a["tv"], a["name"], "index" if a["etf"] else "stock"
        t = tick[base]
        stocks.append({
            "base": base, "under": under, "name": name, "sector": sector,
            "last": num(t.get("lastPrice")), "chg": num(t.get("priceChangePercent")),
            "vol": round(num(t.get("quoteVolume"))), "listed": listed.get(base, 0),
        })
    stocks.sort(key=lambda r: -r["vol"])
    stock_set = {s["base"] for s in stocks}

    # 2) Binance'те да бар криптолор — сайт аларды Binance'тен жандуу жүктөйт.
    #    GitHub Actions АКШда иштейт, api.binance.com аны бөгөттөйт (451) — анда расмий маалымат күзгүсү data-api.binance.vision.
    #    Экөө тең жооп бербесе — мурунку тизме калат (бош тизме сайттагы 15м/4с/1к баскычтарын өчүрүп салат).
    binance = []
    for host in ("https://api.binance.com", "https://data-api.binance.vision"):
        try:
            bn = get(host + "/api/v3/ticker/price")
            binance = sorted({x["symbol"][:-4] for x in bn if x["symbol"].endswith("USDT")} & set(online) - stock_set)
            if binance:
                break
        except Exception as e:  # noqa: BLE001
            print("binance %s: %s" % (host, e))
    if not binance:
        try:
            with open(OUT, encoding="utf-8") as f:
                binance = json.load(f).get("binance") or []
            print("binance: мурунку тизме калды (%d)" % len(binance))
        except (OSError, ValueError):
            binance = []

    top = sorted(
        ({"base": b, "last": num(t.get("lastPrice")), "chg": num(t.get("priceChangePercent")), "vol": round(num(t.get("quoteVolume")))}
         for b, t in tick.items() if b in online and b not in stock_set and b not in STOCKS and b not in STABLE and not b.startswith("TEST")),
        key=lambda r: -r["vol"])[:15]

    growing, checked = find_growing(online, listed, tick, {s["base"]: s for s in stocks})

    # 3) Шамдар (k/*.json): бардык акция токендери + Binance'те жок, көлөмү бар криптолор + өсүп жаткандар
    os.makedirs(KDIR, exist_ok=True)
    vol = {b: num(t.get("quoteVolume")) for b, t in tick.items()}
    bn_set = set(binance)
    crypto_only = sorted((b for b in online if b not in stock_set and b not in bn_set and b not in STABLE and not LEVERAGED.search(b)
                          and not b.startswith("TEST") and vol.get(b, 0) >= 100000), key=lambda b: -vol.get(b, 0))[:150]
    want = list(stock_set) + crypto_only + [g["base"] for g in growing if g["base"] not in bn_set]
    have = set()
    for b in dict.fromkeys(want):
        try:
            rows = bingx_klines(b)
        except Exception:  # noqa: BLE001
            rows = None
        time.sleep(0.06)
        if rows:
            save_k(b, rows)
            have.add(b)

    # 4) Валюта жуптары (BinoDex бөлүмү) — Yahoo, 1 саат
    forex = []
    for code, label, ysym, tv in FX_PAIRS:
        try:
            rows = yahoo_klines(ysym)
        except Exception:  # noqa: BLE001
            continue
        if len(rows) < 120:
            continue
        save_k("FX_" + code, rows)
        last, prev = rows[-1][4], rows[max(0, len(rows) - 25)][4]
        forex.append({"code": code, "name": label, "tv": tv, "last": last, "chg": round((last / prev - 1) * 100, 2) if prev else 0})
    # эскирген файлдарды тазалоо
    keep = {b + ".json" for b in have} | {"FX_" + f["code"] + ".json" for f in forex}
    for fn in os.listdir(KDIR):
        if fn.endswith(".json") and fn not in keep:
            os.remove(os.path.join(KDIR, fn))

    data = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "https://open-api.bingx.com (spot)",
        "spot": online,
        "binance": binance,
        "kfiles": sorted(have),
        "stocks": stocks,
        "forex": forex,
        "top": top,
        "growing": growing,
        "growing_checked": checked,
        "growing_rules": GROW_RULES,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    old = os.path.join(DATA_DIR, "bingx_klines.json")
    if os.path.exists(old):
        os.remove(old)
    print("spot:", len(online), "| binance live:", len(binance), "| stock tokens:", len(stocks), "| k-files:", len(have), "| forex:", len(forex))
    print("growing: %d / %d checked:" % (len(growing), checked), ", ".join("%s %+.1f%%/7d" % (g["base"], g["chg7"]) for g in growing))
    print("saved:", OUT, os.path.getsize(OUT) // 1024, "KB")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001 — API жеткиликсиз болсо эски файл калат, жумуш токтобойт
        print("BingX API жеткиликсиз, эски bingx.json калды:", e)
