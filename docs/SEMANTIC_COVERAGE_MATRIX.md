# IBCI语义覆盖矩阵（Semantic Coverage Matrix）
> Created: 2026-05-13
> Purpose: 建立IBCI核心语义到测试覆盖的完整映射，确保测试体系的完整性

## 文档目标

本文档不是为了"删减测试数量"，而是为了**论证测试覆盖的完整性**。

**核心问题**：当前的契约测试 + 高价值集成测试，是否真正覆盖了IBCI的所有核心语义？

**使用方式**：
1. ✅ = 已被契约测试充分覆盖
2. 🔶 = 需要高价值集成测试覆盖（无法用简单契约表达）
3. ❌ = 覆盖不足，需要补充测试
4. ⚠️ = 存在测试但需要评估是否足够

---

## §1 类型系统语义 (Type System Semantics)

### 1.1 基础类型保证

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| int 算术运算正确性 | ✅ | INV-CAST-*, 编译器测试 | 基础运算由Python保证 |
| str 字符串操作 | ⚠️ | 散落在e2e测试中 | **待评估**：是否需要str操作契约？ |
| float 精度保证 | ⚠️ | 部分e2e测试 | **待评估** |
| bool 逻辑运算 | ✅ | 控制流测试覆盖 | |

### 1.2 Optional[T] 语义

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| None访问时运行时错误 | ✅ | INV-OPT-1 | test_optional_none_access_raises |
| Optional赋值兼容性 | ✅ | INV-OPT-2 | test_optional_accepts_none |
| Optional类型检查 | ✅ | INV-OPT-3 | test_optional_rejects_wrong_type |
| Optional链式操作 | ✅ | INV-OPT-4 | test_optional_chaining_safe |

### 1.3 泛型类型语义

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| list[T] 元素类型约束 | ✅ | INV-GEN-1 | test_list_generic_type_check |
| dict[K,V] 键值类型约束 | ✅ | INV-GEN-2 | test_dict_generic_type_check |
| 嵌套泛型类型 | ✅ | INV-GEN-3 | test_nested_generics |
| 泛型类型推断 | ✅ | INV-INFER-* | |

### 1.4 Tuple类型语义

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| tuple[T1,T2] 位置类型 | ✅ | INV-TUPLE-1,2 | test_tuple_positional_types |
| tuple下标类型推断 | ✅ | INV-TUPLE-3 | test_tuple_subscript_type |
| tuple解包类型检查 | ⚠️ | test_e2e_tuple_unpack.py | **待评估**：是否需要契约测试？ |

### 1.5 类型转换语义

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| 显式cast安全性 | ✅ | INV-CAST-1 | test_cast_validates_type |
| 隐式类型转换规则 | ✅ | INV-CAST-2 | test_implicit_conversion |
| 类型推断规则 | ✅ | INV-INFER-1,2 | |

---

## §2 执行模型语义 (Execution Model Semantics)

### 2.1 CPS执行模型

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| 深递归无Python栈溢出 | ✅ | INV-CPS-1 | test_deep_recursion_no_python_overflow |
| 深调用链通过trampoline | ✅ | INV-CPS-2 | test_deep_call_chain_succeeds |
| 相互递归支持 | ✅ | INV-CPS-3 | test_mutual_recursion_supported |

### 2.2 控制流信号传播

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| return立即退出函数 | ✅ | INV-SIGNAL-1 | test_return_signal_exits_function |
| break退出循环 | ✅ | INV-SIGNAL-2 | test_break_signal_exits_loop |
| continue跳过迭代 | ✅ | INV-SIGNAL-3 | test_continue_signal_skips_iteration |
| 嵌套循环break只退出内层 | ✅ | INV-SIGNAL-4 | test_nested_loop_break_only_inner |
| 深层嵌套中的return | ✅ | INV-SIGNAL-5 | test_return_from_nested_context |

### 2.3 帧栈管理

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| 函数调用创建隔离帧 | ✅ | INV-FRAME-1 | test_function_call_creates_new_frame |
| return时帧弹出 | ✅ | INV-FRAME-2 | test_frame_pops_on_return |
| 嵌套调用维护帧链 | ✅ | INV-FRAME-3 | test_nested_calls_maintain_frame_chain |
| 帧局部变量隔离 | ✅ | INV-FRAME-4 | test_frame_local_variables_isolated |

### 2.4 递归深度保证

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| 合理递归深度成功 | ✅ | INV-RECURSION-1 | test_reasonable_recursion_depth |
| 尾调用式递归支持 | ✅ | INV-RECURSION-2 | test_tail_call_like_recursion |

