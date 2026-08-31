from __future__ import annotations

import json
from pathlib import Path

import pytest
from unreal_asset_batch_auditor import (
    Texture2DMetadata,
    TextureAuditProfile,
    TextureFixtureCollector,
    TextureUnrealCppCollector,
    audit_textures,
)
from unreal_asset_batch_auditor.contracts import ContractError
from unreal_asset_batch_auditor.panel_task import PanelAuditTask

ROOT = Path(__file__).parents[1]
PROFILE = ROOT / "Resources/Profiles/texture-desktop-balanced.v1.json"
FIXTURE = ROOT / "tests/fixtures/textures.v1.json"


def test_texture_profile_and_metadata_are_versioned_and_strict() -> None:
    profile = TextureAuditProfile.load(PROFILE)
    assert profile.profile_id == "texture-desktop-balanced-v1"
    assert profile.source_dimension.max_size == 4096
    assert ("TC_Normalmap", False) in {
        (item.compression, item.srgb)
        for item in profile.compression_color_space.allowed_combinations
    }

    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))["assets"][0]
    texture = Texture2DMetadata.from_dict(raw)
    assert texture.source_is_power_of_two is True
    with pytest.raises(ContractError, match="source_width"):
        Texture2DMetadata.from_dict({**raw, "source_width": 0})


def test_texture_audit_covers_good_oversize_npot_mips_group_color_and_streaming() -> None:
    report = audit_textures(
        profile=TextureAuditProfile.load(PROFILE),
        collector=TextureFixtureCollector(FIXTURE),
        report_id_factory=lambda: "texture-fixture-report",
    )

    assert report.schema_version == "unreal-texture-audit@1.0.0"
    assert report.asset_type == "texture2d"
    assert report.real_unreal_validation is False
    assert report.asset_count == 3
    issue_keys = {(issue.asset_path, issue.rule_id) for issue in report.issues}
    assert not any(path.endswith("T_Good_BaseColor.T_Good_BaseColor") for path, _ in issue_keys)
    assert any(rule == "texture2d.source_dimension" for _, rule in issue_keys)
    npot_rules = {
        rule for path, rule in issue_keys if path.endswith("T_NPOT_Mask.T_NPOT_Mask")
    }
    assert npot_rules == {
        "texture2d.power_of_two",
        "texture2d.mip_count",
        "texture2d.texture_group",
        "texture2d.compression_color_space",
        "texture2d.streaming",
    }
    assert {proof.profile_pointer for proof in report.evidence} >= {
        "/rules/source_dimension/max_size",
        "/rules/power_of_two/required",
        "/rules/mip_count/min_count",
    }


def test_texture_audit_is_deterministic_except_timestamp() -> None:
    kwargs = {
        "profile": TextureAuditProfile.load(PROFILE),
        "collector": TextureFixtureCollector(FIXTURE),
        "asset_paths": [
            "/Game/Textures/T_NPOT_Mask.T_NPOT_Mask",
            "/Game/Textures/T_Good_BaseColor.T_Good_BaseColor",
        ],
        "batch_size": 1,
    }
    first = audit_textures(**kwargs).to_dict()
    second = audit_textures(**kwargs).to_dict()
    first.pop("created_at")
    second.pop("created_at")
    assert first == second
    assert first["completed_batch_count"] == 2


class _TextureRow:
    asset_path = "/Game/T.T"
    asset_name = "T"
    source_width = 1024
    source_height = 512
    platform_width = 1024
    platform_height = 512
    mip_count = 11
    mip_gen_settings = "TMGS_FromTextureGroup"
    texture_group = "TEXTUREGROUP_World"
    compression_settings = "TC_Default"
    srgb = True
    virtual_texture_streaming = False
    never_stream = False
    collected = True


class _Library:
    @staticmethod
    def collect_texture2d_metadata(paths: list[str]) -> list[_TextureRow]:
        assert paths == ["/Game/T.T"]
        return [_TextureRow()]


class _SystemLibrary:
    @staticmethod
    def get_engine_version() -> str:
        return "5.8.1-test"


class _Unreal:
    UnrealAssetBatchAuditorLibrary = _Library
    SystemLibrary = _SystemLibrary


def test_texture_cpp_adapter_maps_host_rows_without_mutation_api() -> None:
    collector = TextureUnrealCppCollector(_Unreal())
    batch = collector.collect(["/Game/T.T"])
    assert collector.real_unreal_validation is True
    assert batch.assets[0].source_size == (1024, 512)
    assert batch.assets[0].compression_settings == "TC_Default"
    assert batch.failures == []


def test_panel_task_routes_texture_request_to_texture_report(tmp_path: Path) -> None:
    request = {
        "asset_type": "texture2d",
        "task_id": "texture-panel-task",
        "profile_path": str(PROFILE),
        "asset_paths": [
            "/Game/Textures/T_Good_BaseColor.T_Good_BaseColor",
            "/Game/Textures/T_NPOT_Mask.T_NPOT_Mask",
        ],
        "batch_size": 1,
        "output_path": str(tmp_path / "report.json"),
        "session_root": str(tmp_path / "Sessions"),
        "handoff_root": str(tmp_path / "Handoffs"),
        "state_path": str(tmp_path / "task-state.json"),
        "cancel_path": str(tmp_path / "cancel.json"),
    }
    task = PanelAuditTask(request, TextureFixtureCollector(FIXTURE))
    while not task.tick():
        pass

    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["asset_type"] == "texture2d"
    assert report["asset_count"] == 2
    assert (tmp_path / "Handoffs" / report["report_id"] / "交付目录热区.csv").exists()
