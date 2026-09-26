// Affective Core v1 — emotions, mood and temperament for the Navi (docs/06-mind-v2-design.md §1).
//
//   EVENT → APPRAISAL (LLM observes) → EMOTION IMPULSES (code) → EMOTION STATE (decaying vector)
//         → MOOD (PAD, slow) → REGULATION → EMBODIMENT (body / face / voice)   … and it feeds MEMORY.
//
// "LLM observes/proposes. Core decides." The model never picks what Pixel feels.
// Pure functions over a plain state object + injectable `now` (ms).

const MIN = 60e3;
const clamp = (v, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, Number(v) || 0));
const pos = (v) => Math.max(0, v), neg = (v) => Math.max(0, -v);

export const EMOTIONS = ["joy", "sadness", "fear", "anger", "relief", "pride", "disappointment",
  "concern", "curiosity", "excitement", "affection"];

// PAD direction of each emotion (Pleasure, Arousal, Dominance) — used to move the slow mood
const PAD = {
  joy: [0.8, 0.5, 0.4], sadness: [-0.7, -0.4, -0.4], fear: [-0.6, 0.7, -0.6], anger: [-0.6, 0.7, 0.4],
  relief: [0.6, -0.3, 0.2], pride: [0.7, 0.4, 0.6], disappointment: [-0.6, -0.2, -0.3], concern: [-0.4, 0.4, -0.2],
  curiosity: [0.3, 0.5, 0.2], excitement: [0.7, 0.9, 0.3], affection: [0.8, 0.1, 0.2],
};
// base half-life (minutes); scaled by the temperament's recovery rate
const HALF_LIFE = { joy: 45, sadness: 120, fear: 30, anger: 40, relief: 30, pride: 60, disappointment: 150,
  concern: 90, curiosity: 20, excitement: 25, affection: 180 };

// Pixel's temperament (genesis): curious, fairly bold, warm, quick to recover. Almost fixed for life.
export const PIXEL_TEMPERAMENT = { noveltySeeking: 0.78, threatSensitivity: 0.35, rewardSensitivity: 0.7, sociability: 0.75,
  persistence: 0.6, emotionalReactivity: 0.6, recoveryRate: 0.6, autonomy: 0.5 };

export function emptyAffect(temperament = PIXEL_TEMPERAMENT) {
  return {
    version: 1, temperament: { ...temperament },
    developed: { boldness: 0.5, patience: 0.5, playfulness: 0.6, openness: 0.6, cooperativeness: 0.6, selfControl: 0.5 },
    regulation: { reappraisalBias: 0.5, socialSoothingSensitivity: 0.7 },
    emotions: {},                                   // type -> { intensity, at, cause }
    mood: baselineMood(temperament), updatedAt: 0, evidence: [],
  };
}

// the mood Pixel drifts back to — set by temperament (a cheerful, curious creature sits slightly positive)
export function baselineMood(T) {
  return {
    p: clamp(0.15 + 0.3 * (T.rewardSensitivity - 0.5) - 0.3 * (T.threatSensitivity - 0.5) + 0.2 * (T.sociability - 0.5), -1, 1),
    a: clamp(0.0 + 0.3 * (T.noveltySeeking - 0.5) + 0.2 * (T.emotionalReactivity - 0.5), -1, 1),
    d: clamp(0.1 + 0.3 * (T.autonomy - 0.5) - 0.2 * (T.threatSensitivity - 0.5), -1, 1),
  };
}

// ---------- time: emotions decay (fast), mood relaxes to baseline (slow) ----------
export function advance(state, now) {
  const dtMin = state.updatedAt ? Math.max(0, (now - state.updatedAt) / MIN) : 0;
  const rec = 0.5 + state.temperament.recoveryRate;                 // 0.5..1.5 — quick recoverers let go sooner
  for (const [k, e] of Object.entries(state.emotions)) {
    e.intensity *= Math.pow(2, -dtMin / (HALF_LIFE[k] / rec));
    if (e.intensity < 0.03) delete state.emotions[k];
  }
  const base = baselineMood(state.temperament);
  const keep = Math.exp(-0.15 * (dtMin / 60));                       // λ≈0.15/h → mood half-life ≈ 4.6h
  for (const c of ["p", "a", "d"]) state.mood[c] = base[c] + (state.mood[c] - base[c]) * keep;
  state.updatedAt = now;
  return state;
}

