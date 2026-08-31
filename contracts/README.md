# JSON 合同

所有线上数据结构使用 JSON Schema Draft 2020-12。Profile 是项目拥有的输入，Report、Issue 与
Evidence 是确定性的审计输出；破坏性变更必须新增 schema 文件、`$id` 和解析分支，不能静默改写旧格式。

## Static Mesh v1、v2 与 v3

- `profile.v1` / `report.v1`：三角形、顶点、材质槽、LOD、Nanite；
- `profile.v2` / `report.v2`：在 v1 基础上增加简单碰撞体数量、碰撞复杂度、UV 通道数、Lightmap
  Coordinate Index 与 Lightmap 分辨率；
- Python 仍能读取 v1 Profile，并为没有扩展元数据的旧调用生成 v1 Report；
- v2 Report 要求每个成功资产都包含完整的碰撞与 Lightmap 字段，避免出现“半升级”报告；
- v2 Profile 可选加入 `object_name` 与 `package_path`。前者配置允许前缀和完整正则，后者配置
  允许根目录与禁用目录段；旧 v2 Profile 缺少这两段时仍按原语义读取；
- Issue、Evidence 和 collection failure 的字段形状没有改变，因此 v2 Report 继续复用 v1 子合同。
- `profile.v3` / `report.v3`：增加有效材质路径、缺失材质槽、唯一材质数、材质接口报告的纹理路径、
  纹理依赖数和最大纹理边长。四条新政策分别可禁用，不能用材质槽数量代替依赖事实；
- v3 Report 要求所有成功资产同时具备完整 v2 与 v3 元数据。v1/v2 Profile 和没有依赖字段的旧
collector 继续生成对应旧版 Report，不会被静默升级。

## Texture2D v1

`texture-profile.v1` / `texture-report.v1` 是与 Static Mesh v1/v2/v3 并列的独立合同，不把纹理字段
塞入已有模型报告。Profile 可配置源尺寸、2 次幂、Mip 数、Texture Group、Compression/sRGB 组合、
Virtual Texture 与 Streaming 政策；成功资产保存源/平台尺寸、Mip 与对应 Editor 设置。

纹理 Report 固定写入 `asset_type=texture2d`、真实宿主标识和批次计数，并继续复用稳定的 Issue、
Evidence 与 collection failure 子合同。平台尺寸和 Mip 来自当前 Unreal Editor 平台数据；它们不等于
最终 Cook 体积、运行时驻留、显存、采样成本或 GPU 性能。

每条 Evidence 都记录观测值、期望值和提供阈值的 Profile JSON Pointer。`assets` 保存全部成功资产的
元数据，所以通过项也能在 Editor 中逐项复核。执行计数覆盖请求、处理、取消、完成批次及实际批大小，
解析器会检查计数自洽。

`benchmark.v1` 专门记录真实宿主计时来源与只读完整性，不是离线 fixture 合同；其限制说明不可省略。

## 会话历史与比较

`unreal-audit-session-index@1.0.0` 是项目 `Saved` 目录中的轻量索引，不是数据库。历史 Report 采用
独占创建和 SHA-256 校验，已存在且内容不同的文件会被拒绝覆盖；索引可原子替换，但索引损坏不会删除
历史文件。`unreal-audit-comparison@1.0.0` 以稳定的 `asset_path + rule_id` 比较两份 Report，分别输出
新增、持续、已解决 Issue，以及新增、持续、已解决采集失败。

## 面板任务与团队交接

`unreal-audit-task-state@1.0.0` 记录原生面板的 pending、running、cancelling、completed、cancelled、
failed 状态、对象/批次计数和最终产物路径。状态文件采用原子替换，取消只在批次之间生效。

`unreal-audit-handoff@1.0.0` 是 HTML/CSV 交接目录的清单，固定记录源 Report、Profile、宿主、验证边界、
统计摘要和文件 SHA-256。导出器只消费已有 Report，不重新采集或修改资产。

`unreal-audit-review-ledger@1.0.0` 是人工审阅 sidecar，以 Report SHA-256、Issue ID 和 Evidence ID
绑定“需修复 / 批准例外”、负责人和备注。缺少记录表示未复核。它不改写 Report；同名报告内容变化时
旧决定进入孤儿记录，损坏 JSON 会被重命名隔离。

`unreal-audit-delivery-groups@1.0.0` 是当前 Report 的只读目录聚合视图。它把成功资产和采集失败按
package path 的前三段业务目录稳定分组，记录对象、通过、需处理、问题密度、采集失败与审阅计数。
排序规则固定为“采集失败 > 需修复 > 问题密度 > 问题数 > 目录路径”；异常路径进入明确的未归档组，
不会触发 Asset Registry 扫描，也不推断运行时性能。

## 项目预设与无人值守摘要

`unreal-asset-audit-preset@1.0.0` 把 Profile、显式 asset/folder 范围、批大小、阻断严重度和输出位置绑定为
可评审项目配置。范围不能为空，不支持通配或隐式全项目扫描。

`unreal-asset-audit-run@1.0.0` 是无人值守包装层的轻量结果，固定映射 0/10/20/30/40 五类退出语义，
并指向完整 Report。它不复制 Issue/Evidence，也不能代替正式审计报告。

## 发布清单

`unreal-audit-release@1.0.0` 描述可安装 ZIP 的插件版本、测试宿主、二进制兼容标识、源修订、payload
逐文件 SHA-256 和整体 tree hash，并显式记录 Marketplace、跨版本兼容和 Engine 派生素材声明。
