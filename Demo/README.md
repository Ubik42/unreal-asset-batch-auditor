# UABA Recording Demo

这是 Unreal Asset Batch Auditor 的非生产录屏工程。执行准备脚本后，它会在本机生成 24 个真实
`.uasset` Static Mesh，并提供三套训练 Profile、两个诊断输入和三份真实 UE 5.8.1 审计结果。

演示素材来自用户本机 `/Engine` Static Mesh 的项目内副本。仓库不分发这些 Engine 内容二进制；
生成器不会修改 Engine 原资产，审计器也不会保存、重建或修改任何资产。

快速准备：

```powershell
cd D:\3D\_tools\unreal-asset-batch-auditor
.\scripts\prepare_demo.ps1 -EngineRoot "C:\Program Files\Epic Games\UE_5.8"
```

如果 `artifacts/host-build/UE_5.8.1-v0.3.0` 已经是当前插件包：

```powershell
.\scripts\prepare_demo.ps1 -SkipBuild
```

然后打开 `UABADemo.uproject`，按
[`docs/demo/DEMO_SETUP_AND_USE.md`](../docs/demo/DEMO_SETUP_AND_USE.md) 操作。

重要：Profile 数字是为了教学对比而设计的模拟项目数据，不是行业标准。
