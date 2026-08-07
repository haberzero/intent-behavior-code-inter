# IBCI 子系统设计手册

> 本手册是 IBCI 各子系统的内部设计文档集合（"子系统如何工作"）。
> 用户侧语法权威见 `docs/SYNTAX_REFERENCE.md`；架构原则见 `docs/ARCHITECTURE.md`。

## 章节索引

| 章 | 文件 | 主题 | 说明 |
|----|------|------|------|
| 01 | [01_intent_system](subsystems/01_intent_system.md) | 意图注释子系统 | AST 节点、IbIntentContext、fork 语义、序列化 |
| 02 | [02_file_container](subsystems/02_file_container.md) | 文件容器与磁盘型存储 | 协议族、Backing 模型、类型继承、file 模块、LLM 交互 |
| 03 | [03_callable_fn](subsystems/03_callable_fn.md) | fn / 可调用类型设计 | 无 callable 基类、duck-type + capability 协议 |
| 04 | [04_plugin_system](subsystems/04_plugin_system.md) | 插件与模块系统 | 模块分类、发现路径、插件开发、from import |
| 05 | [05_coroutine](subsystems/05_coroutine.md) | 协程层设计 | 并发架构定案、调度器多任务化、await/generator 演进规划 |

## 搁置项

- **协程层（L3）**：见 [05_coroutine](subsystems/05_coroutine.md)。调度器多任务化与 `await` 已落地；语言级生成器（`yield`）列为阶段 5 实现项（无 async 函数关键字，任意函数可 await）。
