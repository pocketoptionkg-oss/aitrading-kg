"""ИИ-посттор / ИИ-посты: күнүмдүк рынок обзору (кыргызча + орусча).

    python tools/ai_posts.py            # пост жазып, site/assets/data/posts.json'го кошот
    python tools/ai_posts.py --dry-run  # API'ге кайрылбай, киргизүүчү маалыматты гана көрсөтөт

Керек: pip install -r tools/requirements.txt жана ANTHROPIC_API_KEY (console.anthropic.com).
Иштөө тартиби:
  1. Маалымат: site/assets/data/bingx.json (tools/update_bingx.py) + CoinGecko trending (BingX'те барлары).
  2. Claude пост жазат — эрежелер: киреше убада кылбоо, «сатып ал» дебөө, сандар маалыматтан гана.
  3. Текшерүү: посттогу ар бир % жана $ сан маалыматтан алынганбы? Жок болсо — бир жолу кайра жаздырат.
     Экинчи жолу да ката болсо — пост жарыяланбайт (сайтта эски пост калат).
"""
import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "site", "assets", "data")
BINGX = os.path.join(DATA, "bingx.json")
POSTS = os.path.join(DATA, "posts.json")
MODEL = "claude-opus-5-5"
KEEP = 30
BISHKEK = timezone(timedelta(hours=6))

SYSTEM = """Сен AITRADING.KG сайтынын редакторусуң (автор — TRADER KG, Нурсултан). Күн сайын BingX биржасындагы рынок боюнча кыска обзор жазасың: кыргызча (негизги) жана орусча.

Катуу эрежелер:
- Сандарды (пайыз, баа, көлөм) ЖАЛГЫЗ гана FACTS тизмесинен ал жана так ошол жазылыштай көчүр. Башка сан ойлоп таппа, тегеректебе, эсептебе.
- Киреше, кепилдик, «сөзсүз өсөт», «сатып ал», «эң жакшы мүмкүнчүлүк» сыяктуу убада же чакырык жазба. Бул — маалымат, сунуш эмес.
- Хайп активдер жөнүндө жазсаң, алардын тобокелдиги жогору экенин ачык айт.
- Жөнөкөй, элге түшүнүктүү тил: кыйын терминди бир сөз менен түшүндүр. Кыргызча туура грамматика жана орфография (ң, ө, ү тамгалары менен). Орусча да грамматикалык катасыз.
- Ар бир обзордун аягы — тобокелдик жөнүндө бир сүйлөм.
- CTA (чакырык) жумшак болсун: «сайттан графикти кара», «адегенде демо же кичине сумма», «кантип сатып алууну Окуу бөлүмүнөн оку» — басым жасаба, шаштырба.
- Эмодзини аз колдон (telegram текстинде 2–4 эмодзи болушу мүмкүн)."""

PROMPT = """Бүгүнкү күн: {date} (Бишкек убактысы).

FACTS (сандарды ушул жерден гана ал, так көчүр):
{facts}

Тапшырма: бүгүнкү обзорду жаз.
- title_ky / title_ru: 4–9 сөздөн турган аталыш.
- body_ky / body_ru: 3–5 кыска абзац (жалпы 500–900 белги): рынок абалы, хайп/тренд, жаңы IPO токендери, ИИ сектору.
- highlights: эң кызыктуу 3 актив (asset — BingX жубу, мисалы "BTC/USDT"; note_ky/note_ru — бир сүйлөм, эмне үчүн көңүл бурууга татыктуу).
- telegram_ky / telegram_ru: Telegram канал үчүн кыскача версия (400–600 белги), аягында "aitrading.kg" жана тобокелдик эскертүүсү.
- cta_ky / cta_ru: бир сүйлөмдүү жумшак чакырык."""

SCHEMA = {
    "type": "object",
    "properties": {
        "title_ky": {"type": "string"},
        "title_ru": {"type": "string"},
        "body_ky": {"type": "string"},
        "body_ru": {"type": "string"},
        "highlights": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"asset": {"type": "string"}, "note_ky": {"type": "string"}, "note_ru": {"type": "string"}},
                "required": ["asset", "note_ky", "note_ru"],
                "additionalProperties": False,
            },
        },
        "telegram_ky": {"type": "string"},
        "telegram_ru": {"type": "string"},
        "cta_ky": {"type": "string"},
        "cta_ru": {"type": "string"},
    },
    "required": ["title_ky", "title_ru", "body_ky", "body_ru", "highlights", "telegram_ky", "telegram_ru", "cta_ky", "cta_ru"],
    "additionalProperties": False,
}

STABLE = {"USDT", "USDC", "FDUSD", "DAI", "USDE", "TUSD", "PYUSD", "USD1", "USDS", "WBTC", "WETH", "STETH"}


# ---------- Маалымат ----------
def pct(v):
    return ("+" if v > 0 else "") + ("%.2f" % v) + "%"


def money(v):
    if v >= 1e9:
        return "$%.2fB" % (v / 1e9)
    if v >= 1e6:
        return "$%.1fM" % (v / 1e6)
    if v >= 1e3:
        return "$%.0fK" % (v / 1e3)
    return "$%.0f" % v


def price(v):
    if v >= 100:
        return "$" + format(round(v, 2), ",")
    if v >= 1:
        return "$%.3f" % v
    return "$%s" % ("%.4g" % v)


