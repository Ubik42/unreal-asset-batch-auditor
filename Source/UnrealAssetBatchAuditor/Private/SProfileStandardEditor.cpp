#include "SProfileStandardEditor.h"

#include "Framework/Application/SlateApplication.h"
#include "IPythonScriptPlugin.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Styling/AppStyle.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SCheckBox.h"
#include "Widgets/Input/SComboBox.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/Layout/SSplitter.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SWindow.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/Views/SHeaderRow.h"
#include "Widgets/Views/SListView.h"
#include "Widgets/Views/STableRow.h"

namespace
{
const FLinearColor StandardCyan(0.08f, 0.78f, 0.82f, 1.0f);
const FLinearColor StandardGreen(0.20f, 0.76f, 0.46f, 1.0f);
const FLinearColor StandardAmber(0.96f, 0.62f, 0.12f, 1.0f);
const FLinearColor StandardRed(0.95f, 0.28f, 0.24f, 1.0f);

FString JsonDisplay(const TSharedPtr<FJsonValue>& Value)
{
    if (!Value.IsValid() || Value->IsNull()) return TEXT("—");
    if (Value->Type == EJson::String) return Value->AsString();
    if (Value->Type == EJson::Boolean) return Value->AsBool() ? TEXT("true") : TEXT("false");
    if (Value->Type == EJson::Number)
    {
        const double Number = Value->AsNumber();
        return FMath::IsNearlyEqual(Number, FMath::RoundToDouble(Number))
            ? FString::Printf(TEXT("%lld"), static_cast<int64>(FMath::RoundToDouble(Number)))
            : FString::SanitizeFloat(Number);
    }
    return TEXT("—");
}

FText LocalizedEnum(const FString& Value)
{
    if (Value == TEXT("info")) return FText::FromString(TEXT("提示"));
    if (Value == TEXT("warning")) return FText::FromString(TEXT("警告"));
    if (Value == TEXT("error")) return FText::FromString(TEXT("错误"));
    if (Value == TEXT("enabled")) return FText::FromString(TEXT("启用"));
    if (Value == TEXT("disabled")) return FText::FromString(TEXT("禁用"));
    if (Value == TEXT("any")) return FText::FromString(TEXT("不限"));
    return FText::FromString(Value);
}

FText ChangeLabel(const FString& Value)
{
    if (Value == TEXT("added")) return FText::FromString(TEXT("新增"));
    if (Value == TEXT("removed")) return FText::FromString(TEXT("移除"));
    return FText::FromString(TEXT("修改"));
}
}

class SProfileChangeRow final : public SMultiColumnTableRow<SProfileStandardEditor::FChangePtr>
{
public:
    SLATE_BEGIN_ARGS(SProfileChangeRow) {}
        SLATE_ARGUMENT(SProfileStandardEditor::FChangePtr, Item)
    SLATE_END_ARGS()

    void Construct(const FArguments& InArgs, const TSharedRef<STableViewBase>& OwnerTable)
    {
        Item = InArgs._Item;
        SMultiColumnTableRow::Construct(
            FSuperRowType::FArguments().Padding(FMargin(5.0f, 4.0f)), OwnerTable);
    }

    virtual TSharedRef<SWidget> GenerateWidgetForColumn(const FName& ColumnName) override
    {
        if (ColumnName == TEXT("Change"))
            return SNew(STextBlock).Text(ChangeLabel(Item->Change)).ColorAndOpacity(StandardAmber);
        if (ColumnName == TEXT("Field"))
            return SNew(STextBlock).Text(FText::FromString(Item->Label)).ToolTipText(FText::FromString(Item->Path));
        if (ColumnName == TEXT("Before"))
            return SNew(STextBlock).Text(FText::FromString(Item->Before)).ColorAndOpacity(FSlateColor::UseSubduedForeground());
        return SNew(STextBlock).Text(FText::FromString(Item->After)).ColorAndOpacity(StandardCyan);
    }

private:
    SProfileStandardEditor::FChangePtr Item;
};

