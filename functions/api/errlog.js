/* AITRADING.KG — боттун каталар журналы (Claude ушул жерден алып, оңдоп, жаңыртат).
   POST /api/errlog   бот: башы X-Ts, X-Sig = HMAC(LINK_SECRET, "err|" + X-Ts)[0:22]; тело {where,msg,sig,n,t,tb}
   GET  /api/errlog?after=<id>   окуу: башы X-Key = ERRLOG_READ_KEY (автордун компьютериндеги tools/pull_errors.py)
   Сакталат: LEADS_KV, ачкыч err:<убакыт36>-<кокус>, 30 күн. */
import { json, sign, same } from "../../server/sign.js";

export async function onRequest(context) {
  const { request, env } = context;
  if (!env.LEADS_KV || !env.LINK_SECRET) return json({ error: "config" }, 503);

  if (request.method === "POST") {
    const ts = request.headers.get("x-ts") || "";
    const sig = request.headers.get("x-sig") || "";
    if (!/^\d{12,14}$/.test(ts) || Math.abs(Date.now() - +ts) > 300000) return json({ error: "forbidden" }, 403);
    if (!same(sig, (await sign(env.LINK_SECRET, "err|" + ts)).slice(0, 22))) return json({ error: "forbidden" }, 403);
    let b;
    try { b = await request.json(); } catch (e) { return json({ error: "bad" }, 400); }
    const item = {
      where: String(b.where || "").slice(0, 60), msg: String(b.msg || "").slice(0, 400), sig: String(b.sig || "").slice(0, 16),
      n: +b.n || 1, t: +b.t || Date.now(), tb: String(b.tb || "").slice(0, 3000)
    };
    const id = Date.now().toString(36).padStart(9, "0") + "-" + Math.random().toString(36).slice(2, 7);
    item.id = id;
    await env.LEADS_KV.put("err:" + id, JSON.stringify(item), { expirationTtl: 30 * 86400 });
    return json({ ok: true, id });
  }

  if (request.method === "GET") {
    const rk = String(env.ERRLOG_READ_KEY || "").trim();   // wrangler stdin аркылуу жаңы сап кошулуп калышы мүмкүн
    if (!rk || !same((request.headers.get("x-key") || "").trim(), rk)) return json({ error: "forbidden" }, 403);
    const after = new URL(request.url).searchParams.get("after") || "";
    const ids = [];
    let cursor;
    do {
      const page = await env.LEADS_KV.list({ prefix: "err:", cursor, limit: 1000 });
      for (const k of page.keys) { const id = k.name.slice(4); if (id > after) ids.push(id); }
      cursor = page.list_complete ? null : page.cursor;
    } while (cursor);
    ids.sort();
    const items = [];
    for (const id of ids.slice(0, 50)) {
      const v = await env.LEADS_KV.get("err:" + id);
      if (v) { try { items.push(JSON.parse(v)); } catch (e) { /* */ } }
    }
    return json({ items });
  }
  return json({ error: "method" }, 405);
}
