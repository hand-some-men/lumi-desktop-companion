"""Headless M0 render evidence: real 3D geometry, real per-pixel alpha.

Renders the spike scene offscreen, writes PNGs, and checks the alpha channel
pixel by pixel. Runs on any machine with a graphics pipe (no display needed if
--driver p3tinydisplay is used).

Usage:
    python tools/m0_render_check.py                 # auto driver
    python tools/m0_render_check.py --driver p3tinydisplay
    python tools/m0_render_check.py --frames 240 --json out.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lumi.rendering.offscreen import OffscreenRenderer, RenderConfig  # noqa: E402


def alpha_counts(pnm) -> dict[str, int]:
    width, height = pnm.getXSize(), pnm.getYSize()
    transparent = partial = opaque = 0
    for y in range(height):
        for x in range(width):
            # PNMImage alpha is a float in 0..1, not 0..255.
            a = pnm.getAlpha(x, y)
            if a <= 0.0:
                transparent += 1
            elif a >= 0.99:
                opaque += 1
            else:
                partial += 1
    return {"transparent": transparent, "partial": partial, "opaque": opaque}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=int, default=120)
    parser.add_argument("--size", type=int, default=320)
    parser.add_argument("--driver", default=None, help="p3tinydisplay | pandagl | None")
    parser.add_argument("--png", default="docs/m0_capture_render.png")
    parser.add_argument("--json", default="docs/m0_results_render.json")
    args = parser.parse_args()

    cfg = RenderConfig(width=args.size, height=args.size, driver=args.driver)
    renderer = OffscreenRenderer(cfg)
    results: dict[str, object] = {"config": {"size": args.size, "frames": args.frames}}
    checks: list[dict[str, object]] = []

    try:
        renderer.start()
    except Exception as exc:  # noqa: BLE001 - reported, not swallowed
        print(f"START FAILED: {type(exc).__name__}: {exc}")
        results["start_error"] = f"{type(exc).__name__}: {exc}"
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(results, indent=2))
        return 2

    try:
        renderer.render_frames(args.frames)
        png = renderer.grab_png(args.png)
        pnm = renderer.grab_pnm()
        counts = alpha_counts(pnm)
        total = pnm.getXSize() * pnm.getYSize()

        # Corner must be transparent: proves the background alpha is really 0.
        corner = [
            pnm.getAlpha(1, 1),
            pnm.getAlpha(pnm.getXSize() - 2, 1),
            pnm.getAlpha(1, pnm.getYSize() - 2),
            pnm.getAlpha(pnm.getXSize() - 2, pnm.getYSize() - 2),
        ]
        centre = pnm.getAlpha(pnm.getXSize() // 2, pnm.getYSize() // 2)

        checks.append(
            {
                "check": "background is transparent",
                "detail": f"corner alpha values {corner}",
                "pass": all(a == 0 for a in corner),
            }
        )
        checks.append(
            {
                "check": "geometry is drawn and opaque",
                "detail": f"opaque pixels {counts['opaque']} / {total}",
                "pass": counts["opaque"] > total * 0.05,
            }
        )
        checks.append(
            {
                "check": "semi-transparent pixels exist (not binary alpha)",
                "detail": f"partial pixels {counts['partial']}",
                "pass": counts["partial"] > 0,
            }
        )
        checks.append(
            {
                "check": "centre pixel belongs to the model",
                "detail": f"centre alpha {centre}",
                "pass": centre > 0,
            }
        )
        # A mostly transparent PNG is legitimately tiny, so verify content by
        # reading it back instead of trusting the file size.
        from panda3d.core import Filename, PNMImage

        reread = PNMImage()
        ok = reread.read(Filename.fromOsSpecific(str(png))) and reread.hasAlpha()
        visible = 0
        if ok:
            visible = sum(
                1
                for y in range(0, reread.getYSize(), 2)
                for x in range(0, reread.getXSize(), 2)
                if reread.getAlpha(x, y) > 0.5
            )
        checks.append(
            {
                "check": "PNG on disk round-trips with visible pixels",
                "detail": f"{png.name} = {png.stat().st_size if png.exists() else 0} bytes, "
                f"{visible} sampled visible pixels",
                "pass": bool(ok and visible > 0),
            }
        )

        results.update(
            {
                "renderer": renderer.describe(),
                "frame_stats": renderer.stats.as_dict(),
                "alpha": counts,
                "checks": checks,
            }
        )
    finally:
        renderer.shutdown()

    Path(args.json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json).write_text(json.dumps(results, indent=2))

    print("=== M0 render check ===")
    print(f"driver            : {results['renderer']['driver']}")
    print(f"frames rendered   : {results['frame_stats']['frames']}")
    print(
        "frame time (ms)   : mean {mean_ms} | p50 {p50_ms} | p95 {p95_ms} | max {max_ms}".format(
            **results["frame_stats"]
        )
    )
    print(f"alpha             : {results['alpha']}")
    print(f"capture           : {args.png}")
    failures = 0
    for check in checks:
        status = "PASS" if check["pass"] else "FAIL"
        if not check["pass"]:
            failures += 1
        print(f"[{status}] {check['check']} - {check['detail']}")
    print(f"result: {'ALL PASS' if failures == 0 else f'{failures} FAILED'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
