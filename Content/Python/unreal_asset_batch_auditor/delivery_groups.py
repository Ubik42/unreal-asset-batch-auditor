from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

from .review_ledger import load_review_snapshot

DELIVERY_GROUP_VIEW_VERSION = "unreal-audit-delivery-groups@1.0.0"
UNGROUPED_PATH = "/未归档路径"


class DeliveryGroupError(ValueError):
    """Raised when a Report cannot produce a trustworthy delivery-group view."""


def delivery_group_path(asset_path: str) -> str:
    """Return a stable package group without querying the Asset Registry.

    Unreal object paths are grouped at the first business folder below their
    namespace and project root, for example ``/Game/UABADemo/03_Heavy``. Short
    engine paths such as ``/Engine/BasicShapes/Cube.Cube`` retain their parent
    folder. Malformed or root-only values are kept in an explicit fallback group.
    """

    if not isinstance(asset_path, str) or not asset_path.startswith("/"):
        return UNGROUPED_PATH
    package_path = asset_path.split(".", 1)[0].rstrip("/")
    parts = [part for part in package_path.split("/") if part]
    if len(parts) < 2:
        return UNGROUPED_PATH
    parent = parts[:-1]
    if not parent:
        return UNGROUPED_PATH
    return "/" + "/".join(parent[:3])


def _read_report(path: str | Path) -> tuple[Path, dict[str, Any]]:
    source = Path(path)
    try:
        report = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DeliveryGroupError(f"报告无法读取或不是有效 JSON：{source}") from exc
    required = {
        "report_id",
        "assets",
        "issues",
        "collection_failures",
        "asset_count",
        "issue_count",
        "collection_failure_count",
    }
    if not isinstance(report, dict) or not required.issubset(report):
        raise DeliveryGroupError("报告缺少目录分组所需字段")
    if not all(isinstance(report[field], list) for field in ("assets", "issues", "collection_failures")):
        raise DeliveryGroupError("报告资产、问题或采集失败字段格式无效")
    return source, report


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def build_delivery_group_view(
    report_path: str | Path,
    review_ledger_root: str | Path | None = None,
) -> dict[str, Any]:
    """Aggregate only facts already present in one immutable Report."""

    _, report = _read_report(report_path)
    assets = report["assets"]
    issues = report["issues"]
    failures = report["collection_failures"]
    if int(report["asset_count"]) != len(assets):
        raise DeliveryGroupError("asset_count 与 assets 数组不一致")
    if int(report["issue_count"]) != len(issues):
        raise DeliveryGroupError("issue_count 与 issues 数组不一致")
    if int(report["collection_failure_count"]) != len(failures):
        raise DeliveryGroupError("collection_failure_count 与 collection_failures 数组不一致")

    successful_paths = {
        str(asset.get("asset_path", "")) for asset in assets if isinstance(asset, dict)
    }
    failure_paths = {
        str(failure.get("asset_path", ""))
        for failure in failures
        if isinstance(failure, dict)
    }
    all_paths = successful_paths | failure_paths
    issue_count_by_asset: dict[str, int] = defaultdict(int)
    issue_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    unbound_issue_count = 0
    for issue in issues:
        if not isinstance(issue, dict):
            raise DeliveryGroupError("issues 数组包含非对象条目")
        asset_path = str(issue.get("asset_path", ""))
        if asset_path not in all_paths:
            unbound_issue_count += 1
            continue
        issue_count_by_asset[asset_path] += 1
        issue_by_key[(str(issue.get("issue_id", "")), str(issue.get("evidence_id", "")))] = issue

    decisions: dict[tuple[str, str], str] = {}
    orphan_count = 0
    if review_ledger_root is not None:
        snapshot = load_review_snapshot(report_path, review_ledger_root)
        orphan_count = len(snapshot.orphan_records)
        decisions = {
            (record["issue_id"], record["evidence_id"]): record["decision"]
            for record in snapshot.records
        }

    buckets: dict[str, dict[str, Any]] = {}
    for asset_path in sorted(all_paths):
        group_path = delivery_group_path(asset_path)
        bucket = buckets.setdefault(
            group_path,
            {
                "group_path": group_path,
                "group_label": group_path.rsplit("/", 1)[-1],
                "asset_paths": [],
                "asset_count": 0,
                "passed_asset_count": 0,
                "issue_asset_count": 0,
                "issue_count": 0,
                "collection_failure_count": 0,
                "unreviewed_issue_count": 0,
                "fix_required_count": 0,
                "approved_exception_count": 0,
            },
        )
        bucket["asset_paths"].append(asset_path)
        bucket["asset_count"] += 1
        if asset_path in failure_paths:
            bucket["collection_failure_count"] += 1
        elif issue_count_by_asset[asset_path] > 0:
            bucket["issue_asset_count"] += 1
        else:
            bucket["passed_asset_count"] += 1

    for key, issue in issue_by_key.items():
        asset_path = str(issue.get("asset_path", ""))
        bucket = buckets[delivery_group_path(asset_path)]
        bucket["issue_count"] += 1
        decision = decisions.get(key, "unreviewed")
        bucket[f"{decision}_issue_count" if decision == "unreviewed" else f"{decision}_count"] += 1

    groups = list(buckets.values())
    for group in groups:
        group["issue_density"] = round(
            group["issue_count"] / max(1, group["asset_count"]), 2
        )
        if group["collection_failure_count"]:
            group["risk_band"] = "采集阻断"
            group["hotspot_reason"] = f"{group['collection_failure_count']} 个对象采集失败"
        elif group["fix_required_count"]:
            group["risk_band"] = "需修复"
            group["hotspot_reason"] = f"{group['fix_required_count']} 项已判定需修复"
        elif group["issue_density"] >= 2.0 or group["issue_count"] >= 5:
            group["risk_band"] = "高密度"
            group["hotspot_reason"] = f"每个对象 {group['issue_density']:.2f} 条规则问题"
        elif group["issue_count"]:
            group["risk_band"] = "待复核"
            group["hotspot_reason"] = f"{group['issue_count']} 条规则问题"
        else:
            group["risk_band"] = "清洁"
            group["hotspot_reason"] = "未触发规则问题"

    groups.sort(
        key=lambda item: (
            -item["collection_failure_count"],
            -item["fix_required_count"],
            -item["issue_density"],
            -item["issue_count"],
            item["group_path"].casefold(),
        )
    )
    for index, group in enumerate(groups, start=1):
        group["hotspot_rank"] = index

    return {
        "schema_version": DELIVERY_GROUP_VIEW_VERSION,
        "report_id": str(report["report_id"]),
        "grouping_rule": "package_parent_first_3_segments",
        "ranking_rule": "采集失败 > 需修复 > 问题密度 > 问题数 > 目录路径",
        "group_count": len(groups),
        "asset_count": len(assets) + len(failures),
        "issue_count": len(issues),
        "collection_failure_count": len(failures),
        "unbound_issue_count": unbound_issue_count,
        "review_orphan_count": orphan_count,
        "groups": groups,
    }


def write_delivery_group_view(
    report_path: str | Path,
    output_path: str | Path,
    review_ledger_root: str | Path | None = None,
) -> dict[str, Any]:
    view = build_delivery_group_view(report_path, review_ledger_root)
    _atomic_write(Path(output_path), view)
    return view
