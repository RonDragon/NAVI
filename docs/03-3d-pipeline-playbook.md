# Playbook: מתמונה ל-Navi תלת-ממדי מונפש

מקור: מחקר NotebookLM על 31 מקורות:
- 8 סרטוני YouTube (Meshy rigging/animation 2026, Claude Code + Three.js, ‏character configurator ב-R3F ועוד).
- המדריכים הרשמיים של Meshy (image-to-3D, ‏auto-rigging, ‏retopology, ‏Godot).
- ‏pipeline של Meshy → Blender → RetopoFlow → Auto-Rig Pro.
- מדריכים כלליים לבניית משחקי 3D עם AI (Summer Engine, ‏Tripo, ‏Reallusion, ‏Wavect).
- מחקר על texturing, ‏toon shader ו-emissive glow.

---

## 0. העיקרון

**AI מקצר את ה-pipeline משבועות לדקות, אבל לא יודע אם זה "מרגיש חי".**
- **AI טוב ב:** mesh בסיסי, טקסטורות PBR, ‏rig של שלד דו-רגלי, ‏presets של אנימציה, וכתיבת קוד הסצנה.
- **AI נכשל ב:** topology במפרקים של דמות ראשית, ‏rig לא-סטנדרטי (אוזניים, זנב, כנפיים), עקביות של פנים ועיניים בין הרצות, ושיפוט של "כיף" ו"חי".
- **לכן:** בדיקה אנושית אחרי כל שלב, ותנועה משנית (אוזניים, זנב, מבט) בקוד שלנו.

---

## 1. תמונת הקלט

| כלל | למה |
|---|---|
| **Multi-view:** תמונה נפרדת מלפנים, ב-45° ומהצד (ואחורה אם אפשר) | בלי זה ה-AI מנחש את הגב, ומאבד את סמל החזה והדפוסים |
| רקע **לבן אחיד** או PNG שקוף, בלי צללים | צל נראה ל-AI כמו גיאומטריה |
| הדמות ממלאת את הפריים | יותר פיקסלים = יותר פרטים |
| ≥1024×1024, ‏מומלץ 2048 | |
| **T-pose/A-pose**: ידיים רחוקות מהגוף, אצבעות פרושות, רגליים מעט מפוסקות | אחרת הגפיים "מתאחות" ולא מתכופפות |
| זנב ואוזניים **לא נוגעים** בגוף או זה בזה | גיאומטריה שנוגעת הופכת לגוש אחד |
| בלי טקסט, פלטה, שורות הבעה, בגדים מתנופפים, אביזרים | |

⚠️ ה-character sheet הראשון מ-GPT לא עומד בכללים: רקע אפור, תוויות ושורת הבעות. צריך לחתוך או לייצר מחדש.

## 2. הגדרות Meshy

- **מודל:** הכי חדש (Meshy 6/7).
- **Topology:** ‏**Quad**, או Smart Topology. אחרי Standard מריצים Remesh. ‏Quad חובה בשביל כיפוף נקי במפרקים.
- **Polycount למובייל:** ‏**8,000–10,000**. מעל 300K ה-auto-rig דוחה.
- **Symmetry:** ‏**on**.
- **Pose mode:** ‏**T-pose**.
- **API:** ‏`POST /v1/multi-image-to-3d` (1–4 תמונות), `topology: "quad"`, `target_polycount: 10000`, `symmetry_mode: "on"`.

## 3. צביעה (Texturing)

- **AI Texturing עם PBR.** אם הגיאומטריה טובה אבל הצבעים לא, עושים **Retexture** עם prompt. זה לא בונה את המודל מחדש וחוסך קרדיטים.
  ```
  stylized chibi creature, dark navy body, white/ice face and belly,
  glowing cyan light lines, cyan chest emblem, clean toon look
  ```
