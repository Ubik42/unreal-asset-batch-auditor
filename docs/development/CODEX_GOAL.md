# Product completion definition

Deliver a reproducible, project-Profile-driven Unreal Static Mesh auditor. Python owns configuration,
rule evaluation, reporting, and batch orchestration. An Editor-only C++ module owns bulk metadata
collection. Read-only scans must never modify `.uasset` files.

Completion requires versioned contracts, explicit evidence provenance, bounded batch collection,
failure reporting, real UE5 compile/host evidence, and measured performance on a representative
project. Offline fixtures are regression evidence only and have an explicit evidence ceiling.

The current MVP does not toggle Nanite, save packages, or claim production-scale performance. A
recorded UE 5.8.1 compile, host run, visible metadata review, and asset-integrity comparison now
establish the real-host evidence floor. The unique next slice is always recorded in
`config/goal-state.json`.

The scoped MVP completion gates were satisfied on 2026-08-25. The repository goal state and final
checkpoint record the exact evidence and limitations; future feature work requires a new goal rather
than silently expanding this one into asset mutation.
