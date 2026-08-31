from __future__ import annotations

import json
from pathlib import Path

import pytest
from unreal_asset_batch_auditor import (
    clone_as_project_profile,
    diff_profiles,
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
