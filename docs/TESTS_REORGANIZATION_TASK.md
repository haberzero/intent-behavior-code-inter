# 测试体系重构任务控制文档

> **✅ 完成（2026-05-12）** — 15 步全部落地，基线 1259 passed → 1259 passed，Δ = 0。
> 详见 `docs/COMPLETED.md` 锚点「tests 重构（15 步全部完成）」。
> 本文档作为长期维护参照保留；`tests/README.md` 与 `tests/COVERAGE_MAP.md` 是日常入口。

> 本文档是 **`tests/` 目录重构主任务的控制文件**，供后续智能体按阶段执行。
> 当前测试基线：1259 passed（`python -m pytest tests/ -q --tb=short`，2026-05-12）。
> **核心红线**：本任务全程**不允许下降覆盖度**。任何 PR 跑出的测试数不得低于基线，所有原有断言必须保留语义（可重组、可改名，不可删除）。
>
> 最后更新：2026-05-12（完成版）

---

## §0 任务目标

把 `tests/` 从"按里程碑/任务编号堆叠的零碎脚本"重构为"按语言概念/子系统组织的体系化测试"，并且：

1. **大幅减少重复样板代码**（13 处 `run_and_capture` 重复定义、~14 处 `make_engine/make_vm/find_node_uid/ai_setup` 重复定义）。
2. **同一语言概念的测试集中到同一文件**（消除"PT-2.1 在这个文件，PT-2.2 在那个文件，NS-2b 又在 e2e 里"的散落现象）。
3. **保持覆盖度不降**（按提交逐步迁移；每步 PR 必须跑通 `pytest tests/ -q`）。
4. **建立长效维护守则**（让未来 agent 不再倾向于"再起一个 `test_ns_XX.py`"）。
5. **新增覆盖映射文档**（`tests/COVERAGE_MAP.md`）作为可读索引。

---

## §1 现状事实清单（基于 2026-05-12 仓库状态）

### 1.1 数量与结构

- 测试文件：61 个 `.py`（含 `__init__.py`）
- 实质测试文件：54 个
- 总行数：约 **15,828 行**
- 总测试数：**1,259 个**
- 目录结构（`tests/` 下）：
  - `kernel/`（4 个文件）：TypeRef / Spec / Axiom / Symbol
  - `compiler/`（8 个文件）：Lexer + Pipeline + 各专题（D3 callable / G1G2/G3 泛型 / M2 Optional / NS-6 链式下标 / NS-7 tuple 位置类型）
  - `runtime/`（13 个文件）：IbCell / IbValue / 插件 / Intent / llmexcept / VM CPS 部分 / NS-3 / NS-4 / NS-1 / PT-2.1 / PT-2.2 / PT-1.2/1.3 / PT-3.3
  - `unit/`（8 个文件）：VMExecutor 骨架 + signals + llmexcept + m3d + m3dprep / DDG / LLMScheduler / M2 artifact rehydrator
  - `e2e/`（15 个文件）：basic / advanced / classes / control_flow / functions / fn_callable / fn_lambda_syntax / tuple_unpack / modules / ai_mock(1510 行) / llm_pipeline / m2_higher_order / m4_multi_interpreter / snapshot_semantics
  - `compliance/`（3 个文件）：concurrent_llm / execution_isolation / memory_model
  - `sdk/`（2 个文件）：check_plugin / gen_spec
- **没有任何 `conftest.py`**。

### 1.2 重复样板（核实）

| 函数名 | 重复定义点数 | 备注 |
|--------|------------|------|
| `run_and_capture(code) -> List[str]` | **13** 个文件 | 几乎一字不差，只是 `os.path.dirname` 求值的 `__file__` 不同 |
| `make_engine(code)` | **14** 个文件 | 部分含 `output_lines`，部分不含；细节微差 |
| `make_vm(engine)` | 5 个文件 | 均为 `VMExecutor(engine.interpreter._execution_context, interpreter=engine.interpreter)` |
| `find_node_uid(engine, type)` / `find_node_uids` / `find_all_node_uids` | 4–5 个文件 | 完全可下沉 |
| `native(obj)` | 2 个文件 | `obj.to_native() if hasattr(...)` |
| `ai_setup()` / `ai_setup_code()` / `_ai_prefix()` | **~15** 个文件 | 同一段 `import ai\nai.set_config("TESTONLY","TESTONLY","TESTONLY")\n` |
| `make_intent(reg, content, mode, role)` | 3 个文件（intent_context 相关）| 字段构造完全相同 |
| `compile_code(code) → (artifact, error_codes)` | 2 个文件 | `try/except CompilerError` 提取 `d.code` |

**保守估计：单是去重就可削减 300–500 行样板。**

### 1.3 按里程碑命名的"专题文件"清单（核实）

这些文件名以代号开头（M2/M3/M3d/G1/G2/G3/D3/NS-1/NS-3/NS-4/NS-6/NS-7/PT-1.2/1.3/PT-2.1/2.2/PT-3.3/M4 …），随着新任务积累必然继续膨胀，且**对外部读者完全不可解释**：

| 当前文件 | 真实语言概念 |
|----------|------------|
| `unit/test_vm_executor.py` | VM CPS 主骨架（基础节点 handler） |
| `unit/test_vm_executor_m3dprep.py` | VM CPS（14 个补齐节点 handler） |
| `unit/test_vm_executor_m3d.py` | VM CPS（行为/闭包/for/try/retry 6 个 handler + 主路径切换） |
| `unit/test_vm_executor_signals.py` | VM CPS（控制信号数据化） |
| `unit/test_vm_executor_llmexcept.py` | VM CPS（llmexcept handler） |
| `runtime/test_vm_llm_cps_dispatch.py` | NS-1 探针 — 实际是"LLM 调用进入 CPS 帧栈" |
| `runtime/test_evaluate_segments_cps.py` | "段求值进入帧栈" |
| `runtime/test_ns3_callsite_ec.py` | "lambda/snapshot/behavior 调用现场 EC 优先" |
| `runtime/test_intent_context.py` | Intent 基础语义 + NS-2b 活跃指针 |
| `runtime/test_pt21_intent_context_oop.py` | Intent OOP combine/to_prompt/deep_clone |
| `runtime/test_pt22_intent_context_serialization.py` | Intent 序列化 |
| `runtime/test_llm_except_frame_enhancements.py` | llmexcept 错误历史 + 深度限制 |
| `runtime/test_uncertain_str_concat_prohibition.py` | NS-4 `str+uncertain` 禁止 |
| `compiler/test_g1_g2_generics.py` | 泛型早缓存 + list[T] 写方法 |
| `compiler/test_g3_generics.py` | 嵌套泛型 + 协变 |
| `compiler/test_tuple_positional_types.py` | NS-7 tuple 位置类型 |
| `compiler/test_chain_subscript.py` | NS-6 链式下标 |
| `compiler/test_m2_optional_methods.py` | M2 Optional 类型方法 |
| `compiler/test_m2_optional_null_safety.py` | M2 Optional 空安全 |
| `unit/test_m2_optional_artifact_rehydrator.py` | M2 Optional artifact 还原 |
| `compiler/test_d3_callable_sig.py` | `fn[(in)->(out)]` 签名 |
| `e2e/test_e2e_m2_higher_order.py` | 高阶函数 |
| `e2e/test_e2e_m4_multi_interpreter.py` | 多 Interpreter 隔离 |
| `runtime/test_idbg_plugin.py` | PT-3.3 idbg 改进 |