- **קווי האור הזוהרים:** מפת **emissive כמסכה אפור-לבן** (שחור = לא זוהר, לבן = זוהר). לא לאפות בהירות לתוך הצבע. את העוצמה, הגוון וה-bloom שולטים בזמן ריצה, באפליקציה.
- **פנים ועיניים מרוחות:** סגנון toon מקטין את הבעיה. אם צריך, מתקנים ב-Blender (Data Transfer לנורמלים, ‏Ctrl+N).
- **רזולוציה:** ‏2K לדמות הראשית. אחרי הדחיסה יורדים ל-1K באנדרואיד.

## 4. Rigging

- **סוג:** Humanoid.
- **מיקום:** מרכז ב-(0,0,0), פנים קדימה, כפות רגליים על Y=0.
- **8 סמנים:** ראש, סנטר/צוואר, כתפיים, מרפקים, פרקי ידיים, אגן, ברכיים, קרסוליים.
- **אוזניים וזנב:** ה-auto-rig הרגיל מחבר רק גפיים ועמוד שדרה. שלוש אפשרויות:
  - A. ‏**Smart Rig (Beta)** של Meshy.
  - B. ‏Blender: להוסיף שרשרת עצמות לאוזניים ולזנב, עם weight painting.
  - C. ‏**בקוד (מה שנעשה):** spring/sine על עצמות או על קבוצות vertices. זה גם נותן תנועה חיה שמגיבה לרגש.

| תקלה | סיבה | תיקון |
|---|---|---|
| כתפיים/אגן קורסים | הדמות נוצרה בתנוחה כפופה | לייצר מחדש ב-T-pose |
| צד אחד נשבר | גיאומטריה לא סימטרית | ‏symmetry on / "symmetrical" |
| קריעה במפרקים | משולשים מבולגנים | ‏Quad Remesh לפני rig |
| גפה זזה כגוש | mesh נוגע בעצמו | "arms away from body, fingers spread" |
| מרחף או שוקע | root offset | רגליים על Y=0 לפני rig |

## 5. אנימציות ל-Navi

סט ראשון: **Idle** (נשימה), ‏**Wave**, ‏**Happy jump**, ‏**Sleep**, ‏**Listening / head tilt**, ‏**Walk**.
- לבדוק קודם clips עדינים, כדי לוודא שה-rig תקין.
- **Smooth Loop** ל-idle ול-walk (blend של ~10 פריימים).
- יצוא: Download → Animation → All Added → **Single File**. ‏GLB אחד עם mesh, חומרים, שלד וכל ה-clips.

## 6. יצוא ודחיסה

```bash
npx @gltf-transform/cli optimize navi.glb navi.min.glb \
  --compress meshopt --texture-compress webp --texture-size 1024
# or: gltfpack -i navi.glb -o navi.min.glb -cc -tc
```
יעד: **2–5MB** לכל הדמות עם האנימציות.

## 7. באפליקציה (React Three Fiber)

```tsx
const { scene, animations } = useGLTF('/models/navi.min.glb');
const { actions } = useAnimations(animations, scene);
// crossfade
actions.Idle?.fadeOut(0.3); actions.Happy?.reset().fadeIn(0.3).play();
```

התוספות שעושות אותו חי (ב-`useFrame`):
- **מבט:** slerp של עצם הראש/צוואר לכיוון המגע או המצלמה.
- **מצמוץ:** morph target, או shader על העיניים, בזמנים אקראיים.
- **אוזניים וזנב:** spring physics / sine. ה-Emotion Engine שולט באמפליטודה.
- **מראה:** cel/toon shader (smoothstep על `dot(N,L)` + rim light) ו-**selective bloom** על ה-emissive.
- **סוללה:** `frameloop="demand"` כשהוא לא זז.

## 8. ה-workflow המלא

```
1. one-sentence character brief
2. turnaround concept art (GPT) — clean T-pose, white bg, per-view images
3. Meshy multi-image-to-3D — quad, ~10k, symmetry on, T-pose
4. AI texture (PBR + emissive mask) → retexture if needed
5. auto-rig humanoid → stack animations → single GLB
6. gltf-transform optimize
7. R3F: mixer + cel shader + bloom + procedural ears/tail/look-at
8. human review: does he feel alive? → iterate
```
