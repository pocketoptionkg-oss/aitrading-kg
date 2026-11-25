/* AITRADING.KG — шашылыш жаңылыктар жана твиттер (бот → сайт → тиркеме). Cloudflare Pages Function: /api/live
   GET  → {ok, alert, urgent[], tweets[], t}      — сайт ар мүнөттө окуйт, sw.js push келгенде окуйт
   POST (X-Live-Key: LIVE_KEY) — Telegram-бот гана (tools/tg_bot.py), ПК'дан:
        {type:"alert",  item:{id, ky, ru, rule, value, src, verify}, push:true}   — рынок эрежеси иштеди
        {type:"alert_clear"}
        {type:"urgent", item:{ky, ru, url?}, push:true}                           — админ жазган шашылыш жаңылык
        {type:"tweet",  item:{url, handle, name, date, text, ky?, ru?, tg_url}, push:false} — АЛГАЧ Telegram-каналга чыккан твит
        {type:"fresh",  items:[{id, kind:"main"|"ta"|"opinions", src, url, t, orig, ru?, ky?, desc_ru?, desc_ky?, cat?, tp?, imp?, …}]}
                                                                                  — бот RSS'тен жаңы чыккан жаңылыктар/теханализ (ар 10 мүн), сайт news.json'дун үстүнө кошот
        {type:"delete", kind:"urgent"|"tweet", id}
        {type:"push", cursor}                                                     — билдирмелердин кийинки бөлүгү
   Жооп POST: {ok, pushed, failed, removed, cursor}  — cursor бош эмес болсо, бот кайра {type:"push", cursor} жөнөтөт.
   Керек: KV binding LIVE_KV, сыр LIVE_KEY; билдирмелер үчүн VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY. */
import { json, sameSecret, pushReady, sendEmptyPush } from "../../lib/webpush.js";

const DOC = "live";
const BATCH = 40;                     // Cloudflare бекер планы: бир суроодо ≤50 тышкы fetch
const ALERT_TTL = 3 * 3600 * 1000;    // рынок плашкасы 3 саат көрүнөт (бот жаңыртып турат)
const URGENT_TTL = 12 * 3600 * 1000;
const MAX_URGENT = 10, MAX_TWEETS = 40;
const FRESH_TTL = 36 * 3600 * 1000, MAX_FRESH = 60;   // news.json ар 2 саатта жаңырат — бул «ортодогу» жаңылыктар

