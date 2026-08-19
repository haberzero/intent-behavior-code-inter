# tests 覆盖矩阵（三段式引用：`file::class::method`）

> 单一权威：覆盖测试列全部为**机器可校验的三段式引用**（相对 `tests/` 根，如
> `tests/contracts/test_scope_semantics.py::TestCellSharedReferences::test_cell_captures_reference`）。
> 机器校验：`tests/meta/test_matrix_sync.py` 解析矩阵内反引号三段式引用，与
> `pytest --collect-only` 的 nodeid 集合对账——**引用不存在即失败**。
> 数字纪律：不冻结测试通过数字，以当次 `python -m pytest tests/` 实跑为准。
>
> 结构沿用 `tests_docs/SEMANTIC_COVERAGE_MATRIX.md` 的 13 个语义域与 INV-* 编号；
> 旧矩阵"测试位置"列的虚构/过时测试名已替换为真实测试引用；找不到语义吻合测试的行标
> `🔶 缺失`（不硬凑）。迁移依据与核对发现存档见 git 历史（原 tasks_docs/TEST_MATRIX_FINDINGS.md 已随文档清理删除）。

## §1 类型系统语义 (Type System Semantics)

### 1.1 基础类型保证

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| — | int 算术运算正确性 | `tests/compiler/test_pipeline.py::TestCompileExpressions::test_arithmetic` | 编译级；基础运算由 Python 保证 |
| — | str 字符串操作 | `tests/contracts/test_collection_semantics.py::TestStringOperationInvariants::test_str_concatenation_type` | 代表项；完整 str 不变量见 §9.3 INV-STR-* |
| — | float 精度保证 | `tests/e2e/test_for_filter_compound.py::TestCompoundAssignment::test_div_assign_float` | ⚠️ 无专门 float 精度契约，用除法 e2e 近似 |
| — | bool 逻辑运算 | `tests/compiler/test_pipeline.py::TestCompileExpressions::test_logical_ops` | 编译级；运行期 bool 语境见 e2e TestE2EBoolContextTyping |

### 1.2 Optional[T] 语义

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| INV-OPT-1 | None 访问时运行时错误 | `tests/contracts/test_type_invariants.py::TestOptionalNullSafety::test_optional_none_access_raises` | 现契约演化为编译期 or_else 兜底 |
| INV-OPT-2 | Optional 赋值兼容性 | `tests/contracts/test_type_invariants.py::TestOptionalNullSafety::test_optional_accepts_value_of_T[int-42]` | 参数化覆盖 int/str/list[T] |
| INV-OPT-3 | Optional 类型检查 | `tests/contracts/test_type_invariants.py::TestOptionalNullSafety::test_optional_is_some_compile_contract` | is_some/unwrap 编译期签名；编译器侧另有 `test_plain_int_rejects_none` |
| INV-OPT-4 | Optional 链式操作 | `tests/runtime/test_optional_runtime.py::TestOptionalOrElse::test_or_else[or_else_empty_returns_default]` | 运行期方法（or_else/unwrap/is_some）见 runtime/test_optional_runtime.py |

### 1.3 泛型类型语义

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| INV-GEN-1 | list[T] 元素类型约束 | `tests/contracts/test_type_invariants.py::TestGenericTypeInvariants::test_list_homogeneous_type[int-[1, 2, 3]]` | 参数化覆盖 int/str/list[int] |
| INV-GEN-2 | dict[K,V] 键值类型约束 | `tests/contracts/test_type_invariants.py::TestGenericTypeInvariants::test_dict_key_value_types[int-str-{1: 'a', 2: 'b'}]` | |
| INV-GEN-3 | 嵌套泛型类型 | `tests/e2e/test_generics_runtime.py::TestNestedGenerics::test_nested_list_e2e` | e2e 层嵌套 list 运行正确 |
| — | 泛型类型推断 | `tests/contracts/test_type_invariants.py::TestTypeInferenceInvariants::test_auto_infers_literal_type[42-42]` | 见 §1.5 INV-INFER-* |

### 1.4 Tuple 类型语义

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| INV-TUPLE-1 | tuple[T1,T2] 位置类型 | `tests/contracts/test_type_invariants.py::TestTuplePositionalTypes::test_tuple_positional_access_type`；`tests/contracts/test_type_invariants.py::TestTuplePositionalTypes::test_tuple_different_types` | 原 INV-TUPLE-1,2 合一 |
| INV-TUPLE-3 | tuple 下标类型推断 | `tests/e2e/test_type_annotations_runtime.py::TestTuplePositionalTypeInference::test_int_str_literal_index` | 字面量下标推断；变量下标见 TestTuplePositionalFallback |
| — | tuple 解包类型检查 | `tests/contracts/test_type_invariants.py::TestTuplePositionalTypes::test_tuple_unpacking_preserves_types` | 旧矩阵标注文件已删，现已有契约测试 |

