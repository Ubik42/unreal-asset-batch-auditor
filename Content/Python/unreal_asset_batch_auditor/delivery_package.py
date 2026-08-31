from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from .audit import audit_assets
from .collectors import MetadataCollector, UnrealCppCollector
from .contracts import AuditProfile, ContractError
from .material_audit import audit_materials
from .material_collectors import MaterialUnrealCppCollector
from .material_contracts import MaterialAuditProfile
from .texture_audit import audit_textures
from .texture_collectors import TextureUnrealCppCollector
from .texture_contracts import TextureAuditProfile

DELIVERY_PACKAGE_RECIPE_VERSION = "unreal-delivery-package-recipe@1.0.0"
DELIVERY_PACKAGE_SUMMARY_VERSION = "unreal-delivery-package-summary@1.0.0"
ASSET_TYPES = ("static_mesh", "texture2d", "material_interface")
AssetType = Literal["static_mesh", "texture2d", "material_interface"]
LaneState = Literal["completed", "cancelled", "failed", "skipped"]
PackageStatus = Literal["completed", "partial", "cancelled"]
PackageDecision = Literal["ready", "attention", "blocked"]


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _non_empty_text(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{key} must be a non-empty string")
    return value.strip()


@dataclass(frozen=True)
class DeliveryPackageRecipe:
    schema_version: str
    recipe_id: str
    recipe_version: str
    description: str
    profile_paths: dict[AssetType, str]
    blocking_severities: tuple[str, ...]
    source_path: str

    @classmethod
    def load(cls, path: str | Path) -> DeliveryPackageRecipe:
        source = Path(path).resolve()
        try:
            raw = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ContractError(f"could not read delivery package recipe: {source}") from exc
        if not isinstance(raw, dict):
            raise ContractError("delivery package recipe must be an object")
        if raw.get("schema_version") != DELIVERY_PACKAGE_RECIPE_VERSION:
            raise ContractError(
                f"unsupported delivery package recipe: {raw.get('schema_version')!r}"
            )
        profiles = raw.get("profiles")
        if not isinstance(profiles, dict) or set(profiles) != set(ASSET_TYPES):
            raise ContractError(
                "profiles must map static_mesh, texture2d, and material_interface"
            )
        resolved_profiles: dict[AssetType, str] = {}
        for asset_type in ASSET_TYPES:
            value = profiles.get(asset_type)
            if not isinstance(value, str) or not value.strip():
                raise ContractError(f"profiles.{asset_type} must be a non-empty path")
            profile_path = Path(value)
            if not profile_path.is_absolute():
                profile_path = source.parent / profile_path
            profile_path = profile_path.resolve()
            if not profile_path.is_file():
                raise ContractError(f"profile does not exist: {profile_path}")
            resolved_profiles[asset_type] = str(profile_path)  # type: ignore[index]
        blocking = raw.get("blocking_severities", ["error"])
        if (
            not isinstance(blocking, list)
            or not blocking
            or any(item not in {"info", "warning", "error"} for item in blocking)
        ):
            raise ContractError(
                "blocking_severities must be a non-empty subset of info, warning, error"
            )
        return cls(
            schema_version=DELIVERY_PACKAGE_RECIPE_VERSION,
            recipe_id=_non_empty_text(raw, "recipe_id"),
            recipe_version=_non_empty_text(raw, "recipe_version"),
            description=str(raw.get("description", "")),
            profile_paths=resolved_profiles,
            blocking_severities=tuple(dict.fromkeys(blocking)),
            source_path=str(source),
        )


@dataclass(frozen=True)
class IgnoredPackageAsset:
    asset_path: str
    asset_class: str
    reason: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> IgnoredPackageAsset:
        if not isinstance(raw, dict):
            raise ContractError("ignored asset must be an object")
        return cls(
            asset_path=_non_empty_text(raw, "asset_path"),
            asset_class=_non_empty_text(raw, "asset_class"),
            reason=_non_empty_text(raw, "reason"),
        )


@dataclass(frozen=True)
class DeliveryPackageLane:
    asset_type: AssetType
    state: LaneState
    profile_id: str | None
    profile_version: str | None
    report_path: str | None
    report_id: str | None
    requested_count: int
    processed_count: int
    passed_asset_count: int
    issue_asset_count: int
    issue_count: int
    collection_failure_count: int
    cancelled_count: int
    blocking_issue_count: int
    hotspot_path: str | None
    hotspot_issue_count: int
    error_code: str | None = None
    error_message: str | None = None


@dataclass
class DeliveryPackageSummary:
    schema_version: str
    package_run_id: str
    created_at: str
    recipe_id: str
    recipe_version: str
    recipe_schema_version: str
    status: PackageStatus
    decision: PackageDecision
    real_unreal_validation: bool
    host_engine_versions: list[str]
    selected_count: int
    supported_count: int
    ignored_count: int
    processed_count: int
    passed_asset_count: int
    issue_asset_count: int
    issue_count: int
    collection_failure_count: int
    cancelled_count: int
    blocking_issue_count: int
    lanes: list[DeliveryPackageLane] = field(default_factory=list)
    ignored_assets: list[IgnoredPackageAsset] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write(self, path: str | Path) -> None:
        _atomic_json(Path(path), self.to_dict())


def _read_report(path: str | Path, expected_type: AssetType) -> dict[str, Any]:
    source = Path(path)
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"could not read lane report: {source}") from exc
    actual_type = raw.get("asset_type", "static_mesh") if isinstance(raw, dict) else None
    if not isinstance(raw, dict) or actual_type != expected_type:
        raise ContractError(f"lane report type mismatch: expected {expected_type}")
    required_counts = (
        "asset_count",
        "issue_count",
        "collection_failure_count",
        "requested_asset_count",
        "processed_asset_count",
        "cancelled_asset_count",
    )
    for key in required_counts:
        if isinstance(raw.get(key), bool) or not isinstance(raw.get(key), int):
            raise ContractError(f"lane report {key} must be an integer")
    for key in ("issues", "assets", "collection_failures"):
        if not isinstance(raw.get(key), list):
            raise ContractError(f"lane report {key} must be an array")
    if raw["asset_count"] != len(raw["assets"]):
        raise ContractError("lane report asset_count does not match assets")
    if raw["issue_count"] != len(raw["issues"]):
        raise ContractError("lane report issue_count does not match issues")
    if raw["collection_failure_count"] != len(raw["collection_failures"]):
        raise ContractError(
            "lane report collection_failure_count does not match collection_failures"
        )
    return raw


