"""Explicit Unreal Editor orchestration entry point; importing this file performs no scan."""

import json
from collections.abc import Callable
from pathlib import Path

from unreal_asset_batch_auditor import (
    AuditProfile,
    BatchProgress,
    SessionStore,
    UnrealCppCollector,
    audit_assets,
    compare_reports,
    export_handoff,
    update_review,
    write_delivery_group_view,
    write_review_view,
)


def run(
    profile_path: str,
    asset_paths: list[str],
    output_path: str,
    *,
    batch_size: int = 128,
    should_cancel: Callable[[], bool] | None = None,
    on_progress: Callable[[BatchProgress], None] | None = None,
    session_root: str | None = None,
) -> dict:
    """Collect explicit Static Mesh paths through C++, evaluate in Python, and write a report."""

    report = audit_assets(
        profile=AuditProfile.load(profile_path),
        collector=UnrealCppCollector(),
        asset_paths=asset_paths,
        batch_size=batch_size,
        should_cancel=should_cancel,
        on_progress=on_progress,
    )
    report.write(Path(output_path))
    if session_root:
        store = SessionStore(session_root)
        session = store.save_report(output_path)
        store.write_latest_comparison(session)
    return report.to_dict()


def run_from_request_file(request_path: str) -> dict:
    """Run a panel-authored request without embedding paths or asset arrays in Python source."""

    request = json.loads(Path(request_path).read_text(encoding="utf-8"))
    return run(
        profile_path=str(request["profile_path"]),
        asset_paths=[str(path) for path in request["asset_paths"]],
        output_path=str(request["output_path"]),
        batch_size=int(request.get("batch_size", 64)),
        session_root=(str(request["session_root"]) if request.get("session_root") else None),
    )


def compare_from_request_file(request_path: str) -> dict:
    """Compare two immutable reports selected by the native panel and write JSON output."""

    request = json.loads(Path(request_path).read_text(encoding="utf-8"))
    result = compare_reports(
        str(request["baseline_report_path"]), str(request["current_report_path"])
    ).to_dict()
    result["status"] = "ready"
    destination = Path(str(request["output_path"]))
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_suffix(destination.suffix + ".tmp")
    temp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(destination)
    return result


def export_handoff_from_request_file(request_path: str) -> dict:
    """Export a standalone Chinese team package without rescanning Unreal assets."""

    request = json.loads(Path(request_path).read_text(encoding="utf-8"))
    args = [str(request["report_path"]), str(request["output_root"])]
    if request.get("review_ledger_root"):
        args.append(str(request["review_ledger_root"]))
    result = export_handoff(*args)
    return {
        "root": str(result.root),
        "html_path": str(result.html_path),
        "csv_path": str(result.csv_path),
        "manifest_path": str(result.manifest_path),
    }


def refresh_review_view_from_request_file(request_path: str) -> dict:
    """Reconcile review metadata with the exact current Report and write a panel view."""

    request = json.loads(Path(request_path).read_text(encoding="utf-8"))
    return write_review_view(
        str(request["report_path"]),
        str(request["review_ledger_root"]),
        str(request["review_view_path"]),
    )


def update_review_from_request_file(request_path: str) -> dict:
    """Persist one explicit human review decision and refresh the panel view."""

    request = json.loads(Path(request_path).read_text(encoding="utf-8"))
    update_review(
        str(request["report_path"]),
        str(request["review_ledger_root"]),
        issue_id=str(request["issue_id"]),
        evidence_id=str(request["evidence_id"]),
        decision=str(request["decision"]),
        owner=str(request.get("owner", "")),
        note=str(request.get("note", "")),
    )
    return write_review_view(
        str(request["report_path"]),
        str(request["review_ledger_root"]),
        str(request["review_view_path"]),
    )


def write_delivery_group_view_from_request_file(request_path: str) -> dict:
    """Build the panel's directory hotspot view from the current Report only."""

    request = json.loads(Path(request_path).read_text(encoding="utf-8"))
    return write_delivery_group_view(
        str(request["report_path"]),
        str(request["output_path"]),
        (
            str(request["review_ledger_root"])
            if request.get("review_ledger_root")
            else None
        ),
    )
