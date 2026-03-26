# IBC-Inter 代码审计最终报告

**审计日期**: 2026-03-25
**审计范围**: 核心代码库全面审计
**subagent 数量**: 12 个独立 subagent

---

## 执行摘要

本次审计启动了 **12 个独立 subagent**，从 **6 个不同维度** 对 IBC-Inter 核心代码进行了交叉核验。经过多轮验证，所有关键结论已**收敛确认**。

---

## 一、严重程度分级总结

### 🔴 P0 - 必须立即修复

| 问题 | 位置 | 描述 |
|------|------|------|
| **intent_stack 类型不匹配** | [runtime_context.py:418-424](file:///c:/myself/proj/intent-behavior-code-inter/core/runtime/interpreter/runtime_context.py#L418-L424) | setter 期望 `IntentNode`，但 base_handler.py:91 和 runtime_serializer.py:200 传入 `list`，会导致 `TypeError` |
| **llmexcept 机制设计缺陷** | [stmt_handler.py:132-143](file:///c:/myself/proj/intent-behavior-code-inter/core/runtime/interpreter/handlers/stmt_handler.py#L132-L143) | llm_fallback 检查时机与子节点异常时机不匹配，子节点抛出的 `LLMUncertaintyError` 无法被父节点 llmexcept 捕获 |
| **Mock 机制 MOCK:FAIL/REPAIR 未实现** | [ibci_ai/core.py:165-184](file:///c:/myself/proj/intent-behavior-code-inter/ibci_modules/ibci_ai/core.py#L165-L184) | 文档声称的 `MOCK:TRUE/FALSE/FAIL/REPAIR` 前缀检测**完全不存在**，TESTONLY 模式总是返回 "1" |
| **意图标签解析缺失** | [statement.py:148-203](file:///c:/myself/proj/intent-behavior-code-inter/core/compiler/parser/components/statement.py#L148-L203) | `@+#1`, `@-#2` 等语法中的 `#1`, `#2` 标签**完全未被解析**，tag 字段始终为 None |

### 🟡 P1 - 应尽快修复

| 问题 | 位置 | 描述 |
|------|------|------|
| **Symbol.Kind vs SymbolKind** | [scope_manager.py:44](file:///c:/myself/proj/intent-behavior-code-inter/core/compiler/semantic/passes/scope_manager.py#L44) | 使用了不存在的 `Symbol.Kind` 而非 `SymbolKind`，会导致 AttributeError |
| **ScopeManager 缺少 Intent 场景** | [scope_manager.py:15](file:///c:/myself/proj/intent-behavior-code-inter/core/compiler/semantic/passes/scope_manager.py#L15) | 场景栈只初始化了 `GENERAL/BRANCH/LOOP`，缺少 `INTENT` 场景 |
| **FunctionMetadata.resolve_return 协变错误** | [descriptors.py:544-552](file:///c:/myself/proj/intent-behavior-code-inter/core/kernel/types/descriptors.py#L544-L552) | 参数类型检查使用协变而非逆变，导致 `int` 不能赋值给 `float` 参数槽位 |
| **int // int 返回 float** | [primitives.py:73](file:///c:/myself/proj/intent-behavior-code-inter/core/kernel/axioms/primitives.py#L73) | 整除操作应返回 int，实际返回 float |
| **OVERRIDE 意图内容丢失** | [intent_resolver.py:46-48](file:///c:/myself/proj/intent-behavior-code-inter/core/kernel/intent_resolver.py#L46-L48) | `@!` 修饰的意图内容不会被注入到 prompt |
| **ai.set_retry() 无效** | [ibci_ai/core.py:86-87](file:///c:/myself/proj/intent-behavior-code-inter/ibci_modules/ibci_ai/core.py#L86-L87) | 重试次数配置被存储但从未读取，硬编码为 3 |

### 🟢 P2 - 计划修复

| 问题 | 位置 | 描述 |
|------|------|------|
| **ExpressionAnalyzer 未被使用** | [expression_analyzer.py](file:///c:/myself/proj/intent-behavior-code-inter/core/compiler/semantic/passes/expression_analyzer.py) | 完整的表达式分析器定义但从未被实例化 |
| **Behavior 表达式不支持嵌套** | [expression.py:272](file:///c:/myself/proj/intent-behavior-code-inter/core/compiler/parser/components/expression.py#L272) | 遇到嵌套 `@inner~` 会提前终止外层解析 |
| **单元测试断言质量低** | tests/ 目录 | 大量 `len(body) >= 1` 级别弱断言，不验证 AST 结构正确性 |
| **运行时测试完全空白** | tests/runtime/ | 解释器、LLMExecutor、IntentStack 测试全部缺失 |

---

## 二、模块维度问题汇总

| 模块 | 严重问题数 | 中等问题数 | 总体评估 |
|------|------------|------------|----------|
| **Lexer** | 1 | 3 | 基本正确，但 @ 修饰符标签处理有问题 |
| **Parser** | 1 | 4 | 基本正确，但意图关联位置和标签解析有缺陷 |
| **Semantic Analyzer** | 2 | 5 | 存在 Symbol.Kind 错误和场景栈问题 |
| **Type System** | 1 | 4 | FunctionMetadata 逆变错误，int//int 返回 float |
| **Interpreter** | 2 | 3 | intent_stack 类型错误，llmexcept 路径缺陷 |
| **Intent Stack** | 2 | 2 | 标签解析缺失，OVERRIDE 语义问题 |
| **Mock/AI** | 1 | 1 | MOCK:xxx 前缀完全未实现 |
| **单元测试** | 1 | 3 | 测试覆盖不足，断言质量低 |

---

## 三、Example 功能有效性

| Example | 功能正确性 | 验证充分性 |
|---------|------------|------------|
| [basic_ai.ibci](file:///c:/myself/proj/intent-behavior-code-inter/examples/01_basics/basic_ai.ibci) | ⚠️ 部分正确 | 不充分 - Mock 模式只返回固定格式 |
| [class_protocol.ibci](file:///c:/myself/proj/intent-behavior-code-inter/examples/01_basics/class_protocol.ibci) | ✅ 正确 | 不充分 - 无法验证 LLM 真正理解 |
| [intent_driven_loop.ibci](file:///c:/myself/proj/intent-behavior-code-inter/examples/02_control_flow/intent_driven_loop.ibci) | ❌ **不工作** | **无效** - llmexcept/retry 机制不工作 |
| [llm_error_handling.ibci](file:///c:/myself/proj/intent-behavior-code-inter/examples/02_control_flow/llm_error_handling.ibci) | ❌ **不工作** | **无效** - MOCK:FAIL/REPAIR 未实现 |
| [04_mock_advanced.ibci](file:///c:/myself/proj/intent-behavior-code-inter/examples/05_llm_config/04_mock_advanced.ibci) | ❌ **不工作** | **无效** - 依赖的 Mock 机制未实现 |

---

## 四、收敛确认的关键结论

经过 12 个独立 subagent 的交叉核验，以下结论已**完全收敛**：

1. ✅ **intent_stack 类型错误** - 多方验证确认，会导致 TypeError
2. ✅ **llmexcept 机制设计缺陷** - 异常捕获路径不连通
3. ✅ **MOCK:xxx 前缀未实现** - 代码中完全没有解析逻辑
4. ✅ **意图标签解析缺失** - infrastructure 存在但解析器未实现
5. ✅ **单元测试只验证编译通过** - 不验证功能正确性

---

## 五、核心建议

### 立即行动（本周）

1. 修复 `intent_stack` 类型不匹配问题，将 setter 改为接受 `list` 并转换为 `IntentNode`
2. 修复 `scope_manager.py:44` 的 `Symbol.Kind` → `SymbolKind`
3. 在 `ibci_ai/core.py` 中实现 `MOCK:FAIL/REPAIR` 前缀检测逻辑

### 短期行动（本月）

4. 修复 llmexcept 异常捕获路径，使子节点异常能被父节点 llmexcept 捕获
5. 实现意图标签 (`#1`, `#2`) 解析
6. 修复 `FunctionMetadata.resolve_return` 的逆变检查逻辑

### 中期规划

7. 重写单元测试，从"编译通过"验证转向"功能正确性"验证
8. 补充运行时集成测试（Interpreter、LLMExecutor、IntentStack）
9. 实现 `ai.set_retry()` 的实际重试次数控制

---

## 六、详细问题索引

### 6.1 Lexer 问题详情

| 问题 | 文件:行号 | 严重程度 |
|------|----------|----------|
| @ 修饰符标签处理不完整 | core_scanner.py:253-278 | 中 |
| 三引号字符串不支持 | core_scanner.py:245-250 | 高 |
| \\ 转义处理缺失 | core_scanner.py:448-461 | 高 |

### 6.2 Parser 问题详情

| 问题 | 文件:行号 | 严重程度 |
|------|----------|----------|
| 意图关联位置不正确 | statement.py:127-142 | 高 |
| llm 关键字跳过逻辑可疑 | declaration.py:173 | 中 |
| 意图标签未解析 | statement.py:148-203 | 高 |
| IbExprStmt 不支持 llm_fallback | ast.py:236-243 | 中 |

### 6.3 Semantic Analyzer 问题详情

| 问题 | 文件:行号 | 严重程度 |
|------|----------|----------|
| Symbol.Kind vs SymbolKind | scope_manager.py:44 | 高 |
| ScopeManager 缺少 INTENT 场景 | scope_manager.py:15 | 中 |
| ExpressionAnalyzer 未被使用 | expression_analyzer.py | 中 |
| 列表字面量同构假设 | semantic_analyzer.py:761-772 | 中 |
| 场景栈不穿透循环体 | semantic_analyzer.py:595 | 中 |

### 6.4 Type System 问题详情

| 问题 | 文件:行号 | 严重程度 |
|------|----------|----------|
| FunctionMetadata 逆变错误 | descriptors.py:544-552 | 高 |
| int // int 返回 float | primitives.py:73 | 中 |
| is_dynamic() 硬编码回退 | descriptors.py:201 | 中 |
| 预定义描述符未绑定公理 | descriptors.py:742-760 | 中 |

### 6.5 Interpreter 问题详情

| 问题 | 文件:行号 | 严重程度 |
|------|----------|----------|
| intent_stack 类型不匹配 | runtime_context.py:418-424 | 高 |
| llmexcept 路径缺陷 | stmt_handler.py:132-143 | 高 |
| for 循环双重 pop_loop_context | stmt_handler.py:213-220 | 中 |
| retry_hint 全局污染 | llm_executor.py:246-255 | 中 |

### 6.6 Intent Stack 问题详情

| 问题 | 文件:行号 | 严重程度 |
|------|----------|----------|
| 标签解析缺失 | statement.py:148-203 | 高 |
| OVERRIDE 内容丢失 | intent_resolver.py:46-48 | 中 |
| IntentNode 缓存无失效 | runtime_context.py:192-205 | 低 |
| push/pop 非原子 | runtime_context.py:380,385 | 中 |

### 6.7 Mock/AI 问题详情

| 问题 | 文件:行号 | 严重程度 |
|------|----------|----------|
| MOCK:xxx 前缀未实现 | ibci_ai/core.py:165-184 | 高 |
| ai.set_retry() 无效 | ibci_ai/core.py:86-87 | 中 |

---

## 七、与 PENDING_TASKS.md 的关系

本节说明审计发现的问题与 `PENDING_TASKS.md` 中记录的问题之间的对应关系。

### 7.1 已知技术债务 vs 新发现问题

| 审计发现 | PENDING_TASKS.md 对应 | 状态 |
|---------|---------------------|------|
| intent_stack 类型不匹配 | **1.1 Intent Stack 深拷贝实现** | 已知问题，技术债务 |
| Intent 公理化缺失 | **2.1 Intent 完整公理化** | 已知问题，计划中 |
| Behavior 公理化缺失 | **2.2 Behavior 完整公理化** | 已知问题，计划中 |
| Intent Stack 不可变性 | **2.3 Intent Stack 不可变性约束** | 已知问题，计划中 |
| 符号同步深拷贝 | **2.4 符号同步深拷贝** | 已知问题，计划中 |
| MetadataRegistry 双轨 | **8.1 统一注册表管理** | 已知问题，计划中 |
| vtable 参数签名提取 | **9.5 vtable 参数签名提取** | 已知问题，优先级高 |
| 多值返回与Tuple | **9.4 多值返回与 Tuple** | 已知问题，计划中 |

### 7.2 本次审计新发现的问题

以下问题在 `PENDING_TASKS.md` 中**未提及**，属于新发现：

| 新发现 | 严重程度 | 说明 |
|--------|---------|------|
| **llmexcept 机制设计缺陷** | P0 | 异常捕获路径断裂，需要紧急修复 |
| **Mock 机制 MOCK:FAIL/REPAIR 未实现** | P0 | 文档声称已实现但代码未实现 |
| **意图标签解析缺失** | P0 | 语法手册描述但代码未实现 |
| **Symbol.Kind vs SymbolKind** | P1 | typo 错误，不是设计问题 |
| **int // int 返回 float** | P1 | 类型系统运算错误 |
| **OVERRIDE 意图内容丢失** | P1 | 意图系统语义问题 |

### 7.3 PENDING_TASKS.md 中可删除的已完成项

根据代码审计，以下条目**可能已在代码中解决**或**描述不准确**：

| 条目 | 审计发现 | 建议 |
|------|---------|------|
| 9.1 vtable 参数签名提取 | 问题仍存在，与文档描述不符 | 需确认 |
| 9.3 模块符号去重 | 存在 MODULE/CLASS 符号冲突 | 需处理 |

---

### 八、与 NEXT_STEPS_PLAN.md 的关系

**重要声明**：`NEXT_STEPS_PLAN.md` 声称 **"Phase 0-6 全部完成"**，但本次审计发现多个 P0/P1 问题尚未解决。

| 声称完成 | 审计发现 | 结论 |
|---------|---------|------|
| Phase 1: 公理体系健壮性 ✅ | FunctionMetadata.resolve_return **逆变错误仍存在** | **声明不准确** |
| Phase 3: DynamicHost ✅ | 异常处理后状态可能不干净 | **声明不准确** |
| Phase 6: IES 2.2 重构 ✅ | Mock 机制严重简化，不支持 MOCK:FAIL/REPAIR | **声明不准确** |

**建议**：项目负责人需重新评估 Phase 完成状态，不应仅依赖文档声明。

---

### 九、关于 UNIT_TEST_LOG.md

`UNIT_TEST_LOG.md` 声称 **"单元测试：❌ 不存在"**，但实际存在 **25 个测试文件**。

此文档内容与实际情况**完全相反**，建议：
- **立即删除** 或
- **完全重写** 以反映实际测试状态

---

*本报告由 IBC-Inter 自动化代码审计系统生成*
