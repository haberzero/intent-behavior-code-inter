# PENDING_TASKS — 待办 / 长期规划

> 当前最紧要见 `tasks_docs/NEXT_STEPS.md`；本文档只保留**仍有价值**的待办、长期规划与设计决策。
> 已完成/无价值条目已删除（完整历史在 git）。
> 任务代号体系（2026-08-05 重整，按**性质**分域，一概念一前缀）：
> **PT-INTRO-1**（内省体系，已完成）｜**PT-FEAT-\*** 语言特性｜**PT-DEBT-\*** 缺陷/技术债
> ｜**PT-AUDIT-\*** 长期周期清扫（审查/审计/文档与注释治理，持续周期工作）
> ｜**PT-DOC-\*** 文档同步｜**PT-TEST-\*** 测试体系｜**PT-DECIDE-\*** 待用户拍板
> ｜**PT-SEALED-\*** 封存

---

## 〇、当前主线与优先级总表（单一权威源，2026-08-08 用户认可）

> **三维度判断：易用性 / 架构健康性 / 长远收益**。当前主线与长期优先级统一在此，
> `NEXT_STEPS.md` 只列当前最紧要并指向本节。

| 优先级 | 任务 | 维度 | 说明 |
|--------|------|------|------|
| **✅ 已完成（2026-08-15，exp/llm-prompt-mechanism → unsafe-vibe-dev，全量 2787 passed / 1 skipped 零回归）** | **IBCI LLM 调用机制改进（T5 枚举解析失败暴露）** | 架构健康性 | 完整试用核查中 T02 T5（枚举成员名→值映射）真实 LLM 间歇失败，深挖实证为**机制弱点**而非单纯模型非确定性。**可直接复现机制 bug**：枚举 `__outputhint_prompt__`（"Reply with exactly one of..."）**未注入提示词**——`_get_llmoutput_hint`（`llm_executor/_prompt.py:259`）用裸名 `resolve("Status")` 查枚举（S2/S5 module 化后注册为 `__string_exec__.Status`）→ None → hint 断链；`_try_vtable_hint` 也失败（枚举 hint 在 EnumAxiom 上，不在类 vtable）。实际 sys_prompt = `'你是一个意图行为代码执行器。'`（无 `[输出格式要求]`），type_hint 仅用于解析不注入。**三结构性弱点**：① 系统提示词过弱未建立程序化调用纪律（模型滑回对话助手模式——失败响应形态"请提供..."/安全拒绝）；② 期望输出类型不注入 prompt；③ llmexcept/retry 只回喂用户手写 retry_hint，不自动回喂解析错误/上次响应。**vs OpenAI 标准**：IBCI `@~...~` 是"裸用户单轮 + 通用系统提示"最弱框架，缺 function/tool 调用框架、schema 注入、错误回喂重试。**改进方向 A-E**（见 `_HANDOFF_LLM_PROMPT_MECHANISM.md`）：A 修复 module 感知注入 bug（明确低风险）；B 强化程序化调用纪律；C 期望类型注入 prompt；D retry 自动错误回喂；E 长期对齐结构化输出。**性质**：语言级机制改进（LLM 调用面）。**✅ 完成（2026-08-15）**：A-D 四项落地（枚举输出约束 module 感知注入 / 程序化调用纪律 / 期望类型注入 / retry 自动错误回喂）；新增 `_prompt_assembly.py` 单一权威组装；判别性回归 +6；真实 LLM T02 T3/T4/T5 三连 PASS。设计/实施 `（已清理任务文档）`。E 结构化输出对齐仍为长期项。 |
| **✅ 已修复（2026-08-14，exp/callable-sig-signature → unsafe-vibe-dev，全量 2775 passed / 1 skipped）** | **CALLABLE_SIG（fn[(...)->...]）签名模型架构碎片化根治** | 架构健康性 | KNOWN_LIMITS §10.4"潜伏边界"深挖推翻——真实类型安全漏洞。**漏洞 1（匹配双通道）**：`_matches_callable_sig`（is_assignable 路径）只查参数数量+返回，`fn[(Box[int])->int]` 收 `get2(str)->int` 编译期放行、运行期 RUN_TYPE_MISMATCH；**漏洞 2（嵌套类型参数不替换）**：扁平构造 `TypeRef('Box[T]')` substitute 不可穿透 → `Host[int]` 特化后检查静默跳过。**根因**：CALLABLE_SIG 构造用 `TypeRef.of(p.name)` 扁平化（与 fn/callable 断层同源——泛型结构化地基后签名构造/匹配未升级）+ 匹配双实现。**根治**：结构化构造（from_spec）/ 结构化重建（resolve_typeref 保留嵌套）/ 统一匹配（`_matches_callable_sig` 补逐参数 + resolve_typeref 收敛双通道）/ 延后规则（裸占位延后、any 通配不误拒模板、带实参不可解析 fail-fast）。判别性回归 +10 + 模板回归 2；两轮独立复核 P1 已整改。KNOWN_LIMITS §10.4 定性更新。设计 `_DESIGN_CALLABLE_SIG_SIGNATURE.md`。 |
| **✅ 已修复（2026-08-14，exp/fn-callable-redesign → unsafe-vibe-dev，全量 2765 passed / 1 skipped）** | **fn/callable 关键字体系重构（方向 A：callable 内部化 + fn 参数/返回强制可调用）** | 架构健康性 | 彻查（`_DESIGN_FN_CALLABLE.md`）证实 `callable` 作为用户类型是"内部概念泄漏 + 半成品"：只对 lambda/绑定方法生效、误拒裸函数/可调用类实例/容器；与文档"不引入统一 callable 基类"鸭子类型哲学矛盾；与 `fn` 职责重叠（双通道）；一词四义（运行期基类名/公理根/用户类型/thread 参数名）。**用户 2026-08-14 拍板方向 A**：① `callable` 降级为纯内部概念（运行期基类名 `type(make)`="callable" + 公理族根 + `thread(callable=...)` 参数名保留并文档化），用户注解 `callable f`/`-> callable`/`list[callable]`/`class X(callable)` 报 `SEM_UNRESOLVED_TYPE` 引导用 `fn`；② `fn` 参数/返回收紧为"任意可调用（强制）"——`apply(42)`/`-> fn: return 42` 编译期拦截，CLASS 按 `__call__` 成员判定（P1 整改，与声明路径对齐），动态 any/auto 放行；③ `_infer_fn_type` 兜底改 `fn` 哨兵（不再泄漏内部 callable）。判别性回归 +19；独立复核（general agent）P1/P2 已整改。已知残留：`list[fn]` 容器元素级强制可调用未接线。 |
| **✅ 已修复（2026-08-14，exp/func-callable-identity → unsafe-vibe-dev，全量 2746 passed / 1 skipped）** | **函数/可调用类型身份架构断层根治（三个深层次缺陷同源）** | 架构健康性 | 用户猜想"fn 设计早于泛型体系存在历史包袱"**已证实**，且深挖为**三层系统性断层**：① spec→TypeRef 转换无单一权威（`TypeRef.from_spec` 缺 FUNCTION/BOUND_METHOD/CALLABLE_SIG，存在 `scheduler._spec_to_typeref` 与 `_param_type_ref` 两个部分实现）；② type_checking 回填用 `.name` 字符串覆盖 symbol_collection 已产出的结构化 spec（`-> fn[(...)->...]` 退化为裸 fn，create_func 为早期字符串级 API）；③ 函数签名序列化缺口（FUNCTION `get_references` 恒空 + rehydrator `_fill_descriptor` uid 通道回退 void——运行期函数 spec 恒 void 返回）。**三个问题**：① 绑定方法建模缺陷（`resolve_member` 无条件 FUNCTION kind，BoundMethodAxiom 编译期不接线）；② 函数符号 spec 回填签名丢失；③ 函数返回值 Optional 包装缺失。**五项根治**：A `TypeRef.from_spec` 补三 kind（FUNCTION 按名区分 callable/fn 标记与真实签名）；B `create_func` 结构化升级（向后兼容字符串）+ 编译期回填传 from_spec + `-> auto` 收敛；C `resolve_member` 非 MODULE 方法成员产出 BOUND_METHOD（携带签名 + receiver_type），4 消费点补 kind；D `_wrap_function_result` 单一 helper 接线三返回消费点（含方法 owner_class 成员签名路径、lambda 表达式体）；E 序列化 FUNCTION/BOUND_METHOD/CALLABLE_SIG 持久化 canonical_name 签名 + rehydrator shell/_fill_descriptor 对称恢复。判别性回归 +29（test_func_callable_identity 19 + TestBoundMethodReturn 反转 + 方法包装）。潜伏边界 KNOWN_LIMITS §10.4（fn 签名内嵌套泛型实参名称回绕可用/结构化不可穿透）。独立复核（general agent）放行（P1 方法返回包装 + P2 双包装去重已整改）。设计/实施 `_code_func_callable_identity.md`。 |
| **✅ 已修复（2026-08-14，统一类身份模型 S4，全量 2616 passed / 1 skipped）** | **KERNEL_ISSUE-CROSSMOD-THREAD-1：被 import 模块用户类在线程 worker 内不可用** | 架构健康性 | 触发 `trials/T05_critical_stress/cases/D1-10/`。**根因（`_code_class_identity_unify.md` S4）**：task_ec 的 `get_side_table` 回调读 interpreter 共享 current_module_name（忽略任务本地模块切换）。**根治**：`get_side_table` 增 module 参数（`ExecutionContextImpl` 透传自身 `current_module_name` 任务本地值）+ 同族 `is_truthy` 任务本地化（`get_current_execution_context`）。**判别性回归 +2**（imported/入口类线程 worker：405/405 + 105/105）。独立复核 PASS（反向实验证明 S4 前回归测试失败）。 |
| **✅ 已修复（2026-08-14，跨模块类型注解解析，全量 2665 passed / 1 skipped）** | **KERNEL_ISSUE-CROSSMOD-LLM-1：跨模块用户类作行为表达式 LLM 输出目标失败** | 编译期正确性 | 触发 `trials/T06_class_identity/cases/D3-02/`、`D2-05/`。`geo.Counter c = @~...~` 运行时抛 `__call__ on None`。**根因（编译期实证）**：`_resolve_type` 对 IbAttribute 点号限定注解（geo.Counter）未解析目标 spec → node_to_type 退化。**根治**：`_resolve_type`/`resolve_type_annotation`/`_resolve_annotation`/`_annotation_to_typeref` 支持 IbAttribute 注解（module 限定，含泛型 `geo.Box[int]`）。**判别性回归 +3**（行为节点 node_to_type 绑定 geo.Counter / 泛型注解 / 无 __from_prompt__ fail-fast）。D3-02/D2-05 转 PASS。设计 `_code_optional_unify.md` 变更 A。 |
| **✅ 已修复（2026-08-14，统一 Optional 值模型，全量 2665 passed / 1 skipped）** | **KERNEL_ISSUE-OPTIONAL-ISNONE-1：`Optional[T] a = None; a is None` 返回 False + `is_none()` 缺失** | 语义正确性 | 触发 `trials/T05_critical_stress/cases/D2-03.ibci`。**根因（深层）**：Optional 空值表示分叉（变量/返回包装为 IbOptional，参数/字段/容器裸存 IbNone）。**根治（`_code_optional_unify.md`）**：`wrap_optional` 单一包装权威 + 全值创建路径覆盖（参数 spec 解析/字段 member_types/容器元素）+ `is`/`is not` None 双向语义 + `is_none()` + `None==Opt` 对称 + deep_clone 保 _is_some + llmexcept 类符号跳过。**判别性回归 +20**（`tests/runtime/test_optional_value_model.py`）。**P2→已修复**。 |
| **✅ 已修复（2026-08-14，幽灵诊断码根治，全量 2665 passed / 1 skipped）** | **8 幽灵诊断码 + 快照篡改警告未发射** | 诊断契约 | T05 发现：`RUN_DIVISION_BY_ZERO`/`RUN_ATTRIBUTE_ERROR`/`RUN_INDEX_ERROR`/`RUN_PERMISSION_ERROR`/`RUN_LLMEXCEPT_SNAPSHOT_VIOLATION`/`LEX_INVALID_NUMBER`/`PAR_INDENTATION_ERROR`/`PAR_MULTIPLE_INTENTS` 全仓零发射；越界/除零/属性缺失报裸 RUNTIME_ERROR（issue.py 默认码未注册）；`indent_processor` 误用 `LEX_INVALID_ESCAPE`。**根治（`_code_ghost_codes.md`）**：7 码实现发射（`_runtime_error_code_for` 异常映射 + collections/permissions 显式码 + llmexcept 快照警告 + 词法器 LEX_INVALID_NUMBER 完整校验 + indent_processor 改码）；**PAR_MULTIPLE_INTENTS 删减**（语言无该约束，杜绝死契约）；`InterpreterError` 默认码 RUNTIME_ERROR → RUN_GENERIC_ERROR。**契约测试 CAT-7**（目录码须有生产发射点，全码零幽灵）+ 判别性回归 10 项。 |
| **✅ 已修复（2026-08-14，set_mock_mode 对称开关，全量 2665 passed / 1 skipped）** | **`set_mock_mode()` 单向无 off API** | 易用性 | `set_mock_mode()` 仅进入 mock（`_config["mock"]=True`），退出只能 `ai.set_config`/`apply_config`。**修复（`_code_set_mock_mode.md`）**：`set_mock_mode(enable: bool = True)` 对称开关——`enable=False` 退出并重建真实客户端（未配置 fail-fast）；无参调用兼容。vtable 增 enable 参数。**判别性回归 3 项**（进入/退出 fail-fast/mock-真实-mock 往返）。 |
| **✅ 文档部分已治理（2026-08-14，doc-governance；代码联动项见 `_HANDOFF_T05_ISSUES.md` §六）** | **DOC_ISSUE-1~23 文档批量（含 4 项代码联动：mock STR/BOOL 值语义 / 8 幽灵诊断码+快照警告 / `is_none()` 缺失（与 KI-2 合并）/ `set_mock_mode` 单向）** | 文档健康 | T05 全量文档核验产出 23 条。**文档部分全部治理**（doc-governance，2026-08-14）：KNOWN_LIMITS §七/§八/§十三 实证修正、mock STR/BOOL 值语义文档精确化（**已决断：修文档保持实现**——含空格需引号/仅大写 TRUE）、15_diagnostics 8 幽灵码标注未发射、快照篡改改静默恢复、Optional `is None` 判空说明（`== None`）、cast_to/lambda 示例修复、TESTONLY→MOCK、find_last 索引、set_mock_mode 单向性说明等。**代码联动项全部完成**（2026-08-14）：① 8 幽灵码实现发射/删减（§六.3，见幽灵诊断码行）；② `is_none()` 实现（与 KI-2 合并，§六.2）；③ `set_mock_mode(False)` 对称开关（§六.4，见上）。 |
| **✅ 已修复（2026-08-14，unsafe-vibe-dev）** | **KERNEL_ISSUE-OPTIONAL-SCOPE-1：函数作用域内 Optional 先 None 后赋值，unwrap()/is_some() 报 `Object of type None`** | 语义正确性 | 触发 `trials/T07_fixes_critical_stress/cases/D2-09.ibci`（**已核销转 PASS**）。根因（系统性）：函数作用域局部变量声明类型编译期丢失——`_prescan_body_locals` 硬编码 any → 符号池 type_uid=any → 运行时 wrap_optional 不包装；同源：函数内类型化局部变量重赋值检查失效（`int x = 5; x = "abc"` 放行）、闭包/cell 写路径不包装。修复：prescan 解析类型注解（无注解 auto 占位）+ type_checking 复用 owned_scope（局部符号可见）+ 闭包绑定/cell 写 declared_type 对齐 + rehydrator FUNCTION/CALLABLE_SIG/BOUND_METHOD/MODULE kind 保真（预存缺陷）+ TYPE_PARAM 运行时检查放行。判别性回归（compiler 7 + runtime 7）。文档 arch/03 §8 已同步。**P1→已修复**。 |
| **✅ 已修复（2026-08-14，unsafe-vibe-dev）** | **KERNEL_ISSUE-OPTIONAL-CONTAINER-1：Optional[list[int]] 有值包装后 len()/下标不可用** | 语义正确性 | 触发 `trials/T07_fixes_critical_stress/cases/D2-10.ibci`（**已核销转 PASS**）。根因：`IbOptional.receive` 无内层值委托（容器方法对 Optional 包装不可用）+ `resolve_iterable` 不支持 Optional 委托（for 迭代失败）。修复：`IbOptional.receive` 统一委托链（内层值优先 + Optional 专属方法回退 + 空值 fail-fast RUN_ATTRIBUTE_ERROR）+ `resolve_iterable` 识别 Optional（有值按内层解析、空值 fail-fast）。文档 arch/03 §8 新增"Optional 容器委托"条目。判别性回归（runtime 5）。**P1→已修复**。 |
| **✅ 已修复（2026-08-14，unsafe-vibe-dev）** | **KERNEL_ISSUE-ATTR-READ-1：未声明属性读取静默返回 None（仅调用路径报 RUN_ATTRIBUTE_ERROR）** | 语义正确性 | 触发 `trials/T07_fixes_critical_stress/cases/D1-13.ibci`（**已核销转 PASS**）。根因：`Object` 基类 `__getattr__` 兜底（`_default_getattr`，bootstrapper）未命中成员时静默返回 IbNone——错误值流入程序后在调用路径报困惑的 "Object of type None has no method __call__"。修复：改抛 `InterpreterError(RUN_ATTRIBUTE_ERROR)`（读取/调用路径一致 fail-fast；符合工作模式定论"不静默错误值"）。文档 15_diagnostics RUN_ATTRIBUTE_ERROR 触发条件精确化。判别性回归（runtime 4，含线程内）。**P1→已修复**。 |
| **✅ 已同步（2026-08-14，doc-governance；与 3 项 KI 修复联动）** | **DOC-24~28 文档同步批次（与 3 项 KI 同源 + KNOWN_LIMITS §10.2 + 14_concurrency）** | 文档健康 | T07 文档核验产出：DOC-24（arch/03_type_system §8 `unwrap/is_some/is_none 在任何路径可用`不成立，同 OPTIONAL-SCOPE-1）、DOC-25（§8 Optional 容器方法不可用未说明，同 OPTIONAL-CONTAINER-1）、DOC-26（15_diagnostics RUN_ATTRIBUTE_ERROR `访问对象不存在的属性/方法`触发条件与实现不符——读取路径静默 None，同 ATTR-READ-1）、DOC-27（KNOWN_LIMITS §10.2 建议补 qualified 路径实证——裸名退化表述仍成立，T07 D3 实证 qualified 全生效）、DOC-28（14_concurrency `chan(T, name, ...)` 宜补充说明：特化类对象实参降级为裸类，普适写法 `chan[E] ch = chan()`，见 BOUNDARY-CHAN-ARGS-1）。**全部已同步（2026-08-14）**：§8 值创建路径枚举补函数作用域局部变量/闭包捕获 + 新增"Optional 容器委托"条目；15_diagnostics RUN_ATTRIBUTE_ERROR 触发条件精确化（读取/调用均报）；KNOWN_LIMITS §10.2 补 qualified 路径实证；14_concurrency 补 chan T 实参形态说明。 |
| **✅ 已修复（2026-08-14，unsafe-vibe-dev 19920d39，全量 2714 passed / 1 skipped）** | **DOC-29 空 Optional 操作错误码与文档承诺不一致** | 诊断契约 | `Optional[T] e = None` 的 `for x in e` 迭代 / `next(e)` / `e.unwrap()` 抛 `RUN_GENERIC_ERROR`（iterable.py:39 / optional.py:90 抛 InterpreterError 未指定 error_code → 默认码）；而委托链空值路径（optional.py:174）与文档 arch/03 §8 承诺均报 `RUN_ATTRIBUTE_ERROR`——**同语义"空 Optional 操作不可用"两处码不一致 + 文档矛盾**（15_diagnostics RUN_GENERIC_ERROR 定义"未归类运行时错误" vs arch/03 §8 "空 Optional 操作 fail-fast 报 RUN_ATTRIBUTE_ERROR"）。base（30511d4f）同现空值 unwrap 亦 RUN_GENERIC_ERROR=pre-existing。**修复（架构判断裁决：统一为 RUN_ATTRIBUTE_ERROR）**：iterable.py resolve_iterable 空 Optional + optional.py unwrap 补 `error_code="RUN_ATTRIBUTE_ERROR"`（三处发射点收敛 + 与文档 arch/03 §8 承诺一致）。判别性回归 +4（TestOptionalEmptyErrorCode）。触发用例 E1/E2 核销转 PASS。**P2→已修复**。 |
| **✅ 已修复（2026-08-14，unsafe-vibe-dev 19920d39，全量 2714 passed / 1 skipped）** | **BOUNDARY-NESTED-FUNC-1 函数返回嵌套函数赋 fn_callable 类型 RUN_TYPE_MISMATCH** | 语义正确性 | `func outer() -> fn_callable[int]: func inner() -> int: ...; return inner` → 运行时 `RUN_TYPE_MISMATCH: Cannot assign 'callable' to 'fn_callable[int]'`（`_check_type` 把嵌套函数符号识别为裸 callable）；lambda 返回正常。**base（30511d4f）同现=pre-existing**。**深度分析修正定性**：真实根因 = 编译期 `visit_IbReturn` 返回类型兼容校验整体缺失（从不比对返回表达式类型与声明返回类型；实测 `-> fn_callable[int]: return lambda -> str`、`-> int: return "abc"` 均编译期放行）。**修复（根因，非症状）**：`visit_IbReturn` 对非动态的可调用返回类型（FUNCTION/BOUND_METHOD/CALLABLE_SIG/CALLABLE_INSTANCE）补 is_assignable 校验——`return inner`/签名不匹配 lambda 编译期拦截（与直接赋值路径 `fn_callable[T] g = inner` 语义一致）；`-> fn`（动态哨兵）跳过（现有 HOF 路径零影响）；普通类型返回保持宽松（独立问题不并入）。判别性回归 +13（test_return_type_validation.py）。触发用例 E3 语义改进（运行时 RUN_TYPE_MISMATCH → 编译期 SEM_TYPE_MISMATCH，fail-fast 提前）核销转 PASS。**P1→已修复**。 |
| **🟡 已登记待办（2026-08-14，供应商感知思考禁用——既有长期项）** | **PT-DECIDE 供应商感知模型思考禁用机制** | 架构健康性 | 见 `LLM_SERVICE.md`（qwen3.6-35b-a3b 思考禁用：LM Studio 界面替换提示模板已生效，IBCI 侧逐供应商参数形态探测为待设计项）。P2，独立设计窗口。 |
| **🟡 暂缓（2026-08-15 用户改主线，下一主线后回到本项）** | **PT-FEAT-14 IBCI LLM 调用接口通用化 / 供应商感知配置** | 架构健康性 | **真实 LLM 专项暴露的接口设计问题**：`AIPlugin` 仍硬编码 LM Studio 专用 `enable_thinking=false` / `chat_template_kwargs` extra_body（probe 与 create 两处重复），且 `max_tokens=4096` 未参数化——自定义 OpenAI 兼容 API 开发者无法干净接入。**目标**：请求参数下沉为 provider/model 级配置，单一请求构造权威；与 PT-DECIDE 收敛。**用户裁定 2026-08-15：本项暂缓，先做 LLM 全能力真实压力试用。** |
| **🔴 P0（进行中，2026-08-16 用户指定）** | **内核协议化收尾与双轨收敛（体系化重构，交接见 `tasks_docs/_HANDOFF_KERNEL_PROTOCOLIZATION.md`）** | 架构健康性 | **用户裁定：内核/架构体系健康性与宏观长远利益为最高准则；全量重跑/试用是对智能体的约束而非负担；理论问题清理完毕后进入宣发/推广阶段。** 已确认隐患：① **OOP 侧纯字符串分派与硬编码**（receive 字符串消息 + `message ==` 分支 base.py:51/71/87、ib_class.py:603/620/626；`_default_getattr` 字符串兜底；`_impl_cls` 按名解析）；② **公理声明端硬编码**（has_*_cap 布尔字段——判定已协议化、声明未协议化）；③ **双轨形态**（方法符号 spec self 形态单文件/跨文件不一致、特化类字符串注册键 `"Box[int]"`、成员多表 methods/default_fields/member_types/spec.members、auto-init 运行时闭包 + 参数数量校验三处并存）；④ **编译期-运行期断裂**（node_to_symbol 绑定双义（self 符号 vs 函数符号）、`_method_declared_spec` 符号池回退桥、字段默认值预求值 vm.run 重入、序列化字符串键残留）；⑤ **已知边界堆积**（KNOWN_LIMITS 26 节灰色地带，§4 归类初稿）；⑥ **工程面**（性能基准/工具链/文档旅程，宣发前置）。**阶段规划**：A OOP 侧协议化（dunder 注册表化）→ B 双轨收敛（self 形态统一/特化身份结构化/成员单一权威/auto-init 声明化）→ C 公理声明协议化 → D 已知边界三分类处置 → E 宣发前置。每阶段：全量 pytest 零回归门 + 独立复核（general agent）+ 真实 LLM 试用复跑（T09+受影响套件，分类逐例一致）+ 文档同步。 |
| **✅ 已完成（2026-08-16，已合并 unsafe-vibe-dev）** | **协议化内核大重构 + 内核全方位梳理清洁 + 架构级重构**（exp/protocol-kernel 独立分支） | 架构健康性 | **交接清单全部落地 + 独立复核整改 + T09 影响确认 + 方法 spec 根治**。① LLM 函数残留清理（统一路径/删兼容别名/死分支/休眠 API）；② Prompt sync/CPS 双通道收敛（_pump_cps 泵驱动单一 CPS 权威）；③ retroactive implementation 推进到"可为已有类型补充方法"（含 LLM 方法，+18 测试）；④ 序列化键历史兼容映射清除（双写真相收敛）；⑤ dispatch_eager 同步重入消除（CPS 预求值嵌入帧栈）；⑥ 独立复核整改（P1-1/P2-1~7 全闭环）；⑦ 方法对象 spec 语义错位根治（函数 spec 统一 + __init__ 契约校验生效 + 成员表权威）；⑧ `__from_prompt__` 能力查询单一入口；⑨ T09 真实试用（108 例回归零回归 + 8 例新能力全 PASS）；⑩ 合并前 116 例真实 LLM 复跑分类与基线逐例一致。**合并**：fast-forward 1b83a698..fbda2098（用户显式授权直接合并，79 文件 +4216/-784）；合并门全量 2912/1 + 试用逐例一致。临时分支与临时交接/设计文档已清理归并（KNOWN_LIMITS §二十六）。 |
| **✅ 已完成（2026-08-15，T08 第一轮，全量 pytest 零回归）** | **IBCI LLM 全能力真实压力试用（第一轮）** | 验证/架构健康性 | 41 例：**32 PASS + 2 GUARD + 4 LLM_BEHAVIOR + 2 BOUNDARY + 1 LIMIT**。覆盖内联/容器/协议/批量/意图/LLM 函数/流式/路由/线程/chan/生成器/配置错误。**修复 2 项**：`KERNEL_ISSUE-LLM-2`（LLM 函数容器返回解析）、`KERNEL_ISSUE-LLM-3`（`set_retry(0)` 重试耗尽）。**新登记**：`DOC_ISSUE-30`（`@!`+run_batch 文档与实现不一致，**已同步文档**）、`BOUNDARY-LLM-2`（LLM 函数 `-> void`）、`BOUNDARY-LLM-3`（stream 调用不入 call_info）。详见 `trials/T08_llm_pressure/REGISTER.md`。**注（2026-08-16）**：后续扩展压力维度的工作顺延至协议化内核大重构之后。 |
| **🔴 P0（进行中，2026-08-15 用户指定）** | **IBCI LLM 全能力真实压力试用（本地 qwen）** | 验证/架构健康性 | **第一轮已完成，继续扩展压力维度。** 专注点：LLM 一侧。用本地可用 qwen 模型真实调用，检查 IBCI 承诺的所有直接/间接 LLM 能力：内联行为表达式（赋值/条件/循环/表达式语句/dispatch-before-use）、类型解析（int/float/bool/str/list/dict/enum/自定义 `__from_prompt__`/`__validate_prompt__`/`__outputhint_prompt__`/`__to_prompt__`）、意图系统（@/@!/@+/global/mask）、命名 LLM 函数（`__sys__`/`__user__`/`__llmretry__`/参数插值/返回类型/函数值）、llmexcept/llmretry（自动错误回喂/快照隔离/耗尽）、批量与并发（`ai.run_batch`/dispatch/thread/chan/generator 交互）、模型路由（`@NAME~`/`ai.register_model`/`ai.probe_model`）、配置与观测（`ai.set_config`/`load_project_config`/`get_current_call_info`/`stream_call`）。**工作模式**：真实 LLM 为主，mock 仅作对照；发现缺陷记录并自主修复；全量 pytest 零回归 + 交接。 | |
| **当前阶段（已完成，2026-08-12）** | **真实 LLM 全面试用 + 语法/语言功能评估**（`_REAL_LLM_TRIAL_REPORT_20260812.md`） | 验证/发布 | **已完成**：D1 全语法遍历 + D2 压力试用 + D3 批判检测（C1-C4）+ A1-A5 重验全部基于修复后代码真实 LLM 跑通；暴露 4 项 P1 KERNEL_ISSUE（PT-DEBT-25~28）+ 7 DOC_ISSUE + 5 BOUNDARY。**PT-DEBT-25/26/27/28 已修复（2026-08-12）**；REVERIFY 回归通过（`_LLM_TRIAL_20260812/REVERIFY.md`）。报告 §四/§五/§七 已基于修复后代码刷新 |
| **✅ 已完成（2026-08-12，合并执行）** | **unsafe-vibe-dev 合并取代 main**（`_MAIN_MERGE_PLAN.md`） | 发布/稳定性 | **阶段 3 已执行（用户显式授权）**：`git merge --no-ff unsafe-vibe-dev → main`（merge commit `eb4a7d1`，main 树 == unsafe-vibe-dev 树，全量 2308/1 验证通过）+ push main；原 unsafe-vibe-dev 本地+远端删除，从新 main 分支出新 unsafe-vibe-dev（== origin/unsafe-vibe-dev == eb4a7d1）。main 现为稳定基线；日常开发基于新 unsafe-vibe-dev |
| **✅ 已完成（2026-08-12，unsafe-vibe-dev 35bb2de，全量 2339 passed / 1 skipped）** | **用户类泛型参数（PT-FEAT-3 升主线）** | 易用性+架构 | **用户裁定（2026-08-12）升主线 + 本轮完整落地**。设计冻结 `PT_FEAT3_DESIGN.md`（6 项开放问题决断：无约束裸参数/使用面全/裸用禁止/特化名+registry 键/父泛型继承/Enum 排除）。**全链路**：AST `IbClassDef.type_params`+`parent_args` + parser（`class Box[T]`/`(Box[T])`）+ `TypeKind.TYPE_PARAM`/`SymbolKind.TYPE_PARAM`/`TypeDef.type_params` + 语义类型参数占位解析 + `resolve_specialization` 用户类分支（特化 spec 构造 + members 替换 + 父特化递归注册）+ 序列化（type_params/parent_args 落 artifact）+ 运行时（`IbClass.__getitem__` 类型特化 + 特化类 hydration）。**已支持**：多特化并存/字段·方法参数·返回类型特化（含嵌套 `Box[list[int]]`）/嵌套泛型 `list[Box[int]]`/多参数 `Pair[K,V]`/泛型继承 `class Sub[T](Box[T])`。**守卫**：裸用（注解+实例化）/实参数不匹配/字段-T 冲突/Enum 泛型/类型参数遮蔽内置/非泛型子类继承特化 fail-fast。**方法参数类型检查生效**（`Box[int].set("str")` 报 SEM_TYPE_MISMATCH）。**测试**：21 e2e + 2 序列化 round-trip（全量 2311→2339）。**独立复核两轮 PASS**（P2-1 父特化恒注册 / P2-2 嵌套实参映射 全整改）。**文档**：06_oop §6.4 + KNOWN_LIMITS §十四 #1 + arch/02 §2.6 + 15_diagnostics。**边界**（KNOWN_LIMITS §十四#1 ①-⑧）：bound 约束/`class Sub(Box[int])`/父引用嵌套实参/Enum 泛型 为后续增量。当前无阻塞 |
| **✅ 已完成（2026-08-13，unsafe-vibe-dev 0fee0c43，全量 2377 passed / 1 skipped）** | **试用体系规范化** | 工程/验证 | **试用机制体系化 + 日志体系化 + 历史记录整理定型——全部完成**。**Phase 1 机制规范化**（2026-08-13）：单一 harness `trials/_toolkit/run_one.py` + `CLASSIFICATION.md` + DESIGN/REGISTER 模板。**Phase 2 历史定型**：4 套 git mv 迁移 + 编号映射表 + `trials/INDEX.md` 跨套索引。**Phase B 收尾**：T01 57 个 LLM 用例真实重跑 **55 PASS + 2 GUARD**（零 HARNESS/零缺陷复现），断言精化为确定性行。**Phase C**：用户原则**不冻结历史资产、问题直接重构**（唯一底线：不为规避缺陷改套件，缺陷触发用例保留）——删除 40 个过期文档、套件重构（T02 T3/T4/T5 映射有效性 / T04 R1-05/R5-01/R5-04 修复后语义删 b 变体）、4 套 register.jsonl classification 写回 100%。**Phase D**：报告自动生成器 `_toolkit/gen_register.py` + 收敛流程硬规则 `_toolkit/PHASE_D_AUTOMATION.md`（缺陷修复=根因修复+tests/ 回归双交付）。**GEN-5/GEN-6 已修复（2026-08-13，架构级方案 `GEN_FIX_ARCHITECTURE.md`）**。**遗留独立窗口**：供应商感知思考禁用机制（待设计）。设计权威 `TRIAL_SYSTEM_REDESIGN.md` |
| **P0（发布）** | **CI/CD 退役 + 重新设计** | 发布/工程 | **GitHub 侧 CI 自动触发已停用（2026-08-11，`.github/workflows/ci.yml` → `workflow_dispatch`）**。现 CI 与本机 pytest 区别不大、必要性不足；待单独设计"可靠化/实用化"（真实 LLM e2e / 跨平台 / 发布产物）后重新启用，另行规划 |
| **P0（真实 LLM e2e 前置）** | **PT-FEAT-13 api_config 配置机制完备化（C1-C3）**（`_API_CONFIG_DESIGN.md`） | 验证/工程 | 现 api_config.json 非原生加载（脚本约定）、无校验、mock 字符串嗅探。为真实 LLM e2e（本地非思考模型）做**一等配置机制**：**C1 原生加载**（ai 模块/引擎自动，替代每脚本 file/json.parse）+ **C2 set_config 结构化** + **C3 校验诊断**（fail-fast/诊断码，不静默回退 mock）。C4-C7 随 e2e 完善、C8 远期。**C1-C7 已落地（2026-08-11，全量 2161/1）**。**注（2026-08-12）**：F9 用户裁定改显式配置（`ai.autoset`）后，C1 的"引擎自动加载"落地形态同步调整（"原生一等入口"仍成立，只是显式），见 F9 行与 `_code_ai_autoset.md` |
| **当前主线（已完成）** | **PT-DEBT-12/13/14/15 异步地基遗留妥协根治**（`_ASYNC_UNIFY.md`） | 架构健康性 | **统一执行模型闭环——全部收尾（2026-08-09）**。F1→B1→F2/F3→M4 已完成（2026-08-08），M3 已收敛；**M1（.call 双写收敛）/ M2（驱动去重）已完成（2026-08-09，独立分支 exp/async-m1m2，全量 2137/1）**。消"任务内同步重入调度器"遗留旁路 |
| **P1（异步统一完整）** | **异步统一遗留 A1-A6**（`_HEALTH_AUDIT_PLAN.md`） | 架构健康性 | 地基闭环后 6 处**次要路径**仍任务内同步重入/嵌套调度器：**A1-A4 已完成（2026-08-10，全量 2138/1）**；**A5 类构造已根治（2026-08-11，`_ClassInstantiateDrive` CPSDrivable，全量 2137/1）**；**A6 协议方法 `.call` 评估维持现状（2026-08-11，niche + 条件触发，CPS 化成本高收益低，登记已知项）** |
| **P1** | **PT-DEBT-17 `ai.run_batch` 同步阻塞**（统一执行模型冲突） | 架构健康性 | **已彻底修复（2026-08-11，unsafe-vibe-dev ebbb7f8，全量 2135/1）**：`run_batch` 返回 `CPSDrivable` Waitable（CPS 预求值 `_prepare_behavior_call_cps` 消除 vm.run 重入 + 多 LLM Future 聚合 `LLMBatchFuture` 由调度器非阻塞等待，与 `stream_call` Waitable 范式一致）。vtable return_type=list 契约不变（auto-yield 后仍收 boxed IbList）。顺带清理死代码 `resolve()`/`LLMFuture.get()`。`ihost.collect`/`run_isolated` 为透明异步 auto-yield（非问题，已澄清） |
| **P0** | 阶段 5 增量（`next()` 内建 + `yield from`） | 易用性 | **已完成（2026-08-09，全量 2128/1）**：`next()`（c61a6e0）+ `yield from` 生成器委托。设计 `_code_yield_from.md` |
| **P0** | PT-FEAT-5 错误用户友好化 | 易用性 | **已完成三项（2026-08-09）**：诊断码目录 + 符号表/类型绑定导出 + 编译基准。**CI/CD 已停用 GitHub 侧自动触发（2026-08-11 用户裁定）**——现 CI 与本机 pytest 区别不大、必要性不足；待单独设计"可靠化/实用化"后重新启用 |
| **P1** | PT-FEAT-10/11/12 UID/序列化统一 | 架构健康性 | **PT-FEAT-10 已完成（2026-08-09）**；PT-FEAT-11（序列化器自动化）、PT-FEAT-12（AST uid 字段）评估为维持现状（见下） |
| **P1** | PT-DEBT-4 `file` 模块重命名 | 架构健康性 | 影子化 Python 内建，长期隐患；破坏性变更独立窗口 |
| **P1** | **技术手册健康待修**（P1/P2） | 文档健康 | 三修**已完成（2026-08-10，PT-DOC-3）**：`01_principles.md:258` 过时 `inherit_intents`、`04_vm_interpreter.md:29` `.call` 表述、`README` 目录树补 `15_diagnostics.md`。剩余 How-to 层缺口为 P2 规划 |
| **P2** | PT-AUDIT-1/2 + R4/R5 | 架构健康性 | 长期周期清扫，阶段边界启动。**R4 覆盖率核对已执行 + R5 聚焦治理已执行 + PT-AUDIT-1 smell 全量事实回顾已完成（2026-08-09）**；**`runtime_serializer._collect_instance` 巨型 elif 链已拆具名 collector（2026-08-11，unsafe-vibe-dev 4592636，纯可读性/整洁性重构）**；PT-AUDIT-2（分支嵌套）剩余：`_get_instance`（已按 `_type` 干净分派，可选对称）、`core_scanner` 深度10 状态机、`binding_analysis` 深度9 AST 访问者（惯用模式，维持现状）待独立窗口 |
| **P1（下一 session 主线）** | PT-FEAT-2 Enum 非 str 成员 + 迭代能力 | 易用性+长远 | **✅ 已完成（2026-08-12，unsafe-vibe-dev，全量 2308/1）**：① 非 str 枚举 LLM 集成修复（编译期常量成员写 `MemberSpec.metadata["value"]`，EnumAxiom 成员名→值映射，含负数 `-1`；str 零回归/值≠名正确，真实 LLM 实证 qwen 成员名→值 200→switch 命中）；② 迭代 `for v in Color:` / 数量 `len(Color)`（has_iter_cap + get_method_specs + 运行时 Enum 基类绑定）；③ 自定义方法 = **值模型边界**（`Color.RED` 是底层值非实例，方法不可达）——实例化枚举为独立设计候选（`_code_enum_completion.md`）；④ KNOWN_LIMITS §二 更新。**遗留**：**枚举实例化设计窗口**（`_enum_instancing_assessment.md`——评估结论维持现状：LLM 集成改造为核心硬伤（kernel 层无法构造实例 + 通用解析路径需类型感知包裹），爆炸半径不确定，独立设计冻结候选） |
| **P3** | PT-FEAT-8 `.ibc_meta` 快照 / PT-FEAT-4/7 / PT-FEAT-6 | 长远 VISION | 概念验证阶段 / 前置条件多 |
| **暂缓** | PT-DEBT-5 文件命名清理 | 架构健康性 | 破坏面大纯机械，独立窗口 |
| **当前阶段（LLM e2e 已完成，不合格操作待重修）** | ~~**PT-DEBT-18 generator IbClass 注册 + IbGenerator.receive 特判回退**~~（`_HANDOFF_ISSUES_LLM_E2E.md` U1）**已修复 2026-08-11** | 架构健康性 | **修复方式**：新建 GeneratorAxiom（`core/kernel/axioms/primitives/generator.py`，声明 to_list/generic_next 方法规格）+ `GENERATOR_SPEC` 注册（specs.py + _runtime.py）+ `@register_ib_type("generator")` 于 IbGenerator（kernel/__init__ 导入触发）+ **删 IbGenerator.receive 特判** + leaf.py:373/392 改 `get_class("generator")` 优先。契约测试 `test_generator_ibclass.py`（GEN-1~4：generator 类注册 + vtable + 值身份 `type(gen)` = "generator" + 用户显式 .to_list()/.generic_next() 协议分发）。全量 2176/1 零回归（+4 契约 +3 meta 派生） |
| **当前阶段** | ~~**PT-DEBT-19 内建遮蔽 + LLM 表达式 UID 解析缺陷**~~（`_HANDOFF_ISSUES_LLM_E2E.md` U2）**已修复 2026-08-11** | 编译器正确性 | **真实根因（比交接推断更精确）**：编译器对模块级带类型声明 `int X = ...` 统一绑定既有 intrinsic 符号 UID（字面量/LLM 同 `intrinsic:X`），遮蔽语义由运行时 define 承担（`_vm_assign_to_target` define_only 路径）；但 dispatch-before-use 路径 `_assign_future_to_name_target`（`_shared.py`）在符号已存在时原地覆写 `.value` 而非 define → intrinsic 常量符号被写入 LLMFuture，使用点回写触发 `Cannot reassign constant`。**修复**：`_assign_future_to_name_target` 增加 `define_only` 参数（与 `_vm_assign_to_target` 同构），IbTypeAnnotatedExpr 递归置 True，定义路径恒走 `define_raw` 创建全新用户符号（遮蔽语义正确）。函数局部声明本就生成新局部符号 UID，不受影响。**验证**：`int sum/@~...~/int len` 遮蔽 LLM 初始化全通（+2 回归测试）；示例 01_hello_world.ibci 改回 `int sum`（真实跑通 mock 10）。全量 2178/1 零回归 |
| **当前阶段** | ~~**PT-DEBT-20 InterpreterError 双实现统一**~~（`_HANDOFF_ISSUES_LLM_E2E.md` U3）**已修复 2026-08-11** | 架构健康性 | **修复**：`core.extension.exceptions` 删除 `InterpreterError` 定义（历史遗留重复，无 error_code 能力）；公开名 `core.extension.InterpreterError` 改指 `core.kernel.issue.InterpreterError`（IBCBaseException，error_code/location/severity 能力完备）——公开契约保持；清理 ibcext.py 死 import（三个异常类均未使用）；__init__.py 直接导入。+3 契约测试（公开名同一类 / error_code 能力 / 无重复定义）。全量 2181/1 零回归。**注**：extension.exceptions 的 PluginError/CompilerError 仍为 SDK 独立类型（构造契约与 kernel 版不同，未纳入 U3 范围，无重复名冲突） |
| **当前阶段** | ~~**PT-DEBT-21 AIPlugin.setup 自动加载路径规范化绕过**~~（`_HANDOFF_ISSUES_LLM_E2E.md` U4+U6+U7）**已修复 2026-08-11** | 安全 | **U4**：config_path 经 `PathValidator.canonicalize_for_security` 规范化（插件层统一走符号链接解析机制）。**U7**：三重 if 收敛为 fail-fast 契约——execution_context/project_root 缺失=注入异常（InterpreterError），api_config.json 不存在=合法态静默跳过。**U6**：测试显式传 project_root=None 表意 + ExecutionContextImpl 类契约文档（生产必传，消费方对 None fail-fast）。+4 契约测试（含符号链接 project_root 加载验证）。全量 2185/1 零回归 |
| **当前阶段** | ~~**PT-DEBT-22 意图一次性/排他（@/@!）dispatch-before-use 路径丢失**~~（commit 7339220）**已修复 2026-08-11** | 语义正确性 | **真实缺陷（原被误判为'模型服从性'）**：`fork_intent_snapshot()` 把 @ smear / @! override 移入快照 `_inherited_*` 槽位，`_prepare_behavior_call`（sync+CPS）captured 分支只取 active/global → 赋值+并行预调度下 @/@! 从未进 prompt。**修复**：`IbIntentContext.resolve_to_prompts(+cps)` 单一权威消解（override>smear+active>global）+ `get_resolved_prompt_intents` 委托 + captured 分支改快照方法。真实模型实证 qwen3.6 遵循意图（'你好。'）。+6 回归测试。全量 2194/1 |
| **当前阶段** | ~~**PT-DEBT-23 配置机制 fail-fast 硬化**~~（commit 0eb8939，F1-F7）**已修复 2026-08-11** | 工程正确性 | general agent 独立彻查上一批次发现（自审计 D 段误标'正确'）：**F1** `{env:VAR}` 格式非法静默透传→残留检测 fail-fast；**F2** IBC_TEST_MODE 隐式覆盖显式 set_config→删 env 分支（mock 显式化）；**F3** load_config 锚 entry_dir vs setup 锚 project_root 分叉→统一锚 project_root；**F4** reasoning:true 不对称→对称落 probed/is_reasoning；**F5** extract_strategy/supports_system 死字段→删除；**F6** 空/空白凭据过校验→_require_nonempty+_init_client fail-fast；**F7** 默认值字面量三重复→引用 config_loader 常量。+5 契约测试。全量 2201/1 |
| **✅ 已清理（2026-08-12，unsafe-vibe-dev）** | **PT-DEBT-24 call_intent 预留机制死代码清理**（T2 审计发现） | 架构健康性 | `IbBehaviorExpr`/LLM 函数 AST 均无 intent 字段 → 所有调用方 call_intent 恒 None → 死代码全链清理：`_prepare_behavior_call(_cps)` auto_intent 关闭短路分支 + BehaviorCallSpec.pre_resolved + execute_behavior_expression_cps 参数 + execute/invoke_llm_function_cps 穿透参数 + IbBehavior.call_intent 值字段（含 meta 序列化/工厂/协议）。保留 `get_resolved_prompt_intents` 的 call_intent 协议预留参数（docstring 注明未消费）。全量 2308/1 零回归 |
| **✅ 已完成（2026-08-12，unsafe-vibe-dev a49555b，全量 2311 passed / 1 skipped）** | **F9 配置副作用显式化**（T4 审计发现） | 设计评估 | 真实配置 + 未装 openai 时 `import ai`/引擎启动即抛 RuntimeError（setup 自动加载 api_config.json → apply_config → set_config → _init_client）。**用户裁定（2026-08-12）：改为显式配置，命名拍板 `ai.load_project_config`，本轮实施**。**落地**：`setup()` 去自动加载段（仅保留 capabilities.expose）；新增 `load_project_config()`（ec/project_root 缺失 fail-fast + 路径规范化 + 缺失 no-op 合法态 + 存在即加载校验应用 + 幂等）；`_spec.py` vtable 注册；测试 TestEngineExplicitConfigLoad（无调用不加载/显式调用加载）+ TestLoadProjectConfigContract（fail-fast/no-op/符号链接/幂等）+ 语言级可达；examples 01/02/03 判断前加 `ai.load_project_config()`；文档同步（README/guide 01+02/syntax 11+15/config_loader/execution_context/catalog/codes）。独立复核 PASS（5 项整改全完成）。设计记录 `_code_ai_autoset.md` + 实施记录 `_code_f9_load_project_config.md` |
| **P2** | **PT-AUDIT-3 双路径分裂专项审计**（T1/T4 教训驱动，新增） | 架构健康性 | 意图缺陷（PT-DEBT-22）揭示"双路径语义分裂 + 快照半消费 + 自审计不可全信"三类模式；T4 独立审计已证明 general agent 能发现自审计 D 段误标的真问题。**对近期子系统做独立审计**：异步统一 A1-A6 / run_batch CPS（exp/run-batch-cps）/ yield 生成器 / generator IbClass / llmexcept / M1-M2 调用收敛——专项查：① sync vs CPS 孪生语义一致；② 快照/双路径"复制完整消费部分"；③ 自审计标注"正确"但实际漂移。用 general agent 独立执行 + 主代理交叉核验。**已执行（2026-08-11，general agent 独立审计 + 主代理核验）**：无 P0；3 确凿 P2 漂移已修复（run_batch 观测 / active_intents 漂移 / _drive 装箱一致）+ generator 兜底 fail-fast + KNOWN_LIMITS §二十四 机制描述修正（commit df1a896）。**疑似项处置（2026-08-12）**：① **S4 已根治**（PT-DEBT-24 call_intent 死代码全链清理）；② **S5 部分处置**（共享 axiom hint 查找抽单一实现，vtable 驱动分支保持各自驱动）；③ **S1/S2/S3 复核为已知边界**（S1 dispatch hint 同步 .call 嵌套调度器仅 hint 含 VM 依赖 Waitable 时可观察，niche；S2 跨线程 EC 模块名改写需 worker 同步构造类且 drive 返回非实例，路径非预期；S3 task 线程写单写槽为纯可观测性竞态，GIL 下无崩溃）——均登记待独立设计窗口，见 `_PT_AUDIT3_RECORD.md` §三 |
| **✅ 已修复（2026-08-12，unsafe-vibe-dev，全量 2252 passed / 1 skipped）** | **PT-DEBT-25/26/27/28 已根治** | 架构健康性 | 按 `_FIX_PROPOSAL_CRITICAL_REVIEW_20260812.md` 修正后方案执行。**PT-DEBT-25（global）**：symbol_resolution_pass 加 visit_IbGlobalStmt + prescan 排除 global 名（镜像 nonlocal），运行时零改动；+6 测试。**PT-DEBT-26（整模块 import）**：档3 写入侧 `_symbol_to_member` 统一 Symbol→MemberSpec/MethodMemberSpec（scheduler.py）+ 档2 `_expression_visitors` 零参数 callable 按 kind 绑定（不再退化 any）；+4 测试。**PT-DEBT-27（异常逃逸）**：`_drive_loop_gen` Waitable yield 加 except Exception 重投递 pending_exception（与值投递对称，TaskCancelled 穿透）；+4 测试。**PT-DEBT-28（ai vtable）**：`_spec.py` 补 get_retry/is_auto_intent_injection_enabled 注册；+3 测试。独立复核三修复全部 PASS（含 TaskCancelled/UnhandledSignal/异常沿 CPS 栈上抛验证）。**遗留**：嵌套包 `import subpkg.util` + `subpkg.util.fn()` 的 INT_INTERNAL_ERROR 为修复前既有缺陷（git stash 实证非本批引入）——中间模块符号以 VariableSymbol(kind=MODULE) 形态经 `import subpkg` 注入，成员访问仍触发 type_ref 缺失；待独立窗口（与 PT-DEBT-26 同族形态问题） |
| **✅ 已修复（2026-08-12，unsafe-vibe-dev，全量 2252 passed / 1 skipped）** | **PT-DEBT-O1/I1/O2 + 生成器/文档修正** | 架构健康性 | 按 `_FIX_PROPOSAL_CRITICAL_REVIEW_20260812.md` 批次 C/D 执行（用户授权破坏性变更）。**O1（可调用类实例 obj()）**：`IbObject.receive('__call__')` 对含用户 `__call__` 的类实例返回 `_UserCallDrive`（Waitable+CPSDrivable，与 A5 `_ClassInstantiateDrive` 同构），VM 经 cps_drive 帧内驱动（UserFunctionCall trampoline）——根治嵌套调度器（EXEC-1 深递归 Python 深度恒定恢复 + Waitable 协作挂起）；receive 保持唯一协议分派，VM 侧零新特判；+5 测试（含深递归 depth=400/fn 引用/LLM await/chan await）。**I1（生成器 __iter__）**：`IbUserFunction.call` 对生成器方法返回 IbGenerator（make_generator_driver 同构）+ `resolve_iterable` 对 __iter__ 返回的 IbGenerator 做 to_list——修复 `for x in obj` 的 GeneratorYield 崩溃，附带修复 `yield from <生成器 __iter__ 实例>`；+4 测试。**O2（字段默认值）**：static_val 改经 `try_deep_clone` 递归深克隆（补全"每实例独立默认值"既有意图，非语义反转；不可克隆值回退共享引用）——消除内层 list/用户对象跨实例共享；+3 测试。**文档**：05_functions §5.8/§5.9（for=to_list 急物化）、KNOWN_LIMITS §二十四（await 阻塞消费可用）、§十四 #2（运算符可重载）、§一（可调用实例已 CPS 化）修正。设计记录 `_code_call_cps_drive.md` |
| **✅ 已修复（2026-08-12，unsafe-vibe-dev，全量 2270 passed / 1 skipped）** | **试用易用性修复**（`_USABILITY_AUDIT_20260812.md`） | 易用性 | 用户观察"`while true` 无法工作"驱动系统审计。**① return@~ 编译期拦截随迁 v2**（v1 曾实现，v2 语义重构 afe9644 时未随迁→设计意图丢失；visit_IbReturn 补全拦截报 SEM_TYPE_MISMATCH，消除"文档说禁止实际通过+运行时类型错"陷阱；+4 测试）。**② switch 内 break 消费为 no-op**（IBCI switch 无 fall-through，break 是 C 冗余写法；vm_handle_IbSwitch 消费 BREAK、CONTINUE 透传外层循环，不再报 RUN_GENERIC_ERROR；+3 测试）。**③ 布尔字面量错误引导**（true/false/none 未定义报"Did you mean True/False/None"，不推翻 Python 对齐设计；+3 测试）。**④ KNOWN_LIMITS §十一 更新**（switch 基本可用 + 使用约束）。**根因**：① 重构丢失；② C 习惯冗余；③ 有意 Python 对齐（3c6d137 true→True）；④ 过度保守 |
| **✅ 已处置（2026-08-12，unsafe-vibe-dev）** | **DOC-ISSUE-001~007 + BOUNDARY-001~005**（`（已清理任务文档）`） | 文档/边界 | **全部处置**：DOC-ISSUE-001（02_variables §2.6 补 `-> void`）/002（9 处 `__init__` 补 `-> auto`）/003（14.6 await thread 矛盾修正）/004（stream_call 签名）/005（howto thread_result `.value()`）/006（§十二 警告可见性精确化——编译期诊断经 issue tracker，运行时不打印）/007（`__from_prompt__` 契约 `(bool,实例)`）。BOUNDARY-001（for=to_list 物化，§5.8/§5.9 已核验一致）/002（§二十四 已修）/003（§11.6 隔离不继承 LLM 配置明示）/004（§9.1 `@!` run_batch 粒度说明）/005（§11.3 probe_model 推理判定说明）。详见 commit 6f8506d |
| **✅ 已修复（2026-08-12，unsafe-vibe-dev，全量 2296/1）** | **嵌套包 `import subpkg.util` + 成员访问 INT_INTERNAL_ERROR** | 架构健康性 | 根治（PT-DEBT-26 同族形态遗留，修复前既有）。三层根因：① 调度器嵌套 import 把原始 Symbol 入 members（resolve_member 崩）；② visit_IbImport 绑定全名而 scheduler 只注入根段；③ 中间段 create_primitive 产出 PRIMITIVE kind 重导入守卫恒真 + 运行时缺包命名空间。修复：嵌套段统一 MemberSpec + 中间段 create_module 全名注册 + 绑定根段 + `_bind_package_chain` 运行时合成 IbModule 包命名空间（幂等合并）。2层/3层/同包多导入合并全过；+4 e2e（`test_ibc_file_imports.py` TestIbcFileNestedPackageImport）。**遗留**：`import subpkg`（纯包目录无模块）DEP_MODULE_NOT_FOUND（Python 同语义，包须含可导入模块） |
| **✅ 已修复（2026-08-12，unsafe-vibe-dev 32484fe，全量 2350 passed / 1 skipped）** | **KERNEL-ISSUE-G2 泛型类自引用字段特化替换失效（编译期）** | 架构健康性 | **现象**：`class Node[T]: Node[T] next` 特化后 `n1.next = Node[int](2)` 报 `Cannot assign 'Node[int]' to 'Node[T]'`（SEM_TYPE_MISMATCH）。**根因（深度核验实证）**：字段构造 `TypeRef.from_spec(Node[T] spec)` 对 CLASS kind 落**默认 fallback**（`TypeRef(get_base_name())`）→ 扁平化为 `TypeRef('Node[T]')`（head 含方括号、args 空）；`TypeRef.substitute` 对扁平形态无法替换。**修复**：TypeDef 新增 `type_args`+`base_name` 字段，`_specialize_user_class` 填充，`from_spec` CLASS 特化 spec 结构化构造（`TypeRef('Node',(int,))`），serializer/rehydrator 持久化保真。`Node[T] next` 特化后 `Node[int]`，赋值/递归特化均正确。+3 e2e。**P1** |
| **✅ 已修复（2026-08-12，unsafe-vibe-dev 32484fe，全量 2350 passed / 1 skipped）** | **KERNEL-ISSUE-G1 泛型方法体内类型参数表达式运行时失效（运行期）** | 架构健康性 | **现象**：`func make(self, T v) -> Box[T]: return Box[T](v)` 运行期 `Variable UID 'Box:T' is not defined`。**根因**：编译期语义正确（slice T 绑 TYPE_PARAM 符号，UID=`Box:T`），但运行时类型参数不产生变量、UID 未注册 → `vm_handle_IbName` 失败。**修复**：`IbFunctionDef.type_param_uids` 编译期收集（binding_analysis 进入类作用域解析 TYPE_PARAM [name,uid] 对），运行时 `_bind_type_params` 按 receiver 特化实参注册类型参数符号（简单实参→IbClass；嵌套实参→boxed 特化名，对齐 `_specialize` 内置泛型标识机制）。方法体内 `Box[T]` slice T 求值为类型标识，多特化/嵌套实参全正确。+6 e2e。**P1** |
| **✅ 已修复（2026-08-12，unsafe-vibe-dev 3fe98d6，全量 2350 passed / 1 skipped）** | **BOUNDARY-G1 非法特化实参编译期未拦截** | 架构健康性 | `Box[42]`/`Box[None]` 原编译通过、运行期裸 `AttributeError`；`Box[None]` 注解位置还产生幻影 `Box[None]` spec（赋值误报 SEM_TYPE_MISMATCH）。**修复**：注解+表达式位置字面量 slice（`Box[42]`）与哨兵类型实参（`None`/`auto`；`void` 按 base 收窄——仅内置 `thread[void]` 合法）报 `SEM_GENERIC_TYPE_NEEDS_ARGS`。+4 e2e。**P2** |
| **✅ 已修复（2026-08-12，unsafe-vibe-dev 32484fe，全量 2350 passed / 1 skipped）** | **双通道设计缺陷：特化方法参数 descriptors 替换两套实现** | 架构健康性 | `_substitute_members`（真实 mapping dict 驱动）与 `_sync_specialized_members`（**字符串解析特化名反推 mapping**）是同一语义的**两个实现**，违反工作模式定论第 3 条 + design-philosophy §四。**修复**：特化 spec 新增 `type_args` 字段（结构化实参，`_specialize_user_class` 填充），`_sync_specialized_members` 改用 `type_args`+基类 `type_params` 配对——**删除字符串反推**（`_type_param_mapping`/`_split_top_level_args`/`_parse_type_ref_name`），单一权威源。嵌套实参方法参数类型检查仍正确。**P2** |
| **✅ 已修复（2026-08-13，unsafe-vibe-dev b0f4d74，全量 2365 passed / 1 skipped）** | **KERNEL-ISSUE-G3 继承特化 + 父类字段值丢失** | 架构健康性 | **交接诊断纠偏**：并非"特化父类字段未绑定"（`Node[int].default_fields` 含 `data`/`next`，继承链收集正确）。**真实根因**：`_hydrate_user_classes` 自动构造器只收集**类自身 body** 的无默认值字段 → 子类 auto-init 参数被削减并遮蔽父 auto-init → `Linked[int](5)` 把 5 绑到 `tag`、`data` 静默 None。**非泛型同构复现**（`Sub(Base)`+单参→父字段静默 None），且原为文档化 Known Limit（KNOWN_LIMITS §六）——按"文档化限制是修复候选"重新定性为真实缺陷。**修复（chain-aware auto-init）**：自动构造器参数 = 继承链全部有效无默认值字段（父类优先、子类同名覆盖），与 instantiate 字段收集同构（机制同构）；构造器生成拆为独立第二 pass（父类字段须已 hydrate）。非泛型/泛型/多级继承全修；少传参 fail-fast 报缺参（不再静默错误值）。+7 e2e。**P1** |
| **✅ 已修复（2026-08-13，unsafe-vibe-dev b0f4d74，全量 2365 passed / 1 skipped）** | **BOUNDARY-G2 自引用链 while 遍历"类型退化"** | 架构健康性 | **交接诊断纠偏**：并非运行时类型退化（探针实证 `cur` 持续保持 `Node[int]`）。**真实根因**：试用用例设计无效——`Node[int]` 编译期禁止赋 `None`（SEM_TYPE_MISMATCH），`while cur is not None` 哨兵在非 Optional 字段上类型不可行；且 `nodes[2].next` 未赋值，默认 `= any` 产出非 None 的 truthy any 类对象，循环永不终止。**附带根治 Finding C**：`_check_type` 对 USER_DEFINED CLASS 目标无条件跳过运行时复查 → any 类对象静默流入用户类变量（§七 契约失效），现对动态 any 逃生值强制 `RUN_TYPE_MISMATCH`（is_assignable 因"类可调用"会放行，直接判定）。R5-04 现报清晰 `RUN_TYPE_MISMATCH` 而非困惑 AttributeError。+3 e2e。**P2** |
| **✅ 已修复（2026-08-13，GEN-FIX 架构级方案，commit c00c87bb，全量 2377 passed / 1 skipped）** | **KERNEL_ISSUE-GEN-5 用户泛型类下标表达式位置特化未注册** | 架构健康性 | **根因**：表达式位置 visit_IbSubscript 仅处理裸 IbName slice，嵌套 IbSubscript（list[int]）/IbTuple 落空 → 编译期未注册特化 spec → 运行时 _specialize 抛错；注解路径已有递归实现，机制同构缺失。**修复**：用户泛型特化分支 slice 解析复用 _resolve_type 递归（IbTuple 逐元素/嵌套/单元素），复用其 None/auto/void 守卫+list 多参拒绝+数量校验。**判别性回归 +5**（test_user_class_generics TestExpressionPositionSpecialization）；**触发用例 GEN5-01 核销（PASS）**。**补充记录**： **现象**：`Box[list[int]]`（内置泛型 list 作实参的用户类特化）在**表达式位置**（如 `print(type(Box[list[int]]))` 的 type() 参数）求值时运行时 `_specialize` 报 `Generic class 'Box' has no registered specialization for type 'list[int]'`（R5-04 组合用例 Box 部分首次触发；探针实证最小形态仅需 Box 泛型类 + 表达式位置下标）。**git stash 实证为预存缺陷**（与 2026-08-13 G3/Finding C 修复无关）。**根因方向（探针实证）**：编译期对表达式位置的 `Box[list[int]]` 未注册特化 spec；对照注解位置 `Box[list[int]] bl = ...` 会触发编译期注册、正常运行。**触发用例**：`trials/T04_generics_fix_regression/cases/GEN5-01-nested-specialization.ibci`（持续复现证据，修复后应输出 `box_slice=Box[list[int]]`）。**P2**，独立窗口深挖（可能同源影响其它表达式位置泛型下标） |
| **✅ 已修复（2026-08-13，GEN-FIX 架构级方案，commit 8f7fff8a/52e7992f，全量 2377 passed / 1 skipped）** | **KERNEL_ISSUE-GEN-6 泛型运算符方法参数含 T 的特化未生效（G1 修复不完整）** | 架构健康性 | **记录根因纠偏**：非"运算符方法签名特化路径分叉"（substitute/_sync_specialized_members 对运算符与普通方法同等处理），而是 **根因 A**（解析端）_inference.resolve_op 用 resolve(return_type.head) 丢弃实参，把特化结果降级为基类（触发因子是 `-> Vec[T]` 返回类型，非参数形态）+ **根因 B**（构造端）_param_type_ref 用 TypeRef.of(name) 扁平化泛型类参数致 substitute 失效（影响所有 Vec[T] 形态参数方法）。**修复**：解析端 14 个 .head 解析点迁移 resolve_typeref（8f7fff8a）+ 构造端 _param_type_ref 复用 from_spec/engine 扁平残留/to_typeref 委托收敛（52e7992f）。**判别性回归 +6**（test_operator_overrides TestGenericOperatorOverrides +3 / test_user_class_generics TestGenericMethodParamDescriptor +3）；**触发用例 D2-01 核销（PASS）**。**补充记录**： **现象**：`class Vec[T]: func __add__(self, Vec[T] other) -> Vec[T]: return Vec[T](...)`（运算符方法**参数类型含 T**）编译期报 `SEM_TYPE_MISMATCH: Cannot assign 'Vec' to 'Vec[int]'`（D2-01，`Vec[int] c = a + b`）。**G1 修复（32484fe）覆盖了方法体 `Box[T]` 构造/返回（T04 R2 组：参数为裸 `T v` 全通过），但运算符方法参数 `Vec[T] other`（参数类型嵌套用户泛型类 + T）的返回特化未生效**——T04 回归用例参数均为裸 T，未覆盖此形态。**触发用例**：`trials/T03_user_class_generics/cases/D2-01-operator-override.ibci`（断言为修复后期望 `cx=4|cy=6|eq=True|neq=False`，当前报编译错）。**P1**（运算符重载 + 泛型组合不可用），独立窗口深挖（`_sync_specialized_members`/`_substitute_members` 对运算符方法签名的特化路径） |
| **🟡 待设计（2026-08-13 用户提出，`LLM_SERVICE.md` 记录）** | **供应商感知的模型思考禁用机制** | 架构健康性 | **背景**：qwen3.6-35b-a3b 在 LM Studio 强制思考，`enable_thinking=false`/`thinking.enabled=false`/`chat_template_kwargs` 全参数实测无效（后端强制，API 无法关闭）。**LM Studio 官方机制（2026-08-13 专项调查，modelyaml 文档实证）**：思考由 `model.yaml` 的 `customFields.enableThinking`（effects: setJinjaVariable → `enable_thinking`）+ Jinja 模板 `enable_thinking` 变量控制（false → 空 think 标签）；qwen3.6-35b-a3b 在 LM Studio Hub 有官方 model.yaml，**本机用纯 GGUF（无 model.yaml）→ 参数无效**。**待办**：① 本机 LM Studio 启用官方配置（界面 Hub 添加或补 model.yaml + 重载，验证 enable_thinking=false 生效）；② IBCI 按供应商参数形态实现思考禁用/检测失败覆盖（LM Studio/llama.cpp `chat_template_kwargs.enable_thinking`、vLLM `chat_template_kwargs`、Ollama 模型模板、OpenAI `reasoning.effort`（Responses）、Anthropic `thinking.budget_tokens`、Gemini `thinkingConfig` 等），逐供应商探测禁用有效性 + 失败警告（现有警告引导联系开发者/提交 issue，不引导改配置绕开）。**P2**，独立设计窗口 |
| **✅ 已修复（2026-08-13，unsafe-vibe-dev 80294a64 + 447ad35c + 7a15c1b9，全量 2559 passed / 1 skipped）** | **内置泛型赋值类型检查缺失泛型实参校验（缺陷一）+ 内建泛型值层类型擦除（缺陷二）** | 架构健康性 | **两缺陷统一根治（统一根因=内置泛型与用户类泛型类型身份模型双轨不对称）**。**缺陷一**（80294a64）：`is_assignable` 在 axiom 兼容前做同家族结构化实参比较（`_generic_spec_args` 按 kind 提取实参 + `_generic_family_compatible` 沿 axiom 父链处理 behavior→fn_callable 跨家族），10/11 类 `X[int]→X[str]` 编译期拦截；协变（list[int]→list / dict[str,int]→dict[str,any]）保留；bool isa int / Optional 分支 / 裸→特化语义不破坏。**缺陷二**（447ad35c+7a15c1b9）：内置泛型特化 spec 水化为运行时特化类——ArtifactLoader 加载期预创建特化类（sealed 前）+ IbClass._specialize 内置泛型下标水化（sealed 回落 boxed 字符串）+ 编译期容器字面量 RHS bind_type + VM 字面量 handler 按特化类绑值 + 值层分派沿 spec 基名统一（deep_clone/is_sequence_value/runtime_serializer/thread args）。效果：`type(list[int]值)=list[int]`（原 list）、运行时值层可区分 `list[int]`/`list[str]`（缺陷一+二联动 is_assignable 拦截）、深克隆/同引擎序列化 round-trip 保真、嵌套泛型外层/内层字面量值身份、跨家族行为实参校验。判别性回归 +25（compiler 23 + e2e 12 + runtime 白盒 4，去重后）；触发用例 G6-01（GUARD）+ G6-02（PASS）。**独立复核（general agent）发现 3 项全部整改**（dict 协变假拒绝 / boxed 回落防御 / 跨家族实参残留）。**值层身份彻底收敛（2026-08-13，`_code_generic_value_convergence.md`）**：§2.6 全部边界（函数返回/调用实参/下标赋值/嵌套内层/切片/Optional/跨引擎）已收敛——统一"类型上下文→字面量"递归传递机制覆盖全部容器字面量产生路径（含 lambda/复合赋值/条件/默认参数/for 源/生成器 yield/运算符），两轮独立复核零风险，全量 2579/1。**第三轮扫描再修**：generator 双包+value_type 序列化（`7de1818c`）/ 元组解包容器身份 / `_contains_yield` lambda 误标（`2586/1`）。**🔴 下一 session 交接任务（用户裁定 2026-08-13，全部纳入彻底修复可能性分析）**：交接文档 `（已清理任务文档）`——① 句柄类值身份未水化（thread/chan/slot/generator/thread_result 值 type() 裸名，根治可能高，机制同构已备）；② `_rehydrate_type_pool_spec` 按 name 匹配（跨引擎多模块同名理论误选，低风险低成本）；③ generator value_type 嵌套扁平化 + `_slice_type_objs_for` 残缺实参；④ 元组解包错误类型不检查（`["x"]` 赋 list[int]）；⑤ `-> auto` 泛型实参推断（auto 语义不保留实参）；⑥ `*expr` 展开实参（部分缓解：元素级值身份）；#7 与 #1 同根因合并。每项含现状/根因/根治方向/工作量/建议顺序。设计冻结 `（已清理任务文档）` + `_code_generic_value_convergence.md` + `_HANDOFF_GENERIC_REMAINING.md`。**⚠ 地基深挖分析（2026-08-13，`_DEEP_ANALYSIS_TYPE_SYSTEM_FOUNDATION.md`）**：三路并行 general subagent 交叉比对 + 实证探针证实——7 项边界中 6 项（除 #6 语言级根本限制）同源于同一地基缺陷：类型身份自始是“扁平字符串名”单一权威 + TypeRef 平行并存的双轨模型，泛型特化在唯一创建点（resolve_specialization）把嵌套实参扁平化（`TypeRef.of('list[int]')`）。派生缺陷链：descriptor 双真相致错误类型静默放行（`Box[int].make(list[list[str]])` 编译通过）、get_base_name() 双轨致运行时 `_impl_cls` 失效、句柄类值创建点无 node_to_type 侧表、sealed 运行时字符串魔法回落、声明机制半成品（serialize/restore 手写并联表 7+ 处）、序列化多信息丢失（get_references 死通道/type_ref 死字段/module 出生即丢）。**根治方向 = `GenericTypeDeclaration.build` 与 `SpecFactory.create_*` 从字符串接口升级为结构化 TypeRef 接口**（改一处治愈 B/C/D/G/H 下游）。已修四轮（GEN-5/GEN-6/spec→TypeRef/值层身份收敛）属症状层修复，未回填根基。**✅ 根治方案已冻结（2026-08-13 v2 重启分析修正，`_TYPE_SYSTEM_REBUILD.md`）**：用户裁定要摆脱历史错误设计、从架构远景判断。**v2 决定性修正**：不是拉回原始架构意图——原始文档 §8.1 纯函数 substitute 是擦除式方向，照搬会回归 `type(list[int]值)=list[int]` 运行时身份特性（C#/Kotlin reified 现代主流 vs Java erasure 过时）。当前物化特化类路线正确，修的是物化路线内实现缺陷：桩1 build/create_* 字符串→结构化 TypeRef 接口（创建点扁平化根治，保留物化注册）；桩2 get_base_name 单义 + 句柄类值身份物化覆盖完整；桩3 特化生命周期声明驱动（删 per-kind 手工表）；桩4 module 承载。**分阶段 S0-S7**（独立分支 exp/type-identity-rebuild）：S1 桩1/S2 descriptor 双真相/S3 桩2/S4 桩3/S5 桩4/S6 元组解包+auto 推断+*expr/S7 文档治理。每阶段全量零回归 + 判别性回归 + 独立复核 + cherry-pick 更新 unsafe-vibe-dev；不触碰 main。**非目标**：不改为擦除式、不删物化注册、不重写 TypeRef、不动 Axiom 字符串边界。**✅ 跨模块同名类运行时类表 module 化已根治（2026-08-14，`exp/runtime-class-module`，全量 2614/1 零回归 + 独立复核放行）**：S5 编译期 module 化的运行期闭环——`KernelRegistry._classes`/`Bootstrapper._class_registry` 注册键 = `spec.qualified_name`（geo.Box/graph.Box 独立 IbClass），`get_class(name, module)` module 感知，`_specialize` 特化名/父链 module 化，artifact_loader 水化/class_to_node module 化，跨引擎 round-trip 存 qualified 名 + `_rehydrate_type_pool_spec` (module,name) 联合匹配；判别性回归 `geo.Box[int](5).get()`=105 / `graph.Box[str]("hi").get()`="hi!"（方法表不串扰）。设计 `_code_runtime_class_module.md`；已知边界（LLM 裸名返回路径 graceful 退化 / 未编译目标引擎用户类重建受封印限制）登记 KNOWN_LIMITS §10.2 |

