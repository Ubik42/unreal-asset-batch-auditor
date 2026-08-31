from __future__ import annotations

import binascii
import hashlib
import json
import os
import struct
import zlib
from datetime import UTC, datetime
from pathlib import Path

import unreal
from unreal_asset_batch_auditor import (
    TextureAuditProfile,
    TextureUnrealCppCollector,
    audit_textures,
)

ASSET_ROOT = "/Game/UABADemo/Textures"
SPECS = (
    ("T_UABA_Good_BaseColor", 1024, 1024, (70, 150, 210, 255), "good"),
    ("T_UABA_Oversize_BaseColor", 4096, 4096, (210, 120, 65, 255), "oversize"),
    ("T_UABA_NPOT_Mask", 1500, 900, (120, 210, 110, 255), "npot_mask"),
)


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", binascii.crc32(kind + payload) & 0xFFFFFFFF)
    )


def _write_solid_png(path: Path, width: int, height: int, color: tuple[int, ...]) -> None:
    compressor = zlib.compressobj(level=9)
    row = b"\x00" + bytes(color) * width
    compressed = bytearray()
    for _ in range(height):
        compressed.extend(compressor.compress(row))
    compressed.extend(compressor.flush())
    payload = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + _chunk(b"IDAT", bytes(compressed))
        + _chunk(b"IEND", b"")
    )
    path.write_bytes(payload)


def _import_texture(source: Path, name: str):  # type: ignore[no-untyped-def]
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", str(source))
    task.set_editor_property("destination_path", ASSET_ROOT)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", True)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    asset = unreal.EditorAssetLibrary.load_asset(f"{ASSET_ROOT}/{name}")
    if not isinstance(asset, unreal.Texture2D):
        raise TypeError(f"Could not import generated Texture2D: {name}")
    return asset


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    source_root = Path(
        unreal.Paths.convert_relative_path_to_full(
            unreal.Paths.project_saved_dir() + "UABATextureSources"
        )
    )
    source_root.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    manifest_assets = []
    for name, width, height, color, scenario in SPECS:
        source = source_root / f"{name}.png"
        _write_solid_png(source, width, height, color)
        texture = _import_texture(source, name)
        texture.set_editor_property(
            "compression_settings", unreal.TextureCompressionSettings.TC_DEFAULT
        )
        texture.set_editor_property("srgb", True)
        texture.set_editor_property(
            "mip_gen_settings", unreal.TextureMipGenSettings.TMGS_FROM_TEXTURE_GROUP
        )
        texture.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_WORLD)
        texture.set_editor_property("never_stream", False)
        texture.set_editor_property("virtual_texture_streaming", False)
        if scenario == "oversize":
            texture.set_editor_property("virtual_texture_streaming", True)
        if scenario == "npot_mask":
            texture.set_editor_property("srgb", False)
            texture.set_editor_property(
                "mip_gen_settings", unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS
            )
            texture.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_PIXELS2D)
            texture.set_editor_property("never_stream", True)
            texture.set_editor_property("virtual_texture_streaming", False)
        if not unreal.EditorAssetLibrary.save_loaded_asset(texture, only_if_is_dirty=False):
            raise RuntimeError(f"Could not save generated Texture2D: {name}")
        object_path = f"{ASSET_ROOT}/{name}.{name}"
        paths.append(object_path)
        manifest_assets.append(
            {
                "asset_path": object_path,
                "source_size": [width, height],
                "scenario": scenario,
                "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            }
        )

    profile = TextureAuditProfile.load(
        repo_root / "Resources/Profiles/texture-mobile-strict.v1.json"
    )
    report_path = Path(
        os.environ.get(
            "UABA_TEXTURE_REPORT",
            repo_root / "artifacts/demo/demo-texture-mobile-strict-v1-report.json",
        )
    )
    report = audit_textures(
        profile=profile,
        collector=TextureUnrealCppCollector(),
        asset_paths=paths,
        batch_size=2,
    )
    report.write(report_path)
    manifest = {
        "schema_version": "unreal-texture-demo-manifest@1.0.0",
        "created_at": datetime.now(UTC).isoformat(),
        "engine_version": report.host_engine_version,
        "generation": "deterministic solid-color RGBA PNG imported into the isolated demo project",
        "asset_count": len(paths),
        "assets": manifest_assets,
        "report_path": str(report_path),
        "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
        "claims_runtime_performance": False,
    }
    manifest_path = report_path.with_name("demo-texture-asset-manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    unreal.log(
        f"UABA_TEXTURE_EVIDENCE_OK assets={report.asset_count} "
        f"issues={report.issue_count} report={report_path}"
    )


main()
