# Task for Astra: build Navi v1 in Blender

You are working inside `C:\CloudeRepo\NAVI`. Stay inside this folder.
Blender 5.2 is at `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe` — drive it headless with
`blender --background --python <script> -- <args>` and write all scripts under `tools/blender/`.

## Goal
Model, texture/shade, rig and animate the companion character "Navi" so it matches the concept art:
- `assets/concept/navi-front.png`, `assets/concept/navi-side.png`, `assets/concept/navi-back.png`
  (look at these images carefully before you start, and again every time you compare renders).

Character: stylized chibi bipedal fox-like cyber creature. Huge ears (dark navy outside, glowing cyan/blue inside, cream rims),
spiky navy hair tuft with a cyan streak, big glossy dark-blue eyes with white highlights, small black nose, cream face mask and cheeks,
cream belly, navy body, cyan diamond/star emblem on the chest, glowing cyan orbs on the back of the wrists, cyan light seams on arms,
legs and a vertical line down the back with a ring between the shoulder blades, chunky navy boots with cream toes and cyan trim,
a fluffy tail with blue→cyan gradient tip. Style: clean toon / stylized 3D game character (think high-quality mobile game), not realistic.
Design rule from our visual bible: "Creature warm. System electric." Do NOT make it look like MegaMan or any existing character.

## Hard requirements
1. **Geometry**: clean, mostly-quad topology, symmetric (mirror modifier then apply), ~8k–15k triangles total.
   T-pose (arms horizontal, fingers slightly spread), feet slightly apart, facing **-Y** in Blender, feet on **Z=0**, total height **1.0 m**.
   Tail and ears must NOT touch the body/legs. Separate meshes are fine for eyes and emblem, but keep the count small.
2. **Materials** (glTF-exportable Principled BSDF only): `Navi_Navy` (#10183A-ish), `Navi_Cream` (#F1E9DC-ish),
   `Navi_Glow` (cyan #18E0E8 with **emission** — this is our emissive mask for bloom in the app), `Navi_Eye`, `Navi_EyeHighlight`, `Navi_Nose`.
   Use vertex colors or simple UV + small generated textures only if needed; prefer material slots.
3. **Face**: shape keys `Blink` (eyes close), `Happy` (smile / squint), `MouthOpen`. Name them exactly.
4. **Armature** named `NaviRig`: humanoid chain `Hips, Spine, Chest, Neck, Head, Shoulder.L/R, UpperArm.L/R, LowerArm.L/R, Hand.L/R,
   UpperLeg.L/R, LowerLeg.L/R, Foot.L/R` **plus** `Tail.1–Tail.4` (chain from Hips backwards) **plus** `Ear.L.1, Ear.L.2, Ear.R.1, Ear.R.2`.
   Skin with automatic weights, then **verify and fix**: tail vertices weighted ONLY to Tail bones, ear vertices ONLY to Ear bones + Head,
   no leg weights on the tail. Print a weight report.
5. **Animations** (Actions, 30 fps, looping where noted): `Idle` (breathing, subtle ear/tail sway, loop), `Wave` (right hand),
   `HappyJump`, `TailWag` (loop), `Listen` (head tilt + ears perk), `Sleep` (curled/slumped, loop).
6. **Export**: `assets/models/navi-v1.glb` (mesh + materials + skin + shape keys + all actions as separate animations, +Y up) and
   save the working file `assets/models/navi-v1.blend`.
7. **QA loop (mandatory)**: render front / side / back / 3-4 views (Eevee or Workbench, flat studio light, dark background) to
   `renders/navi-v1-*.png`, compare with the concept images, and iterate on shape/colors/proportions at least 3 times until it clearly
   reads as the same character. Also render one frame from the middle of `Wave` and `TailWag` to prove the rig deforms correctly
   (no tearing, tail moves independently of legs).
8. **Report**: write `docs/04-astra-build-report.md` — what you built, poly count, bone list, weight report summary, animation list,
   known issues and what you'd improve next. Keep all build scripts so the model is reproducible.

Work autonomously until everything above is done. Do not install anything, do not use the network, do not touch files outside this folder.