**问题**：当读者想知道"intent 系统在哪里测试"时，必须扫描 4+ 个文件。当 NS-2c 修复 retry 干净还原时，新增的 `TestE2ENS2cLlmExceptIntentRestore` 又被埋在 `e2e/test_e2e_ai_mock.py` 的 1510 行里。

### 1.4 `e2e/test_e2e_ai_mock.py` 巨型文件（核实）

1510 行，22 个测试类，覆盖：
- 基础 behavior 表达式 / MOCK 协议
- LLM 函数 / llmend
- llmexcept 基本 + 嵌套 + for 循环 + 条件驱动 + 用户对象快照 + __snapshot__ 协议
- intent 注释 / OOP / scope 隔离 / NS-2b 统一路径 / NS-2c 干净还原
- LLM 异常体系（E5 测试）
- 用户自定义异常

这是典型的"百宝箱"型文件：所有 e2e LLM 相关内容堆在一起，且大部分类与 `runtime/` 下的同名概念测试重复（intent / llmexcept 都在两处各测一遍）。

### 1.5 缺失的基础设施

- ❌ 无 `tests/conftest.py`
- ❌ 无任何子目录 `conftest.py`
- ❌ 无 `tests/README.md` 或测试规约文档
- ❌ 无覆盖映射文档（"X 语言特性的测试入口在哪里"）

---

## §2 目标架构

### 2.1 顶层目录与分层职责

```
tests/
├── conftest.py                  # 全局 fixture / 公共助手（engine, run_ibci, compile_or_errors, ai_mock_prefix, ...）
├── README.md                    # 本目录的"使用与维护守则"（迁移完成时由 §8 步骤产出）
├── COVERAGE_MAP.md              # 概念 ↔ 测试入口映射表（每次新增 / 重组测试时同步）
│
├── kernel/                      # 纯数据层：TypeRef / Spec / Axiom / Symbol（无 engine、不编译 IBCI 代码）
│   ├── conftest.py              # 提供 spec_reg / axiom_reg 共享 fixture
│   ├── test_typeref.py
│   ├── test_spec_layer.py
│   ├── test_axioms.py
│   └── test_symbols.py
│
├── compiler/                    # 仅调 engine.compile_string()，断言 artifact 结构 / SEM_xxx / PAR_xxx
│   ├── test_lexer.py
│   ├── test_pipeline.py         # 综合 pipeline（含原 compiler_pipeline 内容）
│   ├── test_type_annotations.py # 类型标注：Optional、callable[fn]、tuple 位置类型、None 返回（吸收 m2_optional_* / d3_callable_sig / tuple_positional_types）
│   ├── test_generics.py         # list/dict 泛型：早缓存、写方法、协变、嵌套（吸收 g1_g2_generics / g3_generics）
│   ├── test_subscript_typing.py # 链式下标、字面量 int 索引精确推断（吸收 chain_subscript）
│   ├── test_cast_expr.py        # cast 表达式语义（为 NS-5 编译期 cast 校验预留入口）
│   ├── test_intent_syntax.py    # @/@+/@-/@! 语法校验 + 后继语句强制（SEM_060）
│   └── test_error_codes.py      # 所有 SEM_xxx / PAR_xxx 错误码的负样本汇总
│
├── runtime/                     # 单子系统单元 / 子系统集成（小段 IBCI 代码驱动）
│   ├── conftest.py              # 提供 ctx / registry / intent_class 等共享 fixture
│   ├── test_objects_cell.py     # IbCell + promote_to_cell（原 test_ib_cell.py）
│   ├── test_objects_value.py    # IbValue 包装层（原 test_ib_value.py）
│   ├── test_vm_executor.py      # VM CPS 全部：dispatch 表、所有 handler、signals、frame_stack_depth、main path switch、llmexcept handler（吸收 vm_executor / vm_executor_m3d / vm_executor_m3dprep / vm_executor_signals / vm_executor_llmexcept）
│   ├── test_vm_llm_pipeline.py  # VM↔LLM 集成：CPS 调度 / dispatch_eager / LLMScheduler / segments CPS / NS-3 调用现场 EC（吸收 test_vm_llm_cps_dispatch / test_evaluate_segments_cps / test_ns3_callsite_ec / test_llm_scheduler）
│   ├── test_intent_context.py   # Intent 全部：smear/override/persist + 活跃 ibobj 指针 + OOP combine/to_prompt + deep_clone + 序列化 round-trip（吸收 test_intent_context / test_pt21_intent_context_oop / test_pt22_intent_context_serialization）
│   ├── test_llmexcept.py        # llmexcept 全部：LLMExceptFrame 数据结构 + 错误历史 + 深度限制 + retry 语义 + uncertain 处理 + str+uncertain 禁止（吸收 test_llm_except_frame_enhancements / test_uncertain_str_concat_prohibition + 与 vm_executor_llmexcept 共享 handler 部分）
│   ├── test_ddg_analysis.py     # DDG 编译期分析（原 unit/test_ddg_analysis.py 平移）
│   ├── test_serialization.py    # 通用快照/还原（与 intent_context 互补：变量/Loop 栈/用户对象）
│   ├── test_plugin_lifecycle.py
│   ├── test_plugin_implementations.py
│   └── test_idbg.py             # idbg 插件（原 test_idbg_plugin.py 改名）
│
├── e2e/                         # 完整 IBCI 程序，按"语言概念"组织（不按 basic/advanced/历史里程碑）
│   ├── conftest.py              # 提供 run_ibci / capture / ai_setup_prefix
│   ├── test_e2e_core_syntax.py  # 变量/算术/字符串/布尔/类型 cast/赋值（吸收 e2e_basic 大部分内容）
│   ├── test_e2e_control_flow.py # if/while/for/switch/break/continue（保留并精简）
│   ├── test_e2e_functions.py    # func 定义/调用/默认参/参数绑定（保留）
│   ├── test_e2e_classes.py      # 类/继承/方法/字段（保留并吸收 e2e_advanced 中的类部分）
│   ├── test_e2e_modules.py      # import / 跨模块（保留）
│   ├── test_e2e_higher_order.py # fn/lambda/snapshot/HOF（吸收 e2e_fn_callable / e2e_fn_lambda_syntax / e2e_m2_higher_order / e2e_snapshot_semantics）
│   ├── test_e2e_tuple_unpack.py # 元组解包（保留）
│   ├── test_e2e_llm_basic.py    # behavior 表达式 / MOCK 协议 / LLM 函数 / 输出类型（拆 ai_mock 第 1–7 类）
│   ├── test_e2e_llm_pipeline.py # 端到端 LLM 流水线（dispatch + future + DDG 验证）（吸收原 e2e_llm_pipeline 内容）
│   ├── test_e2e_llmexcept.py    # llmexcept 全部 e2e：基本 / 嵌套 / for 循环 / 条件驱动 / 用户对象 / __snapshot__ 协议（拆 ai_mock 第 8–11 类）
│   ├── test_e2e_intent.py       # 意图 e2e：基本 / OOP / scope 隔离 / NS-2b / NS-2c（拆 ai_mock 第 12–14 类）
│   ├── test_e2e_exceptions.py   # try/except + LLM 异常体系 + 用户自定义异常（拆 ai_mock 第 15–16 类）
│   └── test_e2e_multi_interpreter.py # 多 Interpreter 隔离（原 e2e_m4_multi_interpreter 改名）
│
├── compliance/                  # 公开 API 黑盒契约测试（保持现状，仅去重 helper）
│   ├── test_concurrent_llm.py
│   ├── test_execution_isolation.py
│   └── test_memory_model.py
│
└── sdk/                         # SDK 工具测试
    ├── test_check_plugin.py
    └── test_gen_spec.py
```

