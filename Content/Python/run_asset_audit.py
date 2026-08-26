"""Explicit Unreal Editor orchestration entry point; importing this file performs no scan."""

import json
from collections.abc import Callable
from pathlib import Path

from unreal_asset_batch_auditor import AuditProfile, BatchProgress, UnrealCppCollector, audit_assets


def run(
    profile_path: str,
    asset_paths: list[str],
    output_path: str,
    *,
    batch_size: int = 128,
    should_cancel: Callable[[], bool] | None = None,
    on_progress: Callable[[BatchProgress], None] | None = None,
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
    return report.to_dict()


def run_from_request_file(request_path: str) -> dict:
    """Run a panel-authored request without embedding paths or asset arrays in Python source."""

    request = json.loads(Path(request_path).read_text(encoding="utf-8"))
    return run(
        profile_path=str(request["profile_path"]),
        asset_paths=[str(path) for path in request["asset_paths"]],
        output_path=str(request["output_path"]),
        batch_size=int(request.get("batch_size", 64)),
    )
