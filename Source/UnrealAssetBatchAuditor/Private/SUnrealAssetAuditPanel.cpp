#include "SUnrealAssetAuditPanel.h"

#include "AssetRegistry/AssetData.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "ContentBrowserModule.h"
#include "ContentBrowserDataSubsystem.h"
#include "IContentBrowserDataModule.h"
#include "IContentBrowserSingleton.h"
#include "DesktopPlatformModule.h"
#include "Framework/Application/SlateApplication.h"
#include "HAL/PlatformProcess.h"
#include "Interfaces/IPluginManager.h"
#include "IPythonScriptPlugin.h"
#include "JsonObjectConverter.h"
#include "Engine/StaticMesh.h"
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
#include "Widgets/Notifications/SProgressBar.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/SOverlay.h"
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
const FLinearColor GraphiteAccent(0.48f, 0.54f, 0.58f, 1.0f);

bool RuleBelongsToRiskCategory(const FString& RuleId, const FString& Category)
{
    if (Category.IsEmpty()) return true;
    if (Category == TEXT("geometry"))
        return RuleId.Contains(TEXT("triangle_budget")) || RuleId.Contains(TEXT("vertex_budget"));
    if (Category == TEXT("materials"))
        return RuleId.Contains(TEXT("material_slots")) || RuleId.Contains(TEXT("material"))
            || RuleId.Contains(TEXT("texture_"));
    if (Category == TEXT("readiness"))
        return RuleId.Contains(TEXT("lod_count")) || RuleId.Contains(TEXT("nanite_state"))
            || RuleId.Contains(TEXT("simple_collision")) || RuleId.Contains(TEXT("lightmap"));
    if (Category == TEXT("structure"))
        return RuleId.Contains(TEXT("object_name")) || RuleId.Contains(TEXT("package_path"));
    if (Category == TEXT("collection"))
        return RuleId == TEXT("collection.failure");
    return true;
}

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
    if (RuleId.Contains(TEXT("missing_materials"))) return FText::FromString(TEXT("缺失材质"));
    if (RuleId.Contains(TEXT("unique_materials"))) return FText::FromString(TEXT("唯一材质"));
    if (RuleId.Contains(TEXT("texture_dependencies"))) return FText::FromString(TEXT("纹理依赖"));
    if (RuleId.Contains(TEXT("texture_dimension"))) return FText::FromString(TEXT("纹理尺寸"));
    if (RuleId.Contains(TEXT("lod_count"))) return FText::FromString(TEXT("LOD 数量"));
    if (RuleId.Contains(TEXT("nanite_state"))) return FText::FromString(TEXT("Nanite 状态"));
    if (RuleId.Contains(TEXT("simple_collision"))) return FText::FromString(TEXT("简单碰撞"));
    if (RuleId.Contains(TEXT("lightmap_uv"))) return FText::FromString(TEXT("Lightmap UV"));
    if (RuleId.Contains(TEXT("lightmap_resolution"))) return FText::FromString(TEXT("Lightmap 分辨率"));
    if (RuleId.Contains(TEXT("object_name"))) return FText::FromString(TEXT("资产命名"));
    if (RuleId.Contains(TEXT("package_path"))) return FText::FromString(TEXT("目录规范"));
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
    if (RuleId.Contains(TEXT("missing_materials")))
        return FString::Printf(TEXT("缺失材质槽为 %s，超过 Profile 上限 %s。"), *Observed, *Expected);
    if (RuleId.Contains(TEXT("unique_materials")))
        return FString::Printf(TEXT("唯一材质为 %s 个，超过 Profile 上限 %s。"), *Observed, *Expected);
    if (RuleId.Contains(TEXT("texture_dependencies")))
        return FString::Printf(TEXT("纹理依赖为 %s 个，超过 Profile 上限 %s。"), *Observed, *Expected);
    if (RuleId.Contains(TEXT("texture_dimension")))
        return FString::Printf(TEXT("最大纹理边长为 %s，超过 Profile 上限 %s。"), *Observed, *Expected);
    if (RuleId.Contains(TEXT("lod_count")))
        return FString::Printf(TEXT("LOD 数量为 %s，低于 Profile 下限 %s。"), *Observed, *Expected);
    if (RuleId.Contains(TEXT("nanite_state")))
        return FString::Printf(TEXT("Nanite 状态为 %s，Profile 期望为 %s。"), *Observed, *Expected);
    if (RuleId.Contains(TEXT("simple_collision")))
        return FString::Printf(TEXT("碰撞实测为 %s；Profile 要求 %s。"), *Observed, *Expected);
    if (RuleId.Contains(TEXT("lightmap_uv")))
        return FString::Printf(TEXT("Lightmap UV 实测为 %s；Profile 要求 %s。"), *Observed, *Expected);
    if (RuleId.Contains(TEXT("lightmap_resolution")))
        return FString::Printf(TEXT("Lightmap 分辨率为 %s，低于 Profile 下限 %s。"), *Observed, *Expected);
    if (RuleId.Contains(TEXT("object_name")))
        return FString::Printf(TEXT("资产名 %s 不符合 Profile 命名规则：%s。"), *Observed, *Expected);
    if (RuleId.Contains(TEXT("package_path")))
        return FString::Printf(TEXT("资产目录 %s 不符合 Profile 目录规则：%s。"), *Observed, *Expected);
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

FLinearColor AssetStatusColor(const FString& Status)
{
    if (Status == TEXT("failed")) return RedAccent;
    if (Status == TEXT("issue")) return AmberAccent;
    return GreenAccent;
}

FText AssetStatusLabel(const FString& Status)
{
    if (Status == TEXT("failed")) return FText::FromString(TEXT("失败"));
    if (Status == TEXT("issue")) return FText::FromString(TEXT("需处理"));
    return FText::FromString(TEXT("通过"));
}

FText ComparisonChangeLabel(const FString& ChangeType)
{
    if (ChangeType == TEXT("new")) return FText::FromString(TEXT("新增"));
    if (ChangeType == TEXT("persistent")) return FText::FromString(TEXT("持续"));
    if (ChangeType == TEXT("resolved")) return FText::FromString(TEXT("已解决"));
    if (ChangeType == TEXT("new_failure")) return FText::FromString(TEXT("新增失败"));
    if (ChangeType == TEXT("persistent_failure")) return FText::FromString(TEXT("持续失败"));
    return FText::FromString(TEXT("失败已恢复"));
}

FLinearColor ComparisonChangeColor(const FString& ChangeType)
{
    if (ChangeType == TEXT("new") || ChangeType == TEXT("new_failure")) return RedAccent;
    if (ChangeType == TEXT("persistent") || ChangeType == TEXT("persistent_failure")) return AmberAccent;
    return GreenAccent;
}

