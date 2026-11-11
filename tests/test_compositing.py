"""Compositing logic, tested without a display.

This proves the pixel maths, not that Windows draws a transparent window.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")


@pytest.fixture(scope="module")
def qapp():
    # QWidget (the overlay) requires a QApplication, not just a QGuiApplication.
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def _frame_with_hole(size: int = 32):
    from PySide6.QtGui import QColor, QImage

    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(0, 0, 0, 0))
    for y in range(size // 4, size * 3 // 4):
        for x in range(size // 4, size * 3 // 4):
            image.setPixelColor(x, y, QColor(239, 230, 255, 255))
    return image


def test_alpha_survives_compositing(qapp):
    from lumi.rendering.composite import alpha_histogram, compose_onto_transparent

    frame = _frame_with_hole()
    canvas = compose_onto_transparent(frame, 32, 32)
    hist = alpha_histogram(canvas)

    assert hist["transparent"] == 32 * 32 - 16 * 16
    assert hist["opaque"] == 16 * 16
    assert hist["partial"] == 0


def test_semi_transparent_frame_stays_semi_transparent(qapp):
    from PySide6.QtGui import QColor, QImage

    from lumi.rendering.composite import alpha_histogram, compose_onto_transparent

    frame = QImage(8, 8, QImage.Format.Format_ARGB32_Premultiplied)
    frame.fill(QColor(0, 230, 255, 128))
    hist = alpha_histogram(compose_onto_transparent(frame, 8, 8))
    assert hist["partial"] == 64


def test_overlay_flags_declare_a_translucent_tool_window(qapp):
    from lumi.desktop.overlay import LumiOverlay

    overlay = LumiOverlay(64, 64)
    info = overlay.describe()
    assert info["frameless"] is True
    assert info["top_most"] is True
    assert info["tool_window"] is True
    assert info["translucent_attr"] is True
    assert info["click_through"] is False


def test_click_through_comes_from_creation_flags(qapp):
    from lumi.desktop.overlay import LumiOverlay

    assert LumiOverlay(32, 32, click_through=True).is_click_through is True
    assert LumiOverlay(32, 32, click_through=False).is_click_through is False


def test_click_through_can_be_enabled_on_a_plain_window(qapp):
    from lumi.desktop.overlay import LumiOverlay

    overlay = LumiOverlay(32, 32)
    overlay.set_click_through(True)
    assert overlay.is_click_through is True


def test_is_click_through_always_reports_real_flags(qapp):
    """A refused toggle must be visible to the caller, not silently swallowed."""
    from PySide6.QtCore import Qt

    from lumi.desktop.overlay import LumiOverlay

    overlay = LumiOverlay(32, 32, click_through=True)
    overlay.set_click_through(False)
    actual = bool(overlay.windowFlags() & Qt.WindowType.WindowTransparentForInput)
    assert overlay.is_click_through == actual


def test_frame_is_painted(qapp):
    from lumi.desktop.overlay import LumiOverlay

    overlay = LumiOverlay(16, 16)
    overlay.set_frame(_frame_with_hole(16))
    overlay.repaint()
    assert overlay.frame is not None
