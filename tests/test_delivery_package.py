from __future__ import annotations

import json
from pathlib import Path

import pytest
from unreal_asset_batch_auditor import (
    DeliveryPackageRecipe,
    FixtureCollector,
    IgnoredPackageAsset,
    MaterialFixtureCollector,
    PanelDeliveryPackageTask,
    TextureFixtureCollector,
    audit_delivery_package,
    build_delivery_package_summary,
)
from unreal_asset_batch_auditor.contracts import ContractError

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "Resources" / "DeliveryRecipes" / "desktop-delivery-balanced.v1.json"


def _offline_package(tmp_path: Path):
    recipe = DeliveryPackageRecipe.load(RECIPE)
    lanes = {
        "static_mesh": ["/Game/Props/SM_Healthy.SM_Healthy"],
        "texture2d": ["/Game/Textures/T_Good_BaseColor.T_Good_BaseColor"],
        "material_interface": ["/Game/Materials/M_Prop_Master.M_Prop_Master"],
    }
    collectors = {
        "static_mesh": FixtureCollector(ROOT / "tests/fixtures/static_meshes.v3.json"),
        "texture2d": TextureFixtureCollector(ROOT / "tests/fixtures/textures.v1.json"),
        "material_interface": MaterialFixtureCollector(
            ROOT / "tests/fixtures/materials.v1.json"
        ),
    }
    summary = audit_delivery_package(
        recipe=recipe,
        lane_asset_paths=lanes,  # type: ignore[arg-type]
        output_root=tmp_path / "reports",
        summary_path=tmp_path / "summary.json",
        ignored_assets=[
            IgnoredPackageAsset(
                asset_path="/Game/Maps/Demo.Demo",
                asset_class="World",
                reason="当前总检只接收模型、纹理和材质接口",
            )
        ],
        batch_size=2,
        collectors=collectors,  # type: ignore[arg-type]
    )
    return recipe, summary


def test_recipe_resolves_three_independent_profiles() -> None:
    recipe = DeliveryPackageRecipe.load(RECIPE)

    assert recipe.recipe_id == "desktop-delivery-balanced-v1"
    assert list(recipe.profile_paths) == [
        "static_mesh",
        "texture2d",
        "material_interface",
    ]
    assert all(Path(path).is_file() for path in recipe.profile_paths.values())
    assert len(set(recipe.profile_paths.values())) == 3


def test_offline_package_keeps_lane_reports_and_ignored_scope(tmp_path: Path) -> None:
    _, summary = _offline_package(tmp_path)
    raw = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))

    assert summary.status == "completed"
    assert summary.real_unreal_validation is False
    assert summary.selected_count == 4
    assert summary.supported_count == 3
    assert summary.ignored_count == 1
    assert summary.processed_count == 3
    assert [lane.asset_type for lane in summary.lanes] == [
        "static_mesh",
        "texture2d",
        "material_interface",
    ]
    assert all(lane.state == "completed" for lane in summary.lanes)
    assert all(lane.report_path for lane in summary.lanes)
    assert raw["schema_version"] == "unreal-delivery-package-summary@1.0.0"
    assert raw["ignored_assets"][0]["asset_class"] == "World"


def test_package_run_id_is_stable_for_the_same_reports(tmp_path: Path) -> None:
    recipe, first = _offline_package(tmp_path)
    reports = {
        lane.asset_type: lane.report_path
        for lane in first.lanes
        if lane.report_path is not None
    }
    second = build_delivery_package_summary(
        recipe=recipe,
        report_paths=reports,  # type: ignore[arg-type]
        requested_counts={
            "static_mesh": 1,
            "texture2d": 1,
            "material_interface": 1,
        },
        ignored_assets=first.ignored_assets,
    )

    assert second.package_run_id == first.package_run_id


def test_single_lane_failure_produces_legal_partial_summary(tmp_path: Path) -> None:
    recipe, first = _offline_package(tmp_path)
    model_report = next(
        lane.report_path
        for lane in first.lanes
        if lane.asset_type == "static_mesh"
    )

    partial = build_delivery_package_summary(
        recipe=recipe,
        report_paths={"static_mesh": model_report},  # type: ignore[arg-type]
        requested_counts={
            "static_mesh": 1,
            "texture2d": 2,
            "material_interface": 0,
        },
        lane_errors={
            "texture2d": ("COLLECTOR_UNAVAILABLE", "纹理采集接口未就绪")
        },  # type: ignore[arg-type]
    )

    assert partial.status == "partial"
    assert partial.decision == "blocked"
    assert [lane.state for lane in partial.lanes] == [
        "completed",
        "failed",
        "skipped",
    ]
    assert partial.lanes[1].requested_count == 2
    assert partial.lanes[1].error_code == "COLLECTOR_UNAVAILABLE"


