# Demo 安装与完整操作教程

## 1. 准备环境

- Unreal Engine 5.8.1；
- Visual Studio 2022 与 Unreal C++ 编译组件；
- NetFxSDK 4.8；
- 本仓库路径中不要移动 `Demo` 与 `artifacts/host-build` 的相对关系。

在 PowerShell 中执行：

```powershell
cd D:\3D\_tools\unreal-asset-batch-auditor
.\scripts\prepare_demo.ps1 -EngineRoot "C:\Program Files\Epic Games\UE_5.8"
```

它会依次完成：BuildPlugin、把打包插件链接到 Demo Project、重建插件专用 `/Game/UABADemo`
演示资产、执行一轮基线审计和一轮故障审计、再执行三套 Profile，并把报告写入
`artifacts/demo/`。脚本只清理自己确定性生成的保留路径，不触碰 `/Engine` 源资产或其他项目内容。

## 2. 打开录屏工程

双击：

```text
D:\3D\_tools\unreal-asset-batch-auditor\Demo\UABADemo.uproject
```

打开 Content Drawer，进入：

```text
/Game/UABADemo
├─ 01_Light     8 个
├─ 02_Medium    8 个
├─ 03_Heavy     7 个（含 1 个故意错误命名）
├─ Developers   1 个（故意错误目录）
└─ Textures     3 个（合格、超尺寸、非 2 次幂/错误设置）
```

文件夹只是相对复杂度分组。审核结论来自 Profile，不能把目录名当成质量结论。

### Texture2D 快速演示（推荐作为开场）

若 `Textures` 尚未生成，关闭 Demo Editor 后执行：

```powershell
.\scripts\build_plugin.ps1 -EngineRoot "C:\Program Files\Epic Games\UE_5.8" -Label "UE_5.8-v0.10.0-dev4"
.\scripts\link_demo_plugin.ps1 -BuildLabel "UE_5.8-v0.10.0-dev4"
.\scripts\run_texture_host_validation.ps1 -EngineRoot "C:\Program Files\Epic Games\UE_5.8" -BuildLabel "UE_5.8-v0.10.0-dev4"
```

重新打开 Demo Project 后：

1. 打开 `工具 > 资产批量审计`，把“验收轨道”切到“纹理交付轨道”；
2. 在 Content Browser 选中 `/Game/UABADemo/Textures` 文件夹，再点击“读取资产 / 文件夹选择”；
3. 选择“纹理移动端严格”，确认规则摘要显示源尺寸、2 次幂、Mip、VT 与流送政策；
4. 点击“开始只读审计”，在资产总览对比 1024、1500×900 与 4096 三类真实平台数据；
5. 合格 BaseColor 应通过；NPOT Mask 显示 2 次幂、Mip、Group、压缩/色彩与流送问题；Oversize BaseColor 显示源尺寸与 VT 问题；
6. 切换“问题明细”，分别搜索“压缩”“Mip”“Virtual Texture”，再用“定位资产 / 打开复核 / 复制证据”完成闭环。

这 3 个 `.uasset` 来自仓库脚本确定性生成的 PNG，并由独立 UE 5.8.1 宿主真实导入。生成素材的脚本会写入 Demo；正式审计路径只读，不会替用户修改纹理设置。演示阈值是模拟项目 Profile，不是通用行业标准。

## 3. 在 Editor 面板内完成一次审计

1. 在 Content Browser 打开 `/Game/UABADemo`，搜索 `UABA_` 并全选 24 个 Static Mesh；该搜索会包含故意命名错误的 `BAD_UABA_22_EditorShaderBall`；
2. 选择 `工具 > 资产批量审计`；
3. 点击“读取当前选择”，确认范围显示 24 个资产；
4. 在“检查规则”下拉框选择“桌面平衡（推荐演示）”；其下方会直接显示几何预算、简单碰撞、Lightmap UV 与分辨率阈值；
5. 将单批资产数设为 8，点击“开始只读审计”；
6. 观察左下任务卡：阶段、对象进度、批次进度会随 Editor Tick 更新；面板不会在扫描期间伪装成已完成；
7. 审计完成后默认进入“交付热区”。先看 6 个 Report 目录组：两个采集失败组、Developers、Heavy、Medium 和 Light；
8. 选择 `03_Heavy`，点击“查看组内问题”，确认下钻条说明只筛选当前 Report、不会重新扫描 Content Browser；
9. 点击“清除下钻”，再进入“资产总览”，确认每个资产的状态、LOD0 三角形、顶点、材质/纹理、LOD、Nanite、碰撞、LM UV、LM 分辨率与问题数；
10. 切换“问题明细”，用搜索框筛选规则、证据说明或资产名，并对照实测值与 Profile 阈值；
11. 点击“打开最新报告”直接查看 JSON，或点击“打开报告目录”进入本次报告所在目录。

### 如何解释“交付热区”

