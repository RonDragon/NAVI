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
const FOLLOWUP_INTENTS = ["ask_outcome", "prepare", "check_progress", "support", "celebrate"];
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
    // a future event worth following up on (Follow-up Engine, Bible §15.4)
    followUp: {
      type: ["object", "null"],
      properties: {
        subject: { type: "string" },          // short Hebrew, e.g. "הראיון בחברת X"
        eventAt: { type: "string" },          // ISO 8601 with +03:00/+02:00 offset
        askAfter: { type: "string" },         // ISO 8601 — when it's natural to ask
        intent: { type: "string", enum: FOLLOWUP_INTENTS },
      },
      required: ["subject", "eventAt", "askAfter", "intent"],
      additionalProperties: false,
    },
  },
  required: ["reply", "mood", "animation", "face", "remember", "followUp"],
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
const FOLLOWUPS_FILE = path.join(DATA, "followups.json");
let followups = load(FOLLOWUPS_FILE, []); // [{id, subject, eventAt, askAfter, intent, status: pending|asked|expired, createdAt}]
const save = () => {
  fs.writeFileSync(HISTORY_FILE, JSON.stringify(history.slice(-200), null, 1));
  fs.writeFileSync(MEMORY_FILE, JSON.stringify(memory, null, 1));
  fs.writeFileSync(FOLLOWUPS_FILE, JSON.stringify(followups, null, 1));
};

// cheap guard: never keep things that look like secrets
const SECRET = /(\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b)|(סיסמ|password|קוד אימות|otp)/i;

const TZ = "Asia/Jerusalem";
function nowLabel(d = new Date()) {
  // e.g. "2026-09-25T17:05:00+03:00 (יום שישי, 17:05)" — the model needs an exact date to resolve "tomorrow"
  const parts = Object.fromEntries(new Intl.DateTimeFormat("en-CA", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZoneName: "longOffset" }).formatToParts(d).map((p) => [p.type, p.value]));
  const off = (parts.timeZoneName || "GMT+03:00").replace("GMT", "") || "+00:00";
  const he = d.toLocaleString("he-IL", { timeZone: TZ, weekday: "long", hour: "2-digit", minute: "2-digit" });
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}:00${off} (${he})`;
}

function contextBlock() {
  const facts = memory.length ? memory.map((m) => `- ${m.fact}`).join("\n") : "- (nothing yet — you just met)";
  const open = followups.filter((f) => f.status === "pending");
  const fu = open.length ? open.map((f) => `- ${f.subject} (event ${f.eventAt}, ask after ${f.askAfter})`).join("\n") : "- (none)";
  return `## What you know about the Operator\n${facts}\n\n## Things you're waiting to hear about (already tracked — don't create duplicates)\n${fu}\n\n## Now\n${nowLabel()}`;
}

