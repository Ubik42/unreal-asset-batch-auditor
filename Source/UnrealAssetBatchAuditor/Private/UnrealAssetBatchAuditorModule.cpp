#include "UnrealAssetBatchAuditorModule.h"

#include "SUnrealAssetAuditPanel.h"
#include "Framework/Docking/TabManager.h"
#include "Modules/ModuleManager.h"
#include "Styling/AppStyle.h"
#include "ToolMenus.h"
#include "Widgets/Docking/SDockTab.h"

IMPLEMENT_MODULE(FUnrealAssetBatchAuditorModule, UnrealAssetBatchAuditor)

namespace
{
const FName AuditTabName(TEXT("UnrealAssetBatchAuditor"));
}

FName FUnrealAssetBatchAuditorModule::GetAuditTabName()
{
    return AuditTabName;
}

void FUnrealAssetBatchAuditorModule::StartupModule()
{
    FGlobalTabmanager::Get()->RegisterNomadTabSpawner(
        AuditTabName,
        FOnSpawnTab::CreateRaw(this, &FUnrealAssetBatchAuditorModule::SpawnAuditTab))
        .SetDisplayName(NSLOCTEXT("UnrealAssetBatchAuditor", "TabTitle", "资产批量审计"))
        .SetTooltipText(NSLOCTEXT(
            "UnrealAssetBatchAuditor", "TabTooltip", "检查 Static Mesh 预算、材质、LOD、Nanite、碰撞、Lightmap、命名与目录规范"))
        .SetMenuType(ETabSpawnerMenuType::Hidden);

    UToolMenus::RegisterStartupCallback(
        FSimpleMulticastDelegate::FDelegate::CreateRaw(this, &FUnrealAssetBatchAuditorModule::RegisterMenus));
}

void FUnrealAssetBatchAuditorModule::ShutdownModule()
{
    UToolMenus::UnRegisterStartupCallback(this);
    UToolMenus::UnregisterOwner(this);
    FGlobalTabmanager::Get()->UnregisterNomadTabSpawner(AuditTabName);
}

void FUnrealAssetBatchAuditorModule::RegisterMenus()
{
    FToolMenuOwnerScoped OwnerScoped(this);
    UToolMenu* Menu = UToolMenus::Get()->ExtendMenu(TEXT("LevelEditor.MainMenu.Tools"));
    FToolMenuSection& Section = Menu->FindOrAddSection(TEXT("AssetAudit"));
    Section.AddMenuEntry(
        TEXT("OpenUnrealAssetBatchAuditor"),
        NSLOCTEXT("UnrealAssetBatchAuditor", "MenuLabel", "资产批量审计"),
        NSLOCTEXT("UnrealAssetBatchAuditor", "MenuTooltip", "打开只读 Static Mesh 审计工作台"),
        FSlateIcon(FAppStyle::GetAppStyleSetName(), TEXT("Icons.Check")),
        FUIAction(FExecuteAction::CreateLambda([]
        {
            FGlobalTabmanager::Get()->TryInvokeTab(AuditTabName);
        })));
}

TSharedRef<SDockTab> FUnrealAssetBatchAuditorModule::SpawnAuditTab(const FSpawnTabArgs& SpawnTabArgs)
{
    return SNew(SDockTab)
        .TabRole(ETabRole::NomadTab)
        [
            SNew(SUnrealAssetAuditPanel)
        ];
}
