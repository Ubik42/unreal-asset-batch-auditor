from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import unreal
from unreal_asset_batch_auditor import AuditProfile, UnrealCppCollector, audit_assets

PROFILE_PATH = Path(os.environ["UABA_PROFILE_PATH"])
REPORT_PATH = Path(os.environ["UABA_REPORT_PATH"])
ENVIRONMENT_PATH = Path(os.environ["UABA_ENVIRONMENT_PATH"])
ASSET_PATHS = [
    "/Engine/BasicShapes/Cube.Cube",
    "/Engine/BasicShapes/Sphere.Sphere",
    "/Engine/BasicShapes/DoesNotExist.DoesNotExist",
]


def main() -> None:
    report = audit_assets(
        profile=AuditProfile.load(PROFILE_PATH),
        collector=UnrealCppCollector(),
        asset_paths=ASSET_PATHS,
    )
    if not report.real_unreal_validation or not report.host_engine_version:
        raise RuntimeError("Host report did not obtain a real Unreal Engine version")
    if report.asset_count != 2 or report.collection_failure_count != 1:
        raise RuntimeError(
            "Expected two collected Engine meshes and one diagnosable missing-path failure"
        )
    report.write(REPORT_PATH)
    environment = {
        "schema_version": "unreal-host-validation-environment@1.0.0",
        "created_at": datetime.now(UTC).isoformat(),
        "engine_version": report.host_engine_version,
        "execution": "UnrealEditor-Cmd ExecutePythonScript",
        "project_kind": "disposable_non_production_host",
        "asset_paths": ASSET_PATHS,
        "report_path": REPORT_PATH.name,
        "claims_visible_editor_review": False,
    }
    ENVIRONMENT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ENVIRONMENT_PATH.write_text(
        json.dumps(environment, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    unreal.log(
        f"UABA_HOST_VALIDATION_OK assets={report.asset_count} "
        f"failures={report.collection_failure_count} engine={report.host_engine_version}"
    )


main()
