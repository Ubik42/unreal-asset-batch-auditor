from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from .collectors import CollectionBatch, MetadataCollector


@dataclass(frozen=True)
class BatchProgress:
    requested_count: int
    processed_count: int
    collected_count: int
    failed_count: int
    cancelled_count: int
    completed_batch_count: int
    total_batch_count: int


@dataclass
class BatchedCollectionResult:
    batch: CollectionBatch = field(default_factory=CollectionBatch)
    progress: BatchProgress | None = None


def collect_in_batches(
    *,
    collector: MetadataCollector,
    asset_paths: Sequence[str],
    batch_size: int,
    should_cancel: Callable[[], bool] | None = None,
    on_progress: Callable[[BatchProgress], None] | None = None,
) -> BatchedCollectionResult:
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1:
        raise ValueError("batch_size must be a positive integer")

    paths = list(asset_paths)
    requested_count = len(paths)
    total_batch_count = math.ceil(requested_count / batch_size) if paths else 0
    aggregate = CollectionBatch()
    processed_count = 0
    completed_batch_count = 0

    def make_progress(*, cancelled_count: int = 0) -> BatchProgress:
        return BatchProgress(
            requested_count=requested_count,
            processed_count=processed_count,
            collected_count=len(aggregate.assets),
            failed_count=len(aggregate.failures),
            cancelled_count=cancelled_count,
            completed_batch_count=completed_batch_count,
            total_batch_count=total_batch_count,
        )

    if not paths:
        progress = make_progress()
        if on_progress:
            on_progress(progress)
        return BatchedCollectionResult(batch=aggregate, progress=progress)

    for offset in range(0, requested_count, batch_size):
        if should_cancel and should_cancel():
            aggregate.assets.sort(key=lambda item: item.asset_path)
            aggregate.failures.sort(key=lambda item: (item.asset_path, item.code, item.message))
            progress = make_progress(cancelled_count=requested_count - processed_count)
            if on_progress:
                on_progress(progress)
            return BatchedCollectionResult(batch=aggregate, progress=progress)

        current_paths = paths[offset : offset + batch_size]
        current = collector.collect(current_paths)
        aggregate.assets.extend(current.assets)
        aggregate.failures.extend(current.failures)
        processed_count += len(current_paths)
        completed_batch_count += 1
        progress = make_progress()
        if on_progress:
            on_progress(progress)

    aggregate.assets.sort(key=lambda item: item.asset_path)
    aggregate.failures.sort(key=lambda item: (item.asset_path, item.code, item.message))
    return BatchedCollectionResult(batch=aggregate, progress=make_progress())
