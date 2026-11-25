/* AITRADING.KG — Web Push (VAPID, RFC 8292) Cloudflare'дин ичинде, китепканасыз.
   Билдирме «бош» жөнөтүлөт (payload жок, шифрлөө керек эмес): телефондогу service worker (sw.js)
   аны алганда /api/live'дан акыркы шашылыш жаңылыкты өзү окуп көрсөтөт.
   Ачкычтар: VAPID_PUBLIC_KEY (base64url, 65 байт) жана VAPID_PRIVATE_KEY (base64url, 32 байт) —
   tools/live_keys.mjs жасайт; Cloudflare → Settings → Variables and Secrets'ке коюлат. */

export function b64u(buf) {
  const bytes = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
  let s = "";
  for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function b64uDecode(str) {
  let s = String(str || "").replace(/-/g, "+").replace(/_/g, "/");
  while (s.length % 4) s += "=";
  const bin = atob(s), out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

const enc = new TextEncoder();

export function pushReady(env) {
  return !!(env && env.VAPID_PUBLIC_KEY && env.VAPID_PRIVATE_KEY);
}

async function signingKey(env) {
  const pub = b64uDecode(env.VAPID_PUBLIC_KEY);
  if (pub.length !== 65 || pub[0] !== 4) throw new Error("VAPID_PUBLIC_KEY туура эмес");
  const jwk = { kty: "EC", crv: "P-256", x: b64u(pub.slice(1, 33)), y: b64u(pub.slice(33, 65)), d: String(env.VAPID_PRIVATE_KEY).trim(), ext: true };
  return crypto.subtle.importKey("jwk", jwk, { name: "ECDSA", namedCurve: "P-256" }, false, ["sign"]);
}

async function vapidJwt(key, aud, sub) {
  const head = b64u(enc.encode(JSON.stringify({ typ: "JWT", alg: "ES256" })));
  const body = b64u(enc.encode(JSON.stringify({ aud, exp: Math.floor(Date.now() / 1000) + 12 * 3600, sub })));
  const sig = await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, key, enc.encode(head + "." + body));
  return head + "." + body + "." + b64u(sig);
}

/* Бир топ жазылуучуга бош push жөнөтөт. endpoints — массив. Жооп: [{endpoint, status}] */
export async function sendEmptyPush(env, endpoints, opts) {
  const o = opts || {};
  const key = await signingKey(env);
  const sub = env.VAPID_SUBJECT || "https://aitrading-kg.pages.dev";
  const jwts = new Map();
  const results = await Promise.all(endpoints.map(async (ep) => {
    try {
      const aud = new URL(ep).origin;
      if (!jwts.has(aud)) jwts.set(aud, await vapidJwt(key, aud, sub));
      const r = await fetch(ep, {
        method: "POST",
        headers: {
          TTL: String(o.ttl || 6 * 3600),
          Urgency: o.urgency || "high",
          Topic: o.topic || "aitrading-urgent",
          Authorization: "vapid t=" + jwts.get(aud) + ", k=" + env.VAPID_PUBLIC_KEY,
          "Content-Length": "0"
        }
      });
      return { endpoint: ep, status: r.status };
    } catch (e) {
      return { endpoint: ep, status: 0 };
    }
  }));
  return results;
}

export async function sha(s) {
  const h = await crypto.subtle.digest("SHA-256", enc.encode(s));
  return Array.from(new Uint8Array(h)).map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 32);
}

/* Түп нуска менен бирдей узундуктагы сырларды салыштыруу (убакыт боюнча агып кетпесин) */
export function sameSecret(a, b) {
  a = String(a || ""); b = String(b || "");
  if (!a || !b || a.length !== b.length) return false;
  let x = 0;
  for (let i = 0; i < a.length; i++) x |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return x === 0;
}

export function json(obj, status, extra) {
  return new Response(JSON.stringify(obj), {
    status: status || 200,
    headers: Object.assign({ "content-type": "application/json; charset=utf-8", "cache-control": "no-store" }, extra || {})
  });
}

export function sameOrigin(request) {
  const origin = request.headers.get("origin");
  if (!origin) return false;
  try {
    const o = new URL(origin), self = new URL(request.url);
    return o.host === self.host || /^(localhost|127\.0\.0\.1)$/.test(o.hostname);
  } catch (e) {
    return false;
  }
}
