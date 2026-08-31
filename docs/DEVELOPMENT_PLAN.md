# 开发计划

## 当前架构

```text
Project Profile JSON
        ↓
Python orchestration ──→ Issue / Evidence / Report JSON
        ↑
collector protocol
   ├─ offline fixture（回归证据，不是 Unreal 证据）
   └─ Editor-only C++ batch collector（真实宿主边界）
```

规则和阈值归 Profile；Python 不携带隐藏预算。C++ 只采集事实，不做项目规则决策。这样更换平台、资产类别或项目预算时不需要重新编译插件。

## M1：只读审计 MVP

- Profile、Issue、Evidence、Report v1 JSON Schema；
- Static Mesh LOD 顶点/三角形、材质槽、LOD 数和 Nanite 元数据；
- 五项 Profile 驱动检查；
- Python/C++ collector 边界；
- 合成 fixture 故障集与离线回归报告；
- Editor-only 插件骨架、安装和编译说明。

M1 的证据上限是离线 fixture。只有在选定 UE 项目中成功编译、启动并核对真实资产报告后，才能进入 M2 完成状态。

## M2：真实 Unreal 宿主验证

状态：已在 UE 5.8.1 非生产宿主完成；证据见 `artifacts/host-validation/`。

1. 选择非生产 UE5 测试项目，记录 Engine 精确版本和 commit；
2. 编译 Development Editor 插件并保存构建日志摘要；
3. 用已知 Static Mesh 人工核对五类元数据；
4. 覆盖无 render data、错误 object path、Nanite 不可用和部分失败批次；
5. 验证扫描前后 `.uasset` 哈希/时间戳未改变；
6. 保存脱敏 Report 和宿主验证记录。

## M3：实测性能与产品化

状态：首个 UE 5.8.1 热缓存基线已完成。64 个 Engine Static Mesh 经 2 次预热、7 次重复，
中位数 0.5483 ms、P95 0.5968 ms，64 个文件哈希不变。该数字只作为同机回归基线，
不代表冷启动、生产资产或数千资产性能。

有界分批、进度事件、批次间取消和部分失败汇总也已完成真实宿主验证。当前 MVP 的 M3
范围完成；后续项目化扩展不属于本轮完成声明。

- 根据 Unreal Insights/计时数据决定 Asset Registry 预筛选和按批加载策略；
- 增加进度、取消、部分失败和超时合同；
- 扩展碰撞与 Lightmap UV 检查；
- 只有在独立 ChangeSet、人工审批、撤销/备份和复检合同完成后，才讨论 Nanite 修改能力；
- 不在没有基准数据时声称“数千资产不会冻结编辑器”。

唯一下一切片及证据门槛以 `config/goal-state.json` 为准。

## M4：完整资产台账与结果探索

状态：已完成。中文 Slate 面板提供“资产总览 / 问题明细”、共享搜索、通过/需处理/失败状态、
全部成功资产元数据、直接打开最新报告和报告目录。8 张 v0.4 Slate 自动化图片及哈希保留在
`artifacts/host-validation/m4/`。

## M5：交付就绪规则

状态：已完成。

### M5-S1：碰撞与 Lightmap（已完成）

- Profile / Report v2，同时保留 v1 解析兼容；
- C++ 采集简单碰撞体数量、碰撞复杂度、UV 通道、Lightmap Coordinate Index 与分辨率；
- Python 评估简单碰撞、Lightmap UV 就绪度与最低分辨率，政策全部来自 Profile；
- 中文资产账本与问题证据支持新字段和筛选；
- 41+ 离线回归、UE 5.8.1 BuildPlugin、真实 BasicShapes 采集、SHA-256 只读验证和 8 张 v0.5 Slate 截图。

### M5-S2：命名与目录政策（已完成）

- 定义可组合、可禁用的命名前缀/正则/目录规则；
- 对象名、package path 与规则命中证据进入 Report；
- 仅报告，不自动重命名或移动资产；
- 扩展 Demo 故障素材、中文筛选、真实宿主证据和教程。

