// Live test of MemoryEngine inside the real brain (model calls). Scratch data dir — never touches brain/data.
// Run: node brain/test-memory-live.mjs
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import * as Mem from "./memory/engine.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const PORT = 8798, DAY = 86400e3;
const results = [];
const check = (name, cond, detail) => { results.push(!!cond); console.log(`${cond ? "PASS" : "FAIL"}  ${name}  ${detail || ""}`); };

async function withServer(memState, fn) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "navi-mem-"));
  fs.writeFileSync(path.join(dir, "memory-v2.json"), JSON.stringify(memState));
  fs.writeFileSync(path.join(dir, "history.json"), JSON.stringify([
    { role: "user", text: "היי", at: new Date(Date.now() - 30 * 60e3).toISOString() },
    { role: "navi", text: "היי! אני פה.", at: new Date(Date.now() - 30 * 60e3).toISOString() }]));
  const srv = spawn("node", [path.join(here, "server.mjs")], { env: { ...process.env, PORT: String(PORT), NAVI_DATA_DIR: dir } });
  await new Promise((r) => srv.stdout.once("data", r));
  const api = (p, body) => fetch(`http://localhost:${PORT}${p}`, { method: body ? "POST" : "GET",
    headers: { "content-type": "application/json" }, body: body ? JSON.stringify(body) : undefined }).then((r) => r.json());
  try { return await fn(api); } finally { srv.kill(); fs.rmSync(dir, { recursive: true, force: true }); }
}

// 1. a story becomes an episode with details
await withServer(Mem.emptyState(), async (api) => {
  const a = await api("/api/chat", { message: "אתמול הייתי עם יוסי בים בתל אביב, ראינו דולפינים! היה מטורף" });
  const s = await api("/api/state");
  const ep = s.memory.episodes[0];
  check("story → episode encoded", ep && /ים|דולפינ/.test(ep.gist), ep && `gist="${ep.gist}" people=${JSON.stringify(ep.people)} details=${ep.details.length}`);
  console.log(`      reply: "${a.reply}"`);
});

// 2. an old memory (12 days) comes back from a cue; the fuzzy detail is hedged or dropped; using it strengthens it
{
  const st = Mem.emptyState();
  const ep = Mem.encodeEpisode(st, { gist: "הוא היה עם יוסי בים וראו דולפינים", details: [
    { key: "place", value: "חוף גורדון בתל אביב", salience: 0.3 }, { key: "day", value: "יום שבת", salience: 0.2 }],
    people: ["יוסי"], places: ["ים"], topics: ["חופש", "דולפינים"], importance: 0.6, arousal: 0.8, valence: 0.9, relationshipMeaning: 0.5 },
    Date.now() - 12 * DAY, "old");
  ep.occurredAt = ep.encodedAt;
  await withServer(st, async (api) => {
    const a = await api("/api/chat", { message: "דיברתי היום עם יוסי" });
    const s = await api("/api/state");
    const e = s.memory.episodes.find((x) => x.id === ep.id);
    check("cue (Yossi) brings back the old beach memory", /ים|דולפינ/.test(a.reply), `reply: "${a.reply}"`);
    check("no confident claim of the faded detail", !/גורדון/.test(a.reply) || /נדמה|אולי|\?/.test(a.reply));
    check("using the memory strengthens it", e.successfulRecalls === 1, `successfulRecalls=${e.successfulRecalls}`);
  });
}

// 3. a correction reconsolidates into a revision
{
  const st = Mem.emptyState();
  const ep = Mem.encodeEpisode(st, { gist: "היה לו ראיון עבודה בחברת הייטק", details: [{ key: "day", value: "יום חמישי", salience: 0.6 }],
    people: [], places: [], topics: ["ראיון", "עבודה"], importance: 0.8, arousal: 0.6, valence: 0.3, relationshipMeaning: 0.6 },
    Date.now() - 2 * 3600e3, "iv");
  await withServer(st, async (api) => {
    const a = await api("/api/chat", { message: "רגע, הראיון לא היה ביום חמישי, הוא היה ביום שישי" });
    const s = await api("/api/state");
    const e = s.memory.episodes.find((x) => x.id === ep.id);
    const day = e.details.find((d) => d.key === "day")?.value;
    check("correction applied to the current memory", /שישי/.test(day || "") || /שישי/.test(e.gist), `day=${day} gist="${e.gist}"`);
    check("original kept as a revision", s.memory.revisions.length === 1, `reply: "${a.reply}"`);
  });
}

// 4. unrelated small talk: nothing recalled, nothing invented, no episode for chit-chat
await withServer(Mem.emptyState(), async (api) => {
  const a = await api("/api/chat", { message: "מה נשמע?" });
  const s = await api("/api/state");
  check("small talk is not stored as an episode", s.memory.episodes.length === 0, `reply: "${a.reply}"`);
});

console.log(`\n${results.filter(Boolean).length}/${results.length} passed`);
process.exit(results.every(Boolean) ? 0 : 1);
