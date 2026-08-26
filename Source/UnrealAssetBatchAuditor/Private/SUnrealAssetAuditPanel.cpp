#include "SUnrealAssetAuditPanel.h"

#include "AssetRegistry/AssetData.h"
#include "ContentBrowserModule.h"
#include "IContentBrowserSingleton.h"
#include "DesktopPlatformModule.h"
#include "Framework/Application/SlateApplication.h"
#include "HAL/PlatformProcess.h"
#include "Interfaces/IPluginManager.h"
#include "IPythonScriptPlugin.h"
#include "JsonObjectConverter.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Modules/ModuleManager.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Widgets/Images/SImage.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SComboBox.h"
#include "Widgets/Input/SEditableTextBox.h"
#include "Widgets/Input/SSearchBox.h"
#include "Widgets/Input/SSpinBox.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/Layout/SSplitter.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/Views/SHeaderRow.h"
#include "Widgets/Views/SListView.h"

namespace
{
const FLinearColor CyanAccent(0.10f, 0.72f, 0.82f, 1.0f);
const FLinearColor GreenAccent(0.20f, 0.75f, 0.45f, 1.0f);
const FLinearColor AmberAccent(0.95f, 0.62f, 0.12f, 1.0f);
const FLinearColor RedAccent(0.95f, 0.25f, 0.22f, 1.0f);

FString JsonValueToDisplay(const TSharedPtr<FJsonValue>& Value)
{
    if (!Value.IsValid())
    {
        return TEXT("—");
    }
    switch (Value->Type)
    {
    case EJson::String: return Value->AsString();
    case EJson::Number: return FString::SanitizeFloat(Value->AsNumber());
    case EJson::Boolean: return Value->AsBool() ? TEXT("是") : TEXT("否");
    case EJson::Null: return TEXT("—");
    default: return TEXT("[复杂值]");
    }
}

FText RuleLabel(const FString& RuleId)
{
    if (RuleId.Contains(TEXT("triangle_budget"))) return FText::FromString(TEXT("三角形预算"));
    if (RuleId.Contains(TEXT("vertex_budget"))) return FText::FromString(TEXT("顶点预算"));
    if (RuleId.Contains(TEXT("material_slots"))) return FText::FromString(TEXT("材质槽"));
    if (RuleId.Contains(TEXT("lod_count"))) return FText::FromString(TEXT("LOD 数量"));
    if (RuleId.Contains(TEXT("nanite_state"))) return FText::FromString(TEXT("Nanite 状态"));
    if (RuleId == TEXT("collection.failure")) return FText::FromString(TEXT("采集失败"));
    return FText::FromString(RuleId);
}

FString LocalizedIssueMessage(const FString& RuleId, const FString& Observed, const FString& Expected)
{
    if (RuleId.Contains(TEXT("triangle_budget")))
        return FString::Printf(TEXT("LOD0 三角形为 %s，超过 Profile 上限 %s。"), *Observed, *Expected);
    if (RuleId.Contains(TEXT("vertex_budget")))
        return FString::Printf(TEXT("LOD0 顶点为 %s，超过 Profile 上限 %s。"), *Observed, *Expected);
    if (RuleId.Contains(TEXT("material_slots")))
        return FString::Printf(TEXT("材质槽为 %s，超过 Profile 上限 %s。"), *Observed, *Expected);
    if (RuleId.Contains(TEXT("lod_count")))
        return FString::Printf(TEXT("LOD 数量为 %s，低于 Profile 下限 %s。"), *Observed, *Expected);
    if (RuleId.Contains(TEXT("nanite_state")))
        return FString::Printf(TEXT("Nanite 状态为 %s，Profile 期望为 %s。"), *Observed, *Expected);
    return FString();
}

FLinearColor SeverityColor(const FString& Severity)
{
    if (Severity == TEXT("error")) return RedAccent;
    if (Severity == TEXT("warning")) return AmberAccent;
    return CyanAccent;
}

FText SeverityLabel(const FString& Severity)
{
    if (Severity == TEXT("error")) return FText::FromString(TEXT("错误"));
    if (Severity == TEXT("warning")) return FText::FromString(TEXT("警告"));
    return FText::FromString(TEXT("提示"));
}
}

