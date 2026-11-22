/* AITRADING.KG — «Войти через BinoDex» (OAuth) → Telegram-бот.
   Cloudflare Pages Function: https://aitrading.kg/oauth/callback
   (Pages долбоорунда: чыгыш папкасы — site, бул файл — functions/oauth/callback.js).

   1) Бот колдонуучуга https://binodex.app/oauth/authorize?...&state=<tg.ts.sig> шилтемесин берет (state — боттун колу).
   2) BinoDex ушул дарекке ?code=…&state=… менен кайтарат. Код 120 секунд жашайт, бир жолу колдонулат.
   3) Бул функция кодду сервер↔сервер токенге алмаштырат (client_secret браузерге жетпейт), /broker/user'ден балансты окуйт,
      токендерди САКТАБАЙТ, email'ди эч жакка бербейт — ботко кол коюлган кыска белги гана кетет:
      https://t.me/<бот>?start=bx_<tg36>_<id36>_<flags>_<ts36>_<sig>   (flags: 1 — партнёрдун кардары, 2 — реалдуу баланс > 0)

   Cloudflare → Pages → Settings → Environment variables (Secrets):
     BINODEX_CLIENT_ID      — Broker API клиентинин client_id
     BINODEX_CLIENT_SECRET  — Broker API клиентинин сыры (бир жолу көрсөтүлгөн)
     LINK_SECRET            — бот менен жалпы сыр (Телеграм_бот_туташтыруу.bat чыгарат)
     TG_BOT_USERNAME        — боттун логини, @ белгисиз (мис. aitrading_kg_bot)
*/
const API = "https://api.binodex.app/v1";
const MAX_AGE = 1800; // state 30 мүнөттө эскирет
const enc = new TextEncoder();

async function sign(secret, msg) {
  const key = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const raw = new Uint8Array(await crypto.subtle.sign("HMAC", key, enc.encode(msg)));
  let bin = "";
  for (let i = 0; i < raw.length; i++) bin += String.fromCharCode(raw[i]);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function page(ok, kg, ru, link, status) {
  const go = link
    ? `<a class="btn" href="${esc(link)}">Ботко кайтуу · Вернуться в бот</a><script>setTimeout(function(){location.href=${JSON.stringify(link)}},1200)</script>`
    : `<a class="btn ghost" href="/register.html">Катталуу · Регистрация</a>`;
  const html = `<!doctype html><html lang="ky"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><title>AITRADING.KG · BinoDex</title>
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#070b12;color:#e9eef6;font:16px/1.5 system-ui,Segoe UI,sans-serif}
.c{max-width:420px;margin:16px;padding:28px;border-radius:18px;background:#0f1725;border:1px solid rgba(255,255,255,.1);text-align:center}
.i{font-size:42px}.t{font-weight:700;font-size:20px;margin:8px 0}.m{color:#9aa6b8;font-size:14px;margin:0 0 18px}
.btn{display:inline-block;padding:12px 20px;border-radius:12px;background:#5ce8aa;color:#04170f;font-weight:700;text-decoration:none}
.ghost{background:transparent;color:#e9eef6;border:1px solid rgba(255,255,255,.2)}</style></head>
<body><div class="c"><div class="i">${ok ? "✅" : "⚠️"}</div><div class="t">${esc(kg)}</div><p class="m">${esc(ru)}</p>${go}</div></body></html>`;
  return new Response(html, {
    status: status || 200,
    headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store", "Referrer-Policy": "no-referrer" }
  });
}

export async function onRequestGet({ request, env }) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const state = url.searchParams.get("state") || "";
  if (!env.BINODEX_CLIENT_ID || !env.BINODEX_CLIENT_SECRET || !env.LINK_SECRET || !env.TG_BOT_USERNAME) {
    return page(false, "Текшерүү азырынча жөндөлө элек", "Проверка ещё не настроена. Попробуйте позже или отправьте ID в бот вручную.", null, 503);
  }
  // state = <tg36>.<ts36>.<sig> — шилтемени бот түзгөн
  const [tg36, ts36, ssig] = state.split(".");
  const ok = tg36 && ts36 && ssig && /^[0-9a-z]+$/.test(tg36 + ts36) && ssig === (await sign(env.LINK_SECRET, "st|" + tg36 + "|" + ts36)).slice(0, 22);
  if (!ok) return page(false, "Шилтеме туура эмес", "Ссылка недействительна. Откройте её заново из бота.", null, 400);
  if (Date.now() / 1000 - parseInt(ts36, 36) > MAX_AGE) {
    return page(false, "Шилтеменин мөөнөтү бүттү", "Ссылка устарела. Нажмите кнопку в боте ещё раз.", null, 400);
  }
  if (!code) return page(false, "BinoDex код берген жок", "BinoDex не вернул код. Попробуйте ещё раз из бота.", null, 400);

  let tok;
  try {
    const r = await fetch(API + "/broker/oauth/token", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        grant_type: "authorization_code", code: code,
        client_id: env.BINODEX_CLIENT_ID, client_secret: env.BINODEX_CLIENT_SECRET,
        redirect_uri: url.origin + url.pathname
      })
    });
    if (!r.ok) return page(false, "BinoDex текшерүүсү өтпөй калды (" + r.status + ")", "Проверка BinoDex не прошла. Нажмите кнопку в боте ещё раз.", null, 502);
    tok = await r.json();
  } catch (e) {
    return page(false, "BinoDex жооп берген жок", "BinoDex не отвечает. Попробуйте чуть позже.", null, 502);
  }
  const user = tok.user || {};
  if (!user.id) return page(false, "Аккаунт табылган жок", "Аккаунт не найден.", null, 502);
  let balance = 0;
  try {
    const ur = await fetch(API + "/broker/user", { headers: { Authorization: "Bearer " + tok.access_token } });
    if (ur.ok) {
      const j = await ur.json();
      balance = Number(((j && j.real) || {}).total || 0);
    }
  } catch (e) { /* баланс окулбаса — 0 деп эсептейбиз, бот кол менен текшерүүнү сунуштайт */ }
  const flags = (user.is_partner_client ? 1 : 0) | (balance > 0 ? 2 : 0);
  const body = tg36 + "_" + Number(user.id).toString(36) + "_" + flags + "_" + Math.floor(Date.now() / 1000).toString(36);
  const payload = "bx_" + body + "_" + (await sign(env.LINK_SECRET, "bx|" + body)).slice(0, 16);
  const link = "https://t.me/" + env.TG_BOT_USERNAME.replace(/^@/, "") + "?start=" + payload;
  return page(true, "BinoDex аккаунтуңуз табылды", "Аккаунт BinoDex найден. Возвращаем вас в бот — нажмите «Start», если Telegram попросит.", link, 200);
}
