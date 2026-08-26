from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

SCHEMA = "unreal-asset-integrity-manifest@1.0.0"


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot(root: Path, label: str) -> dict:
    root = root.resolve(strict=True)
    files = sorted(path for path in root.rglob("*.uasset") if path.is_file())
    if not files:
        raise ValueError(f"no .uasset files found under {root}")
    return {
        "schema_version": SCHEMA,
        "label": label,
        "created_at": datetime.now(UTC).isoformat(),
        "algorithm": "sha256",
        "assets": [
            {"relative_path": path.relative_to(root).as_posix(), "sha256": hash_file(path)}
            for path in files
        ],
    }


def compare(before: dict, after: dict) -> dict:
    if before.get("schema_version") != SCHEMA or after.get("schema_version") != SCHEMA:
        raise ValueError("unsupported integrity manifest schema")
    left = {item["relative_path"]: item["sha256"] for item in before["assets"]}
    right = {item["relative_path"]: item["sha256"] for item in after["assets"]}
    changed = sorted(path for path in left.keys() & right.keys() if left[path] != right[path])
    result = {
        "schema_version": "unreal-asset-integrity-comparison@1.0.0",
        "before_label": before["label"],
        "after_label": after["label"],
        "unchanged": not changed and left.keys() == right.keys(),
        "changed": changed,
        "added": sorted(right.keys() - left.keys()),
        "removed": sorted(left.keys() - right.keys()),
    }
    return result


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prove that audited .uasset files were not changed.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    snapshot_parser = subparsers.add_parser("snapshot")
    snapshot_parser.add_argument("--root", type=Path, required=True)
    snapshot_parser.add_argument("--label", required=True)
    snapshot_parser.add_argument("--out", type=Path, required=True)
    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("--before", type=Path, required=True)
    compare_parser.add_argument("--after", type=Path, required=True)
    compare_parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if args.command == "snapshot":
        write_json(args.out, snapshot(args.root, args.label))
        return 0
    before = json.loads(args.before.read_text(encoding="utf-8"))
    after = json.loads(args.after.read_text(encoding="utf-8"))
    result = compare(before, after)
    write_json(args.out, result)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["unchanged"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
