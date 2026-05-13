# COMPLETED — 极简时间线归档

> 本文档以**极简时间线**记录主线工作的完成节点。
> 设计与实现细节见对应正式文档：`docs/TYPE_SYSTEM_DESIGN.md`、`docs/VM_AND_INTERPRETER_DESIGN.md`、`docs/VM_SPEC.md`、`docs/ARCH_DETAILS.md`。
> 当前最紧要项见 `docs/NEXT_STEPS.md`；阻塞项见 `docs/PENDING_TASKS.md`。
>
> **最后更新**：2026-05-13

---

## 2026-05-13 锚点：代码库健康度全面审计与局部导入清理

完成对 IBCI 代码库的全方位深度审计，识别代码健康度问题并制定重构计划。同时立即清理了所有非必要的局部导入。

**审计范围**：
- 229 个 Python 源文件（44,329 行代码）
- 10 个内置模块插件
- 611 个测试用例
- 23 份技术文档

**主要发现**：
- 8 个文件超过 1000 行（危急）
- 15 个类超过 500 行（严重）
- 26 个函数超过 100 行（需拆分）
- 7 处深层嵌套逻辑（需优化）
- 10 个非必要局部导入（已清理 ✅）
- 28 个架构性局部导入（合理，打破循环依赖）

**交付物**：
- `docs/CODE_HEALTH_REFACTORING.md`（统一的审计与重构指南）

**重构计划概要**：
- Phase 1（Week 1-2）：快速胜利 - 局部导入清理 ✅、LLM 解析优化、semantic_analyzer.py 拆分
- Phase 2（Week 3-5）：核心重构 - handlers.py 模块化、For 循环优化、primitives.py 拆分
- Phase 3（Week 6-8）：补充重构 - llm_executor.py、kernel.py 拆分，剩余逻辑优化

**局部导入清理完成** ✅：
- `ibci_net/core.py`: 移动 requests, base64 至文件顶部（9+ 处清理）
- `ibci_json/core.py`: 移动 copy 至文件顶部
- `ibci_sdk/check.py`: 移动 sys 至文件顶部
- `tests/compiler/test_lexer.py`: 移动 TokenType 至文件顶部
- `tests/compiler/test_type_annotations.py`: 移动 SpecFactory, TypeKind 至文件顶部

**预估工作量**：150-200 开发小时，跨 6-8 周

---

## 2026-05-13 锚点：测试体系契约化重构（Phase 1 + Phase 2 完成）

测试目录从"覆盖实现细节"转向"验证语义不变量"的重构完成。

**Phase 1 成果**（2026-05-12）：
- 建立统一基础设施（tests/conftest.py消除helper重复）
- 去除文件名/类名中的里程碑代号（NS-/PT-/M[0-9]等）
- 建立覆盖映射文档（COVERAGE_MAP.md）
- 15步重构全部完成，目录结构体系化

**Phase 2 成果**（2026-05-13）：
- 创建契约测试系统（tests/contracts/，116个INV-XXX-N不变量测试）
- 删除白盒实现测试（kernel层全部、VM handler单元测试等）
- 建立测试哲学文档（TEST_PHILOSOPHY.md，628行）
- 建立语义覆盖矩阵（SEMANTIC_COVERAGE_MATRIX.md，577行）
- 测试代码从15,345行精简至10,213行（削减33%）
- 测试用例从1,259个优化至~591个（聚焦核心语义）

**重构原则**：测试验证"IBCI作为一门语言的语义不变量"，而非"解释器的实现细节"。

---

## 2026-05-12 锚点：NS-4 / NS-6 / NS-7（语言级语法/类型清理）

三项 NEXT_STEPS 一并收口，回归测试通过。

### NS-4：收紧 `str + llm_uncertain` 隐式拼接

