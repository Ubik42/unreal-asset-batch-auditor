"""Profile-driven Static Mesh audit orchestration."""

from .audit import audit_assets
from .batching import BatchedCollectionResult, BatchProgress, collect_in_batches
from .benchmark import BENCHMARK_VERSION, run_benchmark
from .collectors import CollectionBatch, FixtureCollector, MetadataCollector, UnrealCppCollector
from .contracts import AuditProfile, CollectionFailure, Evidence, Issue, Report, StaticMeshMetadata
from .sessions import (
    COMPARISON_VERSION,
    SESSION_INDEX_VERSION,
    SessionComparison,
    SessionError,
    SessionStore,
    compare_reports,
)

__all__ = [
    "BENCHMARK_VERSION",
    "COMPARISON_VERSION",
    "SESSION_INDEX_VERSION",
    "AuditProfile",
    "BatchProgress",
    "BatchedCollectionResult",
    "CollectionBatch",
    "CollectionFailure",
    "Evidence",
    "FixtureCollector",
    "Issue",
    "MetadataCollector",
    "Report",
    "SessionComparison",
    "SessionError",
    "SessionStore",
    "StaticMeshMetadata",
    "UnrealCppCollector",
    "audit_assets",
    "collect_in_batches",
    "compare_reports",
    "run_benchmark",
]
