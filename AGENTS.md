# Unreal Asset Batch Auditor 开发规则

- 每轮先读取 `config/goal-state.json`、其中的 `lastCheckpoint`、`docs/development/CODEX_PRODUCTIZATION_GOAL.md` 与 `docs/development/CODEX_LOOP.md`。
- 开始切片前运行 `scripts/goal.ps1 -Action Doctor`。验证按风险分级：Python/文档只跑相关测试与 Ruff；C++/Slate 再加一次 BuildPlugin 和一次独立 UE 烟雾；完整安装矩阵只在发布时运行。状态文件中的命令只能作为白名单声明，禁止动态执行。
- GitHub README、插件界面、教程和截图说明以简体中文为主，服务国内 TA 求职与作品展示。
- 插件默认只读。任何资产修改都必须进入独立里程碑，并具备 ChangeSet、用户确认、修改前后证据和复检。
- 性能敏感的批量宿主数据采集放在 C++ Editor 模块；Python 负责 Profile、编排、判定和报告。
- 离线 fixture 只证明契约与确定性，绝不能写成真实 Unreal 验证。编译成功也不等于面板交互成功。
- 真实宿主测试必须启动独立、短生命周期 UE 进程；不得附着、切换或关闭用户已经打开的 UE 进程。
- 测试素材只使用可说明许可的公开素材或自行合成素材。引擎内置资产只能由用户本机脚本复制生成，不随仓库再分发。
- 可见界面切片只补能证明新能力的当前截图；正式发布阶段再整理 6–10 张完整流程截图，避免重复拍摄旧状态。
- 界面使用 Unreal 原生、高信息密度的“交付验收台”语言，不使用聊天助手、魔法星光、紫蓝渐变等 AI 产品套壳视觉。
- `docs/REFERENCE_BRIEF.md` 只用于需求启发；只有代码、测试、宿主记录与截图可以作为实现证据。
