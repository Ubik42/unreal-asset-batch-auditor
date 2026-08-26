from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

CONTRACT_VERSION = "unreal-asset-audit@1.0.0"
PROFILE_VERSION = "unreal-static-mesh-profile@1.0.0"
Severity = Literal["info", "warning", "error"]


class ContractError(ValueError):
    """Raised when external JSON does not satisfy the supported contract."""


def _required(mapping: dict[str, Any], key: str) -> Any:
    if key not in mapping:
        raise ContractError(f"missing required field: {key}")
    return mapping[key]


def _positive_int(value: Any, path: str, *, allow_zero: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractError(f"{path} must be an integer")
    minimum = 0 if allow_zero else 1
    if value < minimum:
        raise ContractError(f"{path} must be >= {minimum}")
    return value


def _severity(value: Any, path: str) -> Severity:
    if value not in {"info", "warning", "error"}:
        raise ContractError(f"{path} must be info, warning, or error")
    return value


def _boolean(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise ContractError(f"{path} must be a boolean")
    return value


@dataclass(frozen=True)
class LimitRule:
    enabled: bool
    max_value: int
    severity: Severity


@dataclass(frozen=True)
class MinimumRule:
    enabled: bool
    min_value: int
    severity: Severity


@dataclass(frozen=True)
class NaniteRule:
    enabled: bool
    expected: Literal["enabled", "disabled", "any"]
    severity: Severity


@dataclass(frozen=True)
class AuditProfile:
    schema_version: str
    profile_id: str
    profile_version: str
    description: str
    triangle_budget: LimitRule
    vertex_budget: LimitRule
    material_slots: LimitRule
    lod_count: MinimumRule
    nanite: NaniteRule

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> AuditProfile:
        if _required(raw, "schema_version") != PROFILE_VERSION:
            raise ContractError(f"unsupported profile schema_version: {raw['schema_version']!r}")
        rules = _required(raw, "rules")
        if not isinstance(rules, dict):
            raise ContractError("rules must be an object")

        def limit(name: str, threshold: str) -> LimitRule:
            item = _required(rules, name)
            return LimitRule(
                enabled=_boolean(_required(item, "enabled"), f"rules.{name}.enabled"),
                max_value=_positive_int(_required(item, threshold), f"rules.{name}.{threshold}"),
                severity=_severity(_required(item, "severity"), f"rules.{name}.severity"),
            )

        lod = _required(rules, "lod_count")
        nanite = _required(rules, "nanite")
        expected = _required(nanite, "expected")
        if expected not in {"enabled", "disabled", "any"}:
            raise ContractError("rules.nanite.expected must be enabled, disabled, or any")
        profile_id = _required(raw, "profile_id")
        profile_version = _required(raw, "profile_version")
        if not isinstance(profile_id, str) or not profile_id.strip():
            raise ContractError("profile_id must be a non-empty string")
        if not isinstance(profile_version, str) or not profile_version.strip():
            raise ContractError("profile_version must be a non-empty string")
        return cls(
            schema_version=PROFILE_VERSION,
            profile_id=profile_id,
            profile_version=profile_version,
            description=str(raw.get("description", "")),
            triangle_budget=limit("triangle_budget", "max_lod0"),
            vertex_budget=limit("vertex_budget", "max_lod0"),
            material_slots=limit("material_slots", "max_count"),
            lod_count=MinimumRule(
                enabled=_boolean(_required(lod, "enabled"), "rules.lod_count.enabled"),
                min_value=_positive_int(_required(lod, "min_count"), "rules.lod_count.min_count"),
                severity=_severity(_required(lod, "severity"), "rules.lod_count.severity"),
            ),
            nanite=NaniteRule(
                enabled=_boolean(_required(nanite, "enabled"), "rules.nanite.enabled"),
                expected=expected,
                severity=_severity(_required(nanite, "severity"), "rules.nanite.severity"),
            ),
        )

    @classmethod
    def load(cls, path: str | Path) -> AuditProfile:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


@dataclass(frozen=True)
class LODMetadata:
    index: int
    triangles: int
    vertices: int

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> LODMetadata:
        return cls(
            index=_positive_int(_required(raw, "index"), "lod.index", allow_zero=True),
            triangles=_positive_int(
                _required(raw, "triangles"), "lod.triangles", allow_zero=True
            ),
            vertices=_positive_int(_required(raw, "vertices"), "lod.vertices", allow_zero=True),
        )


@dataclass(frozen=True)
class StaticMeshMetadata:
    asset_path: str
    asset_name: str
    lods: tuple[LODMetadata, ...]
    material_slot_count: int
    nanite_enabled: bool

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> StaticMeshMetadata:
        lods = tuple(LODMetadata.from_dict(item) for item in _required(raw, "lods"))
        if not lods:
            raise ContractError("lods must contain at least LOD0")
        if [lod.index for lod in lods] != list(range(len(lods))):
            raise ContractError("lod indices must be contiguous and start at zero")
        return cls(
            asset_path=str(_required(raw, "asset_path")),
            asset_name=str(_required(raw, "asset_name")),
            lods=lods,
            material_slot_count=_positive_int(
                _required(raw, "material_slot_count"),
                "material_slot_count",
                allow_zero=True,
            ),
            nanite_enabled=_boolean(_required(raw, "nanite_enabled"), "nanite_enabled"),
        )


@dataclass(frozen=True)
class CollectionFailure:
    schema_version: str
    asset_path: str
    code: str
    message: str
    collector: str


@dataclass(frozen=True)
class Evidence:
    schema_version: str
    evidence_id: str
    asset_path: str
    metric: str
    observed: int | bool | str
    expected: int | bool | str
    profile_pointer: str
    collector: str


@dataclass(frozen=True)
class Issue:
    schema_version: str
    issue_id: str
    asset_path: str
    rule_id: str
    severity: Severity
    message: str
    evidence_id: str


@dataclass
class Report:
    schema_version: str
    report_id: str
    created_at: str
    profile_id: str
    profile_version: str
    profile_schema_version: str
    collection_mode: Literal["offline_fixture", "unreal_editor"]
    real_unreal_validation: bool
    host_engine_version: str | None
    asset_count: int
    issue_count: int
    collection_failure_count: int
    requested_asset_count: int
    processed_asset_count: int
    cancelled_asset_count: int
    completed_batch_count: int
    batch_size: int | None
    assets: list[StaticMeshMetadata] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    collection_failures: list[CollectionFailure] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        *,
        report_id: str,
        profile: AuditProfile,
        collection_mode: Literal["offline_fixture", "unreal_editor"],
        real_unreal_validation: bool,
        host_engine_version: str | None,
        assets: list[StaticMeshMetadata],
        requested_asset_count: int,
        processed_asset_count: int,
        cancelled_asset_count: int,
        completed_batch_count: int,
        batch_size: int | None,
        issues: list[Issue],
        evidence: list[Evidence],
        collection_failures: list[CollectionFailure],
    ) -> Report:
        if collection_mode == "offline_fixture" and real_unreal_validation:
            raise ContractError("offline_fixture reports cannot claim real Unreal validation")
        if real_unreal_validation and not host_engine_version:
            raise ContractError("real Unreal validation requires host_engine_version")
        execution_counts = {
            "requested_asset_count": requested_asset_count,
            "processed_asset_count": processed_asset_count,
            "cancelled_asset_count": cancelled_asset_count,
            "completed_batch_count": completed_batch_count,
        }
        for name, value in execution_counts.items():
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ContractError(f"{name} must be a non-negative integer")
        if requested_asset_count != processed_asset_count + cancelled_asset_count:
            raise ContractError(
                "requested_asset_count must equal processed_asset_count + cancelled_asset_count"
            )
        if processed_asset_count != len(assets) + len(collection_failures):
            raise ContractError(
                "processed_asset_count must equal successful assets + collection failures"
            )
        if batch_size is not None and (
            isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1
        ):
            raise ContractError("batch_size must be null or a positive integer")
        return cls(
            schema_version=CONTRACT_VERSION,
            report_id=report_id,
            created_at=datetime.now(UTC).isoformat(),
            profile_id=profile.profile_id,
            profile_version=profile.profile_version,
            profile_schema_version=profile.schema_version,
            collection_mode=collection_mode,
            real_unreal_validation=real_unreal_validation,
            host_engine_version=host_engine_version,
            asset_count=len(assets),
            issue_count=len(issues),
            collection_failure_count=len(collection_failures),
            requested_asset_count=requested_asset_count,
            processed_asset_count=processed_asset_count,
            cancelled_asset_count=cancelled_asset_count,
            completed_batch_count=completed_batch_count,
            batch_size=batch_size,
            assets=assets,
            issues=issues,
            evidence=evidence,
            collection_failures=collection_failures,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write(self, path: str | Path) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
