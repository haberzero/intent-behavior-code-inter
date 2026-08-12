# TEST_MATRIX_FINDINGS — 测试覆盖矩阵核对发现（PT-TEST-3/R4 研究存档）

> 2026-08-06 对 `tests_docs/SEMANTIC_COVERAGE_MATRIX.md` 的测试名/文件引用核对结果。
> **处置**：矩阵彻底完善推迟至 PT-TEST-1（测试体系重构）；本文件为未来重构输入存档，不作为独立任务执行。

## 一、核对范围与方法

- 范围：矩阵全部 124 个唯一测试函数名 + 9 个测试文件名（"测试位置"列与备注）。
- 方法：`grep "def <name>\b"` 全词匹配 + 语义级映射（按 INV 契约语义匹配当前测试）。
- 结论：矩阵"测试位置"列**大面积过期**——契约测试经历过改名/重组，多数旧名在代码中 0 命中。

## 二、文件名级发现

| 文件 | 状态 |
|------|------|
| `test_e2e_control_flow.py` | 已删除（矩阵 §9.1/§10 已自标注） |
| `test_e2e_tuple_unpack.py` | 已删除（矩阵 §1.4 已自标注） |
| `test_execution_isolation.py` | 位置应为 `tests/compliance/`（矩阵未标注目录） |
| `test_concurrent_llm.py` | 位置应为 `tests/compliance/` |

## 三、函数名映射摘要（旧名 → 当前名）

> 完整逐条映射在 subagent 结果中；以下为结构性摘要。关键：**矩阵旧名几乎全部改名**。

- **§1 类型系统**：INV-OPT-2→`test_optional_accepts_value_of_T`（test_type_invariants.py）；INV-OPT-3 语义等价→编译器侧 `test_plain_int_rejects_none`/`test_optional_int_accepts_none`；INV-OPT-4→`tests/runtime/test_optional_runtime.py`（or_else/unwrap/is_some）；INV-GEN-3 嵌套泛型→`tests/compiler/test_generics.py`（TestG3NestedGenerics）；INV-TUPLE-1/2/3→`test_tuple_positional_access_type`/`test_tuple_different_types`/`test_tuple_unpacking_preserves_types`；INV-CAST-1→`test_cast_valid_conversions`；INV-CAST-2 无专门隐式转换测试。
- **§3 作用域/闭包**：INV-CELL-1/2→`test_cell_captures_reference`/`test_multiple_closures_share_cell`（test_scope_semantics.py）；INV-LAMBDA-1/2/3→`test_lambda_captures_by_reference`/`test_lambda_in_loop_shares_variable`/`test_lambda_body_mutation_persists`；INV-SNAPSHOT-1/2/3→`test_snapshot_captures_value_not_reference`/`test_snapshot_deep_clones_mutable_objects`/`test_snapshot_each_call_independent`；INV-SCOPE-1/2→`test_nested_function_accesses_parent_scope`/`test_function_creates_new_scope`。
- **§4 Intent**：INV-INTENT-PROP-1→`test_smear_intent_cleared_after_use`；PROP-2→`test_at_plus_persists_after_llm_call`；PROP-3→`test_remove_clears_intents`；PRIORITY-1→`test_override_replaces_existing`；RETRY-2→`test_persist_intent_survives_retry`；SCOPE-1→`test_function_intent_isolated`；SCOPE-2→e2e `test_lambda_behavior_uses_call_time_intents`；FLOW-1→`test_intent_in_loop_iteration`（矩阵误写 `test_intent_in_loop`）。
- **§5 LLM 集成**：INV-MOCK-1/2→`test_mock_typed_returns`；INV-BEHAVIOR-1/2/3→`test_behavior_expression_executes`/`test_behavior_in_assignment`/`test_behavior_in_expression`；INV-LLMFN-1/2→`test_llm_function_definition_and_call`/`test_llm_function_parameter_binding`；INV-INTENT-LLM-1→`test_intent_affects_llm_call`；INV-DISPATCH-1→`test_sequential_llm_calls_execute_in_order`。
- **§6 llmexcept**：CATCH-2→`test_retry_executes_on_error`；CATCH-3→`test_nested_llmexcept_independent`；HISTORY-1→`test_error_history_accumulates`；DEPTH-1/2→`test_reasonable_depth_succeeds`/`test_exhausted_retries_raises`；UNCERTAIN-1→`test_uncertain_value_isolated`；FLOW-3/4→`test_llmexcept_with_break`/`test_llmexcept_with_return`；SCOPE-1→`test_outer_variable_accessible_in_retry`。
- **§9/§11**：旧名与当前真名一致（集合/异常契约测试命名稳定）。

## 四、TRUE_GAP（确认真缺失的语义测试）

> 这些是**语义覆盖缺口**，不因改名而消失，属 PT-TEST-1 重构时需补充的项：

| 契约 | 语义 | 说明 |
|------|------|------|
| INV-INTENT-PRIORITY-2 | smear 排在 stack 之后 | 无优先级次序断言测试 |
| INV-INTENT-SCOPE-3 | snapshot 捕获定义时 intent | 无测试 |
| INV-MOCK-3 | MOCK:INVALID 触发错误 | 样例仅在孤儿 fixture `tests/fixtures/llm_samples.py`（无测试消费者） |
| INV-LLMEXCEPT-CATCH-4 | llmexcept 不捕获普通异常 | 无活测试 |
| INV-CAST-2 | 隐式类型转换规则 | 无专门测试，占位为 cast 往返保值 |

## 五、契约漂移 / 需人工裁决

| 项 | 问题 |
|----|------|
| INV-LLMEXCEPT-UNCERTAIN-2 | 当前测试 `test_str_plus_uncertain_concatenates` 断言 str+uncertain **可**拼接，与矩阵"禁止"矛盾；编译器层无 uncertain 测试。语义已反转或契约废弃，需裁决 |
| INV-BEHAVIOR-4 | 占位 `test_behavior_in_control_flow` 语义不匹配（实为控制流），真实错误处理只在 e2e |
| INV-INTENT-FLOW-3 | return 清除 smear 无专用测试，最接近 `test_smear_intent_cleared_after_use` |

## 六、矩阵标注过时项

- §2.5 "普通异常传播 ❌缺失" 已过时——现被 `tests/contracts/test_exception_semantics.py` 全面覆盖。
- §9.3 "str+uncertain 禁止" 声称由编译器测试覆盖，实际编译器目录无 uncertain 测试命中。
