"""Animation interfaces: fallback resolution and procedural motion."""

from __future__ import annotations

import random

import pytest

from lumi.character.animation import (
    DEFAULT_FALLBACKS,
    SAFE_CLIP,
    ClipInfo,
    ClipLibrary,
    EventDrivenAnimator,
    PlaceholderAnimationController,
    ProceduralMotion,
)
from lumi.character.state_machine import ClipRequested


def test_library_resolves_direct_clips():
    library = ClipLibrary(["idle", "walk", "blink"])
    assert library.resolve("walk") == "walk"
    assert len(library) == 3
    assert "walk" in library


def test_missing_clip_uses_contract_fallback():
    library = ClipLibrary(["idle", "walk"])
    assert library.resolve("run") == "walk"  # run falls back to walk


def test_unknown_clip_falls_back_to_safe_idle():
    library = ClipLibrary(["idle"])
    assert library.resolve("backflip") == SAFE_CLIP
    assert library.resolve("fly") == SAFE_CLIP  # fly has no explicit fallback


def test_empty_library_resolves_nothing():
    library = ClipLibrary([])
    assert library.resolve("idle") is None
    assert library.info("idle") is None


def test_from_manifest_accepts_dict_and_list():
    as_dict = ClipLibrary.from_manifest({"clips": {"idle": {}, "walk": {}}})
    assert "idle" in as_dict and "walk" in as_dict

    as_list = ClipLibrary.from_manifest({"clips": [{"name": "idle"}, "walk"]})
    assert as_list.names == ("idle", "walk")


def test_fallback_chain_does_not_loop_forever():
    library = ClipLibrary(["idle"], fallbacks={"loop_a": "loop_b", "loop_b": "loop_a"})
    assert library.resolve("loop_a") == SAFE_CLIP


def test_controller_reports_mode_honestly():
    controller = PlaceholderAnimationController(ClipLibrary(["idle"]))
    assert controller.play("idle") == "idle"
    assert controller.mode == "clips"

    assert controller.play("run") == "idle"
    assert controller.mode == "fallback"
    assert controller.requested == "run"

    empty = PlaceholderAnimationController(ClipLibrary([]))
    assert empty.play("idle") is None
    assert empty.mode == "procedural"
    assert empty.current is None


def test_controller_stop_and_snapshot():
    controller = PlaceholderAnimationController(ClipLibrary(["idle"]))
    controller.play("idle")
    controller.update(0.5)
    snap = controller.snapshot()
    assert snap["current"] == "idle"
    controller.stop()
    assert controller.snapshot()["current"] is None


def test_procedural_breathing_stays_in_range():
    motion = ProceduralMotion(rng=random.Random(1))
    samples = [motion.sample(t / 30.0) for t in range(0, 300)]
    scales = [s.breath_scale for s in samples]
    assert min(scales) >= 1.0 - motion.breath_amplitude - 1e-9
    assert max(scales) <= 1.0 + motion.breath_amplitude + 1e-9
    assert max(scales) - min(scales) > 0.001  # it actually moves


def test_procedural_blink_eventually_closes_the_eyes():
    motion = ProceduralMotion(blink_interval=(1.0, 2.0), rng=random.Random(3))
    values = [motion.blink_amount(t / 60.0) for t in range(0, 600)]
    assert max(values) == pytest.approx(1.0, abs=0.05)
    assert min(values) == pytest.approx(0.0)


def test_sleeping_forces_eyes_closed_and_slower_breath():
    motion = ProceduralMotion(rng=random.Random(2))
    sample = motion.sample(3.0, sleeping=True)
    assert sample.blink == 1.0


def test_event_driven_animator_feeds_the_controller():
    controller = PlaceholderAnimationController(ClipLibrary(["idle", "walk"]))
    animator = EventDrivenAnimator(controller)
    played = animator.handle([ClipRequested(clip="walk", loop=True)])
    assert played == ["walk"]
    assert controller.current == "walk"

    animator.handle([ClipRequested(clip="run", loop=True), ClipRequested(clip="idle", loop=True)])
    assert [name for name, _ in controller.history] == ["walk", "walk", "idle"]


def test_animator_survives_a_broken_controller():
    class Exploding(PlaceholderAnimationController):
        def play(self, clip, fade=0.25):
            raise RuntimeError("gpu exploded")

    animator = EventDrivenAnimator(Exploding(ClipLibrary(["idle"])))
    assert animator.handle([ClipRequested(clip="idle", loop=True)]) == []
    assert animator.last_error and "gpu exploded" in animator.last_error


def test_default_fallbacks_only_point_at_known_clips():
    from lumi.character.rig_contract import CLIP_NAMES

    from lumi.character.animation import SYNTHETIC_CLIPS

    known = set(CLIP_NAMES) | set(SYNTHETIC_CLIPS)
    for clip, fallback in DEFAULT_FALLBACKS.items():
        assert clip in known, f"{clip} is neither a contract clip nor a declared synthetic clip"
        assert fallback in known, f"{fallback} is not a known clip"