FString LocalizedComparisonMessage(const FString& ChangeType)
{
    if (ChangeType == TEXT("new"))
        return TEXT("当前审计首次触发该规则，请检查资产改动或确认 Profile 阈值。");
    if (ChangeType == TEXT("persistent"))
        return TEXT("基线与当前审计均触发该规则，问题仍未关闭。");
    if (ChangeType == TEXT("resolved"))
        return TEXT("当前审计不再触发该规则，修复结果已记录。");
    if (ChangeType == TEXT("new_failure"))
        return TEXT("当前审计新增采集失败；该资产未参与规则评估。");
    if (ChangeType == TEXT("persistent_failure"))
        return TEXT("该资产在基线与当前审计中均采集失败，需要修复采集边界。");
    return TEXT("当前审计已恢复采集，该资产重新进入规则评估。");
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

class SAuditAssetRow final : public SMultiColumnTableRow<SUnrealAssetAuditPanel::FAssetPtr>
{
public:
    SLATE_BEGIN_ARGS(SAuditAssetRow) {}
        SLATE_ARGUMENT(SUnrealAssetAuditPanel::FAssetPtr, Item)
    SLATE_END_ARGS()

    void Construct(const FArguments& InArgs, const TSharedRef<STableViewBase>& OwnerTable)
    {
        Item = InArgs._Item;
        SMultiColumnTableRow::Construct(
            FSuperRowType::FArguments().Padding(FMargin(4.0f, 3.0f)), OwnerTable);
    }

    virtual TSharedRef<SWidget> GenerateWidgetForColumn(const FName& ColumnName) override
    {
        if (ColumnName == TEXT("Status"))
        {
            return SNew(STextBlock)
                .Text(AssetStatusLabel(Item->Status))
                .ColorAndOpacity(AssetStatusColor(Item->Status))
                .Font(FAppStyle::GetFontStyle(TEXT("SmallFontBold")));
        }
        if (ColumnName == TEXT("Asset"))
        {
            return SNew(STextBlock)
                .Text(FText::FromString(Item->AssetName))
                .ToolTipText(FText::FromString(Item->AssetPath));
        }
        if (ColumnName == TEXT("Triangles")) return SNew(STextBlock).Text(FText::FromString(Item->TriangleCount));
        if (ColumnName == TEXT("Vertices")) return SNew(STextBlock).Text(FText::FromString(Item->VertexCount));
        if (ColumnName == TEXT("Materials"))
            return SNew(STextBlock)
                .Text(FText::FromString(Item->MaterialDependencyState))
                .ToolTipText(FText::FromString(TEXT("材质槽 / 唯一有效材质；缺失槽会进入问题明细")));
        if (ColumnName == TEXT("Textures"))
            return SNew(STextBlock)
                .Text(FText::FromString(Item->TextureDependencyState))
                .ToolTipText(FText::FromString(TEXT("材质接口报告的唯一纹理数 / 最大纹理边长")));
        if (ColumnName == TEXT("LODs")) return SNew(STextBlock).Text(FText::FromString(Item->LodCount));
        if (ColumnName == TEXT("Nanite")) return SNew(STextBlock).Text(FText::FromString(Item->NaniteState));
        if (ColumnName == TEXT("Collision")) return SNew(STextBlock).Text(FText::FromString(Item->CollisionState));
        if (ColumnName == TEXT("LightmapUV")) return SNew(STextBlock).Text(FText::FromString(Item->LightmapUvState));
        if (ColumnName == TEXT("LightmapResolution")) return SNew(STextBlock).Text(FText::FromString(Item->LightmapResolution));
        return SNew(STextBlock)
            .Text(Item->IssueCount > 0 ? FText::AsNumber(Item->IssueCount) : FText::FromString(TEXT("—")))
            .ColorAndOpacity(Item->IssueCount > 0 ? FSlateColor(AmberAccent) : FSlateColor::UseSubduedForeground());
    }

private:
    SUnrealAssetAuditPanel::FAssetPtr Item;
};

class SAuditComparisonRow final
    : public SMultiColumnTableRow<SUnrealAssetAuditPanel::FComparisonPtr>
{
public:
    SLATE_BEGIN_ARGS(SAuditComparisonRow) {}
        SLATE_ARGUMENT(SUnrealAssetAuditPanel::FComparisonPtr, Item)
    SLATE_END_ARGS()

    void Construct(const FArguments& InArgs, const TSharedRef<STableViewBase>& OwnerTable)
    {
        Item = InArgs._Item;
        SMultiColumnTableRow::Construct(
            FSuperRowType::FArguments().Padding(FMargin(4.0f, 3.0f)), OwnerTable);
    }

    virtual TSharedRef<SWidget> GenerateWidgetForColumn(const FName& ColumnName) override
    {
        if (ColumnName == TEXT("Change"))
        {
            return SNew(STextBlock)
                .Text(ComparisonChangeLabel(Item->ChangeType))
                .ColorAndOpacity(ComparisonChangeColor(Item->ChangeType))
                .Font(FAppStyle::GetFontStyle(TEXT("SmallFontBold")));
        }
        if (ColumnName == TEXT("Asset"))
        {
            FString Name;
            Item->AssetPath.Split(TEXT("."), nullptr, &Name, ESearchCase::IgnoreCase, ESearchDir::FromEnd);
            return SNew(STextBlock)
                .Text(FText::FromString(Name.IsEmpty() ? Item->AssetPath : Name))
                .ToolTipText(FText::FromString(Item->AssetPath));
        }
        if (ColumnName == TEXT("Rule"))
        {
            return SNew(STextBlock)
                .Text(RuleLabel(Item->RuleId))
                .ToolTipText(FText::FromString(Item->RuleId));
        }
        if (ColumnName == TEXT("Severity"))
        {
            return SNew(STextBlock)
                .Text(SeverityLabel(Item->Severity))
                .ColorAndOpacity(SeverityColor(Item->Severity));
        }
        return SNew(STextBlock)
            .Text(FText::FromString(Item->Message))
            .ToolTipText(FText::FromString(Item->Message));
    }

private:
    SUnrealAssetAuditPanel::FComparisonPtr Item;
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
            TEXT("三角形 ≤ 2,000 · 唯一材质 ≤ 2 · 纹理 ≤ 8 · 最大 2K · 无缺失材质 · 碰撞/Lightmap/命名"),
            FPaths::Combine(ProfilesRoot, TEXT("desktop-balanced.v3.json"))}),
        MakeShared<FAuditProfileOption>(FAuditProfileOption{
            TEXT("移动端严格"),
            TEXT("三角形 ≤ 500 · 唯一材质 ≤ 1 · 纹理 ≤ 4 · 最大 1K · LOD ≥ 2 · 严格交付规则"),
            FPaths::Combine(ProfilesRoot, TEXT("mobile-strict.v3.json"))}),
        MakeShared<FAuditProfileOption>(FAuditProfileOption{
            TEXT("宽松复核"),
            TEXT("三角形 ≤ 10,000 · 唯一材质 ≤ 4 · 纹理 ≤ 16 · 最大 4K · 宽松复核"),
            FPaths::Combine(ProfilesRoot, TEXT("review-lenient.v3.json"))})
    };
    SelectedProfile = ProfileOptions[0];
    ReportPath = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("UnrealAssetBatchAuditor/Reports/latest-report.json"));
    SessionRoot = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("UnrealAssetBatchAuditor/Sessions"));
    ComparisonPath = FPaths::Combine(SessionRoot, TEXT("latest-comparison.v1.json"));
    TaskStatePath = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("UnrealAssetBatchAuditor/Tasks/current-task-state.json"));
    CancelRequestPath = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("UnrealAssetBatchAuditor/Tasks/cancel-request.json"));
    HandoffRoot = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("UnrealAssetBatchAuditor/Handoffs"));
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
                            .Text(FText::FromString(TEXT("资产交付验收台")))
                            .Font(FAppStyle::GetFontStyle(TEXT("HeadingMedium")))
                        ]
                        + SVerticalBox::Slot().AutoHeight().Padding(0, 3, 0, 0)
                        [
                            SNew(STextBlock)
                            .Text(FText::FromString(TEXT("交付批次 · 规则校准 · 只读证据")))
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
                            SNew(STextBlock).Text(FText::FromString(TEXT("验收校准"))).Font(FAppStyle::GetFontStyle(TEXT("HeadingSmall")))
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
                            SNew(STextBlock).Text(FText::FromString(TEXT("交付批次范围"))).ColorAndOpacity(FSlateColor::UseSubduedForeground())
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
                            SNew(SButton).Text(FText::FromString(TEXT("读取资产 / 文件夹选择"))).OnClicked(this, &SUnrealAssetAuditPanel::RefreshSelection)
                        ]
                        + SVerticalBox::Slot().AutoHeight().Padding(0, 18, 0, 4)
                        [
                            SNew(STextBlock).Text(FText::FromString(TEXT("单批资产数"))).ColorAndOpacity(FSlateColor::UseSubduedForeground())
                        ]
                        + SVerticalBox::Slot().AutoHeight()
                        [
                            SNew(SSpinBox<int32>).MinValue(1).MaxValue(1024).Value(BatchSize).OnValueChanged_Lambda([this](int32 Value) { BatchSize = Value; })
                        ]
                        + SVerticalBox::Slot().AutoHeight().Padding(0, 18, 0, 4)
                        [
                            SNew(STextBlock)
                            .Text(FText::FromString(TEXT("回归基线（同一 Profile）")))
                            .ColorAndOpacity(FSlateColor::UseSubduedForeground())
                        ]
                        + SVerticalBox::Slot().AutoHeight()
                        [
                            SAssignNew(SessionComboBox, SComboBox<FSessionPtr>)
                            .OptionsSource(&SessionOptions)
                            .OnGenerateWidget(this, &SUnrealAssetAuditPanel::GenerateSessionOption)
                            .OnSelectionChanged(this, &SUnrealAssetAuditPanel::HandleSessionChanged)
                            [
                                SNew(STextBlock).Text(this, &SUnrealAssetAuditPanel::GetSelectedSessionLabel)
                            ]
                        ]
                        + SVerticalBox::Slot().AutoHeight().Padding(0, 6, 0, 0)
                        [
                            SNew(SButton)
                            .Text(FText::FromString(TEXT("与所选基线比较")))
                            .IsEnabled(this, &SUnrealAssetAuditPanel::CanRunComparison)
                            .OnClicked(this, &SUnrealAssetAuditPanel::RunComparison)
                        ]
                        + SVerticalBox::Slot().FillHeight(1)
                        + SVerticalBox::Slot().AutoHeight().Padding(0, 16, 0, 0)
                        [
                            SNew(SOverlay)
                            + SOverlay::Slot()
                            [
                                SNew(SButton)
                                .Visibility(this, &SUnrealAssetAuditPanel::GetIdleActionVisibility)
                                .ButtonStyle(FAppStyle::Get(), TEXT("PrimaryButton"))
                                .HAlign(HAlign_Center)
                                .ContentPadding(FMargin(12, 8))
                                .Text(FText::FromString(TEXT("开始只读审计")))
                                .IsEnabled(this, &SUnrealAssetAuditPanel::CanRunAudit)
                                .OnClicked(this, &SUnrealAssetAuditPanel::RunAudit)
                            ]
                            + SOverlay::Slot()
                            [
                                SNew(SBorder)
                                .Visibility(this, &SUnrealAssetAuditPanel::GetRunningActionVisibility)
                                .BorderImage(FAppStyle::GetBrush(TEXT("Brushes.Header")))
                                .BorderBackgroundColor(FLinearColor(0.04f, 0.13f, 0.16f, 1.0f))
                                .Padding(FMargin(10, 8))
                                [
                                    SNew(SVerticalBox)
                                    + SVerticalBox::Slot().AutoHeight()
                                    [
                                        SNew(STextBlock)
                                        .Text(this, &SUnrealAssetAuditPanel::GetTaskPhaseText)
                                        .Font(FAppStyle::GetFontStyle(TEXT("SmallFontBold")))
                                        .ColorAndOpacity(CyanAccent)
                                    ]
                                    + SVerticalBox::Slot().AutoHeight().Padding(0, 6, 0, 0)
                                    [
                                        SNew(SProgressBar)
                                        .Percent(this, &SUnrealAssetAuditPanel::GetTaskProgressFraction)
                                        .FillColorAndOpacity(CyanAccent)
                                    ]
                                    + SVerticalBox::Slot().AutoHeight().Padding(0, 6, 0, 0)
                                    [
                                        SNew(SHorizontalBox)
                                        + SHorizontalBox::Slot().FillWidth(1).VAlign(VAlign_Center)
                                        [
                                            SNew(STextBlock)
                                            .Text(this, &SUnrealAssetAuditPanel::GetTaskProgressText)
                                            .Font(FAppStyle::GetFontStyle(TEXT("SmallFont")))
                                            .ColorAndOpacity(FSlateColor::UseSubduedForeground())
                                        ]
                                        + SHorizontalBox::Slot().AutoWidth()
                                        [
                                            SNew(SButton)
                                            .Text(FText::FromString(TEXT("批次间取消")))
                                            .IsEnabled(this, &SUnrealAssetAuditPanel::CanCancelAudit)
                                            .OnClicked(this, &SUnrealAssetAuditPanel::CancelAudit)
                                        ]
                                    ]
                                ]
                            ]
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
                        SNew(SBorder)
                        .BorderImage(FAppStyle::GetBrush(TEXT("Brushes.Header")))
                        .BorderBackgroundColor(FLinearColor(0.065f, 0.075f, 0.078f, 1.0f))
                        .Padding(FMargin(10, 7))
                        [
                            SNew(SHorizontalBox)
                            + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(2, 0, 12, 0)
                            [
                                SNew(STextBlock)
                                .Text(FText::FromString(TEXT("交付风险谱")))
                                .Font(FAppStyle::GetFontStyle(TEXT("SmallFontBold")))
                                .ColorAndOpacity(AmberAccent)
                            ]
                            + SHorizontalBox::Slot().FillWidth(1)
                            [BuildRiskCell(FText::FromString(TEXT("几何预算")), TEXT("geometry"), RedAccent)]
                            + SHorizontalBox::Slot().FillWidth(1).Padding(4, 0)
                            [BuildRiskCell(FText::FromString(TEXT("材质负载")), TEXT("materials"), AmberAccent)]
                            + SHorizontalBox::Slot().FillWidth(1)
                            [BuildRiskCell(FText::FromString(TEXT("构建就绪")), TEXT("readiness"), CyanAccent)]
                            + SHorizontalBox::Slot().FillWidth(1).Padding(4, 0)
                            [BuildRiskCell(FText::FromString(TEXT("命名路径")), TEXT("structure"), GreenAccent)]
                            + SHorizontalBox::Slot().FillWidth(1)
                            [BuildRiskCell(FText::FromString(TEXT("采集异常")), TEXT("collection"), GraphiteAccent)]
                        ]
                    ]
                    + SVerticalBox::Slot().AutoHeight().Padding(14, 0, 14, 8)
                    [
                        SNew(SHorizontalBox)
                        + SHorizontalBox::Slot().AutoWidth()
                        [
                            SNew(SButton)
                            .ButtonStyle(FAppStyle::Get(), TEXT("SimpleButton"))
                            .Text(FText::FromString(TEXT("资产总览")))
                            .ForegroundColor_Lambda([this] { return ResultViewMode == 0 ? FSlateColor(CyanAccent) : FSlateColor::UseForeground(); })
                            .OnClicked(this, &SUnrealAssetAuditPanel::ShowAssetOverview)
                        ]
                        + SHorizontalBox::Slot().AutoWidth().Padding(6, 0, 0, 0)
                        [
                            SNew(SButton)
                            .ButtonStyle(FAppStyle::Get(), TEXT("SimpleButton"))
                            .Text(FText::FromString(TEXT("问题明细")))
                            .ForegroundColor_Lambda([this] { return ResultViewMode == 1 ? FSlateColor(CyanAccent) : FSlateColor::UseForeground(); })
                            .OnClicked(this, &SUnrealAssetAuditPanel::ShowIssueDetails)
                        ]
                        + SHorizontalBox::Slot().AutoWidth().Padding(6, 0, 0, 0)
                        [
                            SNew(SButton)
                            .ButtonStyle(FAppStyle::Get(), TEXT("SimpleButton"))
                            .Text(FText::FromString(TEXT("回归对比")))
                            .ForegroundColor_Lambda([this] { return ResultViewMode == 2 ? FSlateColor(CyanAccent) : FSlateColor::UseForeground(); })
                            .OnClicked(this, &SUnrealAssetAuditPanel::ShowComparison)
                        ]
                        + SHorizontalBox::Slot().FillWidth(1).VAlign(VAlign_Center).Padding(12, 0, 0, 0)
                        [
                            SNew(STextBlock)
                            .Text(this, &SUnrealAssetAuditPanel::GetResultViewHint)
                            .ColorAndOpacity(FSlateColor::UseSubduedForeground())
                        ]
                    ]
                    + SVerticalBox::Slot().AutoHeight().Padding(14, 0, 14, 8)
                    [
                        SAssignNew(SearchInput, SSearchBox)
                        .HintText(FText::FromString(TEXT("搜索资产、状态、规则或证据说明")))
                        .OnTextChanged(this, &SUnrealAssetAuditPanel::HandleSearchChanged)
                    ]
                    + SVerticalBox::Slot().FillHeight(1).Padding(14, 0, 14, 10)
                    [
                        SNew(SOverlay)
                        + SOverlay::Slot()
                        [
                            SAssignNew(AssetList, SListView<FAssetPtr>)
                            .Visibility(this, &SUnrealAssetAuditPanel::GetAssetViewVisibility)
                            .ListItemsSource(&FilteredAssets)
                            .SelectionMode(ESelectionMode::Single)
                            .OnGenerateRow(this, &SUnrealAssetAuditPanel::GenerateAssetRow)
                            .HeaderRow
                            (
                                SNew(SHeaderRow)
                                + SHeaderRow::Column(TEXT("Status")).DefaultLabel(FText::FromString(TEXT("状态"))).FixedWidth(72)
                                + SHeaderRow::Column(TEXT("Asset")).DefaultLabel(FText::FromString(TEXT("资产"))).FillWidth(0.31f)
                                + SHeaderRow::Column(TEXT("Triangles")).DefaultLabel(FText::FromString(TEXT("三角形"))).FixedWidth(86)
                                + SHeaderRow::Column(TEXT("Vertices")).DefaultLabel(FText::FromString(TEXT("顶点"))).FixedWidth(78)
                                + SHeaderRow::Column(TEXT("Materials")).DefaultLabel(FText::FromString(TEXT("槽/材"))).FixedWidth(62)
                                + SHeaderRow::Column(TEXT("Textures")).DefaultLabel(FText::FromString(TEXT("纹理/最大"))).FixedWidth(82)
                                + SHeaderRow::Column(TEXT("LODs")).DefaultLabel(FText::FromString(TEXT("LOD"))).FixedWidth(52)
                                + SHeaderRow::Column(TEXT("Nanite")).DefaultLabel(FText::FromString(TEXT("Nanite"))).FixedWidth(66)
                                + SHeaderRow::Column(TEXT("Collision")).DefaultLabel(FText::FromString(TEXT("碰撞"))).FixedWidth(58)
                                + SHeaderRow::Column(TEXT("LightmapUV")).DefaultLabel(FText::FromString(TEXT("LM UV"))).FixedWidth(62)
                                + SHeaderRow::Column(TEXT("LightmapResolution")).DefaultLabel(FText::FromString(TEXT("LM 分辨率"))).FixedWidth(76)
                                + SHeaderRow::Column(TEXT("Issues")).DefaultLabel(FText::FromString(TEXT("问题"))).FixedWidth(58)
                            )
                        ]
                        + SOverlay::Slot()
                        [
                            SAssignNew(IssueList, SListView<FIssuePtr>)
                            .Visibility(this, &SUnrealAssetAuditPanel::GetIssueViewVisibility)
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
                        + SOverlay::Slot()
                        [
                            SNew(SVerticalBox)
                            .Visibility(this, &SUnrealAssetAuditPanel::GetComparisonViewVisibility)
                            + SVerticalBox::Slot().AutoHeight().Padding(0, 0, 0, 8)
                            [
                                SNew(SBorder)
                                .BorderImage(FAppStyle::GetBrush(TEXT("Brushes.Header")))
                                .BorderBackgroundColor(FLinearColor(0.05f, 0.10f, 0.12f, 1.0f))
                                .Padding(FMargin(12, 9))
                                [
                                    SNew(SVerticalBox)
                                    + SVerticalBox::Slot().AutoHeight()
                                    [
                                        SNew(STextBlock)
                                        .Text(FText::FromString(TEXT("同一 Profile 的质量变化")))
                                        .Font(FAppStyle::GetFontStyle(TEXT("SmallFontBold")))
                                        .ColorAndOpacity(CyanAccent)
                                    ]
                                    + SVerticalBox::Slot().AutoHeight().Padding(0, 3, 0, 0)
                                    [
                                        SNew(STextBlock)
                                        .Text(this, &SUnrealAssetAuditPanel::GetComparisonBaselineText)
                                        .ColorAndOpacity(FSlateColor::UseSubduedForeground())
                                    ]
                                ]
                            ]
                            + SVerticalBox::Slot().AutoHeight().Padding(0, 0, 0, 8)
                            [
                                SNew(SHorizontalBox)
                                + SHorizontalBox::Slot().FillWidth(1)
                                [BuildSummaryCell(FText::FromString(TEXT("新增问题")), TAttribute<FText>::CreateSP(this, &SUnrealAssetAuditPanel::GetNewIssueCountText), RedAccent)]
                                + SHorizontalBox::Slot().FillWidth(1).Padding(6, 0)
                                [BuildSummaryCell(FText::FromString(TEXT("持续问题")), TAttribute<FText>::CreateSP(this, &SUnrealAssetAuditPanel::GetPersistentIssueCountText), AmberAccent)]
                                + SHorizontalBox::Slot().FillWidth(1).Padding(6, 0)
                                [BuildSummaryCell(FText::FromString(TEXT("已解决")), TAttribute<FText>::CreateSP(this, &SUnrealAssetAuditPanel::GetResolvedIssueCountText), GreenAccent)]
                                + SHorizontalBox::Slot().FillWidth(1)
                                [BuildSummaryCell(FText::FromString(TEXT("失败变化")), TAttribute<FText>::CreateSP(this, &SUnrealAssetAuditPanel::GetFailureChangeCountText), CyanAccent)]
                            ]
                            + SVerticalBox::Slot().FillHeight(1)
                            [
                                SAssignNew(ComparisonList, SListView<FComparisonPtr>)
                                .ListItemsSource(&FilteredComparisons)
                                .SelectionMode(ESelectionMode::Single)
                                .OnGenerateRow(this, &SUnrealAssetAuditPanel::GenerateComparisonRow)
                                .HeaderRow
                                (
                                    SNew(SHeaderRow)
                                    + SHeaderRow::Column(TEXT("Change")).DefaultLabel(FText::FromString(TEXT("变化"))).FixedWidth(82)
                                    + SHeaderRow::Column(TEXT("Asset")).DefaultLabel(FText::FromString(TEXT("资产"))).FillWidth(0.25f)
                                    + SHeaderRow::Column(TEXT("Rule")).DefaultLabel(FText::FromString(TEXT("检查项"))).FillWidth(0.18f)
                                    + SHeaderRow::Column(TEXT("Severity")).DefaultLabel(FText::FromString(TEXT("级别"))).FixedWidth(68)
                                    + SHeaderRow::Column(TEXT("Message")).DefaultLabel(FText::FromString(TEXT("变化说明"))).FillWidth(0.39f)
                                )
                            ]
                        ]
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
                                SNew(SButton)
                                .Text(FText::FromString(TEXT("打开最新报告")))
                                .IsEnabled_Lambda([this] { return FPaths::FileExists(ReportPath); })
                                .OnClicked(this, &SUnrealAssetAuditPanel::OpenReportFile)
                            ]
                            + SHorizontalBox::Slot().AutoWidth().Padding(6, 0, 0, 0)
                            [
                                SNew(SButton).Text(FText::FromString(TEXT("打开报告目录"))).OnClicked(this, &SUnrealAssetAuditPanel::OpenReportFolder)
                            ]
                            + SHorizontalBox::Slot().AutoWidth().Padding(6, 0, 0, 0)
                            [
                                SNew(SButton).Text(FText::FromString(TEXT("打开会话目录"))).OnClicked(this, &SUnrealAssetAuditPanel::OpenSessionFolder)
                            ]
                            + SHorizontalBox::Slot().AutoWidth().Padding(6, 0, 0, 0)
                            [
                                SNew(SButton)
                                .Text(FText::FromString(TEXT("导出团队包")))
                                .IsEnabled_Lambda([this] { return !bAuditRunning && FPaths::FileExists(ReportPath); })
                                .OnClicked(this, &SUnrealAssetAuditPanel::ExportHandoff)
                            ]
                            + SHorizontalBox::Slot().AutoWidth().Padding(6, 0, 0, 0)
                            [
                                SNew(SButton)
                                .Text(FText::FromString(TEXT("打开交接目录")))
                                .IsEnabled_Lambda([this] { return !LastHandoffPath.IsEmpty() && FPaths::DirectoryExists(LastHandoffPath); })
                                .OnClicked(this, &SUnrealAssetAuditPanel::OpenHandoffFolder)
                            ]
                        ]
                    ]
                ]
            ]
        ]
    ];

    RefreshSelection();
    if (FPaths::FileExists(ReportPath))
    {
        FString LoadError;
        LoadReport(ReportPath, LoadError);
        LoadSessionIndex(LoadError);
        if (FPaths::FileExists(ComparisonPath)) LoadComparison(ComparisonPath, LoadError);
    }
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

