#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"

class ITableRow;
class SEditableTextBox;
class SSearchBox;
class STableViewBase;
template <typename OptionType> class SComboBox;
template <typename ItemType> class SListView;

struct FAuditPanelIssue
{
    FString Severity;
    FString AssetPath;
    FString RuleId;
    FString Message;
    FString Metric;
    FString Observed;
    FString Expected;
};

struct FAuditProfileOption
{
    FString Label;
    FString Summary;
    FString Path;
    bool bCustom = false;
};

struct FAuditPanelAsset
{
    FString AssetPath;
    FString AssetName;
    FString Status;
    FString TriangleCount;
    FString VertexCount;
    FString MaterialSlotCount;
    FString LodCount;
    FString NaniteState;
    FString CollisionState;
    FString LightmapUvState;
    FString LightmapResolution;
    int32 IssueCount = 0;
};

struct FAuditSessionOption
{
    FString Label;
    FString SessionId;
    FString ReportPath;
    int32 IssueCount = 0;
};

struct FAuditComparisonRow
{
    FString ChangeType;
    FString AssetPath;
    FString RuleId;
    FString Severity;
    FString Message;
};

class SUnrealAssetAuditPanel final : public SCompoundWidget
{
public:
    SLATE_BEGIN_ARGS(SUnrealAssetAuditPanel) {}
    SLATE_END_ARGS()

    using FIssuePtr = TSharedPtr<FAuditPanelIssue>;
    using FProfilePtr = TSharedPtr<FAuditProfileOption>;
    using FAssetPtr = TSharedPtr<FAuditPanelAsset>;
    using FSessionPtr = TSharedPtr<FAuditSessionOption>;
    using FComparisonPtr = TSharedPtr<FAuditComparisonRow>;

    void Construct(const FArguments& InArgs);

#if WITH_DEV_AUTOMATION_TESTS
    bool LoadReportForEvidence(const FString& Path, FString& OutError);
    bool LoadComparisonForEvidence(const FString& Path, FString& OutError);
    void SetEvidenceView(bool bAssetOverview, const FString& FilterText);
    void SetComparisonEvidenceView(const FString& FilterText);
    void SetFolderSelectionForEvidence(const TArray<FString>& InternalFolders);
    void SetRiskCategoryForEvidence(const FString& Category);
    void SetTaskEvidenceState(
        const FString& State, int32 Processed, int32 Requested, int32 CompletedBatches,
        int32 TotalBatches);
    int32 GetEvidenceAssetCount() const { return AllAssets.Num(); }
    int32 GetEvidenceIssueCount() const { return AllIssues.Num(); }
    int32 GetEvidenceComparisonCount() const { return AllComparisons.Num(); }
    int32 GetEvidenceSelectedAssetCount() const { return SelectedAssetPaths.Num(); }
    int32 GetEvidenceFilteredIssueCount() const { return FilteredIssues.Num(); }
#endif

private:
    FReply RefreshSelection();
    FReply BrowseProfile();
    FReply RunAudit();
    FReply CancelAudit();
    FReply ExportHandoff();
    FReply OpenReportFile();
    FReply OpenReportFolder();
    FReply OpenSessionFolder();
    FReply OpenHandoffFolder();
    FReply RunComparison();
    void HandleProfileChanged(FProfilePtr Item, ESelectInfo::Type SelectInfo);
    TSharedRef<SWidget> GenerateProfileOption(FProfilePtr Item) const;
    void HandleSearchChanged(const FText& Text);
    void HandleSessionChanged(FSessionPtr Item, ESelectInfo::Type SelectInfo);
    void RebuildFilteredIssues();
    void RebuildFilteredAssets();
    void RebuildFilteredComparisons();
    bool LoadReport(const FString& Path, FString& OutError);
    bool LoadSessionIndex(FString& OutError);
    bool LoadComparison(const FString& Path, FString& OutError);
    bool LoadTaskState(FString& OutError);
    EActiveTimerReturnType PollAuditTask(double CurrentTime, float DeltaTime);
    TSharedRef<ITableRow> GenerateIssueRow(FIssuePtr Item, const TSharedRef<STableViewBase>& OwnerTable);
    TSharedRef<ITableRow> GenerateAssetRow(FAssetPtr Item, const TSharedRef<STableViewBase>& OwnerTable);
    TSharedRef<ITableRow> GenerateComparisonRow(FComparisonPtr Item, const TSharedRef<STableViewBase>& OwnerTable);
    TSharedRef<SWidget> GenerateSessionOption(FSessionPtr Item) const;
    FReply ShowAssetOverview();
    FReply ShowIssueDetails();
    FReply ShowComparison();
    TSharedRef<SWidget> BuildSummaryCell(const FText& Label, TAttribute<FText> Value, const FLinearColor& Accent) const;
    TSharedRef<SWidget> BuildRiskCell(const FText& Label, const FString& Category, const FLinearColor& Accent);
    FReply ToggleRiskCategory(FString Category);
    void RebuildSelectionFromInternalFolders(const TArray<FString>& InternalFolders, TSet<FString>& InOutAssetPaths);

