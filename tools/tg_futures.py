"""AITRADING.KG — BingX фьючерс сигналдары (жабык BingX каналы үчүн): кыска мөөнөт (15 мүн шамдар) жана орто мөөнөт (4 саат).

    python tools/tg_futures.py --scan          # бир скан: ар бир агымдын эң мыкты сунушун экранга чыгарат (эч нерсе жөнөтпөйт)

Эреже (сайттагы ИИ-анализатор менен бирдей, кошумча чыпкалар менен):
  1. Модель (tg_signals.model) — өсүү ыктымалдыгы p жана тесттеги тактык; judge(): edge > 1 п.п. жана p ≥ 55% же ≤ 45%.
  2. Тренд чыпкасы: EMA20 жана EMA50 сигналдын багытында; RSI каршы чекте эмес (лонгдо < 70, шортто > 30).
  3. Кирүү — акыркы баа (зона ±0.25 ATR). Стоп — акыркы 12 шамдын экстремумунан ары, аралыгы 1–3 ATR.
     TP1 = 1.5R, TP2 = 3R. Мөөнөт: кыска 8 саат, орто 4 күн. Мөөнөт бүтсө — рыноктук баа менен жабылат.
  4. Ар бир монетада бир агымга бир ачык соода; күнүнө: кыска ≤ 4, орто ≤ 2.
Натыйжалар ойлоп табылбайт: TP/SL BingX'тин 1 мүнөттүк шамдарынын high/low'у боюнча текшерилет.
"""
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tg_signals as S  # noqa: E402

API = "https://open-api.bingx.com/openApi/swap"
UNIVERSE = ["BTC", "ETH", "SOL", "XRP", "BNB", "DOGE", "ADA", "LINK", "AVAX", "SUI", "BCH", "TRX", "NEAR", "APT", "ATOM", "UNI",
            "ETC", "FIL", "HYPE", "ONDO", "TIA", "NCCOGOLD2USD", "NCSINASDAQ1002USD", "NCSKNVDA2USD"]   # акыркы үчөө: алтын, Nasdaq 100, NVIDIA
HZ = {
    "short": {"iv": "15m", "h": 4, "hold": 8 * 3600, "every": 15 * 60, "max_day": 4, "sl_lb": 12},
    "mid": {"iv": "4h", "h": 3, "hold": 4 * 86400, "every": 2 * 3600, "max_day": 2, "sl_lb": 12},
}
NAMES = {"BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana", "XRP": "XRP", "BNB": "BNB", "DOGE": "Dogecoin", "ADA": "Cardano",
         "LINK": "Chainlink", "AVAX": "Avalanche", "SUI": "Sui", "BCH": "Bitcoin Cash", "TRX": "TRON", "NEAR": "NEAR", "APT": "Aptos",
         "ATOM": "Cosmos", "UNI": "Uniswap", "ETC": "Ethereum Classic", "FIL": "Filecoin", "HYPE": "Hyperliquid", "ONDO": "Ondo", "TIA": "Celestia"}
PAIR = {"NCCOGOLD2USD": "GOLD (XAU/USD)", "NCSINASDAQ1002USD": "NASDAQ 100", "NCSKNVDA2USD": "NVIDIA (NVDA)"}


def label(sym):
    return PAIR.get(sym, sym + "/USDT")