- **编译期**：`StrAxiom.resolve_operation_type_name` 移除 `llm_uncertain` 放行分支；编译期出现该静态类型组合时按常规 SEM_003 处理。
- **运行期**：`IbString.__add__` 检测到 `llm_uncertain` 哨兵时抛 `ThrownException(LLMParseError)`，由 `try/except LLMParseError` 接管；不再隐式 coerce 为 `"uncertain"` 字符串。
- **基础设施**：`IbNativeFunction.call` 显式让 `ThrownException` 穿透原生函数边界，避免被包装成 `InterpreterError`，保证 LLMParseError 等语言级异常能传到 `IbTry` 处理器。
- **用户保留路径**：`(str)uncertain_var` 显式转换仍返回 `"uncertain"` 字符串；`uncertain == Uncertain` 比较与 retry 流程未受影响。
- **测试**：新增 `tests/runtime/test_uncertain_str_concat_prohibition.py`（3 用例：try-except 捕获、显式 cast 保留、公理直接询问）。
- **文档**：删除 `KNOWN_LIMITS.md §八`、收口 `OPEN_ISSUES.md OI-1`。

### NS-6：链式下标 `(expr)[index]` 语法消歧

- **根因修复**：`expression.py:grouping()` 推测块内部的 `ParseControlFlowError` 不再被块内 try/except 吞掉，改由 `with` 外侧的 try/except 接管，避免 speculate 失败时 temp_tracker 被合并（这是历史 PAR_001 误报的根因，也是 `KNOWN_LIMITS §九` 的物理来源）。
- **NS-6 启发规则**：speculate 成功解析出类型节点为 `IbSubscript` 且 RPAREN 之后紧跟 `[` 时，立刻触发 PCFE 回退到分组表达式路径，让 `(value[idx])[idx]` 形态自然走链式下标。
- **回归保护**：`(list[int])arr` / `(int)x` 等正常 cast 不受影响。
- **测试**：新增 `tests/compiler/test_chain_subscript.py`（5 用例：tuple/list/dict 链式下标 + 泛型 cast 与基本 cast 不被误伤）。
- **文档**：删除 `KNOWN_LIMITS.md §九`。

### NS-7：`tuple[T1, T2, ...]` 位置元素类型标注

- **TypeDef 扩展**：新增 `positional_element_types: List[TypeRef]`，与 `LIST.allowed_element_types`（set-like union）正交，仅 TUPLE kind 在元素数 ≥ 2 时使用；单类型元组 `tuple[T]` 维持 `element_type` 单字段路径，向后兼容。
- **SpecFactory.create_tuple**：新增 `positional_element_type_names` 形参；多元素时生成 `tuple[T1,T2,...]` 名称（顺序敏感，不 sort）。
- **TupleAxiom.resolve_specialization_by_names**：元素数 ≥ 2 走位置路径。
- **SpecRegistry.resolve_specialization 早缓存修复**：candidate_key 不再 sort 多参数列表，避免 `tuple[int,str]` 与 `tuple[str,int]` 因排序键碰撞被误命中（这一缓存键 bug 对 dict[K,V] 等位置敏感 spec 也潜在影响，一并修复；list 等 union 容器仍正确，仅可能略有缓存未命中代价）。
- **SemanticAnalyzer.visit_IbSubscript**：当 value_type 是带位置元素的 tuple 且 slice 是字面量 int 常量时，精确返回对应位置类型；越界或变量索引回退到通用 `resolve_subscript` 路径。
- **测试**：新增 `tests/compiler/test_tuple_positional_types.py`（12 用例：位置推断、目标类型不匹配 SEM_003、fallback、协变、顺序敏感、单类型回退、factory 直接 API）。
- **文档**：`KNOWN_LIMITS.md §16.5` 标记 NS-7 已完成。

---

## 2026-05-12 锚点：PT-1.2 / PT-1.3 / PT-3.3（idbg）收口

三项工作按"llmexcept 可追踪性 + 防御性深度限制 + 调试器可观测性"主线一并落地，回归测试通过。

### PT-1.2：LLMExceptFrame 重试历史追踪

- `LLMExceptFrame` 新增 `error_history` 字段（结构化记录 `retry_count/error_type/error_message/response`）。
- `set_error()` 追加历史记录；`reset_for_retry()` 仅清理当前错误态，不清空历史。
- `get_retry_info()` 新增 `error_history_count` 与 `error_history` 输出，供调试器/日志直接消费。

