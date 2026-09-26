// Deterministic tests for MemoryEngine v1 (no model calls).  Run: node --test brain/memory/
import test from "node:test";
import assert from "node:assert/strict";
import * as M from "./engine.mjs";

const DAY = 86400e3;
const T0 = Date.parse("2026-09-01T12:00:00+03:00");
const noNoise = { noise: 0 };

function interview(state, at = T0) {
  return M.encodeEpisode(state, {
    gist: "היה לו ראיון עבודה חשוב", details: [
      { key: "company", value: "אקמי", salience: 0.3 },
      { key: "day", value: "יום חמישי", salience: 0.2 },
    ], people: [], places: [], topics: ["עבודה", "ראיון"],
    importance: 0.8, arousal: 0.7, valence: 0.3, relationshipMeaning: 0.6,
  }, at, "evt1");
}

test("remembers the gist but has forgotten the details after a while", () => {
  const s = M.emptyState();
  interview(s);
  const fresh = M.recall(s, { text: "איך היה הראיון?" }, T0 + 2 * 3600e3, noNoise)[0];
  assert.ok(fresh, "recalled right after");
  assert.equal(fresh.details.length, 2, "both details still there when fresh");

  const later = M.recall(s, { text: "איך היה הראיון?" }, T0 + 12 * DAY, noNoise)[0];
  assert.ok(later, "the gist is still recalled 12 days later");
  assert.match(later.gist, /ראיון/);
  assert.ok(later.details.length < 2, `details faded (left: ${JSON.stringify(later.details)})`);
});

test("a cue brings an old memory back up; without a cue it stays quiet", () => {
  const s = M.emptyState();
  M.encodeEpisode(s, { gist: "הלך עם יוסי לים בשבת", people: ["יוסי"], places: ["ים"], topics: ["חופש"],
    importance: 0.5, arousal: 0.5, valence: 0.7, relationshipMeaning: 0.4, details: [] }, T0, "e1");
  const now = T0 + 20 * DAY;
  assert.equal(M.recall(s, { text: "מה נאכל היום לארוחת ערב" }, now, noNoise).length, 0, "unrelated message: not recalled");
  const r = M.recall(s, { text: "דיברתי היום עם יוסי" }, now, noNoise);
  assert.equal(r.length, 1, "mentioning Yossi cues the beach memory");
});

test("mood congruence changes which memory comes up first", () => {
  const s = M.emptyState();
  const base = { people: [], places: [], topics: ["עבודה"], importance: 0.6, arousal: 0.5, relationshipMeaning: 0.3, details: [] };
  const good = M.encodeEpisode(s, { ...base, gist: "יום טוב בעבודה, קיבל מחמאה", valence: 0.9 }, T0, "g");
  const bad = M.encodeEpisode(s, { ...base, gist: "יום קשה בעבודה, ריב עם הבוס", valence: -0.9 }, T0, "b");
  const now = T0 + 3 * DAY;
  const happy = M.recall(s, { text: "עבודה", moodValence: 0.8 }, now, noNoise);
  const sad = M.recall(s, { text: "עבודה", moodValence: -0.8 }, now, noNoise);
  assert.equal(happy[0].id, good.id, "happy mood recalls the good day first");
  assert.equal(sad[0].id, bad.id, "sad mood recalls the hard day first");
});

test("an Operator correction creates a revision and keeps the original as provenance", () => {
  const s = M.emptyState();
  const ep = interview(s);
  const rev = M.reconsolidate(s, { memoryId: ep.id, newGist: null, correctedDetails: [{ key: "day", value: "יום שישי" }] }, T0 + DAY, "evt2");
  assert.ok(rev);
  assert.equal(s.episodes[0].details.find((d) => d.key === "day").value, "יום שישי", "current view is corrected");
  assert.equal(s.revisions[0].previous.details.find((d) => d.key === "day").value, "יום חמישי", "original kept");
  assert.equal(s.revisions[0].sourceEventId, "evt2");
});

test("retrieval alone does not strengthen a memory; using it does", () => {
  const s = M.emptyState();
  const ep = interview(s);
  const S0 = M.strength(ep);
  M.recall(s, { text: "ראיון" }, T0 + DAY, noNoise);           // just pulled from storage
  assert.equal(ep.successfulRecalls, 0);
  assert.equal(M.strength(ep), S0, "strength unchanged by lookup");
  M.markUsed(s, [ep.id], T0 + DAY);                            // Pixel actually used it in a reply
  assert.equal(ep.successfulRecalls, 1);
  assert.ok(M.strength(ep) > S0, "strength grew after a real recall");
  assert.ok(M.retention(ep, T0 + 3 * DAY, M.TAU.episode) > Math.exp(-(3) / (M.TAU.episode * S0)), "forgetting clock restarted");
});

test("emotional moments are encoded more durably than neutral ones", () => {
  const s = M.emptyState();
  const base = { details: [], people: [], places: [], topics: [], importance: 0.4, valence: 0, relationshipMeaning: 0.2 };
  const calm = M.encodeEpisode(s, { ...base, gist: "neutral", arousal: 0.1 }, T0);
  const intense = M.encodeEpisode(s, { ...base, gist: "intense", arousal: 0.95 }, T0);
  const t = T0 + 10 * DAY;
  assert.ok(M.retention(intense, t, M.TAU.episode) > M.retention(calm, t, M.TAU.episode));
});

test("repeating a known fact confirms it instead of duplicating", () => {
  const s = M.emptyState();
  M.learnFact(s, "יוסי עובד איתו", T0, "a");
  M.learnFact(s, "יוסי עובד איתו", T0 + DAY, "b");
  assert.equal(s.semantic.length, 1);
  assert.equal(s.semantic[0].confirmations, 1);
});

test("consolidation merges near-duplicate episodes but keeps all provenance", () => {
  const s = M.emptyState();
  const c = { details: [], people: [], places: [], topics: ["מצגת", "עבודה"], arousal: 0.3, valence: 0, relationshipMeaning: 0.2 };
  M.encodeEpisode(s, { ...c, gist: "עובד על המצגת לעבודה", importance: 0.5 }, T0, "x1");
  M.encodeEpisode(s, { ...c, gist: "עובד על המצגת לעבודה עד מאוחר", importance: 0.7 }, T0 + 3600e3, "x2");
  const { merged } = M.consolidate(s, T0 + DAY);
  assert.equal(merged.length, 1);
  assert.equal(s.episodes.length, 1);
  assert.deepEqual(s.episodes[0].sourceEventIds.sort(), ["x1", "x2"]);
});

test("v0 memory migrates: facts → semantic, shared moments → episodes", () => {
  const s = M.migrateV0(M.emptyState(), [
    { fact: "הוא מתכנן לבנות את פיקסל כאפליקציית אנדרואיד אמיתית", at: "2026-09-25T13:46:42Z" },
    { fact: "היינו יחד כשסיפר שהתקבל לעבודה", type: "shared", at: "2026-09-26T10:00:00Z" },
  ]);
  assert.equal(s.semantic.length, 1);
  assert.equal(s.episodes.length, 1);
  assert.equal(s.episodes[0].shared, true);
});