### 1.5 类型转换语义

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| INV-CAST-1 | 显式 cast 安全性 | `tests/contracts/test_type_invariants.py::TestTypeCastInvariants::test_cast_valid_conversions[42-str-42]` | 参数化覆盖 int→str/str→int/float→int |
| INV-CAST-2 | 隐式类型转换规则 | 🔶 缺失 | TRUE_GAP：无隐式转换专门测试（历史核对存档见 git） |
| INV-INFER-1 | 类型推断规则（字面量） | `tests/contracts/test_type_invariants.py::TestTypeInferenceInvariants::test_auto_infers_literal_type[42-42]` | |
| INV-INFER-2 | 类型推断规则（函数返回） | `tests/contracts/test_type_invariants.py::TestTypeInferenceInvariants::test_function_return_type_inference` | |

---

## §2 执行模型语义 (Execution Model Semantics)

### 2.1 CPS 执行模型

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| INV-CPS-1 | 深递归无 Python 栈溢出 | `tests/contracts/test_execution_model.py::TestCPSExecutionModel::test_deep_recursion_no_python_overflow` | |
| INV-CPS-2 | 深调用链通过 trampoline | `tests/contracts/test_execution_model.py::TestCPSExecutionModel::test_deep_call_chain_succeeds` | |
| INV-CPS-3 | 相互递归支持 | `tests/contracts/test_execution_model.py::TestCPSExecutionModel::test_mutual_recursion_supported` | |

### 2.2 控制流信号传播

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| INV-SIGNAL-1 | return 立即退出函数 | `tests/contracts/test_execution_model.py::TestSignalPropagation::test_return_signal_exits_function` | |
| INV-SIGNAL-2 | break 退出循环 | `tests/contracts/test_execution_model.py::TestSignalPropagation::test_break_signal_exits_loop` | |
| INV-SIGNAL-3 | continue 跳过迭代 | `tests/contracts/test_execution_model.py::TestSignalPropagation::test_continue_signal_skips_iteration` | |
| INV-SIGNAL-4 | 嵌套循环 break 只退出内层 | `tests/contracts/test_execution_model.py::TestSignalPropagation::test_nested_loop_break_only_inner` | |
| INV-SIGNAL-5 | 深层嵌套中的 return | `tests/contracts/test_execution_model.py::TestSignalPropagation::test_return_from_nested_context` | |

### 2.3 帧栈管理

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| INV-FRAME-1 | 函数调用创建隔离帧 | `tests/contracts/test_execution_model.py::TestFrameStackManagement::test_function_call_creates_new_frame` | |
| INV-FRAME-2 | return 时帧弹出 | `tests/contracts/test_execution_model.py::TestFrameStackManagement::test_frame_pops_on_return` | |
| INV-FRAME-3 | 嵌套调用维护帧链 | `tests/contracts/test_execution_model.py::TestFrameStackManagement::test_nested_calls_maintain_frame_chain` | |
| INV-FRAME-4 | 帧局部变量隔离 | `tests/contracts/test_execution_model.py::TestFrameStackManagement::test_frame_local_variables_isolated` | |

### 2.4 递归深度保证

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| INV-RECURSION-1 | 合理递归深度成功 | `tests/contracts/test_execution_model.py::TestRecursionGuarantees::test_reasonable_recursion_depth` | |
| INV-RECURSION-2 | 尾调用式递归支持 | `tests/contracts/test_execution_model.py::TestRecursionGuarantees::test_tail_call_like_recursion` | |

### 2.5 异常回退

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| INV-UNWIND-1 | LLM 错误回退到 llmexcept | `tests/contracts/test_execution_model.py::TestExceptionUnwinding::test_error_unwinds_to_llmexcept` | |
| INV-UNWIND-2 | 错误通过调用栈传播 | `tests/contracts/test_execution_model.py::TestExceptionUnwinding::test_error_propagates_through_calls` | |
| — | 普通异常传播 | `tests/contracts/test_exception_semantics.py::TestExceptionPropagation::test_exception_propagates_through_function` | 旧标 ❌ 已过时，见 §11 全面覆盖 |

---

## §3 作用域与闭包语义 (Scope & Closure Semantics)

### 3.1 IbCell 共享引用

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| INV-CELL-1 | Cell 变量共享可见 | `tests/contracts/test_scope_semantics.py::TestCellSharedReferences::test_cell_captures_reference` | 另覆盖模块级变量函数内可见 |
| INV-CELL-2 | Cell 修改对所有引用可见 | `tests/contracts/test_scope_semantics.py::TestCellSharedReferences::test_multiple_closures_share_cell` | |

