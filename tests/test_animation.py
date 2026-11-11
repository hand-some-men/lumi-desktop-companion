"""Animation clip resolution and procedural motion, tested with no rig."""

from __future__ import annotations

import math
import random

import pytest

from lumi.character.animation import (
    DEFAULT_FALLBACKS,
    SAFE_CLIP,
    SYNTHETIC_CLIPS,
    ClipInfo,
    ClipLibrary,
    EventDrivenAnimator,
    PlaceholderAnimationController,
    ProceduralMotion,
)
from lumi.character.rig_contract import CLIP_NAMES, REQUIRED_CLIP_NAMES


def test_empty_library_is_honest_about_having_nothing():
    lib = ClipLibrary([])
    assert len(lib) == 0
    assert lib.resolve("idle") is None


def test_missing_clip_falls_back_through_the_chain():
    lib = ClipLibrary(["idle", "walk"])
    assert lib.resolve("run") == "walk"  # run -> walk
    assert lib.resolve("turn_left") == "walk"  # turn_left -> walk
    assert lib.resolve("look_around") == "idle"


def test_fallback_chain_is_cycle_safe():
    lib = ClipLibrary(["idle"], fallbacks={"loop_a": "loop_b", "loop_b": "loop_a"})
    assert lib.resolve("loop_a") == SAFE_CLIP


def test_last_resort_is_idle_when_available():
    lib = ClipLibrary(["idle", "walk"], fallbacks={"mystery": "nowhere"})
    assert lib.resolve("mystery") == "idle"


def test_library_from_manifest_accepts_dict_and_list():
    assert ClipLibrary.from_manifest({"clips": {"idle": 1.0, "walk": 1.0}}).names == ("idle", "walk")
    assert ClipLibrary.from_manifest({"clips": ["idle", "walk"]}).names == ("idle", "walk")
    assert ClipLibrary.from_manifest({}).names == ()


def test_clip_info_only_when_present():
    lib = ClipLibrary([ClipInfo("idle", duration=2.0)])
    assert lib.info("idle").duration == 2.0
    assert lib.info("nope") is None


def test_synthetic_clips_are_marked_not_in_the_asset_table():
    assert "dragged" in SYNTHETIC_CLIPS
    assert "dragged" not in CLIP_NAMES


def test_default_fallbacks_cover_every_optional_contract_clip():
    from lumi.character.rig_contract import CLIPS

    optional = {c.name for c in CLIPS if not c.required}
    assert optional <= set(DEFAULT_FALLBACKS)


def test_controller_reports_mode_honestly():
    lib = ClipLibrary(["idle", "walk"])
    ctrl = PlaceholderAnimationController(lib)
    assert ctrl.play("walk") == "walk"
    assert ctrl.mode == "clips"
    assert ctrl.play("run") == "walk"
    assert ctrl.mode == "fallback"
    assert ctrl.requested == "run"


def test_controller_without_clips_is_procedural():
    ctrl = PlaceholderAnimationController(ClipLibrary([]))
    assert ctrl.play("idle") is None
    assert ctrl.mode == "procedural"
    assert ctrl.current is None


def test_update_accumulates_time_and_samples_motion():
    ctrl = PlaceholderAnimationController(ClipLibrary(["idle"]))
    ctrl.play("idle")
    for _ in range(10):
        ctrl.update(0.1)
    snap = ctrl.snapshot()
    assert snap["time"] == pytest.approx(1.0, abs=1e-6)
    assert snap["mode"] == "clips"


def test_update_ignores_non_positive_dt():
    ctrl = PlaceholderAnimationController()
    ctrl.update(0)
    ctrl.update(-1)
    assert ctrl.snapshot()["time"] == 0.0


def test_stop_clears_state():
    ctrl = PlaceholderAnimationController(ClipLibrary(["idle"]))
    ctrl.play("idle")
    ctrl.stop()
    assert ctrl.current is None and ctrl.requested is None
    assert ctrl.mode == "procedural"


def test_history_records_every_request():
    ctrl = PlaceholderAnimationController(ClipLibrary(["idle", "walk"]))
    ctrl.play("walk")
    ctrl.play("run")
    assert ctrl.history == [("walk", "clips"), ("walk", "fallback")]


def test_breathing_is_smooth_and_bounded():
    motion = ProceduralMotion(breath_amplitude=0.01)
    samples = [motion.sample(t).breath_scale for t in [i * 0.05 for i in range(200)]]
    assert max(samples) <= 1.01 + 1e-9
    assert min(samples) >= 0.99 - 1e-9
    assert max(samples) - min(samples) > 0.01  # it actually moves
    # No jumps: consecutive samples stay close together.
    assert max(abs(b - a) for a, b in zip(samples, samples[1:])) < 0.01


def test_sleeping_breathes_slower_and_deeper():
    motion = ProceduralMotion()
    awake = motion.sample(0.3, sleeping=False)
    asleep = motion.sample(0.3, sleeping=True)
    assert asleep.blink == 1.0  # eyes closed
    assert abs(asleep.breath_offset) >= abs(awake.breath_offset)


def test_blinks_are_short_and_occasional():
    motion = ProceduralMotion(blink_interval=(4.0, 4.0), blink_duration=0.12, rng=random.Random(3))
    closed = [t for t in [i * 0.01 for i in range(2000)] if motion.blink_amount(t) > 0.5]
    # Roughly two blinks in 20 s, each ~0.06 s above half-closed.
    assert 6 <= len(closed) <= 20


def test_blink_is_zero_while_open():
    motion = ProceduralMotion(blink_interval=(50.0, 50.0))
    assert motion.blink_amount(1.0) == 0.0


def test_wing_flap_stays_in_range():
    motion = ProceduralMotion()
    for i in range(100):
        value = motion.sample(i * 0.03).wing_flap
        assert 0.0 <= value <= 1.0
        assert not math.isnan(value)


def test_animator_forwards_clip_requests():
    from lumi.character.state_machine import ClipRequested

    ctrl = PlaceholderAnimationController(ClipLibrary(["idle", "pet_reaction"]))
    animator = EventDrivenAnimator(ctrl)
    played = animator.handle([ClipRequested("pet_reaction", loop=False), "not an event"])
    assert played == ["pet_reaction"]
    assert ctrl.current == "pet_reaction"


def test_animator_survives_a_broken_controller():
    class Boom:
        def play(self, clip, fade=0.25):
            raise RuntimeError("bone missing")

        def update(self, dt):
            raise RuntimeError("update failed")

    from lumi.character.state_machine import ClipRequested

    animator = EventDrivenAnimator(Boom())
    assert animator.handle([ClipRequested("idle", loop=True)]) == []
    assert "bone missing" in animator.last_error


def test_required_clips_exist_in_contract():
    assert set(REQUIRED_CLIP_NAMES) <= set(CLIP_NAMES)
