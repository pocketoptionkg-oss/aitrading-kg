"""AITRADING.KG — өнөктөштүк программа (сайттагы «Маркетинг» → «Башкаруу панелине кирүү»).

Каалаган адам ботто «🤝 Өнөктөштүк» (/partner) басып өнөктөш болот → жеке код жана шилтеме алат:
    https://aitrading.kg/r/<код>   (сайт өтүүнү эсептеп, ботко ?start=p_<код> же өнөктөштүн BinoDex шилтемесине жиберет)
Ботко ушул шилтеме менен БИРИНЧИ жолу келген адам ошол өнөктөшкө жазылат (users.ref_partner). Кийин катталуу
(trader_id + биздин шилтеме) жана толуктоо (deposit / активдүү доступ) боттун учурдагы текшерүүсүнөн алынат.

Акча: авторго брокер ошол трейдерлер үчүн төлөгөн кирешенин PARTNER_SHARE (демейки 0.6 = 60%) бөлүгү.
Айлык кирешени автор ADMIN PANEL → «🤝 Өнөктөштөр» ичинде өзү киргизет (брокердин кабинетинен), бот 60%ды эсептейт,
төлөм кол менен, «✅ Төлөндү» белгиси менен. Сандар ойдон чыгарылбайт: киргизилбесе — 0.

Сайтка маалымат: бот 10 мүнөт сайын өзгөргөн өнөктөштөрдүн «сүрөтүн» POST /api/partner'ге жөнөтөт (functions/api/partner.js).
Панелге кирүү: кол коюлган шилтеме marketing.html#p=<tg36>.<exp36>.<sig> (30 күн). Чакырылгандардын аты, номери, ID'си
сайтка жөнөтүлбөйт — эсептер гана.

Чөйрө өзгөрмөлөрү: LINK_SECRET (сайт менен жалпы), PARTNER_SHARE (милдеттүү эмес), SITE_URL.
"""
import hashlib
import hmac
import base64
import html
import json
import os
import re
import secrets
import threading
import time
import urllib.parse
import urllib.request

import tg_signals as S

E = html.escape
SHARE = min(max(float(os.environ.get("PARTNER_SHARE") or 0.6), 0.0), 1.0)
PANEL_DAYS = 30
SYNC_EVERY = 600
CONFIG_JS = os.path.join(S.ROOT, "site", "assets", "js", "config.js")
CODE_ABC = "abcdefghjkmnpqrstuvwxyz23456789"          # окшош тамгаларсыз (0/o, 1/l/i)

SCHEMA = """
CREATE TABLE IF NOT EXISTS partners(tg_id INTEGER PRIMARY KEY, code TEXT UNIQUE, created INTEGER, on_ INTEGER DEFAULT 1,
  bd_url TEXT, pay TEXT, name TEXT);
CREATE TABLE IF NOT EXISTS partner_income(tg_id INTEGER, month TEXT, income REAL, payout REAL, paid INTEGER DEFAULT 0, paid_t INTEGER,
  set_t INTEGER, PRIMARY KEY(tg_id, month));
"""

