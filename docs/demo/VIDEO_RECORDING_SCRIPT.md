# 完整插件使用视频分镜

建议成片 6–8 分钟，录制 2560×1440 或 1920×1080。先把“资产批量审计”面板停靠在
Content Browser 上方，让资产选择与审计结果同时入镜。

## 0:00–0:35 开场：问题与结果

画面：Content Browser 展示 `/Game/UABADemo` 的 24 个资产。

讲解：

> 美术交付里，几何预算、材质、LOD、Nanite、简单碰撞和 Lightmap 是否合规，不能靠统一行业数字，也不能靠人工逐个打开资产。本工具使用项目 Profile 定义标准，C++ 批量采集事实，Python 生成可追溯报告，全程只读。

## 0:35–1:20 演示素材

依次打开 Light、Medium、Heavy 文件夹，展示缩略图数量和复杂度差异。

强调：24 个都是准备脚本从本机 `/Engine` 内容生成的真实项目 `.uasset`；仓库不再分发这些
Engine 内容二进制。此外还加入一个 Material 和一个不存在路径，专门测试部分失败。

## 1:20–2:00 Profile

画面：打开 `demo-desktop-balanced.v2.json`。

指出：

- 所有阈值都来自 Profile；
- severity 也由 Profile 决定；
- 示例数值是模拟项目数据，不是行业标准。

## 2:00–3:00 运行桌面平衡审计

1. 在 Content Browser 搜索 `SM_UABA_` 并全选 24 个网格；
2. `工具 > 资产批量审计`；
3. 点击“读取当前选择”；
4. 从下拉框选择“桌面平衡（推荐演示）”，让阈值摘要入镜，批大小设为 8；
5. 点击“开始只读审计”，展示摘要与问题表。

讲解：

> 24 个当前选择按 8 个一批进入 C++。5 个资产通过，19 个需要处理，共 43 条问题。界面展示的是同一份正式 JSON 报告，不是预置表格。

## 3:00–4:10 报告与证据

画面：先在面板中搜索 `material`，观察实测值与阈值；再点击“打开报告目录”，打开
`Saved/UnrealAssetBatchAuditor/Reports/latest-report.json`。

依次展示：

1. `real_unreal_validation=true`；
2. `assets` 中的真实三角形、顶点、简单碰撞、UV 通道和 Lightmap 元数据；
3. 一条 Issue；
4. 对应 Evidence 的 observed、expected、profile_pointer；
5. 两条 collection failure；
6. Session 文件中的 `integrity.unchanged=true`。

## 4:10–5:20 切换平台策略

在面板下拉框中切换为“移动端严格”，对同一选择再次审计。

画面保留五条 `UABA_DEMO_RULE`：

- triangle budget；
- vertex budget；
- material slots；
- LOD count；
- Nanite state。

讲解：

> 同一批资产没有改变，只是项目 Profile 改成了严格移动端训练配置，Issue 从 43 条变成 111 条。这证明规则属于项目政策，而不是被写死在 C++ 里。

再切换“宽松复核”，展示 Issue 降至 17 条，并指出它关闭了简单碰撞门禁、放宽了 UV 通道要求。

## 5:20–6:20 架构说明

画面可以切到 README 架构说明或一张简单流程图：

```text
项目 Profile → Python 规则与分批 → C++ 原生采集 → Evidence / Report → 中文台账
```

讲解：

> C++ 负责 Unreal 原生元数据访问，Python 负责分批、进度、取消、规则和报告。审计器没有 SavePackage、MarkPackageDirty 或自动修改 Nanite 的能力。

## 6:20–结束 边界与下一步

如实说明：

- 已验证 UE 5.8.1；
- v0.5 的真实主机证据覆盖 4 个 Engine BasicShapes 的碰撞与 Lightmap 元数据，扫描前后哈希不变；
- Demo 是 24 个项目资产，不代表生产项目规模；
- 120 个 Engine Static Mesh 的额外热缓存测试为 120/120 成功；
- 当前面板是同步只读审计；批次进度、取消回调和错误路径注入仍由自动化入口完整验证。

结尾建议：

> 这个项目展示的重点不是让 AI 猜标准，而是把项目规则、原生采集、失败隔离和证据链组合成可复现的资产质量门禁。