### 3.2 Lambda 引用捕获

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| INV-LAMBDA-1 | lambda 捕获外层变量 | `tests/contracts/test_scope_semantics.py::TestLambdaCapture::test_lambda_captures_by_reference` | |
| INV-LAMBDA-2 | lambda 看到外层变量修改 | `tests/e2e/test_higher_order.py::TestLambdaReferenceSemantics::test_lambda_sees_outer_mutation` | |
| INV-LAMBDA-3 | lambda 修改外层变量 | `tests/e2e/test_higher_order.py::TestLambdaReferenceSemantics::test_lambda_body_mutation_persists` | |

### 3.3 Snapshot 值捕获

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| INV-SNAPSHOT-1 | snapshot 定义时捕获值 | `tests/contracts/test_scope_semantics.py::TestSnapshotSemantics::test_snapshot_captures_value_not_reference` | |
| INV-SNAPSHOT-2 | snapshot 深克隆不受外层修改影响 | `tests/contracts/test_scope_semantics.py::TestSnapshotSemantics::test_snapshot_deep_clones_mutable_objects` | |
| INV-SNAPSHOT-3 | snapshot 每次调用独立求值 | `tests/contracts/test_scope_semantics.py::TestSnapshotSemantics::test_snapshot_each_call_independent` | |

### 3.4 词法作用域规则

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| INV-SCOPE-1 | 内层可访问外层变量 | `tests/contracts/test_scope_semantics.py::TestLexicalScoping::test_nested_function_accesses_parent_scope` | |
| INV-SCOPE-2 | 内层变量遮蔽外层 | `tests/contracts/test_scope_semantics.py::TestLexicalScoping::test_function_creates_new_scope` | |
| INV-SCOPE-3 | 函数作用域隔离 | `tests/contracts/test_scope_semantics.py::TestLexicalScoping::test_function_creates_new_scope` | 与 INV-SCOPE-2 共用（同一测试同时断言隔离与遮蔽） |
| INV-SCOPE-4 | 全局变量可见性 | `tests/contracts/test_scope_semantics.py::TestCellSharedReferences::test_cell_captures_reference` | 模块级变量在函数内可见；新套件编号漂移为循环变量测试 |

### 3.5 闭包上下文传播

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| INV-CONTEXT-1 | 闭包捕获父帧变量 | `tests/contracts/test_execution_model.py::TestFrameContextPropagation::test_closure_captures_parent_frame` | |
| INV-CONTEXT-2 | 多个闭包独立帧 | `tests/contracts/test_execution_model.py::TestFrameContextPropagation::test_multiple_closures_independent_frames` | |
| INV-CONTEXT-3 | 嵌套闭包访问链 | `tests/contracts/test_execution_model.py::TestFrameContextPropagation::test_nested_closure_access_chain` | |

---

## §4 Intent 系统语义 (Intent System Semantics)

### 4.1 Intent 传播机制

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| INV-INTENT-PROP-1 | @ smear intent 一次性 | `tests/contracts/test_intent_propagation.py::TestIntentScopeIsolation::test_smear_intent_cleared_after_use` | |
| INV-INTENT-PROP-2 | @+ stack intent 持久化 | `tests/e2e/test_intent.py::TestE2EIntents::test_at_plus_persists_after_llm_call` | |
| INV-INTENT-PROP-3 | @- remove intent 移除 | `tests/contracts/test_intent_propagation.py::TestIntentPriority::test_remove_clears_intents` | |

### 4.2 Intent 优先级

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| INV-INTENT-PRIORITY-1 | @! override 清空栈 | `tests/contracts/test_intent_propagation.py::TestIntentPriority::test_override_replaces_existing` | |
| INV-INTENT-PRIORITY-2 | smear 排在 stack 之后 | 🔶 缺失 | TRUE_GAP：无优先级次序断言测试 |
| INV-INTENT-PRIORITY-3 | 多层 stack 按顺序 | `tests/e2e/test_intent.py::TestE2EIntents::test_incremental_intent` | 多个 @+ 按序累积 |

### 4.3 Intent 恢复

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| INV-INTENT-RETRY-1 | llmexcept 后 intent 恢复 | `tests/contracts/test_intent_propagation.py::TestIntentRetryRestoration::test_intent_restored_after_retry` | |
| INV-INTENT-RETRY-2 | 嵌套 llmexcept intent 栈 | `tests/contracts/test_intent_propagation.py::TestIntentRetryRestoration::test_persist_intent_survives_retry` | @+ intent 穿越 retry 存活 |

### 4.4 Intent 作用域隔离

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| INV-INTENT-SCOPE-1 | 函数调用 intent 隔离 | `tests/contracts/test_intent_propagation.py::TestIntentScopeIsolation::test_function_intent_isolated` | |
| INV-INTENT-SCOPE-2 | lambda 继承调用方 intent | `tests/e2e/test_intent.py::TestE2EIntents::test_lambda_behavior_uses_call_time_intents` | 调用时意图栈而非定义时空栈 |
| INV-INTENT-SCOPE-3 | snapshot 捕获定义时 intent | 🔶 缺失 | TRUE_GAP：无测试（历史核对存档见 git） |

