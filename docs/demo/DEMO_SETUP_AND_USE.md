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

它会依次完成：BuildPlugin、把打包插件链接到 Demo Project、幂等生成 24 个项目资产、执行
三套 Profile，并把报告写入 `artifacts/demo/`。它不会删除已有 Demo 资产。

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
└─ 03_Heavy     8 个
```

文件夹只是相对复杂度分组。审核结论来自 Profile，不能把目录名当成质量结论。

## 3. 在 Editor 面板内完成一次审计

1. 在 Content Browser 打开 `/Game/UABADemo`，搜索 `SM_UABA_` 并全选 24 个 Static Mesh；
2. 选择 `工具 > 资产批量审计`；
3. 点击“读取当前选择”，确认范围显示 24 个资产；
4. 在“检查规则”下拉框选择“桌面平衡（推荐演示）”；其下方会直接显示三角形、顶点、材质槽、LOD 与 Nanite 阈值；
5. 将单批资产数设为 8，点击“开始只读审计”；
6. 查看“已扫描 / 通过资产 / 问题 / 采集失败”摘要，并用搜索框筛选 `triangle`、`material` 或资产名；
7. 点击“打开报告目录”查看正式 JSON Report。

桌面平衡场景应显示：24 个资产完成真实采集，15 个资产通过，21 条 Issue。面板审计只处理当前选择，
所以不会凭空加入不存在路径。若同时选中一个 Material，它会被显示为“采集失败”，其余网格仍继续完成。

自动化和诊断演示仍可打开 `Window > Developer Tools > Output Log`，再执行
`Tools > Execute Python Script`：

```text
Demo/Scripts/run_demo_balanced.py
```

该脚本会额外注入一个 Material 和一个不存在路径，用于完整展示两条失败隔离证据和批次进度。

报告位置：

```text
Demo/Saved/UABAAudit/demo-desktop-balanced-report.json
artifacts/demo/demo-desktop-balanced-report.json
```

## 4. 展示“规则来自项目”

回到面板，对同一批选择依次切换“移动端严格”和“宽松复核”后重复审计。

- mobile-strict：87 条 Issue，三角形、顶点、材质槽、LOD、Nanite 五类规则全部触发；
- review-lenient：13 条 Issue，展示同一资产在不同项目政策下结论不同。

不要说“移动端标准就是这些数值”。正确说法是：“这是为了演示 Profile 驱动机制而模拟的项目阈值。”

## 5. 如何阅读报告

报告的重要区域：

- `assets`：每个成功资产的真实采集元数据；
- `issues`：规则、严重度、消息与 Evidence ID；
- `evidence`：观测值、期望值和 Profile JSON Pointer；
- `collection_failures`：类型错误与不存在路径；
- `requested/processed/cancelled`：本次批次执行统计；
- `real_unreal_validation=true`：数据来自真实 Unreal Editor；
- Session 的 `integrity.unchanged=true`：本次扫描没有改写演示资产。

## 6. 重新生成与故障处理

- 资产生成器是幂等的，重复执行会复用 `/Game/UABADemo` 中的资产并重新核对元数据；
- 如果插件未加载，先关闭 Editor，重新执行 `prepare_demo.ps1`；
- 如果报告不存在，检查 Output Log 中的 `LogPython: Error`；
- 如果更换 Engine 版本，必须重新 BuildPlugin 和重新保存真实宿主证据，不能沿用 5.8.1 的结论。

面板是默认人工工作流；`Demo/Scripts` 是独立的自动化与错误注入入口。两者调用同一套 C++ 采集、
Python 规则和 JSON 合同，不要把脚本预生成报告说成面板当场产生的结果。