void SProfileStandardEditor::Construct(const FArguments& InArgs)
{
    SourcePath = InArgs._SourcePath;
    ProjectProfileRoot = InArgs._ProjectProfileRoot;
    RequestPath = InArgs._RequestPath;
    ResultPath = InArgs._ResultPath;
    OnSaved = InArgs._OnSaved;
    FString Error;
    if (!Describe(Error))
    {
        StatusMessage = Error;
        bLastResultInvalid = true;
    }
    ChildSlot[BuildWorkspace()];
}

#if WITH_DEV_AUTOMATION_TESTS
bool SProfileStandardEditor::SetTextFieldForEvidence(const FString& Path, const FString& Value)
{
    FFieldPtr* Field = FieldsByPath.Find(Path);
    if (!Field || (*Field)->Kind == TEXT("boolean")) return false;
    (*Field)->Value = Value;
    if ((*Field)->TextInput.IsValid()) (*Field)->TextInput->SetText(FText::FromString(Value));
    MarkDirty();
    return true;
}

bool SProfileStandardEditor::SetBoolFieldForEvidence(const FString& Path, bool bValue)
{
    FFieldPtr* Field = FieldsByPath.Find(Path);
    if (!Field || (*Field)->Kind != TEXT("boolean")) return false;
    (*Field)->bBoolValue = bValue;
    MarkDirty();
    return true;
}

bool SProfileStandardEditor::PreviewForEvidence(FString& OutError)
{
    return RunEditorBridge(TEXT("preview"), OutError) && LoadResult(TEXT("preview"), OutError);
}

bool SProfileStandardEditor::SaveForEvidence(FString& OutError)
{
    if (!CanSave())
    {
        OutError = TEXT("当前差异尚未通过预览");
        return false;
    }
    return RunEditorBridge(TEXT("save"), OutError) && LoadResult(TEXT("save"), OutError);
}

int32 SProfileStandardEditor::GetErrorCountForEvidence() const
{
    int32 Count = 0;
    for (const TPair<FString, FFieldPtr>& Pair : FieldsByPath)
        Count += Pair.Value->Error.IsEmpty() ? 0 : 1;
    return Count;
}
#endif

bool SProfileStandardEditor::Describe(FString& OutError)
{
    return RunEditorBridge(TEXT("describe"), OutError) && LoadResult(TEXT("describe"), OutError);
}

bool SProfileStandardEditor::RunEditorBridge(const FString& Action, FString& OutError)
{
    TSharedRef<FJsonObject> Request = MakeShared<FJsonObject>();
    Request->SetStringField(TEXT("action"), Action);
    Request->SetStringField(TEXT("source_path"), SourcePath);
    Request->SetStringField(TEXT("project_profile_root"), ProjectProfileRoot);
    Request->SetStringField(TEXT("result_path"), ResultPath);
    if (Action != TEXT("describe")) Request->SetObjectField(TEXT("values"), BuildValuesObject());
    FString Json;
    const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Json);
    FJsonSerializer::Serialize(Request, Writer);
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(RequestPath), true);
    if (!FFileHelper::SaveStringToFile(
        Json, *RequestPath, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM))
    {
        OutError = TEXT("无法写入标准工作台请求；项目标准未改变");
        return false;
    }
    IPythonScriptPlugin* Python = IPythonScriptPlugin::Get();
    if (!Python || (!Python->IsPythonInitialized() && !Python->ForceEnablePythonAtRuntime()))
    {
        OutError = TEXT("Python Script Plugin 未就绪");
        return false;
    }
    FString SafePath = RequestPath.Replace(TEXT("\\"), TEXT("/"));
    SafePath.ReplaceInline(TEXT("'"), TEXT("\\'"));
    const FString Command = FString::Printf(
        TEXT("import run_asset_audit; run_asset_audit.profile_editor_from_request_file(r'%s')"),
        *SafePath);
    if (!Python->ExecPythonCommand(*Command))
    {
        OutError = TEXT("标准工作台执行失败；项目标准未改变");
        return false;
    }
    return true;
}

