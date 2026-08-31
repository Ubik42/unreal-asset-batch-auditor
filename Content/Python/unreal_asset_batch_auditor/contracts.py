from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

CONTRACT_VERSION = "unreal-asset-audit@1.0.0"
CONTRACT_VERSION_V2 = "unreal-asset-audit@2.0.0"
CONTRACT_VERSION_V3 = "unreal-asset-audit@3.0.0"
PROFILE_VERSION = "unreal-static-mesh-profile@1.0.0"
PROFILE_VERSION_V2 = "unreal-static-mesh-profile@2.0.0"
PROFILE_VERSION_V3 = "unreal-static-mesh-profile@3.0.0"
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


def _string_tuple(value: Any, path: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or (not value and not allow_empty):
        qualifier = "an array" if allow_empty else "a non-empty array"
        raise ContractError(f"{path} must be {qualifier} of non-empty strings")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ContractError(f"{path} must contain only non-empty strings")
    return tuple(value)


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
class CollisionRule:
    enabled: bool
    min_primitive_count: int
    allow_complex_as_simple: bool
    severity: Severity


@dataclass(frozen=True)
class LightmapUvRule:
    enabled: bool
    required: bool
    min_uv_channel_count: int
    severity: Severity


@dataclass(frozen=True)
class ObjectNameRule:
    enabled: bool
    required_prefixes: tuple[str, ...]
    pattern: str | None
    severity: Severity


@dataclass(frozen=True)
class PackagePathRule:
    enabled: bool
    allowed_roots: tuple[str, ...]
    forbidden_segments: tuple[str, ...]
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
    simple_collision: CollisionRule | None = None
    lightmap_uv: LightmapUvRule | None = None
    lightmap_resolution: MinimumRule | None = None
    object_name: ObjectNameRule | None = None
    package_path: PackagePathRule | None = None
    missing_materials: LimitRule | None = None
    unique_materials: LimitRule | None = None
    texture_dependencies: LimitRule | None = None
    texture_dimension: LimitRule | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> AuditProfile:
        schema_version = _required(raw, "schema_version")
        if schema_version not in {PROFILE_VERSION, PROFILE_VERSION_V2, PROFILE_VERSION_V3}:
            raise ContractError(f"unsupported profile schema_version: {schema_version!r}")
        rules = _required(raw, "rules")
        if not isinstance(rules, dict):
            raise ContractError("rules must be an object")

        def limit(name: str, threshold: str, *, allow_zero: bool = False) -> LimitRule:
            item = _required(rules, name)
            return LimitRule(
                enabled=_boolean(_required(item, "enabled"), f"rules.{name}.enabled"),
                max_value=_positive_int(
                    _required(item, threshold),
                    f"rules.{name}.{threshold}",
                    allow_zero=allow_zero,
                ),
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
        simple_collision = None
        lightmap_uv = None
        lightmap_resolution = None
        object_name = None
        package_path = None
        missing_materials = None
        unique_materials = None
        texture_dependencies = None
        texture_dimension = None
        if schema_version in {PROFILE_VERSION_V2, PROFILE_VERSION_V3}:
            collision = _required(rules, "simple_collision")
            lightmap = _required(rules, "lightmap_uv")
            resolution = _required(rules, "lightmap_resolution")
            simple_collision = CollisionRule(
                enabled=_boolean(
                    _required(collision, "enabled"), "rules.simple_collision.enabled"
                ),
                min_primitive_count=_positive_int(
                    _required(collision, "min_primitive_count"),
                    "rules.simple_collision.min_primitive_count",
                    allow_zero=True,
                ),
                allow_complex_as_simple=_boolean(
                    _required(collision, "allow_complex_as_simple"),
                    "rules.simple_collision.allow_complex_as_simple",
                ),
                severity=_severity(
                    _required(collision, "severity"), "rules.simple_collision.severity"
                ),
            )
            lightmap_uv = LightmapUvRule(
                enabled=_boolean(_required(lightmap, "enabled"), "rules.lightmap_uv.enabled"),
                required=_boolean(
                    _required(lightmap, "required"), "rules.lightmap_uv.required"
                ),
                min_uv_channel_count=_positive_int(
                    _required(lightmap, "min_uv_channel_count"),
                    "rules.lightmap_uv.min_uv_channel_count",
                ),
                severity=_severity(
                    _required(lightmap, "severity"), "rules.lightmap_uv.severity"
                ),
            )
            lightmap_resolution = MinimumRule(
                enabled=_boolean(
                    _required(resolution, "enabled"), "rules.lightmap_resolution.enabled"
                ),
                min_value=_positive_int(
                    _required(resolution, "min_resolution"),
                    "rules.lightmap_resolution.min_resolution",
                ),
                severity=_severity(
                    _required(resolution, "severity"),
                    "rules.lightmap_resolution.severity",
                ),
            )
            name_policy = rules.get("object_name")
            if name_policy is not None:
                prefixes = _string_tuple(
                    _required(name_policy, "required_prefixes"),
                    "rules.object_name.required_prefixes",
                )
                pattern = name_policy.get("pattern")
                if pattern is not None:
                    if not isinstance(pattern, str) or not pattern:
                        raise ContractError("rules.object_name.pattern must be non-empty or null")
                    try:
                        re.compile(pattern)
                    except re.error as exc:
                        raise ContractError(
                            f"rules.object_name.pattern is invalid: {exc}"
                        ) from exc
                object_name = ObjectNameRule(
                    enabled=_boolean(
                        _required(name_policy, "enabled"), "rules.object_name.enabled"
                    ),
                    required_prefixes=prefixes,
                    pattern=pattern,
                    severity=_severity(
                        _required(name_policy, "severity"), "rules.object_name.severity"
                    ),
                )
            path_policy = rules.get("package_path")
            if path_policy is not None:
                package_path = PackagePathRule(
                    enabled=_boolean(
                        _required(path_policy, "enabled"), "rules.package_path.enabled"
                    ),
                    allowed_roots=_string_tuple(
                        _required(path_policy, "allowed_roots"),
                        "rules.package_path.allowed_roots",
                    ),
                    forbidden_segments=_string_tuple(
                        _required(path_policy, "forbidden_segments"),
                        "rules.package_path.forbidden_segments",
                        allow_empty=True,
                    ),
                    severity=_severity(
                        _required(path_policy, "severity"), "rules.package_path.severity"
                    ),
                )
            if schema_version == PROFILE_VERSION_V3:
                missing_materials = limit(
                    "missing_materials", "max_missing_slots", allow_zero=True
                )
                unique_materials = limit("unique_materials", "max_count")
                texture_dependencies = limit("texture_dependencies", "max_count")
                texture_dimension = limit("texture_dimension", "max_size")

        return cls(
            schema_version=schema_version,
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
            simple_collision=simple_collision,
            lightmap_uv=lightmap_uv,
            lightmap_resolution=lightmap_resolution,
            object_name=object_name,
            package_path=package_path,
            missing_materials=missing_materials,
            unique_materials=unique_materials,
            texture_dependencies=texture_dependencies,
            texture_dimension=texture_dimension,
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
    simple_collision_primitive_count: int | None = None
    collision_complexity: str | None = None
    uv_channel_count: int | None = None
    lightmap_coordinate_index: int | None = None
    lightmap_resolution: int | None = None
    material_paths: tuple[str, ...] | None = None
    missing_material_slot_count: int | None = None
    unique_material_count: int | None = None
    texture_paths: tuple[str, ...] | None = None
    texture_dependency_count: int | None = None
    max_texture_dimension: int | None = None

    @property
    def has_extended_metadata(self) -> bool:
        return all(
            value is not None
            for value in (
                self.simple_collision_primitive_count,
                self.collision_complexity,
                self.uv_channel_count,
                self.lightmap_coordinate_index,
                self.lightmap_resolution,
            )
        )

    @property
    def has_valid_lightmap_uv(self) -> bool:
        return bool(
            self.uv_channel_count is not None
            and self.lightmap_coordinate_index is not None
            and self.uv_channel_count > 0
            and 0 <= self.lightmap_coordinate_index < self.uv_channel_count
        )

    @property
    def has_dependency_metadata(self) -> bool:
        return all(
            value is not None
            for value in (
                self.material_paths,
                self.missing_material_slot_count,
                self.unique_material_count,
                self.texture_paths,
                self.texture_dependency_count,
                self.max_texture_dimension,
            )
        )

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> StaticMeshMetadata:
        lods = tuple(LODMetadata.from_dict(item) for item in _required(raw, "lods"))
        if not lods:
            raise ContractError("lods must contain at least LOD0")
        if [lod.index for lod in lods] != list(range(len(lods))):
            raise ContractError("lod indices must be contiguous and start at zero")
        def optional_int(
            name: str, *, allow_zero: bool = True, allow_negative_one: bool = False
        ) -> int | None:
            value = raw.get(name)
            if value is None:
                return None
            if allow_negative_one and value == -1:
                return -1
            return _positive_int(value, name, allow_zero=allow_zero)

        collision_complexity = raw.get("collision_complexity")
        if collision_complexity is not None and (
            not isinstance(collision_complexity, str) or not collision_complexity.strip()
        ):
            raise ContractError("collision_complexity must be a non-empty string or null")
        def optional_paths(name: str) -> tuple[str, ...] | None:
            value = raw.get(name)
            if value is None:
                return None
            paths = _string_tuple(value, name, allow_empty=True)
            if paths != tuple(sorted(set(paths))):
                raise ContractError(f"{name} must be unique and sorted")
            return paths

        material_paths = optional_paths("material_paths")
        texture_paths = optional_paths("texture_paths")
        unique_material_count = optional_int("unique_material_count")
        texture_dependency_count = optional_int("texture_dependency_count")
        if material_paths is not None and unique_material_count != len(material_paths):
            raise ContractError("unique_material_count must match material_paths")
        if texture_paths is not None and texture_dependency_count != len(texture_paths):
            raise ContractError("texture_dependency_count must match texture_paths")
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
            simple_collision_primitive_count=optional_int(
                "simple_collision_primitive_count"
            ),
            collision_complexity=collision_complexity,
            uv_channel_count=optional_int("uv_channel_count"),
            lightmap_coordinate_index=optional_int(
                "lightmap_coordinate_index", allow_negative_one=True
            ),
            lightmap_resolution=optional_int("lightmap_resolution"),
            material_paths=material_paths,
            missing_material_slot_count=optional_int("missing_material_slot_count"),
            unique_material_count=unique_material_count,
            texture_paths=texture_paths,
            texture_dependency_count=texture_dependency_count,
            max_texture_dimension=optional_int("max_texture_dimension"),
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
        use_v3 = profile.schema_version == PROFILE_VERSION_V3 or any(
            asset.has_dependency_metadata for asset in assets
        )
        use_v2 = profile.schema_version in {PROFILE_VERSION_V2, PROFILE_VERSION_V3} or any(
            asset.has_extended_metadata for asset in assets
        )
        if use_v3 and any(not asset.has_dependency_metadata for asset in assets):
            raise ContractError("v3 reports require complete material and texture metadata")
        if use_v2 and any(not asset.has_extended_metadata for asset in assets):
            raise ContractError("v2 reports require complete collision and Lightmap metadata")
        return cls(
            schema_version=(
                CONTRACT_VERSION_V3
                if use_v3
                else CONTRACT_VERSION_V2 if use_v2 else CONTRACT_VERSION
            ),
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
        def drop_none(value: Any) -> Any:
            if isinstance(value, dict):
                return {key: drop_none(item) for key, item in value.items() if item is not None}
            if isinstance(value, list):
                return [drop_none(item) for item in value]
            return value

        return drop_none(asdict(self))

    def write(self, path: str | Path) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
