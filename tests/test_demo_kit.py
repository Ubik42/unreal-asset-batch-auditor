from __future__ import annotations

import json
import struct
from pathlib import Path

from unreal_asset_batch_auditor import AuditProfile

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "Demo"
ARTIFACTS = ROOT / "artifacts" / "demo"


def test_demo_manifest_has_24_real_project_assets_and_two_diagnostics() -> None:
    manifest = json.loads((DEMO / "demo-asset-manifest.json").read_text(encoding="utf-8"))
    assert manifest["engine_version"].startswith("5.8.1-")
    assert manifest["asset_count"] == 24
    assert len(manifest["valid_asset_paths"]) == 24
    assert len(manifest["diagnostic_paths"]) == 2
    assert {item["group"] for item in manifest["assets"]} == {
        "01_Light",
        "02_Medium",
        "03_Heavy",
    }
    assert all(
        item["matches_source_metadata"] or item["intentional_variation"]
        for item in manifest["assets"]
    )
    synthetic = [item for item in manifest["assets"] if item["intentional_variation"]]
    assert len(synthetic) == 1
    assert synthetic[0]["demo_metadata"]["simple_collision_primitive_count"] == 0
    assert synthetic[0]["demo_metadata"]["lightmap_resolution"] == 8
    for object_path in manifest["valid_asset_paths"]:
        package_path = object_path.split(".", 1)[0].removeprefix("/Game/")
        assert (DEMO / "Content" / f"{package_path}.uasset").is_file()


def test_demo_profiles_are_versioned_and_explicitly_training_data() -> None:
    for path in sorted((DEMO / "Profiles").glob("*.json")):
        profile = AuditProfile.load(path)
        assert profile.profile_id.startswith("demo-")
        assert "training" in profile.description.lower()


def test_recorded_demo_sessions_cover_real_mixed_and_strict_scenarios() -> None:
    expected = {
        "demo-desktop-balanced": (15, 21),
        "demo-mobile-strict": (0, 87),
        "demo-review-lenient": (18, 13),
    }
    for profile_id, (expected_passing, expected_issues) in expected.items():
        report = json.loads((ARTIFACTS / f"{profile_id}-report.json").read_text(encoding="utf-8"))
        session = json.loads((ARTIFACTS / f"{profile_id}-session.json").read_text(encoding="utf-8"))
        affected = {item["asset_path"] for item in report["issues"]}
        assert report["collection_mode"] == "unreal_editor"
        assert report["real_unreal_validation"] is True
        assert report["asset_count"] == 24
        assert report["requested_asset_count"] == 26
        assert report["collection_failure_count"] == 2
        assert report["issue_count"] == expected_issues
        assert report["asset_count"] - len(affected) == expected_passing
        assert session["integrity"] == {
            "algorithm": "sha256",
            "hashed_asset_count": 24,
            "unchanged": True,
            "changed": [],
        }


def test_recorded_v2_demo_sessions_cover_collision_and_lightmap_scenarios() -> None:
    expected = {
        "demo-desktop-balanced-v2": {"issues": 43, "collision": 10, "uv": 8, "resolution": 4},
        "demo-mobile-strict-v2": {"issues": 111, "collision": 11, "uv": 8, "resolution": 5},
        "demo-review-lenient-v2": {"issues": 17, "collision": 0, "uv": 0, "resolution": 4},
    }
    for profile_id, counts in expected.items():
        report = json.loads((ARTIFACTS / f"{profile_id}-report.json").read_text(encoding="utf-8"))
        session = json.loads((ARTIFACTS / f"{profile_id}-session.json").read_text(encoding="utf-8"))
        rule_ids = [item["rule_id"] for item in report["issues"]]

        assert report["schema_version"] == "unreal-asset-audit@2.0.0"
        assert report["real_unreal_validation"] is True
        assert report["asset_count"] == 24
        assert report["issue_count"] == counts["issues"]
        assert rule_ids.count("static_mesh.simple_collision") == counts["collision"]
        assert rule_ids.count("static_mesh.lightmap_uv") == counts["uv"]
        assert rule_ids.count("static_mesh.lightmap_resolution") == counts["resolution"]
        assert session["integrity"]["unchanged"] is True


def test_current_panel_evidence_contains_eight_real_slate_pngs() -> None:
    image_root = ROOT / "docs" / "images" / "workflow" / "v0.4"
    expected = [
        "01-empty-state.png",
        "02-asset-overview.png",
        "03-passing-assets.png",
        "04-assets-needing-work.png",
        "05-issue-details.png",
        "06-triangle-evidence.png",
        "07-material-evidence.png",
        "08-collection-failures.png",
    ]

    assert [path.name for path in sorted(image_root.glob("*.png"))] == expected
    for filename in expected:
        payload = (image_root / filename).read_bytes()
        assert payload.startswith(b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", payload[16:24])
        assert (width, height) == (1280, 688)
        assert len(payload) > 50_000


def test_v05_panel_evidence_covers_collision_and_lightmap() -> None:
    image_root = ROOT / "docs" / "images" / "workflow" / "v0.5"
    expected = [
        "01-empty-state.png",
        "02-asset-overview.png",
        "03-passing-assets.png",
        "04-assets-needing-work.png",
        "05-issue-details.png",
        "06-collision-evidence.png",
        "07-lightmap-uv-evidence.png",
        "08-lightmap-resolution-evidence.png",
    ]

    assert [path.name for path in sorted(image_root.glob("*.png"))] == expected
    for filename in expected:
        payload = (image_root / filename).read_bytes()
        assert payload.startswith(b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", payload[16:24])
        assert (width, height) == (1280, 688)
        assert len(payload) > 50_000

    manifest = json.loads(
        (
            ROOT
            / "artifacts"
            / "host-validation"
            / "m5"
            / "panel-evidence-v0.5.0-dev3.json"
        ).read_text(encoding="utf-8")
    )
    assert manifest["automation_result"] == "Success"
    assert manifest["claims_slate_rendering"] is True
    assert manifest["claims_user_interaction"] is False
    assert len(manifest["screenshots"]) == 8