class SAuditIssueRow final : public SMultiColumnTableRow<SUnrealAssetAuditPanel::FIssuePtr>
{
public:
    SLATE_BEGIN_ARGS(SAuditIssueRow) {}
        SLATE_ARGUMENT(SUnrealAssetAuditPanel::FIssuePtr, Item)
    SLATE_END_ARGS()

    void Construct(const FArguments& InArgs, const TSharedRef<STableViewBase>& OwnerTable)
    {
        Item = InArgs._Item;
        SMultiColumnTableRow::Construct(
            FSuperRowType::FArguments().Padding(FMargin(4.0f, 3.0f)), OwnerTable);
    }

    virtual TSharedRef<SWidget> GenerateWidgetForColumn(const FName& ColumnName) override
    {
        if (ColumnName == TEXT("Severity"))
        {
            return SNew(STextBlock)
                .Text(SeverityLabel(Item->Severity))
                .ColorAndOpacity(SeverityColor(Item->Severity))
                .Font(FAppStyle::GetFontStyle(TEXT("SmallFontBold")));
        }
        if (ColumnName == TEXT("Asset"))
        {
            FString Name;
            Item->AssetPath.Split(TEXT("."), nullptr, &Name, ESearchCase::IgnoreCase, ESearchDir::FromEnd);
            return SNew(STextBlock).Text(FText::FromString(Name.IsEmpty() ? Item->AssetPath : Name)).ToolTipText(FText::FromString(Item->AssetPath));
        }
        if (ColumnName == TEXT("Rule"))
        {
            return SNew(STextBlock).Text(RuleLabel(Item->RuleId)).ToolTipText(FText::FromString(Item->RuleId));
        }
        if (ColumnName == TEXT("Observed"))
        {
            return SNew(STextBlock).Text(FText::FromString(Item->Observed));
        }
        if (ColumnName == TEXT("Expected"))
        {
            return SNew(STextBlock).Text(FText::FromString(Item->Expected));
        }
        return SNew(STextBlock).Text(FText::FromString(Item->Message)).ToolTipText(FText::FromString(Item->Message));
    }

private:
    SUnrealAssetAuditPanel::FIssuePtr Item;
};

