# 变量存储模型

> 本文档是存储模型的架构层摘要。完整的子系统设计（协议族实现、类型继承、Backing 模型、file 模块 API）见 `docs/subsystems/02_file_container.md`。

---

## 两轴正交模型

变量的存储行为由 `IbSpec.storage_model` 字段决定：

| StorageModel | 语义 | 快照行为 | 序列化行为 |
|---|---|---|---|
| `MEMORY_BACKED`（默认） | 值在内存中完整持有 | 深克隆（递归复制字节） | 值序列化 |
| `DISK_BACKED` | 值以路径引用持有，字节在磁盘 | 浅克隆（`__clone_ref__`，仅复制路径） | 路径描述符序列化 |

## 协议驱动分发（核心原则）

存储模型的分发通过协议方法完成，禁止在调用方做 `if storage_model == ...` 判断：

| 调用方 | 分发入口 | 协议方法 |
|---|---|---|
| `deep_clone` | `receive("__clone_ref__")` | 磁盘型返回路径引用拷贝，内存型深拷贝 |
| 序列化器 | `receive("__to_descriptor__")` | 输出路径引用描述符 |
| 反序列化器 | `receive("__from_descriptor__")` | 从描述符重建 handle |

新增磁盘型类型不需要改动 executor / strategy / deep_clone / 序列化器。

## 当前磁盘型类型

`file_handle` / `audio` / `image` / `video`。继承体系与协议族实现见 `docs/subsystems/02_file_container.md`。

## `is_disk_backed` 辅助属性

`IbSpec` 提供 `is_disk_backed` 只读 property（`storage_model == StorageModel.DISK_BACKED`），仅用于诊断/断言。分发路径不得改读此 property 做 if/else。
