from __future__ import annotations

import csv
import hashlib
import html
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HANDOFF_VERSION = "unreal-audit-handoff@1.0.0"


class HandoffError(ValueError):
    """Raised when a report cannot be safely exported for team handoff."""


@dataclass(frozen=True)
class HandoffResult:
    root: Path
    html_path: Path
    csv_path: Path
    manifest_path: Path


def _load_report(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    try:
        report = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HandoffError(f"报告无法读取或不是有效 JSON：{source}") from exc
    required = {
        "schema_version",
        "report_id",
        "created_at",
        "profile_id",
        "profile_version",
        "collection_mode",
        "real_unreal_validation",
        "asset_count",
        "issue_count",
        "collection_failure_count",
        "requested_asset_count",
        "processed_asset_count",
        "cancelled_asset_count",
        "issues",
        "evidence",
        "collection_failures",
    }
    missing = sorted(required - report.keys())
    if missing:
        raise HandoffError(f"报告缺少交接所需字段：{', '.join(missing)}")
    return report


def _display(value: Any) -> str:
    if isinstance(value, bool):
        return "是" if value else "否"
    if value is None:
        return "—"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _validation_label(report: dict[str, Any]) -> tuple[str, str]:
    if report["real_unreal_validation"] and report["collection_mode"] == "unreal_editor":
        return (
            "真实 Unreal 宿主采集",
            "资产事实由报告记录的 Unreal Editor 宿主采集；导出过程只读取报告，不重新扫描或修改资产。",
        )
    return (
        "离线 Fixture 验证",
        "本报告来自离线 Fixture，仅证明合同、规则与导出逻辑；不能作为 Unreal 编译、加载或真实资产验证证据。",
    )


def _rule_label(rule_id: str) -> str:
    labels = (
        ("triangle_budget", "三角形预算"),
        ("vertex_budget", "顶点预算"),
        ("material_slots", "材质槽"),
        ("missing_materials", "缺失材质"),
        ("unique_materials", "唯一材质"),
        ("texture_dependencies", "纹理依赖"),
        ("texture_dimension", "纹理尺寸"),
        ("lod_count", "LOD 数量"),
        ("nanite_state", "Nanite 状态"),
        ("simple_collision", "简单碰撞"),
        ("lightmap_uv", "Lightmap UV"),
        ("lightmap_resolution", "Lightmap 分辨率"),
        ("object_name", "资产命名"),
        ("package_path", "目录规范"),
    )
    for marker, label in labels:
        if marker in rule_id:
            return label
    return "采集失败" if rule_id == "collection.failure" else rule_id


def _severity_label(severity: str) -> str:
    return {"error": "错误", "warning": "警告", "info": "提示"}.get(
        severity, severity
    )


def _localized_issue(rule_id: str, observed: str, expected: str) -> str:
    templates = (
        ("triangle_budget", f"LOD0 三角形为 {observed}，超过 Profile 上限 {expected}。"),
        ("vertex_budget", f"LOD0 顶点为 {observed}，超过 Profile 上限 {expected}。"),
        ("material_slots", f"材质槽为 {observed}，超过 Profile 上限 {expected}。"),
        ("missing_materials", f"缺失材质槽为 {observed}，超过 Profile 上限 {expected}。"),
        ("unique_materials", f"唯一材质为 {observed} 个，超过 Profile 上限 {expected}。"),
        ("texture_dependencies", f"纹理依赖为 {observed} 个，超过 Profile 上限 {expected}。"),
        ("texture_dimension", f"最大纹理边长为 {observed}，超过 Profile 上限 {expected}。"),
        ("lod_count", f"LOD 数量为 {observed}，低于 Profile 下限 {expected}。"),
        ("nanite_state", f"Nanite 状态为 {observed}，Profile 期望为 {expected}。"),
        ("simple_collision", f"碰撞实测为 {observed}；Profile 要求 {expected}。"),
        ("lightmap_uv", f"Lightmap UV 实测为 {observed}；Profile 要求 {expected}。"),
        (
            "lightmap_resolution",
            f"Lightmap 分辨率为 {observed}，低于 Profile 下限 {expected}。",
        ),
        ("object_name", f"资产名 {observed} 不符合 Profile 命名规则：{expected}。"),
        ("package_path", f"资产目录 {observed} 不符合 Profile 目录规则：{expected}。"),
    )
    for marker, message in templates:
        if marker in rule_id:
            return message
    return "规则检查未通过；请结合实测值、期望值和 Profile 指针复核。"


def _rows(report: dict[str, Any]) -> list[dict[str, str]]:
    evidence_by_id = {
        str(item.get("evidence_id", "")): item for item in report.get("evidence", [])
    }
    rows: list[dict[str, str]] = []
    for issue in report.get("issues", []):
        evidence = evidence_by_id.get(str(issue.get("evidence_id", "")), {})
        rule_id = str(issue.get("rule_id", ""))
        severity = str(issue.get("severity", ""))
        observed = _display(evidence.get("observed"))
        expected = _display(evidence.get("expected"))
        rows.append(
            {
                "类型": "规则问题",
                "级别": _severity_label(severity),
                "级别代码": severity,
                "资产": str(issue.get("asset_path", "")),
                "检查项": _rule_label(rule_id),
                "规则 ID": rule_id,
                "指标": str(evidence.get("metric", "")),
                "实测": observed,
                "期望": expected,
                "Profile 指针": str(evidence.get("profile_pointer", "")),
                "说明": _localized_issue(rule_id, observed, expected),
                "原始说明": str(issue.get("message", "")),
                "证据 ID": str(issue.get("evidence_id", "")),
            }
        )
    for failure in report.get("collection_failures", []):
        rows.append(
            {
                "类型": "采集失败",
                "级别": "错误",
                "级别代码": "error",
                "资产": str(failure.get("asset_path", "")),
                "检查项": "采集失败",
                "规则 ID": "collection.failure",
                "指标": str(failure.get("collector", "")),
                "实测": str(failure.get("code", "")),
                "期望": "可读取的 Static Mesh",
                "Profile 指针": "—",
                "说明": (
                    "资产无法作为 Static Mesh 读取；该对象未进入规则评估，"
                    "其余批次结果不受影响。"
                ),
                "原始说明": str(failure.get("message", "")),
                "证据 ID": "—",
            }
        )
    return rows


def _csv_bytes(rows: list[dict[str, str]]) -> bytes:
    columns = [
        "类型",
        "级别",
        "级别代码",
        "资产",
        "检查项",
        "规则 ID",
        "指标",
        "实测",
        "期望",
        "Profile 指针",
        "说明",
        "原始说明",
        "证据 ID",
    ]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(rows)
    return ("\ufeff" + stream.getvalue()).encode("utf-8")


def _html_text(report: dict[str, Any], rows: list[dict[str, str]]) -> str:
    validation_label, validation_note = _validation_label(report)
    host = report.get("host_engine_version") or "未记录（离线报告）"
    state = "已取消，保留部分结果" if report["cancelled_asset_count"] else "已完成"
    row_html = "\n".join(
        "<tr>"
        f"<td><span class='level {html.escape(row['级别代码'])}'>{html.escape(row['级别'])}</span></td>"
        f"<td>{html.escape(row['资产'])}</td>"
        f"<td>{html.escape(row['检查项'])}</td>"
        f"<td>{html.escape(row['实测'])}</td>"
        f"<td>{html.escape(row['期望'])}</td>"
        f"<td>{html.escape(row['说明'])}</td>"
        "</tr>"
        for row in rows
    ) or "<tr><td colspan='6' class='empty'>没有规则问题或采集失败</td></tr>"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" href="data:,">
<title>Unreal 资产审计交接报告</title>
<style>
:root{{--bg:#0b1014;--panel:#121a20;--line:#24313a;--text:#e7eef2;--muted:#8fa2ad;--cyan:#33c5d5;--green:#58d69a;--amber:#f5bd4f;--red:#ff6b6b}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.55 "Microsoft YaHei UI","Noto Sans CJK SC",sans-serif}}
.shell{{max-width:1440px;margin:auto;padding:34px}} .hero{{display:flex;justify-content:space-between;gap:24px;align-items:flex-end;margin-bottom:22px}}
h1{{font-size:32px;margin:0 0 6px}} h2{{font-size:18px;margin:26px 0 12px}} .sub,.meta,.note{{color:var(--muted)}}
.badge{{border:1px solid var(--cyan);color:var(--cyan);padding:7px 12px}} .grid{{display:grid;grid-template-columns:repeat(6,1fr);gap:10px}}
.metric{{background:var(--panel);border-top:2px solid var(--cyan);padding:14px}} .metric strong{{display:block;font-size:25px;margin-top:4px}}
.note{{background:#0e1b20;border-left:3px solid var(--cyan);padding:12px 14px;margin:18px 0}}
.table-wrap{{overflow:auto;border:1px solid var(--line)}} table{{width:100%;table-layout:fixed;border-collapse:collapse;min-width:1100px}}
th{{position:sticky;top:0;background:#172229;text-align:left;color:#b7c6ce}} th,td{{padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}}
td{{overflow-wrap:anywhere}}
tr:hover td{{background:#101a20}} .level{{font-weight:700}} .level.error{{color:var(--red)}} .level.warning{{color:var(--amber)}} .level.info{{color:var(--cyan)}}
.empty{{text-align:center;color:var(--green);padding:36px}} footer{{margin-top:24px;color:var(--muted);font-size:12px}}
@media(max-width:900px){{.shell{{padding:18px}}.hero{{display:block}}.badge{{display:inline-block;margin-top:12px}}.grid{{grid-template-columns:repeat(2,1fr)}}}}
</style>
</head>
<body><main class="shell">
<section class="hero"><div><h1>Unreal 资产审计交接报告</h1><div class="sub">Profile 驱动 · 只读证据链 · 可离线查阅</div></div><div class="badge">{html.escape(state)}</div></section>
<div class="meta">报告 {html.escape(str(report['report_id']))} · Profile {html.escape(str(report['profile_id']))} / {html.escape(str(report['profile_version']))} · {html.escape(str(report['created_at']))}</div>
<section class="grid">
<div class="metric">请求资产<strong>{report['requested_asset_count']}</strong></div>
<div class="metric">已处理<strong>{report['processed_asset_count']}</strong></div>
<div class="metric">成功采集<strong>{report['asset_count']}</strong></div>
<div class="metric">规则问题<strong>{report['issue_count']}</strong></div>
<div class="metric">采集失败<strong>{report['collection_failure_count']}</strong></div>
<div class="metric">取消未处理<strong>{report['cancelled_asset_count']}</strong></div>
</section>
<div class="note"><strong>{html.escape(validation_label)}</strong><br>{html.escape(validation_note)}<br>宿主版本：{html.escape(str(host))}</div>
<h2>问题与失败明细</h2>
<div class="table-wrap"><table><thead><tr><th>级别</th><th>资产</th><th>检查项</th><th>实测</th><th>期望</th><th>证据说明</th></tr></thead><tbody>{row_html}</tbody></table></div>
<footer>此文件由 Unreal Asset Batch Auditor 从版本化 JSON Report 确定性生成。CSV 文件保留 Profile 指针和证据 ID，便于制作人、TA 与美术负责人筛选交接。</footer>
</main></body></html>
"""


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def export_handoff(report_path: str | Path, output_root: str | Path) -> HandoffResult:
    """Create a standalone Chinese HTML/CSV package from an existing report."""

    report = _load_report(report_path)
    safe_report_id = "".join(
        char if char.isalnum() or char in "._-" else "_" for char in str(report["report_id"])
    )[:96]
    root = Path(output_root) / safe_report_id
    root.mkdir(parents=True, exist_ok=True)
    rows = _rows(report)
    html_payload = _html_text(report, rows).encode("utf-8")
    csv_payload = _csv_bytes(rows)
    html_path = root / "审计交接报告.html"
    csv_path = root / "审计问题明细.csv"
    manifest_path = root / "交接清单.json"
    html_path.write_bytes(html_payload)
    csv_path.write_bytes(csv_payload)
    validation_label, validation_note = _validation_label(report)
    manifest = {
        "schema_version": HANDOFF_VERSION,
        "report_id": report["report_id"],
        "report_created_at": report["created_at"],
        "profile_id": report["profile_id"],
        "profile_version": report["profile_version"],
        "collection_mode": report["collection_mode"],
        "real_unreal_validation": report["real_unreal_validation"],
        "host_engine_version": report.get("host_engine_version"),
        "validation_label": validation_label,
        "validation_boundary": validation_note,
        "summary": {
            "requested_asset_count": report["requested_asset_count"],
            "processed_asset_count": report["processed_asset_count"],
            "cancelled_asset_count": report["cancelled_asset_count"],
            "asset_count": report["asset_count"],
            "issue_count": report["issue_count"],
            "collection_failure_count": report["collection_failure_count"],
        },
        "files": [
            {"path": html_path.name, "sha256": _sha256(html_payload)},
            {"path": csv_path.name, "sha256": _sha256(csv_payload)},
        ],
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return HandoffResult(root, html_path, csv_path, manifest_path)
