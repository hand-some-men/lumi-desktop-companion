"""Offscreen Panda3D renderer for the Lumi overlay (M0 spike).

No native Panda window is ever created. The scene is rendered into an RGBA
graphics buffer that is copied to RAM, so the result can be composited into a
frameless translucent Qt window by the desktop layer.

Verified behaviour is recorded in docs/WINDOWS_OVERLAY_SPIKE.md. Do not assume
any Windows-specific behaviour from this module alone.
"""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path

from panda3d.core import (
    Camera,
    GraphicsOutput,
    GraphicsPipeSelection,
    GraphicsPipe,
    LVecBase4f,
    NodePath,
    PNMImage,
    PerspectiveLens,
    Texture,
    WindowProperties,
    loadPrcFileData,
)

from lumi.rendering.scene import build_spike_scene


@dataclass(frozen=True)
class RenderConfig:
    """Everything that affects the offscreen target."""

    width: int = 320
    height: int = 320
    depth_bits: int = 24
    samples: int = 1
    driver: str | None = None  # None = let Panda choose (pandagl on Windows)


@dataclass
class FrameStats:
    samples: list[float] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.samples)

    @property
    def mean_ms(self) -> float:
        return statistics.fmean(self.samples) * 1000.0 if self.samples else 0.0

    def percentile_ms(self, pct: float) -> float:
        if not self.samples:
            return 0.0
        ordered = sorted(self.samples)
        idx = min(len(ordered) - 1, max(0, round(pct / 100.0 * (len(ordered) - 1))))
        return ordered[idx] * 1000.0

    def as_dict(self) -> dict[str, float | int]:
        return {
            "frames": self.count,
            "mean_ms": round(self.mean_ms, 3),
            "p50_ms": round(self.percentile_ms(50), 3),
            "p95_ms": round(self.percentile_ms(95), 3),
            "max_ms": round(self.percentile_ms(100), 3),
        }