### 4.5 Intent 与控制流

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| INV-INTENT-FLOW-1 | 循环中 intent 累积 | `tests/contracts/test_intent_propagation.py::TestIntentControlFlow::test_intent_in_loop_iteration` | |
| INV-INTENT-FLOW-2 | 条件分支 intent 隔离 | `tests/contracts/test_intent_propagation.py::TestIntentControlFlow::test_intent_in_conditional` | |
| INV-INTENT-FLOW-3 | return 清除 smear intent | 🔶 缺失 | 无 return 语境专用测试；最近似 `test_intent_cleared_between_iterations`（循环迭代清除） |

---

## §5 LLM 集成语义 (LLM Integration Semantics)

### 5.1 MOCK 协议

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| INV-MOCK-1 | MOCK:STR 确定性 | `tests/contracts/test_llm_integration.py::TestMOCKProtocol::test_mock_typed_returns[MOCK:STR:hello-hello]` | 参数化亦覆盖 INT/LIST/FLOAT |
| INV-MOCK-2 | MOCK:INT 确定性 | `tests/contracts/test_llm_integration.py::TestMOCKProtocol::test_mock_typed_returns[MOCK:INT:42-42]` | |
| INV-MOCK-3 | MOCK:INVALID 触发错误 | 🔶 缺失 | TRUE_GAP：样例仅存于孤儿 fixture，无测试消费者 |

### 5.2 Behavior 表达式

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| INV-BEHAVIOR-1 | @~...~ 执行 LLM 调用 | `tests/contracts/test_llm_integration.py::TestBehaviorExpression::test_behavior_expression_executes` | |
| INV-BEHAVIOR-2 | behavior 立即求值 | `tests/contracts/test_llm_integration.py::TestBehaviorExpression::test_behavior_in_assignment` | |
| INV-BEHAVIOR-3 | behavior 类型推断 | `tests/contracts/test_llm_integration.py::TestBehaviorExpression::test_behavior_in_expression` | |
| INV-BEHAVIOR-4 | behavior 错误处理 | `tests/e2e/test_llmexcept.py::TestE2ELLMExcept::test_llmexcept_with_mock_fail` | 真实错误处理在 e2e；契约层无专门错误路径 |

### 5.3 LLM 函数

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| INV-LLMFN-1 | llmfn 定义与调用 | `tests/contracts/test_llm_integration.py::TestLLMFunction::test_llm_function_definition_and_call` | |
| INV-LLMFN-2 | llmfn 参数传递 | `tests/contracts/test_llm_integration.py::TestLLMFunction::test_llm_function_parameter_binding` | |
| INV-LLMFN-3 | llmfn 返回值类型 | `tests/contracts/test_llm_integration.py::TestLLMFunction::test_llm_function_return_type` | |

### 5.4 Intent 与 LLM 交互

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| INV-INTENT-LLM-1 | intent 注入 LLM 提示 | `tests/contracts/test_llm_integration.py::TestIntentWithLLM::test_intent_affects_llm_call` | |
| INV-INTENT-LLM-2 | @+ intent 持续影响 | `tests/contracts/test_llm_integration.py::TestIntentWithLLM::test_intent_in_llm_function` | |
| INV-INTENT-LLM-3 | @! intent 覆盖 | `tests/contracts/test_llm_integration.py::TestIntentWithLLM::test_intent_cleared_after_llm_call` | 新套件该号语义漂移为"LLM 调用后 smear 清除" |

### 5.5 LLM 调度

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| INV-DISPATCH-1 | LLM 调用进入 CPS | `tests/contracts/test_llm_integration.py::TestLLMDispatch::test_sequential_llm_calls_execute_in_order` | 顺序执行保证；并发见下行 |
| — | 并发 LLM 调用 | `tests/compliance/test_concurrent_llm.py::TestParallelDispatch::test_two_independent_assignments_produce_correct_values` | 原 test_concurrent_llm.py 迁移至 compliance/ |

---

## §6 llmexcept 语义 (llmexcept Semantics)

### 6.1 异常捕获与重试

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| INV-LLMEXCEPT-CATCH-1 | llmexcept 捕获 LLM 错误 | `tests/contracts/test_llmexcept_guarantees.py::TestLLMExceptCatch::test_llmexcept_catches_llm_error` | |
| INV-LLMEXCEPT-CATCH-2 | retry 块执行 | `tests/contracts/test_llmexcept_guarantees.py::TestLLMExceptCatch::test_retry_executes_on_error` | |
| INV-LLMEXCEPT-CATCH-3 | 无错误时跳过 retry | `tests/contracts/test_llmexcept_guarantees.py::TestLLMExceptCatch::test_no_error_skips_retry` | |
| INV-LLMEXCEPT-CATCH-4 | 嵌套 llmexcept 独立 | `tests/contracts/test_llmexcept_guarantees.py::TestLLMExceptCatch::test_nested_llmexcept_independent` | |
| INV-LLMEXCEPT-CATCH-5 | llmexcept 不捕获普通异常 | `tests/contracts/test_llmexcept_guarantees.py::TestLLMExceptCatch::test_llmexcept_does_not_catch_normal_error` | |

