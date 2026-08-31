from __future__ import annotations

import json
from pathlib import Path

from unreal_asset_batch_auditor import AuditProfile, FixtureCollector, audit_assets

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "config" / "Profiles" / "default-static-mesh-profile.v1.json"
FIXTURE = ROOT / "tests" / "fixtures" / "static_meshes.v1.json"
PROFILE_V2 = ROOT / "config" / "Profiles" / "default-static-mesh-profile.v2.json"
FIXTURE_V2 = ROOT / "tests" / "fixtures" / "static_meshes.v2.json"
PROFILE_V3 = ROOT / "config" / "Profiles" / "default-static-mesh-profile.v3.json"
FIXTURE_V3 = ROOT / "tests" / "fixtures" / "static_meshes.v3.json"


def test_problem_asset_emits_all_five_profile_driven_issues() -> None:
    report = audit_assets(
        profile=AuditProfile.load(PROFILE),
        collector=FixtureCollector(FIXTURE),
        asset_paths=["/Game/Props/SM_Problem.SM_Problem"],
    )
    assert report.issue_count == 5
    assert {issue.rule_id for issue in report.issues} == {
        "static_mesh.triangle_budget.lod0",
        "static_mesh.vertex_budget.lod0",
        "static_mesh.material_slots",
        "static_mesh.lod_count",
        "static_mesh.nanite_state",
    }
    assert len(report.evidence) == report.issue_count
    assert all(item.profile_pointer.startswith("/rules/") for item in report.evidence)


def test_healthy_asset_passes() -> None:
    report = audit_assets(
        profile=AuditProfile.load(PROFILE),
        collector=FixtureCollector(FIXTURE),
        asset_paths=["/Game/Props/SM_Healthy.SM_Healthy"],
    )
    assert report.asset_count == 1
    assert report.assets[0].asset_path == "/Game/Props/SM_Healthy.SM_Healthy"
    assert report.assets[0].lods[0].triangles > 0
    assert report.issue_count == 0


def test_fixture_report_is_explicitly_not_real_unreal_evidence() -> None:
    report = audit_assets(
        profile=AuditProfile.load(PROFILE), collector=FixtureCollector(FIXTURE)
    )
    assert report.collection_mode == "offline_fixture"
    assert report.real_unreal_validation is False
    assert all(item.collector == "offline_fixture" for item in report.evidence)


def test_issue_and_evidence_ids_are_reproducible() -> None:
    profile = AuditProfile.load(PROFILE)
    first = audit_assets(profile=profile, collector=FixtureCollector(FIXTURE))
    second = audit_assets(profile=profile, collector=FixtureCollector(FIXTURE))
    assert [issue.issue_id for issue in first.issues] == [issue.issue_id for issue in second.issues]
    assert [item.evidence_id for item in first.evidence] == [
        item.evidence_id for item in second.evidence
    ]


def test_v2_problem_asset_adds_collision_and_lightmap_issues() -> None:
    report = audit_assets(
        profile=AuditProfile.load(PROFILE_V2),
        collector=FixtureCollector(FIXTURE_V2),
        asset_paths=["/Game/Props/SM_Problem.SM_Problem"],
    )

    assert report.schema_version == "unreal-asset-audit@2.0.0"
    assert report.issue_count == 8
    assert {
        "static_mesh.simple_collision",
        "static_mesh.lightmap_uv",
        "static_mesh.lightmap_resolution",
    }.issubset({issue.rule_id for issue in report.issues})
    assert report.assets[0].simple_collision_primitive_count == 0
    assert report.assets[0].has_valid_lightmap_uv is False


def test_v2_complex_as_simple_can_satisfy_profile_collision_policy() -> None:
    report = audit_assets(
        profile=AuditProfile.load(PROFILE_V2),
        collector=FixtureCollector(FIXTURE_V2),
        asset_paths=["/Game/Props/SM_ComplexCollision.SM_ComplexCollision"],
    )

    assert "static_mesh.simple_collision" not in {issue.rule_id for issue in report.issues}
    assert report.issue_count == 1  # only the three-LOD project policy fails


def test_v2_name_and_package_policy_are_profile_driven() -> None:
    raw = json.loads(PROFILE_V2.read_text(encoding="utf-8"))
    raw["rules"]["object_name"] = {
        "enabled": True,
        "required_prefixes": ["ENV_"],
        "pattern": r"^ENV_[A-Z0-9_]+$",
        "severity": "error",
    }
    raw["rules"]["package_path"] = {
        "enabled": True,
        "allowed_roots": ["/Game/Production/Environment"],
        "forbidden_segments": ["Developers", "Temp"],
        "severity": "warning",
    }
    report = audit_assets(
        profile=AuditProfile.from_dict(raw),
        collector=FixtureCollector(FIXTURE_V2),
        asset_paths=["/Game/Props/SM_Healthy.SM_Healthy"],
    )

    policy_issues = {
        issue.rule_id: issue for issue in report.issues
        if issue.rule_id in {"static_mesh.object_name", "static_mesh.package_path"}
    }
    assert set(policy_issues) == {"static_mesh.object_name", "static_mesh.package_path"}
    evidence = {item.metric: item for item in report.evidence}
    assert evidence["asset_name"].observed == "SM_Healthy"
    assert evidence["package_directory"].observed == "/Game/Props"


def test_v3_material_risk_emits_profile_driven_dependency_issues() -> None:
    report = audit_assets(
        profile=AuditProfile.load(PROFILE_V3),
        collector=FixtureCollector(FIXTURE_V3),
        asset_paths=["/Game/Props/SM_MaterialRisk.SM_MaterialRisk"],
    )

    assert report.schema_version == "unreal-asset-audit@3.0.0"
    dependency_rules = {
        "static_mesh.missing_materials",
        "static_mesh.unique_materials",
        "static_mesh.texture_dependencies",
        "static_mesh.texture_dimension",
    }
    assert dependency_rules.issubset({issue.rule_id for issue in report.issues})
    dependency_evidence = {
        item.metric: item
        for item in report.evidence
        if item.metric in {
            "missing_material_slot_count",
            "unique_material_count",
            "texture_dependency_count",
            "max_texture_dimension",
        }
    }
    assert dependency_evidence["missing_material_slot_count"].observed == 1
    assert dependency_evidence["max_texture_dimension"].expected == 4096
    assert all(item.profile_pointer.startswith("/rules/") for item in dependency_evidence.values())
    assert report.assets[0].material_paths[0].startswith("/Game/Materials/")
    assert report.assets[0].texture_dependency_count == 17


def test_v3_dependency_policies_can_be_disabled_independently() -> None:
    raw = json.loads(PROFILE_V3.read_text(encoding="utf-8"))
    dependency_names = (
        "missing_materials",
        "unique_materials",
        "texture_dependencies",
        "texture_dimension",
    )
    for name in dependency_names:
        raw["rules"][name]["enabled"] = False
    report = audit_assets(
        profile=AuditProfile.from_dict(raw),
        collector=FixtureCollector(FIXTURE_V3),
        asset_paths=["/Game/Props/SM_MaterialRisk.SM_MaterialRisk"],
    )
    assert not {
        f"static_mesh.{name}" for name in dependency_names
    }.intersection(issue.rule_id for issue in report.issues)