### PT-1.3：LLMExceptFrameStack 最大嵌套深度限制

- `LLMExceptFrameStack` 新增 `max_depth`（默认 128）与溢出检查，超限抛 `RuntimeError`。
- 主运行路径同步施加约束：`RuntimeContextImpl.push_llm_except_frame()` 入栈时检查 `_llm_except_max_depth`，避免仅工具类生效而主路径旁路。

### PT-3.3：idbg 改进（打印输出 + protection_map）

- `idbg.protection_map()` 由空实现改为真实映射构建：
  - `IbLLMExceptionalStmt.target -> handler_uid`
  - `IbFor.llmexcept_handler`（含 `IbFilteredExpr` 解包）条件节点 -> handler_uid
- 新增打印入口：`show_retry_stack()` / `show_env()` / `show_protection_map()`；`show_all()` 扩展为聚合打印 vars/intents/retry/env/protection/prompt/result。
- `ibci_modules/ibci_idbg/_spec.py` 补齐导出方法：`print_vars`、`protection_map`、`show_retry_stack`、`show_protection_map`、`show_env`。

### 测试

- 新增 `tests/runtime/test_llm_except_frame_enhancements.py`（4 个测试）：
  - 错误历史保留
  - `get_retry_info` 历史输出
  - `LLMExceptFrameStack` 深度限制
  - `RuntimeContext` 主路径深度限制
- 新增 `tests/runtime/test_idbg_plugin.py`（3 个测试）：
  - vtable 导出校验
  - protection_map 映射构建
  - `show_protection_map()` 打印输出

---

## 2026-05-12 锚点：NS-3 / PT-2.1 / PT-2.2 / `_evaluate_segments` CPS 化一并收口

四项配套工作按"调用现场优先 / 段求值入帧 / 意图上下文身份贯通"主线一并落地，测试通过。

### NS-3：lambda / snapshot / behavior 跨帧 `_execution_context` 边界

**设计澄清**：lambda 的语义是"调用现场" — 自由变量、意图栈、执行机制（VM、节点池、runtime_context）均取**调用时刻**的值；snapshot 的语义是"定义时冻结自由变量与意图，但执行机制仍是调用现场"；immediate behavior 是一次性的，定义时刻与调用时刻 EC 等价。统一结论：`_execution_context` **字段仅作定义时回退**，CPS 主路径与同步后备路径都必须优先使用调用现场的 EC。

- **CPS 主路径**：`_vm_invoke_behavior` 一律使用 `executor.ec`（VM 当前 EC），完全忽略 `behavior._execution_context` 字段（`core/runtime/vm/handlers.py:_vm_invoke_behavior`）。
- **同步后备路径**：新增 `core/runtime/frame.py::_current_execution_context` ContextVar；`Interpreter.run` / `execute_module` 入口处 `set` / `reset`，`IbBehavior.call` / `IbFnCallable.call` 在缺少显式 EC 时优先读取 ContextVar，仅在 ContextVar 与字段都缺失时报错。
- **测试**：`tests/runtime/test_ns3_callsite_ec.py`（3 个测试，含跨 Interpreter 验证）。

### PT-2.1：intent_context 高级 OOP 场景

- **`IbIntentContext.combine(other)`**：与既有 `merge`（替换语义）互补，提供加法式合并（追加 intent_top / smear / global，遇 override 取后者）；IBCI 端通过 `IntentContextAxiom.get_method_specs` 暴露。
- **`IbIntentContext.__to_prompt__()` / `to_prompt()`**：渲染当前活跃意图列表（intent_top + smear + override），让 `(str)ctx` 与 prompt 段插值 `@~ ... $ctx ... ~` 返回结构化文本。
- **`try_deep_clone` 识别 `IbIntentContext`**：调用 `IbIntentContext.fork()` 取代默认浅拷贝；使 intent_context 作为类字段时 llmexcept 快照 / 恢复获得正确独立副本（与 NS-2c 的 fork-and-replace 链路对齐）。
- **测试**：`tests/runtime/test_pt21_intent_context_oop.py`（12 个测试）。

