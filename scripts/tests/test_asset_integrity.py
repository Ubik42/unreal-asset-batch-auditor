from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "asset_integrity", ROOT / "scripts" / "asset_integrity.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_snapshot_uses_relative_paths_and_detects_no_change(tmp_path: Path) -> None:
    content = tmp_path / "Content" / "Props"
    content.mkdir(parents=True)
    (content / "SM_Test.uasset").write_bytes(b"stable")
    before = MODULE.snapshot(tmp_path, "before")
    after = MODULE.snapshot(tmp_path, "after")
    assert before["assets"][0]["relative_path"] == "Content/Props/SM_Test.uasset"
    assert MODULE.compare(before, after)["unchanged"] is True


def test_compare_reports_changed_added_and_removed(tmp_path: Path) -> None:
    first = tmp_path / "A.uasset"
    removed = tmp_path / "Removed.uasset"
    first.write_bytes(b"before")
    removed.write_bytes(b"removed")
    before = MODULE.snapshot(tmp_path, "before")
    first.write_bytes(b"after")
    removed.unlink()
    (tmp_path / "Added.uasset").write_bytes(b"added")
    after = MODULE.snapshot(tmp_path, "after")
    result = MODULE.compare(before, after)
    assert result["unchanged"] is False
    assert result["changed"] == ["A.uasset"]
    assert result["added"] == ["Added.uasset"]
    assert result["removed"] == ["Removed.uasset"]
