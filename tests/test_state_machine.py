"""State machine behaviour, tested without a renderer or a model."""

from __future__ import annotations

import random

import pytest

from lumi.character.state_machine import (
    BehaviourConfig,
    CharacterStateMachine,
    ClipRequested,
    StateChanged,
    StateId,
    replay,
    states_from,
)


def make_machine(**config) -> CharacterStateMachine:
    # Wide variant interval keeps autonomous wandering out of the way unless a
    # test asks for it.
    config.setdefault("variant_interval", (99.0, 100.0))
    return CharacterStateMachine(config=BehaviourConfig(**config), rng=random.Random(7))


def test_starts_idle_with_full_energy():
    sm = make_machine()
    assert sm.state is StateId.IDLE
    assert sm.energy == pytest.approx(1.0)


def test_petting_reacts_then_returns_to_idle():
    sm = make_machine()
    events = sm.handle_interaction("pet")
    assert isinstance(events[0], StateChanged)
    assert sm.state is StateId.PET_REACTION
    assert any(isinstance(e, ClipRequested) and e.clip == "pet_reaction" for e in events)

    states = states_from(replay(sm, 0.1, 1.3))
    assert states[-1] is StateId.IDLE


def test_petting_raises_mood_within_bounds():
    sm = make_machine()
    for _ in range(20):
        sm.handle_interaction("pet")
    assert 0.0 <= sm.mood <= 1.0
    assert sm.mood > 0.6


def test_drag_suspends_autonomy_until_release():
    sm = make_machine()
    sm.handle_interaction("drag_start")
    assert sm.state is StateId.DRAGGED
    assert sm.is_suspended is True

    # Nothing autonomous may start while held.
    replay(sm, 0.1, 5.0)
    assert sm.state is StateId.DRAGGED

    sm.handle_interaction("drag_end")
    assert sm.state is StateId.IDLE
    assert sm.is_suspended is False


def test_minimum_dwell_time_blocks_an_early_switch():
    sm = make_machine()
    assert sm.request(StateId.WALK) == []  # IDLE requires 0.4 s first
    replay(sm, 0.05, 0.5)
    assert sm.request(StateId.WALK)  # now allowed


def test_lower_priority_cannot_interrupt_higher():
    sm = make_machine()
    replay(sm, 0.1, 0.5)
    sm.request(StateId.RUN)
    assert sm.state is StateId.RUN
    replay(sm, 0.1, 0.7)  # satisfy RUN's own minimum dwell
    assert sm.request(StateId.WALK) == []
    assert sm.state is StateId.RUN


def test_forced_transition_ignores_priority():
    sm = make_machine()
    replay(sm, 0.1, 0.5)
    sm.request(StateId.RUN)
    assert sm.request(StateId.IDLE, force=True)
    assert sm.state is StateId.IDLE


def test_low_energy_blocks_running():
    sm = make_machine()
    sm.energy = 0.1
    replay(sm, 0.1, 0.5)
    assert sm.request(StateId.RUN) == []
    assert sm.state is StateId.IDLE


def test_inactivity_leads_to_yawn_then_sleep():
    sm = make_machine(yawn_after=1.0, sleep_after=2.0)
    replay(sm, 0.1, 1.1)
    assert sm.state is StateId.YAWN

    replay(sm, 0.1, 1.2)  # yawn is a 2.0 s one-shot (starts partway through here)
    assert sm.state in {StateId.YAWN, StateId.SLEEP}

    replay(sm, 0.1, 1.5)
    assert sm.state is StateId.SLEEP


def test_energy_recovers_while_sleeping():
    sm = make_machine()
    sm.request(StateId.SLEEP, force=True)
    sm.energy = 0.4
    replay(sm, 0.1, 10.0)
    assert sm.energy > 0.4


def test_waking_up_interrupts_sleep():
    sm = make_machine()
    sm.request(StateId.SLEEP, force=True)
    events = sm.wake()
    assert sm.state is StateId.IDLE
    assert isinstance(events[0], StateChanged)


def test_look_around_returns_by_itself():
    sm = make_machine()
    sm.request(StateId.LOOK_AROUND, force=True)
    states = states_from(replay(sm, 0.1, 3.2))
    assert states and states[-1] is StateId.IDLE


def test_every_transition_emits_a_clip_request():
    sm = make_machine()
    sm.handle_interaction("pet")
    assert sm.spec.clip == "pet_reaction"
    events = sm.request(StateId.IDLE, force=True)
    assert any(isinstance(e, ClipRequested) for e in events)


def test_update_ignores_non_positive_dt():
    sm = make_machine()
    assert sm.update(0) == []
    assert sm.update(-5) == []
    assert sm.time_in_state == 0.0


def test_snapshot_and_restore_always_resume_idle():
    sm = make_machine()
    sm.handle_interaction("drag_start")
    sm.energy = 0.42
    data = sm.snapshot()
    assert data["state"] == "dragged"

    other = make_machine()
    other.restore(data)
    assert other.state is StateId.IDLE
    assert other.energy == pytest.approx(0.42)

    # Restoring a snapshot taken while sleeping does interrupt the sleep state.
    sleeper = make_machine()
    sleeper.request(StateId.SLEEP, force=True)
    events = sleeper.restore(data)
    assert sleeper.state is StateId.IDLE
    assert any(isinstance(e, StateChanged) for e in events)


def test_unknown_interaction_is_ignored():
    sm = make_machine()
    before = sm.state
    assert sm.handle_interaction("nap") == []
    assert sm.state is before
