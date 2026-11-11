# M0 — Windows transparency and windowing proof-of-concept

**Milestone status: NOT SIGNED OFF. Code complete, partially executed.**
The Windows-specific half of M0 cannot be run outside Windows, and no Windows
machine was available. Everything below is separated into *actually measured*
and *not yet measured*.

Date of this record: 2026-11-11
Executed on: Ubuntu 24.04 (Linux), Python 3.12.3, Panda3D 1.10.16, PySide6 6.12.0,
no GPU, no X server, no root. **This is not the target platform.**

---

## 1. Strategy under test

Option B from the architecture document: **render offscreen with Panda3D, composite
the RGBA frame into a frameless translucent Qt window.**

Option A (a Panda-owned window with Windows layered-window styles) is not implemented.
The comparison stays open until Option B is measured on Windows.

## 2. What was built

| File | Purpose |
|---|---|
| `src/lumi/rendering/offscreen.py` | Panda3D RGBA buffer, no native window, frame timing, readback |
| `src/lumi/rendering/scene.py` | Debug geometry only (cube + translucent card) — not Lumi |
| `src/lumi/rendering/composite.py` | Frame → QImage, source-over compositing, alpha histogram |
| `src/lumi/desktop/overlay.py` | Frameless, translucent, always-on-top, tool-window, click-through-capable |
| `src/lumi/desktop/windows_report.py` | Read-only Windows facts: window styles, DPI, idle time, CPU, tray |
| `tools/m0_render_check.py` | Headless render + per-pixel alpha verification |
| `tools/m0_overlay_check.py` | Live overlay run + M0 acceptance record (JSON) |
| `tests/` | 12 automated tests (alpha correctness, compositing, overlay flags) |

## 3. Actually measured (Linux, software rasteriser)

`python tools/m0_render_check.py --frames 40 --size 160 --driver p3tinydisplay`

```
driver            : TinyPanda (software, no GPU)
frames rendered   : 40
frame time (ms)   : mean 0.119 | p50 0.113 | p95 0.157 | max 0.189
alpha histogram   : transparent 20929 | partial 1482 | opaque 3189  (of 25600 px)
[PASS] background is transparent            corners 0.0, 0.0, 0.0, 0.0
[PASS] geometry is drawn and opaque         3189 opaque pixels
[PASS] semi-transparent pixels exist        1482 partial pixels (blending works)
[PASS] centre pixel belongs to the model    alpha 1.0
[PASS] PNG round-trips with visible pixels  529 bytes, 1177 sampled visible pixels
```

`python tools/m0_overlay_check.py --seconds 4 --size 160 --fps 20` (Qt offscreen platform)

```
[PASS] offscreen renderer started                 TinyPanda
[PASS] frames composited into the overlay         76 frames at target 20 fps
[PASS] frameless + always-on-top + tool window    flags confirmed
[PASS] translucency attribute accepted            True
[PASS] click-through mode matches request         requested False, got False
[SKIP] window handle exists                       windows only
[SKIP] topmost style set by Windows               windows only
[SKIP] not listed in the taskbar                  windows only
[SKIP] per-window DPI readable                    windows only
effective fps: 20.0   frame mean 0.352 ms, p95 0.492 ms
```

`python -m pytest -q` → **12 passed, 0 failed.**

Evidence files: `docs/m0_capture_render.png`, `docs/m0_capture_overlay.png`,
`docs/m0_results_render.json`, `docs/m0_results_overlay.json`.

### What these results do and do not prove

They prove: the 3D scene renders into an RGBA buffer, the buffer has real per-pixel
alpha (background 0, geometry 1, blended surfaces in between), the frame converts into
a Qt image and is painted into the overlay widget at a stable rate, and the window is
created with the intended flags.

They do **not** prove anything about Windows: alpha compositing over the desktop,
z-order persistence, taskbar/Alt-Tab exclusion, OS-level click-through, DPI changes or
real GPU frame times. The frame times above come from a software rasteriser and are
meaningless as performance numbers for a Windows machine.

## 4. Not yet measured — requires a real Windows 10/11 machine

1. No opaque rectangle around transparent pixels, over wallpaper / white / dark windows.
2. Window stays above other windows after focus changes and window switches.
3. Window absent from the taskbar and Alt-Tab.
4. Click-through actually passes clicks to the window underneath.
5. Display scaling 100% ↔ 150% and multi-monitor behaviour.
6. CPU use while idle (render-on-demand not implemented yet — the spike renders on a timer).
7. GPU/driver-specific behaviour (Intel, NVIDIA, AMD, and hybrid laptops).

Run `python tools\m0_overlay_check.py --seconds 15` and
`python tools\m0_overlay_check.py --seconds 15 --click-through` on Windows and keep
`docs/m0_results_overlay.json` plus a screenshot for each background test.

## 5. Defects found and fixed during the spike

Recorded because they will bite again in M1:

1. `panda3d.core.Color4` does not exist — colours are `LVecBase4f`.
2. With `window-type none`, ShowBase never creates a graphics pipe; the pipe must be
   requested from `GraphicsPipeSelection.makeDefaultPipe()`.
3. A camera is bound to a **display region**, not to the buffer (`setCamera` does not
   exist on `GraphicsOutput`).
4. Software pipes cannot attach a render texture; readback falls back to
   `getScreenshot()`. Recorded per-renderer as `readback`.
5. `PNMImage.getAlpha()` returns a float 0..1, not 0..255. A checker comparing against
   254 silently reported "no opaque pixels".
6. A `QWidget` requires `QApplication`; using `QGuiApplication` aborts the process.
   This crashed the test suite until fixed.
7. **Qt will not clear `WindowTransparentForInput` on a window created with it.**
   `setWindowFlag(flag, False)`, an explicit flag mask and `setWindowFlags` are all
   silently ignored. Consequence: `is_click_through` always reports the real flag state,
   and callers must not assume a runtime toggle took effect. M1 must recreate the
   overlay window when the setting changes (or discover that Windows behaves differently).
8. A mostly-transparent PNG is legitimately a few hundred bytes — file size is not
   evidence of content. The check now re-reads the pixels.

## 6. Environment limitations encountered

- No Windows machine and no X server in the execution environment, hence the
  software pipe (`p3tinydisplay`). `p3headlessgl` was present but EGL could not
  initialise without a GPU/DRM device.
- No root access, so Qt's system libraries were fetched into user space to run the
  Qt half. This is a workaround for the test machine only and is not part of the app.

## 7. Recommendation and next step

The pipeline design holds up: one RGBA buffer, one compositing path, clean separation
between renderer and window. Nothing in the Linux evidence argues against Option B.

**M0 is not complete until items 1–7 in section 4 are measured on Windows.**
M1 (application scaffold, SQLite settings, tray, placeholder character) must not start
before that, because the overlay strategy it depends on would still be unproven.

If the Windows test fails, the next step is Option A: a Panda-owned window made
transparent through Win32 layered-window styles, measured with the same checks.