void SUnrealAssetAuditPanel::Construct(const FArguments& InArgs)
{
    const TSharedPtr<IPlugin> Plugin = IPluginManager::Get().FindPlugin(TEXT("UnrealAssetBatchAuditor"));
    const FString ProfilesRoot = Plugin.IsValid()
        ? FPaths::Combine(Plugin->GetBaseDir(), TEXT("Resources/Profiles"))
        : FString();
    ProfileOptions = {
        MakeShared<FAuditProfileOption>(FAuditProfileOption{
            TEXT("桌面平衡（推荐演示）"),
            TEXT("三角形 ≤ 2,000 · 顶点 ≤ 1,500 · 材质槽 ≤ 2 · LOD ≥ 1 · Nanite 不限"),
            FPaths::Combine(ProfilesRoot, TEXT("desktop-balanced.v1.json"))}),
        MakeShared<FAuditProfileOption>(FAuditProfileOption{
            TEXT("移动端严格"),
            TEXT("三角形 ≤ 500 · 顶点 ≤ 400 · 材质槽 ≤ 1 · LOD ≥ 2 · 要求启用 Nanite"),
            FPaths::Combine(ProfilesRoot, TEXT("mobile-strict.v1.json"))}),
        MakeShared<FAuditProfileOption>(FAuditProfileOption{
            TEXT("宽松复核"),
            TEXT("三角形 ≤ 10,000 · 顶点 ≤ 7,000 · 材质槽 ≤ 4 · LOD ≥ 1 · Nanite 不限"),
            FPaths::Combine(ProfilesRoot, TEXT("review-lenient.v1.json"))})
    };
    SelectedProfile = ProfileOptions[0];
    ReportPath = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("UnrealAssetBatchAuditor/Reports/latest-report.json"));
    StatusMessage = TEXT("选择 Static Mesh，然后开始只读审计");

    ChildSlot
    [
        SNew(SBorder)
        .BorderImage(FAppStyle::GetBrush(TEXT("Brushes.Panel")))
        .Padding(0)
        [
            SNew(SVerticalBox)
            + SVerticalBox::Slot().AutoHeight()
            [
                SNew(SBorder)
                .BorderImage(FAppStyle::GetBrush(TEXT("Brushes.Header")))
                .BorderBackgroundColor(FLinearColor(0.035f, 0.08f, 0.10f, 1.0f))
                .Padding(FMargin(18, 13))
                [
                    SNew(SHorizontalBox)
                    + SHorizontalBox::Slot().FillWidth(1)
                    [
                        SNew(SVerticalBox)
                        + SVerticalBox::Slot().AutoHeight()
                        [
                            SNew(STextBlock)
                            .Text(FText::FromString(TEXT("资产批量审计")))
                            .Font(FAppStyle::GetFontStyle(TEXT("HeadingMedium")))
                        ]
                        + SVerticalBox::Slot().AutoHeight().Padding(0, 3, 0, 0)
                        [
                            SNew(STextBlock)
                            .Text(FText::FromString(TEXT("PROFILE 驱动 · STATIC MESH · 只读证据链")))
                            .Font(FAppStyle::GetFontStyle(TEXT("SmallFont")))
                            .ColorAndOpacity(CyanAccent)
                        ]
                    ]
                    + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
                    [
                        SNew(STextBlock)
                        .Text(this, &SUnrealAssetAuditPanel::GetStatusText)
                        .ColorAndOpacity(FSlateColor::UseSubduedForeground())
                    ]
                ]
            ]
            + SVerticalBox::Slot().FillHeight(1)
            [
                SNew(SSplitter)
                + SSplitter::Slot().Value(0.27f).MinSize(260)
                [
                    SNew(SBorder)
                    .BorderImage(FAppStyle::GetBrush(TEXT("Brushes.Recessed")))
                    .Padding(16)
                    [
                        SNew(SVerticalBox)
                        + SVerticalBox::Slot().AutoHeight()
                        [
                            SNew(STextBlock).Text(FText::FromString(TEXT("审计设置"))).Font(FAppStyle::GetFontStyle(TEXT("HeadingSmall")))
                        ]
                        + SVerticalBox::Slot().AutoHeight().Padding(0, 16, 0, 4)
                        [
                            SNew(STextBlock).Text(FText::FromString(TEXT("检查规则"))).ColorAndOpacity(FSlateColor::UseSubduedForeground())
                        ]
                        + SVerticalBox::Slot().AutoHeight()
                        [
                            SAssignNew(ProfileComboBox, SComboBox<FProfilePtr>)
                            .OptionsSource(&ProfileOptions)
                            .InitiallySelectedItem(SelectedProfile)
                            .OnGenerateWidget(this, &SUnrealAssetAuditPanel::GenerateProfileOption)
                            .OnSelectionChanged(this, &SUnrealAssetAuditPanel::HandleProfileChanged)
                            [
                                SNew(STextBlock)
                                .Text(this, &SUnrealAssetAuditPanel::GetSelectedProfileLabel)
                            ]
                        ]
                        + SVerticalBox::Slot().AutoHeight().Padding(0, 6, 0, 0)
                        [
                            SNew(STextBlock)
                            .Text(this, &SUnrealAssetAuditPanel::GetSelectedProfileSummary)
                            .AutoWrapText(true)
                            .ColorAndOpacity(FSlateColor::UseSubduedForeground())
                        ]
                        + SVerticalBox::Slot().AutoHeight().Padding(0, 8, 0, 0)
                        [
                            SNew(SButton).Text(FText::FromString(TEXT("导入自定义规则…"))).OnClicked(this, &SUnrealAssetAuditPanel::BrowseProfile)
                        ]
                        + SVerticalBox::Slot().AutoHeight().Padding(0, 18, 0, 4)
                        [
                            SNew(STextBlock).Text(FText::FromString(TEXT("审计范围"))).ColorAndOpacity(FSlateColor::UseSubduedForeground())
                        ]
                        + SVerticalBox::Slot().AutoHeight()
                        [
                            SNew(SBorder)
                            .BorderImage(FAppStyle::GetBrush(TEXT("Brushes.Header")))
                            .Padding(10)
                            [
                                SNew(STextBlock).Text(this, &SUnrealAssetAuditPanel::GetSelectionText).AutoWrapText(true)
                            ]
                        ]
                        + SVerticalBox::Slot().AutoHeight().Padding(0, 6, 0, 0)
                        [
                            SNew(SButton).Text(FText::FromString(TEXT("读取当前选择"))).OnClicked(this, &SUnrealAssetAuditPanel::RefreshSelection)
                        ]
                        + SVerticalBox::Slot().AutoHeight().Padding(0, 18, 0, 4)
                        [
                            SNew(STextBlock).Text(FText::FromString(TEXT("单批资产数"))).ColorAndOpacity(FSlateColor::UseSubduedForeground())
                        ]
                        + SVerticalBox::Slot().AutoHeight()
                        [
                            SNew(SSpinBox<int32>).MinValue(1).MaxValue(1024).Value(BatchSize).OnValueChanged_Lambda([this](int32 Value) { BatchSize = Value; })
                        ]
                        + SVerticalBox::Slot().FillHeight(1)
                        + SVerticalBox::Slot().AutoHeight().Padding(0, 16, 0, 0)
                        [
                            SNew(SButton)
                            .ButtonStyle(FAppStyle::Get(), TEXT("PrimaryButton"))
                            .HAlign(HAlign_Center)
                            .ContentPadding(FMargin(12, 8))
                            .Text(FText::FromString(TEXT("开始只读审计")))
                            .IsEnabled(this, &SUnrealAssetAuditPanel::CanRunAudit)
                            .OnClicked(this, &SUnrealAssetAuditPanel::RunAudit)
                        ]
                    ]
                ]
                + SSplitter::Slot().Value(0.73f).MinSize(520)
                [
                    SNew(SVerticalBox)
                    + SVerticalBox::Slot().AutoHeight().Padding(14, 12, 14, 10)
                    [
                        SNew(SHorizontalBox)
                        + SHorizontalBox::Slot().FillWidth(1)[BuildSummaryCell(FText::FromString(TEXT("已扫描")), TAttribute<FText>::CreateSP(this, &SUnrealAssetAuditPanel::GetAssetCountText), CyanAccent)]
                        + SHorizontalBox::Slot().FillWidth(1).Padding(6, 0)[BuildSummaryCell(FText::FromString(TEXT("通过资产")), TAttribute<FText>::CreateSP(this, &SUnrealAssetAuditPanel::GetPassCountText), GreenAccent)]
                        + SHorizontalBox::Slot().FillWidth(1).Padding(6, 0)[BuildSummaryCell(FText::FromString(TEXT("问题")), TAttribute<FText>::CreateSP(this, &SUnrealAssetAuditPanel::GetIssueCountText), AmberAccent)]
                        + SHorizontalBox::Slot().FillWidth(1)[BuildSummaryCell(FText::FromString(TEXT("采集失败")), TAttribute<FText>::CreateSP(this, &SUnrealAssetAuditPanel::GetFailureCountText), RedAccent)]
                    ]
                    + SVerticalBox::Slot().AutoHeight().Padding(14, 0, 14, 8)
                    [
                        SAssignNew(SearchInput, SSearchBox)
                        .HintText(FText::FromString(TEXT("搜索资产、规则或说明")))
                        .OnTextChanged(this, &SUnrealAssetAuditPanel::HandleSearchChanged)
                    ]
                    + SVerticalBox::Slot().FillHeight(1).Padding(14, 0, 14, 10)
                    [
                        SAssignNew(IssueList, SListView<FIssuePtr>)
                        .ListItemsSource(&FilteredIssues)
                        .SelectionMode(ESelectionMode::Single)
                        .OnGenerateRow(this, &SUnrealAssetAuditPanel::GenerateIssueRow)
                        .HeaderRow
                        (
                            SNew(SHeaderRow)
                            + SHeaderRow::Column(TEXT("Severity")).DefaultLabel(FText::FromString(TEXT("级别"))).FixedWidth(68)
                            + SHeaderRow::Column(TEXT("Asset")).DefaultLabel(FText::FromString(TEXT("资产"))).FillWidth(0.25f)
                            + SHeaderRow::Column(TEXT("Rule")).DefaultLabel(FText::FromString(TEXT("检查项"))).FillWidth(0.16f)
                            + SHeaderRow::Column(TEXT("Observed")).DefaultLabel(FText::FromString(TEXT("实测"))).FixedWidth(82)
                            + SHeaderRow::Column(TEXT("Expected")).DefaultLabel(FText::FromString(TEXT("阈值"))).FixedWidth(82)
                            + SHeaderRow::Column(TEXT("Message")).DefaultLabel(FText::FromString(TEXT("证据说明"))).FillWidth(0.34f)
                        )
                    ]
                    + SVerticalBox::Slot().AutoHeight()
                    [
                        SNew(SBorder)
                        .BorderImage(FAppStyle::GetBrush(TEXT("Brushes.Header")))
                        .Padding(FMargin(14, 9))
                        [
                            SNew(SHorizontalBox)
                            + SHorizontalBox::Slot().FillWidth(1).VAlign(VAlign_Center)
                            [
                                SNew(STextBlock)
                                .Text_Lambda([this] { return FText::FromString(ReportPath); })
                                .Font(FAppStyle::GetFontStyle(TEXT("SmallFont")))
                                .ColorAndOpacity(FSlateColor::UseSubduedForeground())
                                .ToolTipText_Lambda([this] { return FText::FromString(ReportPath); })
                            ]
                            + SHorizontalBox::Slot().AutoWidth().Padding(8, 0, 0, 0)
                            [
                                SNew(SButton).Text(FText::FromString(TEXT("打开报告目录"))).OnClicked(this, &SUnrealAssetAuditPanel::OpenReportFolder)
                            ]
                        ]
                    ]
                ]
            ]
        ]
    ];

    RefreshSelection();
}