def test_cancelled_lane_does_not_claim_completed_package(tmp_path: Path) -> None:
    recipe, first = _offline_package(tmp_path)
    texture_path = Path(
        next(
            lane.report_path
            for lane in first.lanes
            if lane.asset_type == "texture2d"
        )
    )
    cancelled_report = json.loads(texture_path.read_text(encoding="utf-8"))
    cancelled_report["requested_asset_count"] = 2
    cancelled_report["processed_asset_count"] = 1
    cancelled_report["cancelled_asset_count"] = 1
    texture_path.write_text(
        json.dumps(cancelled_report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    summary = build_delivery_package_summary(
        recipe=recipe,
        report_paths={"texture2d": str(texture_path)},  # type: ignore[arg-type]
        requested_counts={
            "static_mesh": 0,
            "texture2d": 2,
            "material_interface": 0,
        },
    )

    assert summary.status == "cancelled"
    assert summary.processed_count == 1
    assert summary.cancelled_count == 1
    assert summary.lanes[1].state == "cancelled"


def test_recipe_rejects_missing_lane_profile(tmp_path: Path) -> None:
    invalid = json.loads(RECIPE.read_text(encoding="utf-8"))
    invalid["profiles"].pop("material_interface")
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(invalid), encoding="utf-8")

    with pytest.raises(ContractError, match="must map"):
        DeliveryPackageRecipe.load(path)


def _panel_request(tmp_path: Path) -> dict:
    return {
        "task_id": "package-task-test",
        "recipe_path": str(RECIPE),
        "lanes": {
            "static_mesh": ["/Game/Props/SM_Healthy.SM_Healthy"],
            "texture2d": ["/Game/Textures/T_Good_BaseColor.T_Good_BaseColor"],
            "material_interface": ["/Game/Materials/M_Prop_Master.M_Prop_Master"],
        },
        "ignored_assets": [],
        "batch_size": 1,
        "output_path": str(tmp_path / "latest-package-summary.json"),
        "reports_root": str(tmp_path / "reports"),
        "task_root": str(tmp_path / "tasks"),
        "handoff_root": str(tmp_path / "handoffs"),
        "session_root": str(tmp_path / "sessions"),
        "state_path": str(tmp_path / "task-state.json"),
        "cancel_path": str(tmp_path / "cancel.json"),
    }


def _fixture_factories():
    return {
        "static_mesh": lambda: FixtureCollector(
            ROOT / "tests/fixtures/static_meshes.v3.json"
        ),
        "texture2d": lambda: TextureFixtureCollector(
            ROOT / "tests/fixtures/textures.v1.json"
        ),
        "material_interface": lambda: MaterialFixtureCollector(
            ROOT / "tests/fixtures/materials.v1.json"
        ),
    }


def test_panel_package_task_advances_three_lanes_without_merging_reports(
    tmp_path: Path,
) -> None:
    task = PanelDeliveryPackageTask(
        _panel_request(tmp_path), _fixture_factories()  # type: ignore[arg-type]
    )

    for _ in range(20):
        if task.tick():
            break

    assert task.state == "completed"
    summary = json.loads(
        (tmp_path / "latest-package-summary.json").read_text(encoding="utf-8")
    )
    assert summary["processed_count"] == 3
    assert [lane["state"] for lane in summary["lanes"]] == [
        "completed",
        "completed",
        "completed",
    ]
    assert sorted(path.name for path in (tmp_path / "reports").iterdir()) == [
        "material_interface-report.json",
        "static_mesh-report.json",
        "texture2d-report.json",
    ]


def test_panel_package_cancel_preserves_legal_partial_summary(tmp_path: Path) -> None:
    request = _panel_request(tmp_path)
    task = PanelDeliveryPackageTask(
        request, _fixture_factories()  # type: ignore[arg-type]
    )
    assert task.tick() is False
    Path(request["cancel_path"]).write_text("{}", encoding="utf-8")

    for _ in range(10):
        if task.tick():
            break

    summary = json.loads(
        (tmp_path / "latest-package-summary.json").read_text(encoding="utf-8")
    )
    assert task.state == "cancelled"
    assert summary["status"] == "cancelled"
    assert summary["processed_count"] == 0
    assert summary["cancelled_count"] == 3