TSharedRef<SWidget> SUnrealAssetAuditPanel::BuildRiskCell(
    const FText& Label, const FString& Category, const FLinearColor& Accent)
{
    return SNew(SButton)
        .ButtonStyle(FAppStyle::Get(), TEXT("SimpleButton"))
        .ToolTipText(FText::FromString(TEXT("点击筛选该类问题；再次点击取消筛选")))
        .OnClicked_Lambda([this, Category] { return ToggleRiskCategory(Category); })
        [
            SNew(SHorizontalBox)
            + SHorizontalBox::Slot().FillWidth(1).VAlign(VAlign_Center)
            [
                SNew(STextBlock)
                .Text(Label)
                .Font(FAppStyle::GetFontStyle(TEXT("SmallFont")))
                .ColorAndOpacity_Lambda([this, Category, Accent]
                {
                    return ActiveRiskCategory.IsEmpty() || ActiveRiskCategory == Category
                        ? FSlateColor(Accent)
                        : FSlateColor::UseSubduedForeground();
                })
            ]
            + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(5, 0, 0, 0)
            [
                SNew(STextBlock)
                .Text_Lambda([this, Category] { return GetRiskCategoryCountText(Category); })
                .Font(FAppStyle::GetFontStyle(TEXT("SmallFontBold")))
                .ColorAndOpacity(Accent)
            ]
        ];
}

