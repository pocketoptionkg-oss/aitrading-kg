// Локалдык текшерүү: сайт + /api/live жана /api/push (Cloudflare Functions'тун өзү, KV — эс тутумда).
//   node tools/live_dev.mjs [порт]        → http://127.0.0.1:8791
// wrangler'сиз иштейт. Ачкычтар: Сайт_AITRADING_kg/.dev.vars (node tools/live_keys.mjs --dev).
// KV ушул папкадагы .wrangler/live-dev-kv.json файлында сакталат (GitHub'га кетпейт).
import http from "node:http";
import { readFileSync, writeFileSync, existsSync, statSync, mkdirSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const site = path.join(root, "site");
const port = +process.argv[2] || 8791;

// .dev.vars → env
const env = {};
const dv = path.join(root, ".dev.vars");
if (existsSync(dv)) for (const ln of readFileSync(dv, "utf8").split(/\r?\n/)) {
  const m = ln.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
  if (m) env[m[1]] = m[2].replace(/^"(.*)"$/, "$1");
}

// KV (эс тутум + файл)
const kvFile = path.join(root, ".wrangler", "live-dev-kv.json");
mkdirSync(path.dirname(kvFile), { recursive: true });
const store = existsSync(kvFile) ? JSON.parse(readFileSync(kvFile, "utf8")) : {};
const save = () => writeFileSync(kvFile, JSON.stringify(store, null, 1));
env.LIVE_KV = {
  async get(k, o) { const v = store[k]; if (!v) return null; return o && (o.type === "json" || o === "json") ? JSON.parse(v.value) : v.value; },
  async put(k, value, o) { store[k] = { value: String(value), metadata: (o && o.metadata) || null }; save(); },
  async delete(k) { delete store[k]; save(); },
  async list(o) {
    const keys = Object.keys(store).filter((k) => k.startsWith((o && o.prefix) || "")).sort();
    const start = o && o.cursor ? +o.cursor : 0, lim = (o && o.limit) || 1000;
    const page = keys.slice(start, start + lim);
    const done = start + lim >= keys.length;
    return { keys: page.map((k) => ({ name: k, metadata: store[k].metadata })), list_complete: done, cursor: done ? undefined : String(start + lim) };
  }
};
globalThis.caches = globalThis.caches || { default: { async match() { return undefined; }, async put() {}, async delete() { return true; } } };

const routes = {
  "/api/live": await import(pathToFileURL(path.join(root, "functions", "api", "live.js")).href),
  "/api/push": await import(pathToFileURL(path.join(root, "functions", "api", "push.js")).href)
};
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".json": "application/json",
  ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp", ".mp4": "video/mp4", ".webmanifest": "application/manifest+json",
  ".mp3": "audio/mpeg", ".txt": "text/plain; charset=utf-8", ".xml": "application/xml", ".ico": "image/x-icon" };

http.createServer(async (req, res) => {
  const u = new URL(req.url, "http://127.0.0.1:" + port);
  const mod = routes[u.pathname];
  if (mod) {
    const chunks = [];
    for await (const c of req) chunks.push(c);
    const request = new Request(u.href, { method: req.method, headers: req.headers, body: ["GET", "HEAD"].includes(req.method) ? undefined : Buffer.concat(chunks) });
    const fn = mod["onRequest" + req.method[0] + req.method.slice(1).toLowerCase()] || mod.onRequest;
    let r;
    try { r = fn ? await fn({ request, env }) : new Response("Method Not Allowed", { status: 405 }); }
    catch (e) { console.error(e); r = new Response(String(e), { status: 500 }); }
    res.writeHead(r.status, Object.fromEntries(r.headers));
    res.end(Buffer.from(await r.arrayBuffer()));
    console.log(req.method, u.pathname, r.status);
    return;
  }
  let f = path.join(site, decodeURIComponent(u.pathname));
  if (!f.startsWith(site)) { res.writeHead(403).end(); return; }
  if (existsSync(f) && statSync(f).isDirectory()) f = path.join(f, "index.html");
  if (!existsSync(f)) { res.writeHead(404, { "content-type": "text/plain" }).end("404"); return; }
  res.writeHead(200, { "content-type": TYPES[path.extname(f).toLowerCase()] || "application/octet-stream", "cache-control": "no-cache" });
  res.end(readFileSync(f));
}).listen(port, "127.0.0.1", () => console.log("AITRADING.KG + /api/live, /api/push → http://127.0.0.1:" + port +
  " · KV: эс тутумда · VAPID: " + (env.VAPID_PUBLIC_KEY ? "бар" : "жок") + " · LIVE_KEY: " + (env.LIVE_KEY ? "бар" : "жок")));