TX = {
    "kg": {
        "h_short": "ФЬЮЧЕРС · КЫСКА МӨӨНӨТ", "h_mid": "ФЬЮЧЕРС · ОРТО МӨӨНӨТ",
        "long": "ЛОНГ (өсүүгө)", "short": "ШОРТ (түшүүгө)",
        "zone": "Кирүү зонасы", "sl": "Стоп-лосс", "tp1": "Тейк-профит 1", "tp2": "Тейк-профит 2",
        "rr": "Тобокелдик/пайда", "valid": "Жарактуу", "tf_short": "15 мүн шамдар · 8 саатка чейин", "tf_mid": "4 саат шамдар · 4 күнгө чейин",
        "prob": "ыктымалдык", "model": "Модель: тест {a} / жөнөкөй {b}",
        "risk": "Плечо 1–3x, бир соодага депозиттин 1–2% гана. Стопсуз кирбеңиз. Ыктымалдык — кепилдик эмес. 18+",
        "r_tp1": "🎯 TP1 алынды · стоп кирүү баасына (безубыток) жылдырылды",
        "r_tp2": "✅ ПЛЮС · TP2 алынды", "r_sl": "❌ МИНУС · стоп-лосс", "r_be": "✅ ПЛЮС · TP1 алынды, калганы безубыток менен жабылды",
        "r_exp_w": "✅ ПЛЮС · мөөнөт бүттү, рыноктук баа менен жабылды", "r_exp_l": "❌ МИНУС · мөөнөт бүттү, рыноктук баа менен жабылды",
        "stats": "Фьючерс статистикасы (акыркы {n}): плюс {w} · минус {l} · {pc}%", "stats_few": "Фьючерс статистикасы: плюс {w} · минус {l}",
    },
    "ru": {
        "h_short": "ФЬЮЧЕРС · КРАТКОСРОК", "h_mid": "ФЬЮЧЕРС · СРЕДНЕСРОК",
        "long": "ЛОНГ (на рост)", "short": "ШОРТ (на падение)",
        "zone": "Зона входа", "sl": "Стоп-лосс", "tp1": "Тейк-профит 1", "tp2": "Тейк-профит 2",
        "rr": "Риск/прибыль", "valid": "Действует", "tf_short": "свечи 15 мин · до 8 часов", "tf_mid": "свечи 4 часа · до 4 дней",
        "prob": "вероятность", "model": "Модель: тест {a} / угадывание {b}",
        "risk": "Плечо 1–3x, риск на сделку — 1–2% депозита. Без стопа не входите. Вероятность, а не гарантия. 18+",
        "r_tp1": "🎯 TP1 взят · стоп перенесён в безубыток (цена входа)",
        "r_tp2": "✅ ПЛЮС · TP2 взят", "r_sl": "❌ МИНУС · стоп-лосс", "r_be": "✅ ПЛЮС · TP1 взят, остаток закрыт в безубыток",
        "r_exp_w": "✅ ПЛЮС · срок вышел, закрыто по рынку", "r_exp_l": "❌ МИНУС · срок вышел, закрыто по рынку",
        "stats": "Статистика фьючерсов (последние {n}): плюс {w} · минус {l} · {pc}%", "stats_few": "Статистика фьючерсов: плюс {w} · минус {l}",
    },
}


# ---------------------------------------------------------------- маалымат
def klines(sym, iv, limit=500):
    j = S.get_json("%s/v3/quote/klines?symbol=%s-USDT&interval=%s&limit=%d" % (API, sym, iv, limit), 12)
    rows = j.get("data")
    if not isinstance(rows, list) or not rows:
        raise S.Fetch("nodata %s %s" % (sym, iv))
    out = [{"time": int(r["time"]) // 1000, "open": float(r["open"]), "high": float(r["high"]), "low": float(r["low"]),
            "close": float(r["close"]), "volume": float(r["volume"])} for r in rows]
    out.sort(key=lambda c: c["time"])
    return out


def ema(vals, n):
    k, e, out = 2 / (n + 1), None, []
    for v in vals:
        e = v if e is None else v * k + e * (1 - k)
        out.append(e)
    return out


def atr(cs, n=14):
    tr = [max(c["high"] - c["low"], abs(c["high"] - p["close"]), abs(c["low"] - p["close"])) for p, c in zip(cs, cs[1:])]
    if len(tr) < n:
        return None
    a = sum(tr[:n]) / n
    for t in tr[n:]:
        a = (a * (n - 1) + t) / n
    return a


def rnd(x):
    return float("%.6g" % x)


# ---------------------------------------------------------------- анализ
def analyze(sym, hz):
    cfg = HZ[hz]
    cs = klines(sym, cfg["iv"], 500)
    if len(cs) < 200:
        return None
    ml = S.model(cs, cfg["h"])
    if not ml:
        return None
    edge, d = S.judge(ml)
    closes = [c["close"] for c in cs]
    e20, e50 = ema(closes, 20)[-1], ema(closes, 50)[-1]
    r = S.rsi(closes, 14)
    r = r[-1] if isinstance(r, list) else r
    a = atr(cs, 14)
    last = closes[-1]
    row = {"sym": sym, "hz": hz, "p": ml["p"], "acc": ml["acc"], "bl": ml["base"], "edge": edge, "dir": d, "price": last, "atr": a,
           "ema20": e20, "ema50": e50, "rsi": r, "why": ""}
    if d == 0 or not a:
        row["why"] = "модель: сигнал жок"
        return row
    if d > 0 and not (last > e20 > e50):
        row["why"], row["dir"] = "тренд каршы (EMA)", 0
    elif d < 0 and not (last < e20 < e50):
        row["why"], row["dir"] = "тренд каршы (EMA)", 0
    elif r is not None and ((d > 0 and r >= 70) or (d < 0 and r <= 30)):
        row["why"], row["dir"] = "RSI чекте", 0
    if row["dir"] == 0:
        return row
    lb = cs[-cfg["sl_lb"]:]
    if d > 0:
        sl = min(c["low"] for c in lb) - 0.2 * a
        dist = min(max(last - sl, 1.0 * a), 3.0 * a)
        sl = last - dist
    else:
        sl = max(c["high"] for c in lb) + 0.2 * a
        dist = min(max(sl - last, 1.0 * a), 3.0 * a)
        sl = last + dist
    row.update({"entry": rnd(last), "zone": [rnd(last - 0.25 * a), rnd(last + 0.25 * a)], "sl": rnd(sl),
                "tp1": rnd(last + d * 1.5 * dist), "tp2": rnd(last + d * 3.0 * dist),
                "_cs": [{k: c[k] for k in ("time", "open", "high", "low", "close")} for c in cs[-64:]]})
    return row


