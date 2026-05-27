# Phase 1 技术决策记录

> 2026-05-27 | 命名模型路由（`@NAME~` 语法）实现

---

## 已识别风险与决策

### R1: `ILLMProvider` 接口兼容性

**风险**：`_call_llm` 调用 `self.llm_callback(sys_prompt, user_prompt)` — 新增 `target_model` 关键字参数是否破坏接口契约？

**分析**：
- `llm_callback` 实际指向 `AIPlugin.__call__`，通过 capability registry 获取
- Python 的关键字参数 (`target_model=""`) 不破坏现有调用者（旧代码不传该参数则使用默认值）
- `ILLMProvider` 在 `core/base/interfaces.py` 中是 Protocol 类型，未强制定义 `__call__` 签名

**决策**：采用 keyword-only 参数 `*, target_model: str = ""`，完全后向兼容。

---

### R2: 测试模式下 MOCK 拦截路由

**风险**：在 `IBC_TEST_MODE` / `url == "TESTONLY"` 时，`_handle_mock_response` 在路由逻辑之前执行。这意味着：
- 未注册的命名模型在 MOCK 模式下不会报错
- 无法在 MOCK 模式下测试路由错误场景

**分析**：
- 这是 IBCI 测试体系的固有设计：MOCK 模式拦截所有 LLM 调用
- 真实路由错误（如未注册模型）只在真实 LLM 模式下触发
- 当前测试体系无法覆盖此场景

**决策**：接受此限制，记录为已知限制。如果将来需要测试路由错误，可在 MOCK 拦截后增加一个可选的路由验证步骤。但当前不增加复杂度。

---

### R3: Tag 大小写策略

**风险**：用户写 `@gpt4o~`、`@GPT4o~`、`@GPT4O~` 应该路由到同一模型还是不同模型？

**分析**：
- tag 是用户自定义的标识符，属于用户控制的命名空间
- 隐式大小写转换属于不可见的行为变换，违反"所见即所得"原则
- 精确匹配让用户对自己定义的标识符拥有完全控制权

**决策**：大小写敏感精确匹配。`@GPT4o~` 仅路由到 `register_model("GPT4o", ...)` 注册的模型，用户必须保证使用时的 tag 与注册时完全一致。

---

### R4: `dispatch_eager` 路径的 `target_model` 传递

**风险**：`dispatch_eager` 在后台线程中调用 `execute_behavior_expression`，`target_model` 是否能正确传递？

**分析**：
- `dispatch_eager` 不接受 `target_model` 参数
- 但 `execute_behavior_expression` 内部有 fallback 逻辑：`if not target_model: target_model = node_data.get("tag", "")`
- `node_data` 通过 `execution_context.get_node_data(node_uid)` 获取，在后台线程中仍然可访问

**决策**：不修改 `dispatch_eager` 签名。依赖 `execute_behavior_expression` 内部的 node_data fallback 机制。这样既保持 API 简洁，又确保所有路径都能正确获取 tag。

---

### R5: 命名模型的能力探测

**风险**：当前 `probe_model()` 只对默认模型生效。命名模型使用时可能需要不同的推理策略。

**分析**：
- Phase 1 不涉及推理策略差异化
- 命名模型在真实 LLM 模式下使用默认的保守推理策略（`is_reasoning_model = True`）
- 后续 Phase 可增加 per-model capability probing

**决策**：Phase 1 不实现命名模型探测。所有命名模型统一使用保守推理策略。在文档中标记为"尚未实现"。

---

## 代码改动概要

| 文件 | 改动类型 | 行数 |
|------|---------|------|
| `core/runtime/vm/handlers.py` | 提取 tag 并传递 | +3 行 |
| `core/runtime/interpreter/llm_executor.py` | 添加 `target_model` 参数到 3 个方法 + `_call_llm` | +15 行 |
| `ibci_modules/ibci_ai/core.py` | 模型注册表 + 路由逻辑 + `register_model()` + `_get_named_client()` | +75 行 |
| `ibci_modules/ibci_ai/_spec.py` | vtable 注册 | +1 行 |
| `tests/e2e/test_e2e_model_routing.py` | 新增 6 项 e2e 测试 | +85 行（新文件）|

**总计**：~180 行新增/修改，0 行删除，0 回归。
