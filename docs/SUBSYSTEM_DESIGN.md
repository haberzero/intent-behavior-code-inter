# IBCI 子系统设计手册

> 本手册是 IBCI 各子系统的内部设计文档集合（"子系统如何工作"）。
> 用户侧语法权威见 `docs/SYNTAX_REFERENCE.md`；架构原则见 `docs/ARCHITECTURE.md`。

## 章节索引

| 章 | 文件 | 主题 | 说明 |
|----|------|------|------|
| 01 | [01_intent_system](subsystems/01_intent_system.md) | 意图注释子系统 | AST 节点、IbIntentContext、fork 语义、序列化 |
| 02 | [02_multimodal_behavior](subsystems/02_multimodal_behavior.md) | 全模态行为表达式子系统 | 协议设计、payload 构建、AIPlugin 架构 |
| 03 | [03_callable_fn](subsystems/03_callable_fn.md) | fn / 可调用类型设计 | 无 callable 基类、duck-type + capability 协议 |
| 04 | [04_plugin_system](subsystems/04_plugin_system.md) | 插件与模块系统 | 模块分类、发现路径、插件开发、from import |
| 05 | [05_coroutine](subsystems/05_coroutine.md) | 协程层设计（SHELVED） | L3 异步层、搁置条件、恢复条件 |

## 搁置项

- **协程层（L3）**：见 [05_coroutine](subsystems/05_coroutine.md)，当前 SHELVED，恢复条件见文件内说明。
