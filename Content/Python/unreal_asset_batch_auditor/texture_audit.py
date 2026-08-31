from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence

from .audit import _stable_id
from .batching import BatchProgress, collect_in_batches
from .collectors import CollectionBatch
from .contracts import CONTRACT_VERSION, Evidence, Issue, Severity
from .texture_collectors import TextureMetadataCollector
from .texture_contracts import Texture2DMetadata, TextureAuditProfile, TextureAuditReport


def _record(
    *,
    asset: Texture2DMetadata,
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


def _evaluate_texture(
    asset: Texture2DMetadata, profile: TextureAuditProfile, collector: str
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

    rule = profile.source_dimension
    source_max = max(asset.source_size)
    if rule.enabled:
        check(
            source_max > rule.max_size,
            rule_id="texture2d.source_dimension",
            severity=rule.severity,
            metric="source_max_dimension",
            observed=f"{asset.source_width}x{asset.source_height}",
            expected=f"max {rule.max_size}",
            pointer="/rules/source_dimension/max_size",
            message=(
                f"Texture source size {asset.source_width}x{asset.source_height} exceeds "
                f"profile limit {rule.max_size}."
            ),
        )
    rule = profile.power_of_two
    if rule.enabled:
        check(
            asset.source_is_power_of_two is not rule.required,
            rule_id="texture2d.power_of_two",
            severity=rule.severity,
            metric="source_is_power_of_two",
            observed=asset.source_is_power_of_two,
            expected=rule.required,
            pointer="/rules/power_of_two/required",
            message=(
                f"Texture source size {asset.source_width}x{asset.source_height} power-of-two "
                f"state is {asset.source_is_power_of_two}; profile expects {rule.required}."
            ),
        )
    rule = profile.mip_count
    if rule.enabled:
        check(
            asset.mip_count < rule.min_count,
            rule_id="texture2d.mip_count",
            severity=rule.severity,
            metric="mip_count",
            observed=asset.mip_count,
            expected=rule.min_count,
            pointer="/rules/mip_count/min_count",
            message=(
                f"Texture has {asset.mip_count} mip levels; profile minimum is {rule.min_count}."
            ),
        )
    rule = profile.texture_group
    if rule.enabled:
        check(
            asset.texture_group not in rule.allowed_values,
            rule_id="texture2d.texture_group",
            severity=rule.severity,
            metric="texture_group",
            observed=asset.texture_group,
            expected=" | ".join(rule.allowed_values),
            pointer="/rules/texture_group/allowed_values",
            message=(
                f"Texture group {asset.texture_group!r} is outside profile allowlist "
                f"{list(rule.allowed_values)}."
            ),
        )
    rule = profile.compression_color_space
    if rule.enabled:
        allowed = {(item.compression, item.srgb) for item in rule.allowed_combinations}
        observed_pair = (asset.compression_settings, asset.srgb)
        expected_pairs = ", ".join(
            f"{item.compression}+{'sRGB' if item.srgb else 'Linear'}"
            for item in rule.allowed_combinations
        )
        check(
            observed_pair not in allowed,
            rule_id="texture2d.compression_color_space",
            severity=rule.severity,
            metric="compression_color_space",
            observed=f"{asset.compression_settings}+{'sRGB' if asset.srgb else 'Linear'}",
            expected=expected_pairs,
            pointer="/rules/compression_color_space/allowed_combinations",
            message=(
                f"Compression/color-space pair {observed_pair!r} is not allowed by profile."
            ),
        )
    rule = profile.virtual_texture
    if rule.enabled and rule.expected != "any":
        expected = rule.expected == "enabled"
        check(
            asset.virtual_texture_streaming is not expected,
            rule_id="texture2d.virtual_texture",
            severity=rule.severity,
            metric="virtual_texture_streaming",
            observed=asset.virtual_texture_streaming,
            expected=expected,
            pointer="/rules/virtual_texture/expected",
            message=(
                f"Virtual Texture Streaming is {asset.virtual_texture_streaming}; "
                f"profile expects {rule.expected}."
            ),
        )
    rule = profile.streaming
    if rule.enabled and rule.expected != "any":
        expected_never_stream = rule.expected == "disabled"
        check(
            asset.never_stream is not expected_never_stream,
            rule_id="texture2d.streaming",
            severity=rule.severity,
            metric="never_stream",
            observed=not asset.never_stream,
            expected=not expected_never_stream,
            pointer="/rules/streaming/expected",
            message=(
                f"Texture streamable state is {not asset.never_stream}; "
                f"profile expects {rule.expected}."
            ),
        )
    return issues, evidence


def build_texture_report_from_collection(
    *,
    profile: TextureAuditProfile,
    collector: TextureMetadataCollector,
    batch: CollectionBatch,
    requested_asset_paths: Sequence[str],
    requested_asset_count: int,
    processed_asset_count: int,
    cancelled_asset_count: int,
    completed_batch_count: int,
    batch_size: int | None,
    report_id_factory: Callable[[], str] | None = None,
) -> TextureAuditReport:
    assets = list(batch.assets)
    issues: list[Issue] = []
    evidence: list[Evidence] = []
    for asset in sorted(assets, key=lambda item: item.asset_path):
        asset_issues, asset_evidence = _evaluate_texture(asset, profile, collector.mode)
        issues.extend(asset_issues)
        evidence.extend(asset_evidence)
    profile_fingerprint = hashlib.sha256(
        f"{profile.profile_id}:{profile.profile_version}".encode()
    ).hexdigest()[:8]
    report_id = (
        report_id_factory()
        if report_id_factory
        else _stable_id(
            "texture-report",
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
    return TextureAuditReport.create(
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


def audit_textures(
    *,
    profile: TextureAuditProfile,
    collector: TextureMetadataCollector,
    asset_paths: Sequence[str] | None = None,
    batch_size: int = 128,
    should_cancel: Callable[[], bool] | None = None,
    on_progress: Callable[[BatchProgress], None] | None = None,
    report_id_factory: Callable[[], str] | None = None,
) -> TextureAuditReport:
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
    return build_texture_report_from_collection(
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
