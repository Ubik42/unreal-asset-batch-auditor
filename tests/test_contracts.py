from __future__ import annotations

import json
from pathlib import Path

import pytest
from unreal_asset_batch_auditor.contracts import (
    AuditProfile,
    ContractError,
    Report,
)

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "config" / "Profiles" / "default-static-mesh-profile.v1.json"
PROFILE_V2 = ROOT / "config" / "Profiles" / "default-static-mesh-profile.v2.json"


def test_profile_loads_all_project_owned_thresholds() -> None:
    profile = AuditProfile.load(PROFILE)
    assert profile.triangle_budget.max_value == 50_000
    assert profile.vertex_budget.max_value == 35_000
    assert profile.material_slots.max_value == 4
    assert profile.lod_count.min_value == 3
    assert profile.nanite.expected == "enabled"


def test_profile_rejects_missing_threshold() -> None:
    raw = json.loads(PROFILE.read_text(encoding="utf-8"))
    del raw["rules"]["triangle_budget"]["max_lod0"]
    with pytest.raises(ContractError, match="max_lod0"):
        AuditProfile.from_dict(raw)


def test_profile_rejects_unknown_schema_version() -> None:
    raw = json.loads(PROFILE.read_text(encoding="utf-8"))
    raw["schema_version"] = "future@9"
    with pytest.raises(ContractError, match="unsupported"):
        AuditProfile.from_dict(raw)


def test_profile_rejects_string_boolean() -> None:
    raw = json.loads(PROFILE.read_text(encoding="utf-8"))
    raw["rules"]["nanite"]["enabled"] = "false"
    with pytest.raises(ContractError, match="boolean"):
        AuditProfile.from_dict(raw)


def test_v2_profile_loads_collision_and_lightmap_policy() -> None:
    profile = AuditProfile.load(PROFILE_V2)

    assert profile.schema_version == "unreal-static-mesh-profile@2.0.0"
    assert profile.simple_collision is not None
    assert profile.simple_collision.min_primitive_count == 1
    assert profile.simple_collision.allow_complex_as_simple is True
    assert profile.lightmap_uv is not None and profile.lightmap_uv.required is True
    assert profile.lightmap_uv.min_uv_channel_count == 2
    assert profile.lightmap_resolution is not None
    assert profile.lightmap_resolution.min_value == 32
    assert profile.object_name is not None
    assert profile.object_name.required_prefixes == ("SM_",)
    assert profile.package_path is not None
    assert profile.package_path.allowed_roots == ("/Game/Props",)


def test_v2_profile_rejects_missing_collision_policy() -> None:
    raw = json.loads(PROFILE_V2.read_text(encoding="utf-8"))
    del raw["rules"]["simple_collision"]
    with pytest.raises(ContractError, match="simple_collision"):
        AuditProfile.from_dict(raw)


def test_v2_profile_rejects_invalid_name_regex() -> None:
    raw = json.loads(PROFILE_V2.read_text(encoding="utf-8"))
    raw["rules"]["object_name"]["pattern"] = "[broken"
    with pytest.raises(ContractError, match="pattern is invalid"):
        AuditProfile.from_dict(raw)


def test_older_v2_profile_without_naming_policy_remains_readable() -> None:
    raw = json.loads(PROFILE_V2.read_text(encoding="utf-8"))
    del raw["rules"]["object_name"]
    del raw["rules"]["package_path"]
    profile = AuditProfile.from_dict(raw)
    assert profile.object_name is None
    assert profile.package_path is None


def test_offline_report_cannot_claim_real_unreal_validation() -> None:
    profile = AuditProfile.load(PROFILE)
    with pytest.raises(ContractError, match="cannot claim"):
        Report.create(
            report_id="bad",
            profile=profile,
            collection_mode="offline_fixture",
            real_unreal_validation=True,
            host_engine_version=None,
            assets=[],
            requested_asset_count=0,
            processed_asset_count=0,
            cancelled_asset_count=0,
            completed_batch_count=0,
            batch_size=None,
            issues=[],
            evidence=[],
            collection_failures=[],
        )


def test_report_rejects_inconsistent_execution_counts() -> None:
    profile = AuditProfile.load(PROFILE)
    with pytest.raises(ContractError, match="requested_asset_count"):
        Report.create(
            report_id="bad-counts",
            profile=profile,
            collection_mode="offline_fixture",
            real_unreal_validation=False,
            host_engine_version=None,
            assets=[],
            requested_asset_count=2,
            processed_asset_count=1,
            cancelled_asset_count=0,
            completed_batch_count=0,
            batch_size=1,
            issues=[],
            evidence=[],
            collection_failures=[],
        )