### PT-2.2：IbIntentContext 序列化 / 反序列化

- **完整 4 槽位序列化**：`RuntimeSerializer._collect_intent_context` 写入 `intent_top` / `smear_queue` / `override` / `global_intents`，取代旧的仅 `intent_stack` 平铺方案；通过 `id(ic) → uid` 备忘表保留共享身份。
- **`IbIntent` 显式分支**：通用 object 分支会丢失 `__slots__` 中的 `content` / `mode` / `tag` / `role` / `pop_top` / `source_uid`；新增 `_type: "intent"` 专用编解码（`core/runtime/serialization/runtime_serializer.py`）。
- **`intent_context` 封装实例**：`_type: "intent_context"` 分支保留 `_ctx` 字段对应的 native UID 引用，反序列化时恢复"wrapper.fields['_ctx'] is rt_ctx._intent_ctx"共享身份不变量（NS-2b 协议）。
- **`serialize_context`**：纳入 `intent_ctx_uid` 与 `active_intent_ibobj_uid`；保留 `intent_stack` 字段用于向后兼容遗留快照。
- **`deserialize_context`**：优先读新格式；活跃指针恢复时强制 `_ctx is rt_ctx._intent_ctx`。
- **`serialize_context.intent_exclusive_depth`** 改为容错（`getattr(..., 0)`），使无 `IStateProvider` 完整实现的精简 `RuntimeContextImpl` 也可序列化。
- **测试**：`tests/runtime/test_pt22_intent_context_serialization.py`（7 个测试，含 round-trip / 共享身份 / wrapper / 向后兼容遗留格式）。

### `_evaluate_segments` CPS 化

- **新增 `_evaluate_segments_cps`**：把 `vm.run(seg)` 替换为 `yield seg`，让 prompt 段中的子节点求值成为外层 VM 帧栈的子任务，而非启动一次新的 `_drive_loop`。
- **新增 `*_cps` 公理化变体**：`execute_behavior_expression_cps` / `execute_behavior_object_cps` / `execute_llm_function_cps` / `invoke_behavior_cps` / `invoke_llm_function_cps`，把 `_evaluate_segments` 调用替换为 `yield from _evaluate_segments_cps`，其它逻辑与同步版完全等价。
- **VM handler 切换**：`_vm_invoke_behavior` / `_vm_invoke_llm_function` 改用 `yield from invoke_*_cps`，消除 `_drive_loop` 重入。
- **同步 `_evaluate_segments` 保留**：作为 `dispatch_eager` 后台线程路径的兼容入口，内部委托给生成器并通过 `vm.run` 驱动；保证非 CPS 调用方语义不变。
- **测试**：`tests/runtime/test_evaluate_segments_cps.py`（4 个测试，含 frame_stack_depth ≥ 1 的嵌套深度验证）；同步刷新 `test_vm_llm_cps_dispatch.py` / `test_ns3_callsite_ec.py` 探针为 `*_cps` 变体。

### 累计影响
- 修改文件：`core/runtime/frame.py`（新增 ContextVar）、`core/runtime/interpreter/interpreter.py`、`core/runtime/objects/builtins.py`、`core/runtime/objects/deep_clone.py`、`core/runtime/objects/intent_context.py`、`core/runtime/vm/handlers.py`、`core/runtime/interpreter/llm_executor.py`、`core/runtime/serialization/runtime_serializer.py`、`core/runtime/bootstrap/builtin_initializer.py`、`core/kernel/axioms/intent_context.py`。
- 新增测试：4 套（NS-3 / PT-2.1 / PT-2.2 / segments CPS）。
- 文档刷新：本文件、`docs/NEXT_STEPS.md`、`docs/PENDING_TASKS.md`、`docs/VM_AND_INTERPRETER_DESIGN.md §12`。
- 回归结果：测试通过。

---

## 2026-05-11 锚点：lambda / snapshot 语义按用户澄清最终对齐

按用户澄清的最终设计（"lambda 不拷贝任何内容；snapshot 提供完全的深克隆，作为完全无状态且可重入的可调用实例存在"）收口 lambda / snapshot：

