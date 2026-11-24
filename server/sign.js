/* AITRADING.KG — бот менен сайттын жалпы колу (LINK_SECRET, HMAC-SHA256, base64url).
   Python тарабы: tools/tg_bot.py → link_sig(msg, n). Ошол эле формула. */
const enc = new TextEncoder();

export async function sign(secret, msg) {
  const key = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const raw = new Uint8Array(await crypto.subtle.sign("HMAC", key, enc.encode(msg)));
  let bin = "";
  for (let i = 0; i < raw.length; i++) bin += String.fromCharCode(raw[i]);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/* Убакыттын туруктуу салыштыруусу */
export function same(a, b) {
  a = String(a || ""); b = String(b || "");
  if (a.length !== b.length) return false;
  let r = 0;
  for (let i = 0; i < a.length; i++) r |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return r === 0;
}

export function json(obj, status) {
  return new Response(JSON.stringify(obj), {
    status: status || 200,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" }
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
