#if WITH_DEV_AUTOMATION_TESTS

#include "SProfileStandardEditor.h"

#include "Framework/Application/SlateApplication.h"
#include "ImageUtils.h"
#include "Interfaces/IPluginManager.h"
#include "IPythonScriptPlugin.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Widgets/SWindow.h"

namespace
{
bool CaptureEditor(const TSharedRef<SProfileStandardEditor>& Editor, const FString& OutputPath)
{
    Editor->SlatePrepass();
    FSlateApplication::Get().Tick();
    TArray<FColor> Pixels;
    FIntVector Size;
    if (!FSlateApplication::Get().TakeScreenshot(Editor, Pixels, Size) || Pixels.IsEmpty())
        return false;
    for (FColor& Pixel : Pixels) Pixel.A = 255;
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(OutputPath), true);
    return FImageUtils::SaveImageByExtension(
        *OutputPath, FImageView(Pixels.GetData(), Size.X, Size.Y, EGammaSpace::sRGB));
}

bool PrepareProjectProfile(
    FAutomationTestBase& Test, const FString& Source, const FString& Destination,
    const FString& SourceId, const FString& ProjectId)
{
    FString Json;
    if (!FFileHelper::LoadFileToString(Json, *Source))
    {
        Test.AddError(TEXT("Could not read built-in Profile"));
        return false;
    }
    Json.ReplaceInline(*SourceId, *ProjectId);
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(Destination), true);
    if (!FFileHelper::SaveStringToFile(
        Json, *Destination, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM))
    {
        Test.AddError(TEXT("Could not prepare project Profile"));
        return false;
    }
    return true;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FUnrealAssetBatchAuditorProfileEditorEvidenceTest,
    "UnrealAssetBatchAuditor.ProfileStandardEditorEvidence",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)