- **lambda**：保持现状——自由变量经共享 `IbCell` 引用，调用时 deref 当前最新值；意图栈调用时现读（`captured_intents=None`）；**不拷贝任何内容**。
- **snapshot 深克隆**：抽取通用 `core/runtime/objects/deep_clone.py::try_deep_clone`（沿用 `LLMExceptFrame._try_deep_clone` 的语义实现），`LLMExceptFrame` 改为委托调用；`vm_handle_IbLambdaExpr` 在 snapshot 分支下**定义时**对每个自由变量做 `try_deep_clone` 形成只读种子（不再用 `IbCell` 浅包装——旧实现仅复制 cell 容器，内层可变对象引用仍泄漏）。
- **snapshot 调用时再克隆**：`_vm_call_fn_callable` / `_vm_invoke_behavior` / `IbFnCallable.call` / `IbBehavior.call` 在 snapshot 分支下**每次调用前**对种子再做一次 `try_deep_clone` 注入子作用域，使每次调用得到种子的私有副本——同一 snapshot 多次/并发调用之间彼此独立。
- **删除 snapshot 结果缓存**：
  - `IbFnCallable._cache` 字段及全部相关分支（`call` 短路、`to_native` / `__to_prompt__` / `receive` 缓存路径）整体删除——`IbFnCallable` 仅服务 lambda/snapshot，两种模式都不应缓存。
  - `_vm_call_fn_callable` 的无参 snapshot cache 短路 / 写入整体删除。
  - `IbBehavior._cache`：保留给 immediate 行为对象（`capture_mode is None`，值语义的"求值一次后复用"），但在 `IbBehavior.call` / `_vm_invoke_behavior` 进入 lambda/snapshot 路径时强制清零；`execute_behavior_object` 的 cache 读写也用 `capture_mode is None` 闸门，避免对 lambda/snapshot 路径污染。
- **回归覆盖**：新增 `tests/e2e/test_e2e_snapshot_semantics.py`（9 个测试）覆盖定义时深克隆隔离（list/dict/参数化）、调用间重入独立性（list/dict/参数化）、无缓存外层种子不被污染、lambda 引用语义对照。同步刷新 `tests/e2e/test_e2e_fn_lambda_syntax.py` 的过时"caches"描述。
- **文档收敛**：`core/runtime/objects/cell.py` LT-3、`core/kernel/ast.py` `IbLambdaExpr` 语义注释、`docs/TYPE_SYSTEM_DESIGN.md §7.4`、`docs/VM_AND_INTERPRETER_DESIGN.md §4.3`、`docs/VM_SPEC.md §2.4 GC-2`、`docs/INTENT_SYSTEM_DESIGN.md §9.1` 全部刷新为新语义。
- 代码：`core/runtime/objects/deep_clone.py`（新）、`core/runtime/objects/builtins.py`、`core/runtime/vm/handlers.py`、`core/runtime/interpreter/llm_executor.py`、`core/runtime/interpreter/llm_except_frame.py`。
- 回归结果：测试通过。

---

## 2026-05-11 锚点：NS-1 LLM 调用路径合并入 CPS 调度循环

将 `IbBehavior.call()` / `IbLLMFunction.call()` 与 `vm_handle_IbExprStmt` 中的 behavior 同步旁路合并入 VMExecutor 的 CPS 主循环；所有 LLM 调用（行为表达式 / 命名 LLM 函数）触发时，对应 VMTask 都在帧栈上，使 LLM 帧受 VM 调度管理（快照、并发、调试可观察性）。

- **新增 CPS 生成器助手**（`core/runtime/vm/handlers.py`）：
  - `_vm_invoke_behavior(executor, behavior, args)`：镜像 `IbBehavior.call` 的 scope/closure/参数绑定簿记，在调用 LLM 之前 `yield None` 一次以保证当前 VMTask 留在帧栈上，然后委托给 `executor.invoke_behavior(...)`。
  - `_vm_invoke_llm_function(executor, func, receiver, args)`：镜像 `IbLLMFunction.call` 的意图栈 fork / 模块切换 / `push_stack` / `enter_scope` / 参数自动绑定（含 `intent_context` 形参 `use_intent_context`）/ `call_intent` 解析簿记，`yield None` 后委托给 `executor.invoke_llm_function(...)`。
