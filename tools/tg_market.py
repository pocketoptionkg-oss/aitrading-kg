"""Рынок окуялары ботто / События рынка в боте (tools/tg_bot.py ичинде иштейт: App.market).

    python tools/tg_market.py --demo <папка>   # күндүн жыйынтыгы (сүрөт + текст KG/RU) азыркы рыноктон — эч жерге жөнөтүлбөйт
    python tools/tg_market.py --listen 60      # 60 секунд ликвидацияларды жана киттерди угуп, эмне келгенин көрсөтөт

Эмне кылат (баары чыныгы ачык маалыматтан, сандар ойлоп табылбайт — [[trader-kg-honest-numbers]]):
  💥 Ликвидациялар — Binance (!forceOrder@arr: ар бир монета боюнча секундасына эң ирисин гана берет) жана
     Bybit (allLiquidation, оборот боюнча 40 ири контракт). Ошондуктан бул «биз байкаган» сумма, бүт рыноктун суммасы эмес.
     • бир ири ликвидация ≥ TG_LIQ_BIG ($1 млн) → канал/тема (күнүнө ≤4, ортосу ≥45 мүн);
     • 1 саатта ≥ TG_LIQ_HOUR ($30 млн) → «ликвидация толкуну»: канал + ботто жазылгандар (6 саатта бир).
  🐳 Киттер — BTC блокчейни (blockchain.info, тастыктала элек транзакциялар): ≥ TG_WHALE_BTC (500 BTC) которуу →
     канал/тема (күнүнө ≤6, ортосу ≥30 мүн). Белгилүү биржа капчыктары гана аталат, калганы «белгисиз капчык».
     WHALE_ALERT_KEY коюлса — Whale Alert API (биржалардын аттары менен, бардык блокчейндер).
  📊 Күндүн жыйынтыгы — TG_DAY_H (22:00 Бишкек): BTC/ETH, лидер/аутсайдер, волатилдүүлүк 30 күндүн орточосуна
     салыштырмалуу, ликвидациялар лонг/шорт, киттер, Коркуу/Ачкөздүк индекси, капитализация. Сүрөт + тамаша менен.
  📣 VIP жарнамасы — TG_PROMO_H (13:00): TG_PROMO_CHAT (болбосо TELEGRAM_CHANNEL) жана доступу жоктор (3 күндө бир).
Кайда: жаңылыктар менен бирдей (tg_news.NewsDesk.dest: форумдагы /news темасы → TELEGRAM_CHANNEL).
Колдонуучу профилинде «📰 Жаңылыктар» өчүк болсо — бул посттор да келбейт.
"""
import argparse
import base64
import datetime as dt
import html
import json
import math
import os
import random
import socket
import ssl
import statistics
import struct
import sys
import threading
import time
import urllib.parse
import urllib.request
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import market_pulse as MP  # noqa: E402

BISHKEK = dt.timezone(dt.timedelta(hours=6))
UA = "Mozilla/5.0 (compatible; AITRADING.KG market bot)"
E = lambda s: html.escape(str(s if s is not None else ""), quote=False)  # noqa: E731


def env_num(name, default):
    try:
        return float(os.environ.get(name) or default)
    except ValueError:
        return float(default)


LIQ_BIG = env_num("TG_LIQ_BIG", 1_000_000)
LIQ_HOUR = env_num("TG_LIQ_HOUR", 30_000_000)
WHALE_BTC = env_num("TG_WHALE_BTC", 500)
WHALE_USD = env_num("TG_WHALE_USD", 50_000_000)       # Whale Alert үчүн (бардык монеталар)
DAY_H = int(env_num("TG_DAY_H", 22))
PROMO_H = int(env_num("TG_PROMO_H", 13))
PROMO_USER_DAYS = 3
MIN = 60_000
HOUR = 60 * MIN
TICK_S = 60

BINANCE_WS = ["wss://fstream.binance.com/market/ws/!forceOrder@arr", "wss://fstream.binance.com/ws/!forceOrder@arr"]
BYBIT_WS = "wss://stream.bybit.com/v5/public/linear"
BTC_WS = "wss://ws.blockchain.info/inv"

# Биржалардын белгилүү BTC капчыктары (ачык рейтингдерде биржанын аты менен белгиленген). Тизмеде жок — «белгисиз».
BTC_LABELS = {
    "34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo": "Binance",
    "bc1qm34lsc65zpw79lxes69zkqmk6ee3ewf0j77s3h": "Binance",
    "3M219KR5vEneNb47ewrPfWyb5jQ2DjxRP6": "Binance",
    "bc1qgdjqv0av3q56jvd82tkdjpy7gdp9ut8tlqmgrpmv24sq90ecnvqqjwvw97": "Bitfinex",
}


def now_ms():
    return int(time.time() * 1000)


