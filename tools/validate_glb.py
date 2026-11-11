"""Validate a Lumi GLB against the rig, animation and colour contract.

Checks are read-only and use no third-party libraries: the GLB container is
parsed directly so failures are reported precisely instead of hidden by an
importer.

Usage:
    python tools/validate_glb.py assets/models/lumi.glb
    python tools/validate_glb.py assets/models/lumi.glb --json report.json --strict

Exit code is 1 when errors are found (or warnings, with --strict).
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lumi.character import rig_contract as contract  # noqa: E402

GLB_MAGIC = 0x46546C67
CHUNK_JSON = 0x4E4F534A
CHUNK_BIN = 0x004E4942
COLOUR_TOLERANCE = 0.20  # RGB Euclidean distance from the nearest palette entry
MAX_SANE_SIZE_METRES = 10.0


@dataclass
class Issue:
    severity: str  # "error" | "warning"
    code: str
    message: str


@dataclass
class Report:
    path: str
    issues: list[Issue] = field(default_factory=list)
    facts: dict[str, object] = field(default_factory=dict)

    def error(self, code: str, message: str) -> None:
        self.issues.append(Issue("error", code, message))

    def warn(self, code: str, message: str) -> None:
        self.issues.append(Issue("warning", code, message))

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "ok": self.ok,
            "errors": [i.__dict__ for i in self.errors],
            "warnings": [i.__dict__ for i in self.warnings],
            "facts": self.facts,
        }


def parse_glb(data: bytes) -> tuple[dict[str, object], bytes]:
    """Split a GLB into its JSON document and binary chunk."""
    if len(data) < 12:
        raise ValueError("file is shorter than a GLB header")
    magic, version, length = struct.unpack_from("<III", data, 0)
    if magic != GLB_MAGIC:
        raise ValueError(f"not a GLB file (magic 0x{magic:08x})")
    if version != 2:
        raise ValueError(f"unsupported GLB container version {version}")
    if length != len(data):
        raise ValueError(f"header says {length} bytes, file is {len(data)} bytes")

    json_doc: dict[str, object] | None = None
    binary = b""
    offset = 12
    while offset + 8 <= len(data):
        chunk_length, chunk_type = struct.unpack_from("<II", data, offset)
        offset += 8
        chunk = data[offset : offset + chunk_length]
        offset += chunk_length
        if chunk_type == CHUNK_JSON:
            json_doc = json.loads(chunk.decode("utf-8"))
        elif chunk_type == CHUNK_BIN:
            binary = chunk
    if json_doc is None:
        raise ValueError("GLB has no JSON chunk")
    return json_doc, binary


def _node_names(gltf: dict) -> dict[int, str]:
    return {i: node.get("name", "") for i, node in enumerate(gltf.get("nodes", []))}


def _joint_parents(gltf: dict, joint_ids: list[int]) -> dict[str, str]:
    """Map joint name -> parent joint name, when the file defines that link."""
    names = _node_names(gltf)
    index_of = {node_id: names.get(node_id, "") for node_id in joint_ids}
    parents: dict[str, str] = {}
    for index, node in enumerate(gltf.get("nodes", [])):
        if index not in index_of:
            continue
        for child in node.get("children", []) or []:
            if child in index_of and index_of.get(child):
                parents[index_of[child]] = index_of[index]
    return parents


def validate_glb(path: str | Path) -> Report:
    path = Path(path)
    report = Report(path=str(path))
    try:
        raw = path.read_bytes()
    except OSError as exc:
        report.error("IO001", f"cannot read file: {exc}")
        return report

    try:
        gltf, binary = parse_glb(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        report.error("GLB001", str(exc))
        return report

    # -- asset ------------------------------------------------------------
    asset = gltf.get("asset", {})
    version = str(asset.get("version", ""))
    report.facts["asset_version"] = version
    report.facts["generator"] = asset.get("generator", "")
    if not version.startswith("2."):
        report.error("GLTF001", f"asset.version is {version!r}, expected 2.x")
    if not binary:
        report.warn("GLB002", "no binary chunk present")

    # -- geometry ---------------------------------------------------------
    meshes = gltf.get("meshes", []) or []
    accessors = gltf.get("accessors", []) or []
    if not meshes:
        report.error("MESH001", "file contains no meshes")
    triangles = 0
    for mesh_index, mesh in enumerate(meshes):
        for prim_index, prim in enumerate(mesh.get("primitives", []) or []):
            attrs = prim.get("attributes", {}) or {}
            if "POSITION" not in attrs:
                report.error("MESH002", f"mesh {mesh_index} primitive {prim_index} has no POSITION")
                continue
            if "indices" in prim:
                accessor = accessors[prim["indices"]] if prim["indices"] < len(accessors) else {}
                triangles += int(accessor.get("count", 0)) // 3
            else:
                position = accessors[attrs["POSITION"]] if attrs["POSITION"] < len(accessors) else {}
                triangles += int(position.get("count", 0)) // 3
    report.facts["triangles"] = triangles
    if triangles == 0:
        report.error("MESH003", "no triangles found in any mesh")

    # bounding box from POSITION accessor min/max
    bbox_size = None
    for mesh in meshes:
        for prim in mesh.get("primitives", []) or []:
            pos_index = (prim.get("attributes") or {}).get("POSITION")
            if pos_index is None or pos_index >= len(accessors):
                continue
            accessor = accessors[pos_index]
            lo, hi = accessor.get("min"), accessor.get("max")
            if lo and hi and len(lo) == 3:
                size = [round(hi[i] - lo[i], 4) for i in range(3)]
                bbox_size = size if bbox_size is None else [max(a, b) for a, b in zip(bbox_size, size)]
    report.facts["bbox_size"] = bbox_size
    if bbox_size and max(bbox_size) > MAX_SANE_SIZE_METRES:
        report.warn(
            "SCALE001",
            f"model is {max(bbox_size):.1f} m on its longest axis - expected a desktop-scale character "
            f"(~0.30 m tall)",
        )

    # -- materials and colour --------------------------------------------
    materials = gltf.get("materials", []) or []
    report.facts["materials"] = [m.get("name", "") for m in materials]
    report.facts["textures"] = len(gltf.get("textures", []) or [])
    if not materials:
        report.warn("MAT001", "no materials: the character will render as untextured geometry")
    for index, material in enumerate(materials):
        pbr = material.get("pbrMetallicRoughness")
        name = material.get("name", f"material {index}")
        if not pbr:
            report.warn("MAT002", f"{name} has no pbrMetallicRoughness block")
            continue
        colour = pbr.get("baseColorFactor")
        if not colour:
            continue
        nearest, distance = _nearest_palette(colour)
        if distance > COLOUR_TOLERANCE:
            report.warn(
                "MAT003",
                f"{name} base colour {_hex(colour)} is {distance:.2f} away from the nearest Lumi "
                f"colour ({nearest} {contract.PALETTE_HEX[nearest]}) - check the character was not recoloured",
            )

    # -- rig --------------------------------------------------------------
    skins = gltf.get("skins", []) or []
    report.facts["skins"] = len(skins)
    bone_names: list[str] = []
    if not skins:
        report.error("BONE001", "file has no skin: the character is not rigged")
    else:
        names = _node_names(gltf)
        joints = skins[0].get("joints", []) or []
        bone_names = [names.get(j, f"node{j}") for j in joints]
        report.facts["bones"] = bone_names
        rig_name = skins[0].get("name")
        report.facts["rig_name"] = rig_name
        if rig_name and rig_name != contract.RIG_NAME:
            report.warn("BONE005", f"skin is named {rig_name!r}, contract expects {contract.RIG_NAME!r}")

        bone_check = contract.check_bones(bone_names)
        if bone_check.missing:
            report.error(
                "BONE002",
                f"missing {len(bone_check.missing)} required bones: {', '.join(bone_check.missing)}",
            )
        if bone_check.unknown:
            report.warn("BONE003", f"bones not in the contract: {', '.join(bone_check.unknown)}")

        parents = _joint_parents(gltf, joints)
        if parents:
            report.facts["rig_hierarchy_present"] = True
            mismatches = []
            for child, actual_parent in parents.items():
                expected = contract.parent_of(child)
                if expected is None and child in contract._BONE_INDEX:
                    mismatches.append(f"{child} should be a root but is parented to {actual_parent}")
                elif expected is not None and expected != actual_parent:
                    mismatches.append(f"{child} is parented to {actual_parent}, expected {expected}")
            if mismatches:
                report.warn("BONE004", "; ".join(mismatches[:8]))
        else:
            report.facts["rig_hierarchy_present"] = False

    # -- animations -------------------------------------------------------
    animations = gltf.get("animations", []) or []
    clip_names = [a.get("name", f"animation{i}") for i, a in enumerate(animations)]
    report.facts["clips"] = clip_names
    clip_check = contract.check_clips(clip_names)
    if clip_check.missing:
        report.error(
            "CLIP001",
            f"missing {len(clip_check.missing)} required clips: {', '.join(clip_check.missing)}",
        )
    if clip_check.unknown:
        report.warn("CLIP002", f"clips not in the contract: {', '.join(clip_check.unknown)}")
    for index, animation in enumerate(animations):
        if not animation.get("channels"):
            report.error("CLIP003", f"animation {index} has no channels")

    # -- content rules ----------------------------------------------------
    for node in gltf.get("nodes", []) or []:
        name = str(node.get("name", "")).lower()
        if "platform" in name or "pedestal" in name or name in {"base", "stand"}:
            report.warn(
                "CONTENT001",
                f"node {node.get('name')!r} looks like a display platform; Lumi must sit on the desktop "
                "without a base",
            )

    return report


def _nearest_palette(colour: list[float]) -> tuple[str, float]:
    rgb = [float(c) for c in colour[:3]]
    best_name, best_distance = "", float("inf")
    for name, palette_rgb in contract.PALETTE.items():
        distance = sum((a - b) ** 2 for a, b in zip(rgb, palette_rgb)) ** 0.5
        if distance < best_distance:
            best_name, best_distance = name, distance
    return best_name, best_distance


def _hex(colour: list[float]) -> str:
    return "#" + "".join(f"{max(0, min(255, round(float(c) * 255))):02X}" for c in colour[:3])


def print_report(report: Report, strict: bool = False) -> None:
    print(f"=== GLB validation: {report.path} ===")
    for key in ("asset_version", "triangles", "bbox_size", "skins", "rig_name", "clips", "materials"):
        if key in report.facts:
            print(f"{key:14s}: {report.facts[key]}")
    if "bones" in report.facts:
        print(f"{'bones':14s}: {len(report.facts['bones'])}")  # type: ignore[arg-type]
    for issue in report.issues:
        print(f"[{issue.severity.upper():7s}] {issue.code}: {issue.message}")
    if not report.issues:
        print("no issues found")
    errors, warnings = len(report.errors), len(report.warnings)
    verdict = "PASS" if report.ok and not (strict and warnings) else "FAIL"
    print(f"result: {verdict} ({errors} errors, {warnings} warnings)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a Lumi GLB against the character contract")
    parser.add_argument("glb", help="path to the .glb file")
    parser.add_argument("--json", dest="json_out", default=None, help="write the report as JSON")
    parser.add_argument("--strict", action="store_true", help="treat warnings as failures")
    args = parser.parse_args(argv)

    report = validate_glb(args.glb)
    print_report(report, strict=args.strict)
    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(json.dumps(report.as_dict(), indent=2))
        print(f"report written to {args.json_out}")

    if not report.ok:
        return 1
    if args.strict and report.warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
