#if WITH_DEV_AUTOMATION_TESTS

#include "IPythonScriptPlugin.h"
#include "Interfaces/IPluginManager.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace
{
constexpr TCHAR TaskStateVersion[] = TEXT("unreal-audit-task-state@1.0.0");

struct FTaskPaths
{
    FString Request;
    FString State;
    FString Cancel;
    FString Report;
    FString Sessions;
    FString Handoffs;
    FString TaskId;
};

bool ReadJson(const FString& Path, TSharedPtr<FJsonObject>& OutRoot)
{
    FString Json;
    if (!FFileHelper::LoadFileToString(Json, *Path)) return false;
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
    return FJsonSerializer::Deserialize(Reader, OutRoot) && OutRoot.IsValid();
}

bool StartTask(
    FAutomationTestBase& Test, const FString& Root, const FString& ProfilePath,
    const FString& Label, const TArray<FString>& AssetPaths, int32 BatchSize,
    FTaskPaths& OutPaths)
{
    OutPaths.TaskId = FString::Printf(TEXT("task-%s"), *Label);
    const FString TaskRoot = FPaths::Combine(Root, Label);
    OutPaths.Request = FPaths::Combine(TaskRoot, TEXT("request.json"));
    OutPaths.State = FPaths::Combine(TaskRoot, TEXT("task-state.json"));
    OutPaths.Cancel = FPaths::Combine(TaskRoot, TEXT("cancel.json"));
    OutPaths.Report = FPaths::Combine(TaskRoot, TEXT("latest-report.json"));
    OutPaths.Sessions = FPaths::Combine(TaskRoot, TEXT("Sessions"));
    OutPaths.Handoffs = FPaths::Combine(TaskRoot, TEXT("Handoffs"));
    IFileManager::Get().MakeDirectory(*TaskRoot, true);
    IFileManager::Get().Delete(*OutPaths.State, false, true, true);
    IFileManager::Get().Delete(*OutPaths.Cancel, false, true, true);

    TSharedRef<FJsonObject> Request = MakeShared<FJsonObject>();
    Request->SetStringField(TEXT("task_id"), OutPaths.TaskId);
    Request->SetStringField(TEXT("profile_path"), ProfilePath);
    Request->SetStringField(TEXT("output_path"), OutPaths.Report);
    Request->SetStringField(TEXT("session_root"), OutPaths.Sessions);
    Request->SetStringField(TEXT("handoff_root"), OutPaths.Handoffs);
    Request->SetStringField(TEXT("state_path"), OutPaths.State);
    Request->SetStringField(TEXT("cancel_path"), OutPaths.Cancel);
    Request->SetNumberField(TEXT("batch_size"), BatchSize);
    TArray<TSharedPtr<FJsonValue>> Values;
    for (const FString& Path : AssetPaths) Values.Add(MakeShared<FJsonValueString>(Path));
    Request->SetArrayField(TEXT("asset_paths"), Values);
    FString Json;
    const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Json);
    FJsonSerializer::Serialize(Request, Writer);
    if (!FFileHelper::SaveStringToFile(
        Json, *OutPaths.Request, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM))
    {
        Test.AddError(FString::Printf(TEXT("Could not write task request: %s"), *OutPaths.Request));
        return false;
    }

    IPythonScriptPlugin* Python = IPythonScriptPlugin::Get();
    if (!Python || (!Python->IsPythonInitialized() && !Python->ForceEnablePythonAtRuntime()))
    {
        Test.AddError(TEXT("Python Script Plugin is not ready"));
        return false;
    }
    FString PythonPath = OutPaths.Request.Replace(TEXT("\\"), TEXT("/"));
    PythonPath.ReplaceInline(TEXT("'"), TEXT("\\'"));
    const FString Command = FString::Printf(
        TEXT("from unreal_asset_batch_auditor import start_panel_task; start_panel_task(r'%s')"),
        *PythonPath);
    if (!Python->ExecPythonCommand(*Command))
    {
        Test.AddError(FString::Printf(TEXT("Could not start panel task: %s"), *Label));
        return false;
    }
    return true;
}

class FPanelTaskLifecycleCommand final : public IAutomationLatentCommand
{
public:
    FPanelTaskLifecycleCommand(
        FAutomationTestBase& InTest, FString InRoot, FString InProfilePath,
        FTaskPaths InFullPaths, TArray<FString> InCancelAssets)
        : Test(InTest)
        , Root(MoveTemp(InRoot))
        , ProfilePath(MoveTemp(InProfilePath))
        , FullPaths(MoveTemp(InFullPaths))
        , CancelAssets(MoveTemp(InCancelAssets))
        , Deadline(FPlatformTime::Seconds() + 45.0)
    {
    }