完成证据：Profile 可选合同、Python 规则、中文规则标签与说明、旧 v2 兼容测试、真实错误命名/错目录
Demo 资产、三套 UE Report、UE 5.8.1 `UE_5.8.1-v0.6.0-dev1` BuildPlugin、独立隐藏宿主 PID 生命周期
记录和 10 张当前 Slate 截图均已落盘。插件仍然只报告，不提供重命名、移动或保存 API。

## M6：历史会话、回归对比与团队交接

状态：已完成。

### M6-S1：不可变会话与回归对比（已完成）

- 已实现项目 `Saved` 下的版本化会话索引和不可变历史 Report；
- 已实现 SHA-256 冲突拒绝、索引损坏中文诊断和原子索引更新；
- 已实现基于 `asset_path + rule_id` 的新增、持续、已解决问题与采集失败分类；
- 面板请求自动归档，同 Profile 历史下拉框可人工选择基线；
- 中文回归页展示新增、持续、已解决和失败变化，并共享搜索；
- Demo 先后运行两次真实 UE 采集，保存 10 新增、35 持续、6 已解决和 2 失败变化；
- 52 项离线测试、UE 5.8.1 `UE_5.8.1-v0.7.0-dev1` BuildPlugin、独立 PID 生命周期和 12 张 Slate 截图通过。

### M6-S2：大批次交互与团队交付（已完成）

- 面板审计改为可观察的分批任务状态，不在尚未验证时宣称 Editor 永不卡顿；
- 增加取消入口，并明确“批次间取消、已完成批次保留”的语义；
- 从正式 Report 生成中文 HTML/CSV 团队交付包，不引入云服务或数据库；
- 导出内容必须包含 Profile、宿主版本、摘要、问题、证据、失败和验证边界；
- 补充大批量 fixture、宿主行为证据、交接教程和当前截图。

完成证据：版本化任务状态、Editor Tick 间单批推进、面板进度与取消入口、取消后的合法部分 Report、
不完整会话基线隔离、中文 HTML/UTF-8 CSV/SHA-256 清单、60 项离线测试、UE 5.8.1
`UE_5.8.1-v0.8.0-dev3` BuildPlugin、独立完整/取消宿主生命周期、19 个任务证据产物和 15 张当前截图。

## M7：发布打包与作品级交付

状态：已完成。

- 从干净暂存源生成确定性插件发布包，而不是把开发缓存混入交付；
- 验证全新安装、启用、启动、升级与卸载路径；
- 生成版本、文件清单、许可证和 SHA-256；
- 只声明实际验证过的 UE 版本，不以一次 5.8.1 构建外推兼容范围；
- 保持只读审计边界，不在发布阶段加入自动修复或 AI/PCG。

完成证据：UE 5.8.1 `UE_5.8.1-v0.8.0-release1` BuildPlugin；32 文件白名单发布树；固定 ZIP
时间戳与双次相同哈希；ZIP、逐文件与 payload tree SHA-256；MIT 许可证；可恢复安装/升级/卸载；
两个独立隐藏 UE 进程分别验证全新安装和升级后的生产 Tab 入口、Python 编排、C++ 真实采集和 Report
落盘；测试进程退出后无残留。当前证据只覆盖 Win64 + UE 5.8.1。

## M8：交付批次与风险谱（已完成）

- Content Browser 中显式选择的资产与文件夹合并为同一审计范围；
- 文件夹通过 Asset Registry 递归发现 Static Mesh，和单选对象去重后稳定排序；
- 面板显示待验收对象、文件夹数和递归发现数，不默认扫描整个项目；
- 原生 Slate 视觉升级为“资产交付验收台”，加入可点击的几何、材质、构建、命名路径和采集异常风险谱；
- 风险数量来自当前 Report，筛选继续保留资产、规则、实测、阈值和 Evidence 证据链。

完成证据：63 项 Python 测试和 Ruff；UE 5.8.1 `UE_5.8.1-v0.9.0-dev1` BuildPlugin；独立隐藏
宿主从真实 `/Engine/BasicShapes` 递归发现网格并验证风险分类；14 张 v0.9-dev1 原生 Slate 截图。

## M9：材质与纹理依赖政策（已完成）