FReply SUnrealAssetAuditPanel::ToggleRiskCategory(FString Category)
{
    ActiveRiskCategory = ActiveRiskCategory == Category ? FString() : MoveTemp(Category);
    ResultViewMode = 1;
    RebuildFilteredIssues();
    return FReply::Handled();
}

void SUnrealAssetAuditPanel::RebuildSelectionFromInternalFolders(
    const TArray<FString>& InternalFolders, TSet<FString>& InOutAssetPaths)
{
    SelectedFolderPaths.Reset();
    TSet<FString> FolderMeshPaths;
    FAssetRegistryModule& AssetRegistryModule = FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry"));
    for (const FString& InternalFolder : InternalFolders)
    {
        SelectedFolderPaths.Add(InternalFolder);
        TArray<FAssetData> FolderAssets;
        AssetRegistryModule.Get().GetAssetsByPath(FName(*InternalFolder), FolderAssets, true, true);
        for (const FAssetData& Asset : FolderAssets)
        {
            if (Asset.AssetClassPath == UStaticMesh::StaticClass()->GetClassPathName())
            {
                FolderMeshPaths.Add(Asset.GetSoftObjectPath().ToString());
            }
        }
    }
    DiscoveredFolderAssetCount = FolderMeshPaths.Num();
    InOutAssetPaths.Append(FolderMeshPaths);
    SelectedFolderPaths.Sort();
}

FReply SUnrealAssetAuditPanel::RefreshSelection()
{
    SelectedAssetPaths.Reset();
    SelectedFolderPaths.Reset();
    DiscoveredFolderAssetCount = 0;
    FContentBrowserModule& ContentBrowser = FModuleManager::LoadModuleChecked<FContentBrowserModule>(TEXT("ContentBrowser"));
    TArray<FAssetData> SelectedAssets;
    ContentBrowser.Get().GetSelectedAssets(SelectedAssets);
    TSet<FString> UniqueAssetPaths;
    for (const FAssetData& Asset : SelectedAssets)
    {
        UniqueAssetPaths.Add(Asset.GetSoftObjectPath().ToString());
    }

    TArray<FString> VirtualFolders;
    ContentBrowser.Get().GetSelectedFolders(VirtualFolders);
    UContentBrowserDataSubsystem* BrowserData = IContentBrowserDataModule::Get().GetSubsystem();
    TArray<FString> InternalFolders;
    for (const FString& VirtualFolder : VirtualFolders)
    {
        FName InternalFolder;
        if (!BrowserData
            || BrowserData->TryConvertVirtualPath(FName(*VirtualFolder), InternalFolder) != EContentBrowserPathType::Internal)
        {
            continue;
        }
        InternalFolders.Add(InternalFolder.ToString());
    }
    RebuildSelectionFromInternalFolders(InternalFolders, UniqueAssetPaths);
    SelectedAssetPaths = UniqueAssetPaths.Array();
    SelectedAssetPaths.Sort();
    SelectedFolderPaths.Sort();
    StatusMessage = SelectedAssetPaths.IsEmpty()
        ? TEXT("尚未选择资产或文件夹")
        : FString::Printf(
            TEXT("交付批次已就绪 · %d 个对象 · %d 个文件夹"),
            SelectedAssetPaths.Num(), SelectedFolderPaths.Num());
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
    bTaskCanCancel = true;
    TaskState = TEXT("pending");
    TaskRequestedCount = SelectedAssetPaths.Num();
    TaskProcessedCount = 0;
    TaskCompletedBatchCount = 0;
    TaskTotalBatchCount = FMath::DivideAndRoundUp(TaskRequestedCount, BatchSize);
    TaskProgressFraction = 0.0f;
    ActiveTaskId = FGuid::NewGuid().ToString(EGuidFormats::DigitsWithHyphensLower);
    StatusMessage = TEXT("任务已创建，等待第一个只读采集批次");
    IFileManager::Get().Delete(*TaskStatePath, false, true, true);
    IFileManager::Get().Delete(*CancelRequestPath, false, true, true);

    TSharedRef<FJsonObject> Request = MakeShared<FJsonObject>();
    Request->SetStringField(TEXT("profile_path"), ProfilePath);
    Request->SetStringField(TEXT("output_path"), ReportPath);
    Request->SetStringField(TEXT("session_root"), SessionRoot);
    Request->SetStringField(TEXT("handoff_root"), HandoffRoot);
    Request->SetStringField(TEXT("state_path"), TaskStatePath);
    Request->SetStringField(TEXT("cancel_path"), CancelRequestPath);
    Request->SetStringField(TEXT("task_id"), ActiveTaskId);
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
        TEXT("from unreal_asset_batch_auditor import start_panel_task; start_panel_task(r'%s')"),
        *PythonPath);
    const bool bSucceeded = Python->ExecPythonCommand(*Command);
    if (!bSucceeded)
    {
        bAuditRunning = false;
        bTaskCanCancel = false;
        TaskState = TEXT("failed");
        StatusMessage = TEXT("审计执行失败；详细堆栈已写入 Output Log");
        return FReply::Handled();
    }
    RegisterActiveTimer(
        0.10f,
        FWidgetActiveTimerDelegate::CreateSP(this, &SUnrealAssetAuditPanel::PollAuditTask));
    return FReply::Handled();
}

