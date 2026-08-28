# 演示资产矩阵

## 场景设计

演示工程模拟“美术团队准备把一批来源复杂度不同的 Static Mesh 交付到不同平台”的场景。
24 个资产按原始三角形复杂度分成 Light、Medium、Heavy 三组；文件夹名只表示相对复杂度，
不预先决定审核结论。是否通过完全由本次选择的项目 Profile 决定。

v0.5 还为每个资产记录简单碰撞体数量、碰撞复杂度、UV 通道、Lightmap Coordinate Index 与
Lightmap 分辨率。当前真实 Demo 分布中，11 个资产没有简单碰撞，8 个资产只有 1 个 UV 通道，
4 个资产的 Lightmap 分辨率低于 32。第 24 个资产是唯一明确修改过的项目副本：简单碰撞被移除、
Lightmap 分辨率设为 8；此变体用于稳定复现交付错误，不会改写 `/Engine` 源资产。

| # | 分组 | 演示资产 | 三角形 | 顶点 | 材质槽 | LOD | Nanite |
| ---: | --- | --- | ---: | ---: | ---: | ---: | --- |
| 1 | Light | SM_UABA_01_LineSegmentCylinder | 40 | 67 | 1 | 1 | 关闭 |
| 2 | Light | SM_UABA_02_DemoBoxMesh | 48 | 54 | 1 | 1 | 关闭 |
| 3 | Light | SM_UABA_03_GizmoCornerHandle | 80 | 158 | 1 | 1 | 关闭 |
| 4 | Light | SM_UABA_04_StretchingHandle | 120 | 112 | 2 | 1 | 关闭 |
| 5 | Light | SM_UABA_05_TranslateArrowHandle | 172 | 203 | 2 | 1 | 关闭 |
| 6 | Light | SM_UABA_06_BackgroundCube | 204 | 138 | 1 | 1 | 关闭 |
| 7 | Light | SM_UABA_07_SM_Dialog_Move | 240 | 112 | 2 | 1 | 关闭 |
| 8 | Light | SM_UABA_08_RotationHandleIndicator | 272 | 156 | 2 | 1 | 关闭 |
| 9 | Medium | SM_UABA_09_RotationHandle | 352 | 354 | 2 | 1 | 关闭 |
| 10 | Medium | SM_UABA_10_Cylinder | 512 | 334 | 1 | 1 | 关闭 |
| 11 | Medium | SM_UABA_11_SM_ContentWindow_01 | 670 | 376 | 1 | 1 | 关闭 |
| 12 | Medium | SM_UABA_12_RotationHandleQuarter | 952 | 760 | 2 | 1 | 关闭 |
| 13 | Medium | SM_UABA_13_SM_CraneRig_Base | 1068 | 738 | 1 | 1 | 关闭 |
| 14 | Medium | SM_UABA_14_SM_Cube_01 | 1404 | 816 | 1 | 1 | 关闭 |
| 15 | Medium | SM_UABA_15_SM_Radial_Disk | 1728 | 1152 | 1 | 1 | 关闭 |
| 16 | Medium | SM_UABA_16_S_EV_FogVolume_Sphere_01 | 3968 | 2143 | 1 | 1 | 关闭 |
| 17 | Heavy | SM_UABA_17_SimplePivotPainterExample | 4080 | 4590 | 1 | 1 | 关闭 |
| 18 | Heavy | SM_UABA_18_SM_CineCam | 6252 | 4174 | 2 | 1 | 关闭 |
| 19 | Heavy | SM_UABA_19_VivePreController_Trimlines | 17912 | 10587 | 1 | 1 | 关闭 |
| 20 | Heavy | SM_UABA_20_TransformGizmoFreeRotation | 32256 | 32512 | 2 | 1 | 关闭 |
| 21 | Heavy | SM_UABA_21_SM_ColorCalibrator | 37472 | 21422 | 5 | 1 | 关闭 |
| 22 | Heavy | SM_UABA_22_EditorShaderBall | 58540 | 32470 | 3 | 1 | 关闭 |
| 23 | Heavy | SM_UABA_23_SM_MatPreviewMesh_01 | 58540 | 32470 | 3 | 1 | 关闭 |
| 24 | Heavy | SM_UABA_24_SM_Room_01 | 63774 | 41436 | 1 | 1 | 关闭 |

另有两个故意加入的诊断输入：一个真实 Material（类型不匹配）和一个不存在的 object path。
它们用于证明单资产失败不会中断其余 24 个网格。

## 三套 Profile 的预期对比

| Profile | 通过资产 | 有 Issue 的资产 | Issue | 采集失败 | 适合演示 |
| --- | ---: | ---: | ---: | ---: | --- |
| desktop-balanced v2 | 5 | 19 | 43 | 2 | 同时展示几何、碰撞与 Lightmap 交付问题 |
| mobile-strict v2 | 0 | 24 | 111 | 2 | 8 类规则形成严格平台门禁 |
| review-lenient v2 | 15 | 9 | 17 | 2 | 关闭碰撞门禁并放宽 UV 后问题自然减少 |

三次真实 UE 5.8.1 扫描均记录 `unchanged=true`。Profile 数值是教学用模拟数据。
