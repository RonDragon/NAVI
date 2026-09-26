// MemoryEngine v1 — human-like memory for the Navi (docs/06-mind-v2-design.md §2).
//
// Principles:
//   * The LLM *proposes* memories (candidates, facts, corrections). This engine *decides* strength, forgetting and recall.
//   * Records are never lost; `retention` is how easily Pixel recalls something naturally, not whether it exists.
//   * Retrieval from storage is not remembering: only memories actually *used* in a reply get strengthened.
//   * Reconsolidation never overwrites: corrections become revisions and the original stays as provenance.
//
// Pure functions over a plain state object + an injectable `now` (ms), so everything is testable without a model.

const DAY = 86400e3, HOUR = 3600e3;

// τ (days) per memory kind: facts are stable, an episode's gist lasts, its details fade fastest.
export const TAU = { semantic: 30, episode: 4, detail: 1.2 };
export const RECALL_THRESHOLD = 1.25;   // activation needed for Pixel to actually "remember" something
export const DETAIL_MIN_CONF = 0.25;    // below this a detail isn't even offered to the LLM

export function emptyState() {
  return { version: 1, episodes: [], semantic: [], procedural: [], revisions: [], lastConsolidatedAt: 0 };
}

const clamp01 = (v) => Math.max(0, Math.min(1, Number(v) || 0));
const id = (p) => `${p}_${Math.random().toString(36).slice(2, 10)}`;

// ---------- Hebrew-ish tokenization for retrieval cues ----------
const STOP = new Set(("של את על עם זה זו זאת הוא היא הם הן אני אתה את אנחנו לא כן גם רק כל אבל או אם כי מה מי איך למה " +
  "מתי איפה יש אין היה הייתה היו יהיה עוד כבר פה שם אז כמו הרבה קצת ממש מאוד טוב שלי שלך שלו שלה לי לך לו לה " +
  "the a an and or to of in on is it you i me my").split(/\s+/));
export function tokens(text) {
  return [...new Set(String(text || "").toLowerCase().replace(/[^\p{L}\p{N}\s]/gu, " ").split(/\s+/)
    .filter(Boolean)
    .map((w) => (w.length > 3 && /^[והבלמשכ]/.test(w) ? w.slice(1) : w))   // strip one Hebrew prefix letter (ו/ה/ב/ל/מ/ש/כ)
    .filter((w) => w.length > 1 && !STOP.has(w)))];
}
const overlap = (a, b) => {                // share of cue tokens found in the memory, softened
  if (!a.length || !b.length) return 0;
  const B = new Set(b);
  const hit = a.filter((w) => B.has(w) || [...B].some((x) => x.length > 3 && (x.startsWith(w) || w.startsWith(x)))).length;
  return hit / Math.sqrt(a.length * b.length);
};

// ---------- strength & retention ----------
// S = 1 + 2·ln(1+successfulRecalls) + 3I + 1.5E + 1.5C      (GPT-normalized version of the research formula)
export function strength(m) {
  return 1 + 2 * Math.log(1 + (m.successfulRecalls || 0)) + 3 * clamp01(m.importance) +
    1.5 * clamp01(m.arousal) + 1.5 * clamp01(m.confirmations ? Math.min(1, m.confirmations / 3) : 0);
}
// R = e^(−Δt / (τ·S)), Δt measured from the last *successful* recall (or encoding)
export function retention(m, now, tau) {
  const since = now - (m.lastRecalledAt || m.encodedAt);
  return Math.exp(-(since / DAY) / (tau * strength(m)));
}

