from __future__ import annotations

import json
from pathlib import Path

import run_asset_audit
from unreal_asset_batch_auditor import AuditProfile

ROOT = Path(__file__).resolve().parents[1]


def test_panel_request_file_forwards_explicit_inputs(tmp_path: Path, monkeypatch) -> None:
    request_path = tmp_path / "panel-request.json"
    request_path.write_text(
        json.dumps(
            {
                "profile_path": "D:/Profiles/mobile.json",
                "asset_paths": ["/Game/A.A", "/Game/B.B"],
                "output_path": "D:/Saved/latest-report.json",
                "batch_size": 8,
            }
        ),
        encoding="utf-8",
    )
    captured: dict = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return {"report_id": "report-panel-test"}

    monkeypatch.setattr(run_asset_audit, "run", fake_run)

    result = run_asset_audit.run_from_request_file(str(request_path))

    assert result == {"report_id": "report-panel-test"}
    assert captured == {
        "profile_path": "D:/Profiles/mobile.json",
        "asset_paths": ["/Game/A.A", "/Game/B.B"],
        "output_path": "D:/Saved/latest-report.json",
        "batch_size": 8,
        "session_root": None,
    }


def test_all_packaged_panel_profiles_are_valid() -> None:
    profiles = sorted((ROOT / "Resources" / "Profiles").glob("*.v2.json"))

    assert [path.name for path in profiles] == [
        "desktop-balanced.v2.json",
        "mobile-strict.v2.json",
        "review-lenient.v2.json",
    ]
    assert {AuditProfile.load(path).profile_id for path in profiles} == {
        "demo-desktop-balanced-v2",
        "demo-mobile-strict-v2",
        "demo-review-lenient-v2",
    }


def test_native_panel_exposes_complete_asset_ledger_and_issue_detail_views() -> None:
    source = (
        ROOT
        / "Source"
        / "UnrealAssetBatchAuditor"
        / "Private"
        / "SUnrealAssetAuditPanel.cpp"
    ).read_text(encoding="utf-8")

    assert 'TEXT("资产总览")' in source
    assert 'TEXT("问题明细")' in source
    assert 'Root->GetArrayField(TEXT("assets"))' in source
    assert 'Root->GetArrayField(TEXT("issues"))' in source
    assert 'Root->GetArrayField(TEXT("collection_failures"))' in source
    assert 'TEXT("session_root")' in source
    assert 'TEXT("三角形")' in source
    assert 'TEXT("材质槽")' in source
    assert 'TEXT("回归对比")' in source
    assert 'TEXT("回归基线（同一 Profile）")' in source
    assert 'TEXT("与所选基线比较")' in source


def test_panel_comparison_request_writes_versioned_result(tmp_path: Path) -> None:
    def report(report_id: str, issues: list[dict]) -> dict:
        return {
            "schema_version": "unreal-asset-audit@2.0.0",
            "report_id": report_id,
            "created_at": "2026-08-28T01:00:00+00:00",
            "profile_id": "desktop",
            "profile_version": "2.0.0",
            "asset_count": 1,
            "issue_count": len(issues),
            "collection_failure_count": 0,
            "issues": issues,
            "collection_failures": [],
        }

    baseline = report("baseline", [])
    current = report(
        "current",
        [
            {
                "asset_path": "/Game/A.A",
                "rule_id": "static_mesh.material_slots",
                "severity": "warning",
                "message": "Material slots exceed limit.",
            }
        ],
    )
    baseline_path = tmp_path / "baseline.json"
    current_path = tmp_path / "current.json"
    output_path = tmp_path / "comparison.json"
    request_path = tmp_path / "request.json"
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
    current_path.write_text(json.dumps(current), encoding="utf-8")
    request_path.write_text(
        json.dumps(
            {
                "baseline_report_path": str(baseline_path),
                "current_report_path": str(current_path),
                "output_path": str(output_path),
            }
        ),
        encoding="utf-8",
    )

    result = run_asset_audit.compare_from_request_file(str(request_path))

    assert result["schema_version"] == "unreal-audit-comparison@1.0.0"
    assert result["status"] == "ready"
    assert len(result["new_issues"]) == 1
    assert json.loads(output_path.read_text(encoding="utf-8")) == result
