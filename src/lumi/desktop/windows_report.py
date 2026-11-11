"""Windows facts needed to fill in the M0 acceptance record.

Everything here is read-only introspection via ctypes: no pywin32 dependency,
no hooks, no global input capture. On non-Windows platforms each probe returns
{"supported": False} instead of raising.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import platform
import sys
import time

IS_WINDOWS = sys.platform == "win32"

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOPMOST = 0x00000008
WS_EX_APPWINDOW = 0x00040000
GA_ROOTOWNER = 3


def unsupported(reason: str = "not windows") -> dict[str, object]:
    return {"supported": False, "reason": reason}


def environment() -> dict[str, object]:
    info: dict[str, object] = {
        "platform": sys.platform,
        "python": platform.python_version(),
        "machine": platform.machine(),
        "windows_release": None,
        "windows_build": None,
    }
    if IS_WINDOWS:
        version = sys.getwindowsversion()
        info["windows_release"] = f"{version.major}.{version.minor}"
        info["windows_build"] = version.build
    return info


def window_styles(hwnd: int) -> dict[str, object]:
    """Read layered / topmost / taskbar-visibility facts for a window handle."""
    if not IS_WINDOWS or not hwnd:
        return unsupported()
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetWindowLongW.restype = ctypes.c_long
    ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & 0xFFFFFFFF
    owner = user32.GetAncestor(hwnd, GA_ROOTOWNER)
    return {
        "supported": True,
        "exstyle": hex(ex),
        "layered": bool(ex & WS_EX_LAYERED),
        "click_through_style": bool(ex & WS_EX_TRANSPARENT),
        "topmost_style": bool(ex & WS_EX_TOPMOST),
        "appwindow_style": bool(ex & WS_EX_APPWINDOW),
        # A window whose root owner is not itself is normally left out of the taskbar.
        "owned_by_other_window": bool(owner and owner != hwnd),
        "is_visible": bool(user32.IsWindowVisible(hwnd)),
        "is_foreground": bool(user32.GetForegroundWindow() == hwnd),
    }


def dpi_for_window(hwnd: int) -> dict[str, object]:
    if not IS_WINDOWS or not hwnd:
        return unsupported()
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    try:
        dpi = user32.GetDpiForWindow(wt.HWND(hwnd))
    except (AttributeError, OSError):
        return {"supported": False, "reason": "GetDpiForWindow unavailable (pre Win10 1607)"}
    return {"supported": True, "dpi": int(dpi), "scale_percent": round(dpi / 96.0 * 100, 1)}


def idle_seconds() -> dict[str, object]:
    """System-wide idle time, no input hook required."""
    if not IS_WINDOWS:
        return unsupported()
    user32 = ctypes.WinDLL("user32", use_last_error=True)

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", wt.UINT), ("dwTime", wt.DWORD)]

    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not user32.GetLastInputInfo(ctypes.byref(info)):
        return {"supported": False, "reason": "GetLastInputInfo failed"}
    tick = ctypes.windll.kernel32.GetTickCount()
    return {"supported": True, "idle_seconds": round((tick - info.dwTime) / 1000.0, 2)}


def cpu_percent(sample_seconds: float = 3.0) -> dict[str, object]:
    """Process CPU use as a percentage of one core, measured over a window."""
    process_time = time.process_time()
    wall_start = time.perf_counter()
    time.sleep(sample_seconds)
    cpu = time.process_time() - process_time
    wall = time.perf_counter() - wall_start
    return {
        "sample_seconds": round(wall, 2),
        "cpu_percent_of_one_core": round(cpu / wall * 100.0, 2),
    }


def taskbar_present() -> dict[str, object]:
    if not IS_WINDOWS:
        return unsupported()
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.FindWindowW.restype = wt.HWND
    tray = user32.FindWindowW("Shell_TrayWnd", None)
    return {"supported": True, "shell_tray_found": bool(tray)}