### 2.5 异常回退

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| LLM错误回退到llmexcept | ✅ | INV-UNWIND-1 | test_error_unwinds_to_llmexcept |
| 错误通过调用栈传播 | ✅ | INV-UNWIND-2 | test_error_propagates_through_calls |
| 普通异常传播 | ❌ | **缺失** | **需要补充**：try/except/finally语义 |

---

## §3 作用域与闭包语义 (Scope & Closure Semantics)

### 3.1 IbCell共享引用

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| Cell变量共享可见 | ✅ | INV-CELL-1 | test_cell_shared_reference_visible |
| Cell修改对所有引用可见 | ✅ | INV-CELL-2 | test_cell_mutation_visible_to_all |

### 3.2 Lambda引用捕获

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| lambda捕获外层变量 | ✅ | INV-LAMBDA-1 | test_lambda_captures_outer_variable |
| lambda看到外层变量修改 | ✅ | INV-LAMBDA-2 | test_lambda_sees_outer_mutation |
| lambda修改外层变量 | ✅ | INV-LAMBDA-3 | test_lambda_modifies_outer_cell |

### 3.3 Snapshot值捕获

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| snapshot定义时深克隆 | ✅ | INV-SNAPSHOT-1 | test_snapshot_deep_clone_at_definition |
| snapshot不受外层修改影响 | ✅ | INV-SNAPSHOT-2 | test_snapshot_isolated_from_outer_changes |
| snapshot每次调用独立求值 | ✅ | INV-SNAPSHOT-3 | test_snapshot_no_cache |

### 3.4 词法作用域规则

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| 内层可访问外层变量 | ✅ | INV-SCOPE-1 | test_inner_scope_accesses_outer |
| 内层变量遮蔽外层 | ✅ | INV-SCOPE-2 | test_inner_scope_shadows_outer |
| 函数作用域隔离 | ✅ | INV-SCOPE-3 | test_function_scope_isolated |
| 全局变量可见性 | ✅ | INV-SCOPE-4 | test_global_variable_visible |

### 3.5 闭包上下文传播

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| 闭包捕获父帧变量 | ✅ | INV-CONTEXT-1 | test_closure_captures_parent_frame |
| 多个闭包独立帧 | ✅ | INV-CONTEXT-2 | test_multiple_closures_independent_frames |
| 嵌套闭包访问链 | ✅ | INV-CONTEXT-3 | test_nested_closure_access_chain |

---

## §4 Intent系统语义 (Intent System Semantics)

### 4.1 Intent传播机制

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| @ smear intent一次性 | ✅ | INV-INTENT-PROP-1 | test_smear_intent_one_shot |
| @+ stack intent持久化 | ✅ | INV-INTENT-PROP-2 | test_stack_intent_persists |
| @- remove intent移除 | ✅ | INV-INTENT-PROP-3 | test_remove_intent_works |

### 4.2 Intent优先级

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| @! override清空栈 | ✅ | INV-INTENT-PRIORITY-1 | test_override_clears_stack |
| smear排在stack之后 | ✅ | INV-INTENT-PRIORITY-2 | test_smear_after_stack |
| 多层stack按顺序 | ✅ | INV-INTENT-PRIORITY-3 | test_multiple_stack_order |

### 4.3 Intent恢复

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| llmexcept后intent恢复 | ✅ | INV-INTENT-RETRY-1 | test_intent_restored_after_retry |
| 嵌套llmexcept intent栈 | ✅ | INV-INTENT-RETRY-2 | test_nested_retry_intent_stack |

### 4.4 Intent作用域隔离

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| 函数调用intent隔离 | ✅ | INV-INTENT-SCOPE-1 | test_function_call_intent_isolated |
| lambda继承调用方intent | ✅ | INV-INTENT-SCOPE-2 | test_lambda_inherits_caller_intent |
| snapshot捕获定义时intent | ✅ | INV-INTENT-SCOPE-3 | test_snapshot_captures_definition_intent |

### 4.5 Intent与控制流

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| 循环中intent累积 | ✅ | INV-INTENT-FLOW-1 | test_intent_in_loop |
| 条件分支intent隔离 | ✅ | INV-INTENT-FLOW-2 | test_intent_in_conditional |
| return清除smear intent | ✅ | INV-INTENT-FLOW-3 | test_return_clears_smear |

---

## §5 LLM集成语义 (LLM Integration Semantics)

