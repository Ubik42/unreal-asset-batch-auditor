from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REVIEW_LEDGER_VERSION = "unreal-audit-review-ledger@1.0.0"
REVIEW_VIEW_VERSION = "unreal-audit-review-view@1.0.0"
REVIEW_DECISIONS = frozenset({"fix_required", "approved_exception"})


class ReviewLedgerError(ValueError):
    """Raised when review metadata cannot be safely associated with a report."""


@dataclass(frozen=True)
class ReviewSnapshot:
    report_id: str
    report_sha256: str
    ledger_path: Path
    reviewable_count: int
    records: tuple[dict[str, str], ...]
    orphan_records: tuple[dict[str, str], ...]
    isolated_corrupt_path: Path | None = None

    def to_view(self) -> dict[str, Any]:
        counts = {
            "unreviewed": max(0, self.reviewable_count - len(self.records)),
            "fix_required": 0,
            "approved_exception": 0,
        }
        for record in self.records:
            counts[record["decision"]] += 1
        return {
            "schema_version": REVIEW_VIEW_VERSION,
            "report_id": self.report_id,
            "report_sha256": self.report_sha256,
            "ledger_path": str(self.ledger_path),
            "records": list(self.records),
            "orphan_records": list(self.orphan_records),
            "orphan_count": len(self.orphan_records),
            "counts": counts,
            "isolated_corrupt_path": (
                str(self.isolated_corrupt_path) if self.isolated_corrupt_path else None
            ),
        }