- **handler 改写**：
  - `vm_handle_IbCall`：当 `func` 是 `IbBehavior` 或 `IbLLMFunction` 时改用 `yield from` 助手；其他 callable 维持 `func.call(...)`。
  - `vm_handle_IbExprStmt`：behavior 分支由 `res.call(...)` 改为 `yield from _vm_invoke_behavior(executor, res, [])`。
- **VMExecutor 可观察性**：`VMExecutor` 新增 `frame_stack_depth` 属性（暴露主循环当前栈深度），供调试器 / NS-1 回归测试观察 CPS 帧层级。
- **`IbBehavior.call()` / `IbLLMFunction.call()` 保留为 Python-可调用后备**（host/用户直接调用场景），外部契约未变。
- **回归覆盖**：新增 `tests/runtime/test_vm_llm_cps_dispatch.py`（2 个测试）验证 `execute_behavior_object` / `execute_llm_function` 进入时 `vm.frame_stack_depth >= 2` 且 `step_count` 已推进。
- **范围外（已记为后续）**：`LLMExecutorImpl._evaluate_segments` 的 CPS 化转换未本批纳入。`_evaluate_segments` 通过 `vm.run(segment)` 对 prompt 片段做嵌套求值；改造为 yield-based 形式需要把它本身改为生成器、并让 `_call_llm`/`execute_behavior_expression` 调用方也变成 yield，扩散面较大且收益弱于 NS-1 主路径，因此留作 follow-up。
- 代码：`core/runtime/vm/handlers.py`、`core/runtime/vm/vm_executor.py`。文档：`docs/NEXT_STEPS.md`、`docs/VM_AND_INTERPRETER_DESIGN.md`。
- 回归结果：测试通过。

NS-3（lambda/snapshot 跨帧 `_execution_context` 边界）由于 `vm_handle_IbCall` 现在对 IbBehavior 走 CPS 助手，**捕获时刻的 `_execution_context`** 已和**调用时刻的执行器** 通过 VMTask 帧栈对齐；但 `IbBehavior` 字段中仍持有定义期 `execution_context` 引用，跨线程时仍可能出现历史绑定问题（与 `core/runtime/objects/builtins.py:930` 一致）。因此 NS-3 不算被本次合并完全吃掉，保留待后续单独评估。

---

## 2026-05-11 锚点：NS-2 intent 系统 OOP 化完整收口（NS-2a/b/c/d 全部完成）

NS-2 全四步合龙——意图注释体系语法路径（`@`/`@+`/`@-`/`@!`）与 OOP 路径（`intent_context` 实例方法）打通为同一底层 `IbIntentContext`，双轨断裂彻底消除。

- **NS-2a**（已收录于本日条目）：`intent_context` 参数自动激活；`use(ctx)` 与函数自动绑定统一复用 `RuntimeContextImpl.use_intent_context(...)`。
- **NS-2b**：帧级活跃 `intent_context` IBCI 实例指针 `RuntimeContextImpl._active_intent_ibobj`，与帧 `_intent_ctx` 共享底层引用。`use()` / `clear_inherited()` / 函数入口 / NS-2a 自动绑定均同步重建此指针，使语法路径的 `@+`/`@-` 修改能通过 OOP `get_current()` 实时观察到（调试器亦获得用户命名身份）。
- **NS-2c**：`LLMExceptFrame.restore_context()` 由 `intent_context.merge(saved)` 改为 `_intent_ctx = saved.fork()` 干净替换，并同步重建活跃实例指针；retry 前后意图状态完全一致，与 vars / loop_context 的恢复语义对齐。
- **NS-2d**：新增 11 项测试覆盖（7 个 `tests/runtime/test_intent_context.py` 单元测试 + 4 个 `tests/e2e/test_e2e_ai_mock.py` 端到端测试），覆盖共享引用不变量、`use()` fork 语义、`clear_inherited()` 重建、`@+` × `get_current()` 同源观察、`llmexcept` retry 干净还原。
- 代码：`core/runtime/interpreter/runtime_context.py`，`core/runtime/objects/kernel.py`，`core/runtime/bootstrap/builtin_initializer.py`，`core/runtime/interpreter/llm_except_frame.py`。
- 回归结果：`python -m pytest tests/ -q --tb=short` 通过（1195 passed）。