FReply SUnrealAssetAuditPanel::CancelAudit()
{
    if (!CanCancelAudit()) return FReply::Handled();
    IPythonScriptPlugin* Python = IPythonScriptPlugin::Get();
    if (!Python)
    {
        StatusMessage = TEXT("无法提交取消请求：Python Script Plugin 未就绪");
        return FReply::Handled();
    }
    FString PythonPath = CancelRequestPath.Replace(TEXT("\\"), TEXT("/"));
    PythonPath.ReplaceInline(TEXT("'"), TEXT("\\'"));
    const FString Command = FString::Printf(
        TEXT("from unreal_asset_batch_auditor import request_panel_cancel; request_panel_cancel(r'%s')"),
        *PythonPath);
    if (!Python->ExecPythonCommand(*Command))
    {
        StatusMessage = TEXT("无法提交取消请求；当前批次会继续完成");
        return FReply::Handled();
    }
    TaskState = TEXT("cancelling");
    bTaskCanCancel = false;
    StatusMessage = TEXT("已请求取消；当前批次完成后保留部分报告");
    return FReply::Handled();
}

bool SUnrealAssetAuditPanel::LoadTaskState(FString& OutError)
{
    FString Json;
    if (!FFileHelper::LoadFileToString(Json, *TaskStatePath))
    {
        OutError = TEXT("任务状态尚未写入");
        return false;
    }
    TSharedPtr<FJsonObject> Root;
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
    if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
    {
        OutError = TEXT("任务状态 JSON 无效");
        return false;
    }
    FString SchemaVersion;
    FString StateTaskId;
    if (!Root->TryGetStringField(TEXT("schema_version"), SchemaVersion)
        || SchemaVersion != TEXT("unreal-audit-task-state@1.0.0")
        || !Root->TryGetStringField(TEXT("task_id"), StateTaskId)
        || StateTaskId != ActiveTaskId)
    {
        OutError = TEXT("任务状态版本或任务 ID 不匹配");
        return false;
    }
    Root->TryGetStringField(TEXT("state"), TaskState);
    Root->TryGetStringField(TEXT("message"), StatusMessage);
    Root->TryGetBoolField(TEXT("can_cancel"), bTaskCanCancel);
    double Number = 0.0;
    if (Root->TryGetNumberField(TEXT("requested_count"), Number)) TaskRequestedCount = FMath::RoundToInt(Number);
    if (Root->TryGetNumberField(TEXT("processed_count"), Number)) TaskProcessedCount = FMath::RoundToInt(Number);
    if (Root->TryGetNumberField(TEXT("completed_batch_count"), Number)) TaskCompletedBatchCount = FMath::RoundToInt(Number);
    if (Root->TryGetNumberField(TEXT("total_batch_count"), Number)) TaskTotalBatchCount = FMath::RoundToInt(Number);
    if (Root->TryGetNumberField(TEXT("progress_fraction"), Number)) TaskProgressFraction = FMath::Clamp(static_cast<float>(Number), 0.0f, 1.0f);
    Root->TryGetStringField(TEXT("handoff_path"), LastHandoffPath);
    OutError.Reset();
    return true;
}

EActiveTimerReturnType SUnrealAssetAuditPanel::PollAuditTask(double CurrentTime, float DeltaTime)
{
    FString Error;
    if (!LoadTaskState(Error))
    {
        return bAuditRunning
            ? EActiveTimerReturnType::Continue
            : EActiveTimerReturnType::Stop;
    }
    if (TaskState != TEXT("completed") && TaskState != TEXT("cancelled") && TaskState != TEXT("failed"))
    {
        return EActiveTimerReturnType::Continue;
    }
    bAuditRunning = false;
    bTaskCanCancel = false;
    if (TaskState == TEXT("failed"))
    {
        return EActiveTimerReturnType::Stop;
    }
    if (FPaths::FileExists(ReportPath))
    {
        FString LoadError;
        if (!LoadReport(ReportPath, LoadError))
        {
            StatusMessage = FString::Printf(TEXT("部分结果已写入，但报告读取失败：%s"), *LoadError);
            return EActiveTimerReturnType::Stop;
        }
        FString SessionError;
        LoadSessionIndex(SessionError);
        if (FPaths::FileExists(ComparisonPath)) LoadComparison(ComparisonPath, SessionError);
    }
    return EActiveTimerReturnType::Stop;
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
    ResultViewMode = 0;
    CurrentProfileId = Root->GetStringField(TEXT("profile_id"));
    CurrentProfileVersion = Root->GetStringField(TEXT("profile_version"));
    CurrentReportCreatedAt = Root->GetStringField(TEXT("created_at"));
    AllIssues.Reset();
    AllAssets.Reset();
    TSet<FString> AssetsWithIssues;
    TMap<FString, int32> IssueCountByAsset;

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
        IssueCountByAsset.FindOrAdd(Item->AssetPath) += 1;
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

        FAssetPtr FailedAsset = MakeShared<FAuditPanelAsset>();
        FailedAsset->AssetPath = Item->AssetPath;
        FailedAsset->AssetName = FPaths::GetBaseFilename(Item->AssetPath);
        FailedAsset->Status = TEXT("failed");
        FailedAsset->TriangleCount = TEXT("—");
        FailedAsset->VertexCount = TEXT("—");
        FailedAsset->MaterialSlotCount = TEXT("—");
        FailedAsset->MaterialDependencyState = TEXT("—");
        FailedAsset->TextureDependencyState = TEXT("—");
        FailedAsset->LodCount = TEXT("—");
        FailedAsset->NaniteState = TEXT("—");
        FailedAsset->CollisionState = TEXT("—");
        FailedAsset->LightmapUvState = TEXT("—");
        FailedAsset->LightmapResolution = TEXT("—");
        FailedAsset->IssueCount = 1;
        AllAssets.Add(FailedAsset);
    }
    for (const TSharedPtr<FJsonValue>& Value : Root->GetArrayField(TEXT("assets")))
    {
        const TSharedPtr<FJsonObject> Asset = Value->AsObject();
        if (!Asset.IsValid()) continue;
        FAssetPtr Item = MakeShared<FAuditPanelAsset>();
        Item->AssetPath = Asset->GetStringField(TEXT("asset_path"));
        Item->AssetName = Asset->GetStringField(TEXT("asset_name"));
        Item->IssueCount = IssueCountByAsset.FindRef(Item->AssetPath);
        Item->Status = Item->IssueCount > 0 ? TEXT("issue") : TEXT("pass");
        Item->MaterialSlotCount = FText::AsNumber(Asset->GetIntegerField(TEXT("material_slot_count"))).ToString();
        double UniqueMaterials = 0.0;
        double MissingMaterials = 0.0;
        if (Asset->TryGetNumberField(TEXT("unique_material_count"), UniqueMaterials)
            && Asset->TryGetNumberField(TEXT("missing_material_slot_count"), MissingMaterials))
        {
            Item->MaterialDependencyState = FString::Printf(
                TEXT("%s/%d%s"), *Item->MaterialSlotCount, FMath::RoundToInt(UniqueMaterials),
                MissingMaterials > 0.0 ? TEXT(" !") : TEXT(""));
        }
        else
        {
            Item->MaterialDependencyState = Item->MaterialSlotCount;
        }
        double TextureCount = 0.0;
        double MaxTextureDimension = 0.0;
        if (Asset->TryGetNumberField(TEXT("texture_dependency_count"), TextureCount)
            && Asset->TryGetNumberField(TEXT("max_texture_dimension"), MaxTextureDimension))
        {
            const int32 MaxSize = FMath::RoundToInt(MaxTextureDimension);
            const FString SizeLabel = MaxSize >= 1024 && MaxSize % 1024 == 0
                ? FString::Printf(TEXT("%dK"), MaxSize / 1024)
                : FText::AsNumber(MaxSize).ToString();
            Item->TextureDependencyState = FString::Printf(
                TEXT("%d/%s"), FMath::RoundToInt(TextureCount), *SizeLabel);
        }
        else
        {
            Item->TextureDependencyState = TEXT("—");
        }
        Item->NaniteState = Asset->GetBoolField(TEXT("nanite_enabled")) ? TEXT("启用") : TEXT("关闭");
        double CollisionCount = 0.0;
        Item->CollisionState = Asset->TryGetNumberField(TEXT("simple_collision_primitive_count"), CollisionCount)
            ? FText::AsNumber(FMath::RoundToInt(CollisionCount)).ToString()
            : TEXT("—");
        double UvChannels = 0.0;
        double LightmapIndex = 0.0;
        if (Asset->TryGetNumberField(TEXT("uv_channel_count"), UvChannels)
            && Asset->TryGetNumberField(TEXT("lightmap_coordinate_index"), LightmapIndex))
        {
            Item->LightmapUvState = FString::Printf(
                TEXT("%d/%d"), FMath::RoundToInt(LightmapIndex), FMath::RoundToInt(UvChannels));
        }
        else
        {
            Item->LightmapUvState = TEXT("—");
        }
        double LightmapResolution = 0.0;
        Item->LightmapResolution = Asset->TryGetNumberField(TEXT("lightmap_resolution"), LightmapResolution)
            ? FText::AsNumber(FMath::RoundToInt(LightmapResolution)).ToString()
            : TEXT("—");
        const TArray<TSharedPtr<FJsonValue>>& Lods = Asset->GetArrayField(TEXT("lods"));
        Item->LodCount = FText::AsNumber(Lods.Num()).ToString();
        Item->TriangleCount = TEXT("—");
        Item->VertexCount = TEXT("—");
        if (!Lods.IsEmpty())
        {
            const TSharedPtr<FJsonObject> Lod0 = Lods[0]->AsObject();
            if (Lod0.IsValid())
            {
                Item->TriangleCount = FText::AsNumber(Lod0->GetIntegerField(TEXT("triangles"))).ToString();
                Item->VertexCount = FText::AsNumber(Lod0->GetIntegerField(TEXT("vertices"))).ToString();
            }
        }
        AllAssets.Add(Item);
    }
    AllAssets.Sort([](const FAssetPtr& Left, const FAssetPtr& Right) { return Left->AssetPath < Right->AssetPath; });
    PassingAssetCount = FMath::Max(0, AssetCount - AssetsWithIssues.Num());
    RebuildFilteredIssues();
    RebuildFilteredAssets();
    StatusMessage = FString::Printf(TEXT("已载入报告 · %d 个资产 · %d 个问题"), AssetCount, IssueCount);
    return true;
}