def coingecko_trending(spot):
    try:
        req = urllib.request.Request("https://api.coingecko.com/api/v3/search/trending", headers={"User-Agent": "Mozilla/5.0 (aitrading posts)"})
        with urllib.request.urlopen(req, timeout=20) as r:
            j = json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001 — CoinGecko жок болсо да пост чыга берет
        print("CoinGecko жеткиликсиз:", e, file=sys.stderr)
        return []
    out = []
    for i, c in enumerate(j.get("coins", []), 1):
        it = c["item"]
        sym = it["symbol"].upper()
        if sym in spot and sym not in STABLE:
            out.append((i, it["name"], sym))
    return out[:5]


def build_facts():
    with open(BINGX, encoding="utf-8") as f:
        bx = json.load(f)
    spot = set(bx["spot"])
    lines, allowed = [], set()

    def add(line, *tokens):
        lines.append(line)
        allowed.update(tokens)

    add("BingX маалыматы жаңыртылган: %s" % bx["updated"])
    add("BingX'тин көлөм боюнча топ крипто жуптары (24 саат):")
    for r in bx["top"][:6]:
        add("- %s/USDT: баа %s, 24с %s, көлөм %s" % (r["base"], price(r["last"]), pct(r["chg"]), money(r["vol"])),
            price(r["last"]), pct(r["chg"]), money(r["vol"]))
    seen = set()
    add("BingX'теги акция токендери (24 саат көлөмү боюнча):")
    for s in bx["stocks"]:
        if s["name"] in seen:
            continue
        seen.add(s["name"])
        add("- %s (%s/USDT, сектор: %s): баа %s, 24с %s, көлөм %s" % (s["name"], s["base"], s["sector"], price(s["last"]), pct(s["chg"]), money(s["vol"])),
            price(s["last"]), pct(s["chg"]), money(s["vol"]))
        if len(seen) >= 10:
            break
    add("2026-жылдын жаңы IPOлору (BingX'те токен түрүндө): Anthropic (IPO 18.11.2026, $83.00), SK hynix (IPO 2026-ж. июль, $149 / ADS), SpaceX (IPO 11.06.2026, $135.00).",
        "$83.00", "$149", "$135.00")
    tr = coingecko_trending(spot)
    if tr:
        add("CoinGecko'до азыр эң көп изделген монеталар (BingX'те бар): " + ", ".join("№%d %s (%s)" % (i, n, s) for i, n, s in tr))
    return "\n".join(lines), allowed


# ---------- Сандарды текшерүү ----------
NUM = re.compile(r"[+\-−]?\$?\d[\d,]*(?:\.\d+)?\s?(?:%|[KMB]\b)?")


def norm(tok):
    return tok.replace("−", "-").replace(" ", "").rstrip(",.")


def bad_numbers(post, allowed):
    """Маалыматта жок % жана $ сандарды табат (даталар, №, жалгыз цифралар эсепке алынбайт)."""
    allowed_n = {norm(a) for a in allowed} | {norm(a).lstrip("+") for a in allowed}
    bad = []
    for key in ("body_ky", "body_ru", "telegram_ky", "telegram_ru", "title_ky", "title_ru"):
        for m in NUM.finditer(post.get(key, "")):
            t = norm(m.group(0))
            if not ("%" in t or "$" in t):
                continue
            if t not in allowed_n and t.lstrip("+") not in allowed_n:
                bad.append(t)
    for h in post.get("highlights", []):
        for key in ("note_ky", "note_ru"):
            for m in NUM.finditer(h.get(key, "")):
                t = norm(m.group(0))
                if ("%" in t or "$" in t) and t not in allowed_n and t.lstrip("+") not in allowed_n:
                    bad.append(t)
    return sorted(set(bad))


# ---------- Claude ----------
def generate(facts, date_txt, feedback=None):
    import anthropic  # dry-run үчүн SDK талап кылынбайт

    client = anthropic.Anthropic()
    content = PROMPT.format(date=date_txt, facts=facts)
    if feedback:
        content += "\n\nМУРУНКУ ВАРИАНТТА ҮЧҮН КАТА: бул сандар FACTS тизмесинде жок: %s. Аларды алып сал же FACTS'тагы так жазылышын колдон." % ", ".join(feedback)
    resp = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM,
        messages=[{"role": "user", "content": content}],
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("Модель баш тартты: %s" % (resp.stop_details,))
    if resp.stop_reason == "max_tokens":
        raise RuntimeError("Жооп кесилип калды (max_tokens).")
    text = next(b.text for b in resp.content if b.type == "text")
    return json.loads(text), resp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    now = datetime.now(BISHKEK)
    date_txt = now.strftime("%d.%m.%Y")
    facts, allowed = build_facts()
    if args.dry_run:
        print(facts)
        print("\nУруксат берилген сандар:", len(allowed))
        return 0

    if not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        print("ANTHROPIC_API_KEY жок — пост жазылган жок (сайттагы эски пост калат).")
        return 0

    post, resp = generate(facts, date_txt)
    bad = bad_numbers(post, allowed)
    if bad:
        print("Текшерүү: маалыматта жок сандар табылды %s — кайра жаздырабыз." % bad)
        post, resp = generate(facts, date_txt, feedback=bad)
        bad = bad_numbers(post, allowed)
        if bad:
            print("Экинчи вариантта да ката %s — пост жарыяланган жок." % bad)
            return 1

    post.update({"date": now.strftime("%Y-%m-%d"), "created": now.isoformat(timespec="minutes"), "model": resp.model, "ai": True})
    try:
        with open(POSTS, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {"posts": []}
    posts = [p for p in data.get("posts", []) if p.get("date") != post["date"]]
    data = {"updated": post["created"], "posts": ([post] + posts)[:KEEP]}
    with open(POSTS, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("Пост сакталды:", post["title_ky"], "| tokens in/out:", resp.usage.input_tokens, resp.usage.output_tokens)
    return 0


if __name__ == "__main__":
    sys.exit(main())
