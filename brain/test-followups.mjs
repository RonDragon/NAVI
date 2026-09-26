// Scenario test for the Follow-up Engine lifecycle. Uses a scratch data dir — never touches brain/data.
// Run: node brain/test-followups.mjs      (calls the real brain → each scenario costs 1–2 model calls)
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const PORT = 8799;
const iso = (msFromNow) => new Date(Date.now() + msFromNow).toISOString();
const H = 3600e3, M = 60e3;

async function withServer(seed, fn) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "navi-test-"));
  fs.writeFileSync(path.join(dir, "followups.json"), JSON.stringify(seed.followups || []));
  fs.writeFileSync(path.join(dir, "history.json"), JSON.stringify([
    { role: "user", text: "היי", at: iso(-20 * M) }, { role: "navi", text: "היי! אני פה.", at: iso(-20 * M) }]));
  fs.writeFileSync(path.join(dir, "memory.json"), "[]");
  const srv = spawn("node", [path.join(here, "server.mjs")], { env: { ...process.env, PORT: String(PORT), NAVI_DATA_DIR: dir } });
  await new Promise((r) => srv.stdout.once("data", r));
  const api = (p, body) => fetch(`http://localhost:${PORT}${p}`, { method: body === undefined ? "GET" : "POST",
    headers: { "content-type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) }).then((r) => r.json());
  try { return await fn(api); } finally { srv.kill(); fs.rmSync(dir, { recursive: true, force: true }); }
}

const fu = (over) => ({ id: "f1", subject: "ראיון העבודה בחברת ההייטק", intent: "ask_outcome", status: "pending", createdAt: iso(-20 * H), ...over });
const results = [];
const check = (name, cond, detail) => { results.push({ name, ok: !!cond }); console.log(`${cond ? "PASS" : "FAIL"}  ${name}  ${detail || ""}`); };

// 1. ~1 hour before → a short nudge, and it's marked so it won't repeat
await withServer({ followups: [fu({ eventAt: iso(60 * M), askAfter: iso(4 * H) })] }, async (api) => {
  const g = await api("/api/greeting", {});
  const s = await api("/api/state");
  check("soon: nudges before the event", g.phase === "soon" && !g.silent, `→ "${g.reply}"`);
  check("soon: marked encouraged, still pending", s.followups[0].encouragedAt && s.followups[0].status === "pending");
});

// 2. during the event → stays quiet about it
await withServer({ followups: [fu({ eventAt: iso(-30 * M), askAfter: iso(-5 * M) })] }, async (api) => {
  const g = await api("/api/greeting", {});
  check("during: stays silent", g.silent === true, JSON.stringify(g.reasons));
});

// 3. after → asks once; a good answer closes it, celebrates and creates a shared memory
await withServer({ followups: [fu({ eventAt: iso(-4 * H), askAfter: iso(-1 * H) })] }, async (api) => {
  const g = await api("/api/greeting", {});
  check("after: asks how it went", g.phase === "after", `→ "${g.reply}"`);
  const a = await api("/api/chat", { message: "קיבלתי את העבודה!!" });
  const s = await api("/api/state");
  check("good answer: closed as good", s.followups[0].status === "closed" && s.followups[0].outcome === "good", `→ "${a.reply}"`);
  check("good answer: body celebrates", ["Celebrate", "HappyJump"].includes(a.animation), a.animation);
  check("good answer: shared memory saved", s.memory.some((m) => m.type === "shared"), JSON.stringify(s.memory));
  const g2 = await api("/api/greeting", {});
  check("after: never asks twice", g2.silent === true);
});

// 4. bad answer → closed as bad, one gentle care check-in scheduled for tomorrow (not a nag)
await withServer({ followups: [fu({ eventAt: iso(-4 * H), askAfter: iso(-1 * H) })] }, async (api) => {
  await api("/api/greeting", {});
  const a = await api("/api/chat", { message: "היה גרוע. ממש מבאס אותי" });
  const s = await api("/api/state");
  const care = s.followups.find((f) => f.care);
  check("bad answer: closed as bad", s.followups[0].outcome === "bad", `→ "${a.reply}"`);
  check("bad answer: one care check-in tomorrow", care && Date.parse(care.askAfter) > Date.now() + 6 * H, care && care.askAfter);
});

// 5. "forget it" → declined, dropped for good
await withServer({ followups: [fu({ eventAt: iso(-4 * H), askAfter: iso(-1 * H) })] }, async (api) => {
  await api("/api/greeting", {});
  const a = await api("/api/chat", { message: "עזוב, לא בא לי לדבר על זה" });
  const s = await api("/api/state");
  check("declined: closed, nothing new scheduled", s.followups[0].outcome === "declined" && s.followups.length === 1, `→ "${a.reply}"`);
});

// 6. ongoing effort with no date → tracked with eventAt null
await withServer({}, async (api) => {
  const a = await api("/api/chat", { message: "אני מנסה כבר שבוע לסיים את המצגת לעבודה ולא מצליח" });
  const s = await api("/api/state");
  const f = s.followups[0];
  check("ongoing: tracked without a date", f && f.eventAt === null && Date.parse(f.askAfter) > Date.now(), f && JSON.stringify(f));
});

const failed = results.filter((r) => !r.ok).length;
console.log(`\n${results.length - failed}/${results.length} passed`);
process.exit(failed ? 1 : 0);
