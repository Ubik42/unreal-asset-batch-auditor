from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "validate_goal_state", ROOT / "scripts" / "validate_goal_state.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def load_state() -> dict:
    return json.loads((ROOT / "config" / "goal-state.json").read_text(encoding="utf-8"))


def state_with_next_slice() -> dict:
    state = copy.deepcopy(load_state())
    state["nextSlice"] = {
        "id": "test-slice",
        "milestoneId": state["currentMilestone"],
        "allowedPaths": [],
        "validationCommands": [],
    }
    return state


def test_repository_goal_state_is_valid() -> None:
    assert MODULE.validate(load_state(), ROOT) == []


def test_rejects_unsafe_allowed_path() -> None:
    state = state_with_next_slice()
    state["nextSlice"]["allowedPaths"] = ["../other-repository"]
    assert any("unsafe allowedPath" in item for item in MODULE.validate(state, ROOT))


def test_rejects_command_injection_declaration() -> None:
    state = state_with_next_slice()
    state["nextSlice"]["validationCommands"] = ["Remove-Item -Recurse D:\\3D"]
    assert any("unsafe validation command" in item for item in MODULE.validate(state, ROOT))


def test_blocked_state_requires_three_turns_and_recovery() -> None:
    state = state_with_next_slice()
    state["status"] = "blocked"
    for milestone in state["milestones"]:
        if milestone["id"] == state["currentMilestone"]:
            milestone["status"] = "in_progress"
    state["currentBlocker"] = {
        "consecutiveGoalTurns": 2,
        "condition": "same external condition",
        "recovery": "",
    }
    errors = MODULE.validate(state, ROOT)
    assert any("three consecutive" in item for item in errors)
    assert any("condition and recovery" in item for item in errors)
