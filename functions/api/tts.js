/* AITRADING.KG — автордун үнү (ElevenLabs клону) менен текстти окуу.
   GET  /api/tts            → {ok:true|false} — үн туташканбы (сайт ушуну текшерип, болбосо браузердин үнүнө өтөт)
   POST /api/tts {text,lang} → audio/mpeg
   Сырлар (Cloudflare → Settings → Variables and Secrets):
     ELEVENLABS_API_KEY   — ElevenLabs ачкычы (Secret)
     ELEVENLABS_VOICE_ID  — автордун клон үнүнүн ID'си
     ELEVENLABS_MODEL     — милдеттүү эмес (демейки eleven_v3; кыргызча да окуйт)
   Ошол эле текст кайра суралса — Cloudflare кэшинен (акча кетпейт). IP боюнча саатына TTS_PER_HOUR чектөө. */
import { json, sameOrigin } from "../../server/sign.js";

const MAX = 600;
const PER_HOUR = 60;

async function sha(s) {
  const b = new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)));
  return Array.from(b.slice(0, 16), (x) => x.toString(16).padStart(2, "0")).join("");
}

export async function onRequest(context) {
  const { request, env } = context;
  const ready = !!(env.ELEVENLABS_API_KEY && env.ELEVENLABS_VOICE_ID);
  if (request.method === "GET") return json({ ok: ready });
  if (request.method !== "POST") return json({ error: "method" }, 405);
  if (!ready) return json({ error: "config" }, 503);
  if (!sameOrigin(request)) return json({ error: "forbidden" }, 403);

  let body;
  try { body = await request.json(); } catch (e) { return json({ error: "bad" }, 400); }
  const text = String((body && body.text) || "").replace(/\s+/g, " ").trim().slice(0, MAX);
  const lang = body && body.lang === "ru" ? "ru" : "ky";
  if (!text) return json({ error: "bad" }, 400);

  const model = env.ELEVENLABS_MODEL || "eleven_v3";
  const id = await sha([env.ELEVENLABS_VOICE_ID, model, lang, text].join("|"));
  const cacheKey = new Request(new URL("/api/tts-cache/" + id, request.url).toString());
  const cache = caches.default;
  const hit = await cache.match(cacheKey);
  if (hit) return hit;

  // IP боюнча чектөө (кэштен келгени эсептелбейт)
  if (env.LEADS_KV) {
    const ip = request.headers.get("cf-connecting-ip") || "0";
    const hk = "tts:" + ip + ":" + Math.floor(Date.now() / 3600000);
    const n = +(await env.LEADS_KV.get(hk)) || 0;
    if (n >= (+env.TTS_PER_HOUR || PER_HOUR)) return json({ error: "limit" }, 429);
    context.waitUntil(env.LEADS_KV.put(hk, String(n + 1), { expirationTtl: 3700 }));
  }

  const r = await fetch("https://api.elevenlabs.io/v1/text-to-speech/" + encodeURIComponent(env.ELEVENLABS_VOICE_ID) + "?output_format=mp3_44100_64", {
    method: "POST",
    headers: { "xi-api-key": env.ELEVENLABS_API_KEY, "content-type": "application/json", accept: "audio/mpeg" },
    body: JSON.stringify({
      text,
      model_id: model,
      voice_settings: { stability: 0.5, similarity_boost: 0.85, speed: 1.1 }
    })
  });
  if (!r.ok) return json({ error: "api", status: r.status }, 502);
  const res = new Response(r.body, {
    headers: { "content-type": "audio/mpeg", "cache-control": "public, max-age=2592000" }
  });
  context.waitUntil(cache.put(cacheKey, res.clone()));
  return res;
}