bool SUnrealAssetAuditPanel::LoadSessionIndex(FString& OutError)
{
    SessionOptions.Reset();
    SelectedSession.Reset();
    const FString IndexPath = FPaths::Combine(SessionRoot, TEXT("session-index.v1.json"));
    FString Json;
    if (!FFileHelper::LoadFileToString(Json, *IndexPath))
    {
        OutError = TEXT("当前 Profile 尚无历史会话");
        if (SessionComboBox.IsValid()) SessionComboBox->RefreshOptions();
        return false;
    }
    TSharedPtr<FJsonObject> Root;
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
    if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid()
        || Root->GetStringField(TEXT("schema_version")) != TEXT("unreal-audit-session-index@1.0.0"))
    {
        OutError = TEXT("会话索引格式无效；历史报告没有被删除");
        if (SessionComboBox.IsValid()) SessionComboBox->RefreshOptions();
        return false;
    }

    for (const TSharedPtr<FJsonValue>& Value : Root->GetArrayField(TEXT("sessions")))
    {
        const TSharedPtr<FJsonObject> Session = Value->AsObject();
        double CancelledCount = 0.0;
        if (Session.IsValid())
        {
            Session->TryGetNumberField(TEXT("cancelled_asset_count"), CancelledCount);
        }
        if (!Session.IsValid()
            || Session->GetStringField(TEXT("profile_id")) != CurrentProfileId
            || Session->GetStringField(TEXT("profile_version")) != CurrentProfileVersion
            || CancelledCount > 0.0
            || Session->GetStringField(TEXT("created_at")) == CurrentReportCreatedAt)
        {
            continue;
        }
        FString CreatedAt = Session->GetStringField(TEXT("created_at"));
        CreatedAt.ReplaceInline(TEXT("T"), TEXT(" "));
        if (CreatedAt.Len() > 19) CreatedAt.LeftInline(19);
        const int32 SessionIssueCount = Session->GetIntegerField(TEXT("issue_count"));
        FSessionPtr Option = MakeShared<FAuditSessionOption>();
        Option->SessionId = Session->GetStringField(TEXT("session_id"));
        Option->IssueCount = SessionIssueCount;
        Option->Label = FString::Printf(TEXT("%s · %d 个问题"), *CreatedAt, SessionIssueCount);
        Option->ReportPath = FPaths::Combine(
            SessionRoot, Session->GetStringField(TEXT("report_path")));
        SessionOptions.Add(Option);
    }
    if (!SessionOptions.IsEmpty()) SelectedSession = SessionOptions[0];
    if (SessionComboBox.IsValid())
    {
        SessionComboBox->RefreshOptions();
        SessionComboBox->SetSelectedItem(SelectedSession);
    }
    OutError = SessionOptions.IsEmpty() ? TEXT("当前 Profile 尚无更早会话") : FString();
    return !SessionOptions.IsEmpty();
}

bool SUnrealAssetAuditPanel::LoadComparison(const FString& Path, FString& OutError)
{
    FString Json;
    if (!FFileHelper::LoadFileToString(Json, *Path))
    {
        OutError = TEXT("尚未生成回归对比");
        return false;
    }
    TSharedPtr<FJsonObject> Root;
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
    if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid()
        || Root->GetStringField(TEXT("schema_version")) != TEXT("unreal-audit-comparison@1.0.0"))
    {
        OutError = TEXT("回归对比 JSON 格式无效");
        return false;
    }

    AllComparisons.Reset();
    NewIssueCount = 0;
    PersistentIssueCount = 0;
    ResolvedIssueCount = 0;
    FailureChangeCount = 0;
    const FString ComparisonStatus = Root->GetStringField(TEXT("status"));
    if (ComparisonStatus == TEXT("no_baseline") || ComparisonStatus == TEXT("incomplete_current"))
    {
        ComparisonBaselineLabel = Root->GetStringField(TEXT("message"));
        RebuildFilteredComparisons();
        return true;
    }

    const TSharedPtr<FJsonObject>* BaselineSession = nullptr;
    if (Root->TryGetObjectField(TEXT("baseline_session"), BaselineSession)
        && BaselineSession && BaselineSession->IsValid())
    {
        FString CreatedAt = (*BaselineSession)->GetStringField(TEXT("created_at"));
        CreatedAt.ReplaceInline(TEXT("T"), TEXT(" "));
        if (CreatedAt.Len() > 19) CreatedAt.LeftInline(19);
        ComparisonBaselineLabel = FString::Printf(
            TEXT("基线：%s · 当前：%s"), *CreatedAt, *CurrentReportCreatedAt.Left(19).Replace(TEXT("T"), TEXT(" ")));
    }
    else
    {
        ComparisonBaselineLabel = SelectedSession.IsValid()
            ? FString::Printf(TEXT("基线：%s"), *SelectedSession->Label)
            : TEXT("已生成回归对比");
    }

    auto AppendRows = [this, &Root](const TCHAR* Field, const TCHAR* ChangeType, bool bFailure)
    {
        const TArray<TSharedPtr<FJsonValue>>& Values = Root->GetArrayField(Field);
        for (const TSharedPtr<FJsonValue>& Value : Values)
        {
            const TSharedPtr<FJsonObject> Item = Value->AsObject();
            if (!Item.IsValid()) continue;
            FComparisonPtr Row = MakeShared<FAuditComparisonRow>();
            Row->ChangeType = ChangeType;
            Row->AssetPath = Item->GetStringField(TEXT("asset_path"));
            Row->RuleId = bFailure ? TEXT("collection.failure") : Item->GetStringField(TEXT("rule_id"));
            Row->Severity = bFailure ? TEXT("error") : Item->GetStringField(TEXT("severity"));
            Row->Message = LocalizedComparisonMessage(ChangeType);
            AllComparisons.Add(Row);
        }
    };
    AppendRows(TEXT("new_issues"), TEXT("new"), false);
    AppendRows(TEXT("persistent_issues"), TEXT("persistent"), false);
    AppendRows(TEXT("resolved_issues"), TEXT("resolved"), false);
    AppendRows(TEXT("new_failures"), TEXT("new_failure"), true);
    AppendRows(TEXT("persistent_failures"), TEXT("persistent_failure"), true);
    AppendRows(TEXT("resolved_failures"), TEXT("resolved_failure"), true);
    NewIssueCount = Root->GetArrayField(TEXT("new_issues")).Num();
    PersistentIssueCount = Root->GetArrayField(TEXT("persistent_issues")).Num();
    ResolvedIssueCount = Root->GetArrayField(TEXT("resolved_issues")).Num();
    FailureChangeCount = Root->GetArrayField(TEXT("new_failures")).Num()
        + Root->GetArrayField(TEXT("persistent_failures")).Num()
        + Root->GetArrayField(TEXT("resolved_failures")).Num();
    RebuildFilteredComparisons();
    OutError.Reset();
    return true;
}

#if WITH_DEV_AUTOMATION_TESTS
bool SUnrealAssetAuditPanel::LoadReportForEvidence(const FString& Path, FString& OutError)
{
    ReportPath = Path;
    if (!LoadReport(Path, OutError)) return false;
    FString SessionError;
    LoadSessionIndex(SessionError);
    return true;
}

bool SUnrealAssetAuditPanel::LoadComparisonForEvidence(const FString& Path, FString& OutError)
{
    ComparisonPath = Path;
    return LoadComparison(Path, OutError);
}

void SUnrealAssetAuditPanel::SetEvidenceView(bool bAssetOverview, const FString& FilterText)
{
    ResultViewMode = bAssetOverview ? 0 : 1;
    SearchText = FilterText;
    if (SearchInput.IsValid())
    {
        SearchInput->SetText(FText::FromString(FilterText));
    }
    else
    {
        RebuildFilteredIssues();
        RebuildFilteredAssets();
    }
}


