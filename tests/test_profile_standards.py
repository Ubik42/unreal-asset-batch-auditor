from __future__ import annotations

import json
from pathlib import Path

import pytest
from unreal_asset_batch_auditor import (
    build_profile_editor_view,
    clone_as_project_profile,
    diff_profiles,
    evaluate_profile_edit,
    save_project_profile,
    validate_profile,
)
from unreal_asset_batch_auditor.contracts import ContractError

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "name,asset_type",
    [
        ("desktop-balanced.v3.json", "static_mesh"),
        ("texture-desktop-balanced.v1.json", "texture2d"),
        ("material-desktop-balanced.v1.json", "material_interface"),
    ],
)
def test_validate_supported_profile_tracks(name: str, asset_type: str) -> None:
    raw = json.loads((ROOT / "Resources" / "Profiles" / name).read_text(encoding="utf-8"))

    result = validate_profile(raw)

    assert result.valid is True
    assert result.asset_type == asset_type
    assert result.errors == {}


def test_validation_returns_localized_field_error() -> None:
    raw = json.loads(
        (ROOT / "Resources" / "Profiles" / "desktop-balanced.v3.json").read_text(
            encoding="utf-8"
        )
    )
    raw["rules"]["triangle_budget"]["max_lod0"] = 0

    result = validate_profile(raw)

    assert result.valid is False
    assert "rules.triangle_budget.max_lod0" in result.errors
    assert "LOD0 上限" in result.errors["rules.triangle_budget.max_lod0"]
    assert "不能小于 1" in result.errors["rules.triangle_budget.max_lod0"]


def test_diff_is_stable_and_ignores_object_key_order() -> None:
    source = {"profile_id": "one", "rules": {"b": {"enabled": True}, "a": 4}}
    reordered = {"rules": {"a": 4, "b": {"enabled": True}}, "profile_id": "one"}
    assert diff_profiles(source, reordered) == []

    draft = {"rules": {"a": 8, "c": {"enabled": False}}, "profile_id": "one"}
    changes = diff_profiles(source, draft)
    assert [(item.path, item.change) for item in changes] == [
        ("rules.a", "changed"),
        ("rules.b", "removed"),
        ("rules.c", "added"),
    ]


def test_clone_uses_project_directory_without_touching_builtin(tmp_path: Path) -> None:
    source = ROOT / "Resources" / "Profiles" / "desktop-balanced.v3.json"
    original = source.read_bytes()

    first = clone_as_project_profile(source, tmp_path)
    second = clone_as_project_profile(source, tmp_path)

    assert first.parent == tmp_path
    assert first.name == "demo-desktop-balanced-v3-project.v3.json"
    assert second.name == "demo-desktop-balanced-v3-project-2.v3.json"
    assert source.read_bytes() == original
    assert json.loads(first.read_text(encoding="utf-8"))["profile_version"] == "1.0.0"


def test_atomic_save_rejects_invalid_profile(tmp_path: Path) -> None:
    destination = tmp_path / "profile.v3.json"
    destination.write_text("keep", encoding="utf-8")
    invalid = json.loads(
        (ROOT / "Resources" / "Profiles" / "desktop-balanced.v3.json").read_text(
            encoding="utf-8"
        )
    )
    invalid["rules"]["triangle_budget"]["max_lod0"] = 0

    with pytest.raises(ContractError, match="LOD0 上限"):
        save_project_profile(invalid, destination)

    assert destination.read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize(
    "name,rule_count,required_path",
    [
        ("desktop-balanced.v3.json", 14, "rules.triangle_budget.max_lod0"),
        ("texture-desktop-balanced.v1.json", 7, "rules.compression_color_space.allowed_combinations"),
        ("material-desktop-balanced.v1.json", 7, "rules.parent_depth.max_count"),
    ],
)
def test_editor_view_describes_supported_fields(
    name: str, rule_count: int, required_path: str
) -> None:
    view = build_profile_editor_view(ROOT / "Resources" / "Profiles" / name)
    paths = {
        field["path"]
        for rule in view["rules"]
        for field in rule["fields"]
    }

    assert view["schema_version"] == "unreal-profile-editor-view@1.0.0"
    assert len(view["rules"]) == rule_count
    assert required_path in paths
    assert {field["path"] for field in view["identity_fields"]} == {
        "profile_id",
        "profile_version",
        "description",
    }


