# Unreal BuildPlugin attempts — 2026-08-25

Evidence status: **the initial environment blocker was recovered and UE 5.8.1 validation passed**.
The failed attempts below are retained as diagnostic history.

The same condition was rechecked for three consecutive `/goal` turns. Repository state revision 3
therefore records `M2-HOST-ENVIRONMENT` as a formal blocker with an explicit recovery condition.

## Host inventory

| Engine | Exact build | Result before plugin compilation |
| --- | --- | --- |
| UE 5.4.4 | changelist 35576357 | UBT stopped because NetFxSDK 4.6+ was not installed |
| UE 5.5.4 | changelist 40574608 | UBT stopped while loading an unrelated HoudiniEngine ModuleRules type |
| UE 5.8.1 | changelist 56057345 | UBT stopped because NetFxSDK 4.6+ was not installed |

All attempts used Epic `RunUAT BuildPlugin`, Win64, Rocket packaging, and generated an UnrealEditor
Development host target. In every case UBT failed while constructing engine/module rules, before UHT
or the compiler reached `UnrealAssetBatchAuditor` source files.

## Read-only header compatibility audit

The installed UE 5.4, 5.5, and 5.8 source headers were inspected after the failed builds. All three
contain the exact APIs used by the collector: `UStaticMesh::GetRenderData() const`, public
`FMeshNaniteSettings NaniteSettings`, and `FStaticMeshSection`. This is useful compatibility evidence,
but it is static header inspection—not UHT, compiler, linker, or runtime proof.

The Python orchestration package was moved to the plugin-standard `Content/Python` directory and a
wheel was built and inspected successfully. The wheel contains the same single implementation under
`unreal_asset_batch_auditor/`; the Editor and standalone test environment no longer depend on two
copies of the orchestration source. This proves Python packaging only, not Unreal plugin compilation.

Generated packaging directories are local runtime artifacts under `artifacts/host-build/` and are
Git-ignored. Authoritative full logs remain in AutomationTool's per-engine log directory on this
machine; this summary deliberately does not claim source compilation.

## Recovery and successful build

The user installed NetFxSDK 4.8. `scripts/build_plugin.ps1` was then rerun against UE 5.8.1.
UHT, `UnrealAssetBatchAuditorLibrary.cpp`, module compilation, linking, and Win64 Development Editor
packaging all completed with `BUILD SUCCESSFUL`. A UE 5.8 deprecation warning was removed by using
`UStaticMesh::GetNaniteSettings()` on 5.8 while retaining the field fallback for supported older
engines. The final clean package contains the current C++ and Python report implementation.

The packaged plugin was subsequently loaded by a disposable UE 5.8.1 project and produced the real
host artifacts in this directory. UE 5.4 and UE 5.5 were not rerun and remain unverified.