TX = {
    "kg": {
        "intro": "🤝 <b>Өнөктөштүк программа</b>\n\n"
                 "Каалаган адам өнөктөш боло алат: жеке шилтемеңиз менен жаңы трейдерлерди <b>BinoDex</b> же <b>BingX</b>'ке чакырасыз.\n\n"
                 "💰 <b>{pct}%</b> — сиз чакырган трейдерлер үчүн брокер авторго (TRADER KG) төлөгөн кирешенин {pct}%ы сизге. "
                 "Эсеп айына бир жолу, төлөмдү автор кол менен жөнөтөт.\n"
                 "📊 Башкаруу панелинде: шилтемеге канча өтүү болду, канча адам ботко келди, катталды, толуктады жана канча эсептелди.\n\n"
                 "⚠️ Киреше кепилденбейт: брокер төлөбөсө — 0. Чакырылгандардын аты, номери көрсөтүлбөйт, эсептер гана.\n"
                 "Эрежелер: шилтеме өнөктөштүк экенин айтыңыз, «кепилденген киреше» деп убада бербеңиз, 18 жашка толбогондорго жарнама кылбаңыз.",
        "btn_join": "✅ Өнөктөш болуу",
        "btn_terms": "📖 Шарттар сайтта",
        "card": "🤝 <b>Сиз өнөктөшсүз</b> · код <code>{code}</code>\n\n"
                "🔗 Жеке шилтемеңиз:\n{main}\n\n"
                "👣 Шилтемеге өтүү: <b>{clicks}</b>\n👋 Ботко келди: <b>{inv}</b>\n📝 Брокерде катталды: <b>{reg}</b>\n"
                "💳 Толуктады: <b>{fund}</b> (азыр доступу ачык: {act})\n\n"
                "💰 Эсептелди: <b>${earned}</b> · төлөндү: ${paid} · <b>төлөнө элек: ${due}</b>\n"
                "💳 Төлөм реквизиттери: {pay}\n\n"
                "Эсеп: брокер авторго төлөгөн кирешенин {pct}%ы · айына бир жолу, кол менен.",
        "pay_none": "коюла элек ❗",
        "card_off": "\n\n⛔ Өнөктөштүгүңүз азыр өчүрүлгөн. Суроо болсо — 💬 Колдоо.",
        "btn_panel": "📊 Башкаруу панели",
        "btn_share": "📤 Шилтемени бөлүшүү",
        "btn_pay": "💳 Төлөм реквизиттери",
        "btn_refresh": "🔄 Жаңыртуу",
        "share_text": "AITRADING.KG — ИИ сигналдары жана сабактар (BinoDex, BingX). 18+, соода тобокелдиктүү.",
        "ask_pay": "💳 Төлөм кайда жөнөтүлсүн? Бир билдирүү менен жазыңыз, мисалы:\n<code>USDT TRC20: T…</code> же <code>BingX UID 12345678</code>\n(150 белгиге чейин. Сырсөз, карта коду, SMS-код ЖАЗБАҢЫЗ.)",
        "pay_ok": "✓ Реквизиттер сакталды.",
        "pay_bad": "Өтө узун же бош. 150 белгиге чейин жазыңыз.",
        "joined": "🎉 Даяр! Сиз өнөктөшсүз. Шилтемеңизди бөлүшүңүз — ар бир келген, катталган жана толуктаган адам панелде көрүнөт.",
        "new_ref": "👋 Сиздин шилтеме менен жаңы адам ботко келди. Азыр ботко келгендер: <b>{inv}</b>.",
        "new_reg": "📝 Сиз чакырган адамдардан дагы {n} киши брокерде катталды. Баары: <b>{reg}</b>.",
        "new_fund": "💳 Сиз чакырган адамдардан дагы {n} киши эсебин толуктады. Баары: <b>{fund}</b>.",
        "paid": "💸 {m} айы үчүн <b>${v}</b> төлөндү деп белгиленди. Рахмат!",
        "accrued": "💰 {m} айы үчүн эсептелди: <b>${v}</b> (брокерден келген кирешенин {pct}%ы). Төлөм кол менен жөнөтүлөт.",
    },
    "ru": {
        "intro": "🤝 <b>Партнёрская программа</b>\n\n"
                 "Партнёром может стать любой: по личной ссылке вы приглашаете новых трейдеров на <b>BinoDex</b> или <b>BingX</b>.\n\n"
                 "💰 <b>{pct}%</b> — вам {pct}% от дохода, который брокер платит автору (TRADER KG) за приглашённых вами трейдеров. "
                 "Расчёт раз в месяц, выплату автор отправляет вручную.\n"
                 "📊 В панели управления: сколько было переходов по ссылке, сколько людей пришли в бот, зарегистрировались, пополнили и сколько начислено.\n\n"
                 "⚠️ Доход не гарантирован: если брокер ничего не заплатил — 0. Имена и номера приглашённых не показываются, только количество.\n"
                 "Правила: говорите, что ссылка партнёрская, не обещайте «гарантированный доход», не рекламируйте лицам младше 18 лет.",
        "btn_join": "✅ Стать партнёром",
        "btn_terms": "📖 Условия на сайте",
        "card": "🤝 <b>Вы партнёр</b> · код <code>{code}</code>\n\n"
                "🔗 Ваша личная ссылка:\n{main}\n\n"
                "👣 Переходов по ссылке: <b>{clicks}</b>\n👋 Пришли в бот: <b>{inv}</b>\n📝 Зарегистрировались у брокера: <b>{reg}</b>\n"
                "💳 Пополнили: <b>{fund}</b> (сейчас с доступом: {act})\n\n"
                "💰 Начислено: <b>${earned}</b> · выплачено: ${paid} · <b>к выплате: ${due}</b>\n"
                "💳 Реквизиты для выплаты: {pay}\n\n"
                "Расчёт: {pct}% от дохода, который брокер платит автору · раз в месяц, вручную.",
        "pay_none": "не указаны ❗",
        "card_off": "\n\n⛔ Ваше партнёрство сейчас отключено. Вопросы — 💬 Поддержка.",
        "btn_panel": "📊 Панель управления",
        "btn_share": "📤 Поделиться ссылкой",
        "btn_pay": "💳 Реквизиты для выплаты",
        "btn_refresh": "🔄 Обновить",
        "share_text": "AITRADING.KG — ИИ-сигналы и обучение (BinoDex, BingX). 18+, торговля рискованна.",
        "ask_pay": "💳 Куда отправлять выплату? Напишите одним сообщением, например:\n<code>USDT TRC20: T…</code> или <code>BingX UID 12345678</code>\n(до 150 символов. НЕ пишите пароли, коды карт, SMS-коды.)",
        "pay_ok": "✓ Реквизиты сохранены.",
        "pay_bad": "Слишком длинно или пусто. Напишите до 150 символов.",
        "joined": "🎉 Готово! Вы партнёр. Делитесь ссылкой — каждый, кто пришёл, зарегистрировался и пополнил, появится в панели.",
        "new_ref": "👋 По вашей ссылке в бот пришёл новый человек. Всего пришли: <b>{inv}</b>.",
        "new_reg": "📝 Ещё {n} из приглашённых вами зарегистрировались у брокера. Всего: <b>{reg}</b>.",
        "new_fund": "💳 Ещё {n} из приглашённых вами пополнили счёт. Всего: <b>{fund}</b>.",
        "paid": "💸 Выплата за {m}: <b>${v}</b> отмечена как отправленная. Спасибо!",
        "accrued": "💰 Начислено за {m}: <b>${v}</b> ({pct}% от дохода от брокера). Выплата отправляется вручную.",
    },
}


