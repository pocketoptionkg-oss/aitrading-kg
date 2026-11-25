"""Рынок пульсу / Пульс рынка: «⚠️ Шашылыш» плашкасынын эрежеси (сайттагы assets/js/alerts.js менен бирдей).

    python tools/market_pulse.py          # азыркы абалды көрсөтөт
    python tools/market_pulse.py --json

Эреже (ачык жана текшерилүүчү):
  Себет — config.js → ALERTS.basket (демейки: капитализациясы боюнча 10 ири крипто, стейблкоинсиз).
  Ар бир монетанын өзгөрүүсү Binance'тин расмий ticker'инен (rolling window): 24 саат жана 1 саат.
  «Бүт рынок» = себеттин МЕДИАНАСЫ (бир монетанын секириги эсепке кирбейт).
  - |медиана 24 с| ≥ ALERTS.move24 (5%)  → «рынок 24 саатта ±X% өстү/түштү»
  - |медиана 1 с|  ≥ ALERTS.move1h (3%)  → «кескин кыймыл бир саатта» (24 сааттыкына карама-каршы болсо — «рынок бурулду»)
  Булак: api.binance.com → data-api.binance.vision (Binance'тин расмий күзгүсү) → BingX (запас).
  Ар бир сан TradingView'дон текшерилет: CRYPTOCAP:TOTAL, BINANCE:BTCUSDT.
"""
import argparse
import json
import os
import re
import statistics
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_JS = os.path.join(os.path.dirname(HERE), "site", "assets", "js", "config.js")
UA = "Mozilla/5.0 (compatible; AITRADING.KG market pulse)"
BASKET = ["BTC", "ETH", "XRP", "BNB", "SOL", "DOGE", "TRX", "ADA", "LINK", "AVAX"]
MOVE24, MOVE1H = 5.0, 3.0
BINANCE = ["https://api.binance.com", "https://data-api.binance.vision"]
VERIFY_URL = "https://ru.tradingview.com/symbols/CRYPTOCAP-TOTAL/"


def settings():
    """config.js → ALERTS (автор ошол жерден гана өзгөртөт)."""
    basket, m24, m1 = list(BASKET), MOVE24, MOVE1H
    try:
        js = open(CONFIG_JS, encoding="utf-8").read()
        blk = re.search(r"ALERTS\s*:\s*\{(.*?)\n\s*\}", js, re.S)
        if blk:
            b = blk.group(1)
            m = re.search(r"basket\s*:\s*\[(.*?)\]", b, re.S)
            if m:
                got = re.findall(r'"([A-Z0-9]+)"', m.group(1))
                basket = got or basket
            m = re.search(r"move24\s*:\s*([\d.]+)", b)
            m24 = float(m.group(1)) if m else m24
            m = re.search(r"move1h\s*:\s*([\d.]+)", b)
            m1 = float(m.group(1)) if m else m1
    except OSError:
        pass
    return basket, m24, m1