def _directory_for(asset_path: str) -> str:
    package_path = asset_path.split(".", 1)[0].rstrip("/")
    if "/" not in package_path[1:]:
        return package_path
    return package_path.rsplit("/", 1)[0]


def _lane_from_report(
    *,
    asset_type: AssetType,
    report_path: str,
    report: dict[str, Any],
    blocking_severities: tuple[str, ...],
) -> DeliveryPackageLane:
    issue_assets: set[str] = set()
    hotspot_counts: dict[str, int] = {}
    blocking_count = 0
    for issue in report["issues"]:
        if not isinstance(issue, dict):
            raise ContractError("lane report issues must contain objects")
        asset_path = _non_empty_text(issue, "asset_path")
        issue_assets.add(asset_path)
        directory = _directory_for(asset_path)
        hotspot_counts[directory] = hotspot_counts.get(directory, 0) + 1
        if issue.get("severity") in blocking_severities:
            blocking_count += 1
    hotspot = min(
        hotspot_counts,
        key=lambda path: (-hotspot_counts[path], path),
        default=None,
    )
    cancelled_count = int(report["cancelled_asset_count"])
    return DeliveryPackageLane(
        asset_type=asset_type,
        state="cancelled" if cancelled_count else "completed",
        profile_id=str(report.get("profile_id") or ""),
        profile_version=str(report.get("profile_version") or ""),
        report_path=str(report_path),
        report_id=str(report.get("report_id") or ""),
        requested_count=int(report["requested_asset_count"]),
        processed_count=int(report["processed_asset_count"]),
        passed_asset_count=max(0, int(report["asset_count"]) - len(issue_assets)),
        issue_asset_count=len(issue_assets),
        issue_count=int(report["issue_count"]),
        collection_failure_count=int(report["collection_failure_count"]),
        cancelled_count=cancelled_count,
        blocking_issue_count=blocking_count,
        hotspot_path=hotspot,
        hotspot_issue_count=hotspot_counts.get(hotspot, 0) if hotspot else 0,
    )


