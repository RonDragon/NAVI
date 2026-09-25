# שפת העיצוב — NEXUS PET

> **Creature warm. System electric.**
> ה-Navi חם ואורגני. העולם שסביבו טכנולוגי וחשמלי.

מקורות:
- התייעצות עם GPT, שבחן שלושה כיוונים והמליץ על NEXUS PET.
- מחקר NotebookLM על 26 מקורות: ארכיון האמנות של Mega Man Battle Network, Star Force, ‏Meshy/Tripo/Hunyuan3D, ‏Filament, ‏React Three Fiber, וסרטוני YouTube על pipeline של 3D עם AI.

---

## 1. מה לוקחים מ-Battle Network, ומה לא

**הדקדוק, לא העיצוב.**

| לוקחים ✅ | לא לוקחים ❌ (IP של Capcom) |
|---|---|
| מכשיר אישי שבתוכו חי חבר דיגיטלי | הצללית של ה-PET, הקסדה והגוף של MegaMan |
| ניגוד בין העולם הפיזי לעולם הדיגיטלי | המילים PET, NetNavi, "Jack In!", ‏SciLab |
| grid ורשתות ניאון על רקע כהה | מסגרת Battle Chip, זירת 3×3 אדום/כחול |
| סמל אישי על החזה = זהות | Navi Marks רשמיים, דמויות, sprites, פונטים |
| פרופורציות אנימה: ראש, ידיים ורגליים גדולים, קריאים במסך קטן | סאונדים ומפות |
| **חוק "אין בד"**: דמויות סייבר בלי בגדים מתנופפים, רק חומר דיגיטלי אחיד | |
| מעבר "כניסה" עם wireframe וטבעות אור | |
| יכולות ככרטיסים/שבבים | |

מילים משלנו: **Link Up** (במקום Jack In), **Data Chips**, **Navi Space**.
"Navi" הוא שם עבודה. למוצר צריך שם משלו.

---

## 2. פלטה

```
Void Navy      #071522   background
Deep Grid      #0D2633   surfaces, grid
Electric Cyan  #18E0E8   system, Navi light seams
Signal Lime    #B8F23C   growth, success
Pulse Orange   #FF8A32   attention, upcoming event
Alert Coral    #FF5268   urgent (rare)
Ice White      #EAFBFF   text
```

## 3. טיפוגרפיה

- **Heebo** לעברית (UI וטקסט).
- **IBM Plex Mono** למספרים, שעות ו"טלמטריה".
- לא פונט פיקסלים לעברית. זה הורס את הקריאות.

## 4. ה-Navi עצמו

- **צורה:** chibi דו-רגלי. ראש גדול, ידיים ורגליים גדולות (כמו ב-MMBN), ותכונות יצור: אוזניים, זנב וקווי אור.
- **זהות:** סמל אישי על החזה. בעתיד הוא יוכל להשתנות לפי מה שחוויתם יחד.
- **חומר:** גוף חלק ואורגני עם 2–3 אלמנטים של "ביולוגיה דיגיטלית": קווי אור, ליבה זוהרת, אוזניים שמגיבות.
- **למה דו-רגלי:** ה-auto-rig של Meshy/Tripo עובד הכי טוב על דמויות דו-רגליות. זה גם קרוב לתחושת NetNavi, ועדיין לא אדם (אין uncanny valley).

## 5. תנועה

- מהירה ומעט "gamey": anticipation לפני קפיצה, ‏squash/stretch עדין, ‏afterimage דיגיטלי בריצה.
- אוזניים וזנב הם מערכת הבעה נפרדת: מקשיב, מופתע, עייף, שמח.
- כשאין אינטראקציה, ה-UI נסוג וה-Navi מקבל את הבמה.

### Link Up, פתיחת האפליקציה (~800ms)

```
0–100ms     haptic tick
100–250ms   horizontal scan line
250–450ms   grid lines converge to a point
450–650ms   Navi arrives as a data streak
650–800ms   Navi Space materializes
```

פתיחה חוזרת: ~300ms. אין intro של 3 שניות.

### שפת רטט (Haptics)

```
tap                ·
Navi notices       · ·
memory recalled    · — ·
important event    — —
growth moment      · — — ·
```

### סאונד

שלוש שכבות:
1. **Navi:** ציוצים, נשימות, תנועה.
2. **מערכת:** קליק, packet, חיבור.
3. **רגעי צמיחה:** צליל נדיר. אם הוא מתנגן כל יום, אין לו משמעות.

---

## 6. 3D — איך מייצרים את ה-Navi

```
concept art (GPT)  ──►  Meshy 6 image-to-3D  ──►  auto-rig + animations
   T-pose sheet            (or Tripo 3.1)           (idle, walk, jump,
                                                    wave, sleep, happy...)
                                │
                                ▼
                   Blender cleanup + gltfpack -cc -tc
                   GLB < ~100KB-1MB, 1024px textures
                                │
                                ▼
                        Android runtime
```

השוואת מחוללים (נתונים מ-200 יצירות, r/aigamedev):

| | Meshy 6 | Tripo 3.1 | Hunyuan3D-2 |
|---|---|---|---|
| מוכן לייצור | **78%** | 72% | 61% |
| rigging | מובנה, 600+ אנימציות | 7 סוגי שלד | אין |
| מהירות | בינונית | **~1 דקה** | 5–10 דקות |
| מחיר | בתשלום | **הכי זול** | חינם (קוד פתוח) |

טיפים:
- לייצר ב-**T-pose או A-pose**. הגפיים נפרדות, וה-rig יוצא נקי.
- טקסטורות 1024×1024.
- לתקן פנים/ידיים ב-Blender, או לחזור על היצירה.

### איפה ה-3D רץ באנדרואיד

| משטח | טכנולוגיה | הערה |
|---|---|---|
| **Navi Space** (האפליקציה) | React Native + React Three Fiber, או Filament | `frameloop="demand"`: לא מרנדרים כשהוא לא זז, כדי לחסוך סוללה |
| **Live Wallpaper** 🔥 | Filament (יש sample רשמי של live wallpaper) | ה-Navi חי על מסך הבית עצמו |
| **Widget** | תמונות 2D שמרונדרות מראש מהמודל | widgets לא תומכים ב-3D |
| **התראות** | דיוקן 2D של ה-Navi לפי מצב | |
| **Navi צף** (v0.2) | overlay קטן | בהסכמה מפורשת |

---

## 7. ה-PET המודרני

```
                    ANDROID PHONE
                         │
   ┌──────────────┬──────┴───────┬──────────────┐
LIVE WALLPAPER   WIDGET     NOTIFICATIONS       APP
Navi lives on   tiny Navi   Navi portrait   Navi Space (3D)
home screen     + next      + one line
                thing
   └──────────────┴──────┬───────┴──────────────┘
                     NAVI CORE (cloud)
```

**האפליקציה היא הבית שלו. אנדרואיד הוא העולם שהוא חי בו איתך.**