function str(v, n) { return typeof v === "string" ? v.trim().slice(0, n) : ""; }
function url(v) { const s = str(v, 600); return /^https:\/\/[^\s"<>]+$/i.test(s) ? s : ""; }
function num(v) { const n = +v; return isFinite(n) ? Math.round(n * 100) / 100 : null; }
function rid() { return Date.now().toString(36) + Math.random().toString(36).slice(2, 7); }

const KINDS = ["main", "ta", "opinions"], CATS = ["crypto", "fx", "stock"], TOPICS = ["move", "etf", "reg", "tech", "macro"];
function freshItem(x) {
  if (!x || typeof x !== "object") return null;
  const u = url(x.url), t = +x.t, id = str(x.id, 24);
  if (!u || !id || !isFinite(t) || t > Date.now() + 600000 || KINDS.indexOf(x.kind) < 0 || !str(x.orig, 400)) return null;
  const o = { id, kind: x.kind, src: str(x.src, 40), url: u, t, orig: str(x.orig, 400) };
  ["ru", "ky"].forEach((k) => { const v = str(x[k], 400); if (v) o[k] = v; });
  ["desc", "desc_ru", "desc_ky"].forEach((k) => { const v = str(x[k], 600); if (v) o[k] = v; });
  ["author", "sym", "who", "who_ru", "who_ky"].forEach((k) => { const v = str(x[k], 80); if (v) o[k] = v; });
  if (CATS.indexOf(x.cat) >= 0) o.cat = x.cat;
  if (Array.isArray(x.tp)) o.tp = x.tp.filter((v) => TOPICS.indexOf(v) >= 0).slice(0, 5);
  if (x.imp === "hot" || x.imp === "top") o.imp = x.imp;
  const img = url(x.img); if (img && /^https:\/\/s3\.tradingview\.com\//.test(img)) o.img = img;
  if (+x.n > 1) o.n = Math.min(20, Math.round(+x.n));
  return o;
}

async function load(env) {
  return (await env.LIVE_KV.get(DOC, { type: "json" })) || { alert: null, urgent: [], tweets: [] };
}

function visible(doc) {
  const now = Date.now();
  return {
    ok: true,
    t: doc.t || null,
    alert: doc.alert && doc.alert.until > now ? doc.alert : null,
    urgent: (doc.urgent || []).filter((u) => now - u.t < URGENT_TTL),
    tweets: doc.tweets || [],
    fresh: (doc.fresh || []).filter((x) => now - x.t < FRESH_TTL)
  };
}

export async function onRequestGet({ request, env }) {
  if (!env.LIVE_KV) return json({ ok: false, reason: "no-kv", alert: null, urgent: [], tweets: [], fresh: [] }, 200, { "cache-control": "public, max-age=60" });
  const cache = caches.default, key = new Request(new URL("/api/live?c=1", request.url).toString());
  const hit = await cache.match(key);
  if (hit) return hit;
  const res = json(visible(await load(env)), 200, { "cache-control": "public, max-age=20" });
  await cache.put(key, res.clone());
  return res;
}

async function fanout(env, cursor) {
  if (!pushReady(env)) return { pushed: 0, failed: 0, removed: 0, cursor: null, note: "no-vapid" };
  const page = await env.LIVE_KV.list({ prefix: "sub:", limit: BATCH, cursor: cursor || undefined });
  const subs = page.keys.filter((k) => k.metadata && k.metadata.e);
  const res = await sendEmptyPush(env, subs.map((k) => k.metadata.e));
  let pushed = 0, failed = 0, removed = 0;
  for (let i = 0; i < res.length; i++) {
    const st = res[i].status;
    if (st >= 200 && st < 300) pushed++;
    else {
      failed++;
      if (st === 404 || st === 410) { await env.LIVE_KV.delete(subs[i].name); removed++; }   // жазылуу эскирген
    }
  }
  return { pushed, failed, removed, cursor: page.list_complete ? null : page.cursor };
}

export async function onRequestPost({ request, env }) {
  if (!env.LIVE_KV || !env.LIVE_KEY) return json({ error: "config" }, 503);
  if (!sameSecret(request.headers.get("x-live-key"), env.LIVE_KEY)) return json({ error: "forbidden" }, 403);
  let b;
  try { b = await request.json(); } catch (e) { return json({ error: "bad" }, 400); }
  if (!b || typeof b.type !== "string") return json({ error: "bad" }, 400);

  if (b.type === "push") return json(Object.assign({ ok: true }, await fanout(env, str(b.cursor, 2000))));

  const doc = await load(env), now = Date.now(), it = b.item || {};
  let saved = null;
  if (b.type === "alert") {
    const ky = str(it.ky, 400), ru = str(it.ru, 400);
    if (!ky && !ru) return json({ error: "bad" }, 400);
    saved = doc.alert = { id: str(it.id, 40) || "market", ky, ru, rule: str(it.rule, 20), value: num(it.value), src: str(it.src, 40),
      verify: url(it.verify), t: now, until: now + ALERT_TTL };
  } else if (b.type === "alert_clear") {
    doc.alert = null;
  } else if (b.type === "urgent") {
    const ky = str(it.ky, 700), ru = str(it.ru, 700);
    if (!ky && !ru) return json({ error: "bad" }, 400);
    saved = { id: "u" + rid(), ky, ru, url: url(it.url), t: now };
    doc.urgent = [saved].concat(doc.urgent || []).slice(0, MAX_URGENT);
  } else if (b.type === "tweet") {
    const u = url(it.url), tg = url(it.tg_url);
    if (!/^https:\/\/(x|twitter)\.com\/[A-Za-z0-9_]{1,15}\/status\/\d+/.test(u) || !str(it.text, 2000)) return json({ error: "bad" }, 400);
    saved = { id: "t" + rid(), url: u, handle: str(it.handle, 20), name: str(it.name, 80), date: str(it.date, 40), text: str(it.text, 2000),
      ky: str(it.ky, 2400), ru: str(it.ru, 2400), tg_url: tg, t: now };
    doc.tweets = [saved].concat((doc.tweets || []).filter((x) => x.url !== u)).slice(0, MAX_TWEETS);
  } else if (b.type === "fresh") {
    const add = (Array.isArray(b.items) ? b.items : []).slice(0, 40).map(freshItem).filter(Boolean);
    if (!add.length) return json({ error: "bad" }, 400);
    const ids = new Set(add.map((x) => x.id));
    doc.fresh = add.concat((doc.fresh || []).filter((x) => !ids.has(x.id) && now - x.t < FRESH_TTL))
      .sort((a, b2) => b2.t - a.t).slice(0, MAX_FRESH);
    saved = { n: add.length };
  } else if (b.type === "delete") {
    const id = str(b.id, 40);
    if (b.kind === "urgent") doc.urgent = (doc.urgent || []).filter((x) => x.id !== id);
    else if (b.kind === "tweet") doc.tweets = (doc.tweets || []).filter((x) => x.id !== id);
  } else {
    return json({ error: "bad" }, 400);
  }
  doc.t = now;
  await env.LIVE_KV.put(DOC, JSON.stringify(doc));
  try { await caches.default.delete(new Request(new URL("/api/live?c=1", request.url).toString())); } catch (e) { /* */ }
  const out = { ok: true, item: saved };
  if (b.push && saved) Object.assign(out, await fanout(env, null));
  return json(out);
}
