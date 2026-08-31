# 项目预设与无人值守审计

这套入口用于把美术团队在面板里使用的同一份 Profile 接入本地提交检查或 CI。它没有第二套隐藏规则：
项目预设只绑定 Profile、显式范围、阻断严重度和输出位置，真正的资产事实仍由 Editor-only C++ 采集，
Python 仍生成同一种版本化 Report。

## 1. 创建项目预设

在项目中创建 `Config/AssetAudit/delivery-gate.v1.json`：

```json
{
  "schema_version": "unreal-asset-audit-preset@1.0.0",
  "preset_id": "my-project-delivery-gate-v1",
  "description": "角色与场景网格提交门禁",
  "profile_path": "Profiles/production-static-mesh.v3.json",
  "scope": {
    "asset_paths": ["/Game/Characters/Hero/SM_Hero.SM_Hero"],
    "folder_paths": ["/Game/Environment/Delivery"]
  },
  "batch_size": 64,
  "gate": {
    "blocking_severities": ["error", "warning"]
  },
  "output": {
    "report_path": "Saved/UnrealAssetBatchAuditor/CI/latest-report.json",
    "summary_path": "Saved/UnrealAssetBatchAuditor/CI/latest-run-summary.json"
  }
}
```

`profile_path` 相对预设文件解析；两个输出路径相对 `.uproject` 所在目录解析。`asset_paths` 必须是完整
object path，`folder_paths` 必须是显式 `/Game/...` 或 `/Engine/...` package 目录。工具会递归发现目录
中的 Static Mesh，再与单独资产合并、去重和稳定排序；不会接受 `*`、`?` 或空范围。

JSON Schema 位于 `contracts/project-preset.v1.schema.json`。仓库自带的
`Resources/ProjectPresets/engine-basic-shapes-ci.v1.json` 只用于宿主演示，数值不代表生产标准。

## 2. 运行

确保插件已经安装并为项目对应的 Engine 编译，然后执行：

```powershell
.\scripts\run_unattended_audit.ps1 `
  -EngineRoot "C:\Program Files\Epic Games\UE_5.8" `
  -ProjectPath "D:\Project\MyGame.uproject" `
  -PresetPath "D:\Project\Config\AssetAudit\delivery-gate.v1.json" `
  -TimeoutSeconds 180
```

脚本启动一个独立隐藏 `UnrealEditor-Cmd`，不打开审计面板，不附着或关闭用户已有 Editor。超时时只会
结束自己创建的进程。完成后输出一句中文摘要，并把预设结果转换为稳定进程退出码。

## 3. 退出码

| 退出码 | 状态 | 含义 |
| ---: | --- | --- |
| 0 | `passed` | 没有命中预设声明的阻断严重度，且采集完整 |
| 10 | `policy_failed` | 至少一条 Issue 的严重度属于 `blocking_severities` |
| 20 | `collection_failed` | 至少一个请求对象无法完整采集；优先于规则结论 |
| 30 | `config_error` | 预设、Profile、路径或范围不合法 |
| 40 | `runtime_error` | Unreal、插件 API 或不可预期宿主边界失败 |

告警可以进入完整 Report 但不阻断。例如把 `blocking_severities` 设为 `["error"]` 时，warning 会被
记录但退出码仍可为 0。采集失败始终返回 20，因为不完整数据不能被误报为“质量通过”。

## 4. 两种输出

- `latest-report.json`：正式版本化 Report，包含资产事实、Issue、Evidence、采集失败和宿主版本；
- `latest-run-summary.json`：给脚本读取的轻量摘要，包含状态、退出码、计数、消息和正式 Report 路径。

配置错误发生在 Report 生成前时，包装脚本仍会在固定位置写出运行摘要。摘要合同位于
`contracts/unattended-run.v1.schema.json`。

## 5. 本仓验证边界

v0.9.0-dev3 已在 UE 5.8.1 独立隐藏宿主中使用打包插件与随包预设递归审计 `/Engine/BasicShapes`：
6 个 Static Mesh、12 条非阻断告警、0 个采集失败，包装进程退出码为 0，正式 Report 标记
`real_unreal_validation=true`。证据位于 `artifacts/host-validation/m10/`。

这只能证明明确范围、真实采集、报告和退出语义闭环；不代表已接入某家公司 CI，不证明其他 UE 版本，
也不证明生产项目规模性能。
