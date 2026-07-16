# 测试覆盖映射 (Coverage Map)

> 索引：语言概念 / 子系统 → 测试入口文件。
> **新增测试时必须先在本表找到对应概念的文件；如不存在，先在此表新增一行 + 说明，再创建文件。**
> 详见 `tests/README.md` 的维护守则。
>
> 最后更新：2026-06-25（文档体系整理：统计快照纪律化）

---

## 契约测试（核心语义不变量）

| 概念 | 测试入口 |
|------|----------|
| 类型系统不变量（Optional/泛型/cast/tuple位置类型） | `tests/contracts/test_type_invariants.py` |
| 执行模型公理（CPS/信号/帧栈/递归保证） | `tests/contracts/test_execution_model.py` |
| 作用域语义（Cell/lambda/snapshot/词法作用域） | `tests/contracts/test_scope_semantics.py` |
| Intent传播/优先级/恢复/作用域隔离 | `tests/contracts/test_intent_propagation.py` |
| llmexcept保证（异常捕获/重试/历史/深度） | `tests/contracts/test_llmexcept_guarantees.py` |
| LLM集成（MOCK/行为表达式/LLM函数/分发） | `tests/contracts/test_llm_integration.py` |
| 异常传播语义（try/except/finally） | `tests/contracts/test_exception_semantics.py` |
| 集合操作语义（list/dict/str索引/切片/变更） | `tests/contracts/test_collection_semantics.py` |
| 冗余侧表禁止（node_protection 等已废弃侧表不残留） | `tests/contracts/test_no_redundant_side_tables.py` |

## Kernel 层

| 概念 | 测试入口 |
|------|----------|
| SpecRegistry.resolve_call_return 统一入口 | `tests/kernel/test_resolve_call_return.py` |

## 编译器 — 语义分析

| 概念 | 测试入口 |
|------|----------|
| SemanticAnalyzer 集成（4-Phase pipeline 端到端） | `tests/compiler/semantic/test_analyzer.py` |
| BindingAnalysisPass / BehaviorDependencyPass | `tests/compiler/semantic/test_binding_analysis_pass.py` |
| 方法覆写 / super 调用语义 | `tests/compiler/semantic/test_override_and_super.py` |
| super() e2e 运行时分发（init / method / 多级继承） | `tests/e2e/test_e2e_classes.py::TestE2ESuperCall` |
| Pass 2 警告（unused / shadow 等）| `tests/compiler/semantic/test_p2_warnings.py` |
| 各 Pass 回归修复集 | `tests/compiler/semantic/test_pass_fixes.py` |
| ScopedVisitor 基类 | `tests/compiler/semantic/test_scoped_visitor.py` |
| TypeInferenceState 数据结构 | `tests/compiler/semantic/test_type_inference_state.py` |
| 类型系统（auto lock / any / resolve_op / llmexcept body） | `tests/compiler/semantic/test_type_system.py` |

## 编译器 — 其它

| 概念 | 测试入口 |
|------|----------|
| Lexer | `tests/compiler/test_lexer.py` |
| Pipeline 整体（compile_string / 各 Pass 集成） | `tests/compiler/test_pipeline.py` |
| ``list[T]`` / ``dict[K,V]`` 泛型 — 早缓存 / 写方法 / 协变 / 嵌套 | `tests/compiler/test_generics.py` |
| ``Optional[T]`` / ``fn[(in)->(out)]`` / ``tuple[T1,T2,...]`` 类型标注 | `tests/compiler/test_type_annotations.py` |
| import 位置限制 | `tests/compiler/test_import_position.py` |
| SymbolCollectionPass | `tests/compiler/test_symbol_collection_pass.py` |

## 作用域 / 闭包 / 对象层

| 概念 | 测试入口 |
|------|----------|
| lambda / snapshot / behavior 高阶函数（e2e） | `tests/e2e/test_e2e_higher_order.py` |
| 内存模型（公理 SC-3/4、LT-2/3） | `tests/compliance/test_memory_model.py` |

## 意图系统

| 概念 | 测试入口 |
|------|----------|
| 意图 e2e（注释 / scope 隔离 / lambda 交互 / 统一路径 / retry 还原） | `tests/e2e/test_e2e_intent.py` |

