from __future__ import annotations

import json
import math
import re
from datetime import UTC, datetime
from pathlib import Path

import unreal
from unreal_asset_batch_auditor import UnrealCppCollector

DEMO_ROOT = "/Game/UABADemo"
ASSET_COUNT = 24


def _project_root() -> Path:
    return Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))


def _object_path(asset_data) -> str:  # type: ignore[no-untyped-def]
    getter = getattr(asset_data, "get_soft_object_path", None)
    if callable(getter):
        return str(getter())
    return f"{asset_data.package_name}.{asset_data.asset_name}"


def _engine_static_mesh_paths() -> list[str]:
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    static_mesh_class = unreal.TopLevelAssetPath("/Script/Engine", "StaticMesh")
    asset_filter = unreal.ARFilter(
        package_paths=["/Engine"],
        class_paths=[static_mesh_class],
        recursive_paths=True,
        recursive_classes=True,
    )
    return sorted(_object_path(item) for item in registry.get_assets(asset_filter))


def _select_diverse_assets(metadata):  # type: ignore[no-untyped-def]
    ranked = sorted(
        metadata,
        key=lambda item: (
            item.lods[0].triangles,
            item.lods[0].vertices,
            item.material_slot_count,
            item.asset_path,
        ),
    )
    if len(ranked) < ASSET_COUNT:
        raise RuntimeError(f"Need {ASSET_COUNT} source meshes, found {len(ranked)}")

    quantile_indices = {
        round(index * (len(ranked) - 1) / (ASSET_COUNT - 1)) for index in range(ASSET_COUNT)
    }
    selected = [ranked[index] for index in sorted(quantile_indices)]
    material_rich = sorted(
        ranked,
        key=lambda item: (
            item.material_slot_count,
            item.lods[0].triangles,
            item.asset_path,
        ),
        reverse=True,
    )[:4]
    selected_by_path = {item.asset_path: item for item in selected}
    for item in material_rich:
        selected_by_path[item.asset_path] = item
    selected = sorted(
        selected_by_path.values(),
        key=lambda item: (item.lods[0].triangles, item.asset_path),
    )
    if len(selected) > ASSET_COUNT:
        removable = [item for item in selected if item not in material_rich]
        for item in removable:
            if len(selected) == ASSET_COUNT:
                break
            selected.remove(item)
    return selected


def _safe_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", name)
    return cleaned[:40] or "Mesh"


def _metadata_dict(item) -> dict:  # type: ignore[no-untyped-def]
    return {
        "lod_count": len(item.lods),
        "lod0_triangles": item.lods[0].triangles,
        "lod0_vertices": item.lods[0].vertices,
        "material_slot_count": item.material_slot_count,
        "nanite_enabled": item.nanite_enabled,
        "simple_collision_primitive_count": item.simple_collision_primitive_count,
        "collision_complexity": item.collision_complexity,
        "uv_channel_count": item.uv_channel_count,
        "lightmap_coordinate_index": item.lightmap_coordinate_index,
        "lightmap_resolution": item.lightmap_resolution,
        "lightmap_uv_valid": item.has_valid_lightmap_uv,
    }


def _demo_location(index: int, source_name: str, default_group: str) -> tuple[str, str, list[str]]:
    safe_source_name = _safe_name(source_name)
    group = default_group
    asset_name = f"SM_UABA_{index:02d}_{safe_source_name}"
    policy_faults: list[str] = []
    if index == 22:
        asset_name = f"BAD_UABA_{index:02d}_{safe_source_name}"
        policy_faults.append("invalid_object_name")
    if index == 23:
        group = "Developers"
        policy_faults.append("forbidden_package_segment")
    return group, asset_name, policy_faults


