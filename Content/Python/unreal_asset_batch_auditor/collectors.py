from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from .contracts import CONTRACT_VERSION, CollectionFailure, ContractError, StaticMeshMetadata


@dataclass
class CollectionBatch:
    assets: list[StaticMeshMetadata] = field(default_factory=list)
    failures: list[CollectionFailure] = field(default_factory=list)


@runtime_checkable
class MetadataCollector(Protocol):
    """Read-only boundary used by orchestration; implementations must not mutate assets."""

    mode: str
    real_unreal_validation: bool
    host_engine_version: str | None

    def collect(self, asset_paths: Sequence[str] | None = None) -> CollectionBatch: ...


class FixtureCollector:
    """Offline test adapter. Its output is never evidence of a real Unreal run."""

    mode = "offline_fixture"
    real_unreal_validation = False
    host_engine_version = None

    def __init__(self, fixture_path: str | Path) -> None:
        self.fixture_path = Path(fixture_path)

    def collect(self, asset_paths: Sequence[str] | None = None) -> CollectionBatch:
        raw = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        if raw.get("schema_version") != "unreal-static-mesh-fixture@1.0.0":
            raise ContractError("unsupported fixture schema_version")
        requested = set(asset_paths or [])
        assets = [StaticMeshMetadata.from_dict(item) for item in raw.get("assets", [])]
        if requested:
            assets = [asset for asset in assets if asset.asset_path in requested]
        return CollectionBatch(assets=assets)


class UnrealCppCollector:
    """Adapter for the Editor-only C++ batch collection API exposed through Unreal Python."""

    mode = "unreal_editor"
    real_unreal_validation = False
    host_engine_version: str | None = None

    def __init__(self, unreal_module: object | None = None) -> None:
        if unreal_module is None:
            try:
                import unreal as unreal_module  # type: ignore[import-not-found]
            except ImportError as exc:
                raise RuntimeError("UnrealCppCollector must run inside Unreal Editor") from exc
        self._unreal = unreal_module
        system_library = getattr(unreal_module, "SystemLibrary", None)
        get_version = getattr(system_library, "get_engine_version", None)
        if callable(get_version):
            version = str(get_version()).strip()
            if version:
                self.host_engine_version = version
                self.real_unreal_validation = True

    def collect(self, asset_paths: Sequence[str] | None = None) -> CollectionBatch:
        if not asset_paths:
            raise ContractError("Unreal C++ collection requires explicit asset paths")
        library = getattr(self._unreal, "UnrealAssetBatchAuditorLibrary", None)
        if library is None:
            raise RuntimeError("UnrealAssetBatchAuditor C++ Python API is unavailable")
        rows = library.collect_static_mesh_metadata(list(asset_paths))
        result = CollectionBatch()
        returned_paths: set[str] = set()
        for row in rows:
            returned_paths.add(str(row.asset_path))
            collected = bool(getattr(row, "collected", getattr(row, "b_collected", False)))
            if not collected:
                result.failures.append(
                    CollectionFailure(
                        schema_version=CONTRACT_VERSION,
                        asset_path=str(row.asset_path),
                        code=str(getattr(row, "error_code", "COLLECTION_FAILED")),
                        message=str(getattr(row, "error", "Unknown collection failure")),
                        collector=self.mode,
                    )
                )
                continue
            metadata = {
                        "asset_path": str(row.asset_path),
                        "asset_name": str(row.asset_name),
                        "lods": [
                            {
                                "index": int(lod.index),
                                "triangles": int(lod.triangle_count),
                                "vertices": int(lod.vertex_count),
                            }
                            for lod in getattr(
                                row,
                                "lod_metadata",
                                getattr(row, "lods", getattr(row, "lo_ds", ())),
                            )
                        ],
                        "material_slot_count": int(row.material_slot_count),
                        "nanite_enabled": bool(row.nanite_enabled),
                        "simple_collision_primitive_count": getattr(
                            row, "simple_collision_primitive_count", None
                        ),
                        "collision_complexity": getattr(
                            row, "collision_complexity", None
                        ),
                        "uv_channel_count": getattr(row, "uv_channel_count", None),
                        "lightmap_coordinate_index": getattr(
                            row, "lightmap_coordinate_index", None
                        ),
                        "lightmap_resolution": getattr(row, "lightmap_resolution", None),
                    }
            dependency_fields = (
                "material_paths",
                "missing_material_slot_count",
                "unique_material_count",
                "texture_paths",
                "texture_dependency_count",
                "max_texture_dimension",
            )
            if all(hasattr(row, name) for name in dependency_fields):
                metadata.update(
                    {
                        "material_paths": sorted(str(item) for item in row.material_paths),
                        "missing_material_slot_count": int(row.missing_material_slot_count),
                        "unique_material_count": int(row.unique_material_count),
                        "texture_paths": sorted(str(item) for item in row.texture_paths),
                        "texture_dependency_count": int(row.texture_dependency_count),
                        "max_texture_dimension": int(row.max_texture_dimension),
                    }
                )
            result.assets.append(StaticMeshMetadata.from_dict(metadata))
        for missing_path in sorted(set(asset_paths) - returned_paths):
            result.failures.append(
                CollectionFailure(
                    schema_version=CONTRACT_VERSION,
                    asset_path=missing_path,
                    code="MISSING_COLLECTOR_ROW",
                    message="C++ collector returned no result row for the requested asset.",
                    collector=self.mode,
                )
            )
        return result