### 6.2 错误历史

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| INV-LLMEXCEPT-HISTORY-1 | 错误历史记录 | `tests/contracts/test_llmexcept_guarantees.py::TestLLMExceptHistory::test_error_history_accumulates` | |
| INV-LLMEXCEPT-HISTORY-2 | 嵌套 retry 错误历史 | `tests/contracts/test_llmexcept_guarantees.py::TestLLMExceptHistory::test_error_history_accessible_in_retry` | |

### 6.3 帧深度限制

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| INV-LLMEXCEPT-DEPTH-1 | 深度限制强制执行 | `tests/contracts/test_llmexcept_guarantees.py::TestLLMExceptDepth::test_reasonable_depth_succeeds` | |
| INV-LLMEXCEPT-DEPTH-2 | 超深度触发错误 | `tests/contracts/test_llmexcept_guarantees.py::TestLLMExceptDepth::test_exhausted_retries_raises` | |

### 6.4 不确定值处理

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| INV-LLMEXCEPT-UNCERTAIN-1 | uncertain 标记传播 | `tests/contracts/test_llmexcept_guarantees.py::TestLLMExceptUncertain::test_uncertain_value_isolated` | |
| INV-LLMEXCEPT-UNCERTAIN-2 | uncertain 值禁止运算 | `tests/contracts/test_llmexcept_guarantees.py::TestLLMExceptUncertain::test_str_plus_uncertain_concatenates` | ⚠️ 语义已反转：现契约允许 str+uncertain 拼接（契约废弃待裁决） |

### 6.5 控制流交互

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| INV-LLMEXCEPT-FLOW-1 | llmexcept 在循环中 | `tests/contracts/test_llmexcept_guarantees.py::TestLLMExceptControlFlow::test_llmexcept_in_loop` | |
| INV-LLMEXCEPT-FLOW-2 | llmexcept 在条件中 | `tests/contracts/test_llmexcept_guarantees.py::TestLLMExceptControlFlow::test_llmexcept_in_conditional` | |
| INV-LLMEXCEPT-FLOW-3 | break 退出 llmexcept | `tests/contracts/test_llmexcept_guarantees.py::TestLLMExceptControlFlow::test_llmexcept_with_break` | |
| INV-LLMEXCEPT-FLOW-4 | return 穿透 llmexcept | `tests/contracts/test_llmexcept_guarantees.py::TestLLMExceptControlFlow::test_llmexcept_with_return` | |

### 6.6 变量作用域

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| INV-LLMEXCEPT-SCOPE-1 | try 块变量在 retry 可见 | `tests/contracts/test_llmexcept_guarantees.py::TestLLMExceptScoping::test_outer_variable_accessible_in_retry` | |
| INV-LLMEXCEPT-SCOPE-2 | retry 块变量隔离 | `tests/compiler/semantic/test_binding_analysis_pass.py::TestLLMExceptReadOnlyConstraint::test_sem052_outer_scope_write_produces_error` | 编译期 SEM052：retry 体只读（写外层变量报错） |
| INV-LLMEXCEPT-SCOPE-3 | 嵌套 llmexcept 作用域 | `tests/contracts/test_llmexcept_guarantees.py::TestLLMExceptCatch::test_nested_llmexcept_independent` | 与 INV-LLMEXCEPT-CATCH-3 共用（嵌套独立性即作用域隔离） |

---

## §7 模块系统语义 (Module System Semantics)

### 7.1 Import 机制

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| — | import 语句加载模块 | `tests/e2e/test_modules.py::TestE2EMathModule::test_math_sqrt` | 原 test_e2e_modules.py 迁移至 e2e/test_modules.py |
| — | from...import 语法 | `tests/runtime/test_ibc_file_imports.py::TestIbcFileNamedImport::test_named_import_variable` | 具名导入；别名见 test_named_import_alias |
| — | 模块路径解析 | `tests/runtime/test_ibc_file_imports.py::TestIbcFileMultiModule::test_transitive_import` | 跨模块传递导入 |
| — | 模块缓存机制 | 🔶 缺失 | 需评估；无专门缓存测试 |

### 7.2 循环依赖

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| — | 循环 import 检测 | 🔶 缺失 | 无 IBCI 模块循环依赖测试 |
| — | 循环依赖错误处理 | 🔶 缺失 | 同上 |