### 5.1 MOCK协议

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| MOCK:STR确定性 | ✅ | INV-MOCK-1 | test_mock_str_deterministic |
| MOCK:INT确定性 | ✅ | INV-MOCK-2 | test_mock_int_deterministic |
| MOCK:INVALID触发错误 | ✅ | INV-MOCK-3 | test_mock_invalid_triggers_error |

### 5.2 Behavior表达式

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| @~...~ 执行LLM调用 | ✅ | INV-BEHAVIOR-1 | test_behavior_expr_executes_llm |
| behavior立即求值 | ✅ | INV-BEHAVIOR-2 | test_behavior_immediate_evaluation |
| behavior类型推断 | ✅ | INV-BEHAVIOR-3 | test_behavior_type_inference |
| behavior错误处理 | ✅ | INV-BEHAVIOR-4 | test_behavior_error_handling |

### 5.3 LLM函数

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| llmfn定义与调用 | ✅ | INV-LLMFN-1 | test_llm_function_definition |
| llmfn参数传递 | ✅ | INV-LLMFN-2 | test_llm_function_parameters |
| llmfn返回值类型 | ✅ | INV-LLMFN-3 | test_llm_function_return_type |

### 5.4 Intent与LLM交互

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| intent注入LLM提示 | ✅ | INV-INTENT-LLM-1 | test_intent_injected_to_llm |
| @+ intent持续影响 | ✅ | INV-INTENT-LLM-2 | test_stack_intent_affects_llm |
| @! intent覆盖 | ✅ | INV-INTENT-LLM-3 | test_override_intent_in_llm |

### 5.5 LLM调度

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| LLM调用进入CPS | ✅ | INV-DISPATCH-1 | test_llm_call_enters_cps |
| 并发LLM调用 | 🔶 | test_concurrent_llm.py | 需要集成测试 |

---

## §6 llmexcept语义 (llmexcept Semantics)

### 6.1 异常捕获与重试

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| llmexcept捕获LLM错误 | ✅ | INV-LLMEXCEPT-CATCH-1 | test_llmexcept_catches_llm_error |
| retry块执行 | ✅ | INV-LLMEXCEPT-CATCH-2 | test_retry_block_executes |
| 嵌套llmexcept | ✅ | INV-LLMEXCEPT-CATCH-3 | test_nested_llmexcept |
| llmexcept不捕获普通异常 | ✅ | INV-LLMEXCEPT-CATCH-4 | test_llmexcept_ignores_normal_exception |

### 6.2 错误历史

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| 错误历史记录 | ✅ | INV-LLMEXCEPT-HISTORY-1 | test_error_history_tracked |
| 嵌套retry错误历史 | ✅ | INV-LLMEXCEPT-HISTORY-2 | test_nested_retry_error_history |

### 6.3 帧深度限制

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| 深度限制强制执行 | ✅ | INV-LLMEXCEPT-DEPTH-1 | test_depth_limit_enforced |
| 超深度触发错误 | ✅ | INV-LLMEXCEPT-DEPTH-2 | test_excessive_depth_fails |

### 6.4 不确定值处理

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| uncertain标记传播 | ✅ | INV-LLMEXCEPT-UNCERTAIN-1 | test_uncertain_flag_propagates |
| uncertain值禁止运算 | ✅ | INV-LLMEXCEPT-UNCERTAIN-2 | test_uncertain_blocks_operations |

### 6.5 控制流交互

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| llmexcept在循环中 | ✅ | INV-LLMEXCEPT-FLOW-1 | test_llmexcept_in_loop |
| llmexcept在条件中 | ✅ | INV-LLMEXCEPT-FLOW-2 | test_llmexcept_in_conditional |
| break退出llmexcept | ✅ | INV-LLMEXCEPT-FLOW-3 | test_break_exits_llmexcept |
| return穿透llmexcept | ✅ | INV-LLMEXCEPT-FLOW-4 | test_return_through_llmexcept |

### 6.6 变量作用域

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| try块变量在retry可见 | ✅ | INV-LLMEXCEPT-SCOPE-1 | test_try_variable_visible_in_retry |
| retry块变量隔离 | ✅ | INV-LLMEXCEPT-SCOPE-2 | test_retry_variable_isolated |
| 嵌套llmexcept作用域 | ✅ | INV-LLMEXCEPT-SCOPE-3 | test_nested_llmexcept_scope |

---

## §7 模块系统语义 (Module System Semantics)