class OffscreenRenderer:
    """Owns the Panda pipe, the RGBA buffer, and the spike scene."""

    def __init__(self, config: RenderConfig | None = None) -> None:
        self.config = config or RenderConfig()
        self.stats = FrameStats()
        self.base = None
        self.buffer: GraphicsOutput | None = None
        self.texture: Texture | None = None
        self.camera: NodePath | None = None
        self.scene_root: NodePath | None = None
        self.driver_used: str | None = None
        self.uses_texture = False
        self._started = False

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> "OffscreenRenderer":
        if self._started:
            return self

        # Must be set before ShowBase builds the graphics engine.
        loadPrcFileData("", "window-type none")
        loadPrcFileData("", "audio-library-name null")
        loadPrcFileData("", "notify-level warning")
        if self.config.driver:
            loadPrcFileData("", f"load-display {self.config.driver}")

        from direct.showbase.ShowBase import ShowBase

        self.base = ShowBase()

        # With window-type none, ShowBase never builds a pipe, so ask for one
        # directly. The prc load-display setting chooses which driver it is.
        pipe = self.base.pipe or GraphicsPipeSelection.getGlobalPtr().makeDefaultPipe()
        if pipe is None:
            raise RuntimeError(
                "Panda3D could not create a graphics pipe. On a headless machine "
                "try --driver p3headlessgl or --driver p3tinydisplay."
            )
        self.driver_used = pipe.getInterfaceName()

        fbp = self._framebuffer_properties()
        props = WindowProperties()
        props.setSize(self.config.width, self.config.height)
        props.setTitle("lumi-offscreen")

        buf = self.base.graphicsEngine.makeOutput(
            pipe, "lumi-fbo", 0, fbp, props, GraphicsPipe.BFRefuseWindow
        )
        if buf is None:
            raise RuntimeError(
                f"makeOutput failed for driver {self.driver_used}: no RGBA buffer"
            )
        self.buffer = buf

        tex = Texture("lumi-color")
        tex.setFormat(Texture.FRgba8)
        tex.setMinfilter(Texture.FTLinear)
        tex.setMagfilter(Texture.FTLinear)
        # Software pipes (p3tinydisplay) cannot attach a render texture. In that
        # case readback goes straight from the framebuffer via getScreenshot().
        if buf.addRenderTexture(tex, GraphicsOutput.RTMCopyRam, GraphicsOutput.RTPColor):
            self.texture = tex
            self.uses_texture = True
        else:
            self.texture = None
            self.uses_texture = False

        cam = Camera("lumi-camera")
        lens = PerspectiveLens()
        lens.setFov(38, 38)
        lens.setNearFar(0.1, 100.0)
        cam.setLens(lens)
        cam_np = self.base.render.attachNewNode(cam)
        cam_np.setPos(0, -6.5, 1.9)
        self.camera = cam_np

        # A camera is bound to a display region, not to the buffer itself.
        region = buf.makeDisplayRegion()
        region.setCamera(cam_np)
        region.setActive(True)

        buf.setClearColorActive(True)
        buf.setClearColor(LVecBase4f(0, 0, 0, 0))  # transparent background

        self.scene_root = self.base.render.attachNewNode("m0-scene")
        self._cube, self._card = build_spike_scene(self.scene_root, cam_np)

        self._started = True
        # One warm-up frame: shader/state setup costs are not frame time.
        self.base.graphicsEngine.renderFrame()
        return self

    def _framebuffer_properties(self):
        from panda3d.core import FrameBufferProperties

        fbp = FrameBufferProperties()
        fbp.setRgbaBits(8, 8, 8, 8)
        fbp.setColorBits(32)
        fbp.setAlphaBits(8)
        fbp.setDepthBits(self.config.depth_bits)
        fbp.setMultisamples(self.config.samples)
        return fbp

    def shutdown(self) -> None:
        try:
            if self.buffer is not None:
                self.buffer.clearRenderTextures()
            if self.base is not None:
                self.base.graphicsEngine.removeAllWindows()
                self.base.destroy()
        finally:
            self.buffer = None
            self.texture = None
            self.base = None
            self._started = False

    # -- rendering ---------------------------------------------------------
    def spin(self, frame_index: int, degrees_per_frame: float = 1.5) -> None:
        if self._cube is not None:
            self._cube.setH(self._cube.getH() + degrees_per_frame)

    def render_frame(self) -> float:
        if not self._started:
            raise RuntimeError("renderer.start() must be called first")
        t0 = time.perf_counter()
        self.base.graphicsEngine.renderFrame()
        dt = time.perf_counter() - t0
        self.stats.samples.append(dt)
        return dt

    def render_frames(self, count: int) -> None:
        for i in range(count):
            self.spin(i)
            self.render_frame()

    # -- output ------------------------------------------------------------
    def grab_pnm(self) -> PNMImage:
        """Copy the colour buffer (including alpha) into a PNMImage."""
        pnm = PNMImage()
        if self.texture is not None:
            try:
                if self.texture.store(pnm):
                    if not pnm.hasAlpha():
                        pnm.addAlpha()
                    return pnm
            except Exception:
                pass  # fall through to the screenshot path
        if self.buffer is not None:
            shot = PNMImage()
            if self.buffer.getScreenshot(shot):
                if not shot.hasAlpha():
                    shot.addAlpha()
                return shot
        raise RuntimeError("could not read back the offscreen buffer")

    def grab_png(self, path: str | Path) -> Path:
        pnm = self.grab_pnm()
        out = Path(path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        from panda3d.core import Filename

        if not pnm.write(Filename.fromOsSpecific(str(out))):
            raise RuntimeError(f"failed to write {out}")
        return out

    # -- diagnostics -------------------------------------------------------
    def describe(self) -> dict[str, object]:
        return {
            "driver": self.driver_used,
            "width": self.config.width,
            "height": self.config.height,
            "samples": self.config.samples,
            "has_alpha_texture": self.uses_texture,
            "readback": "render_texture" if self.uses_texture else "framebuffer_screenshot",
        }
