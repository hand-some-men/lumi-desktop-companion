# Lumi — Character Asset Specification

**Status: specification only. No 3D model of Lumi exists.**
Everything here is derived from the three supplied reference boards (hero shot,
360° board, pose/expression sheet). It describes what must be built and how it
will be checked — not what has been built.

Machine-readable companion: `src/lumi/character/rig_contract.py`
Validation: `python tools/validate_glb.py assets/models/lumi.glb`

---

## 1. Identity lock

Lumi is a stylised unicorn-pegasus (alicorn) with chibi proportions. These
properties are load-bearing for recognition and must not change:

1. **Oversized head** — roughly 45% of total height; the face is the focal point.
2. **Spiral bicone horn**, gold at the base with a cyan-lit tip.
3. **Two layered feathered wings**, purple-to-white with gold edging, about as
   long as the body when folded out.
4. **Layered rainbow mane** (purple/blue/pink) flowing to the character's left,
   plus a long spiral tail of the same gradient.
5. **Large violet eyes** with a bright iris gradient, highlight spec and thick
   lashes; pink inner ears; pink cheek marks.
6. **Gold accessories**: forehead crown with a blue diamond, hoof caps, collar
   V-trim, cuffs.
7. **Purple chest plate** with cyan trim and the diamond/monogram emblem.
8. **Lavender-white coat** with soft shading — never pure white, never grey.

## 2. Palette

| Role | Hex | Linear floats (glTF `baseColorFactor`) |
|---|---|---|
| Coat | `#EFE6FF` | 0.937, 0.902, 1.000 |
| Mane purple | `#B64BFF` | 0.714, 0.294, 1.000 |
| Mane blue | `#4EC8FF` | 0.306, 0.784, 1.000 |
| Mane pink | `#FF6EC7` | 1.000, 0.431, 0.780 |
| Deep purple (plate, shadowed mane) | `#8A5CFF` | 0.541, 0.361, 1.000 |
| Gold (horn base, crown, hooves, trim) | `#FFC94D` | 1.000, 0.788, 0.302 |
| Accent cyan (horn tip glow, emblem glow) | `#00E6FF` | 0.000, 0.902, 1.000 |

The validator warns when a material's base colour is more than 0.20 (RGB
Euclidean) from the nearest palette entry, which catches an accidental recolour.

## 3. Proportions

From the character board: **W : H : L = 1.0 : 1.0 : 1.2** relative, head ≈ 45% of
height. In metres the asset is authored at **0.30 m tall** at the origin between
the front hooves, facing −Z, Y-up. The application scales it to the user's
`character.scale` setting; the asset itself must not bake in a scale.

## 4. Part-by-part requirements

**Head and face**
- Round muzzle, small closed smile, two blush marks per cheek.
- Eyes: iris radial gradient (violet to light lavender), dark upper lash line,
  one large specular highlight plus one small secondary highlight.
- Eyelids must be able to close fully for `sleep` and `blink`.
- Ears: tall, rounded, pink inside, able to flick independently.

**Horn**
- Spiral bicone, gold at the base, cyan-lit tip (emissive), seated in the crown.

**Mane and tail**
- Three-colour gradient with visible strand separation, not a smooth blob.
- Mane falls to the character's left; a forelock crosses the forehead.
- Tail spirals out and back, roughly two-thirds of body length.
- Both need enough segments to move with secondary motion (Mane1-3, Tail1-4).

**Wings**
- Two layers of feathers, gold edge trim, folded by default.
- Wing root near the shoulder so `fly` reads correctly.

**Legs and hooves**
- Short, stocky legs; gold hoof caps with a purple insert and small diamond.
- Ground contact at y = 0 with `Root` at the origin.

**Body**
- Purple chest plate with cyan trim, gold collar V, emblem centred on the plate.

## 5. Materials and shading

| Surface | Requirement |
|---|---|
| Coat | PBR base colour, roughness ~0.55, no metallic; soft wrap shading preferred |
| Mane / tail | Vertex colour or UV gradient across the three mane colours; roughness ~0.35 |
| Gold | metallic 1.0, roughness ~0.25 |
| Horn tip, emblem, chest trim | emissive cyan, low intensity so it does not bloom out |
| Eyes | separate material, high gloss, no metallic; iris as texture |
| Textures | ≤ 2048², PBR metallic-roughness, no baked lighting |

## 6. Geometry budget

| Item | Target |
|---|---|
| Total triangles | 25,000 – 40,000 (LOD0) |
| LOD1 | ≤ 60% of LOD0, used when the user lowers animation quality |
| Materials | ≤ 8 |
| Max bone influences per vertex | 4 |
| Origin | between front hooves, ground level |
| Forward axis | −Z, Y-up, transforms applied, scale 1.0 |

## 7. Required expressions and poses

Expressions from the sheet: happy, wink, surprised, thinking, sleepy/yawn,
sleeping. Poses needed by the desktop app: all-four-legs idle stance, walk, run,
flight, sleep, pet reaction, ball play. `sit` is optional and only if it stays
recognisably the same character.

## 8. Forbidden

- No circular platform, pedestal or base of any kind.
- No substitute or lookalike character. Lumi is not a pony from any franchise.
- No recolouring, simplification of the horn/wings/emblem, or removal of the mane
  gradient.
- A static PNG is never an acceptable stand-in for the 3D model.
- No baked-in camera, lighting rig, or environment in the export.

## 9. Acceptance procedure

1. `python tools/validate_glb.py assets/models/lumi.glb --json docs/lumi_asset_report.json`
   must pass with zero errors and zero warnings (use `--strict`).
2. Renders from front, back, left, right and three-quarter views compared against
   the character board.
3. Each required clip plays in isolation and loops cleanly (no popping at the wrap).
4. Checked at 100% and 150% Windows display scaling on a real desktop overlay.

## 10. Current gaps

| Item | Status |
|---|---|
| Rigged GLB asset | **does not exist** |
| Rig / clip contract | defined (`rig_contract.py`) |
| Validator | implemented and tested against synthetic fixtures |
| Placeholder | the M0 debug cube stands in for rendering tests only; it is not a pony and is never presented as Lumi |

When a real asset arrives it replaces the placeholder wholesale. Until then no
document, README or UI may describe Lumi as modelled, rigged, animated or finished.