// ---------- encoding ----------
// candidate (from the LLM): { gist, details:[{key,value,salience}], people, places, topics, importance, arousal, valence, relationshipMeaning }
export function encodeEpisode(state, c, now, sourceEventId) {
  if (!c || !c.gist) return null;
  const ep = {
    id: id("ep"), encodedAt: now, occurredAt: now, gist: String(c.gist),
    details: (c.details || []).filter((d) => d && d.value).map((d) => ({ key: String(d.key || "detail"), value: String(d.value),
      salience: clamp01(d.salience ?? 0.5), confidence: 1 })),
    people: (c.people || []).map(String), places: (c.places || []).map(String), topics: (c.topics || []).map(String),
    importance: clamp01(c.importance), arousal: clamp01(c.arousal), valence: Math.max(-1, Math.min(1, Number(c.valence) || 0)),
    relationshipMeaning: clamp01(c.relationshipMeaning), shared: !!c.shared,
    successfulRecalls: 0, lastRecalledAt: null, sourceEventIds: sourceEventId ? [sourceEventId] : [],
  };
  // emotionally strong / relationship-heavy moments are encoded more durably (flashbulb-ish), capped
  if (ep.arousal > 0.7 || ep.relationshipMeaning > 0.7) ep.importance = Math.min(1, ep.importance + 0.15);
  state.episodes.push(ep);
  return ep;
}

// semantic facts from `remember`; repeating a known fact confirms it instead of duplicating
export function learnFact(state, proposition, now, evidenceId) {
  const p = String(proposition || "").trim();
  if (!p) return null;
  const tp = tokens(p);
  const same = state.semantic.find((s) => s.proposition === p || overlap(tp, tokens(s.proposition)) > 0.8);
  if (same) {
    same.confirmations = (same.confirmations || 0) + 1; same.lastConfirmedAt = now;
    if (evidenceId) same.evidenceIds.push(evidenceId);
    return same;
  }
  const f = { id: id("sf"), proposition: p, encodedAt: now, lastConfirmedAt: now, confirmations: 0, importance: 0.5, arousal: 0,
    successfulRecalls: 0, lastRecalledAt: null, evidenceIds: evidenceId ? [evidenceId] : [] };
  state.semantic.push(f);
  return f;
}

// ---------- retrieval: "remembering", not "searching" ----------
// cue: { text, mood: {valence} , now }   → recalled items with gist + confidence-weighted details
export function recall(state, cue, now, { limit = 4, noise = 0.08, rng = Math.random } = {}) {
  const cueTok = tokens(cue.text);
  const moodV = Number(cue.moodValence) || 0;
  const scored = [];
  for (const m of state.episodes) {
    const R = retention(m, now, TAU.episode);
    const memTok = tokens([m.gist, ...m.people, ...m.places, ...m.topics, ...m.details.map((d) => d.value)].join(" "));
    const cueRelevance = overlap(cueTok, memTok);
    const moodCongruence = 1 - Math.abs(m.valence - moodV) / 2;              // 0..1
    const recentPriming = m.lastRecalledAt && now - m.lastRecalledAt < 2 * HOUR ? 1 : 0;
    const activation = 1.2 * cueRelevance + 0.8 * moodCongruence * (cueRelevance > 0 ? 1 : 0.35) + 0.8 * R
      + 0.7 * m.importance + 0.6 * m.relationshipMeaning + 0.4 * recentPriming + (rng() - 0.5) * 2 * noise;
    scored.push({ m, R, activation, cueRelevance });
  }
  scored.sort((a, b) => b.activation - a.activation);
  return scored.filter((s) => s.activation >= RECALL_THRESHOLD).slice(0, limit).map(({ m, R, activation }) => ({
    id: m.id, gist: m.gist, confidence: +Math.min(1, 0.3 + R).toFixed(2), shared: m.shared, activation: +activation.toFixed(3),
    whenDaysAgo: +((now - m.occurredAt) / DAY).toFixed(1),
    details: m.details.map((d) => {
      // each detail fades on its own clock; salient details last longer
      const dR = Math.exp(-(((now - (m.lastRecalledAt || m.encodedAt)) / DAY)) / (TAU.detail * strength(m) * (0.5 + d.salience)));
      return { key: d.key, value: d.value, confidence: +(dR * d.confidence).toFixed(2) };
    }).filter((d) => d.confidence >= DETAIL_MIN_CONF),
  }));
}