def test_editor_preview_returns_stable_changes_without_writing(tmp_path: Path) -> None:
    source = clone_as_project_profile(
        ROOT / "Resources" / "Profiles" / "desktop-balanced.v3.json", tmp_path
    )
    original = source.read_bytes()

    result = evaluate_profile_edit(
        source,
        {
            "profile_version": "1.1.0",
            "rules.triangle_budget.max_lod0": "3200",
            "rules.nanite.enabled": False,
            "rules.nanite.severity": "info",
        },
    )

    assert result["status"] == "ready"
    assert [change["path"] for change in result["changes"]] == [
        "profile_version",
        "rules.nanite.enabled",
        "rules.nanite.severity",
        "rules.triangle_budget.max_lod0",
    ]
    assert source.read_bytes() == original


def test_editor_rejects_field_values_with_localized_errors(tmp_path: Path) -> None:
    source = clone_as_project_profile(
        ROOT / "Resources" / "Profiles" / "texture-desktop-balanced.v1.json", tmp_path
    )

    result = evaluate_profile_edit(
        source,
        {
            "profile_id": "INVALID ID",
            "profile_version": "next",
            "rules.source_dimension.max_size": "4K",
            "rules.streaming.expected": "sometimes",
            "rules.compression_color_space.allowed_combinations": "broken",
        },
    )

    assert result["status"] == "invalid"
    assert "3–64" in result["errors"]["profile_id"]
    assert "x.y.z" in result["errors"]["profile_version"]
    assert "必须填写整数" in result["errors"]["rules.source_dimension.max_size"]
    assert "请选择有效选项" in result["errors"]["rules.streaming.expected"]
    assert "应写成" in result["errors"][
        "rules.compression_color_space.allowed_combinations"
    ]


def test_editor_save_is_confined_to_project_profile_root(tmp_path: Path) -> None:
    root = tmp_path / "Config" / "AssetAudit" / "Profiles"
    source = clone_as_project_profile(
        ROOT / "Resources" / "Profiles" / "texture-desktop-balanced.v1.json", root
    )

    result = evaluate_profile_edit(
        source,
        {
            "profile_id": "project-texture-standard",
            "profile_version": "2.0.0",
            "rules.source_dimension.max_size": "2048",
            "rules.streaming.enabled": False,
            "rules.streaming.expected": "disabled",
        },
        save=True,
        project_profile_root=root,
    )

    saved = json.loads(source.read_text(encoding="utf-8"))
    assert result["status"] == "saved"
    assert result["change_count"] == 5
    assert saved["profile_id"] == "project-texture-standard"
    assert saved["rules"]["source_dimension"]["max_size"] == 2048
    assert saved["rules"]["streaming"] == {
        "enabled": False,
        "expected": "disabled",
        "severity": "warning",
    }

    with pytest.raises(ContractError, match="内置模板保持只读"):
        evaluate_profile_edit(
            ROOT / "Resources" / "Profiles" / "texture-desktop-balanced.v1.json",
            {"profile_version": "2.0.0"},
            save=True,
            project_profile_root=root,
        )


def test_material_editor_previews_render_state_and_parent_policy(tmp_path: Path) -> None:
    source = clone_as_project_profile(
        ROOT / "Resources" / "Profiles" / "material-desktop-balanced.v1.json",
        tmp_path,
    )

    result = evaluate_profile_edit(
        source,
        {
            "profile_version": "1.1.0",
            "rules.allowed_blend_modes.allowed_values": "BLEND_Opaque",
            "rules.parent_depth.max_count": "3",
            "rules.two_sided.expected": "enabled",
        },
    )

    assert result["status"] == "ready"
    assert [item["path"] for item in result["changes"]] == [
        "profile_version",
        "rules.allowed_blend_modes.allowed_values",
        "rules.parent_depth.max_count",
        "rules.two_sided.expected",
    ]


def test_demo_project_standards_are_supported_and_explicitly_simulated() -> None:
    model = ROOT / "Demo" / "ProjectStandards" / "environment-prop-pc.v3.json"
    texture = ROOT / "Demo" / "ProjectStandards" / "mobile-prop-texture.v1.json"

    assert validate_profile(json.loads(model.read_text(encoding="utf-8"))).asset_type == "static_mesh"
    assert validate_profile(json.loads(texture.read_text(encoding="utf-8"))).asset_type == "texture2d"
    assert "自行模拟" in model.read_text(encoding="utf-8")
    assert "自行模拟" in texture.read_text(encoding="utf-8")