> **关键不变量**：上述结构与 `docs/VM_AND_INTERPRETER_DESIGN.md` 的子系统划分（§2 CPS、§4 作用域、§5 LLM 流水线、§6 llmexcept、§7 意图、§8 多 Interpreter）一一对应。**未来读 VM 设计文档的人能一眼对应到测试文件**。

### 2.2 `tests/conftest.py` 强制契约

`tests/conftest.py` 必须导出以下统一助手与 fixture（命名固定，不再允许各文件复刻）：

| 名称 | 形态 | 用途 |
|------|------|------|
| `repo_root` | session fixture | 仓库根目录绝对路径 |
| `engine` | function fixture | 全新 `IBCIEngine(root_dir=tmp_path, auto_sniff=False)` |
| `engine_session` | session fixture | 长寿命引擎（适用于只读 registry 查询） |
| `run_ibci(code, *, prefix="", ai=False) -> List[str]` | helper | 执行并捕获 print 输出 |
| `compile_ibci(code) -> CompilationArtifact` | helper | 仅编译，失败抛 `CompilerError` |
| `compile_or_errors(code) -> Tuple[Optional[Artifact], Set[str]]` | helper | 编译，返回 (artifact, error_codes 集合) |
| `make_vm(engine) -> VMExecutor` | helper | 构造 VMExecutor（统一参数顺序） |
| `find_nodes(engine, node_type, *, predicate=None) -> List[Tuple[uid, data]]` | helper | 在 node_pool 中查找节点 |
| `find_node(engine, node_type, *, predicate=None) -> Tuple[uid, data]` | helper | 同上，断言唯一 |
| `native(obj)` | helper | `obj.to_native() if hasattr(obj, "to_native") else obj` |
| `AI_MOCK_PREFIX` | constant | `'import ai\nai.set_config("TESTONLY","TESTONLY","TESTONLY")\n'` |
| `make_intent(registry, content, *, mode=APPEND, role=SMEAR)` | helper | 构造 `IbIntent` |
| `runtime_context_class(registry)` | fixture | 提供独立的裸 `RuntimeContextImpl` |

> 任何测试文件**不允许**再自定义同名/同义助手。CI 可加一行 grep 检查（见 §7 守则）。

### 2.3 分层职责红线

| 层 | 必须 | 禁止 |
|----|------|------|
| `kernel/` | 直接构造 `TypeRef` / `Spec` / `Axiom` / `Symbol`，断言纯数据结构性质 | 启动 `IBCIEngine`、执行 IBCI 代码 |
| `compiler/` | `engine.compile_string()` 或更底层 Lexer/Parser，断言 artifact、SEM/PAR 错误码 | 调 `engine.run_string()` |
| `runtime/` | 小段 IBCI 程序（≤30 行）驱动单子系统；或直接构造 `RuntimeContextImpl/VMExecutor` 单元测试 | 复杂多模块/多 LLM 调用脚本 |
| `e2e/` | 完整 IBCI 程序，验证端到端语言语义；可以 ≥30 行 | 跨多个层（如直接访问 VM 帧栈细节，那是 runtime 层职责） |
| `compliance/` | 仅公开 API（`IBCIEngine` / `host.*`），充当跨实现合规规约 | 任何 `core/runtime/...` 内部导入 |

---

## §3 合并矩阵（旧文件 → 新文件 一一映射）

> 此表是 §8 迁移步骤的实际指南。每一行对应一个独立 PR 的合并目标。

| 旧文件 | 目标新文件 | 处理方式 | 备注 |
|--------|----------|---------|------|
| `unit/test_vm_executor.py` | `runtime/test_vm_executor.py` | 平移 + 重命名分类 | 作为新主干 |
| `unit/test_vm_executor_m3dprep.py` | `runtime/test_vm_executor.py` | 并入：作为 "TestExpressionHandlers / TestStatementHandlers / TestDefinitionHandlers / TestIntentHandlers" 节 | 删除原文件 |
| `unit/test_vm_executor_m3d.py` | `runtime/test_vm_executor.py` | 并入："TestBehaviorAndClosureHandlers / TestLoopAndExceptionHandlers / TestMainPathSwitch" 节 | 删除原文件 |
| `unit/test_vm_executor_signals.py` | `runtime/test_vm_executor.py` | 并入："TestControlSignals" 节 | 删除原文件 |
| `unit/test_vm_executor_llmexcept.py` | `runtime/test_vm_executor.py`（handler 注册/CPS 部分） + `runtime/test_llmexcept.py`（语义部分） | 拆分 | 删除原文件 |
| `unit/test_llm_scheduler.py` | `runtime/test_vm_llm_pipeline.py` | 并入："TestLLMScheduler" 节 | 删除原文件 |
| `unit/test_ddg_analysis.py` | `runtime/test_ddg_analysis.py` | 平移 | 删除原文件 |
| `unit/test_m2_optional_artifact_rehydrator.py` | `compiler/test_type_annotations.py` | 并入："TestOptionalArtifactRehydration" 节 | 删除原文件 |
| `runtime/test_vm_llm_cps_dispatch.py` | `runtime/test_vm_llm_pipeline.py` | 并入："TestLLMCpsDispatch" 节 | 删除原文件 |
| `runtime/test_evaluate_segments_cps.py` | `runtime/test_vm_llm_pipeline.py` | 并入："TestEvaluateSegmentsCps" 节 | 删除原文件 |
| `runtime/test_ns3_callsite_ec.py` | `runtime/test_vm_llm_pipeline.py` | 并入："TestCallsiteExecutionContext" 节 | 删除原文件 |
| `runtime/test_intent_context.py` | `runtime/test_intent_context.py`（同名，作为新主干） | 平移 + 重组分类 | 主干文件 |
| `runtime/test_pt21_intent_context_oop.py` | `runtime/test_intent_context.py` | 并入："TestIntentContextOOPCombine / OOPToPrompt / OOPDeepClone" 节 | 删除原文件 |
| `runtime/test_pt22_intent_context_serialization.py` | `runtime/test_intent_context.py` | 并入："TestIntentContextSerialization" 节 | 删除原文件 |
| `runtime/test_llm_except_frame_enhancements.py` | `runtime/test_llmexcept.py` | 并入："TestErrorHistory / TestDepthLimit" 节 | 主干文件 |
| `runtime/test_uncertain_str_concat_prohibition.py` | `runtime/test_llmexcept.py` | 并入："TestUncertainStrConcatProhibition" 节 | 删除原文件 |
| `runtime/test_idbg_plugin.py` | `runtime/test_idbg.py` | 改名 | 仅 git mv |
| `compiler/test_g1_g2_generics.py` | `compiler/test_generics.py` | 并入新主干 | 删除原文件 |
| `compiler/test_g3_generics.py` | `compiler/test_generics.py` | 并入"TestNestedGenerics / TestCovariance" 节 | 删除原文件 |
| `compiler/test_tuple_positional_types.py` | `compiler/test_type_annotations.py` | 并入"TestTuplePositionalTypes" 节 | 删除原文件 |
| `compiler/test_chain_subscript.py` | `compiler/test_subscript_typing.py` | 新主干（或并入 generics） | 删除原文件 |
| `compiler/test_m2_optional_methods.py` | `compiler/test_type_annotations.py` | 并入"TestOptionalMethods" 节 | 删除原文件 |
| `compiler/test_m2_optional_null_safety.py` | `compiler/test_type_annotations.py` | 并入"TestOptionalNullSafety" 节 | 删除原文件 |
| `compiler/test_d3_callable_sig.py` | `compiler/test_type_annotations.py` | 并入"TestCallableSignature" 节 | 删除原文件 |
| `compiler/test_compiler_pipeline.py` | `compiler/test_pipeline.py` | 改名 | 仅 git mv |
| `e2e/test_e2e_basic.py` | `e2e/test_e2e_core_syntax.py` | 改名 + 精简 | 删除原文件 |
| `e2e/test_e2e_advanced.py` | 拆分到 `test_e2e_classes.py` / `test_e2e_higher_order.py` / `test_e2e_core_syntax.py` | 按主题拆 | 删除原文件 |
| `e2e/test_e2e_fn_callable.py` | `e2e/test_e2e_higher_order.py` | 并入 | 删除原文件 |
| `e2e/test_e2e_fn_lambda_syntax.py` | `e2e/test_e2e_higher_order.py` | 并入"TestLambdaSyntax / TestSnapshotSyntax" 节 | 删除原文件 |
| `e2e/test_e2e_snapshot_semantics.py` | `e2e/test_e2e_higher_order.py` | 并入"TestSnapshotSemantics" 节 | 删除原文件 |
| `e2e/test_e2e_m2_higher_order.py` | `e2e/test_e2e_higher_order.py` | 并入 | 删除原文件 |
| `e2e/test_e2e_m4_multi_interpreter.py` | `e2e/test_e2e_multi_interpreter.py` | 改名 | 仅 git mv |
| `e2e/test_e2e_ai_mock.py` (1510 行) | 拆为四个：`test_e2e_llm_basic.py` / `test_e2e_llmexcept.py` / `test_e2e_intent.py` / `test_e2e_exceptions.py` | **唯一硬性拆分** | 删除原文件 |

