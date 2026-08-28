# v0.8.0 Beta：可安装的 Unreal 资产审计工作台

这是第一个面向作品展示和真实试用的二进制发布版。重点不是继续堆检查项，而是把 Profile 驱动的
Static Mesh 审计闭环交付成可下载、可安装、可录制、可复核的 Unreal Editor 插件。

## 核心能力

- 10 类 Profile 驱动检查：几何预算、材质槽、LOD、Nanite、简单碰撞、碰撞复杂度、Lightmap UV、
  Lightmap 分辨率、资产命名和项目目录；
- 原生中文 Slate 面板，覆盖资产台账、问题证据、共享搜索和同 Profile 回归对比；
- Editor Tick 间逐批推进、可观察进度、批次间取消和合法部分 Report；
- 不可变历史会话，以及新增、持续、已解决和采集失败变化；
- 中文单文件 HTML、UTF-8 BOM CSV 与 SHA-256 团队交接清单。

## 发布工程

- Windows 项目级安装器支持 Install、Upgrade 和可恢复 Uninstall；
- 32 文件白名单发布树，不包含 Intermediate、PDB、pycache 或 Engine 派生 Demo `.uasset`；
- 固定 ZIP 元数据，相同输入连续两次打包产生相同哈希；
- 发布 manifest 保存源提交、逐文件哈希、payload tree hash 和兼容边界；
- 已在全新 UE 5.8.1 项目中完成安装与升级后的两轮独立宿主烟雾测试。

## 已验证环境

- Windows 11 / Win64；
- Unreal Engine 5.8.1，changelist 56057345；
- Visual Studio 2022 工具链；
- 插件版本 0.8.0 Beta。

本版本不是 Marketplace 包，也不声明兼容其他 Unreal Engine 版本。插件保持只读，不自动修改 Nanite、
不调用 SavePackage，不重建网格。演示 Profile 数值是模拟项目策略，不是行业统一标准。
