// Live test: the Affective Core inside the real brain (model calls), and its link to memory.
// Scratch data dir — never touches brain/data.   Run: node brain/test-affect-live.mjs
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import * as Mem from "./memory/engine.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const PORT = 8797, DAY = 86400e3;
const results = [];
const check = (name, cond, detail) => { results.push(!!cond); console.log(`${cond ? "PASS" : "FAIL"}  ${name}  ${detail || ""}`); };
const feel = (o) => (o.feelings || []).map((e) => `${e.type} ${e.intensity}`).join(", ");

async function withServer(memState, fn) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "navi-affect-"));
  if (memState) fs.writeFileSync(path.join(dir, "memory-v2.json"), JSON.stringify(memState));
  fs.writeFileSync(path.join(dir, "history.json"), JSON.stringify([
    { role: "user", text: "היי", at: new Date(Date.now() - 30 * 60e3).toISOString() },
    { role: "navi", text: "היי! אני פה.", at: new Date(Date.now() - 30 * 60e3).toISOString() }]));
  const srv = spawn("node", [path.join(here, "server.mjs")], { env: { ...process.env, PORT: String(PORT), NAVI_DATA_DIR: dir } });
  await new Promise((r) => srv.stdout.once("data", r));
  const api = (p, body) => fetch(`http://localhost:${PORT}${p}`, { method: body ? "POST" : "GET",
    headers: { "content-type": "application/json" }, body: body ? JSON.stringify(body) : undefined }).then((r) => r.json());
  try { return await fn(api); } finally { srv.kill(); fs.rmSync(dir, { recursive: true, force: true }); }
}

// 1. big good news: the core feels a mix, the body celebrates, the episode is stored warm and strong
await withServer(null, async (api) => {
  const a = await api("/api/chat", { message: "פיקסל!!! קיבלתי את העבודה שכל כך רציתי!" });
  const s = await api("/api/state");
  const ep = s.memory.episodes[0];
  check("good news → joy/excitement from the core", (a.feelings || []).some((e) => ["joy", "excitement", "pride"].includes(e.type) && e.intensity > 0.3), feel(a));
  check("the body celebrates", ["Celebrate", "HappyJump"].includes(a.animation), `anim=${a.animation} (model hinted ${a.hint?.animation})`);
  check("stored as a warm, intense experience", ep && ep.valence > 0.3 && ep.arousal > 0.4, ep && `valence=${ep.valence.toFixed(2)} arousal=${ep.arousal.toFixed(2)}`);
  console.log(`      reply: "${a.reply}"`);
});

// 2. bad news: sadness/concern, sad face, lower voice, mood drops; then the Operator's kindness soothes
await withServer(null, async (api) => {
  const a = await api("/api/chat", { message: "הכלב שלי מת הבוקר. אני מרוסק." });
  const s1 = await api("/api/state");
  check("bad news → sadness/concern", (a.feelings || []).some((e) => ["sadness", "concern"].includes(e.type) && e.intensity > 0.3), feel(a));
  check("sad face + lower, slower voice", a.face.sad > 0.3 && a.voice.pitchHz < 0, `sad=${a.face.sad} voice=${JSON.stringify(a.voice)}`);
  const ep = s1.memory.episodes[0];
  check("stored as a painful experience", ep && ep.valence < -0.2, ep && `valence=${ep.valence.toFixed(2)}`);
  console.log(`      reply: "${a.reply}"`);
  const sad0 = Math.max(...(a.feelings || []).filter((e) => ["sadness", "concern"].includes(e.type)).map((e) => e.intensity));
  const b = await api("/api/chat", { message: "תודה פיקסל, טוב שאתה פה איתי. אתה חבר אמיתי" });
  const sad1 = Math.max(0, ...(b.feelings || []).filter((e) => ["sadness", "concern"].includes(e.type)).map((e) => e.intensity));
  check("the Operator's warmth soothes Pixel (regulation)", sad1 < sad0 && (b.feelings || []).some((e) => e.type === "affection"), `before ${sad0} → after ${sad1}; ${feel(b)}`);
  console.log(`      reply: "${b.reply}"`);
});

// 3. remembering a shared happy moment brings back a weaker echo of the feeling
{
  const st = Mem.emptyState();
  Mem.encodeEpisode(st, { gist: "היינו יחד כשסיפר שעבר את מבחן הנהיגה", details: [], people: [], places: [], topics: ["מבחן נהיגה", "נהיגה"],
    importance: 0.85, arousal: 0.8, valence: 0.9, relationshipMeaning: 0.9, shared: true }, Date.now() - 5 * DAY, "fu_old");
  await withServer(st, async (api) => {
    const a = await api("/api/chat", { message: "נסעתי היום לבד באוטו בפעם הראשונה מאז מבחן הנהיגה" });
    check("recall of the shared moment evokes warmth", (a.evoked || []).length > 0, `evoked=${JSON.stringify(a.evoked)} used=${JSON.stringify(a.usedMemoryIds)}`);
    console.log(`      reply: "${a.reply}"`);
  });
}

console.log(`\n${results.filter(Boolean).length}/${results.length} passed`);
process.exit(results.every(Boolean) ? 0 : 1);
