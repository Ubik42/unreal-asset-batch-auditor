# Codex `/goal`：Unreal 资产审计工作台产品化

## 可直接恢复的目标提示词

```text
/goal

仅开发 D:\3D\_tools\unreal-asset-batch-auditor，不修改 Art Pipeline Skill、AIToolTA 或其他仓库。

把 Unreal Asset Batch Auditor 持续开发成面向国内 TA 求职展示、可真实安装、可录制完整演示、可由团队复用的中文 Unreal Editor 资产审计工作台。

每轮必须先读取：
1. AGENTS.md；
2. config/goal-state.json；
3. goal-state.lastCheckpoint 指向的检查点；
4. docs/development/CODEX_PRODUCTIZATION_GOAL.md；
5. docs/development/CODEX_LOOP.md；
6. 当前 git diff 与最近提交。

然后运行 scripts/goal.ps1 -Action Doctor，只执行 nextSlice 中明确允许的范围。每轮只推进一个可验证切片；先修复已有失败，再开发新能力。切片结束必须运行 quick validation；需要 UE 的切片还必须完成 BuildPlugin，并用独立短生命周期 Unreal 进程验证，不得接管或关闭用户已有 UE 会话。

产品方向：
- 原生中文编辑器面板，不依赖用户手填路径；
- Profile 驱动，所有阈值来自版本化项目规则；
- C++ 批量采集宿主事实，Python 负责规则、编排和报告；
- 资产总览、问题明细、证据说明、失败隔离、报告导出和团队交接完整闭环；
- 逐步扩展 Static Mesh 的几何预算、材质槽、LOD、Nanite、碰撞、Lightmap UV、命名与目录政策；
- 大批量任务要有进度、取消、稳定排序和可恢复结果；
- 默认只读。任何自动修复必须作为独立里程碑，先生成 ChangeSet，用户确认后才可执行并复检；
- 使用自合成或许可清晰的公开测试素材，提供 6–10 张真实当前版本截图、安装教程、录屏脚本和已知限制；
- 不为了显得复杂而加入 AI/PCG。只有能降低规则配置、问题解释或团队交接成本时才引入 AI，并且确定性规则仍是最终判定依据。

证据边界：
- fixture ≠ Unreal 宿主验证；
- BuildPlugin 成功 ≠ 面板交互成功；
- 单一 UE 版本验证 ≠ 跨版本兼容；
- warm-cache 小样本 ≠ 生产规模性能；
- README 计划项 ≠ 已实现能力。

持续里程碑：
M4 完整审计台账与结果探索；
M5 碰撞、Lightmap UV、命名和目录政策；
M6 大批量交互、保存会话与团队交接；
M7 发布包、真实截图、教学素材和作品级交付。

每次推进时同步更新 goal-state 与新 checkpoint；保留旧 checkpoint，不改写历史证据。只有所有验收项和真实宿主验证完成后，才能把当前里程碑标为 completed。
```

## 设计理由

这个循环把“要做什么”“本轮能碰什么”“证据最多能证明什么”分开。Codex 即使经过上下文压缩，也能从状态文件恢复到唯一进行中的切片，并且不会把离线 mock、编译结果或旧版本截图升级成新版本真实验证。

## 产品化路线

| 里程碑 | 用户价值 | 主要交付 |
| --- | --- | --- |
| M4 | 一眼看完整批次，而非只看错误 | 资产总览、问题明细、共享搜索、通过/问题/失败状态 |
| M5 | 覆盖交付前最常见 Static Mesh 风险 | 碰撞、Lightmap UV、命名、目录规则，全部 Profile 驱动 |
| M6 | 支持团队级批量审计 | 非阻塞进度、取消、保存会话、报告对比与交接摘要 |
| M7 | 可安装、可教学、可录屏、可复核 | 发布包、6–10 张截图、演示素材、教程、兼容性与限制 |