bool FUnrealAssetBatchAuditorProfileEditorEvidenceTest::RunTest(const FString& Parameters)
{
    const FString Output = FPlatformMisc::GetEnvironmentVariable(TEXT("UABA_PROFILE_EDITOR_EVIDENCE_OUTPUT"));
    const TSharedPtr<IPlugin> Plugin = IPluginManager::Get().FindPlugin(TEXT("UnrealAssetBatchAuditor"));
    if (Output.IsEmpty() || !Plugin.IsValid())
    {
        AddError(TEXT("Profile editor evidence environment is incomplete"));
        return false;
    }
    const FString BuiltInRoot = FPaths::Combine(Plugin->GetBaseDir(), TEXT("Resources/Profiles"));
    const FString ProjectRoot = FPaths::Combine(FPaths::ProjectConfigDir(), TEXT("AssetAudit/Profiles"));
    const FString RequestRoot = FPaths::Combine(
        FPaths::ProjectSavedDir(), TEXT("UnrealAssetBatchAuditor/ProfileEditorEvidence"));
    const FString ModelPath = FPaths::Combine(ProjectRoot, TEXT("host-model-standard.v3.json"));
    const FString TexturePath = FPaths::Combine(ProjectRoot, TEXT("host-texture-standard.v1.json"));
    if (!PrepareProjectProfile(
            *this, FPaths::Combine(BuiltInRoot, TEXT("desktop-balanced.v3.json")), ModelPath,
            TEXT("demo-desktop-balanced-v3"), TEXT("host-model-standard"))
        || !PrepareProjectProfile(
            *this, FPaths::Combine(BuiltInRoot, TEXT("texture-desktop-balanced.v1.json")), TexturePath,
            TEXT("texture-desktop-balanced-v1"), TEXT("host-texture-standard")))
        return false;

    auto MakeWindow = [&ProjectRoot, &RequestRoot](
        const FString& Path, const FString& Id, TSharedPtr<SProfileStandardEditor>& Editor)
    {
        return SNew(SWindow)
            .Title(FText::FromString(TEXT("项目验收标准工作台 · 宿主证据")))
            .ClientSize(FVector2D(1380, 900))
            .SupportsMaximize(false)
            .SupportsMinimize(false)
            [
                SAssignNew(Editor, SProfileStandardEditor)
                .SourcePath(Path)
                .ProjectProfileRoot(ProjectRoot)
                .RequestPath(FPaths::Combine(RequestRoot, Id + TEXT("-request.json")))
                .ResultPath(FPaths::Combine(RequestRoot, Id + TEXT("-result.json")))
            ];
    };
    bool bPassed = true;
    auto Capture = [this, &Output, &bPassed](
        const TSharedPtr<SProfileStandardEditor>& Editor, const TCHAR* Filename)
    {
        if (!CaptureEditor(Editor.ToSharedRef(), FPaths::Combine(Output, Filename)))
        {
            AddError(FString::Printf(TEXT("Could not capture %s"), Filename));
            bPassed = false;
        }
    };

    TSharedPtr<SProfileStandardEditor> ModelEditor;
    const TSharedRef<SWindow> ModelWindow = MakeWindow(ModelPath, TEXT("model"), ModelEditor);
    FSlateApplication::Get().AddWindow(ModelWindow, true);
    Capture(ModelEditor, TEXT("01-model-standard-loaded.png"));
    TestTrue(TEXT("Model invalid version field is editable"),
        ModelEditor->SetTextFieldForEvidence(TEXT("profile_version"), TEXT("next")));
    TestTrue(TEXT("Model invalid threshold field is editable"),
        ModelEditor->SetTextFieldForEvidence(TEXT("rules.triangle_budget.max_lod0"), TEXT("0")));
    FString Error;
    TestTrue(TEXT("Invalid model preview returns a structured result"), ModelEditor->PreviewForEvidence(Error));
    TestTrue(TEXT("Invalid model preview localizes field errors"), ModelEditor->GetErrorCountForEvidence() >= 2);
    TestFalse(TEXT("Invalid model preview cannot save"), ModelEditor->CanSaveForEvidence());
    Capture(ModelEditor, TEXT("02-model-invalid-fields.png"));
    TestTrue(TEXT("Model semantic version can be corrected"),
        ModelEditor->SetTextFieldForEvidence(TEXT("profile_version"), TEXT("1.1.0")));
    TestTrue(TEXT("Model triangle budget can be corrected"),
        ModelEditor->SetTextFieldForEvidence(TEXT("rules.triangle_budget.max_lod0"), TEXT("3200")));
    TestTrue(TEXT("Model Nanite rule can be disabled"),
        ModelEditor->SetBoolFieldForEvidence(TEXT("rules.nanite.enabled"), false));
    TestTrue(TEXT("Valid model preview succeeds"), ModelEditor->PreviewForEvidence(Error));
    TestTrue(TEXT("Valid model preview lists changes"), ModelEditor->GetChangeCountForEvidence() >= 3);
    TestTrue(TEXT("Valid model preview enables save"), ModelEditor->CanSaveForEvidence());
    Capture(ModelEditor, TEXT("03-model-difference-preview.png"));
    TestTrue(TEXT("Validated model standard saves"), ModelEditor->SaveForEvidence(Error));
    Capture(ModelEditor, TEXT("04-model-standard-saved.png"));
    FSlateApplication::Get().RequestDestroyWindow(ModelWindow);

    TSharedPtr<SProfileStandardEditor> TextureEditor;
    const TSharedRef<SWindow> TextureWindow = MakeWindow(TexturePath, TEXT("texture"), TextureEditor);
    FSlateApplication::Get().AddWindow(TextureWindow, true);
    TestTrue(TEXT("Texture dimension can be edited"),
        TextureEditor->SetTextFieldForEvidence(TEXT("rules.source_dimension.max_size"), TEXT("2048")));
    TestTrue(TEXT("Texture streaming policy can be disabled"),
        TextureEditor->SetBoolFieldForEvidence(TEXT("rules.streaming.enabled"), false));
    TestTrue(TEXT("Valid texture preview succeeds"), TextureEditor->PreviewForEvidence(Error));
    TestTrue(TEXT("Texture preview exposes both changes"), TextureEditor->GetChangeCountForEvidence() >= 2);
    Capture(TextureEditor, TEXT("05-texture-difference-preview.png"));
    TestTrue(TEXT("Validated texture standard saves"), TextureEditor->SaveForEvidence(Error));
    Capture(TextureEditor, TEXT("06-texture-standard-saved.png"));
    FSlateApplication::Get().RequestDestroyWindow(TextureWindow);

    FString SavedModel;
    FString SavedTexture;
    TestTrue(TEXT("Saved model Profile is readable"), FFileHelper::LoadFileToString(SavedModel, *ModelPath));
    TestTrue(TEXT("Saved model Profile records edited version and threshold"),
        SavedModel.Contains(TEXT("\"profile_version\": \"1.1.0\""))
            && SavedModel.Contains(TEXT("\"max_lod0\": 3200")));
    TestTrue(TEXT("Saved texture Profile records edited threshold"),
        FFileHelper::LoadFileToString(SavedTexture, *TexturePath)
            && SavedTexture.Contains(TEXT("\"max_size\": 2048")));

    const FString ReportRoot = FPaths::Combine(
        FPaths::ProjectSavedDir(), TEXT("UnrealAssetBatchAuditor/ProfileEditorEvidence/Reports"));
    const FString ModelReportPath = FPaths::Combine(ReportRoot, TEXT("model-project-standard-report.json"));
    const FString TextureReportPath = FPaths::Combine(ReportRoot, TEXT("texture-project-standard-report.json"));
    auto SafePythonPath = [](FString Path)
    {
        Path.ReplaceInline(TEXT("\\"), TEXT("/"));
        Path.ReplaceInline(TEXT("'"), TEXT("\\'"));
        return Path;
    };
    IPythonScriptPlugin* Python = IPythonScriptPlugin::Get();
    TestTrue(TEXT("Python Script Plugin remains ready for Profile-driven audits"), Python != nullptr);
    if (Python)
    {
        const FString ModelCommand = FString::Printf(
            TEXT("import run_asset_audit; run_asset_audit.run(r'%s', ['/Engine/BasicShapes/Cube.Cube'], r'%s', batch_size=1)"),
            *SafePythonPath(ModelPath), *SafePythonPath(ModelReportPath));
        const FString TextureCommand = FString::Printf(
            TEXT("from pathlib import Path; from unreal_asset_batch_auditor import TextureAuditProfile, TextureUnrealCppCollector, audit_textures; p=TextureAuditProfile.load(Path(r'%s')); r=audit_textures(profile=p, collector=TextureUnrealCppCollector(), asset_paths=['/Engine/EngineResources/DefaultTexture.DefaultTexture'], batch_size=1); r.write(Path(r'%s'))"),
            *SafePythonPath(TexturePath), *SafePythonPath(TextureReportPath));
        TestTrue(TEXT("Saved model project standard drives a real UE Static Mesh audit"),
            Python->ExecPythonCommand(*ModelCommand));
        TestTrue(TEXT("Saved texture project standard drives a real UE Texture2D audit"),
            Python->ExecPythonCommand(*TextureCommand));
        FString ModelReport;
        FString TextureReport;
        TestTrue(TEXT("Model Report records the edited project standard identity"),
            FFileHelper::LoadFileToString(ModelReport, *ModelReportPath)
                && ModelReport.Contains(TEXT("\"profile_id\": \"host-model-standard\""))
                && ModelReport.Contains(TEXT("\"profile_version\": \"1.1.0\"")));
        TestTrue(TEXT("Texture Report records the edited project standard identity"),
            FFileHelper::LoadFileToString(TextureReport, *TextureReportPath)
                && TextureReport.Contains(TEXT("\"profile_id\": \"host-texture-standard\"")));
    }
    return bPassed;
}

#endif
