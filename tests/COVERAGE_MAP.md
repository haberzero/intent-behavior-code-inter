# 测试覆盖映射 (Coverage Map)

> 索引：语言概念 / 子系统 → 测试入口文件。
> **新增测试时必须先在本表找到对应概念的文件；如不存在，先在此表新增一行 + 说明，再创建文件。**
> 详见 `docs/TESTS_REORGANIZATION_TASK.md` §5 与 `tests/README.md` 的维护守则。
>
> 最后更新：2026-05-13（Phase 2 完成）— 测试体系契约化。

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

## 类型系统（Kernel 层已删除，转由契约测试覆盖）

注：Kernel层白盒测试已删除，类型系统不变量由`tests/contracts/test_type_invariants.py`覆盖。

## 类型标注（编译期）

| 概念 | 测试入口 |
|------|----------|
| ``Optional[T]`` 类型方法解析 + 空安全 + artifact 还原 | `tests/compiler/test_type_annotations.py` |
| ``fn[(in)->(out)]`` callable 签名 | `tests/compiler/test_type_annotations.py` |
| ``tuple[T1,T2,...]`` 位置类型推断 | `tests/compiler/test_type_annotations.py` |
| ``list[T]`` / ``dict[K,V]`` 泛型 — 早缓存 / 写方法 / 协变 / 嵌套 | `tests/compiler/test_generics.py` |
| 链式下标 ``(expr)[idx]`` / 字面量 int 索引精确推断 | `tests/compiler/test_subscript_typing.py` |

## 编译器（其它）

| 概念 | 测试入口 |
|------|----------|
| Lexer | `tests/compiler/test_lexer.py` |
| Pipeline 整体（compile_string / 各 Pass 集成）| `tests/compiler/test_pipeline.py` |

## VM / 解释器（运行时核心已删除，转由契约测试覆盖）

注：VM handler白盒测试已删除，执行模型公理由`tests/contracts/test_execution_model.py`覆盖。

| 概念 | 测试入口 |
|------|----------|
| DDG（数据依赖图）编译期分析 | `tests/runtime/test_ddg_analysis.py` |

## 作用域 / 闭包 / 对象层

注：IbCell/IbValue白盒测试已删除，作用域语义由`tests/contracts/test_scope_semantics.py`覆盖。

| 概念 | 测试入口 |
|------|----------|
| lambda / snapshot / behavior 语义（e2e）| `tests/e2e/test_e2e_higher_order.py` |
| 内存模型（公理 SC-3/4、LT-2/3）| `tests/compliance/test_memory_model.py` |

## 意图系统

注：Intent白盒测试已删除，Intent传播不变量由`tests/contracts/test_intent_propagation.py`覆盖。

| 概念 | 测试入口 |
|------|----------|
| 意图 e2e（注释 / scope 隔离 / lambda 交互 / 统一路径 / retry 还原）| `tests/e2e/test_e2e_intent.py` |

## llmexcept

注：llmexcept白盒测试已删除，llmexcept保证由`tests/contracts/test_llmexcept_guarantees.py`覆盖。

| 概念 | 测试入口 |
|------|----------|
| e2e 行为（基本 / 嵌套 / for 循环 / 条件驱动 / 用户对象 __snapshot__ 协议）| `tests/e2e/test_e2e_llmexcept.py` |

## 异常体系

| 概念 | 测试入口 |
|------|----------|
| LLM 异常层级（E5）+ 用户自定义异常 + ``Exception.__init__`` | `tests/e2e/test_e2e_exceptions.py` |

## 端到端语言语义（e2e）

