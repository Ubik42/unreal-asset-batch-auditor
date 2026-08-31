# v0.9-dev2 材质与纹理证据

01–14 均由 UE 5.8.1 独立隐藏 `UnrealEditor-Cmd -RenderOffscreen` 进程直接渲染生产 Slate 控件。
源 Report 真实采集 5 个 Engine Static Mesh 的材质与已加载纹理依赖；证据专用模拟 Profile 产生
5 条纹理依赖和 4 条纹理尺寸问题。

这组图片证明报告解析、材质风险筛选、回归页和任务状态可以在真实宿主渲染，不声明人工鼠标操作、
完整 Cook 依赖、运行时显存或 GPU 成本。生命周期、PID、哈希和报告路径见：

`artifacts/host-validation/m9/panel-lifecycle-UE_5.8.1-v0.9.0-dev2-material-ui.json`
