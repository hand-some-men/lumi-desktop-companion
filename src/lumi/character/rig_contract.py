"""Canonical rig and animation contract for the Lumi character asset.

This module is the single source of truth for bone names, hierarchy and clip
names. The 3D asset (whenever a real one exists) must satisfy it, and
`tools/validate_glb.py` enforces it.

Naming convention
-----------------
* Root armature object: ``Lumi_Rig``
* Bones: ``PascalCase`` for body parts (``Spine``, ``Chest``, ``Head``)
* Side suffix: ``_L`` / ``_R`` (character's own left/right, not screen)
* Legs are identified by side and position: ``Leg_FL`` = front-left,
  ``Leg_BR`` = back-right
* Repeating segments are numbered from the body outward: ``Tail1`` .. ``Tail4``
* Animation clips are ``snake_case`` and match the clip table exactly.

Nothing in this file has been verified against a real rig - it is a contract, not
a description of an existing model.
"""

from __future__ import annotations

from dataclasses import dataclass

RIG_NAME = "Lumi_Rig"


@dataclass(frozen=True)
class BoneSpec:
    name: str
    parent: str | None
    required: bool
    purpose: str = ""


# Order matters: parents always appear before their children.
BONES: tuple[BoneSpec, ...] = (
    BoneSpec("Root", None, True, "whole-character transform; origin between front hooves on the ground"),
    BoneSpec("Hips", "Root", True, "body centre of mass; carries the bob"),
    BoneSpec("Spine", "Hips", True, "lower torso"),
    BoneSpec("Chest", "Spine", True, "upper torso; breathing and squash"),
    BoneSpec("Neck", "Chest", True, "head base"),
    BoneSpec("Head", "Neck", True, "head; look-at target"),
    BoneSpec("Jaw", "Head", False, "muzzle open for yawn and happy"),
    BoneSpec("Horn", "Head", True, "golden spiral horn with cyan tip"),
    BoneSpec("Ear_L", "Head", True, "ear flick secondary motion"),
    BoneSpec("Ear_R", "Head", True, "ear flick secondary motion"),
    BoneSpec("Eye_L", "Head", True, "eye aim / parallax"),
    BoneSpec("Eye_R", "Head", True, "eye aim / parallax"),
    BoneSpec("Eyelid_L", "Head", False, "blink if eyelids are separate geometry"),
    BoneSpec("Eyelid_R", "Head", False, "blink if eyelids are separate geometry"),
    BoneSpec("Wing_L", "Chest", True, "left wing root"),
    BoneSpec("Wing_R", "Chest", True, "right wing root"),
    BoneSpec("Wing_L_Feather1", "Wing_L", False, "layered feather segment"),
    BoneSpec("Wing_L_Feather2", "Wing_L", False, "layered feather segment"),
    BoneSpec("Wing_R_Feather1", "Wing_R", False, "layered feather segment"),
    BoneSpec("Wing_R_Feather2", "Wing_R", False, "layered feather segment"),
    BoneSpec("Leg_FL", "Hips", True, "front-left upper leg"),
    BoneSpec("Leg_FR", "Hips", True, "front-right upper leg"),
    BoneSpec("Leg_BL", "Hips", True, "back-left upper leg"),
    BoneSpec("Leg_BR", "Hips", True, "back-right upper leg"),
    BoneSpec("Hoof_FL", "Leg_FL", False, "gold hoof cap, ground contact"),
    BoneSpec("Hoof_FR", "Leg_FR", False, "gold hoof cap, ground contact"),
    BoneSpec("Hoof_BL", "Leg_BL", False, "gold hoof cap, ground contact"),
    BoneSpec("Hoof_BR", "Leg_BR", False, "gold hoof cap, ground contact"),
    BoneSpec("Tail1", "Hips", True, "tail root"),
    BoneSpec("Tail2", "Tail1", True, "tail mid"),
    BoneSpec("Tail3", "Tail2", True, "tail tip"),
    BoneSpec("Tail4", "Tail3", True, "tail curl"),
    BoneSpec("Mane1", "Head", False, "front mane strand"),
    BoneSpec("Mane2", "Neck", False, "mane strand"),
    BoneSpec("Mane3", "Chest", False, "long mane strand"),
)


@dataclass(frozen=True)
class ClipSpec:
    name: str
    loop: bool
    required: bool
    fallback: str | None
    description: str


