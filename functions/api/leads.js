/* AITRADING.KG — Telegram-бот үчүн: жаңы WhatsApp заявкалары.
   GET /api/leads?after=<акыркы id>   башы: X-Ts (ms), X-Sig = HMAC(LINK_SECRET, "leads|" + X-Ts)[0:22]
   Колу 5 мүнөт жарактуу. Жооп: { items: [lead…] } — id боюнча иреттелген, 50гө чейин. */
import { json, sign, same } from "../../server/sign.js";

export async function onRequest(context) {
  const { request, env } = context;
  if (request.method !== "GET") return json({ error: "method" }, 405);
  if (!env.LEADS_KV || !env.LINK_SECRET) return json({ error: "config" }, 503);
  const ts = request.headers.get("x-ts") || "";
  const sig = request.headers.get("x-sig") || "";
  if (!/^\d{12,14}$/.test(ts) || Math.abs(Date.now() - +ts) > 300000) return json({ error: "forbidden" }, 403);
  if (!same(sig, (await sign(env.LINK_SECRET, "leads|" + ts)).slice(0, 22))) return json({ error: "forbidden" }, 403);

  const after = new URL(request.url).searchParams.get("after") || "";
  const out = [];
  let cursor;
  do {
    const page = await env.LEADS_KV.list({ prefix: "lead:", cursor, limit: 1000 });
    for (const k of page.keys) {
      const id = k.name.slice(5);
      if (id > after) out.push(id);
    }
    cursor = page.list_complete ? null : page.cursor;
  } while (cursor && out.length < 200);
  out.sort();
  const items = [];
  for (const id of out.slice(0, 50)) {
    const v = await env.LEADS_KV.get("lead:" + id);
    if (v) { try { items.push(JSON.parse(v)); } catch (e) { /* бузук жазуу */ } }
  }
  return json({ items });
}
