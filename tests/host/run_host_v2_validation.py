from __future__ import annotations

import hashlib
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
    "/Engine/BasicShapes/Cone.Cone",
    "/Engine/BasicShapes/Cube.Cube",
    "/Engine/BasicShapes/Cylinder.Cylinder",
    "/Engine/BasicShapes/Sphere.Sphere",
]


def _asset_file(object_path: str) -> Path:
    package_path = object_path.split(".", 1)[0].removeprefix("/Engine/")
    return Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.engine_content_dir())) / (
        package_path + ".uasset"
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    files = {path: _asset_file(path) for path in ASSET_PATHS}
    before = {path: _sha256(file) for path, file in files.items()}
    report = audit_assets(
        profile=AuditProfile.load(PROFILE_PATH),
        collector=UnrealCppCollector(),
        asset_paths=ASSET_PATHS,
        batch_size=2,
    )
    after = {path: _sha256(file) for path, file in files.items()}
    changed = sorted(path for path in ASSET_PATHS if before[path] != after[path])

    if report.schema_version != "unreal-asset-audit@2.0.0":
        raise RuntimeError(f"Expected Report v2, received {report.schema_version}")
    if report.asset_count != len(ASSET_PATHS) or report.collection_failure_count:
        raise RuntimeError("Expected four successful Static Mesh rows and no collection failures")
    if any(not asset.has_extended_metadata for asset in report.assets):
        raise RuntimeError("At least one real host asset is missing v2 metadata")
    if changed:
        raise RuntimeError(f"Read-only audit changed Engine assets: {changed}")

    report.write(REPORT_PATH)
    environment = {
        "schema_version": "unreal-host-v2-validation@1.0.0",
        "created_at": datetime.now(UTC).isoformat(),
        "engine_version": report.host_engine_version,
        "plugin_build": "UE_5.8.1-v0.5.0-dev3",
        "execution": "independent UnrealEditor-Cmd ExecutePythonScript",
        "profile_path": str(PROFILE_PATH),
        "report_path": str(REPORT_PATH),
        "asset_count": report.asset_count,
        "issue_count": report.issue_count,
        "metadata": [
            {
                "asset_path": asset.asset_path,
                "simple_collision_primitive_count": asset.simple_collision_primitive_count,
                "collision_complexity": asset.collision_complexity,
                "uv_channel_count": asset.uv_channel_count,
                "lightmap_coordinate_index": asset.lightmap_coordinate_index,
                "lightmap_resolution": asset.lightmap_resolution,
                "lightmap_uv_valid": asset.has_valid_lightmap_uv,
            }
            for asset in report.assets
        ],
        "integrity": {
            "algorithm": "sha256",
            "hashed_asset_count": len(before),
            "unchanged": not changed,
            "changed": changed,
        },
        "claims_visible_editor_review": False,
    }
    ENVIRONMENT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ENVIRONMENT_PATH.write_text(
        json.dumps(environment, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    unreal.log(
        "UABA_HOST_V2_VALIDATION_OK "
        f"assets={report.asset_count} issues={report.issue_count} unchanged={not changed}"
    )


main()
