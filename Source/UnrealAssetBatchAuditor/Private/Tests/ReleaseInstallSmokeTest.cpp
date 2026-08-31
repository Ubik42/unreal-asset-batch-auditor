#if WITH_DEV_AUTOMATION_TESTS

#include "UnrealAssetBatchAuditorModule.h"

#include "Framework/Docking/TabManager.h"
#include "HAL/PlatformMisc.h"
#include "IPythonScriptPlugin.h"
#include "Interfaces/IPluginManager.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Widgets/Docking/SDockTab.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FUnrealAssetBatchAuditorReleaseInstallSmokeTest,
    "UnrealAssetBatchAuditor.ReleaseInstallSmoke",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)

bool FUnrealAssetBatchAuditorReleaseInstallSmokeTest::RunTest(const FString& Parameters)
{
    const FString ExpectedRootFromEnvironment =
        FPlatformMisc::GetEnvironmentVariable(TEXT("UABA_RELEASE_PLUGIN_ROOT"));
    if (ExpectedRootFromEnvironment.IsEmpty())
    {
        AddInfo(TEXT("Skipped: UABA_RELEASE_PLUGIN_ROOT is only supplied by the release-install validation workflow."));
        return true;
    }

    const TSharedPtr<IPlugin> Plugin = IPluginManager::Get().FindPlugin(TEXT("UnrealAssetBatchAuditor"));
    if (!TestTrue(TEXT("Release plugin is discovered"), Plugin.IsValid())) return false;
    TestTrue(TEXT("BuildPlugin descriptor is installed"), Plugin->GetDescriptor().bInstalled);
    TestTrue(
        TEXT("Native editor module is loaded"),
        FModuleManager::Get().IsModuleLoaded(TEXT("UnrealAssetBatchAuditor")));

    FString ActualRoot = FPaths::ConvertRelativePathToFull(Plugin->GetBaseDir());
    FPaths::NormalizeDirectoryName(ActualRoot);
    FString ExpectedRoot = ExpectedRootFromEnvironment;
    ExpectedRoot = FPaths::ConvertRelativePathToFull(ExpectedRoot);
    FPaths::NormalizeDirectoryName(ExpectedRoot);
    TestEqual(TEXT("Plugin is loaded from the fresh project install"), ActualRoot, ExpectedRoot);

    const FString ProfilePath = FPaths::Combine(
        ActualRoot, TEXT("Resources/Profiles/desktop-balanced.v3.json"));
    const FString TextureProfilePath = FPaths::Combine(
        ActualRoot, TEXT("Resources/Profiles/texture-review-lenient.v1.json"));
    TestTrue(TEXT("Packaged Profile exists"), FPaths::FileExists(ProfilePath));
    TestTrue(TEXT("Packaged Texture Profile exists"), FPaths::FileExists(TextureProfilePath));
    TestTrue(
        TEXT("Packaged Python entry exists"),
        FPaths::FileExists(FPaths::Combine(ActualRoot, TEXT("Content/Python/run_asset_audit.py"))));
    TestTrue(
        TEXT("Packaged Texture orchestrator exists"),
        FPaths::FileExists(FPaths::Combine(
            ActualRoot, TEXT("Content/Python/unreal_asset_batch_auditor/texture_audit.py"))));

    const FName TabName = FUnrealAssetBatchAuditorModule::GetAuditTabName();
    TestTrue(TEXT("Chinese audit panel tab spawner is registered"), FGlobalTabmanager::Get()->HasTabSpawner(TabName));
    const TSharedPtr<SDockTab> Tab = FGlobalTabmanager::Get()->TryInvokeTab(TabName);
    TestTrue(TEXT("Production audit panel opens through its real tab entry"), Tab.IsValid());

    const FString OutputRoot = FPaths::Combine(
        FPaths::ProjectSavedDir(), TEXT("UnrealAssetBatchAuditor/ReleaseInstallEvidence"));
    IFileManager::Get().MakeDirectory(*OutputRoot, true);
    const FString ReportPath = FPaths::Combine(OutputRoot, TEXT("latest-report.json"));
    const FString TextureReportPath = FPaths::Combine(OutputRoot, TEXT("latest-texture-report.json"));
    IFileManager::Get().Delete(*ReportPath, false, true, true);
    IFileManager::Get().Delete(*TextureReportPath, false, true, true);

    IPythonScriptPlugin* Python = IPythonScriptPlugin::Get();
    if (!TestNotNull(TEXT("Python Script Plugin is available"), Python)) return false;
    if (!Python->IsPythonInitialized() && !Python->ForceEnablePythonAtRuntime())
    {
        AddError(TEXT("Python Script Plugin could not initialize"));
        return false;
    }
    FString SafeProfile = ProfilePath.Replace(TEXT("\\"), TEXT("/"));
    FString SafeReport = ReportPath.Replace(TEXT("\\"), TEXT("/"));
    FString SafeTextureProfile = TextureProfilePath.Replace(TEXT("\\"), TEXT("/"));
    FString SafeTextureReport = TextureReportPath.Replace(TEXT("\\"), TEXT("/"));
    SafeProfile.ReplaceInline(TEXT("'"), TEXT("\\'"));
    SafeReport.ReplaceInline(TEXT("'"), TEXT("\\'"));
    SafeTextureProfile.ReplaceInline(TEXT("'"), TEXT("\\'"));
    SafeTextureReport.ReplaceInline(TEXT("'"), TEXT("\\'"));
    const FString Command = FString::Printf(
        TEXT("from run_asset_audit import run; run(r'%s', ['/Engine/BasicShapes/Cube.Cube'], r'%s', batch_size=1)"),
        *SafeProfile,
        *SafeReport);
    if (!TestTrue(TEXT("Packaged Python orchestrator completes a real audit"), Python->ExecPythonCommand(*Command)))
    {
        return false;
    }

    FString ReportJson;
    TSharedPtr<FJsonObject> Report;
    const bool bLoaded = FFileHelper::LoadFileToString(ReportJson, *ReportPath);
    if (bLoaded)
    {
        const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(ReportJson);
        FJsonSerializer::Deserialize(Reader, Report);
    }
    if (!TestTrue(TEXT("Fresh install writes a parseable Report"), bLoaded && Report.IsValid())) return false;
    TestTrue(TEXT("Report records real Unreal collection"), Report->GetBoolField(TEXT("real_unreal_validation")));
    TestEqual(TEXT("One real Static Mesh was audited"), Report->GetArrayField(TEXT("assets")).Num(), 1);

    const FString TextureCommand = FString::Printf(
        TEXT("from pathlib import Path; from unreal_asset_batch_auditor import TextureAuditProfile, TextureUnrealCppCollector, audit_textures; p=TextureAuditProfile.load(Path(r'%s')); r=audit_textures(profile=p, collector=TextureUnrealCppCollector(), asset_paths=['/Engine/EngineResources/DefaultTexture.DefaultTexture'], batch_size=1); r.write(Path(r'%s'))"),
        *SafeTextureProfile,
        *SafeTextureReport);
    if (!TestTrue(
            TEXT("Packaged Texture orchestrator completes a real audit"),
            Python->ExecPythonCommand(*TextureCommand)))
    {
        return false;
    }

    FString TextureReportJson;
    TSharedPtr<FJsonObject> TextureReport;
    const bool bTextureLoaded = FFileHelper::LoadFileToString(TextureReportJson, *TextureReportPath);
    if (bTextureLoaded)
    {
        const TSharedRef<TJsonReader<>> TextureReader = TJsonReaderFactory<>::Create(TextureReportJson);
        FJsonSerializer::Deserialize(TextureReader, TextureReport);
    }
    if (!TestTrue(
            TEXT("Fresh install writes a parseable Texture Report"),
            bTextureLoaded && TextureReport.IsValid()))
    {
        return false;
    }
    TestEqual(TEXT("Texture Report records its asset type"), TextureReport->GetStringField(TEXT("asset_type")), TEXT("texture2d"));
    TestTrue(TEXT("Texture Report records real Unreal collection"), TextureReport->GetBoolField(TEXT("real_unreal_validation")));
    TestEqual(TEXT("One real Texture2D was audited"), TextureReport->GetArrayField(TEXT("assets")).Num(), 1);
    TestEqual(TEXT("Texture2D collection has no failures"), TextureReport->GetArrayField(TEXT("collection_failures")).Num(), 0);

    if (Tab.IsValid()) Tab->RequestCloseTab();
    return true;
}

#endif