TSharedRef<SWidget> SUnrealAssetAuditPanel::BuildSummaryCell(
    const FText& Label, TAttribute<FText> Value, const FLinearColor& Accent) const
{
    return SNew(SBorder)
        .BorderImage(FAppStyle::GetBrush(TEXT("Brushes.Header")))
        .BorderBackgroundColor(FLinearColor(Accent.R * 0.10f, Accent.G * 0.10f, Accent.B * 0.10f, 1.0f))
        .Padding(FMargin(12, 8))
        [
            SNew(SHorizontalBox)
            + SHorizontalBox::Slot().FillWidth(1).VAlign(VAlign_Center)
            [SNew(STextBlock).Text(Label).ColorAndOpacity(FSlateColor::UseSubduedForeground())]
            + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
            [SNew(STextBlock).Text(Value).Font(FAppStyle::GetFontStyle(TEXT("HeadingSmall"))).ColorAndOpacity(Accent)]
        ];
}

FReply SUnrealAssetAuditPanel::RefreshSelection()
{
    SelectedAssetPaths.Reset();
    FContentBrowserModule& ContentBrowser = FModuleManager::LoadModuleChecked<FContentBrowserModule>(TEXT("ContentBrowser"));
    TArray<FAssetData> SelectedAssets;
    ContentBrowser.Get().GetSelectedAssets(SelectedAssets);
    for (const FAssetData& Asset : SelectedAssets)
    {
        SelectedAssetPaths.Add(Asset.GetSoftObjectPath().ToString());
    }
    SelectedAssetPaths.Sort();
    StatusMessage = SelectedAssetPaths.IsEmpty()
        ? TEXT("尚未选择资产")
        : FString::Printf(TEXT("已读取 %d 个 Content Browser 资产"), SelectedAssetPaths.Num());
    return FReply::Handled();
}

