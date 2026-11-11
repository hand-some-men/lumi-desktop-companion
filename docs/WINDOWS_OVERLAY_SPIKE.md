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
