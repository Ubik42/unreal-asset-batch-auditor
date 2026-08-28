# 开发计划

## 当前架构

```text
Project Profile JSON
        ↓
Python orchestration ──→ Issue / Evidence / Report JSON
        ↑
collector protocol
   ├─ offline fixture（回归证据，不是 Unreal 证据）
   └─ Editor-only C++ batch collector（真实宿主边界）
```

规则和阈值归 Profile；Python 不携带隐藏预算。C++ 只采集事实，不做项目规则决策。这样更换平台、资产类别或项目预算时不需要重新编译插件。

## M1：只读审计 MVP

- Profile、Issue、Evidence、Report v1 JSON Schema；
- Static Mesh LOD 顶点/三角形、材质槽、LOD 数和 Nanite 元数据；
- 五项 Profile 驱动检查；
- Python/C++ collector 边界；
- 合成 fixture 故障集与离线回归报告；
- Editor-only 插件骨架、安装和编译说明。

M1 的证据上限是离线 fixture。只有在选定 UE 项目中成功编译、启动并核对真实资产报告后，才能进入 M2 完成状态。

## M2：真实 Unreal 宿主验证

状态：已在 UE 5.8.1 非生产宿主完成；证据见 `artifacts/host-validation/`。

1. 选择非生产 UE5 测试项目，记录 Engine 精确版本和 commit；
2. 编译 Development Editor 插件并保存构建日志摘要；
3. 用已知 Static Mesh 人工核对五类元数据；
4. 覆盖无 render data、错误 object path、Nanite 不可用和部分失败批次；
5. 验证扫描前后 `.uasset` 哈希/时间戳未改变；
6. 保存脱敏 Report 和宿主验证记录。

## M3：实测性能与产品化

状态：首个 UE 5.8.1 热缓存基线已完成。64 个 Engine Static Mesh 经 2 次预热、7 次重复，
中位数 0.5483 ms、P95 0.5968 ms，64 个文件哈希不变。该数字只作为同机回归基线，
不代表冷启动、生产资产或数千资产性能。

有界分批、进度事件、批次间取消和部分失败汇总也已完成真实宿主验证。当前 MVP 的 M3
范围完成；后续项目化扩展不属于本轮完成声明。

- 根据 Unreal Insights/计时数据决定 Asset Registry 预筛选和按批加载策略；
- 增加进度、取消、部分失败和超时合同；
- 扩展碰撞与 Lightmap UV 检查；
- 只有在独立 ChangeSet、人工审批、撤销/备份和复检合同完成后，才讨论 Nanite 修改能力；
- 不在没有基准数据时声称“数千资产不会冻结编辑器”。

唯一下一切片及证据门槛以 `config/goal-state.json` 为准。

## M4：完整资产台账与结果探索

状态：已完成。中文 Slate 面板提供“资产总览 / 问题明细”、共享搜索、通过/需处理/失败状态、
全部成功资产元数据、直接打开最新报告和报告目录。8 张 v0.4 Slate 自动化图片及哈希保留在
`artifacts/host-validation/m4/`。

## M5：交付就绪规则

状态：进行中。

### M5-S1：碰撞与 Lightmap（已完成）

- Profile / Report v2，同时保留 v1 解析兼容；
- C++ 采集简单碰撞体数量、碰撞复杂度、UV 通道、Lightmap Coordinate Index 与分辨率；
- Python 评估简单碰撞、Lightmap UV 就绪度与最低分辨率，政策全部来自 Profile；
- 中文资产账本与问题证据支持新字段和筛选；
- 41+ 离线回归、UE 5.8.1 BuildPlugin、真实 BasicShapes 采集、SHA-256 只读验证和 8 张 v0.5 Slate 截图。

### M5-S2：命名与目录政策（已完成）

- 定义可组合、可禁用的命名前缀/正则/目录规则；
- 对象名、package path 与规则命中证据进入 Report；
- 仅报告，不自动重命名或移动资产；
- 扩展 Demo 故障素材、中文筛选、真实宿主证据和教程。

完成证据：Profile 可选合同、Python 规则、中文规则标签与说明、旧 v2 兼容测试、真实错误命名/错目录
Demo 资产、三套 UE Report、UE 5.8.1 `UE_5.8.1-v0.6.0-dev1` BuildPlugin、独立隐藏宿主 PID 生命周期
记录和 10 张当前 Slate 截图均已落盘。插件仍然只报告，不提供重命名、移动或保存 API。
