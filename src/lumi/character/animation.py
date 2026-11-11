"""Animation controller interfaces with placeholder-safe fallbacks.

There is no rigged Lumi model yet. Everything here therefore works with an empty
clip library: requests resolve to a safe substitute, and a procedural fallback
provides breathing and blinking that need no bones at all.

The Panda3D implementation arrives in M3; it only has to satisfy
`AnimationController`.
"""

from __future__ import annotations

import math
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterable

SAFE_CLIP = "idle"

# Clips requested by the behaviour machine that are not part of the asset clip
# table (they are rendered procedurally or as a fallback).
SYNTHETIC_CLIPS: frozenset[str] = frozenset({"dragged"})

# Contract fallbacks, duplicated here as plain data so this module has no
# dependency on the rig contract (and cannot drift it by accident).
DEFAULT_FALLBACKS: dict[str, str] = {
    "look_around": "idle",
    "run": "walk",
    "turn_left": "walk",
    "turn_right": "walk",
    "fly_start": "idle",
    "fly_land": "idle",
    "surprised": "idle",
    "sit": "idle",
    "dragged": "idle",
}


@dataclass(frozen=True)
class ClipInfo:
    name: str
    duration: float = 1.0
    loop: bool = True


class ClipLibrary:
    """What the loaded asset actually provides."""

    def __init__(self, clips: Iterable[str] | Iterable[ClipInfo], fallbacks: dict[str, str] | None = None):
        infos: dict[str, ClipInfo] = {}
        for clip in clips:
            info = clip if isinstance(clip, ClipInfo) else ClipInfo(name=str(clip))
            infos[info.name] = info
        self._clips = infos
        self._fallbacks = dict(DEFAULT_FALLBACKS)
        if fallbacks:
            self._fallbacks.update(fallbacks)

    # -- queries -----------------------------------------------------------
    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._clips))

    def __contains__(self, name: object) -> bool:
        return name in self._clips

    def __len__(self) -> int:
        return len(self._clips)

    def info(self, name: str) -> ClipInfo | None:
        return self._clips.get(name)

    def resolve(self, name: str) -> str | None:
        """Map a requested clip onto one that exists, following fallbacks."""
        seen: set[str] = set()
        current: str | None = name
        while current is not None and current not in seen:
            if current in self._clips:
                return current
            seen.add(current)
            current = self._fallbacks.get(current)
        return SAFE_CLIP if SAFE_CLIP in self._clips else None

    @classmethod
    def from_manifest(cls, manifest: dict[str, object]) -> "ClipLibrary":
        raw = manifest.get("clips")
        names: list[str] = []
        if isinstance(raw, dict):
            names = list(raw.keys())
        elif isinstance(raw, list):
            names = [str(item.get("name") if isinstance(item, dict) else item) for item in raw]
        fallbacks = manifest.get("fallbacks")
        return cls(names, fallbacks if isinstance(fallbacks, dict) else None)


class AnimationController(ABC):
    """The interface the Panda3D controller will implement in M3."""

    @property
    @abstractmethod
    def available(self) -> ClipLibrary: ...

    @property
    @abstractmethod
    def current(self) -> str | None:
        """Clip currently playing, after fallback resolution."""

    @property
    @abstractmethod
    def requested(self) -> str | None:
        """Clip that was last asked for, before fallback resolution."""

    @abstractmethod
    def play(self, clip: str, fade: float = 0.25) -> str | None:
        """Play *clip*, returning the clip actually started (or None)."""

    @abstractmethod
    def update(self, dt: float) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...


@dataclass
class ProceduralSample:
    """Values the renderer applies directly when no rig is available."""

    breath_scale: float = 1.0
    breath_offset: float = 0.0
    blink: float = 0.0
    wing_flap: float = 0.0


