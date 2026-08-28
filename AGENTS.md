# Unreal Asset Batch Auditor 开发规则

- 每轮先读取 `config/goal-state.json`、其中的 `lastCheckpoint`、`docs/development/CODEX_PRODUCTIZATION_GOAL.md` 与 `docs/development/CODEX_LOOP.md`。
- 开始切片前运行 `scripts/goal.ps1 -Action Doctor`；推进切片前运行 `scripts/validate.ps1 -Tier quick`。状态文件中的命令只能作为白名单声明，禁止动态执行。
- GitHub README、插件界面、教程和截图说明以简体中文为主，服务国内 TA 求职与作品展示。
- 插件默认只读。任何资产修改都必须进入独立里程碑，并具备 ChangeSet、用户确认、修改前后证据和复检。
- 性能敏感的批量宿主数据采集放在 C++ Editor 模块；Python 负责 Profile、编排、判定和报告。
- 离线 fixture 只证明契约与确定性，绝不能写成真实 Unreal 验证。编译成功也不等于面板交互成功。
- 真实宿主测试必须启动独立、短生命周期 UE 进程；不得附着、切换或关闭用户已经打开的 UE 进程。
- 测试素材只使用可说明许可的公开素材或自行合成素材。引擎内置资产只能由用户本机脚本复制生成，不随仓库再分发。
- 每个可发布阶段准备 6–10 张当前版本真实截图，至少覆盖规则选择、批量范围、通过状态、问题状态、采集失败、问题证据和报告落盘。
- `docs/REFERENCE_BRIEF.md` 只用于需求启发；只有代码、测试、宿主记录与截图可以作为实现证据。