bool SProfileStandardEditor::LoadResult(const FString& Action, FString& OutError)
{
    FString Json;
    TSharedPtr<FJsonObject> Root;
    if (!FFileHelper::LoadFileToString(Json, *ResultPath)
        || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Json), Root)
        || !Root.IsValid()
        || Root->GetStringField(TEXT("schema_version")) != TEXT("unreal-profile-editor-view@1.0.0"))
    {
        OutError = TEXT("标准工作台返回数据无效");
        return false;
    }
    if (Action == TEXT("describe"))
    {
        AssetTypeLabel = Root->GetStringField(TEXT("asset_type_label"));
        ProfileId = Root->GetStringField(TEXT("profile_id"));
        ProfileVersion = Root->GetStringField(TEXT("profile_version"));
        IdentityFields.Reset();
        Rules.Reset();
        FieldsByPath.Reset();
        auto ParseField = [this](const TSharedPtr<FJsonObject>& JsonField) -> FFieldPtr
        {
            FFieldPtr Field = MakeShared<FProfileEditorField>();
            Field->Path = JsonField->GetStringField(TEXT("path"));
            Field->Label = JsonField->GetStringField(TEXT("label"));
            Field->Kind = JsonField->GetStringField(TEXT("kind"));
            const TSharedPtr<FJsonValue> Value = JsonField->TryGetField(TEXT("value"));
            Field->bBoolValue = Value.IsValid() && Value->Type == EJson::Boolean && Value->AsBool();
            Field->Value = JsonDisplay(Value);
            for (const TSharedPtr<FJsonValue>& Option : JsonField->GetArrayField(TEXT("options")))
                Field->Options.Add(MakeShared<FString>(Option->AsString()));
            FieldsByPath.Add(Field->Path, Field);
            return Field;
        };
        for (const TSharedPtr<FJsonValue>& Value : Root->GetArrayField(TEXT("identity_fields")))
            IdentityFields.Add(ParseField(Value->AsObject()));
        for (const TSharedPtr<FJsonValue>& Value : Root->GetArrayField(TEXT("rules")))
        {
            const TSharedPtr<FJsonObject> JsonRule = Value->AsObject();
            FProfileEditorRule Rule;
            Rule.RuleId = JsonRule->GetStringField(TEXT("rule_id"));
            Rule.Label = JsonRule->GetStringField(TEXT("label"));
            for (const TSharedPtr<FJsonValue>& FieldValue : JsonRule->GetArrayField(TEXT("fields")))
                Rule.Fields.Add(ParseField(FieldValue->AsObject()));
            Rules.Add(MoveTemp(Rule));
        }
        StatusMessage = TEXT("项目标准已载入 · 修改后先预览差异");
        return true;
    }
    ClearFieldErrors();
    Changes.Reset();
    const TSharedPtr<FJsonObject>* Errors = nullptr;
    if (Root->TryGetObjectField(TEXT("errors"), Errors) && Errors)
    {
        for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : (*Errors)->Values)
            if (FFieldPtr* Field = FieldsByPath.Find(Pair.Key)) (*Field)->Error = Pair.Value->AsString();
    }
    for (const TSharedPtr<FJsonValue>& Value : Root->GetArrayField(TEXT("changes")))
    {
        const TSharedPtr<FJsonObject> JsonChange = Value->AsObject();
        FChangePtr Change = MakeShared<FProfileEditorChange>();
        Change->Path = JsonChange->GetStringField(TEXT("path"));
        Change->Label = JsonChange->GetStringField(TEXT("label"));
        Change->Change = JsonChange->GetStringField(TEXT("change"));
        Change->Before = JsonChange->GetStringField(TEXT("before"));
        Change->After = JsonChange->GetStringField(TEXT("after"));
        Changes.Add(Change);
    }
    if (ChangeList.IsValid()) ChangeList->RequestListRefresh();
    const FString Status = Root->GetStringField(TEXT("status"));
    bLastResultInvalid = Status == TEXT("invalid");
    bPreviewCurrent = Action == TEXT("preview") && !bLastResultInvalid;
    if (Status == TEXT("saved"))
    {
        bPreviewCurrent = false;
        ProfileId = Root->GetStringField(TEXT("profile_id"));
        ProfileVersion = Root->GetStringField(TEXT("profile_version"));
        StatusMessage = FString::Printf(TEXT("项目标准已保存 · %s v%s"), *ProfileId, *ProfileVersion);
        OnSaved.ExecuteIfBound();
    }
    else if (bLastResultInvalid)
    {
        StatusMessage = FString::Printf(TEXT("发现 %d 个字段问题 · 请按红色提示修正"), Errors ? (*Errors)->Values.Num() : 0);
    }
    else
    {
        StatusMessage = Changes.IsEmpty()
            ? TEXT("当前内容与已保存标准一致")
            : FString::Printf(TEXT("差异预检完成 · %d 项变化待保存"), Changes.Num());
    }
    return true;
}

