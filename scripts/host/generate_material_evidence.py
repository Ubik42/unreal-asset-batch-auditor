from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import unreal
from unreal_asset_batch_auditor import (
    MaterialAuditProfile,
    MaterialUnrealCppCollector,
    audit_materials,
)

ASSET_ROOT = "/Game/UABAMaterialDemo"
SOURCES = (
    (
        "/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial",
        "01_Approved/M_UABA_BasicSurface",
        "基础 Surface 材质",
    ),
    (
        "/Engine/BasicShapes/BasicShapeMaterial_Inst.BasicShapeMaterial_Inst",
        "01_Approved/MI_UABA_BasicSurface",
        "单层材质实例",
    ),
    (
        "/Engine/EngineDebugMaterials/M_SimpleOpaque.M_SimpleOpaque",
        "01_Approved/M_UABA_SimpleOpaque",
        "Opaque 对照材质",
    ),
    (
        "/Engine/EngineDebugMaterials/M_SimpleTranslucent.M_SimpleTranslucent",
        "02_RenderState/M_UABA_Translucent",
        "Translucent 混合模式样本",
    ),
    (
        "/Engine/EngineDebugMaterials/M_SimpleUnlitTranslucent.M_SimpleUnlitTranslucent",
        "02_RenderState/M_UABA_UnlitTranslucent",
        "Unlit + Translucent 样本",
    ),
    (
        "/Engine/EngineVolumetrics/Fogsheet/Materials/M_EV_FogSheet_2sided_Master_Addi.M_EV_FogSheet_2sided_Master_Addi",
        "02_RenderState/M_UABA_TwoSidedAdditive",
        "Two Sided + Additive 样本",
    ),
    (
        "/Engine/EngineDebugMaterials/M_VolumeRenderSphereTracePP.M_VolumeRenderSphereTracePP",
        "02_RenderState/M_UABA_PostProcess",
        "Post Process Domain 样本",
    ),
    (
        "/Engine/EditorShapes/Materials/M_ShapeMaster.M_ShapeMaster",
        "03_ParentChain/M_UABA_ShapeMaster",
        "带纹理依赖的父材质",
    ),
    (
        "/Engine/EditorShapes/Materials/MI_ShapeInstance.MI_ShapeInstance",
        "03_ParentChain/MI_UABA_ShapeInstance",
        "材质实例父级样本",
    ),
)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    asset_paths: list[str] = []
    manifest_assets: list[dict[str, str]] = []
    for source_path, relative_destination, scenario in SOURCES:
        source = unreal.EditorAssetLibrary.load_asset(source_path)
        if not isinstance(source, unreal.MaterialInterface):
            raise TypeError(f"Engine material sample is unavailable: {source_path}")
        destination = f"{ASSET_ROOT}/{relative_destination}"
        duplicated = unreal.EditorAssetLibrary.duplicate_asset(source_path, destination)
        if not isinstance(duplicated, unreal.MaterialInterface):
            raise TypeError(f"Duplicated sample is not a MaterialInterface: {source_path}")
        if not unreal.EditorAssetLibrary.save_loaded_asset(duplicated, only_if_is_dirty=False):
            raise RuntimeError(f"Could not save duplicated material: {destination}")
        object_path = duplicated.get_path_name()
        asset_paths.append(object_path)
        manifest_assets.append(
            {
                "source_asset_path": source_path,
                "demo_asset_path": object_path,
                "scenario": scenario,
            }
        )

    profile = MaterialAuditProfile.load(
        repo_root / "Resources/Profiles/material-desktop-balanced.v1.json"
    )
    report_path = Path(
        os.environ.get(
            "UABA_MATERIAL_REPORT",
            repo_root / "artifacts/demo/demo-material-desktop-balanced-v1-report.json",
        )
    )
    report = audit_materials(
        profile=profile,
        collector=MaterialUnrealCppCollector(),
        asset_paths=asset_paths,
        batch_size=3,
    )
    report.write(report_path)
    manifest = {
        "schema_version": "unreal-material-demo-manifest@1.0.0",
        "created_at": datetime.now(UTC).isoformat(),
        "engine_version": report.host_engine_version,
        "generation": (
            "public UE installation samples duplicated into an isolated demo project; "
            "Engine source assets remain unchanged"
        ),
        "asset_count": len(asset_paths),
        "assets": manifest_assets,
        "report_path": str(report_path),
        "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
        "claims_runtime_performance": False,
        "redistributes_engine_uasset": False,
    }
    manifest_path = report_path.with_name("demo-material-asset-manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    unreal.log(
        f"UABA_MATERIAL_EVIDENCE_OK assets={report.asset_count} "
        f"issues={report.issue_count} report={report_path}"
    )


main()
