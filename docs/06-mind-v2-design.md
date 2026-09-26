# המוח של ה-Navi, גרסה 2: רגש, זיכרון ומוח מקומי

> **"LLM observes/proposes. Core decides."**
> המודל מתאר מה קרה. הקוד מחליט מה ה-Navi מרגיש, מה הוא זוכר, ומי הוא נהיה.

מקורות:
- תכנון עם GPT (26.9.2026).
- מחקר NotebookLM על 30 מקורות: Scherer CPM, ‏OCC, ‏EMA/FAtiMA, ‏PAD, ‏Generative Agents, ‏MemoryBank/A-MEM, ‏ExecuTorch, ‏llama.cpp, ‏MediaPipe ועוד.

"אנושי" כאן = עומק רגשי וזיכרון טבעי. **הוא עדיין יצור, לא בן אדם**, וכל כללי ה-Bible נשארים: אין מניפולציה רגשית, אין אשמה, אין בלעדיות.

---

## איפה אנחנו היום, ומה מחליפים

| היום (קיצורי דרך) | גרסה 2 |
|---|---|
| האישיות היא prompt | טמפרמנט + תכונות מפותחות, כפרמטרים שמשנים appraisal |
| ה-LLM בוחר `mood: happy` | Appraisal → וקטור רגשות → mood (PAD) → ויסות → גוף וקול |
| עובדות + 12 הודעות אחרונות | זיכרון עבודה, אפיזודי, סמנטי ופרוצדורלי, עם חוזק, שכחה ושליפה חלקית |
| כל תשובה בענן (~9 שנ') | שכבות: דטרמיניסטי → LLM מקומי → ענן |

---

## 1. רגשות ואישיות: Affective Core

```
EVENT → APPRAISAL → EMOTIONAL IMPULSES → EMOTION STATE → MOOD (PAD) → REGULATION
      → ACTION TENDENCIES → BODY / VOICE / BEHAVIOUR → the LLM verbalizes it
```

### Appraisal: ה-LLM מחלץ, הקוד מחשב
היברידי של Scherer ו-OCC. המחקר תומך ב-Scherer: ממדי appraisal רציפים יציבים יותר מתוויות רגש בדידות.
```ts
interface Appraisal {
  novelty: number;              // 0..1
  pleasantness: number;         // -1..1
  goalRelevance: number;        // 0..1
  goalCongruence: number;       // -1..1
  agency: "operator" | "navi" | "other" | "circumstance";
  controllability: number;      // 0..1
  certainty: number;            // 0..1
  normCompatibility: number;    // -1..1
  relationshipRelevance: number;// 0..1
  expectedness: number;         // 0..1
  copingPotential: number;      // 0..1
}
```

### רגש = וקטור, לא תווית
```ts
type Emotion = "joy" | "sadness" | "fear" | "anger" | "relief" | "pride" | "disappointment"
             | "concern" | "curiosity" | "excitement" | "affection";
interface ActiveEmotion { type: Emotion; intensity: number; target?: string; causeEventId: string;
                          onsetAt: number; halfLifeMs: number; }
interface EmotionalState { active: ActiveEmotion[]; mood: PAD; }
```
- **דוגמה:** הצלחה של ה-Operator מייצרת `joy .74, pride .48, excitement .61, affection .39`, ולא "happy".
- **מיפוי appraisal לרגשות:** מרחק משוקלל לאב-טיפוס של כל רגש, לפי המחקר (Scherer):
  - $A_k = \max(0, 1 - d_k/d_{max})$.
  - משקלות: pleasantness ‏9.7, ‏urgency ‏7.9, ‏goal ‏7.7.
- **רגשות מעורבים:** אם שני הרגשות הקרובים ביותר קרובים זה לזה (פער קטן מ-0.15), שניהם פעילים. למשל חשש ותקווה יחד.

### Mood ≠ Emotion
הרגש הוא גל, וה-mood הוא הים שמתחתיו. ‏PAD = ‏Pleasure / Arousal / Dominance, כל אחד בטווח ‎-1..1.
```ts
moodNext = mood + emotionContribution * 0.08 - (mood - baselineMood) * decay;
// NotebookLM: exponential return to baseline, λ ≈ 0.15/hour (half-life ≈ 4.6h)
```

### טמפרמנט ואישיות: "צמיגה"
```ts
interface Personality {
  temperament: { noveltySeeking; threatSensitivity; rewardSensitivity; sociability;
                 persistence; emotionalReactivity; recoveryRate; autonomy };   // almost fixed
  developedTraits: { boldness; patience; playfulness; openness; cooperativeness; selfControl }; // slow
}
```
- **הטמפרמנט משנה את ה-appraisal.** אותו אירוע ("רעש לא מוכר") פוגש שני Navi שונים:
  - noveltySeeking .85 → curiosity .68.
  - threatSensitivity .78 → concern .52.
  - אותו עולם, מוח אחר.
- **ה-baseline של ה-mood** נגזר מהטמפרמנט.
- **שינוי אישיות רק מ-`TraitEvidence` חוזר:** למשל 20 ומעלה אירועים עצמאיים לאורך שבועות מזיזים boldness ב-‎+0.02. אף פעם לא "‎+0.1 אחרי קרב".

### ויסות רגשי: כללים, לא LLM
```ts
interface RegulationProfile { recoveryRate; reappraisalBias; suppressionBias;
                              socialSoothingSensitivity; distractionEffectiveness; }
```
דוגמה: הפסד מביא ל-disappointment ‎.72. ה-Operator אומר "היינו ממש קרובים", וכשה-trust גבוה, disappointment יורד ל-‎.46 ו-affection עולה ל-‎.34.

### גוף וקול: Expression Resolver
```ts
interface EmbodimentState { posture; movementEnergy; proximityDrive; gazeIntensity; earTension;
  tailAmplitude; tailSpeed; blinkRate; voice: { pitchDelta; speed; volume; pauseRate }; animationBiases: string[] }
```
כך שני Navi "שמחים" לא עושים את אותה אנימציה. (שכבת הרפלקסים שבנינו היא גרסה ראשונה של זה.)

### Relational coping (מהמחקר, עם כללי ה-Bible)
במצוקה של ה-Operator:
- להיות לצידו.
- לא להסכים עם פרשנות הרסנית.
- לעודד קשר עם אנשים אמיתיים.
- לבנות אצלו מסוגלות, כדי שיזדקק ל-Navi **פחות** עם הזמן.

---

## 2. זיכרון כמו של בני אדם: MemoryEngine

### ארבע שכבות
```ts
interface EpisodicMemory {
  id; occurredAt; gist: string;               // what he mainly remembers
  details: { value: string; salience: number; confidence: number }[];  // fade separately
  people: string[]; places: string[]; topics: string[];
  importance; emotionalArousal; emotionalValence; relationshipMeaning;
  encodingStrength; retrievalCount; lastRecalledAt?; lastReconsolidatedAt?;
  sourceEventIds: string[]; confidence;
}
interface SemanticMemory   { id; proposition: string; confidence; evidenceIds: string[]; lastConfirmedAt }
interface ProceduralMemory { id; context: string[]; behavior: string; strength; evidenceIds: string[] }
// + working memory: the live conversation, its goal, entities, not-yet-consolidated items
```

### חוזק ושכחה
**GPT נרמל את הנוסחה מהמחקר:**

$$S = 1 + 2\ln(1+\text{successfulRecalls}) + 3I + 1.5E + 1.5C \qquad R = e^{-\Delta t/(\tau S)}$$

- **I** = חשיבות, **E** = עוצמה רגשית, **C** = אישור/ראיות. כולם בטווח 0..1.
- **τ** תלוי בסוג הזיכרון: עובדה סמנטית יציבה יותר מפרט אקראי.
- **R לא אומר אם הרשומה קיימת,** אלא כמה בקלות ה-Navi נזכר בה באופן טבעי. הרשומה עצמה נשארת.
- **מהמחקר:** מידע לא מאומת דועך עד פי 3 מהר יותר.

### שליפה: "להיזכר", לא "לחפש"
```
activation = 1.2·cueRelevance + 0.8·moodCongruence + 0.8·retention + 0.7·importance
           + 0.6·relationshipRelevance + 0.4·recentPriming + noise
```
```
situation → retrieval cues (person/topic/place/time/emotion/goal) → keyword+vector candidates
          → activation scoring → threshold → recall | no recall
```
- **ה-vector DB** אומר מה *עשוי* להיות קשור. **ה-MemoryEngine** מחליט אם ה-Navi באמת נזכר.
- **רעש קטן:** אחרת אותה שאלה מחזירה תמיד את אותם חמישה זיכרונות, וזה מרגיש כמו מנוע חיפוש.

### זיכרון חלקי
לכל פרט יש retention משלו. ‏ה-LLM מקבל:
```json
{ "recall": { "gist": "Operator had an important job interview", "confidence": 0.91,
  "details": { "company": { "value": "Acme", "confidence": 0.43 }, "day": { "value": "Thursday", "confidence": 0.28 } } } }
```
- **כלל:** אסור להציג פרט חלש כעובדה.
- **התוצאה הטבעית:** "נדמה לי...", "זה היה ביום חמישי?", או פשוט השמטת הפרט.
- **חריג:** דברים שביקשת במפורש שיזכור (תזכורות) לא נשכחים. זו יכולת, לא זיכרון ביולוגי.

### Reconsolidation: כאן GPT חולק על המחקר ⚠️
- **המחקר הציע:** כל שליפה מאפסת את Δt.
- **GPT:** קריאה פנימית מה-DB היא **לא** היזכרות, ולכן:
  - שליפה פנימית לא מחזקת.
  - שימוש מודע בתשובה נחשב successful recall.
  - דיון, תיקון או עוררות רגשית מחדש מביאים ל-reconsolidation.
- **Reconsolidation לא משכתב.** הוא יוצר `MemoryRevision`, והמקור נשמר. כך "לא, זה היה ביום שישי" לא מוחק את ההיסטוריה.
- **ההחלטה שלנו: הגרסה של GPT.**

### Consolidation
- **"שינה" (לילה / off-screen):** אירועים → אפיזודות → אשכולות → gist → מועמדים סמנטיים ופרוצדורליים → בדיקת סתירות → עדכון חוזק.
- **אירוע גדול לא מחכה ללילה:** "קיבלתי את העבודה!" הופך מיד לאפיזודה עמידה ולזיכרון משותף. זה כבר קורה אצלנו ב-follow-ups.
- **מהמחקר (שלב מאוחר, אופציונלי):** ‏NREM (חיזוק Hebbian וצמצום רעש) ו-REM (הליכה אקראית על גרף אסוציאציות). קישורים חדשים, "חלומות", שאפשר לספר עליהם.

### זיכרון ⇄ רגש (מעגל)
- **אירוע רגשי חזק מעלה את חוזק הקידוד.**
- **ה-mood משפיע מעט על השליפה** (התאמה רגשית).
- **שליפה מעוררת מחדש רגש,** חלש מהמקור.

---

## 3. מוח מקומי בטלפון + חלוקה היברידית

### מה מקומי **בלי LLM בכלל** (דטרמיניסטי, מיידי)
- רפלקסים, חשבון ה-appraisal, PAD ודעיכת רגשות.
- אישיות, מצב הקשר, agency, ‏off-screen life.
- הפעלת זיכרונות, ה-follow-up scheduler, סינון פרטיות.

### מה ה-LLM המקומי הקטן עושה
- זיהוי כוונה וישויות, וחילוץ מועמדים לזיכרון.
- "כן / לא / רגע" ותגובות חברתיות קצרות, שיחה פשוטה.
- ניסוח לפי ה-CommunicationEnvelope, ומצב offline.
- **דוגמה:** "מתי הראיון שלי?" לא צריך ענן בכלל.

### מה עולה לענן
חשיבה קשה, ייעוץ עמוק, תכנון, מחקר וקוד. הענן מקבל זהות, רגש, אישיות, קשר, זיכרונות נבחרים ומשימה, ומחזיר **תכנית תשובה**. השכבה המקומית יכולה לעשות את הניסוח הסופי, כך שהחלפת ספק ענן כמעט לא משנה את האישיות.

### פתרון 9 השניות
```
0–150ms   reflex (already built)
150–400ms local appraisal + memory cues
300–800ms local intent + acknowledgement ("אה...", "רגע.", "כן, אני זוכר.")
simple? ── yes → local response (sub-second / few seconds)
        └─ no  → cloud starts concurrently → stream answer
```
**ה-Navi Core מחזיק את האמת.** ה-LLM המקומי וה-LLM בענן הם "disposable cognition", ואפשר להחליף אותם בלי להחליף את ה-Navi.

### מודלים ו-frameworks
- **GPT:** אל תבחרו עכשיו. עשו **bake-off על הטלפון שלך**. שלושה מועמדים:
  - Qwen קטן (multilingual, ‏JSON).
  - Gemma 3n (בנוי במיוחד לנייד).
  - Llama 3.2 1B/3B (baseline עם tooling בוגר).
- **Framework ראשון:** ExecuTorch (AAR ל-Kotlin, ‏mmap, runtime ל-LLM). ‏llama.cpp להשוואה.
- **המחקר:**
  - 1–3B ב-INT4: בערך 15–50 tokens/s, ‏1–2GB RAM.
  - ‏ExecuTorch על NPU של Snapdragon: חסכוני פי 4–12 באנרגיה.
  - ⚠️ **חלק מהמספרים ושמות מסוימים מהמחקר לא אומתו** (למשל "Hebatron", "Qwen 3.5", "HybridInferenceApi"). מתייחסים אליהם כהשערות עד שה-bake-off יוכיח.
- **עברית:**
  - לא ברור איזה מודל קטן טוב בה. חייבים benchmark משלנו.
  - המחקר מציין בעיית tokenizer: מודלים כלליים מפרקים מילה עברית להרבה tokens, והרחבות כמו DictaLM משפרות.
- **במדידה (100–200 prompts בעברית מתוך ה-Navi):** איכות עברית, זהות Navi, תקינות JSON, זמן לטוקן ראשון, tokens/sec, ‏RAM, סוללה, חום אחרי 10 דקות, גודל.

---

## תכנית שלבים (מוסכמת)

| שלב | מה | למה |
|---|---|---|
| **1 — ✅ בוצע** | **MemoryEngine v1 ב-Node**: working, episodic, semantic, procedural; ‏cues; ‏activation; זיכרון חלקי; consolidation; ‏reconsolidation ב-revisions. עם בדיקות | "המערכת הזו תשנה בפועל מי ה-Navi נהיה." משפיע יותר מהחלפת מודל |
| **2 — ✅ בוצע** | חיבור רגש וזיכרון: חוזק קידוד רגשי, ‏mood congruence, רגש שמתעורר בהיזכרות | המעגל חוויה → רגש → זיכרון → appraisal |
| **3 — ✅ בוצע** | הוצאת החלטות מה-LLM: הוא מחזיר appraisal observations, וה-Emotion Engine מחליט | "LLM observes. Core decides." |
| 4 | מעטפת אנדרואיד (עם מוח בשרת) | |
| 5 | Local Brain bake-off על הטלפון שלך | בחירת מודל ו-runtime לפי מדידה, לא לפי אינטרנט |
| 6 | Hybrid Router: ‏deterministic, ‏local_fast או cloud | היעד: התגובה המהירה והפרטית ביותר שעדיין חכמה מספיק |

### מה נבנה בשלבים 2 ו-3
- `brain/affect/engine.mjs` (Affective Core v1): appraisal בן 12 שדות מה-LLM. טמפרמנט שמטה את הקריאה. וקטור של 11 רגשות עם half-life. ‏PAD mood שחוזר ל-baseline (λ≈0.15 לשעה). ויסות (תמיכת ה-Operator מרככת). ‏embodiment: אנימציה, פנים, זוהר וקול. ‏TraitEvidence צמיג (20+ עדויות, צעד של 0.02).
- חיבור לזיכרון: חוויה נשמרת עם הרגש של פיקסל ברגע הקידוד (60% core, ‏40% הקריאה של המודל). ‏recall לפי ה-valence הנוכחי. זיכרון שנעשה בו שימוש מעורר הד חלש של הרגש (evoke).
- בדיקות: `node --test brain/affect/engine.test.mjs` (9), ‏`node brain/test-affect-live.mjs` (8, בתיקייה זמנית).

### בדיקות ל-MemoryEngine (מ-GPT)
- זוכר את ה-gist אבל שכח פרט.
- רמז מעלה זיכרון ישן.
- mood congruence משנה את הדירוג.
- תיקון של המשתמש לא מוחק provenance.
- שליפה מה-DB לבדה לא מחזקת זיכרון.
