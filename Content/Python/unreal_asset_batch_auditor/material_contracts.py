from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from .contracts import (
    CollectionFailure,
    ContractError,
    Evidence,
    Issue,
    Severity,
    _boolean,
    _positive_int,
    _required,
    _severity,
    _string_tuple,
)

MATERIAL_PROFILE_VERSION = "unreal-material-profile@1.0.0"
MATERIAL_REPORT_VERSION = "unreal-material-audit@1.0.0"
MATERIAL_FIXTURE_VERSION = "unreal-material-fixture@1.0.0"


@dataclass(frozen=True)
class MaterialAllowedValuesRule:
    enabled: bool
    allowed_values: tuple[str, ...]
    severity: Severity


@dataclass(frozen=True)
class MaterialStateRule:
    enabled: bool
    expected: Literal["enabled", "disabled", "any"]
    severity: Severity


@dataclass(frozen=True)
class MaterialBooleanRule:
    enabled: bool
    required: bool
    severity: Severity


@dataclass(frozen=True)
class MaterialMaximumRule:
    enabled: bool
    max_count: int
    severity: Severity


@dataclass(frozen=True)
class MaterialDimensionRule:
    enabled: bool
    max_size: int
    severity: Severity


@dataclass(frozen=True)
class MaterialAuditProfile:
    schema_version: str
    profile_id: str
    profile_version: str
    description: str
    allowed_domains: MaterialAllowedValuesRule
    allowed_blend_modes: MaterialAllowedValuesRule
    two_sided: MaterialStateRule
    instance_parent: MaterialBooleanRule
    parent_depth: MaterialMaximumRule
    texture_dependencies: MaterialMaximumRule
    texture_dimension: MaterialDimensionRule

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> MaterialAuditProfile:
        if _required(raw, "schema_version") != MATERIAL_PROFILE_VERSION:
            raise ContractError("unsupported material profile schema_version")
        profile_id = _required(raw, "profile_id")
        profile_version = _required(raw, "profile_version")
        if not isinstance(profile_id, str) or not profile_id.strip():
            raise ContractError("profile_id must be a non-empty string")
        if not isinstance(profile_version, str) or not profile_version.strip():
            raise ContractError("profile_version must be a non-empty string")
        rules = _required(raw, "rules")
        if not isinstance(rules, dict):
            raise ContractError("rules must be an object")

        def item(name: str) -> dict[str, Any]:
            value = _required(rules, name)
            if not isinstance(value, dict):
                raise ContractError(f"rules.{name} must be an object")
            return value

        def allowed(name: str) -> MaterialAllowedValuesRule:
            value = item(name)
            allowed_values = _string_tuple(
                _required(value, "allowed_values"), f"rules.{name}.allowed_values"
            )
            if len(set(allowed_values)) != len(allowed_values):
                raise ContractError(f"rules.{name}.allowed_values must be unique")
            return MaterialAllowedValuesRule(
                enabled=_boolean(_required(value, "enabled"), f"rules.{name}.enabled"),
                allowed_values=allowed_values,
                severity=_severity(_required(value, "severity"), f"rules.{name}.severity"),
            )

        two_sided = item("two_sided")
        expected = _required(two_sided, "expected")
        if expected not in {"enabled", "disabled", "any"}:
            raise ContractError(
                "rules.two_sided.expected must be enabled, disabled, or any"
            )
        instance_parent = item("instance_parent")
        parent_depth = item("parent_depth")
        texture_dependencies = item("texture_dependencies")
        texture_dimension = item("texture_dimension")
        return cls(
            schema_version=MATERIAL_PROFILE_VERSION,
            profile_id=profile_id,
            profile_version=profile_version,
            description=str(raw.get("description", "")),
            allowed_domains=allowed("allowed_domains"),
            allowed_blend_modes=allowed("allowed_blend_modes"),
            two_sided=MaterialStateRule(
                enabled=_boolean(
                    _required(two_sided, "enabled"), "rules.two_sided.enabled"
                ),
                expected=expected,
                severity=_severity(
                    _required(two_sided, "severity"), "rules.two_sided.severity"
                ),
            ),
            instance_parent=MaterialBooleanRule(
                enabled=_boolean(
                    _required(instance_parent, "enabled"),
                    "rules.instance_parent.enabled",
                ),
                required=_boolean(
                    _required(instance_parent, "required"),
                    "rules.instance_parent.required",
                ),
                severity=_severity(
                    _required(instance_parent, "severity"),
                    "rules.instance_parent.severity",
                ),
            ),
            parent_depth=MaterialMaximumRule(
                enabled=_boolean(
                    _required(parent_depth, "enabled"), "rules.parent_depth.enabled"
                ),
                max_count=_positive_int(
                    _required(parent_depth, "max_count"),
                    "rules.parent_depth.max_count",
                ),
                severity=_severity(
                    _required(parent_depth, "severity"), "rules.parent_depth.severity"
                ),
            ),
            texture_dependencies=MaterialMaximumRule(
                enabled=_boolean(
                    _required(texture_dependencies, "enabled"),
                    "rules.texture_dependencies.enabled",
                ),
                max_count=_positive_int(
                    _required(texture_dependencies, "max_count"),
                    "rules.texture_dependencies.max_count",
                    allow_zero=True,
                ),
                severity=_severity(
                    _required(texture_dependencies, "severity"),
                    "rules.texture_dependencies.severity",
                ),
            ),
            texture_dimension=MaterialDimensionRule(
                enabled=_boolean(
                    _required(texture_dimension, "enabled"),
                    "rules.texture_dimension.enabled",
                ),
                max_size=_positive_int(
                    _required(texture_dimension, "max_size"),
                    "rules.texture_dimension.max_size",
                ),
                severity=_severity(
                    _required(texture_dimension, "severity"),
                    "rules.texture_dimension.severity",
                ),
            ),
        )

    @classmethod
    def load(cls, path: str | Path) -> MaterialAuditProfile:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