| **🟡 待设计（2026-08-15，自 PROMPT_DESIGN_REVIEW 收敛）** | **LLM prompt 协议家族待决项** | 架构健康性 | ① 用户类 `__from_prompt__` 返回目标类实例时的 auto-boxing 二次封装边界（类身份比对失败时是否跳过/强制）；② `__validate_prompt__` 是否扩展至内置类型（当前内置 `from_prompt` 自带校验，不经过 `__validate_prompt__`）；③ `SEM_PROTOCOL_SIGNATURE` 强度（warning vs error）；④ `__to_prompt__`/`__payload_prompt__` 异常回退可观测性已落地，待按需复核。**P2**，独立设计窗口 |

---

## 一、运行时内省体系（PT-INTRO-1，已完成）

> `type(x)` 内建 + fn/behavior 签名形态 + `__return_type__()` 返回类型查询 **全部落地（2026-08-06）**。
> 完成形态：
> 1. `type(f)` 对 fn_callable/behavior 返回含签名类型名（`fn_callable[()->int]` /
>    `behavior[(int,str)->bool]`）；其余值返回 `ib_class.name` 规范名。
> 2. `f.__return_type__()` 返回返回类型规范名；签名随序列化 round-trip 保真。
>
> 设计决策（签名属值层属性）见 §十。

