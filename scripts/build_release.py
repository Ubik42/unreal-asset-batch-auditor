from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import zipfile
from collections.abc import Iterable
from pathlib import Path

RELEASE_SCHEMA_VERSION = "unreal-audit-release@1.0.0"
PLUGIN_NAME = "UnrealAssetBatchAuditor"
FIXED_ZIP_TIMESTAMP = (2020, 1, 1, 0, 0, 0)
WINDOWS_ABSOLUTE_PATH = re.compile(rb"(?<![A-Za-z0-9_])[A-Za-z]:[\\/]")


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _read_files(root: Path, patterns: Iterable[str]) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for pattern in patterns:
        for path in sorted(root.glob(pattern)):
            if path.is_file():
                files[path.relative_to(root).as_posix()] = path.read_bytes()
    return files


def _source_revision(repo_root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else "unknown"


def collect_release_entries(
    *,
    repo_root: Path,
    package_root: Path,
    tested_engine_version: str,
    source_revision: str,
) -> tuple[dict[str, bytes], dict[str, object]]:
    descriptor_path = package_root / f"{PLUGIN_NAME}.uplugin"
    if not descriptor_path.is_file():
        raise ValueError(f"打包插件描述文件不存在：{descriptor_path}")
    descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
    if descriptor.get("Installed") is not True:
        raise ValueError("输入必须是 Unreal BuildPlugin 产物，descriptor.Installed 应为 true")
    version = str(descriptor.get("VersionName", "")).strip()
    engine_compatibility = str(descriptor.get("EngineVersion", "")).strip()
    if not version or not engine_compatibility:
        raise ValueError("BuildPlugin descriptor 缺少 VersionName 或 EngineVersion")

    plugin_files = _read_files(
        package_root,
        (
            "Binaries/Win64/*.dll",
            "Binaries/Win64/*.modules",
            "Content/Python/*.py",
            "Content/Python/unreal_asset_batch_auditor/*.py",
            "Resources/Profiles/*.json",
            "Resources/ProjectPresets/*.json",
            "contracts/*.json",
            "Source/**/*.h",
            "Source/**/*.cpp",
            "Source/**/*.cs",
        ),
    )
    plugin_files = {
        path: content
        for path, content in plugin_files.items()
        if "/Private/Tests/" not in f"/{path}"
    }
    required_prefixes = (
        "Binaries/Win64/",
        "Content/Python/",
        "Resources/Profiles/",
        "Resources/ProjectPresets/",
        "contracts/",
        "Source/UnrealAssetBatchAuditor/",
    )
    for prefix in required_prefixes:
        if not any(path.startswith(prefix) for path in plugin_files):
            raise ValueError(f"发布输入缺少必要目录内容：{prefix}")

    descriptor_bytes = (
        json.dumps(descriptor, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")
    entries = {
        f"{PLUGIN_NAME}/{PLUGIN_NAME}.uplugin": descriptor_bytes,
        **{
            f"{PLUGIN_NAME}/{relative_path}": content
            for relative_path, content in plugin_files.items()
        },
    }

    release_notes_name = f"版本说明_v{version}.md"
    support_files = {
        "README_安装说明.md": repo_root / "docs" / "RELEASE_INSTALL.md",
        release_notes_name: repo_root / "docs" / "releases" / f"v{version}.md",
        "install-plugin.ps1": repo_root / "scripts" / "release" / "install-plugin.ps1",
        "run-unattended-audit.ps1": repo_root / "scripts" / "run_unattended_audit.ps1",
        "LICENSE.txt": repo_root / "LICENSE",
    }
    for archive_path, source_path in support_files.items():
        if not source_path.is_file():
            raise ValueError(f"发布支持文件不存在：{source_path}")
        entries[archive_path] = source_path.read_bytes()
    entries[f"{PLUGIN_NAME}/LICENSE.txt"] = (repo_root / "LICENSE").read_bytes()

    forbidden_roots = {
        str(repo_root.resolve()).replace("\\", "/").encode("utf-8").lower(),
        str(package_root.resolve()).replace("\\", "/").encode("utf-8").lower(),
    }
    text_suffixes = {".cs", ".cpp", ".h", ".json", ".md", ".ps1", ".py", ".txt", ".uplugin"}
    for archive_path, content in entries.items():
        if Path(archive_path).suffix.lower() not in text_suffixes:
            continue
        normalized = content.replace(b"\\", b"/").lower()
        if any(root in normalized for root in forbidden_roots) or WINDOWS_ABSOLUTE_PATH.search(content):
            raise ValueError(f"发布文件包含开发机绝对路径：{archive_path}")

    payload = [
        {
            "path": path,
            "bytes": len(content),
            "sha256": sha256_bytes(content),
        }
        for path, content in sorted(entries.items())
    ]
    payload_fingerprint = sha256_bytes(
        "".join(f"{item['sha256']}  {item['path']}\n" for item in payload).encode("utf-8")
    )
    manifest: dict[str, object] = {
        "schema_version": RELEASE_SCHEMA_VERSION,
        "plugin_name": PLUGIN_NAME,
        "plugin_version": version,
        "release_channel": "beta",
        "platform": "Win64",
        "tested_engine_version": tested_engine_version,
        "binary_engine_compatibility": engine_compatibility,
        "source_revision": source_revision,
        "install_scope": "project_plugin",
        "payload_file_count": len(payload),
        "payload_bytes": sum(int(item["bytes"]) for item in payload),
        "payload_tree_sha256": payload_fingerprint,
        "payload": payload,
        "claims": {
            "marketplace_ready": False,
            "cross_version_compatible": False,
            "contains_engine_derived_demo_assets": False,
        },
    }
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode(
        "utf-8"
    )
    entries["RELEASE-MANIFEST.json"] = manifest_bytes
    checksums = "".join(
        f"{sha256_bytes(content)}  {path}\n" for path, content in sorted(entries.items())
    ).encode("utf-8")
    entries["SHA256SUMS.txt"] = checksums
    return entries, manifest


def write_deterministic_zip(entries: dict[str, bytes], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        output_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        strict_timestamps=True,
    ) as archive:
        for archive_path, content in sorted(entries.items()):
            info = zipfile.ZipInfo(archive_path, date_time=FIXED_ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def build_release(
    *,
    repo_root: Path,
    package_root: Path,
    output_directory: Path,
    tested_engine_version: str,
    source_revision: str | None = None,
) -> dict[str, object]:
    revision = source_revision or _source_revision(repo_root)
    entries, manifest = collect_release_entries(
        repo_root=repo_root,
        package_root=package_root,
        tested_engine_version=tested_engine_version,
        source_revision=revision,
    )
    version = str(manifest["plugin_version"])
    engine_label = tested_engine_version.rsplit(".", 1)[0]
    archive_name = f"{PLUGIN_NAME}-{version}-UE{engine_label}-Win64.zip"
    output_path = output_directory / archive_name

    with tempfile.TemporaryDirectory(prefix="uaba-release-") as temp_root:
        first = Path(temp_root) / "first.zip"
        second = Path(temp_root) / "second.zip"
        write_deterministic_zip(entries, first)
        write_deterministic_zip(entries, second)
        first_hash = sha256_bytes(first.read_bytes())
        second_hash = sha256_bytes(second.read_bytes())
        if first_hash != second_hash:
            raise RuntimeError("相同输入的两次发布打包结果不一致")
        output_directory.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(first.read_bytes())

    archive_hash = sha256_bytes(output_path.read_bytes())
    checksum_path = output_path.with_suffix(output_path.suffix + ".sha256")
    checksum_path.write_text(f"{archive_hash}  {output_path.name}\n", encoding="utf-8")
    manifest_path = output_path.with_suffix(output_path.suffix + ".manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "schema_version": "unreal-audit-release-build@1.0.0",
        "archive_path": str(output_path),
        "archive_bytes": output_path.stat().st_size,
        "archive_sha256": archive_hash,
        "manifest_path": str(manifest_path),
        "checksum_path": str(checksum_path),
        "determinism_verified": True,
        "payload_tree_sha256": manifest["payload_tree_sha256"],
        "payload_file_count": manifest["payload_file_count"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="生成确定性的 Unreal Asset Batch Auditor 发布包")
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--tested-engine-version", required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--source-revision")
    args = parser.parse_args()
    result = build_release(
        repo_root=args.repo_root.resolve(),
        package_root=args.package_root.resolve(),
        output_directory=args.output_directory.resolve(),
        tested_engine_version=args.tested_engine_version,
        source_revision=args.source_revision,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
