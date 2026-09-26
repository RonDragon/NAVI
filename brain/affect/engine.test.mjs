// Deterministic tests for the Affective Core + its link to memory.  Run: node --test brain/affect/engine.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import * as A from "./engine.mjs";
import * as M from "../memory/engine.mjs";

const T0 = Date.parse("2026-09-01T12:00:00+03:00"), MIN = 60e3, HOUR = 3600e3;
const jobOffer = { novelty: 0.7, pleasantness: 0.9, goalRelevance: 0.95, goalCongruence: 0.95, agency: "operator",
  controllability: 0.6, certainty: 0.95, normCompatibility: 0.8, relationshipRelevance: 0.9, expectedness: 0.3, copingPotential: 0.8 };
const jobRejected = { ...jobOffer, pleasantness: -0.8, goalCongruence: -0.9, agency: "other", controllability: 0.2 };
const strangeNoise = { novelty: 0.95, pleasantness: 0, goalRelevance: 0.5, goalCongruence: -0.3, agency: "circumstance",
  controllability: 0.3, certainty: 0.2, normCompatibility: 0.5, relationshipRelevance: 0.1, expectedness: 0.1, copingPotential: 0.4 };

test("good news for the Operator is a mix, not one label (joy + pride + excitement + affection)", () => {
  const s = A.emptyAffect();
  const felt = A.feel(s, jobOffer, T0).map((e) => e.type);
  for (const k of ["joy", "excitement", "pride", "affection"]) assert.ok(s.emotions[k]?.intensity > 0.2, `${k} active: ${JSON.stringify(A.top(s, 6))}`);
  assert.ok(!s.emotions.sadness, "no sadness");
  assert.ok(felt.length >= 3);
});

test("same event, different temperament → different feelings (curious Navi vs anxious Navi)", () => {
  const curious = A.emptyAffect({ ...A.PIXEL_TEMPERAMENT, noveltySeeking: 0.9, threatSensitivity: 0.15 });
  const anxious = A.emptyAffect({ ...A.PIXEL_TEMPERAMENT, noveltySeeking: 0.25, threatSensitivity: 0.9 });
  A.feel(curious, strangeNoise, T0); A.feel(anxious, strangeNoise, T0);
  const c = (s, k) => s.emotions[k]?.intensity || 0;
  assert.ok(c(curious, "curiosity") > c(curious, "fear"), `curious: ${JSON.stringify(A.top(curious))}`);
  assert.ok(c(anxious, "fear") + c(anxious, "concern") > c(anxious, "curiosity"), `anxious: ${JSON.stringify(A.top(anxious))}`);
});

test("emotions fade within hours; the mood lingers longer and drifts back to baseline", () => {
  const s = A.emptyAffect();
  const base = A.baselineMood(s.temperament);
  A.feel(s, jobRejected, T0);
  const p0 = s.mood.p;
  assert.ok(p0 < base.p, "mood dropped");
  A.advance(s, T0 + 6 * HOUR);
  assert.ok(!s.emotions.disappointment || s.emotions.disappointment.intensity < 0.2, "emotion mostly faded after 6h");
  assert.ok(s.mood.p < base.p - 0.001, "mood still a bit low after 6h");
  A.advance(s, T0 + 48 * HOUR);
  assert.ok(Math.abs(s.mood.p - base.p) < 0.01, "mood back to baseline after 2 days");
});

test("regulation: support from the Operator softens disappointment and brings affection", () => {
  const alone = A.emptyAffect(), held = A.emptyAffect();
  A.feel(alone, jobRejected, T0); A.feel(held, jobRejected, T0);
  A.feel(held, { goalRelevance: 0.3, goalCongruence: 0.3, pleasantness: 0.6, relationshipRelevance: 0.9, operatorSupport: 0.9, novelty: 0.1 }, T0 + MIN);
  A.advance(alone, T0 + MIN);
  assert.ok(held.emotions.disappointment.intensity < alone.emotions.disappointment.intensity, "disappointment softened");
  assert.ok((held.emotions.affection?.intensity || 0) > 0.2, "affection rose");
});

