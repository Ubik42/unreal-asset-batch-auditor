from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_plugin_module_is_editor_only() -> None:
    descriptor = json.loads((ROOT / "UnrealAssetBatchAuditor.uplugin").read_text(encoding="utf-8"))
    assert descriptor["Modules"] == [
        {"Name": "UnrealAssetBatchAuditor", "Type": "Editor", "LoadingPhase": "Default"}
    ]


def test_cpp_boundary_is_batch_read_only_and_has_no_mutation_surface() -> None:
    header = (
        ROOT
        / "Source"
        / "UnrealAssetBatchAuditor"
        / "Public"
        / "UnrealAssetBatchAuditorLibrary.h"
    ).read_text(encoding="utf-8")
    implementation = (
        ROOT
        / "Source"
        / "UnrealAssetBatchAuditor"
        / "Private"
        / "UnrealAssetBatchAuditorLibrary.cpp"
    ).read_text(encoding="utf-8")
    assert "CollectStaticMeshMetadata" in header
    assert "TArray<FString>" in header
    forbidden = ("SavePackage", "Modify()", "Build(", "MarkPackageDirty", "SetNanite")
    assert not any(token in implementation for token in forbidden)


def test_all_json_files_parse() -> None:
    for path in [*ROOT.glob("contracts/*.json"), *ROOT.glob("config/Profiles/*.json")]:
        json.loads(path.read_text(encoding="utf-8"))
