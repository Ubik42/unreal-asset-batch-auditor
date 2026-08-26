from __future__ import annotations

import argparse
from pathlib import Path

from .audit import audit_assets
from .collectors import FixtureCollector
from .contracts import AuditProfile


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run an offline Static Mesh audit fixture.")
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = audit_assets(
        profile=AuditProfile.load(args.profile), collector=FixtureCollector(args.fixture)
    )
    report.write(args.out)
    print(
        f"offline fixture audit: {report.asset_count} assets, {report.issue_count} issues, "
        f"{report.collection_failure_count} collection failures; "
        "real_unreal_validation=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
