"""AITRADING.KG — Telegram үчүн сүрөттөр (бренд стили «Аврора»): сигнал + график, сделканын жыйынтыгы, доступ, акысыз сигналдар бүттү.

    python tools/tg_cards.py --demo <папка>     # 4 үлгү сүрөт (текшерүү үчүн)

Pillow менен тартылат (2x чоңдукта, анан кичирейтилет — сызыктар жумшак). Шрифт: DejaVu (matplotlib'дин ичинде келет,
серверде өзүнчө орнотуу керек эмес) же системанын шрифти. Сүрөт чыкпай калса — бот кадимки текст менен жөнөтөт.
Сандар сигналдын өзүнөн гана алынат, эч нерсе ойлоп табылбайт ([[trader-kg-honest-numbers]]).
"""
import io
import math
import os
import sys
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, K = 1280, 720, 2                  # чыгуучу өлчөм жана 2x тартуу
BISHKEK = timezone(timedelta(hours=6))
C = {
    "bg": (7, 11, 18), "panel": (15, 23, 37), "line": (40, 52, 70), "grid": (30, 40, 56),
    "text": (233, 238, 246), "muted": (154, 166, 184), "dim": (109, 122, 143),
    "mint": (92, 232, 170), "red": (255, 107, 107), "yellow": (255, 204, 21), "blue": (59, 123, 255), "grey": (154, 166, 184),
}

TXT = {
    "kg": {
        "signal": "СИГНАЛ", "up": "ӨЙДӨ", "dn": "ЫЛДЫЙ", "prob": "Ыктымалдык", "entry": "Кирүү", "time": "Убакыт",
        "price": "Баа", "model": "Модель: тест {a} · жөнөкөй {b}", "fx": "BinoDex · {m} мүн", "bx": "BingX спот · 1 саат",
        "foot": "Ыктымалдык — кепилдик эмес · 18+", "bish": "Бишкек",
        "win": "ПЛЮС", "loss": "МИНУС", "tie": "НӨЛ", "res_sub": "Сигналдын жыйынтыгы",
        "chg": "Баанын өзгөрүшү", "dur": "Мөөнөт", "min": "мүн", "h1": "1 саат",
        "stats": "Боттун статистикасы (акыркы {n}): плюс {w} · минус {l} · {pc}%", "stats_few": "Боттун статистикасы: плюс {w} · минус {l}",
        "acc_t": "ДОСТУП АЧЫЛДЫ", "acc_s": "Сиз AITRADING.KG командасындасыз",
        "acc_l": ["Сигналдар ушул чатка келет", "Сайттагы сигналдар — «Сайтта ачуу» баскычы", "Ар бир сигналдан кийин — плюс же минус жыйынтыгы"],
        "free_t": "АКЫСЫЗ СИГНАЛДАР БҮТТҮ", "free_s": "Бардык сигналдарды алуу үчүн:",
        "free_l": ["Биздин шилтеме менен брокерде катталыңыз", "Эсепти толуктаңыз (милдеттүү)", "ID'ни ботко жибериңиз — доступ ачылат"],
    },
    "ru": {
        "signal": "СИГНАЛ", "up": "ВВЕРХ", "dn": "ВНИЗ", "prob": "Вероятность", "entry": "Вход", "time": "Время",
        "price": "Цена", "model": "Модель: тест {a} · угадывание {b}", "fx": "BinoDex · {m} мин", "bx": "BingX спот · 1 час",
        "foot": "Вероятность, а не гарантия · 18+", "bish": "Бишкек",
        "win": "ПЛЮС", "loss": "МИНУС", "tie": "НОЛЬ", "res_sub": "Итог сигнала",
        "chg": "Изменение цены", "dur": "Срок", "min": "мин", "h1": "1 час",
        "stats": "Статистика бота (последние {n}): плюс {w} · минус {l} · {pc}%", "stats_few": "Статистика бота: плюс {w} · минус {l}",
        "acc_t": "ДОСТУП ОТКРЫТ", "acc_s": "Вы в команде AITRADING.KG",
        "acc_l": ["Сигналы будут приходить в этот чат", "Сигналы на сайте — кнопка «Открыть на сайте»", "После каждого сигнала — итог: плюс или минус"],
        "free_t": "БЕСПЛАТНЫЕ СИГНАЛЫ ЗАКОНЧИЛИСЬ", "free_s": "Чтобы получать все сигналы:",
        "free_l": ["Зарегистрируйтесь у брокера по нашей ссылке", "Пополните счёт (обязательно)", "Отправьте ID в бот — доступ откроется"],
    },
}


