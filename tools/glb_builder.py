"""Build minimal, valid GLB files for testing the validator.

The result is a degenerate one-triangle "character" with the full bone set from
the rig contract and one animation per clip. It exists so the validator can be
tested honestly. It is NOT a Lumi model and is never shipped as one.
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lumi.character import rig_contract as contract  # noqa: E402

GLB_MAGIC = 0x46546C67
CHUNK_JSON = 0x4E4F534A
CHUNK_BIN = 0x004E4942


def _pad4(data: bytes, fill: bytes = b"\x00") -> bytes:
    return data + fill * ((4 - len(data) % 4) % 4)


def build_glb_bytes(
    *,
    asset_version: str = "2.0",
    bones: list[str] | None = None,
    clips: list[str] | None = None,
    include_skin: bool = True,
    include_material: bool = True,
    material_color: tuple[float, float, float, float] = (0.937, 0.902, 1.0, 1.0),
    hierarchy_overrides: dict[str, str | None] | None = None,
    extra_node_name: str | None = None,
) -> bytes:
    bones = list(bones if bones is not None else contract.REQUIRED_BONE_NAMES)
    clips = list(clips if clips is not None else contract.CLIP_NAMES)
    overrides = hierarchy_overrides or {}

    # --- binary buffer -------------------------------------------------
    positions = [(0.0, 0.0, 0.0), (0.2, 0.0, 0.0), (0.0, 0.3, 0.0)]
    pos_bytes = b"".join(struct.pack("<3f", *p) for p in positions)
    idx_bytes = _pad4(struct.pack("<3H", 0, 1, 2))
    time_bytes = struct.pack("<2f", 0.0, 1.0)
    rot_bytes = struct.pack("<4f", 0.0, 0.0, 0.0, 1.0) + struct.pack("<4f", 0.0, 0.1, 0.0, 0.99)

    blobs: list[tuple[bytes, int]] = []  # (data, target)
    bin_parts: list[bytes] = []
    views: list[dict] = []

    def add_view(data: bytes, target: int | None = None) -> int:
        offset = sum(len(b) for b in bin_parts)
        bin_parts.append(_pad4(data))
        view = {"buffer": 0, "byteOffset": offset, "byteLength": len(data)}
        if target is not None:
            view["target"] = target
        views.append(view)
        return len(views) - 1

    v_pos = add_view(pos_bytes, 34962)
    v_idx = add_view(idx_bytes, 34963)
    v_time = add_view(time_bytes)
    v_rot = add_view(rot_bytes)
    binary = b"".join(bin_parts)

    accessors = [
        {
            "bufferView": v_pos,
            "componentType": 5126,
            "count": 3,
            "type": "VEC3",
            "min": [0.0, 0.0, 0.0],
            "max": [0.2, 0.3, 0.0],
        },
        {"bufferView": v_idx, "componentType": 5123, "count": 3, "type": "SCALAR"},
        {"bufferView": v_time, "componentType": 5126, "count": 2, "type": "SCALAR", "min": [0.0], "max": [1.0]},
        {"bufferView": v_rot, "componentType": 5126, "count": 2, "type": "VEC4"},
    ]

    # --- nodes + hierarchy ---------------------------------------------
    bone_index = {name: i + 1 for i, name in enumerate(bones)}  # node 0 is the mesh
    parents = {name: contract.parent_of(name) for name in bones}
    parents.update(overrides)

    nodes: list[dict] = [{"name": "Lumi_Body", "mesh": 0}]
    if include_skin:
        nodes[0]["skin"] = 0
    for name in bones:
        node: dict[str, object] = {"name": name}
        children = [
            bone_index[child]
            for child in bones
            if parents.get(child) == name and child in bone_index
        ]
        if children:
            node["children"] = sorted(children)
        nodes.append(node)
    if extra_node_name:
        nodes.append({"name": extra_node_name})

    gltf: dict[str, object] = {
        "asset": {"version": asset_version, "generator": "lumi test fixture (not a character)"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": nodes,
        "meshes": [
            {
                "name": "Lumi_Body",
                "primitives": [{"attributes": {"POSITION": 0}, "indices": 1}],
            }
        ],
        "accessors": accessors,
        "bufferViews": views,
        "buffers": [{"byteLength": len(binary)}],
    }
    if include_material:
        gltf["meshes"][0]["primitives"][0]["material"] = 0
        gltf["materials"] = [
            {
                "name": "Coat",
                "pbrMetallicRoughness": {
                    "baseColorFactor": list(material_color),
                    "metallicFactor": 0.0,
                    "roughnessFactor": 0.6,
                },
            }
        ]
    if include_skin:
        gltf["skins"] = [
            {
                "name": "Lumi_Rig",
                "joints": [bone_index[name] for name in bones],
                "skeleton": bone_index.get("Root", bone_index[bones[0]]),
            }
        ]
    if clips:
        gltf["animations"] = [
            {
                "name": clip,
                "channels": [
                    {"sampler": 0, "target": {"node": bone_index[bones[0]], "path": "rotation"}}
                ],
                "samplers": [{"input": 2, "output": 3, "interpolation": "LINEAR"}],
            }
            for clip in clips
        ]

    json_chunk = _pad4(json.dumps(gltf, separators=(",", ":")).encode("utf-8"), b" ")
    bin_chunk = _pad4(binary)

    header_len = 12 + 8 + len(json_chunk) + (8 + len(bin_chunk) if bin_chunk else 0)
    out = bytearray()
    out += struct.pack("<III", GLB_MAGIC, 2, header_len)
    out += struct.pack("<II", len(json_chunk), CHUNK_JSON) + json_chunk
    if bin_chunk:
        out += struct.pack("<II", len(bin_chunk), CHUNK_BIN) + bin_chunk
    return bytes(out)


def write_fixture(path: str | Path, **kwargs) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(build_glb_bytes(**kwargs))
    return out


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "build/lumi_fixture.glb"
    print(write_fixture(target))
