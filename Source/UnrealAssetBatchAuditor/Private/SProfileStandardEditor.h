#pragma once

#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"

class FJsonObject;
class ITableRow;
class SEditableTextBox;
class STableViewBase;
template <typename ItemType> class SListView;

struct FProfileEditorField
{
    FString Path;
    FString Label;
    FString Kind;
    FString Value;
    FString Error;
    bool bBoolValue = false;
    TArray<TSharedPtr<FString>> Options;
    TSharedPtr<SEditableTextBox> TextInput;
};

struct FProfileEditorRule
{
    FString RuleId;
    FString Label;
    TArray<TSharedPtr<FProfileEditorField>> Fields;
};

struct FProfileEditorChange
{
    FString Path;
    FString Label;
    FString Change;
    FString Before;
    FString After;
};

class SProfileStandardEditor final : public SCompoundWidget
{
public:
    SLATE_BEGIN_ARGS(SProfileStandardEditor) {}
        SLATE_ARGUMENT(FString, SourcePath)
        SLATE_ARGUMENT(FString, ProjectProfileRoot)
        SLATE_ARGUMENT(FString, RequestPath)
        SLATE_ARGUMENT(FString, ResultPath)
        SLATE_EVENT(FSimpleDelegate, OnSaved)
    SLATE_END_ARGS()

    using FFieldPtr = TSharedPtr<FProfileEditorField>;
    using FChangePtr = TSharedPtr<FProfileEditorChange>;

    void Construct(const FArguments& InArgs);

#if WITH_DEV_AUTOMATION_TESTS
    bool SetTextFieldForEvidence(const FString& Path, const FString& Value);
    bool SetBoolFieldForEvidence(const FString& Path, bool bValue);
    bool PreviewForEvidence(FString& OutError);
    bool SaveForEvidence(FString& OutError);
    int32 GetChangeCountForEvidence() const { return Changes.Num(); }
    int32 GetErrorCountForEvidence() const;
    bool CanSaveForEvidence() const { return CanSave(); }
#endif

private:
    bool Describe(FString& OutError);
    bool RunEditorBridge(const FString& Action, FString& OutError);
    bool LoadResult(const FString& Action, FString& OutError);
    TSharedRef<SWidget> BuildWorkspace();
    TSharedRef<SWidget> BuildField(const FFieldPtr& Field);
    TSharedRef<SWidget> BuildRule(const FProfileEditorRule& Rule);
    TSharedRef<ITableRow> GenerateChangeRow(
        FChangePtr Item, const TSharedRef<STableViewBase>& OwnerTable);
    TSharedRef<SWidget> GenerateEnumOption(TSharedPtr<FString> Item) const;
    FReply PreviewChanges();
    FReply SaveProfile();
    FReply CloseWindow();
    void MarkDirty();
    void ClearFieldErrors();
    bool CanSave() const;
    FText GetStatusText() const;
    FText GetChangeSummaryText() const;
    FText GetEnumLabel(FFieldPtr Field) const;
    FText GetFieldErrorText(FFieldPtr Field) const;
    EVisibility GetFieldErrorVisibility(FFieldPtr Field) const;
    FSlateColor GetStatusColor() const;
    TSharedRef<FJsonObject> BuildValuesObject() const;

    FString SourcePath;
    FString ProjectProfileRoot;
    FString RequestPath;
    FString ResultPath;
    FString AssetTypeLabel;
    FString ProfileId;
    FString ProfileVersion;
    FString StatusMessage;
    TArray<FFieldPtr> IdentityFields;
    TArray<FProfileEditorRule> Rules;
    TMap<FString, FFieldPtr> FieldsByPath;
    TArray<FChangePtr> Changes;
    TSharedPtr<SListView<FChangePtr>> ChangeList;
    FSimpleDelegate OnSaved;
    bool bPreviewCurrent = false;
    bool bLastResultInvalid = false;
};