---

## 二、PT-DECIDE-1 LLM 解析默认策略语义（已裁定，2026-08-06）

> **裁定**：编译期 `SEM_BEHAVIOR_OUTPUT_NOT_PARSEABLE` + 运行时兜底（DefaultParsingStrategy）。
>
> **问题**："已声明具体类型但无 `__from_prompt__`/parser" 的 LLM 输出被静默 box 成成功
> 字符串 → 错误类型静默流入（实测：`Point p = make()` 中 p 实际为 str）。
>
> **方案评估**：`uncertain`（原提案）有致命缺陷——无 parser 类型在 llmexcept 下重试
> 永远不可能成功，每轮重试重新调用 LLM，白耗 3 次后必然 `LLMRetryExhaustedError`；
> 且需小心排除 `-> any`（运行时 type_hint 为裸 behavior）。编译期错误在零成本处暴露根因，
> 与 fail-fast / 根因优先原则一致。
>
> **落地**：
> 1. 编译期：lambda 行为体 `-> T`、`T x = @~...~`、`obj.field = @~...~` 三处检查
>    T 是否可解析（from_prompt/parser 公理能力 或 类 `__from_prompt__` 含继承）；
>    不可解析报 `SEM_BEHAVIOR_OUTPUT_NOT_PARSEABLE`。`auto`/`any`/行为本体动态类型不设
>    契约，豁免。
> 2. 运行时兜底：`DefaultParsingStrategy` 对"已声明具体类型却无解析能力"返回 uncertain
>    （含明确 retry_hint），不再静默 box；无契约情形（空/auto/any/行为本体）保持 box。
>
> **兼容性**：`auto result = @~...~`、`-> auto/any`、有 parser 的内建类型全部保留原行为；
> 现有测试无"无 parser 具体类型 → str"依赖。设计决策（含 futile-retry 论证）见 WORKLOG。

