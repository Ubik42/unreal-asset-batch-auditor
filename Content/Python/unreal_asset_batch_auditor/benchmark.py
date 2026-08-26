from __future__ import annotations

import math
import statistics
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass

from .collectors import MetadataCollector

BENCHMARK_VERSION = "unreal-readonly-collector-benchmark@1.0.0"


@dataclass(frozen=True)
class BenchmarkRun:
    run_index: int
    elapsed_ms: float
    collected_count: int
    failure_count: int


def run_benchmark(
    *,
    collector: MetadataCollector,
    asset_paths: Sequence[str],
    warmup_runs: int,
    repetitions: int,
    clock: Callable[[], float] = time.perf_counter,
) -> dict:
    if not asset_paths:
        raise ValueError("benchmark requires at least one asset path")
    if warmup_runs < 0:
        raise ValueError("warmup_runs must be >= 0")
    if repetitions < 1:
        raise ValueError("repetitions must be >= 1")

    for _ in range(warmup_runs):
        collector.collect(asset_paths)

    runs: list[BenchmarkRun] = []
    for run_index in range(repetitions):
        started = clock()
        batch = collector.collect(asset_paths)
        elapsed_ms = (clock() - started) * 1000.0
        runs.append(
            BenchmarkRun(
                run_index=run_index,
                elapsed_ms=round(elapsed_ms, 6),
                collected_count=len(batch.assets),
                failure_count=len(batch.failures),
            )
        )

    elapsed = sorted(run.elapsed_ms for run in runs)
    median_ms = statistics.median(elapsed)
    p95_index = max(0, math.ceil(0.95 * len(elapsed)) - 1)
    p95_ms = elapsed[p95_index]
    throughput = len(asset_paths) / (median_ms / 1000.0) if median_ms > 0 else None
    return {
        "runs": [asdict(run) for run in runs],
        "summary": {
            "median_ms": round(median_ms, 6),
            "p95_ms": round(p95_ms, 6),
            "median_assets_per_second": round(throughput, 3) if throughput else None,
            "stable_result_counts": len(
                {(run.collected_count, run.failure_count) for run in runs}
            )
            == 1,
        },
    }
