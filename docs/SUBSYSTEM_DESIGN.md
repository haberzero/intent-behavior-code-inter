# IBCI 子系统设计手册

> 本手册是 IBCI 各子系统的内部设计文档集合（"子系统如何工作"）。
> 用户侧语法权威见 `docs/SYNTAX_REFERENCE.md`；架构原则见 `docs/ARCHITECTURE.md`。

## 章节索引

| 章 | 文件 | 主题 | 说明 |
|----|------|------|------|
| 01 | [01_intent_system](subsystems/01_intent_system.md) | 意图注释子系统 | AST 节点、IbIntentContext、fork 语义、序列化 |
| 02 | [02_file_container](subsystems/02_file_container.md) | 文件容器与磁盘型存储 | 协议族、Backing 模型、类型继承、file 模块、LLM 交互 |
| 03 | [03_callable_fn](subsystems/03_callable_fn.md) | fn / 可调用类型设计 | 无 callable 基类、duck-type + capability 协议 |
| 04 | [04_plugin_system](subsystems/04_plugin_system.md) | 内置模块系统与宿主绑定 | 模块分类、构造期注册、宿主绑定扩展、from import |
| 05 | [05_coroutine](subsystems/05_coroutine.md) | 协程层设计 | 并发架构、调度器多任务化、await/generator 执行模型说明 |

