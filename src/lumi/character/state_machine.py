"""Modular behaviour state machine for Lumi.

Pure Python with no Panda3D or Qt dependency, so it is fully unit testable and
platform independent. The machine decides *what* Lumi is doing; the animation
layer decides how to draw it, and the renderer decides where.

Time is supplied by the caller (`update(dt)`), never read from the clock inside,
which is what makes the tests deterministic.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace
from enum import Enum
from typing import Iterable


class StateId(str, Enum):
    IDLE = "idle"
    LOOK_AROUND = "look_around"
    WALK = "walk"
    RUN = "run"
    FLY = "fly"
    YAWN = "yawn"
    SLEEP = "sleep"
    HAPPY = "happy"
    PET_REACTION = "pet_reaction"
    PLAY = "play_ball"
    DRAGGED = "dragged"


@dataclass(frozen=True)
class StateSpec:
    """Static description of a state.

    ``clip`` is the logical clip the animation layer should request; the layer
    resolves it against whatever the asset actually contains.
    """

    id: StateId
    clip: str
    priority: int
    loop: bool = True
    duration: float | None = None          # one-shot length, None for loops
    min_duration: float = 0.0              # cannot be interrupted before this
    suspends_autonomy: bool = False        # dragging: nothing else may start
    energy_per_second: float = 0.0         # negative drains, positive restores

    def with_clip(self, clip: str) -> "StateSpec":
        return replace(self, clip=clip)


STATE_SPECS: dict[StateId, StateSpec] = {
    StateId.IDLE: StateSpec(StateId.IDLE, "idle", priority=1, min_duration=0.4, energy_per_second=-0.002),
    StateId.LOOK_AROUND: StateSpec(
        StateId.LOOK_AROUND, "look_around", priority=2, loop=False, duration=3.0, energy_per_second=-0.002
    ),
    StateId.WALK: StateSpec(StateId.WALK, "walk", priority=4, min_duration=0.5, energy_per_second=-0.006),
    StateId.RUN: StateSpec(StateId.RUN, "run", priority=5, min_duration=0.6, energy_per_second=-0.014),
    StateId.FLY: StateSpec(StateId.FLY, "fly", priority=6, min_duration=1.0, energy_per_second=-0.018),
    StateId.YAWN: StateSpec(StateId.YAWN, "yawn", priority=3, loop=False, duration=2.0),
    StateId.SLEEP: StateSpec(StateId.SLEEP, "sleep", priority=2, energy_per_second=0.02),
    StateId.HAPPY: StateSpec(StateId.HAPPY, "happy", priority=7, loop=False, duration=1.6),
    StateId.PET_REACTION: StateSpec(StateId.PET_REACTION, "pet_reaction", priority=9, loop=False, duration=1.2),
    StateId.PLAY: StateSpec(StateId.PLAY, "play_ball", priority=8, min_duration=1.0, energy_per_second=-0.01),
    StateId.DRAGGED: StateSpec(StateId.DRAGGED, "dragged", priority=10, suspends_autonomy=True),
}


@dataclass(frozen=True)
class BehaviourConfig:
    """Timings that the settings screen will eventually expose."""

    yawn_after: float = 90.0            # seconds of inactivity before a yawn
    sleep_after: float = 120.0          # seconds of inactivity before sleep
    variant_interval: tuple[float, float] = (8.0, 20.0)  # random idle variation
    exhausted_energy: float = 0.05      # below this Lumi sleeps on her own
    run_energy: float = 0.35            # below this she will not run
    fly_energy: float = 0.45            # below this she will not fly
    allow_autonomy: bool = True


@dataclass(frozen=True)
class StateChanged:
    from_state: StateId | None
    to_state: StateId
    reason: str


@dataclass(frozen=True)
class ClipRequested:
    clip: str
    loop: bool


Event = StateChanged | ClipRequested


class CharacterStateMachine:
    """Single-active-state machine with priorities, cooldowns and one-shots."""

    def __init__(
        self,
        config: BehaviourConfig | None = None,
        specs: dict[StateId, StateSpec] | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self.config = config or BehaviourConfig()
        self.specs = dict(specs or STATE_SPECS)
        self._rng = rng or random.Random()
        self._state = StateId.IDLE
        self._time_in_state = 0.0
        self._idle_seconds = 0.0
        self._next_variant_at = self._pick_variant_delay()
        self.energy = 1.0
        self.mood = 0.6

    # -- read-only view ----------------------------------------------------
    @property
    def state(self) -> StateId:
        return self._state

    @property
    def spec(self) -> StateSpec:
        return self.specs[self._state]

    @property
    def time_in_state(self) -> float:
        return self._time_in_state

    @property
    def idle_seconds(self) -> float:
        return self._idle_seconds

    @property
    def is_suspended(self) -> bool:
        """True while something (dragging) forbids autonomous behaviour."""
        return self.spec.suspends_autonomy

    # -- transitions -------------------------------------------------------
    def can_enter(self, target: StateId) -> bool:
        if target is self._state:
            return False
        spec = self.specs[target]
        current = self.spec
        # Lowest priority wins nothing: a walk cannot interrupt a run.
        if spec.priority < current.priority:
            return False
        # Respect the current state's minimum dwell time.
        if self._time_in_state < current.min_duration:
            return False
        # Energy gates.
        if target is StateId.RUN and self.energy < self.config.run_energy:
            return False
        if target is StateId.FLY and self.energy < self.config.fly_energy:
            return False
        return True

    def request(self, target: StateId, *, force: bool = False, reason: str = "request") -> list[Event]:
        """Ask for a state change. Returns the events it produced (possibly none)."""
        if target is self._state:
            return []
        if not force and not self.can_enter(target):
            return []
        return self._transition(target, reason)

    def _transition(self, target: StateId, reason: str) -> list[Event]:
        previous = self._state
        self._state = target
        self._time_in_state = 0.0
        spec = self.specs[target]
        if target is not StateId.SLEEP:
            self._next_variant_at = self._pick_variant_delay()
        return [
            StateChanged(from_state=previous, to_state=target, reason=reason),
            ClipRequested(clip=spec.clip, loop=spec.loop),
        ]

    # -- time --------------------------------------------------------------
    def update(self, dt: float) -> list[Event]:
        if dt <= 0:
            return []
        events: list[Event] = []
        self._time_in_state += dt
        spec = self.spec

        # Energy: draining while awake, recovering in sleep.
        self.energy = _clamp(self.energy + spec.energy_per_second * dt)
        if spec.id is not StateId.SLEEP:
            self._idle_seconds += dt

        # One-shot states finish by themselves.
        if not spec.loop and spec.duration is not None and self._time_in_state >= spec.duration:
            events.extend(self._finish_one_shot())
            return events

        if self.is_suspended or not self.config.allow_autonomy:
            return events

        if spec.id is StateId.IDLE:
            events.extend(self._idle_behaviour())

        return events

    def _finish_one_shot(self) -> list[Event]:
        if self._state is StateId.YAWN and self._idle_seconds >= self.config.sleep_after:
            return self._transition(StateId.SLEEP, "yawn finished, still tired")
        if self._state is StateId.SLEEP:
            return []
        return self._transition(StateId.IDLE, "one-shot finished")

    def _idle_behaviour(self) -> list[Event]:
        if self._idle_seconds >= self.config.yawn_after:
            return self._transition(StateId.YAWN, "inactivity threshold reached")
        if self.energy <= self.config.exhausted_energy:
            return self._transition(StateId.SLEEP, "out of energy")
        if self._time_in_state >= self._next_variant_at:
            choice = self._rng.choice((StateId.LOOK_AROUND, StateId.WALK))
            return self._transition(choice, "idle variation")
        return []

    # -- interaction -------------------------------------------------------
    def handle_interaction(self, kind: str) -> list[Event]:
        """Human input. Always counts as activity, so it wakes Lumi up."""
        self._idle_seconds = 0.0
        if kind == "pet":
            self.mood = _clamp(self.mood + 0.08)
            return self.request(StateId.PET_REACTION, force=True, reason="petted")
        if kind == "drag_start":
            return self.request(StateId.DRAGGED, force=True, reason="drag started")
        if kind == "drag_end":
            return self.request(StateId.IDLE, force=True, reason="drag released")
        if kind == "play":
            return self.request(StateId.PLAY, reason="play requested")
        if kind == "wake":
            if self._state is StateId.SLEEP:
                return self.request(StateId.IDLE, force=True, reason="woken")
            return []
        if kind == "feed":
            self.mood = _clamp(self.mood + 0.05)
            self.energy = _clamp(self.energy + 0.25)
            return []
        return []

    def wake(self) -> list[Event]:
        return self.handle_interaction("wake")

    # -- persistence -------------------------------------------------------
    def snapshot(self) -> dict[str, object]:
        return {
            "state": self._state.value,
            "energy": round(self.energy, 4),
            "mood": round(self.mood, 4),
            "idle_seconds": round(self._idle_seconds, 3),
        }

    def restore(self, data: dict[str, object]) -> list[Event]:
        """Restore from a snapshot. Always resumes in IDLE, never mid-drag."""
        energy = data.get("energy")
        mood = data.get("mood")
        idle = data.get("idle_seconds")
        if isinstance(energy, (int, float)):
            self.energy = _clamp(float(energy))
        if isinstance(mood, (int, float)):
            self.mood = _clamp(float(mood))
        if isinstance(idle, (int, float)):
            self._idle_seconds = max(0.0, float(idle))
        return self.request(StateId.IDLE, force=True, reason="restored")

    # -- internals ---------------------------------------------------------
    def _pick_variant_delay(self) -> float:
        low, high = self.config.variant_interval
        return self._rng.uniform(low, high)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def replay(sm: CharacterStateMachine, dt: float, seconds: float) -> list[Event]:
    """Convenience helper for tests: advance the machine for a duration."""
    events: list[Event] = []
    steps = int(seconds / dt)
    for _ in range(steps):
        events.extend(sm.update(dt))
    return events


def states_from(events: Iterable[Event]) -> list[StateId]:
    return [e.to_state for e in events if isinstance(e, StateChanged)]