### 7.3 模块作用域

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| — | 模块级变量隔离 | `tests/runtime/test_ibc_file_imports.py::TestIbcFileStarImport::test_star_import_does_not_leak_importing_module_intrinsics` | import-* 精确成员枚举，不泄漏被导入模块内部符号 |
| — | 模块重新加载 | 🔶 缺失 | 需评估；无重新加载测试 |

---

## §8 类与继承语义 (Class & Inheritance Semantics)

### 8.1 类定义

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| — | class 定义语法 | `tests/e2e/test_classes.py::TestE2EClasses::test_simple_class` | |
| — | 实例化与 __init__ | `tests/e2e/test_classes.py::TestE2EExplicitInit::test_explicit_init_is_called` | 显式构造；auto-init 见 test_auto_init_positional |
| — | 字段访问 | `tests/e2e/test_classes.py::TestE2EClasses::test_class_field_access` | |

### 8.2 继承

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| — | 单继承 | `tests/e2e/test_classes.py::TestE2EClassInheritance::test_child_accesses_parent_field` | |
| — | 方法覆盖 | `tests/e2e/test_classes.py::TestE2EClassInheritance::test_child_overrides_parent_method` | 签名兼容性另见 e2e/test_override_and_super.py |
| — | super 调用 | `tests/e2e/test_classes.py::TestE2ESuperCall::test_super_init_basic` | 6 个 super e2e 测试覆盖 |

### 8.3 方法解析

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| — | 方法查找顺序（MRO） | `tests/e2e/test_classes.py::TestE2EClassInheritance::test_multi_level_inheritance` | 多层继承成员查找 |
| — | bound_method 语义 | `tests/kernel/test_resolve_call_return.py::TestResolveCallReturn::test_bound_method_with_return` | 内核级：bound method 调用返回类型解析 |

---

## §9 集合类型语义 (Collection Semantics)

### 9.1 List 操作

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| — | list[T] 类型约束 | `tests/contracts/test_type_invariants.py::TestGenericTypeInvariants::test_list_append_preserves_type` | INV-GEN-1 见 §1.3 |
| INV-LIST-1 | list 索引访问（边界检查） | `tests/contracts/test_collection_semantics.py::TestListOperationInvariants::test_list_index_bounds_checked` | |
| INV-LIST-2 | list 负数索引 | `tests/contracts/test_collection_semantics.py::TestListOperationInvariants::test_list_negative_index_wraps` | |
| INV-LIST-4 | list 切片操作 | `tests/contracts/test_collection_semantics.py::TestListOperationInvariants::test_list_slice_preserves_type` | |
| INV-LIST-3 | list.append 类型约束 | `tests/contracts/test_collection_semantics.py::TestListOperationInvariants::test_list_append_type_constraint` | |
| INV-LIST-5 | list.insert 类型约束 | `tests/contracts/test_collection_semantics.py::TestListOperationInvariants::test_list_insert_type_constraint` | |
| INV-LIST-6 | list.pop 返回元素 | `tests/contracts/test_collection_semantics.py::TestListOperationInvariants::test_list_pop_returns_element` | |
| INV-LIST-7 | list.remove 删除语义 | `tests/contracts/test_collection_semantics.py::TestListOperationInvariants::test_list_remove_value_semantics` | |
| INV-LIST-8 | len(list) 不变量 | `tests/contracts/test_collection_semantics.py::TestListOperationInvariants::test_list_len_invariant` | |
| — | for-in list 迭代 | `tests/compiler/test_pipeline.py::TestCompileControlFlow::test_for_in_loop` | 编译级；运行期迭代见 §10.2 |

### 9.2 Dict 操作

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| — | dict[K,V] 类型约束 | `tests/contracts/test_type_invariants.py::TestGenericTypeInvariants::test_dict_key_value_types[int-str-{1: 'a', 2: 'b'}]` | INV-GEN-3 见 §1.3 |
| INV-DICT-2 | dict 键类型约束 | `tests/contracts/test_collection_semantics.py::TestDictOperationInvariants::test_dict_key_type_enforced` | |
| INV-DICT-3 | dict 值类型约束 | `tests/contracts/test_collection_semantics.py::TestDictOperationInvariants::test_dict_value_type_enforced` | |
| INV-DICT-1 | dict.get 默认值 | `tests/contracts/test_collection_semantics.py::TestDictOperationInvariants::test_dict_get_with_default` | |
| INV-DICT-4 | dict.keys 迭代 | `tests/contracts/test_collection_semantics.py::TestDictOperationInvariants::test_dict_keys_returns_collection` | |
| INV-DICT-5 | dict.values 迭代 | `tests/contracts/test_collection_semantics.py::TestDictOperationInvariants::test_dict_values_returns_collection` | |
| INV-DICT-6 | dict 键赋值覆盖 | `tests/contracts/test_collection_semantics.py::TestDictOperationInvariants::test_dict_update_overwrites` | |
| INV-DICT-7 | dict 变更追踪 | `tests/contracts/test_collection_semantics.py::TestDictOperationInvariants::test_dict_update_tracking` | |

