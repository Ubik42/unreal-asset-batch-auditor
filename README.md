# Unreal Asset Batch Auditor

面向 Unreal 美术团队的只读资产交付验收台。项目 Profile 定义预算和预期，Editor-only C++ 采集宿主事实，Python 负责任务编排与版本化报告。插件不保存、重建或自动修复资产。

> **公开版本：v0.10.0 Beta** · `main` 开发线包含模型、纹理、材质三条专业轨道与“交付包总检”编排 · Windows 11 / Unreal Engine 5.8.1 已验证<br>
> [下载已编译插件](https://github.com/Ubik42/unreal-asset-batch-auditor/releases/tag/v0.10.0) ·
> [5 分钟安装说明](docs/RELEASE_INSTALL.md) · [完整录屏脚本](docs/demo/VIDEO_RECORDING_SCRIPT.md)

![资产交付验收台：批量审计结果](docs/images/workflow/v0.11-demo-flow/02-batch-results.png)

<p align="center"><sub>真实 UE 5.8.1 原生 Slate：从 Content Browser 读取显式选择，按项目 Profile 输出资产、问题与采集失败证据。</sub></p>

## 这个项目体现什么

- **真实管线分层**：C++ 批量读取 Unreal 原生元数据，Python 负责项目规则、任务编排和报告，UI 不承载隐藏业务判断；
- **三轨资产验收**：模型覆盖几何、LOD、碰撞和 Lightmap；纹理覆盖尺寸、Mip、压缩色彩、VT 与流送；材质覆盖 Domain、Blend、双面、Shading、父级链和纹理负载；
- **交付包总检**：一次读取混合选择，稳定分类为模型、纹理、材质三条泳道；每条泳道保留自己的 Profile 与原始 Report，总摘要只负责交付决策、阻断计数和风险热区；
- **上下文与证据设计**：Profile、Issue、Evidence、Report 均有版本化合同，每个问题都能追到实测值、期望值和规则指针；
- **生产可靠性**：逐批任务、批次间取消、部分失败隔离、不可变会话和修复前后回归，不把“没有抛异常”当作成功；
- **团队交付**：一键生成中文 HTML、Excel 可读 CSV 和 SHA-256 清单，无 Unreal 环境也能参与复核；
- **项目标准可治理**：内置模板保持只读，可一键复制到工程 `Config/AssetAudit/Profiles`；项目自有标准被重新发现并直接用于审计；
- **面板与门禁同源**：项目预设把 Profile、显式目录和阻断等级固化为可评审 JSON；人工验收和命令行门禁消费同一规则源；
- **可安装而非只在开发机运行**：发布 ZIP 经过确定性打包、全新项目安装、升级、卸载和两轮独立 UE 宿主验证。

## 从选择规则到交付结论

插件不试图用一张“万能质量分”替代专业判断。单类资产可以直接进入对应轨道；需要验收一批混合交付时，选择“交付包总检”，由版本化 Recipe 把三类资产交给各自 Profile。未知类型会列入“未纳入”，不会静默扩大范围，也不会自动追踪依赖或修改资产。

三条泳道允许独立完成、取消或采集失败。总摘要保留每条原始 Report 的路径，并汇总覆盖数、通过资产、需处理资产、阻断问题和目录热区；用户可以从总览下钻到模型、纹理或材质台账继续复核。

![选择项目规则](docs/images/workflow/v0.11-demo-flow/01-select-profile.png)

## 五步完成单轨审计与交接

### 1. 选择项目检查规则

先选择“模型交付轨道”“纹理交付轨道”或“材质血缘轨道”，再从下拉框选择对应 Profile。内置模板明确标为只读；点击
“复制为项目标准”会把合同校验后的副本写入工程 `Config/AssetAudit/Profiles`，重新发现并立即选中，
不会覆盖插件模板。项目标准说明与当前编辑边界见[项目验收标准](docs/PROJECT_AUDIT_STANDARDS.md)。

复制后点击“打开标准工作台”，可按规则分组修改启停、阈值、严重度、标准 ID 和版本。右侧“保存前差异”
列出保存值与当前值；字段通过合同校验且预览仍有效时，保存按钮才会启用。

![项目验收标准工作台：模型规则差异预览](docs/images/workflow/v0.11-profile-standards/03-model-difference-preview.png)

![选择项目检查规则与空状态](docs/images/workflow/v0.8/01-empty-state.png)

### 2. 选择资源并执行批量审计

在 Content Browser 中显式选择多个资产，或选择一个/多个文件夹。插件只递归发现当前轨道的 Static Mesh、Texture2D 或 Material Interface，
与单独选择的对象合并、去重并稳定排序；不会默认扫描整个项目。资产总览不会隐藏通过项，同一批次内
可以直接对比通过、需处理和采集失败对象。

![文件夹递归形成交付批次](docs/images/workflow/v0.9-material/02-asset-overview.png)

### 3. 先找到交付热区，再查看可追溯报告

“交付热区”只聚合当前 Report，按“采集失败 > 需修复 > 问题密度 > 问题数”稳定排序。每个目录组显示
对象、通过、需处理、规则问题、采集失败和审阅进度；选择一行即可下钻组内资产或问题，不会重新扫描
Content Browser。切换“问题明细”后仍能看到严重度、实测值、Profile 阈值和中文证据说明。

![交付目录热区与稳定排序依据](docs/images/workflow/v0.10-delivery-hotspots/13-delivery-hotspots.png)

![Heavy 目录组下钻后的可追溯问题](docs/images/workflow/v0.10-delivery-hotspots/14-heavy-group-issues.png)

### 4. 从问题回到资产复核

在“资产总览”或“问题明细”选择一行，复核条会显示当前资产与检查项。`定位资产` 只同步
Content Browser 选择，`打开复核` 只打开对应的 Static Mesh Editor、纹理编辑器或材质编辑器；问题行还可复制包含资产路径、规则、
实测、阈值、Evidence ID 和中文说明的确定性摘要。报告路径已失效、对象类型与当前报告不一致或该行属于
采集失败时，动作保持禁用并说明原因，不会误开其他资产。

![问题行定位、打开与复制证据](docs/images/workflow/v0.10-review/13-review-actions.png)

### 5. 记录人工决定并交给团队

规则结果不会自动代表制作决定。审阅刻度把问题分为“未复核 / 需修复 / 批准例外”，并可记录负责人和
简短依据。决定写入按 `report_id + issue_id + evidence_id` 绑定的独立 Review Ledger；原始 Report
保持字节不变。切换或改写同名报告时，无法精确匹配的旧记录会作为孤儿保留，不会套到新问题。

![独立审阅台账：需修复、批准例外与负责人](docs/images/workflow/v0.10-review-ledger/13-review-ledger.png)

以上面板截图由独立 UE 5.8.1 `-RenderOffscreen` 宿主直接渲染生产 Slate 控件；模型数据来自
24 个本机生成的项目 Demo `.uasset` 与 2 条采集失败，纹理数据来自 3 张确定性生成并真实导入的 PNG，材质数据来自复制到隔离 Demo 工程的 9 个公开 Engine 样本；不是网页复刻或设计稿。生命周期记录保存测试 PID、
耗时、退出状态、截图、报告与交接包哈希。自动化证明面板渲染、任务状态、批次间取消和报告解析，
不冒充鼠标点击人工测试。演示 Profile 使用模拟项目阈值，不代表行业统一标准。

## 真实状态画廊

### 交付批次热区

目录组只来自当前 Report 的 object path。问题密度表示“规则问题数 / 本组对象数”，不代表帧率、GPU、
Shader 或 Cook 成本。双击目录组直接进入问题，下钻条可随时返回完整交付批次。

![目录热区选中 Heavy 交付组](docs/images/workflow/v0.10-delivery-hotspots/13-delivery-hotspots.png)

![只查看 Heavy 组规则问题](docs/images/workflow/v0.10-delivery-hotspots/14-heavy-group-issues.png)

### Texture2D 交付轨道

纹理不是模型依赖栏里的一个附属数字。切换“纹理交付轨道”后，面板使用独立 Texture Profile 与
Report，显示源尺寸、平台尺寸、Mip、Texture Group、Compression、色彩空间、Virtual Texture 和
Streaming 状态；类型不匹配的选择会被明确忽略，不会静默扩大扫描范围。

![Texture2D 资产总览](docs/images/workflow/v0.10-texture-audit/02-asset-overview.png)

![压缩与色彩空间组合证据](docs/images/workflow/v0.10-texture-audit/09-compression-color.png)

### Material Interface 材质血缘轨道

材质不再只是 Static Mesh 台账里的一个依赖数字。独立材质合同同时覆盖 Material 与 Material Instance，
资产台账直接呈现材质域、混合模式、双面、Shading Model、直接父级、父级深度与纹理依赖。规则仍由
Profile 决定；它不推测 GPU 时间、Shader permutation 或 Cook 结果，也不会改写材质图。

![材质渲染状态与父级链总览](docs/images/workflow/v0.11-material-interface/02-asset-overview.png)

![材质问题的实测、期望与证据说明](docs/images/workflow/v0.11-material-interface/05-issue-details.png)

完整边界、演示素材和录制顺序见[材质血缘审计说明](docs/MATERIAL_INTERFACE_AUDIT.md)。

### 模型材质与纹理依赖风险

资产台账用“槽/材”和“纹理/最大”同时表达材质槽、唯一有效材质、已加载纹理依赖数与最大边长。
风险谱可只查看材质链路，问题仍保留实测值、Profile 阈值和 JSON Pointer。

![材质风险谱](docs/images/workflow/v0.9-material/09-material-risk-spectrum.png)

![最大纹理尺寸证据](docs/images/workflow/v0.9-material/08-texture-size-evidence.png)

### 只看通过资产

![5 个通过资产](docs/images/workflow/v0.8/03-passing-assets.png)

### 只看需处理资产

![19 个需处理资产](docs/images/workflow/v0.8/04-assets-needing-work.png)

### 简单碰撞证据

![简单碰撞筛选](docs/images/workflow/v0.8/06-collision-evidence.png)

### Lightmap 就绪度证据

![Lightmap UV 证据](docs/images/workflow/v0.8/07-lightmap-uv-evidence.png)

![Lightmap 分辨率证据](docs/images/workflow/v0.8/08-lightmap-resolution-evidence.png)

### 命名与目录政策

![错误资产命名证据](docs/images/workflow/v0.8/09-object-name-evidence.png)

![错误项目目录证据](docs/images/workflow/v0.8/10-package-path-evidence.png)

### 修复前后回归对比

每次面板审计都会保留不可变历史报告。选择同一 Profile 的历史会话作为基线后，插件按稳定的
`asset_path + rule_id` 标识展示新增、持续、已解决问题，并独立跟踪采集失败变化。

![同一 Profile 的回归对比](docs/images/workflow/v0.8/11-regression-overview.png)

![只看已解决变化](docs/images/workflow/v0.8/12-resolved-changes.png)

### 可观察批处理与安全取消

面板每个 Editor Tick 最多推进一个采集批次，明确显示当前阶段、对象进度和已完成批次数。用户可提交
“批次间取消”：当前 C++ 批次完成后停止，已经采集的资产和失败证据会写入合法的部分 Report；该会话
不会被误用作后续回归基线。

![正在执行有界批处理](docs/images/workflow/v0.8/13-running-batch-task.png)

![批次间取消正在保留部分结果](docs/images/workflow/v0.8/14-cancelling-task.png)

### 一键生成团队交接包

“导出团队包”只读取正式 Report 与独立 Review Ledger，不重新扫描资产。每次导出生成可离线打开的
中文 HTML、问题明细 CSV、交付目录热区 CSV 和带 SHA-256 的交接清单。制片、主美或外包同事无需
安装 Unreal，可以先按目录热区定位采集阻断、需修复和高密度组，再跳到组内资产、Profile 阈值、
Evidence 与人工决定。目录问题密度只表示规则问题数 / 处理对象数，不代表资产质量或运行时性能。

![独立中文团队交接报告](docs/images/workflow/v0.8/15-team-handoff-report.png)

真实 UE 5.8.1 Demo Report 的当前交接样例：
[中文 HTML](artifacts/host-validation/m14/team-handoff-hotspots/report-8a19ab6cca63e661/审计交接报告.html) ·
[目录热区 CSV](artifacts/host-validation/m14/team-handoff-hotspots/report-8a19ab6cca63e661/交付目录热区.csv) ·
[问题明细 CSV](artifacts/host-validation/m14/team-handoff-hotspots/report-8a19ab6cca63e661/审计问题明细.csv) ·
[SHA-256 清单](artifacts/host-validation/m14/team-handoff-hotspots/report-8a19ab6cca63e661/交接清单.json)。

## 当前已实现

- 版本化 JSON `Profile`、`Issue`、`Evidence`、`Report` 合同；
- 独立版本化 Texture Profile / Report：源尺寸上限、2 次幂、Mip、Texture Group、Compression/sRGB、Virtual Texture 与 Streaming 政策；
- 独立版本化 Material Interface Profile / Report：Domain、Blend Mode、双面、实例父级、父级深度、纹理数量与最大尺寸政策；
- LOD0 三角形预算、LOD0 顶点预算、材质槽上限、LOD 数量下限、Nanite 预期状态；
- 简单碰撞体数量与碰撞复杂度政策，可由 Profile 决定是否接受 `Complex As Simple`；
- 缺失材质槽、唯一有效材质数、已加载纹理依赖数与最大纹理尺寸政策；
- Lightmap UV 有效性与最少 UV 通道数、Lightmap 最低分辨率；
- 可选资产名前缀、完整正则、允许项目根目录与禁用目录段；旧 v2 Profile 不配置时保持兼容；
- 每条 Evidence 记录观测值、Profile 期望值及其 JSON Pointer；
- Report 同时保存所有成功资产的采集元数据，因此通过项也可与 Editor 复核；
- Unreal Editor-only 插件和 Static Mesh / Texture2D / Material Interface 三组只读 C++ 批量采集接口；
- UE 原生中文 Slate 面板：读取 Content Browser 选择、从预置规则下拉框切换 Profile、运行审计与共享搜索；
- 内置 Profile 与项目自有标准明确分层；支持从当前模板原子复制到工程配置、自动去重命名、重新发现并选中；
- 项目验收标准工作台按模型/纹理/材质规则分组编辑启停、阈值、枚举、标识和版本；字段错误就地显示，保存前提供结构化差异；
- 显式资产与文件夹可以组成同一交付批次；文件夹递归只发现当前验收轨道的资产类型，结果去重并稳定排序；
- “交付风险谱”按几何预算、材质负载、构建就绪、命名路径和采集异常汇总真实问题，点击即可筛选明细；
- “交付热区”按当前 Report 的 package path 形成稳定目录组，显示对象/问题/失败/审阅统计并一键下钻；
- “资产总览”展示每个已采集资产的通过/需处理/失败状态、几何预算、材质/纹理依赖、LOD、Nanite、碰撞、Lightmap UV、Lightmap 分辨率和问题数，不再隐藏通过资产；
- “问题明细”保留严重度、规则、实测值、Profile 阈值与本地化证据说明，并可直接打开最新 JSON 或报告目录；
- 资产行和问题行可只读定位到 Content Browser、打开对应资产编辑器；规则问题可复制带 Evidence ID 的确定性复核摘要；
- 独立 Review Ledger 支持未复核、需修复、批准例外、负责人和备注；台账原子写入，损坏文件隔离，未知旧记录不套用；
- 面板运行会在项目 `Saved/UnrealAssetBatchAuditor/Sessions` 中保存不可变历史报告和版本化轻量索引，不再只留下会被覆盖的 `latest-report.json`；
- 中文面板可选择同 Profile 历史会话作为回归基线，查看新增、持续、已解决和采集失败变化；比较结果使用版本化 JSON，可供后续 CI 或团队看板消费；
- 调用方可设置正整数批次大小；进度事件覆盖请求、处理、成功、失败和取消数量；
- 取消仅在 C++ 批次之间生效，已完成批次的资产与失败证据会保留在 Report；
- 原生面板使用版本化任务状态驱动 pending/running/cancelling/completed/cancelled/failed，并在 Editor Tick 之间推进批次；
- 从正式 Report 确定性生成中文单文件 HTML、两份 UTF-8 BOM CSV 和 SHA-256 交接清单，不重新扫描资产；
- 团队交接 HTML、CSV 与清单可带出人工审阅决定、负责人、备注及台账 SHA-256，同时保留规则严重度；
- 团队包按 `delivery-group-view v1` 输出目录热区排名、组级通过/问题/失败/复核统计，并从目录索引跳到单条 Evidence；
- Python fixture collector 与 Unreal C++ collector 使用同一编排边界；
- 离线错误资产集、回归测试和显式 `real_unreal_validation=false` 报告。
- 版本化项目预设与 `UnrealEditor-Cmd` 无人值守入口，输出正式 Report、轻量运行摘要和稳定退出码。

示例 Profile 的数值只是格式示例，不代表行业标准。正式项目必须复制并评审自己的 Profile。

## 离线运行

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\scripts\validate.ps1 -Tier quick
.\.venv\Scripts\unreal-asset-audit.exe `
  --profile config\Profiles\default-static-mesh-profile.v3.json `
  --fixture tests\fixtures\static_meshes.v3.json `
  --out artifacts\reports\offline-fixture-report.json
```

离线 fixture 只验证合同、规则和报告编排，不能证明插件已经在 Unreal 中编译或运行。

## 无人值守项目门禁

把项目 Profile、显式资产/目录范围、阻断严重度和输出位置写入项目预设，然后运行：

```powershell
.\scripts\run_unattended_audit.ps1 `
  -EngineRoot "C:\Program Files\Epic Games\UE_5.8" `
  -ProjectPath "D:\Project\MyGame.uproject" `
  -PresetPath "D:\Project\Config\AssetAudit\delivery-gate.v1.json"
```

退出码固定为：`0` 通过、`10` 规则阻断、`20` 采集不完整、`30` 配置错误、`40` 宿主运行错误。
工具不会默认扫描整个项目：预设必须显式写出 object path 或允许递归的 `/Game/...` 目录，空范围和
通配符会被拒绝。每轮同时生成完整 Report 与轻量 `latest-run-summary.json`，便于本地脚本或 CI
读取；本仓只证明命令行入口可用，不声称已经接入任何公司的外部 CI。

- [项目预设与无人值守接入教程](docs/UNATTENDED_AUDIT.md)
- [可复制的宿主演示预设](Resources/ProjectPresets/engine-basic-shapes-ci.v1.json)

## 可录制 Demo Kit

仓库内置一个 UE 5.8.1 非生产演示工程和确定性生成脚本。脚本从用户本机已安装的 `/Engine`
内容生成 24 个模型 Demo，并可在隔离工程生成 9 个材质/材质实例样本；同时建立三种复杂度分组、训练 Profile、诊断输入、
两轮真实 v3 报告与只读哈希证据。生成器先建立无三类注入故障的基线，再明确构造三个项目自有故障副本：错误命名、放入
`Developers` 目录、移除简单碰撞并把 Lightmap 分辨率降到 8；生成器不会修改 `/Engine` 源资产。

```powershell
.\scripts\prepare_demo.ps1 -EngineRoot "C:\Program Files\Epic Games\UE_5.8"
```

- [完整安装与操作教程](docs/demo/DEMO_SETUP_AND_USE.md)
- [24 个演示资产矩阵](docs/demo/DEMO_ASSET_MATRIX.md)
- [9 个材质血缘样本与录制步骤](docs/MATERIAL_INTERFACE_AUDIT.md)
- [6–8 分钟录屏分镜与讲稿](docs/demo/VIDEO_RECORDING_SCRIPT.md)
- [当前界面与交接报告截图清单](docs/demo/SCREENSHOT_PLAN.md)

Demo Profile 是为了形成清晰对比而模拟的项目数据，不代表行业标准。主要 Editor 交互入口是
`工具 > 资产批量审计`；脚本入口仍保留给自动化、回归测试和进阶演示。

仓库不再分发由 Unreal Engine 内容复制出的 `.uasset` 二进制；`prepare_demo.ps1` 会在本机生成它们。
生成器不会修改 `/Engine` 原始资产。

`main` 为模型、纹理和材质轨道各带三套演示规则。普通用户不需要填写 JSON 路径；团队规则从内置模板
复制为项目标准后，直接在原生工作台编辑。`临时导入`只用于一次性排查，不进入项目标准治理。

## 安装

### 推荐：直接使用发布包

从 [GitHub Releases](https://github.com/Ubik42/unreal-asset-batch-auditor/releases/tag/v0.10.0)
下载 `UnrealAssetBatchAuditor-0.10.0-UE5.8-Win64.zip`，解压后执行：

```powershell
.\install-plugin.ps1 -Action Install -ProjectPath "<项目目录或 .uproject 路径>"
```

安装器会复制独立插件目录、备份并更新 `.uproject`。升级保留旧插件备份，卸载也可恢复；完整步骤见
[发布包安装说明](docs/RELEASE_INSTALL.md)。

### 从源码编译

1. 把本仓复制或链接到 `<Project>/Plugins/UnrealAssetBatchAuditor`。
2. 在项目 `.uproject` 中启用 `PythonScriptPlugin`，并启用本插件。
3. Python 编排包已位于插件标准目录 `Content/Python`，不需要额外复制或配置搜索路径。
4. 关闭 Editor，重新生成 IDE project files。
5. 用项目所对应的 Unreal Engine 版本构建 `Development Editor` target。
6. 启动 Editor，在 `工具 > 资产批量审计` 打开工作台，再按
   [宿主测试清单](docs/HOST_TEST_PLAN.md)执行真实验证。

插件 descriptor 只声明 `Editor` 模块。C++ collector 仅接收显式 object path：模型轨道读取
`UStaticMesh` render data、材质/已加载纹理依赖、Nanite、BodySetup 与 Lightmap；纹理轨道读取
`UTexture2D` 的源/平台尺寸、Mip、分组、压缩、色彩、VT 与流送状态；材质轨道读取
`UMaterialInterface` 的有效渲染状态、实例父级链和已加载纹理依赖。三条轨道都不会扫描整个项目，
也不会在 Python 中逐顶点或逐像素处理。

Editor Python 的便捷入口默认每批 128 个显式 object path，也允许调用方注入取消和进度回调：

```python
from run_asset_audit import run

report = run(
    profile_path="D:/Project/Config/static-mesh-profile.json",
    asset_paths=selected_asset_paths,
    output_path="D:/Project/Saved/Audits/static-mesh-report.json",
    batch_size=64,
)
```

## 验证边界与开发路线

- 当前没有自动修改 Nanite、SavePackage、MarkPackageDirty 或网格 Build API；
- 已在 UE 5.8.1（changelist 56057345）完成 Win64 Development Editor BuildPlugin、命令行真实宿主运行和可见 Static Mesh Editor 复核；
- v0.5 已在独立 UE 5.8.1 宿主实际采集 Cone、Cube、Cylinder、Sphere 的碰撞体、碰撞复杂度、UV 通道、Lightmap 索引与分辨率；4 个源资产扫描前后 SHA-256 不变；
- 扫描前后 Engine BasicShapes 的 9 个 `.uasset` SHA-256 全部不变；证据位于 `artifacts/host-validation/`；
- 已建立 64 个 Engine Static Mesh、2 次预热、7 次重复的真实宿主热缓存基线；结果只用于回归，不外推到生产项目或数千资产；
- 有界分批、进度、批次间取消和部分失败汇总已在真实 UE 5.8.1 宿主验证；完整场景调用尺寸为 `[2,2,1]`，取消场景只执行首批 `[2]`；
- v0.8 发布基线完成历史会话、回归对比、批次间取消、团队包、确定性发布以及全新安装/升级验证；完整证据见 `artifacts/goal/checkpoint-0015.json`；
- v0.9-dev2 已通过 68 项 Python 测试、Ruff 与 UE 5.8.1 BuildPlugin；独立宿主真实采集 5 个 Engine Static Mesh 的有效材质路径、纹理依赖数和最大纹理边长；
- 材质证据宿主以明确标注的模拟 Profile 产生 9 条纹理风险，14 张原生 Slate 图与生命周期记录位于 `docs/images/workflow/v0.9-material/` 和 `artifacts/host-validation/m9/`；这不代表运行时 GPU 成本、完整 Cook 依赖或人工点击测试；
- v0.9-dev3 增加项目预设与稳定退出码；独立 UE 5.8.1 命令行宿主按显式 `/Engine/BasicShapes` 范围审计 6 个资产，生成 12 条非阻断告警、0 个采集失败并以退出码 0 结束；
- v0.9.0 发布包包含 55 个白名单文件；相同输入双次 ZIP 完全一致；全新安装、真实 Cube 采集、随包无人值守、升级和可恢复卸载均通过。ZIP SHA-256：`1D555A6A525A0C22436E8B3CFF6F0A1F70D7ACD0B6F7447E9E3CB9ACC7865BCC`；
- v0.10-dev1/2 完成资产定位、Evidence 摘要和独立 Review Ledger；人工决定不会改写规则事实或源 Report；
- v0.10-dev3 已通过 83 项 Python 测试、Ruff 与 UE 5.8.1 BuildPlugin；独立宿主使用 24 个 Demo Static Mesh 与 2 个采集失败验证 6 个交付目录组、Heavy 组下钻和清除恢复，并生成 17 张生产 Slate 图；
- v0.10-dev4 已通过 88 项 Python 测试、Ruff 与 UE 5.8.1 BuildPlugin；独立宿主真实导入并采集 3 张 Texture2D，得到 1 个通过对象、2 个待处理对象与 7 条问题，并生成 13 张纹理轨道 Slate 图；
- v0.10.0 发布包含 67 个白名单文件；ZIP SHA-256 为 `0D466D4779D32A8A563C387DC4A910BDBCA8F7C7AFFBACA82079C89F297F6A33`；全新安装、真实双轨采集、随包无人值守、从公开 v0.9 升级和两次可恢复卸载均已通过；
- v0.11-dev2 完成项目验收标准工作台；独立 UE 5.8.1 宿主验证字段错误、差异预览、原子保存，并使用保存后的模型/纹理标准生成两份真实采集 Report；
- v0.11-dev3 完成 Material Interface 材质血缘轨道；独立 UE 5.8.1 宿主真实采集 9 个 Material / Material Instance，得到 5 个通过、4 个待处理、5 条问题、0 个采集失败，并生成 13 张原生 Slate 状态图；
- 不声明 Marketplace 就绪、其他 UE 版本兼容或生产规模绝对无卡顿。

## 许可证与演示素材

源码使用 [MIT License](LICENSE)。仓库不再分发 Unreal Engine 派生 `.uasset`；24 个 Demo 网格由用户本机
已安装的 Engine 内容通过确定性脚本复制到项目专用命名空间，生成器不会修改 `/Engine` 原件。Profile
阈值是用于展示机制的模拟项目数据，不代表行业统一标准。

持续开发状态见 [`config/goal-state.json`](config/goal-state.json)，可恢复的 Codex `/goal` 提示词见
[`docs/development/CODEX_PRODUCTIZATION_GOAL.md`](docs/development/CODEX_PRODUCTIZATION_GOAL.md)，完整路线见
[`docs/DEVELOPMENT_PLAN.md`](docs/DEVELOPMENT_PLAN.md)。