---

## 三、内核接口协议化（PT-DEBT-1/2/3，已完成）

> 三者同性质（跨对象私有穿透 → 公开访问器/容器）**全部落地（2026-08-06）**，全量 pytest 零回归。

| # | 落地内容 |
|---|---------|
| PT-DEBT-1 | `BoundPlugin(implementation, registry_id)` 容器替代 `_ibci_registry_id` 私有标记注入；`InterOpImpl` 记录/查询 registry_id；`IbNativeObject` 构造时携带（跨引擎隔离校验保留）；加载期跨引擎单例守卫改用 process 级 weak map（保留安全语义，不污染实现对象） |
| PT-DEBT-2 | `snapshot.py` 改走公开访问器（`peek_runtime_coordinator`/`peek_comm_registry`/`get_current_call_info`）；LLMExecutor 补 `pending_futures_count()` 只读计数 |
| PT-DEBT-3 | RuntimeContextImpl 补通信域/协调器公开访问器（`get_comm_registry`/`get_comm_config_store`/`get_comm_event_bus`/`get_runtime_coordinator` 惰性创建 + `peek_*` 只读），统一替换 core（comm/assignment/host/coordinator）与插件（iruntime）全部 `rc._comm_*`/`rc._runtime_coordinator` 直接访问 |