TSharedRef<SWidget> SProfileStandardEditor::BuildWorkspace()
{
    TSharedRef<SVerticalBox> Identity = SNew(SVerticalBox);
    for (const FFieldPtr& Field : IdentityFields)
        Identity->AddSlot().AutoHeight().Padding(0, 3)[BuildField(Field)];
    TSharedRef<SVerticalBox> RuleStack = SNew(SVerticalBox);
    for (const FProfileEditorRule& Rule : Rules)
        RuleStack->AddSlot().AutoHeight().Padding(0, 0, 0, 8)[BuildRule(Rule)];

    return SNew(SBorder)
        .BorderImage(FAppStyle::GetBrush(TEXT("Brushes.Panel")))
        .Padding(0)
        [
            SNew(SVerticalBox)
            + SVerticalBox::Slot().AutoHeight()
            [
                SNew(SBorder)
                .BorderImage(FAppStyle::GetBrush(TEXT("Brushes.Header")))
                .BorderBackgroundColor(FLinearColor(0.025f, 0.10f, 0.11f, 1.0f))
                .Padding(FMargin(20, 15))
                [
                    SNew(SHorizontalBox)
                    + SHorizontalBox::Slot().FillWidth(1)
                    [
                        SNew(SVerticalBox)
                        + SVerticalBox::Slot().AutoHeight()
                        [SNew(STextBlock).Text(FText::FromString(TEXT("项目验收标准工作台"))).Font(FAppStyle::GetFontStyle(TEXT("HeadingMedium")))]
                        + SVerticalBox::Slot().AutoHeight().Padding(0, 4, 0, 0)
                        [SNew(STextBlock).Text(FText::FromString(TEXT("规则刻度 · 差异预检 · 项目配置"))).ColorAndOpacity(StandardCyan)]
                    ]
                    + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
                    [
                        SNew(SBorder)
                        .BorderImage(FAppStyle::GetBrush(TEXT("Brushes.Header")))
                        .Padding(FMargin(10, 5))
                        [SNew(STextBlock).Text(FText::FromString(AssetTypeLabel)).ColorAndOpacity(StandardCyan)]
                    ]
                ]
            ]
            + SVerticalBox::Slot().FillHeight(1).Padding(16, 14, 16, 10)
            [
                SNew(SSplitter)
                + SSplitter::Slot().Value(0.64f).MinSize(560)
                [
                    SNew(SScrollBox)
                    + SScrollBox::Slot()
                    [
                        SNew(SVerticalBox)
                        + SVerticalBox::Slot().AutoHeight()
                        [SNew(STextBlock).Text(FText::FromString(TEXT("标准身份"))).Font(FAppStyle::GetFontStyle(TEXT("HeadingSmall")))]
                        + SVerticalBox::Slot().AutoHeight().Padding(0, 8, 0, 16)[Identity]
                        + SVerticalBox::Slot().AutoHeight()
                        [SNew(STextBlock).Text(FText::FromString(TEXT("规则刻度"))).Font(FAppStyle::GetFontStyle(TEXT("HeadingSmall")))]
                        + SVerticalBox::Slot().AutoHeight().Padding(0, 8, 8, 0)[RuleStack]
                    ]
                ]
                + SSplitter::Slot().Value(0.36f).MinSize(360)
                [
                    SNew(SBorder)
                    .BorderImage(FAppStyle::GetBrush(TEXT("Brushes.Recessed")))
                    .Padding(14)
                    [
                        SNew(SVerticalBox)
                        + SVerticalBox::Slot().AutoHeight()
                        [SNew(STextBlock).Text(FText::FromString(TEXT("保存前差异"))).Font(FAppStyle::GetFontStyle(TEXT("HeadingSmall")))]
                        + SVerticalBox::Slot().AutoHeight().Padding(0, 4, 0, 10)
                        [SNew(STextBlock).Text(this, &SProfileStandardEditor::GetChangeSummaryText).AutoWrapText(true).ColorAndOpacity(FSlateColor::UseSubduedForeground())]
                        + SVerticalBox::Slot().FillHeight(1)
                        [
                            SAssignNew(ChangeList, SListView<FChangePtr>)
                            .ListItemsSource(&Changes)
                            .OnGenerateRow(this, &SProfileStandardEditor::GenerateChangeRow)
                            .HeaderRow
                            (
                                SNew(SHeaderRow)
                                + SHeaderRow::Column(TEXT("Change")).DefaultLabel(FText::FromString(TEXT("变化"))).FixedWidth(56)
                                + SHeaderRow::Column(TEXT("Field")).DefaultLabel(FText::FromString(TEXT("字段"))).FillWidth(0.35f)
                                + SHeaderRow::Column(TEXT("Before")).DefaultLabel(FText::FromString(TEXT("保存值"))).FillWidth(0.3f)
                                + SHeaderRow::Column(TEXT("After")).DefaultLabel(FText::FromString(TEXT("当前值"))).FillWidth(0.35f)
                            )
                        ]
                    ]
                ]
            ]
            + SVerticalBox::Slot().AutoHeight()
            [
                SNew(SBorder)
                .BorderImage(FAppStyle::GetBrush(TEXT("Brushes.Header")))
                .Padding(FMargin(16, 10))
                [
                    SNew(SHorizontalBox)
                    + SHorizontalBox::Slot().FillWidth(1).VAlign(VAlign_Center)
                    [SNew(STextBlock).Text(this, &SProfileStandardEditor::GetStatusText).ColorAndOpacity(this, &SProfileStandardEditor::GetStatusColor)]
                    + SHorizontalBox::Slot().AutoWidth().Padding(8, 0)
                    [SNew(SButton).Text(FText::FromString(TEXT("预览差异"))).OnClicked(this, &SProfileStandardEditor::PreviewChanges)]
                    + SHorizontalBox::Slot().AutoWidth().Padding(0, 0, 8, 0)
                    [SNew(SButton).ButtonStyle(FAppStyle::Get(), TEXT("PrimaryButton")).Text(FText::FromString(TEXT("保存项目标准"))).IsEnabled(this, &SProfileStandardEditor::CanSave).OnClicked(this, &SProfileStandardEditor::SaveProfile)]
                    + SHorizontalBox::Slot().AutoWidth()
                    [SNew(SButton).Text(FText::FromString(TEXT("关闭"))).OnClicked(this, &SProfileStandardEditor::CloseWindow)]
                ]
            ]
        ];
}

