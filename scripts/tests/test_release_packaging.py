from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

from scripts.build_release import build_release

ROOT = Path(__file__).resolve().parents[2]


def _write(path: Path, content: str | bytes = "fixture") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")


def _fake_build_plugin(root: Path) -> Path:
    descriptor = {
        "FileVersion": 3,
        "Version": 16,
        "VersionName": "0.10.0",
        "FriendlyName": "Unreal 资产批量审计",
        "EngineVersion": "5.8.0",
        "Installed": True,
        "Modules": [
            {"Name": "UnrealAssetBatchAuditor", "Type": "Editor", "LoadingPhase": "Default"}
        ],
    }
    _write(
        root / "UnrealAssetBatchAuditor.uplugin",
        json.dumps(descriptor, ensure_ascii=False),
    )
    _write(root / "Binaries/Win64/UnrealEditor-UnrealAssetBatchAuditor.dll", b"dll")
    _write(root / "Binaries/Win64/UnrealEditor.modules", "{}")
    _write(root / "Binaries/Win64/debug.pdb", b"pdb")
    _write(root / "Content/Python/init_unreal.py", "READY = True\n")
    _write(root / "Content/Python/unreal_asset_batch_auditor/audit.py", "VALUE = 1\n")
    _write(root / "Content/Python/unreal_asset_batch_auditor/texture_audit.py", "VALUE = 2\n")
    _write(root / "Content/Python/__pycache__/audit.pyc", b"cache")
    _write(root / "Resources/Profiles/desktop-balanced.v2.json", "{}")
    _write(root / "Resources/Profiles/texture-desktop-balanced.v1.json", "{}")
    _write(root / "Resources/ProjectPresets/engine-basic-shapes-ci.v1.json", "{}")
    _write(root / "contracts/project-preset.v1.schema.json", "{}")
    _write(root / "contracts/unattended-run.v1.schema.json", "{}")
    _write(root / "contracts/texture-profile.v1.schema.json", "{}")
    _write(root / "contracts/texture-report.v1.schema.json", "{}")
    _write(root / "Source/UnrealAssetBatchAuditor/Module.Build.cs", "class Module {}\n")
    _write(root / "Source/UnrealAssetBatchAuditor/Public/Module.h", "#pragma once\n")
    _write(root / "Source/UnrealAssetBatchAuditor/Private/Module.cpp", "// source\n")
    _write(root / "Source/UnrealAssetBatchAuditor/Private/Tests/Test.cpp", "// test\n")
    _write(root / "Intermediate/generated.obj", b"obj")
    return root


def test_release_is_deterministic_and_uses_a_strict_allowlist(tmp_path: Path) -> None:
    package = _fake_build_plugin(tmp_path / "package")
    first = build_release(
        repo_root=ROOT,
        package_root=package,
        output_directory=tmp_path / "first",
        tested_engine_version="5.8.1",
        source_revision="fixture-revision",
    )
    second = build_release(
        repo_root=ROOT,
        package_root=package,
        output_directory=tmp_path / "second",
        tested_engine_version="5.8.1",
        source_revision="fixture-revision",
    )
    first_bytes = Path(str(first["archive_path"])).read_bytes()
    second_bytes = Path(str(second["archive_path"])).read_bytes()
    assert first_bytes == second_bytes
    assert first["archive_sha256"] == hashlib.sha256(first_bytes).hexdigest()
    assert first["determinism_verified"] is True

    with zipfile.ZipFile(Path(str(first["archive_path"]))) as archive:
        names = set(archive.namelist())
        assert "UnrealAssetBatchAuditor/UnrealAssetBatchAuditor.uplugin" in names
        assert "UnrealAssetBatchAuditor/Binaries/Win64/UnrealEditor-UnrealAssetBatchAuditor.dll" in names
        assert "install-plugin.ps1" in names
        assert "run-unattended-audit.ps1" in names
        assert "README_安装说明.md" in names
        assert "版本说明_v0.10.0.md" in names
        assert "RELEASE-MANIFEST.json" in names
        assert "SHA256SUMS.txt" in names
        assert "UnrealAssetBatchAuditor/Resources/ProjectPresets/engine-basic-shapes-ci.v1.json" in names
        assert "UnrealAssetBatchAuditor/contracts/project-preset.v1.schema.json" in names
        assert "UnrealAssetBatchAuditor/Resources/Profiles/texture-desktop-balanced.v1.json" in names
        assert "UnrealAssetBatchAuditor/contracts/texture-profile.v1.schema.json" in names
        assert "UnrealAssetBatchAuditor/contracts/texture-report.v1.schema.json" in names
        assert not any("Intermediate" in name for name in names)
        assert not any("__pycache__" in name or name.endswith((".pyc", ".pdb")) for name in names)
        assert not any("/Private/Tests/" in name for name in names)
        manifest = json.loads(archive.read("RELEASE-MANIFEST.json"))
        assert manifest["tested_engine_version"] == "5.8.1"
        assert manifest["source_revision"] == "fixture-revision"
        assert manifest["claims"] == {
            "marketplace_ready": False,
            "cross_version_compatible": False,
            "contains_engine_derived_demo_assets": False,
        }
        checksum_lines = archive.read("SHA256SUMS.txt").decode("utf-8").splitlines()
        assert len(checksum_lines) == len(names) - 1


