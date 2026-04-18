# IBC-Inter 近期优先任务

> 本文档从 PENDING_TASKS.md 中提取最紧急、最值得近期开展的任务，作为下一阶段的工作指导。
>
> **最后更新**：2026-04-18（Step 4a + BehaviorSpec(return_type_name) 编译期推断已完成；下一重点：Step 4b ibci_ihost/idbg 重构，或 §3.1 显式引入原则严格化）

---

## 一、代码健康（低风险，改动范围极小）

### 1.1 ibci_file 文档描述修正 ✅ 已完成

`ibci_file` 导入 `IbPath`（`core.runtime.path`）并使用 `capabilities.execution_context`，与文档"零内核依赖"的定义不符。

**已修正**：
- `ibcext.py` 非侵入层注释新增"轻量依赖型"例外说明，`ibci_file` 从代表模块列表中单独提出
- `ARCHITECTURE_PRINCIPLES.md` 插件架构表格拆分为三行，新增"非侵入式（轻量依赖）"行
- `ARCH_DETAILS.md` §11.2 和 `PENDING_TASKS.md` §11.2 均标注为已修正

---

## 二、运行时正确性（有明确方向，可独立完成）

### 2.1 llmexcept Loop 上下文完整恢复 [PENDING_TASKS 10.1]

**问题**：`LLMExceptFrame` 保存了 `_loop_stack` 的浅拷贝，但循环迭代器的当前位置未被完整恢复，重试后 `for` 循环会从头开始。

**建议方向**：在 `_save_vars_snapshot()` 中记录循环迭代器的当前索引，在 `restore_snapshot()` 中恢复。

**文件**：`core/runtime/interpreter/llm_except_frame.py`

---

### 2.2 重试诊断日志 ✅ 已完成

**已实现**：在 `visit_IbLLMExceptionalStmt` 重试循环中添加 `self.debugger.trace(CoreModule.INTERPRETER, ...)` 调用：

| 时机 | 级别 | 内容 |
|------|------|------|
| 进入 llmexcept 帧 | DETAIL | target_uid + max_retry |
| 每次循环迭代开始 | DETAIL | 当前尝试编号 `N/M` |
| LLM 结果正常退出 | DETAIL | resolved on attempt N |
| LLM 返回 UNCERTAIN | BASIC | 原始响应前 60 字符预览 |
| 重试次数耗尽 | BASIC | max_retry 和 target_uid |

所有日志通过 `CoreModule.INTERPRETER` 频道输出，只在对应级别启用时可见，生产运行无影响。

---

## 三、设计改进（涉及多文件，可安排在功能稳定后）

### 3.1 显式引入原则严格化 [PENDING_TASKS 9.2]

当前 `discover_all()` 在 Engine 初始化时无条件调用，所有插件元数据被注册到全局 MetadataRegistry，导致符号在未 `import` 前即可见。

**长期目标**：延迟 `discover_all()` 调用到首次 `import` 时；内置模块与插件模块显式分离。

**文件**：`core/engine.py`、`core/compiler/semantic/passes/prelude.py`

---

### 3.2 behavior 类型语义分析硬编码检查替代 [COMPLETED ✅]

`semantic_analyzer.py` 的 `visit_IbFor` 中使用字符串 `"behavior"` 进行直接类型名比较，已改为 `SpecRegistry.is_behavior()` 方法。

**后续完成情况**（同 PR）：`visit_IbCall` 中的 `is_behavior()` 特殊路由整体删除——`BehaviorAxiom` 完成后，behavior 对象通过标准 `hasattr(func, 'call')` 分支自主执行，无需特判。

**文件**：`core/runtime/interpreter/handlers/expr_handler.py`、`core/compiler/semantic/passes/semantic_analyzer.py`

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