FReply SUnrealAssetAuditPanel::BrowseProfile()
{
    IDesktopPlatform* DesktopPlatform = FDesktopPlatformModule::Get();
    if (!DesktopPlatform) return FReply::Handled();
    TArray<FString> Files;
    const void* Parent = FSlateApplication::Get().FindBestParentWindowHandleForDialogs(nullptr);
    const FString Current = SelectedProfile.IsValid() ? SelectedProfile->Path : FString();
    if (DesktopPlatform->OpenFileDialog(
        Parent, TEXT("选择审计 Profile"), FPaths::GetPath(Current), TEXT(""),
        TEXT("JSON Profile (*.json)|*.json"), EFileDialogFlags::None, Files) && !Files.IsEmpty())
    {
        FProfilePtr Custom = MakeShared<FAuditProfileOption>(FAuditProfileOption{
            FString::Printf(TEXT("自定义 · %s"), *FPaths::GetBaseFilename(Files[0])),
            TEXT("来自外部 JSON；阈值由该文件定义。"),
            Files[0],
            true});
        ProfileOptions.Add(Custom);
        SelectedProfile = Custom;
        ProfileComboBox->RefreshOptions();
        ProfileComboBox->SetSelectedItem(Custom);
    }
    return FReply::Handled();
}

FReply SUnrealAssetAuditPanel::RunAudit()
{
    if (!CanRunAudit()) return FReply::Handled();
    const FString ProfilePath = SelectedProfile->Path;
    if (!FPaths::FileExists(ProfilePath))
    {
        StatusMessage = TEXT("Profile 文件不存在，请重新选择");
        return FReply::Handled();
    }

    bAuditRunning = true;
    StatusMessage = TEXT("正在执行只读采集与规则检查…");

    TSharedRef<FJsonObject> Request = MakeShared<FJsonObject>();
    Request->SetStringField(TEXT("profile_path"), ProfilePath);
    Request->SetStringField(TEXT("output_path"), ReportPath);
    Request->SetNumberField(TEXT("batch_size"), BatchSize);
    TArray<TSharedPtr<FJsonValue>> Paths;
    for (const FString& Path : SelectedAssetPaths)
    {
        Paths.Add(MakeShared<FJsonValueString>(Path));
    }
    Request->SetArrayField(TEXT("asset_paths"), Paths);

    const FString RequestPath = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("UnrealAssetBatchAuditor/panel-request.json"));
    FString RequestJson;
    const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&RequestJson);
    FJsonSerializer::Serialize(Request, Writer);
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(RequestPath), true);
    if (!FFileHelper::SaveStringToFile(RequestJson, *RequestPath, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM))
    {
        bAuditRunning = false;
        StatusMessage = TEXT("无法写入审计请求文件");
        return FReply::Handled();
    }

    IPythonScriptPlugin* Python = IPythonScriptPlugin::Get();
    if (!Python || (!Python->IsPythonInitialized() && !Python->ForceEnablePythonAtRuntime()))
    {
        bAuditRunning = false;
        StatusMessage = TEXT("Python Script Plugin 未就绪");
        return FReply::Handled();
    }

    FString PythonPath = RequestPath.Replace(TEXT("\\"), TEXT("/"));
    PythonPath.ReplaceInline(TEXT("'"), TEXT("\\'"));
    const FString Command = FString::Printf(
        TEXT("import run_asset_audit; run_asset_audit.run_from_request_file(r'%s')"), *PythonPath);
    const bool bSucceeded = Python->ExecPythonCommand(*Command);
    bAuditRunning = false;
    if (!bSucceeded)
    {
        StatusMessage = TEXT("审计执行失败；详细堆栈已写入 Output Log");
        return FReply::Handled();
    }

    FString Error;
    if (!LoadReport(ReportPath, Error))
    {
        StatusMessage = FString::Printf(TEXT("报告读取失败：%s"), *Error);
        return FReply::Handled();
    }
    StatusMessage = FString::Printf(TEXT("审计完成 · %d 个资产 · %d 个问题"), AssetCount, IssueCount);
    return FReply::Handled();
}

