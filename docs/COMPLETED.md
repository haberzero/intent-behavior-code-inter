# IBC-Inter 代码演进记录（已完成工作归档）

> 精炼记录各阶段完成的工程工作，按时间线从早期向当前推进。  
> 每条记录格式：任务名称 → 一句话结果。近期任务见 `docs/NEXT_STEPS.md`。
>
> **工作窗口**：2026-04-16 ~ 2026-04-27（690 测试通过后归档）

---

## 一、类型系统与公理化基础（2026-04-16 ~ 2026-04-18）

| 序号 | 工作内容 | 结果摘要 |
|------|---------|---------|
| 1.1 | Tuple 类型全栈实现 | `TupleSpec` + `TupleAxiom` + `IbTuple`（不可变元组，专用 boxer），元组解包赋值支持 IbList/IbTuple。 |
| 1.2 | 类型兼容性方向修复 | `is_compatible(target)` 语义固定为"source 能否赋给 target"，修复父类型向下兼容子类型的历史 Bug。 |
| 1.3 | VoidAxiom 替代 DynamicAxiom("void") | `void` 成为具体类型，无 Capability，只与自身兼容。 |
| 1.4 | CallableAxiom 替代 DynamicAxiom("callable") | `callable` 成为抽象可调用根类型，只与自身兼容；用户可见 `callable` 关键字废弃。 |
| 1.5 | DeferredAxiom + DeferredSpec + IbDeferred | 任意表达式可通过 `lambda`/`snapshot` 关键字延迟执行；`DeferredAxiom` 继承 `CallableAxiom`。 |
| 1.6 | BehaviorAxiom + IbBehavior 自主执行（Step 1+2） | `IbBehavior.call()` 通过 `KernelRegistry.get_llm_executor()` 自主执行，`_execute_behavior()` 旁路彻底删除。 |
| 1.7 | BehaviorSpec(return_type_name) 编译期类型推断 | 语义分析器对 `int lambda f = @~...~` 创建带类型的 BehaviorSpec，运行时精确解析。 |
| 1.8 | ibci_ai 职责拆分（Step 3a） | `LLMExecutorImpl.llm_callback` 唯一来源为 `capability_registry.get("llm_provider")`，移除所有 fallback。 |
| 1.9 | IbLLMFunction 自主执行（Step 4a） | `IbLLMFunction.call()` 通过 `registry.get_llm_executor()` 自主执行，不再持有 executor 引用。 |

---

## 二、语法与编译器（2026-04-17 ~ 2026-04-20）

| 序号 | 工作内容 | 结果摘要 |
|------|---------|---------|
| 2.1 | lambda / snapshot 关键字引入 | `callable` 从用户语法移除；`lambda`（调用时意图栈）和 `snapshot`（定义时意图快照）完整落地。 |
| 2.2 | `(Type) @~...~` 废弃（PAR_010 硬错误） | LHS 类型自动成为 LLM 输出格式提示词上下文，无需额外语法。 |
| 2.3 | behavior_expression() STRING token 修复 | `@~...~` 内引号字符串不再被静默丢弃，`MOCK:["a","b","c"]` 正确解析。 |
| 2.4 | llmexcept 嵌套块绑定修复 | `_bind_llm_except()` 递归进入 `IbFor`/`IbIf`/`IbWhile`/`IbTry`/`IbSwitch` body，修复静默失效 Bug。 |
| 2.5 | for 循环条件 + llmexcept 语义修复 | 条件驱动 for 循环保护绑定到 `iter_uid`（条件表达式），而非整个 for 节点。 |
| 2.6 | behavior 类型名硬编码消除 | `semantic_analyzer.py visit_IbFor` 的 `"behavior"` 字符串直接比较替换为 `SpecRegistry.is_behavior()`。 |
| 2.7 | `for...if` / `while...if` 过滤语法 | `visit_IbFilteredExpr` 实现过滤条件，foreach/while 场景语义正确。 |
| 2.8 | 泛型专化崩溃三处子修复（Bug #3） | `list[str]`/`dict[str,int]`/`tuple[int]` 等泛型标注完全可用；联合修复 `_resolve_type`、`hasattr` 检查、方法成员补全。 |
| 2.9 | 重复 `_stmt_contains_behavior` 删除（Bug #2） | 删除 AI Agent 遗留残缺重复实现，修复 `llmexcept` 跟在 `if/while/for @~...~:` 后报 SEM_050 的问题。 |

---

## 三、LLM 执行 & 异常处理（2026-04-17 ~ 2026-04-20）

| 序号 | 工作内容 | 结果摘要 |
|------|---------|---------|
| 3.1 | MOCK:FAIL 哨兵修复 | 哨兵检测在 `_parse_result()` 之前拦截，修复被误装箱导致 llmexcept 不触发的 Bug。 |
| 3.2 | IbBehavior call_intent 传播修复 | `IbBehavior` 新增 `call_intent` 字段，`@!` 排他意图在延迟执行路径中不再丢失。 |
| 3.3 | 重试诊断日志 | `visit_IbLLMExceptionalStmt` 重试循环新增 `core_trace()` 调用，生产运行无影响。 |
| 3.4 | IbTuple 序列化/快照集成 | `_is_serializable()` 和 `runtime_serializer.py` 添加 `"tuple"` 分支，与 IbList 对称。 |
| 3.5 | max_retry 配置穿透 | `visit_IbLLMExceptionalStmt` 通过 `capability_registry.get("llm_provider").get_retry()` 读取配置。 |
| 3.6 | IbBool(False) / IbInteger(0) 假值误判修复（Bug #1） | 三处 `result.value if result and result.value` 改为 `is not None` 判断，修复零值被误替换为 IbNone。 |
| 3.7 | 嵌套 llmexcept 集成测试 | 新增 `TestE2ELLMExceptNested` 三个场景（独立重试、内层恢复外层继续、重试耗尽后不污染外部变量）。 |