TSharedRef<SWidget> SProfileStandardEditor::BuildField(const FFieldPtr& Field)
{
    TSharedRef<SVerticalBox> Box = SNew(SVerticalBox);
    if (Field->Kind == TEXT("boolean"))
    {
        Box->AddSlot().AutoHeight()
        [
            SNew(SCheckBox)
            .IsChecked_Lambda([Field]() { return Field->bBoolValue ? ECheckBoxState::Checked : ECheckBoxState::Unchecked; })
            .OnCheckStateChanged_Lambda([this, Field](ECheckBoxState State) { Field->bBoolValue = State == ECheckBoxState::Checked; MarkDirty(); })
            [SNew(STextBlock).Text(FText::FromString(Field->Label))]
        ];
    }
    else
    {
        Box->AddSlot().AutoHeight().Padding(0, 0, 0, 2)
        [SNew(STextBlock).Text(FText::FromString(Field->Label)).ColorAndOpacity(FSlateColor::UseSubduedForeground())];
        if (Field->Kind == TEXT("enum"))
        {
            TSharedPtr<FString> Initial;
            for (const TSharedPtr<FString>& Option : Field->Options)
                if (*Option == Field->Value) Initial = Option;
            Box->AddSlot().AutoHeight()
            [
                SNew(SComboBox<TSharedPtr<FString>>)
                .OptionsSource(&Field->Options)
                .InitiallySelectedItem(Initial)
                .OnGenerateWidget(this, &SProfileStandardEditor::GenerateEnumOption)
                .OnSelectionChanged_Lambda([this, Field](TSharedPtr<FString> Item, ESelectInfo::Type) { if (Item.IsValid()) { Field->Value = *Item; MarkDirty(); } })
                [SNew(STextBlock).Text_Lambda([Field]() { return LocalizedEnum(Field->Value); })]
            ];
        }
        else
        {
            Box->AddSlot().AutoHeight()
            [
                SAssignNew(Field->TextInput, SEditableTextBox)
                .Text(FText::FromString(Field->Value))
                .OnTextChanged_Lambda([this, Field](const FText& Text) { Field->Value = Text.ToString(); MarkDirty(); })
            ];
        }
    }
    Box->AddSlot().AutoHeight().Padding(0, 2, 0, 0)
    [
        SNew(STextBlock)
        .Text(this, &SProfileStandardEditor::GetFieldErrorText, Field)
        .Visibility(this, &SProfileStandardEditor::GetFieldErrorVisibility, Field)
        .ColorAndOpacity(StandardRed)
        .AutoWrapText(true)
    ];
    return Box;
}

