/* AITRADING.KG — өнөктөштүк программа / партнёрская программа («Маркетинг» → панель управления).
   Маалыматтын булагы — Telegram-бот (tools/tg_partners.py): ал ким кимди чакырганын, катталганын жана толуктаганын билет.

   1) Бот → сайт, жаңыртуу:  POST /api/partner   башы X-Ts (ms), X-Sig = HMAC(LINK_SECRET, "partner|" + X-Ts + "|" + sha256(body))[0:22]
        body: { items: [ { tg36, code, route: { bd, bx, bot, on }, snap: {…панелдин маалыматы…} } ] }
        KV: pt:<tg36> = snap, pc:<code> = route (functions/r/[code].js окуйт), idx:pcode — коддордун индекси (list() жок).
   2) Бот ← сайт, өтүүлөр:   GET /api/partner?clicks=1   ошол эле кол ("partner|" + X-Ts + "|")  → { clicks: { code: { n, d7, d30 } } }
   3) Панель (браузер):      GET /api/partner?t=<tg36>.<exp36>.<sig>   sig = HMAC(LINK_SECRET, "ptn|" + tg36 + "|" + exp36)[0:22]
        → { ok, snap, clicks: { n, d7, d30, days } }. Чакырылгандардын аттары, номерлери, ID'лери бул жерге ЖЕТПЕЙТ — эсептер гана. */
import { json, sign, same } from "../../server/sign.js";
import { idxAdd } from "../../server/kvidx.js";

const enc = new TextEncoder();

async function sha(s) {
  const raw = new Uint8Array(await crypto.subtle.digest("SHA-256", enc.encode(s)));
  return Array.from(raw, (b) => b.toString(16).padStart(2, "0")).join("");
}

async function botSigned(request, env, body) {
  const ts = request.headers.get("x-ts") || "";
  const sig = request.headers.get("x-sig") || "";
  if (!/^\d{12,14}$/.test(ts) || Math.abs(Date.now() - +ts) > 300000) return false;
  return same(sig, (await sign(env.LINK_SECRET, "partner|" + ts + "|" + (await sha(body || "")))).slice(0, 22));
}

function clickSum(c) {
  const d = (c && c.d) || {};
  const now = Date.now();
  let d7 = 0, d30 = 0;
  const days = [];
  for (let i = 29; i >= 0; i--) {
    const k = new Date(now - i * 86400000).toISOString().slice(0, 10).replace(/-/g, "");
    const n = +d[k] || 0;
    days.push(n);
    d30 += n;
    if (i < 7) d7 += n;
  }
  return { n: (c && c.n) || 0, d7, d30, days };
}

async function readJson(kv, key) {
  try { return JSON.parse((await kv.get(key)) || "null"); } catch (e) { return null; }
}

export async function onRequest(context) {
  const { request, env } = context;
  if (!env.LEADS_KV || !env.LINK_SECRET) return json({ ok: false, error: "config" }, 503);
  const url = new URL(request.url);
  const kv = env.LEADS_KV;

  if (request.method === "POST") {
    const body = await request.text();
    if (body.length > 200000 || !(await botSigned(request, env, body))) return json({ error: "forbidden" }, 403);
    let b;
    try { b = JSON.parse(body); } catch (e) { return json({ error: "bad" }, 400); }
    let n = 0;
    for (const it of (b && b.items) || []) {
      if (!it || !/^[0-9a-z]{1,13}$/.test(it.tg36 || "") || !/^[a-z0-9]{4,16}$/.test(it.code || "")) continue;
      if (it.snap) await kv.put("pt:" + it.tg36, JSON.stringify(it.snap));
      if (it.route) {
        const had = await kv.get("pc:" + it.code);
        await kv.put("pc:" + it.code, JSON.stringify({
          t: it.tg36, on: it.route.on ? 1 : 0, main: it.route.main === "bd" ? "bd" : "bot",
          bd: String(it.route.bd || ""), bx: String(it.route.bx || ""), bot: String(it.route.bot || "")
        }));
        if (!had) await idxAdd(kv, "pcode", it.code);
      }
      n++;
    }
    return json({ ok: true, n });
  }

  if (request.method !== "GET") return json({ error: "method" }, 405);

  if (url.searchParams.get("clicks")) {
    if (!(await botSigned(request, env, ""))) return json({ error: "forbidden" }, 403);
    let codes = [];
    try { codes = JSON.parse((await kv.get("idx:pcode")) || "[]"); } catch (e) { codes = []; }
    const out = {};
    for (const code of codes.slice(-300)) {
      const s = clickSum(await readJson(kv, "ck:" + code));
      out[code] = { n: s.n, d7: s.d7, d30: s.d30 };
    }
    return json({ clicks: out });
  }

  // Панель: өнөктөштүн өз маалыматы гана
  const t = url.searchParams.get("t") || "";
  const m = /^([0-9a-z]{1,13})\.([0-9a-z]{1,10})\.([A-Za-z0-9_-]{22})$/.exec(t);
  if (!m) return json({ ok: false });
  if (!(parseInt(m[2], 36) * 1000 > Date.now())) return json({ ok: false, expired: true });
  if (!same(m[3], (await sign(env.LINK_SECRET, "ptn|" + m[1] + "|" + m[2])).slice(0, 22))) return json({ ok: false });
  const snap = await readJson(kv, "pt:" + m[1]);
  if (!snap) return json({ ok: true, pending: true });
  const clicks = snap.code ? clickSum(await readJson(kv, "ck:" + snap.code)) : clickSum(null);
  return json({ ok: true, snap, clicks });
}
