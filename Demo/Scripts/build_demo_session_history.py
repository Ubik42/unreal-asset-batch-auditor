from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root / "Content" / "Python"))
    from unreal_asset_batch_auditor import SessionStore, export_handoff

    artifact_root = repo_root / "artifacts" / "demo"
    session_root = repo_root / "Demo" / "Saved" / "UnrealAssetBatchAuditor" / "Sessions"
    if session_root.exists():
        shutil.rmtree(session_root)
    store = SessionStore(session_root)
    baseline = store.save_report(
        artifact_root / "demo-desktop-balanced-v3-baseline-report.json"
    )
    current = store.save_report(artifact_root / "demo-desktop-balanced-v3-report.json")
    comparison = store.write_latest_comparison(current)
    handoff_root = artifact_root / "handoff"
    if handoff_root.exists():
        shutil.rmtree(handoff_root)
    handoff = export_handoff(
        artifact_root / "demo-desktop-balanced-v3-report.json", handoff_root
    )

    committed = artifact_root / "session-history"
    committed.mkdir(parents=True, exist_ok=True)
    shutil.copy2(store.index_path, committed / store.index_path.name)
    shutil.copy2(
        session_root / "latest-comparison.v1.json",
        committed / "latest-comparison.v1.json",
    )
    summary = {
        "schema_version": "unreal-demo-session-history@1.0.0",
        "baseline_session_id": baseline.session_id,
        "current_session_id": current.session_id,
        "new_issue_count": len(comparison.get("new_issues", [])),
        "persistent_issue_count": len(comparison.get("persistent_issues", [])),
        "resolved_issue_count": len(comparison.get("resolved_issues", [])),
        "new_failure_count": len(comparison.get("new_failures", [])),
        "persistent_failure_count": len(comparison.get("persistent_failures", [])),
        "resolved_failure_count": len(comparison.get("resolved_failures", [])),
        "handoff_path": handoff.root.relative_to(repo_root).as_posix(),
        "evidence_boundary": (
            "Both source reports were collected in UE; this script only archives and compares them."
        ),
    }
    (committed / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