void SUnrealAssetAuditPanel::SetComparisonEvidenceView(const FString& FilterText)
{
    ResultViewMode = 2;
    SearchText = FilterText;
    if (SearchInput.IsValid())
    {
        SearchInput->SetText(FText::FromString(FilterText));
    }
    else
    {
        RebuildFilteredComparisons();
    }
}

void SUnrealAssetAuditPanel::SetFolderSelectionForEvidence(const TArray<FString>& InternalFolders)
{
    TSet<FString> Paths;
    RebuildSelectionFromInternalFolders(InternalFolders, Paths);
    SelectedAssetPaths = Paths.Array();
    SelectedAssetPaths.Sort();
}

void SUnrealAssetAuditPanel::SetRiskCategoryForEvidence(const FString& Category)
{
    ActiveRiskCategory = Category;
    ResultViewMode = 1;
    RebuildFilteredIssues();
}

void SUnrealAssetAuditPanel::SetTaskEvidenceState(
    const FString& State, int32 Processed, int32 Requested, int32 CompletedBatches,
    int32 TotalBatches)
{
    TaskState = State;
    bAuditRunning = State != TEXT("completed") && State != TEXT("cancelled") && State != TEXT("failed");
    bTaskCanCancel = State == TEXT("pending") || State == TEXT("running");
    TaskProcessedCount = Processed;
    TaskRequestedCount = Requested;
    TaskCompletedBatchCount = CompletedBatches;
    TaskTotalBatchCount = TotalBatches;
    TaskProgressFraction = Requested > 0
        ? FMath::Clamp(static_cast<float>(Processed) / Requested, 0.0f, 1.0f)
        : 1.0f;
    StatusMessage = State == TEXT("cancelling")
        ? TEXT("已请求取消；当前批次完成后保留部分报告")
        : TEXT("正在逐批只读采集；面板可在批次之间响应取消");
}
#endif

void SUnrealAssetAuditPanel::HandleSearchChanged(const FText& Text)
{
    SearchText = Text.ToString().TrimStartAndEnd();
    RebuildFilteredIssues();
    RebuildFilteredAssets();
    RebuildFilteredComparisons();
}

void SUnrealAssetAuditPanel::RebuildFilteredIssues()
{
    FilteredIssues.Reset();
    for (const FIssuePtr& Item : AllIssues)
    {
        const FString LocalRule = RuleLabel(Item->RuleId).ToString();
        const FString LocalSeverity = SeverityLabel(Item->Severity).ToString();
        const bool bMatchesSearch = SearchText.IsEmpty()
            || Item->AssetPath.Contains(SearchText, ESearchCase::IgnoreCase)
            || Item->RuleId.Contains(SearchText, ESearchCase::IgnoreCase)
            || LocalRule.Contains(SearchText, ESearchCase::IgnoreCase)
            || LocalSeverity.Contains(SearchText, ESearchCase::IgnoreCase)
            || Item->Message.Contains(SearchText, ESearchCase::IgnoreCase);
        if (bMatchesSearch && RuleBelongsToRiskCategory(Item->RuleId, ActiveRiskCategory))
        {
            FilteredIssues.Add(Item);
        }
    }
    if (IssueList.IsValid()) IssueList->RequestListRefresh();
}

void SUnrealAssetAuditPanel::RebuildFilteredAssets()
{
    FilteredAssets.Reset();
    for (const FAssetPtr& Item : AllAssets)
    {
        const FString StatusText = AssetStatusLabel(Item->Status).ToString();
        if (SearchText.IsEmpty()
            || Item->AssetPath.Contains(SearchText, ESearchCase::IgnoreCase)
            || Item->AssetName.Contains(SearchText, ESearchCase::IgnoreCase)
            || StatusText.Contains(SearchText, ESearchCase::IgnoreCase))
        {
            FilteredAssets.Add(Item);
        }
    }
    if (AssetList.IsValid()) AssetList->RequestListRefresh();
}

void SUnrealAssetAuditPanel::RebuildFilteredComparisons()
{
    FilteredComparisons.Reset();
    for (const FComparisonPtr& Item : AllComparisons)
    {
        const FString Change = ComparisonChangeLabel(Item->ChangeType).ToString();
        const FString Rule = RuleLabel(Item->RuleId).ToString();
        if (SearchText.IsEmpty()
            || Item->AssetPath.Contains(SearchText, ESearchCase::IgnoreCase)
            || Item->RuleId.Contains(SearchText, ESearchCase::IgnoreCase)
            || Change.Contains(SearchText, ESearchCase::IgnoreCase)
            || Rule.Contains(SearchText, ESearchCase::IgnoreCase)
            || Item->Message.Contains(SearchText, ESearchCase::IgnoreCase))
        {
            FilteredComparisons.Add(Item);
        }
    }
    if (ComparisonList.IsValid()) ComparisonList->RequestListRefresh();
}

TSharedRef<ITableRow> SUnrealAssetAuditPanel::GenerateIssueRow(
    FIssuePtr Item, const TSharedRef<STableViewBase>& OwnerTable)
{
    return SNew(SAuditIssueRow, OwnerTable).Item(Item);
}

TSharedRef<ITableRow> SUnrealAssetAuditPanel::GenerateAssetRow(
    FAssetPtr Item, const TSharedRef<STableViewBase>& OwnerTable)
{
    return SNew(SAuditAssetRow, OwnerTable).Item(Item);
}

TSharedRef<ITableRow> SUnrealAssetAuditPanel::GenerateComparisonRow(
    FComparisonPtr Item, const TSharedRef<STableViewBase>& OwnerTable)
{
    return SNew(SAuditComparisonRow, OwnerTable).Item(Item);
}

FReply SUnrealAssetAuditPanel::ShowAssetOverview()
{
    ResultViewMode = 0;
    return FReply::Handled();
}

FReply SUnrealAssetAuditPanel::ShowIssueDetails()
{
    ResultViewMode = 1;
    return FReply::Handled();
}

FReply SUnrealAssetAuditPanel::ShowComparison()
{
    ResultViewMode = 2;
    FString Error;
    if (FPaths::FileExists(ComparisonPath)) LoadComparison(ComparisonPath, Error);
    return FReply::Handled();
}

FReply SUnrealAssetAuditPanel::OpenReportFolder()
{
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(ReportPath), true);
    FPlatformProcess::ExploreFolder(*FPaths::GetPath(ReportPath));
    return FReply::Handled();
}

FReply SUnrealAssetAuditPanel::OpenSessionFolder()
{
    IFileManager::Get().MakeDirectory(*SessionRoot, true);
    FPlatformProcess::ExploreFolder(*SessionRoot);
    return FReply::Handled();
}

FReply SUnrealAssetAuditPanel::ExportHandoff()
{
    if (bAuditRunning || !FPaths::FileExists(ReportPath)) return FReply::Handled();
    const FString RequestPath = FPaths::Combine(
        FPaths::ProjectSavedDir(), TEXT("UnrealAssetBatchAuditor/handoff-request.json"));
    TSharedRef<FJsonObject> Request = MakeShared<FJsonObject>();
    Request->SetStringField(TEXT("report_path"), ReportPath);
    Request->SetStringField(TEXT("output_root"), HandoffRoot);
    FString Json;
    const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Json);
    FJsonSerializer::Serialize(Request, Writer);
    if (!FFileHelper::SaveStringToFile(
        Json, *RequestPath, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM))
    {
        StatusMessage = TEXT("无法写入团队交接导出请求");
        return FReply::Handled();
    }
    IPythonScriptPlugin* Python = IPythonScriptPlugin::Get();
    if (!Python || (!Python->IsPythonInitialized() && !Python->ForceEnablePythonAtRuntime()))
    {
        StatusMessage = TEXT("Python Script Plugin 未就绪");
        return FReply::Handled();
    }
    FString PythonPath = RequestPath.Replace(TEXT("\\"), TEXT("/"));
    PythonPath.ReplaceInline(TEXT("'"), TEXT("\\'"));
    const FString Command = FString::Printf(
        TEXT("import run_asset_audit; run_asset_audit.export_handoff_from_request_file(r'%s')"),
        *PythonPath);
    if (!Python->ExecPythonCommand(*Command))
    {
        StatusMessage = TEXT("团队交接包导出失败；最新 JSON 报告未被修改");
        return FReply::Handled();
    }
    FString ReportJson;
    TSharedPtr<FJsonObject> ReportRoot;
    if (FFileHelper::LoadFileToString(ReportJson, *ReportPath)
        && FJsonSerializer::Deserialize(
            TJsonReaderFactory<>::Create(ReportJson), ReportRoot)
        && ReportRoot.IsValid())
    {
        LastHandoffPath = FPaths::Combine(
            HandoffRoot, ReportRoot->GetStringField(TEXT("report_id")));
    }
    StatusMessage = TEXT("团队交接包已导出：中文 HTML、CSV 与 SHA-256 清单");
    return FReply::Handled();
}

FReply SUnrealAssetAuditPanel::OpenHandoffFolder()
{
    if (!LastHandoffPath.IsEmpty() && FPaths::DirectoryExists(LastHandoffPath))
    {
        FPlatformProcess::ExploreFolder(*LastHandoffPath);
    }
    return FReply::Handled();
}

