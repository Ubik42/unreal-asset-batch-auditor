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

## M1：只读审计 MVP（本轮）

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
