from __future__ import annotations

from pathlib import Path

from unreal_asset_batch_auditor import AuditProfile, BatchProgress, audit_assets, collect_in_batches
from unreal_asset_batch_auditor.collectors import CollectionBatch
from unreal_asset_batch_auditor.contracts import (
    CONTRACT_VERSION,
    CollectionFailure,
    LODMetadata,
    StaticMeshMetadata,
)

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "config" / "Profiles" / "default-static-mesh-profile.v1.json"


def _asset(path: str) -> StaticMeshMetadata:
    return StaticMeshMetadata(
        asset_path=path,
        asset_name=path.rsplit("/", 1)[-1],
        lods=(LODMetadata(index=0, triangles=1, vertices=3),),
        material_slot_count=1,
        nanite_enabled=False,
    )


class RecordingCollector:
    mode = "unreal_editor"
    real_unreal_validation = True
    host_engine_version = "test-engine"

    def __init__(self, failing: set[str] | None = None) -> None:
        self.failing = failing or set()
        self.calls: list[list[str]] = []

    def collect(self, asset_paths):  # type: ignore[no-untyped-def]
        paths = list(asset_paths)
        self.calls.append(paths)
        assets = [_asset(path) for path in reversed(paths) if path not in self.failing]
        failures = [
            CollectionFailure(
                schema_version=CONTRACT_VERSION,
                asset_path=path,
                code="TEST_FAILURE",
                message="expected test failure",
                collector=self.mode,
            )
            for path in reversed(paths)
            if path in self.failing
        ]
        return CollectionBatch(assets=assets, failures=failures)


def test_collector_calls_are_bounded_and_results_are_deterministic() -> None:
    collector = RecordingCollector(failing={"/Game/B.B", "/Game/D.D"})
    progress: list[BatchProgress] = []
    result = collect_in_batches(
        collector=collector,
        asset_paths=["/Game/E.E", "/Game/D.D", "/Game/C.C", "/Game/B.B", "/Game/A.A"],
        batch_size=2,
        on_progress=progress.append,
    )
    assert [len(call) for call in collector.calls] == [2, 2, 1]
    assert [item.asset_path for item in result.batch.assets] == [
        "/Game/A.A",
        "/Game/C.C",
        "/Game/E.E",
    ]
    assert [item.asset_path for item in result.batch.failures] == ["/Game/B.B", "/Game/D.D"]
    assert [(item.processed_count, item.cancelled_count) for item in progress] == [
        (2, 0),
        (4, 0),
        (5, 0),
    ]
    assert progress[-1].collected_count == 3
    assert progress[-1].failed_count == 2


def test_cancellation_is_observed_between_batches_and_keeps_completed_results() -> None:
    collector = RecordingCollector(failing={"/Game/B.B"})
    progress: list[BatchProgress] = []
    result = collect_in_batches(
        collector=collector,
        asset_paths=["/Game/A.A", "/Game/B.B", "/Game/C.C", "/Game/D.D"],
        batch_size=2,
        should_cancel=lambda: bool(progress),
        on_progress=progress.append,
    )
    assert collector.calls == [["/Game/A.A", "/Game/B.B"]]
    assert [item.asset_path for item in result.batch.assets] == ["/Game/A.A"]
    assert [item.asset_path for item in result.batch.failures] == ["/Game/B.B"]
    assert result.progress == BatchProgress(
        requested_count=4,
        processed_count=2,
        collected_count=1,
        failed_count=1,
        cancelled_count=2,
        completed_batch_count=1,
        total_batch_count=2,
    )


def test_empty_input_emits_terminal_progress_without_collector_call() -> None:
    collector = RecordingCollector()
    progress: list[BatchProgress] = []
    result = collect_in_batches(
        collector=collector, asset_paths=[], batch_size=8, on_progress=progress.append
    )
    assert collector.calls == []
    assert result.progress == progress[0]
    assert progress[0].requested_count == 0


def test_batch_size_must_be_positive_integer() -> None:
    collector = RecordingCollector()
    for invalid in (0, -1, True):
        try:
            collect_in_batches(collector=collector, asset_paths=["/Game/A.A"], batch_size=invalid)
        except ValueError as error:
            assert "positive integer" in str(error)
        else:
            raise AssertionError("invalid batch size was accepted")


def test_audit_report_persists_bounded_cancellation_summary() -> None:
    collector = RecordingCollector(failing={"/Game/B.B"})
    progress: list[BatchProgress] = []
    report = audit_assets(
        profile=AuditProfile.load(PROFILE),
        collector=collector,
        asset_paths=["/Game/A.A", "/Game/B.B", "/Game/C.C", "/Game/D.D"],
        batch_size=2,
        should_cancel=lambda: bool(progress),
        on_progress=progress.append,
    )
    assert report.requested_asset_count == 4
    assert report.processed_asset_count == 2
    assert report.cancelled_asset_count == 2
    assert report.completed_batch_count == 1
    assert report.batch_size == 2
    assert [item.asset_path for item in report.collection_failures] == ["/Game/B.B"]


def test_cancelled_report_id_includes_unprocessed_request_scope() -> None:
    profile = AuditProfile.load(PROFILE)
    first_progress: list[BatchProgress] = []
    first = audit_assets(
        profile=profile,
        collector=RecordingCollector(),
        asset_paths=["/Game/A.A", "/Game/B.B", "/Game/C.C"],
        batch_size=1,
        should_cancel=lambda: bool(first_progress),
        on_progress=first_progress.append,
    )
    second_progress: list[BatchProgress] = []
    second = audit_assets(
        profile=profile,
        collector=RecordingCollector(),
        asset_paths=["/Game/A.A", "/Game/B.B", "/Game/D.D"],
        batch_size=1,
        should_cancel=lambda: bool(second_progress),
        on_progress=second_progress.append,
    )
    assert first.assets == second.assets
    assert first.report_id != second.report_id