| 概念 | 测试入口 |
|------|----------|
| 变量 / 算术 / 字符串 / 布尔 / 类型 cast / 重赋值 / 列表方法 / dict 方法 / in 运算符 / 三元运算符 / global / is 运算符 / 嵌套作用域 / 复杂综合程序（注：已删除，基础语法由契约测试覆盖） | — |
| 控制流（if/while/for/switch/break/continue）| `tests/e2e/test_e2e_control_flow.py` |
| 函数 / 默认参 / 参数绑定 | `tests/e2e/test_e2e_functions.py` |
| 类 / 继承 / 方法 / 字段 | `tests/e2e/test_e2e_classes.py` |
| import / 跨模块 | `tests/e2e/test_e2e_modules.py` |
| 元组解包 | `tests/e2e/test_e2e_tuple_unpack.py` |
| LLM 基础（MOCK 协议 / behavior 表达式 / LLM 函数 / cast / control flow / mock repair / stale 隔离）| `tests/e2e/test_e2e_llm_basic.py` |
| LLM 流水线（dispatch / future / DDG e2e 验证）| `tests/e2e/test_e2e_llm_pipeline.py` |
| 多 Interpreter 隔离 | `tests/e2e/test_e2e_multi_interpreter.py` + `tests/compliance/test_execution_isolation.py` |

## 插件 / SDK

| 概念 | 测试入口 |
|------|----------|
| 插件生命周期 | `tests/runtime/test_plugin_lifecycle.py` |
| 各插件实现（math / json / time / 等）| `tests/runtime/test_plugin_implementations.py` |
| idbg 调试插件 | `tests/runtime/test_idbg.py` |
| SDK：check_plugin / gen_spec | `tests/sdk/test_check_plugin.py` / `tests/sdk/test_gen_spec.py` |

## 合规（公开 API 黑盒）

| 概念 | 测试入口 |
|------|----------|
| 并发 LLM dispatch（SPEC §3）| `tests/compliance/test_concurrent_llm.py` |
| 多 Interpreter 执行隔离（SPEC §4）| `tests/compliance/test_execution_isolation.py` |
| 内存模型（SPEC §2）| `tests/compliance/test_memory_model.py` |

---

## 共享 fixture / helper 入口

| 层 | conftest |
|----|----------|
| 全局（所有 `tests/`）| `tests/conftest.py` — `run_ibci` / `compile_ibci` / `compile_or_errors` / `make_vm` / `find_node` / `native` / `AI_MOCK_PREFIX` / `engine` / `engine_session` |
| Kernel | `tests/kernel/conftest.py` — 已删除 |
| Compliance | `tests/compliance/conftest.py` — `compliance_root` / `make_compliance_engine` / `run_compliance_code` |
| Fixtures | `tests/fixtures/` — 可复用IBCI代码样本（type_system/control_flow/llm） |

**严禁在测试文件中重复定义这些 helper / fixture。** 详见 `tests/README.md`。

---

## 历史合并锚点

本表对应的目录结构由 `docs/TESTS_REORGANIZATION_TASK.md` 描述的 15 步重构得到。
关键合并：

- 5 个 ``test_vm_executor*`` → `tests/runtime/test_vm_executor.py`（Step 4）
- 4 个 VM↔LLM 流水线文件 → `tests/runtime/test_vm_llm_pipeline.py`（Step 5）
- 3 个 Intent 文件 → `tests/runtime/test_intent_context.py`（Step 6）
- 2 个 llmexcept 文件 → `tests/runtime/test_llmexcept.py`（Step 7）
- 5 个类型标注文件 → `tests/compiler/test_type_annotations.py`（Step 8）
- 2 个泛型文件 → `tests/compiler/test_generics.py`（Step 9）
- 4 个高阶函数 e2e 文件 → `tests/e2e/test_e2e_higher_order.py`（Step 10）
- `test_e2e_ai_mock.py`（1510 行 / 22 类）→ 4 文件 `test_e2e_{llm_basic,llmexcept,intent,exceptions}.py`（Step 11）
- `test_e2e_advanced.py` 拆主题 → `test_e2e_{tuple_unpack,core_syntax}.py`（Step 12）
- `tests/unit/` 撤销（剩 `test_ddg_analysis.py` 移至 `tests/runtime/`）（Step 13）

类名一律去除里程碑代号（NS-/PT-/M2/M3d/M3dprep/G1/G2/G3/D3 等）。
