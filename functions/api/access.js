/* AITRADING.KG — сайттагы сигналдарга доступ (ботто текшерүүдөн өткөндөр үчүн).
   Бот активдүү колдонуучуга шилтеме берет: https://сайт/forecast.html#acc=<tg36>.<exp36>.<sig>
   sig = HMAC(LINK_SECRET, "acc|" + tg36 + "|" + exp36)[0:22]. Сайт бул жерден текшертет:
   GET /api/access?t=<token> → { ok: true, exp } же { ok: false } */
import { json, sign, same, sameOrigin } from "../../server/sign.js";

export async function onRequest(context) {
  const { request, env } = context;
  if (request.method !== "GET") return json({ error: "method" }, 405);
  if (!env.LINK_SECRET) return json({ ok: false, error: "config" }, 503);
  const t = new URL(request.url).searchParams.get("t") || "";
  const m = /^([0-9a-z]{1,13})\.([0-9a-z]{1,10})\.([A-Za-z0-9_-]{22})$/.exec(t);
  if (!m) return json({ ok: false });
  const exp = parseInt(m[2], 36) * 1000;
  if (!(exp > Date.now())) return json({ ok: false, expired: true });
  const want = (await sign(env.LINK_SECRET, "acc|" + m[1] + "|" + m[2])).slice(0, 22);
  if (!same(m[3], want)) return json({ ok: false });
  return json({ ok: true, exp });
}
