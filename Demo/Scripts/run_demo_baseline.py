from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from demo_audit_common import run_demo

run_demo(
    "demo-desktop-balanced.v2.json",
    manifest_filename="demo-baseline-asset-manifest.json",
    output_stem="demo-desktop-balanced-v2-baseline",
)
