"""Rig and animation contract integrity, plus GLB validator behaviour."""

from __future__ import annotations

import pytest

import glb_builder
import validate_glb
from lumi.character import rig_contract as contract


# --------------------------------------------------------------------------
# contract integrity
# --------------------------------------------------------------------------
def test_every_bone_parent_is_declared_before_its_child():
    seen: set[str] = set()
    for bone in contract.BONES:
        if bone.parent is not None:
            assert bone.parent in seen, f"{bone.name} appears before its parent {bone.parent}"
        seen.add(bone.name)


def test_only_root_has_no_parent():
    roots = [b.name for b in contract.BONES if b.parent is None]
    assert roots == ["Root"]


def test_clip_fallbacks_exist_in_the_contract():
    for clip in contract.CLIPS:
        if clip.fallback is not None:
            assert clip.fallback in contract.CLIP_BY_NAME, f"{clip.name} -> unknown {clip.fallback}"


def test_every_state_clip_exists_in_the_contract():
    from lumi.character.state_machine import STATE_SPECS

    for spec in STATE_SPECS.values():
        if spec.clip == "dragged":
            continue  # synthetic clip handled by the animation fallback table
        assert spec.clip in contract.CLIP_BY_NAME, f"state {spec.id} wants unknown clip {spec.clip}"


def test_palette_hex_matches_float_values():
    for name, rgb in contract.PALETTE.items():
        expected = contract.PALETTE_HEX[name].lstrip("#")
        actual = "".join(f"{round(c * 255):02X}" for c in rgb)
        assert actual == expected, f"{name}: {actual} != {expected}"


def test_bone_and_clip_checks_report_missing_items():
    bones = contract.check_bones(["Root", "Hips"])
    assert bones.ok is False
    assert "Head" in bones.missing

    clips = contract.check_clips(["idle"])
    assert clips.ok is False
    assert "walk" in clips.missing


def test_resolve_clip_follows_fallbacks():
    assert contract.resolve_clip("run") == "walk"
    assert contract.resolve_clip("look_around") == "idle"
    assert contract.resolve_clip("idle") == "idle"
    assert contract.resolve_clip("nonsense") is None


# --------------------------------------------------------------------------
# validator
# --------------------------------------------------------------------------
def test_fixture_builds_and_passes(tmp_path):
    path = glb_builder.write_fixture(tmp_path / "lumi_fixture.glb")
    report = validate_glb.validate_glb(path)
    assert report.ok, [i.message for i in report.errors]
    assert report.facts["triangles"] == 1
    assert len(report.facts["clips"]) == len(contract.CLIP_NAMES)


def test_missing_bone_is_an_error(tmp_path):
    bones = [b for b in contract.REQUIRED_BONE_NAMES if b != "Head"]
    path = glb_builder.write_fixture(tmp_path / "no_head.glb", bones=bones)
    report = validate_glb.validate_glb(path)
    assert not report.ok
    codes = [issue.code for issue in report.errors]
    assert "BONE002" in codes
    assert any("Head" in issue.message for issue in report.errors)


def test_missing_clips_are_errors(tmp_path):
    clips = [c for c in contract.CLIP_NAMES if c not in {"walk", "run"}]
    path = glb_builder.write_fixture(tmp_path / "no_walk.glb", clips=clips)
    report = validate_glb.validate_glb(path)
    assert not report.ok
    assert any(issue.code == "CLIP001" for issue in report.errors)


def test_unrigged_model_is_an_error(tmp_path):
    path = glb_builder.write_fixture(tmp_path / "no_skin.glb", include_skin=False)
    report = validate_glb.validate_glb(path)
    assert not report.ok
    assert any(issue.code == "BONE001" for issue in report.errors)


def test_wrong_asset_version_is_an_error(tmp_path):
    path = glb_builder.write_fixture(tmp_path / "v1.glb", asset_version="1.0")
    report = validate_glb.validate_glb(path)
    assert not report.ok
    assert any(issue.code == "GLTF001" for issue in report.errors)


def test_not_a_glb_file(tmp_path):
    path = tmp_path / "notes.glb"
    path.write_bytes(b"this is not a model at all")
    report = validate_glb.validate_glb(path)
    assert not report.ok
    assert report.errors[0].code == "GLB001"


def test_missing_file_is_reported_not_raised(tmp_path):
    report = validate_glb.validate_glb(tmp_path / "nope.glb")
    assert not report.ok
    assert report.errors[0].code == "IO001"


def test_recoloured_model_warns(tmp_path):
    path = glb_builder.write_fixture(tmp_path / "red.glb", material_color=(0.9, 0.1, 0.1, 1.0))
    report = validate_glb.validate_glb(path)
    assert report.ok  # a colour deviation is a warning, not a hard failure
    assert any(issue.code == "MAT003" for issue in report.warnings)


def test_missing_materials_warn(tmp_path):
    path = glb_builder.write_fixture(tmp_path / "no_material.glb", include_material=False)
    report = validate_glb.validate_glb(path)
    assert any(issue.code == "MAT001" for issue in report.warnings)


def test_platform_node_is_flagged(tmp_path):
    path = glb_builder.write_fixture(tmp_path / "platform.glb", extra_node_name="Display_Platform")
    report = validate_glb.validate_glb(path)
    assert any(issue.code == "CONTENT001" for issue in report.warnings)


def test_wrong_bone_parent_is_flagged(tmp_path):
    path = glb_builder.write_fixture(
        tmp_path / "bad_parent.glb", hierarchy_overrides={"Head": "Hips"}
    )
    report = validate_glb.validate_glb(path)
    assert any(issue.code == "BONE004" for issue in report.warnings)


def test_cli_returns_failure_for_broken_asset(tmp_path):
    path = glb_builder.write_fixture(tmp_path / "no_skin.glb", include_skin=False)
    assert validate_glb.main([str(path)]) == 1


def test_cli_returns_success_for_valid_asset(tmp_path):
    path = glb_builder.write_fixture(tmp_path / "ok.glb")
    out = tmp_path / "report.json"
    assert validate_glb.main([str(path), "--json", str(out)]) == 0
    assert out.exists()
