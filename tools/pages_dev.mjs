// Локалдык текшерүү: сайт + Cloudflare Functions (ИИ-жардамчы /api/assistant) — http://127.0.0.1:8790
// Ачкыч керек болсо: Сайт_AITRADING_kg/.dev.vars файлына ANTHROPIC_API_KEY=... (бул файл GitHub'га кетпейт).
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";
import os from "node:os";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const p = spawn("npx", ["wrangler", "pages", "dev", "site", "--port", "8790", "--ip", "127.0.0.1", "--kv", "LEADS_KV", "--persist-to", JSON.stringify(path.join(os.tmpdir(), "aitrading-wrangler"))], { cwd: root, stdio: "inherit", shell: true });
p.on("exit", (c) => process.exit(c ?? 0));
