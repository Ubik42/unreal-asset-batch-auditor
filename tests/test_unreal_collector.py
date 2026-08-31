from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from unreal_asset_batch_auditor import AuditProfile, UnrealCppCollector, audit_assets

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "config" / "Profiles" / "default-static-mesh-profile.v1.json"


class FakeLibrary:
    @staticmethod
    def collect_static_mesh_metadata(asset_paths: list[str]) -> list[SimpleNamespace]:
        assert asset_paths == ["/Game/Valid.Valid", "/Game/Missing.Missing"]
        return [
            SimpleNamespace(
                collected=True,
                asset_path="/Game/Valid.Valid",
                asset_name="Valid",
                lod_metadata=[SimpleNamespace(index=0, triangle_count=100, vertex_count=80)],
                material_slot_count=1,
                nanite_enabled=True,
                error_code="",
                error="",
            ),
            SimpleNamespace(
                collected=False,
                asset_path="/Game/Missing.Missing",
                error_code="NOT_STATIC_MESH",
                error="Object could not be loaded as UStaticMesh.",
            ),
        ]


def test_unreal_adapter_preserves_per_asset_failure_without_dropping_success() -> None:
    unreal = SimpleNamespace(UnrealAssetBatchAuditorLibrary=FakeLibrary)
    collector = UnrealCppCollector(unreal)
    report = audit_assets(
        profile=AuditProfile.load(PROFILE),
        collector=collector,
        asset_paths=["/Game/Valid.Valid", "/Game/Missing.Missing"],
    )
    assert report.asset_count == 1
    assert report.collection_failure_count == 1
    assert report.collection_failures[0].asset_path == "/Game/Missing.Missing"
    assert report.collection_failures[0].code == "NOT_STATIC_MESH"
    assert report.collection_mode == "unreal_editor"
    assert report.real_unreal_validation is False
    assert report.host_engine_version is None


def test_unreal_adapter_reports_missing_cpp_result_row() -> None:
    class EmptyLibrary:
        @staticmethod
        def collect_static_mesh_metadata(asset_paths: list[str]) -> list:
            return []

    unreal = SimpleNamespace(UnrealAssetBatchAuditorLibrary=EmptyLibrary)
    batch = UnrealCppCollector(unreal).collect(["/Game/MissingRow.MissingRow"])
    assert batch.assets == []
    assert batch.failures[0].code == "MISSING_COLLECTOR_ROW"


def test_real_unreal_marker_requires_engine_version_from_host_api() -> None:
    class FakeSystemLibrary:
        @staticmethod
        def get_engine_version() -> str:
            return "5.8.1-56057345+++UE5+Release-5.8"

    unreal = SimpleNamespace(
        UnrealAssetBatchAuditorLibrary=FakeLibrary,
        SystemLibrary=FakeSystemLibrary,
    )
    report = audit_assets(
        profile=AuditProfile.load(PROFILE),
        collector=UnrealCppCollector(unreal),
        asset_paths=["/Game/Valid.Valid", "/Game/Missing.Missing"],
    )
    assert report.real_unreal_validation is True
    assert report.host_engine_version.startswith("5.8.1")


def test_unreal_adapter_preserves_material_and_texture_dependency_facts() -> None:
    class DependencyLibrary:
        @staticmethod
        def collect_static_mesh_metadata(asset_paths: list[str]) -> list[SimpleNamespace]:
            return [
                SimpleNamespace(
                    collected=True,
                    asset_path=asset_paths[0],
                    asset_name="MaterialAsset",
                    lod_metadata=[SimpleNamespace(index=0, triangle_count=12, vertex_count=16)],
                    material_slot_count=2,
                    material_paths=["/Game/M/MI_A.MI_A", "/Game/M/MI_B.MI_B"],
                    missing_material_slot_count=0,
                    unique_material_count=2,
                    texture_paths=["/Game/T/T_A.T_A", "/Game/T/T_N.T_N"],
                    texture_dependency_count=2,
                    max_texture_dimension=2048,
                    nanite_enabled=False,
                    simple_collision_primitive_count=1,
                    collision_complexity="project_default",
                    uv_channel_count=2,
                    lightmap_coordinate_index=1,
                    lightmap_resolution=64,
                    error_code="",
                    error="",
                )
            ]

    batch = UnrealCppCollector(
        SimpleNamespace(UnrealAssetBatchAuditorLibrary=DependencyLibrary)
    ).collect(["/Game/MaterialAsset.MaterialAsset"])
    asset = batch.assets[0]
    assert asset.has_dependency_metadata is True
    assert asset.material_paths == ("/Game/M/MI_A.MI_A", "/Game/M/MI_B.MI_B")
    assert asset.texture_dependency_count == 2
    assert asset.max_texture_dimension == 2048
