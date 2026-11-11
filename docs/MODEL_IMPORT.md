# Importing a Real Lumi Model

How to take a Blender-made Lumi and get it into the application without touching
code. Read `docs/CHARACTER_SPEC.md` and `docs/RIG_AND_ANIMATION.md` first — this
is the mechanical procedure for those documents.

**No Lumi model exists yet.** Following this guide is what makes one usable; it is
not evidence that one exists.

---

## 1. Before you start

Install Blender 4.x. The glTF exporter is built in; no add-on needed.

You need: the reference boards, the palette from `CHARACTER_SPEC.md`, and the bone
list from `RIG_AND_ANIMATION.md`.

## 2. Scene setup

1. Delete the default cube, camera and light — the app supplies its own light.
2. `Scene Properties → Units`: Metric, scale 1.0.
3. Build Lumi facing **−Y in Blender** (the exporter converts to −Z for glTF).
4. Origin between the front hooves, on the ground plane (`Z = 0` in Blender).
5. Target height: **0.30 m** for the finished character.
6. Apply all transforms before export: `Ctrl+A → All Transforms`.

## 3. Rigging

1. Name the armature object `Lumi_Rig`.
2. Create bones with exactly the names in `RIG_AND_ANIMATION.md`. Use `_L`/`_R`
   for the character's own sides.
3. Parent the mesh with automatic weights, then fix by hand:
   - no vertex with more than 4 influences,
   - no unweighted vertices (they will not move with the body),
   - wings, mane and tail need real weight gradients, not rigid assignment.
4. Use `Armature → Pose Mode` to check that `Head`, `Wing_L/R`, `Tail1-4` and the
   legs all deform cleanly.

## 4. Animation

1. One Action per clip, named exactly: `idle`, `blink`, `walk`, `run`, `fly`,
   `sleep`, `yawn`, `happy`, `pet_reaction`, `play_ball` (required), plus optional
   clips if you have them.
2. Locomotion is **in place** — the app moves the character.
3. Looping clips must end on their starting pose, otherwise the wrap pops.
4. Push each Action to an NLA strip if Blender needs it to export, but export
   **one glTF animation per clip name**. Duplicated or suffixed names
   (`walk.001`) are rejected.

## 5. Materials

Follow the material table in `CHARACTER_SPEC.md`: PBR metallic-roughness, coat
`#EFE6FF`, gold metal 1.0 / rough 0.25, emissive cyan for the horn tip and emblem.
No baked lighting into textures. Textures ≤ 2048².

## 6. Export

`File → Export → glTF 2.0 (.glb)`:

| Setting | Value |
|---|---|
| Format | `glTF Binary (.glb)` |
| Include | Selected objects only (armature + mesh) |
| Transform | `+Y Up` **on** |
| Data | Apply Modifiers on, Cameras off, Lights off |
| Animation | `Actions`, one animation per action, sampling on, `Optimize Animation Size` off |
| Skinning | Export all influences (4) |
| Compression | Draco off (the app reads uncompressed GLB) |

Save to `assets/models/lumi.glb`.

## 7. Validate before importing into the app

```powershell
python tools\validate_glb.py assets\models\lumi.glb --json docs\lumi_asset_report.json --strict
```

Read the output. Common failures and what they mean:

| Code | Meaning | Fix |
|---|---|---|
| `BONE001` | no skin | the mesh was exported without the armature |
| `BONE002` | required bones missing | bone names are wrong or bones were not exported |
| `BONE004` | wrong parent | a bone is attached to the wrong parent |
| `CLIP001` | required clips missing | action names do not match the table, or actions were not exported |
| `CLIP002` | unknown clip | a name has a suffix like `.001` |
| `MAT003` | colour far from palette | material was recoloured, or a texture is doing the colour |
| `CONTENT001` | looks like a platform | a base/pedestal node was exported |
| `SCALE001` | model is metres too large | transforms were not applied, or the scene scale is wrong |

Zero errors and zero warnings with `--strict` is the acceptance bar.

## 8. What happens in the application

The app does not need to know the file changed:

1. `ClipLibrary` is built from the GLB's animation names.
2. The behaviour machine requests logical clips (`pet_reaction`, `play_ball`, ...).
3. The animation layer resolves each request against the real clip list, using the
   fallback table when something is missing.
4. If no model is present at all, the procedural fallback still animates breathing
   and blinking, and the UI must say the model is a placeholder.

## 9. Placeholder policy

Until a validated GLB exists at `assets/models/lumi.glb`:

- The only 3D geometry in the project is the M0 debug cube, which is **not** a pony
  and is never shown as Lumi.
- No screenshot, icon or store listing may present the placeholder as the
  finished character.
- The README stays explicit that the character is unmodelled.

## 10. When the real model lands

Record in the commit message: which validator command was run, its verdict, and
the Blender version used. Attach the front/back/side/three-quarter renders so the
identity check in `CHARACTER_SPEC.md` §9 can actually be reviewed.
