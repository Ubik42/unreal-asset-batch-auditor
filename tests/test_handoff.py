from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

import pytest
from unreal_asset_batch_auditor import HandoffError, export_handoff, update_review


def _report(*, real: bool, cancelled: int = 0) -> dict:
    processed = 2
    return {
        "schema_version": "unreal-asset-audit@2.0.0",
        "report_id": "report-handoff",
        "created_at": "2026-08-28T04:00:00+00:00",
        "profile_id": "demo-desktop-balanced-v2",
        "profile_version": "2.0.0",
        "profile_schema_version": "unreal-static-mesh-profile@2.0.0",
        "collection_mode": "unreal_editor" if real else "offline_fixture",
        "real_unreal_validation": real,
        "host_engine_version": "5.8.1-test" if real else None,
        "asset_count": 1,
        "issue_count": 1,
        "collection_failure_count": 1,
        "requested_asset_count": processed + cancelled,
        "processed_asset_count": processed,
        "cancelled_asset_count": cancelled,
        "completed_batch_count": 1,
        "batch_size": 2,
        "assets": [
            {
                "asset_path": "/Game/Demo/01_Light/A.A",
                "asset_name": "A",
                "lods": [{"index": 0, "triangles": 100, "vertices": 80}],
                "material_slot_count": 3,
                "nanite_enabled": False,
            }
        ],
        "issues": [
            {
                "schema_version": "unreal-asset-audit@1.0.0",
                "issue_id": "issue-1",
                "asset_path": "/Game/Demo/01_Light/A.A",
                "rule_id": "static_mesh.material_slots",
                "severity": "warning",
                "message": "Material slots exceed limit.",
                "evidence_id": "ev-1",
            }
        ],
        "evidence": [
            {
                "schema_version": "unreal-asset-audit@1.0.0",
                "evidence_id": "ev-1",
                "asset_path": "/Game/Demo/01_Light/A.A",
                "metric": "material_slot_count",
                "observed": 3,
                "expected": 2,
                "profile_pointer": "/rules/max_material_slots",
                "collector": "unreal_editor" if real else "offline_fixture",
            }
        ],
        "collection_failures": [
            {
                "schema_version": "unreal-asset-audit@1.0.0",
                "asset_path": "/Game/Demo/99_Broken/Bad.Bad",
                "code": "ASSET_NOT_FOUND",
                "message": "Asset does not exist.",
                "collector": "unreal_editor" if real else "offline_fixture",
            }
        ],
    }