    virtual bool Update() override
    {
        if (FPlatformTime::Seconds() > Deadline)
        {
            Test.AddError(TEXT("Panel task lifecycle timed out"));
            return true;
        }
        if (Stage == 0)
        {
            TSharedPtr<FJsonObject> State;
            if (!ReadJson(FullPaths.State, State)) return false;
            const FString Value = State->GetStringField(TEXT("state"));
            if (Value == TEXT("failed"))
            {
                Test.AddError(TEXT("Full panel task entered failed state"));
                return true;
            }
            if (Value != TEXT("completed")) return false;
            ValidateTerminal(FullPaths, State, TEXT("completed"), 5, 0);
            if (!StartTask(
                Test, Root, ProfilePath, TEXT("cancelled"), CancelAssets, 2, CancelPaths))
            {
                return true;
            }
            Stage = 1;
            return false;
        }
        TSharedPtr<FJsonObject> State;
        if (!ReadJson(CancelPaths.State, State)) return false;
        const FString Value = State->GetStringField(TEXT("state"));
        if (Value == TEXT("failed"))
        {
            Test.AddError(TEXT("Cancelled panel task entered failed state"));
            return true;
        }
        if (Stage == 1)
        {
            const int32 Processed = State->GetIntegerField(TEXT("processed_count"));
            if (Value == TEXT("completed"))
            {
                Test.AddError(TEXT("Task completed before between-batch cancellation was observed"));
                return true;
            }
            if (Value == TEXT("running") && Processed >= 2)
            {
                const FString CancelJson = TEXT("{\"schema_version\":\"unreal-audit-task-state@1.0.0\"}\n");
                if (!FFileHelper::SaveStringToFile(
                    CancelJson, *CancelPaths.Cancel,
                    FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM))
                {
                    Test.AddError(TEXT("Could not write cancellation request"));
                    return true;
                }
                Stage = 2;
            }
            return false;
        }
        if (Value != TEXT("cancelled")) return false;
        const int32 Processed = State->GetIntegerField(TEXT("processed_count"));
        const int32 Cancelled = State->GetIntegerField(TEXT("cancelled_count"));
        ValidateTerminal(CancelPaths, State, TEXT("cancelled"), Processed, Cancelled);
        Test.TestTrue(TEXT("Cancellation preserves completed batch"), Processed >= 2);
        Test.TestTrue(TEXT("Cancellation leaves unprocessed request scope"), Cancelled > 0);
        TSharedPtr<FJsonObject> Comparison;
        const FString ComparisonPath = FPaths::Combine(
            CancelPaths.Sessions, TEXT("latest-comparison.v1.json"));
        Test.TestTrue(
            TEXT("Cancelled session comparison exists"), ReadJson(ComparisonPath, Comparison));
        if (Comparison.IsValid())
        {
            Test.TestEqual(
                TEXT("Cancelled session is excluded from complete regression"),
                Comparison->GetStringField(TEXT("status")), FString(TEXT("incomplete_current")));
        }
        return true;
    }

private:
    void ValidateTerminal(
        const FTaskPaths& Paths, const TSharedPtr<FJsonObject>& State,
        const FString& ExpectedState, int32 ExpectedProcessed, int32 ExpectedCancelled)
    {
        Test.TestEqual(
            TEXT("Task state schema"), State->GetStringField(TEXT("schema_version")),
            FString(TaskStateVersion));
        Test.TestEqual(TEXT("Terminal state"), State->GetStringField(TEXT("state")), ExpectedState);
        Test.TestEqual(
            TEXT("Processed count"), State->GetIntegerField(TEXT("processed_count")),
            ExpectedProcessed);
        Test.TestEqual(
            TEXT("Cancelled count"), State->GetIntegerField(TEXT("cancelled_count")),
            ExpectedCancelled);
        Test.TestTrue(TEXT("Terminal Report exists"), FPaths::FileExists(Paths.Report));
        if (ExpectedState == TEXT("completed"))
        {
            TSharedPtr<FJsonObject> Report;
            Test.TestTrue(TEXT("v3 Report is parseable"), ReadJson(Paths.Report, Report));
            if (Report.IsValid())
            {
                Test.TestEqual(
                    TEXT("Material dependency Report schema"),
                    Report->GetStringField(TEXT("schema_version")),
                    FString(TEXT("unreal-asset-audit@3.0.0")));
                bool bFoundMaterial = false;
                bool bFoundTexture = false;
                for (const TSharedPtr<FJsonValue>& Value : Report->GetArrayField(TEXT("assets")))
                {
                    const TSharedPtr<FJsonObject> Asset = Value->AsObject();
                    if (!Asset.IsValid()) continue;
                    bFoundMaterial |= Asset->GetIntegerField(TEXT("unique_material_count")) > 0;
                    bFoundTexture |= Asset->GetIntegerField(TEXT("texture_dependency_count")) > 0;
                }
                Test.TestTrue(TEXT("Real Static Mesh exposes an assigned material"), bFoundMaterial);
                Test.TestTrue(TEXT("Real material exposes at least one used texture"), bFoundTexture);
                TSet<FString> IssueRules;
                for (const TSharedPtr<FJsonValue>& Value : Report->GetArrayField(TEXT("issues")))
                {
                    const TSharedPtr<FJsonObject> Issue = Value->AsObject();
                    if (Issue.IsValid()) IssueRules.Add(Issue->GetStringField(TEXT("rule_id")));
                }
                Test.TestTrue(
                    TEXT("Real texture dependency exceeds evidence Profile"),
                    IssueRules.Contains(TEXT("static_mesh.texture_dependencies")));
                Test.TestTrue(
                    TEXT("Real texture dimension exceeds evidence Profile"),
                    IssueRules.Contains(TEXT("static_mesh.texture_dimension")));
            }
        }
        const FString HandoffPath = State->GetStringField(TEXT("handoff_path"));
        Test.TestTrue(TEXT("Handoff HTML exists"), FPaths::FileExists(FPaths::Combine(HandoffPath, TEXT("审计交接报告.html"))));
        Test.TestTrue(TEXT("Handoff CSV exists"), FPaths::FileExists(FPaths::Combine(HandoffPath, TEXT("审计问题明细.csv"))));
        Test.TestTrue(TEXT("Handoff manifest exists"), FPaths::FileExists(FPaths::Combine(HandoffPath, TEXT("交接清单.json"))));
    }