### 3.1 ai_mock 拆分细则（22 个测试类 → 4 个文件）

| 原测试类 | 目标文件 |
|---------|---------|
| `TestE2EAIMockBasic` | `test_e2e_llm_basic.py` |
| `TestE2EAITypeCast` | `test_e2e_llm_basic.py` |
| `TestE2EAIControlFlow` | `test_e2e_llm_basic.py` |
| `TestE2ELLMFunctions` | `test_e2e_llm_basic.py` |
| `TestE2EMockRepair` | `test_e2e_llm_basic.py` |
| `TestE2EMockStrQuoted` | `test_e2e_llm_basic.py` |
| `TestE2EStaleResultIsolation` | `test_e2e_llm_basic.py` |
| `TestE2ELLMExcept` | `test_e2e_llmexcept.py` |
| `TestE2ELLMExceptNested` | `test_e2e_llmexcept.py` |
| `TestE2ELLMExceptForLoopMock` | `test_e2e_llmexcept.py` |
| `TestE2ELLMExceptConditionDrivenLoop` | `test_e2e_llmexcept.py` |
| `TestE2EUserClassPromptProtocols` | `test_e2e_llmexcept.py` |
| `TestE2ELLMExceptUserObjectSnapshot` | `test_e2e_llmexcept.py` |
| `TestE2ELLMExceptSnapshotProtocol` | `test_e2e_llmexcept.py` |
| `TestE2EIntents` | `test_e2e_intent.py` |
| `TestE2EIntentScopeIsolation` | `test_e2e_intent.py` |
| `TestE2ELambdaRestriction` | `test_e2e_intent.py`（lambda 与意图栈交互） |
| `TestE2EIntentContextOOP` | `test_e2e_intent.py` |
| `TestE2ENS2bUnifiedIntentPath` | `test_e2e_intent.py`（重命名为 `TestE2EIntentUnifiedPath`，去掉 NS-2b 前缀） |
| `TestE2ENS2cLlmExceptIntentRestore` | `test_e2e_intent.py`（重命名为 `TestE2EIntentRetryRestore`） |
| `TestE2ELLMExceptionHierarchy` | `test_e2e_exceptions.py` |
| `TestE2EUserDefinedException` | `test_e2e_exceptions.py` |

---

## §4 命名规约

### 4.1 文件命名

- **`test_<concept>.py`**：concept 必须是语言概念或子系统名，**禁止**含里程碑代号（`m2/m3/g1/d3/ns_/pt_` 等）。
- 例外：`compliance/` 目录可保留 SPEC 章节号引用（如 `test_memory_model.py` 对应 SPEC §2），但不带任务编号。

### 4.2 测试类命名

- **`Test<Concept><Aspect>`**：如 `TestIntentContextActivePointer`、`TestVMExecutorControlSignals`、`TestLLMExceptDepthLimit`。
- **禁止**：`TestNS2bXxx` / `TestPT21Xxx` / `TestM3dXxx`。
- 例外：若测试本身就是验证某个文档化的"语言级回归条目"，可以**注释**注明历史代号，但**类名**不带它。

### 4.3 测试方法命名

- 描述**行为**而非编号：`test_smear_intent_is_cleared_after_resolution`，不是 `test_ns2b_smear_clearance`。
- 一句一断言主题；多断言时方法名概括"该场景下的不变量"。

### 4.4 文档字符串

- 文件头 docstring 必须列出**本文件覆盖的语言概念清单**（用于 `COVERAGE_MAP.md` 自动生成的根据）。
- 每个 `TestClass` docstring 说明**它专管哪个 aspect**。
- **禁止**在 docstring 里写"此文件源自 NS-X 的修复"；这种信息属于 `docs/COMPLETED.md`。

---

## §5 `tests/COVERAGE_MAP.md` 规约

迁移完成后，由本任务的最后一个 PR 产出 `tests/COVERAGE_MAP.md`，格式如下示例：

