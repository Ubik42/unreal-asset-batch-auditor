from __future__ import annotations

from pathlib import Path

from unreal_asset_batch_auditor import AuditProfile, FixtureCollector, audit_assets

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "config" / "Profiles" / "default-static-mesh-profile.v1.json"
FIXTURE = ROOT / "tests" / "fixtures" / "static_meshes.v1.json"


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