- 目录组完全来自当前 Report 中的 `asset_path`，不会偷偷扫描整个项目；
- “问题/对象”是规则问题数量除以本组处理对象数，用于寻找复核工作集中处；
- 排序依次考虑采集失败、已经人工判定需修复、问题密度、问题数和目录路径；
- `Developers` 是故意放错目录的真实项目副本，`Missing` 是不存在路径，二者用于展示不同失败语义；
- 该刻度不表示 FPS、GPU 时间、Shader 成本或 Cook 体积。

目录聚合视图写入：

```text
<Project>/Saved/UnrealAssetBatchAuditor/Views/current-delivery-groups.v1.json
```

它是可重建的面板视图，不替代正式 Report，也不会修改 Report。

### 演示批次间取消

1. 选择足够多的资产，或把单批资产数设为 2；
2. 开始审计后，在任务卡仍显示运行时点击“批次间取消”；
3. 面板先显示“正在取消”，等待当前 C++ 批次结束，再写出部分 Report；
4. 检查 Report 的 `processed_asset_count` 与 `cancelled_asset_count`。已完成批次和采集失败会保留，
   未处理对象不会伪装成采集失败；
5. 取消会话不会出现在可选回归基线中，比较文件状态为 `incomplete_current`。

取消不是逐资产抢占：一次 C++ 批次已经开始后不会从中间打断。若要让取消反馈更及时，应调小单批资产数，
而不是声称 Editor 工作完全异步或永不阻塞。

### 导出给制片、美术或外包

审计完成或保留部分结果后，点击“导出团队包”，再点击“打开交接目录”。插件从现有 Report 生成：

- `审计交接报告.html`：可离线打开的中文单文件报告；
- `审计问题明细.csv`：UTF-8 BOM，Excel 可直接识别中文；
- `交接清单.json`：记录源报告身份、验证边界与两个交付文件的 SHA-256。

交接包位于 `<Project>/Saved/UnrealAssetBatchAuditor/Handoffs/<report-id>/`。导出过程不会重新扫描或
修改资产；HTML/CSV 都保留规则 ID、实测值、期望值、Profile 指针和 Evidence ID，便于技术复核。

## 4. 展示修复前后回归对比

`prepare_demo.ps1` 已经为“桌面平衡”生成两个同 Profile 真实会话：基线轮保持第 22–24 个副本
为原始状态，当前轮再注入错误命名、禁用目录、无简单碰撞和低 Lightmap 分辨率。

1. 保持“桌面平衡（推荐演示）”；
2. 在“回归基线（同一 Profile）”下拉框选择较早的 `41 个问题` 会话；
3. 点击“与所选基线比较”，再切换顶部“回归对比”；
4. 依次指出 `新增 10`、`持续 35`、`已解决 6` 和 `失败变化 2`；
5. 在搜索框输入“已解决”，展示因资产路径变化而从旧稳定标识中消失的 6 条历史问题；
6. 点击“打开会话目录”，展示不可变 Reports、`session-index.v1.json` 与
   `latest-comparison.v1.json`。

“已解决”表示当前 `asset_path + rule_id` 不再命中，不等于插件替用户修复了资产。命名或移动导致
稳定路径改变时，旧路径会归类为已解决、新路径上的命中会归类为新增，这一语义需要在团队接入时明确。

桌面平衡 v3 场景应显示 24 个资产完成真实采集，并增加材质完整性、唯一材质、纹理依赖数和最大纹理
尺寸四类证据。具体 Issue 数以本机生成资产和当前 Profile 为准，不把录屏讲稿中的固定数字当成产品合同。
面板审计只处理当前选择；若同时选中一个 Material，它会被显示为“采集失败”，其余网格仍继续完成。

自动化和诊断演示仍可打开 `Window > Developer Tools > Output Log`，再执行
`Tools > Execute Python Script`：

```text
Demo/Scripts/run_demo_balanced.py
```

该脚本会额外注入一个 Material 和一个不存在路径，用于完整展示两条失败隔离证据和批次进度。

报告位置：

```text
Demo/Saved/UABAAudit/demo-desktop-balanced-v3-report.json
artifacts/demo/demo-desktop-balanced-v3-report.json
```

## 5. 展示“规则来自项目”

回到面板，对同一批选择依次切换“移动端严格”和“宽松复核”后重复审计。

- mobile-strict v3：启用严格几何、材质、纹理、碰撞与 Lightmap 门禁；
- review-lenient v3：关闭简单碰撞与 Lightmap 门禁，放宽几何和纹理预算，但仍检查材质完整性。

不要说“移动端标准就是这些数值”。正确说法是：“这是为了演示 Profile 驱动机制而模拟的项目阈值。”

## 6. 如何阅读报告

报告的重要区域：