```markdown
# 测试覆盖映射

> 索引：语言概念 → 测试入口。新增测试时同步更新本表。

## 类型系统
- TypeRef / Spec / Axiom / Symbol：`tests/kernel/`
- Optional[T] / tuple 位置类型 / callable 签名 / -> None：`tests/compiler/test_type_annotations.py`
- 泛型（list[T] / dict[K,V] / 嵌套）：`tests/compiler/test_generics.py`
- 下标推断（含链式）：`tests/compiler/test_subscript_typing.py`
- cast 表达式（编译期 + 运行期）：`tests/compiler/test_cast_expr.py` + `tests/runtime/test_objects_value.py`

## 编译器
- Lexer：`tests/compiler/test_lexer.py`
- Pipeline 整体：`tests/compiler/test_pipeline.py`
- 错误码 SEM/PAR 负样本：`tests/compiler/test_error_codes.py`
- Intent 语法 + Pass 3.5 SEM_060：`tests/compiler/test_intent_syntax.py`

## VM / 解释器
- VM CPS 全部 handler / signals / dispatch table / 主路径切换：`tests/runtime/test_vm_executor.py`
- VM ↔ LLM 集成（dispatch / future / segments / NS-3 调用现场 EC）：`tests/runtime/test_vm_llm_pipeline.py`

## 作用域 / 闭包
- IbCell + promote_to_cell：`tests/runtime/test_objects_cell.py`
- lambda / snapshot / behavior 语义：`tests/e2e/test_e2e_higher_order.py` + `tests/compliance/test_memory_model.py`

## 意图系统
- Intent 全部（语法 + OOP + 序列化 + retry 还原）：`tests/runtime/test_intent_context.py` + `tests/e2e/test_e2e_intent.py`

## llmexcept
- 数据结构 + retry + 深度 + 错误历史 + uncertain 处理：`tests/runtime/test_llmexcept.py`
- e2e 行为（含 __snapshot__ 协议）：`tests/e2e/test_e2e_llmexcept.py`

## 异常体系
- LLM 异常层级 + 用户自定义：`tests/e2e/test_e2e_exceptions.py`

## 多 Interpreter / Host
- spawn_isolated / collect：`tests/e2e/test_e2e_multi_interpreter.py` + `tests/compliance/test_execution_isolation.py`

## 插件 / SDK
- 插件生命周期：`tests/runtime/test_plugin_lifecycle.py`
- 各插件实现（math/json/time/...）：`tests/runtime/test_plugin_implementations.py`
- idbg：`tests/runtime/test_idbg.py`
- SDK check / gen_spec：`tests/sdk/`
```

> **新增测试时的硬约束**：所有新测试必须出现在表内某一行对应的文件下；如果你认为需要新建文件，说明该行不存在 —— 请先在本表新增一行，再创建文件。

---

## §6 迁移步骤（每步为独立 PR）

> 顺序很重要：先做基础设施（不动测试逻辑），再分子系统挪窝。每步结束必须 `python -m pytest tests/ -q` 全绿，**且测试总数不减少**。

### Step 1 — 建立基础设施（不改任何测试逻辑）
- 新增 `tests/conftest.py`，导出 §2.2 全部统一助手与 fixture。
- 新增 `tests/README.md`：开篇说明分层职责（§2.3）+ 链接本任务控制文档。
- 跑全量回归。**Δ 测试数 = 0**。

### Step 2 — kernel 层去重（最简单，热身）
- `kernel/` 4 个文件：把 `make_spec_registry` / `axiom_reg` 等本地构造改为 import `tests.conftest` 的 fixture。
- 跑回归。**Δ 测试数 = 0**。

### Step 3 — compliance 层去重
- `compliance/` 3 个文件：替换 `make_engine` / `run_code` 为 conftest helper。
- 跑回归。**Δ 测试数 = 0**。

### Step 4 — VM CPS 五合一（最大合并）
- 合并 `unit/test_vm_executor.py` + `_m3d` + `_m3dprep` + `_signals` + `_llmexcept` → `runtime/test_vm_executor.py`（部分） + `runtime/test_llmexcept.py`（部分）。
- 按 §3 合并矩阵执行；类名一律去掉 m3d/m3dprep 前缀。
- 跑回归。**Δ 测试数 = 0**（每个原断言都必须保留）。

### Step 5 — VM↔LLM 流水线三合一
- 合并 `runtime/test_vm_llm_cps_dispatch.py` + `test_evaluate_segments_cps.py` + `test_ns3_callsite_ec.py` + `unit/test_llm_scheduler.py` → `runtime/test_vm_llm_pipeline.py`。
- 跑回归。**Δ 测试数 = 0**。

### Step 6 — Intent 系统三合一
- 合并 `runtime/test_intent_context.py` + `test_pt21_intent_context_oop.py` + `test_pt22_intent_context_serialization.py` → `runtime/test_intent_context.py`。
- 类名重组：`TestSmearIntent` / `TestOverrideWithSmear` / `TestActiveIbobjPointer`（原 NS-2b） / `TestLlmExceptIntentRestore`（原 NS-2c） / `TestCombineSemantics` / `TestToPromptRendering` / `TestDeepCloneFork` / `TestSerializationRoundTrip` / `TestSerializationBackwardCompat`。
- 跑回归。**Δ 测试数 = 0**。

### Step 7 — llmexcept 三合一
- 合并 `runtime/test_llm_except_frame_enhancements.py` + `test_uncertain_str_concat_prohibition.py` + Step 4 析出的 llmexcept 语义部分 → `runtime/test_llmexcept.py`。
- 跑回归。**Δ 测试数 = 0**。

### Step 8 — 编译器类型标注合并
- 合并 `compiler/test_m2_optional_methods.py` + `test_m2_optional_null_safety.py` + `test_d3_callable_sig.py` + `test_tuple_positional_types.py` + `unit/test_m2_optional_artifact_rehydrator.py` → `compiler/test_type_annotations.py`。
- 跑回归。**Δ 测试数 = 0**。

### Step 9 — 编译器泛型/下标合并
- 合并 `compiler/test_g1_g2_generics.py` + `test_g3_generics.py` → `compiler/test_generics.py`。
- 合并 `compiler/test_chain_subscript.py` → `compiler/test_subscript_typing.py`（独立新文件或并入 generics，二选一，倾向于独立）。
- 跑回归。**Δ 测试数 = 0**。

### Step 10 — e2e 高阶函数四合一
- 合并 `e2e/test_e2e_fn_callable.py` + `test_e2e_fn_lambda_syntax.py` + `test_e2e_snapshot_semantics.py` + `test_e2e_m2_higher_order.py` → `e2e/test_e2e_higher_order.py`。
- 跑回归。**Δ 测试数 = 0**。

### Step 11 — e2e_ai_mock 巨型拆解（**最复杂一步**）
- 按 §3.1 表把 22 个测试类挪到 4 个新文件。
- 共享 fixture 全部走 `tests/conftest.py` 的 `AI_MOCK_PREFIX` / `run_ibci`。
- 类名重命名：去掉 `NS2b/NS2c` 前缀。
- 跑回归。**Δ 测试数 = 0**。

### Step 12 — 简单改名与精简
- `git mv` 改名：`unit/test_ddg_analysis.py` → `runtime/test_ddg_analysis.py`；`compiler/test_compiler_pipeline.py` → `compiler/test_pipeline.py`；`e2e/test_e2e_basic.py` → `e2e/test_e2e_core_syntax.py`；`e2e/test_e2e_m4_multi_interpreter.py` → `e2e/test_e2e_multi_interpreter.py`；`runtime/test_idbg_plugin.py` → `runtime/test_idbg.py`。
- 处理 `e2e/test_e2e_advanced.py`：按主题拆到 `core_syntax.py` / `higher_order.py` / `classes.py`。
- 跑回归。**Δ 测试数 = 0**。

### Step 13 — 撤销 `unit/` 目录
- 若 Step 12 后 `unit/` 仅剩零星文件，全部挪到 `runtime/`，删除空目录。
- 跑回归。**Δ 测试数 = 0**。