def _read_report(path: str | Path) -> tuple[Path, bytes, dict[str, Any]]:
    source = Path(path)
    try:
        payload = source.read_bytes()
        report = json.loads(payload.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewLedgerError(f"报告无法读取或不是有效 JSON：{source}") from exc
    if not isinstance(report, dict) or not isinstance(report.get("report_id"), str):
        raise ReviewLedgerError("报告缺少 report_id")
    if not isinstance(report.get("issues"), list):
        raise ReviewLedgerError("报告缺少 issues 数组")
    return source, payload, report


def _safe_report_id(report_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", report_id)[:96]
    if not safe:
        raise ReviewLedgerError("report_id 无法生成安全台账文件名")
    return safe


def review_ledger_path(report_id: str, ledger_root: str | Path) -> Path:
    return Path(ledger_root) / f"{_safe_report_id(report_id)}.review.v1.json"


def _validate_record(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise ReviewLedgerError("审阅记录必须是对象")
    required = {"issue_id", "evidence_id", "asset_path", "rule_id", "decision", "owner", "note", "updated_at"}
    missing = sorted(required - raw.keys())
    if missing:
        raise ReviewLedgerError(f"审阅记录缺少字段：{', '.join(missing)}")
    record = {key: str(raw[key]) for key in required}
    if record["decision"] not in REVIEW_DECISIONS:
        raise ReviewLedgerError(f"未知审阅决定：{record['decision']}")
    if not record["issue_id"] or not record["evidence_id"]:
        raise ReviewLedgerError("审阅记录必须绑定 issue_id 和 evidence_id")
    if len(record["owner"]) > 80 or len(record["note"]) > 500:
        raise ReviewLedgerError("负责人或备注超过长度限制")
    return record


def _load_ledger(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewLedgerError(f"审阅台账损坏：{path}") from exc
    if not isinstance(raw, dict) or raw.get("schema_version") != REVIEW_LEDGER_VERSION:
        raise ReviewLedgerError("审阅台账版本不受支持")
    if not isinstance(raw.get("report_id"), str) or not isinstance(raw.get("report_sha256"), str):
        raise ReviewLedgerError("审阅台账缺少报告身份")
    if not isinstance(raw.get("records"), list):
        raise ReviewLedgerError("审阅台账缺少 records 数组")
    records = [_validate_record(item) for item in raw["records"]]
    keys = [(item["issue_id"], item["evidence_id"]) for item in records]
    if len(keys) != len(set(keys)):
        raise ReviewLedgerError("审阅台账包含重复问题记录")
    return {**raw, "records": records}


def _isolate_corrupt(path: Path, now: datetime) -> Path:
    stamp = now.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    destination = path.with_name(f"{path.name}.corrupt-{stamp}")
    counter = 1
    while destination.exists():
        destination = path.with_name(f"{path.name}.corrupt-{stamp}-{counter}")
        counter += 1
    path.replace(destination)
    return destination


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def load_review_snapshot(
    report_path: str | Path,
    ledger_root: str | Path,
    *,
    isolate_corrupt: bool = True,
    now_factory: Callable[[], datetime] | None = None,
) -> ReviewSnapshot:
    _, report_payload, report = _read_report(report_path)
    report_id = str(report["report_id"])
    report_sha256 = hashlib.sha256(report_payload).hexdigest()
    path = review_ledger_path(report_id, ledger_root)
    isolated: Path | None = None
    try:
        ledger = _load_ledger(path)
    except ReviewLedgerError:
        if not isolate_corrupt or not path.exists():
            raise
        isolated = _isolate_corrupt(path, (now_factory or (lambda: datetime.now(UTC)))())
        ledger = None

    if ledger is None:
        return ReviewSnapshot(
            report_id, report_sha256, path, len(report["issues"]), (), (), isolated
        )
    if ledger["report_id"] != report_id:
        raise ReviewLedgerError("审阅台账 report_id 与当前报告不匹配")

    current_pairs = {
        (str(issue.get("issue_id", "")), str(issue.get("evidence_id", "")))
        for issue in report["issues"]
    }
    hash_matches = ledger["report_sha256"] == report_sha256
    matched: list[dict[str, str]] = []
    orphaned: list[dict[str, str]] = []
    for record in ledger["records"]:
        pair = (record["issue_id"], record["evidence_id"])
        if hash_matches and pair in current_pairs:
            matched.append(record)
        else:
            orphaned.append(record)
    matched.sort(key=lambda item: (item["issue_id"], item["evidence_id"]))
    orphaned.sort(key=lambda item: (item["issue_id"], item["evidence_id"]))
    return ReviewSnapshot(
        report_id,
        report_sha256,
        path,
        len(report["issues"]),
        tuple(matched),
        tuple(orphaned),
        isolated,
    )


def update_review(
    report_path: str | Path,
    ledger_root: str | Path,
    *,
    issue_id: str,
    evidence_id: str,
    decision: str,
    owner: str = "",
    note: str = "",
    now_factory: Callable[[], datetime] | None = None,
) -> ReviewSnapshot:
    owner = owner.strip()
    note = note.strip()
    if decision not in REVIEW_DECISIONS | {"unreviewed"}:
        raise ReviewLedgerError(f"未知审阅决定：{decision}")
    if len(owner) > 80 or len(note) > 500:
        raise ReviewLedgerError("负责人最多 80 字，备注最多 500 字")
    _, _, report = _read_report(report_path)
    issue = next(
        (
            item
            for item in report["issues"]
            if str(item.get("issue_id", "")) == issue_id
            and str(item.get("evidence_id", "")) == evidence_id
        ),
        None,
    )
    if issue is None:
        raise ReviewLedgerError("当前报告中找不到对应的 Issue / Evidence，未写入台账")

    clock = now_factory or (lambda: datetime.now(UTC))
    snapshot = load_review_snapshot(
        report_path, ledger_root, isolate_corrupt=True, now_factory=clock
    )
    if snapshot.orphan_records:
        raise ReviewLedgerError("台账与同名报告内容不一致；孤儿记录已保留，未覆盖写入")

    records = {
        (item["issue_id"], item["evidence_id"]): dict(item) for item in snapshot.records
    }
    key = (issue_id, evidence_id)
    if decision == "unreviewed":
        records.pop(key, None)
    else:
        records[key] = {
            "issue_id": issue_id,
            "evidence_id": evidence_id,
            "asset_path": str(issue.get("asset_path", "")),
            "rule_id": str(issue.get("rule_id", "")),
            "decision": decision,
            "owner": owner,
            "note": note,
            "updated_at": clock().astimezone(UTC).isoformat().replace("+00:00", "Z"),
        }
    ordered = sorted(records.values(), key=lambda item: (item["issue_id"], item["evidence_id"]))
    _atomic_write(
        snapshot.ledger_path,
        {
            "schema_version": REVIEW_LEDGER_VERSION,
            "report_id": snapshot.report_id,
            "report_sha256": snapshot.report_sha256,
            "records": ordered,
        },
    )
    return load_review_snapshot(report_path, ledger_root, isolate_corrupt=False)


def write_review_view(
    report_path: str | Path, ledger_root: str | Path, output_path: str | Path
) -> dict[str, Any]:
    view = load_review_snapshot(report_path, ledger_root).to_view()
    _atomic_write(Path(output_path), view)
    return view
