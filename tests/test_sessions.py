from __future__ import annotations

import json
from pathlib import Path

import pytest
from unreal_asset_batch_auditor import SessionError, SessionStore, compare_reports


def _report(
    path: Path,
    *,
    report_id: str,
    created_at: str,
    issues: list[tuple[str, str]],
    failures: list[str],
) -> None:
    payload = {
        "schema_version": "unreal-asset-audit@2.0.0",
        "report_id": report_id,
        "created_at": created_at,
        "profile_id": "test-profile",
        "profile_version": "2.0.0",
        "asset_count": 3,
        "issue_count": len(issues),
        "collection_failure_count": len(failures),
        "issues": [
            {
                "asset_path": asset_path,
                "rule_id": rule_id,
                "severity": "warning",
                "message": f"{asset_path}:{rule_id}",
            }
            for asset_path, rule_id in issues
        ],
        "collection_failures": [
            {"asset_path": item, "code": "FAILED", "message": "failed"}
            for item in failures
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_session_store_preserves_immutable_report_and_deduplicates_index(
    tmp_path: Path,
) -> None:
    source = tmp_path / "latest.json"
    _report(
        source,
        report_id="report-a",
        created_at="2026-08-28T01:02:03+00:00",
        issues=[("/Game/A.A", "rule.a")],
        failures=[],
    )
    store = SessionStore(tmp_path / "Sessions")

    first = store.save_report(source)
    second = store.save_report(source)

    assert first == second
    loaded = store.load_index()
    assert loaded.diagnostics == ()
    assert loaded.sessions == (first,)
    historical = store.root / first.report_path
    assert historical.read_bytes() == source.read_bytes()


def test_session_store_refuses_to_overwrite_changed_historical_report(tmp_path: Path) -> None:
    source = tmp_path / "latest.json"
    _report(
        source,
        report_id="report-a",
        created_at="2026-08-28T01:02:03+00:00",
        issues=[],
        failures=[],
    )
    store = SessionStore(tmp_path / "Sessions")
    record = store.save_report(source)
    (store.root / record.report_path).write_text("tampered", encoding="utf-8")

    with pytest.raises(SessionError, match="拒绝覆盖"):
        store.save_report(source)


def test_invalid_index_returns_localized_diagnostic_without_deleting_reports(
    tmp_path: Path,
) -> None:
    store = SessionStore(tmp_path / "Sessions")
    store.reports_dir.mkdir(parents=True)
    historical = store.reports_dir / "keep.json"
    historical.write_text("keep", encoding="utf-8")
    store.index_path.write_text("{broken", encoding="utf-8")

    loaded = store.load_index()

    assert loaded.sessions == ()
    assert loaded.diagnostics and "历史报告未被删除" in loaded.diagnostics[0]
    assert historical.read_text(encoding="utf-8") == "keep"


def test_comparison_classifies_new_persistent_resolved_and_failures(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    _report(
        baseline,
        report_id="baseline",
        created_at="2026-08-28T01:00:00+00:00",
        issues=[("/Game/A.A", "rule.a"), ("/Game/B.B", "rule.b")],
        failures=["/Game/OldFailure.OldFailure", "/Game/Shared.Shared"],
    )
    _report(
        current,
        report_id="current",
        created_at="2026-08-28T02:00:00+00:00",
        issues=[("/Game/A.A", "rule.a"), ("/Game/C.C", "rule.c")],
        failures=["/Game/NewFailure.NewFailure", "/Game/Shared.Shared"],
    )

    result = compare_reports(baseline, current)

    assert [item["asset_path"] for item in result.new_issues] == ["/Game/C.C"]
    assert [item["asset_path"] for item in result.persistent_issues] == ["/Game/A.A"]
    assert [item["asset_path"] for item in result.resolved_issues] == ["/Game/B.B"]
    assert [item["asset_path"] for item in result.new_failures] == [
        "/Game/NewFailure.NewFailure"
    ]
    assert [item["asset_path"] for item in result.persistent_failures] == [
        "/Game/Shared.Shared"
    ]
    assert [item["asset_path"] for item in result.resolved_failures] == [
        "/Game/OldFailure.OldFailure"
    ]
