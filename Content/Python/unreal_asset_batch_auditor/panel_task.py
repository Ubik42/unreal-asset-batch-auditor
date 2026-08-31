from __future__ import annotations

import json
import math
import traceback
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .audit import build_report_from_collection
from .collectors import CollectionBatch, MetadataCollector, UnrealCppCollector
from .contracts import AuditProfile
from .handoff import export_handoff
from .material_audit import build_material_report_from_collection
from .material_collectors import MaterialUnrealCppCollector
from .material_contracts import MaterialAuditProfile
from .sessions import SessionStore
from .texture_audit import build_texture_report_from_collection
from .texture_collectors import TextureUnrealCppCollector
from .texture_contracts import TextureAuditProfile

TASK_STATE_VERSION = "unreal-audit-task-state@1.0.0"
TERMINAL_STATES = frozenset({"completed", "cancelled", "failed"})


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temp.replace(path)


class PanelAuditTask:
    """One-batch-per-tick orchestration so the native panel remains cancellable."""

    def __init__(self, request: dict[str, Any], collector: MetadataCollector) -> None:
        self.request = request
        self.collector = collector
        self.task_id = str(request["task_id"])
        self.asset_type = str(request.get("asset_type", "static_mesh"))
        if self.asset_type not in {"static_mesh", "texture2d", "material_interface"}:
            raise ValueError(
                "asset_type must be static_mesh, texture2d, or material_interface"
            )
        profile_types = {
            "static_mesh": AuditProfile,
            "texture2d": TextureAuditProfile,
            "material_interface": MaterialAuditProfile,
        }
        self.profile = profile_types[self.asset_type].load(str(request["profile_path"]))
        self.paths = [str(path) for path in request["asset_paths"]]
        self.batch_size = int(request.get("batch_size", 64))
        if self.batch_size < 1:
            raise ValueError("batch_size must be a positive integer")
        self.output_path = Path(str(request["output_path"]))
        self.session_root = (
            Path(str(request["session_root"])) if request.get("session_root") else None
        )
        self.handoff_root = Path(str(request["handoff_root"]))
        self.state_path = Path(str(request["state_path"]))
        self.cancel_path = Path(str(request["cancel_path"]))
        self.aggregate = CollectionBatch()
        self.processed_count = 0
        self.completed_batch_count = 0
        self.total_batch_count = math.ceil(len(self.paths) / self.batch_size) if self.paths else 0
        self.started_at = _utc_now()
        self.state = "pending"
        self.last_state = self._state_payload(
            message="任务已创建，等待第一个批次", can_cancel=True
        )
        self._write_state(self.last_state)

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    def _state_payload(
        self,
        *,
        message: str,
        can_cancel: bool,
        error_code: str | None = None,
        error_message: str | None = None,
        report_path: str | None = None,
        handoff_path: str | None = None,
    ) -> dict[str, Any]:
        requested = len(self.paths)
        cancelled = requested - self.processed_count if self.state == "cancelled" else 0
        payload: dict[str, Any] = {
            "schema_version": TASK_STATE_VERSION,
            "task_id": self.task_id,
            "state": self.state,
            "message": message,
            "can_cancel": can_cancel,
            "started_at": self.started_at,
            "updated_at": _utc_now(),
            "requested_count": requested,
            "processed_count": self.processed_count,
            "collected_count": len(self.aggregate.assets),
            "failed_count": len(self.aggregate.failures),
            "cancelled_count": cancelled,
            "completed_batch_count": self.completed_batch_count,
            "total_batch_count": self.total_batch_count,
            "progress_fraction": (
                self.processed_count / requested if requested else 1.0
            ),
        }
        if error_code:
            payload["error_code"] = error_code
        if error_message:
            payload["error_message"] = error_message
        if report_path:
            payload["report_path"] = report_path
        if handoff_path:
            payload["handoff_path"] = handoff_path
        return payload

    def _write_state(self, payload: dict[str, Any]) -> None:
        _atomic_json(self.state_path, payload)
        self.last_state = payload

    def _transition(self, state: str, message: str, *, can_cancel: bool) -> None:
        self.state = state
        self._write_state(self._state_payload(message=message, can_cancel=can_cancel))

    def tick(self) -> bool:
        """Advance at most one collection batch. Returns True when terminal."""

        if self.is_terminal:
            return True
        try:
            if self.state == "pending":
                if self.cancel_path.exists():
                    self._transition("cancelling", "已收到取消请求，正在保留部分结果", can_cancel=False)
                else:
                    self._transition("running", "正在准备第一个只读采集批次", can_cancel=True)
                return False
            if self.state == "cancelling":
                self._finish(cancelled=True)
                return True
            if self.cancel_path.exists():
                self._transition("cancelling", "当前批次已结束，正在保留部分结果", can_cancel=False)
                return False
            if self.processed_count >= len(self.paths):
                self._finish(cancelled=False)
                return True

            current = self.paths[
                self.processed_count : self.processed_count + self.batch_size
            ]
            batch = self.collector.collect(current)
            self.aggregate.assets.extend(batch.assets)
            self.aggregate.failures.extend(batch.failures)
            self.processed_count += len(current)
            self.completed_batch_count += 1
            if self.processed_count >= len(self.paths):
                self._finish(cancelled=False)
                return True
            self._write_state(
                self._state_payload(
                    message=(
                        f"已完成 {self.completed_batch_count}/{self.total_batch_count} 个批次，"
                        "可在下一批开始前取消"
                    ),
                    can_cancel=True,
                )
            )
            return False
        except Exception as exc:  # noqa: BLE001 - terminal boundary must preserve diagnostics
            self.state = "failed"
            self._write_state(
                self._state_payload(
                    message="审计任务失败；资产未被修改，技术堆栈已写入 Unreal 日志",
                    can_cancel=False,
                    error_code=type(exc).__name__,
                    error_message=str(exc),
                )
            )
            traceback.print_exc()
            return True

    def _finish(self, *, cancelled: bool) -> None:
        self.aggregate.assets.sort(key=lambda item: item.asset_path)
        self.aggregate.failures.sort(
            key=lambda item: (item.asset_path, item.code, item.message)
        )
        cancelled_count = len(self.paths) - self.processed_count if cancelled else 0
        report_builders = {
            "static_mesh": build_report_from_collection,
            "texture2d": build_texture_report_from_collection,
            "material_interface": build_material_report_from_collection,
        }
        build_report = report_builders[self.asset_type]
        report = build_report(
            profile=self.profile,
            collector=self.collector,
            batch=self.aggregate,
            requested_asset_paths=self.paths,
            requested_asset_count=len(self.paths),
            processed_asset_count=self.processed_count,
            cancelled_asset_count=cancelled_count,
            completed_batch_count=self.completed_batch_count,
            batch_size=self.batch_size,
        )
        report.write(self.output_path)
        if self.session_root:
            store = SessionStore(self.session_root)
            session = store.save_report(self.output_path)
            store.write_latest_comparison(session)
        handoff = export_handoff(self.output_path, self.handoff_root)
        self.state = "cancelled" if cancelled else "completed"
        self._write_state(
            self._state_payload(
                message=(
                    f"已取消：保留 {self.processed_count} 个已处理对象，"
                    f"{cancelled_count} 个未处理"
                    if cancelled
                    else f"审计完成：{len(self.aggregate.assets)} 个资产，"
                    f"{len(report.issues)} 个问题"
                ),
                can_cancel=False,
                report_path=str(self.output_path),
                handoff_path=str(handoff.root),
            )
        )


