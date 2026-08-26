from __future__ import annotations

import json
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
    assert all(item["matches_source_metadata"] for item in manifest["assets"])
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