# The clip table. `fallback` is the clip to substitute when the asset lacks this
# one; a missing required clip is an asset error, not a silent T-pose.
CLIPS: tuple[ClipSpec, ...] = (
    ClipSpec("idle", True, True, None, "breathing loop, weight shifting, tail sway"),
    ClipSpec("blink", False, True, None, "single blink, ~0.12 s"),
    ClipSpec("look_around", True, False, "idle", "head turns left/right at random"),
    ClipSpec("walk", True, True, None, "four-beat walk in place, no root motion"),
    ClipSpec("run", True, True, "walk", "faster gait, ears back, tail streaming"),
    ClipSpec("turn_left", True, False, "walk", "banked turn, used while walking"),
    ClipSpec("turn_right", True, False, "walk", "banked turn, used while walking"),
    ClipSpec("fly_start", False, False, "idle", "crouch and push off"),
    ClipSpec("fly", True, True, None, "wing flap loop, legs tucked"),
    ClipSpec("fly_land", False, False, "idle", "flare and touch down"),
    ClipSpec("sleep", True, True, None, "curled up, slow breathing, closed eyes"),
    ClipSpec("yawn", False, True, None, "big stretch and open-mouth yawn"),
    ClipSpec("happy", False, True, None, "cheerful bounce, ears up"),
    ClipSpec("surprised", False, False, "idle", "startle, wide eyes"),
    ClipSpec("pet_reaction", False, True, None, "leans into the cursor, eyes closed"),
    ClipSpec("play_ball", True, True, None, "crouch, pounce and chase loop"),
    ClipSpec("sit", True, False, "idle", "optional sitting pose, only if it fits the design"),
)

CLIP_NAMES: tuple[str, ...] = tuple(c.name for c in CLIPS)
CLIP_BY_NAME: dict[str, ClipSpec] = {c.name: c for c in CLIPS}

REQUIRED_BONE_NAMES: tuple[str, ...] = tuple(b.name for b in BONES if b.required)
REQUIRED_CLIP_NAMES: tuple[str, ...] = tuple(c.name for c in CLIPS if c.required)

# Colour palette from the character board. Used by the asset validator to catch
# a model that was recoloured by accident.
PALETTE: dict[str, tuple[float, float, float]] = {
    "coat": (0.937, 0.902, 1.000),      # #EFE6FF
    "mane_purple": (0.714, 0.294, 1.000),  # #B64BFF
    "mane_blue": (0.306, 0.784, 1.000),   # #4EC8FF
    "mane_pink": (1.000, 0.431, 0.780),   # #FF6EC7
    "deep_purple": (0.541, 0.361, 1.000),  # #8A5CFF
    "gold": (1.000, 0.788, 0.302),      # #FFC94D
    "accent_cyan": (0.000, 0.902, 1.000),  # #00E6FF
}
PALETTE_HEX: dict[str, str] = {
    "coat": "#EFE6FF",
    "mane_purple": "#B64BFF",
    "mane_blue": "#4EC8FF",
    "mane_pink": "#FF6EC7",
    "deep_purple": "#8A5CFF",
    "gold": "#FFC94D",
    "accent_cyan": "#00E6FF",
}


@dataclass(frozen=True)
class ContractResult:
    ok: bool
    missing: tuple[str, ...] = ()
    unknown: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {"ok": self.ok, "missing": list(self.missing), "unknown": list(self.unknown)}


def bone_names(required_only: bool = False) -> tuple[str, ...]:
    return tuple(b.name for b in BONES if b.required or not required_only)


def clip_names(required_only: bool = False) -> tuple[str, ...]:
    return tuple(c.name for c in CLIPS if c.required or not required_only)


def parent_of(bone_name: str) -> str | None:
    index = _BONE_INDEX.get(bone_name)
    return None if index is None else BONES[index].parent


_BONE_INDEX: dict[str, int] = {b.name: i for i, b in enumerate(BONES)}


def check_bones(names: set[str] | list[str]) -> ContractResult:
    """Compare a rig's bone names against the contract."""
    present = set(names)
    missing = tuple(n for n in REQUIRED_BONE_NAMES if n not in present)
    known = {b.name for b in BONES}
    unknown = tuple(sorted(n for n in present if n not in known))
    return ContractResult(ok=not missing, missing=missing, unknown=unknown)


def check_clips(names: set[str] | list[str]) -> ContractResult:
    present = set(names)
    missing = tuple(n for n in REQUIRED_CLIP_NAMES if n not in present)
    known = set(CLIP_NAMES)
    unknown = tuple(sorted(n for n in present if n not in known))
    return ContractResult(ok=not missing, missing=missing, unknown=unknown)


def resolve_clip(name: str) -> str | None:
    """Follow the fallback chain for a clip name.

    Returns the best available substitute for *name* known to the contract, or
    ``None`` when nothing sensible exists. Cycle-safe.
    """
    seen: set[str] = set()
    current: str | None = name
    while current is not None and current not in seen:
        seen.add(current)
        spec = CLIP_BY_NAME.get(current)
        if spec is None:
            return None
        if spec.fallback is None:
            return current
        current = spec.fallback
    return None


def hierarchy() -> dict[str, str | None]:
    return {b.name: b.parent for b in BONES}