def get_json(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def from_binance(basket):
    syms = urllib.parse.quote(json.dumps([b + "USDT" for b in basket], separators=(",", ":")))
    last = None
    for base in BINANCE:
        try:
            out = {}
            for win, key in (("1d", "c24"), ("1h", "c1h")):
                rows = get_json("%s/api/v3/ticker?type=MINI&windowSize=%s&symbols=%s" % (base, win, syms))
                for r in rows:
                    o, c = float(r["openPrice"]), float(r["lastPrice"])
                    if o > 0:
                        out.setdefault(r["symbol"][:-4], {})[key] = (c / o - 1) * 100
                        out[r["symbol"][:-4]]["last"] = c
            return out, "Binance"
        except Exception as e:  # noqa: BLE001
            last = e
    raise RuntimeError("Binance: %s" % last)


def from_bingx(basket):
    out = {}
    ts = int(time.time() * 1000)
    for b in basket:
        try:
            t = get_json("https://open-api.bingx.com/openApi/spot/v1/ticker/24hr?symbol=%s-USDT&timestamp=%d" % (b, ts))["data"][0]
            k = get_json("https://open-api.bingx.com/openApi/spot/v2/market/kline?symbol=%s-USDT&interval=1m&limit=61" % b)["data"]
            last = float(t["lastPrice"])
            o1 = float(k[-1][1])                      # 60 мүнөт мурунку ачылыш (эң эски шам)
            out[b] = {"c24": (last / float(t["openPrice"]) - 1) * 100, "c1h": (last / o1 - 1) * 100, "last": last}
        except Exception:  # noqa: BLE001
            continue
    if len(out) < len(basket) // 2 + 1:
        raise RuntimeError("BingX: маалымат жетишсиз")
    return out, "BingX"


def pulse():
    basket, m24, m1 = settings()
    try:
        rows, src = from_binance(basket)
    except Exception:  # noqa: BLE001
        rows, src = from_bingx(basket)
    c24 = [v["c24"] for v in rows.values() if "c24" in v]
    c1 = [v["c1h"] for v in rows.values() if "c1h" in v]
    if len(c24) < len(basket) // 2 + 1:
        raise RuntimeError("маалымат жетишсиз (%d/%d)" % (len(c24), len(basket)))
    med24, med1 = statistics.median(c24), statistics.median(c1) if c1 else 0.0
    return {
        "t": int(time.time() * 1000), "src": src, "n": len(c24), "basket": basket,
        "rows": {k: {kk: round(vv, 4) for kk, vv in v.items()} for k, v in rows.items()},
        "m24": round(med24, 2), "m1h": round(med1, 2),
        "up24": sum(1 for x in c24 if x > 0), "dn24": sum(1 for x in c24 if x < 0),
        "th24": m24, "th1h": m1,
    }


def pct(v):
    return ("+" if v > 0 else "−" if v < 0 else "") + ("%.1f" % abs(v)) + "%"


def alert_of(p):
    """Эреже иштесе — плашка/билдирме үчүн текст (кыргызча + орусча), болбосо None."""
    if not p:
        return None
    m24, m1 = p["m24"], p["m1h"]
    note_ky = "(%d ири монетанын медианасы, %s)" % (p["n"], p["src"])
    note_ru = "(медиана %d крупнейших монет, %s)" % (p["n"], p["src"])
    if abs(m1) >= p["th1h"]:
        d = 1 if m1 > 0 else -1
        turned = m24 * m1 < 0 and abs(m24) >= 1
        if turned:
            ky = "Крипто рыногу бурулду: 1 саатта %s (24 саатта %s) %s" % (pct(m1), pct(m24), note_ky)
            ru = "Крипторынок развернулся: %s за час (за 24 ч %s) %s" % (pct(m1), pct(m24), note_ru)
        else:
            ky = "Крипто рыногу кескин %s: 1 саатта %s, 24 саатта %s %s" % ("өстү" if d > 0 else "түштү", pct(m1), pct(m24), note_ky)
            ru = "Крипторынок резко %s: %s за час, %s за 24 ч %s" % ("вырос" if d > 0 else "упал", pct(m1), pct(m24), note_ru)
        return {"id": "m1h:%s" % ("up" if d > 0 else "dn"), "rule": "move1h", "dir": d, "value": m1, "turned": turned, "ky": ky, "ru": ru,
                "t": p["t"], "src": p["src"], "verify": VERIFY_URL}
    if abs(m24) >= p["th24"]:
        d = 1 if m24 > 0 else -1
        ky = "Бүт крипто рыногу 24 саатта %s: %s %s" % ("өстү" if d > 0 else "түштү", pct(m24), note_ky)
        ru = "Весь крипторынок %s за 24 ч: %s %s" % ("вырос" if d > 0 else "упал", pct(m24), note_ru)
        return {"id": "m24:%s" % ("up" if d > 0 else "dn"), "rule": "move24", "dir": d, "value": m24, "turned": False, "ky": ky, "ru": ru,
                "t": p["t"], "src": p["src"], "verify": VERIFY_URL}
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    p = pulse()
    a = alert_of(p)
    if args.json:
        print(json.dumps({"pulse": p, "alert": a}, ensure_ascii=False, indent=1))
        return 0
    print("Булак: %s · %d монета · медиана 24с %s (чек ±%s%%) · 1с %s (чек ±%s%%) · өсүүдө %d / түшүүдө %d" % (
        p["src"], p["n"], pct(p["m24"]), p["th24"], pct(p["m1h"]), p["th1h"], p["up24"], p["dn24"]))
    for k, v in p["rows"].items():
        print("  %-5s 24с %7s   1с %7s" % (k, pct(v.get("c24", 0)), pct(v.get("c1h", 0))))
    print("ШАШЫЛЫШ:", a["ky"] if a else "жок")
    return 0


if __name__ == "__main__":
    sys.exit(main())
