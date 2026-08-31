# v0.11-dev3 材质血缘轨道截图

本目录的 13 张图片由独立 UE 5.8.1 `-RenderOffscreen` 宿主直接渲染生产 Slate 控件，不是网页复刻或设计稿。
源 Report 真实采集隔离 Demo 工程中的 9 个 Material / Material Instance，得到 5 个通过、4 个待处理、
5 条 Profile 驱动问题和 0 个采集失败。

- `01`：材质轨道空状态与内置 Profile；
- `02`：9 个材质接口的渲染状态、父级链和纹理负载总览；
- `03–04`：通过与待处理资产筛选；
- `05`：问题实测、阈值、审阅和 Evidence；
- `06–08`：Material Domain、Blend Mode 与 Two Sided 专项；
- `09`：Material Instance 父级链筛选；
- `10`：待处理材质复核集合；
- `13`：定位、打开材质编辑器与复制证据；
- `14–15`：运行与批次间取消状态。

生命周期、测试 PID、截图哈希和源报告哈希记录在
`artifacts/host-validation/m18/panel-lifecycle-UE_5.8-v0.11.0-dev3-material-interface.json`。
这些证据不声明人工鼠标操作、运行时 GPU 成本、Shader permutation、Cook 结果或跨版本兼容。