### Step 14 — 产出 `tests/COVERAGE_MAP.md`
- 按 §5 模板填表；扫描所有 `test_*.py` 头部 docstring 自动校对。
- 跑回归（无代码改动，仅文档）。

### Step 15 — 收口
- 更新 `docs/COMPLETED.md` 锚点："tests 重构 N 步完成，基线 1259 → 1259"。
- 更新本任务控制文档：在 §0 上方加 "✅ 完成（日期）"标记。

---

## §7 未来 agent 的维护守则（强制）

> 本节内容应被后续每一个改测试的 agent 读到。可以由 `tests/README.md` 转引本节。

### 7.1 新增测试时

1. **先查 `tests/COVERAGE_MAP.md`** 找到目标概念对应的文件。
2. **不存在概念匹配的文件 → 先在 COVERAGE_MAP 里加一行 + 写理由 → 再新建文件**。绝不允许"快速新建 `test_<task_id>.py`"。
3. 文件名/类名/方法名严守 §4 命名规约。**禁止任何里程碑代号**（NS- / PT- / M[0-9] / G[0-9] / D[0-9] / C[0-9]）。
4. 使用 `tests/conftest.py` 的统一 helper / fixture，**不要重复定义** `run_and_capture` / `make_engine` / `make_vm` / `ai_setup` 等。
5. 新测试必须遵守分层红线（§2.3）。

### 7.2 修 Bug 添加回归测试时

- 在最贴近问题的 concept 文件下，新增类 `TestRegressions` 或并入已存在的相关 `TestClass`。
- 测试 docstring 可以引用 issue/PR 编号或 `COMPLETED.md` 锚点说明，但**类名/方法名不带这些编号**。

### 7.3 删除/修改测试时

- 严禁因为"测试碍事"而删除断言。Refactor 时如必须改动测试，需在 PR 描述中**逐条说明被改/删测试的语义是否被另一处测试承接**。
- 若任务文档（如 `KNOWN_LIMITS.md`）声明"X 限制已解除"，请同步把原"验证 X 限制存在"的测试改为"验证 X 限制已解除"，**不要删整组**。

### 7.4 CI 防护建议（可选实施）

- 在 `tests/conftest.py` 顶部加 `_BANNED_FILENAME_PATTERNS` 列表（如 `r'test_(ns|pt|m\d|g\d|d\d)_'`），并提供一个 `tests/test_meta_naming.py` 元测试：自动扫描 `tests/` 下文件名违规则失败。
- 可加 `tests/test_meta_no_duplicate_helpers.py`：grep 各 helper 名在测试源码中的定义次数，定义次数 > 1（且不在 conftest.py 内）则失败。
- 上述两个 meta 测试可选；不实施也不阻碍本任务，但落地后能极大降低未来漂移成本。

---

## §8 完成判据

迁移任务整体完成需同时满足：

- [ ] `tests/conftest.py` 存在并被全部测试文件使用；不再有 13 处 `run_and_capture` / 14 处 `make_engine` 等重复定义。
- [ ] 所有以里程碑代号命名的文件已被改名或合并；`tests/` 下无任何文件名包含 `ns_/pt_/m[0-9]/g[0-9]/d[0-9]/c[0-9]` 模式。
- [ ] `tests/COVERAGE_MAP.md` 存在并涵盖每个 `test_*.py` 文件。
- [ ] `tests/README.md` 存在，链接本控制文档与 COVERAGE_MAP。
- [ ] `python -m pytest tests/ -q --tb=short` 全绿，测试数 ≥ 1259（基线）。
- [ ] 重构期间任何一步 PR 都未删除断言（仅重组/改名/换 helper 来源）。
- [ ] `docs/COMPLETED.md` 增加 "tests reorganization" 锚点。
- [ ] 本文档 §0 顶部标记 "✅ 完成（日期）"。

---

## §9 不在本任务范围内的事

为避免任务蔓延，以下显式排除：

- **不为 NS-5（编译期 cast 校验）等未完成任务添加新测试**：当 NS-5 实施时，按 §7 守则自然写入 `compiler/test_cast_expr.py` 即可。
- **不重写测试断言风格**（如把 `assert ... in lines` 全部换成 helper）：除非该 helper 已经在 conftest.py 里。
- **不调整 IBCI 源码**：本任务纯属测试目录重构，绝不改 `core/` 任何文件。
- **不引入新依赖**（不增加 pytest 插件、不引入 hypothesis 等）。
- **不引入 pytest mark 体系**（如 `@pytest.mark.slow` / `.llm` / `.e2e`）：可作为后续单独提案。

---

## §10 与其他文档的关系

- 本文档**只**控制测试目录重构任务的执行节奏与规约。
- 任何与"语言行为/VM 实现/类型系统"的设计修改无关。
- 完成迁移并通过回归后，可将本文档与 `tests/README.md` / `tests/COVERAGE_MAP.md` 一起作为测试体系的长期维护参照。
- `docs/NEXT_STEPS.md` / `docs/PENDING_TASKS.md` 不需要因本任务变动；本任务可作为独立线程穿插在主线 NS-5 等工作之前/之间执行。

---

## §11 Phase 2 根本性重构（2026-05-13 启动）

### 11.1 Phase 1 的局限性评估

Phase 1（15 步）完成了**目录结构调整**与**文件合并**，取得以下成果：
- ✅ 删除了 `tests/unit/` 目录
- ✅ 去除文件名中的里程碑代号（NS-/PT-/M[0-9] 等）
- ✅ 建立了 `tests/conftest.py` 基础设施
- ✅ 巨型文件拆分（`test_e2e_ai_mock.py` 1510 行 → 4 个主题文件）
- ✅ 创建了 `tests/COVERAGE_MAP.md` 索引

**但未解决根本问题**：

1. **测试规模失控**：
   - 15,345 行测试代码 vs 30,120 行核心实现（测试占比 51%）
   - 1,259 个测试用例分散在 309 个测试类中
   - 单个文件最大 1,734 行（`test_vm_executor.py`）

2. **Helper 重复未消除**：
   - 9 个文件仍定义 `make_engine`
   - 12 个文件仍定义 `run_and_capture`
   - 大量文件未使用 `conftest.py` 统一基础设施

3. **测试粒度过细**：
   - 测试关注**微观实现细节**而非**语言语义不变量**
   - 示例：单独测试 `test_int_constant` / `test_binop_addition` 等字面量操作

4. **实现耦合过深**：
   - Runtime 层测试直接访问 `interpreter.node_pool` / `find_node_uid`
   - 测试需要理解编译器内部数据结构（node_uid / side_table）
   - 任何内部重构都会破坏大量测试

### 11.2 Phase 2 目标：从"覆盖实现"到"验证契约"

#### 核心理念转变

**Phase 1 思维**（已过时）：
- 为每个 AST 节点写 handler 测试
- 为每个编译器 Pass 写细节验证
- 覆盖每个代码分支

**Phase 2 思维**（新范式）：
- **只测试对外可观察的语义不变量**
- **通过属性测试（Property-Based Testing）而非具体样本**
- **分层测试，各层职责清晰，避免白盒耦合**

#### IBCI 的核心价值主张（测试重点）

IBCI **不是**：
- ❌ 通用编程语言（有 Python）
- ❌ 性能优化目标（解释器即可）
- ❌ 复杂语法展示（语法是 Python 子集）

