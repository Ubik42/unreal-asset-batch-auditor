# Codex /goal loop

Resume from `config/goal-state.json`, then the referenced checkpoint, current code/tests, and
`CODEX_GOAL.md`. Chat history is not a progress database. Run `scripts/goal.ps1 -Action Doctor`
before implementation.

Only one milestone and slice may be in progress. Each slice declares scope, non-goals, evidence
ceiling, real-host requirement, acceptance criteria, and fixed validation entry points. Commands in
JSON are review metadata and must never be dynamically executed.

After acceptance passes, write the next numbered checkpoint and atomically advance the state
revision, milestone, and next slice. Do not promote an offline fixture to real-host evidence. Real
Unreal compilation and visible Editor testing remain a manual track until actually performed.
