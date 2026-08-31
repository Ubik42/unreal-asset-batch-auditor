from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from unreal_asset_batch_auditor import (
    EXIT_COLLECTION_FAILED,
    EXIT_CONFIG_ERROR,
    EXIT_PASSED,
    EXIT_POLICY_FAILED,
    CollectionBatch,
    CollectionFailure,
    FixtureCollector,
    ProjectPreset,
    StaticMeshMetadata,
    resolve_asset_paths,
    run_project_preset,
)

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "config" / "Profiles" / "default-static-mesh-profile.v3.json"
FIXTURE = ROOT / "tests" / "fixtures" / "static_meshes.v3.json"


def _write_preset(tmp_path: Path, *, asset_paths: list[str], folder_paths: list[str]) -> Path:
    path = tmp_path / "project-preset.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "unreal-asset-audit-preset@1.0.0",
                "preset_id": "test-project-v1",
                "description": "测试项目显式范围",
                "profile_path": str(PROFILE),
                "scope": {"asset_paths": asset_paths, "folder_paths": folder_paths},
                "batch_size": 8,
                "gate": {"blocking_severities": ["error", "warning"]},
                "output": {
                    "report_path": "Saved/Audit/report.json",
                    "summary_path": "Saved/Audit/summary.json",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def test_project_preset_requires_an_explicit_non_wildcard_scope(tmp_path: Path) -> None:
    empty = _write_preset(tmp_path, asset_paths=[], folder_paths=[])
    result = run_project_preset(
        empty,
        project_root=tmp_path,
        collector=FixtureCollector(FIXTURE),
        summary_override=tmp_path / "empty-summary.json",
    )
    assert result["exit_code"] == EXIT_CONFIG_ERROR
    assert "范围为空" in result["message"]

    wildcard = _write_preset(
        tmp_path,
        asset_paths=[],
        folder_paths=["/Game/**"],
    )
    result = run_project_preset(
        wildcard,
        project_root=tmp_path,
        collector=FixtureCollector(FIXTURE),
        summary_override=tmp_path / "wildcard-summary.json",
    )
    assert result["exit_code"] == EXIT_CONFIG_ERROR
    assert "通配符" in result["message"]


def test_scope_merges_explicit_assets_and_folders_with_stable_deduplication(
    tmp_path: Path,
) -> None:
    preset = ProjectPreset.load(
        _write_preset(
            tmp_path,
            asset_paths=["/Game/Props/SM_Healthy.SM_Healthy"],
            folder_paths=["/Game/Props"],
        )
    )
    assert resolve_asset_paths(
        preset,
        lambda _: [
            "/Game/Props/SM_MaterialRisk.SM_MaterialRisk",
            "/Game/Props/SM_Healthy.SM_Healthy",
        ],
    ) == [
        "/Game/Props/SM_Healthy.SM_Healthy",
        "/Game/Props/SM_MaterialRisk.SM_MaterialRisk",
    ]


def test_unattended_pass_and_policy_exit_codes_write_report_and_summary(tmp_path: Path) -> None:
    healthy = _write_preset(
        tmp_path,
        asset_paths=["/Game/Props/SM_Healthy.SM_Healthy"],
        folder_paths=[],
    )
    result = run_project_preset(
        healthy,
        project_root=tmp_path,
        collector=FixtureCollector(FIXTURE),
    )
    assert result["exit_code"] == EXIT_PASSED
    assert result["status"] == "passed"
    assert (tmp_path / "Saved/Audit/report.json").is_file()
    assert (tmp_path / "Saved/Audit/summary.json").is_file()

    risky = _write_preset(
        tmp_path,
        asset_paths=["/Game/Props/SM_MaterialRisk.SM_MaterialRisk"],
        folder_paths=[],
    )
    result = run_project_preset(
        risky,
        project_root=tmp_path,
        collector=FixtureCollector(FIXTURE),
    )
    assert result["exit_code"] == EXIT_POLICY_FAILED
    assert result["status"] == "policy_failed"
    assert result["blocking_issue_count"] == 5


def test_collection_failure_has_a_distinct_exit_code(tmp_path: Path) -> None:
    healthy = StaticMeshMetadata.from_dict(
        json.loads(FIXTURE.read_text(encoding="utf-8"))["assets"][0]
    )

    class FailingCollector:
        mode = "unreal_editor"
        real_unreal_validation = True
        host_engine_version = "test-host"

        def collect(self, asset_paths=None):  # type: ignore[no-untyped-def]
            return CollectionBatch(
                assets=[replace(healthy, asset_path=asset_paths[0])],
                failures=[
                    CollectionFailure(
                        schema_version="unreal-asset-audit@1.0.0",
                        asset_path=asset_paths[1],
                        code="LOAD_FAILED",
                        message="fixture failure",
                        collector=self.mode,
                    )
                ],
            )

    preset = _write_preset(
        tmp_path,
        asset_paths=[
            "/Game/Props/SM_Healthy.SM_Healthy",
            "/Game/Props/SM_Broken.SM_Broken",
        ],
        folder_paths=[],
    )
    result = run_project_preset(
        preset,
        project_root=tmp_path,
        collector=FailingCollector(),
    )
    assert result["exit_code"] == EXIT_COLLECTION_FAILED
    assert result["collection_failure_count"] == 1


def test_missing_profile_writes_config_error_to_override_path(tmp_path: Path) -> None:
    preset_path = _write_preset(
        tmp_path,
        asset_paths=["/Game/Props/SM_Healthy.SM_Healthy"],
        folder_paths=[],
    )
    raw = json.loads(preset_path.read_text(encoding="utf-8"))
    raw["profile_path"] = "missing-profile.json"
    preset_path.write_text(json.dumps(raw), encoding="utf-8")
    summary_path = tmp_path / "fallback" / "summary.json"
    result = run_project_preset(
        preset_path,
        project_root=tmp_path,
        collector=FixtureCollector(FIXTURE),
        summary_override=summary_path,
    )
    assert result["exit_code"] == EXIT_CONFIG_ERROR
    assert "Profile 不存在" in result["message"]
    assert json.loads(summary_path.read_text(encoding="utf-8"))["exit_code"] == 30