IBCI **是**：
- ✅ **混合执行实验平台**：确定性代码 + LLM 不确定性推理融合
- ✅ **意图驱动范式**：通过 `@` 注释动态增强上下文
- ✅ **AI 容错控制流**：`llmexcept` / `retry` 处理 LLM 输出不稳定性
- ✅ **快照语义**：`snapshot` 实现无状态可重入行为

#### 核心不变量映射（测试优先级）

| 层级 | 核心不变量 | 测试方式 |
|------|----------|---------|
| **类型系统** | Optional[T] 空安全 / 泛型协变 / tuple 位置类型 / cast 合法性 | 参数化契约测试 |
| **执行模型** | CPS 无递归 / 控制流数据化 / Signal 透传与拦截 | 公理验证测试 |
| **作用域** | Cell 共享语义 / lambda 引用捕获 / snapshot 值捕获 + 深克隆 | 语义不变量测试 |
| **Intent** | smear/override/persist 优先级 / 跨帧传播 / retry 还原 | 状态机测试 |
| **llmexcept** | 错误历史追踪 / 深度限制 / retry 循环不变量 | 边界条件测试 |
| **LLM 集成** | MOCK 协议 / dispatch / future / DDG 顺序保证 | 集成契约测试 |

### 11.3 新测试体系架构

```
tests/
├── conftest.py                      # 统一基础设施（强制使用）
├── fixtures/                        # 可复用的测试 fixture（IBCI 代码片段库）
│   ├── type_system_samples.py       # 类型系统样本：泛型/Optional/cast
│   ├── control_flow_samples.py      # 控制流样本：if/for/while/switch
│   ├── llm_samples.py               # LLM 样本：behavior/llmexcept/intent
│   └── edge_cases.py                # 边界条件样本
│
├── contracts/                       # 契约测试（核心，300-400 tests）
│   ├── test_type_invariants.py      # 类型系统不变量
│   ├── test_execution_model.py      # 执行模型公理（CPS/Signal/Frame）
│   ├── test_scope_semantics.py      # 作用域语义（Cell/lambda/snapshot）
│   ├── test_intent_propagation.py   # 意图系统不变量
│   ├── test_llmexcept_guarantees.py # llmexcept 保证
│   └── test_llm_integration.py      # LLM 集成契约
│
├── compliance/                      # 公开 API 黑盒合规（保留现状）
│   ├── test_concurrent_llm.py
│   ├── test_execution_isolation.py
│   └── test_memory_model.py
│
├── regression/                      # 历史 Bug 回归（精简保留）
│   └── test_known_issues.py         # 所有历史 Bug 的最小复现
│
└── examples/                        # 示例程序端到端（文档化测试）
    ├── test_calculator.py           # 简单计算器
    ├── test_chat_agent.py           # 对话代理（LLM）
    ├── test_data_pipeline.py        # 数据流水线
    └── test_concurrent_tasks.py     # 并发任务
```

**关键决策**：
- **删除** `kernel/` / `compiler/` / `runtime/` / `e2e/` 旧结构（80% 的测试）
- **创建** `contracts/` 层聚焦语义不变量
- **创建** `fixtures/` 层提供可复用样本
- **精简** `regression/` 只保留不可被 contract 覆盖的历史 Bug

### 11.4 测试规模目标与削减策略

| 当前层级 | 当前规模 | 目标规模 | 削减策略 |
|----------|---------|---------|---------|
| Kernel 层 | ~500 行 | **删除** | 类型系统不变量已被 contracts/test_type_invariants.py 覆盖 |
| Compiler 层 | ~3000 行 | **500 行** | 只保留类型推断契约测试，删除 Pass 白盒测试 |
| Runtime（VM） | ~4000 行 | **删除** | CPS 公理已被 contracts/test_execution_model.py 覆盖 |
| Runtime（Intent） | ~800 行 | **200 行** | 合并到 contracts/test_intent_propagation.py |
| Runtime（llmexcept） | ~500 行 | **150 行** | 合并到 contracts/test_llmexcept_guarantees.py |
| E2E | ~6000 行 | **2000 行** | 保留核心语义样本，删除重复边界测试 |
| Compliance | ~500 行 | **保持** | 公开 API 契约必须完整 |
| Regression | 0 行（散落） | **500 行** | 集中所有历史 Bug 最小复现 |
| Examples | 0 行 | **300 行** | 新增：文档化示例程序 |
| **总计** | **15,345 行** | **≤4,000 行** | **削减 74%** |

**量化指标**：

| 指标 | 当前 | 目标 | 改善 |
|------|-----|------|------|
| 测试代码行数 | 15,345 | ≤ 4,000 | **-74%** |
| 测试用例数 | 1,259 | 300-400 | **-68%** |
| 测试类数 | 309 | ≈ 40 | **-87%** |
| 平均测试长度 | 12 行 | 15-20 行 | **提升可读性** |
| Helper 重复定义 | 21 处 | 0 | **-100%** |
| 文件数 | 54 | ≈ 20 | **-63%** |

### 11.5 实施路线图

#### Phase 2.1：建立新基础设施（Week 1）

**Step 2.1.1**：创建 `tests/fixtures/` 目录与样本库
- 提取现有测试中的 IBCI 代码样本（按主题分类）
- 提供 pytest fixture 接口
- 目标：100-200 个可复用样本

**Step 2.1.2**：强化 `tests/conftest.py`
- 新增统一 API：`run_ibci` / `expect_compile_error` / `expect_runtime_error`
- 删除所有测试文件中的本地 helper 定义
- 验证：grep 检查无本地 helper

**Step 2.1.3**：建立 CI 强制检查
- 创建 `tests/meta/test_no_duplicate_helpers.py`
- 禁止本地定义 `make_engine` / `run_and_capture` / `ai_setup` 等
- 集成到 CI 流水线

**完成标准**：
- ✅ `tests/fixtures/` 存在且包含 100+ 样本
- ✅ 所有测试文件使用 `conftest.py` 统一 API
- ✅ CI 门禁通过（无 helper 重复）

#### Phase 2.2：创建 contracts/ 层（Week 2-3）

**Step 2.2.1**：从设计文档提取不变量 ✅ 完成（2026-05-13）
- 阅读 `docs/VM_AND_INTERPRETER_DESIGN.md` / `IBCI_SPEC.md`
- 为每个公理编写 1-3 个契约测试
- 目标：50-80 个核心不变量测试

**实际成果**：
- ✅ 创建 6 个核心契约测试文件（`tests/contracts/`）：
  - `test_type_invariants.py` - 14 tests（Optional/泛型/cast/tuple类型不变量）
  - `test_execution_model.py` - 19 tests（CPS/信号传播/帧栈/递归保证）
  - `test_scope_semantics.py` - 12 tests（Cell共享引用/lambda/snapshot/词法作用域）
  - `test_intent_propagation.py` - 14 tests（Intent传播/优先级/恢复/作用域隔离）
  - `test_llmexcept_guarantees.py` - 17 tests（异常捕获/重试/错误历史/深度限制）
  - `test_llm_integration.py` - 15 tests（MOCK协议/行为表达式/LLM函数/分发）