// ---------- appraisal → emotion impulses (deterministic; temperament biases the reading) ----------
// appraisal (from the LLM): novelty, pleasantness, goalRelevance, goalCongruence, agency, controllability, certainty,
//   normCompatibility, relationshipRelevance, expectedness, copingPotential, operatorSupport
export function impulsesFrom(ap, state) {
  const T = state.temperament;
  const g = clamp(ap.goalRelevance), gc = clamp(ap.goalCongruence, -1, 1), pl = clamp(ap.pleasantness, -1, 1);
  const nov = clamp(ap.novelty), cert = clamp(ap.certainty ?? 0.7), ctrl = clamp(ap.controllability ?? 0.5);
  const exp = clamp(ap.expectedness ?? 0.5), rel = clamp(ap.relationshipRelevance), norm = clamp(ap.normCompatibility ?? 0.5, -1, 1);
  const cope = clamp(ap.copingPotential ?? 0.5), who = ap.agency || "circumstance";
  const good = pos(gc) * (0.4 + 0.6 * g), bad = neg(gc) * (0.4 + 0.6 * g);
  const unknown = nov * (1 - cert) * (1 - exp) * T.threatSensitivity;   // the unfamiliar & unclear — threat only to the sensitive
  const threat = clamp(bad * (1 - cert) * (1 - 0.5 * cope) + 0.6 * unknown);
  const reward = 0.7 + 0.6 * (T.rewardSensitivity - 0.5), fearful = 0.7 + 0.8 * (T.threatSensitivity - 0.5);
  const curious = 0.6 + 0.8 * (T.noveltySeeking - 0.5);
  const imp = {
    joy: reward * (0.7 * good + 0.3 * pos(pl)),
    excitement: reward * good * (0.4 + 0.6 * nov) * (0.5 + 0.5 * (1 - exp)),
    pride: who === "operator" || who === "navi" ? good * (0.5 + 0.5 * rel) * 0.8 : 0,
    relief: good * cert * (1 - exp) * (state.emotions.concern || state.emotions.fear ? 0.9 : 0.3),
    sadness: bad * cert * (1 - 0.6 * ctrl),
    disappointment: bad * cert * (1 - exp) * 0.9,
    fear: fearful * threat * (1 - rel * 0.5),                         // fear for himself…
    concern: fearful * (bad * (0.3 + 0.7 * rel) * (1 - 0.3 * cert) + threat * rel),   // …concern for the Operator
    anger: bad * (who === "other" || who === "navi" ? 1 : 0.2) * ctrl * (0.5 + 0.5 * neg(norm)) * 0.8,
    curiosity: curious * nov * (0.5 + 0.5 * (pl + 1) / 2) * (1 - 0.6 * threat) * (1 - 0.7 * bad),
    affection: pos(pl) * rel * (0.5 + 0.5 * T.sociability),
  };
  const react = 0.6 + 0.8 * (T.emotionalReactivity - 0.5);           // 0.6 · (0.2..1.0) range
  for (const k of EMOTIONS) imp[k] = clamp(imp[k] * react * 1.4);
  return imp;
}

// ---------- apply an appraised event: impulses join the (decayed) state, then mood moves a little ----------
export function feel(state, ap, now, cause = null) {
  advance(state, now);
  const imp = impulsesFrom(ap, state);
  for (const k of EMOTIONS) {
    if (imp[k] < 0.05) continue;
    const cur = state.emotions[k]?.intensity || 0;
    state.emotions[k] = { intensity: clamp(Math.max(cur, imp[k]) + 0.3 * Math.min(cur, imp[k])), at: now, cause };   // saturating
  }
  regulate(state, ap);
  moveMood(state);
  return top(state);
}

// emotion regulation: social soothing from the Operator + reappraisal (rules, not the LLM)
export function regulate(state, ap) {
  const support = clamp(ap.operatorSupport);
  if (support > 0) {
    const s = support * state.regulation.socialSoothingSensitivity;
    for (const k of ["sadness", "disappointment", "fear", "concern", "anger"]) {
      if (state.emotions[k]) state.emotions[k].intensity *= (1 - 0.45 * s);
    }
    const aff = state.emotions.affection?.intensity || 0;
    state.emotions.affection = { intensity: clamp(aff + 0.2 * s), at: state.updatedAt, cause: "operator_support" };
    state.mood.d = clamp(state.mood.d + 0.15 * s, -1, 1);           // feeling held → a bit more in control
  }
}

function moveMood(state) {
  for (const [k, e] of Object.entries(state.emotions)) {
    const v = PAD[k];
    state.mood.p = clamp(state.mood.p + 0.08 * e.intensity * v[0], -1, 1);
    state.mood.a = clamp(state.mood.a + 0.08 * e.intensity * v[1], -1, 1);
    state.mood.d = clamp(state.mood.d + 0.08 * e.intensity * v[2], -1, 1);
  }
}

