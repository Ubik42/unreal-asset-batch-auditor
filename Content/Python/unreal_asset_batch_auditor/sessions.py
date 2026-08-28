from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SESSION_INDEX_VERSION = "unreal-audit-session-index@1.0.0"
COMPARISON_VERSION = "unreal-audit-comparison@1.0.0"


class SessionError(ValueError):
    """Raised when immutable session storage cannot safely accept a report."""


@dataclass(frozen=True)
class SessionRecord:
    session_id: str
    created_at: str
    report_id: str
    profile_id: str
    profile_version: str
    report_path: str
    report_sha256: str
    asset_count: int
    issue_count: int
    collection_failure_count: int


@dataclass(frozen=True)
class SessionIndexResult:
    sessions: tuple[SessionRecord, ...]
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class SessionComparison:
    baseline_report_id: str
    current_report_id: str
    new_issues: tuple[dict[str, Any], ...]
    persistent_issues: tuple[dict[str, Any], ...]
    resolved_issues: tuple[dict[str, Any], ...]
    new_failures: tuple[dict[str, Any], ...]
    persistent_failures: tuple[dict[str, Any], ...]
    resolved_failures: tuple[dict[str, Any], ...]
    schema_version: str = COMPARISON_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _read_report(path: str | Path) -> tuple[dict[str, Any], bytes]:
    source = Path(path)
    try:
        payload = source.read_bytes()
        raw = json.loads(payload.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SessionError(f"报告无法读取或不是有效 JSON：{source}") from exc
    required = (
        "report_id",
        "created_at",
        "profile_id",
        "profile_version",
        "asset_count",
        "issue_count",
        "collection_failure_count",
        "issues",
        "collection_failures",
    )
    missing = [name for name in required if name not in raw]
    if missing:
        raise SessionError(f"报告缺少必要字段：{', '.join(missing)}")
    return raw, payload


class SessionStore:
    """Project-local immutable report history with a small replaceable JSON index."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.reports_dir = self.root / "Reports"
        self.index_path = self.root / "session-index.v1.json"

    def load_index(self) -> SessionIndexResult:
        if not self.index_path.exists():
            return SessionIndexResult(())
        try:
            raw = json.loads(self.index_path.read_text(encoding="utf-8"))
            if raw.get("schema_version") != SESSION_INDEX_VERSION:
                raise ValueError("unsupported schema")
            sessions = tuple(SessionRecord(**item) for item in raw.get("sessions", []))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return SessionIndexResult(
                (), (f"会话索引无法读取，历史报告未被删除：{self.index_path}",)
            )
        return SessionIndexResult(
            tuple(sorted(sessions, key=lambda item: item.created_at, reverse=True))
        )

    def save_report(self, report_path: str | Path) -> SessionRecord:
        raw, payload = _read_report(report_path)
        digest = hashlib.sha256(payload).hexdigest()
        session_id = f"session-{digest[:16]}"
        timestamp = re.sub(r"[^0-9]", "", str(raw["created_at"]))[:20] or "undated"
        safe_report_id = re.sub(r"[^A-Za-z0-9_.-]", "_", str(raw["report_id"]))[:80]
        relative_report = Path("Reports") / f"{timestamp}-{safe_report_id}-{digest[:8]}.json"
        destination = self.root / relative_report
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            existing_digest = hashlib.sha256(destination.read_bytes()).hexdigest()
            if existing_digest != digest:
                raise SessionError(f"历史报告已存在但哈希不同，拒绝覆盖：{destination}")
        else:
            try:
                with destination.open("xb") as stream:
                    stream.write(payload)
            except FileExistsError:
                existing_digest = hashlib.sha256(destination.read_bytes()).hexdigest()
                if existing_digest != digest:
                    raise SessionError(f"并发写入产生冲突，拒绝覆盖：{destination}")

        record = SessionRecord(
            session_id=session_id,
            created_at=str(raw["created_at"]),
            report_id=str(raw["report_id"]),
            profile_id=str(raw["profile_id"]),
            profile_version=str(raw["profile_version"]),
            report_path=relative_report.as_posix(),
            report_sha256=digest,
            asset_count=int(raw["asset_count"]),
            issue_count=int(raw["issue_count"]),
            collection_failure_count=int(raw["collection_failure_count"]),
        )
        loaded = self.load_index()
        sessions = [item for item in loaded.sessions if item.session_id != session_id]
        sessions.append(record)
        sessions.sort(key=lambda item: item.created_at, reverse=True)
        self._write_index(sessions)
        return record

    def _write_index(self, sessions: list[SessionRecord]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temp = self.root / "session-index.v1.json.tmp"
        payload = {
            "schema_version": SESSION_INDEX_VERSION,
            "sessions": [asdict(item) for item in sessions],
        }
        temp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        temp.replace(self.index_path)


def _issue_map(report: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(item["asset_path"]), str(item["rule_id"])): {
            "asset_path": str(item["asset_path"]),
            "rule_id": str(item["rule_id"]),
            "severity": str(item["severity"]),
            "message": str(item["message"]),
        }
        for item in report.get("issues", [])
    }


def _failure_map(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item["asset_path"]): {
            "asset_path": str(item["asset_path"]),
            "code": str(item["code"]),
            "message": str(item["message"]),
        }
        for item in report.get("collection_failures", [])
    }


def _classified(
    baseline: dict[Any, dict[str, Any]], current: dict[Any, dict[str, Any]]
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    new = tuple(current[key] for key in sorted(current.keys() - baseline.keys()))
    persistent = tuple(current[key] for key in sorted(current.keys() & baseline.keys()))
    resolved = tuple(baseline[key] for key in sorted(baseline.keys() - current.keys()))
    return new, persistent, resolved


def compare_reports(
    baseline_path: str | Path, current_path: str | Path
) -> SessionComparison:
    baseline, _ = _read_report(baseline_path)
    current, _ = _read_report(current_path)
    new_issues, persistent_issues, resolved_issues = _classified(
        _issue_map(baseline), _issue_map(current)
    )
    new_failures, persistent_failures, resolved_failures = _classified(
        _failure_map(baseline), _failure_map(current)
    )
    return SessionComparison(
        baseline_report_id=str(baseline["report_id"]),
        current_report_id=str(current["report_id"]),
        new_issues=new_issues,
        persistent_issues=persistent_issues,
        resolved_issues=resolved_issues,
        new_failures=new_failures,
        persistent_failures=persistent_failures,
        resolved_failures=resolved_failures,
    )
