"""UnrealEditor-Cmd entry point. Inputs are environment variables set by the wrapper."""

from __future__ import annotations

import os

import unreal
from unreal_asset_batch_auditor import UnrealCppCollector, run_project_preset


def _discover_static_meshes(folder_path: str) -> list[str]:
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    discovered: list[str] = []
    for asset_data in registry.get_assets_by_path(folder_path, recursive=True):
        class_path = getattr(asset_data, "asset_class_path", None)
        class_name = str(getattr(class_path, "asset_name", ""))
        if class_name != "StaticMesh":
            continue
        get_soft_path = getattr(asset_data, "get_soft_object_path", None)
        if callable(get_soft_path):
            soft_path = get_soft_path()
            to_string = getattr(soft_path, "to_string", None)
            discovered.append(str(to_string() if callable(to_string) else soft_path))
        else:
            discovered.append(f"{asset_data.package_name}.{asset_data.asset_name}")
    return sorted(set(discovered))


def main() -> dict:
    preset_path = os.environ.get("UABA_UNATTENDED_PRESET", "")
    summary_path = os.environ.get("UABA_UNATTENDED_SUMMARY", "")
    project_root = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    result = run_project_preset(
        preset_path,
        project_root=project_root,
        collector=UnrealCppCollector(unreal),
        discover_folder=_discover_static_meshes,
        summary_override=summary_path or None,
    )
    unreal.log(
        "UABA_UNATTENDED_RESULT "
        f"status={result['status']} exit_code={result['exit_code']} "
        f"assets={result['asset_count']} issues={result['issue_count']}"
    )
    return result


if __name__ == "__main__":
    main()