def test_release_rejects_non_buildplugin_input(tmp_path: Path) -> None:
    package = _fake_build_plugin(tmp_path / "package")
    descriptor_path = package / "UnrealAssetBatchAuditor.uplugin"
    descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
    descriptor["Installed"] = False
    descriptor_path.write_text(json.dumps(descriptor), encoding="utf-8")
    try:
        build_release(
            repo_root=ROOT,
            package_root=package,
            output_directory=tmp_path / "out",
            tested_engine_version="5.8.1",
            source_revision="fixture-revision",
        )
    except ValueError as exc:
        assert "BuildPlugin" in str(exc)
    else:
        raise AssertionError("Expected non-BuildPlugin input to be rejected")


def test_release_install_upgrade_and_recoverable_uninstall(tmp_path: Path) -> None:
    if shutil.which("pwsh") is None:
        raise AssertionError("Windows release lifecycle test requires pwsh")
    package = _fake_build_plugin(tmp_path / "package")
    result = build_release(
        repo_root=ROOT,
        package_root=package,
        output_directory=tmp_path / "release-output",
        tested_engine_version="5.8.1",
        source_revision="fixture-revision",
    )
    extracted = tmp_path / "release"
    with zipfile.ZipFile(Path(str(result["archive_path"]))) as archive:
        archive.extractall(extracted)
    project = tmp_path / "Project"
    _write(project / "ReleaseTest.uproject", '{"FileVersion": 3}\n')
    script = extracted / "install-plugin.ps1"

    def run(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["pwsh", "-NoProfile", "-File", str(script), *arguments],
            check=check,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    run("-Action", "Install", "-ProjectPath", str(project))
    installed = project / "Plugins/UnrealAssetBatchAuditor"
    assert (installed / "UnrealAssetBatchAuditor.uplugin").is_file()
    project_descriptor = json.loads((project / "ReleaseTest.uproject").read_text(encoding="utf-8-sig"))
    assert {entry["Name"]: entry["Enabled"] for entry in project_descriptor["Plugins"]} == {
        "UnrealAssetBatchAuditor": True
    }

    installed_descriptor = json.loads(
        (installed / "UnrealAssetBatchAuditor.uplugin").read_text(encoding="utf-8")
    )
    installed_descriptor["VersionName"] = "0.7.0"
    (installed / "UnrealAssetBatchAuditor.uplugin").write_text(
        json.dumps(installed_descriptor, ensure_ascii=False), encoding="utf-8"
    )
    run("-Action", "Upgrade", "-ProjectPath", str(project))
    backups = list((project / "PluginBackups").glob("UnrealAssetBatchAuditor-0.7.0-*"))
    assert len(backups) == 1

    refused = run("-Action", "Uninstall", "-ProjectPath", str(project), check=False)
    assert refused.returncode != 0
    assert installed.is_dir()
    run(
        "-Action",
        "Uninstall",
        "-ProjectPath",
        str(project),
        "-ConfirmUninstall",
    )
    assert not installed.exists()
    assert any((project / "PluginBackups").glob("*-uninstalled-*"))
    project_descriptor = json.loads((project / "ReleaseTest.uproject").read_text(encoding="utf-8-sig"))
    assert not any(
        entry["Name"] == "UnrealAssetBatchAuditor"
        for entry in project_descriptor.get("Plugins", [])
    )
