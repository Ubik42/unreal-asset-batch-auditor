# v0.11 项目验收标准工作台

6 张图片由独立 UE 5.8.1 `UnrealEditor-Cmd -RenderOffscreen` 直接渲染生产 Slate 控件：

1. 模型项目标准初始状态；
2. 非法语义版本与三角形阈值的字段级错误；
3. 模型标准三项保存前差异；
4. 模型标准保存完成；
5. 纹理标准两项保存前差异；
6. 纹理标准保存完成。

同一宿主随后使用保存后的 Profile 审计 Engine Cube 与 DefaultTexture，并保存真实 Report。图片证明
控件渲染与自动化状态流，不冒充人工鼠标交互。
