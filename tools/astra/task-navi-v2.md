# Task for Astra: Navi v2 — "more alive, softer" pass

You are working inside `C:\CloudeRepo\NAVI`. Stay inside this folder. Do not install anything or use the network.
Blender 5.2: `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe` (headless: `--background --python`).

Start from your own v1 build: `tools/blender/build_navi.py`, report `docs/04-astra-build-report.md`,
renders `renders/navi-v1-*.png`, and the concept art `assets/concept/navi-front.png`, `navi-side.png`, `navi-back.png`.
Keep v1 files untouched; write v2 as new files.

## Art-direction review to address (from our design lead)
The v1 keeps the DNA well (ears, palette, eyes, chest core, tail, light seams) but reads **more robotic and less polished than the concept**.
Fix in this order:
1. **Face polish (the main blocker).** One soft, round muzzle/cheek mass like the concept. Fewer seams and hard joins around eyes–cheeks–mouth.
   The mouth must be real geometry, not look painted on. Clean, real **eyelids** for Blink (no retracting eyes).
2. **Eyes 8–12% smaller** (area), head size unchanged — less toy/mascot, more creature partner; leave room for brows/lids to act.
3. **Hands and forearms 10–15% bigger**, a bit more forearm volume (chibi action-character silhouette).
4. **Chest core integrated** into the torso design: a small frame/panel and a light line flowing from it into the body — not a pendant stuck on.
5. **Tail**: slightly thicker base, stronger taper, smoother deformation across the 4 bones (it should feel like an emotional limb, not a rigid prop).
6. **Sleep must change the silhouette**: curled — sitting or lying, low center of gravity, ears limp, tail wrapped close to the body, slow breathing.
7. **Do NOT add more armor/tech details.** This pass adds life and softness. "Creature warm. System electric."

## New content for "idle life" and reactions
Add these actions (30 fps) in addition to v1's `Idle, Wave, HappyJump, TailWag, Listen, Sleep` (keep those names; improve Sleep as above):
- `Notice` — mid-activity he notices the Operator: head turns to camera, ears perk, small step toward camera (2 s, one-shot).
- `Stretch` — big cute stretch, arms up, tail up (3 s, one-shot).
- `Inspect` — crouches and studies something on the floor grid, head tilts, ear twitch (4 s, loop).
- `Celebrate` — bigger than HappyJump: bounce, arms up, tail going wild (2.5 s, one-shot).
- `Concerned` — ears lowered, hands close to chest, slight lean toward camera (3 s, loop).
New shape keys in addition to `Blink, Happy, MouthOpen`: `Surprised` (eyes/lids wide, brows up), `Sad` (brows/lids down, mouth corners down).

## Hard compatibility rules (the app depends on these)
- Same armature name `NaviRig` and the same 27 bone names; tail and ear weight rules from v1 still hold (tail verts only on Tail bones, ear verts only on Ear bones + Head).
- 1.0 m tall, facing -Y, feet on Z=0, ~10k–18k triangles, same material names (`Navi_Glow` stays the emissive material).
- Export `assets/models/navi-v2.glb` (all actions as separate animations, all shape keys) and save `assets/models/navi-v2.blend`.

## QA (mandatory)
Render turnarounds `renders/navi-v2-{front,side,back,threequarter}.png` and one frame of each new/changed action
`renders/navi-v2-{sleep,notice,stretch,inspect,celebrate,concerned}.png`, plus `renders/navi-v2-{surprised,sad,blink}.png`.
Put v1 and v2 side by side against the concept and iterate at least twice on the face. Validate the GLB round-trip like v1.
Write `docs/05-astra-v2-report.md`: what changed vs v1 (with numbers), bone/weight report, new actions and shape keys, known issues.
