# IBC-Inter 近期优先任务

> 本文档从 PENDING_TASKS.md 中提取最紧急、最值得近期开展的任务，作为下一阶段的工作指导。
>
> **最后更新**：2026-04-17

---

## 一、代码健康（低风险，改动范围极小）

### 1.1 ibci_file 文档描述修正 [PENDING_TASKS 11.2]

`ibci_file` 被文档归类为"非侵入式"插件，但其 `core.py` 导入了 `core.runtime.path.IbPath`。`IbPath` 是纯数据类（`@dataclass(frozen=True)`），无状态依赖，属可接受的轻量边界导入。

**建议**：在 `ibcext.py` 插件分级注释和 `ARCHITECTURE_PRINCIPLES.md` 中将 `ibci_file` 标注为"轻量依赖"型，并解释 `IbPath` 的可用范围。

---

## 二、运行时正确性（有明确方向，可独立完成）

### 2.1 llmexcept Loop 上下文完整恢复 [PENDING_TASKS 10.1]

**问题**：`LLMExceptFrame` 保存了 `_loop_stack` 的浅拷贝，但循环迭代器的当前位置未被完整恢复，重试后 `for` 循环会从头开始。

**建议方向**：在 `_save_vars_snapshot()` 中记录循环迭代器的当前索引，在 `restore_snapshot()` 中恢复。

**文件**：`core/runtime/interpreter/llm_except_frame.py`

---

### 2.2 重试诊断日志 [PENDING_TASKS 10.4]

每次重试时缺少详细日志（帧状态、重试次数、错误原因），难以调试多次重试场景。

**建议**：在 `visit_IbLLMExceptionalStmt` 的重试循环中，通过 `core_debugger.trace()` 输出帧状态摘要。

**文件**：`core/runtime/interpreter/handlers/stmt_handler.py`

---

## 三、设计改进（涉及多文件，可安排在功能稳定后）

### 3.1 显式引入原则严格化 [PENDING_TASKS 9.2]

当前 `discover_all()` 在 Engine 初始化时无条件调用，所有插件元数据被注册到全局 MetadataRegistry，导致符号在未 `import` 前即可见。

**长期目标**：延迟 `discover_all()` 调用到首次 `import` 时；内置模块与插件模块显式分离。

**文件**：`core/engine.py`、`core/compiler/semantic/passes/prelude.py`

---

### 3.2 behavior 类型语义分析硬编码检查替代 [PENDING_TASKS 11.7]

`semantic_analyzer.py` 的 `visit_IbFor` 中使用字符串 `"behavior"` 进行直接类型名比较，应改为 `SpecRegistry.is_behavior()` 或公理层协议方法。

**文件**：`core/compiler/semantic/passes/semantic_analyzer.py`

---

### 3.3 重试策略配置扩展 [PENDING_TASKS 10.2]

当前只支持固定次数重试（`ai.set_retry(n)`）。后续可支持：
- 指数退避（Exponential Backoff）
- 条件重试（基于错误类型）

**文件**：`ibci_modules/ibci_ai/core.py`、`core/runtime/interpreter/handlers/stmt_handler.py`

---

### 3.4 嵌套 llmexcept 系统性测试 [PENDING_TASKS 10.3]

`LLMExceptFrameStack` 已支持多层嵌套帧的压栈/弹栈，但嵌套场景下的作用域隔离和帧交互未经过系统性测试。建议补充集成测试用例。

---

*本文档记录 IBC-Inter 近期优先任务，供下一阶段开发参考。*
*详细背景和完整任务列表见 PENDING_TASKS.md。*