def main() -> None:
    collector = UnrealCppCollector()
    static_mesh_editor = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    source_paths = _engine_static_mesh_paths()
    source_batch = collector.collect(source_paths)
    selected = _select_diverse_assets(source_batch.assets)
    group_size = math.ceil(len(selected) / 3)
    created_paths: list[str] = []
    entries = []

    for index, source in enumerate(selected, start=1):
        group_index = min((index - 1) // group_size, 2)
        default_group = ("01_Light", "02_Medium", "03_Heavy")[group_index]
        group, asset_name, policy_faults = _demo_location(
            index, source.asset_name, default_group
        )
        destination = f"{DEMO_ROOT}/{group}/{asset_name}"
        legacy_name = f"SM_UABA_{index:02d}_{_safe_name(source.asset_name)}"
        legacy_destination = f"{DEMO_ROOT}/{default_group}/{legacy_name}"
        if (
            legacy_destination != destination
            and unreal.EditorAssetLibrary.does_asset_exist(legacy_destination)
            and not unreal.EditorAssetLibrary.delete_asset(legacy_destination)
        ):
            raise RuntimeError(f"Could not remove legacy generated asset: {legacy_destination}")
        if not unreal.EditorAssetLibrary.does_asset_exist(destination):
            duplicated = unreal.EditorAssetLibrary.duplicate_asset(source.asset_path, destination)
            if duplicated is None:
                raise RuntimeError(f"Could not duplicate {source.asset_path} to {destination}")
        intentional_variation = index == ASSET_COUNT
        if intentional_variation:
            demo_asset = unreal.EditorAssetLibrary.load_asset(destination)
            if not isinstance(demo_asset, unreal.StaticMesh):
                raise RuntimeError(f"Could not load synthetic fault mesh: {destination}")
            static_mesh_editor.remove_collisions(demo_asset)
            demo_asset.set_editor_property("light_map_resolution", 8)
        if not unreal.EditorAssetLibrary.save_asset(destination, only_if_is_dirty=False):
            raise RuntimeError(f"Could not save demo asset: {destination}")
        object_path = f"{destination}.{asset_name}"
        created_paths.append(object_path)
        entries.append(
            {
                "index": index,
                "group": group,
                "source_asset_path": source.asset_path,
                "demo_asset_path": object_path,
                "source_metadata": _metadata_dict(source),
                "intentional_variation": intentional_variation,
                "policy_faults": policy_faults,
                "variation_note": (
                    "Synthetic delivery fault: no simple collision and Lightmap resolution 8."
                    if intentional_variation
                    else ""
                ),
            }
        )

    demo_batch = collector.collect(created_paths)
    demo_by_path = {item.asset_path: item for item in demo_batch.assets}
    for entry in entries:
        demo = demo_by_path.get(entry["demo_asset_path"])
        if demo is None:
            raise RuntimeError(f"Generated asset was not collected: {entry['demo_asset_path']}")
        entry["demo_metadata"] = _metadata_dict(demo)
        entry["matches_source_metadata"] = entry["source_metadata"] == entry["demo_metadata"]

    manifest = {
        "schema_version": "unreal-asset-auditor-demo-manifest@1.0.0",
        "created_at": datetime.now(UTC).isoformat(),
        "engine_version": collector.host_engine_version,
        "project_kind": "recording_demo_non_production",
        "asset_root": DEMO_ROOT,
        "asset_count": len(entries),
        "source_inventory_count": len(source_batch.assets),
        "generation_strategy": (
            "24 deterministic triangle-count quantiles plus material-slot-rich coverage from "
            "/Engine Static Meshes"
        ),
        "assets": entries,
        "valid_asset_paths": created_paths,
        "diagnostic_paths": [
            "/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial",
            f"{DEMO_ROOT}/Missing/SM_DoesNotExist.SM_DoesNotExist",
        ],
        "notes": [
            "Demo assets are project-owned duplicates; Engine source assets are never modified.",
            "Folder names describe relative source complexity, not audit pass/fail status.",
            "All demo thresholds are training values and are not studio standards.",
            "Asset 22 intentionally violates the object-name policy.",
            "Asset 23 intentionally lives under the forbidden Developers segment.",
            "Asset 24 is an explicitly labeled project-owned collision and resolution fault.",
        ],
    }
    manifest_path = _project_root() / "demo-asset-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    unreal.log(
        f"UABA_DEMO_GENERATION_OK assets={len(entries)} "
        f"sources={len(source_batch.assets)} manifest={manifest_path}"
    )


main()
