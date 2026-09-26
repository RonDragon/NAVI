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
import * as Mem from "./memory/engine.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(here, "..");
const DATA = process.env.NAVI_DATA_DIR ? path.resolve(process.env.NAVI_DATA_DIR) : path.join(here, "data");  // tests use a scratch dir
const PORT = Number(process.env.PORT || 8765);
fs.mkdirSync(DATA, { recursive: true });

const CONFIG = { operator_gender: process.env.NAVI_OPERATOR_GENDER || "masculine", historyTurns: 12 };
const PERSONA = fs.readFileSync(path.join(here, "persona.md"), "utf8").replace("{{operator_gender}}", CONFIG.operator_gender);

const MOODS = ["calm", "happy", "curious", "greet", "playful", "tired"];
const ANIMS = ["Idle", "Wave", "HappyJump", "TailWag", "Listen", "Sleep", "Celebrate", "Concerned", "Stretch"];
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
        eventAt: { type: ["string", "null"] }, // ISO 8601 with offset; null for ongoing things ("finishing the presentation")
        askAfter: { type: "string" },         // ISO 8601 — when it's natural to ask
        intent: { type: "string", enum: FOLLOWUP_INTENTS },
      },
      required: ["subject", "eventAt", "askAfter", "intent"],
      additionalProperties: false,
    },
    // the Operator just answered something you asked about (closes the loop — GPT review §C)
    followUpAnswer: {
      type: ["object", "null"],
      properties: {
        id: { type: "string" },               // id from "Waiting for an answer"
        outcome: { type: "string", enum: ["good", "bad", "neutral", "declined", "unclear"] },
        sharedMoment: { type: ["string", "null"] }, // good news worth remembering together, Hebrew, e.g. "היינו יחד כשסיפר שקיבל את העבודה"
      },
      required: ["id", "outcome", "sharedMoment"],
      additionalProperties: false,
    },
    // MemoryEngine v1 (docs/06 §2): the model proposes, the engine decides strength / forgetting / recall
    memoryCandidate: {                         // a meaningful episode worth remembering (not every message)
      type: ["object", "null"],
      properties: {
        gist: { type: "string" },
        details: { type: "array", items: { type: "object", properties: { key: { type: "string" }, value: { type: "string" },
          salience: { type: "number" } }, required: ["key", "value", "salience"], additionalProperties: false } },
        people: { type: "array", items: { type: "string" } },
        places: { type: "array", items: { type: "string" } },
        topics: { type: "array", items: { type: "string" } },
        importance: { type: "number" }, arousal: { type: "number" }, valence: { type: "number" }, relationshipMeaning: { type: "number" },
      },
      required: ["gist", "details", "people", "places", "topics", "importance", "arousal", "valence", "relationshipMeaning"],
      additionalProperties: false,
    },
    usedMemoryIds: { type: "array", items: { type: "string" } },   // recalled memories you actually used in this reply
    memoryCorrection: {                        // the Operator corrected something you remembered
      type: ["object", "null"],
      properties: {
        memoryId: { type: "string" }, newGist: { type: ["string", "null"] },
        correctedDetails: { type: "array", items: { type: "object", properties: { key: { type: "string" }, value: { type: "string" } },
          required: ["key", "value"], additionalProperties: false } },
      },
      required: ["memoryId", "newGist", "correctedDetails"],
      additionalProperties: false,
    },
  },
  required: ["reply", "mood", "animation", "face", "remember", "followUp", "followUpAnswer", "memoryCandidate", "usedMemoryIds", "memoryCorrection"],
  additionalProperties: false,
};
const SCHEMA_FILE = path.join(DATA, "reply-schema.json");
fs.writeFileSync(SCHEMA_FILE, JSON.stringify(SCHEMA));

