"""Frameless translucent always-on-top overlay window.

M0 spike scope: this is the Option B strategy from the architecture document
(render offscreen, composite into a Qt window). Option A (Panda-owned window
with Win32 layering) is deliberately not implemented yet - the comparison needs
measurements from a real Windows machine first.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QWidget


class LumiOverlay(QWidget):
    """A borderless window that paints one RGBA frame and nothing else."""

    def __init__(self, width: int = 320, height: int = 320, click_through: bool = False):
        super().__init__(None)
        self.setWindowFlags(self._window_flags(click_through))
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, click_through)
        self.setWindowTitle("Lumi - M0 overlay spike")
        self.resize(width, height)
        self._frame: QImage | None = None
        self._paints = 0

    @staticmethod
    def _window_flags(click_through: bool):
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool  # keeps it out of the taskbar and Alt-Tab
            | Qt.WindowType.NoDropShadowWindowHint
        )
        if click_through:
            flags |= Qt.WindowType.WindowTransparentForInput
        return flags

    # -- content -----------------------------------------------------------
    def set_frame(self, image: QImage) -> None:
        self._frame = image
        self.update()

    @property
    def frame(self) -> QImage | None:
        return self._frame

    @property
    def paint_count(self) -> int:
        return self._paints

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self._paints += 1
        painter = QPainter(self)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        if self._frame is not None and not self._frame.isNull():
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_SourceOver
            )
            painter.drawImage(0, 0, self._frame)
        painter.end()

    # -- behaviour ---------------------------------------------------------
    def set_click_through(self, enabled: bool) -> None:
        """Request mouse pass-through.

        Measured behaviour: Qt applies this flag reliably when it is set at
        window creation, but a window already created with the flag may refuse
        to clear it at runtime (setWindowFlags / setWindowFlag are silently
        ignored on this Qt build). Callers should not assume the toggle took
        effect: read `is_click_through` afterwards, which always reports the
        real flag state. See docs/WINDOWS_OVERLAY_SPIKE.md.
        """
        if self.is_click_through == enabled:
            return
        visible = self.isVisible()
        flags = self.windowFlags()
        if enabled:
            flags |= Qt.WindowType.WindowTransparentForInput
        else:
            flags &= ~Qt.WindowType.WindowTransparentForInput
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, enabled)
        if visible:
            self.show()
            self.raise_()

    @property
    def is_click_through(self) -> bool:
        return bool(self.windowFlags() & Qt.WindowType.WindowTransparentForInput)

    def keep_on_top(self) -> None:
        """Re-assert z-order. Windows can demote a topmost window after focus changes."""
        if self.isVisible():
            self.raise_()

    def place(self, rect: QRect) -> None:
        self.setGeometry(rect)

    def native_handle_value(self) -> int:
        if sys.platform == "win32":
            return int(self.winId())
        return 0

    def describe(self) -> dict[str, object]:
        return {
            "size": [self.width(), self.height()],
            "frameless": bool(self.windowFlags() & Qt.WindowType.FramelessWindowHint),
            "top_most": bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint),
            "tool_window": bool(self.windowFlags() & Qt.WindowType.Tool),
            "translucent_attr": self.testAttribute(
                Qt.WidgetAttribute.WA_TranslucentBackground
            ),
            "click_through": self.is_click_through,
            "paints": self._paints,
            "platform": sys.platform,
        }
