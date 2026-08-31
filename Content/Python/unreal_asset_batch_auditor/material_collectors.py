from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, runtime_checkable

from .collectors import CollectionBatch
from .contracts import CONTRACT_VERSION, CollectionFailure, ContractError
from .material_contracts import MATERIAL_FIXTURE_VERSION, MaterialInterfaceMetadata


@runtime_checkable
class MaterialMetadataCollector(Protocol):
    mode: str
    real_unreal_validation: bool
    host_engine_version: str | None

    def collect(self, asset_paths: Sequence[str] | None = None) -> CollectionBatch: ...


class MaterialFixtureCollector:
    """Offline material adapter; its output is never real Unreal evidence."""

    mode = "offline_fixture"
    real_unreal_validation = False
    host_engine_version = None

    def __init__(self, fixture_path: str | Path) -> None:
        self.fixture_path = Path(fixture_path)

    def collect(self, asset_paths: Sequence[str] | None = None) -> CollectionBatch:
        raw = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        if raw.get("schema_version") != MATERIAL_FIXTURE_VERSION:
            raise ContractError("unsupported material fixture schema_version")
        requested = set(asset_paths or [])
        assets = [MaterialInterfaceMetadata.from_dict(item) for item in raw.get("assets", [])]
        if requested:
            assets = [asset for asset in assets if asset.asset_path in requested]
        return CollectionBatch(assets=assets)  # type: ignore[arg-type]


class MaterialUnrealCppCollector:
    """Adapter for the read-only Editor C++ Material Interface batch API."""

    mode = "unreal_editor"
    real_unreal_validation = False
    host_engine_version: str | None = None

    def __init__(self, unreal_module: object | None = None) -> None:
        if unreal_module is None:
            try:
                import unreal as unreal_module  # type: ignore[import-not-found]
            except ImportError as exc:
                raise RuntimeError(
                    "MaterialUnrealCppCollector must run inside Unreal Editor"
                ) from exc
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
            raise ContractError("Unreal C++ material collection requires explicit asset paths")
        library = getattr(self._unreal, "UnrealAssetBatchAuditorLibrary", None)
        if library is None:
            raise RuntimeError("UnrealAssetBatchAuditor C++ Python API is unavailable")
        rows = library.collect_material_interface_metadata(list(asset_paths))
        result = CollectionBatch()
        returned_paths: set[str] = set()
        for row in rows:
            asset_path = str(row.asset_path)
            returned_paths.add(asset_path)
            collected = bool(getattr(row, "collected", getattr(row, "b_collected", False)))
            if not collected:
                result.failures.append(
                    CollectionFailure(
                        schema_version=CONTRACT_VERSION,
                        asset_path=asset_path,
                        code=str(getattr(row, "error_code", "COLLECTION_FAILED")),
                        message=str(getattr(row, "error", "Unknown collection failure")),
                        collector=self.mode,
                    )
                )
                continue
            result.assets.append(  # type: ignore[arg-type]
                MaterialInterfaceMetadata.from_dict(
                    {
                        "asset_path": asset_path,
                        "asset_name": str(row.asset_name),
                        "material_kind": str(row.material_kind),
                        "material_domain": str(row.material_domain),
                        "blend_mode": str(row.blend_mode),
                        "two_sided": bool(row.two_sided),
                        "shading_models": [str(value) for value in row.shading_models],
                        "parent_path": str(row.parent_path) or None,
                        "base_material_path": str(row.base_material_path) or None,
                        "parent_depth": int(row.parent_depth),
                        "texture_paths": [str(value) for value in row.texture_paths],
                        "texture_dependency_count": int(row.texture_dependency_count),
                        "max_texture_dimension": int(row.max_texture_dimension),
                    }
                )
            )
        for missing_path in sorted(set(asset_paths) - returned_paths):
            result.failures.append(
                CollectionFailure(
                    schema_version=CONTRACT_VERSION,
                    asset_path=missing_path,
                    code="MISSING_COLLECTOR_ROW",
                    message="C++ material collector returned no row for the requested asset.",
                    collector=self.mode,
                )
            )
        return result