---

## 四、架构清理 & 代码健康（2026-04-19 ~ 2026-04-22）

| 序号 | 工作内容 | 结果摘要 |
|------|---------|---------|
| 4.1 | OOP×Protocol 边界清理（PR-A） | 删除 `IIibObject.descriptor` 幽灵字段，移除 5 处 Protocol isinstance 调用及 6 处死 import。 |
| 4.2 | Impl 类 Protocol 继承清理（PR-B） | 6 个 Impl 类移除 Protocol 直接继承（Python `@runtime_checkable` 卫生清理）。 |
| 4.3 | 技术债清理 | 删除 `"llm_fallback"` 无效属性遍历；清理 5 处过期 TODO；`interop.py` Protocol TODO 替换为注释。 |
| 4.4 | ibci_isys v2.0 | `ibci_sys` 合并进 `ibci_isys`，新增 `sys.script_dir()` / `sys.script_path()` 等路径 API。 |
| 4.5 | llmexcept 循环迭代器状态恢复 | `LLMExceptFrame` 新增 `loop_resume` 字段，for 循环 retry 后从失败迭代索引处继续。 |
| 4.6 | 显式引入原则 Phase 1+2 | 所有插件 `_spec.py` 新增 `"kind"` 字段；`Prelude` 按 `is_user_defined` 过滤；`discover_all()` 改为懒加载。 |
| 4.7 | vtable callable 签名自动提取 | `discovery.py` 通过 `inspect.signature()` 自动提取 vtable callable 条目签名转为 `MethodMemberSpec`。 |
| 4.8 | Mock 仿真引擎完善 | `MOCK:FAIL/REPAIR/INT/STR/FLOAT/LIST` 全部正确实现；`MOCK:REPAIR` 按调用点独立计数。 |
| 4.9 | Vibe 代码债务清理 | 修复 `interpreter.py:229` kwargs bug；规范化 `engine.py` orchestrator 注入方式。 |

---

## 五、核心公理化路径（Steps 1–8，2026-04-17 ~ 2026-04-20）

| 步骤 | 工作内容 | 结果摘要 |
|------|---------|---------|
| Step 4b | ibci_ihost / ibci_idbg KernelRegistry 标准化 | 两个核心插件改为通过 `KernelRegistry` 稳定钩子接口（`get_host_service/stack_inspector/state_reader`）访问服务。 |
| Step 5a | IExecutionFrame Protocol 定义 | `core/base/interfaces.py` 定义 `IExecutionFrame`；`RuntimeContextImpl` 实现该接口。 |
| Step 5b | ContextVar 帧注册表 | `core/runtime/frame.py` 引入 `contextvars.ContextVar`；`IbUserFunction.call()` 去除 context 参数依赖。 |
| Step 6a | IntentContextAxiom | `core/kernel/axioms/intent_context.py` 注册 `IntentContextAxiom`（`is_class=True`）。 |
| Step 6b | IbIntentContext 运行时对象 | `core/runtime/objects/intent_context.py` 实现 fork/push/pop/remove/merge，持久栈通过不可变链表结构共享。 |
| Step 6c | RuntimeContextImpl 意图字段完整迁移 | 四个意图私有字段全部迁移至 `_intent_ctx: IbIntentContext`，外部接口零破坏。 |
| Step 6d | LLMExceptFrame 意图快照清洁化 | `saved_intent_stack`（裸引用）完整删除，仅保留 `saved_intent_ctx`（fork 值快照）。 |
| Step 7 | LlmCallResultAxiom + IbLLMCallResult 全链路接入 | `IbLLMCallResult` IBCI 对象完整接入公理体系；`set_last_llm_result()` 自动转换；所有读取点适配新字段。 |
| Step 8 | 架构边界文档化 | `interpreter.py`/`engine.py`/`service.py` 头部添加架构边界说明注释。 |
| Step 8-pre §9.2 | llmexcept body 编译期 read-only 约束（SEM_052） | `visit_IbAssign` 检测外部作用域变量写入并发出 `SEM_052`；body-local 新声明和 retry 语句不受限。 |
| Step 8-pre §9.3 | `_last_llm_result` per-snapshot 化 | 读取后立即清零共享字段；`LLMExceptFrame.last_result` 为 per-snapshot 权威来源；idbg 改为帧优先模式。 |
| Step 8-pre §9.4 | 函数调用意图隔离 | `IbUserFunction.call()` / `IbLLMFunction.call()` 统一 fork/restore；三个显式作用域控制 API（`clear_inherited`/`use`/`get_current`）注册。 |
| Step 8-pre §9.5 | intent_context OOP MVP | `IntentContextAxiom.is_class=True`；`INTENT_CONTEXT_SPEC`；11 个实例/类方法完整注册；用户可显式实例化 `intent_context()`。 |

---

*当前测试套件：690 个测试通过。近期任务见 `docs/NEXT_STEPS.md`。*