bool SUnrealAssetAuditPanel::LoadReport(const FString& Path, FString& OutError)
{
    FString Json;
    if (!FFileHelper::LoadFileToString(Json, *Path))
    {
        OutError = TEXT("找不到输出文件");
        return false;
    }
    TSharedPtr<FJsonObject> Root;
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
    if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
    {
        OutError = TEXT("JSON 格式无效");
        return false;
    }

    AssetCount = Root->GetIntegerField(TEXT("asset_count"));
    IssueCount = Root->GetIntegerField(TEXT("issue_count"));
    FailureCount = Root->GetIntegerField(TEXT("collection_failure_count"));
    AllIssues.Reset();
    TSet<FString> AssetsWithIssues;

    TMap<FString, TSharedPtr<FJsonObject>> EvidenceById;
    for (const TSharedPtr<FJsonValue>& Value : Root->GetArrayField(TEXT("evidence")))
    {
        const TSharedPtr<FJsonObject> Evidence = Value->AsObject();
        if (Evidence.IsValid()) EvidenceById.Add(Evidence->GetStringField(TEXT("evidence_id")), Evidence);
    }
    for (const TSharedPtr<FJsonValue>& Value : Root->GetArrayField(TEXT("issues")))
    {
        const TSharedPtr<FJsonObject> Issue = Value->AsObject();
        if (!Issue.IsValid()) continue;
        FIssuePtr Item = MakeShared<FAuditPanelIssue>();
        Item->Severity = Issue->GetStringField(TEXT("severity"));
        Item->AssetPath = Issue->GetStringField(TEXT("asset_path"));
        Item->RuleId = Issue->GetStringField(TEXT("rule_id"));
        const FString RawMessage = Issue->GetStringField(TEXT("message"));
        AssetsWithIssues.Add(Item->AssetPath);
        if (const TSharedPtr<FJsonObject>* Evidence = EvidenceById.Find(Issue->GetStringField(TEXT("evidence_id"))))
        {
            Item->Metric = (*Evidence)->GetStringField(TEXT("metric"));
            Item->Observed = JsonValueToDisplay((*Evidence)->TryGetField(TEXT("observed")));
            Item->Expected = JsonValueToDisplay((*Evidence)->TryGetField(TEXT("expected")));
        }
        Item->Message = LocalizedIssueMessage(Item->RuleId, Item->Observed, Item->Expected);
        if (Item->Message.IsEmpty()) Item->Message = RawMessage;
        AllIssues.Add(Item);
    }
    for (const TSharedPtr<FJsonValue>& Value : Root->GetArrayField(TEXT("collection_failures")))
    {
        const TSharedPtr<FJsonObject> Failure = Value->AsObject();
        if (!Failure.IsValid()) continue;
        FIssuePtr Item = MakeShared<FAuditPanelIssue>();
        Item->Severity = TEXT("error");
        Item->AssetPath = Failure->GetStringField(TEXT("asset_path"));
        Item->RuleId = TEXT("collection.failure");
        Item->Metric = TEXT("collector");
        Item->Observed = Failure->GetStringField(TEXT("code"));
        Item->Expected = TEXT("Static Mesh");
        Item->Message = TEXT("资产无法作为 Static Mesh 读取；本项已隔离，其余资产继续审计。");
        AllIssues.Add(Item);
    }
    PassingAssetCount = FMath::Max(0, AssetCount - AssetsWithIssues.Num());
    RebuildFilteredIssues();
    return true;
}

