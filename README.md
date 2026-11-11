# Lumi — 3D Windows Desktop Companion

Lumi is a desktop pet: a real-time 3D unicorn-pegasus (your original character
design) that lives on the Windows desktop as a transparent, always-on-top window.

**Current status: Milestone M0 only, and M0 is not signed off yet.**
M0 is the "can we even do a transparent 3D overlay on Windows?" experiment. There
is no character model, no animation, no settings screen and no installer. Nothing
in this repository should be mistaken for a working desktop pet.

Read `docs/WINDOWS_OVERLAY_SPIKE.md` for what has actually been run and what has not.

---

## What exists right now

| Path | What it is |
|---|---|
| `src/lumi/rendering/offscreen.py` | Panda3D renders into an offscreen RGBA buffer (no native window) |
| `src/lumi/rendering/scene.py` | Debug geometry (cube + translucent card) used only to prove the pipeline |
| `src/lumi/rendering/composite.py` | Converts a rendered frame into a Qt image, source-over compositing |
| `src/lumi/desktop/overlay.py` | Frameless, translucent, always-on-top, click-through-capable window |
| `src/lumi/desktop/windows_report.py` | Read-only Windows facts (window styles, DPI, idle time, CPU) |
| `tools/m0_render_check.py` | Headless render + per-pixel alpha verification, writes a PNG |
| `tools/m0_overlay_check.py` | Live overlay run that produces the M0 acceptance record |
| `src/lumi/character/rig_contract.py` | Bone hierarchy, clip table and palette the 3D asset must satisfy |
| `src/lumi/character/state_machine.py` | Behaviour state machine (pure Python, no renderer needed) |
| `src/lumi/character/animation.py` | Animation controller interface with placeholder-safe fallbacks |
| `tools/validate_glb.py` | Checks a GLB against the rig, clip and colour contract |
| `tools/glb_builder.py` | Builds synthetic GLBs used to test the validator |
| `tests/` | Automated tests for alpha, compositing, behaviour, animation and GLB validation |

The cube in `scene.py` is **not Lumi**. It is a debug object and is labelled as
such in code. It exists so the pipeline can be measured before any character work.

---

## Setup (beginner friendly, Windows 10/11)

1. Install **Python 3.12** from python.org. On the first screen of the installer,
   tick **"Add python.exe to PATH"**.
2. Open **PowerShell** in this folder (Shift + right-click inside the folder →
   "Open PowerShell window here").
3. Create a virtual environment and install the two libraries:

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   python -m pip install panda3d PySide6-Essentials pytest
   ```

   If PowerShell refuses to run the activate script, run this once and try again:
   `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

4. Check it works:

   ```powershell
   python -m pytest
   ```

## Run the M0 checks

Two commands, in this order. Both print PASS/FAIL per check.

**1. Rendering and transparency (no window shown):**

```powershell
python tools\m0_render_check.py --frames 120
```

This renders the debug scene 120 times, saves `docs/m0_capture_render.png`, and
verifies pixel by pixel that the background alpha is 0, the object is opaque and
the translucent card produces in-between alpha values.

**2. The actual desktop overlay (this is the M0 decision):**

```powershell
python tools\m0_overlay_check.py --seconds 15
```

A 320×320 borderless window appears near the bottom-right of the screen showing
the rotating debug object over your desktop. While it runs, check with your own
eyes:

- Is the area around the object **truly transparent** (no grey box, no black
  rectangle)? Look at it over a white window, a dark window and your wallpaper.
- Does it stay **above** other windows when you click them?
- Is it **absent from the taskbar and Alt-Tab**?
- Does dragging a window under it look right?

Then try the click-through mode:

```powershell
python tools\m0_overlay_check.py --seconds 15 --click-through
```

Clicks should pass through to whatever is underneath.

The tool writes `docs/m0_results_overlay.json` with the window styles Windows
actually applied, DPI, monitor list, system idle time and CPU use. Send that file
back — it is the evidence M0 needs.

---

## What "M0 done" means

M0 is finished when, on a real Windows 10 or 11 machine:

1. The overlay shows the 3D object with no opaque rectangle around it.
2. It stays on top.
3. It stays out of the taskbar and Alt-Tab.
4. Click-through passes clicks through.
5. It survives a display-scale change (100% → 150%) without breaking.
6. Idle CPU is low enough to leave running all day (target: under 1%).
7. The results file records the Windows build, GPU and scaling.

Until that evidence exists, the architecture choice (offscreen render composited
into Qt, versus a Panda-owned window with Win32 layering) stays open.

---

## Character reference

Lumi is a lavender-white unicorn-pegasus with a purple/blue/pink mane and tail, a
golden spiral horn with a cyan tip, feathered wings, large violet eyes and gold
accessories. Colours: coat `#EFE6FF`, mane `#B64BFF` / `#4EC8FF` / `#FF6EC7`,
deep purple `#8A5CFF`, gold `#FFC94D`, cyan accent `#00E6FF`.

No 3D model of Lumi exists yet. When one is produced it must be a rigged glTF/GLB
matching the reference sheet; a static image will never be used in its place.

---

## Troubleshooting

- **"No graphics pipe" / renderer will not start** — Panda3D needs a working
  graphics driver. Update your GPU driver; on a remote-desktop session 3D may be
  unavailable.
- **The window shows a solid rectangle** — that is the exact failure M0 is
  looking for. Record your GPU, driver version and Windows build in an issue.
- **Nothing appears** — check the console output; the tools report every failure
  instead of hiding it.

---

## Character, rig and behaviour work (platform independent)

These parts do not need Windows and are finished and unit tested:

- `docs/CHARACTER_SPEC.md` — the complete character asset specification.
- `docs/RIG_AND_ANIMATION.md` — rig hierarchy, bone naming, clip contract.
- `docs/MODEL_IMPORT.md` — how a Blender-made Lumi gets in.
- Behaviour state machine, animation interfaces and GLB validation, with tests.

Validate any candidate model:

```powershell
python tools\validate_glb.py assets\models\lumi.glb --strict
```

**There is still no Lumi 3D model.** The contract exists so that one can be
checked the moment it arrives; nothing in this repository should be read as
Lumi being modelled, rigged or animated.
