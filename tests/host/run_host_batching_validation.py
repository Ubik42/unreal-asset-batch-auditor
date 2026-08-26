from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import unreal
from unreal_asset_batch_auditor import AuditProfile, UnrealCppCollector, audit_assets

PROFILE_PATH = Path(os.environ["UABA_PROFILE_PATH"])
OUTPUT_PATH = Path(os.environ["UABA_BATCHING_VALIDATION_PATH"])
ENGINE_BASIC_SHAPES = Path(os.environ["UABA_BASIC_SHAPES_ROOT"])
ASSET_PATHS = [
    "/Engine/BasicShapes/Cube.Cube",
    "/Engine/BasicShapes/DoesNotExist.DoesNotExist",
    "/Engine/BasicShapes/Sphere.Sphere",
    "/Engine/BasicShapes/Cone.Cone",
    "/Engine/BasicShapes/Plane.Plane",
]
ASSET_FILES = ["Cube.uasset", "Sphere.uasset", "Cone.uasset", "Plane.uasset"]


class RecordingRealCollector:
    def __init__(self) -> None:
        self.delegate = UnrealCppCollector()
        self.mode = self.delegate.mode
        self.real_unreal_validation = self.delegate.real_unreal_validation
        self.host_engine_version = self.delegate.host_engine_version
        self.call_sizes: list[int] = []

    def collect(self, asset_paths):  # type: ignore[no-untyped-def]
        paths = list(asset_paths)
        self.call_sizes.append(len(paths))
        return self.delegate.collect(paths)


def _hash_assets() -> dict[str, str]:
    result = {}
    for name in ASSET_FILES:
        digest = hashlib.sha256((ENGINE_BASIC_SHAPES / name).read_bytes()).hexdigest()
        result[name] = digest
    return result


def _summary(report, collector, progress):  # type: ignore[no-untyped-def]
    return {
        "collector_call_sizes": collector.call_sizes,
        "report": report.to_dict(),
        "progress_events": [asdict(item) for item in progress],
    }


def main() -> None:
    profile = AuditProfile.load(PROFILE_PATH)
    before = _hash_assets()

    completed_collector = RecordingRealCollector()
    completed_progress = []
    completed_report = audit_assets(
        profile=profile,
        collector=completed_collector,
        asset_paths=ASSET_PATHS,
        batch_size=2,
        on_progress=completed_progress.append,
    )
    if completed_collector.call_sizes != [2, 2, 1]:
        raise RuntimeError(f"Unexpected completed call sizes: {completed_collector.call_sizes}")
    if (
        completed_report.processed_asset_count != 5
        or completed_report.asset_count != 4
        or completed_report.collection_failure_count != 1
        or completed_report.cancelled_asset_count != 0
    ):
        raise RuntimeError("Completed bounded run returned unexpected counts")

    cancelled_collector = RecordingRealCollector()
    cancelled_progress = []
    cancelled_report = audit_assets(
        profile=profile,
        collector=cancelled_collector,
        asset_paths=ASSET_PATHS,
        batch_size=2,
        should_cancel=lambda: bool(cancelled_progress),
        on_progress=cancelled_progress.append,
    )
    if cancelled_collector.call_sizes != [2]:
        raise RuntimeError(f"Cancellation crossed a batch boundary: {cancelled_collector.call_sizes}")
    if (
        cancelled_report.processed_asset_count != 2
        or cancelled_report.asset_count != 1
        or cancelled_report.collection_failure_count != 1
        or cancelled_report.cancelled_asset_count != 3
    ):
        raise RuntimeError("Cancelled bounded run returned unexpected counts")

    after = _hash_assets()
    changed = sorted(name for name in before if before[name] != after[name])
    payload = {
        "schema_version": "unreal-batching-host-validation@1.0.0",
        "created_at": datetime.now(UTC).isoformat(),
        "engine_version": completed_report.host_engine_version,
        "collection_mode": completed_report.collection_mode,
        "real_unreal_validation": completed_report.real_unreal_validation,
        "batch_size": 2,
        "completed_scenario": _summary(
            completed_report, completed_collector, completed_progress
        ),
        "cancelled_scenario": _summary(
            cancelled_report, cancelled_collector, cancelled_progress
        ),
        "integrity": {
            "algorithm": "sha256",
            "hashed_asset_count": len(before),
            "unchanged": not changed,
            "changed": changed,
        },
        "claims_asset_mutation": False,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    unreal.log(
        "UABA_HOST_BATCHING_OK calls=2,2,1 cancelled_calls=2 "
        f"failures=1 cancelled=3 unchanged={not changed}"
    )


main()
