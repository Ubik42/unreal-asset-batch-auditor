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
    names = [
        "desktop-balanced.v3.json",
        "mobile-strict.v3.json",
        "review-lenient.v3.json",
    ]
    profiles = [ROOT / "Resources" / "Profiles" / name for name in names]

    assert [path.name for path in profiles] == [
        "desktop-balanced.v3.json",
        "mobile-strict.v3.json",
        "review-lenient.v3.json",
    ]
    assert {AuditProfile.load(path).profile_id for path in profiles} == {
        "demo-desktop-balanced-v3",
        "demo-mobile-strict-v3",
        "demo-review-lenient-v3",
    }
    evidence_profile = AuditProfile.load(
        ROOT / "Resources" / "Profiles" / "host-material-evidence.v3.json"
    )
    assert "证据专用模拟规则" in evidence_profile.description
    assert evidence_profile.texture_dependencies is not None
    assert evidence_profile.texture_dependencies.max_value == 1


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
    assert 'TEXT("纹理/最大")' in source
    assert 'TEXT("交付风险谱")' in source
    assert 'TEXT("回归对比")' in source
    assert 'TEXT("回归基线（同一 Profile）")' in source
    assert 'TEXT("与所选基线比较")' in source
    assert 'TEXT("批次间取消")' in source
    assert 'TEXT("导出团队包")' in source
    assert "current-task-state.json" in source
    assert "start_panel_task" in source


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


def test_panel_handoff_request_exports_without_rescan(tmp_path: Path, monkeypatch) -> None:
    request_path = tmp_path / "handoff-request.json"
    request_path.write_text(
        json.dumps(
            {
                "report_path": str(tmp_path / "report.json"),
                "output_root": str(tmp_path / "handoffs"),
            }
        ),
        encoding="utf-8",
    )
    captured: list[tuple[str, str]] = []

    class Result:
        root = tmp_path / "handoffs" / "report-1"
        html_path = root / "审计交接报告.html"
        csv_path = root / "审计问题明细.csv"
        manifest_path = root / "交接清单.json"

    def fake_export(report_path: str, output_root: str):
        captured.append((report_path, output_root))
        return Result()

    monkeypatch.setattr(run_asset_audit, "export_handoff", fake_export)

    result = run_asset_audit.export_handoff_from_request_file(str(request_path))

    assert captured == [(str(tmp_path / "report.json"), str(tmp_path / "handoffs"))]
    assert result["root"].endswith("report-1")
    assert result["html_path"].endswith("审计交接报告.html")
