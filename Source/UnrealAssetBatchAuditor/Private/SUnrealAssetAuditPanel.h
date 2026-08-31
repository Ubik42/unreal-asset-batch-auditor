#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"

class ITableRow;
class FJsonObject;
struct FAssetData;
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
    FString EvidenceId;
    FString IssueId;
    FString ReviewDecision = TEXT("unreviewed");
    FString ReviewOwner;
    FString ReviewNote;
};

struct FAuditProfileOption
{
    FString Label;
    FString Summary;
    FString Path;
    bool bCustom = false;
};

struct FAuditAssetTypeOption
{
    FString Id;
    FString Label;
    FString Summary;
};

struct FAuditPanelAsset
{
    FString AssetPath;
    FString AssetName;
    FString Status;
    FString TriangleCount;
    FString VertexCount;
    FString MaterialSlotCount;
    FString MaterialDependencyState;
    FString TextureDependencyState;
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

struct FAuditDeliveryGroup
{
    FString GroupPath;
    FString GroupLabel;
    FString RiskBand;
    FString HotspotReason;
    TSet<FString> AssetPaths;
    int32 HotspotRank = 0;
    int32 AssetCount = 0;
    int32 PassedAssetCount = 0;
    int32 IssueAssetCount = 0;
    int32 IssueCount = 0;
    int32 CollectionFailureCount = 0;
    int32 UnreviewedIssueCount = 0;
    int32 FixRequiredCount = 0;
    int32 ApprovedExceptionCount = 0;
    double IssueDensity = 0.0;
};

class SUnrealAssetAuditPanel final : public SCompoundWidget
{
public:
    SLATE_BEGIN_ARGS(SUnrealAssetAuditPanel) {}
    SLATE_END_ARGS()