---

## 四、语言特性 / 功能规划（PT-FEAT-*）

| # | 内容 | 说明 |
|---|------|------|
| PT-FEAT-1 | 语言级协程完整形态：async 函数 / `yield` 生成器 | `await` 表达式已落地。**`yield` 惰性生成器已落地（2026-08-08，阶段 5，独立分支 exp/yield-generator → 手动应用 unsafe-vibe-dev，全量 2043/1）**：含 `yield` 函数自动为生成器（D-08 自标记，async 关键字已取消），单可恢复驱动 `_drive_generator_loop` + `GeneratorYield` 标记 + `IbGenerator` 值对象 + `generator[T]` 类型。设计 `YIELD_GENERATOR_DESIGN.md`。**增量 `next()` 内建 + `yield from` 委托已落地（2026-08-09，全量 2083/1）**。剩余：**LLM 函数同步阻塞收敛**（`execute_llm_function_cps` 的 `_call_llm` 阻塞调度线程，`_llm_function.py:202`——behavior 路径已 yield LLMFuture，llm 函数路径未对齐，即 `_HEALTH_AUDIT_PLAN.md` A4）、streaming / host async 改进（STREAM 依赖已封存多模态，deferred） |
| PT-FEAT-2 | Enum 非 str 成员 + 迭代能力 | **✅ 已完成（2026-08-12，unsafe-vibe-dev，全量 2308/1）**：非 str 枚举 LLM 集成修复（成员名→值映射，真实 LLM 实证）+ 迭代/数量 + KNOWN_LIMITS §二 更新；自定义方法 = 值模型边界（`_code_enum_completion.md` / `_enum_instancing_assessment.md`） |
| PT-FEAT-3 | 用户类泛型类型参数 | **2026-08-12 用户升主线（下一 session）**：`class Box[T]:` 语法/语义/序列化扩展。地基已备（GenericTypeRegistry 全链路）。见 §〇 当前主线行 |
| PT-FEAT-4 | 用户类运算符重载 | VISION |
| PT-FEAT-5 | 语义错误用户友好化 + 诊断工具 + 性能基准 + CI/CD | 语义 4 阶段管线已稳定；错误码 `SEM_xxx` 转用户友好表述、符号表/类型绑定 JSON/dot 导出、编译时间基准。**前三项已落地（2026-08-09：诊断码目录 + 符号表/类型绑定导出 + `bench` 编译基准）**；**CI/CD：GitHub 侧自动触发已停用（2026-08-11 用户裁定，`.github/workflows/ci.yml` 改 `workflow_dispatch` 手动）**——现 CI 与本机 pytest 区别不大、必要性不足；待单独设计"可靠化/实用化"（真实 LLM e2e / 跨平台 / 发布产物等）后重新启用并补充，另行规划 |
| PT-FEAT-6 | CompilationResult 字段精简 | 前置：PT-FEAT-5 完成 + 管线稳定 ≥ 1 月 |
| PT-FEAT-7 | 二层 IR 路线评估 | VISION |
| PT-FEAT-8 | `.ibc_meta` 静态元数据快照 | **评估：维持现状待独立窗口（2026-08-09）**。核心切片（export_metadata/load_metadata_from_file）存在分层张力：加载侧重建要么重复 runtime `ArtifactRehydrator`（违禁双写真相），要么引入跨层入口（kernel→runtime / runtime→compiler 均禁止）。generic registry `restore` 仅覆盖 11 种泛型 kind（primitive/class/function 等需另建重建）。需独立窗口做完整设计冻结再落地。原 `docs/architecture/01_principles.md` §7.3.7 规划（已移除，登记于此） |
| PT-FEAT-9 | 内核结构化诊断/可观测性机制（CORE_DEBUG 替代物） | **已完成（2026-08-07，unsafe-vibe-dev，全量 2021 passed / 1 skipped）**：`kernel_diagnostic` helper（单一记录双投影：警告不门控 + 事件受 observability 门控，rc best-effort）+ 12 处站点迁移（文案逐字）+ e2e 事件投影测试 + `docs/architecture/09_observability.md`。设计/决策见下方 §12（归档记录） |
| PT-FEAT-10 | UID 生成统一（符号/节点/类型） | **已完成（2026-08-09）**：新建 `core/base/uid.py` 单一权威源（scope/symbol/intrinsic/node/type/anon_symbol/asset/rt_scope 九家族），symbols.py/serialization/context/runtime_serializer/scheduler/intrinsics/interpreter 全部经此生成，零内联格式字符串；格式逐字不变（round-trip 保真），契约测试 `test_uid_generator.py` 固化 |
| PT-FEAT-11 | 序列化器自动化（消除手动 `_collect_*` 调用） | **评估：维持现状（2026-08-09）**。`_process_value` 已对 `IbASTNode` 自动分派到 `_collect_node`（base 层）；`serialize_result` 的手动 `_collect_node/_collect_symbol/_collect_type/_collect_scope` 属**类型显式**调用（各写不同 pool），改 isinstance 自动分派不减少复杂度、反降可读性。标记"现有实现正确"成立，不强制重构。**撤销登记** |
| PT-FEAT-12 | AST 节点 UID 字段（编译期可见） | **登记于文档清理（2026-08-08）**：原 `02_metadata_ast.md §九 优化4` 愿景内容。UID 现仅序列化时生成，编译期不可见；建议 AST 节点加可选 `uid` 字段供编译期查询。低优先级，涉及 AST 结构变更（须查 `02_metadata_ast.md`） |
| PT-FEAT-13 | `api_config.json` 配置机制完备化（`_API_CONFIG_DESIGN.md`） | **2026-08-11 用户提出**：现 api_config.json 非运行时原生加载（仅脚本级约定）、schema 极简、无校验、mock 靠字符串嗅探。改进（参考 opencode.json）：**C1 原生加载**（`ai.load_config`/引擎自动，替代每脚本 file/json.parse）+ **C2 set_config 结构化** + **C3 校验诊断**（P0）；**C4 env 引用** + **C5 mock 配置化** + **C6 命名模型路由** + **C7 reasoning/每模型参数**（P1）；**C8 容器类型系统**（P2，示例 `(dict)config[...]` 强制转换限制）。C1-C3 为真实 LLM e2e 前置准备 |

