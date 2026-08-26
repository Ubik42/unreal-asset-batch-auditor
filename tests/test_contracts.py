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