def build_delivery_package_summary(
    *,
    recipe: DeliveryPackageRecipe,
    report_paths: dict[AssetType, str],
    requested_counts: dict[AssetType, int],
    ignored_assets: list[IgnoredPackageAsset] | None = None,
    lane_errors: dict[AssetType, tuple[str, str]] | None = None,
    cancelled_lanes: set[AssetType] | None = None,
) -> DeliveryPackageSummary:
    ignored = sorted(
        ignored_assets or [], key=lambda item: (item.asset_path, item.asset_class)
    )
    errors = lane_errors or {}
    cancelled = cancelled_lanes or set()
    lanes: list[DeliveryPackageLane] = []
    host_versions: set[str] = set()
    real_flags: list[bool] = []
    for asset_type in ASSET_TYPES:
        typed_asset_type: AssetType = asset_type  # type: ignore[assignment]
        requested = int(requested_counts.get(typed_asset_type, 0))
        if requested < 0:
            raise ContractError("requested lane counts cannot be negative")
        if typed_asset_type in report_paths:
            report = _read_report(report_paths[typed_asset_type], typed_asset_type)
            if int(report["requested_asset_count"]) != requested:
                raise ContractError(
                    f"requested count mismatch for {typed_asset_type} lane"
                )
            lane = _lane_from_report(
                asset_type=typed_asset_type,
                report_path=report_paths[typed_asset_type],
                report=report,
                blocking_severities=recipe.blocking_severities,
            )
            lanes.append(lane)
            real_flags.append(bool(report.get("real_unreal_validation")))
            if report.get("host_engine_version"):
                host_versions.add(str(report["host_engine_version"]))
        elif typed_asset_type in errors:
            code, message = errors[typed_asset_type]
            lanes.append(
                DeliveryPackageLane(
                    asset_type=typed_asset_type,
                    state="failed",
                    profile_id=None,
                    profile_version=None,
                    report_path=None,
                    report_id=None,
                    requested_count=requested,
                    processed_count=0,
                    passed_asset_count=0,
                    issue_asset_count=0,
                    issue_count=0,
                    collection_failure_count=0,
                    cancelled_count=0,
                    blocking_issue_count=0,
                    hotspot_path=None,
                    hotspot_issue_count=0,
                    error_code=str(code),
                    error_message=str(message),
                )
            )
        elif typed_asset_type in cancelled:
            lanes.append(
                DeliveryPackageLane(
                    asset_type=typed_asset_type,
                    state="cancelled",
                    profile_id=None,
                    profile_version=None,
                    report_path=None,
                    report_id=None,
                    requested_count=requested,
                    processed_count=0,
                    passed_asset_count=0,
                    issue_asset_count=0,
                    issue_count=0,
                    collection_failure_count=0,
                    cancelled_count=requested,
                    blocking_issue_count=0,
                    hotspot_path=None,
                    hotspot_issue_count=0,
                )
            )
        else:
            lanes.append(
                DeliveryPackageLane(
                    asset_type=typed_asset_type,
                    state="skipped",
                    profile_id=None,
                    profile_version=None,
                    report_path=None,
                    report_id=None,
                    requested_count=requested,
                    processed_count=0,
                    passed_asset_count=0,
                    issue_asset_count=0,
                    issue_count=0,
                    collection_failure_count=0,
                    cancelled_count=requested,
                    blocking_issue_count=0,
                    hotspot_path=None,
                    hotspot_issue_count=0,
                )
            )
    supported_count = sum(lane.requested_count for lane in lanes)
    processed_count = sum(lane.processed_count for lane in lanes)
    cancelled_count = sum(lane.cancelled_count for lane in lanes)
    failures = sum(lane.collection_failure_count for lane in lanes)
    blocking = sum(lane.blocking_issue_count for lane in lanes)
    any_failed = any(lane.state == "failed" for lane in lanes)
    any_cancelled = any(lane.state == "cancelled" for lane in lanes)
    status: PackageStatus = (
        "cancelled"
        if any_cancelled
        else ("partial" if any_failed or processed_count < supported_count else "completed")
    )
    issue_count = sum(lane.issue_count for lane in lanes)
    decision: PackageDecision = (
        "blocked"
        if blocking or failures or any_failed
        else ("attention" if issue_count else "ready")
    )
    identity = {
        "recipe": [recipe.recipe_id, recipe.recipe_version],
        "lanes": [
            [lane.asset_type, lane.report_id, lane.state, lane.requested_count]
            for lane in lanes
        ],
        "ignored": [asdict(item) for item in ignored],
    }
    run_id = "package-" + hashlib.sha256(
        json.dumps(identity, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    return DeliveryPackageSummary(
        schema_version=DELIVERY_PACKAGE_SUMMARY_VERSION,
        package_run_id=run_id,
        created_at=datetime.now(UTC).isoformat(),
        recipe_id=recipe.recipe_id,
        recipe_version=recipe.recipe_version,
        recipe_schema_version=recipe.schema_version,
        status=status,
        decision=decision,
        real_unreal_validation=bool(real_flags) and all(real_flags) and not any_failed,
        host_engine_versions=sorted(host_versions),
        selected_count=supported_count + len(ignored),
        supported_count=supported_count,
        ignored_count=len(ignored),
        processed_count=processed_count,
        passed_asset_count=sum(lane.passed_asset_count for lane in lanes),
        issue_asset_count=sum(lane.issue_asset_count for lane in lanes),
        issue_count=issue_count,
        collection_failure_count=failures,
        cancelled_count=cancelled_count,
        blocking_issue_count=blocking,
        lanes=lanes,
        ignored_assets=ignored,
    )


def audit_delivery_package(
    *,
    recipe: DeliveryPackageRecipe,
    lane_asset_paths: dict[AssetType, list[str]],
    output_root: str | Path,
    summary_path: str | Path,
    ignored_assets: list[IgnoredPackageAsset] | None = None,
    batch_size: int = 64,
    collectors: dict[AssetType, MetadataCollector] | None = None,
) -> DeliveryPackageSummary:
    if batch_size < 1:
        raise ContractError("batch_size must be a positive integer")
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    collector_map: dict[AssetType, MetadataCollector] = collectors or {
        "static_mesh": UnrealCppCollector(),
        "texture2d": TextureUnrealCppCollector(),
        "material_interface": MaterialUnrealCppCollector(),
    }
    report_paths: dict[AssetType, str] = {}
    requested_counts: dict[AssetType, int] = {}
    for asset_type in ASSET_TYPES:
        typed_asset_type: AssetType = asset_type  # type: ignore[assignment]
        paths = sorted(dict.fromkeys(lane_asset_paths.get(typed_asset_type, [])))
        requested_counts[typed_asset_type] = len(paths)
        if not paths:
            continue
        report_path = root / f"{typed_asset_type}-report.json"
        if typed_asset_type == "static_mesh":
            report = audit_assets(
                profile=AuditProfile.load(recipe.profile_paths[typed_asset_type]),
                collector=collector_map[typed_asset_type],
                asset_paths=paths,
                batch_size=batch_size,
            )
        elif typed_asset_type == "texture2d":
            report = audit_textures(
                profile=TextureAuditProfile.load(recipe.profile_paths[typed_asset_type]),
                collector=collector_map[typed_asset_type],
                asset_paths=paths,
                batch_size=batch_size,
            )
        else:
            report = audit_materials(
                profile=MaterialAuditProfile.load(recipe.profile_paths[typed_asset_type]),
                collector=collector_map[typed_asset_type],
                asset_paths=paths,
                batch_size=batch_size,
            )
        report.write(report_path)
        report_paths[typed_asset_type] = str(report_path)
    summary = build_delivery_package_summary(
        recipe=recipe,
        report_paths=report_paths,
        requested_counts=requested_counts,
        ignored_assets=ignored_assets,
    )
    summary.write(summary_path)
    return summary


__all__ = [
    "ASSET_TYPES",
    "DELIVERY_PACKAGE_RECIPE_VERSION",
    "DELIVERY_PACKAGE_SUMMARY_VERSION",
    "DeliveryPackageLane",
    "DeliveryPackageRecipe",
    "DeliveryPackageSummary",
    "IgnoredPackageAsset",
    "audit_delivery_package",
    "build_delivery_package_summary",
]
