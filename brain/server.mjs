// Navi brain server: serves the NAVI folder (preview + model) and POST /api/chat.
//
// Provider selection (first match wins):
//   1. Anthropic API  — when ANTHROPIC_API_KEY is set (Claude Opus 5, low effort, structured output)
//   2. Codex CLI      — `codex exec` on the user's ChatGPT account (slower, ~9s, no key needed)
//
// Run:  node brain/server.mjs      (from C:\CloudeRepo\NAVI)   → http://localhost:8765/preview/

import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(here, "..");
const DATA = path.join(here, "data");
const PORT = Number(process.env.PORT || 8765);
fs.mkdirSync(DATA, { recursive: true });

const CONFIG = { operator_gender: process.env.NAVI_OPERATOR_GENDER || "masculine", historyTurns: 12 };
const PERSONA = fs.readFileSync(path.join(here, "persona.md"), "utf8").replace("{{operator_gender}}", CONFIG.operator_gender);

const MOODS = ["calm", "happy", "curious", "greet", "playful", "tired"];
const ANIMS = ["Idle", "Wave", "HappyJump", "TailWag", "Listen", "Sleep"];
const SCHEMA = {
  type: "object",
  properties: {
    reply: { type: "string" },
    mood: { type: "string", enum: MOODS },
    animation: { type: "string", enum: ANIMS },
    face: {
      type: "object",
      properties: { happy: { type: "number" }, mouthOpen: { type: "number" } },
      required: ["happy", "mouthOpen"],
      additionalProperties: false,
    },
    remember: { type: ["string", "null"] },
  },
  required: ["reply", "mood", "animation", "face", "remember"],
  additionalProperties: false,
};
const SCHEMA_FILE = path.join(DATA, "reply-schema.json");
fs.writeFileSync(SCHEMA_FILE, JSON.stringify(SCHEMA));

// ---------- tiny persistent state ----------
const HISTORY_FILE = path.join(DATA, "history.json");
const MEMORY_FILE = path.join(DATA, "memory.json");
const load = (f, d) => { try { return JSON.parse(fs.readFileSync(f, "utf8")); } catch { return d; } };
let history = load(HISTORY_FILE, []);   // [{role:"user"|"navi", text, at}]
let memory = load(MEMORY_FILE, []);     // [{fact, at}]
const save = () => {
  fs.writeFileSync(HISTORY_FILE, JSON.stringify(history.slice(-200), null, 1));
  fs.writeFileSync(MEMORY_FILE, JSON.stringify(memory, null, 1));
};

// cheap guard: never keep things that look like secrets
const SECRET = /(\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b)|(סיסמ|password|קוד אימות|otp)/i;

function contextBlock() {
  const facts = memory.length ? memory.map((m) => `- ${m.fact}`).join("\n") : "- (nothing yet — you just met)";
  const now = new Date().toLocaleString("he-IL", { timeZone: "Asia/Jerusalem", weekday: "long", hour: "2-digit", minute: "2-digit" });
  return `## What you know about the Operator\n${facts}\n\n## Now\n${now}`;
}

// ---------- providers ----------
async function askAnthropic(userText) {
  const { default: Anthropic } = await import("@anthropic-ai/sdk");
  const client = new Anthropic();
  const messages = [];
  for (const h of history.slice(-CONFIG.historyTurns * 2)) {
    messages.push({ role: h.role === "user" ? "user" : "assistant", content: h.text });
  }
  messages.push({ role: "user", content: userText });
  const response = await client.beta.messages.create({
    model: "claude-opus-5",
    max_tokens: 2000,
    betas: ["server-side-fallback-2026-07-01"],
    fallbacks: "default",
    system: [
      { type: "text", text: PERSONA, cache_control: { type: "ephemeral" } },
      { type: "text", text: contextBlock() },
    ],
    output_config: { effort: "low", format: { type: "json_schema", schema: SCHEMA } },
    messages,
  });
  if (response.stop_reason === "refusal") throw new Error("refusal");
  const text = response.content.find((b) => b.type === "text")?.text ?? "{}";
  return JSON.parse(text);
}

