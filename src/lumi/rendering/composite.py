"""Convert a rendered RGBA frame into something Qt can paint.

The frame is transferred through RAM in M0. That is acceptable for a 320x320
overlay but it is the first thing to replace in M1 if a shared-texture path
turns out to be fast enough on real hardware.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from panda3d.core import PNMImage


def pnm_to_qimage(pnm: PNMImage):
    """PNMImage -> QImage(Format_RGBA8888), alpha preserved."""
    from PySide6.QtGui import QImage

    if not pnm.hasAlpha():
        pnm.addAlpha()

    # Panda writes PNG only through a file, so round-trip via a temp file.
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as handle:
        tmp = Path(handle.name)
    from panda3d.core import Filename

    try:
        if not pnm.write(Filename.fromOsSpecific(str(tmp))):
            raise RuntimeError("could not encode frame as PNG")
        image = QImage(str(tmp))
    finally:
        tmp.unlink(missing_ok=True)

    if image.isNull():
        raise RuntimeError("Qt could not decode the rendered frame")
    return image.convertToFormat(QImage.Format.Format_RGBA8888)


def transparent_canvas(width: int, height: int):
    """A fully transparent QImage of the given size."""
    from PySide6.QtGui import QImage

    canvas = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    canvas.fill(0)
    return canvas


def compose_onto_transparent(frame, width: int, height: int):
    """Composite a frame over a transparent canvas, source-over.

    This is the same operation the overlay widget performs in paintEvent(); it
    exists as a pure function so it can be unit tested without a display.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPainter

    canvas = transparent_canvas(width, height)
    painter = QPainter(canvas)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
    painter.drawImage(0, 0, frame.scaled(width, height, Qt.AspectRatioMode.IgnoreAspectRatio))
    painter.end()
    return canvas


def alpha_histogram(image) -> dict[str, int]:
    """Count fully transparent, partial and opaque pixels in a QImage."""
    image = image.convertToFormat(image.Format.Format_ARGB32)
    transparent = partial = opaque = 0
    width, height = image.width(), image.height()
    for y in range(height):
        for x in range(width):
            alpha = (image.pixel(x, y) >> 24) & 0xFF
            if alpha == 0:
                transparent += 1
            elif alpha == 255:
                opaque += 1
            else:
                partial += 1
    return {"transparent": transparent, "partial": partial, "opaque": opaque}
