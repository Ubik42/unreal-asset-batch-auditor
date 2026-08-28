# JSON 合同

所有线上数据结构使用 JSON Schema Draft 2020-12。Profile 是项目拥有的输入，Report、Issue 与
Evidence 是确定性的审计输出；破坏性变更必须新增 schema 文件、`$id` 和解析分支，不能静默改写旧格式。

## v1 与 v2

- `profile.v1` / `report.v1`：三角形、顶点、材质槽、LOD、Nanite；
- `profile.v2` / `report.v2`：在 v1 基础上增加简单碰撞体数量、碰撞复杂度、UV 通道数、Lightmap
  Coordinate Index 与 Lightmap 分辨率；
- Python 仍能读取 v1 Profile，并为没有扩展元数据的旧调用生成 v1 Report；
- v2 Report 要求每个成功资产都包含完整的碰撞与 Lightmap 字段，避免出现“半升级”报告；
- Issue、Evidence 和 collection failure 的字段形状没有改变，因此 v2 Report 继续复用 v1 子合同。

每条 Evidence 都记录观测值、期望值和提供阈值的 Profile JSON Pointer。`assets` 保存全部成功资产的
元数据，所以通过项也能在 Editor 中逐项复核。执行计数覆盖请求、处理、取消、完成批次及实际批大小，
解析器会检查计数自洽。

`benchmark.v1` 专门记录真实宿主计时来源与只读完整性，不是离线 fixture 合同；其限制说明不可省略。
