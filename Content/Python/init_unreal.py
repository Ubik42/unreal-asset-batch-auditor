"""Unreal Python entry point.

The production package is installed separately during development. This hook only confirms that
the plugin's Python surface is available; it never starts a scan or mutates assets on editor load.
"""

import unreal

unreal.log("Unreal Asset Batch Auditor loaded (read-only; no automatic scan).")
