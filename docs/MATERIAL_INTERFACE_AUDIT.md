# Material Interface 材质血缘审计

## 它解决什么问题

模型台账只能告诉团队“这个网格用了多少材质”，不能回答材质本身是否适合当前交付目标。材质血缘轨道把
`Material` 与 `Material Instance` 作为独立交付对象，集中检查有效渲染状态、实例父级关系和已加载纹理负载。
它适合主美或 TA 在合并资产、外包回收、平台迁移前快速找到透明、双面、特殊 Domain、过深实例链等需要复核的对象。

这不是性能分析器。结果不代表 GPU 时间、Shader permutation、PSO、显存、Cook 体积或最终平台表现。

## 当前七组 Profile 规则

| 规则 | 采集事实 | Profile 决定 |
| --- | --- | --- |
| 材质域 | Effective Material Domain | 允许值 |
| 混合模式 | Effective Blend Mode | 允许值 |
| 双面渲染 | Effective Two Sided | 期望启用或关闭 |
| 实例父级 | 直接父级与基础材质 | 材质实例是否必须有父级 |
| 父级深度 | 实例链深度 | 最大层数 |
| 纹理依赖 | `GetUsedTextures` 可见路径 | 最大数量 |
| 纹理尺寸 | 已加载纹理的最大边长 | 最大尺寸 |

每条 Issue 都保留资产路径、实测值、Profile 期望、JSON Pointer 和 Evidence ID。阈值不写死在 C++ 或面板中。

## 三分钟录屏流程

1. 打开 `工具 > 资产批量审计`，将“验收轨道”切到“材质血缘轨道”。
2. 选择“材质桌面平衡（推荐演示）”，强调下拉摘要里的 Surface、Opaque/Masked、父级深度和纹理上限来自 Profile。
3. 在 Content Browser 选择 `/Game/UABAMaterialDemo` 文件夹，点击“读取资产 / 文件夹选择”，确认 9 个 Material Interface 进入待验收范围。
4. 点击“开始只读审计”。资产总览应显示 5 个通过、4 个需处理、5 条问题和 0 个采集失败。
5. 依次搜索 `PostProcess`、`Translucent`、`材质实例`，展示材质域、混合模式和直接父级；切到“问题明细”展示实测、阈值和中文证据。
6. 选择问题行后使用“定位资产”“打开复核”“复制证据”，最后打开最新 JSON Report。

## 生成真实演示素材

开发仓使用独立隐藏 UE 进程，把本机公开 `/Engine` 样本复制到隔离 Demo 工程的
`/Game/UABAMaterialDemo`。源 Engine 资产保持不变，仓库不重新分发 `.uasset`：

```powershell
.\scripts\run_material_host_validation.ps1 `
  -EngineRoot "C:\Program Files\Epic Games\UE_5.8" `
  -BuildLabel "UE_5.8-v0.11.0-dev3"
```

9 个样本分为三组：

- `01_Approved`：基础 Surface、单层实例、Opaque 对照；
- `02_RenderState`：Translucent、Unlit Translucent、Two Sided Additive、Post Process；
- `03_ParentChain`：带纹理依赖的父材质及其实例。

资产来源和目标路径记录在
[demo-material-asset-manifest.json](../artifacts/demo/demo-material-asset-manifest.json)，真实宿主结果在
[demo-material-desktop-balanced-v1-report.json](../artifacts/demo/demo-material-desktop-balanced-v1-report.json)。

## 当前验证边界

- 已验证 Windows 11、UE 5.8.1 Editor、9 个真实 Material Interface、0 个采集失败；
- C++ collector 只接受显式 object path，加载失败、非材质对象和异常父级链逐项隔离；
- 运行路径只读，不调用保存、改父级、改参数、改材质图或自动优化接口；
- 离线 fixture 只验证合同和规则，不能冒充 Unreal 宿主验证；
- 当前不声明其他 UE 版本、生产规模性能、人工鼠标交互或运行时画质正确性。
