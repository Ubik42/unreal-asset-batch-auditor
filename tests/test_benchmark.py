from __future__ import annotations

from unreal_asset_batch_auditor import run_benchmark
from unreal_asset_batch_auditor.collectors import CollectionBatch


class FakeBatchCollector:
    def __init__(self) -> None:
        self.calls = 0

    def collect(self, asset_paths):
        self.calls += 1
        return CollectionBatch()


def test_benchmark_separates_warmup_and_reports_nearest_rank_p95() -> None:
    collector = FakeBatchCollector()
    ticks = iter([0.0, 0.010, 1.0, 1.020, 2.0, 2.030])
    result = run_benchmark(
        collector=collector,  # type: ignore[arg-type]
        asset_paths=["/Engine/A.A", "/Engine/B.B"],
        warmup_runs=2,
        repetitions=3,
        clock=lambda: next(ticks),
    )
    assert collector.calls == 5
    assert result["summary"]["median_ms"] == 20.0
    assert result["summary"]["p95_ms"] == 30.0
    assert result["summary"]["median_assets_per_second"] == 100.0
    assert result["summary"]["stable_result_counts"] is True