# ---------------------------------------------------------------- шрифттер
_FONTS = {}


def _font_paths(bold):
    out = []
    try:
        import matplotlib
        out.append(os.path.join(matplotlib.get_data_path(), "fonts", "ttf", "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"))
    except Exception:  # noqa: BLE001
        pass
    out += ["/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf" % ("-Bold" if bold else ""),
            "C:/Windows/Fonts/%s" % ("segoeuib.ttf" if bold else "segoeui.ttf"),
            "C:/Windows/Fonts/%s" % ("arialbd.ttf" if bold else "arial.ttf")]
    return out


def font(size, bold=False):
    k = (size, bold)
    if k not in _FONTS:
        for p in _font_paths(bold):
            if os.path.exists(p):
                _FONTS[k] = ImageFont.truetype(p, size * K)
                break
        else:
            raise RuntimeError("кириллица шрифти табылган жок (pip install matplotlib)")
    return _FONTS[k]


def available():
    try:
        font(20)
        return True
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------- жардамчылар
def S(*v):
    return [int(round(x * K)) for x in v]


def tw(d, s, f):
    b = d.textbbox((0, 0), s, font=f)
    return (b[2] - b[0]) / K


def fit(d, s, size, maxw, bold=True, minsize=18):
    while size > minsize and tw(d, s, font(size, bold)) > maxw:
        size -= 2
    return font(size, bold)


def pct(x):
    return "%d%%" % int(math.floor(x * 100 + 0.5))


def money(x, fx):
    if x is None:
        return "—"
    if fx:
        return ("%.5f" if x < 20 else "%.3f") % x
    if x >= 1000:
        return "$" + ("{:,.2f}".format(x)).rstrip("0").rstrip(".")
    p = 10 if x < 0.0001 else 7 if x < 0.01 else 5 if x < 1 else 3 if x < 100 else 2
    return "$" + ("%." + str(p) + "f") % x


def hm(ms, sec=False):
    return datetime.fromtimestamp(ms / 1000, BISHKEK).strftime("%H:%M:%S" if sec else "%H:%M")


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


_BG = {}


