from __future__ import annotations

import json
import math
import traceback
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .collectors import MetadataCollector, UnrealCppCollector
from .delivery_package import (
    ASSET_TYPES,
    AssetType,
    DeliveryPackageRecipe,
    IgnoredPackageAsset,
    build_delivery_package_summary,
)
from .material_collectors import MaterialUnrealCppCollector
from .panel_task import TASK_STATE_VERSION, PanelAuditTask
from .texture_collectors import TextureUnrealCppCollector


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


class PanelDeliveryPackageTask:
    """Advance one child audit batch per Slate tick across three independent lanes."""

    def __init__(
        self,
        request: dict[str, Any],
        collector_factories: dict[AssetType, Callable[[], MetadataCollector]],
    ) -> None:
        self.request = request
        self.recipe = DeliveryPackageRecipe.load(str(request["recipe_path"]))
        self.task_id = str(request["task_id"])
        raw_lanes = request.get("lanes")
        if not isinstance(raw_lanes, dict):
            raise TypeError("lanes must be an object")
        self.lane_paths: dict[AssetType, list[str]] = {}
        for asset_type in ASSET_TYPES:
            raw_paths = raw_lanes.get(asset_type, [])
            if not isinstance(raw_paths, list) or any(
                not isinstance(path, str) or not path.strip() for path in raw_paths
            ):
                raise ValueError(f"lanes.{asset_type} must be an array of paths")
            self.lane_paths[asset_type] = sorted(dict.fromkeys(raw_paths))  # type: ignore[index]
        raw_ignored = request.get("ignored_assets", [])
        if not isinstance(raw_ignored, list):
            raise TypeError("ignored_assets must be an array")
        self.ignored_assets = [IgnoredPackageAsset.from_dict(item) for item in raw_ignored]
        self.batch_size = int(request.get("batch_size", 64))
        if self.batch_size < 1:
            raise ValueError("batch_size must be a positive integer")
        self.output_path = Path(str(request["output_path"]))
        self.reports_root = Path(str(request["reports_root"]))
        self.task_root = Path(str(request["task_root"]))
        self.handoff_root = Path(str(request["handoff_root"]))
        self.session_root = Path(str(request["session_root"]))
        self.state_path = Path(str(request["state_path"]))
        self.cancel_path = Path(str(request["cancel_path"]))
        self.collector_factories = collector_factories
        self.report_paths: dict[AssetType, str] = {}
        self.lane_errors: dict[AssetType, tuple[str, str]] = {}
        self.cancelled_lanes: set[AssetType] = set()
        self.lane_index = -1
        self.active_lane: AssetType | None = None
        self.active_child: PanelAuditTask | None = None
        self.started_at = _utc_now()
        self.state = "pending"
        self.last_state = self._state_payload(
            "交付包已建立，等待模型、纹理、材质三条泳道", can_cancel=True
        )
        self._write_state(self.last_state)

    @property
    def is_terminal(self) -> bool:
        return self.state in {"completed", "cancelled", "failed"}

    def _requested_count(self) -> int:
        return sum(len(paths) for paths in self.lane_paths.values())

    def _processed_count(self) -> int:
        completed = 0
        for asset_type, report_path in self.report_paths.items():
            try:
                raw = json.loads(Path(report_path).read_text(encoding="utf-8"))
                completed += int(raw.get("processed_asset_count", 0))
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                if asset_type != self.active_lane:
                    continue
        if self.active_child and self.active_lane not in self.report_paths:
            completed += self.active_child.processed_count
        return completed

    def _completed_batches(self) -> int:
        completed = 0
        for report_path in self.report_paths.values():
            try:
                raw = json.loads(Path(report_path).read_text(encoding="utf-8"))
                completed += int(raw.get("completed_batch_count", 0))
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                continue
        if self.active_child and self.active_lane not in self.report_paths:
            completed += self.active_child.completed_batch_count
        return completed

    def _total_batches(self) -> int:
        return sum(
            math.ceil(len(paths) / self.batch_size) if paths else 0
            for paths in self.lane_paths.values()
        )

    def _state_payload(self, message: str, *, can_cancel: bool) -> dict[str, Any]:
        requested = self._requested_count()
        processed = self._processed_count()
        return {
            "schema_version": TASK_STATE_VERSION,
            "task_id": self.task_id,
            "task_kind": "delivery_package",
            "state": self.state,
            "message": message,
            "can_cancel": can_cancel,
            "started_at": self.started_at,
            "updated_at": _utc_now(),
            "requested_count": requested,
            "processed_count": processed,
            "collected_count": processed,
            "failed_count": len(self.lane_errors),
            "cancelled_count": requested - processed if self.state == "cancelled" else 0,
            "completed_batch_count": self._completed_batches(),
            "total_batch_count": self._total_batches(),
            "progress_fraction": processed / requested if requested else 1.0,
            "active_lane": self.active_lane,
            "completed_lanes": sorted(self.report_paths),
            "failed_lanes": sorted(self.lane_errors),
        }

    def _write_state(self, payload: dict[str, Any]) -> None:
        _atomic_json(self.state_path, payload)
        self.last_state = payload

    def _start_next_lane(self) -> bool:
        self.active_child = None
        self.active_lane = None
        while self.lane_index + 1 < len(ASSET_TYPES):
            self.lane_index += 1
            asset_type: AssetType = ASSET_TYPES[self.lane_index]  # type: ignore[assignment]
            paths = self.lane_paths[asset_type]
            if not paths:
                continue
            self.active_lane = asset_type
            lane_root = self.task_root / asset_type
            child_request = {
                "task_id": f"{self.task_id}-{asset_type}",
                "asset_type": asset_type,
                "profile_path": self.recipe.profile_paths[asset_type],
                "asset_paths": paths,
                "batch_size": self.batch_size,
                "output_path": str(self.reports_root / f"{asset_type}-report.json"),
                "session_root": str(self.session_root / asset_type),
                "handoff_root": str(self.handoff_root / asset_type),
                "state_path": str(lane_root / "task-state.json"),
                "cancel_path": str(self.cancel_path),
            }
            self.active_child = PanelAuditTask(
                child_request, self.collector_factories[asset_type]()
            )
            return True
        return False

    def tick(self) -> bool:
        if self.is_terminal:
            return True
        try:
            if self.state == "pending":
                self.state = "running"
                if self.cancel_path.exists():
                    self.cancelled_lanes.update(ASSET_TYPES)  # type: ignore[arg-type]
                    self._finish(cancelled=True)
                    return True
                if not self._start_next_lane():
                    self._finish(cancelled=False)
                    return True
                self._write_state(
                    self._state_payload(
                        f"正在进入{self._lane_label(self.active_lane)}泳道", can_cancel=True
                    )
                )
                return False
            if not self.active_child or not self.active_lane:
                self._finish(cancelled=False)
                return True
            terminal = self.active_child.tick()
            if not terminal:
                self._write_state(
                    self._state_payload(
                        f"{self._lane_label(self.active_lane)}泳道 · "
                        f"{self.active_child.processed_count}/{len(self.lane_paths[self.active_lane])}",
                        can_cancel=True,
                    )
                )
                return False
            child_state = self.active_child.state
            report_path = str(self.active_child.output_path)
            if child_state in {"completed", "cancelled"} and Path(report_path).is_file():
                self.report_paths[self.active_lane] = report_path
            elif child_state == "failed":
                self.lane_errors[self.active_lane] = (
                    str(self.active_child.last_state.get("error_code", "LANE_FAILED")),
                    str(self.active_child.last_state.get("error_message", "泳道执行失败")),
                )
            if child_state == "cancelled" or self.cancel_path.exists():
                for pending in ASSET_TYPES[self.lane_index + 1 :]:
                    self.cancelled_lanes.add(pending)  # type: ignore[arg-type]
                self._finish(cancelled=True)
                return True
            if self._start_next_lane():
                self._write_state(
                    self._state_payload(
                        f"已完成一条泳道，正在进入{self._lane_label(self.active_lane)}泳道",
                        can_cancel=True,
                    )
                )
                return False
            self._finish(cancelled=False)
            return True
        except Exception as exc:  # noqa: BLE001 - preserve a legal partial package
            if self.active_lane:
                self.lane_errors[self.active_lane] = (type(exc).__name__, str(exc))
            traceback.print_exc()
            try:
                self._finish(cancelled=False)
            except Exception:  # noqa: BLE001 - last-resort terminal state
                self.state = "failed"
                self._write_state(
                    self._state_payload(
                        "交付包总检失败；三条原始资产均未被修改", can_cancel=False
                    )
                )
            return True

    @staticmethod
    def _lane_label(asset_type: AssetType | None) -> str:
        return {
            "static_mesh": "模型",
            "texture2d": "纹理",
            "material_interface": "材质",
        }.get(asset_type, "交付")

    def _finish(self, *, cancelled: bool) -> None:
        summary = build_delivery_package_summary(
            recipe=self.recipe,
            report_paths=self.report_paths,
            requested_counts={
                asset_type: len(paths) for asset_type, paths in self.lane_paths.items()
            },
            ignored_assets=self.ignored_assets,
            lane_errors=self.lane_errors,
            cancelled_lanes=self.cancelled_lanes,
        )
        summary.write(self.output_path)
        self.state = "cancelled" if cancelled else "completed"
        message = (
            f"交付包已取消 · 保留 {summary.processed_count} 个已处理对象"
            if cancelled
            else f"三轨总检完成 · {summary.processed_count} 个对象 · "
            f"{summary.issue_count} 个问题 · {summary.blocking_issue_count} 个阻断"
        )
        payload = self._state_payload(message, can_cancel=False)
        payload["report_path"] = str(self.output_path)
        self._write_state(payload)