TSharedRef<SWidget> SProfileStandardEditor::BuildRule(const FProfileEditorRule& Rule)
{
    TSharedRef<SVerticalBox> Fields = SNew(SVerticalBox);
    for (const FFieldPtr& Field : Rule.Fields)
        Fields->AddSlot().AutoHeight().Padding(0, 3)[BuildField(Field)];
    return SNew(SBorder)
        .BorderImage(FAppStyle::GetBrush(TEXT("Brushes.Header")))
        .Padding(FMargin(12, 9))
        [
            SNew(SVerticalBox)
            + SVerticalBox::Slot().AutoHeight()
            [
                SNew(SHorizontalBox)
                + SHorizontalBox::Slot().FillWidth(1)
                [SNew(STextBlock).Text(FText::FromString(Rule.Label)).Font(FAppStyle::GetFontStyle(TEXT("SmallFontBold")))]
                + SHorizontalBox::Slot().AutoWidth()
                [SNew(STextBlock).Text(FText::FromString(Rule.RuleId)).Font(FAppStyle::GetFontStyle(TEXT("SmallFont"))).ColorAndOpacity(FSlateColor::UseSubduedForeground())]
            ]
            + SVerticalBox::Slot().AutoHeight().Padding(0, 6, 0, 0)[Fields]
        ];
}

TSharedRef<ITableRow> SProfileStandardEditor::GenerateChangeRow(
    FChangePtr Item, const TSharedRef<STableViewBase>& OwnerTable)
{
    return SNew(SProfileChangeRow, OwnerTable).Item(Item);
}