    using FIssuePtr = TSharedPtr<FAuditPanelIssue>;
    using FProfilePtr = TSharedPtr<FAuditProfileOption>;
    using FAssetTypePtr = TSharedPtr<FAuditAssetTypeOption>;
    using FAssetPtr = TSharedPtr<FAuditPanelAsset>;
    using FSessionPtr = TSharedPtr<FAuditSessionOption>;
    using FComparisonPtr = TSharedPtr<FAuditComparisonRow>;
    using FDeliveryGroupPtr = TSharedPtr<FAuditDeliveryGroup>;

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
    bool SelectIssueForEvidence(const FString& AssetPath, const FString& RuleId);
    bool SelectFirstResolvableIssueForEvidence();
    FString GetSelectedEvidenceSummaryForEvidence() const;
    bool LocateSelectedAssetForEvidence(FString& OutError);
    bool SetSelectedReviewForEvidence(
        const FString& Decision, const FString& Owner, const FString& Note, FString& OutError);
    int32 GetEvidenceReviewedCount() const;
    void SetDeliveryGroupEvidenceView();
    bool DrillIntoDeliveryGroupForEvidence(const FString& GroupPath, bool bShowIssues);
    bool SelectDeliveryGroupForEvidence(const FString& GroupPath);
    int32 GetEvidenceDeliveryGroupCount() const { return AllDeliveryGroups.Num(); }
    int32 GetEvidenceFilteredAssetCount() const { return FilteredAssets.Num(); }
    void ClearDeliveryGroupDrilldownForEvidence() { ClearDeliveryGroupDrilldown(); }
#endif

private:
    FReply RefreshSelection();
    FReply BrowseProfile();
    FReply CloneSelectedProfile();
    FReply OpenProfileEditor();
    FReply OpenProjectProfileFolder();
    FReply RunAudit();
    FReply CancelAudit();
    FReply ExportHandoff();
    FReply OpenReportFile();
    FReply OpenReportFolder();
    FReply OpenSessionFolder();
    FReply OpenHandoffFolder();
    FReply RunComparison();
    void HandleProfileChanged(FProfilePtr Item, ESelectInfo::Type SelectInfo);
    void HandleAssetTypeChanged(FAssetTypePtr Item, ESelectInfo::Type SelectInfo);
    TSharedRef<SWidget> GenerateProfileOption(FProfilePtr Item) const;
    TSharedRef<SWidget> GenerateAssetTypeOption(FAssetTypePtr Item) const;
    void RebuildProfileOptions();
    void HandleSearchChanged(const FText& Text);
    void HandleSessionChanged(FSessionPtr Item, ESelectInfo::Type SelectInfo);
    void HandleIssueSelectionChanged(FIssuePtr Item, ESelectInfo::Type SelectInfo);
    void HandleAssetSelectionChanged(FAssetPtr Item, ESelectInfo::Type SelectInfo);
    void HandleIssueDoubleClick(FIssuePtr Item);
    void HandleAssetDoubleClick(FAssetPtr Item);
    void HandleDeliveryGroupSelectionChanged(FDeliveryGroupPtr Item, ESelectInfo::Type SelectInfo);
    void HandleDeliveryGroupDoubleClick(FDeliveryGroupPtr Item);
    void RebuildFilteredIssues();
    void RebuildFilteredAssets();
    void RebuildFilteredComparisons();
    void RebuildFilteredDeliveryGroups();
    bool LoadReport(const FString& Path, FString& OutError);
    bool LoadSessionIndex(FString& OutError);
    bool LoadComparison(const FString& Path, FString& OutError);
    bool LoadTaskState(FString& OutError);
    bool RefreshDeliveryGroups(FString& OutError);
    bool LoadDeliveryGroupView(FString& OutError);
    EActiveTimerReturnType PollAuditTask(double CurrentTime, float DeltaTime);
    TSharedRef<ITableRow> GenerateIssueRow(FIssuePtr Item, const TSharedRef<STableViewBase>& OwnerTable);
    TSharedRef<ITableRow> GenerateAssetRow(FAssetPtr Item, const TSharedRef<STableViewBase>& OwnerTable);
    TSharedRef<ITableRow> GenerateComparisonRow(FComparisonPtr Item, const TSharedRef<STableViewBase>& OwnerTable);
    TSharedRef<ITableRow> GenerateDeliveryGroupRow(FDeliveryGroupPtr Item, const TSharedRef<STableViewBase>& OwnerTable);
    TSharedRef<SWidget> GenerateSessionOption(FSessionPtr Item) const;
    FReply ShowAssetOverview();
    FReply ShowIssueDetails();
    FReply ShowComparison();
    FReply ShowDeliveryGroups();
    FReply DrillIntoSelectedGroup(bool bShowIssues);
    FReply ClearDeliveryGroupDrilldown();
    FReply LocateReviewAsset();
    FReply OpenReviewAsset();
    FReply CopyReviewEvidence();
    FReply SaveReviewDecision();
    FReply SetDraftReviewDecision(FString Decision);
    FReply SetReviewFilter(FString Decision);
    TSharedRef<SWidget> BuildSummaryCell(const FText& Label, TAttribute<FText> Value, const FLinearColor& Accent) const;
    TSharedRef<SWidget> BuildRiskCell(const FText& Label, const FString& Category, const FLinearColor& Accent);
    FReply ToggleRiskCategory(FString Category);
    void RebuildSelectionFromInternalFolders(const TArray<FString>& InternalFolders, TSet<FString>& InOutAssetPaths);
    bool RefreshReviewData(FString& OutError);
    bool LoadReviewView(FString& OutError);
    bool RunPanelPythonBridge(
        const FString& FunctionName, const TSharedRef<FJsonObject>& Request,
        const FString& RequestPath, FString& OutError);

    FText GetSelectionText() const;
    FText GetStatusText() const;
    FText GetAssetCountText() const;
    FText GetPassCountText() const;
    FText GetIssueCountText() const;
    FText GetFailureCountText() const;
    FText GetRiskCategoryCountText(FString Category) const;
    FText GetSelectedProfileLabel() const;
    FText GetSelectedProfileSummary() const;
    FText GetSelectedAssetTypeLabel() const;
    FText GetSelectedAssetTypeSummary() const;
    FText GetResultViewHint() const;
    FText GetReviewContextText() const;
    FText GetReviewActionTooltip() const;
    FText GetReviewProgressText() const;
    FText GetReviewFilterLabel(FString Decision) const;
    FText GetReviewOrphanText() const;
    FText GetDeliveryGroupSummaryText() const;
    FText GetDeliveryGroupDrilldownText() const;
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
    EVisibility GetTextureAssetViewVisibility() const;
    EVisibility GetIssueViewVisibility() const;
    EVisibility GetComparisonViewVisibility() const;
    EVisibility GetDeliveryGroupViewVisibility() const;
    EVisibility GetDeliveryGroupContextVisibility() const;
    EVisibility GetIdleActionVisibility() const;
    EVisibility GetRunningActionVisibility() const;
    bool CanRunAudit() const;
    bool CanEditSelectedProfile() const;
    bool CanCancelAudit() const;
    bool CanRunComparison() const;
    bool CanLocateReviewAsset() const;
    bool CanOpenReviewAsset() const;
    bool CanCopyReviewEvidence() const;
    bool CanSaveReviewDecision() const;
    bool TryResolveReviewAsset(FAssetData& OutAssetData, FString& OutError) const;
    FString GetReviewAssetPath() const;
    FString BuildReviewEvidenceSummary() const;
    void HandleProfileEditorSaved();