- Profile / Report v3 保留 v1/v2 解析兼容；
- 缺失材质槽、唯一有效材质数、已加载纹理依赖数和最大纹理尺寸四项政策可独立启停；
- C++ 只采集所选 Static Mesh 的材质与 `UMaterialInterface::GetUsedTextures` 可见事实；
- Python 按 Profile 判定，Slate 台账显示“槽/材”和“纹理/最大”，风险谱可只看材质链路。

完成证据：68 项 Python 测试与 Ruff；UE 5.8.1 `UE_5.8.1-v0.9.0-dev2` BuildPlugin；独立隐藏宿主
真实采集 5 个 Engine Static Mesh，得到每资产 1 个有效材质、2 个已加载纹理依赖，最大边长为 512
或 32；证据专用模拟 Profile 产生 9 条可追溯问题；14 张当前 Slate 图位于
`docs/images/workflow/v0.9-material/`。这些事实不等同于完整 Cook 依赖、Shader 成本或 GPU 性能。

## M10：项目预设与无人值守门禁（已完成）

- 版本化项目预设绑定 Profile、显式资产/目录范围、阻断严重度和输出位置；
- 递归目录只发现 Static Mesh，与显式 object path 合并、去重并稳定排序；
- 包装脚本提供 0/10/20/30/40 稳定退出语义，同时写完整 Report 和轻量运行摘要；
- 面板人工验收与无人值守门禁共用 Profile、C++ collector 和 Evidence 合同。

完成证据：73 项 Python 测试与 Ruff；UE 5.8.1 `UE_5.8.1-v0.9.0-dev3` BuildPlugin；独立隐藏
命令行宿主使用打包插件递归审计 `/Engine/BasicShapes` 的 6 个 Static Mesh，记录 12 条非阻断告警、
0 个采集失败并以包装退出码 0 完成；Report、摘要、日志和哈希位于 `artifacts/host-validation/m10/`。
不声明已接入外部 CI、跨版本兼容或生产规模性能。

## M11：v0.9 作品级发布（已完成）

- 55 个白名单 payload 包含运行时 C++/Python、v3 Profile、项目预设、Schema、安装器和中文说明；
- 固定 ZIP 时间戳，相同输入连续两次生成相同哈希；
- 全新临时项目完成独立安装、中文生产 Tab、真实 Cube 采集、随包无人值守、升级与可恢复卸载；
- 发布证据记录源修订、逐文件 SHA-256、payload tree、进程归属和声明边界。

完成证据：`UE_5.8.1-v0.9.0-release1` BuildPlugin；ZIP SHA-256
`1D555A6A525A0C22436E8B3CFF6F0A1F70D7ACD0B6F7447E9E3CB9ACC7865BCC`；完整验证位于
`artifacts/host-validation/m7/v0.9.0-ue5.8.1-win64-validation.json`。只覆盖 Windows 11、Win64、
UE 5.8.1，不声明 Marketplace 或跨版本兼容。

## M12：资产定位与复核效率（已完成）

- 资产总览与问题明细共用一个紧凑复核上下文，不引入聊天式 AI 界面；
- 有效 Static Mesh 可同步到 Content Browser，或显式打开 Static Mesh Editor；
- 规则问题可复制资产、规则、实测、阈值、Evidence ID 和说明，不在 UI 中重新判定规则；
- 采集失败、无效路径、跨工程缺失和非 Static Mesh 对象均保持不可用并显示中文原因；
- 所有动作只读，不保存、重命名、移动或自动修复资产。

完成证据：UE 5.8 `UE_5.8-v0.10.0-dev1` BuildPlugin 已通过；独立隐藏宿主从真实
`/Engine/BasicShapes` 报告问题定位到 Content Browser，并生成 15 张当前 Slate 截图。完整记录见
`artifacts/goal/checkpoint-0021.json`；不把自动化同步选择宣称成可见人工点击测试。

## M13：审阅决策与责任交接（已完成）

- Review Ledger v1 以 Report SHA-256、Issue ID 和 Evidence ID 绑定人工决定；
- 缺少记录表示未复核，可记录需修复、批准例外、负责人和备注；
- 台账采用临时文件加原子替换，损坏 JSON 隔离，同名报告内容变化时旧记录作为孤儿保留；
- Slate 审阅刻度、筛选、行内状态和编辑区区分规则严重度与人工决定；
- HTML、CSV 与交接清单带出审阅状态和台账 SHA-256，不泄露本机绝对路径。

