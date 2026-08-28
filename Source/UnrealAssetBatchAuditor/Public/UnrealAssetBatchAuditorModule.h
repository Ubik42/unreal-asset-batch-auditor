#pragma once

#include "Modules/ModuleManager.h"

class SDockTab;
class FSpawnTabArgs;

class FUnrealAssetBatchAuditorModule final : public IModuleInterface
{
public:
    virtual void StartupModule() override;
    virtual void ShutdownModule() override;
    static FName GetAuditTabName();

private:
    void RegisterMenus();
    TSharedRef<SDockTab> SpawnAuditTab(const FSpawnTabArgs& SpawnTabArgs);
};