// ---------- providers ----------
// turn = { kind: "message", text } from the Operator, or { kind: "event", text } from the app (e.g. app opened)
async function askAnthropic(turn) {
  const { default: Anthropic } = await import("@anthropic-ai/sdk");
  const client = new Anthropic();
  const messages = [];
  for (const h of history.slice(-CONFIG.historyTurns * 2)) {
    messages.push({ role: h.role === "user" ? "user" : "assistant", content: h.text });
  }
  messages.push({ role: "user", content: turn.kind === "event" ? `(system event — not the Operator speaking)\n${turn.text}` : turn.text });
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

function askCodex(turn) {
  const transcript = history.slice(-CONFIG.historyTurns * 2)
    .map((h) => `${h.role === "user" ? "Operator" : "Pixel"}: ${h.text}`).join("\n");
  const header = turn.kind === "event" ? "## App event (not the Operator speaking)" : "## New message from the Operator";
  const prompt = `${PERSONA}\n\n${contextBlock()}\n\n## Conversation so far\n${transcript || "(start)"}\n\n` +
    `${header}\n${turn.text}\n\n` +
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

async function think(turn) {
  const t0 = Date.now();
  const out = PROVIDER === "anthropic" ? await askAnthropic(turn) : await askCodex(turn);
  // sanitize model output before it drives the body
  out.mood = MOODS.includes(out.mood) ? out.mood : "calm";
  out.animation = ANIMS.includes(out.animation) ? out.animation : "Idle";
  const clamp = (v) => Math.max(0, Math.min(1, Number(v) || 0));
  out.face = { happy: clamp(out.face?.happy), mouthOpen: clamp(out.face?.mouthOpen) };
  out.ms = Date.now() - t0;
  out.provider = PROVIDER;

  if (turn.kind === "message") history.push({ role: "user", text: turn.text, at: new Date().toISOString() });
  history.push({ role: "navi", text: out.reply, at: new Date().toISOString() });
  if (out.remember && !SECRET.test(out.remember) && !memory.some((m) => m.fact === out.remember)) {
    memory.push({ fact: out.remember, at: new Date().toISOString() });
  }
  trackFollowUp(out.followUp);
  save();
  return out;
}

// ---------- Follow-up Engine (Bible §15.4): remember future events, ask about them once ----------
function trackFollowUp(f) {
  if (!f || !f.subject) return;
  const eventAt = Date.parse(f.eventAt), askAfter = Date.parse(f.askAfter);
  if (Number.isNaN(eventAt) || Number.isNaN(askAfter)) return;
  if (eventAt < Date.now() - 36 * 3600e3) return;                        // already long past
  if (followups.some((x) => x.status === "pending" && (x.subject === f.subject || Math.abs(Date.parse(x.eventAt) - eventAt) < 3600e3))) return;
  followups.push({ id: Math.random().toString(36).slice(2, 10), subject: f.subject, eventAt: f.eventAt, askAfter: f.askAfter,
    intent: FOLLOWUP_INTENTS.includes(f.intent) ? f.intent : "ask_outcome", status: "pending", createdAt: new Date().toISOString() });
}

// What's going on when the Operator opens the app — decides whether Pixel should speak first.
function openingSituation() {
  const now = Date.now();
  for (const f of followups) if (f.status === "pending" && Date.parse(f.eventAt) < now - 4 * 86400e3) f.status = "expired";
  const last = history.length ? Date.parse(history[history.length - 1].at) : null;
  const gapMin = last ? Math.round((now - last) / 60000) : null;
  const due = followups.filter((f) => f.status === "pending" && Date.parse(f.askAfter) <= now)
    .sort((a, b) => Date.parse(b.eventAt) - Date.parse(a.eventAt));
  const soon = followups.filter((f) => f.status === "pending" && !f.encouragedAt
    && Date.parse(f.eventAt) > now && Date.parse(f.eventAt) - now < 3 * 3600e3);
  const reasons = [];
  if (gapMin === null) reasons.push("first_meeting");
  if (due.length) reasons.push("followup_due");
  if (soon.length) reasons.push("event_soon");
  if (gapMin !== null && gapMin >= 180) reasons.push("back_after_a_while");
  return { gapMin, due, soon, reasons };
}

async function greet() {
  const s = openingSituation();
  if (!s.reasons.length) { save(); return { silent: true, reasons: [] }; }   // nothing worth interrupting for — silence is fine
  const pick = s.due[0] || s.soon[0] || null;
  const lines = [
    "The Operator just opened the app and is looking at you. Say the first thing, like a friend who noticed them.",
    `Time since your last exchange: ${s.gapMin === null ? "never talked before" : `${s.gapMin} minutes`}.`,
    pick && s.due[0] === pick ? `Follow-up due — ask briefly and warmly how this went: "${pick.subject}" (was at ${pick.eventAt}).` : "",
    pick && s.soon[0] === pick ? `Coming up soon — a short, practical word of encouragement: "${pick.subject}" at ${pick.eventAt}.` : "",
    "Rules: at most ONE topic. One or two short sentences. Match the time of day. Never guilt the Operator for being away.",
    "If nothing special, a light natural opener is enough. followUp must be null unless the Operator told you something new.",
  ].filter(Boolean).join("\n");
  const out = await think({ kind: "event", text: lines });
  // each follow-up is asked once (maxAttempts 1); an encouragement before the event doesn't close it
  if (pick && s.due[0] === pick) { pick.status = "asked"; pick.askedAt = new Date().toISOString(); }
  else if (pick) pick.encouragedAt = new Date().toISOString();
  save();
  return { ...out, silent: false, reasons: s.reasons };
}

// ---------- voice (edge-tts: free Microsoft neural Hebrew voices, no key) ----------
const VOICE = {
  name: process.env.NAVI_VOICE || "he-IL-AvriNeural",
  pitch: process.env.NAVI_VOICE_PITCH || "+35Hz",   // a little higher = smaller creature
  rate: process.env.NAVI_VOICE_RATE || "+8%",
};

function speak(text) {
  // emojis and symbols are read aloud badly — strip them
  const clean = text.replace(/[\p{Extended_Pictographic}‍️]/gu, "").replace(/\s+/g, " ").trim().slice(0, 600);
  if (!clean) return Promise.reject(new Error("empty text"));
  const out = path.join(os.tmpdir(), `navi-tts-${Date.now()}-${Math.random().toString(36).slice(2)}.mp3`);
  const txt = out.replace(/\.mp3$/, ".txt");
  fs.writeFileSync(txt, clean, "utf8");             // via file: no shell quoting issues with Hebrew
  return new Promise((resolve, reject) => {
    const child = spawn("python", ["-m", "edge_tts", "--voice", VOICE.name, `--pitch=${VOICE.pitch}`, `--rate=${VOICE.rate}`,
      "--file", txt, "--write-media", out]);
    let err = "";
    child.stderr.on("data", (d) => (err += d));
    const timer = setTimeout(() => { child.kill(); reject(new Error("tts timeout")); }, 30_000);
    child.on("close", (code) => {
      clearTimeout(timer);
      try {
        const audio = fs.readFileSync(out);
        if (process.env.NAVI_DEBUG) console.log("[tts] exit", code, "bytes", audio.length, err.slice(-200));
        if (!audio.length) throw new Error("empty audio");
        resolve(audio);
      } catch {
        reject(new Error(`tts failed (exit ${code}): ${err.slice(-300)}`));
      } finally {
        fs.rmSync(out, { force: true }); fs.rmSync(txt, { force: true });
      }
    });
  });
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
      const out = await think({ kind: "message", text: message.trim() });
      res.writeHead(200, { "content-type": "application/json; charset=utf-8" });
      res.end(JSON.stringify(out));
    } catch (e) {
      console.error("[chat]", e.message);
      res.writeHead(500, { "content-type": "application/json; charset=utf-8" });
      res.end(JSON.stringify({ error: e.message }));
    }
    return;
  }
  if (url.pathname === "/api/greeting" && req.method === "POST") {
    try {
      const out = await greet();
      res.writeHead(200, { "content-type": "application/json; charset=utf-8" });
      res.end(JSON.stringify(out));
    } catch (e) {
      console.error("[greeting]", e.message);
      res.writeHead(500, { "content-type": "application/json; charset=utf-8" });
      res.end(JSON.stringify({ error: e.message }));
    }
    return;
  }
  if (url.pathname === "/api/tts" && req.method === "POST") {
    let body = "";
    for await (const chunk of req) body += chunk;
    try {
      const { text } = JSON.parse(body || "{}");
      const audio = await speak(String(text || ""));
      res.writeHead(200, { "content-type": "audio/mpeg", "cache-control": "no-store" });
      res.end(audio);
    } catch (e) {
      console.error("[tts]", e.message);
      res.writeHead(500, { "content-type": "application/json; charset=utf-8" });
      res.end(JSON.stringify({ error: e.message }));
    }
    return;
  }
  if (url.pathname === "/api/state") {
    res.writeHead(200, { "content-type": "application/json; charset=utf-8" });
    res.end(JSON.stringify({ provider: PROVIDER, memory, followups, history: history.slice(-20) }));
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
