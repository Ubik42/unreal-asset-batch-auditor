from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import unreal
from unreal_asset_batch_auditor import BENCHMARK_VERSION, UnrealCppCollector, run_benchmark

OUTPUT_PATH = Path(os.environ["UABA_BENCHMARK_PATH"])
ENGINE_CONTENT_ROOT = Path(os.environ["UABA_ENGINE_CONTENT_ROOT"])
DATASET_SIZE = int(os.environ.get("UABA_BENCHMARK_DATASET_SIZE", "64"))
WARMUP_RUNS = int(os.environ.get("UABA_BENCHMARK_WARMUP_RUNS", "2"))
REPETITIONS = int(os.environ.get("UABA_BENCHMARK_REPETITIONS", "7"))


def _object_path(asset_data) -> str:
    getter = getattr(asset_data, "get_soft_object_path", None)
    if callable(getter):
        return str(getter())
    return f"{asset_data.package_name}.{asset_data.asset_name}"


def _asset_file(object_path: str) -> Path:
    package_path = object_path.split(".", 1)[0]
    relative = package_path.removeprefix("/Engine/") + ".uasset"
    return ENGINE_CONTENT_ROOT / Path(relative)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _select_dataset() -> tuple[list[str], dict[str, Path]]:
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    static_mesh_class = unreal.TopLevelAssetPath("/Script/Engine", "StaticMesh")
    asset_filter = unreal.ARFilter(
        package_paths=["/Engine"],
        class_paths=[static_mesh_class],
        recursive_paths=True,
        recursive_classes=True,
    )
    candidates = sorted(_object_path(item) for item in registry.get_assets(asset_filter))
    selected: list[str] = []
    files: dict[str, Path] = {}
    for path in candidates:
        asset_file = _asset_file(path)
        if asset_file.is_file():
            selected.append(path)
            files[path] = asset_file
        if len(selected) == DATASET_SIZE:
            break
    if len(selected) != DATASET_SIZE:
        raise RuntimeError(f"Expected {DATASET_SIZE} hashable Engine Static Meshes, got {len(selected)}")
    return selected, files


def main() -> None:
    asset_paths, files = _select_dataset()
    before = {path: _sha256(files[path]) for path in asset_paths}
    collector = UnrealCppCollector()
    result = run_benchmark(
        collector=collector,
        asset_paths=asset_paths,
        warmup_runs=WARMUP_RUNS,
        repetitions=REPETITIONS,
    )
    after = {path: _sha256(files[path]) for path in asset_paths}
    changed = sorted(path for path in asset_paths if before[path] != after[path])
    payload = {
        "schema_version": BENCHMARK_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "engine_version": collector.host_engine_version,
        "collection_mode": collector.mode,
        "dataset": {
            "source": "/Engine Asset Registry",
            "selection": (
                f"first {DATASET_SIZE} sorted StaticMesh object paths with on-disk "
                "Engine Content uassets"
            ),
            "requested_count": len(asset_paths),
            "asset_paths": asset_paths,
        },
        "configuration": {
            "batch_size": len(asset_paths),
            "warmup_runs": WARMUP_RUNS,
            "repetitions": REPETITIONS,
            "timer": "python.time.perf_counter around one C++ batch call",
        },
        **result,
        "integrity": {
            "algorithm": "sha256",
            "hashed_asset_count": len(asset_paths),
            "unchanged": not changed,
            "changed": changed,
        },
        "limitations": [
            "This is a disposable UE 5.8.1 Engine-content baseline, not a production project.",
            "Warm runs include Unreal object caching and must not be extrapolated to cold project scans.",
            "The result does not prove that thousands of project assets will avoid Editor stalls.",
        ],
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    unreal.log(
        "UABA_HOST_BENCHMARK_OK "
        f"assets={len(asset_paths)} median_ms={payload['summary']['median_ms']} "
        f"p95_ms={payload['summary']['p95_ms']} unchanged={not changed}"
    )


main()
