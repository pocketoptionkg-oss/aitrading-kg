/* AITRADING.KG — алдын ала катталуу: WhatsApp номери (брокерде катталуудан мурун милдеттүү).
   POST /api/lead  { wa: "+996 700 123 456", name?: "…", broker: "bingx"|"binodex"|"", lang: "ky"|"ru", page: "register" }
   Сакталат: Cloudflare KV (binding LEADS_KV), ачкыч lead:<убакыт36>-<кокус> — 120 күн.
   Telegram-бот (tools/tg_bot.py) /api/leads аркылуу жаңы заявкаларды алып, админге жиберет.
   Почта жана сырсөз суралбайт. */
import { json, sameOrigin } from "../../server/sign.js";

const TTL = 120 * 86400;
const PER_HOUR = 6;   // бир IP'ден саатына

function normPhone(s) {
  s = String(s || "").trim();
  const plus = s.startsWith("+") || s.startsWith("00");
  let d = s.replace(/\D/g, "");
  if (s.startsWith("00")) d = d.slice(2);
  if (!plus && /^0\d{9}$/.test(d)) d = "996" + d.slice(1);      // 0700123456 → 996700123456 (Кыргызстан)
  if (!plus && /^\d{9}$/.test(d)) d = "996" + d;                 // 700123456 → 996700123456
  if (!/^\d{10,15}$/.test(d)) return null;
  return "+" + d;
}

function clean(s, n) {
  return String(s || "").replace(/[\u0000-\u001f<>]/g, " ").replace(/\s+/g, " ").trim().slice(0, n);
}

export async function onRequest(context) {
  const { request, env } = context;
  if (request.method !== "POST") return json({ error: "method" }, 405);
  if (!sameOrigin(request)) return json({ error: "forbidden" }, 403);
  if (!env.LEADS_KV) return json({ error: "config" }, 503);

  let b;
  try { b = await request.json(); } catch (e) { return json({ error: "bad" }, 400); }
  const wa = normPhone(b && b.wa);
  if (!wa) return json({ error: "phone" }, 400);
  if (!b.consent) return json({ error: "consent" }, 400);

  const ip = request.headers.get("cf-connecting-ip") || "local";
  const hk = "rl:" + new Date().toISOString().slice(0, 13) + ":" + ip;
  const n = +(await env.LEADS_KV.get(hk)) || 0;
  if (n >= PER_HOUR) return json({ error: "limit" }, 429);
  await env.LEADS_KV.put(hk, String(n + 1), { expirationTtl: 3700 });

  const t = Date.now();
  const id = t.toString(36).padStart(9, "0") + "-" + Math.random().toString(36).slice(2, 8);
  const lead = {
    id, t, wa,
    name: clean(b.name, 60),
    broker: /^(bingx|binodex)$/.test(b.broker) ? b.broker : "",
    lang: b.lang === "ru" ? "ru" : "ky",
    page: clean(b.page, 30),
    country: (request.cf && request.cf.country) || ""
  };
  await env.LEADS_KV.put("lead:" + id, JSON.stringify(lead), { expirationTtl: TTL });
  return json({ ok: true, id });
}