---

## §12 PT-FEAT-9 交接要点：内核结构化诊断机制重建

> **状态**：**已完成（2026-08-07，unsafe-vibe-dev，全量 2021 passed / 1 skipped）**。本节为决策记录
> 归档。设计权威：`（已清理任务文档）`；实施记录见 `WORKLOG` PT-FEAT-9 阶段 B-D 落地。
> 落地后观测体系统一文档：`docs/architecture/09_observability.md`（状态面/事件面/诊断面/配置面）。
> **设计已冻结（2026-08-07）**：`（已清理任务文档）`——技术定位、职责边界、核心决策 D1-D7
> （单一事件类型 + KDIAG 代码注册表；单一记录双投影；代码即数据非门控；rc best-effort；边界；
> 码入 codes.py；不设 severity）、诊断码集（10 码 / 12 站点）、事件 schema、实施步骤 A-E。
> **前置依赖（2026-08-07 更新）**：统一执行地基已落地（阶段 1/3，unsafe-vibe-dev）；**先完成 R 批次**
> （`EXEC_REFACTOR_BATCH.md`：R1 trampoline/R2 通知式唤醒/R3 D-04 unify/R4 P3 公开/R6 函数自动捕获——彻底修复
> 阶段 1-3 的妥协处理）→ 诊断机制（阶段 4）落地；全局事件总线（P4）已就绪。