历史 PT-1.1（llmexcept merge vs 替换语义对齐）随 NS-2c 一并落地，已从 `docs/PENDING_TASKS.md` 移除。PT-2.1 / PT-2.2 解除阻塞（依赖 NS-2b 的活跃实例指针），可作为 P2 排队。

---

## 2026-05-11 锚点：NS-2a（intent_context 参数自动激活）完成

- 在 `IbUserFunction.call()` 与 `IbLLMFunction.call()` 参数绑定阶段，`intent_context` 形参会自动激活为当前帧意图上下文（等价 `use(arg)` 语义）。
- 新增统一运行时入口 `RuntimeContextImpl.use_intent_context(...)`，并让 `intent_context.use(ctx)` 复用该入口，消除双轨分叉。
- 新增 e2e 覆盖：验证自动绑定生效、以及函数内 `@+` 修改不泄漏回调用方/实参上下文。
- 回归结果：`python -m pytest tests/ -q --tb=short` 通过（1182 passed）。

---

## 2026-05-08 锚点：类型系统主线收口 + VM CPS 全链路

### 类型系统五件套（M1–M5）

| 里程碑 | 完成日 | 摘要 |
|--------|--------|------|
| **M1**　TypeRef 引入 | 2026-05-07 | `core/kernel/spec/type_ref.py`：不可变 / 递归 / 工厂入口；编译器 / 解释器双端可读取 |
| **M2**　Optional[T] 与空安全 | 2026-05-07 | `OptionalSpec` + `OptionalAxiom` + 赋值规则；`is_nullable` 退役为兼容字段 |
| **M3**　TypeDef 单一化 | 2026-05-08 | 旧 `*Spec` 子类全部归并入统一 `TypeDef`，按 `kind` 分派；扁平 `*_name`/`*_module` 字段全面 TypeRef 化 |
| **M3→M5**　callable-instance 路线 | 2026-05-08 | `TypeKind.DEFERRED` + `BEHAVIOR` 合并为 `CALLABLE_INSTANCE`；`deferred_mode` → `capture_mode` |
| **M4**　运行时值模型单一化 | 2026-05-08 | `IbValue(type_ref, payload, fields, meta)` 成为运行时值公共承载层 |
| **M5**　Axiom 接口统一化 | 2026-05-08 | 单一 `TypeAxiom` 取代 9 个 Capability 子协议；`has_*_cap` 类属性声明能力 |

### 命名规范化（deferred → fn_callable，2026-05-08）

`IbDeferred` → `IbFnCallable`；`DeferredAxiom` → `FnCallableAxiom`；`DEFERRED_SPEC` → `FN_CALLABLE_SPEC`；`create_deferred()` → `create_fn_callable()`；`IbDeferredField` → `IbClassField`。无后向兼容 shim。

### VM CPS 全链路（M3a–M3d / M5a–M5c / M6 / Phase 1–5 编译器深度清洁）