function askCodex(userText) {
  const transcript = history.slice(-CONFIG.historyTurns * 2)
    .map((h) => `${h.role === "user" ? "Operator" : "Pixel"}: ${h.text}`).join("\n");
  const prompt = `${PERSONA}\n\n${contextBlock()}\n\n## Conversation so far\n${transcript || "(start)"}\n\n` +
    `## New message from the Operator\n${userText}\n\n` +
    `Reply as Pixel. Output only the JSON object required by the schema. Do not run any commands or read any files.`;
  const outFile = path.join(os.tmpdir(), `navi-reply-${Date.now()}-${Math.random().toString(36).slice(2)}.json`);
  return new Promise((resolve, reject) => {
    const child = spawn("codex", [
      "exec", "--skip-git-repo-check", "-s", "read-only",
      "-c", 'model_reasoning_effort="low"',
      "--output-schema", SCHEMA_FILE, "-o", outFile, "-",
    ], { cwd: DATA, shell: process.platform === "win32" });
    let err = "";
    child.stderr.on("data", (d) => (err += d));
    child.stdout.on("data", () => {});
    const timer = setTimeout(() => { child.kill(); reject(new Error("codex timeout")); }, 90_000);
    child.on("close", (code) => {
      clearTimeout(timer);
      try {
        const out = JSON.parse(fs.readFileSync(outFile, "utf8"));
        fs.rmSync(outFile, { force: true });
        resolve(out);
      } catch {
        reject(new Error(`codex failed (exit ${code}): ${err.slice(-400)}`));
      }
    });
    child.stdin.end(prompt, "utf8");
  });
}

const PROVIDER = process.env.ANTHROPIC_API_KEY ? "anthropic" : "codex";

async function think(userText) {
  const t0 = Date.now();
  const out = PROVIDER === "anthropic" ? await askAnthropic(userText) : await askCodex(userText);
  // sanitize model output before it drives the body
  out.mood = MOODS.includes(out.mood) ? out.mood : "calm";
  out.animation = ANIMS.includes(out.animation) ? out.animation : "Idle";
  const clamp = (v) => Math.max(0, Math.min(1, Number(v) || 0));
  out.face = { happy: clamp(out.face?.happy), mouthOpen: clamp(out.face?.mouthOpen) };
  out.ms = Date.now() - t0;
  out.provider = PROVIDER;

  history.push({ role: "user", text: userText, at: new Date().toISOString() });
  history.push({ role: "navi", text: out.reply, at: new Date().toISOString() });
  if (out.remember && !SECRET.test(out.remember) && !memory.some((m) => m.fact === out.remember)) {
    memory.push({ fact: out.remember, at: new Date().toISOString() });
  }
  save();
  return out;
}

// ---------- http ----------
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".mjs": "text/javascript", ".json": "application/json",
  ".glb": "model/gltf-binary", ".png": "image/png", ".css": "text/css", ".md": "text/markdown; charset=utf-8" };

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);

  if (url.pathname === "/api/chat" && req.method === "POST") {
    let body = "";
    for await (const chunk of req) body += chunk;
    try {
      const { message } = JSON.parse(body || "{}");
      if (!message || typeof message !== "string" || message.length > 2000) throw new Error("bad message");
      const out = await think(message.trim());
      res.writeHead(200, { "content-type": "application/json; charset=utf-8" });
      res.end(JSON.stringify(out));
    } catch (e) {
      console.error("[chat]", e.message);
      res.writeHead(500, { "content-type": "application/json; charset=utf-8" });
      res.end(JSON.stringify({ error: e.message }));
    }
    return;
  }
  if (url.pathname === "/api/state") {
    res.writeHead(200, { "content-type": "application/json; charset=utf-8" });
    res.end(JSON.stringify({ provider: PROVIDER, memory, history: history.slice(-20) }));
    return;
  }

  // static files, confined to the NAVI folder (never serve brain/data)
  const rel = decodeURIComponent(url.pathname === "/" ? "/preview/index.html" : url.pathname);
  const file = path.normalize(path.join(ROOT, rel.endsWith("/") ? rel + "index.html" : rel));
  if (!file.startsWith(ROOT) || file.startsWith(DATA)) { res.writeHead(403); res.end(); return; }
  fs.readFile(file, (err, data) => {
    if (err) { res.writeHead(404); res.end("not found"); return; }
    res.writeHead(200, { "content-type": TYPES[path.extname(file)] || "application/octet-stream" });
    res.end(data);
  });
});

server.listen(PORT, "127.0.0.1", () => console.log(`Navi brain on http://localhost:${PORT}/preview/  (provider: ${PROVIDER})`));