- `assets`：每个成功资产的真实采集元数据；
- `simple_collision_primitive_count` / `collision_complexity`：简单碰撞体数量及 Collision Trace Policy；
- `uv_channel_count` / `lightmap_coordinate_index` / `lightmap_resolution`：Lightmap 就绪事实；
- `material_paths` / `missing_material_slot_count` / `unique_material_count`：材质槽完整性与唯一材质事实；
- `texture_paths` / `texture_dependency_count` / `max_texture_dimension`：已加载材质报告的纹理依赖事实；
- `static_mesh.object_name`：资产名、允许前缀、完整正则和对应 Profile 指针；
- `static_mesh.package_path`：实际 package directory、允许根目录和禁用目录段；
- `issues`：规则、严重度、消息与 Evidence ID；
- `evidence`：观测值、期望值和 Profile JSON Pointer；
- `collection_failures`：类型错误与不存在路径；
- `Sessions/session-index.v1.json`：按时间倒序的轻量历史索引和报告 SHA-256；
- `Sessions/latest-comparison.v1.json`：新增、持续、已解决与失败变化；
- `requested/processed/cancelled`：本次批次执行统计；
- `Tasks/current-task-state.json`：原生面板任务阶段、进度、批次计数和最终产物位置；
- `Handoffs/<report-id>/`：HTML、CSV 与 SHA-256 交接清单；
- `Views/current-delivery-groups.v1.json`：当前 Report 的目录热区、排序依据与下钻成员路径；
- `real_unreal_validation=true`：数据来自真实 Unreal Editor；
- Session 的 `integrity.unchanged=true`：本次扫描没有改写演示资产。

## 7. 重新生成与故障处理

- 资产生成器是确定性的，重复执行会在插件保留命名空间内从 Engine 源重新生成副本并核对元数据；
- 24 个资产均从本机 Engine 内容复制为项目资产；第 24 个项目副本被明确改造成“无简单碰撞、Lightmap 分辨率 8”的故障素材，Engine 原件不受影响；
- 第 22 个副本故意命名为 `BAD_UABA_...`，第 23 个副本故意位于 `Developers`；生成器升级时只清理这两个保留命名空间中的旧生成副本，随后可确定性重建；
- 如果插件未加载，先关闭 Editor，重新执行 `prepare_demo.ps1`；
- 如果报告不存在，检查 Output Log 中的 `LogPython: Error`；
- 如果更换 Engine 版本，必须重新 BuildPlugin 和重新保存真实宿主证据，不能沿用 5.8.1 的结论。

## 从问题行复核真实资产

1. 完成审计后切换到“问题明细”，单击任意一条规则问题；
2. 观察搜索框下方的复核条，确认资产名和检查项与所选行一致；
3. 点击“定位资产”，Content Browser 会同步选中报告中的 Static Mesh；
4. 点击“打开复核”进入 Static Mesh Editor，人工查看 LOD、材质、碰撞或 Lightmap 等事实；
5. 点击“复制证据”，把资产路径、规则、实测、阈值、Evidence ID 和说明粘贴到任务单或群聊。

## 记录审阅决定并导出交接包

1. 在“问题明细”选择 `Cone / 资产命名`，选择“需修复”；
2. 负责人填写“环境组 / 小林”，备注填写“移动到项目允许目录并按 SM_ 前缀重命名后复检”；
3. 点击“记录决定”，确认表格审阅列显示红色“需修复”，顶部审阅刻度更新；
4. 选择 `Cube / 资产命名`，记录“批准例外”，负责人填写“主美”；
5. 点击“导出团队包”，在 HTML 或 CSV 中核对规则级别、人工决定、负责人和备注同时存在。

导出目录包含四个文件：

- `审计交接报告.html`：先看交付目录热区，再点击目录进入组内 Evidence；
- `交付目录热区.csv`：可用 Excel 打开，适合按体检刻度、失败数、需修复数或问题密度排序；
- `审计问题明细.csv`：保留资产、规则、实测、期望、Profile 指针、Evidence ID 和审阅决定；
- `交接清单.json`：记录以上文件 SHA-256、目录聚合合同版本、排序规则和验证边界。

推荐演示顺序是：先在 `交付目录热区.csv` 指出 `采集阻断` 与 `高密度` 目录，再打开 HTML 点击对应
目录，展示如何落到具体资产和 Evidence。HTML 中“问题/对象”只表示该目录的规则问题密度，不是
FPS、GPU、Shader、Cook 或资产质量评分。没有 Review Ledger 时，问题会明确显示为“未复核”；
采集失败没有 Issue / Evidence 绑定，因此显示“不可审阅”。

审阅决定保存在项目 `Saved/UnrealAssetBatchAuditor/Reviews`。删除某条决定时选择“未复核”并再次记录。
Report、Static Mesh 和 Profile 均不会被写回。若顶部显示“孤儿记录”，说明台账中的旧决定无法与当前
Report 的 Issue / Evidence 精确匹配；工具会保留但不套用这些记录。

双击有效结果行等同于“打开复核”。以上动作均不修改、保存、重命名或移动资产。若报告来自另一工程、
资产已删除，或该行是采集失败记录，按钮会保持禁用；悬停可查看具体原因。

面板是默认人工工作流；`Demo/Scripts` 是独立的自动化与错误注入入口。两者调用同一套 C++ 采集、
Python 规则和 JSON 合同，不要把脚本预生成报告说成面板当场产生的结果。
