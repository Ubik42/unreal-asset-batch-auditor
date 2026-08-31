from __future__ import annotations

import json
from pathlib import Path

import pytest
from unreal_asset_batch_auditor import (
    DeliveryGroupError,
    build_delivery_group_view,
    delivery_group_path,
    update_review,
    write_delivery_group_view,
)


def _report(tmp_path: Path) -> Path:
    issues = [
        {
            "issue_id": "issue-heavy-a",
            "evidence_id": "evidence-heavy-a",
            "asset_path": "/Game/UABADemo/03_Heavy/SM_A.SM_A",
            "rule_id": "static_mesh.triangle_budget",
            "severity": "error",
            "message": "heavy",
        },
        {
            "issue_id": "issue-heavy-b",
            "evidence_id": "evidence-heavy-b",
            "asset_path": "/Game/UABADemo/03_Heavy/SM_A.SM_A",
            "rule_id": "static_mesh.vertex_budget",
            "severity": "error",
            "message": "heavy",
        },
        {
            "issue_id": "issue-dev",
            "evidence_id": "evidence-dev",
            "asset_path": "/Game/UABADemo/Developers/SM_B.SM_B",
            "rule_id": "static_mesh.package_path",
            "severity": "warning",
            "message": "wrong folder",
        },
    ]
    payload = {
        "schema_version": "unreal-asset-audit@3.0.0",
        "report_id": "report-groups",
        "asset_count": 3,
        "issue_count": len(issues),
        "collection_failure_count": 1,
        "assets": [
            {"asset_path": "/Game/UABADemo/01_Light/SM_OK.SM_OK"},
            {"asset_path": "/Game/UABADemo/03_Heavy/SM_A.SM_A"},
            {"asset_path": "/Game/UABADemo/Developers/SM_B.SM_B"},
        ],
        "issues": issues,
        "collection_failures": [
            {
                "asset_path": "/Game/UABADemo/Missing/SM_Gone.SM_Gone",
                "code": "asset_not_found",
            }
        ],
    }
    path = tmp_path / "report.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_group_path_is_stable_and_malformed_paths_are_explicit() -> None:
    assert (
        delivery_group_path("/Game/UABADemo/03_Heavy/Sub/SM_A.SM_A")
        == "/Game/UABADemo/03_Heavy"
    )
    assert delivery_group_path("/Engine/BasicShapes/Cube.Cube") == "/Engine/BasicShapes"
    assert delivery_group_path("not-an-object-path") == "/未归档路径"
    assert delivery_group_path("/OnlyRoot") == "/未归档路径"


def test_groups_reconcile_report_counts_and_sort_hotspots(tmp_path: Path) -> None:
    view = build_delivery_group_view(_report(tmp_path))
    groups = view["groups"]

    assert view["asset_count"] == 4
    assert sum(group["asset_count"] for group in groups) == 4
    assert sum(group["issue_count"] for group in groups) == 3
    assert sum(group["collection_failure_count"] for group in groups) == 1
    assert groups[0]["group_path"] == "/Game/UABADemo/Missing"
    assert groups[0]["risk_band"] == "采集阻断"
    assert groups[1]["group_path"] == "/Game/UABADemo/03_Heavy"
    assert groups[1]["issue_density"] == 2.0
    assert groups[-1]["group_path"] == "/Game/UABADemo/01_Light"
    assert groups[-1]["risk_band"] == "清洁"


def test_review_decisions_change_group_priority_without_changing_report(tmp_path: Path) -> None:
    report = _report(tmp_path)
    before = report.read_bytes()
    reviews = tmp_path / "Reviews"
    update_review(
        report,
        reviews,
        issue_id="issue-dev",
        evidence_id="evidence-dev",
        decision="fix_required",
        owner="外包负责人",
    )

    view = build_delivery_group_view(report, reviews)
    developers = next(
        group for group in view["groups"] if group["group_path"].endswith("/Developers")
    )
    assert developers["fix_required_count"] == 1
    assert developers["unreviewed_issue_count"] == 0
    assert developers["risk_band"] == "需修复"
    assert report.read_bytes() == before


def test_view_write_is_deterministic_and_rejects_count_mismatch(tmp_path: Path) -> None:
    report = _report(tmp_path)
    output = tmp_path / "delivery-groups.json"
    first = write_delivery_group_view(report, output)
    first_bytes = output.read_bytes()
    second = write_delivery_group_view(report, output)

    assert first == second
    assert output.read_bytes() == first_bytes

    broken = json.loads(report.read_text(encoding="utf-8"))
    broken["asset_count"] = 99
    report.write_text(json.dumps(broken), encoding="utf-8")
    with pytest.raises(DeliveryGroupError, match="asset_count"):
        build_delivery_group_view(report)