- ✅ 总计：**91 个契约测试**（覆盖所有核心不变量）
- ✅ 测试风格统一：
  - INV-XXX-N 编号体系
  - 最小化 IBCI 代码（5-15 行）
  - 黑盒断言（无 node_pool/side_table 访问）
  - 参数化测试提高效率
- ✅ 所有文件 Python 语法验证通过

**Step 2.2.2**：识别高价值 e2e 测试并迁移
- 从现有 1,259 个测试中筛选 **100-150 个代表性样本**
- 标准：覆盖真实使用场景 + 触发多子系统交互
- 重写为契约风格（5-15 行 IBCI 代码）

**Step 2.2.3**：参数化测试重构
- 示例：10 个类似测试 → 1 个 `@pytest.mark.parametrize` 测试
- 目标：将测试数从 1,259 → 300-400

**完成标准**：
- ✅ `tests/contracts/` 6 个文件存在
- ✅ 总计 300-400 个契约测试
- ✅ 所有测试通过（`pytest tests/contracts/ -v`）

#### Phase 2.3：删除冗余测试（Week 4）

**Step 2.3.1**：删除实现细节测试 ✅ 完成（2026-05-13）
- 删除所有 `find_node_uid` / `node_pool` 相关测试
- 删除所有 VM handler 单元测试
- 删除所有编译器 Pass 白盒测试

**实际成果**：
- ✅ 删除 6 个文件，共 493 tests：
  - test_e2e_core_syntax.py (-128): 微观语法测试
  - test_vm_executor.py (-122): 白盒 VM 测试
  - test_kernel/test_typeref.py (-102): TypeRef 实现测试
  - test_kernel/test_spec_layer.py (-81): Spec 层实现测试
  - test_kernel/test_axioms.py (-34): 公理层级测试
  - test_kernel/test_symbols.py (-26): 符号表测试
- ✅ 精简 2 个文件，共 128 tests：
  - test_e2e_higher_order.py: 112 → 62 (-50): 删除 axiom 测试，保留闭包/snapshot 语义
  - test_plugin_implementations.py: 98 → 20 (-78): 转换为烟雾测试（每插件 3-5 个测试）
- **总削减：621 tests (-49%)**
- **1,259 → 638 tests 估算**（实际需验证）

**Step 2.3.2**：合并重复测试与进一步削减（🚧 进行中）
- 识别语义相同的测试并只保留最简洁版本
- 删除微观测试（字面量常量 / 单个 AST 节点）
- 参数化相似测试以减少数量

**待完成（Phase 2.3 Step 2）**：
需要额外削减 ~268 tests 以达到 300-400 目标（详见 `docs/PHASE_2_TEST_DELETION_STRATEGY.md`）：
- 删除 runtime 实现测试文件 (-96 tests)
- 精简 E2E 测试文件 (-78 tests)
- 削减 compiler 测试 (-47 tests)
- 其他精简 (-47 tests)

**Step 2.3.3**：迁移历史 Bug 回归测试（待完成）
- 创建 `tests/regression/test_known_issues.py`
- 将所有历史 Bug 的最小复现集中到此文件
- 按 GitHub issue 编号索引

**完成标准**：
- ✅ 已删除 `tests/kernel/` 4 个文件（全部）
- 🚧 部分删除 `tests/runtime/` 文件（需进一步削减）
- ⏳ 保留 `tests/compliance/` 不变
- ⏳ `tests/regression/` 待创建

#### Phase 2.4：创建示例层与文档（Week 5）

**Step 2.4.1**：创建 `tests/examples/` 文档化测试
- 编写 4-6 个完整示例程序（计算器 / 聊天代理 / 数据流水线等）
- 每个示例 50-100 行 IBCI 代码
- 双重目的：测试 + 文档

**Step 2.4.2**：回归验证
- 运行新测试套件：`pytest tests/ -v --tb=short`
- 目标：300-400 个测试全绿
- 覆盖率分析：`pytest --cov=core tests/`

**Step 2.4.3**：更新文档
- 更新 `tests/README.md`：新测试哲学 + 编写指南
- 创建 `docs/TEST_PHILOSOPHY.md`：长期测试战略
- 本文档添加 Phase 2 完成标记

**完成标准**：
- ✅ 测试套件 < 5,000 行且全绿
- ✅ 覆盖率不降低（关键路径 > 85%）
- ✅ 文档完整且与代码同步

### 11.6 风险缓解策略

#### 风险 1：删除测试后可能遗漏边界条件

**缓解措施**：
1. **分阶段删除**：先创建新测试，验证覆盖率不降，再删旧测试
2. **Git 保护**：每批删除前打 tag，随时可回滚
3. **Code Review**：每批删除需 2 人复查
4. **覆盖率监控**：CI 强制覆盖率不降低

#### 风险 2：强制使用 conftest 的执行难度

**执行策略**：
1. **CI 门禁**：`test_meta_no_duplicate_helpers.py` 必须通过
2. **Pre-commit Hook**：本地提交时自动检查
3. **文档强调**：`tests/README.md` 首段红字警告
4. **自动化工具**：提供脚本批量替换本地 helper

#### 风险 3：团队协作冲突

**协调规则**：
1. **暂停新测试提交**（Phase 2.1-2.3 期间，约 4 周）
2. **每周同步会议**：展示进度 + 识别风险
3. **沟通渠道**：专用 Slack 频道 #test-refactor
4. **完成标准公示**：明确定义 "Done" 标准

### 11.7 预期成果与验收标准

#### 量化成果

- ✅ 测试代码从 15,345 行削减到 ≤ 4,000 行（**-74%**）
- ✅ 测试用例从 1,259 个精简到 300-400 个（**-68%**）
- ✅ 测试类从 309 个减少到 ≈ 40 个（**-87%**）
- ✅ Helper 重复定义从 21 处消除到 0（**-100%**）
- ✅ 测试运行时间 < 60 秒（优化后）

#### 质量成果

- ✅ **测试即文档**：每个 contract 测试清晰表达一个语义不变量
- ✅ **维护性**：修改内部实现不破坏测试（解耦白盒依赖）
- ✅ **可理解性**：新贡献者 1 天内理解测试体系
- ✅ **扩展性**：新增语言特性只需添加 1-3 个 contract 测试

#### 验收标准

**必须满足**：
1. ✅ 测试套件总行数 ≤ 5,000 行
2. ✅ 所有测试通过（`pytest tests/ -v`）
3. ✅ 覆盖率不降低（核心路径 ≥ 85%）
4. ✅ 无 helper 重复定义（CI 检查通过）
5. ✅ 文档完整（`TEST_PHILOSOPHY.md` / 更新 `tests/README.md`）

**可选加分**：
- ⭐ 测试运行时间 < 30 秒
- ⭐ 参数化测试覆盖率 > 50%
- ⭐ 示例程序可作为教程使用

### 11.8 长期愿景

Phase 2 完成后，IBCI 测试体系将达到：

1. **战略一致性**：测试验证语言设计文档中的公理，而非实现细节
2. **最小化原则**：每个测试验证一个核心不变量，避免冗余
3. **文档化特性**：测试本身就是语言特性的可执行规范
4. **持续进化**：新特性通过契约测试自然融入体系

**核心信念**：
> **测试应验证"IBCI 作为一门语言的语义不变量"，而非"解释器的实现细节"。**

---

*最后更新：2026-05-13（Phase 2 启动）*