export function top(state, n = 4) {
  return Object.entries(state.emotions).map(([type, e]) => ({ type, intensity: +e.intensity.toFixed(2) }))
    .sort((a, b) => b.intensity - a.intensity).slice(0, n);
}

// "how I feel right now" in one number the memory system can use (−1..1)
export const valenceNow = (state) => {
  const e = Object.entries(state.emotions).reduce((s, [k, v]) => s + PAD[k][0] * v.intensity, 0);
  return clamp(0.5 * state.mood.p + 0.7 * Math.tanh(e), -1, 1);
};
export const arousalPeak = (state) => Math.max(0, ...Object.values(state.emotions).map((e) => e.intensity));

// ---------- memory → emotion: recalling an experience brings back a weaker echo of its feeling ----------
export function evoke(state, memory, now) {
  advance(state, now);
  const strength = 0.4 * clamp(memory.arousal ?? 0.5);
  const kind = (memory.valence ?? 0) >= 0.2 ? (memory.shared ? "affection" : "joy") : (memory.valence ?? 0) <= -0.2 ? "sadness" : null;
  if (!kind || strength < 0.05) return null;
  const cur = state.emotions[kind]?.intensity || 0;
  state.emotions[kind] = { intensity: clamp(Math.max(cur, strength)), at: now, cause: `recall:${memory.id}` };
  moveMood(state);
  return { type: kind, intensity: +strength.toFixed(2) };
}

// ---------- embodiment: emotions + mood → body, face and voice (so two "happy" Navis don't look the same) ----------
export function embody(state, suggestedAnimation = "Idle") {
  const E = (k) => state.emotions[k]?.intensity || 0;
  const M = state.mood;
  const face = {
    happy: clamp(Math.max(E("joy"), E("excitement") * 0.8, E("affection") * 0.6, E("pride") * 0.7)),
    sad: clamp(Math.max(E("sadness"), E("disappointment"), E("concern") * 0.7)),
    surprised: clamp(Math.max(E("excitement") * 0.5, E("fear") * 0.6, E("curiosity") * 0.3)),
    mouthOpen: clamp(E("excitement") * 0.5),
  };
  const [lead] = top(state, 1);
  // strong feelings choose the body; otherwise the model's contextual suggestion (Wave for hello, Sleep for goodnight…)
  let animation = suggestedAnimation;
  if (lead && lead.intensity >= 0.45) {
    animation = { joy: E("excitement") > 0.5 ? "Celebrate" : "HappyJump", excitement: "Celebrate", pride: "Celebrate",
      affection: "TailWag", relief: "Stretch", sadness: "Concerned", disappointment: "Concerned", concern: "Concerned",
      fear: "Concerned", curiosity: "Listen", anger: "Listen" }[lead.type] || animation;
    if (["Wave", "Sleep"].includes(suggestedAnimation) && lead.intensity < 0.7) animation = suggestedAnimation;
  }
  const mood = !lead || lead.intensity < 0.25 ? (M.a < -0.3 ? "tired" : "calm")
    : { joy: "happy", excitement: "happy", pride: "happy", relief: "calm", affection: "playful", curiosity: "curious",
      sadness: "calm", disappointment: "calm", concern: "calm", fear: "curious", anger: "calm" }[lead.type];
  return {
    mood, animation, face,
    glow: +clamp(2.5 + 4 * pos(M.a) + 3 * (E("excitement") + E("joy")) / 2 - 1.5 * E("sadness"), 0.8, 8).toFixed(2),
    voice: {                                                          // relative to the base voice (edge-tts units)
      pitchHz: Math.round(12 * M.a + 10 * (E("excitement") + E("joy")) - 12 * (E("sadness") + E("disappointment"))),
      ratePct: Math.round(8 * M.a + 6 * E("excitement") - 8 * (E("sadness") + E("disappointment"))),
    },
    emotions: top(state), pad: { p: +M.p.toFixed(2), a: +M.a.toFixed(2), d: +M.d.toFixed(2) },
  };
}

// ---------- slow personality development: evidence accumulates; only repeated evidence moves a trait ----------
export function addTraitEvidence(state, trait, direction, strength, now, eventId) {
  state.evidence.push({ trait, direction: Math.sign(direction), strength: clamp(strength), at: now, eventId });
  const recent = state.evidence.filter((e) => e.trait === trait && now - e.at < 60 * 86400e3);
  const net = recent.reduce((s, e) => s + e.direction * e.strength, 0);
  if (recent.length >= 20 && Math.abs(net) >= 8) {                   // 20+ independent episodes, clearly one-sided
    state.developed[trait] = clamp(state.developed[trait] + 0.02 * Math.sign(net));
    state.evidence = state.evidence.filter((e) => e.trait !== trait);
    return true;
  }
  return false;
}
