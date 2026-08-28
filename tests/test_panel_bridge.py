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
    assert 'TEXT("三角形")' in source
    assert 'TEXT("材质槽")' in source