TSharedRef<SWidget> SProfileStandardEditor::GenerateEnumOption(TSharedPtr<FString> Item) const
{
    return SNew(STextBlock).Text(Item.IsValid() ? LocalizedEnum(*Item) : FText::GetEmpty());
}

FReply SProfileStandardEditor::PreviewChanges()
{
    FString Error;
    if (!RunEditorBridge(TEXT("preview"), Error) || !LoadResult(TEXT("preview"), Error))
    {
        StatusMessage = Error;
        bLastResultInvalid = true;
    }
    return FReply::Handled();
}

FReply SProfileStandardEditor::SaveProfile()
{
    if (!CanSave()) return FReply::Handled();
    FString Error;
    if (!RunEditorBridge(TEXT("save"), Error) || !LoadResult(TEXT("save"), Error))
    {
        StatusMessage = Error;
        bLastResultInvalid = true;
    }
    return FReply::Handled();
}

FReply SProfileStandardEditor::CloseWindow()
{
    const TSharedPtr<SWindow> Window = FSlateApplication::Get().FindWidgetWindow(AsShared());
    if (Window.IsValid()) Window->RequestDestroyWindow();
    return FReply::Handled();
}

void SProfileStandardEditor::MarkDirty()
{
    bPreviewCurrent = false;
    bLastResultInvalid = false;
    Changes.Reset();
    ClearFieldErrors();
    if (ChangeList.IsValid()) ChangeList->RequestListRefresh();
    StatusMessage = TEXT("规则刻度已修改 · 请先预览差异");
}

void SProfileStandardEditor::ClearFieldErrors()
{
    for (const TPair<FString, FFieldPtr>& Pair : FieldsByPath) Pair.Value->Error.Reset();
}

bool SProfileStandardEditor::CanSave() const
{
    return bPreviewCurrent && !bLastResultInvalid && !Changes.IsEmpty();
}

FText SProfileStandardEditor::GetStatusText() const { return FText::FromString(StatusMessage); }

FText SProfileStandardEditor::GetChangeSummaryText() const
{
    if (bLastResultInvalid) return FText::FromString(TEXT("字段存在问题，修正后重新预览。保存按钮保持禁用。"));
    if (!bPreviewCurrent) return FText::FromString(TEXT("修改左侧规则后点击“预览差异”。只有当前预览有效时才允许保存。"));
    if (Changes.IsEmpty()) return FText::FromString(TEXT("没有待保存变化。"));
    return FText::FromString(FString::Printf(TEXT("%d 项变化已经通过合同校验。"), Changes.Num()));
}

FText SProfileStandardEditor::GetEnumLabel(FFieldPtr Field) const { return LocalizedEnum(Field->Value); }
FText SProfileStandardEditor::GetFieldErrorText(FFieldPtr Field) const { return FText::FromString(Field->Error); }
EVisibility SProfileStandardEditor::GetFieldErrorVisibility(FFieldPtr Field) const { return Field->Error.IsEmpty() ? EVisibility::Collapsed : EVisibility::Visible; }

FSlateColor SProfileStandardEditor::GetStatusColor() const
{
    if (bLastResultInvalid) return StandardRed;
    if (bPreviewCurrent && Changes.IsEmpty()) return StandardGreen;
    if (bPreviewCurrent) return StandardCyan;
    return FSlateColor::UseSubduedForeground();
}

TSharedRef<FJsonObject> SProfileStandardEditor::BuildValuesObject() const
{
    TSharedRef<FJsonObject> Values = MakeShared<FJsonObject>();
    for (const TPair<FString, FFieldPtr>& Pair : FieldsByPath)
    {
        if (Pair.Value->Kind == TEXT("boolean")) Values->SetBoolField(Pair.Key, Pair.Value->bBoolValue);
        else Values->SetStringField(Pair.Key, Pair.Value->Value);
    }
    return Values;
}
