# Unreal Asset Batch Auditor 发布包安装说明

本发布包面向 Windows 项目级安装，已经在 Unreal Engine 5.8.1 验证。它不是 Marketplace 安装包，
也不声明兼容 UE 5.4、5.5、5.6、5.7 或未来版本。

## 安装前

1. 关闭目标项目的 Unreal Editor；
2. 确认项目使用 UE 5.8.x，并已安装 Windows C++ 开发组件；
3. 解压完整 ZIP，不要只复制 DLL；
4. 项目应有唯一的 `<项目名>.uproject`。

## 一键安装

在解压后的发布目录打开 PowerShell：

```powershell
.\install-plugin.ps1 -Action Install -ProjectPath "<项目目录或 .uproject 路径>"
```

脚本会把 `UnrealAssetBatchAuditor` 复制到 `<Project>/Plugins/`，备份 `.uproject` 后写入启用项。
随后启动 Editor，在插件管理器中确认“Unreal 资产批量审计”和 `PythonScriptPlugin` 已启用；必要时按提示重启。入口位于
`工具 > 资产批量审计`。

## 升级

先关闭 Editor，再执行：

```powershell
.\install-plugin.ps1 -Action Upgrade -ProjectPath "<项目目录或 .uproject 路径>"
```

旧版本会移动到 `<Project>/PluginBackups/`，新版本安装失败时脚本会尝试恢复旧目录。确认新版本正常后，
可以自行删除备份。

## 卸载与恢复

```powershell
.\install-plugin.ps1 -Action Uninstall -ProjectPath "<项目目录或 .uproject 路径>" -ConfirmUninstall
```

卸载不会直接销毁插件，而是移动到 `<Project>/PluginBackups/`，并从 `.uproject` 移除插件启用项；每次
descriptor 修改前的副本位于 `PluginBackups/ProjectDescriptors/`。恢复时关闭 Editor，把对应插件备份目录
改回 `<Project>/Plugins/UnrealAssetBatchAuditor`，再重新执行 Install 或在插件管理器中启用。审计产生的 Report、Sessions 和 Handoffs 保留在
项目 `Saved/UnrealAssetBatchAuditor/`，卸载脚本不会删除这些团队证据。

## 手动安装

也可以把发布包中的 `UnrealAssetBatchAuditor` 文件夹复制到：

```text
<Project>/Plugins/UnrealAssetBatchAuditor
```

不要复制仓库的 `.venv`、`Intermediate`、测试工程或 Demo 生成资产。正式 ZIP 已排除这些开发内容。

## 校验下载

发布页同时提供 ZIP 的 `.sha256`。下载后执行：

```powershell
Get-FileHash .\UnrealAssetBatchAuditor-0.9.0-UE5.8-Win64.zip -Algorithm SHA256
```

结果应与 `.sha256` 文件一致。ZIP 内的 `SHA256SUMS.txt` 用于逐文件复核，`RELEASE-MANIFEST.json`
记录版本、测试宿主、源代码修订、文件清单和兼容边界。

## 首次成功路径

1. 在 Content Browser 选择若干 Static Mesh；
2. 打开 `工具 > 资产批量审计`；
3. 选择“桌面平衡（推荐演示）”，点击“读取当前选择”；
4. 设置批大小，执行“开始只读审计”；
5. 查看资产总览中的材质/纹理依赖、交付风险谱、问题证据与回归页；
6. 点击“导出团队包”，在项目 `Saved/UnrealAssetBatchAuditor/Handoffs/` 查看 HTML 和 CSV。

插件只读取元数据，不保存资产、不自动修改 Nanite，也不删除项目内容。单个 C++ 批次仍是同步边界；
“批次间取消”会等待当前批次完成后保留部分 Report。

## 无人值守门禁

发布包根目录同时提供 `run-unattended-audit.ps1`，随包插件包含一个明确标注为演示数据的预设：

```powershell
.\run-unattended-audit.ps1 `
  -EngineRoot "<UE 5.8 安装目录>" `
  -ProjectPath "<项目目录或 .uproject 路径>" `
  -PresetPath ".\UnrealAssetBatchAuditor\Resources\ProjectPresets\engine-basic-shapes-ci.v1.json"
```

正式项目应复制预设并替换 Profile 与显式 `/Game/...` 范围。退出码为：0 通过、10 规则阻断、
20 采集不完整、30 配置错误、40 宿主运行错误。完整接入说明见源码仓 `docs/UNATTENDED_AUDIT.md`。