### 9.3 String 操作

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| INV-STR-1 | string 索引访问（边界检查） | `tests/contracts/test_collection_semantics.py::TestStringOperationInvariants::test_str_index_bounds_checked` | |
| INV-STR-2 | string 负数索引 | `tests/contracts/test_collection_semantics.py::TestStringOperationInvariants::test_str_negative_index_wraps` | |
| INV-STR-3 | string 切片操作 | `tests/contracts/test_collection_semantics.py::TestStringOperationInvariants::test_str_slice_returns_str` | |
| INV-STR-4 | string 拼接类型 | `tests/contracts/test_collection_semantics.py::TestStringOperationInvariants::test_str_concatenation_type` | |
| INV-STR-5 | len(string) 不变量 | `tests/contracts/test_collection_semantics.py::TestStringOperationInvariants::test_str_len_invariant` | |
| INV-STR-6 | string 不可变性 | `tests/contracts/test_collection_semantics.py::TestStringOperationInvariants::test_str_immutability` | |
| — | str + uncertain 禁止 | `tests/contracts/test_llmexcept_guarantees.py::TestLLMExceptUncertain::test_str_plus_uncertain_concatenates` | ⚠️ 旧标"编译器测试"过期；现契约允许拼接（编译器目录无 uncertain 测试） |

---

## §10 控制流语义 (Control Flow Semantics)

### 10.1 条件分支

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| — | if/elif/else | `tests/e2e/test_llm_basic.py::TestE2EAIControlFlow::test_if_mock_true` | 原 test_e2e_control_flow.py 已删；现由 e2e 覆盖 |
| — | 嵌套 if | `tests/contracts/test_execution_model.py::TestSignalPropagation::test_return_from_nested_context` | 嵌套条件在信号传播测试中被覆盖 |

### 10.2 循环

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| — | while 循环 | `tests/compliance/test_concurrent_llm.py::TestDependentBehaviorSerialized::test_behavior_in_loop_produces_all_results` | 循环内 behavior 每轮产生正确值 |
| — | for-in 循环 | `tests/contracts/test_execution_model.py::TestSignalPropagation::test_break_signal_exits_loop` | 循环变量作用域另见 INV-SCOPE 相关测试 |
| — | for...if 过滤语法 | `tests/e2e/test_for_filter_compound.py::TestForIfFiltering::test_numeric_filter` | |
| — | condition-driven for | `tests/e2e/test_llmexcept.py::TestE2ELLMExceptConditionDrivenLoop::test_condition_driven_loop_with_uncertain_at_middle` | |

### 10.3 Switch 语句

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| — | switch 表达式求值 | `tests/e2e/test_classes.py::TestE2EEnums::test_switch_case` | ⏸️ 旧标"设计未稳定"已过时：switch 已落地且有 e2e 覆盖 |
| — | case 匹配与执行 | `tests/e2e/test_classes.py::TestE2EEnums::test_switch_case` | 与上共用；编译级另有 TestVisitorCoverage::test_switch_case |
| — | switch 内控制流（break/return） | 🔶 缺失 | 无 switch 内 break/return 测试 |

---

## §11 异常处理语义 (Exception Handling Semantics)

### 11.1 Try/Except

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| INV-EXCEPT-CATCH-1 | try/except 基本语法 | `tests/contracts/test_exception_semantics.py::TestExceptionCatching::test_catch_specific_exception_type` | |
| INV-EXCEPT-CATCH-2 | 异常类型匹配 | `tests/contracts/test_exception_semantics.py::TestExceptionCatching::test_multiple_except_blocks` | |
| — | 嵌套 try/except | `tests/contracts/test_exception_semantics.py::TestUnhandledExceptions::test_unhandled_exception_in_nested_try` | 旧行误标 INV-EXCEPT-PROPAGATE-2 |
| INV-EXCEPT-CATCH-3 | except with as 子句 | `tests/contracts/test_exception_semantics.py::TestExceptionCatching::test_except_with_as_clause` | |
| INV-EXCEPT-CATCH-4 | 裸 except 捕获所有异常 | `tests/contracts/test_exception_semantics.py::TestExceptionCatching::test_bare_except_catches_all` | |

### 11.2 Finally

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| INV-EXCEPT-FINALLY-1 | finally 正常完成时执行 | `tests/contracts/test_exception_semantics.py::TestFinallySemantics::test_finally_executes_on_normal_completion` | |
| INV-EXCEPT-FINALLY-2 | finally 异常时执行 | `tests/contracts/test_exception_semantics.py::TestFinallySemantics::test_finally_executes_on_exception` | |
| INV-EXCEPT-FINALLY-3 | finally 在 return 前执行 | `tests/contracts/test_exception_semantics.py::TestFinallySemantics::test_finally_executes_on_return` | |
| INV-EXCEPT-FINALLY-4 | finally 在 break 前执行 | `tests/contracts/test_exception_semantics.py::TestFinallySemantics::test_finally_executes_on_break` | |
| INV-EXCEPT-FINALLY-5 | finally 在 continue 前执行 | `tests/contracts/test_exception_semantics.py::TestFinallySemantics::test_finally_executes_on_continue` | |

