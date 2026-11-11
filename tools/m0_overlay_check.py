"""M0 overlay evidence: render offscreen, composite into a QWidget, measure it.

The Qt-side checks run anywhere Qt runs. The four Windows-only checks are
reported as SKIPPED everywhere else and never counted as passes.

Usage:
    python tools/m0_overlay_check.py --driver p3tinydisplay
    python tools/m0_overlay_check.py --driver pandagl --frames 60 --json out.json
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


WINDOWS_CHECKS = (
    ("wns_layered", "Window is a layered top-level window (WS_EX_LAYERED)"),
    ("wns_clickthrough", "Click-through passes clicks to the app underneath"),
    ("wns_no_taskbar", "Overlay never appears in the taskbar or Alt-Tab"),
    ("wns_topmost_over_fullscreen", "Stays above borderless fullscreen games"),
)


def _windows_only(name: str, note: str) -> dict[str, object]:
    return {"check": name, "status": "SKIPPED", "detail": note}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=int, default=120)
    parser.add_argument("--size", type=int, default=320)
    parser.add_argument("--driver", default=None)
    parser.add_argument("--png", default="docs/m0_capture_overlay.png")
    parser.add_argument("--json", default="docs/m0_results_overlay.json")
    args = parser.parse_args()

    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])

    from lumi.desktop.overlay import LumiOverlay
    from lumi.rendering.composite import alpha_histogram, qimage_from_pnm
    from lumi.rendering.offscreen import OffscreenRenderer, RenderConfig

    results: dict[str, object] = {
        "config": {"size": args.size, "frames": args.frames},
        "platform": platform.system(),
        "checks": [],
    }
    checks: list[dict[str, object]] = results["checks"]  # type: ignore[assignment]

    renderer = OffscreenRenderer(RenderConfig(width=args.size, height=args.size, driver=args.driver))
    overlay = LumiOverlay(args.size, args.size)

    frame_times: list[float] = []
    try:
        renderer.start()
    except Exception as exc:  # noqa: BLE001
        print(f"START FAILED: {type(exc).__name__}: {exc}")
        results["start_error"] = f"{type(exc).__name__}: {exc}"
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(results, indent=2))
        return 2

    try:
        overlay.show()
        app.processEvents()

        for _ in range(args.frames):
            renderer.spin(0)
            t0 = time.perf_counter()
            renderer.render_frame()
            pnm = renderer.grab_pnm()
            image = qimage_from_pnm(pnm)
            overlay.set_frame(image)
            overlay.repaint()
            app.processEvents()
            frame_times.append(time.perf_counter() - t0)

        info = overlay.describe()
        results["overlay"] = info

        final_pnm = renderer.grab_pnm()
        final_image = qimage_from_pnm(final_pnm)
        histogram = alpha_histogram(final_image)
        results["composited_alpha"] = histogram
        results["frame_stats"] = renderer.stats.as_dict()
        total = final_image.width() * final_image.height()

        checks.append(
            {
                "check": "qt_translucent_window",
                "status": "PASS" if info["translucent_attr"] else "FAIL",
                "detail": "WA_TranslucentBackground set" if info["translucent_attr"] else "not set",
            }
        )
        checks.append(
            {
                "check": "qt_frameless_topmost_toolwindow",
                "status": "PASS"
                if (info["frameless"] and info["top_most"] and info["tool_window"])
                else "FAIL",
                "detail": f"frameless={info['frameless']} topmost={info['top_most']} tool={info['tool_window']}",
            }
        )
        checks.append(
            {
                "check": "frame_composited_into_qimage",
                "status": "PASS" if histogram["opaque"] + histogram["partial"] > 0 else "FAIL",
                "detail": f"opaque={histogram['opaque']} partial={histogram['partial']} of {total}",
            }
        )
        checks.append(
            {
                "check": "background_remains_transparent_after_compositing",
                "status": "PASS" if histogram["transparent"] > 0 else "FAIL",
                "detail": f"transparent pixels {histogram['transparent']} / {total}",
            }
        )
        mean = sum(frame_times) / len(frame_times) if frame_times else 0.0
        checks.append(
            {
                "check": "composite_loop_runs",
                "status": "PASS" if len(frame_times) == args.frames else "FAIL",
                "detail": f"{len(frame_times)} frames, mean composite {mean * 1000:.2f} ms",
            }
        )

        overlay.grab().save(args.png)
        results["capture"] = args.png

        # Windows behaviour is unverified unless this really is Windows, and even
        # then these rows stay manual until someone looks at them.
        note = (
            "requires Windows; not measured on this machine"
            if platform.system() != "Windows"
            else "requires manual visual confirmation on Windows"
        )
        for key, label in WINDOWS_CHECKS:
            checks.append(_windows_only(key, f"{label} - {note}"))
    finally:
        overlay.close()
        renderer.shutdown()

    Path(args.json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json).write_text(json.dumps(results, indent=2))

    print("=== M0 overlay check ===")
    print(f"platform          : {results['platform']}")
    print(f"driver            : {results['overlay'].get('driver') if 'overlay' in results else args.driver}")
    print(f"frames            : {results.get('frame_stats', {}).get('frames')}")
    print(f"alpha             : {results.get('composited_alpha')}")
    counts = {"PASS": 0, "FAIL": 0, "SKIPPED": 0}
    for check in checks:
        counts[check["status"]] += 1  # type: ignore[index]
        print(f"[{check['status']}] {check['check']} - {check['detail']}")
    print(f"result: {counts['PASS']} PASS, {counts['FAIL']} FAIL, {counts['SKIPPED']} SKIPPED")
    if counts["SKIPPED"]:
        print("NOTE: Windows-only rows are unverified; M0 Windows acceptance remains PENDING.")
    return 0 if counts["FAIL"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