    TArray<FString> SelectedAssetPaths;
    TArray<FString> SelectedFolderPaths;
    TArray<FIssuePtr> AllIssues;
    TArray<FIssuePtr> FilteredIssues;
    TSharedPtr<SListView<FIssuePtr>> IssueList;
    TArray<FAssetPtr> AllAssets;
    TArray<FAssetPtr> FilteredAssets;
    TSharedPtr<SListView<FAssetPtr>> AssetList;
    TSharedPtr<SListView<FAssetPtr>> TextureAssetList;
    FAssetPtr SelectedReviewAsset;
    FIssuePtr SelectedReviewIssue;
    TArray<FComparisonPtr> AllComparisons;
    TArray<FComparisonPtr> FilteredComparisons;
    TSharedPtr<SListView<FComparisonPtr>> ComparisonList;
    TArray<FDeliveryGroupPtr> AllDeliveryGroups;
    TArray<FDeliveryGroupPtr> FilteredDeliveryGroups;
    TSharedPtr<SListView<FDeliveryGroupPtr>> DeliveryGroupList;
    FDeliveryGroupPtr SelectedDeliveryGroup;
    TArray<FProfilePtr> ProfileOptions;
    FProfilePtr SelectedProfile;
    TSharedPtr<SComboBox<FProfilePtr>> ProfileComboBox;
    TArray<FAssetTypePtr> AssetTypeOptions;
    FAssetTypePtr SelectedAssetType;
    TSharedPtr<SComboBox<FAssetTypePtr>> AssetTypeComboBox;
    TArray<FSessionPtr> SessionOptions;
    FSessionPtr SelectedSession;
    TSharedPtr<SComboBox<FSessionPtr>> SessionComboBox;
    TSharedPtr<SSearchBox> SearchInput;
    TSharedPtr<SEditableTextBox> ReviewOwnerInput;
    TSharedPtr<SEditableTextBox> ReviewNoteInput;
    FString ReportPath;
    FString SessionRoot;
    FString ComparisonPath;
    FString TaskStatePath;
    FString CancelRequestPath;
    FString HandoffRoot;
    FString ReviewLedgerRoot;
    FString ReviewViewPath;
    FString ReviewRequestPath;
    FString DeliveryGroupViewPath;
    FString DeliveryGroupRequestPath;
    FString ProjectProfileRoot;
    FString ProfileCloneRequestPath;
    FString ProfileCloneResultPath;
    FString LastHandoffPath;
    FString ActiveTaskId;
    FString TaskState = TEXT("idle");
    FString CurrentProfileId;
    FString CurrentAssetType = TEXT("static_mesh");
    FString CurrentReportId;
    FString CurrentProfileVersion;
    FString CurrentReportCreatedAt;
    FString ComparisonBaselineLabel;
    FString StatusMessage;
    FString SearchText;
    FString ActiveRiskCategory;
    FString ActiveReviewFilter;
    FString ActiveDeliveryGroupPath;
    FString DraftReviewDecision = TEXT("unreviewed");
    int32 DiscoveredFolderAssetCount = 0;
    int32 IgnoredSelectionCount = 0;
    int32 BatchSize = 64;
    int32 AssetCount = 0;
    int32 PassingAssetCount = 0;
    int32 IssueCount = 0;
    int32 FailureCount = 0;
    int32 NewIssueCount = 0;
    int32 PersistentIssueCount = 0;
    int32 ResolvedIssueCount = 0;
    int32 FailureChangeCount = 0;
    int32 ReviewOrphanCount = 0;
    int32 TaskRequestedCount = 0;
    int32 TaskProcessedCount = 0;
    int32 TaskCompletedBatchCount = 0;
    int32 TaskTotalBatchCount = 0;
    float TaskProgressFraction = 0.0f;
    bool bAuditRunning = false;
    bool bTaskCanCancel = false;
    int32 ResultViewMode = 0;
};
