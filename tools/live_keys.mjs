// AITRADING.KG — шашылыш билдирмелердин ачкычтары (бир жолу).
//   node tools/live_keys.mjs          → VAPID ачкычтары + LIVE_KEY: экранга (Cloudflare'ге коюу үчүн) жана ушул ПКнын
//                                       Windows чөйрөсүнө LIVE_KEY + LIVE_URL (бот /api/live'га жазышы үчүн)
//   node tools/live_keys.mjs --dev    → ачкычтар .dev.vars файлына гана (локалдык текшерүү; файл GitHub'га кетпейт)
// Ачкычтарды эч кимге жөнөтпөңүз. VAPID_PRIVATE_KEY жана LIVE_KEY — Cloudflare'де «Secret» түрүндө.
import { generateKeyPairSync, randomBytes } from "node:crypto";
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const dev = process.argv.includes("--dev");
const b64u = (b) => Buffer.from(b).toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");

const { publicKey, privateKey } = generateKeyPairSync("ec", { namedCurve: "prime256v1" });
const jwk = privateKey.export({ format: "jwk" });
const pub = Buffer.concat([Buffer.from([4]), Buffer.from(jwk.x, "base64url"), Buffer.from(jwk.y, "base64url")]);
const vars = {
  VAPID_PUBLIC_KEY: b64u(pub),
  VAPID_PRIVATE_KEY: jwk.d,
  LIVE_KEY: b64u(randomBytes(24))
};
void publicKey;

if (dev) {
  const f = path.join(root, ".dev.vars");
  let s = existsSync(f) ? readFileSync(f, "utf8") : "";
  let added = 0;
  for (const [k, v] of Object.entries(vars)) {
    if (new RegExp("^" + k + "=", "m").test(s)) continue;
    s += (s && !s.endsWith("\n") ? "\n" : "") + k + "=" + v + "\n";
    added++;
  }
  writeFileSync(f, s);
  console.log(".dev.vars: " + added + " жаңы ачкыч кошулду (бар болгондору өзгөргөн жок). Экранга чыгарылган жок.");
  process.exit(0);
}

const siteUrl = (process.env.SITE_LIVE_URL || "https://aitrading-kg.pages.dev").replace(/\/$/, "");
console.log("\n Cloudflare → Workers & Pages → aitrading-kg → Settings → Variables and Secrets → Add (тип: Secret):\n");
for (const [k, v] of Object.entries(vars)) console.log("   " + k.padEnd(18) + " " + v);
console.log("\n Анан: Settings → Bindings → Add → KV namespace → Variable name: LIVE_KV (жаңы namespace: aitrading-live).");
if (process.platform === "win32") {
  for (const [k, v] of [["LIVE_KEY", vars.LIVE_KEY], ["LIVE_URL", siteUrl + "/api/live"]]) {
    execFileSync("reg", ["add", "HKCU\\Environment", "/v", k, "/t", "REG_SZ", "/d", v, "/f"], { stdio: "ignore" });
  }
  console.log("\n Бул ПКда LIVE_KEY жана LIVE_URL (" + siteUrl + "/api/live) сакталды — Телеграм_бот.bat'ты кайра ачыңыз.");
}
console.log(" Бул терезени жапкандан кийин ачкычтар эч жерде көрүнбөйт: Cloudflare'ге азыр көчүрүңүз.\n");
