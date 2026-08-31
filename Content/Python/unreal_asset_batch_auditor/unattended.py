from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from .audit import audit_assets
from .collectors import MetadataCollector
from .contracts import AuditProfile, ContractError, Severity

PRESET_VERSION = "unreal-asset-audit-preset@1.0.0"
SUMMARY_VERSION = "unreal-asset-audit-run@1.0.0"

EXIT_PASSED = 0
EXIT_POLICY_FAILED = 10
EXIT_COLLECTION_FAILED = 20
EXIT_CONFIG_ERROR = 30
EXIT_RUNTIME_ERROR = 40

RunStatus = Literal[
    "passed", "policy_failed", "collection_failed", "config_error", "runtime_error"
]


class PresetError(ContractError):
    """Raised when a project preset is unsafe or incomplete."""


def _non_empty_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PresetError(f"{path} 必须是非空字符串")
    return value.strip()


def _string_list(value: Any, path: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or (not value and not allow_empty):
        qualifier = "数组" if allow_empty else "非空数组"
        raise PresetError(f"{path} 必须是{qualifier}")
    return tuple(_non_empty_string(item, f"{path}[]") for item in value)


def _validate_asset_path(path: str) -> str:
    if not path.startswith(("/Game/", "/Engine/")) or "." not in path.rsplit("/", 1)[-1]:
        raise PresetError(
            f"资产路径必须是显式 /Game 或 /Engine object path，不能使用通配或全项目扫描：{path}"
        )
    if any(token in path for token in ("*", "?", "...")):
        raise PresetError(f"资产路径不允许通配符：{path}")
    return path


def _validate_folder_path(path: str) -> str:
    normalized = path.rstrip("/")
    if not normalized.startswith(("/Game/", "/Engine/")):
        raise PresetError(f"目录范围必须位于 /Game 或 /Engine 下：{path}")
    if any(token in normalized for token in ("*", "?", "...", ".")):
        raise PresetError(f"目录范围必须是显式 package 目录且不允许通配符：{path}")
    return normalized


@dataclass(frozen=True)
class ProjectPreset:
    schema_version: str
    preset_id: str
    description: str
    profile_path: str
    asset_paths: tuple[str, ...]
    folder_paths: tuple[str, ...]
    batch_size: int
    blocking_severities: tuple[Severity, ...]
    report_path: str
    summary_path: str

    @classmethod
    def load(cls, path: str | Path) -> ProjectPreset:
        preset_path = Path(path)
        try:
            raw = json.loads(preset_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PresetError(f"无法读取项目预设：{preset_path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise PresetError("项目预设根节点必须是对象")
        if raw.get("schema_version") != PRESET_VERSION:
            raise PresetError(f"不支持的项目预设 schema_version：{raw.get('schema_version')!r}")
        scope = raw.get("scope")
        output = raw.get("output")
        gate = raw.get("gate")
        if not isinstance(scope, dict) or not isinstance(output, dict) or not isinstance(gate, dict):
            raise PresetError("项目预设必须包含 scope、gate 和 output 对象")
        asset_paths = _string_list(scope.get("asset_paths", []), "scope.asset_paths", allow_empty=True)
        folder_paths = _string_list(
            scope.get("folder_paths", []), "scope.folder_paths", allow_empty=True
        )
        if not asset_paths and not folder_paths:
            raise PresetError("审计范围为空；必须显式配置 asset_paths 或 folder_paths")
        batch_size = raw.get("batch_size", 64)
        if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1:
            raise PresetError("batch_size 必须是正整数")
        severities = _string_list(gate.get("blocking_severities"), "gate.blocking_severities")
        if any(item not in {"info", "warning", "error"} for item in severities):
            raise PresetError("gate.blocking_severities 只能包含 info、warning、error")
        if len(set(severities)) != len(severities):
            raise PresetError("gate.blocking_severities 不允许重复")
        return cls(
            schema_version=PRESET_VERSION,
            preset_id=_non_empty_string(raw.get("preset_id"), "preset_id"),
            description=_non_empty_string(raw.get("description"), "description"),
            profile_path=_non_empty_string(raw.get("profile_path"), "profile_path"),
            asset_paths=tuple(_validate_asset_path(item) for item in asset_paths),
            folder_paths=tuple(_validate_folder_path(item) for item in folder_paths),
            batch_size=batch_size,
            blocking_severities=severities,  # type: ignore[arg-type]
            report_path=_non_empty_string(output.get("report_path"), "output.report_path"),
            summary_path=_non_empty_string(output.get("summary_path"), "output.summary_path"),
        )


def resolve_asset_paths(
    preset: ProjectPreset,
    discover_folder: Callable[[str], list[str]] | None,
) -> list[str]:
    resolved = set(preset.asset_paths)
    if preset.folder_paths and discover_folder is None:
        raise PresetError("当前运行环境不能解析 folder_paths")
    for folder in preset.folder_paths:
        discovered = discover_folder(folder) if discover_folder else []
        resolved.update(_validate_asset_path(item) for item in discovered)
    if not resolved:
        raise PresetError("显式目录中没有发现 Static Mesh，拒绝生成空审计")
    return sorted(resolved)


def _resolve_path(value: str, base: Path) -> Path:
    candidate = Path(value)
    return candidate if candidate.is_absolute() else base / candidate


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _summary(
    *,
    preset_id: str | None,
    status: RunStatus,
    exit_code: int,
    message: str,
    report_path: Path | None = None,
    requested_asset_count: int = 0,
    asset_count: int = 0,
    issue_count: int = 0,
    blocking_issue_count: int = 0,
    collection_failure_count: int = 0,
) -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "preset_id": preset_id,
        "status": status,
        "exit_code": exit_code,
        "message": message,
        "report_path": str(report_path) if report_path else None,
        "requested_asset_count": requested_asset_count,
        "asset_count": asset_count,
        "issue_count": issue_count,
        "blocking_issue_count": blocking_issue_count,
        "collection_failure_count": collection_failure_count,
    }


def run_project_preset(
    preset_path: str | Path,
    *,
    project_root: str | Path,
    collector: MetadataCollector,
    discover_folder: Callable[[str], list[str]] | None = None,
    summary_override: str | Path | None = None,
) -> dict[str, Any]:
    """Run one explicit project preset and always return a stable machine-readable result."""

    preset_file = Path(preset_path)
    fallback_summary = Path(summary_override) if summary_override else None
    try:
        preset = ProjectPreset.load(preset_file)
        output_root = Path(project_root)
        summary_path = fallback_summary or _resolve_path(preset.summary_path, output_root)
        report_path = _resolve_path(preset.report_path, output_root)
        profile_path = _resolve_path(preset.profile_path, preset_file.parent)
        if not profile_path.is_file():
            raise PresetError(f"Profile 不存在：{profile_path}")
        requested_paths = resolve_asset_paths(preset, discover_folder)
        report = audit_assets(
            profile=AuditProfile.load(profile_path),
            collector=collector,
            asset_paths=requested_paths,
            batch_size=preset.batch_size,
        )
        report.write(report_path)
        blocking = [
            issue for issue in report.issues if issue.severity in preset.blocking_severities
        ]
        if report.collection_failure_count:
            status: RunStatus = "collection_failed"
            exit_code = EXIT_COLLECTION_FAILED
            message = f"采集失败 {report.collection_failure_count} 个；审计结果不完整"
        elif blocking:
            status = "policy_failed"
            exit_code = EXIT_POLICY_FAILED
            message = f"发现 {len(blocking)} 条阻断问题"
        else:
            status = "passed"
            exit_code = EXIT_PASSED
            message = "项目预设范围通过审计"
        result = _summary(
            preset_id=preset.preset_id,
            status=status,
            exit_code=exit_code,
            message=message,
            report_path=report_path,
            requested_asset_count=report.requested_asset_count,
            asset_count=report.asset_count,
            issue_count=report.issue_count,
            blocking_issue_count=len(blocking),
            collection_failure_count=report.collection_failure_count,
        )
        _write_json(summary_path, result)
        return result
    except (PresetError, ContractError, OSError, json.JSONDecodeError) as exc:
        result = _summary(
            preset_id=None,
            status="config_error",
            exit_code=EXIT_CONFIG_ERROR,
            message=str(exc),
        )
    except Exception as exc:  # noqa: BLE001  # pragma: no cover - Unreal host boundary
        result = _summary(
            preset_id=None,
            status="runtime_error",
            exit_code=EXIT_RUNTIME_ERROR,
            message=f"无人值守审计运行失败：{type(exc).__name__}: {exc}",
        )
    if fallback_summary:
        _write_json(fallback_summary, result)
    return result
