/* AITRADING.KG — өнөктөштүн кыска шилтемеси / короткая ссылка партнёра.
   https://aitrading.kg/r/<код>             → өнөктөшкө админ берген BinoDex шилтемеси, жок болсо — Telegram-бот (?start=p_<код>)
   https://aitrading.kg/r/<код>?b=binodex   → BinoDex (өнөктөштүкү же автордун BINODEX_REF_URL)
   https://aitrading.kg/r/<код>?b=bingx     → BingX
   https://aitrading.kg/r/<код>?b=bot       → Telegram-бот — катталуу жана толуктоо ушул жол менен эсептелет

   Маршрутту бот жазат (POST /api/partner): KV pc:<код> = { t: tg36, bd, bx, bot, main: "bd"|"bot", on }.
   Өтүүлөр: KV ck:<код> = { n, d: { "YYYYMMDD": n } } — бир окуу + бир жазуу. Бир браузерден суткасына бир жолу гана
   эсептелет (cookie, KV жазуусуз), анткени акысыз Cloudflare KV'де жазуу суткасына 1000. Чек бүтсө — өтүү жөн эле эсептелбейт,
   шилтеме иштей берет. */
const DAYS = 45;

function go(url) {
  return new Response(null, { status: 302, headers: { Location: url, "Cache-Control": "no-store", "Referrer-Policy": "no-referrer-when-downgrade" } });
}

export async function onRequestGet({ request, env, params }) {
  const code = String(params.code || "").toLowerCase();
  const url = new URL(request.url);
  const b = url.searchParams.get("b") || "";
  if (!/^[a-z0-9]{4,16}$/.test(code) || !env.LEADS_KV) return go(url.origin + "/register.html");

  let r = null;
  try { r = JSON.parse((await env.LEADS_KV.get("pc:" + code)) || "null"); } catch (e) { r = null; }
  if (!r || !r.on) return go(url.origin + "/register.html");

  // Демейки: өнөктөшкө өз BinoDex шилтемеси берилсе — ошого, болбосо ботко (катталуу/толуктоо ошол жерде эсептелет)
  const pick = { bingx: r.bx, binodex: r.bd, bot: r.bot }[b] || (r.main === "bd" ? r.bd : r.bot) || r.bd;
  const target = /^https:\/\/\S+$/.test(String(pick || "")) ? pick : r.bd;
  if (!/^https:\/\/\S+$/.test(String(target || ""))) return go(url.origin + "/register.html");

  const res = go(target);
  const ck = "atr_" + code;
  if (!(request.headers.get("cookie") || "").includes(ck + "=")) {
    try {
      const day = new Date().toISOString().slice(0, 10).replace(/-/g, "");
      let c = null;
      try { c = JSON.parse((await env.LEADS_KV.get("ck:" + code)) || "null"); } catch (e) { c = null; }
      if (!c || typeof c !== "object") c = { n: 0, d: {} };
      c.n = (c.n || 0) + 1;
      c.d = c.d || {};
      c.d[day] = (c.d[day] || 0) + 1;
      const keep = Object.keys(c.d).sort().slice(-DAYS);
      c.d = Object.fromEntries(keep.map((k) => [k, c.d[k]]));
      await env.LEADS_KV.put("ck:" + code, JSON.stringify(c));
    } catch (e) { /* KV чеги бүттү — өтүү эсептелбейт, шилтеме иштейт */ }
    res.headers.append("Set-Cookie", ck + "=1; Max-Age=86400; Path=/r/; Secure; HttpOnly; SameSite=Lax");
  }
  return res;
}