void SUnrealAssetAuditPanel::HandleSearchChanged(const FText& Text)
{
    SearchText = Text.ToString().TrimStartAndEnd();
    RebuildFilteredIssues();
}

void SUnrealAssetAuditPanel::RebuildFilteredIssues()
{
    FilteredIssues.Reset();
    for (const FIssuePtr& Item : AllIssues)
    {
        if (SearchText.IsEmpty()
            || Item->AssetPath.Contains(SearchText, ESearchCase::IgnoreCase)
            || Item->RuleId.Contains(SearchText, ESearchCase::IgnoreCase)
            || Item->Message.Contains(SearchText, ESearchCase::IgnoreCase))
        {
            FilteredIssues.Add(Item);
        }
    }
    if (IssueList.IsValid()) IssueList->RequestListRefresh();
}

TSharedRef<ITableRow> SUnrealAssetAuditPanel::GenerateIssueRow(
    FIssuePtr Item, const TSharedRef<STableViewBase>& OwnerTable)
{
    return SNew(SAuditIssueRow, OwnerTable).Item(Item);
}

FReply SUnrealAssetAuditPanel::OpenReportFolder()
{
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(ReportPath), true);
    FPlatformProcess::ExploreFolder(*FPaths::GetPath(ReportPath));
    return FReply::Handled();
}

