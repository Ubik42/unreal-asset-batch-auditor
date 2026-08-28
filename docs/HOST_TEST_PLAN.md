# Unreal 宿主测试清单

状态：**UE 5.8.1 的 M2–M5-S1 只读宿主验证已通过**。本文件同时保留可重复步骤和本次证据索引。

## 环境记录

- Unreal Engine 精确版本：5.8.1，changelist 56057345
- 测试项目：仓库内 `tests/host/UnrealAssetBatchAuditorHost.uproject`，一次性非生产宿主
- 插件 build configuration：Development Editor
- 测试日期与执行者：2026-08-25，Codex；可见复核使用 Computer Use 驱动真实 Editor

## 编译门禁

1. 插件位于测试项目 `Plugins/UnrealAssetBatchAuditor`；
2. `.uplugin` 被 Engine 识别为 Editor-only；
3. Unreal Build Tool 编译成功且无弃用 API 警告；
4. Editor 启动后模块和 Python hook 加载成功；
5. packaged/game target 不包含此模块。

## 功能门禁

1. 准备可人工核对的 Static Mesh；
2. 从 Unreal Python 调用 `audit_assets(...)`，由 `UnrealCppCollector` 批量采集；
3. 将报告顶点、三角形、LOD、材质槽、Nanite 值与 Static Mesh Editor 人工核对；
4. 传入错误路径和非 Static Mesh 路径，确认批次返回可诊断失败且 Editor 不崩溃；
5. 记录扫描前后 `.uasset` 文件哈希或时间戳，确认没有修改；
6. 确认真实报告为 `collection_mode=unreal_editor`、`real_unreal_validation=true`。
7. v2 Profile 下复核简单碰撞体数量、碰撞复杂度、UV 通道、Lightmap Coordinate Index 与分辨率。

## 面板门禁（0.2.0）

1. `工具 > 资产批量审计` 能打开并停靠 Nomad Tab；
2. “读取当前选择”只读取 Content Browser 的显式资产选择；
3. Profile 不存在、没有选择、Python 未就绪时给出中文可诊断状态；
4. 审计完成后摘要数值与 Report 一致，问题表能搜索并显示实测值、阈值和中文说明；
5. 非 Static Mesh 显示为单项采集失败，不阻断其余资产；
6. “打开报告目录”指向项目 `Saved/UnrealAssetBatchAuditor/Reports`；
7. 面板只调用读取与报告 API，不提供保存资产、修改 Nanite 或自动修复动作。

## 2026-08-25 执行结果

| 门禁 | 结果 | 证据 |
| --- | --- | --- |
| Development Editor 编译 | 通过；UHT、C++、链接与 Win64 打包成功 | `artifacts/host-build/UE_5.8.1-clean`（本机忽略目录）及 `artifacts/host-validation/build-attempts-2026-08-25.md` |
| 真实宿主采集 | 通过；2 个资产成功，1 个错误路径可诊断失败 | `ue-5.8.1-host-report.json`、`ue-5.8.1-environment.json` |
| 可见 Editor 复核 | 通过；Cube、Sphere 的五类元数据一致 | `ue-5.8.1-visible-review.json` |
| 只读完整性 | 通过；9 个 BasicShapes `.uasset` 均未变化 | `ue-5.8.1-basic-shapes-comparison.json` |
| 热缓存性能基线 | 通过；64 个 Engine Static Mesh，2 次预热、7 次重复 | `ue-5.8.1-readonly-benchmark.json` |
| 有界分批 | 通过；batch size 2 产生 `[2,2,1]` 三次真实 C++ 调用 | `ue-5.8.1-batching-validation.json` |
| 批次间取消 | 通过；只执行首批，保留成功/失败并记录 3 个未处理资产 | `ue-5.8.1-batching-validation.json` |
| 0.3.0 Slate 面板编译 | 通过；UE 5.8.1 Win64 Development Editor 完整编译、链接与打包 | `artifacts/host-build/UE_5.8.1-v0.3.0`（本机忽略目录） |

## 2026-08-27 M4 产品化回归

- 资产总览、问题明细、共享搜索与直接打开最新报告已通过 UE 5.8.1 Win64 Development Editor BuildPlugin（`UE_5.8.1-v0.4.0-dev6`）；
- 独立 `UnrealEditor-Cmd` 宿主成功加载打包插件，真实采集 Cube、Sphere，并隔离一个缺失路径；
- 证据环境明确记录 `claims_visible_editor_review=false`，因此不能把本次无界面回归写成可见面板验收；
- `UnrealAssetBatchAuditor.PanelEvidence` 在独立 `-RenderOffscreen` Editor 中返回 Success，并从真实 Demo Report 渲染 8 张当前版本 Slate 截图；
- 图片、源报告与 SHA-256 记录于 `artifacts/host-validation/m4/panel-evidence-v0.4.0-dev9.json`；该证据证明渲染和解析，不冒充鼠标点击人工测试。
| 面板依赖宿主回归 | 通过；最终二进制加载，24 个真实网格完成采集，21 条 Issue、2 条脚本注入失败 | `artifacts/demo/demo-desktop-balanced-report.json` |

