from __future__ import annotations

import json
from pathlib import Path

import pytest
from unreal_asset_batch_auditor import (
    MaterialAuditProfile,
    MaterialFixtureCollector,
    MaterialInterfaceMetadata,
    MaterialUnrealCppCollector,
    audit_materials,
)
from unreal_asset_batch_auditor.contracts import ContractError
from unreal_asset_batch_auditor.panel_task import PanelAuditTask

ROOT = Path(__file__).parents[1]
PROFILE = ROOT / "Resources/Profiles/material-desktop-balanced.v1.json"
FIXTURE = ROOT / "tests/fixtures/materials.v1.json"


def test_material_profile_and_metadata_are_versioned_and_strict() -> None:
    profile = MaterialAuditProfile.load(PROFILE)
    assert profile.profile_id == "material-desktop-balanced-v1"
    assert profile.parent_depth.max_count == 2
    assert profile.allowed_blend_modes.allowed_values == (
        "BLEND_Opaque",
        "BLEND_Masked",
    )

    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))["assets"][1]
    material = MaterialInterfaceMetadata.from_dict(raw)
    assert material.material_kind == "material_instance"
    assert material.has_parent is True
    with pytest.raises(ContractError, match="texture_dependency_count"):
        MaterialInterfaceMetadata.from_dict({**raw, "texture_dependency_count": 9})


def test_material_audit_covers_domain_blend_two_sided_parent_and_textures() -> None:
    report = audit_materials(
        profile=MaterialAuditProfile.load(PROFILE),
        collector=MaterialFixtureCollector(FIXTURE),
        report_id_factory=lambda: "material-fixture-report",
    )

    assert report.schema_version == "unreal-material-audit@1.0.0"
    assert report.asset_type == "material_interface"
    assert report.real_unreal_validation is False
    assert report.asset_count == 4
    issue_keys = {(issue.asset_path, issue.rule_id) for issue in report.issues}
    assert not any(path.endswith("M_Prop_Master.M_Prop_Master") for path, _ in issue_keys)
    assert not any(path.endswith("MI_Prop_Blue.MI_Prop_Blue") for path, _ in issue_keys)
    deep_rules = {
        rule
        for path, rule in issue_keys
        if path.endswith("MI_Deep_Translucent.MI_Deep_Translucent")
    }
    assert deep_rules == {
        "material.allowed_blend_mode",
        "material.two_sided",
        "material.parent_depth",
        "material.texture_dependencies",
        "material.texture_dimension",
    }
    assert (
        "/Game/Materials/M_Post_Process.M_Post_Process",
        "material.allowed_domain",
    ) in issue_keys
    assert {proof.profile_pointer for proof in report.evidence} >= {
        "/rules/allowed_blend_modes/allowed_values",
        "/rules/parent_depth/max_count",
        "/rules/texture_dimension/max_size",
    }


def test_material_audit_is_deterministic_except_timestamp() -> None:
    kwargs = {
        "profile": MaterialAuditProfile.load(PROFILE),
        "collector": MaterialFixtureCollector(FIXTURE),
        "asset_paths": [
            "/Game/Materials/MI_Deep_Translucent.MI_Deep_Translucent",
            "/Game/Materials/M_Prop_Master.M_Prop_Master",
        ],
        "batch_size": 1,
    }
    first = audit_materials(**kwargs).to_dict()
    second = audit_materials(**kwargs).to_dict()
    first.pop("created_at")
    second.pop("created_at")
    assert first == second
    assert first["completed_batch_count"] == 2


class _MaterialRow:
    asset_path = "/Game/M.M"
    asset_name = "M"
    material_kind = "material"
    material_domain = "MD_Surface"
    blend_mode = "BLEND_Opaque"
    two_sided = False
    shading_models = ("MSM_DefaultLit",)
    parent_path = ""
    base_material_path = "/Game/M.M"
    parent_depth = 0
    texture_paths = ("/Game/T.T",)
    texture_dependency_count = 1
    max_texture_dimension = 1024
    collected = True


class _Library:
    @staticmethod
    def collect_material_interface_metadata(paths: list[str]) -> list[_MaterialRow]:
        assert paths == ["/Game/M.M"]
        return [_MaterialRow()]


class _SystemLibrary:
    @staticmethod
    def get_engine_version() -> str:
        return "5.8.1-test"


class _Unreal:
    UnrealAssetBatchAuditorLibrary = _Library
    SystemLibrary = _SystemLibrary


def test_material_cpp_adapter_maps_host_rows_without_mutation_api() -> None:
    collector = MaterialUnrealCppCollector(_Unreal())
    batch = collector.collect(["/Game/M.M"])
    assert collector.real_unreal_validation is True
    assert batch.assets[0].material_domain == "MD_Surface"
    assert batch.assets[0].texture_dependency_count == 1
    assert batch.failures == []


def test_panel_task_routes_material_request_to_material_report(tmp_path: Path) -> None:
    request = {
        "asset_type": "material_interface",
        "task_id": "material-panel-task",
        "profile_path": str(PROFILE),
        "asset_paths": [
            "/Game/Materials/M_Prop_Master.M_Prop_Master",
            "/Game/Materials/MI_Deep_Translucent.MI_Deep_Translucent",
        ],
        "batch_size": 1,
        "output_path": str(tmp_path / "report.json"),
        "session_root": str(tmp_path / "Sessions"),
        "handoff_root": str(tmp_path / "Handoffs"),
        "state_path": str(tmp_path / "task-state.json"),
        "cancel_path": str(tmp_path / "cancel.json"),
    }
    task = PanelAuditTask(request, MaterialFixtureCollector(FIXTURE))
    while not task.tick():
        pass

    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["asset_type"] == "material_interface"
    assert report["asset_count"] == 2
    assert (tmp_path / "Handoffs" / report["report_id"] / "交付目录热区.csv").exists()
