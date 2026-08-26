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

class SUnrealAssetAuditPanel final : public SCompoundWidget
{
public:
    SLATE_BEGIN_ARGS(SUnrealAssetAuditPanel) {}
    SLATE_END_ARGS()

    using FIssuePtr = TSharedPtr<FAuditPanelIssue>;
    using FProfilePtr = TSharedPtr<FAuditProfileOption>;

    void Construct(const FArguments& InArgs);

private:
    FReply RefreshSelection();
    FReply BrowseProfile();
    FReply RunAudit();
    FReply OpenReportFolder();
    void HandleProfileChanged(FProfilePtr Item, ESelectInfo::Type SelectInfo);
    TSharedRef<SWidget> GenerateProfileOption(FProfilePtr Item) const;
    void HandleSearchChanged(const FText& Text);
    void RebuildFilteredIssues();
    bool LoadReport(const FString& Path, FString& OutError);
    TSharedRef<ITableRow> GenerateIssueRow(FIssuePtr Item, const TSharedRef<STableViewBase>& OwnerTable);
    TSharedRef<SWidget> BuildSummaryCell(const FText& Label, TAttribute<FText> Value, const FLinearColor& Accent) const;

    FText GetSelectionText() const;
    FText GetStatusText() const;
    FText GetAssetCountText() const;
    FText GetPassCountText() const;
    FText GetIssueCountText() const;
    FText GetFailureCountText() const;
    FText GetSelectedProfileLabel() const;
    FText GetSelectedProfileSummary() const;
    bool CanRunAudit() const;

    TArray<FString> SelectedAssetPaths;
    TArray<FIssuePtr> AllIssues;
    TArray<FIssuePtr> FilteredIssues;
    TSharedPtr<SListView<FIssuePtr>> IssueList;
    TArray<FProfilePtr> ProfileOptions;
    FProfilePtr SelectedProfile;
    TSharedPtr<SComboBox<FProfilePtr>> ProfileComboBox;
    TSharedPtr<SSearchBox> SearchInput;
    FString ReportPath;
    FString StatusMessage;
    FString SearchText;
    int32 BatchSize = 64;
    int32 AssetCount = 0;
    int32 PassingAssetCount = 0;
    int32 IssueCount = 0;
    int32 FailureCount = 0;
    bool bAuditRunning = false;
};
