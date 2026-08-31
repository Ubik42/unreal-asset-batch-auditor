from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from .contracts import (
    CONTRACT_VERSION,
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

TEXTURE_PROFILE_VERSION = "unreal-texture-profile@1.0.0"
TEXTURE_REPORT_VERSION = "unreal-texture-audit@1.0.0"
TEXTURE_FIXTURE_VERSION = "unreal-texture-fixture@1.0.0"


@dataclass(frozen=True)
class TextureDimensionRule:
    enabled: bool
    max_size: int
    severity: Severity


@dataclass(frozen=True)
class TextureBooleanRule:
    enabled: bool
    required: bool
    severity: Severity


@dataclass(frozen=True)
class TextureMinimumRule:
    enabled: bool
    min_count: int
    severity: Severity


@dataclass(frozen=True)
class TextureAllowedValuesRule:
    enabled: bool
    allowed_values: tuple[str, ...]
    severity: Severity


@dataclass(frozen=True)
class TextureStateRule:
    enabled: bool
    expected: Literal["enabled", "disabled", "any"]
    severity: Severity


@dataclass(frozen=True)
class CompressionColorSpace:
    compression: str
    srgb: bool


@dataclass(frozen=True)
class TextureCompressionColorRule:
    enabled: bool
    allowed_combinations: tuple[CompressionColorSpace, ...]
    severity: Severity


@dataclass(frozen=True)
class TextureAuditProfile:
    schema_version: str
    profile_id: str
    profile_version: str
    description: str
    source_dimension: TextureDimensionRule
    power_of_two: TextureBooleanRule
    mip_count: TextureMinimumRule
    texture_group: TextureAllowedValuesRule
    compression_color_space: TextureCompressionColorRule
    virtual_texture: TextureStateRule
    streaming: TextureStateRule

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> TextureAuditProfile:
        if _required(raw, "schema_version") != TEXTURE_PROFILE_VERSION:
            raise ContractError("unsupported texture profile schema_version")
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

        dimension = item("source_dimension")
        power_of_two = item("power_of_two")
        mip_count = item("mip_count")
        texture_group = item("texture_group")
        compression = item("compression_color_space")
        combinations = _required(compression, "allowed_combinations")
        if not isinstance(combinations, list) or not combinations:
            raise ContractError(
                "rules.compression_color_space.allowed_combinations must be non-empty"
            )
        parsed_combinations: list[CompressionColorSpace] = []
        for index, value in enumerate(combinations):
            if not isinstance(value, dict):
                raise ContractError(
                    "rules.compression_color_space.allowed_combinations must contain objects"
                )
            compression_name = _required(value, "compression")
            if not isinstance(compression_name, str) or not compression_name.strip():
                raise ContractError(
                    f"rules.compression_color_space.allowed_combinations[{index}].compression "
                    "must be non-empty"
                )
            parsed_combinations.append(
                CompressionColorSpace(
                    compression=compression_name,
                    srgb=_boolean(
                        _required(value, "srgb"),
                        f"rules.compression_color_space.allowed_combinations[{index}].srgb",
                    ),
                )
            )
        if len(set(parsed_combinations)) != len(parsed_combinations):
            raise ContractError("compression/sRGB combinations must be unique")

        def state(name: str) -> TextureStateRule:
            value = item(name)
            expected = _required(value, "expected")
            if expected not in {"enabled", "disabled", "any"}:
                raise ContractError(f"rules.{name}.expected must be enabled, disabled, or any")
            return TextureStateRule(
                enabled=_boolean(_required(value, "enabled"), f"rules.{name}.enabled"),
                expected=expected,
                severity=_severity(_required(value, "severity"), f"rules.{name}.severity"),
            )

        return cls(
            schema_version=TEXTURE_PROFILE_VERSION,
            profile_id=profile_id,
            profile_version=profile_version,
            description=str(raw.get("description", "")),
            source_dimension=TextureDimensionRule(
                enabled=_boolean(
                    _required(dimension, "enabled"), "rules.source_dimension.enabled"
                ),
                max_size=_positive_int(
                    _required(dimension, "max_size"), "rules.source_dimension.max_size"
                ),
                severity=_severity(
                    _required(dimension, "severity"), "rules.source_dimension.severity"
                ),
            ),
            power_of_two=TextureBooleanRule(
                enabled=_boolean(
                    _required(power_of_two, "enabled"), "rules.power_of_two.enabled"
                ),
                required=_boolean(
                    _required(power_of_two, "required"), "rules.power_of_two.required"
                ),
                severity=_severity(
                    _required(power_of_two, "severity"), "rules.power_of_two.severity"
                ),
            ),
            mip_count=TextureMinimumRule(
                enabled=_boolean(_required(mip_count, "enabled"), "rules.mip_count.enabled"),
                min_count=_positive_int(
                    _required(mip_count, "min_count"), "rules.mip_count.min_count"
                ),
                severity=_severity(
                    _required(mip_count, "severity"), "rules.mip_count.severity"
                ),
            ),
            texture_group=TextureAllowedValuesRule(
                enabled=_boolean(
                    _required(texture_group, "enabled"), "rules.texture_group.enabled"
                ),
                allowed_values=_string_tuple(
                    _required(texture_group, "allowed_values"),
                    "rules.texture_group.allowed_values",
                ),
                severity=_severity(
                    _required(texture_group, "severity"), "rules.texture_group.severity"
                ),
            ),
            compression_color_space=TextureCompressionColorRule(
                enabled=_boolean(
                    _required(compression, "enabled"),
                    "rules.compression_color_space.enabled",
                ),
                allowed_combinations=tuple(parsed_combinations),
                severity=_severity(
                    _required(compression, "severity"),
                    "rules.compression_color_space.severity",
                ),
            ),
            virtual_texture=state("virtual_texture"),
            streaming=state("streaming"),
        )

    @classmethod
    def load(cls, path: str | Path) -> TextureAuditProfile:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


@dataclass(frozen=True)
class Texture2DMetadata:
    asset_path: str
    asset_name: str
    source_width: int
    source_height: int
    platform_width: int
    platform_height: int
    mip_count: int
    mip_gen_settings: str
    texture_group: str
    compression_settings: str
    srgb: bool
    virtual_texture_streaming: bool
    never_stream: bool

    @property
    def source_is_power_of_two(self) -> bool:
        return all(value > 0 and value & (value - 1) == 0 for value in self.source_size)

    @property
    def source_size(self) -> tuple[int, int]:
        return self.source_width, self.source_height

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Texture2DMetadata:
        def text(name: str) -> str:
            value = _required(raw, name)
            if not isinstance(value, str) or not value.strip():
                raise ContractError(f"{name} must be a non-empty string")
            return value

        return cls(
            asset_path=text("asset_path"),
            asset_name=text("asset_name"),
            source_width=_positive_int(_required(raw, "source_width"), "source_width"),
            source_height=_positive_int(_required(raw, "source_height"), "source_height"),
            platform_width=_positive_int(
                _required(raw, "platform_width"), "platform_width"
            ),
            platform_height=_positive_int(
                _required(raw, "platform_height"), "platform_height"
            ),
            mip_count=_positive_int(_required(raw, "mip_count"), "mip_count"),
            mip_gen_settings=text("mip_gen_settings"),
            texture_group=text("texture_group"),
            compression_settings=text("compression_settings"),
            srgb=_boolean(_required(raw, "srgb"), "srgb"),
            virtual_texture_streaming=_boolean(
                _required(raw, "virtual_texture_streaming"),
                "virtual_texture_streaming",
            ),
            never_stream=_boolean(_required(raw, "never_stream"), "never_stream"),
        )


@dataclass
class TextureAuditReport:
    schema_version: str
    report_id: str
    created_at: str
    profile_id: str
    profile_version: str
    profile_schema_version: str
    asset_type: Literal["texture2d"]
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
    assets: list[Texture2DMetadata] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    collection_failures: list[CollectionFailure] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        *,
        report_id: str,
        profile: TextureAuditProfile,
        collection_mode: Literal["offline_fixture", "unreal_editor"],
        real_unreal_validation: bool,
        host_engine_version: str | None,
        assets: list[Texture2DMetadata],
        requested_asset_count: int,
        processed_asset_count: int,
        cancelled_asset_count: int,
        completed_batch_count: int,
        batch_size: int | None,
        issues: list[Issue],
        evidence: list[Evidence],
        collection_failures: list[CollectionFailure],
    ) -> TextureAuditReport:
        if collection_mode == "offline_fixture" and real_unreal_validation:
            raise ContractError("offline fixture cannot claim real Unreal validation")
        if real_unreal_validation and not host_engine_version:
            raise ContractError("real Unreal validation requires host_engine_version")
        if processed_asset_count != len(assets) + len(collection_failures):
            raise ContractError("processed count must equal collected assets plus failures")
        if requested_asset_count != processed_asset_count + cancelled_asset_count:
            raise ContractError("requested count must equal processed plus cancelled")
        return cls(
            schema_version=TEXTURE_REPORT_VERSION,
            report_id=report_id,
            created_at=datetime.now(UTC).isoformat(),
            profile_id=profile.profile_id,
            profile_version=profile.profile_version,
            profile_schema_version=profile.schema_version,
            asset_type="texture2d",
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
    "CONTRACT_VERSION",
    "TEXTURE_FIXTURE_VERSION",
    "TEXTURE_PROFILE_VERSION",
    "TEXTURE_REPORT_VERSION",
    "CompressionColorSpace",
    "Texture2DMetadata",
    "TextureAuditProfile",
    "TextureAuditReport",
]
