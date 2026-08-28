# 工作流截图说明

## v0.5 当前版本

`v0.5/` 中的 8 张图由 UE 5.8.1 独立 `-RenderOffscreen` 宿主直接调用当前生产 Slate 控件生成，
覆盖空状态、完整资产账本、通过/待处理筛选、问题明细、简单碰撞、Lightmap UV 与 Lightmap
分辨率。源数据是 24 个真实 Demo `.uasset` 生成的 v2 Report；图片与源报告 SHA-256 位于：

`artifacts/host-validation/m5/panel-evidence-v0.5.0-dev3.json`

该证据证明真实 Slate 渲染和 Report 解析，不声明鼠标点击、窗口停靠或人工可见验收。

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
