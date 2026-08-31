using UnrealBuildTool;

public class UnrealAssetBatchAuditor : ModuleRules
{
    public UnrealAssetBatchAuditor(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine" });
        PrivateDependencyModuleNames.AddRange(new[]
        {
            "ApplicationCore",
            "AssetRegistry",
            "ContentBrowser",
            "ContentBrowserData",
            "DesktopPlatform",
            "InputCore",
            "Json",
            "JsonUtilities",
            "Projects",
            "PythonScriptPlugin",
            "Slate",
            "SlateCore",
            "ToolMenus",
            "UnrealEd"
        });
    }
}