@dataclass(frozen=True)
class MaterialInterfaceMetadata:
    asset_path: str
    asset_name: str
    material_kind: Literal["material", "material_instance"]
    material_domain: str
    blend_mode: str
    two_sided: bool
    shading_models: tuple[str, ...]
    parent_path: str | None
    base_material_path: str | None
    parent_depth: int
    texture_paths: tuple[str, ...]
    texture_dependency_count: int
    max_texture_dimension: int

    @property
    def has_parent(self) -> bool:
        return bool(self.parent_path)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> MaterialInterfaceMetadata:
        def text(name: str) -> str:
            value = _required(raw, name)
            if not isinstance(value, str) or not value.strip():
                raise ContractError(f"{name} must be a non-empty string")
            return value

        def optional_text(name: str) -> str | None:
            value = raw.get(name)
            if value is None:
                return None
            if not isinstance(value, str) or not value.strip():
                raise ContractError(f"{name} must be null or a non-empty string")
            return value

        material_kind = _required(raw, "material_kind")
        if material_kind not in {"material", "material_instance"}:
            raise ContractError("material_kind must be material or material_instance")
        shading_models = _string_tuple(
            _required(raw, "shading_models"), "shading_models"
        )
        texture_paths = _string_tuple(
            _required(raw, "texture_paths"), "texture_paths", allow_empty=True
        )
        if len(set(texture_paths)) != len(texture_paths):
            raise ContractError("texture_paths must be unique")
        parent_path = optional_text("parent_path")
        parent_depth = _positive_int(
            _required(raw, "parent_depth"), "parent_depth", allow_zero=True
        )
        texture_dependency_count = _positive_int(
            _required(raw, "texture_dependency_count"),
            "texture_dependency_count",
            allow_zero=True,
        )
        max_texture_dimension = _positive_int(
            _required(raw, "max_texture_dimension"),
            "max_texture_dimension",
            allow_zero=True,
        )
        if texture_dependency_count != len(texture_paths):
            raise ContractError("texture_dependency_count must match texture_paths")
        if material_kind == "material" and (parent_path is not None or parent_depth != 0):
            raise ContractError("base material cannot declare an instance parent chain")
        if parent_path is None and parent_depth != 0:
            raise ContractError("parent_depth must be zero when parent_path is null")
        if parent_path is not None and parent_depth < 1:
            raise ContractError("parent_depth must be positive when parent_path is present")
        return cls(
            asset_path=text("asset_path"),
            asset_name=text("asset_name"),
            material_kind=material_kind,
            material_domain=text("material_domain"),
            blend_mode=text("blend_mode"),
            two_sided=_boolean(_required(raw, "two_sided"), "two_sided"),
            shading_models=shading_models,
            parent_path=parent_path,
            base_material_path=optional_text("base_material_path"),
            parent_depth=parent_depth,
            texture_paths=texture_paths,
            texture_dependency_count=texture_dependency_count,
            max_texture_dimension=max_texture_dimension,
        )


@dataclass
class MaterialAuditReport:
    schema_version: str
    report_id: str
    created_at: str
    profile_id: str
    profile_version: str
    profile_schema_version: str
    asset_type: Literal["material_interface"]
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
    assets: list[MaterialInterfaceMetadata] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    collection_failures: list[CollectionFailure] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        *,
        report_id: str,
        profile: MaterialAuditProfile,
        collection_mode: Literal["offline_fixture", "unreal_editor"],
        real_unreal_validation: bool,
        host_engine_version: str | None,
        assets: list[MaterialInterfaceMetadata],
        requested_asset_count: int,
        processed_asset_count: int,
        cancelled_asset_count: int,
        completed_batch_count: int,
        batch_size: int | None,
        issues: list[Issue],
        evidence: list[Evidence],
        collection_failures: list[CollectionFailure],
    ) -> MaterialAuditReport:
        if collection_mode == "offline_fixture" and real_unreal_validation:
            raise ContractError("offline fixture cannot claim real Unreal validation")
        if real_unreal_validation and not host_engine_version:
            raise ContractError("real Unreal validation requires host_engine_version")
        if processed_asset_count != len(assets) + len(collection_failures):
            raise ContractError("processed count must equal collected assets plus failures")
        if requested_asset_count != processed_asset_count + cancelled_asset_count:
            raise ContractError("requested count must equal processed plus cancelled")
        return cls(
            schema_version=MATERIAL_REPORT_VERSION,
            report_id=report_id,
            created_at=datetime.now(UTC).isoformat(),
            profile_id=profile.profile_id,
            profile_version=profile.profile_version,
            profile_schema_version=profile.schema_version,
            asset_type="material_interface",
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
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(destination)


__all__ = [
    "MATERIAL_FIXTURE_VERSION",
    "MATERIAL_PROFILE_VERSION",
    "MATERIAL_REPORT_VERSION",
    "MaterialAuditProfile",
    "MaterialAuditReport",
    "MaterialInterfaceMetadata",
]