### 11.3 异常传播

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| INV-EXCEPT-PROPAGATE-3 | 未捕获异常向上传播 | `tests/contracts/test_exception_semantics.py::TestExceptionPropagation::test_unhandled_exception_terminates` | |
| INV-EXCEPT-PROPAGATE-1 | 异常穿透函数调用 | `tests/contracts/test_exception_semantics.py::TestExceptionPropagation::test_exception_propagates_through_function` | |
| INV-EXCEPT-PROPAGATE-2 | 异常穿透深层嵌套调用 | `tests/contracts/test_exception_semantics.py::TestExceptionPropagation::test_exception_propagates_through_nested_calls` | |
| INV-EXCEPT-PROPAGATE-4 | 异常在第一个匹配 handler 停止 | `tests/contracts/test_exception_semantics.py::TestExceptionPropagation::test_exception_stops_at_first_matching_handler` | |

---

## §12 多解释器隔离 (Multi-Interpreter Isolation)

### 12.1 spawn_isolated

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| — | spawn_isolated 创建独立解释器 | `tests/e2e/test_multi_interpreter.py::TestEngineLayerAPI::test_spawn_returns_handle_string` | 原 test_e2e_multi_interpreter.py 迁移至 e2e/test_multi_interpreter.py |
| — | 子解释器变量隔离 | `tests/compliance/test_execution_isolation.py::TestVariableIsolation::test_child_variable_not_visible_in_parent` | 原 test_execution_isolation.py 迁移至 compliance/ |

### 12.2 collect 机制

| INV | 语义特性 | 覆盖测试 | 备注 |
|-----|---------|---------|------|
| — | collect 收集子解释器结果 | `tests/compliance/test_execution_isolation.py::TestCollectSemantics::test_collect_includes_str_int_bool` | |

---

## §13 覆盖差距分析 (Coverage Gap Analysis)

> 以下为本次迁移确认的**真覆盖缺口**（`🔶 缺失`，不硬凑）。均已核对真实测试集合无语义吻合项。

### 契约层缺口（TRUE_GAP，历史核对存档见 git）

| 契约 | 语义 | 说明 |
|------|------|------|
| INV-CAST-2 | 隐式类型转换规则 | 无专门测试 |
| INV-INTENT-PRIORITY-2 | smear 排在 stack 之后 | 无优先级次序断言测试 |
| INV-INTENT-SCOPE-3 | snapshot 捕获定义时 intent | 无测试 |
| INV-INTENT-FLOW-3 | return 清除 smear intent | 无 return 语境专用测试 |
| INV-MOCK-3 | MOCK:INVALID 触发错误 | 样例仅在孤儿 fixture，无测试消费者 |
| INV-LLMEXCEPT-CATCH-4 | llmexcept 不捕获普通异常 | 无活测试 |

### 模块系统缺口（§7）

- 模块缓存机制（需评估）
- 循环 import 检测 / 循环依赖错误处理
- 模块重新加载（需评估）

### 其它

- §10.3 switch 内控制流（break/return）：switch 已落地，但无 switch 内 break/return 测试

### 已确认覆盖的领域（迁移后全引用可机器对账）

- 类型系统（Optional/泛型/Tuple/cast）→ `tests/contracts/test_type_invariants.py`
- CPS 执行模型（信号/帧栈/递归/闭包上下文）→ `tests/contracts/test_execution_model.py`
- 作用域与闭包（Cell/lambda/snapshot/词法作用域）→ `tests/contracts/test_scope_semantics.py`
- Intent 系统（传播/优先级/恢复/隔离/控制流）→ `tests/contracts/test_intent_propagation.py` + `tests/e2e/test_intent.py`
- LLM 集成（MOCK/Behavior/llmfn/调度）→ `tests/contracts/test_llm_integration.py`
- llmexcept 语义（捕获/历史/深度/uncertain/控制流/作用域）→ `tests/contracts/test_llmexcept_guarantees.py`
- 集合操作（list/dict/str 不变量）→ `tests/contracts/test_collection_semantics.py`
- 异常处理（try/except/finally/传播）→ `tests/contracts/test_exception_semantics.py`
- 类与继承、模块导入、多解释器隔离 → `tests/e2e/test_classes.py`、`tests/runtime/test_ibc_file_imports.py`、`tests/compliance/test_execution_isolation.py`

> 数字纪律：本矩阵不冻结测试通过数字与覆盖比例；以当次 `python -m pytest tests/` 实跑为准。
