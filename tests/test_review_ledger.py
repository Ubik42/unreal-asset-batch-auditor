from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from unreal_asset_batch_auditor import (
    REVIEW_LEDGER_VERSION,
    ReviewLedgerError,
    load_review_snapshot,
    update_review,
    write_review_view,
)


def _write_report(path: Path, *, report_id: str = "report-review") -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": "unreal-asset-audit@3.0.0",
                "report_id": report_id,
                "issues": [
                    {
                        "issue_id": "issue-a",
                        "evidence_id": "ev-a",
                        "asset_path": "/Engine/BasicShapes/Cube.Cube",
                        "rule_id": "static_mesh.object_name",
                    },
                    {
                        "issue_id": "issue-b",
                        "evidence_id": "ev-b",
                        "asset_path": "/Engine/BasicShapes/Cone.Cone",
                        "rule_id": "static_mesh.package_path",
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def test_review_update_is_atomic_stable_and_does_not_modify_report(tmp_path: Path) -> None:
    report = _write_report(tmp_path / "report.json")
    before = report.read_bytes()
    clock = lambda: datetime(2026, 8, 30, 12, 0, tzinfo=UTC)

    snapshot = update_review(
        report,
        tmp_path / "Reviews",
        issue_id="issue-b",
        evidence_id="ev-b",
        decision="fix_required",
        owner="环境组 / 小林",
        note="移动到项目允许目录后复检",
        now_factory=clock,
    )
    update_review(
        report,
        tmp_path / "Reviews",
        issue_id="issue-a",
        evidence_id="ev-a",
        decision="approved_exception",
        owner="主美",
        note="引擎内置演示资产，仅用于工具验证",
        now_factory=clock,
    )

    raw = json.loads(snapshot.ledger_path.read_text(encoding="utf-8"))
    assert raw["schema_version"] == REVIEW_LEDGER_VERSION
    assert report.read_bytes() == before
    final = load_review_snapshot(report, tmp_path / "Reviews")
    assert [item["issue_id"] for item in final.records] == ["issue-a", "issue-b"]
    assert not list(snapshot.ledger_path.parent.glob("*.tmp"))


def test_unreviewed_removes_decision_without_rewriting_report(tmp_path: Path) -> None:
    report = _write_report(tmp_path / "report.json")
    update_review(
        report,
        tmp_path / "Reviews",
        issue_id="issue-a",
        evidence_id="ev-a",
        decision="fix_required",
    )
    snapshot = update_review(
        report,
        tmp_path / "Reviews",
        issue_id="issue-a",
        evidence_id="ev-a",
        decision="unreviewed",
    )
    assert snapshot.records == ()


def test_changed_report_with_same_id_preserves_records_as_orphans(tmp_path: Path) -> None:
    report = _write_report(tmp_path / "report.json")
    update_review(
        report,
        tmp_path / "Reviews",
        issue_id="issue-a",
        evidence_id="ev-a",
        decision="fix_required",
    )
    raw = json.loads(report.read_text(encoding="utf-8"))
    raw["issues"] = [raw["issues"][1]]
    report.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")

    snapshot = load_review_snapshot(report, tmp_path / "Reviews")
    assert snapshot.records == ()
    assert [item["issue_id"] for item in snapshot.orphan_records] == ["issue-a"]
    with pytest.raises(ReviewLedgerError, match="孤儿记录"):
        update_review(
            report,
            tmp_path / "Reviews",
            issue_id="issue-b",
            evidence_id="ev-b",
            decision="approved_exception",
        )


def test_corrupt_ledger_is_isolated_and_view_remains_usable(tmp_path: Path) -> None:
    report = _write_report(tmp_path / "report.json")
    reviews = tmp_path / "Reviews"
    reviews.mkdir()
    ledger = reviews / "report-review.review.v1.json"
    ledger.write_text("{broken", encoding="utf-8")

    view_path = tmp_path / "review-view.json"
    view = write_review_view(report, reviews, view_path)
    assert view["records"] == []
    assert view["isolated_corrupt_path"]
    assert Path(view["isolated_corrupt_path"]).read_text(encoding="utf-8") == "{broken"
    assert not ledger.exists()
    assert json.loads(view_path.read_text(encoding="utf-8"))["orphan_count"] == 0
    assert json.loads(view_path.read_text(encoding="utf-8"))["counts"]["unreviewed"] == 2


def test_review_rejects_unknown_issue_and_oversized_fields(tmp_path: Path) -> None:
    report = _write_report(tmp_path / "report.json")
    with pytest.raises(ReviewLedgerError, match="找不到"):
        update_review(
            report,
            tmp_path / "Reviews",
            issue_id="missing",
            evidence_id="missing",
            decision="fix_required",
        )
    with pytest.raises(ReviewLedgerError, match="最多"):
        update_review(
            report,
            tmp_path / "Reviews",
            issue_id="issue-a",
            evidence_id="ev-a",
            decision="fix_required",
            owner="x" * 81,
        )