FReply SUnrealAssetAuditPanel::RunComparison()
{
    if (!CanRunComparison()) return FReply::Handled();
    TSharedRef<FJsonObject> Request = MakeShared<FJsonObject>();
    Request->SetStringField(TEXT("baseline_report_path"), SelectedSession->ReportPath);
    Request->SetStringField(TEXT("current_report_path"), ReportPath);
    Request->SetStringField(TEXT("output_path"), ComparisonPath);
    const FString RequestPath = FPaths::Combine(
        FPaths::ProjectSavedDir(), TEXT("UnrealAssetBatchAuditor/comparison-request.json"));
    FString RequestJson;
    const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&RequestJson);
    FJsonSerializer::Serialize(Request, Writer);
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(RequestPath), true);
    if (!FFileHelper::SaveStringToFile(
        RequestJson, *RequestPath, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM))
    {
        StatusMessage = TEXT("无法写入回归比较请求");
        return FReply::Handled();
    }
    IPythonScriptPlugin* Python = IPythonScriptPlugin::Get();
    if (!Python || (!Python->IsPythonInitialized() && !Python->ForceEnablePythonAtRuntime()))
    {
        StatusMessage = TEXT("Python Script Plugin 未就绪");
        return FReply::Handled();
    }
    FString PythonPath = RequestPath.Replace(TEXT("\\"), TEXT("/"));
    PythonPath.ReplaceInline(TEXT("'"), TEXT("\\'"));
    const FString Command = FString::Printf(
        TEXT("import run_asset_audit; run_asset_audit.compare_from_request_file(r'%s')"),
        *PythonPath);
    if (!Python->ExecPythonCommand(*Command))
    {
        StatusMessage = TEXT("回归比较失败；详细堆栈已写入 Output Log");
        return FReply::Handled();
    }
    FString Error;
    if (!LoadComparison(ComparisonPath, Error))
    {
        StatusMessage = FString::Printf(TEXT("回归比较读取失败：%s"), *Error);
        return FReply::Handled();
    }
    ResultViewMode = 2;
    StatusMessage = FString::Printf(
        TEXT("回归对比完成 · 新增 %d · 已解决 %d"), NewIssueCount, ResolvedIssueCount);
    return FReply::Handled();
}

FReply SUnrealAssetAuditPanel::OpenReportFile()
{
    if (FPaths::FileExists(ReportPath))
    {
        FPlatformProcess::LaunchFileInDefaultExternalApplication(*ReportPath);
    }
    return FReply::Handled();
}

FText SUnrealAssetAuditPanel::GetSelectionText() const
{
    if (SelectedAssetPaths.IsEmpty())
    {
        return FText::FromString(TEXT("未读取到交付批次\n可选择多个资产，或在资源网格中选择文件夹"));
    }
    return FText::Format(
        FText::FromString(TEXT("待验收：{0} 个对象\n{1} 个文件夹递归发现 {2} 个 Static Mesh")),
        SelectedAssetPaths.Num(), SelectedFolderPaths.Num(), DiscoveredFolderAssetCount);
}

FText SUnrealAssetAuditPanel::GetStatusText() const { return FText::FromString(StatusMessage); }
FText SUnrealAssetAuditPanel::GetAssetCountText() const { return FText::AsNumber(AssetCount); }
FText SUnrealAssetAuditPanel::GetPassCountText() const { return FText::AsNumber(PassingAssetCount); }
FText SUnrealAssetAuditPanel::GetIssueCountText() const { return FText::AsNumber(IssueCount); }
FText SUnrealAssetAuditPanel::GetFailureCountText() const { return FText::AsNumber(FailureCount); }
FText SUnrealAssetAuditPanel::GetRiskCategoryCountText(FString Category) const
{
    int32 Count = 0;
    for (const FIssuePtr& Item : AllIssues)
    {
        Count += RuleBelongsToRiskCategory(Item->RuleId, Category) ? 1 : 0;
    }
    return FText::AsNumber(Count);
}
bool SUnrealAssetAuditPanel::CanRunAudit() const
{
    return !bAuditRunning && !SelectedAssetPaths.IsEmpty() && SelectedProfile.IsValid()
        && !SelectedProfile->Path.IsEmpty();
}

bool SUnrealAssetAuditPanel::CanRunComparison() const
{
    return SelectedSession.IsValid() && FPaths::FileExists(SelectedSession->ReportPath)
        && FPaths::FileExists(ReportPath);
}

void SUnrealAssetAuditPanel::HandleProfileChanged(FProfilePtr Item, ESelectInfo::Type SelectInfo)
{
    if (Item.IsValid())
    {
        SelectedProfile = Item;
        StatusMessage = FString::Printf(TEXT("已切换检查规则：%s"), *Item->Label);
    }
}

void SUnrealAssetAuditPanel::HandleSessionChanged(FSessionPtr Item, ESelectInfo::Type SelectInfo)
{
    if (Item.IsValid())
    {
        SelectedSession = Item;
        StatusMessage = FString::Printf(TEXT("已选择回归基线：%s"), *Item->Label);
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

TSharedRef<SWidget> SUnrealAssetAuditPanel::GenerateSessionOption(FSessionPtr Item) const
{
    return SNew(SVerticalBox)
        + SVerticalBox::Slot().AutoHeight().Padding(8, 5, 8, 1)
        [SNew(STextBlock).Text(FText::FromString(Item->Label))]
        + SVerticalBox::Slot().AutoHeight().Padding(8, 0, 8, 5)
        [
            SNew(STextBlock)
            .Text(FText::FromString(Item->SessionId))
            .Font(FAppStyle::GetFontStyle(TEXT("SmallFont")))
            .ColorAndOpacity(FSlateColor::UseSubduedForeground())
        ];
}

FText SUnrealAssetAuditPanel::GetSelectedProfileLabel() const
{
    return SelectedProfile.IsValid() ? FText::FromString(SelectedProfile->Label) : FText::FromString(TEXT("请选择检查规则"));
}

FText SUnrealAssetAuditPanel::GetSelectedProfileSummary() const
{
    return SelectedProfile.IsValid() ? FText::FromString(SelectedProfile->Summary) : FText::GetEmpty();
}

FText SUnrealAssetAuditPanel::GetSelectedSessionLabel() const
{
    return SelectedSession.IsValid()
        ? FText::FromString(SelectedSession->Label)
        : FText::FromString(TEXT("暂无同 Profile 历史会话"));
}

FText SUnrealAssetAuditPanel::GetComparisonBaselineText() const
{
    return FText::FromString(
        ComparisonBaselineLabel.IsEmpty()
            ? TEXT("完成至少两次同 Profile 审计后显示质量变化")
            : ComparisonBaselineLabel);
}

FText SUnrealAssetAuditPanel::GetNewIssueCountText() const { return FText::AsNumber(NewIssueCount); }
FText SUnrealAssetAuditPanel::GetPersistentIssueCountText() const { return FText::AsNumber(PersistentIssueCount); }
FText SUnrealAssetAuditPanel::GetResolvedIssueCountText() const { return FText::AsNumber(ResolvedIssueCount); }
FText SUnrealAssetAuditPanel::GetFailureChangeCountText() const { return FText::AsNumber(FailureChangeCount); }

FText SUnrealAssetAuditPanel::GetTaskPhaseText() const
{
    if (TaskState == TEXT("pending")) return FText::FromString(TEXT("等待开始"));
    if (TaskState == TEXT("running")) return FText::FromString(TEXT("逐批只读审计中"));
    if (TaskState == TEXT("cancelling")) return FText::FromString(TEXT("正在批次间取消"));
    if (TaskState == TEXT("cancelled")) return FText::FromString(TEXT("已取消并保留部分结果"));
    if (TaskState == TEXT("failed")) return FText::FromString(TEXT("任务失败"));
    return FText::FromString(TEXT("审计完成"));
}

FText SUnrealAssetAuditPanel::GetTaskProgressText() const
{
    return FText::Format(
        FText::FromString(TEXT("{0}/{1} 个对象 · {2}/{3} 个批次")),
        TaskProcessedCount, TaskRequestedCount, TaskCompletedBatchCount, TaskTotalBatchCount);
}

TOptional<float> SUnrealAssetAuditPanel::GetTaskProgressFraction() const
{
    return TaskProgressFraction;
}

FText SUnrealAssetAuditPanel::GetResultViewHint() const
{
    if (ResultViewMode == 0)
    {
        return FText::Format(
            FText::FromString(TEXT("显示 {0} 个已处理对象（含采集失败）")), FilteredAssets.Num());
    }
    if (ResultViewMode == 1)
    {
        return FText::Format(FText::FromString(TEXT("显示 {0} 条可追溯问题")), FilteredIssues.Num());
    }
    return FText::Format(FText::FromString(TEXT("显示 {0} 条质量变化")), FilteredComparisons.Num());
}

EVisibility SUnrealAssetAuditPanel::GetAssetViewVisibility() const
{
    return ResultViewMode == 0 ? EVisibility::Visible : EVisibility::Collapsed;
}

EVisibility SUnrealAssetAuditPanel::GetIssueViewVisibility() const
{
    return ResultViewMode == 1 ? EVisibility::Visible : EVisibility::Collapsed;
}

EVisibility SUnrealAssetAuditPanel::GetComparisonViewVisibility() const
{
    return ResultViewMode == 2 ? EVisibility::Visible : EVisibility::Collapsed;
}

EVisibility SUnrealAssetAuditPanel::GetIdleActionVisibility() const
{
    return bAuditRunning ? EVisibility::Collapsed : EVisibility::Visible;
}

EVisibility SUnrealAssetAuditPanel::GetRunningActionVisibility() const
{
    return bAuditRunning ? EVisibility::Visible : EVisibility::Collapsed;
}

bool SUnrealAssetAuditPanel::CanCancelAudit() const
{
    return bAuditRunning && bTaskCanCancel;
}