def tx(u, key, **kw):
    lang = (u or {}).get("lang") or "kg"
    v = TX.get(lang, TX["kg"]).get(key, TX["kg"].get(key, key))
    return v.format(**kw) if kw else v


def ik(rows):
    kb = []
    for r in rows:
        row = []
        for t, v in r:
            if v is None:
                continue
            row.append({"text": t, "url": v} if re.match(r"^(https?|tg)://", v) else {"text": t, "callback_data": v})
        if row:
            kb.append(row)
    return {"inline_keyboard": kb}


def money(v):
    return ("%.2f" % float(v or 0)).rstrip("0").rstrip(".") if v else "0"


def secret():
    return (os.environ.get("LINK_SECRET") or "").strip()


def sig(msg, n):
    raw = hmac.new(secret().encode(), msg.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")[:n]


def b36(n):
    n, s = int(n), ""
    while True:
        n, r = divmod(n, 36)
        s = "0123456789abcdefghijklmnopqrstuvwxyz"[r] + s
        if not n:
            return s


def month_now():
    return S.datetime.now(S.BISHKEK).strftime("%Y-%m")


def month_prev():
    d = S.datetime.now(S.BISHKEK).replace(day=1) - S.timedelta(days=1)
    return d.strftime("%Y-%m")


def config_ref(name):
    try:
        with open(CONFIG_JS, encoding="utf-8") as f:
            m = re.search(name + r'\s*:\s*"([^"]*)"', f.read())
        return m.group(1).strip() if m and m.group(1).startswith("https://") else ""
    except OSError:
        return ""


class Partners:
    def __init__(self, app):
        self.app, self.db = app, app.db
        with self.db.lock:
            self.db.c.executescript(SCHEMA)
            cols = {r[1] for r in self.db.c.execute("PRAGMA table_info(users)").fetchall()}
            for col in ("ref_partner", "ref_t"):
                if col not in cols:
                    self.db.c.execute("ALTER TABLE users ADD COLUMN %s INTEGER" % col)
            self.db.c.execute("CREATE INDEX IF NOT EXISTS users_refp ON users(ref_partner)")
            self.db.c.commit()
        self.sync_lock = threading.Lock()

    # ---------- маалымат ----------
    def get(self, tg):
        return self.db.one("SELECT * FROM partners WHERE tg_id=?", (int(tg),))

    def by_code(self, code):
        return self.db.one("SELECT * FROM partners WHERE code=?", (str(code or "").lower(),))

    def all(self):
        return self.db.q("SELECT * FROM partners ORDER BY created")

    def bot_base(self):
        if self.app.username:
            return "https://t.me/" + self.app.username
        u = config_ref("TELEGRAM_BOT_URL")
        return u.rstrip("/") if re.match(r"^https://t\.me/[A-Za-z0-9_]{5,}/?$", u) else ""

    def links(self, p):
        site = S.SITE_URL + "/r/" + p["code"]
        bot = self.bot_base()
        return {"main": site, "bot_direct": (bot + "?start=p_" + p["code"]) if bot else "",
                "binodex": site + "?b=binodex", "bingx": site + "?b=bingx", "via_bot": site + "?b=bot"}

    def route(self, p):
        bot = self.bot_base()
        bd = (p.get("bd_url") or "").strip()
        return {"on": 1 if p.get("on_") else 0,
                "bd": bd or (self.app.refs.get("binodex") or config_ref("BINODEX_REF_URL")),
                "bx": self.app.refs.get("bingx") or config_ref("BINGX_REF_URL"),
                "bot": (bot + "?start=p_" + p["code"]) if bot else "",
                "main": "bd" if bd else "bot"}

    def counts(self, tg):
        r = self.db.one(
            "SELECT COUNT(*) inv,"
            " SUM(CASE WHEN trader_id IS NOT NULL AND trader_id<>'' AND COALESCE(invited,1)<>0 THEN 1 ELSE 0 END) reg,"
            " SUM(CASE WHEN deposit=1 OR verified_at IS NOT NULL OR status='active' THEN 1 ELSE 0 END) fund,"
            " SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) act,"
            " SUM(CASE WHEN broker='binodex' AND trader_id IS NOT NULL AND COALESCE(invited,1)<>0 THEN 1 ELSE 0 END) reg_bd,"
            " SUM(CASE WHEN broker='bingx' AND trader_id IS NOT NULL AND COALESCE(invited,1)<>0 THEN 1 ELSE 0 END) reg_bx"
            " FROM users WHERE ref_partner=?", (int(tg),)) or {}
        return {k: int(r.get(k) or 0) for k in ("inv", "reg", "fund", "act", "reg_bd", "reg_bx")}

    def months(self, tg):
        return self.db.q("SELECT month, income, payout, paid, paid_t FROM partner_income WHERE tg_id=? ORDER BY month DESC", (int(tg),))

    def totals(self, tg):
        r = self.db.one("SELECT SUM(payout) e, SUM(CASE WHEN paid=1 THEN payout ELSE 0 END) p FROM partner_income WHERE tg_id=?", (int(tg),)) or {}
        e, p = round(r.get("e") or 0, 2), round(r.get("p") or 0, 2)
        return {"earned": e, "paid": p, "due": round(e - p, 2)}

    def clicks(self, code):
        return ((self.db.kv("pt_clicks") or {}).get(code) or {}).get("n", 0)

    def panel_url(self, tg):
        if not secret():
            return None
        tg36, exp36 = b36(tg), b36(int(time.time()) + PANEL_DAYS * 86400)
        return "%s/marketing.html#p=%s.%s.%s" % (S.SITE_URL, tg36, exp36, sig("ptn|%s|%s" % (tg36, exp36), 22))

    def snapshot(self, p):
        tg = p["tg_id"]
        c = self.counts(tg)
        days = {}
        for r in self.db.q("SELECT created, ref_t, status, trader_id, invited, deposit, verified_at FROM users WHERE ref_partner=?", (tg,)):
            d = S.datetime.fromtimestamp((r.get("ref_t") or r.get("created") or 0) / 1000, S.BISHKEK).strftime("%Y-%m-%d")
            x = days.setdefault(d, [0, 0, 0])
            x[0] += 1
            if r.get("trader_id") and (r.get("invited") is None or r.get("invited")):
                x[1] += 1
            if r.get("deposit") == 1 or r.get("verified_at") or r.get("status") == "active":
                x[2] += 1
        recent = [{"d": d, "inv": v[0], "reg": v[1], "fund": v[2]} for d, v in sorted(days.items())[-14:]]
        L = self.links(p)
        return {
            "code": p["code"], "name": (p.get("name") or "")[:40], "created": p["created"], "on": 1 if p.get("on_") else 0,
            "share": SHARE, "own_bd": bool((p.get("bd_url") or "").strip()), "pay_set": bool((p.get("pay") or "").strip()),
            "links": {"main": L["main"], "binodex": L["binodex"], "bingx": L["bingx"], "bot": L["via_bot"]},
            "counts": c, "recent": recent,
            "months": [{"m": m["month"], "income": round(m["income"] or 0, 2), "payout": round(m["payout"] or 0, 2), "paid": int(m["paid"] or 0)}
                       for m in self.months(tg)[:24]],
            "totals": self.totals(tg),
        }

    # ---------- колдонуучу тарабы ----------
    def on_start(self, u, arg, was_new):
        """/start partner — бөлүм; /start p_<код> — жаңы колдонуучуну өнөктөшкө жазуу (эскилер өзгөрбөйт)."""
        if arg == "partner":
            return self.show(u)
        m = re.match(r"^p_([a-z0-9]{4,16})$", arg or "")
        if not m:
            return None
        p = self.by_code(m.group(1))
        if not p or not p.get("on_") or p["tg_id"] == u["id"] or not was_new or u.get("ref_partner"):
            return None
        self.db.upd(u["id"], ref_partner=p["tg_id"], ref_t=S.now_ms())
        pu = self.db.user(p["tg_id"])
        if pu:
            self.app.send(p["tg_id"], tx(pu, "new_ref", inv=self.counts(p["tg_id"])["inv"]))
        self.sync_later(p["tg_id"])
        return None

    def ref_for(self, u, broker):
        """Өнөктөш чакырган адамга BinoDex'те — өнөктөштүн өз шилтемеси (админ берген болсо)."""
        if broker != "binodex" or not u.get("ref_partner"):
            return None
        p = self.get(u["ref_partner"])
        if not p or not p.get("on_"):
            return None
        return (p.get("bd_url") or "").strip() or None

    def show(self, u, mid=None):
        uid = u["id"]
        p = self.get(uid)
        pct = int(round(SHARE * 100))
        if not p:
            return self.app.send(uid, tx(u, "intro", pct=pct), ik([[(tx(u, "btn_join"), "pt:join")],
                                                                    [(tx(u, "btn_terms"), S.SITE_URL + "/marketing.html#partner")]]))
        c, t, L = self.counts(uid), self.totals(uid), self.links(p)
        text = tx(u, "card", code=E(p["code"]), main=E(L["main"]), clicks=self.clicks(p["code"]), inv=c["inv"], reg=c["reg"], fund=c["fund"],
                  act=c["act"], earned=money(t["earned"]), paid=money(t["paid"]), due=money(t["due"]),
                  pay=E(p["pay"]) if p.get("pay") else tx(u, "pay_none"), pct=pct)
        if not p.get("on_"):
            text += tx(u, "card_off")
        share = "https://t.me/share/url?" + urllib.parse.urlencode({"url": L["main"], "text": tx(u, "share_text")})
        return self.app.send(uid, text, ik([[(tx(u, "btn_panel"), self.panel_url(uid))],
                                            [(tx(u, "btn_share"), share)],
                                            [(tx(u, "btn_pay"), "pt:pay"), (tx(u, "btn_refresh"), "pt:me")]]))

    def new_code(self):
        for _ in range(50):
            c = "".join(secrets.choice(CODE_ABC) for _ in range(6))
            if not self.by_code(c):
                return c
        raise RuntimeError("partner code")

    def join(self, u):
        uid = u["id"]
        if not self.get(uid):
            name = (u.get("first_name") or "")[:40]
            self.db.x("INSERT INTO partners(tg_id, code, created, on_, name) VALUES(?,?,?,1,?)", (uid, self.new_code(), S.now_ms(), name))
            p = self.get(uid)
            self.app.notify_admins("🤝 <b>Жаңы өнөктөш</b>: %s · код <code>%s</code>" % (self.app.user_link(u), E(p["code"])),
                                   ik([[("🤝 Карточка", "pa:p:%d" % uid)]]))
            self.app.send(uid, tx(u, "joined"))
            self.sync_later(uid)
        return self.show(self.db.user(uid))

    def on_cb(self, u, data, msg):
        if data == "pt:join":
            return self.join(u)
        if data == "pt:me":
            return self.show(u)
        if data == "pt:pay" and self.get(u["id"]):
            self.db.upd(u["id"], step="pt:pay")
            return self.app.send(u["id"], tx(u, "ask_pay"))
        return None

    def on_step(self, u, text):
        if u.get("step") != "pt:pay":
            return None
        text = re.sub(r"[\u0000-\u001f]", " ", text or "").strip()
        if not text or len(text) > 150:
            return self.app.send(u["id"], tx(u, "pay_bad"))
        self.db.upd(u["id"], step=None)
        self.db.x("UPDATE partners SET pay=? WHERE tg_id=?", (text, u["id"]))
        self.app.send(u["id"], tx(u, "pay_ok"))
        self.sync_later(u["id"])
        return self.show(self.db.user(u["id"]))

    # ---------- ADMIN PANEL ----------
    def admin_row(self):
        n = (self.db.one("SELECT COUNT(*) n FROM partners") or {}).get("n", 0)
        return [("🤝 Өнөктөштөр (%d)" % n, "pa:home")]

    def p_line(self, p):
        c, t = self.counts(p["tg_id"]), self.totals(p["tg_id"])
        return "%s<code>%s</code> %s · 👣%d 👋%d 📝%d 💳%d · эсептелди $%s · <b>карыз $%s</b>" % (
            "" if p.get("on_") else "⛔ ", E(p["code"]), E(p.get("name") or ""), self.clicks(p["code"]),
            c["inv"], c["reg"], c["fund"], money(t["earned"]), money(t["due"]))

    def report(self):
        ps = self.all()
        if not ps:
            return "🤝 <b>Өнөктөштөр</b>\nАзырынча жок. Сайттагы «Маркетинг» → «Башкаруу панелине кирүү» же ботто /partner."
        tot = {"e": 0.0, "p": 0.0}
        lines = []
        for p in ps:
            t = self.totals(p["tg_id"])
            tot["e"] += t["earned"]
            tot["p"] += t["paid"]
            lines.append("• " + self.p_line(p))
        unset = [p["code"] for p in ps if p.get("on_") and not self.db.one("SELECT 1 x FROM partner_income WHERE tg_id=? AND month=?", (p["tg_id"], month_prev()))]
        return ("🤝 <b>Өнөктөштөр</b> · %d · үлүш %d%%\n👣 өтүү · 👋 ботко келди · 📝 катталды · 💳 толуктады\n\n%s\n\n"
                "Баары эсептелди: <b>$%s</b> · төлөндү: $%s · <b>төлөнө элек: $%s</b>%s") % (
            len(ps), int(round(SHARE * 100)), "\n".join(lines), money(tot["e"]), money(tot["p"]), money(tot["e"] - tot["p"]),
            ("\n⚠️ %s айынын кирешеси киргизиле элек: %s" % (month_prev(), ", ".join(unset[:20]))) if unset else "")

    def p_card(self, aid, tg, mid=None):
        p = self.get(tg)
        if not p:
            return self.app.send(aid, "Өнөктөш табылган жок.")
        pu = self.db.user(tg) or {"id": tg}
        L, r = self.links(p), self.route(p)
        ms = self.months(tg)
        mtxt = "\n".join("  %s: киреше $%s → %d%% = <b>$%s</b> %s" % (m["month"], money(m["income"]), int(round(SHARE * 100)), money(m["payout"]),
                                                                    "✅ төлөндү" if m["paid"] else "⏳") for m in ms[:6]) or "  азырынча жок"
        text = ("🤝 <b>Өнөктөш</b> %s\n%s\nКод: <code>%s</code> · %s\nШилтеме: %s\nBinoDex шилтемеси: %s\nРеквизиттер: %s\n\nАйлар:\n%s") % (
            self.app.user_link(pu), self.p_line(p), E(p["code"]), "иштейт" if p.get("on_") else "⛔ өчүк", E(L["main"]),
            E(p["bd_url"]) if p.get("bd_url") else "жок (автордун жалпы шилтемеси: %s)" % E(r["bd"] or "—"),
            E(p["pay"]) if p.get("pay") else "коюла элек", mtxt)
        rows = [[("🔗 BinoDex шилтемеси", "pa:bd:%d" % tg), ("💵 Айлык киреше", "pa:inc:%d" % tg)]]
        for m in ms:
            if not m["paid"] and (m["payout"] or 0) > 0:
                rows.append([("✅ %s төлөндү ($%s)" % (m["month"], money(m["payout"])), "pa:paid:%d:%s" % (tg, m["month"]))])
        rows.append([("⛔ Өчүрүү" if p.get("on_") else "▶️ Иштетүү", "pa:on:%d" % tg), ("⬅️ Тизме", "pa:home")])
        return self.app.edit(aid, mid, text, ik(rows)) if mid else self.app.send(aid, text, ik(rows))

    def on_admin_cb(self, u, data, msg):
        aid, mid = u["id"], msg.get("message_id")
        parts = data.split(":")
        if data == "pa:home":
            ps = self.all()
            rows = [[("%s%s · %s" % ("" if p.get("on_") else "⛔ ", p["code"], (p.get("name") or "")[:16]), "pa:p:%d" % p["tg_id"])] for p in ps[-30:]]
            rows.append([("🔄 Сайтка жөнөтүү", "pa:sync"), ("⬅️ ADMIN PANEL", "adm:home")])
            return self.app.send(aid, self.report(), ik(rows))
        if data == "pa:sync":
            n = self.sync(force=True)
            return self.app.send(aid, "🔄 Сайтка жөнөтүлдү: %s" % n)
        if len(parts) >= 3 and parts[2].isdigit():
            act, tg = parts[1], int(parts[2])
            p = self.get(tg)
            if not p:
                return self.app.send(aid, "Өнөктөш табылган жок.")
            if act == "p":
                return self.p_card(aid, tg)
            if act == "bd":
                self.db.kv_set("pa_step:%d" % aid, {"k": "bd", "tg": tg})
                return self.app.send(aid, "🔗 BinoDex кабинетинен <b>%s</b> үчүн түзгөн жаңы шилтемени жөнөтүңүз (https://…).\n"
                                          "«-» — алып салуу (анда автордун жалпы шилтемеси колдонулат)." % E(p["code"]))
            if act == "inc":
                self.db.kv_set("pa_step:%d" % aid, {"k": "inc", "tg": tg})
                return self.app.send(aid, ("💵 <b>%s</b> чакырган трейдерлерден брокер СИЗГЕ төлөгөн киреше, $ (брокердин кабинетинен).\n"
                                           "Жазыңыз: <code>120.50</code> — өткөн ай (%s), же <code>%s 120.50</code> — так ай.\n"
                                           "Бот %d%%ын эсептейт. Ошол айдын мурдагы суммасы алмаштырылат.") % (
                    E(p["code"]), month_prev(), month_now(), int(round(SHARE * 100))))
            if act == "paid" and len(parts) == 4 and re.match(r"^\d{4}-\d{2}$", parts[3]):
                m = self.db.one("SELECT * FROM partner_income WHERE tg_id=? AND month=?", (tg, parts[3]))
                if m and not m["paid"]:
                    self.db.x("UPDATE partner_income SET paid=1, paid_t=? WHERE tg_id=? AND month=?", (S.now_ms(), tg, parts[3]))
                    pu = self.db.user(tg)
                    if pu:
                        self.app.send(tg, tx(pu, "paid", m=parts[3], v=money(m["payout"])))
                    self.sync_later(tg)
                return self.p_card(aid, tg, mid)
            if act == "on":
                self.db.x("UPDATE partners SET on_=? WHERE tg_id=?", (0 if p.get("on_") else 1, tg))
                self.sync_later(tg)
                return self.p_card(aid, tg, mid)
        return None

    def on_admin_text(self, u, text):
        aid = u["id"]
        st = self.db.kv("pa_step:%d" % aid)
        if not st:
            return False
        self.db.kv_set("pa_step:%d" % aid, None)
        tg, text = int(st["tg"]), (text or "").strip()
        p = self.get(tg)
        if not p:
            self.app.send(aid, "Өнөктөш табылган жок.")
            return True
        if st["k"] == "bd":
            if text == "-":
                self.db.x("UPDATE partners SET bd_url=NULL WHERE tg_id=?", (tg,))
            elif re.match(r"^https://[^\s<>\"']{6,300}$", text):
                self.db.x("UPDATE partners SET bd_url=? WHERE tg_id=?", (text, tg))
            else:
                self.app.send(aid, "Шилтеме https:// менен башталышы керек. Кайра «🔗 BinoDex шилтемеси» басыңыз.")
                return True
            self.sync_later(tg)
            self.p_card(aid, tg)
            return True
        if st["k"] == "inc":
            m = re.match(r"^(?:(\d{4}-\d{2})\s+)?\$?\s*(\d{1,7}(?:[.,]\d{1,2})?)\s*\$?$", text)
            if not m:
                self.app.send(aid, "Түшүнгөн жокмун. Мисал: <code>120.50</code> же <code>%s 120.50</code>. Кайра «💵 Айлык киреше» басыңыз." % month_now())
                return True
            month = m.group(1) or month_prev()
            inc = round(float(m.group(2).replace(",", ".")), 2)
            old = self.db.one("SELECT * FROM partner_income WHERE tg_id=? AND month=?", (tg, month))
            if old and old["paid"]:
                self.app.send(aid, "⛔ %s айы төлөндү деп белгиленген — өзгөртүлбөйт." % month)
                return True
            pay = round(inc * SHARE, 2)
            self.db.x("INSERT INTO partner_income(tg_id, month, income, payout, paid, set_t) VALUES(?,?,?,?,0,?) "
                      "ON CONFLICT(tg_id, month) DO UPDATE SET income=excluded.income, payout=excluded.payout, set_t=excluded.set_t",
                      (tg, month, inc, pay, S.now_ms()))
            self.app.send(aid, "✓ %s · %s: киреше $%s → %d%% = <b>$%s</b> төлөнө турган." % (E(p["code"]), month, money(inc), int(round(SHARE * 100)), money(pay)))
            pu = self.db.user(tg)
            if pu and pay > 0:
                self.app.send(tg, tx(pu, "accrued", m=month, v=money(pay), pct=int(round(SHARE * 100))))
            self.sync_later(tg)
            self.p_card(aid, tg)
            return True
        return False

    # ---------- сайт менен синхрондоо ----------
    def post(self, path, body, method="POST"):
        ts = str(S.now_ms())
        data = body.encode("utf-8") if body else None
        h = hashlib.sha256((body or "").encode("utf-8")).hexdigest()
        req = urllib.request.Request(S.SITE_URL + path, data=data, method=method, headers={
            "content-type": "application/json", "x-ts": ts, "x-sig": sig("partner|%s|%s" % (ts, h), 22), "User-Agent": S.UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8") or "{}")

    def pull_clicks(self):
        r = self.post("/api/partner?clicks=1", "", method="GET")
        if isinstance(r.get("clicks"), dict):
            self.db.kv_set("pt_clicks", r["clicks"])

    def sync_later(self, tg=None):
        threading.Thread(target=self._sync_safe, daemon=True).start()

    def _sync_safe(self):
        try:
            self.sync()
        except Exception as e:  # noqa: BLE001
            print("! partners sync: %s" % self.app.tg.redact(e))

    def sync(self, force=False):
        """Өзгөргөн өнөктөштөрдү гана жөнөтөт (KV жазуулары үнөмдөлөт). Кайтарат: жөнөтүлгөн саны."""
        if not secret():
            return 0
        with self.sync_lock:
            items, marks = [], []
            for p in self.all():
                tg36 = b36(p["tg_id"])
                snap, route = self.snapshot(p), self.route(p)
                hs = hashlib.sha1(json.dumps(snap, sort_keys=True).encode()).hexdigest()
                hr = hashlib.sha1(json.dumps(route, sort_keys=True).encode()).hexdigest()
                ks, kr = "pt_hs:%d" % p["tg_id"], "pt_hr:%d" % p["tg_id"]
                it = {"tg36": tg36, "code": p["code"]}
                if force or self.db.kv(ks) != hs:
                    snap["updated"] = S.now_ms()
                    it["snap"] = snap
                    marks.append((ks, hs))
                if force or self.db.kv(kr) != hr:
                    it["route"] = route
                    marks.append((kr, hr))
                if len(it) > 2:
                    items.append(it)
            sent = 0
            for i in range(0, len(items), 20):
                r = self.post("/api/partner", json.dumps({"items": items[i:i + 20]}, ensure_ascii=False))
                sent += int(r.get("n") or 0)
            for k, v in marks:
                self.db.kv_set(k, v)
            return sent

    def notify_progress(self):
        """Өнөктөшкө: чакырган адамдары катталды / толуктады (аттарысыз)."""
        for p in self.all():
            c = self.counts(p["tg_id"])
            k = "pt_last:%d" % p["tg_id"]
            last = self.db.kv(k)
            self.db.kv_set(k, c)
            pu = self.db.user(p["tg_id"])
            if not last or not pu or not p.get("on_"):
                continue
            if c["reg"] > last.get("reg", 0):
                self.app.send(p["tg_id"], tx(pu, "new_reg", n=c["reg"] - last.get("reg", 0), reg=c["reg"]))
            if c["fund"] > last.get("fund", 0):
                self.app.send(p["tg_id"], tx(pu, "new_fund", n=c["fund"] - last.get("fund", 0), fund=c["fund"]))

    def monthly(self):
        """Айдын 1-күнү 10:00дөн кийин ээсине: отчёт + өткөн айдын кирешесин киргизүү эскертмеси."""
        now = S.datetime.now(S.BISHKEK)
        if now.day != 1 or now.hour < 10 or not self.app.owner or not self.all():
            return
        k = "pt_month:" + now.strftime("%Y-%m")
        if self.db.kv(k):
            return
        self.db.kv_set(k, 1)
        self.app.send(self.app.owner, "📅 <b>Өнөктөштөр: айлык отчёт</b>\n%s айынын кирешесин ар бир өнөктөшкө «💵 Айлык киреше» аркылуу киргизиңиз.\n\n%s" % (
            month_prev(), self.report()), ik([[("🤝 Өнөктөштөр", "pa:home")]]))

    def loop(self):
        time.sleep(20)
        n = 0
        while True:
            try:
                if n % 3 == 0:
                    self.pull_clicks()
                self.notify_progress()
                self.sync()
                self.monthly()
            except Exception as e:  # noqa: BLE001
                print("! partners: %s" % self.app.tg.redact(e))
            n += 1
            time.sleep(SYNC_EVERY)
