from __future__ import annotations

import json
from pathlib import Path

from unreal_asset_batch_auditor import FixtureCollector, PanelAuditTask, request_panel_cancel

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "config" / "Profiles" / "default-static-mesh-profile.v2.json"
FIXTURE = ROOT / "tests" / "fixtures" / "static_meshes.v2.json"
PATHS = [
    "/Game/Props/SM_Healthy.SM_Healthy",
    "/Game/Props/SM_Problem.SM_Problem",
    "/Game/Props/SM_ComplexCollision.SM_ComplexCollision",
]


def _request(tmp_path: Path, *, batch_size: int) -> dict:
    return {
        "task_id": "task-test",
        "profile_path": str(PROFILE),
        "asset_paths": PATHS,
        "output_path": str(tmp_path / "latest-report.json"),
        "session_root": str(tmp_path / "Sessions"),
        "handoff_root": str(tmp_path / "Handoffs"),
        "state_path": str(tmp_path / "task-state.json"),
        "cancel_path": str(tmp_path / "cancel-request.json"),
        "batch_size": batch_size,
    }


def _state(task: PanelAuditTask) -> dict:
    return json.loads(task.state_path.read_text(encoding="utf-8"))


def test_panel_task_advances_one_batch_per_tick_and_exports_handoff(tmp_path: Path) -> None:
    task = PanelAuditTask(_request(tmp_path, batch_size=2), FixtureCollector(FIXTURE))

    assert _state(task)["state"] == "pending"
    assert task.tick() is False
    assert _state(task)["state"] == "running"
    assert task.tick() is False
    after_first_batch = _state(task)
    assert after_first_batch["processed_count"] == 2
    assert after_first_batch["completed_batch_count"] == 1
    assert after_first_batch["progress_fraction"] == 2 / 3
    assert after_first_batch["can_cancel"] is True
    assert task.tick() is True

    terminal = _state(task)
    assert terminal["state"] == "completed"
    assert terminal["processed_count"] == 3
    assert terminal["progress_fraction"] == 1.0
    report = json.loads(Path(terminal["report_path"]).read_text(encoding="utf-8"))
    assert report["processed_asset_count"] == 3
    assert report["cancelled_asset_count"] == 0
    handoff_root = Path(terminal["handoff_path"])
    assert (handoff_root / "审计交接报告.html").exists()
    assert (handoff_root / "审计问题明细.csv").exists()
    assert (handoff_root / "交接清单.json").exists()


def test_panel_task_cancels_between_batches_and_preserves_partial_report(
    tmp_path: Path,
) -> None:
    task = PanelAuditTask(_request(tmp_path, batch_size=1), FixtureCollector(FIXTURE))
    task.tick()  # pending -> running
    task.tick()  # first batch
    request_panel_cancel(str(task.cancel_path))

    assert task.tick() is False
    cancelling = _state(task)
    assert cancelling["state"] == "cancelling"
    assert cancelling["processed_count"] == 1
    assert cancelling["can_cancel"] is False
    assert task.tick() is True

    terminal = _state(task)
    assert terminal["state"] == "cancelled"
    assert terminal["processed_count"] == 1
    assert terminal["cancelled_count"] == 2
    report = json.loads(Path(terminal["report_path"]).read_text(encoding="utf-8"))
    assert report["processed_asset_count"] == 1
    assert report["cancelled_asset_count"] == 2
    comparison = json.loads(
        (tmp_path / "Sessions" / "latest-comparison.v1.json").read_text(encoding="utf-8")
    )
    assert comparison["status"] == "incomplete_current"
    assert "不参与完整回归比较" in comparison["message"]


def test_panel_task_failure_is_localized_and_terminal(tmp_path: Path) -> None:
    class BrokenCollector(FixtureCollector):
        def collect(self, asset_paths=None):  # type: ignore[no-untyped-def]
            raise RuntimeError("synthetic collector failure")

    task = PanelAuditTask(_request(tmp_path, batch_size=2), BrokenCollector(FIXTURE))
    task.tick()

    assert task.tick() is True
    terminal = _state(task)
    assert terminal["state"] == "failed"
    assert terminal["error_code"] == "RuntimeError"
    assert terminal["error_message"] == "synthetic collector failure"
    assert "资产未被修改" in terminal["message"]
    assert not (tmp_path / "latest-report.json").exists()