_ACTIVE_PACKAGE_TASK: PanelDeliveryPackageTask | None = None
_PACKAGE_TICK_HANDLE: Any = None


def start_delivery_package_task(
    request_path: str,
    *,
    collector_factories: dict[
        AssetType, Callable[[], MetadataCollector]
    ] | None = None,
    register_callback: Callable[[Callable[[float], None]], Any] | None = None,
    unregister_callback: Callable[[Any], None] | None = None,
) -> dict[str, Any]:
    global _ACTIVE_PACKAGE_TASK, _PACKAGE_TICK_HANDLE
    if _ACTIVE_PACKAGE_TASK is not None and not _ACTIVE_PACKAGE_TASK.is_terminal:
        raise RuntimeError("已有交付包总检任务正在运行")
    request = json.loads(Path(request_path).read_text(encoding="utf-8"))
    cancel_path = Path(str(request["cancel_path"]))
    cancel_path.unlink(missing_ok=True)
    factories = collector_factories or {
        "static_mesh": UnrealCppCollector,
        "texture2d": TextureUnrealCppCollector,
        "material_interface": MaterialUnrealCppCollector,
    }
    task = PanelDeliveryPackageTask(request, factories)
    _ACTIVE_PACKAGE_TASK = task
    if register_callback is None or unregister_callback is None:
        import unreal  # type: ignore[import-not-found]

        register_callback = unreal.register_slate_post_tick_callback
        unregister_callback = unreal.unregister_slate_post_tick_callback

    def advance(_delta_seconds: float) -> None:
        global _PACKAGE_TICK_HANDLE
        if task.tick() and _PACKAGE_TICK_HANDLE is not None:
            handle = _PACKAGE_TICK_HANDLE
            _PACKAGE_TICK_HANDLE = None
            unregister_callback(handle)

    _PACKAGE_TICK_HANDLE = register_callback(advance)
    return task.last_state


__all__ = ["PanelDeliveryPackageTask", "start_delivery_package_task"]