## llmexcept

| 概念 | 测试入口 |
|------|----------|
| e2e 行为（基本 / 嵌套 / for 循环 / 条件驱动 / 用户对象 __snapshot__ 协议） | `tests/e2e/test_e2e_llmexcept.py` |

## 异常体系

| 概念 | 测试入口 |
|------|----------|
| LLM 异常层级（E5）+ 用户自定义异常 + ``Exception.__init__`` | `tests/e2e/test_e2e_exceptions.py` |

## 端到端语言语义（e2e）

| 概念 | 测试入口 |
|------|----------|
| 类 / 继承 / 方法 / 字段 | `tests/e2e/test_e2e_classes.py` |
| import / 跨模块 | `tests/e2e/test_e2e_modules.py` |
| LLM 基础（MOCK 协议 / behavior 表达式 / LLM 函数 / cast / control flow / mock repair / stale 隔离） | `tests/e2e/test_e2e_llm_basic.py` |
| LLM 流水线（dispatch / future / DDG e2e 验证） | `tests/e2e/test_e2e_llm_pipeline.py` |
| 多 Interpreter 隔离 | `tests/e2e/test_e2e_multi_interpreter.py` + `tests/compliance/test_execution_isolation.py` |

## 插件 / SDK

| 概念 | 测试入口 |
|------|----------|
| 各插件实现（math / json / time / 等） | `tests/runtime/test_plugin_implementations.py` |
| idbg 调试插件 | `tests/runtime/test_idbg.py` |
| SDK：check_plugin / gen_spec | `tests/sdk/test_check_plugin.py` / `tests/sdk/test_gen_spec.py` |

## 合规（公开 API 黑盒）

| 概念 | 测试入口 |
|------|----------|
| 并发 LLM dispatch（SPEC §3） | `tests/compliance/test_concurrent_llm.py` |
| 多 Interpreter 执行隔离（SPEC §4） | `tests/compliance/test_execution_isolation.py` |
| 内存模型（SPEC §2） | `tests/compliance/test_memory_model.py` |

## 元测试

| 概念 | 测试入口 |
|------|----------|
| 禁止 helper 重复定义 | `tests/meta/test_no_duplicate_helpers.py` |

---

## 共享 fixture / helper 入口

| 层 | conftest |
|----|----------|
| 全局（所有 `tests/`） | `tests/conftest.py` — `run_ibci` / `compile_ibci` / `compile_or_errors` / `expect_compile_error` / `expect_runtime_error` / `make_vm` / `find_node` / `native` / `make_intent` / `AI_MOCK_PREFIX` / `engine` / `engine_session` |
| Kernel | `tests/kernel/conftest.py` — `ax_reg` / `axiom_registry` / `spec_reg` / `factory` |
| Compiler/Semantic | `tests/compiler/semantic/conftest.py` — `make_context` / `spec_registry` |
| Compliance | `tests/compliance/conftest.py` — `compliance_root` / `make_compliance_engine` / `run_compliance_code` |
| Fixtures | `tests/fixtures/` — 可复用 IBCI 代码样本（type_system / control_flow / llm） |

**严禁在测试文件中重复定义这些 helper / fixture。** 详见 `tests/README.md`。

---

## 统计快照

> **数字纪律**：以下指标会随开发持续增长，**请以当次 `python -m pytest tests/ -q --tb=no --no-header` 实跑为准**。
> 本表不再冻结具体计数；最新基线锚点见 `docs/NEXT_STEPS.md` 顶部或 `docs/COMPLETED.md` 最新条目。
>
> 历史快照（2026-05-26）：41 文件 / 781 用例 / 778 passed / 3 skipped。当前基线已大幅增长（含多模态 file I/O、序列化 round-trip、engine 生命周期、host collect、MOCK 指令、路径、层级元测试等新增文件）。

| 指标 | 值 |
|------|-----|
| 运行命令 | `python -m pytest tests/ -q --tb=no --no-header` |
| 最新基线 | 见 `docs/NEXT_STEPS.md` 顶部锚点（不在此冻结） |