### 7.1 Import机制

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| import语句加载模块 | 🔶 | test_e2e_modules.py | 需要集成测试 |
| from...import语法 | 🔶 | test_e2e_modules.py | 需要集成测试 |
| 模块路径解析 | 🔶 | test_e2e_modules.py | 需要集成测试 |
| 模块缓存机制 | ❌ | **缺失** | **需要评估** |

### 7.2 循环依赖

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| 循环import检测 | 🔶 | test_e2e_modules.py | 需要集成测试 |
| 循环依赖错误处理 | 🔶 | test_e2e_modules.py | 需要集成测试 |

### 7.3 模块作用域

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| 模块级变量隔离 | 🔶 | test_e2e_modules.py | 需要集成测试 |
| 模块重新加载 | ❌ | **缺失** | **需要评估** |

---

## §8 类与继承语义 (Class & Inheritance Semantics)

### 8.1 类定义

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| class定义语法 | 🔶 | test_e2e_classes.py | 需要集成测试 |
| 实例化与__init__ | 🔶 | test_e2e_classes.py | 需要集成测试 |
| 字段访问 | 🔶 | test_e2e_classes.py | 需要集成测试 |

### 8.2 继承

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| 单继承 | 🔶 | test_e2e_classes.py | 需要集成测试 |
| 方法覆盖 | 🔶 | test_e2e_classes.py | 需要集成测试 |
| super调用 | 🔶 | test_e2e_classes.py | 需要集成测试 |

### 8.3 方法解析

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| 方法查找顺序（MRO） | 🔶 | test_e2e_classes.py | 需要集成测试 |
| bound_method语义 | ❌ | **缺失** | **需要评估**：是否需要契约测试？ |

---

## §9 集合类型语义 (Collection Semantics)

### 9.1 List操作

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| list创建与索引 | ⚠️ | 散落在e2e测试 | **待评估** |
| list.append/extend | ⚠️ | 散落在e2e测试 | **待评估** |
| list切片 | ⚠️ | 部分e2e测试 | **待评估** |
| for-in list迭代 | 🔶 | test_e2e_control_flow.py | 需要集成测试 |

### 9.2 Dict操作

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| dict创建与访问 | ⚠️ | 散落在e2e测试 | **待评估** |
| dict.keys/values | ⚠️ | plugin测试 | **待评估** |
| dict键不存在错误 | ⚠️ | 部分e2e测试 | **待评估** |

### 9.3 String操作

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| str拼接 | ⚠️ | 散落在e2e测试 | **待评估** |
| str.find/replace | ⚠️ | plugin测试 | **待评估** |
| str格式化 | ⚠️ | 部分e2e测试 | **待评估** |
| str + uncertain禁止 | ✅ | 编译器测试 | 已有明确规则 |

---

## §10 控制流语义 (Control Flow Semantics)

### 10.1 条件分支

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| if/elif/else | 🔶 | test_e2e_control_flow.py | 需要集成测试 |
| 嵌套if | 🔶 | test_e2e_control_flow.py | 需要集成测试 |

### 10.2 循环

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| while循环 | 🔶 | test_e2e_control_flow.py | 需要集成测试 |
| for-in循环 | 🔶 | test_e2e_control_flow.py | 需要集成测试 |
| for...if过滤语法 | 🔶 | test_e2e_control_flow.py | 需要集成测试 |
| condition-driven for | 🔶 | test_e2e_control_flow.py | 需要集成测试 |

### 10.3 Switch语句

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| switch/case | ❌ | **缺失** | **需要评估**：switch是否已实现？ |

---

## §11 异常处理语义 (Exception Handling Semantics)

### 11.1 Try/Except

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| try/except基本语法 | 🔶 | test_e2e_exceptions.py | 需要集成测试 |
| 异常类型匹配 | 🔶 | test_e2e_exceptions.py | 需要集成测试 |
| 嵌套try/except | 🔶 | test_e2e_exceptions.py | 需要集成测试 |

### 11.2 Finally

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| finally块必定执行 | ⚠️ | 部分e2e测试 | **需要评估** |

### 11.3 异常传播

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| 未捕获异常向上传播 | ⚠️ | 部分e2e测试 | **需要补充契约测试** |
| 异常穿透函数调用 | ❌ | **缺失** | **需要补充契约测试** |

---

## §12 多解释器隔离 (Multi-Interpreter Isolation)

### 12.1 spawn_isolated

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| spawn_isolated创建独立解释器 | 🔶 | test_e2e_multi_interpreter.py | 需要集成测试 |
| 子解释器变量隔离 | 🔶 | test_execution_isolation.py | 需要集成测试 |

### 12.2 collect机制