def scan(hz, skip=()):
    rows = []
    for sym in UNIVERSE:
        if sym in skip:
            continue
        try:
            r = analyze(sym, hz)
            if r:
                rows.append(r)
        except Exception as e:  # noqa: BLE001 — бул монета азыр жеткиликсиз
            rows.append({"sym": sym, "hz": hz, "dir": 0, "why": str(e)[:60]})
        time.sleep(0.15)
    good = [r for r in rows if r.get("dir")]
    good.sort(key=lambda r: (-abs(r["p"] - 0.5), -r["edge"]))
    return good, rows


# ---------------------------------------------------------------- тексттер
def money(x):
    return S.money(x, False)


def msg_signal(tr, lang):
    L, e = TX.get(lang, TX["kg"]), S.html.escape
    up = tr["dir"] > 0
    dp = S.pct(tr["p"] if up else 1 - tr["p"])
    risk = abs(tr["entry"] - tr["sl"])
    lines = ["%s <b>%s</b>" % ("🟢" if up else "🔴", e(L["h_" + tr["hz"]])), S.LINE,
             ("💎 <b>%s</b> · %s" % (e(label(tr["sym"])), e(NAMES[tr["sym"]]))) if tr["sym"] in NAMES else "💎 <b>%s</b> · BingX" % e(label(tr["sym"])),
             "%s <b>%s</b> · %s <b>%s</b>" % ("📈" if up else "📉", e(L["long"] if up else L["short"]), e(L["prob"]), dp),
             "🎯 %s: <b>%s – %s</b>" % (e(L["zone"]), money(tr["zone"][0]), money(tr["zone"][1])),
             "🛑 %s: <b>%s</b>" % (e(L["sl"]), money(tr["sl"])),
             "✅ %s: <b>%s</b>" % (e(L["tp1"]), money(tr["tp1"])),
             "🏆 %s: <b>%s</b>" % (e(L["tp2"]), money(tr["tp2"])),
             "⚖️ %s: 1 : 1.5 / 1 : 3 · %s %.2f%%" % (e(L["rr"]), e(L["sl"]).lower(), risk / tr["entry"] * 100),
             "⏱ %s" % e(L["tf_" + tr["hz"]]),
             "🧠 " + e(L["model"].format(a=S.pct(tr["acc"]), b=S.pct(tr["bl"]))),
             S.LINE, "⚠️ <i>%s</i>" % e(L["risk"])]
    return "\n".join(lines)


def stats(hist, lang):
    L = TX.get(lang, TX["kg"])
    a = [h for h in hist if h.get("res") in (0, 1)][-50:]
    if not a:
        return None
    w = sum(1 for h in a if h["res"] == 1)
    if len(a) < 10:
        return L["stats_few"].format(w=w, l=len(a) - w)
    return L["stats"].format(n=len(a), w=w, l=len(a) - w, pc=int(round(w / len(a) * 100)))


def msg_update(tr, kind, price, hist, lang):
    L, e = TX.get(lang, TX["kg"]), S.html.escape
    up = tr["dir"] > 0
    ch = (price - tr["entry"]) / tr["entry"] * 100 * (1 if up else -1)
    lines = ["%s" % e(L["r_" + kind]), "<b>%s</b> · %s · %s" % (e(label(tr["sym"])), e(L["long"] if up else L["short"]), e(L["h_" + tr["hz"]].split("·")[-1].strip())),
             "%s → <b>%s</b> (%+.2f%%)" % (money(tr["entry"]), money(price), ch)]
    if kind != "tp1":
        s = stats(hist, lang)
        if s:
            lines.append("📊 " + e(s))
    return "\n".join(lines)


