/* AITRADING.KG — Telegram-бот үчүн: жаңы WhatsApp заявкалары.
   GET /api/leads?after=<акыркы id>   башы: X-Ts (ms), X-Sig = HMAC(LINK_SECRET, "leads|" + X-Ts)[0:22]
   Колу 5 мүнөт жарактуу. Жооп: { items: [lead…] } — id боюнча иреттелген, 50гө чейин. */
import { json, sign, same } from "../../server/sign.js";
import { idxAfter } from "../../server/kvidx.js";

export async function onRequest(context) {
  try {
    return await handle(context);
  } catch (e) {   // CF 1101/500 ордуна — бот себебин көрсүн (мис. KV чеги)
    return json({ error: "exception", detail: String((e && e.message) || e).slice(0, 300) }, 500);
  }
}

async function handle(context) {
  const { request, env } = context;
  if (request.method !== "GET") return json({ error: "method" }, 405);
  if (!env.LEADS_KV || !env.LINK_SECRET) return json({ error: "config" }, 503);
  const ts = request.headers.get("x-ts") || "";
  const sig = request.headers.get("x-sig") || "";
  if (!/^\d{12,14}$/.test(ts) || Math.abs(Date.now() - +ts) > 300000) return json({ error: "forbidden" }, 403);
  if (!same(sig, (await sign(env.LINK_SECRET, "leads|" + ts)).slice(0, 22))) return json({ error: "forbidden" }, 403);

  const after = new URL(request.url).searchParams.get("after") || "";
  const items = [];
  for (const id of await idxAfter(env.LEADS_KV, "lead", after, 50)) {   // list() эмес — суткалык чек бүтпөйт
    const v = await env.LEADS_KV.get("lead:" + id);
    if (v) { try { items.push(JSON.parse(v)); } catch (e) { /* бузук жазуу */ } }
  }
  return json({ items });
}