| 语义特性 | 覆盖状态 | 测试位置 | 备注 |
|---------|---------|---------|------|
| collect收集子解释器结果 | 🔶 | test_e2e_multi_interpreter.py | 需要集成测试 |

---

## §13 覆盖差距分析 (Coverage Gap Analysis)

### 关键发现

1. **✅ 已充分覆盖的领域**：
   - 类型系统核心（Optional, 泛型, Tuple, cast）
   - CPS执行模型（信号, 帧栈, 递归）
   - 作用域与闭包（Cell, lambda, snapshot）
   - Intent系统完整语义
   - LLM集成与MOCK协议
   - llmexcept完整语义

2. **🔶 需要高价值集成测试的领域**（无法用简单契约表达）：
   - 模块系统（import, 循环依赖）
   - 类与继承（MRO, super）
   - 控制流复杂交互
   - 多解释器隔离
   - 并发LLM调用

3. **❌ 覆盖不足需要补充的领域**：
   - **高优先级**：
     - 普通异常传播语义（try/except/finally contract）
     - 异常穿透函数调用契约
   - **中优先级**：
     - 集合类型操作契约（list/dict/str关键操作）
   - **低优先级**：
     - 模块缓存机制
     - bound_method详细语义

### 补充建议

#### 立即补充（高优先级）

1. **创建 `tests/contracts/test_exception_semantics.py`**
   - INV-EXCEPT-PROPAGATE-*: 异常传播规则
   - INV-EXCEPT-FINALLY-*: finally块执行保证
   - INV-EXCEPT-UNHANDLED-*: 未捕获异常行为

2. **扩展现有契约测试**
   - 在 `test_execution_model.py` 中添加更多异常回退场景

#### 评估后决定（中优先级）

1. **集合操作契约** - 需要评估：
   - 大部分集合操作由Python保证语义
   - 可能只需要IBCI特有的类型检查契约
   - 建议：先验证现有e2e测试是否充分

2. **String操作契约** - 需要评估：
   - str + uncertain已有明确契约（禁止）
   - 其他字符串操作是否需要额外契约？

#### 保持现状（低优先级）

1. **模块系统** - 当前集成测试充分
2. **类继承** - 当前集成测试充分
3. **控制流** - 当前集成测试充分
4. **多解释器** - 当前集成测试充分

---

## §14 行动计划 (Action Plan)

### Phase 1: 补充关键契约测试（本周）

1. **创建 `tests/contracts/test_exception_semantics.py`**
   - 编写10-15个异常传播契约测试
   - 覆盖try/except/finally核心语义
   - 验证异常穿透函数调用

2. **验证覆盖完整性**
   - 运行 `pytest --cov=core tests/contracts/`
   - 确认关键异常处理路径被覆盖

### Phase 2: 评估集合操作覆盖（下周）

1. **审查现有e2e测试**
   - 列出所有涉及list/dict/str操作的测试
   - 评估是否需要提炼为契约测试

2. **决策点**
   - 如果现有测试充分 → 保持现状
   - 如果发现语义gap → 补充契约测试

### Phase 3: 基于覆盖证明删除旧测试（之后）

**原则**：只有在明确证明契约测试已覆盖后，才删除旧测试

1. **逐文件审查**
   - 对每个测试文件，逐个测试评估
   - 标注：✅已覆盖 / 🔶需保留 / ❌需补充

2. **安全删除**
   - 确认契约覆盖
   - 运行回归测试
   - 删除并再次验证

---

## 总结 (Summary)

### 当前覆盖状态

- **契约测试数量**：91个（6个文件）
- **覆盖的核心语义**：~70%
- **需要集成测试的语义**：~20%
- **覆盖gap**：~10%（主要是异常传播）

### 核心洞察

1. **不要为删减而删减**
   - 目标是建立完整的语义覆盖证明
   - 删减是覆盖证明的自然结果，不是目标本身

2. **契约测试的价值**
   - 解耦测试与实现
   - 建立可验证的语义不变量
   - 使重构更安全

3. **分层测试策略**
   - 契约层：核心语义不变量（91 tests）
   - 集成层：复杂交互场景（~300 tests）
   - 合规层：跨实现保证（~30 tests）

### 下一步

1. ✅ 已建立完整的语义覆盖矩阵
2. 🚧 补充异常传播契约测试
3. ⏳ 评估集合操作覆盖
4. ⏳ 基于覆盖证明安全删除旧测试

**关键原则**：测试质量 > 测试数量，语义覆盖 > 代码行数