完成证据：79 项 Python 测试与 Ruff；UE 5.8 `UE_5.8-v0.10.0-dev2` BuildPlugin；独立隐藏宿主
写入并重新加载两条真实 BasicShapes 审阅决定，确认源 Report 不变；15 张当前 Slate 图和带审阅字段的
团队交接包位于 `artifacts/host-validation/m13/`。本轮不包含多人并发、账号权限或外部工单。

## M14：交付批次热区与资产组概览（已完成）

### M14-S1：目录热区与下钻（已完成）

- 从当前不可变 Report 的 object path 形成目录组，不查询 Asset Registry 或扩大扫描范围；
- 成功资产与采集失败共同进入组级对象统计，规则问题、通过对象和失败对象保持不同语义；
- 按“采集失败 > 需修复 > 问题密度 > 问题数 > 目录路径”稳定排序；
- Slate 默认先展示资产体检热区，可下钻组内资产或问题，并清除下钻返回完整批次；
- 异常路径进入明确的未归档组，问题无法绑定现有对象时单独计数，不错误归组；
- 问题密度只表示规则问题/对象，不推断 FPS、GPU、Shader 或 Cook 成本。

完成证据：83 项 Python 测试与 Ruff；UE 5.8 `UE_5.8-v0.10.0-dev3` BuildPlugin；真实 24 个
Demo Static Mesh 与 2 个采集失败形成 6 个目录组；独立隐藏宿主验证热区、Heavy 组下钻与清除下钻，
生成 17 张当前 Slate 图。证据位于 `artifacts/host-validation/m14/`。

### M14-S2：热区进入团队交接（已完成）

- 团队包直接复用 `delivery-group-view v1`，只读取现有 Report 与 Review Ledger；
- 中文 HTML 增加目录热区索引、稳定排序说明、组级审阅进度和目录 Evidence 锚点；
- 新增 Excel 可读的 `交付目录热区.csv`，与面板使用同一组级计数和排序；
- `交接清单.json` 记录热区 CSV 哈希、聚合合同、分组/排序规则与不推断性能的边界；
- 清洁组、采集失败组、无 Review Ledger 和未绑定问题均保持明确状态，不把人工决定混入规则严重度。

离线测试与真实 UE Report 交接样例位于 `artifacts/host-validation/m14/team-handoff-hotspots/`。
本切片没有修改 C++、Slate 或采集字段，因此不重复 BuildPlugin 和宿主生命周期测试；真实宿主来源沿用
M14-S1 已保存的 UE 5.8.1 Report，新增证据只证明离线交接导出。

## M15：Texture2D 交付审计（已完成）

- Texture Profile / Report v1 与现有 Static Mesh v1/v2/v3 并列，Issue 与 Evidence 仍保持统一证据形状；
- C++ 批量采集源/平台尺寸、Mip、Texture Group、Compression、sRGB、Virtual Texture 与 Streaming；
- Python 按 Profile 判断尺寸、2 次幂、Mip、分组、压缩/色彩组合、VT 与流送，不携带隐藏阈值；
- Slate 增加“模型交付 / 纹理交付”轨道，类型选择、规则下拉、资产列和复核入口均随报告边界切换；
- 确定性生成 3 张 PNG 并由独立 UE 5.8.1 宿主真实导入，得到 1 个通过、2 个待处理和 7 条问题；
- 88 项离线测试、Ruff、UE 5.8 BuildPlugin、独立真实采集与 13 张当前 Slate 截图通过。

证据位于 `artifacts/host-validation/m15/` 与 `docs/images/workflow/v0.10-texture-audit/`。本里程碑只
证明 Editor 元数据与 Profile 判定，不声明最终 Cook 体积、运行时显存、GPU 成本或跨版本兼容。

## M16：v0.10 双轨可安装作品版本（已完成）

