# 工作流截图说明

## v0.8 当前版本

`v0.8/` 中的 01–14 由 UE 5.8.1 独立 `-RenderOffscreen` 宿主直接调用当前生产 Slate 控件生成，
覆盖空状态、资产台账、证据筛选、回归对比、批处理运行和批次间取消。15 是独立浏览器打开由真实
Unreal Report 生成的中文单文件 HTML 后截取，并完成桌面横向溢出和控制台错误检查。源数据包含
24 个真实 Demo `.uasset` 的两份 v2 Report，以及 Engine BasicShapes 的完整/取消任务。图片 SHA-256、
测试 PID、耗时、进程隔离和 19 个任务产物位于：

`artifacts/host-validation/m6/panel-lifecycle-v0.8.0-dev3.json`

该证据证明真实 Slate 渲染、Report 解析、任务状态与导出页面可读性，不声明鼠标点击、窗口停靠或
人工可见验收。

`v0.7/` 保留为历史会话阶段证据，不再作为 README 当前界面。

## v0.3 历史人工截图

这组三张截图用于证明 Unreal Asset Batch Auditor 0.3.0 在 UE 5.8.1 中的真实操作闭环：

1. `01-select-profile.png`：从插件内置下拉框选择检查规则并查看阈值摘要；
2. `02-audit-assets.png`：选择 8 个 Heavy Static Mesh，执行批量审计并查看 19 条问题；
3. `03-review-report.png`：8 个 Light Static Mesh 全部通过，并打开生成的 `latest-report.json`。

## 来源与使用范围

- 截图日期：2026-08-25；
- 宿主：Unreal Engine 5.8.1；
- 插件版本：0.3.0；
- 素材：仓库自带 `Demo/Content/UABADemo`；
- 来源：项目作者在本机真实运行插件后截取；
- 外部版权：无第三方截图或公司内部资产；
- 处理：原图落盘，未拼接审计结果、未伪造 UI 状态。

## SHA-256

```text
01-select-profile.png 4AD6E7636988A984D42B5317AD8C24DE459F43842D86185098B30DD23BFA444D
02-audit-assets.png   D631FFB2E45871F1AC0B6B96B3FAF38E3378CA3FD83B1CC8701F71DE918B06F7
03-review-report.png  CAABA46B3E277A1CE551B781A2A05C15E1E4769B12DA9E0D92425FC81A2CFB95
```