| 里程碑 | 完成日 | 摘要 |
|--------|--------|------|
| **M3a**　CPS 调度循环骨架 | 2026-04-28 | `VMExecutor` + `VMTask` + dispatch table |
| **M3b**　控制信号数据化 | 2026-04-28 | `Signal(kind, value)` 替代 `ControlSignalException`（类已删除） |
| **M5a**　DDG 编译期分析 | 2026-04-28 | `BehaviorDependencyAnalyzer` 写入 `llm_deps` / `dispatch_eligible` |
| **M3c**　llmexcept retry CPS 化 | 2026-04-28 | `vm_handle_IbLLMExceptionalStmt` + `LLMExceptFrame.restore_snapshot` |
| **M5b**　LLMScheduler / LLMFuture | 2026-04-28 | ThreadPoolExecutor + 占位符模式 |
| **M3d / M5c**　主路径切换 + dispatch-before-use | 2026-04-29 | `execute_module()` / `IbUserFunction.call()` 全部经 `VMExecutor.run_body()` |
| **M4**　多 Interpreter 隔离（Layer 2） | 2026-04-29 | `spawn_isolated` / `collect` 契约 + ContextVar 帧 |
| **M6**　合规测试套件 | 2026-04-29 | `tests/compliance/`（执行隔离 / 并发 LLM / 内存模型） |
| **Phase 1–5 编译器深度清洁** | 2026-04-29 | CPS dispatch 覆盖 43 节点；`fallback_visit()` 调用归零；`node_protection` 侧表与 `bypass_protection` 参数链彻底删除 |

### 语法系统重设计（D1–D6，2026-04-29）

- D1：`fn` 等同 `auto`，不携带返回类型；`int fn f = ...` 形式废弃为 PAR_003。
- D2：lambda / snapshot 返回类型标注迁移至表达式侧（`lambda(...) -> T: EXPR`）。
- D3：`fn[(in)->(out)]` 高阶函数签名标注全链路落地（含 `IbCallableType` / `CallableSigSpec`）。
- D4–D6：现状已满足语义，无代码变更需要。

### llmexcept 影子执行驱动模式（历次演进收口于 2026-05-08）

- 废弃旧 `LLMUncertaintyError` 异常 + `_with_unified_fallback` 包装器。
- 当前实现：`set_last_llm_result(...)` 旗标轮询 + `LLMExceptFrame` 快照隔离 + AST 字段绑定（无侧表）。
- 详见 `docs/ARCH_DETAILS.md §一` 与 `docs/VM_AND_INTERPRETER_DESIGN.md §6`。

### 公理化 / IILLMExecutor 通道（2026-04-17）

- `core/base/interfaces.py:IILLMExecutor` + `KernelRegistry.register_llm_executor()` 建立合法服务通道。
- `BehaviorAxiom` 替换 `DynamicAxiom("behavior")`，`behavior` 成为一等公民类型。
- 旧 `_execute_behavior()` 旁路彻底删除。

### 健康审计修复批次（2026-04-29 → 2026-04-30）

- K1（`KernelRegistry.clone()` 漏拷 `_builtin_instances`）—— 已修复。
- K2（`SpecRegistry.is_assignable()` 防环递归）—— 已修复。
- K3（`register_builtin_instance` token 形同虚设）—— 已修复（移除 token 参数）。
- A1–A5 / L1–L4 等条目全部归档清理。

### OPEN_ISSUES 已解决批次

- OI-3：外部模块符号预注入临时妥协（2026-05-02）。
- OI-4：`SpecRegistry.resolve_specialization()` 缓存（2026-05-02 G1/G3）。
- OI-7：`LLMCallError` 自动抛出（2026-05-06）。

### MetadataRegistry 双轨统一（2026-05-08）

主引擎路径（`discover_all(registry)` + `HostInterface(external_registry=...)`）统一为单一 SpecRegistry 实例。`HostInterface.metadata` 与 `KernelRegistry._metadata_registry` 同源。

---

## 远期归档

更早期（2026-04-17 之前 + 三十余项 C1–C14 / L1–L4 / S1–S4 等清理）的实现细节归档于 `git log` 与具体文件的"演进历程"小节。本文件不再展开，避免污染当前看板。

---

## 关联文档

- 类型系统正式设计：`docs/TYPE_SYSTEM_DESIGN.md`
- VM 与解释器正式设计：`docs/VM_AND_INTERPRETER_DESIGN.md`
- VM 公理化规范：`docs/VM_SPEC.md`
- 实现细节备份：`docs/ARCH_DETAILS.md`
- 意图系统：`docs/INTENT_SYSTEM_DESIGN.md`
- 架构原则：`docs/ARCHITECTURE_PRINCIPLES.md`
- 当前已知限制：`docs/KNOWN_LIMITS.md`
- 代码内 TODO 索引：`docs/OPEN_ISSUES.md`
