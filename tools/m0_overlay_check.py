"""M0 overlay check: composite live offscreen frames into the translucent window.

This tool is the acceptance harness for M0. On Windows it also collects the
facts the milestone record needs (window styles, DPI, monitor layout, idle
input, CPU use). On other platforms the Windows rows are reported as SKIPPED -
that is not a pass.

Usage:
    python tools/m0_overlay_check.py --seconds 10
    python tools/m0_overlay_check.py --seconds 10 --click-through
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QRect, Qt, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402 (QWidget needs this, not QGuiApplication)

from lumi.desktop import windows_report  # noqa: E402
from lumi.rendering.composite import pnm_to_qimage  # noqa: E402
from lumi.rendering.offscreen import OffscreenRenderer, RenderConfig  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--size", type=int, default=320)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--driver", default=None)
    parser.add_argument("--click-through", action="store_true")
    parser.add_argument("--json", default="docs/m0_results_overlay.json")
    parser.add_argument("--capture", default="docs/m0_capture_overlay.png")
    args = parser.parse_args()

    results: dict[str, object] = {
        "environment": windows_report.environment(),
        "host": {"platform": platform.platform()},
        "args": vars(args),
        "checks": [],
    }
    checks: list[dict[str, object]] = results["checks"]  # type: ignore[assignment]

    app = QApplication(sys.argv[:1])

    from lumi.desktop.overlay import LumiOverlay

    renderer = OffscreenRenderer(RenderConfig(width=args.size, height=args.size, driver=args.driver))
    start_error = None
    try:
        renderer.start()
    except Exception as exc:  # noqa: BLE001 - reported honestly
        start_error = f"{type(exc).__name__}: {exc}"

    results["renderer"] = renderer.describe()
    if start_error:
        results["start_error"] = start_error
        print(f"RENDER START FAILED: {start_error}")

    overlay = LumiOverlay(args.size, args.size, click_through=args.click_through)
    screens = app.screens()
    target = screens[0].availableGeometry() if screens else QRect(0, 0, args.size, args.size)
    overlay.place(
        QRect(
            target.right() - args.size - 40,
            target.bottom() - args.size - 40,
            args.size,
            args.size,
        )
    )
    overlay.show()
    overlay.keep_on_top()

    driven_frames = 0

    def tick() -> None:
        nonlocal driven_frames
        if renderer.buffer is None:
            return
        renderer.spin(driven_frames)
        renderer.render_frame()
        try:
            image = pnm_to_qimage(renderer.grab_pnm())
        except Exception as exc:  # noqa: BLE001
            results.setdefault("frame_errors", []).append(f"{type(exc).__name__}: {exc}")
            return
        overlay.set_frame(image)
        driven_frames += 1

    timer = QTimer()
    timer.timeout.connect(tick)
    if start_error is None:
        timer.start(max(1, int(1000 / args.fps)))

    cpu = windows_report.cpu_percent(0.05) if start_error is None else {}
    started = time.perf_counter()

    def finish() -> None:
        observed = time.perf_counter() - started
        timer.stop()
        overlay_info = overlay.describe()
        results["overlay"] = overlay_info
        results["frames_composited"] = driven_frames
        results["observed_seconds"] = round(observed, 2)
        results["effective_fps"] = round(driven_frames / observed, 1) if observed else 0.0
        results["frame_stats"] = renderer.stats.as_dict()

        if overlay.frame is not None and not overlay.frame.isNull():
            Path(args.capture).parent.mkdir(parents=True, exist_ok=True)
            overlay.frame.save(args.capture, "PNG")
            results["capture"] = args.capture

        checks.append(
            {
                "check": "offscreen renderer started",
                "detail": str(results.get("start_error") or renderer.driver_used),
                "pass": start_error is None,
                "windows_only": False,
            }
        )
        checks.append(
            {
                "check": "frames composited into the overlay",
                "detail": f"{driven_frames} frames at target {args.fps} fps",
                "pass": driven_frames > 5,
                "windows_only": False,
            }
        )
        checks.append(
            {
                "check": "window is frameless + always-on-top + tool window",
                "detail": json.dumps(overlay_info),
                "pass": bool(
                    overlay_info["frameless"]
                    and overlay_info["top_most"]
                    and overlay_info["tool_window"]
                ),
                "windows_only": False,
            }
        )
        checks.append(
            {
                "check": "translucency attribute accepted",
                "detail": str(overlay_info["translucent_attr"]),
                "pass": bool(overlay_info["translucent_attr"]),
                "windows_only": False,
            }
        )
        checks.append(
            {
                "check": "click-through mode matches request",
                "detail": f"requested {args.click_through}, got {overlay_info['click_through']}",
                "pass": overlay_info["click_through"] == args.click_through,
                "windows_only": False,
            }
        )

        hwnd = overlay.native_handle_value()
        styles = windows_report.window_styles(hwnd)
        dpi = windows_report.dpi_for_window(hwnd)
        idle = windows_report.idle_seconds()
        taskbar = windows_report.taskbar_present()
        results["windows"] = {
            "window_styles": styles,
            "dpi": dpi,
            "idle": idle,
            "taskbar": taskbar,
            "cpu": cpu,
            "monitors": [
                {
                    "name": screen.name(),
                    "geometry": [screen.geometry().width(), screen.geometry().height()],
                    "available": [
                        screen.availableGeometry().width(),
                        screen.availableGeometry().height(),
                    ],
                    "device_pixel_ratio": screen.devicePixelRatio(),
                }
                for screen in screens
            ],
        }

        # Windows-only acceptance rows: reported as SKIPPED elsewhere, never PASS.
        win_rows = [
            ("window handle exists", bool(hwnd)),
            ("topmost style set by Windows", bool(styles.get("topmost_style"))),
            ("not listed in the taskbar", bool(styles.get("owned_by_other_window"))),
            ("per-window DPI readable", bool(dpi.get("supported"))),
        ]
        for name, ok in win_rows:
            checks.append(
                {
                    "check": name,
                    "detail": "windows only",
                    "pass": ok if windows_report.IS_WINDOWS else None,
                    "windows_only": True,
                }
            )

        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(results, indent=2))

        print("=== M0 overlay check ===")
        for row in checks:
            if row["pass"] is None:
                status = "SKIP"
            else:
                status = "PASS" if row["pass"] else "FAIL"
            print(f"[{status}] {row['check']} - {row['detail']}")
        print(f"effective fps: {results['effective_fps']}  frames: {driven_frames}")
        print(f"report: {args.json}")
        timer.stop()
        if renderer.base is not None:
            renderer.shutdown()
        app.quit()

    QTimer.singleShot(int(args.seconds * 1000), finish)
    app.exec()

    failed = [c for c in checks if c["pass"] is False]
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
