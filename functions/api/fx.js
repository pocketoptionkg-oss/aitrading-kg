/* AITRADING.KG — валюта жуптарынын жандуу шамдары (Yahoo Finance аркылуу; браузер Yahoo'го түз кире албайт — CORS).
   GET /api/fx?code=GBPJPY&iv=1   (iv: 1 | 5 | 15 | 60 мүнөт)
   Жооп: { provider:"Yahoo", candles:[{time,open,high,low,close,volume}] }. Cloudflare кэши: 1 мүн — 20 с, калгандары — 60 с. */
import { json } from "../../server/sign.js";

const YSYM = { XAUUSD: "GC=F", XAGUSD: "SI=F" };
const IV = { 1: ["1m", "1d"], 5: ["5m", "5d"], 15: ["15m", "5d"], 60: ["60m", "1mo"] };

export async function onRequest(context) {
  const { request } = context;
  if (request.method !== "GET") return json({ error: "method" }, 405);
  const u = new URL(request.url);
  const code = (u.searchParams.get("code") || "").toUpperCase();
  const iv = IV[u.searchParams.get("iv") || "1"] ? (u.searchParams.get("iv") || "1") : null;
  if (!/^[A-Z]{6}$/.test(code) || !iv) return json({ error: "bad" }, 400);

  const cacheKey = new Request(new URL("/api/fx-cache/" + code + "/" + iv, request.url).toString());
  const hit = await caches.default.match(cacheKey);
  if (hit) return hit;

  const sym = YSYM[code] || code + "=X";
  const [interval, range] = IV[iv];
  let j;
  try {
    const r = await fetch("https://query1.finance.yahoo.com/v8/finance/chart/" + encodeURIComponent(sym) + "?interval=" + interval + "&range=" + range,
      { headers: { "user-agent": "Mozilla/5.0 (aitrading.kg)" }, cf: { cacheTtl: 0 } });
    if (!r.ok) return json({ error: "upstream", status: r.status }, 502);
    j = await r.json();
  } catch (e) {
    return json({ error: "upstream" }, 502);
  }
  const res = j && j.chart && j.chart.result && j.chart.result[0];
  if (!res || !res.timestamp) return json({ error: "nodata" }, 502);
  const q = (res.indicators && res.indicators.quote && res.indicators.quote[0]) || {};
  const candles = [];
  for (let i = 0; i < res.timestamp.length; i++) {
    const o = q.open[i], h = q.high[i], l = q.low[i], c = q.close[i];
    if (o == null || h == null || l == null || c == null) continue;
    candles.push({ time: res.timestamp[i], open: o, high: h, low: l, close: c, volume: q.volume ? q.volume[i] || 0 : 0 });
  }
  const out = new Response(JSON.stringify({ provider: "Yahoo", candles }), {
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "public, max-age=" + (iv === "1" ? 20 : 60) }
  });
  context.waitUntil(caches.default.put(cacheKey, out.clone()));
  return out;
}