    FText GetSelectionText() const;
    FText GetStatusText() const;
    FText GetAssetCountText() const;
    FText GetPassCountText() const;
    FText GetIssueCountText() const;
    FText GetFailureCountText() const;
    FText GetRiskCategoryCountText(FString Category) const;
    FText GetSelectedProfileLabel() const;
    FText GetSelectedProfileSummary() const;
    FText GetResultViewHint() const;
    FText GetSelectedSessionLabel() const;
    FText GetComparisonBaselineText() const;
    FText GetNewIssueCountText() const;
    FText GetPersistentIssueCountText() const;
    FText GetResolvedIssueCountText() const;
    FText GetFailureChangeCountText() const;
    FText GetTaskPhaseText() const;
    FText GetTaskProgressText() const;
    TOptional<float> GetTaskProgressFraction() const;
    EVisibility GetAssetViewVisibility() const;
    EVisibility GetIssueViewVisibility() const;
    EVisibility GetComparisonViewVisibility() const;
    EVisibility GetIdleActionVisibility() const;
    EVisibility GetRunningActionVisibility() const;
    bool CanRunAudit() const;
    bool CanCancelAudit() const;
    bool CanRunComparison() const;

    TArray<FString> SelectedAssetPaths;
    TArray<FString> SelectedFolderPaths;
    TArray<FIssuePtr> AllIssues;
    TArray<FIssuePtr> FilteredIssues;
    TSharedPtr<SListView<FIssuePtr>> IssueList;
    TArray<FAssetPtr> AllAssets;
    TArray<FAssetPtr> FilteredAssets;
    TSharedPtr<SListView<FAssetPtr>> AssetList;
    TArray<FComparisonPtr> AllComparisons;
    TArray<FComparisonPtr> FilteredComparisons;
    TSharedPtr<SListView<FComparisonPtr>> ComparisonList;
    TArray<FProfilePtr> ProfileOptions;
    FProfilePtr SelectedProfile;
    TSharedPtr<SComboBox<FProfilePtr>> ProfileComboBox;
    TArray<FSessionPtr> SessionOptions;
    FSessionPtr SelectedSession;
    TSharedPtr<SComboBox<FSessionPtr>> SessionComboBox;
    TSharedPtr<SSearchBox> SearchInput;
    FString ReportPath;
    FString SessionRoot;
    FString ComparisonPath;
    FString TaskStatePath;
    FString CancelRequestPath;
    FString HandoffRoot;
    FString LastHandoffPath;
    FString ActiveTaskId;
    FString TaskState = TEXT("idle");
    FString CurrentProfileId;
    FString CurrentProfileVersion;
    FString CurrentReportCreatedAt;
    FString ComparisonBaselineLabel;
    FString StatusMessage;
    FString SearchText;
    FString ActiveRiskCategory;
    int32 DiscoveredFolderAssetCount = 0;
    int32 BatchSize = 64;
    int32 AssetCount = 0;
    int32 PassingAssetCount = 0;
    int32 IssueCount = 0;
    int32 FailureCount = 0;
    int32 NewIssueCount = 0;
    int32 PersistentIssueCount = 0;
    int32 ResolvedIssueCount = 0;
    int32 FailureChangeCount = 0;
    int32 TaskRequestedCount = 0;
    int32 TaskProcessedCount = 0;
    int32 TaskCompletedBatchCount = 0;
    int32 TaskTotalBatchCount = 0;
    float TaskProgressFraction = 0.0f;
    bool bAuditRunning = false;
    bool bTaskCanCancel = false;
    int32 ResultViewMode = 0;
};