    FAutomationTestBase& Test;
    FString Root;
    FString ProfilePath;
    FTaskPaths FullPaths;
    FTaskPaths CancelPaths;
    TArray<FString> CancelAssets;
    double Deadline;
    int32 Stage = 0;
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FUnrealAssetBatchAuditorPanelTaskLifecycleTest,
    "UnrealAssetBatchAuditor.PanelTaskLifecycle",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)

bool FUnrealAssetBatchAuditorPanelTaskLifecycleTest::RunTest(const FString& Parameters)
{
    const TSharedPtr<IPlugin> Plugin = IPluginManager::Get().FindPlugin(TEXT("UnrealAssetBatchAuditor"));
    if (!Plugin.IsValid())
    {
        AddError(TEXT("Plugin descriptor was not found"));
        return false;
    }
    const FString ProfilePath = FPaths::Combine(
        Plugin->GetBaseDir(), TEXT("Resources/Profiles/host-material-evidence.v3.json"));
    const FString Root = FPaths::Combine(
        FPaths::ProjectSavedDir(), TEXT("UnrealAssetBatchAuditor/TaskLifecycleEvidence"));
    const TArray<FString> BasicShapes = {
        TEXT("/Engine/BasicShapes/Cone.Cone"),
        TEXT("/Engine/BasicShapes/Cube.Cube"),
        TEXT("/Engine/BasicShapes/Cylinder.Cylinder"),
        TEXT("/Engine/BasicShapes/Sphere.Sphere"),
        TEXT("/Engine/Functions/Engine_MaterialFunctions02/ExampleContent/TextureBasedWPO/DemoBoxMesh.DemoBoxMesh")};
    FTaskPaths FullPaths;
    if (!StartTask(*this, Root, ProfilePath, TEXT("completed"), BasicShapes, 2, FullPaths))
    {
        return false;
    }
    TArray<FString> CancelAssets;
    for (int32 Index = 0; Index < 4; ++Index) CancelAssets.Append(BasicShapes);
    ADD_LATENT_AUTOMATION_COMMAND(FPanelTaskLifecycleCommand(
        *this, Root, ProfilePath, FullPaths, CancelAssets));
    return true;
}

#endif