def test_handoff_exports_standalone_chinese_html_csv_and_manifest(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    report_path.write_text(
        json.dumps(_report(real=True), ensure_ascii=False), encoding="utf-8"
    )

    result = export_handoff(report_path, tmp_path / "exports")

    page = result.html_path.read_text(encoding="utf-8")
    assert "Unreal 资产审计交接报告" in page
    assert "真实 Unreal 宿主采集" in page
    assert "5.8.1-test" in page
    assert "规则问题" in page
    csv_payload = result.csv_path.read_bytes()
    assert csv_payload.startswith(b"\xef\xbb\xbf")
    rows = list(csv.DictReader(io.StringIO(csv_payload.decode("utf-8-sig"))))
    assert [row["类型"] for row in rows] == ["规则问题", "采集失败"]
    assert rows[0]["实测"] == "3"
    assert rows[0]["期望"] == "2"
    assert rows[0]["级别"] == "警告"
    assert rows[0]["检查项"] == "材质槽"
    assert rows[0]["规则 ID"] == "static_mesh.material_slots"
    assert "超过 Profile 上限" in rows[0]["说明"]
    assert rows[0]["原始说明"] == "Material slots exceed limit."
    assert rows[0]["Profile 指针"] == "/rules/max_material_slots"
    group_payload = result.groups_csv_path.read_bytes()
    assert group_payload.startswith(b"\xef\xbb\xbf")
    groups = list(csv.DictReader(io.StringIO(group_payload.decode("utf-8-sig"))))
    assert [group["交付目录组"] for group in groups] == [
        "/Game/Demo/99_Broken",
        "/Game/Demo/01_Light",
    ]
    assert groups[0]["体检刻度"] == "采集阻断"
    assert groups[1]["问题/对象"] == "1.00"
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "unreal-audit-handoff@1.0.0"
    assert manifest["real_unreal_validation"] is True
    assert manifest["delivery_groups"]["schema_version"] == "unreal-audit-delivery-groups@1.0.0"
    assert manifest["delivery_groups"]["group_count"] == 2
    assert manifest["delivery_groups"]["performance_inference"] is False
    assert manifest["delivery_groups"]["groups_csv_sha256"] == hashlib.sha256(
        group_payload
    ).hexdigest()
    assert "href='#delivery-group-1'" in page
    assert "id='delivery-group-1'" in page
    assert "不是质量评分或运行时性能指标" in page
    for item in manifest["files"]:
        payload = (result.root / item["path"]).read_bytes()
        assert item["sha256"] == hashlib.sha256(payload).hexdigest()


def test_handoff_is_byte_deterministic_and_labels_fixture_boundary(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    report_path.write_text(
        json.dumps(_report(real=False, cancelled=4)), encoding="utf-8"
    )

    first = export_handoff(report_path, tmp_path / "one")
    second = export_handoff(report_path, tmp_path / "two")

    assert first.html_path.read_bytes() == second.html_path.read_bytes()
    assert first.csv_path.read_bytes() == second.csv_path.read_bytes()
    assert first.groups_csv_path.read_bytes() == second.groups_csv_path.read_bytes()
    assert first.manifest_path.read_bytes() == second.manifest_path.read_bytes()
    page = first.html_path.read_text(encoding="utf-8")
    assert "离线 Fixture 验证" in page
    assert "不能作为 Unreal 编译、加载或真实资产验证证据" in page
    assert "已取消，保留部分结果" in page


def test_handoff_includes_review_decisions_without_changing_report(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(_report(real=True), ensure_ascii=False), encoding="utf-8")
    before = report_path.read_bytes()
    reviews = tmp_path / "Reviews"
    update_review(
        report_path,
        reviews,
        issue_id="issue-1",
        evidence_id="ev-1",
        decision="fix_required",
        owner="场景组 / 阿岚",
        note="减少材质槽后重新提交",
    )
    ledger_path = reviews / "report-handoff.review.v1.json"
    ledger_before = ledger_path.read_bytes()

    result = export_handoff(report_path, tmp_path / "exports", reviews)
    rows = list(
        csv.DictReader(io.StringIO(result.csv_path.read_bytes().decode("utf-8-sig")))
    )
    assert rows[0]["审阅决定"] == "需修复"
    assert rows[0]["负责人"] == "场景组 / 阿岚"
    assert rows[0]["审阅备注"] == "减少材质槽后重新提交"
    assert "人工审阅" in result.html_path.read_text(encoding="utf-8")
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["review"]["reviewed_count"] == 1
    assert manifest["review"]["fix_required_count"] == 1
    assert manifest["review"]["ledger_file"] == "report-handoff.review.v1.json"
    assert len(manifest["review"]["ledger_sha256"]) == 64
    assert report_path.read_bytes() == before
    assert ledger_path.read_bytes() == ledger_before
    groups = list(
        csv.DictReader(
            io.StringIO(result.groups_csv_path.read_bytes().decode("utf-8-sig"))
        )
    )
    light_group = next(group for group in groups if group["交付目录组"].endswith("01_Light"))
    assert light_group["未复核"] == "0"
    assert light_group["需修复"] == "1"
    assert light_group["体检刻度"] == "需修复"


def test_handoff_rejects_incomplete_report(tmp_path: Path) -> None:
    report_path = tmp_path / "broken.json"
    report_path.write_text('{"report_id":"broken"}', encoding="utf-8")

    with pytest.raises(HandoffError, match="缺少交接所需字段"):
        export_handoff(report_path, tmp_path / "exports")