- 版本统一为 0.10.0，确定性 ZIP 包含 67 个白名单 payload，不夹带缓存、PDB、测试或 Demo 二进制；
- 全新临时项目完成独立复制安装、生产 Tab、Static Mesh 与 Texture2D 各一条真实 C++ 采集烟雾；
- 随包项目预设审计 6 个 Engine Static Mesh，退出码 0、0 采集失败；
- 从 GitHub 公开 v0.9.0 ZIP 安装后升级 v0.10.0，旧插件备份与升级后双轨复验通过；
- 全新安装和升级场景均完成可恢复卸载，项目 descriptor 移除启用项，本轮 UE 进程无残留；
- GitHub `v0.10.0` Beta Release 已发布 ZIP、SHA-256 与发布清单。

ZIP SHA-256：`0D466D4779D32A8A563C387DC4A910BDBCA8F7C7AFFBACA82079C89F297F6A33`。
结构化证据位于 `artifacts/host-validation/m16/`。验证只覆盖 Windows 11、Win64 与 UE 5.8.1。

## 当前收口状态

| 里程碑 | 方向 | 边界 |
| --- | --- | --- |
| M19-S1（开发收口） | 三轨交付包总检 MVP | 一次显式选择按模型、纹理、材质分类，分别运行既有合同并汇总交付健康度；不合并事实合同，不自动扩依赖 |

### M19-S1 三轨交付包总检（开发收口）

- 已完成：版本化 Recipe / Summary 合同、三套内置 Recipe 与项目配置样例；
- 已完成：混合选择稳定分类、未知类型显式忽略、三轨独立 Profile / Report 与单轨失败隔离；
- 已完成：Python 逐批编排、批次边界取消、阻断计数、目录热区和确定性总摘要；
- 已完成：原生 Slate 三轨泳道总览，可下钻回模型、纹理、材质专业台账；
- 已完成：118 项 Python 回归、Ruff 与 UE 5.8 `UE_5.8-v0.11.0-dev4` BuildPlugin；
- 验证边界：本次收口没有把离线 fixture 或 BuildPlugin 声称为混合交付的独立 Unreal 宿主交互验证；公开演示仍使用仓库内既有真实 UE 5.8.1 单轨截图与宿主证据；
- 产品边界：不自动追踪资产依赖，不自动修改 Nanite、纹理或材质，不把三种事实合同合并成不可解释的总分。

当前停止继续扩展功能。后续若恢复开发，应从真实混合交付宿主录制与 v0.11 安装包验收开始，而不是继续增加规则类型。

### M18-S1 材质接口交付审计（已完成）

- 已完成：独立 Material Interface Profile、fixture、Report 和 JSON Schema，七组规则全部由 Profile 驱动；
- 已完成：Editor-only C++ 只读采集 Material / Material Instance 的有效 Domain、Blend、双面、Shading、父级链与纹理负载；
- 已完成：原生“材质血缘轨道”、材质专用台账、项目标准编辑、问题定位、审阅、回归和团队交接；
- 已完成：隔离 Demo 工程生成 9 个公开 Engine 材质样本，真实宿主得到 5 个通过、4 个待处理、5 条问题、0 个采集失败；
- 已完成：110 项 Python 回归、Ruff、UE 5.8 BuildPlugin、独立宿主与 13 张当前 Slate 图；
- 边界：不声明 GPU、Shader permutation、PSO、Cook 或跨版本性能，不修改任何材质资产。

### M17-S1 项目验收标准编辑器（已完成）

- 已完成：模型 v3 / 纹理 v1 共用的项目标准校验、字段级中文错误、稳定结构化差异和原子保存；
- 已完成：内置模板显示“内置只读”，项目标准以青色归属标识进入同轨道下拉框；
- 已完成：一键复制到工程 `Config/AssetAudit/Profiles`，自动避免覆盖并立即重新发现、选中；
- 已完成：原生“项目验收标准工作台”，按模型 14 组、纹理 7 组规则编辑启停、阈值、枚举、标识和版本；
- 已完成：字段就地中文错误、保存前结构化差异和“预览有效后才能保存”的交互门槛；
- 已完成：两份自行模拟项目标准、6 张当前截图和独立 UE 5.8.1 模型/纹理真实采集 Report；
- 已完成：离线回归、Ruff 与 UE 5.8 `UE_5.8-v0.11.0-dev2` BuildPlugin。
