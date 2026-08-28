from __future__ import annotations

import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any

SCHEMA_VERSION = "codex-goal-state@1.0.0"
SAFE_VALIDATION_PREFIXES = (
    ".\\.venv\\Scripts\\python.exe -m pytest",
    ".\\.venv\\Scripts\\python.exe -m ruff check",
)


def validate(state: dict[str, Any], root: Path) -> list[str]:
    errors: list[str] = []
    if state.get("schemaVersion") != SCHEMA_VERSION:
        errors.append("schemaVersion mismatch")
    goal_id = state.get("goalId")
    if not isinstance(goal_id, str) or not goal_id.strip():
        errors.append("goalId must be a non-empty string")
    if not isinstance(state.get("stateRevision"), int) or state["stateRevision"] < 1:
        errors.append("stateRevision must be a positive integer")

    milestones = state.get("milestones", [])
    ids = [item.get("id") for item in milestones]
    if len(ids) != len(set(ids)) or any(not item for item in ids):
        errors.append("milestone ids must be unique and non-empty")
    known = set(ids)
    status_by_id = {item.get("id"): item.get("status") for item in milestones}
    for item in milestones:
        for dependency in item.get("dependsOn", []):
            if dependency not in known:
                errors.append(f"unknown dependency: {dependency}")
            elif item.get("status") == "completed" and status_by_id.get(dependency) != "completed":
                errors.append(f"completed milestone {item.get('id')} has incomplete dependency")

    active = [item.get("id") for item in milestones if item.get("status") == "in_progress"]
    if state.get("status") == "active":
        if len(active) != 1:
            errors.append("active goal must have exactly one in_progress milestone")
        if state.get("currentMilestone") not in active:
            errors.append("currentMilestone must identify the in_progress milestone")
        if state.get("currentBlocker") is not None:
            errors.append("active goal cannot have currentBlocker")
    elif state.get("status") == "blocked":
        if len(active) != 1 or state.get("currentMilestone") not in active:
            errors.append("blocked goal must preserve exactly one in_progress current milestone")
        blocker = state.get("currentBlocker")
        if not isinstance(blocker, dict):
            errors.append("blocked goal requires currentBlocker")
        else:
            if blocker.get("consecutiveGoalTurns", 0) < 3:
                errors.append("blocked goal requires at least three consecutive blocked turns")
            if not blocker.get("condition") or not blocker.get("recovery"):
                errors.append("currentBlocker requires condition and recovery")

    next_slice = state.get("nextSlice")
    if state.get("status") in {"active", "blocked"} and not isinstance(next_slice, dict):
        errors.append("active or blocked goal requires nextSlice")
    if isinstance(next_slice, dict):
        if next_slice.get("milestoneId") != state.get("currentMilestone"):
            errors.append("nextSlice milestoneId must match currentMilestone")
        for allowed in next_slice.get("allowedPaths", []):
            path = PurePosixPath(str(allowed).replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts:
                errors.append(f"unsafe allowedPath: {allowed}")
        for command in next_slice.get("validationCommands", []):
            if not command.startswith(SAFE_VALIDATION_PREFIXES):
                errors.append(f"unsafe validation command declaration: {command}")

    checkpoint = state.get("lastCheckpoint")
    if not isinstance(checkpoint, str) or not (root / checkpoint).is_file():
        errors.append("lastCheckpoint does not exist")
    else:
        payload = json.loads((root / checkpoint).read_text(encoding="utf-8"))
        if payload.get("goalId") != goal_id:
            errors.append("checkpoint goalId mismatch")
        if payload.get("stateRevision") != state.get("stateRevision"):
            errors.append("checkpoint stateRevision mismatch")
        expected = next_slice.get("id") if isinstance(next_slice, dict) else None
        if payload.get("nextSlice") != expected:
            errors.append("checkpoint nextSlice mismatch")
    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    state = json.loads((root / "config" / "goal-state.json").read_text(encoding="utf-8"))
    errors = validate(state, root)
    result = {
        "schema": "codex-goal-audit@1.0.0",
        "status": "failed" if errors else "passed",
        "goalId": state.get("goalId"),
        "stateRevision": state.get("stateRevision"),
        "currentMilestone": state.get("currentMilestone"),
        "nextSlice": (state.get("nextSlice") or {}).get("id"),
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
