from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence

from .batching import BatchProgress, collect_in_batches
from .collectors import MetadataCollector
from .contracts import (
    CONTRACT_VERSION,
    AuditProfile,
    Evidence,
    Issue,
    Report,
    Severity,
    StaticMeshMetadata,
)


def _stable_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\x1f".join(map(str, parts)).encode()).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _record(
    *,
    asset: StaticMeshMetadata,
    rule_id: str,
    severity: Severity,
    metric: str,
    observed: int | bool | str,
    expected: int | bool | str,
    pointer: str,
    collector: str,
    message: str,
) -> tuple[Issue, Evidence]:
    evidence_id = _stable_id("ev", asset.asset_path, rule_id, observed, expected, pointer)
    issue_id = _stable_id("issue", asset.asset_path, rule_id, evidence_id)
    evidence = Evidence(
        schema_version=CONTRACT_VERSION,
        evidence_id=evidence_id,
        asset_path=asset.asset_path,
        metric=metric,
        observed=observed,
        expected=expected,
        profile_pointer=pointer,
        collector=collector,
    )
    issue = Issue(
        schema_version=CONTRACT_VERSION,
        issue_id=issue_id,
        asset_path=asset.asset_path,
        rule_id=rule_id,
        severity=severity,
        message=message,
        evidence_id=evidence_id,
    )
    return issue, evidence


def _evaluate_asset(
    asset: StaticMeshMetadata, profile: AuditProfile, collector: str
) -> tuple[list[Issue], list[Evidence]]:
    issues: list[Issue] = []
    evidence: list[Evidence] = []

    def check(
        condition: bool,
        *,
        rule_id: str,
        severity: Severity,
        metric: str,
        observed: int | bool | str,
        expected: int | bool | str,
        pointer: str,
        message: str,
    ) -> None:
        if condition:
            issue, proof = _record(
                asset=asset,
                rule_id=rule_id,
                severity=severity,
                metric=metric,
                observed=observed,
                expected=expected,
                pointer=pointer,
                collector=collector,
                message=message,
            )
            issues.append(issue)
            evidence.append(proof)

    lod0 = asset.lods[0]
    rule = profile.triangle_budget
    if rule.enabled:
        check(
            lod0.triangles > rule.max_value,
            rule_id="static_mesh.triangle_budget.lod0",
            severity=rule.severity,
            metric="lod0.triangles",
            observed=lod0.triangles,
            expected=rule.max_value,
            pointer="/rules/triangle_budget/max_lod0",
            message=f"LOD0 triangles {lod0.triangles} exceed profile limit {rule.max_value}.",
        )
    rule = profile.vertex_budget
    if rule.enabled:
        check(
            lod0.vertices > rule.max_value,
            rule_id="static_mesh.vertex_budget.lod0",
            severity=rule.severity,
            metric="lod0.vertices",
            observed=lod0.vertices,
            expected=rule.max_value,
            pointer="/rules/vertex_budget/max_lod0",
            message=f"LOD0 vertices {lod0.vertices} exceed profile limit {rule.max_value}.",
        )
    rule = profile.material_slots
    if rule.enabled:
        check(
            asset.material_slot_count > rule.max_value,
            rule_id="static_mesh.material_slots",
            severity=rule.severity,
            metric="material_slot_count",
            observed=asset.material_slot_count,
            expected=rule.max_value,
            pointer="/rules/material_slots/max_count",
            message=(
                f"Material slots {asset.material_slot_count} exceed profile limit {rule.max_value}."
            ),
        )
    lod_rule = profile.lod_count
    if lod_rule.enabled:
        check(
            len(asset.lods) < lod_rule.min_value,
            rule_id="static_mesh.lod_count",
            severity=lod_rule.severity,
            metric="lod_count",
            observed=len(asset.lods),
            expected=lod_rule.min_value,
            pointer="/rules/lod_count/min_count",
            message=f"LOD count {len(asset.lods)} is below profile minimum {lod_rule.min_value}.",
        )
    nanite_rule = profile.nanite
    if nanite_rule.enabled and nanite_rule.expected != "any":
        expected = nanite_rule.expected == "enabled"
        check(
            asset.nanite_enabled is not expected,
            rule_id="static_mesh.nanite_state",
            severity=nanite_rule.severity,
            metric="nanite_enabled",
            observed=asset.nanite_enabled,
            expected=expected,
            pointer="/rules/nanite/expected",
            message=(
                f"Nanite is {'enabled' if asset.nanite_enabled else 'disabled'}; "
                f"profile expects {nanite_rule.expected}."
            ),
        )
    return issues, evidence


def audit_assets(
    *,
    profile: AuditProfile,
    collector: MetadataCollector,
    asset_paths: Sequence[str] | None = None,
    batch_size: int = 128,
    should_cancel: Callable[[], bool] | None = None,
    on_progress: Callable[[BatchProgress], None] | None = None,
    report_id_factory: Callable[[], str] | None = None,
) -> Report:
    if asset_paths is None:
        if should_cancel or on_progress:
            raise ValueError("progress and cancellation require explicit asset_paths")
        batch = collector.collect(None)
        requested_asset_count = len(batch.assets) + len(batch.failures)
        processed_asset_count = requested_asset_count
        cancelled_asset_count = 0
        completed_batch_count = 1 if requested_asset_count else 0
        applied_batch_size: int | None = None
    else:
        batched = collect_in_batches(
            collector=collector,
            asset_paths=asset_paths,
            batch_size=batch_size,
            should_cancel=should_cancel,
            on_progress=on_progress,
        )
        batch = batched.batch
        if batched.progress is None:
            raise RuntimeError("batched collection did not return progress")
        requested_asset_count = batched.progress.requested_count
        processed_asset_count = batched.progress.processed_count
        cancelled_asset_count = batched.progress.cancelled_count
        completed_batch_count = batched.progress.completed_batch_count
        applied_batch_size = batch_size
    assets = batch.assets
    issues: list[Issue] = []
    evidence: list[Evidence] = []
    for asset in sorted(assets, key=lambda item: item.asset_path):
        asset_issues, asset_evidence = _evaluate_asset(asset, profile, collector.mode)
        issues.extend(asset_issues)
        evidence.extend(asset_evidence)
    profile_fingerprint = hashlib.sha256(
        f"{profile.profile_id}:{profile.profile_version}".encode()
    ).hexdigest()[:8]
    report_id = (
        report_id_factory()
        if report_id_factory
        else _stable_id(
            "report",
            profile_fingerprint,
            applied_batch_size,
            requested_asset_count,
            processed_asset_count,
            cancelled_asset_count,
            *(asset_paths or ()),
            *(a.asset_path for a in assets),
            *(failure.asset_path for failure in batch.failures),
        )
    )
    return Report.create(
        report_id=report_id,
        profile=profile,
        collection_mode=collector.mode,  # type: ignore[arg-type]
        real_unreal_validation=collector.real_unreal_validation,
        host_engine_version=collector.host_engine_version,
        assets=sorted(assets, key=lambda item: item.asset_path),
        requested_asset_count=requested_asset_count,
        processed_asset_count=processed_asset_count,
        cancelled_asset_count=cancelled_asset_count,
        completed_batch_count=completed_batch_count,
        batch_size=applied_batch_size,
        issues=issues,
        evidence=evidence,
        collection_failures=batch.failures,
    )