### 背景与现状

- **旧 CORE_DEBUG 已移除**（OBSERVABILITY 2A，commit 6878986）：`CoreDebugger` 类 / `IBC_CORE_DEBUG` env /
  CLI `--core-debug` / `debugger=` 参数链 / `ServiceContext.debugger` 契约 / 88 个 trace 调用点全部删除。
- **诊断价值承接**：真实异常回退 8 处 → `warnings.warn`（`intent.py:__to_prompt__` 回退、`kernel/base.py`
  cast/parse 回退、`llm_except_frame.py` snapshot/restore 回退、`_prompt.py` __payload_prompt__ 回退、
  `llm_parsing_strategy.py` validate/from_prompt、`engine.py` collect 跳过、`scheduler.py` 预定义符号、
  `loader.py` 插件跳过）；AttributeError 协议缺失回退 = 设计路径静默；流程日志直接删除。
- **观测骨架已存在**（单一权威源，勿另造）：`core/runtime/observability/`——`snapshot.py`（状态聚合）、
  `events.py`（EventBus + `emit_runtime_event` 统一发射入口 + EventSource 协议）、`config.py`（ConfigStore，
  `observability` 开关门控）。用户侧消费经 `iruntime`（snapshot/subscribe/configure）；测试侧经
  `IBCIEngine.test_snapshot()` / `ServiceContext.test_hooks`（TestHooks 协议）。

### 设计方向（对照 design-philosophy，禁止平行机制）

1. **不重建旧 CoreDebugger**：print 推送 + 级别门控 + 进程全局单例 + env/CLI 配置都是历史包袱，不再采用。
2. **结构化诊断面**：诊断事件经既有 EventBus 发射（如 `emit_runtime_event(rc, "kernel_diagnostic", {...})`，
   受 `observability` 开关门控、无订阅者零成本）——与 llm/chan/slot 事件同一机制（机制同构）。
3. **与现有消费端对齐**：`warnings.warn` 8 处是否迁入事件面，或保持 warnings（已可被 pytest.warns 断言）？
   需裁决：warnings 是"开发者可见"通道，事件面是"可编程观测"通道——两者语义不同，可能并存（非双通道冲突）。
4. **可测试**：事件面天然可被测试断言（订阅 + 收事件），优于 print。
5. **文档**：`docs/architecture/01_principles.md` 已删 diagnostics/debugger 引用；重建后按 WRITING_GUIDE 记录。

### 建议实施步骤

1. 设计冻结：诊断事件类型集 + 数据形态（对齐 events.py 现有事件 dict 形态）。
2. 评估 8 处 warnings 是否/如何接入；明确 warnings 与事件面的边界。
3. 在 EventBus 上落地 `kernel_diagnostic` 事件 + 门控 + 测试。
4. docs 治理：architecture 章节记录新诊断机制（人类手册）。

### 关联

- 移除记录：`OBSERVABILITY_REFACTOR.md` 决策记录 2A 行。
- 既有事件类型：`core/runtime/observability/events.py`（llm_dispatched/llm_resolved/chan_*/slot_updated/
  task_*/vm_*/configured）。
- 测试规范：`tests/COVERAGE_MATRIX.md` + `test_matrix_sync`。

---

## 五、缺陷 / 技术债（PT-DEBT-*）

> **优先级排序（2026-08-08 用户裁定原则：架构缺陷 ≥ 强相关依赖顺序 > 小而快的独立任务 > 非紧急功能演进）**：
> **PT-DEBT-9/10/11**（架构缺陷）→ **已根治（2026-08-08）**；
> **PT-DEBT-12/13/14/15**（异步地基遗留妥协）→ **全部收尾（2026-08-09，见 `（已清理任务文档）`）**；
> **PT-DEBT-4/5**（破坏性/暂缓）→ 排后。

| # | 内容 | 说明 |
|---|------|------|
| PT-DEBT-12 | 用户方法调用任务内同步重入调度器（F1） | **异步地基遗留（2026-08-08 审计）**：`vm_handle_IbCall` 不展开 `IbBoundMethod` → `receive('__call__')` → `vm.run_body` 嵌套调度器。最常见 `obj.method(x)` 路径；方法含 Waitable 时死锁、深递归方法嵌套 Python 栈。改造：解包 `IbBoundMethod` → CPS trampoline（与函数调用同构）。见 `_ASYNC_UNIFY.md` F1 |
| PT-DEBT-13 | `chan.send` 有界满通道任务内真阻塞（B1） | **异步地基遗留（2026-08-08 审计）**：`send` 返回 None（满时 `_cond.wait` 阻塞线程），与 `recv`（已转 Waitable）不对称；唯一消费者同调度器时死锁。改造：send 满时返回 Waitable（宿主契约变更需评估）。见 `_ASYNC_UNIFY.md` B1 |
| PT-DEBT-14 | `slot.update(fn)` CAS 同步回调 / prompt hint 同步调用（F2/F3） | **异步地基遗留（2026-08-08 审计）**：CAS 锁外 `fn.call`（lambda 嵌套调度器、behavior 阻塞 LLM）；`_get_llmoutput_hint` CPS 路径内同步 `.call()`。改造：update 可调用分支返回 Waitable / hint vtable CPS 化。见 `_ASYNC_UNIFY.md` F2/F3 |
| PT-DEBT-15 | 同步 `.call()` 孪生 / 驱动循环 / LLM 调用双路径（M1-M4） | **异步地基遗留（2026-08-08 审计）→ 全部收尾（2026-08-09）**：各 CPS 路径保留同步 `.call()` 双写（M1）、`_drive_generator` vs `_drive_loop_gen` 重复（M2）、prompt 构建双实现（M3）、CPS 内 `_call_llm` 同步阻塞（M4）。改造：收敛单一 CPS 权威路径 + 薄宿主包装 + LLM 真挂起。**M1/M2 已完成（独立分支 exp/async-m1m2，全量 2137/1）**；M3 已收敛；M4 已完成（2026-08-08）。见 `_ASYNC_UNIFY.md` M1-M4 |
| PT-DEBT-16 | 异步统一完整性遗留（A1-A6，`_HEALTH_AUDIT_PLAN.md`） | **地基闭环后 6 处次要路径仍任务内同步重入/嵌套调度器（2026-08-09 只读审计）→ A1-A4 已完成（2026-08-10，全量 2138/1）**：**A1** 内联 `@~` 表达式接 CPS（llm_behavior.py 切 `execute_behavior_expression_cps`，顺带补 `IbGenerator.generic_next` Waitable 契约缺口）；**A2** 意图消解 CPS 化（`resolve_content_cps`/`IntentResolver.resolve_cps`/`get_resolved_prompt_intents_cps`，CPS 预求值路径消除 `vm.run` 重入）；**A3** `_SlotUpdateWaitable` 增 `cps_drive` 帧内驱动（`CPSDrivable` 协议分派，消除嵌套 TaskScheduler）；**A4** LLM 函数 CPS-yield（`_prepare_llm_function_call_cps`+`_call_and_parse_llm_function` worker 化，PT-FEAT-1 直接项）。**剩余**：**A5** 类构造 `instantiate` 字段 `vm.run` / `init_method.call`（ib_class.py:128/154）；**A6** 协议方法 `.call` 条件触发嵌套（llm_parsing_strategy / llm_except_frame）。**处置**：**A5 已根治（2026-08-11，unsafe-vibe-dev 356b0d8，全量 2137/1）**——用户类（不含原生 __init__）构造改返回 `_ClassInstantiateDrive`（Waitable+CPSDrivable），`cps_drive` 在 VM 帧内 yield 字段默认值 + 用户 __init__（UserFunctionCall），消除 `vm.run` 重入与 `init_method.call` 嵌套 TaskScheduler；leaf.py 兜底细化（CPSDrivable 无论 func 是否 IbClass 均帧内驱动，纯 Waitable 仅非 IbClass auto-yield——thread 原生 __init__ 返回 IbThread 句柄仍不 auto-yield）；宿主/线程体走同步 instantiate 兜底。**A6 评估维持现状（2026-08-11）**——`__snapshot__`/`__restore__` 为 niche 协议、条件触发（仅用户定义且 llmexcept 异常时），CPS 化需侵入异常/重试路径、成本高收益低；`__from_prompt__`/`__validate_prompt__` 在 worker 线程（非缺陷）。登记为已知项，待未来独立窗口评估。见 WORKLOG 2026-08-11 |
| PT-DEBT-17 | `ai.run_batch` 同步阻塞路径（统一执行模型冲突） | **已彻底修复（2026-08-11，unsafe-vibe-dev ebbb7f8，全量 2135/1）**：三层不一致（①主线程 `fut.result()` 同步阻塞等全部 LLM ②同步 `_prepare_behavior_call` `vm.run` 重入 ③与 `stream_call` Waitable 范式割裂）全部根治——`run_batch` 返回 `CPSDrivable` Waitable（`_run_batch_cps` 用 `_prepare_behavior_call_cps` 嵌入 VM 帧栈消除 vm.run 重入 + 多 LLM Future 聚合 `LLMBatchFuture` 由调度器非阻塞等待），与 `stream_call` 同范式；vtable return_type=list 契约不变（auto-yield 后仍收 boxed IbList）；宿主/线程体无 VM 走 `_run_batch_sync` 同步兜底（与 `_SlotUpdateWaitable._drive` 同构）。顺带清理死代码：`LLMExecutorImpl.resolve()` + `LLMFuture.get()`（VM 全走 `resolve_future_cps`）+ 其 5 个死测试 + 协议声明同步。`ihost.collect`/`run_isolated` 为透明异步 auto-yield（非问题，已澄清）。详见 `_code_run_batch_cps.md` / WORKLOG |
| PT-DEBT-4 | `file` 模块重命名 | `file` 影子化 Python 内建，长期重命名（如 `fs`/`io`）。当前过渡措施已实施 |
| PT-DEBT-29 | KNOWN_LIMITS §二十四 generic_next 协作化（独立专项，阶段 D 登记） | **生成器消费同步阻塞（2026-08-16 阶段 D 处置）**：`IbGenerator.generic_next` 对驱动循环产出的 Waitable 阻塞等待（`event.result()`）——需让出型消费（Waitable 依赖 VM 推进）会死锁。**方向明确**（generic_next 层引入 Waitable 感知挂起，与 CPS 执行模型同构）；当前无生产触发（LLM 行为由独立 worker 完成）。独立专项窗口，不阻塞主线。见 KNOWN_LIMITS §二十四 |
| PT-DEBT-30 | KNOWN_LIMITS §二十五 yield from 序列委托编译期区分（独立专项，阶段 D 登记） | **`yield from <序列>` 静态偏乐观**（类型绑定为元素类型但运行期值为 None，Python 语义一致）。**方向明确**（编译期生成器/序列委托目标区分）；低风险专项，与类型绑定后续对齐。见 KNOWN_LIMITS §二十五 |
| PT-DEBT-31 | KNOWN_LIMITS §十五 _pending_futures 残留泄漏核实（修复候选专项，阶段 D 登记） | **循环体多次 dispatch 覆写 _pending_futures 条目**（behavior_dependency_pass.py:118/168 注释）——旧 Future 泄漏 + 读点解析错乱候选；运行期 `_pending_futures` 有锁保护但**消费完整性未核实**。修复候选专项：实证泄漏面 + 根因处置（读点对齐/条目清理）。见 KNOWN_LIMITS §十五 |
| PT-DEBT-5 | 全项目文件命名清理 | 过短/欠层次/欠区分度/影子化内建的代码文件命名排查。暂缓，独立窗口执行 |
| PT-DEBT-6 | `register_module()` 可观测性缺口 | **已落地（2026-08-06）**：用户插件覆盖 kernel-native 时 `warnings.warn`（原静默忽略）。顺带修正测试配置 bug（plugin_paths 指向插件目录本身导致插件从未加载）。全量 pytest 零回归 |
| PT-DEBT-7 | 删除 `is_nullable` 字段，全面 `Optional[T]` | **已落地（2026-08-06）**：死字段清理（`is_assignable` 早已用 `Optional[T].wrapped_type`，序列化不消费）。全量 pytest 零回归 |
| PT-DEBT-8 | ~~折叠 `IbXxx` 为单一 `IbValue`~~ → **重定义为"值层分派收敛审计"** | **已落地（2026-08-06）**：系统层面定论——折叠是伪目标（消 isinstance 动机已由 name 分派达成；具体类=领域方法载体，折叠违反单一职责）。实际收敛：`is_sequence_value` 统一容器分派、`IbLLMCallResult.is_uncertain` 统一不确定判断；类角色分工固化于 `03_type_system.md` §6.4。全量 pytest 零回归 |
| PT-DEBT-9 | ~~RecursionError 被 `VM: Call failed` 级联包装掩盖根因~~ → **已根治（2026-08-08）** | `leaf.py` 等五处语义错误包装站点加环境限制防护（`core/runtime/shared/env_limits.py` 判定 + `diagnostics.handle_environment_limit` 发射 `KDIAG_RUNTIME_ENV_LIMIT`），RecursionError 根因保留传播，不再被掩盖成语义错误。见 NEXT_STEPS 2026-08-08 批次 |
| PT-DEBT-10 | ~~线程体用户函数递归仍同步嵌套（`_drive_generator` 非 trampoline）~~ → **已根治** | **已落地（2026-08-08）**：`_drive_generator` 改显式生成器栈（trampoline，与 `_drive_loop_gen` 同构），UserFunctionCall 压栈而非递归驱动——线程体内深递归不再嵌套 Python 栈。顺带根治线程体模块级函数解析（任务全局作用域链到模块作用域，`ScopeImpl(parent=main_global_scope)`；此前线程体无法解析模块级函数，n≈2 即失败）与线程逻辑栈上限对齐主路径（`max_call_stack`）；修复 `_vm_call_user_function`/`IbUserFunction.call`/`IbLLMFunction.call` push 后 finally 无条件 pop 的栈不均衡潜在 bug（`pushed` 标志）。新增线程体深递归 e2e（depth=300）。全量 pytest 零回归 |
| PT-DEBT-11 | ~~`_UserFunctionCall` 内部标记类定义位置（handler 依赖 VMExecutor 内部）~~ → **已根治（2026-08-08）** | `UserFunctionCall` 下沉 `core/runtime/shared/user_call.py`（与 Signal/Waitable 同类叶子），handler/线程体不再向上依赖 VMExecutor 内部类。见 NEXT_STEPS 2026-08-08 批次 |

