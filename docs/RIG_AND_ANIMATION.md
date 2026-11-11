# Lumi — Rig Hierarchy, Bone Naming and Animation Clips

**Status: contract, not a description of an existing rig.** No rigged Lumi asset
exists yet. This document and `src/lumi/character/rig_contract.py` are the
contract an asset must satisfy; `tools/validate_glb.py` enforces it.

---

## 1. Naming convention

| Rule | Example |
|---|---|
| Armature object | `Lumi_Rig` |
| Body bones are PascalCase | `Spine`, `Chest`, `Head` |
| Side suffix is the character's own left/right | `Ear_L`, `Wing_R` |
| Legs: side + position (F/B × L/R) | `Leg_FL`, `Leg_BR` |
| Repeated segments numbered outward from the body | `Tail1` … `Tail4` |
| Clips are snake_case and match the table exactly | `pet_reaction`, `fly_land` |

Names are case-sensitive. A clip called `Idle` is not `idle` and will be rejected.

## 2. Hierarchy

```
Root                         ground origin, whole-character transform
└── Hips                     centre of mass, carries the bob
    ├── Spine
    │   └── Chest            breathing, squash and stretch
    │       ├── Neck
    │       │   └── Head     look-at target
    │       │       ├── Jaw              (optional) yawn / happy
    │       │       ├── Horn
    │       │       ├── Ear_L, Ear_R
    │       │       ├── Eye_L, Eye_R
    │       │       ├── Eyelid_L, Eyelid_R   (optional)
    │       │       └── Mane1                (optional)
    │       ├── Mane2, Mane3                 (optional)
    │       ├── Wing_L ── Wing_L_Feather1/2  (optional children)
    │       └── Wing_R ── Wing_R_Feather1/2  (optional children)
    ├── Leg_FL / Leg_FR / Leg_BL / Leg_BR
    │   └── Hoof_xx                          (optional)
    └── Tail1 ── Tail2 ── Tail3 ── Tail4
```

Required bones: 21. Optional bones add facial detail and secondary motion and
must not be faked if absent — the procedural layer covers their absence.

| Group | Required | Optional |
|---|---|---|
| Core | Root, Hips, Spine, Chest, Neck, Head | Jaw |
| Face | Horn, Ear_L, Ear_R, Eye_L, Eye_R | Eyelid_L, Eyelid_R |
| Wings | Wing_L, Wing_R | Wing_*_Feather1/2 |
| Legs | Leg_FL, Leg_FR, Leg_BL, Leg_BR | Hoof_FL, Hoof_FR, Hoof_BL, Hoof_BR |
| Tail | Tail1–Tail4 | — |
| Mane | — | Mane1–Mane3 |

## 3. Animation clips

Names are a contract. `required` clips must be present or the asset is rejected;
`fallback` is the substitute used when an optional clip is missing.

| Clip | Loop | Required | Fallback | Purpose |
|---|---|---|---|---|
| `idle` | yes | yes | — | breathing, weight shift, tail sway |
| `blink` | no | yes | — | single blink, ~0.12 s |
| `look_around` | yes | no | `idle` | head turns left/right |
| `walk` | yes | yes | — | four-beat walk in place |
| `run` | yes | yes | `walk` | faster gait, ears back |
| `turn_left` | yes | no | `walk` | banked turn while walking |
| `turn_right` | yes | no | `walk` | banked turn while walking |
| `fly_start` | no | no | `idle` | crouch and push off |
| `fly` | yes | yes | — | wing flap loop, legs tucked |
| `fly_land` | no | no | `idle` | flare and touch down |
| `sleep` | yes | yes | — | curled, slow breathing, eyes closed |
| `yawn` | no | yes | — | stretch and open-mouth yawn |
| `happy` | no | yes | — | cheerful bounce |
| `surprised` | no | no | `idle` | startle |
| `pet_reaction` | no | yes | — | leans into the cursor |
| `play_ball` | yes | yes | — | crouch, pounce, chase |
| `sit` | yes | no | `idle` | optional, only if it suits the design |

`dragged` is **not** an asset clip. The behaviour machine requests it and the
animation layer resolves it to a safe clip (or procedural motion) — see
`SYNTHETIC_CLIPS` in `src/lumi/character/animation.py`.

## 4. Root motion policy

All locomotion clips animate **in place**. The application moves the character
node across the desktop. Baking forward motion into `walk`/`run` would fight the
window positioning and is rejected at review.

Vertical bob during `walk`/`run` is fine and expected.

## 5. Export requirements

- glTF 2.0 binary (`.glb`), Y-up, metres, transforms applied, scale 1.0.
- One animation per clip, named exactly as the table, no NLA strips.
- Frame 1 is the clip start; looping clips must return to their first pose.
- Skinning: ≤ 4 influences per vertex, no unweighted vertices.
- No baked lighting, cameras, lights or platform geometry.

## 6. How the application uses this contract

```
behaviour state  --(StateId)-->  ClipRequested(clip=...)      src/lumi/character/state_machine.py
ClipRequested    --(resolve)-->  actual clip or safe fallback src/lumi/character/animation.py
actual clip      --(Panda)-->    playback + procedural layer  (M3, not written yet)
```

The state machine never names a bone and never touches the renderer, so the
whole behaviour layer can be tested without a model. The tests in
`tests/test_state_machine.py` and `tests/test_animation.py` run without Panda3D.

## 7. Verification

| Check | Where |
|---|---|
| Bone names present and correctly parented | `tools/validate_glb.py` (`BONE002`, `BONE004`) |
| Required clips present | `CLIP001` |
| Unknown bones/clips flagged | `BONE003`, `CLIP002` |
| Rig named `Lumi_Rig` | `BONE005` |
| File is skinned at all | `BONE001` |
| Contract self-consistency (parents before children, fallbacks valid) | `tests/test_rig_and_validation.py` |

## 8. Known limitations

- The hierarchy has never been checked against a real exported rig.
- Bone roll/orientation conventions are not specified yet; they should be pinned
  down with the first real asset rather than guessed now.
- Facial rig scope (shape keys vs bones) is undecided; `Jaw`, `Eyelid_*` bones are
  the minimum, and morph targets are an acceptable alternative if the validator is
  extended.
