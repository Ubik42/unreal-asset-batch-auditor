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
