# IBC-Inter 近期优先任务

> 记录接下来可以直接开工的具体任务，按优先级排列。
> 中长期任务见 `docs/PENDING_TASKS.md`，已完成工作见 `docs/COMPLETED.md`。
>
> **最后更新**：2026-04-18（Step 4a + BehaviorSpec 编译期推断 + OOP×Protocol PR-A 均已完成；下一重点：Step 4b ibci_ihost/idbg 重构，或显式引入原则 Phase 1）

---

## 1. llmexcept 循环迭代器状态完整恢复 [P1]

**问题**：`LLMExceptFrame` 保存了 `_loop_stack` 的浅拷贝，但循环迭代器的当前位置（for 循环已迭代到哪一步）未被完整恢复。重试后 for 循环会从头开始，而非从失败点之前的状态继续。

**修复方向**：在 `_save_vars_snapshot()` 中记录循环迭代器的当前索引；在 `restore_snapshot()` 中恢复。

**文件**：`core/runtime/interpreter/llm_except_frame.py`

---

## 2. 显式引入原则 Phase 1：插件 metadata `kind` 字段 [P1]

**任务**：向 `__ibcext_metadata__()` 返回值添加 `"kind"` 字段（`"method_module"` 或 `"type_module"`），使 `Prelude._init_defaults()` 能够区分"真正的内置类型模块"和"插件方法模块"，只将前者加入 `builtin_modules`。

**效果**：`import ai` 前 `ai` 不再是预注入的内置符号，向显式引入原则迈出第一步。

**涉及文件**：
- 所有 `ibci_modules/*/` 的 `_spec.py`（添加 `"kind": "method_module"` 字段）
- `core/compiler/semantic/passes/prelude.py`（根据 kind 过滤 `discover_all()` 结果）

---

## 3. 嵌套 llmexcept 系统性集成测试 [P1]

**任务**：`LLMExceptFrameStack` 已支持多层嵌套帧的压栈/弹栈，但嵌套场景下的作用域隔离和帧交互未经过系统性测试。

**补充的测试用例**：
- 外层 llmexcept + 内层 llmexcept（各自独立重试，互不干扰）
- 外层重试过程中，内层 LLM 调用正常成功的情形
- 内层重试耗尽后，外层是否正确感知

**文件**：`tests/e2e/`（在现有 AI mock 测试中扩充，或新增集成测试文件）

---

*本文档记录近期可执行任务。中长期任务见 `docs/PENDING_TASKS.md`。*
