# IBC-Inter 架构设计手册

> 本手册是 IBC-Inter 的架构权威参考，覆盖设计理念、编译期数据模型、类型系统、VM/解释器、路径系统、内核原生模块、存储模型。
> 语法参考见 `docs/SYNTAX_REFERENCE.md`；子系统设计见 `docs/SUBSYSTEM_DESIGN.md`；已知限制见 `docs/KNOWN_LIMITS.md`。

## 章节索引

| 章 | 文件 | 主题 | 关键查找项 |
|----|------|------|-----------|
| 01 | [01_principles](architecture/01_principles.md) | 架构原则与设计理念 | 层级架构、依赖规则、核心原则、命名前缀 |
| 02 | [02_metadata_ast](architecture/02_metadata_ast.md) | 元数据：AST/侧表/序列化 | 新增 AST 字段前必查、MetadataStore 边界、UID 策略 |
| 03 | [03_type_system](architecture/03_type_system.md) | 类型系统设计 | TypeRef/IbSpec/TypeAxiom、fn/lambda 语义 |
| 04 | [04_vm_interpreter](architecture/04_vm_interpreter.md) | VM 与解释器架构 | CPS 调度、llmexcept、LLM 流水线、执行帧 |
| 05 | [05_vm_specification](architecture/05_vm_specification.md) | VM 公理化规范 | 执行模型公理、内存模型公理、合规测试 |
| 06 | [06_path_system](architecture/06_path_system.md) | 路径系统架构 | 三层路径、五概念模型、沙箱隔离 |
| 07 | [07_kernel_native_modules](architecture/07_kernel_native_modules.md) | 内核原生模块与插件边界 | import-gating、provenance/visibility、单一 setup 初始化 |
| 08 | [08_storage_model](architecture/08_storage_model.md) | 变量存储模型 | 磁盘型协议族、IbFileHandle、协议驱动分发 |
| 附录 | [appendix](architecture/appendix_type_system_rationale.md) | 类型系统设计原文（历史） | 设计动机追溯，非当前实现参考 |

## 阅读路径

| 读者 | 推荐阅读顺序 |
|------|------------|
| 新加入的开发者 | 01 -> 02 -> 03 -> 04 |
| 要改类型系统的人 | 03 -> 02 -> 附录 |
| 要改 VM/解释器的人 | 04 -> 05 -> 02 |
| 要改路径/模块系统的人 | 06 -> 07 -> 08 |
| 要做架构决策的人 | 01 -> 相关章节 -> `tasks_docs/` |
