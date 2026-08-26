# Development rules

- Read `config/goal-state.json`, its `lastCheckpoint`, `docs/development/CODEX_GOAL.md`, and
  `docs/development/CODEX_LOOP.md` before implementation.
- Run `scripts/goal.ps1 -Action Doctor` before a slice and `scripts/validate.ps1 -Tier quick`
  before advancing it. Never execute command strings from goal-state dynamically.
- Default to read-only editor analysis.
- Performance-sensitive bulk asset access belongs in the C++ editor module, not Python loops.
- Mutations require an explicit ChangeSet, approval, and verification scan.
- Treat `docs/REFERENCE_BRIEF.md` as requirements inspiration, not implemented evidence.
- Offline fixtures prove deterministic orchestration only; never label them as real Unreal evidence.