class ProceduralMotion:
    """Breathing and blinking that need no bones, skin or clips.

    Used as the always-available fallback, and layered on top of real clips in M3.
    """

    def __init__(
        self,
        breath_hz: float = 0.25,
        breath_amplitude: float = 0.006,
        blink_interval: tuple[float, float] = (3.0, 8.0),
        blink_duration: float = 0.12,
        rng: random.Random | None = None,
    ) -> None:
        self.breath_hz = breath_hz
        self.breath_amplitude = breath_amplitude
        self.blink_interval = blink_interval
        self.blink_duration = blink_duration
        self._rng = rng or random.Random(0)
        self._blinks: list[float] = []
        self._next_blink = self._rng.uniform(*blink_interval)

    def _ensure_blinks(self, t: float) -> None:
        while self._next_blink <= t + 1.0:
            self._blinks.append(self._next_blink)
            self._next_blink += self._rng.uniform(*self.blink_interval)

    def blink_amount(self, t: float) -> float:
        """0 = eyes open, 1 = fully closed. Triangular 0.12 s blink."""
        self._ensure_blinks(t)
        for start in self._blinks:
            if start <= t < start + self.blink_duration:
                phase = (t - start) / self.blink_duration
                return 1.0 - abs(phase * 2.0 - 1.0)
        return 0.0

    def sample(self, t: float, sleeping: bool = False) -> ProceduralSample:
        rate = 0.12 if sleeping else self.breath_hz
        phase = math.sin(t * rate * 2.0 * math.pi)
        amplitude = self.breath_amplitude * (1.6 if sleeping else 1.0)
        return ProceduralSample(
            breath_scale=1.0 + phase * amplitude,
            breath_offset=phase * amplitude * 0.5,
            blink=1.0 if sleeping else self.blink_amount(t),
            wing_flap=abs(math.sin(t * 6.0 * 2.0 * math.pi)),
        )


class PlaceholderAnimationController(AnimationController):
    """Clip-less controller: records intent, never pretends an animation exists.

    `mode` is ``"clips"`` when the requested clip really exists, ``"fallback"``
    when a substitute was used and ``"procedural"`` when nothing exists at all.
    The renderer can show that state honestly instead of faking a pose.
    """

    def __init__(self, library: ClipLibrary | None = None, procedural: ProceduralMotion | None = None):
        self._library = library or ClipLibrary([])
        self._procedural = procedural or ProceduralMotion()
        self._current: str | None = None
        self._requested: str | None = None
        self._mode: str = "procedural"
        self._time = 0.0
        self.history: list[tuple[str | None, str]] = []
        self.last_sample = ProceduralSample()

    # -- properties --------------------------------------------------------
    @property
    def available(self) -> ClipLibrary:
        return self._library

    @property
    def current(self) -> str | None:
        return self._current

    @property
    def requested(self) -> str | None:
        return self._requested

    @property
    def mode(self) -> str:
        return self._mode

    # -- interface ---------------------------------------------------------
    def play(self, clip: str, fade: float = 0.25) -> str | None:
        self._requested = clip
        resolved = self._library.resolve(clip)
        if resolved is None:
            self._current = None
            self._mode = "procedural"
        elif resolved == clip:
            self._current = resolved
            self._mode = "clips"
        else:
            self._current = resolved
            self._mode = "fallback"
        self.history.append((resolved, self._mode))
        return resolved

    def update(self, dt: float) -> None:
        if dt <= 0:
            return
        self._time += dt
        self.last_sample = self._procedural.sample(self._time, sleeping=self._current == "sleep")

    def stop(self) -> None:
        self._current = None
        self._requested = None
        self._mode = "procedural"

    def snapshot(self) -> dict[str, object]:
        return {
            "requested": self._requested,
            "current": self._current,
            "mode": self._mode,
            "time": round(self._time, 3),
            "clips": list(self._library.names),
        }


class EventDrivenAnimator:
    """Feeds state-machine events into an AnimationController.

    Keeping this separate means the behaviour code never touches the renderer
    and the animation code never knows about states.
    """

    def __init__(self, controller: AnimationController) -> None:
        self.controller = controller
        self.last_error: str | None = None

    def handle(self, events: Iterable[object]) -> list[str]:
        from lumi.character.state_machine import ClipRequested

        played: list[str] = []
        for event in events:
            if not isinstance(event, ClipRequested):
                continue
            try:
                result = self.controller.play(event.clip)
            except Exception as exc:  # noqa: BLE001 - an animation failure must not kill the pet
                self.last_error = f"{type(exc).__name__}: {exc}"
                continue
            if result:
                played.append(result)
        return played

    def update(self, dt: float) -> None:
        self.controller.update(dt)