FText SUnrealAssetAuditPanel::GetSelectionText() const
{
    return SelectedAssetPaths.IsEmpty()
        ? FText::FromString(TEXT("未读取到选择\n请在 Content Browser 选择资产"))
        : FText::Format(FText::FromString(TEXT("当前选择：{0} 个资产\n仅采集 Static Mesh；其他类型会记录为失败证据")), SelectedAssetPaths.Num());
}

FText SUnrealAssetAuditPanel::GetStatusText() const { return FText::FromString(StatusMessage); }
FText SUnrealAssetAuditPanel::GetAssetCountText() const { return FText::AsNumber(AssetCount); }
FText SUnrealAssetAuditPanel::GetPassCountText() const { return FText::AsNumber(PassingAssetCount); }
FText SUnrealAssetAuditPanel::GetIssueCountText() const { return FText::AsNumber(IssueCount); }
FText SUnrealAssetAuditPanel::GetFailureCountText() const { return FText::AsNumber(FailureCount); }
bool SUnrealAssetAuditPanel::CanRunAudit() const
{
    return !bAuditRunning && !SelectedAssetPaths.IsEmpty() && SelectedProfile.IsValid()
        && !SelectedProfile->Path.IsEmpty();
}

void SUnrealAssetAuditPanel::HandleProfileChanged(FProfilePtr Item, ESelectInfo::Type SelectInfo)
{
    if (Item.IsValid())
    {
        SelectedProfile = Item;
        StatusMessage = FString::Printf(TEXT("已切换检查规则：%s"), *Item->Label);
    }
}

TSharedRef<SWidget> SUnrealAssetAuditPanel::GenerateProfileOption(FProfilePtr Item) const
{
    return SNew(SVerticalBox)
        + SVerticalBox::Slot().AutoHeight().Padding(8, 5, 8, 1)
        [SNew(STextBlock).Text(FText::FromString(Item->Label))]
        + SVerticalBox::Slot().AutoHeight().Padding(8, 0, 8, 5)
        [SNew(STextBlock).Text(FText::FromString(Item->Summary)).ColorAndOpacity(FSlateColor::UseSubduedForeground())];
}

FText SUnrealAssetAuditPanel::GetSelectedProfileLabel() const
{
    return SelectedProfile.IsValid() ? FText::FromString(SelectedProfile->Label) : FText::FromString(TEXT("请选择检查规则"));
}

FText SUnrealAssetAuditPanel::GetSelectedProfileSummary() const
{
    return SelectedProfile.IsValid() ? FText::FromString(SelectedProfile->Summary) : FText::GetEmpty();
}