// ---------- tiny persistent state ----------
const HISTORY_FILE = path.join(DATA, "history.json");
const MEMORY_FILE = path.join(DATA, "memory.json");
const load = (f, d) => { try { return JSON.parse(fs.readFileSync(f, "utf8")); } catch { return d; } };
let history = load(HISTORY_FILE, []);   // [{role:"user"|"navi", text, at}]
// MemoryEngine state (v2). On first run, the v0 fact list (memory.json) is migrated and left untouched as a backup.
const MEM_FILE = path.join(DATA, "memory-v2.json");
let mem = load(MEM_FILE, null) || Mem.migrateV0(Mem.emptyState(), load(MEMORY_FILE, []));
let lastRecall = [];                    // ids offered to the model this turn (only these may be marked used/corrected)
let lastMoodValence = 0.1;
const FOLLOWUPS_FILE = path.join(DATA, "followups.json");
let followups = load(FOLLOWUPS_FILE, []); // [{id, subject, eventAt, askAfter, intent, status: pending|asked|expired, createdAt}]
const save = () => {
  fs.writeFileSync(HISTORY_FILE, JSON.stringify(history.slice(-200), null, 1));
  fs.writeFileSync(MEM_FILE, JSON.stringify(mem, null, 1));
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

function contextBlock(turn = { text: "" }) {
  const now = Date.now();
  // what Pixel *actually remembers right now*: cued by this message + the last thing the Operator said
  const lastUser = [...history].reverse().find((h) => h.role === "user");
  const cueText = `${turn.text || ""} ${turn.kind === "event" ? (lastUser?.text || "") : ""}`;
  const recalled = Mem.recall(mem, { text: cueText, moodValence: lastMoodValence }, now);
  const known = Mem.knownFacts(mem, now);
  lastRecall = [...recalled.map((r) => r.id), ...known.map((k) => k.id)];
  const facts = known.map((k) => `- [${k.id}] ${k.proposition}${k.confidence < 0.6 ? ` (not sure, ${k.confidence})` : ""}`);
  const memories = recalled.map((r) => {
    const det = r.details.map((d) => `${d.key}: ${d.value} (confidence ${d.confidence})`).join("; ");
    return `- [${r.id}] ${r.gist}${r.shared ? " — a moment you shared" : ""} (≈${r.whenDaysAgo} days ago, confidence ${r.confidence})${det ? ` | details: ${det}` : ""}`;
  });
  const open = followups.filter((f) => f.status === "pending");
  const fu = open.length ? open.map((f) => `- ${f.subject} (${f.eventAt ? `event ${f.eventAt}` : "ongoing"}, ask after ${f.askAfter})`).join("\n") : "- (none)";
  const asked = followups.filter((f) => f.status === "asked" && Date.now() - Date.parse(f.askedAt) < 12 * 3600e3);
  const waiting = asked.length ? asked.map((f) => `- id=${f.id}: you asked about "${f.subject}"`).join("\n") : "- (none)";
  return `## What you know about the Operator\n${facts.join("\n") || "- (nothing yet — you just met)"}\n\n` +
    `## What comes to mind right now (your memories — ids in brackets)\n${memories.join("\n") || "- (nothing in particular)"}\n` +
    `Details under confidence 0.6 are fuzzy: hedge them ("נדמה לי...", "זה היה ביום חמישי?") or leave them out — never state them as fact.\n\n` +
    `## Things you're waiting to hear about (already tracked — don't create duplicates)\n${fu}\n\n` +
    `## Waiting for an answer (if this message answers one, fill followUpAnswer with its id)\n${waiting}\n\n## Now\n${nowLabel()}`;
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
      { type: "text", text: contextBlock(turn) },
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
  const prompt = `${PERSONA}\n\n${contextBlock(turn)}\n\n## Conversation so far\n${transcript || "(start)"}\n\n` +
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
  // MemoryEngine: the model proposed; the engine decides (only memories that were offered can be used/corrected)
  const now = Date.now(), evt = `evt_${now}`;
  if (out.remember && !SECRET.test(out.remember)) Mem.learnFact(mem, out.remember, now, evt);
  if (out.memoryCandidate && !SECRET.test(JSON.stringify(out.memoryCandidate))) Mem.encodeEpisode(mem, out.memoryCandidate, now, evt);
  Mem.markUsed(mem, (out.usedMemoryIds || []).filter((i) => lastRecall.includes(i)), now);
  if (out.memoryCorrection && lastRecall.includes(out.memoryCorrection.memoryId)) Mem.reconsolidate(mem, out.memoryCorrection, now, evt);
  lastMoodValence = { happy: 0.7, playful: 0.5, greet: 0.4, curious: 0.2, calm: 0.1, tired: -0.2 }[out.mood] ?? 0;
  if (out.animation === "Concerned") lastMoodValence = -0.4;
  trackFollowUp(out.followUp);
  if (turn.kind === "message") closeFollowUp(out);
  save();
  return out;
}

// ---------- Follow-up Engine (Bible §15.4 + GPT review): BEFORE → DURING → AFTER → closed ----------
// Lifecycle:  pending ──(evening before: offer to prepare)──(~1h before: short nudge)──(during: stay quiet)
//             ──(askAfter: ask once)──> asked ──(Operator's answer)──> closed{good|bad|neutral|declined}
//             bad → one gentle care check-in next day (never a nag); declined → dropped for good.
const newId = () => Math.random().toString(36).slice(2, 10);
const t = (iso) => (iso ? Date.parse(iso) : NaN);

function israelAt(daysAhead, hour) {            // ISO for Israel local HH:00, N days from today
  const d = new Date(Date.now() + daysAhead * 86400e3);
  const [date, off] = [nowLabel(d).slice(0, 10), nowLabel(d).slice(19, 25)];
  return `${date}T${String(hour).padStart(2, "0")}:00:00${off}`;
}

function trackFollowUp(f) {
  if (!f || !f.subject) return;
  const eventAt = t(f.eventAt), askAfter = t(f.askAfter);
  if (Number.isNaN(askAfter)) return;
  if (!Number.isNaN(eventAt) && eventAt < Date.now() - 36 * 3600e3) return;   // already long past
  const dup = followups.some((x) => (x.status === "pending" || x.status === "asked") && (x.subject === f.subject
    || (!Number.isNaN(eventAt) && x.eventAt && Math.abs(t(x.eventAt) - eventAt) < 3600e3)));
  if (dup) return;
  followups.push({ id: newId(), subject: f.subject, eventAt: Number.isNaN(eventAt) ? null : f.eventAt, askAfter: f.askAfter,
    intent: FOLLOWUP_INTENTS.includes(f.intent) ? f.intent : "ask_outcome", status: "pending", createdAt: new Date().toISOString() });
}

// The Operator answered something Pixel asked about: close the loop according to how it went.
function closeFollowUp(out) {
  const a = out.followUpAnswer;
  if (!a) return;
  const f = followups.find((x) => x.id === a.id && x.status === "asked");
  if (!f || a.outcome === "unclear") return;
  f.status = "closed"; f.outcome = a.outcome; f.closedAt = new Date().toISOString();
  if (a.outcome === "good") {
    if (a.sharedMoment && !SECRET.test(a.sharedMoment)) Mem.encodeEpisode(mem, { gist: a.sharedMoment, details: [], people: [], places: [],
      topics: [f.subject], importance: 0.85, arousal: 0.8, valence: 0.9, relationshipMeaning: 0.9, shared: true }, Date.now(), `fu_${f.id}`);
    if (!["Celebrate", "HappyJump"].includes(out.animation)) out.animation = "Celebrate";   // a win deserves the body
  }
  if (a.outcome === "bad" && !f.care) {        // not another nag: one quiet check-in tomorrow, then let it be
    followups.push({ id: newId(), subject: `איך הוא מרגיש אחרי ${f.subject}`, eventAt: null, askAfter: israelAt(1, 11),
      intent: "support", status: "pending", care: true, createdAt: f.closedAt });
    if (out.animation === "Idle") out.animation = "Concerned";
  }
}

// What's going on when the Operator opens the app — decides whether Pixel should speak first, and about what.
function openingSituation() {
  const now = Date.now();
  const hour = Number(nowLabel().slice(11, 13));
  for (const f of followups) {
    if (f.status !== "pending") continue;
    const ref = f.eventAt ? t(f.eventAt) : t(f.askAfter);
    if (ref < now - 4 * 86400e3) f.status = "expired";
  }
  const last = history.length ? t(history[history.length - 1].at) : null;
  const gapMin = last ? Math.round((now - last) / 60000) : null;
  const open = followups.filter((f) => f.status === "pending");
  const during = (f) => f.eventAt && t(f.eventAt) <= now && now < t(f.eventAt) + 2 * 3600e3;
  const due = open.filter((f) => t(f.askAfter) <= now && !during(f)).sort((a, b) => t(b.askAfter) - t(a.askAfter));
  const soon = open.filter((f) => f.eventAt && !f.encouragedAt && t(f.eventAt) > now && t(f.eventAt) - now <= 90 * 60e3);
  const eveningBefore = open.filter((f) => f.eventAt && !f.preparedAt && hour >= 17 && hour <= 22
    && t(f.eventAt) - now > 8 * 3600e3 && t(f.eventAt) - now <= 20 * 3600e3);
  const reasons = [];
  if (gapMin === null) reasons.push("first_meeting");
  if (due.length) reasons.push("followup_due");
  if (soon.length) reasons.push("event_soon");
  if (eveningBefore.length) reasons.push("evening_before");
  if (gapMin !== null && gapMin >= 180) reasons.push("back_after_a_while");
  return { gapMin, due, soon, eveningBefore, reasons };
}

async function greet() {
  // "sleep": while the Operator was away, near-duplicate episodes get consolidated (at most every 12h)
  if (Date.now() - (mem.lastConsolidatedAt || 0) > 12 * 3600e3) Mem.consolidate(mem, Date.now());
  const s = openingSituation();
  if (!s.reasons.length) { save(); return { silent: true, reasons: [] }; }   // nothing worth interrupting for — silence is fine
  // at most ONE topic, by priority: what happened > what's about to happen > tomorrow's thing
  let pick = null, phase = null;
  if (s.due[0]) [pick, phase] = [s.due[0], "after"];
  else if (s.soon[0]) [pick, phase] = [s.soon[0], "soon"];
  else if (s.eveningBefore[0]) [pick, phase] = [s.eveningBefore[0], "before"];
  const topic = {
    after: pick && (pick.care
      ? `A day ago the Operator had a hard time with this. Check in very gently, one short line, no pressure: "${pick.subject}".`
      : pick.eventAt
        ? `Follow-up due — ask briefly and warmly how this went: "${pick.subject}" (was at ${pick.eventAt}).`
        : `Ongoing thing — ask lightly how it's progressing: "${pick.subject}".`),
    soon: pick && `It's about to happen (${pick.eventAt}): "${pick.subject}". A tiny, practical nudge — a few words, no speech.`,
    before: pick && `It's tomorrow (${pick.eventAt}): "${pick.subject}". Offer once, casually, to help get ready tonight.`,
  }[phase];
  const lines = [
    "The Operator just opened the app and is looking at you. Say the first thing, like a friend who noticed them.",
    `Time since your last exchange: ${s.gapMin === null ? "never talked before" : `${s.gapMin} minutes`}.`,
    topic || "",
    "Rules: at most ONE topic. One or two short sentences. Match the time of day. Never guilt the Operator for being away.",
    "If nothing special, a light natural opener is enough. followUp and followUpAnswer must be null here.",
  ].filter(Boolean).join("\n");
  const out = await think({ kind: "event", text: lines });
  const now = new Date().toISOString();
  if (phase === "after") { pick.status = "asked"; pick.askedAt = now; }       // asked once; the answer closes it
  if (phase === "soon") pick.encouragedAt = now;
  if (phase === "before") pick.preparedAt = now;
  save();
  return { ...out, silent: false, reasons: s.reasons, phase };
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
    res.end(JSON.stringify({ provider: PROVIDER, memory: mem, followups, history: history.slice(-20) }));
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