面板的像素级布局、停靠和交互点击仍应由录制者在可见 Editor 中按上方七项做一次人工验收；
编译和无界面宿主回归不能替代可见 UI 验收。

## 2026-08-27 M5-S1 碰撞与 Lightmap 回归

| 门禁 | 结果 | 证据 |
| --- | --- | --- |
| v0.5.0 Development Editor BuildPlugin | 通过；UE 5.8.1 Win64 完整编译、链接、打包 | `artifacts/host-build/UE_5.8.1-v0.5.0-dev3`（本机忽略目录） |
| Report v2 真实采集 | 通过；Cone、Cube、Cylinder、Sphere 均返回完整碰撞和 Lightmap 字段 | `artifacts/host-validation/m5/ue-5.8.1-v0.5.0-dev3-report.json` |
| 只读完整性 | 通过；4 个 Engine BasicShapes 扫描前后 SHA-256 全部一致 | `artifacts/host-validation/m5/ue-5.8.1-v0.5.0-dev3-environment.json` |
| 当前面板渲染 | 通过；独立 `-RenderOffscreen` Slate 自动化生成 8 张 v0.5 图片 | `artifacts/host-validation/m5/panel-evidence-v0.5.0-dev3.json` |

该轮主机命令行证据明确记录 `claims_visible_editor_review=false`；截图证据明确记录
`claims_user_interaction=false`。它们分别证明原生采集与生产 Slate 渲染，不冒充人工点击流程。

## 2026-08-27 v0.6 命名与目录政策回归

| 门禁 | 结果 | 证据 |
| --- | --- | --- |
| v0.6.0 BuildPlugin | 通过；干净暂存目录仅复制发布所需源码与资源，UE 5.8.1 Win64 编译成功 | `artifacts/host-build/UE_5.8.1-v0.6.0-dev1`（本机忽略目录） |
| 真实政策故障 | 通过；真实项目 `.uasset` 分别触发 1 条资产命名和 1 条目录规范问题 | `artifacts/demo/demo-desktop-balanced-v2-report.json` |
| 三套 Profile | 通过；24 个资产分别产生 45 / 113 / 19 条 Issue，均有 2 条独立采集失败 | `artifacts/demo/*-v2-report.json` |
| 面板生命周期 | 通过；结构化证据记录本轮 PID、启动/退出耗时、无超时、自动化 Success，退出后无残留 Unreal PID | `artifacts/host-validation/m5/panel-lifecycle-v0.6.0-dev1.json` |
| 视觉证据 | 通过；10 张生产 Slate PNG 覆盖空态、账本、碰撞、Lightmap、命名和目录 | `docs/images/workflow/v0.6/` |

生命周期证据仍不声明人工点击、停靠或前台可见验收；这些交互由录屏者按教程完成。

## 2026-08-27 v0.7 历史会话与回归对比

| 门禁 | 结果 | 证据 |
| --- | --- | --- |
| v0.7.0 BuildPlugin | 通过；UE 5.8.1 Win64 Development Editor 完整编译、链接、打包 | `artifacts/host-build/UE_5.8.1-v0.7.0-dev1`（本机忽略目录） |
| 两轮真实报告 | 通过；同一 Profile 的 24 个项目资产先后产生 41 / 45 条 Issue，均有 2 条注入式采集失败 | `artifacts/demo/demo-desktop-balanced-v2-*-report.json` |
| 不可变会话 | 通过；两份报告均按 SHA-256 归档，版本化索引保留相对路径 | `artifacts/demo/session-history/session-index.v1.json` |
| 回归分类 | 通过；10 新增、35 持续、6 已解决、2 持续失败 | `artifacts/demo/session-history/latest-comparison.v1.json` |
| 面板生命周期 | 通过；独立隐藏 PID、无超时、自动化 Success、退出后无残留 Unreal PID | `artifacts/host-validation/m6/panel-lifecycle-v0.7.0-dev1.json` |
| 视觉证据 | 通过；12 张当前生产 Slate PNG，其中 2 张覆盖回归总览和已解决筛选 | `docs/images/workflow/v0.7/` |

本轮“真实”只指两份源 Report 均由 UE 5.8.1 的 C++ collector 采集；历史归档和差异分类由
Python 在报告层完成。`-RenderOffscreen` 证据不声明人工鼠标交互通过。

本结果只覆盖记录的 UE 5.8.1 非生产宿主和 Engine 内容，不等价于 UE 5.4/5.5 兼容证明，也不等价于大规模生产性能证明。

哈希证据使用仓库内只读脚本：

```powershell
.\.venv\Scripts\python.exe scripts\asset_integrity.py snapshot --root <ProjectContent> --label before --out artifacts\host-validation\before.json
# 在 Unreal Editor 中执行审计
.\.venv\Scripts\python.exe scripts\asset_integrity.py snapshot --root <ProjectContent> --label after --out artifacts\host-validation\after.json
.\.venv\Scripts\python.exe scripts\asset_integrity.py compare --before artifacts\host-validation\before.json --after artifacts\host-validation\after.json --out artifacts\host-validation\comparison.json
```

manifest 只保存相对路径和 SHA-256，不写入测试项目的绝对路径。
