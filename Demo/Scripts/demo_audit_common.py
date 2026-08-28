from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import unreal
from unreal_asset_batch_auditor import AuditProfile, UnrealCppCollector, audit_assets


def _project_root() -> Path:
    return Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))


def _asset_file(project_root: Path, object_path: str) -> Path:
    package_path = object_path.split(".", 1)[0]
    relative = package_path.removeprefix("/Game/") + ".uasset"
    return project_root / "Content" / Path(relative)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_demo(
    profile_filename: str,
    *,
    manifest_filename: str = "demo-asset-manifest.json",
    output_stem: str | None = None,
) -> dict:
    project_root = _project_root()
    repo_root = project_root.parent
    manifest_path = project_root / manifest_filename
    profile_path = project_root / "Profiles" / profile_filename
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    valid_paths = list(manifest["valid_asset_paths"])
    requested_paths = valid_paths + list(manifest["diagnostic_paths"])
    files = {path: _asset_file(project_root, path) for path in valid_paths}
    before = {path: _sha256(asset_file) for path, asset_file in files.items()}
    progress_events = []

    def record_progress(progress) -> None:  # type: ignore[no-untyped-def]
        progress_events.append(progress)
        unreal.log(
            "UABA_DEMO_PROGRESS "
            f"processed={progress.processed_count}/{progress.requested_count} "
            f"collected={progress.collected_count} failed={progress.failed_count}"
        )

    report = audit_assets(
        profile=AuditProfile.load(profile_path),
        collector=UnrealCppCollector(),
        asset_paths=requested_paths,
        batch_size=8,
        on_progress=record_progress,
    )
    after = {path: _sha256(asset_file) for path, asset_file in files.items()}
    changed = sorted(path for path in valid_paths if before[path] != after[path])
    saved_root = project_root / "Saved" / "UABAAudit"
    artifact_root = repo_root / "artifacts" / "demo"
    report_name = f"{output_stem or report.profile_id}-report.json"
    report.write(saved_root / report_name)
    report.write(artifact_root / report_name)

    rule_counts = Counter(issue.rule_id for issue in report.issues)
    severity_counts = Counter(issue.severity for issue in report.issues)
    session = {
        "schema_version": "unreal-asset-auditor-demo-session@1.0.0",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_id": report.profile_id,
        "engine_version": report.host_engine_version,
        "requested_count": report.requested_asset_count,
        "asset_count": report.asset_count,
        "issue_count": report.issue_count,
        "collection_failure_count": report.collection_failure_count,
        "rule_counts": dict(sorted(rule_counts.items())),
        "severity_counts": dict(sorted(severity_counts.items())),
        "progress_events": [asdict(item) for item in progress_events],
        "integrity": {
            "algorithm": "sha256",
            "hashed_asset_count": len(before),
            "unchanged": not changed,
            "changed": changed,
        },
        "report_paths": [
            str(saved_root / report_name),
            str(artifact_root / report_name),
        ],
    }
    session_name = f"{output_stem or report.profile_id}-session.json"
    saved_root.mkdir(parents=True, exist_ok=True)
    artifact_root.mkdir(parents=True, exist_ok=True)
    (saved_root / session_name).write_text(json.dumps(session, indent=2) + "\n", encoding="utf-8")
    (artifact_root / session_name).write_text(
        json.dumps(session, indent=2) + "\n", encoding="utf-8"
    )

    unreal.log(
        "UABA_DEMO_COMPLETE "
        f"profile={report.profile_id} assets={report.asset_count} issues={report.issue_count} "
        f"failures={report.collection_failure_count} unchanged={not changed}"
    )
    for rule_id, count in sorted(rule_counts.items()):
        unreal.log_warning(f"UABA_DEMO_RULE {rule_id}={count}")
    return session