---

## 六、长期周期清扫（PT-AUDIT-*，持续周期工作，随主线阶段边界择机启动）

> 审查/审计/治理均为**周期性持续清扫**，非一次性完成——每轮主线改动后按需复核，
> 与"文档清洗与梳理 / 注释卫生清理"同性质。执行记录见 git 历史。

| # | 内容 | 说明 |
|---|------|--------------|
| PT-AUDIT-1 | 代码异味核对分析 | `CODE_SMELL_AUDIT.md`（单一事实来源），独立分支执行。**周期事实回顾已完成（2026-08-09，A/B/C/D 全量定案）** |
| PT-AUDIT-2 | 条件分支与异常嵌套复杂度审计 | `BRANCH_NESTING_AUDIT.md`（AST 基线），独立分支执行。**剩余待核验项已核验（2026-08-09）**——ibci_ai 已窄化 `_PROVIDER_ERRORS`、auto_discovery 为 fail-fast 重抛（A 类保留）。**深嵌套/长 elif 链待独立窗口**（`runtime_serializer._collect_instance` 深度16/`_get_instance`17、`core_scanner._scan_complex_access` 10、`binding_analysis_pass._analyze_node` 9——巨型 elif 分派链，方向：分派表/守卫子句）。**内核健康项（2026-08-09 登记 → 2026-08-10 处置）**：疑似死同步包装（`_behavior.py`/`_llm_function.py` 4 方法）**已清理**；`_drive_loop_gen`/`_drive_generator_loop` 双维护循环**已合并**；A2 意图消解 `vm.run` 重入**已 CPS 化**。**2026-08-10 彻查补充**：同步 `LLMExecutorImpl.resolve()`（`_scheduler.py:78`）与 `LLMFuture.get()`（`llm_result.py:129`）为**死代码**（零真实调用，仅 docstring 示例，VM 全走 CPS `resolve_future_cps`）——可随 PT-DEBT-17 或独立清理（涉及 IILLMExecutor 协议声明） |
| PT-AUDIT-3 | 代码复核审查循环（R 系列） | R1 正式 review / R2 健康诊断 / R3 异味扫描 **已执行（2026-08-05）**；R4 覆盖率核对 **已执行（2026-08-09）**、R5 doc 审计聚焦治理已执行（全量待独立窗口）。复核清单见 `PENDING_REVIEW_ITEMS.md` |
| PT-AUDIT-4 | 任务控制文档清洗与梳理（文档治理周期） | 删除已完成/无价值任务、无用设计决策、任务代号重整、交叉一致性核对。**已执行（2026-08-05）**，周期复核 |
| PT-AUDIT-5 | 注释卫生清理（周期） | 删除代码注释中的任务代号、历史实现方案、修复过程叙述，保留功能设计语义。**已执行（2026-08-05）**，周期复核 |

## 七、文档同步（PT-DOC-*）

### PT-DOC-1 docs/ 技术手册同步（D1-D5 已落地 2026-08-06）
| # | 内容 |
|---|------|
| D1-D5 | **已落地**：新写 `docs/syntax/14_concurrency.md`（chan/slot/subscriber/thread/thread_result + pubsub/send_nowait 语义 + signal 移除说明），KNOWN_LIMITS §二十二，SYNTAX_REFERENCE/README 接入。详见 WORKLOG |

### PT-DOC-2 语法手册定位段补充
**已完成（2026-08-06）**：14 篇 `docs/syntax/*.md` 均已有合格定位段（`> 本章描述...面向...覆盖...`），DOC_AUDIT F3 期间随"深入指引"补齐时一并落地。条目移除。

### PT-DOC-3 技术手册健康修复（2026-08-09 三轴盘点，低风险）
> 来源 `_HEALTH_AUDIT_PLAN.md` 文档健康节。
- **P1/P2 三修已完成（2026-08-10）**：① `01_principles.md:255` §6.3 改写为现状（意图栈继承由 `IbIntentContext.fork()` 承担，公理 IC-1；`IsolationPolicy` 实际字段 `inherit_plugins`/`collect_timeout`，跨隔离边界不继承意图）；② `04_vm_interpreter.md:29` 统一表述（模块入口 `execute_module`→`run_body`，宿主入口 `.call` 薄包装委托 `_vm_call_*`+`_drive_generator`）；③ `docs/README.md` 目录树补 `15_diagnostics.md`。
- **P2（规划）** How-to 层仅 2 篇：生成器/并发/llmexcept/隔离缺操作指南（Reference→How-to 读者旅程断裂），需按 WRITING_GUIDE 评估。

---

## 八、测试体系（PT-TEST-*）

| # | 内容 | 说明 |
|---|------|------|
| PT-TEST-1 | 测试体系治理与彻底重构 | **已完成（2026-08-06，OBSERVABILITY_REFACTOR 2D）**：tests_v2 全域迁移 + Phase 5 切换 + 语义覆盖守恒 1565=1565，全量 1962/1。详见 `TEST_REFACTOR.md` |
| PT-TEST-2 | e2e 测试覆盖率提升 | `for...if` 过滤、复合赋值运算符 e2e **已补（2026-08-06）**；其余覆盖缺口由矩阵 `🔶 缺失` 项承接 |
| PT-TEST-3 | 测试名与覆盖矩阵同步 | **已完成（2026-08-06，并入 PT-TEST-1）**：矩阵三段式填充（`tests/COVERAGE_MATRIX.md`，13 语义域 154 真实引用 + `test_matrix_sync` 机器校验）。核对发现存档于 `（已清理任务文档）`（TRUE_GAP 项已在矩阵标 `🔶 缺失`） |

---

## 九、封存（PT-SEALED-1：media Phase 4 多模态容器）

> **已彻底封存（2026-08-01，无限期搁置）**：恢复需显式解封并重估。代码层零启动，
> 设计要点见 `（已清理任务文档）`。前置（路径统一/内核原生化/磁盘型
> 存储）已完成。解封时需实现三项：
> 1. 多模态模型注册字段（`ai.register_model` 存 modalities/endpoint/audio_config）；
> 2. 非聊天端点推理绕过（endpoint 字段强制非推理，跳过 reasoning prompt 注入）；
> 3. 磁盘型响应解析协议（`from_response` 平行协议 + `has_multimodal_response_cap` flag）。

> **已落地部分**：`__payload_prompt__` 协议与 `audio`/`image`/`video` 类型（见 `docs/syntax/07_behavior_expressions.md` §7.6、`docs/subsystems/02_file_container.md`）。

---

## 十、设计决策（保留——防止未来误解）

### 仍有效的设计决策

| 决策 | 内容 |
|------|------|
| 运行时值 `type_ref` 保持基础 spec | 可变值（list/dict）不固有泛型身份（同一对象可赋给 list[int]/list[str]，语义不自洽）；符号/序列化侧已精确 |
| callable 签名属值层属性 | fn_callable/behavior 的签名（param_types + return_type）在运行时值创建时经 node_to_type 捕获、自持于值（JSON 安全字符串，序列化保真）；不落 CALLABLE_INSTANCE 类型 spec（该 spec 仅载 value_type）。`type(f)`/`__return_type__()` 据此内省 |
| 通信 `Signal` 抽象移除 | 零消费者空壳 + 与 VM 控制流 Signal 撞名 → 彻底删除 |
| 瞬态序列化协议 | thread/chan/slot/subscriber 统一 `__transient_state__` 存根；反序列化不复活活体 |
| 类型符号 `class_ref` | IbClass 序列化为类名引用、反序列化重绑定 registry 真实类 |
| 泛型成员特化协议化 | `resolve_member` per-type 级联收敛为 `GenericTypeDeclaration` 声明回调 |
| 行为体 fn `-> auto` = str 强制 | LLM 输出默认字符串；要其它类型必须显式 `-> T` |
| 可调用实例不写 value_meta | meta 冗余拷贝专用字段且含非 JSON 值（IbIntentContext/IbCell/TypeDef）；专用字段是单一事实来源 |
| `expected_type` 落盘为类型名字符串 | 运行期由调用点经 node_to_type 解析；字段本身仅元数据 |

### 设计排除（语言级限制，已写入 `docs/KNOWN_LIMITS.md`）

| 排除 | 原因 |
|------|------|
| walrus `:=` / lambda 体赋值 | 设计排除（KNOWN_LIMITS §十九.1） |
| if-block 内重声明同名变量 | 设计排除（KNOWN_LIMITS §十九.2） |
| loader 与 check.py 签名校验收敛 | 设计隔离：SDK 离线校验不初始化运行时，强制收敛引入 SDK↔runtime 错误耦合，不收敛 |

---

## 十一、推迟工作记录：循环打破局部 import tradeoff（待架构重构时复核）

> 原则：理想上应永远避免循环依赖。但允许少量"设计合理、能显著减少工作量"的局部 import 作为
> **谨慎 tradeoff**。以下为保留的循环打破局部 import，列为未来推迟工作，待架构重构
> （依赖方向下沉 / 接口上移）时逐项复核。

| 记录 | 位置 | 引用 | 保留理由（tradeoff） | 未来复核方向 |
|---|---|---|---|---|
| L1 | `core/runtime/objects/kernel/base.py:31/32` | `from .functions import IbBoundMethod` / `from .ib_class import IbClass` | 运行时构造/分派所需，base↔functions/ib_class 环 | 下沉共享基类到独立叶子 |
| L2 | `core/runtime/objects/kernel/ib_class.py:165` | `from .functions import IbBoundMethod` | 运行时构造，ib_class↔functions 环 | 同上 |
| L3 | `core/kernel/spec/type_ref.py:128` | `from .base import TypeKind` | 运行时 kind 比较分派，base↔type_ref 环 | 下沉 TypeKind 到叶子 |
| L4 | `core/kernel/spec/registry/_members.py:121` | `from ..base import TypeDef` | 运行时构造 TypeDef | 下沉 TypeDef 到叶子 |
| L5 | `core/kernel/spec/registry/_runtime.py:90` | 相对导入 | 运行时（审计标注循环打破） | 复核定位并下沉 |
| L6 | `core/runtime/interpreter/interpreter.py:466` | `from vm.vm_executor import` | interpreter↔vm 环 | 延迟属性引用评估 |
| L7 | `core/runtime/objects/kernel/user_functions.py:42/79/140` | `from ..primitives` / `..cell` / `..signals` | 运行时（热路径） | 复核能否去环 |
| L8 | `core/runtime/shared/llm_result.py:56/130` | `from ..objects.primitives/kernel` | 运行时 | 复核能否去环 |
| L9 | `core/runtime/path/install.py:36/40` | `import ibci_modules` / `import core` | 模块加载期 | 重构加载顺序 |
| L10 | `ibci_modules/ibci_ai/core.py:298` | `from core.runtime.frame import` | 插件↔core 环 | 接口上移 |
| L15 | `core/engine.py:119/123` | `kernel_native_modules` / `file_impl` | 构造期延迟加载重型实现 | 核验是否可去除 |
| L17 | `core/compiler/semantic/context.py:117` | `from ...passes.prelude import Prelude` | context↔passes 环 | 依赖方向重构 |
| L18 | `core/runtime/bootstrap/kernel_native_modules.py:75` | `from kernel.host_interface import` | 环（审计待核验） | 复核定位并下沉 |

> 复核触发：任一处所在模块发生架构重构、或引入新的循环依赖、或出现相关技术债时，返回本表
> 逐项复核该 tradeoff 是否仍成立。
