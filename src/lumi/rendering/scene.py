"""Throwaway geometry for the M0 spike.

This is NOT Lumi. It is a placeholder cube + semi-transparent card used only to
prove that the offscreen pipeline produces real 3D geometry with per-pixel
alpha. It is deliberately not a pony and must never be presented as the
character.
"""

from __future__ import annotations

from panda3d.core import (
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    LVecBase4f,
    NodePath,
    TransparencyAttrib,
)

# Faces of a cube as (corner indices) for the 6 sides, in cuboid vertex order.
_CUBE_FACES = (
    (0, 1, 3, 2),  # -Y
    (4, 7, 5, 6),  # +X (winding fixed below by rendering double-sided)
    (0, 4, 5, 1),  # -Z ... indices are arbitrary; culling is disabled
    (2, 3, 7, 6),
    (0, 2, 6, 4),
    (1, 5, 7, 3),
)


def _cube_points(size: float) -> list[tuple[float, float, float]]:
    h = size * 0.5
    return [
        (-h, -h, -h),
        (h, -h, -h),
        (-h, h, -h),
        (h, h, -h),
        (-h, -h, h),
        (h, -h, h),
        (-h, h, h),
        (h, h, h),
    ]


def make_cube_geom(size: float, color: LVecBase4f) -> Geom:
    """A flat-shaded cube using vertex colours (no textures, no lighting)."""
    fmt = GeomVertexFormat.getV3c4()
    vdata = GeomVertexData("m0-cube", fmt, Geom.UHStatic)
    vdata.setNumRows(24)

    vert = GeomVertexWriter(vdata, "vertex")
    col = GeomVertexWriter(vdata, "color")
    tris = GeomTriangles(Geom.UHStatic)

    points = _cube_points(size)
    row = 0
    for face in _CUBE_FACES:
        for idx in face:
            vert.addData3f(*points[idx])
            col.addData4f(color[0], color[1], color[2], color[3])
        tris.addVertices(row, row + 1, row + 2)
        tris.addVertices(row, row + 2, row + 3)
        row += 4

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    return geom


def make_alpha_card(width: float, height: float, color: LVecBase4f) -> Geom:
    """A camera-facing quad in the XZ plane whose alpha is < 1.

    Placed between the camera and the cube, so its blended pixels can be
    measured instead of guessed at.
    """
    fmt = GeomVertexFormat.getV3c4()
    vdata = GeomVertexData("m0-card", fmt, Geom.UHStatic)
    vdata.setNumRows(4)

    vert = GeomVertexWriter(vdata, "vertex")
    col = GeomVertexWriter(vdata, "color")
    hw, hh = width * 0.5, height * 0.5
    for x, z in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)):
        vert.addData3f(x, 0.0, z)
        col.addData4f(color[0], color[1], color[2], color[3])

    tris = GeomTriangles(Geom.UHStatic)
    tris.addVertices(0, 1, 2)
    tris.addVertices(0, 2, 3)

    geom = Geom(vdata)
    geom.addPrimitive(tris)
    return geom


def build_spike_scene(render: NodePath, camera: NodePath) -> tuple[NodePath, NodePath]:
    """Attach the spike geometry. Returns (cube, half_alpha_card) node paths.

    Colours come from the Lumi palette only so the capture reads as part of the
    project, but the shape is an obvious debug object.
    """
    body = LVecBase4f(0.937, 0.902, 1.0, 1.0)  # #EFE6FF coat
    mane = LVecBase4f(0.714, 0.294, 1.0, 1.0)  # #B64BFF
    cyan = LVecBase4f(0.0, 0.902, 1.0, 0.55)  # #00E6FF, half transparent

    cube_np = render.attachNewNode(GeomNode("m0-cube-node"))
    cube_np.node().addGeom(make_cube_geom(1.4, body))
    cube_np.setPos(0, 0, 0.35)
    cube_np.setHpr(35, -22, 0)
    cube_np.setLightOff()
    cube_np.setShaderOff()
    cube_np.setTextureOff()
    # A second, slightly larger cube gives the purple mane colour a place to show
    # without needing lights.
    inner = render.attachNewNode(GeomNode("m0-cube-inner"))
    inner.node().addGeom(make_cube_geom(0.55, mane))
    inner.reparentTo(cube_np)
    inner.setLightOff()
    inner.setShaderOff()
    inner.setTextureOff()

    card_np = render.attachNewNode(GeomNode("m0-card-node"))
    card_np.node().addGeom(make_alpha_card(1.6, 1.6, cyan))
    card_np.setPos(0, -1.2, 0.35)  # in front of the cube, facing the camera
    card_np.setTwoSided(True)
    card_np.setLightOff()
    card_np.setShaderOff()
    card_np.setTextureOff()
    card_np.setTransparency(TransparencyAttrib.MAlpha)
    card_np.setBin("transparent", 10)

    camera.lookAt(cube_np)
    return cube_np, card_np