test("embodiment: strong joy celebrates; sadness shows on the face, lowers the voice, dims the glow", () => {
  const happy = A.emptyAffect(), sad = A.emptyAffect();
  A.feel(happy, jobOffer, T0); A.feel(sad, jobRejected, T0);
  const h = A.embody(happy, "Idle"), d = A.embody(sad, "Idle");
  assert.ok(["Celebrate", "HappyJump"].includes(h.animation), h.animation);
  assert.equal(d.animation, "Concerned");
  assert.ok(d.face.sad > 0.4 && h.face.happy > 0.4);
  assert.ok(d.voice.pitchHz < h.voice.pitchHz && d.glow < h.glow);
});

test("MEMORY LINK: the feeling at encoding sets how strongly an experience is stored", () => {
  const mem = M.emptyState(), s = A.emptyAffect();
  A.feel(s, jobOffer, T0);
  const peak = A.arousalPeak(s);
  const ep = M.encodeEpisode(mem, { gist: "קיבל את העבודה", details: [], people: [], places: [], topics: ["עבודה"],
    importance: 0.6, arousal: Math.max(0.2, peak), valence: A.valenceNow(s), relationshipMeaning: 0.8 }, T0);
  const flat = M.encodeEpisode(mem, { gist: "סידר את החדר", details: [], people: [], places: [], topics: [],
    importance: 0.6, arousal: 0.2, valence: 0, relationshipMeaning: 0.8 }, T0);
  assert.ok(M.strength(ep) > M.strength(flat), "emotional moment is encoded stronger");
  assert.ok(ep.valence > 0.3, `valence from the core: ${ep.valence}`);
});

test("MEMORY LINK: the current mood decides which memory surfaces (mood congruence from the core)", () => {
  const mem = M.emptyState();
  const base = { people: [], places: [], topics: ["עבודה"], importance: 0.6, arousal: 0.5, relationshipMeaning: 0.3, details: [] };
  const good = M.encodeEpisode(mem, { ...base, gist: "יום טוב בעבודה", valence: 0.9 }, T0);
  const bad = M.encodeEpisode(mem, { ...base, gist: "יום קשה בעבודה", valence: -0.9 }, T0);
  const happy = A.emptyAffect(), sad = A.emptyAffect();
  A.feel(happy, jobOffer, T0 + HOUR); A.feel(sad, jobRejected, T0 + HOUR);
  const r = (s) => M.recall(mem, { text: "עבודה", moodValence: A.valenceNow(s) }, T0 + 2 * HOUR, { noise: 0 })[0].id;
  assert.equal(r(happy), good.id);
  assert.equal(r(sad), bad.id);
});

test("MEMORY LINK: remembering a shared moment brings back a weaker echo of the feeling", () => {
  const s = A.emptyAffect();
  const echo = A.evoke(s, { id: "ep1", valence: 0.9, arousal: 0.8, shared: true }, T0);
  assert.equal(echo.type, "affection");
  assert.ok(echo.intensity > 0.2 && echo.intensity < 0.5, "an echo, weaker than the original moment");
  assert.equal(A.evoke(A.emptyAffect(), { id: "ep2", valence: 0, arousal: 0.8 }, T0), null, "neutral memory evokes nothing");
});

test("personality is viscous: one experience never moves a trait; 20+ consistent ones nudge it by 0.02", () => {
  const s = A.emptyAffect();
  assert.equal(A.addTraitEvidence(s, "boldness", +1, 0.9, T0, "e0"), false);
  assert.equal(s.developed.boldness, 0.5);
  let moved = false;
  for (let i = 1; i <= 20 && !moved; i++) moved = A.addTraitEvidence(s, "boldness", +1, 0.6, T0 + i * 86400e3, `e${i}`);
  assert.ok(moved);
  assert.equal(+s.developed.boldness.toFixed(2), 0.52);
});