// semantic facts in context: well-retained ones, most confident first (facts are cheap; keep the list small)
export function knownFacts(state, now, limit = 20) {
  return state.semantic.map((f) => ({ f, R: retention(f, now, TAU.semantic) }))
    .filter((x) => x.R > 0.15).sort((a, b) => b.R - a.R).slice(0, limit)
    .map(({ f, R }) => ({ id: f.id, proposition: f.proposition, confidence: +Math.min(1, R + 0.1 * (f.confirmations || 0)).toFixed(2) }));
}

// ---------- recall that was actually used → strengthening ----------
export function markUsed(state, ids, now) {
  for (const mid of ids || []) {
    const m = state.episodes.find((e) => e.id === mid) || state.semantic.find((s) => s.id === mid);
    if (!m) continue;
    m.successfulRecalls = (m.successfulRecalls || 0) + 1;
    m.lastRecalledAt = now;
  }
}

// ---------- reconsolidation: corrections become revisions, never silent overwrites ----------
// correction: { memoryId, newGist|null, correctedDetails:[{key,value}] }
export function reconsolidate(state, correction, now, sourceEventId) {
  if (!correction || !correction.memoryId) return null;
  const m = state.episodes.find((e) => e.id === correction.memoryId);
  if (!m) return null;
  const rev = { id: id("rev"), memoryId: m.id, at: now, sourceEventId: sourceEventId || null,
    previous: { gist: m.gist, details: m.details.map((d) => ({ ...d })) } };
  if (correction.newGist) m.gist = String(correction.newGist);
  for (const cd of correction.correctedDetails || []) {
    const d = m.details.find((x) => x.key === cd.key);
    if (d) { d.value = String(cd.value); d.confidence = 1; }
    else m.details.push({ key: String(cd.key), value: String(cd.value), salience: 0.7, confidence: 1 });
  }
  m.lastRecalledAt = now; m.successfulRecalls = (m.successfulRecalls || 0) + 1;   // discussing it re-activates it
  state.revisions.push(rev);
  return rev;
}

// ---------- consolidation ("sleep"): merge near-duplicates, let faded details go quiet ----------
export function consolidate(state, now) {
  const merged = [];
  const eps = [...state.episodes].sort((a, b) => a.encodedAt - b.encodedAt);
  for (let i = 0; i < eps.length; i++) {
    for (let j = i + 1; j < eps.length; j++) {
      const a = eps[i], b = eps[j];
      if (!a || !b || a.mergedInto || b.mergedInto) continue;
      if (Math.abs(b.encodedAt - a.encodedAt) > DAY) continue;
      const sim = overlap(tokens(a.gist + " " + a.topics.join(" ")), tokens(b.gist + " " + b.topics.join(" ")));
      if (sim < 0.6) continue;
      // keep the more important one, fold the other in (details + provenance), never delete provenance
      const [keep, fold] = a.importance >= b.importance ? [a, b] : [b, a];
      for (const d of fold.details) if (!keep.details.some((x) => x.key === d.key)) keep.details.push(d);
      keep.sourceEventIds.push(...fold.sourceEventIds);
      keep.importance = Math.max(keep.importance, fold.importance);
      fold.mergedInto = keep.id;
      merged.push([keep.id, fold.id]);
    }
  }
  state.episodes = state.episodes.filter((e) => !e.mergedInto);
  state.lastConsolidatedAt = now;
  return { merged };
}

// ---------- migration from the v0 memory.json ({fact, type?, at}) ----------
export function migrateV0(state, v0) {
  for (const m of v0 || []) {
    const at = Date.parse(m.at) || Date.now();
    if (m.type === "shared") {
      const ep = encodeEpisode(state, { gist: m.fact, importance: 0.8, arousal: 0.7, valence: 0.8, relationshipMeaning: 0.9,
        shared: true, topics: [], people: [], places: [], details: [] }, at, null);
      ep.occurredAt = at;
    } else {
      const f = learnFact(state, m.fact, at, null);
      f.encodedAt = at; f.lastConfirmedAt = at;
    }
  }
  return state;
}