def background(accent):
    """Караңгы фон + жумшак «аврора» жарыгы (accent түсү менен)."""
    if accent in _BG:
        return _BG[accent].copy()
    w, h = W * K, H * K
    img = Image.new("RGB", (w, h), C["bg"])
    glow = Image.new("RGB", (w // 4, h // 4), C["bg"])
    g = ImageDraw.Draw(glow)
    for (cx, cy, r, col, a) in ((0.12, 0.05, 0.42, C["blue"], 0.35), (0.9, 0.95, 0.5, accent, 0.30), (0.62, 0.0, 0.32, C["yellow"], 0.16)):
        x, y, rr = cx * w / 4, cy * h / 4, r * w / 4
        g.ellipse([x - rr, y - rr * 0.7, x + rr, y + rr * 0.7], fill=mix(C["bg"], col, a))
    glow = glow.filter(ImageFilter.GaussianBlur(60)).resize((w, h), Image.BILINEAR)
    img = Image.blend(img, glow, 1.0)
    d = ImageDraw.Draw(img)
    for x in range(0, w, 64 * K):                                    # жука тор
        d.line([x, 0, x, h], fill=mix(C["bg"], C["line"], 0.1), width=1)
    _BG[accent] = img
    return img.copy()


def brand(d, lang, ms=None):
    d.rounded_rectangle(S(48, 40, 104, 96), radius=14 * K, fill=C["yellow"])
    f = font(26, True)
    d.text((S(76)[0], S(68)[0]), "AI", font=f, fill=C["bg"], anchor="mm")
    d.text(S(118, 50), "TRADING", font=font(30, True), fill=C["text"])
    x = 118 + tw(d, "TRADING", font(30, True)) + 2
    d.text(S(x, 50), ".KG", font=font(30, True), fill=C["yellow"])
    if ms:
        s = datetime.fromtimestamp(ms / 1000, BISHKEK).strftime("%d.%m.%Y · %H:%M") + " (" + TXT[lang]["bish"] + ")"
        d.text(S(W - 48, 58), s, font=font(20), fill=C["muted"], anchor="rm")


def footer(d, lang):
    d.line(S(48, H - 64, W - 48, H - 64), fill=C["line"], width=2 * K)
    d.text(S(48, H - 42), TXT[lang]["foot"], font=font(20), fill=C["muted"], anchor="lm")
    d.text(S(W - 48, H - 42), "aitrading.kg", font=font(22, True), fill=C["yellow"], anchor="rm")


def tri(d, cx, cy, s, up, col):
    if up:
        pts = [(cx, cy - s), (cx + s * 0.9, cy + s * 0.7), (cx - s * 0.9, cy + s * 0.7)]
    else:
        pts = [(cx, cy + s), (cx + s * 0.9, cy - s * 0.7), (cx - s * 0.9, cy - s * 0.7)]
    d.polygon([(x * K, y * K) for x, y in pts], fill=col)


def png(img):
    out = img.resize((W, H), Image.LANCZOS)
    b = io.BytesIO()
    out.save(b, "PNG", optimize=True)
    return b.getvalue()


# ---------------------------------------------------------------- график
def chart(d, box, cs, entry, up, col, fx, levels=None):
    x0, y0, x1, y1 = box
    d.rounded_rectangle(S(x0, y0, x1, y1), radius=18 * K, fill=mix(C["bg"], C["panel"], 0.85), outline=C["line"], width=2 * K)
    cs = [c for c in (cs or []) if c.get("high") is not None][-64:]
    if len(cs) < 5:
        return
    px0, px1, py0, py1 = x0 + 18, x1 - 120, y0 + 24, y1 - 24
    lv = levels or []
    lo = min([c["low"] for c in cs] + [entry] + [v for v, _, _ in lv])
    hi = max([c["high"] for c in cs] + [entry] + [v for v, _, _ in lv])
    pad = (hi - lo) * 0.08 or hi * 0.001
    lo, hi = lo - pad, hi + pad

    def Y(v):
        return py1 - (v - lo) / (hi - lo) * (py1 - py0)
    for i in range(5):                                                  # тор + баалар
        v = lo + (hi - lo) * i / 4
        y = Y(v)
        d.line(S(px0, y, px1, y), fill=C["grid"], width=1 * K)
        d.text(S(px1 + 12, y), money(v, fx), font=font(15), fill=C["dim"], anchor="lm")
    n = len(cs)
    step = (px1 - px0) / n
    bw = max(2.0, step * 0.62)
    for i, c in enumerate(cs):
        x = px0 + step * (i + 0.5)
        g = c["close"] >= c["open"]
        cc = C["mint"] if g else C["red"]
        d.line(S(x, Y(c["high"]), x, Y(c["low"])), fill=cc, width=max(1, int(1.5 * K)))
        top, bot = Y(max(c["open"], c["close"])), Y(min(c["open"], c["close"]))
        if bot - top < 1:
            bot = top + 1
        d.rectangle(S(x - bw / 2, top, x + bw / 2, bot), fill=cc)
    for v, lc, lab in lv:                                               # стоп / тейктер
        yv = Y(v)
        xx = px0
        while xx < px1:
            d.line(S(xx, yv, min(xx + 7, px1), yv), fill=lc, width=2 * K)
            xx += 13
        d.rounded_rectangle(S(px1 + 6, yv - 13, x1 - 10, yv + 13), radius=7 * K, fill=mix(C["bg"], lc, 0.35), outline=lc, width=1 * K)
        d.text(S((px1 + x1) / 2 - 2, yv), lab, font=font(13, True), fill=C["text"], anchor="mm")
    ye = Y(entry)                                                       # кирүү сызыгы (пунктир)
    x = px0
    while x < px1:
        d.line(S(x, ye, min(x + 10, px1), ye), fill=C["yellow"], width=2 * K)
        x += 18
    d.rounded_rectangle(S(px1 + 6, ye - 15, x1 - 10, ye + 15), radius=8 * K, fill=C["yellow"])
    d.text(S((px1 + x1) / 2 - 2, ye), money(entry, fx), font=font(15, True), fill=C["bg"], anchor="mm")
    lx = px0 + step * (n - 0.5)                                         # акыркы шам + багыттын жебеси
    d.ellipse(S(lx - 7, ye - 7, lx + 7, ye + 7), fill=C["yellow"], outline=C["bg"], width=2 * K)
    ay = ye - 70 if up else ye + 70
    ay = min(max(ay, py0 + 30), py1 - 30)
    d.line(S(lx, ye, lx + 34, ay), fill=col, width=4 * K)
    tri(d, lx + 40, ay, 16, up, col)


# ---------------------------------------------------------------- карточкалар
def card_signal(sg, cs, lang="kg"):
    L = TXT.get(lang, TXT["kg"])
    fx, up = sg["mkt"] == "binodex", sg["dir"] > 0
    col = C["mint"] if up else C["red"]
    img = background(col)
    d = ImageDraw.Draw(img)
    brand(d, lang, sg.get("t0") or sg.get("t"))
    chart(d, (48, 120, 800, 630), cs, sg["entry"], up, col, fx)
    x, r = 830, W - 48                                                  # оң панель
    d.rounded_rectangle(S(x, 120, x + 150, 160), radius=20 * K, outline=C["mint"], width=2 * K)
    d.text(S(x + 75, 140), L["signal"], font=font(20, True), fill=C["mint"], anchor="mm")
    d.text(S(x, 178), sg["name"], font=fit(d, sg["name"], 52, r - x), fill=C["text"])
    d.text(S(x, 246), L["fx"].format(m=sg["exp"]) if fx else L["bx"], font=font(22), fill=C["muted"])
    lab = L["up"] if up else L["dn"]
    pw = 90 + tw(d, lab, font(30, True))
    d.rounded_rectangle(S(x, 292, x + pw, 350), radius=29 * K, fill=mix(C["bg"], col, 0.22), outline=col, width=2 * K)
    tri(d, x + 34, 321, 13, up, col)
    d.text(S(x + 60, 321), lab, font=font(30, True), fill=col, anchor="lm")
    p = sg["p"] if up else 1 - sg["p"]
    d.text(S(x, 372), L["prob"], font=font(20), fill=C["muted"])
    d.text(S(x - 4, 396), pct(p), font=font(92, True), fill=col)
    rows = [(L["entry"], money(sg["entry"], fx))]
    if fx and sg.get("tEnd"):
        rows.append((L["time"], "%s → %s" % (hm(sg["t0"], True), hm(sg["tEnd"], True))))
    y = 518
    for k, v in rows:
        d.text(S(x, y), k, font=font(20), fill=C["muted"])
        d.text(S(r, y), v, font=font(22, True), fill=C["text"], anchor="ra")
        y += 34
    d.text(S(x, y + 4), L["model"].format(a=pct(sg["acc"]), b=pct(sg["bl"])), font=fit(d, L["model"].format(a=pct(sg["acc"]), b=pct(sg["bl"])), 18, r - x, False, 13), fill=C["dim"])
    footer(d, lang)
    return png(img)


FUT = {
    "kg": {"long": "ЛОНГ", "short": "ШОРТ", "h_short": "ФЬЮЧЕРС · КЫСКА", "h_mid": "ФЬЮЧЕРС · ОРТО", "zone": "Кирүү", "sl": "Стоп",
           "tp1": "TP1", "tp2": "TP2", "rr": "Тобокелдик/пайда", "tf_short": "15 мүн · 8 саатка чейин", "tf_mid": "4 саат · 4 күнгө чейин",
           "foot": "Плечо 1–3x · 1–2% депозит · кепилдик эмес · 18+"},
    "ru": {"long": "ЛОНГ", "short": "ШОРТ", "h_short": "ФЬЮЧЕРС · КРАТКОСРОК", "h_mid": "ФЬЮЧЕРС · СРЕДНЕСРОК", "zone": "Вход", "sl": "Стоп",
           "tp1": "TP1", "tp2": "TP2", "rr": "Риск/прибыль", "tf_short": "15 мин · до 8 часов", "tf_mid": "4 часа · до 4 дней",
           "foot": "Плечо 1–3x · 1–2% депозита · не гарантия · 18+"},
}


def card_futures(tr, cs, lang="kg", label=None):
    """BingX фьючерс: график + кирүү/стоп/TP1/TP2 сызыктары, оң жакта лонг/шорт жана деңгээлдер."""
    L, F = TXT.get(lang, TXT["kg"]), FUT.get(lang, FUT["kg"])
    up = tr["dir"] > 0
    col = C["mint"] if up else C["red"]
    img = background(col)
    d = ImageDraw.Draw(img)
    brand(d, lang, tr.get("t0"))
    lv = [(tr["sl"], C["red"], "SL"), (tr["tp1"], C["mint"], "TP1"), (tr["tp2"], C["mint"], "TP2")]
    chart(d, (48, 120, 800, 630), cs, tr["entry"], up, col, False, lv)
    x, r = 830, W - 48
    head = F["h_" + tr["hz"]]
    hw = 40 + tw(d, head, font(18, True))
    d.rounded_rectangle(S(x, 120, x + hw, 158), radius=19 * K, outline=C["yellow"], width=2 * K)
    d.text(S(x + hw / 2, 139), head, font=font(18, True), fill=C["yellow"], anchor="mm")
    name = label or (tr["sym"] + "/USDT")
    d.text(S(x, 172), name, font=fit(d, name, 46, r - x), fill=C["text"])
    d.text(S(x, 232), "BingX · " + F["tf_" + tr["hz"]], font=fit(d, "BingX · " + F["tf_" + tr["hz"]], 20, r - x, False, 14), fill=C["muted"])
    lab = F["long"] if up else F["short"]
    pw = 90 + tw(d, lab, font(30, True))
    d.rounded_rectangle(S(x, 270, x + pw, 326), radius=28 * K, fill=mix(C["bg"], col, 0.22), outline=col, width=2 * K)
    tri(d, x + 34, 298, 13, up, col)
    d.text(S(x + 60, 298), lab, font=font(30, True), fill=col, anchor="lm")
    p = tr["p"] if up else 1 - tr["p"]
    d.text(S(x + pw + 22, 284), pct(p), font=font(40, True), fill=col)
    rows = [(F["zone"], "%s – %s" % (money(tr["zone"][0], False), money(tr["zone"][1], False)), C["yellow"]),
            (F["sl"], money(tr["sl"], False), C["red"]), (F["tp1"], money(tr["tp1"], False), C["mint"]), (F["tp2"], money(tr["tp2"], False), C["mint"]),
            (F["rr"], "1 : 1.5  /  1 : 3", C["text"])]
    y = 350
    for k, v, vc in rows:
        d.text(S(x, y), k, font=font(20), fill=C["muted"])
        d.text(S(r, y), v, font=fit(d, v, 22, r - x - 110, True, 14), fill=vc, anchor="ra")
        d.line(S(x, y + 34, r, y + 34), fill=C["line"], width=1 * K)
        y += 46
    m = L["model"].format(a=pct(tr["acc"]), b=pct(tr["bl"]))
    d.text(S(x, y + 6), m, font=fit(d, m, 17, r - x, False, 12), fill=C["dim"])
    d.line(S(48, H - 64, W - 48, H - 64), fill=C["line"], width=2 * K)
    d.text(S(48, H - 42), F["foot"], font=font(19), fill=C["muted"], anchor="lm")
    d.text(S(W - 48, H - 42), "aitrading.kg", font=font(22, True), fill=C["yellow"], anchor="rm")
    return png(img)


def stats_text(hist, L):
    a = [h for h in (hist or []) if h.get("res") in (0, 1)][-50:]
    if not a:
        return None
    w = sum(1 for h in a if h["res"] == 1)
    if len(a) < 10:
        return L["stats_few"].format(w=w, l=len(a) - w)
    return L["stats"].format(n=len(a), w=w, l=len(a) - w, pc=int(round(w / len(a) * 100)))


def card_result(sg, hist=None, lang="kg"):
    L = TXT.get(lang, TXT["kg"])
    res, fx, up = sg["res"], sg["mkt"] == "binodex", sg["dir"] > 0
    col = {1: C["mint"], 0: C["red"]}.get(res, C["grey"])
    img = background(col)
    d = ImageDraw.Draw(img)
    brand(d, lang, sg.get("tEnd") or sg.get("t0"))
    cx, cy, rr = 250, 340, 130                                          # чоң белги
    d.ellipse(S(cx - rr, cy - rr, cx + rr, cy + rr), fill=mix(C["bg"], col, 0.18), outline=col, width=6 * K)
    if res == 1:
        d.line(S(cx - 60, cy + 2, cx - 15, cy + 50, cx + 65, cy - 50), fill=col, width=18 * K, joint="curve")
    elif res == 0:
        d.line(S(cx - 52, cy - 52, cx + 52, cy + 52), fill=col, width=18 * K)
        d.line(S(cx - 52, cy + 52, cx + 52, cy - 52), fill=col, width=18 * K)
    else:
        d.line(S(cx - 55, cy, cx + 55, cy), fill=col, width=18 * K)
    x, r = 450, W - 60
    d.text(S(x, 150), L["res_sub"], font=font(24), fill=C["muted"])
    d.text(S(x - 4, 182), {1: L["win"], 0: L["loss"]}.get(res, L["tie"]), font=font(120, True), fill=col)
    d.text(S(x, 330), sg["name"], font=fit(d, sg["name"], 46, r - x - 200), fill=C["text"])
    lab = L["up"] if up else L["dn"]
    lw = tw(d, sg["name"], fit(d, sg["name"], 46, r - x - 200))
    tri(d, x + lw + 34, 358, 12, up, C["mint"] if up else C["red"])
    d.text(S(x + lw + 54, 358), lab, font=font(26, True), fill=C["mint"] if up else C["red"], anchor="lm")
    y = 412
    rows = [(L["entry"] + " → " + L["price"].lower(), "%s → %s" % (money(sg["entry"], fx), money(sg.get("exit"), fx)))]
    if sg.get("exit") and sg.get("entry"):
        ch = (sg["exit"] - sg["entry"]) / sg["entry"] * 100
        rows.append((L["chg"], ("%+.3f%%" if abs(ch) < 1 else "%+.2f%%") % ch))
    rows.append((L["dur"], ("%d %s" % (sg["exp"], L["min"])) if fx else L["h1"]))
    for k, v in rows:
        d.text(S(x, y), k, font=font(22), fill=C["muted"])
        d.text(S(r, y), v, font=font(24, True), fill=C["text"], anchor="ra")
        d.line(S(x, y + 40, r, y + 40), fill=C["line"], width=1 * K)
        y += 52
    st = stats_text(hist, L)
    if st:
        d.text(S(x, y + 8), st, font=fit(d, st, 22, r - x, False, 14), fill=C["yellow"])
    footer(d, lang)
    return png(img)


def _list_card(title, sub, items, col, lang, numbered):
    img = background(col)
    d = ImageDraw.Draw(img)
    brand(d, lang)
    x, r = 96, W - 96
    d.text(S(x, 150), title, font=fit(d, title, 68, r - x), fill=col)
    d.text(S(x, 248), sub, font=font(28), fill=C["text"])
    y = 320
    for i, s in enumerate(items):
        d.ellipse(S(x, y, x + 52, y + 52), fill=mix(C["bg"], col, 0.2), outline=col, width=3 * K)
        if numbered:
            d.text(S(x + 26, y + 26), str(i + 1), font=font(26, True), fill=col, anchor="mm")
        else:
            d.line(S(x + 15, y + 27, x + 23, y + 36, x + 38, y + 17), fill=col, width=5 * K)
        d.text(S(x + 76, y + 26), s, font=fit(d, s, 30, r - x - 80, False, 18), fill=C["text"], anchor="lm")
        y += 82
    footer(d, lang)
    return png(img)


def card_access(lang="kg"):
    L = TXT.get(lang, TXT["kg"])
    return _list_card(L["acc_t"], L["acc_s"], L["acc_l"], C["mint"], lang, False)


def card_free_end(lang="kg", m=2):
    L = TXT.get(lang, TXT["kg"])
    return _list_card(L["free_t"] + " (%d/%d)" % (m, m), L["free_s"], L["free_l"], C["yellow"], lang, True)


# ---------------------------------------------------------------- үлгүлөр
def _demo(out):
    import random
    random.seed(7)
    cs, p, t = [], 1.0965, 1795500000
    for i in range(70):
        o = p
        p = max(0.5, p + random.uniform(-0.0006, 0.00065))
        cs.append({"time": t + i * 60, "open": o, "close": p, "high": max(o, p) + random.uniform(0, 0.0003), "low": min(o, p) - random.uniform(0, 0.0003)})
    now = 1795560000000
    sg = {"mkt": "binodex", "name": "EUR/USD", "dir": 1, "p": 0.612, "acc": 0.571, "bl": 0.523, "exp": 1, "entry": cs[-1]["close"],
          "t0": now, "tEnd": now + 60000, "res": 1, "exit": cs[-1]["close"] + 0.00042}
    hist = [{"res": 1}] * 31 + [{"res": 0}] * 19
    os.makedirs(out, exist_ok=True)
    for name, data in (("signal_kg", card_signal(sg, cs, "kg")), ("signal_ru", card_signal(dict(sg, dir=-1, p=0.38, mkt="bingx", name="BTC/USDT", entry=61234.5), [dict(c, open=c["open"] * 55800, close=c["close"] * 55800, high=c["high"] * 55800, low=c["low"] * 55800) for c in cs], "ru")),
                       ("result_win", card_result(sg, hist, "kg")), ("result_loss", card_result(dict(sg, res=0, exit=sg["entry"] - 0.0003), hist, "ru")),
                       ("access", card_access("kg")), ("free_end", card_free_end("ru"))):
        with open(os.path.join(out, name + ".png"), "wb") as f:
            f.write(data)
        print(name, len(data) // 1024, "KB")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--demo":
        _demo(sys.argv[2])
    else:
        print(__doc__)
