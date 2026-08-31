#if WITH_DEV_AUTOMATION_TESTS

#include "SUnrealAssetAuditPanel.h"

#include "Framework/Application/SlateApplication.h"
#include "ImageUtils.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Widgets/SWindow.h"

namespace
{
bool CapturePanel(const TSharedRef<SUnrealAssetAuditPanel>& Panel, const FString& OutputPath)
{
    Panel->SlatePrepass();
    FSlateApplication::Get().Tick();

    TArray<FColor> Pixels;
    FIntVector Size;
    if (!FSlateApplication::Get().TakeScreenshot(Panel, Pixels, Size) || Pixels.IsEmpty())
    {
        return false;
    }
    for (FColor& Pixel : Pixels)
    {
        Pixel.A = 255;
    }
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(OutputPath), true);
    return FImageUtils::SaveImageByExtension(
        *OutputPath,
        FImageView(Pixels.GetData(), Size.X, Size.Y, EGammaSpace::sRGB));
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FUnrealAssetBatchAuditorPanelEvidenceTest,
    "UnrealAssetBatchAuditor.PanelEvidence",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)

bool FUnrealAssetBatchAuditorPanelEvidenceTest::RunTest(const FString& Parameters)
{
    const FString ReportPath = FPlatformMisc::GetEnvironmentVariable(TEXT("UABA_PANEL_EVIDENCE_REPORT"));
    const FString OutputDirectory = FPlatformMisc::GetEnvironmentVariable(TEXT("UABA_PANEL_EVIDENCE_OUTPUT"));
    const FString ComparisonPath = FPlatformMisc::GetEnvironmentVariable(TEXT("UABA_PANEL_EVIDENCE_COMPARISON"));
    const FString EvidenceMode = FPlatformMisc::GetEnvironmentVariable(TEXT("UABA_PANEL_EVIDENCE_MODE"));
    const int32 ExpectedAssets = FCString::Atoi(
        *FPlatformMisc::GetEnvironmentVariable(TEXT("UABA_PANEL_EVIDENCE_EXPECTED_ASSETS")));
    const int32 ExpectedIssues = FCString::Atoi(
        *FPlatformMisc::GetEnvironmentVariable(TEXT("UABA_PANEL_EVIDENCE_EXPECTED_ISSUES")));
    const int32 ExpectedComparisonRows = FCString::Atoi(
        *FPlatformMisc::GetEnvironmentVariable(TEXT("UABA_PANEL_EVIDENCE_EXPECTED_COMPARISONS")));
    if (!FPaths::FileExists(ReportPath))
    {
        AddError(FString::Printf(TEXT("Evidence report does not exist: %s"), *ReportPath));
        return false;
    }
    if (OutputDirectory.IsEmpty())
    {
        AddError(TEXT("UABA_PANEL_EVIDENCE_OUTPUT is empty"));
        return false;
    }

    TSharedPtr<SUnrealAssetAuditPanel> Panel;
    const TSharedRef<SWindow> Window = SNew(SWindow)
        .Title(FText::FromString(TEXT("资产批量审计 · 自动化证据")))
        .ClientSize(FVector2D(1500.0f, 900.0f))
        .SupportsMaximize(false)
        .SupportsMinimize(false)
        [
            SAssignNew(Panel, SUnrealAssetAuditPanel)
        ];
    FSlateApplication::Get().AddWindow(Window, true);

    bool bPassed = true;
    auto Capture = [this, &Panel, &OutputDirectory, &bPassed](const TCHAR* Filename)
    {
        const FString Path = FPaths::Combine(OutputDirectory, Filename);
        if (!CapturePanel(Panel.ToSharedRef(), Path))
        {
            AddError(FString::Printf(TEXT("Could not capture Slate evidence: %s"), *Path));
            bPassed = false;
        }
    };

    Capture(TEXT("01-empty-state.png"));

    FString LoadError;
    if (!Panel->LoadReportForEvidence(ReportPath, LoadError))
    {
        AddError(FString::Printf(TEXT("Could not load evidence report: %s"), *LoadError));
        FSlateApplication::Get().RequestDestroyWindow(Window);
        return false;
    }
    TestEqual(
        TEXT("Asset rows include successes and failures"),
        Panel->GetEvidenceAssetCount(),
        ExpectedAssets > 0 ? ExpectedAssets : 26);
    TestEqual(
        TEXT("Issue rows include rules and collection failures"),
        Panel->GetEvidenceIssueCount(),
        ExpectedIssues > 0 ? ExpectedIssues : 23);

    Panel->SetFolderSelectionForEvidence({TEXT("/Engine/BasicShapes")});
    TestTrue(
        TEXT("Recursive folder scope discovers real Engine Static Mesh assets"),
        Panel->GetEvidenceSelectedAssetCount() >= 4);
    const FString EvidenceRiskCategory = EvidenceMode == TEXT("v3-material")
        ? TEXT("materials")
        : (EvidenceMode == TEXT("review") ? TEXT("structure") : TEXT("geometry"));
    Panel->SetRiskCategoryForEvidence(EvidenceRiskCategory);
    TestTrue(
        TEXT("Risk spectrum filters the report to the evidence category"),
        Panel->GetEvidenceFilteredIssueCount() > 0
            && Panel->GetEvidenceFilteredIssueCount() <= Panel->GetEvidenceIssueCount());
    Panel->SetRiskCategoryForEvidence(TEXT(""));

    Panel->SetEvidenceView(true, TEXT(""));
    Capture(TEXT("02-asset-overview.png"));
    Panel->SetEvidenceView(true, TEXT("通过"));
    Capture(TEXT("03-passing-assets.png"));
    Panel->SetEvidenceView(true, TEXT("需处理"));
    Capture(TEXT("04-assets-needing-work.png"));
    Panel->SetEvidenceView(false, TEXT(""));
    Capture(TEXT("05-issue-details.png"));
    if (EvidenceMode == TEXT("v2") || EvidenceMode == TEXT("review"))
    {
        Panel->SetEvidenceView(false, TEXT("简单碰撞"));
        Capture(TEXT("06-collision-evidence.png"));
        Panel->SetEvidenceView(false, TEXT("Lightmap UV"));
        Capture(TEXT("07-lightmap-uv-evidence.png"));
        Panel->SetEvidenceView(false, TEXT("Lightmap 分辨率"));
        Capture(TEXT("08-lightmap-resolution-evidence.png"));
        Panel->SetEvidenceView(false, TEXT("资产命名"));
        Capture(TEXT("09-object-name-evidence.png"));
        Panel->SetEvidenceView(false, TEXT("目录规范"));
        Capture(TEXT("10-package-path-evidence.png"));
        if (!ComparisonPath.IsEmpty())
        {
            if (!Panel->LoadComparisonForEvidence(ComparisonPath, LoadError))
            {
                AddError(FString::Printf(TEXT("Could not load comparison evidence: %s"), *LoadError));
                bPassed = false;
            }
            else
            {
                Panel->SetComparisonEvidenceView(TEXT(""));
                TestEqual(
                    TEXT("Comparison rows include issue and collection-failure changes"),
                    Panel->GetEvidenceComparisonCount(),
                    ExpectedComparisonRows > 0 ? ExpectedComparisonRows : 53);
                Capture(TEXT("11-regression-overview.png"));
                Panel->SetComparisonEvidenceView(TEXT("已解决"));
                Capture(TEXT("12-resolved-changes.png"));
            }
        }
    }
    else if (EvidenceMode == TEXT("v3-material"))
    {
        Panel->SetEvidenceView(false, TEXT("纹理依赖"));
        Capture(TEXT("06-texture-dependencies.png"));
        Panel->SetEvidenceView(false, TEXT("纹理尺寸"));
        Capture(TEXT("07-texture-dimension.png"));
        Panel->SetEvidenceView(false, TEXT("512"));
        Capture(TEXT("08-texture-size-evidence.png"));
        Panel->SetEvidenceView(false, TEXT(""));
        Panel->SetRiskCategoryForEvidence(TEXT("materials"));
        Capture(TEXT("09-material-risk-spectrum.png"));
        Panel->SetRiskCategoryForEvidence(TEXT(""));
        Capture(TEXT("10-material-risk-overview.png"));
        if (!ComparisonPath.IsEmpty())
        {
            if (!Panel->LoadComparisonForEvidence(ComparisonPath, LoadError))
            {
                AddError(FString::Printf(TEXT("Could not load comparison evidence: %s"), *LoadError));
                bPassed = false;
            }
            else
            {
                Panel->SetComparisonEvidenceView(TEXT(""));
                TestEqual(
                    TEXT("Comparison rows include issue and collection-failure changes"),
                    Panel->GetEvidenceComparisonCount(),
                    ExpectedComparisonRows > 0 ? ExpectedComparisonRows : 53);
                Capture(TEXT("11-regression-overview.png"));
                Panel->SetComparisonEvidenceView(TEXT("已解决"));
                Capture(TEXT("12-resolved-changes.png"));
            }
        }
    }
    else
    {
        Panel->SetEvidenceView(false, TEXT("三角形"));
        Capture(TEXT("06-triangle-evidence.png"));
        Panel->SetEvidenceView(false, TEXT("材质槽"));
        Capture(TEXT("07-material-evidence.png"));
        Panel->SetEvidenceView(false, TEXT("采集失败"));
        Capture(TEXT("08-collection-failures.png"));
    }

    Panel->SetEvidenceView(false, TEXT(""));
    if (Panel->SelectFirstResolvableIssueForEvidence())
    {
        const FString Summary = Panel->GetSelectedEvidenceSummaryForEvidence();
        TestTrue(TEXT("Review summary carries deterministic Evidence ID"), Summary.Contains(TEXT("Evidence ID：")));
        FString LocateError;
        TestTrue(TEXT("Selected report issue locates a real Static Mesh in Content Browser"),
            Panel->LocateSelectedAssetForEvidence(LocateError));
        if (!LocateError.IsEmpty()) AddError(LocateError);
        Capture(TEXT("13-review-actions.png"));
    }
    else
    {
        AddWarning(TEXT("Evidence report has no issue whose Static Mesh resolves in this host project"));
    }

    Panel->SetEvidenceView(true, TEXT(""));
    Panel->SetTaskEvidenceState(TEXT("running"), 16, 64, 2, 8);
    Capture(TEXT("14-running-batch-task.png"));
    Panel->SetTaskEvidenceState(TEXT("cancelling"), 24, 64, 3, 8);
    Capture(TEXT("15-cancelling-task.png"));

    FSlateApplication::Get().RequestDestroyWindow(Window);
    return bPassed;
}

#endif