# ---------------------------------------------------------------- соодаларды жүргүзүү
class Desk:
    """Ачык фьючерс соодалары: state = {"open": [...], "hist": [...], "last_scan": {hz: ts}, "day": {date: {hz: n}}}.
    publish(kind, tr, extra) — сигнал/жаңыртууну каналга жиберүү (tg_bot тарабынан берилет)."""

    def __init__(self, load, save, publish, log=print):
        self.load, self.save, self.publish, self.log = load, save, publish, log
        self.st = load() or {}
        for k, v in (("open", []), ("hist", []), ("last_scan", {}), ("day", {})):
            self.st.setdefault(k, v)

    def tick(self):
        now = time.time()
        self.follow(now)
        today = time.strftime("%Y-%m-%d", time.gmtime(now + 6 * 3600))
        cnt = self.st["day"].setdefault(today, {})
        for k in list(self.st["day"]):
            if k != today:
                del self.st["day"][k]
        for hz, cfg in HZ.items():
            if now - self.st["last_scan"].get(hz, 0) < cfg["every"] or cnt.get(hz, 0) >= cfg["max_day"]:
                continue
            self.st["last_scan"][hz] = now
            busy = {t["sym"] for t in self.st["open"] if t["hz"] == hz}
            good, _ = scan(hz, busy)
            if good:
                tr = good[0]
                tr["id"], tr["t0"], tr["tEnd"], tr["state"] = int(now * 1000), int(now * 1000), int((now + cfg["hold"]) * 1000), "open"
                cs = tr.pop("_cs", None)
                self.publish("signal", tr, {"cs": cs})
                self.st["open"].append(tr)
                cnt[hz] = cnt.get(hz, 0) + 1
                self.log("фьючерс сигнал: %s %s %s p=%.2f" % (hz, tr["sym"], "LONG" if tr["dir"] > 0 else "SHORT", tr["p"]))
            self.save(self.st)

    def follow(self, now):
        """TP/SL текшерүү — 1 мүнөттүк шамдардын high/low'у боюнча (акыркы текшерүүдөн бери)."""
        changed = False
        for tr in list(self.st["open"]):
            try:
                cs = klines(tr["sym"], "1m", 300)
            except Exception:  # noqa: BLE001
                continue
            since = tr.get("chk", tr["t0"]) // 1000
            new = [c for c in cs if c["time"] >= since - 60]
            up = tr["dir"] > 0
            done = None
            for c in new:
                hi, lo = c["high"], c["low"]
                stop = tr["entry"] if tr["state"] == "tp1" else tr["sl"]
                hit_sl = lo <= stop if up else hi >= stop
                hit_tp1 = hi >= tr["tp1"] if up else lo <= tr["tp1"]
                hit_tp2 = hi >= tr["tp2"] if up else lo <= tr["tp2"]
                if hit_sl:                                        # бир шамда экөө тең болсо — эң жаман жыйынтык (чынчыл)
                    done = ("be", tr["entry"]) if tr["state"] == "tp1" else ("sl", tr["sl"])
                    break
                if tr["state"] == "open" and hit_tp1:
                    tr["state"] = "tp1"
                    self.publish("update", tr, {"kind": "tp1", "price": tr["tp1"], "hist": self.st["hist"]})
                    changed = True
                if tr["state"] == "tp1" and hit_tp2:
                    done = ("tp2", tr["tp2"])
                    break
            tr["chk"] = int(now * 1000)
            if not done and now * 1000 >= tr["tEnd"] and cs:
                px = cs[-1]["close"]
                gain = (px - tr["entry"]) * (1 if up else -1)
                done = ("exp_w" if gain > 0 or tr["state"] == "tp1" else "exp_l", px)
            if done:
                kind, px = done
                tr["res"] = 0 if kind in ("sl", "exp_l") else 1           # «be» — TP1 алынгандан кийин: пайда бар
                tr["exit"], tr["state"], tr["tClose"] = px, kind, int(now * 1000)
                self.st["open"].remove(tr)
                self.st["hist"] = (self.st["hist"] + [{k: tr[k] for k in ("id", "sym", "hz", "dir", "entry", "exit", "res", "t0", "tClose")}])[-200:]
                self.publish("update", tr, {"kind": kind, "price": px, "hist": self.st["hist"]})
            changed = True
        if changed:
            self.save(self.st)


if __name__ == "__main__":
    if "--scan" in sys.argv:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
        for hz in HZ:
            good, rows = scan(hz)
            print("\n=== %s ===" % hz)
            for r in rows:
                print("  %-5s %s p=%s edge=%s %s" % (r["sym"], {1: "LONG", -1: "SHORT", 0: "  - "}[r.get("dir", 0)],
                                                     ("%.2f" % r["p"]) if "p" in r else "-", ("%+.1f" % (r["edge"] * 100)) if "edge" in r else "-", r.get("why", "")))
            if good:
                print(msg_signal(good[0], "ru"))
    else:
        print(__doc__)
