from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence

from .audit import _stable_id
from .batching import BatchProgress, collect_in_batches
from .collectors import CollectionBatch
from .contracts import CONTRACT_VERSION, Evidence, Issue, Severity
from .material_collectors import MaterialMetadataCollector
from .material_contracts import (
    MaterialAuditProfile,
    MaterialAuditReport,
    MaterialInterfaceMetadata,
)


def _record(
    *,
    asset: MaterialInterfaceMetadata,
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
    return (
        Issue(
            schema_version=CONTRACT_VERSION,
            issue_id=issue_id,
            asset_path=asset.asset_path,
            rule_id=rule_id,
            severity=severity,
            message=message,
            evidence_id=evidence_id,
        ),
        Evidence(
            schema_version=CONTRACT_VERSION,
            evidence_id=evidence_id,
            asset_path=asset.asset_path,
            metric=metric,
            observed=observed,
            expected=expected,
            profile_pointer=pointer,
            collector=collector,
        ),
    )


def _evaluate_material(
    asset: MaterialInterfaceMetadata, profile: MaterialAuditProfile, collector: str
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

    rule = profile.allowed_domains
    if rule.enabled:
        check(
            asset.material_domain not in rule.allowed_values,
            rule_id="material.allowed_domain",
            severity=rule.severity,
            metric="material_domain",
            observed=asset.material_domain,
            expected=" | ".join(rule.allowed_values),
            pointer="/rules/allowed_domains/allowed_values",
            message=(
                f"Material domain {asset.material_domain!r} is outside profile allowlist "
                f"{list(rule.allowed_values)}."
            ),
        )
    rule = profile.allowed_blend_modes
    if rule.enabled:
        check(
            asset.blend_mode not in rule.allowed_values,
            rule_id="material.allowed_blend_mode",
            severity=rule.severity,
            metric="blend_mode",
            observed=asset.blend_mode,
            expected=" | ".join(rule.allowed_values),
            pointer="/rules/allowed_blend_modes/allowed_values",
            message=(
                f"Blend mode {asset.blend_mode!r} is outside profile allowlist "
                f"{list(rule.allowed_values)}."
            ),
        )
    rule = profile.two_sided
    if rule.enabled and rule.expected != "any":
        expected = rule.expected == "enabled"
        check(
            asset.two_sided is not expected,
            rule_id="material.two_sided",
            severity=rule.severity,
            metric="two_sided",
            observed=asset.two_sided,
            expected=expected,
            pointer="/rules/two_sided/expected",
            message=(
                f"Two Sided is {asset.two_sided}; profile expects {rule.expected}."
            ),
        )
    rule = profile.instance_parent
    if rule.enabled and asset.material_kind == "material_instance":
        check(
            asset.has_parent is not rule.required,
            rule_id="material.instance_parent",
            severity=rule.severity,
            metric="has_parent",
            observed=asset.has_parent,
            expected=rule.required,
            pointer="/rules/instance_parent/required",
            message=(
                f"Material instance parent state is {asset.has_parent}; "
                f"profile expects {rule.required}."
            ),
        )
    rule = profile.parent_depth
    if rule.enabled and asset.material_kind == "material_instance":
        check(
            asset.parent_depth > rule.max_count,
            rule_id="material.parent_depth",
            severity=rule.severity,
            metric="parent_depth",
            observed=asset.parent_depth,
            expected=rule.max_count,
            pointer="/rules/parent_depth/max_count",
            message=(
                f"Material instance parent depth is {asset.parent_depth}; "
                f"profile maximum is {rule.max_count}."
            ),
        )
    rule = profile.texture_dependencies
    if rule.enabled:
        check(
            asset.texture_dependency_count > rule.max_count,
            rule_id="material.texture_dependencies",
            severity=rule.severity,
            metric="texture_dependency_count",
            observed=asset.texture_dependency_count,
            expected=rule.max_count,
            pointer="/rules/texture_dependencies/max_count",
            message=(
                f"Material references {asset.texture_dependency_count} textures; "
                f"profile maximum is {rule.max_count}."
            ),
        )
    rule = profile.texture_dimension
    if rule.enabled:
        check(
            asset.max_texture_dimension > rule.max_size,
            rule_id="material.texture_dimension",
            severity=rule.severity,
            metric="max_texture_dimension",
            observed=asset.max_texture_dimension,
            expected=rule.max_size,
            pointer="/rules/texture_dimension/max_size",
            message=(
                f"Largest referenced texture dimension is {asset.max_texture_dimension}; "
                f"profile maximum is {rule.max_size}."
            ),
        )
    return issues, evidence


def build_material_report_from_collection(
    *,
    profile: MaterialAuditProfile,
    collector: MaterialMetadataCollector,
    batch: CollectionBatch,
    requested_asset_paths: Sequence[str],
    requested_asset_count: int,
    processed_asset_count: int,
    cancelled_asset_count: int,
    completed_batch_count: int,
    batch_size: int | None,
    report_id_factory: Callable[[], str] | None = None,
) -> MaterialAuditReport:
    assets = list(batch.assets)
    issues: list[Issue] = []
    evidence: list[Evidence] = []
    for asset in sorted(assets, key=lambda item: item.asset_path):
        asset_issues, asset_evidence = _evaluate_material(asset, profile, collector.mode)
        issues.extend(asset_issues)
        evidence.extend(asset_evidence)
    profile_fingerprint = hashlib.sha256(
        f"{profile.profile_id}:{profile.profile_version}".encode()
    ).hexdigest()[:8]
    report_id = (
        report_id_factory()
        if report_id_factory
        else _stable_id(
            "material-report",
            profile_fingerprint,
            batch_size,
            requested_asset_count,
            processed_asset_count,
            cancelled_asset_count,
            *requested_asset_paths,
            *(asset.asset_path for asset in assets),
            *(failure.asset_path for failure in batch.failures),
        )
    )
    return MaterialAuditReport.create(
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
        batch_size=batch_size,
        issues=issues,
        evidence=evidence,
        collection_failures=batch.failures,
    )


def audit_materials(
    *,
    profile: MaterialAuditProfile,
    collector: MaterialMetadataCollector,
    asset_paths: Sequence[str] | None = None,
    batch_size: int = 128,
    should_cancel: Callable[[], bool] | None = None,
    on_progress: Callable[[BatchProgress], None] | None = None,
    report_id_factory: Callable[[], str] | None = None,
) -> MaterialAuditReport:
    if asset_paths is None:
        if should_cancel or on_progress:
            raise ValueError("progress and cancellation require explicit asset_paths")
        batch = collector.collect(None)
        requested_count = len(batch.assets) + len(batch.failures)
        processed_count = requested_count
        cancelled_count = 0
        completed_batches = 1 if requested_count else 0
        applied_batch_size = None
    else:
        batched = collect_in_batches(
            collector=collector,  # type: ignore[arg-type]
            asset_paths=asset_paths,
            batch_size=batch_size,
            should_cancel=should_cancel,
            on_progress=on_progress,
        )
        batch = batched.batch
        if batched.progress is None:
            raise RuntimeError("batched collection did not return progress")
        requested_count = batched.progress.requested_count
        processed_count = batched.progress.processed_count
        cancelled_count = batched.progress.cancelled_count
        completed_batches = batched.progress.completed_batch_count
        applied_batch_size = batch_size
    return build_material_report_from_collection(
        profile=profile,
        collector=collector,
        batch=batch,
        requested_asset_paths=list(asset_paths or []),
        requested_asset_count=requested_count,
        processed_asset_count=processed_count,
        cancelled_asset_count=cancelled_count,
        completed_batch_count=completed_batches,
        batch_size=applied_batch_size,
        report_id_factory=report_id_factory,
    )
