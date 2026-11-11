"""The render pipeline must produce 3D geometry with real per-pixel alpha."""

from __future__ import annotations

import os

import pytest

from lumi.rendering.offscreen import OffscreenRenderer, RenderConfig


@pytest.fixture(scope="module")
def renderer():
    driver = os.environ.get("LUMI_TEST_DRIVER")  # e.g. p3tinydisplay in CI
    r = OffscreenRenderer(RenderConfig(width=96, height=96, driver=driver))
    try:
        r.start()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"no graphics pipe available: {exc}")
    yield r
    r.shutdown()


def test_background_alpha_is_zero(renderer):
    renderer.render_frames(2)
    pnm = renderer.grab_pnm()
    assert pnm.hasAlpha()
    corners = [
        pnm.getAlpha(0, 0),
        pnm.getAlpha(pnm.getXSize() - 1, 0),
        pnm.getAlpha(0, pnm.getYSize() - 1),
        pnm.getAlpha(pnm.getXSize() - 1, pnm.getYSize() - 1),
    ]
    assert corners == [0.0, 0.0, 0.0, 0.0]


def test_geometry_renders_opaque_pixels(renderer):
    renderer.render_frames(2)
    pnm = renderer.grab_pnm()
    opaque = sum(
        1
        for y in range(0, pnm.getYSize(), 2)
        for x in range(0, pnm.getXSize(), 2)
        if pnm.getAlpha(x, y) >= 0.99
    )
    assert opaque > 0, "nothing opaque was drawn"


def test_partial_alpha_pixels_exist(renderer):
    renderer.render_frames(4)
    pnm = renderer.grab_pnm()
    partial = sum(
        1
        for y in range(0, pnm.getYSize(), 2)
        for x in range(0, pnm.getXSize(), 2)
        if 0.0 < pnm.getAlpha(x, y) < 0.99
    )
    assert partial > 0, "alpha is binary - the translucent card did not blend"


def test_png_written_with_content(renderer, tmp_path):
    """A transparent PNG can be tiny, so check the pixels, not the byte count."""
    from panda3d.core import Filename, PNMImage

    renderer.render_frames(1)
    out = renderer.grab_png(tmp_path / "frame.png")
    assert out.exists()

    reread = PNMImage()
    assert reread.read(Filename.fromOsSpecific(str(out)))
    assert reread.hasAlpha()
    visible = sum(
        1
        for y in range(0, reread.getYSize(), 2)
        for x in range(0, reread.getXSize(), 2)
        if reread.getAlpha(x, y) > 0.5
    )
    assert visible > 0, "the saved PNG contains no visible pixels"


def test_frame_stats_recorded(renderer):
    renderer.render_frames(5)
    stats = renderer.stats.as_dict()
    assert stats["frames"] >= 5
    assert stats["mean_ms"] > 0
