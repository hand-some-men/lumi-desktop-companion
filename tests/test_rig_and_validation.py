"""The rig contract and the GLB validator, tested against generated fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from lumi.character import rig_contract as contract
from tools.glb_builder import build_glb_bytes
from tools.validate_glb import parse_glb, validate_glb


@pytest.fixture()
def fixture_glb(tmp_path: Path) -> Path:
    path = tmp_path / "fixture.glb"
    path.write_bytes(build_glb_bytes())
    return path


def test_contract_has_the_expected_shape():
    assert len(contract.REQUIRED_BONE_NAMES) >= 20
    assert "Root" in contract.REQUIRED_BONE_NAMES
    assert "Wing_L" in contract.REQUIRED_BONE_NAMES and "Wing_R" in contract.REQUIRED_BONE_NAMES
    assert len(contract.REQUIRED_CLIP_NAMES) >= 10
    for required in ("idle", "walk", "sleep", "yawn", "fly", "pet_reaction"):
        assert required in contract.REQUIRED_CLIP_NAMES


def test_parents_are_declared_before_children():
    seen: set[str] = set()
    for bone in contract.BONES:
        if bone.parent is not None:
            assert bone.parent in seen, f"{bone.name} appears before its parent {bone.parent}"
        seen.add(bone.name)


def test_palette_hex_matches_palette_floats():
    for name, (r, g, b) in contract.PALETTE.items():
        expected = "#" + "".join(f"{round(c * 255):02X}" for c in (r, g, b))
        assert contract.PALETTE_HEX[name] == expected


def test_required_clips_are_part_of_the_clip_table():
    assert set(contract.REQUIRED_CLIP_NAMES) <= set(contract.CLIP_NAMES)


def test_resolve_clip_follows_fallbacks_and_stops():
    assert contract.resolve_clip("run") == "walk"  # run falls back to walk
    assert contract.resolve_clip("idle") == "idle"  # has no fallback
    assert contract.resolve_clip("nope") is None


def test_check_bones_reports_missing_and_unknown():
    result = contract.check_bones(["Root", "Hips", "Mystery"])
    assert result.ok is False
    assert "Spine" in result.missing
    assert "Mystery" in result.unknown


def test_valid_fixture_passes():
    report = validate_glb_or_bytes(build_glb_bytes(), tmp_path_holder := Path(str(__import__("tempfile").mkdtemp())) / "a.glb")
    assert report.ok, [i.message for i in report.errors]
    assert report.facts["triangles"] == 1


def validate_glb_or_bytes(data: bytes, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return validate_glb(path)


def test_fixture_reports_full_bone_and_clip_sets(fixture_glb):
    report = validate_glb(fixture_glb)
    assert len(report.facts["bones"]) == len(contract.REQUIRED_BONE_NAMES)
    assert set(report.facts["clips"]) == set(contract.CLIP_NAMES)


def test_missing_clip_is_an_error():
    path = Path(__file__).parent / "_tmp_missing_clip.glb"
    report = validate_glb_or_bytes(build_glb_bytes(clips=["idle", "walk"]), path)
    assert not report.ok
    assert any("missing" in i.message and "clips" in i.message for i in report.errors)
    path.unlink(missing_ok=True)


def test_missing_bone_is_an_error():
    path = Path(__file__).parent / "_tmp_missing_bone.glb"
    bones = [b for b in contract.REQUIRED_BONE_NAMES if b != "Horn"]
    report = validate_glb_or_bytes(build_glb_bytes(bones=bones), path)
    assert any("Horn" in i.message for i in report.errors)
    path.unlink(missing_ok=True)


def test_unrigged_fixture_fails():
    path = Path(__file__).parent / "_tmp_unrigged.glb"
    report = validate_glb_or_bytes(build_glb_bytes(include_skin=False), path)
    assert any(i.code == "BONE001" for i in report.errors)
    path.unlink(missing_ok=True)


def test_wrong_hierarchy_is_a_warning():
    path = Path(__file__).parent / "_tmp_hierarchy.glb"
    report = validate_glb_or_bytes(build_glb_bytes(hierarchy_overrides={"Neck": "Root"}), path)
    assert any(i.code == "BONE004" for i in report.warnings)
    path.unlink(missing_ok=True)


def test_off_palette_colour_is_a_warning():
    path = Path(__file__).parent / "_tmp_colour.glb"
    report = validate_glb_or_bytes(build_glb_bytes(material_color=(0.1, 0.6, 0.1, 1.0)), path)
    assert any(i.code == "MAT003" for i in report.warnings)
    path.unlink(missing_ok=True)


def test_platform_node_is_flagged():
    path = Path(__file__).parent / "_tmp_platform.glb"
    report = validate_glb_or_bytes(build_glb_bytes(extra_node_name="Platform_Base"), path)
    assert any(i.code == "CONTENT001" for i in report.warnings)
    path.unlink(missing_ok=True)


def test_no_materials_is_only_a_warning():
    path = Path(__file__).parent / "_tmp_nomat.glb"
    report = validate_glb_or_bytes(build_glb_bytes(include_material=False), path)
    assert report.ok
    assert any(i.code == "MAT001" for i in report.warnings)
    path.unlink(missing_ok=True)


def test_not_a_glb_is_reported_not_raised():
    path = Path(__file__).parent / "_tmp_garbage.glb"
    path.write_bytes(b"not a glb at all")
    report = validate_glb(path)
    assert not report.ok
    assert report.errors[0].code in {"GLB001", "IO001"}
    path.unlink(missing_ok=True)


def test_truncated_glb_is_reported():
    data = build_glb_bytes()
    path = Path(__file__).parent / "_tmp_truncated.glb"
    path.write_bytes(data[: len(data) // 2])
    report = validate_glb(path)
    assert not report.ok
    path.unlink(missing_ok=True)


def test_parse_glb_returns_json_and_binary():
    gltf, binary = parse_glb(build_glb_bytes())
    assert gltf["asset"]["version"] == "2.0"
    assert binary


def test_validator_survives_a_missing_file(tmp_path):
    report = validate_glb(tmp_path / "nope.glb")
    assert not report.ok
    assert report.errors[0].code == "IO001"


def test_json_report_is_serialisable(fixture_glb):
    import json

    report = validate_glb(fixture_glb)
    text = json.dumps(report.as_dict())
    assert '"ok": true' in text
