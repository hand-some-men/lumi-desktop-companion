# LUMI — Character Specification

Status: binding for all art and animation work. Nothing in this document has
been produced as an asset yet; it describes what the asset *must* be.

## 1. Identity

Lumi is a small winged unicorn (alicorn) companion that lives on the Windows
desktop. She is a character, not a mascot sprite: every pose, proportion and
colour below is part of her identity and may not be substituted.

Hard rules, from the project owner:

| Rule | Meaning |
| --- | --- |
| No substitute characters | Never ship a corgi, cat, generic pony or placeholder creature as "Lumi". A debug cube is acceptable *only* inside test tooling and must be labelled as such. |
| No static images | A screenshot, sprite sheet, GIF or video is not a stand-in for the 3D character in the app. The running app renders the model. |
| No circular platform | Lumi stands on the desktop itself. No disc, shadow-puck, plinth or pedestal under her. |
| Colour identity is fixed | The palette in section 3 is exact. Recolouring is an asset bug, not a style choice. |

## 2. Silhouette and proportions

Desktop-scale: about **0.30 m** tall at the horn tip, roughly **0.28 m** long
nose to tail base. Chibi proportions, head about 1/3 of the body height.

- **Head** — rounded muzzle, large eyes set wide, small soft ears, spiral horn.
- **Horn** — slim, spiralled, gold with a cyan tip glow. Never a party cone.
- **Body** — plump, short barrel; four slender legs with gold hooves.
- **Wings** — feathered, folded against the barrel at rest, spanning about 1.3×
  the body length when open. Two feather layers per wing for the folded look.
- **Mane and tail** — long, flowing, three-colour gradient (purple → blue →
  pink), always in motion, even at rest.
- **Eyes** — large, dark with a bright highlight; lids close for blinks.

## 3. Palette (exact)

| Name | Hex | RGB 0–1 | Use |
| --- | --- | --- | --- |
| coat | `#EFE6FF` | 0.937, 0.902, 1.000 | body, head, legs |
| mane_purple | `#B64BFF` | 0.714, 0.294, 1.000 | mane root, tail root |
| mane_blue | `#4EC8FF` | 0.306, 0.784, 1.000 | mane mid |
| mane_pink | `#FF6EC7` | 1.000, 0.431, 0.780 | mane tips, tail tips |
| deep_purple | `#8A5CFF` | 0.541, 0.361, 1.000 | wing shadow, ear inner |
| gold | `#FFC94D` | 1.000, 0.788, 0.302 | horn base, hooves |
| accent_cyan | `#00E6FF` | 0.000, 0.902, 1.000 | horn tip glow, eye highlight |

The same values live in `src/lumi/character/rig_contract.py` (`PALETTE`) so the
validator can catch drift automatically. Change the palette in exactly one place.

## 4. Surface treatment

Soft, toy-like, slightly glossy plastic — the look of a well-made vinyl figure.

- Base colour plus subtle gradient, no heavy noise or grunge.
- Rim light on the coat edges so the silhouette reads on dark and light
  wallpapers alike.
- Alpha-tested or alpha-blended transparent mane tips, no opaque cut-out look.
- Hard specular highlights on horn and hooves only.

No baked-in shadows on the ground: the desktop belongs to the user's wallpaper.
A soft contact shadow may be drawn under the hooves *only* if it fades to fully
transparent and never forms a visible disc (see the no-platform rule).

## 5. Scale and origin

- Origin at the ground between the front hooves, +Y up, facing +Z.
- 1 unit = 1 metre. Total height ≈ 0.30 m.
- Feet at y = 0 so the model can be placed by the window origin with no offset.
- No root motion inside clips: translation is owned by the movement layer.

## 6. Expression and personality

Calm, curious, a little shy. Reactions must be readable at 320 px:

| Situation | What the player sees |
| --- | --- |
| Idle | breathing, tail sway, occasional look-around |
| Petted | leans into the cursor, eyes closed, ears up |
| Dragged | legs dangle, wings flare slightly for balance |
| Tired | yawn, then curls up and sleeps |
| Playing | crouch, pounce, chase the ball |

Expression is conveyed by pose and eye state; no facial texture swaps.

## 7. What "done" means

An asset is acceptable only when:

1. `python tools/validate_glb.py <file> --strict` passes;
2. every required bone and clip in `docs/RIG_AND_ANIMATION.md` exists;
3. a rendered frame shows the palette above, measured not eyeballed;
4. it is a unicorn-pegasus, and nothing else.