def get_json(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


# ======================================================================
#  Жөнөкөй WebSocket кардары (стандарттык китепкана гана — серверге кошумча пакет керек эмес)
# ======================================================================
class WS:
    def __init__(self, url, timeout=20):
        u = urllib.parse.urlsplit(url)
        secure = u.scheme == "wss"
        host, port = u.hostname, u.port or (443 if secure else 80)
        raw = socket.create_connection((host, port), timeout=timeout)
        self.s = ssl.create_default_context().wrap_socket(raw, server_hostname=host) if secure else raw
        self.s.settimeout(timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        path = (u.path or "/") + ("?" + u.query if u.query else "")
        self.s.sendall(("GET %s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: %s\r\n"
                        "Sec-WebSocket-Version: 13\r\nUser-Agent: %s\r\n\r\n" % (path, host, key, UA)).encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            c = self.s.recv(4096)
            if not c:
                raise ConnectionError("handshake: connection closed")
            buf += c
            if len(buf) > 65536:
                raise ConnectionError("handshake: too long")
        head, self.buf = buf.split(b"\r\n\r\n", 1)
        status = head.split(b"\r\n", 1)[0].decode("latin-1")
        if " 101" not in status:
            raise ConnectionError("handshake: " + status)
        self.parts = []

    def _need(self, n):
        while len(self.buf) < n:                     # timeout болсо буфер бузулбайт: кадр толук келгенде гана кесилет
            c = self.s.recv(65536)
            if not c:
                raise ConnectionError("closed")
            self.buf += c

    def send(self, data, opcode=1):
        if isinstance(data, str):
            data = data.encode("utf-8")
        n = len(data)
        hdr = bytes([0x80 | opcode])
        if n < 126:
            hdr += bytes([0x80 | n])
        elif n < 65536:
            hdr += bytes([0x80 | 126]) + struct.pack(">H", n)
        else:
            hdr += bytes([0x80 | 127]) + struct.pack(">Q", n)
        mask = os.urandom(4)
        self.s.sendall(hdr + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def recv(self):
        """Бир текст билдирүү (str), же timeout болсо None."""
        while True:
            try:
                self._need(2)
                b1, b2 = self.buf[0], self.buf[1]
                ln, off = b2 & 0x7F, 2
                if ln == 126:
                    self._need(4)
                    ln, off = struct.unpack(">H", self.buf[2:4])[0], 4
                elif ln == 127:
                    self._need(10)
                    ln, off = struct.unpack(">Q", self.buf[2:10])[0], 10
                masked = b2 & 0x80
                self._need(off + (4 if masked else 0) + ln)
            except socket.timeout:
                return None
            if masked:
                m = self.buf[off:off + 4]
                off += 4
                payload = bytes(b ^ m[i % 4] for i, b in enumerate(self.buf[off:off + ln]))
            else:
                payload = self.buf[off:off + ln]
            self.buf = self.buf[off + ln:]
            op, fin = b1 & 0x0F, b1 & 0x80
            if op == 0x9:
                self.send(payload, 0xA)
                continue
            if op == 0xA:
                continue
            if op == 0x8:
                raise ConnectionError("closed by server")
            self.parts.append(payload)
            if fin:
                data, self.parts = b"".join(self.parts), []
                return data.decode("utf-8", "replace")

    def close(self):
        try:
            self.s.close()
        except Exception:  # noqa: BLE001
            pass


# ======================================================================
#  Ликвидациялар: мүнөттүк чогултуу
# ======================================================================
class Liq:
    KEEP_MIN = 26 * 60

    def __init__(self, db=None):
        self.db, self.lock = db, threading.RLock()
        self.mins = {}                                  # мүнөт → [лонг $, шорт $, саны]
        self.events = deque(maxlen=400)                 # ≥ $100 миң: dict
        self.seen = {"binance": 0, "bybit": 0}
        self.err = {"binance": "", "bybit": ""}
        if db is not None:
            try:
                st = db.kv("liq_state") or {}
                self.mins = {int(k): v for k, v in (st.get("m") or {}).items()}
                self.events.extend(st.get("e") or [])
            except Exception:  # noqa: BLE001
                pass

    def add(self, ex, sym, is_long, usd, px, t=None):
        t = t or now_ms()
        if not usd or usd <= 0:
            return
        with self.lock:
            m = self.mins.setdefault(t // MIN, [0.0, 0.0, 0])
            m[0 if is_long else 1] += usd
            m[2] += 1
            self.seen[ex] = t
            if usd >= 100_000:
                self.events.append({"t": t, "ex": ex, "sym": sym, "long": bool(is_long), "usd": round(usd), "px": px})

    def window(self, ms):
        since = (now_ms() - ms) // MIN
        lo = sh = n = 0
        with self.lock:
            for k, v in self.mins.items():
                if k >= since:
                    lo, sh, n = lo + v[0], sh + v[1], n + v[2]
            top = max((e for e in self.events if e["t"] >= now_ms() - ms), key=lambda e: e["usd"], default=None)
            first = min(self.mins) * MIN if self.mins else now_ms()
        cov = min(ms, now_ms() - first) / HOUR                # канча саат байкалды (бот кайра иштесе — азыраак)
        return {"long": lo, "short": sh, "total": lo + sh, "n": n, "top": top, "cov_h": cov}

    def save(self):
        cut = now_ms() // MIN - self.KEEP_MIN
        with self.lock:
            self.mins = {k: v for k, v in self.mins.items() if k >= cut}
            st = {"m": {str(k): [round(v[0]), round(v[1]), v[2]] for k, v in self.mins.items()},
                  "e": [e for e in self.events if e["t"] >= now_ms() - 26 * HOUR]}
        if self.db is not None:
            self.db.kv_set("liq_state", st)

    def live(self):
        """Ар бир биржадан акыркы 10 мүнөттө маалымат келдиби."""
        return {k: (now_ms() - v < 10 * MIN) for k, v in self.seen.items()}


def run_binance(liq, stop):
    i = 0
    while not stop.is_set():
        url = BINANCE_WS[i % len(BINANCE_WS)]
        try:
            ws = WS(url, timeout=30)
            liq.err["binance"] = ""
            while not stop.is_set():
                msg = ws.recv()
                if msg is None:
                    continue
                d = json.loads(msg)
                o = d.get("o") or (d.get("data") or {}).get("o")
                if not o:
                    continue
                q = float(o.get("z") or o.get("q") or 0)
                px = float(o.get("ap") or 0) or float(o.get("p") or 0)
                # SELL — лонг позиция мажбурлап сатылды (лонг ликвидацияланды), BUY — шорт
                liq.add("binance", o.get("s", "?"), o.get("S") == "SELL", q * px, px, int(o.get("T") or d.get("E") or now_ms()))
        except Exception as e:  # noqa: BLE001
            liq.err["binance"] = str(e)[:120]
            i += 1
            stop.wait(15)


def bybit_symbols(n=40):
    try:
        rows = get_json("https://api.bybit.com/v5/market/tickers?category=linear")["result"]["list"]
        rows = [r for r in rows if r["symbol"].endswith("USDT")]
        rows.sort(key=lambda r: -float(r.get("turnover24h") or 0))
        return [r["symbol"] for r in rows[:n]]
    except Exception:  # noqa: BLE001
        return [b + "USDT" for b in MP.settings()[0]]


def run_bybit(liq, stop):
    while not stop.is_set():
        try:
            syms = bybit_symbols()
            ws = WS(BYBIT_WS, timeout=20)
            for i in range(0, len(syms), 10):
                ws.send(json.dumps({"op": "subscribe", "args": ["allLiquidation." + s for s in syms[i:i + 10]]}))
            liq.err["bybit"] = ""
            last_ping, started = time.time(), time.time()
            while not stop.is_set() and time.time() - started < 6 * 3600:    # 6 саатта бир тизмени жаңыртуу
                if time.time() - last_ping > 18:
                    ws.send('{"op":"ping"}')
                    last_ping = time.time()
                msg = ws.recv()
                if msg is None:
                    continue
                d = json.loads(msg)
                if not str(d.get("topic", "")).startswith("allLiquidation"):
                    continue
                for it in d.get("data") or []:
                    v, px = float(it.get("v") or 0), float(it.get("p") or 0)
                    # Bybit: «Buy» — лонг позиция ликвидацияланды (документация)
                    liq.add("bybit", it.get("s", "?"), it.get("S") == "Buy", v * px, px, int(it.get("T") or now_ms()))
            ws.close()
        except Exception as e:  # noqa: BLE001
            liq.err["bybit"] = str(e)[:120]
            stop.wait(15)


# ======================================================================
#  Киттер
# ======================================================================
class Whales:
    def __init__(self, db=None):
        self.db, self.lock = db, threading.RLock()
        self.events = deque(maxlen=300)
        self.seen_hash = deque(maxlen=2000)
        self.last, self.err = 0, ""
        self.src = "Whale Alert" if os.environ.get("WHALE_ALERT_KEY") else "BTC блокчейн"
        if db is not None:
            try:
                self.events.extend(db.kv("whale_state") or [])
            except Exception:  # noqa: BLE001
                pass

    def add(self, ev):
        with self.lock:
            if ev["hash"] in self.seen_hash:
                return
            self.seen_hash.append(ev["hash"])
            self.events.append(ev)

    def count(self, ms):
        with self.lock:
            return sum(1 for e in self.events if e["t"] >= now_ms() - ms)

    def save(self):
        if self.db is not None:
            with self.lock:
                self.db.kv_set("whale_state", [e for e in self.events if e["t"] >= now_ms() - 26 * HOUR])


_PX = {"t": 0, "v": None}


def btc_price():
    if time.time() - _PX["t"] < 60 and _PX["v"]:
        return _PX["v"]
    for url in ("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", "https://data-api.binance.vision/api/v3/ticker/price?symbol=BTCUSDT"):
        try:
            _PX.update(t=time.time(), v=float(get_json(url)["price"]))
            return _PX["v"]
        except Exception:  # noqa: BLE001
            continue
    try:
        _PX.update(t=time.time(), v=float(get_json("https://api.bybit.com/v5/market/tickers?category=spot&symbol=BTCUSDT")["result"]["list"][0]["lastPrice"]))
    except Exception:  # noqa: BLE001
        pass
    return _PX["v"]


def btc_tx_event(x, min_btc):
    """blockchain.info utx → кит окуясы же None. «Которулган» = кирген даректерге кайтпаган чыгыштар (сдача эсепке кирбейт)."""
    ins = {}
    for i in x.get("inputs") or []:
        po = i.get("prev_out") or {}
        if po.get("addr"):
            ins[po["addr"]] = ins.get(po["addr"], 0) + int(po.get("value") or 0)
    outs = [(o.get("addr"), int(o.get("value") or 0)) for o in x.get("out") or [] if o.get("addr")]
    moved = sum(v for a, v in outs if a not in ins) / 1e8
    if moved < min_btc:
        return None
    to_addr, to_v = max(((a, v) for a, v in outs if a not in ins), key=lambda p: p[1], default=(None, 0))
    from_addr = max(ins.items(), key=lambda p: p[1])[0] if ins else None
    px = btc_price()
    return {"t": now_ms(), "hash": x.get("hash", ""), "chain": "bitcoin", "sym": "BTC", "amount": round(moved, 2),
            "usd": round(moved * px) if px else None,
            "from": BTC_LABELS.get(from_addr) or next((BTC_LABELS[a] for a in ins if a in BTC_LABELS), None),
            "to": BTC_LABELS.get(to_addr), "from_addr": from_addr, "to_addr": to_addr, "src": "blockchain"}


def run_btc_whales(wh, stop):
    while not stop.is_set():
        try:
            ws = WS(BTC_WS, timeout=30)
            ws.send('{"op":"unconfirmed_sub"}')
            wh.err = ""
            last_ping = time.time()
            while not stop.is_set():
                if time.time() - last_ping > 25:
                    ws.send('{"op":"ping"}')
                    last_ping = time.time()
                msg = ws.recv()
                if msg is None:
                    continue
                d = json.loads(msg)
                if d.get("op") != "utx":
                    continue
                wh.last = now_ms()
                ev = btc_tx_event(d.get("x") or {}, WHALE_BTC)
                if ev:
                    wh.add(ev)
        except Exception as e:  # noqa: BLE001
            wh.err = str(e)[:120]
            stop.wait(20)


def run_whale_alert(wh, stop, key):
    """Whale Alert API v1 (ачкыч менен): биржалардын аттары менен. Ар 60 с."""
    start = int(time.time()) - 600
    while not stop.is_set():
        try:
            q = urllib.parse.urlencode({"api_key": key, "min_value": int(WHALE_USD), "start": start})
            d = get_json("https://api.whale-alert.io/v1/transactions?" + q, timeout=20)
            if d.get("result") != "success":
                raise RuntimeError(d.get("message") or "Whale Alert: error")
            wh.err, wh.last = "", now_ms()
            for t in d.get("transactions") or []:
                start = max(start, int(t.get("timestamp") or 0))
                fr, to = t.get("from") or {}, t.get("to") or {}
                wh.add({"t": int(t.get("timestamp") or time.time()) * 1000, "hash": t.get("hash", ""), "chain": t.get("blockchain", ""),
                        "sym": str(t.get("symbol", "")).upper(), "amount": t.get("amount"), "usd": t.get("amount_usd"),
                        "from": (fr.get("owner") or "").title() or None, "to": (to.get("owner") or "").title() or None,
                        "from_addr": fr.get("address"), "to_addr": to.get("address"), "src": "whalealert"})
        except Exception as e:  # noqa: BLE001
            wh.err = str(e)[:120]
        stop.wait(60)


# ======================================================================
#  Форматтоо жана тексттер (KG / RU)
# ======================================================================
def usd(v, lang="kg"):
    if v is None:
        return "—"
    a = abs(v)
    for lim, ky, ru in ((1e12, "трлн", "трлн"), (1e9, "млрд", "млрд"), (1e6, "млн", "млн"), (1e3, "миң", "тыс.")):
        if a >= lim:
            x = v / lim
            s = ("%.2f" % x) if x < 10 else ("%.1f" % x) if x < 100 else ("%.0f" % x)
            s = s.rstrip("0").rstrip(".") if "." in s else s
            return "$%s %s" % (s, ru if lang == "ru" else ky)
    return "$%d" % round(v)


def price(v):
    if v is None:
        return "—"
    if v >= 1000:
        return "$" + "{:,.0f}".format(v).replace(",", " ")
    if v >= 1:
        return "$%.2f" % v
    return "$%.4g" % v


def pct(v):
    return MP.pct(v) if v is not None else "—"


def rng(seed, lst):
    return random.Random(seed).choice(lst)


def day_seed():
    return dt.datetime.now(BISHKEK).strftime("%Y%m%d")


JOKE = {
    "liq_big": [
        ("Кимдир бирөөнүн бүгүнкү кечки тамагы абдан кымбат болуп калды 🍽", "У кого-то сегодня очень дорогой ужин 🍽"),
        ("Плечо ×100 — стратегия эмес, лотерея 🎰", "Плечо ×100 — это не стратегия, а лотерея 🎰"),
        ("Рынок эскертпейт — ал жөн эле алат 🤷", "Рынок не предупреждает — он просто забирает 🤷"),
        ("Стоп-лосс коюлбаса, аны рынок өзү коёт 🧯", "Не поставил стоп-лосс — рынок поставит его сам 🧯"),
    ],
    "liq_wave_long": [
        ("Лонгчулар бүгүн «өйдө» деп ишеништи, рынок «ылдый» деп жооп берди 🎢", "Лонгисты верили в «вверх», рынок ответил «вниз» 🎢"),
        ("Өсүүгө ставка кылгандар үчүн оор саат болду — плечо дос эмес 🔥", "Тяжёлый час для ставивших на рост — плечо не друг 🔥"),
    ],
    "liq_wave_short": [
        ("Шортчуларды рынок лимондой сыкты 🍋", "Шортистов рынок выжал как лимон 🍋"),
        ("«Эми түшөт» дегендер үчүн рынок сюрприз даярдады 🚀", "Для тех, кто ждал падения, рынок приготовил сюрприз 🚀"),
    ],
    "whale": [
        ("Кит суудан чыкты — майда балыктар, абайлагыла 🐟", "Кит всплыл — мелкая рыба, осторожно 🐟"),
        ("Бирөө диванынын астынан ушунча биткоин таптыбы? 🛋", "Кто-то нашёл биткоины под диваном? 🛋"),
        ("Мындай которууда комиссияны да кит төлөйт 🐳", "Комиссию за такой перевод тоже платит кит 🐳"),
    ],
    "wild_dn": [("Рынок бүгүн лифт менен түштү — баскычты ким басканы белгисиз 🛗", "Рынок сегодня ехал вниз на лифте — кто нажал кнопку, неизвестно 🛗")],
    "wild_up": [("Букалар бүгүн шайыр: графиктер тоого чыгып баратат 🐂⛰", "Быки в ударе: графики лезут в гору 🐂⛰")],
    "wild": [("Бүгүн рынок аттракцион болду: өйдө-ылдый, курун бекем байлаңыз 🎢", "Сегодня рынок был аттракционом: вверх-вниз, пристегнитесь 🎢")],
    "calm": [("Рынок бүгүн чай ичип отурду ☕ — шамдар кыска, кыймыл андан да аз.", "Рынок сегодня пил чай ☕ — свечи короткие, движения ещё меньше."),
             ("Тынч күн: трейдерлер графикке караганча, график аларга карап турду 😴", "Тихий день: трейдеры смотрели на график, график смотрел на них 😴")],
    "up": [("Жашыл күн 🌿 — бирок эртең да жашыл болот деп ким айтты?", "Зелёный день 🌿 — но кто сказал, что завтра тоже?")],
    "dn": [("Кызыл күн 🍅 — дем алыңыз, депозит качпайт (эгер плечо болбосо).", "Красный день 🍅 — выдохните, депозит не убежит (если без плеча).")],
    "flat": [("Кадимки күн: бир аз өйдө, бир аз ылдый — рынок жөн эле дем алып жатат 🫁", "Обычный день: немного вверх, немного вниз — рынок просто дышит 🫁")],
}

RISK = ("", "")   # автор: эскертүүлөрсүз, жандуу текст
EXN = {"binance": "Binance", "bybit": "Bybit"}


def j(key, seed, lang):
    k, r = rng(seed, JOKE[key])
    return r if lang == "ru" else k


def liq_big_msg(e, lang, seed):
    ru = lang == "ru"
    side = ("лонг (ставка на рост)" if e["long"] else "шорт (ставка на падение)") if ru else ("лонг (өсүүгө)" if e["long"] else "шорт (түшүүгө)")
    sym = e["sym"].replace("USDT", "")
    if ru:
        return ("💥 <b>Крупная ликвидация</b>\n%s · <b>%s</b>: %s позиция на <b>%s</b> закрыта принудительно (цена ≈ %s).\n\n%s\n\n"
                "ℹ️ Ликвидация — биржа сама закрывает позицию с плечом, когда залога не хватает. Защита — маленькое плечо и стоп-лосс.\n%s") % (
            EXN.get(e["ex"], e["ex"]), E(sym), side, usd(e["usd"], "ru"), price(e.get("px")), j("liq_big", seed, "ru"), RISK[1])
    return ("💥 <b>Ири ликвидация</b>\n%s · <b>%s</b>: <b>%s</b> %s позиция мажбурлап жабылды (баа ≈ %s).\n\n%s\n\n"
            "ℹ️ Ликвидация — күрөө жетпей калганда биржа плечо менен ачылган позицияны өзү жабат. Коргоо — кичине плечо жана стоп-лосс.\n%s") % (
        EXN.get(e["ex"], e["ex"]), E(sym), usd(e["usd"]), side, price(e.get("px")), j("liq_big", seed, "kg"), RISK[0])


def liq_wave_msg(w, lang, seed):
    key = "liq_wave_long" if w["long"] >= w["short"] else "liq_wave_short"
    top = w.get("top")
    if lang == "ru":
        t = ("🔥 <b>Волна ликвидаций</b>\nЗа последний час принудительно закрыто позиций на <b>%s</b>:\n🔴 лонги %s · 🟢 шорты %s\n") % (
            usd(w["total"], "ru"), usd(w["long"], "ru"), usd(w["short"], "ru"))
        if top:
            t += "Крупнейшая: %s %s %s (%s)\n" % (E(top["sym"].replace("USDT", "")), "лонг" if top["long"] else "шорт", usd(top["usd"], "ru"), EXN.get(top["ex"], top["ex"]))
        return t + "<i>Данные Binance + Bybit, то, что видим мы (не весь рынок).</i>\n\n%s\n%s" % (j(key, seed, "ru"), RISK[1])
    t = ("🔥 <b>Ликвидация толкуну</b>\nАкыркы 1 саатта <b>%s</b> позиция мажбурлап жабылды:\n🔴 лонг %s · 🟢 шорт %s\n") % (
        usd(w["total"]), usd(w["long"]), usd(w["short"]))
    if top:
        t += "Эң ирииси: %s %s %s (%s)\n" % (E(top["sym"].replace("USDT", "")), "лонг" if top["long"] else "шорт", usd(top["usd"]), EXN.get(top["ex"], top["ex"]))
    return t + "<i>Binance + Bybit маалыматы, биз байкаганы (бүт рынок эмес).</i>\n\n%s\n%s" % (j(key, seed, "kg"), RISK[0])


def tx_url(e):
    if e.get("chain") == "bitcoin" and e.get("hash"):
        return "https://mempool.space/tx/" + e["hash"]
    if e.get("chain") == "ethereum" and e.get("hash"):
        return "https://etherscan.io/tx/0x" + e["hash"].removeprefix("0x")
    if e.get("chain") == "tron" and e.get("hash"):
        return "https://tronscan.org/#/transaction/" + e["hash"]
    return None


def whale_msg(e, lang, seed):
    ru = lang == "ru"
    unk = "неизвестный кошелёк" if ru else "белгисиз капчык"
    fr, to = e.get("from") or unk, e.get("to") or unk
    if e.get("to") and not e.get("from"):
        why = ("Зашло на биржу — иногда это подготовка к продаже." if ru else "Биржага кирди — кээде бул сатууга даярдык болот.")
    elif e.get("from") and not e.get("to"):
        why = ("Ушло с биржи — часто это вывод на долгое хранение." if ru else "Биржадан чыкты — көбүнчө узак сактоого.")
    elif e.get("from") and e.get("to"):
        why = ("Перевод между известными кошельками бирж." if ru else "Белгилүү биржа капчыктарынын ортосундагы которуу.")
    else:
        why = ("Обе стороны неизвестны — возможно, внутренний перевод (кастодиан, биржа)." if ru
               else "Эки тарап тең белгисиз — балким ички которуу (кастодиан, биржа).")
    amt = ("{:,.0f}".format(e["amount"]).replace(",", " ") if isinstance(e.get("amount"), (int, float)) else E(e.get("amount")))
    link = tx_url(e)
    src = ("Whale Alert" if e.get("src") == "whalealert" else ("блокчейн, ещё не подтверждена" if ru else "блокчейн, тастыктала элек"))
    if ru:
        t = "🐳 <b>Кит пошевелился</b>\nПереведено <b>%s %s</b> (≈ %s)\nОткуда: %s\nКуда: %s\n\n%s\n" % (amt, E(e["sym"]), usd(e.get("usd"), "ru"), E(fr), E(to), why)
    else:
        t = "🐳 <b>Кит кыймылдады</b>\n<b>%s %s</b> (≈ %s) которулду\nКимден: %s\nКимге: %s\n\n%s\n" % (amt, E(e["sym"]), usd(e.get("usd")), E(fr), E(to), why)
    if link:
        t += '🔗 <a href="%s">%s</a> · %s\n' % (E(link), "Транзакция" if ru else "Транзакция", src)
    return t + "\n" + j("whale", seed, "ru" if ru else "kg")


# ---------- VIP жарнамасы ----------
PROMO = [
    ("🔐 <b>TRADER KG VIP — ичинде эмне бар?</b>\n"
     "⭐ ИИ сигналдары: BinoDex (1–5 мүн) жана BingX фьючерс — ар биринин жанында тесттеги тактык, кийин ✓/✗ жыйынтыгы\n"
     "📰 Маанилүү жаңылыктар жана экономикалык анонстор — эртерээк\n"
     "💥 Ликвидациялар, 🐳 киттер, 📊 күндүн жыйынтыгы\n"
     "💬 Жабык каналдар жана суроо-жооп\n\n"
     "Кантип кирет: биздин шилтеме менен катталуу → эсепти толуктоо → ID'ни ботко → бот текшерип, өзү шилтеме берет.\n",
     "🔐 <b>TRADER KG VIP — что внутри?</b>\n"
     "⭐ ИИ-сигналы: BinoDex (1–5 мин) и фьючерсы BingX — у каждого точность на тесте, потом итог ✓/✗\n"
     "📰 Важные новости и экономические анонсы — раньше\n"
     "💥 Ликвидации, 🐳 киты, 📊 итоги дня\n"
     "💬 Закрытые каналы и вопросы-ответы\n\n"
     "Как попасть: регистрация по нашей ссылке → пополнение счёта → ID в бот → бот проверит и сам даст ссылку.\n"),
    ("🗺 <b>Сигналсыз соода — картасыз саякат.</b>\n"
     "TRADER KG VIP'те карта бар: ИИ сигналдары, рыноктун абалы, жаңылыктар — баары бир жерде.\n"
     "Бирок рулду өзүңүз кармайсыз 😉 Адегенде демо-эсеп, анан кичине сумма.\n\n"
     "Кирүү — ботто: «📝 Катталуу».",
     "🗺 <b>Торговля без сигналов — путешествие без карты.</b>\n"
     "В TRADER KG VIP карта есть: ИИ-сигналы, состояние рынка, новости — всё в одном месте.\n"
     "Но руль держите сами 😉 Сначала демо-счёт, потом небольшая сумма.\n\n"
     "Вход — в боте: «📝 Регистрация»."),
    ("🤝 <b>VIP акысыз — эмне үчүн?</b>\n"
     "Биз BingX жана BinoDex'тин өнөктөшүбүз: сиз биздин шилтеме менен катталсаңыз, брокер бизге партнёрдук сыйакы төлөйт. "
     "Сизден бизге төлөм жок — эсепти толуктоо өз аккаунтуңузга кетет.\n\n"
     "Ичинде: ⭐ сигналдар (✓/✗ жыйынтыгы менен), 📰 жаңылыктар, 💥 ликвидациялар, 🐳 киттер.",
     "🤝 <b>Почему VIP бесплатный?</b>\n"
     "Мы партнёры BingX и BinoDex: если вы регистрируетесь по нашей ссылке, брокер платит нам партнёрское вознаграждение. "
     "Вы нам ничего не платите — пополнение идёт на ваш собственный счёт.\n\n"
     "Внутри: ⭐ сигналы (с итогом ✓/✗), 📰 новости, 💥 ликвидации, 🐳 киты."),
    ("📏 <b>VIP'те жашырбайбыз</b>: ар бир сигналдан кийин ✓ же ✗ чыгат. Минус да болот — ошондуктан тобокелдиктин эрежелери биринчи.\n"
     "Чынчыл статистика + ИИ + жаңылыктар = TRADER KG VIP.\n\nКирүү — ботто: «📝 Катталуу»",
     "📏 <b>В VIP мы не прячем</b>: после каждого сигнала — ✓ или ✗. Минусы тоже бывают — поэтому правила риска на первом месте.\n"
     "Честная статистика + ИИ + новости = TRADER KG VIP.\n\nВход — в боте: «📝 Регистрация»"),
]


# ======================================================================
#  Күндүн жыйынтыгы: маалымат
# ======================================================================
FNG = {"extreme fear": ("Катуу коркуу", "Сильный страх"), "fear": ("Коркуу", "Страх"), "neutral": ("Нейтралдуу", "Нейтрально"),
       "greed": ("Ачкөздүк", "Жадность"), "extreme greed": ("Катуу ачкөздүк", "Сильная жадность")}


def binance_get(path):
    last = None
    for base in MP.BINANCE:
        try:
            return get_json(base + path)
        except Exception as e:  # noqa: BLE001
            last = e
    raise RuntimeError("Binance: %s" % last)


def day_data(liq=None, whales=None):
    """Акыркы 24 саат. Ар бир бөлүк өзүнчө: булак иштебесе — ошол сап чыкпайт."""
    d = {"t": now_ms(), "src": []}
    basket = MP.settings()[0]
    try:
        syms = urllib.parse.quote(json.dumps([b + "USDT" for b in basket], separators=(",", ":")))
        rows = binance_get("/api/v3/ticker/24hr?symbols=" + syms)
        coins = {}
        for r in rows:
            last, o = float(r["lastPrice"]), float(r["openPrice"])
            hi, lo = float(r["highPrice"]), float(r["lowPrice"])
            coins[r["symbol"][:-4]] = {"last": last, "chg": float(r["priceChangePercent"]), "range": (hi / lo - 1) * 100 if lo else None,
                                       "vol": float(r["quoteVolume"])}
        d["coins"], d["src"] = coins, d["src"] + ["Binance"]
    except Exception:  # noqa: BLE001
        try:
            p = MP.pulse()
            d["coins"] = {k: {"last": v.get("last"), "chg": v.get("c24"), "range": None} for k, v in p["rows"].items()}
            d["src"].append(p["src"])
        except Exception:  # noqa: BLE001
            d["coins"] = {}
    try:                                                   # BTC: бүгүнкү диапазон 30 күндүн орточосуна салыштырмалуу
        k = binance_get("/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=31")
        rngs = [(float(x[2]) / float(x[3]) - 1) * 100 for x in k[:-1] if float(x[3]) > 0]
        h = binance_get("/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=25")
        closes = [float(x[4]) for x in h]
        rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
        hi, lo = max(float(x[2]) for x in h[-24:]), min(float(x[3]) for x in h[-24:])
        d["btc_range"] = (hi / lo - 1) * 100
        d["btc_avg_range"] = statistics.mean(rngs[-30:]) if rngs else None
        d["btc_rv"] = statistics.pstdev(rets) * math.sqrt(24) * 100 if len(rets) > 5 else None
    except Exception:  # noqa: BLE001
        pass
    try:
        f = get_json("https://api.alternative.me/fng/?limit=2")["data"]
        d["fng"] = {"v": int(f[0]["value"]), "cls": f[0]["value_classification"].lower(), "prev": int(f[1]["value"]) if len(f) > 1 else None}
    except Exception:  # noqa: BLE001
        pass
    try:
        g = get_json("https://api.coingecko.com/api/v3/global")["data"]
        d["cap"] = {"usd": g["total_market_cap"]["usd"], "chg": g["market_cap_change_percentage_24h_usd"], "btc_dom": g["market_cap_percentage"]["btc"]}
    except Exception:  # noqa: BLE001
        pass
    if liq is not None:
        w = liq.window(24 * HOUR)
        if w["n"]:
            d["liq"] = w
    if whales is not None:
        d["whales"] = whales.count(24 * HOUR)
    c = d.get("coins") or {}
    ch = [v["chg"] for v in c.values() if v.get("chg") is not None]
    d["up"], d["dn"] = sum(1 for x in ch if x > 0), sum(1 for x in ch if x < 0)
    d["median"] = statistics.median(ch) if ch else None
    if c:
        best = max(c.items(), key=lambda kv: kv[1]["chg"] if kv[1].get("chg") is not None else -1e9)
        worst = min(c.items(), key=lambda kv: kv[1]["chg"] if kv[1].get("chg") is not None else 1e9)
        d["best"], d["worst"] = (best[0], best[1]["chg"]), (worst[0], worst[1]["chg"])
    return d


def mood(d):
    ratio = (d["btc_range"] / d["btc_avg_range"]) if d.get("btc_range") and d.get("btc_avg_range") else None
    m = d.get("median") or 0
    if ratio is not None and ratio >= 1.5:
        return ("wild_dn" if m <= -2 else "wild_up" if m >= 2 else "wild"), ratio
    if ratio is not None and ratio <= 0.7:
        return "calm", ratio
    return ("up" if m >= 1 else "dn" if m <= -1 else "flat"), ratio


VOL_NAME = {"wild": ("жогору", "высокая"), "calm": ("төмөн", "низкая"), "norm": ("кадимки", "обычная")}


def vol_level(ratio):
    return "wild" if ratio is not None and ratio >= 1.5 else "calm" if ratio is not None and ratio <= 0.7 else "norm"


def day_msg(d, lang, seed=None):
    ru = lang == "ru"
    li = 1 if ru else 0
    seed = seed or day_seed()
    mk, ratio = mood(d)
    c = d.get("coins") or {}
    date = dt.datetime.fromtimestamp(d["t"] / 1000, BISHKEK).strftime("%d.%m")
    L = ["📊 <b>%s</b> · %s (%s)" % ("Итоги дня" if ru else "Күндүн жыйынтыгы", date, "последние 24 ч" if ru else "акыркы 24 саат"),
         "<i>%s</i>" % j(mk, seed, lang), ""]
    for sym, ic in (("BTC", "₿"), ("ETH", "Ξ")):
        v = c.get(sym)
        if v:
            extra = (" · %s %.1f%%" % ("диапазон" if ru else "диапазон", v["range"])) if v.get("range") else ""
            L.append("%s %s <b>%s</b> %s%s" % (ic, sym, price(v["last"]), pct(v.get("chg")), extra))
    if ratio is not None:
        L.append("🌡 %s: <b>%s</b> — %s ×%.1f" % ("Волатильность" if ru else "Волатилдүүлүк", VOL_NAME[vol_level(ratio)][li],
                                               "диапазон BTC к среднему за 30 дней" if ru else "BTC диапазону 30 күндүн орточосуна", ratio))
    if d.get("best") and d.get("worst") and d["best"][0] != d["worst"][0]:
        L.append("🏆 %s: %s %s · 🐢 %s: %s %s" % ("Лидер" if ru else "Лидер", d["best"][0], pct(d["best"][1]),
                                                 "аутсайдер" if ru else "аутсайдер", d["worst"][0], pct(d["worst"][1])))
    if c:
        L.append(("📈 выросли %d · 📉 упали %d (из %d крупнейших)" if ru else "📈 %d өстү · 📉 %d түштү (%d ири монетадан)") % (d["up"], d["dn"], len(c)))
    lq = d.get("liq")
    if lq:
        L.append("💥 %s: <b>%s</b> — 🔴 %s %s · 🟢 %s %s" % ("Ликвидации" if ru else "Ликвидациялар", usd(lq["total"], lang),
                                                         "лонги" if ru else "лонг", usd(lq["long"], lang), "шорты" if ru else "шорт", usd(lq["short"], lang)))
        if lq.get("cov_h", 24) < 23:
            L.append(("   <i>бот наблюдал только %.0f ч из 24</i>" if ru else "   <i>бот 24 сааттын %.0f саатын гана байкады</i>") % max(1, lq["cov_h"]))
        if lq.get("top"):
            t = lq["top"]
            L.append("   %s: %s %s %s (%s)" % ("крупнейшая" if ru else "эң ирииси", t["sym"].replace("USDT", ""), "лонг" if t["long"] else "шорт",
                                             usd(t["usd"], lang), EXN.get(t["ex"], t["ex"])))
    if d.get("whales") is not None:
        L.append(("🐳 Переводы китов (≥%d BTC): %d" if ru else "🐳 Кит которуулары (≥%d BTC): %d") % (WHALE_BTC, d["whales"]))
    if d.get("fng"):
        f = d["fng"]
        nm = FNG.get(f["cls"], (f["cls"], f["cls"]))[li]
        prev = (" (%s %d)" % ("вчера" if ru else "кечээ", f["prev"])) if f.get("prev") is not None else ""
        L.append("😱 %s: <b>%d</b> — %s%s" % ("Индекс страха и жадности" if ru else "Коркуу/ачкөздүк индекси", f["v"], nm, prev))
    if d.get("cap"):
        cp = d["cap"]
        L.append("🌐 %s: %s (%s) · %s %.1f%%" % ("Капитализация крипты" if ru else "Крипто капитализациясы", usd(cp["usd"], lang), pct(cp["chg"]),
                                               "доля BTC" if ru else "BTC үлүшү", cp["btc_dom"]))
    if lq:
        k = "liq_wave_long" if lq["long"] >= lq["short"] * 1.5 else "liq_wave_short" if lq["short"] >= lq["long"] * 1.5 else None
        if k:
            L += ["", j(k, seed + "l", lang)]
    src = ", ".join(d["src"] + (["Binance/Bybit (ликвидации)" if ru else "Binance/Bybit (ликвидациялар)"] if lq else [])
                    + (["alternative.me"] if d.get("fng") else []) + (["CoinGecko"] if d.get("cap") else []))
    L += ["", "<i>%s: %s</i>" % ("Источники" if ru else "Булактар", E(src)), RISK[li]]
    return "\n".join(L)


# ---------- сүрөт ----------
def day_card(d, lang):
    import tg_cards as TC
    from PIL import ImageDraw
    ru = lang == "ru"
    up = (d.get("median") or 0) >= 0
    img = TC.background(TC.C["mint"] if up else TC.C["red"])
    dr = ImageDraw.Draw(img)
    TC.brand(dr, lang, d["t"])
    C, S, font = TC.C, TC.S, TC.font
    dr.text(S(48, 118), "ИТОГИ ДНЯ" if ru else "КҮНДҮН ЖЫЙЫНТЫГЫ", font=font(46, True), fill=C["text"])
    dr.text(S(48, 176), "последние 24 часа · крипторынок" if ru else "акыркы 24 саат · крипто рыногу", font=font(22), fill=C["muted"])
    mk, ratio = mood(d)

    def panel(x0, y0, x1, y1):
        dr.rounded_rectangle(S(x0, y0, x1, y1), radius=18 * TC.K, fill=TC.mix(C["bg"], C["panel"], 0.85), outline=C["line"], width=2 * TC.K)

    c = d.get("coins") or {}
    for i, sym in enumerate(("BTC", "ETH")):
        x0 = 48 + i * 400
        panel(x0, 222, x0 + 380, 400)
        v = c.get(sym)
        dr.text(S(x0 + 24, 244), sym, font=font(24, True), fill=C["muted"])
        if v:
            dr.text(S(x0 + 24, 280), price(v["last"]), font=TC.fit(dr, price(v["last"]), 52, 330), fill=C["text"])
            ch = v.get("chg") or 0
            col = C["mint"] if ch > 0 else C["red"] if ch < 0 else C["muted"]
            TC.tri(dr, x0 + 36, 366, 11, ch >= 0, col)
            dr.text(S(x0 + 56, 352), pct(ch), font=font(28, True), fill=col)
            if v.get("range"):
                dr.text(S(x0 + 356, 358), ("диапазон %.1f%%" % v["range"]), font=font(20), fill=C["muted"], anchor="ra")
    # Коркуу/ачкөздүк
    panel(848, 222, 1232, 400)
    dr.text(S(872, 244), "СТРАХ / ЖАДНОСТЬ" if ru else "КОРКУУ / АЧКӨЗДҮК", font=font(22, True), fill=C["muted"])
    f = d.get("fng")
    if f:
        val = f["v"]
        col = TC.mix(C["red"], C["mint"], val / 100)
        dr.text(S(872, 276), str(val), font=font(64, True), fill=col)
        dr.text(S(872 + TC.tw(dr, str(val), font(64, True)) + 16, 300), FNG.get(f["cls"], (f["cls"], f["cls"]))[1 if ru else 0],
                font=TC.fit(dr, FNG.get(f["cls"], (f["cls"],) * 2)[1 if ru else 0], 26, 220, bold=True), fill=C["text"])
        bx0, bx1, by = 872, 1208, 372
        for k in range(40):
            dr.rectangle(S(bx0 + (bx1 - bx0) * k / 40, by, bx0 + (bx1 - bx0) * (k + 1) / 40 - 1, by + 10), fill=TC.mix(C["red"], C["mint"], k / 39))
        mx = bx0 + (bx1 - bx0) * val / 100
        dr.ellipse(S(mx - 9, by - 4, mx + 9, by + 14), fill=C["text"], outline=C["bg"], width=3 * TC.K)
    else:
        dr.text(S(872, 300), "—", font=font(48, True), fill=C["muted"])
    # Ликвидациялар
    panel(48, 420, 828, 640)
    dr.text(S(72, 442), "ЛИКВИДАЦИИ (Binance + Bybit)" if ru else "ЛИКВИДАЦИЯЛАР (Binance + Bybit)", font=font(22, True), fill=C["muted"])
    lq = d.get("liq")
    if lq and lq["total"] > 0:
        dr.text(S(72, 476), usd(lq["total"], lang), font=font(46, True), fill=C["text"])
        if lq.get("cov_h", 24) < 23:
            dr.text(S(804, 496), ("наблюдали %.0f ч" if ru else "%.0f саат байкалды") % max(1, lq["cov_h"]), font=font(20), fill=C["muted"], anchor="ra")
        x0, x1, y0 = 72, 804, 552
        wl = (x1 - x0) * lq["long"] / lq["total"]
        dr.rounded_rectangle(S(x0, y0, x1, y0 + 26), radius=13 * TC.K, fill=C["mint"])
        if wl > 8:
            dr.rounded_rectangle(S(x0, y0, x0 + wl, y0 + 26), radius=13 * TC.K, fill=C["red"])
        dr.text(S(x0, 596), "%s %s" % ("лонги" if ru else "лонг", usd(lq["long"], lang)), font=font(24, True), fill=C["red"])
        dr.text(S(x1, 596), "%s %s" % ("шорты" if ru else "шорт", usd(lq["short"], lang)), font=font(24, True), fill=C["mint"], anchor="ra")
    else:
        dr.text(S(72, 500), "маалымат чогултулууда…" if not ru else "данные собираются…", font=font(26), fill=C["muted"])
    # Волатилдүүлүк + лидерлер
    panel(848, 420, 1232, 640)
    dr.text(S(872, 442), "ВОЛАТИЛЬНОСТЬ BTC" if ru else "BTC ВОЛАТИЛДҮҮЛҮГҮ", font=font(22, True), fill=C["muted"])
    if ratio is not None:
        lvl = vol_level(ratio)
        col = C["yellow"] if lvl == "wild" else C["blue"] if lvl == "calm" else C["text"]
        dr.text(S(872, 474), "×%.1f" % ratio, font=font(46, True), fill=col)
        dr.text(S(872 + TC.tw(dr, "×%.1f" % ratio, font(46, True)) + 14, 492), VOL_NAME[lvl][1 if ru else 0], font=font(26, True), fill=col)
        dr.text(S(872, 536), "к среднему за 30 дней" if ru else "30 күндүн орточосуна", font=font(19), fill=C["muted"])
    if d.get("best") and d.get("worst"):
        b, w = d["best"], d["worst"]
        for y, (sym, ch) in ((568, b), (600, w)):
            col = C["mint"] if ch > 0 else C["red"] if ch < 0 else C["muted"]
            dr.text(S(872, y), "%s %s %s" % ("▲" if ch >= 0 else "▼", sym, pct(ch)), font=font(22, True), fill=col)
        dr.text(S(1208, 568), "лидер" if ru else "лидер", font=font(18), fill=C["muted"], anchor="ra")
        dr.text(S(1208, 600), "аутсайдер", font=font(18), fill=C["muted"], anchor="ra")
    TC.footer(dr, lang)
    return TC.png(img)


# ======================================================================
#  Бот менен иштөө
# ======================================================================
class MarketDesk:
    """tg_bot.App жана tg_news.NewsDesk менен: жөнөтүү, база, админ."""

    def __init__(self, app, news):
        self.app, self.news, self.db = app, news, app.db
        self.liq, self.whales = Liq(self.db), Whales(self.db)
        self.stop = threading.Event()
        self.card_fid = {}

    # ---------- жөнөтүү ----------
    def users(self, only_inactive=False):
        rows = self.db.q("SELECT * FROM users WHERE status<>'blocked' AND COALESCE(news,1)=1")
        return [u for u in rows if not only_inactive or (u.get("status") != "active" and not self.app.is_admin(u["id"]))]

    def vip_kb(self, lang):
        bot = self.app.username
        if not bot:
            return None
        txt = "🔐 Вступить в VIP" if lang == "ru" else "🔐 VIP'ке кошулуу"
        return {"inline_keyboard": [[{"text": txt, "url": "https://t.me/%s?start=vip" % bot}]]}

    def post(self, make, users=False, kb=None, seed=None):
        """Канал/тема: KG + RU бир постто (кыргызча биринчи). users=True — ботто жазылгандар (өз тилинде)."""
        seed = seed or str(now_ms())
        both = make("kg", seed) + "\n\n— — —\n\n" + make("ru", seed)
        ch = self.news.to_channel(both, kb=kb("kg") if kb else None)
        n = 0
        if users:
            for u in self.users():
                l = u.get("lang") or "kg"
                if self.app.send(u["id"], make(l, seed), kb(l) if kb else None):
                    n += 1
                time.sleep(0.04)
        return ch, n

    def daily_counter(self, key, cap, gap_ms):
        st = self.db.kv(key) or {}
        day = dt.datetime.now(BISHKEK).strftime("%Y-%m-%d")
        if st.get("d") != day:
            st = {"d": day, "n": 0, "last": st.get("last", 0)}
        ok = st["n"] < cap and now_ms() - st.get("last", 0) >= gap_ms
        return ok, st

    def bump(self, key, st):
        st["n"] += 1
        st["last"] = now_ms()
        self.db.kv_set(key, st)

    # ---------- ликвидациялар ----------
    def liq_tick(self):
        posted = set(self.db.kv("liq_posted") or [])
        big = [e for e in list(self.liq.events) if e["usd"] >= LIQ_BIG and now_ms() - e["t"] < 30 * MIN
               and "%s:%s:%s" % (e["ex"], e["sym"], e["t"]) not in posted]
        if big:
            ok, st = self.daily_counter("liq_big_day", 4, 45 * MIN)
            if ok:
                e = max(big, key=lambda x: x["usd"])
                ch, _ = self.post(lambda l, s: liq_big_msg(e, l, s))
                posted.add("%s:%s:%s" % (e["ex"], e["sym"], e["t"]))
                self.db.kv_set("liq_posted", list(posted)[-300:])
                self.bump("liq_big_day", st)
                print("💥 Ири ликвидация %s %s %s → канал %s" % (e["ex"], e["sym"], usd(e["usd"]), "✓" if ch else "—"))
        w = self.liq.window(HOUR)
        last = int(self.db.kv("liq_wave_t") or 0)
        if w["total"] >= LIQ_HOUR and now_ms() - last > 6 * HOUR:
            ch, n = self.post(lambda l, s: liq_wave_msg(w, l, s), users=True)
            self.db.kv_set("liq_wave_t", now_ms())
            print("🔥 Ликвидация толкуну %s → канал %s · бот %d" % (usd(w["total"]), "✓" if ch else "—", n))
            self.app.notify_admins("🔥 Авто-пост: ликвидация толкуну %s (1 саат) · канал %s · ботто %d" % (usd(w["total"]), "✓" if ch else "жок", n))

    # ---------- киттер ----------
    def whale_tick(self):
        posted = set(self.db.kv("whale_posted") or [])
        fresh = [e for e in list(self.whales.events) if now_ms() - e["t"] < 30 * MIN and e["hash"] not in posted]
        if not fresh:
            return
        ok, st = self.daily_counter("whale_day", 6, 30 * MIN)
        if not ok:
            return
        e = max(fresh, key=lambda x: x.get("usd") or 0)
        ch, _ = self.post(lambda l, s: whale_msg(e, l, s))
        posted.add(e["hash"])
        self.db.kv_set("whale_posted", list(posted)[-300:])
        self.bump("whale_day", st)
        print("🐳 Кит %s %s → канал %s" % (e.get("amount"), e.get("sym"), "✓" if ch else "—"))

    # ---------- күндүн жыйынтыгы ----------
    def card(self, d, lang):
        try:
            return day_card(d, lang)
        except Exception as e:  # noqa: BLE001 — сүрөт чыкпаса текст жөнөтүлөт
            print("! day_card: %s" % e)
            return None

    def send_day(self, chat, d, lang, kb=None, thread=None, seed=None):
        text = day_msg(d, lang, seed)
        img = self.card_fid.get(lang) or self.card(d, lang)
        if img is not None and len(text) <= 1024:
            fid = self.app.photo(chat, img, text, kb, thread=thread)
            if fid:
                self.card_fid[lang] = fid                     # ушул күнү кайра жүктөлбөйт
                return True
        return bool(self.app.send(chat, text, kb, thread=thread))

    def day_post(self, d=None, admin_only=None):
        d = d or day_data(self.liq, self.whales)
        seed = day_seed()
        self.card_fid = {}
        if admin_only:
            self.send_day(admin_only, d, "kg", self.vip_kb("kg"), seed=seed)
            self.send_day(admin_only, d, "ru", self.vip_kb("ru"), seed=seed)
            self.card_fid = {}
            return {"preview": True}
        chat, th = self.news.dest()
        ch = self.send_day(chat, d, "kg", self.vip_kb("kg"), thread=th, seed=seed) if chat else False
        if chat:
            self.app.send(chat, day_msg(d, "ru", seed), thread=th)       # каналда орусчасы өзүнчө (сүрөттүн жазуусу ≤1024)
        n = 0
        for u in self.users():
            l = u.get("lang") or "kg"
            kb = None if (u.get("status") == "active" or self.app.is_admin(u["id"])) else self.vip_kb(l)
            if self.send_day(u["id"], d, l, kb, seed=seed):
                n += 1
            time.sleep(0.05)
        self.card_fid = {}
        print("📊 Күндүн жыйынтыгы → канал %s · бот %d" % ("✓" if ch else "—", n))
        self.app.notify_admins("📊 Күндүн жыйынтыгы жөнөтүлдү · канал %s · ботто %d" % ("✓" if ch else "жок (/news же TELEGRAM_CHANNEL)", n))
        return {"channel": ch, "users": n}

    # ---------- VIP ----------
    def promo_chat(self):
        c = (os.environ.get("TG_PROMO_CHAT") or "").strip()
        return c if (c.startswith("@") or c.startswith("-")) else self.news.channel

    def promo_post(self, admin_only=None):
        i = int(self.db.kv("promo_i") or 0)
        kg, ru = PROMO[i % len(PROMO)]
        if admin_only:
            self.app.send(admin_only, kg, self.vip_kb("kg"))
            return self.app.send(admin_only, ru, self.vip_kb("ru"))
        chat = self.promo_chat()
        ch = self.app.send(chat, kg + "\n\n— — —\n\n" + ru, self.vip_kb("kg")) if chat else None
        n = 0
        for u in self.users(only_inactive=True):
            k = "promo_u:%d" % u["id"]
            if now_ms() - int(self.db.kv(k) or 0) < PROMO_USER_DAYS * 24 * HOUR:
                continue
            l = u.get("lang") or "kg"
            if self.app.send(u["id"], ru if l == "ru" else kg, self.vip_kb(l)):
                n += 1
                self.db.kv_set(k, now_ms())
            time.sleep(0.05)
        self.db.kv_set("promo_i", i + 1)
        print("📣 VIP жарнамасы #%d → канал %s · бот %d" % (i % len(PROMO) + 1, "✓" if ch else "—", n))
        return {"channel": bool(ch), "users": n}

    # ---------- убакыт боюнча ----------
    def schedule_tick(self):
        if self.db.kv("market_paused"):
            return
        t = dt.datetime.now(BISHKEK)
        day = t.strftime("%Y-%m-%d")
        if t.hour == DAY_H and self.db.kv("day_done") != day:
            self.db.kv_set("day_done", day)
            self.day_post()
        if t.hour == PROMO_H and self.db.kv("promo_done") != day:
            self.db.kv_set("promo_done", day)
            self.promo_post()

    def loop(self):
        threading.Thread(target=run_binance, args=(self.liq, self.stop), daemon=True, name="liq-binance").start()
        threading.Thread(target=run_bybit, args=(self.liq, self.stop), daemon=True, name="liq-bybit").start()
        key = (os.environ.get("WHALE_ALERT_KEY") or "").strip()
        if key:
            threading.Thread(target=run_whale_alert, args=(self.whales, self.stop, key), daemon=True, name="whale-alert").start()
        else:
            threading.Thread(target=run_btc_whales, args=(self.whales, self.stop), daemon=True, name="whale-btc").start()
        n = 0
        while not self.stop.is_set():
            self.stop.wait(TICK_S)
            for name, fn in (("ликвидациялар", self.liq_tick), ("киттер", self.whale_tick), ("жадыбал", self.schedule_tick)):
                if name != "жадыбал" and self.db.kv("market_paused"):
                    continue
                try:
                    fn()
                except Exception as e:  # noqa: BLE001
                    print("! рынок (%s): %s" % (name, self.app.tg.redact(e)))
            n += 1
            if n % 5 == 0:
                self.liq.save()
                self.whales.save()

    # ---------- админ ----------
    def admin_rows(self):
        p = self.db.kv("market_paused")
        return [[("📊 Күндүн жыйынтыгы (үлгү)", "mq:day"), ("💥🐳 Ликвидация/киттер", "mq:stat")],
                [("▶️ Рынок посттору" if p else "⏸ Рынок посттору", "mq:pause"), ("📣 VIP жарнама (үлгү)", "mq:promo")]]

    def status_line(self):
        lv = self.liq.live()
        return "Рынок: ликвидация Binance %s · Bybit %s · киттер %s · жыйынтык %02d:00 · VIP %02d:00%s" % (
            "✓" if lv.get("binance") else "—", "✓" if lv.get("bybit") else "—",
            "✓" if now_ms() - self.whales.last < 10 * MIN else "—", DAY_H, PROMO_H, " · ⏸" if self.db.kv("market_paused") else "")

    def on_admin_cb(self, u, data, msg):
        aid = u["id"]
        if data == "mq:pause":
            self.db.kv_set("market_paused", None if self.db.kv("market_paused") else True)
            return self.app.adm_home(u, msg.get("message_id"))
        if data == "mq:day":
            self.app.send(aid, "🔎 Маалымат чогултулууда… Эч кимге жөнөтүлбөйт, сизге гана үлгү (KG жана RU).")
            return self.day_post(admin_only=aid)
        if data == "mq:promo":
            self.app.send(aid, "👀 VIP жарнамасы ушундай чыгат (кийинкиси — %d/%d). Эч кимге жөнөтүлгөн жок." % (
                int(self.db.kv("promo_i") or 0) % len(PROMO) + 1, len(PROMO)))
            return self.promo_post(admin_only=aid)
        if data == "mq:stat":
            h, dd = self.liq.window(HOUR), self.liq.window(24 * HOUR)
            lines = ["💥🐳 <b>Ликвидациялар жана киттер</b> (биз байкаган)",
                     "1 саат: %s — лонг %s · шорт %s (%d)" % (usd(h["total"]), usd(h["long"]), usd(h["short"]), h["n"]),
                     "24 саат: %s — лонг %s · шорт %s (%d)" % (usd(dd["total"]), usd(dd["long"]), usd(dd["short"]), dd["n"]),
                     "Чектер: бир ликвидация ≥ %s · толкун ≥ %s/саат · кит ≥ %g BTC" % (usd(LIQ_BIG), usd(LIQ_HOUR), WHALE_BTC),
                     "Киттер (24 с): %d · булак: %s" % (self.whales.count(24 * HOUR), self.whales.src)]
            ev = sorted(list(self.liq.events), key=lambda e: -e["usd"])[:5]
            if ev:
                lines.append("Эң ирилери (26 с): " + "; ".join("%s %s %s" % (e["sym"].replace("USDT", ""), "L" if e["long"] else "S", usd(e["usd"])) for e in ev))
            errs = ["%s: %s" % (k, v) for k, v in list(self.liq.err.items()) + [("киттер", self.whales.err)] if v]
            if errs:
                lines.append("⚠️ " + E(" · ".join(errs)))
            lines.append(self.status_line())
            return self.app.send(aid, "\n".join(lines))
        return None


# ======================================================================
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--demo", metavar="DIR", help="күндүн жыйынтыгы: сүрөт + текст KG/RU азыркы рыноктон")
    ap.add_argument("--listen", type=int, metavar="SEC", help="ликвидацияларды жана киттерди N секунд угуу")
    a = ap.parse_args()
    liq, wh = Liq(), Whales()
    if a.listen:
        stop = threading.Event()
        for fn, arg in ((run_binance, liq), (run_bybit, liq), (run_btc_whales, wh)):
            threading.Thread(target=fn, args=(arg, stop), daemon=True).start()
        time.sleep(a.listen)
        stop.set()
        w = liq.window(HOUR)
        print("Ликвидациялар %d с ичинде: %s (лонг %s · шорт %s) · %d окуя · биржалар: %s · каталар: %s" % (
            a.listen, usd(w["total"]), usd(w["long"]), usd(w["short"]), w["n"], liq.live(), liq.err))
        print("BTC транзакциялары келди: %s · кит (≥%g BTC): %d · ката: %s" % ("✓" if wh.last else "—", WHALE_BTC, len(wh.events), wh.err))
        for e in list(wh.events)[:3]:
            print("  ", whale_msg(e, "kg", "x").split("\n\n")[0].replace("\n", " | "))
    if a.demo:
        os.makedirs(a.demo, exist_ok=True)
        d = day_data(liq if a.listen else None, wh if a.listen else None)
        for lang in ("kg", "ru"):
            with open(os.path.join(a.demo, "day_%s.png" % lang), "wb") as f:
                f.write(day_card(d, lang))
            t = day_msg(d, lang)
            with open(os.path.join(a.demo, "day_%s.txt" % lang), "w", encoding="utf-8") as f:
                f.write(t)
            print("— %s (%d симв.) —\n%s\n" % (lang, len(t), t))
        e = {"t": now_ms(), "ex": "binance", "sym": "BTCUSDT", "long": True, "usd": 2_350_000, "px": 87000}
        print(liq_big_msg(e, "kg", "1"), "\n")
        print(whale_msg({"t": now_ms(), "hash": "ab" * 32, "chain": "bitcoin", "sym": "BTC", "amount": 1200, "usd": 1200 * 87000,
                         "from": None, "to": "Binance"}, "ru", "2"))


if __name__ == "__main__":
    main()