_ACTIVE_TASK: PanelAuditTask | None = None
_TICK_HANDLE: Any = None


def start_panel_task(
    request_path: str,
    *,
    collector_factory: Callable[[], MetadataCollector] | None = None,
    register_callback: Callable[[Callable[[float], None]], Any] | None = None,
    unregister_callback: Callable[[Any], None] | None = None,
) -> dict[str, Any]:
    """Register a real Editor post-tick task and return immediately to Slate."""

    global _ACTIVE_TASK, _TICK_HANDLE
    if _ACTIVE_TASK is not None and not _ACTIVE_TASK.is_terminal:
        raise RuntimeError("已有资产审计任务正在运行")
    request = json.loads(Path(request_path).read_text(encoding="utf-8"))
    cancel_path = Path(str(request["cancel_path"]))
    cancel_path.unlink(missing_ok=True)
    if collector_factory is None:
        collector_factories = {
            "static_mesh": UnrealCppCollector,
            "texture2d": TextureUnrealCppCollector,
            "material_interface": MaterialUnrealCppCollector,
        }
        collector_factory = collector_factories.get(
            str(request.get("asset_type", "static_mesh")), UnrealCppCollector
        )
    task = PanelAuditTask(request, collector_factory())
    _ACTIVE_TASK = task

    if register_callback is None or unregister_callback is None:
        import unreal  # type: ignore[import-not-found]

        register_callback = unreal.register_slate_post_tick_callback
        unregister_callback = unreal.unregister_slate_post_tick_callback

    def advance(_delta_seconds: float) -> None:
        global _TICK_HANDLE
        if task.tick() and _TICK_HANDLE is not None:
            handle = _TICK_HANDLE
            _TICK_HANDLE = None
            unregister_callback(handle)

    _TICK_HANDLE = register_callback(advance)
    return task.last_state


def request_panel_cancel(cancel_path: str) -> None:
    _atomic_json(
        Path(cancel_path),
        {"schema_version": TASK_STATE_VERSION, "requested_at": _utc_now()},
    )
