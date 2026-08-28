from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from demo_audit_common import run_demo

run_demo("demo-review-lenient.v2.json")
