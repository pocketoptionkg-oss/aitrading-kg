/* AITRADING.KG — тиркемеге (PWA) билдирмелерге жазылуу. Cloudflare Pages Function: /api/push
   GET    → {ready, publicKey}            — сервер билдирме жөнөтө алабы
   POST   {subscription, lang}             — жазылуу (браузердин PushSubscription'у)
   DELETE {endpoint}                       — жазылуудан чыгуу
   Керек: KV binding LIVE_KV жана VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY (ОКУ_МЕНИ.md, 10-бөлүм). */
import { json, sameOrigin, sha, pushReady } from "../../lib/webpush.js";

const PUSH_HOSTS = /(^|\.)(fcm\.googleapis\.com|googleapis\.com|push\.services\.mozilla\.com|notify\.windows\.com|push\.apple\.com|push\.microsoft\.com)$/i;

function validEndpoint(ep) {
  try {
    const u = new URL(ep);
    return u.protocol === "https:" && PUSH_HOSTS.test(u.hostname) && ep.length < 900;
  } catch (e) {
    return false;
  }
}

export async function onRequestGet({ env }) {
  const ready = !!env.LIVE_KV && pushReady(env);
  return json({ ready, publicKey: ready ? env.VAPID_PUBLIC_KEY : null }, 200, { "cache-control": "public, max-age=300" });
}

export async function onRequestPost({ request, env }) {
  if (!sameOrigin(request)) return json({ error: "forbidden" }, 403);
  if (!env.LIVE_KV || !pushReady(env)) return json({ error: "config" }, 503);
  let body;
  try { body = await request.json(); } catch (e) { return json({ error: "bad" }, 400); }
  const ep = body && body.subscription && body.subscription.endpoint;
  if (!validEndpoint(ep)) return json({ error: "bad" }, 400);
  const lang = body.lang === "ru" ? "ru" : "ky";
  await env.LIVE_KV.put("sub:" + (await sha(ep)), "1", { metadata: { e: ep, l: lang, t: Date.now() } });
  return json({ ok: true });
}

export async function onRequestDelete({ request, env }) {
  if (!sameOrigin(request)) return json({ error: "forbidden" }, 403);
  if (!env.LIVE_KV) return json({ error: "config" }, 503);
  let body;
  try { body = await request.json(); } catch (e) { return json({ error: "bad" }, 400); }
  if (!body || typeof body.endpoint !== "string") return json({ error: "bad" }, 400);
  await env.LIVE_KV.delete("sub:" + (await sha(body.endpoint)));
  return json({ ok: true });
}
