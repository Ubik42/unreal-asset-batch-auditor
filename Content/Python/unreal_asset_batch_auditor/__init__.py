"""Profile-driven Static Mesh audit orchestration."""

from .audit import audit_assets, build_report_from_collection
from .batching import BatchedCollectionResult, BatchProgress, collect_in_batches
from .benchmark import BENCHMARK_VERSION, run_benchmark
from .collectors import CollectionBatch, FixtureCollector, MetadataCollector, UnrealCppCollector
from .contracts import AuditProfile, CollectionFailure, Evidence, Issue, Report, StaticMeshMetadata
from .handoff import HANDOFF_VERSION, HandoffError, HandoffResult, export_handoff
from .panel_task import (
    TASK_STATE_VERSION,
    PanelAuditTask,
    request_panel_cancel,
    start_panel_task,
)
from .sessions import (
    COMPARISON_VERSION,
    SESSION_INDEX_VERSION,
    SessionComparison,
    SessionError,
    SessionStore,
    compare_reports,
)
from .unattended import (
    EXIT_COLLECTION_FAILED,
    EXIT_CONFIG_ERROR,
    EXIT_PASSED,
    EXIT_POLICY_FAILED,
    EXIT_RUNTIME_ERROR,
    PRESET_VERSION,
    SUMMARY_VERSION,
    PresetError,
    ProjectPreset,
    resolve_asset_paths,
    run_project_preset,
)

__all__ = [
    "BENCHMARK_VERSION",
    "COMPARISON_VERSION",
    "EXIT_COLLECTION_FAILED",
    "EXIT_CONFIG_ERROR",
    "EXIT_PASSED",
    "EXIT_POLICY_FAILED",
    "EXIT_RUNTIME_ERROR",
    "HANDOFF_VERSION",
    "PRESET_VERSION",
    "SESSION_INDEX_VERSION",
    "SUMMARY_VERSION",
    "TASK_STATE_VERSION",
    "AuditProfile",
    "BatchProgress",
    "BatchedCollectionResult",
    "CollectionBatch",
    "CollectionFailure",
    "Evidence",
    "FixtureCollector",
    "HandoffError",
    "HandoffResult",
    "Issue",
    "MetadataCollector",
    "PanelAuditTask",
    "PresetError",
    "ProjectPreset",
    "Report",
    "SessionComparison",
    "SessionError",
    "SessionStore",
    "StaticMeshMetadata",
    "UnrealCppCollector",
    "audit_assets",
    "build_report_from_collection",
    "collect_in_batches",
    "compare_reports",
    "export_handoff",
    "request_panel_cancel",
    "resolve_asset_paths",
    "run_benchmark",
    "run_project_preset",
    "start_panel_task",
]
