# NEXT_STEPS - 当前最紧要项

> 本文件**只**记录当前最紧要、可立即开工的下一步；长期规划见 `tasks_docs/PENDING_TASKS.md`（§〇 优先级总表）。
>
> **最后更新**：2026-08-16（用户拍板：**协议化内核大重构为当前主线**，
> 压力测试/真实试用在其后；exp/protocol-kernel 交接恢复，正式任务控制文档已补齐登记）
>
> **🔴 当前主线（2026-08-16 用户指定，进行中）**：
> **协议化内核大重构 + 内核全方位梳理清洁 + 架构级重构**（`exp/protocol-kernel`
> 独立分支）。上一 session 2026-08-16 01:29 因 context 超限中断，恢复交接见
> `tasks_docs/HANDOFF_PROTOCOL_KERNEL_RECOVERY.md`（该 session 未及同步正式
> 任务控制文档，属交接割裂，本 session 已补齐登记）。**已完成**（39 commits）：
> 协议内核地基（ProtocolDef/Registry）/用户协议语法（protocol/implements/继承/
> 签名兼容）/泛型约束与泛型函数/泛型协议/retroactive implementation（声明式）/
> 普通函数与 LLM 函数全链路统一（AST+运行时+CPS+trampoline，删独立 IbLLMFunction）/
> 协议注册表替换硬编码能力（多站点）。中断前未提交的 base.py 改动已验证
> （全量 2877 passed / 1 skipped 零回归）后提交 0518e1bf。**待做**：剩余硬编码
> 能力替换、IbLLMFunctionDef 残留清理、Prompt 装配散落统一、序列化/动态宿主/
> 插件体系类型分支清理、retroactive 推进到可补方法、文档同步。每阶段全量
> pytest 零回归门。**完成后**：在最新代码上开启一轮全方位真实 LLM + 真实 IBCI
> 试用（利用 trials 套件）确认重构影响，再启动新压力测试（原 T08 压力试用
> 主线顺延至此之后）。
>
> **✅ 已完成（2026-08-15，T08 第一轮，全量 pytest 零回归）**：
> **IBCI LLM 全能力真实压力试用（第一轮）**。41 例：32 PASS + 2 GUARD +
> 4 LLM_BEHAVIOR + 2 BOUNDARY + 1 LIMIT。覆盖内联/容器/协议/批量/意图/
> LLM 函数/流式/路由/线程/chan/生成器/配置错误。**修复 2 项内核缺陷**：
> ① `KERNEL_ISSUE-LLM-2` LLM 函数返回 `list[int]`/`dict[str,int]` 未按容器解析
> （`_get_expected_type_hint` 忽略 IbSubscript returns，默认退化为 str）；
> ② `KERNEL_ISSUE-LLM-3` `set_retry(0)` + llmexcept 不抛 `LLMRetryExhaustedError`
> （重试循环零次不进直接返回 uncertain）。均补回归测试。**新登记**：
> `DOC_ISSUE-30`（`@!`+run_batch 文档与实现不一致）、`BOUNDARY-LLM-2`（LLM 函数
> `-> void`）、`BOUNDARY-LLM-3`（stream 调用不入 call_info）。详见
> `trials/T08_llm_pressure/REGISTER.md` + `PENDING_TASKS.md`。
>
> **✅ 已完成（2026-08-15，真实 LLM 调用专项试用，全量 2789 passed / 1 skipped 零回归）**：
> 真实 LLM 全量扫描：T01 57（54 PASS + 2 预期 GUARD + 1 LLM_BEHAVIOR）、
> T02 3、T05 cases_D3 8、T06 7、T07 7。修复三项：① run_batch 每条调用独立
> fork 意图快照（语句级 @!/@ 不再被批内首条调用消费）；② @! 排他意图抑制
> 类型级输出约束（消除 bool 格式与用户 YES/NO 指令冲突）；③ bool 输出提示
> 放宽为 true/false、yes/no、1/0 全形态。另 `get_return_type_prompt` 泛型
> 基名回退。自检结论：修复遵循既有 fork 快照/单一权威组装模式，无兼容层、
> 无 tricky、无纯快速修复。
>
> **🔴 当前主线（2026-08-15 用户指定，进行中）**：
> **IBCI LLM 全能力真实压力试用（本地 qwen）**。第一轮已完成，继续扩展
> 长提示/超时/并发压测/多模态真实文件等压力维度。范围与工作模式详见
> `PENDING_TASKS.md` §〇 P0 行 + `HANDOFF.md` §2.1 交接块。PT-FEAT-14
> 已暂缓（见 PENDING_TASKS §〇 暂缓行）。
>
> **✅ 已完成（2026-08-15，exp/llm-prompt-mechanism → unsafe-vibe-dev，全量 2789 passed / 1 skipped 零回归）**：
> **IBCI LLM 调用机制改进（T5 枚举解析失败暴露的机制弱点）A-D 四项落地**。
> ① A 修复：`_try_axiom_output_hint` module 感知，`_get_llmoutput_hint(_cps)`
> node_to_type 与 returns IbName 分支同 module 解析——枚举 `__outputhint_prompt__`
> 注入断链修复（真实 LLM 实证 T02 T3/T4/T5 三连 PASS）。② B 修复：behavior 基础
> system prompt 升级为程序化调用纪律。③ C 修复：期望输出类型注入 prompt（单一
> 优先级 provider 显式类型提示 > `__outputhint_prompt__` > 通用类型声明）；LLM 函数
> 路径同样接入 `__outputhint_prompt__`。④ D 修复：llmexcept/retry 自动回喂上次
> 响应 + 解析错误（`LLMExceptFrame.last_llm_response`/`last_llm_error`）。架构：
> 新增 `_prompt_assembly.py` 单一权威组装，behavior sync/CPS 共用组装 helper，
> LLM 函数共用 type constraint/intent/retry feedback 构建器。判别性回归
> `tests/e2e/test_llm_prompt_mechanism.py` +6；文档同步 KNOWN_LIMITS §10.2 /
> guide 03 / syntax 10。详见 `_code_llm_prompt_mechanism.md` + WORKLOG。
>
> **✅ 已完成（2026-08-14，完整 IBCI 真实代码试用核查）**：T01-T07 全量重跑，近期改动
> （断层根治 + fn/callable 方向 A + CALLABLE_SIG 根治）对已知试用代码**零回归**；更新
> 4 例过期触发用例 expect-class→PASS（核销）；记录 T02 T5 真实 LLM 间歇失败。详见
> `trials/VERIFICATION_20260814.md`。
>
> **✅ 已完成（2026-08-14，exp/callable-sig-signature → unsafe-vibe-dev，全量 2775 passed / 1 skipped 零回归）**：
> **CALLABLE_SIG 签名模型架构碎片化根治**。深挖推翻 §10.4"潜伏"定性——为真实类型安全
> 漏洞：① 匹配双通道（`_matches_callable_sig` 只查数量+返回，`fn[(Box[int])->int]` 收
> `get2(str)->int` 漏检）；② 嵌套类型参数不替换（扁平构造 `TypeRef('Box[T]')` substitute
> 不可穿透 → 调用点 resolve miss → 检查静默跳过）。**根治**：结构化构造（`TypeRef.from_spec`
> 替代 `TypeRef.of(p.name)` 扁平化）+ 结构化重建（resolve_typeref 保留嵌套实参）+
> 统一匹配（`_matches_callable_sig` 补逐参数类型检查，两 matcher 改 resolve_typeref）+
> 延后规则（仅裸类型参数占位延后；any 通配不误拒模板；带实参不可解析 fail-fast）。
> 判别性回归 +10（TestCallableSigSignature）+ 模板回归 2；两轮独立复核 P1 已整改。
> 已知残留：`list[fn]` 容器元素级强制可调用未接线（独立于签名模型）。
>
> **✅ 已完成（2026-08-14，exp/fn-callable-redesign → unsafe-vibe-dev，全量 2765 passed / 1 skipped 零回归）**：
> **fn/callable 关键字体系重构（方向 A）**。彻查结论（`_DESIGN_FN_CALLABLE.md`）：
> `callable` 作为用户类型是"内部概念泄漏 + 半成品"（只对 lambda/绑定方法生效、误拒
> 裸函数/可调用类实例，与文档"不引入统一 callable 基类"鸭子类型哲学矛盾，且与 `fn`
> 职责重叠）。**定案方向 A**：① `callable` 降级为纯内部概念（运行期基类名
> `type(make)`="callable" + 公理族根 + `thread(callable=...)` 参数名保留），用户注解
> `callable f`/`-> callable`/`list[callable]`/`class X(callable)` 报 SEM_UNRESOLVED_TYPE
> 引导用 `fn`；② `fn` 参数/返回收紧为"任意可调用（强制）"（`apply(42)`/`-> fn: return 42`
> 编译期拦截；CLASS 按 `__call__` 判定；动态 any/auto 放行）；③ `_infer_fn_type` 兜底
> 改 `fn` 哨兵（不再泄漏内部 callable 类型）。判别性回归 +19（TestCallableInternalization
> 4 + TestFnCallabilityEnforcement 13 + 迁移反转）；独立复核（general agent）P1/P2 已整改
> （fn 参数/返回按 __call__ 判定 + class X(callable) 守卫 + 共享消息常量）。已知残留：
> `list[fn]` 容器元素级强制可调用未接线。文档同步 KNOWN_LIMITS §七 / 03_callable_fn /
> 03_type_system §7 / 05_functions §5.6。
>
> **✅ 已完成（2026-08-14，exp/func-callable-identity → unsafe-vibe-dev，全量 2746 passed / 1 skipped 零回归）**：
> **函数/可调用类型身份架构断层根治**（P0，`_HANDOFF_TYPE_IDENTITY_FAULT_LINE.md` +
> 本 session 深化分析）。用户猜想"fn 设计早于泛型体系存在历史包袱"证实，且比交接
> 更进一步：断层为**三层系统性**——① spec→TypeRef 转换无单一权威（from_spec 缺
> FUNCTION/BOUND_METHOD/CALLABLE_SIG 三种 kind，存在 scheduler._spec_to_typeref 与
> _param_type_ref 两个部分实现）；② type_checking 回填用 `.name` 字符串覆盖
> symbol_collection 已产出的结构化 spec（`-> fn[(...)->...]` 退化为裸 fn）；
> ③ 函数签名序列化缺口（FUNCTION get_references 恒空 + rehydrator `_fill_descriptor`
> uid 通道回退 void——运行期函数 spec 恒 void 返回）。**五项根治**：A from_spec 补
> 三 kind（FUNCTION 按名区分 callable/fn 标记与真实签名）；B create_func 结构化升级
> + 编译期回填传 from_spec + `-> auto` 收敛；C resolve_member 产出 BOUND_METHOD
> （BoundMethodAxiom 编译期接线，4 消费点补 kind）；D 函数返回 Optional 包装
> （`_wrap_function_result` 单一 helper 接线三消费点，含方法 owner_class 签名路径）；
> E 序列化 canonical_name 签名保真（FUNCTION/BOUND_METHOD/CALLABLE_SIG）。判别性
> 回归 +29（test_func_callable_identity 19 + TestBoundMethodReturn 反转 + 方法包装）。
> 潜伏边界 KNOWN_LIMITS §10.4。详见 `_code_func_callable_identity.md` + WORKLOG。
>
> **✅ 已完成（2026-08-14，unsafe-vibe-dev 19920d39，全量 2714 passed / 1 skipped 零回归）**：
> **DOC-29 + BOUNDARY-NESTED-FUNC-1 两项根因修复**（E 批判批次发现，无人值守 session）。
> **BOUNDARY-NESTED-FUNC-1（架构级）**——深度分析修正定性：真实根因=编译期 `visit_IbReturn`
> 返回类型兼容校验整体缺失（`-> fn_callable[int]: return inner` 编译期放行、运行期
> RUN_TYPE_MISMATCH；实测 `-> int: return "abc"` 亦放行）。修复：`visit_IbReturn` 对非动态
> 可调用返回类型（FUNCTION/BOUND_METHOD/CALLABLE_SIG/CALLABLE_INSTANCE）补 is_assignable
> 校验，与直接赋值路径语义对齐（fn_callable 槽只接受 lambda/behavior 实例）；`-> fn`
> 动态哨兵跳过、普通类型返回保持宽松。判别性回归 +13。**DOC-29**——空 Optional 操作
> （for 迭代/unwrap）补 error_code=RUN_ATTRIBUTE_ERROR，三处发射点收敛 + 文档一致。
> 判别性回归 +4。E1/E2/E3 触发用例全部核销转 PASS。设计 `_code_return_type_check.md`。
> 详见 PENDING_TASKS 两行 + WORKLOG + REGISTER §八bis。
>
> **📋 第二 session 复核（2026-08-14，未改内核）**：push 已授权执行；T07 全量 43 例重跑 +
> 旧套件 T01-T06 238 例重跑**零回归**（三项修复有效、无内核退化）；E 批判补充批次 8 例
> （5 PASS + 1 BOUNDARY + 2 DOC_ISSUE）新登记 **DOC-29**（空 Optional 操作错误码
> RUN_GENERIC_ERROR vs 文档承诺 RUN_ATTRIBUTE_ERROR）与 **BOUNDARY-NESTED-FUNC-1**
> （函数返回嵌套函数赋 fn_callable 类型 RUN_TYPE_MISMATCH，base 同现）。详见
> `trials/T07_fixes_critical_stress/REGISTER.md` §八 + PENDING_TASKS。
>
> **✅ 已完成（2026-08-14，unsafe-vibe-dev）**：**T07 新发现三项 P1 修复 + DOC-24~28 文档同步**
> （详见"已完成"节）——① **OPTIONAL-SCOPE-1**：函数作用域局部变量声明类型编译期丢失
> （系统性根因：`_prescan_body_locals` 硬编码 any → 符号池 type_uid=any → 运行时
> wrap_optional 不包装；同源：函数内类型化局部变量重赋值检查失效、闭包/cell 写不包装）
> 根治（prescan 解析注解 + type_checking 复用 owned_scope + 闭包/cell 写包装对齐 +
> rehydrator FUNCTION/CALLABLE_SIG/BOUND_METHOD/MODULE kind 保真 + TYPE_PARAM 检查放行）；
> ② **OPTIONAL-CONTAINER-1**：IbOptional.receive 统一委托链 + resolve_iterable 识别
> Optional；③ **ATTR-READ-1**：`_default_getattr` 未命中属性改抛 RUN_ATTRIBUTE_ERROR
> （读取/调用一致 fail-fast）。④ DOC-24~28 全部同步；BOUNDARY-CHAN-ARGS-1 文档说明。
> 判别性回归 +28（compiler 7 + Optional 运行时 13 + 属性 fail-fast 4 + 追加 4）。

---

## ✅ 已完成：T07 三项 P1 修复 + DOC-24~28 文档同步（2026-08-14，unsafe-vibe-dev，全量 2693 passed / 1 skipped）

> 承接 `_HANDOFF_T07_FINDINGS.md`（T07 试用只记录，本 session 修复）。三项 KI
> 均围绕 KI-2 统一 Optional 值模型改动面深挖，发现**系统性根因**（不止交接
> 推断的局部现象），按"彻底根治、不补丁"原则实施。触发用例 D2-09/D2-10/D1-13
> 全部核销转 PASS。设计/分析记录见下方各节与 WORKLOG。

- **① KERNEL_ISSUE-OPTIONAL-SCOPE-1（P1）——函数作用域局部变量声明类型编译期丢失（系统性）**：
  `_prescan_body_locals`（symbol_resolution_pass）预注册函数局部变量**硬编码 any**
  → 符号池 type_uid=any → 运行时 declared_type=any → wrap_optional 不包装（函数内
  `Optional[int] tag = None` 裸 IbNone）。**同源系统性缺陷**（探针实证）：
  函数内 `int x = 5; x = "abc"` 编译通过（类型检查作用域链不含局部符号，重赋值走
  "首次定义推断"）；闭包/cell 写路径（nonlocal 写 Optional）也不包装。**根治**：
  ① prescan 解析类型注解（带注解→正确 spec，无注解→auto 占位，与模块级一致）；
  ② type_checking visit_IbFunctionDef 复用 `func_sym.owned_scope`（局部符号可见，
  重赋值按声明类型检查）；③ 闭包绑定 3 处 + cell 写 2 处 declared_type 对齐；
  ④ **连带预存缺陷**：rehydrator FUNCTION/CALLABLE_SIG/BOUND_METHOD/MODULE shell
  创建不传 kind（TypeDef 默认 primitive）→ 嵌套函数符号水化 kind 错；
  `_resolve_annotation_spec` 缺 IbCallableType 分支（fn[...] 参数退化为裸 fn）；
  TYPE_PARAM 声明运行时 _check_type 放行。判别性回归（compiler 7 + runtime 7）。
- **② KERNEL_ISSUE-OPTIONAL-CONTAINER-1（P1）——Optional 容器协议委托**：
  `IbOptional.receive` 无内层值委托（len/下标对包装对象不可用）+ `resolve_iterable`
  不支持 Optional（for 迭代失败）。**根治**：IbOptional.receive 统一委托链（内层值
  优先 + Optional 专属方法回退 + 空值 fail-fast RUN_ATTRIBUTE_ERROR）+ resolve_iterable
  识别 Optional（有值按内层解析、空值 fail-fast）。判别性回归（runtime 5）。
- **③ KERNEL_ISSUE-ATTR-READ-1（P1）——未声明属性读取静默 None**：
  `_default_getattr`（Object 基类 __getattr__ 兜底）未命中成员时 `return get_none()`。
  **根治**：改抛 `InterpreterError(RUN_ATTRIBUTE_ERROR)`（读取/调用路径一致
  fail-fast，符合"不静默错误值"工程原则）。判别性回归（runtime 4，含线程内）。
- **④ DOC-24~28 文档同步**（doc-governance，与修复联动）：arch/03 §8 值创建路径
  枚举补函数局部/闭包捕获 + 新增"Optional 容器委托"条目；15_diagnostics
  RUN_ATTRIBUTE_ERROR 触发条件精确化；KNOWN_LIMITS §10.2 补 qualified 路径实证；
  14_concurrency chan T 实参形态说明（BOUNDARY-CHAN-ARGS-1）。
- **核销**：D2-09（405）/D2-10（3）/D1-13（RUN_ATTRIBUTE_ERROR）全 PASS；
  REGISTER/INDEX/PENDING_TASKS 状态更新。

---

## ✅ 已完成：跨模块同名类运行时类表 module 化（S5 运行期闭环，2026-08-14，exp/runtime-class-module，全量 2614 passed / 1 skipped）

> 用户 2026-08-14 指出：S5 只根治编译期/元数据层，运行期类表仍 name-only 坍缩。
> 设计 `_code_runtime_class_module.md`；独立复核（general agent）PASS-with-findings
> （1 项 P1 已整改 + 文档同步）。**同 session 的 T05 批判试用确认根治稳健**（D1 12 例
> 全 PASS 零回归），并暴露 2 项既有缺陷 + 23 文档问题（见下方 T05 节）。

- **根因**：编译期 spec 身份 = (module_path, name)；运行期 IbClass 身份 = 裸 name
  （`_classes[name]`/`_class_registry[ib_class.name]`）——两端不对称，运行期坍缩使
  S5 编译期隔离失效（`geo.Box[int](5).get()` 报 int+str，方法表按后编译者覆盖）。
- **根治（运行期闭环）**：注册键 = `spec.qualified_name`（geo.Box/graph.Box 独立）；
  `get_class(name, module)` module 感知（裸名+module 优先、qualified 精确、miss 回落
  裸名——内置/入口键=裸名零影响）；`IbClass` 新增 `module_path`/`qualified_name`；
  `_specialize` 特化名/父链 module 化；artifact_loader 水化/class_to_node 键
  (module_name,name) module 化；VM class def/类型解析/cast/句柄 rebind/hint module 感知；
  跨引擎 round-trip 存 qualified 类名 + `_rehydrate_type_pool_spec` (module_path,name)
  联合匹配（修 #2）。
- **独立复核整改（P1）**：内置泛型父（list[T]/dict[K,T]，module 恒 None 为权威值）
  被无条件补前缀 → `geo.list[int]` 永不注册 → 继承链断裂。修复：`KernelRegistry
  .resolve_class_module` 权威解析（内置/入口→None 不加前缀；已注册用户父→其 module；
  未解析前向引用→default_module 兜底）。
- **判别性回归 +6**：运行期方法表隔离（105/hi!）、运行期注册表隔离、非泛型同名隔离、
  泛型继承同模块父、内置泛型父不加前缀、跨引擎 round-trip qualified 保真 +
  `_rehydrate_type_pool_spec` 联合匹配。
- **已知边界**（KNOWN_LIMITS §10.2）：LLM 输出解析跨模块用户类的 AST 裸名返回路径
  graceful 退化（不误配）；跨引擎 round-trip 未编译目标引擎的用户类重建受注册表封印
  限制（既有边界）。

---

## ✅ 已完成：T05 批判性压力试用 + 内核粗略问题分析（2026-08-14，`trials/T05_critical_stress/`，全量 2614 passed / 1 skipped）

> 跨模块类表 module 化后内核的全方位批判试用（mock 对抗 + 真实 LLM + 文档全量核验）。
> 40 用例 **37 PASS + 1 GUARD + 2 KERNEL_ISSUE**；文档核验 **23 DOC_ISSUE**。
> **本任务是试用/记录/汇报任务，不修复**；发现只登记（PENDING_TASKS）。

- **D1 跨模块根治回归 12 例全 PASS**：方法表隔离（105/hi!）/同模块多特化/非泛型同名/
  三模块/嵌套包/泛型继承/内置泛型实参/函数参数/thread 值类型/序列化/入口遮蔽。
- **D2 对抗 20 例**（深递归/遮蔽/Optional/any 守卫/容器/生成器/闭包/enum/switch/
  llmexcept/并发/字符串/lambda/auto/解包/运算符重载/import/while/嵌套身份/默认参数）：
  17 PASS + 1 GUARD（遮蔽守卫）+ 2 KERNEL_ISSUE。
- **D3 真实 LLM 8 例全 PASS**：意图 @/@! 遵循、@~ typed 解析、enum 成员名→值、
  llmexcept 共存、mock↔真实切换、长提示格式约束。本机服务响应 <1s（reasoning_tokens=0，
  与 LLM_SERVICE 记录的思考耗时不符——环境事实）。
- **KERNEL_ISSUE 2 项（均既有缺陷，非本 session 引入；粗略根因已分析）**：
  - **CROSSMOD-THREAD-1（P1）**：线程 worker 内被 import 模块用户类方法调用失败
    （`Symbol UID missing`）。根因方向：task_ec 的 `get_side_table` 回调读 interpreter
    共享 current_module_name（coordinator.py:213 + interpreter.py:352），忽略任务本地
    module 切换（_shared.py:261）。base 同现。
  - **OPTIONAL-ISNONE-1（P2）**：`Optional[int] a = None; a is None` → False（文档声称
    True）。根因方向：`is` 的 None 分支 `isinstance(left, IbNone)`（leaf.py:269），
    Optional 空值被 IbOptional 包装；`is_none()` 文档有声明实现缺失。
- **DOC_ISSUE 23 条**（P1×4/P2×11/P3×8）：mock STR/BOOL 值语义、KNOWN_LIMITS 自身
  3 条不成立（§七/§八/§十三）、15_diagnostics 8 个幽灵诊断码、Optional 判空误导、
  2 处 P1 示例不能编译、文档间矛盾（intent/生成器/并发）、TESTONLY 遗留术语等。
- **批判性评价**：跨模块根治稳健零回归；**并发模块上下文隔离是主要风险面**（KI-1 +
  14_concurrency 相反承诺）；Optional 判空三路径不一致；文档健康度显著低于代码。
  报告 `REPORT.md` + `REGISTER.md`。

---

## ✅ 已完成：内置泛型类型身份双轨根治（缺陷一 + 缺陷二，2026-08-13，unsafe-vibe-dev 80294a64/447ad35c/7a15c1b9，全量 2559 passed / 1 skipped）

> 用户裁定（2026-08-13）：两缺陷均根治，架构统一性/长期收益/代码质量优先。
> 统一根因 = 内置泛型与用户类泛型类型身份模型双轨不对称。设计冻结 `_code_generic_type_identity.md`；
> 独立复核（general agent）发现 3 项全部整改。

- **缺陷一（P1，80294a64）内置泛型赋值实参校验缺失**：`is_assignable` 在 axiom 前缀匹配前插入同家族结构化实参比较——`_generic_spec_args`（list→element_type / dict→key+value / tuple→positional / thread·chan·slot·generator·fn_callable·behavior→value_type）+ `_generic_family_compatible`（沿 axiom 父链处理 behavior→fn_callable 跨家族）。10/11 类 `X[int]→X[str]` 编译期拦截；协变（`list[int]→list` / `dict[str,int]→dict[str,any]`）保留；bool isa int / Optional 专门分支 / 裸→特化语义不破坏。
- **缺陷二（P1-P2，447ad35c+7a15c1b9）内建泛型值层类型擦除**：特化 spec 水化为运行时特化类四层——① ArtifactLoader 加载期（sealed 前）预创建 type_pool 内置泛型特化类（parent=基类）；② `IbClass._specialize` 内置泛型下标水化特化类（sealed 回落 boxed 嵌套实参字符串）+ `_impl_cls` 沿 spec 基类名解析实现类；③ 编译期赋值 visitor 对容器字面量 RHS `bind_type(target_type)` → VM 字面量 handler `_bind_container_specialization` 按特化类绑值 + type_ref 结构化；④ 值层分派沿 spec 基名统一（deep_clone / is_sequence_value / runtime_serializer 分派+反序列化重建 / thread 构造 args）。
- **效果**：`type(list[int]值)=list[int]`（原 list，与用户类 Box[int] 一致）；运行时值层可区分 `list[int]`/`list[str]`（与缺陷一联动 is_assignable 拦截）；深克隆/同引擎序列化 round-trip 保真；嵌套泛型 `list[list[int]]` 外层值身份。
- **独立复核整改（7a15c1b9）**：① dict 协变假拒绝（`_generic_spec_args` 过滤 any → `dict[str,int]→dict[str,any]` 被 len 比较误拒）——不过滤 any，仅裸基类（key/value 均 any）返回空；② `_bind_container_specialization` boxed 字符串回落直接赋 `value.ib_class` 损坏值——加 `isinstance(specialized_cls, IbClass)` 防御；③ 跨家族残留 `behavior[int]→fn_callable[str]` 放行——`_generic_family_compatible` 沿 src axiom 父链判定子类型关系，跨家族也校验实参。
- **测试**：判别性回归 +25（compiler TestGenericAssignability 23 + e2e TestBuiltinGenericValueIdentity 12 + runtime 白盒 test_generic_value_identity 4，去重净增）；触发用例 G6-01（GUARD）+ G6-02（PASS）入 T04。
- **✅ 已收敛（2026-08-13，unsafe-vibe-dev 617fb3a6/503f92fd 等 5 commits，全量 2579 passed / 1 skipped）**：
  **值层身份彻底收敛**（`_code_generic_type_identity.md` §2.6 全部边界 → `_code_generic_value_convergence.md`）：
  函数返回 / lambda 返回 / 调用实参 / 下标赋值 / 复合赋值 / 条件表达式 / 函数默认参数 /
  for 循环源 / 嵌套内层元素 / Optional 包裹容器 / 生成器 yield 容器 / 容器切片 / 运算符 /
  跨引擎反序列化——全部 type(list[int]值)=list[int]。统一"类型上下文→字面量"递归传递机制。
  两轮独立复核 + 第三轮全面扫描。**🔴 下一 session 交接**（`_HANDOFF_GENERIC_REMAINING.md`）：泛型体系剩余边界 7 项彻底修复分析（句柄类值身份/type_pool 匹配/元组解包检查/auto 推断/*expr 缓解等）。

## ✅ 已完成：G3 继承特化父类字段丢失 + Finding C any 逃生阀用户类复查（2026-08-13，unsafe-vibe-dev b0f4d74，全量 2365 passed / 1 skipped）

> 交接诊断经代码实证纠偏后根治（详见 PENDING_TASKS G3/BOUNDARY-G2 行 + WORKLOG）。

- **G3（chain-aware auto-init）**：交接推断"特化父类字段未绑定"被实证否定（`Node[int]`
  `default_fields` 含 `data`/`next`，继承链收集正确）。真实根因：`_hydrate_user_classes`
  自动构造器只收集**类自身 body** 无默认值字段 → 子类 auto-init 参数被削减并遮蔽父
  auto-init → 继承父类无默认值字段静默 None（原为文档化 Known Limit §六，按
  "文档化限制=修复候选"重新定性为真实缺陷）。**修复**：auto-init 参数 = 继承链全部有效
  无默认值字段（父类优先、子类同名覆盖），与 instantiate 字段收集同构（机制同构）；
  构造器生成拆为独立第二 pass。非泛型/泛型/多级继承全修；少传参 fail-fast 报缺参。
  文档：KNOWN_LIMITS §六/§十四#1③ + 06_oop。
- **BOUNDARY-G2 + Finding C（any 逃生阀复查）**：交接推断"运行时类型退化"被实证否定
  （`cur` 持续 `Node[int]`）。真实根因：试用用例无效（`Node[int]` 编译期禁止赋 None，
  None 哨兵不可行；`= any` 默认是非 None truthy any 类对象）+ 底层真实缺口 **Finding C**
  ——`_check_type` 对 USER_DEFINED CLASS 目标无条件跳过运行时复查 → any 类对象静默流入
  用户类变量（KNOWN_LIMITS §七 契约失效）。**修复**：对动态 any 逃生值强制
  `RUN_TYPE_MISMATCH`（is_assignable 因"类可调用"会放行，直接判定）。R5-04 现报清晰
  诊断码而非困惑 AttributeError。文档：KNOWN_LIMITS §七。

## ✅ 已完成：用户类泛型参数 PT-FEAT-3 完整落地（2026-08-12，unsafe-vibe-dev 35bb2de，全量 2339 passed / 1 skipped）

> 设计冻结 `PT_FEAT3_DESIGN.md`；独立复核两轮 PASS（P2-1 父特化恒注册 / P2-2 嵌套实参映射 全整改）。

- **全链路**：AST `IbClassDef.type_params`+`parent_args` + parser（`class Box[T]`/`(Box[T])`）+
  `TypeKind.TYPE_PARAM`/`TypeDef.type_params` + 语义类型参数占位解析 + `resolve_specialization`
  用户类分支（特化 spec 构造 + members 替换 + 父特化递归注册）+ 序列化（type_params/parent_args
  落 artifact）+ 运行时（`IbClass.__getitem__` 类型特化 + 特化类 hydration）。
- **已支持**：多特化并存 / 字段·方法参数·返回类型特化（含嵌套 `Box[list[int]]` 参数类型检查）/
  嵌套泛型 `list[Box[int]]` / 多参数 `Pair[K,V]` / 泛型继承 `class Sub[T](Box[T])`。
- **守卫**：裸用（注解+实例化）/ 实参数不匹配 / 字段-T 冲突 / Enum 泛型 / 类型参数遮蔽内置 /
  非泛型子类继承特化，均 fail-fast。
- **测试**：21 e2e + 2 序列化 round-trip（全量 2311→2339）。文档：06_oop §6.4 / KNOWN_LIMITS
  §十四 #1 / arch/02 §2.6 / 15_diagnostics。
- **边界**（KNOWN_LIMITS §十四#1 ①-⑧）：bound 约束 / `class Sub(Box[int])` / 父引用嵌套实参 /
  Enum 泛型，后续增量。

## ✅ 已完成：F9 显式配置 `ai.load_project_config`（2026-08-12，unsafe-vibe-dev a49555b，全量 2311 passed / 1 skipped）

> 用户拍板命名 + 本轮实施。独立复核 PASS（5 项整改全完成）。设计记录 `_code_ai_autoset.md` +
> 实施记录 `_code_f9_load_project_config.md`。

- `setup()` 去自动加载段（引擎启动不再自动加载 api_config.json）；新增 `load_project_config()`
  （ec/project_root 缺失 fail-fast + 路径规范化 + 缺失 no-op + 幂等）；vtable 注册；测试
  （无调用不加载/显式调用加载/fail-fast/符号链接/幂等/语言级可达）；examples 01/02/03 判断前
  加显式调用；文档同步（README/guide 01+02/syntax 11+15/config_loader/execution_context/
  catalog/codes）。

## ✅ 已完成：遗留独立窗口批次——PT-DEBT-24 call_intent 清理 + PT-AUDIT-3 S1-S5 处置 + 枚举实例化评估（2026-08-12，unsafe-vibe-dev，全量 2308 passed / 1 skipped）

> general agent 独立复核 PASS；设计记录 `_enum_instancing_assessment.md`。

- **PT-DEBT-24（S4）call_intent 死代码根治**：AST 均无 intent 字段 → call_intent 恒 None →
  全链清理（behavior 短路分支 / BehaviorCallSpec.pre_resolved / LLM 函数穿透参数 /
  IbBehavior.call_intent 值字段+序列化 / 工厂 / 协议）；保留 get_resolved_prompt_intents
  协议预留参数。
- **PT-AUDIT-3 S1-S5**：S4 根治；S5 双实现去重（共享 `_try_axiom_output_hint`）；
  S1/S2/S3 复核为已知边界（S1 dispatch hint 同步 .call 嵌套调度器仅 hint 含 VM 依赖 Waitable
  时可观察；S2 跨线程 EC 模块名改写需 worker 同步构造类且 drive 返回非实例；S3 task 线程写
  单写槽为纯可观测性竞态）——各登记独立设计窗口（`_PT_AUDIT3_RECORD.md` §三）。
- **枚举实例化设计候选评估**：`_enum_instancing_assessment.md`——维持现状（LLM 集成改造为
  核心硬伤：kernel 层无法构造实例 + 通用解析路径需类型感知包裹），独立设计冻结候选。

## ✅ 已完成：enum 补全 + 嵌套包 import 根治 + 文档批次 + 用户试用（2026-08-12，unsafe-vibe-dev，全量 2308 passed / 1 skipped）

> 按 `_ENUM_SWITCH_COMPLETION_HANDOFF.md` + 独立窗口打包（用户确认）。设计记录
> `_code_enum_completion.md`；独立复核（general agent）PASS + 建议项整改；用户试用
> `_LLM_TRIAL_ENUM_IMPORT_20260812/`（9 例全过）。

- **enum 补全（PT-FEAT-2）**：① **非 str 枚举 LLM 集成修复**——编译期枚举常量成员
  （含负数 `-1`）写 `MemberSpec.metadata["value"]`，`EnumAxiom` 建 `{成员名→成员值}`
  映射，from_prompt 大小写不敏感返回值；str 零回归、值≠名正确，真实 LLM 实证
  （qwen 输出成员名 OK→值 200→switch 命中）。② **迭代/数量**——`has_iter_cap` +
  `get_method_specs(to_list/len)` + 运行时 Enum 基类绑定（子类经父链继承）；
  `for v in Color:` / `len(Color)` 可用。③ **自定义方法 = 值模型边界**（`Color.RED`
  是底层值非实例，方法不可达）——文档化 KNOWN_LIMITS §二 §2.4，实例化枚举记设计候选。
  ④ KNOWN_LIMITS §二 更新。+22 契约/e2e 测试。
- **嵌套包 import 根治**：`import subpkg.util` + `subpkg.util.fn()` INT_INTERNAL_ERROR
  三层根因（嵌套段原始 Symbol 入 members / visit_IbImport 绑定全名 / 中间段 PRIMITIVE
  kind 重导入守卫 + 运行时缺包命名空间）全部修复；2 层/3 层/同包多导入合并全过；+4 e2e。
- **文档批次**：DOC-ISSUE-001~007 批量同步 + BOUNDARY-001~005 处置（001/002 已修核验，
  003/004/005 文档精确化）+ KNOWN_LIMITS §十四 #2 运算符覆盖度实测核对
  （比较/算术/一元/成员全可用，`is` 恒身份；+6 回归测试）。
- **用户试用**：自建 `_LLM_TRIAL_ENUM_IMPORT_20260812/`（harness 三层保护复用），
  9 例全过（含真实 LLM 非 str 枚举集成实证），**无新增缺陷**。
- **遗留**：枚举实例化（设计候选，独立窗口）；KNOWN_LIMITS §十四 #1 用户类泛型参数（独立大任务）；
  嵌套包 `import subpkg`（无子模块的纯包）仍 DEP_MODULE_NOT_FOUND（包目录非模块，Python 同）。

## ✅ 已完成：真实 LLM 压力试用暴露缺陷修复 + 易用性修复（2026-08-12，unsafe-vibe-dev，全量 2270 passed / 1 skipped）

> 按 `_FIX_PROPOSAL_CRITICAL_REVIEW_20260812.md` 修正后方案 + `_KERNEL_ISSUES_ANALYSIS_20260812.md`
> 根因分析执行（用户授权破坏性变更）。修复后独立复核全部 PASS。易用性修复见
> `_USABILITY_AUDIT_20260812.md`。

- **批次 A（低风险直接合并）**：**PT-DEBT-27** 真实 LLM provider 失败异常投递对称化
  （`_drive_loop_gen` Waitable yield except→pending_exception 重投递，TaskCancelled 穿透；+4 测试）；
  **PT-DEBT-25** `global` 关键字镜像 nonlocal（visit_IbGlobalStmt + prescan 排除 global 名，
  运行时零改动；+6 测试）；**PT-DEBT-28** `_spec.py` vtable 补注册 `ai.get_retry`/
  `is_auto_intent_injection_enabled`（+3 测试）。
- **批次 B（专项）**：**PT-DEBT-26** 整模块 import 档3 写入侧统一 MemberSpec 形态
  （`_symbol_to_member`/`_spec_to_typeref`）+ 档2 零参数 callable 按 kind 绑定（+4 测试）。
- **批次 C（设计级）**：**O1+I1** 用户类协议方法（`__call__`/`__iter__`）帧内 CPS 驱动
  （`_UserCallDrive` Waitable+CPSDrivable，根治嵌套调度器；生成器方法经 IbUserFunction.call 返回
  IbGenerator + resolve_iterable to_list；+9 测试）。设计记录 `_code_call_cps_drive.md`。
- **批次 D**：**O2** 字段默认值递归深克隆（try_deep_clone，消除内层 list/用户对象跨实例共享；+3 测试）；
  **文档修正**（05_functions §5.8/§5.9、KNOWN_LIMITS §二十四/§十四 #2/§一）。
- **易用性批次**：**return@~ 编译期拦截随迁 v2**（补全设计意图，消除"文档说禁止实际通过+运行时
  类型错"陷阱；+4 测试）；**switch 内 break 消费为 no-op**（C 习惯冗余写法不再报
  RUN_GENERIC_ERROR，CONTINUE 透传；+3 测试）；**布尔字面量错误引导**（true/false/none 报
  "Did you mean True/False/None"；+3 测试）；**KNOWN_LIMITS §十一 更新**（switch 基本可用 +
  使用约束）。
- **遗留待独立窗口**：嵌套包 `import subpkg.util` + 成员访问的 INT_INTERNAL_ERROR（修复前既有）；
  DOC-ISSUE-001~007 文档同步；BOUNDARY 记录；**enum 补全（见 `_ENUM_SWITCH_COMPLETION_HANDOFF.md`）**。

## ✅ 已完成：真实 LLM 全面压力试用重启（2026-08-12，修复后代码）

> **unsafe-vibe-dev，全量 2210 passed / 1 skipped（试用零回归，未改内核）**。
> 完整证据：`tasks_docs/_LLM_TRIAL_20260812/`（DESIGN/harness/cases/logs/REGISTER）+ 报告
> `（已清理任务文档）`。

- **试用地基**：死循环保护 harness（OS 进程级硬超时 SIGKILL 进程组 + LLM 调用
  超时，无超时不运行，零遗漏）+ 确定性文件化记录（logs/ + register.jsonl + REGISTER.md）。
- **D1 全语法遍历**：docs/syntax/01-15 每章特性真实 LLM 各跑一遍，~110 次运行全经保护。
- **A1-A5 重验全通过**：意图 @/@! 赋值路径（7339220 实证：r1=收到）、内建遮蔽+LLM 初始化
  （sum=7）、generator.to_list（U1）、dispatch 赋值后 idbg 观测（d6d28e1）、run_batch 观测（df1a896）。
- **B1-B3 补正式记录**：ihost 隔离（child 需自带 api_config.json）/内建/异常。
- **D2 压力试用**：交叉（生成器+意图+llmexcept、thread+chan+run_batch、类+LLM+slot、闭包+生成器）、
  正交（@+×run_batch、snapshot vs lambda、双批并发）、多层次（高阶 lambda、循环体 LLM+llmexcept）、
  多可能性（边界值/遮蔽拒绝/str'0'真值）、多文件（循环导入/插件/隔离子项目）全 PASS。
- **D3 批判检测**：格式服从稳定、C1 长提示注入完整、C2 非确定性稳定、C4 并发无竞态、
  llmexcept 真实收敛、耗尽可捕获、意图实证。
- **暴露问题（只记录，未修复）**：**4 项 P1 KERNEL_ISSUE**（global 写访问失效 /
  整模块 import+成员访问 INT_INTERNAL_ERROR / provider 失败 LLMCallError 逃逸 try/except /
  ai.get_retry 等 vtable 未注册）+ **7 DOC_ISSUE** + **5 BOUNDARY**。登记 PENDING_TASKS
  （PT-DEBT-25~28 + 清单），见 REGISTER §六/报告 §六。
- **合并条件重估**：检测维度已基于修复后代码确认（无 P0；4 项 P1 不阻断主路径，待独立窗口）；
  阶段 3 合并/push 仍待用户显式授权（禁 push 硬原则）。

## ✅ 已完成：合并收尾准备（2026-08-11，doc-health P1/P2 + 版本 0.2.0 + examples 真实跑通 + PT-AUDIT-3）

> **unsafe-vibe-dev，全量 2209 passed / 1 skipped**。合并前置全部完成，`_MERGE_READY_REPORT.md` 落档。

- **doc-health P1/P2 全部处置**（`_DOC_HEALTH_20260811.md`）：P1 16 项复核修齐（已修核对 4 + 实修 12，
  含 `@method` 陈旧引用、`已重构为包` 历史演变、09 章节编号、KDIAG 码表补全、super 归属唯一化、
  05_coroutine 状态文档重写、04_control_flow 小节归位、15_diagnostics 分域引言）；P2 12 项
  （A5 类构造 CPS 变更反映 arch/04 §2.7 + arch/05 公理 EXEC-4、README 阅读路径、howto 扩充 2 篇、
  死引用清理、定位段强化、TestHooks 模板化）。
- **pyproject 版本 0.1.0 → 0.2.0**（0.1.0 后 411 commits / 65 feat）。
- **examples 真实 LLM 跑通确认**：11 例全过（本地 qwen3.6-35b-a3b）；**暴露并修复 dispatch 赋值后
  idbg/ai 调用信息不可观测缺陷**（`_record_dispatch_call_info` 单写槽即时记录，resolve 补全 response，
  +3 回归测试，commit d6d28e1）。
- **PT-AUDIT-3 双路径专项审计执行**（general agent 独立审计）：无 P0；3 确凿 P2 漂移修复
  （run_batch 观测 / active_intents / _drive 装箱）+ generator 兜底 fail-fast + KNOWN_LIMITS 修正；
  5 疑似项待独立窗口（`_PT_AUDIT3_RECORD.md`）。
- **合并就绪报告**：`（已清理任务文档）`（四项合并条件全满足；阶段 3 待用户授权）。

## ✅ 已完成：R 批次 —— 统一执行地基复核与根治修复（R1-R6）

> **2026-08-07 用户裁定**：阶段 1-3 落地暴露的妥协处理**必须彻底修复，不留妥协**；工作成本/难度不参与权衡；
> IBCI 无用户，已文档化设计可为长远可维护性与架构健康性被推翻。
> **完整设计/深度分析/决策见 `（已清理任务文档）`**（无悬而未决问题）。

**批次（各独立分支，禁合并，全量零回归后手动 cherry-pick 应用 unsafe-vibe-dev）——全部完成**：

| 序 | 项 | 分支 | 内容 |
|----|----|------|------|
| 1 | R4 + R3 | `exp/exec-ra` | P3 公开协议（`IbCell.mark_shared_with_main`）+ D-04 意图修复（`IbThread` 本体满足 Waitable，unify `is_done`，auto-bind 支持 property-backed 方法，`await t` 可用）——**完成 82c9c0f，全量 1988/1** |
| 2 | R6 | `exp/exec-rb` | 嵌套函数自动只读捕获（与 lambda 同构，`nonlocal` 仅用于写）——P3 触发面回到审计预期宽度——**完成 35f1437，全量 1995/1** |
| 3 | R2 | `exp/exec-rc` | 调度器通知式唤醒（Waitable `register_wake` + 各 waitable 完成通知 + CommBuffer 回调表 + 引擎 spawn 钩子）——根治 poll+park 与"单待决阻塞"——**完成 c16b05e/c4c63aa，全量 1998/1** |
| 4 | R1 | `exp/exec-rd` | 函数调用 trampoline 化（`_vm_call_user_function` CPS 内联，EXEC-1 根治，深递归 Python 深度恒定）——**完成 6dc9214，全量 2001/1** |

**已定案（不再重议）**：R5 撤回（`await` 幂等是 auto-yield 组合的承载）；D-08 保留透明 async（CPS 天然可挂起 +
auto-yield 组合 + 值契约 + yield 自标记）。

**后续路线（R 批次已完成，进入下一主线）**：**阶段 4 PT-FEAT-9 诊断机制**（`DIAGNOSTIC_DESIGN.md` 已冻结）→
**阶段 5 `yield` 惰性生成器**（`EXEC_FOUNDATION_DESIGN.md` §5.2）→ 增量（streaming / host async 改进）。

---

## ✅ 已完成：阶段 4 PT-FEAT-9 内核结构化诊断机制重建（CORE_DEBUG 替代物）

> **2026-08-07 完成，unsafe-vibe-dev，全量 2021 passed / 1 skipped**。
> 设计权威：`（已清理任务文档）`（D1-D7 + 诊断码集 + 实施步骤 A-E）。
> 完整落地记录见 `WORKLOG` PT-FEAT-9 阶段 B-D 落地。

- **B 机制落地**：`codes.py` 增 `=== 内核诊断 (KDIAG_) ===` 节（10 码）；新建
  `core/runtime/observability/diagnostics.py`（`kernel_diagnostic` helper：单一记录双投影——投影A 警告
  不门控 + 投影B 事件受 observability 门控；rc 解析 best-effort：显式 > current-EC > 无→仅警告面）；
  events.py docstring 对账确认 P4 已先行完成（如实清单），增补 `kernel_diagnostic`；helper 单测 8 项。
- **C 站点迁移**：12 处运行时 warnings → `kernel_diagnostic`（文案逐字保留、detail JSON-safe）——
  协议回退 8 / 策略 2 / 运行时 2；host_interface（kernel 层）用函数体内惰性 import（先例
  registry.py:283）；scheduler.py 编译期站点按 D5 保持 warnings。
- **D 事件投影测试**：tests/e2e/test_kernel_diagnostics.py——协议回退双投影（警告逐字 + 事件结构化）、
  策略忽略站点无活跃 EC→仅警告面（fail-open 实证）、observability 门控（关→事件停、警告留）。
- **E docs 治理**：新写 `docs/architecture/09_observability.md`（状态面/事件面/诊断面/配置面四机制
  单点真理）；README/ARCHITECTURE/01_principles 索引同步；WORKLOG 记录。

**归档记录（均已根治 2026-08-08，见下方"已完成：2026-08-08 批次"节）**：PT-DEBT-9（RecursionError 级联包装）、PT-DEBT-10（线程体递归非 trampoline）、PT-DEBT-11（`_UserFunctionCall` 定义位置）。

---

## ✅ 已完成：阶段 5 yield 惰性生成器（2026-08-08）

> **unsafe-vibe-dev，全量 2043 passed / 1 skipped**（基线 2029，+14）。独立分支 exp/yield-generator 实验 → 手动应用（设计/决策见 `（已清理任务文档）`）。

- **yield 惰性生成器落地**（c8b8956）：含 `yield` 的函数自动为惰性生成器（D-08 自标记函数种类，无 async 关键字）。
  - 词法 `yield` 关键字 + 语法 `yield` 表达式（LOWEST 优先级，`yield x+1` 产出 `x+1`）+ AST `IbYieldExpr`/`IbFunctionDef.is_generator`。
  - 语义 `_contains_yield` 自动标记生成器；yield 仅函数体内（`SEM_YIELD_OUTSIDE_FUNCTION`）；生成器返回类型 = `generator[元素类型]`。
  - 类型 `GENERATOR` TypeKind + `generator[T]` 泛型（factory/generic/type_ref/artifact_rehydrator 全链路）。
  - VM `vm_handle_IbYieldExpr` yield `GeneratorYield(value)` 标记 + `_drive_generator_loop` 单可恢复驱动（与 `_drive_loop_gen` 同构，GeneratorYield 挂起交付、Waitable 宿主等待）。
  - 运行时 `IbGenerator` 值对象 + `for`/`to_list` 迭代；调用路径经 UserFunctionCall/make_generator_driver。
  - **e2e 9 项**：基础迭代/状态跨 yield 保留/嵌套循环/条件内 yield/break 提前终止/生成器 as 值/LLM 组合（await 正交）/auto 赋值/非函数体 yield 报错。
  - docs/syntax/05_functions.md §5.8 惰性生成器章节。
- **架构缺陷优先起点清空**：PT-DEBT-9/10/11 全部根治（上一批次）。下一主线已完成，无阻塞项。

## ✅ 已完成：2026-08-08 批次（PT-DEBT-11/9/10 根治）

> **unsafe-vibe-dev，全量 2029 passed / 1 skipped**。完整记录见 `WORKLOG` 与 git 历史。

- **PT-DEBT-11**（4bf2644）：`UserFunctionCall` 下沉 `core/runtime/shared/user_call.py`（与 Signal/Waitable
  同类叶子），handler/线程体不再向上依赖 VMExecutor 内部类——保持"handler 是叶子、VMExecutor 调度"分层方向。
- **PT-DEBT-9**（c75541f）：环境限制异常（RecursionError/MemoryError/SystemError）根因保留——新建
  `core/runtime/shared/env_limits.py` 判定 + `diagnostics.handle_environment_limit` 发射 `KDIAG_RUNTIME_ENV_LIMIT`
  诊断，VM 五处语义错误包装站点（Symbol not defined/VM: Call failed/模块导入/try-except）不再掩盖根因。
  深递归触底时用户看到 `RecursionError` 而非误导性符号未定义/调用失败（+2 测试）。
- **PT-DEBT-10**：`_drive_generator` 改显式生成器栈（trampoline，与 `_drive_loop_gen` 同构），线程体内深递归
  不再嵌套 Python 栈（depth=300 e2e 通过）。顺带根治线程体模块级函数解析（任务全局作用域链到模块作用域，
  此前线程体无法解析模块级函数，n≈2 即失败）、线程逻辑栈上限对齐主路径（`max_call_stack`）、
  `_vm_call_user_function`/`IbUserFunction.call`/`IbLLMFunction.call` push 后 finally 无条件 pop 的
  栈不均衡潜在 bug（`pushed` 标志）（+1 测试）。

## ✅ 已完成：2026-08-08 批次（穿透根治 + 文档对账治理 + 意图栈历史兼容移除）

- **kernel→runtime 穿透根治**（d11bad0）：用户红线"禁止一切 kernel→runtime 穿透"。全仓扫描确认两处
  （registry 惰性 import EventBus、host_interface 惰性 import kernel_diagnostic），改依赖注入——
  `registry.set_event_bus`（未注入 get fail-fast、peek fail-open）+ `HostInterface.set_diagnostic_emitter`
  （未注入回退 warnings.warn），engine 组装期注入。残留扫描 core/kernel/ 零 runtime import。
- **死代码清理**（ffaffc0）：删 `KernelRegistry.clone()`（零调用方，spawn 隔离走独立 engine 路径）。
- **文档-代码对账治理**（fe80595/5f5e26d/a8de1b1/3368c28）：5 个并行 general task 全量审查 →
  P0 断链/自相矛盾 4 处、P1 过期/红线/事实错误 ~20 处、P2 缺失/格式/体系 ~15 处全部修复。
  重点：arch/04、05 执行模型对齐调度器（TaskScheduler/Waitable/trampoline/await/auto-yield）、
  kernel-native 清单补 iruntime、意图系统穿透代码块、红线清理（日期戳/已落地/阶段5/搁置项）。
- **意图栈扁平化历史兼容彻底移除**（3ce9b7d）：用户裁定"无事实用户，历史兼容不是考虑项"。删序列化
  `intent_stack` 平铺双写 + 旧格式反序列化回退 + `context.intent_stack` property + 两处接口协议声明；
  补意图上下文 6 槽位 round-trip 测试（+3）。
- **登记 PT-FEAT-10/11/12**（8376195）：原被删愿景（UID 统一/序列化器自动化/AST UID 字段）中值得
  保留的未来任务。

---

## ✅ 已完成：P0 阶段 5 增量（`next()` 内建 + `yield from` 生成器委托）（2026-08-09）

> **unsafe-vibe-dev，全量 2083 passed / 1 skipped**（基线 2074）。设计记录 `（已清理任务文档）`。

- **`next()` 内建**（c61a6e0）：`IbGenerator` 经 `generic_next()` 逐次推进，耗尽抛可捕获 `InterpreterError`；其它可迭代对象取首元素。
- **`yield from` 生成器委托**（本批次）：把子迭代对象（嵌套生成器 / 序列 / 有 `__iter__` 的对象）的每个产出
  **逐值透传**为当前生成器的产出（惰性：逐值推进、外层 `break` 提前终止时子迭代不再继续）；子生成器为
  `IbGenerator` 时表达式值 = 其 `return` 值。全管线：AST `IbYieldFromExpr` + 语法（`yield` 后 `match(FROM)`）+
  语义（仅函数体内，`SEM_YIELD_OUTSIDE_FUNCTION`）+ 类型（`resolve_iter_element` 补 `GENERATOR` kind）+
  VM handler（复用 `GeneratorYield`/`generic_next` 既有机制）+ e2e 8 项。
- **顺带根治预存缺陷**：`_drive_generator_loop` 的 `UserFunctionCall` 分支缺 `is_generator → make_generator_driver`
  （与 `_drive_loop_gen` 同构）——此前生成器体内调用生成器函数损坏（`yield from inner()` 依赖此修复）。
- **迭代解析收敛（单一权威源）**：`for` 的迭代解析（序列 / `IbGenerator`→`to_list` / `__iter__` / `to_list`）抽为
  `_shared._resolve_iterable`，`for` 与 `yield from` 共用——去双写，行为不变（全量零回归验证）。

## ✅ 已完成：PT-FEAT-5 错误用户友好化——诊断码目录（2026-08-09）

> **unsafe-vibe-dev，全量 2092 passed / 1 skipped**。PT-FEAT-5 四项中第一项（诊断码用户友好化）落地。

- **诊断码目录 `core/base/diagnostics/catalog.py`**（单点真理）：76 个诊断码（LEX/PAR/SEM/DEP/INT/RUN/KDIAG）→
  `CodeInfo(title, fix)`——一句话定位 + 修复指引。新增码必须登记（契约测试强制覆盖完备，无孤儿条目）。
- **Formatter 集成**：`DiagnosticFormatter` 渲染时按码附加"说明/修复"段；未登记码 fail-open（正文照常输出不阻断）。
- **参考文档 `docs/syntax/15_diagnostics.md`**：按 WRITING_GUIDE 诊断码模板（触发条件/严重级别/修复方式），
  与目录一一对应（数据驱动，无正文复制）；`SYNTAX_REFERENCE.md` 新增第四部分"诊断与错误"。
- **契约测试 `tests/contracts/test_diagnostic_catalog.py`**：CAT-1 每码有条目 / CAT-2 无孤儿 / CAT-3 条目规范 /
  CAT-4 已知码渲染说明 / CAT-5 未知码 fail-open。

## ✅ 已完成：PT-FEAT-5 诊断工具——符号表/类型绑定 JSON/dot 导出（2026-08-09）

> **unsafe-vibe-dev，全量 2103 passed / 1 skipped**。PT-FEAT-5 四项中第二项落地。

- **`core/compiler/diagnostics/exporter.py`**（只读导出，单一权威源）：`export_symbols_json`（作用域树递归，
  符号 name/kind/uid/type/provenance）+ `export_type_bindings_json`（节点类型+位置 → 类型名）+
  `export_dot`（作用域 cluster + 符号节点 + 作用域父子/类型绑定边）+ `export_artifact`（按格式统一导出）。
- **CLI 修复（两个预存死路径）**：`inspect` 命令原只有 handler 无 subparser 且引用未定义 `module_name`（死代码）；
  `semantic` 命令原只有 subparser 无 handler（静默无输出）。统一接入 exporter，支持 `--format json|dot` 与 `--output`。
- **契约测试 `tests/contracts/test_diagnostic_exporter.py`**：EXP-1 根符号字段 / EXP-2 类型绑定映射 /
  EXP-3 dot 结构 / EXP-4 JSON round-trip / EXP-5 空数据 fail-open / CLI-1 inspect+semantic 子进程 /
  CLI-2 bench 成功 + 编译错误退出 1。

## ✅ 已完成：PT-FEAT-5 编译时间基准（`bench` 命令）（2026-08-09）

> **unsafe-vibe-dev，全量 2107 passed / 1 skipped**。PT-FEAT-5 四项中第三项落地。

- **`main.py bench <file> --runs N --warmup M`**：warmup 后重复编译 N 次，报告 min/avg/max/stdev。
  编译失败按诊断码格式（catalog 说明）报错并以非零码退出（fail-fast）。
- **CLI 测试**：tests/contracts/test_diagnostic_exporter.py CLI-2（bench 成功输出统计 / 编译错误退出 1）。
- **剩余子项**（PT-FEAT-5 未完）：**CI/CD**——涉及远程 push，属禁 push 硬原则范围，须用户显式授权后另行执行。

## ✅ 已完成：PT-FEAT-10 UID 生成统一（2026-08-09）

> **unsafe-vibe-dev，全量 2121 passed / 1 skipped**。P1 第一项落地。

- **`core/base/uid.py` 单一权威源**：UID 生成收敛为九家族函数（`scope_uid`/`child_scope_uid`/`symbol_uid`/
  `intrinsic_uid`/`node_uid`/`type_uid`/`anon_symbol_uid`/`asset_uid`/`rt_scope_uid`），**零内联格式字符串**。
- **调用方全部接入**：symbols.py（scope/symbol）、serialization（node/type/anon/asset）、context.py（intrinsic）、
  scheduler.py（intrinsic）、runtime intrinsics/__init__.py（intrinsic）、interpreter.py（intrinsic）、
  runtime_serializer（rt_scope）。
- **格式逐字不变（round-trip 保真）**：收敛只集中格式、不改任何已产出 UID 值——序列化 round-trip 与
  `intrinsic:` 前缀比对（binding/symbol_resolution/engine）均不受影响。
- **契约测试 `tests/contracts/test_uid_generator.py`**：UID-1 格式逐字一致 / UID-2 确定性 / UID-3 区分性 /
  UID-4 rt_scope 每次唯一。

## ✅ 已完成：异步地基 M1/M2 收尾（.call 双写收敛 + 驱动去重）（2026-08-09）

> **独立分支 exp/async-m1m2 实验，全量 2137 passed / 1 skipped**。统一执行模型闭环全部收尾。
> 设计记录 `（已清理任务文档）` / `_code_m2_drive_dedup.md`；落地状态 `_ASYNC_UNIFY.md`。

- **M2 驱动去重**（31884a8）：线程体 `coordinator._drive_generator` 从"手写阻塞泵"改为复用主 VM 单一权威驱动
  ——根生成器包装为 `VMTask`，经 `task_vm._drive_loop_gen` + `TaskScheduler` 驱动到完成；trampoline/GeneratorYield/
  Signal/None 规范化/协作取消统一由 `_drive_loop_gen`+`TaskScheduler` 承担，消双写；`TaskScheduler` park 期取消承接
  线程体 cancel 中断（初版手写泵对 recv `.result()` 死锁，self-grill+实测发现后改 TaskScheduler）。移除死参数 `send_first`。
- **M1 `.call` 双写收敛**（0bdecbb/4038102/3060950）：四个可调用对象 `.call()` 变薄宿主包装，委托 CPS 权威路径 +
  `_drive_generator`——IbFnCallable→`_vm_call_fn_callable`、IbUserFunction→`_vm_call_user_function`、
  IbLLMFunction→`_vm_invoke_llm_function`、IbBehavior→`_vm_invoke_behavior`；消模块/意图/作用域/闭包/self+super/
  实参绑定双写。返回值语义探针实测一致（void/none/ret）。清理 user_functions.py 8 个死 import；保留真原生
  `IbNativeFunction`/`IbBoundMethod`（无 CPS 孪生）与 `bind_behavior_*` helper。
- **独立复核（general agent）**：A/B/D 放行 + C 记录（IbUserFunction void 返回语义向主路径收敛，方向正确）。
- **回归测试 +9**（`tests/runtime/test_call_drive_convergence.py`）：宿主 .call void/return/self/fn_callable 返回语义
  + 线程体取消/深递归保持。修 coordinator 陈旧 docstring；生产代码注释任务代号清除。

## 📋 交接要点（下一 session）

- **✅ 已完成（2026-08-14，unsafe-vibe-dev，全量 2693 passed / 1 skipped）**：
  **T07 三项 P1 修复 + DOC-24~28 文档同步**（承接 `_HANDOFF_T07_FINDINGS.md`）。
  ① OPTIONAL-SCOPE-1（函数作用域局部变量声明类型编译期丢失的系统性根治：
  prescan 解析注解 + type_checking 复用 owned_scope + 闭包/cell 写包装对齐 +
  rehydrator kind 保真 + TYPE_PARAM 检查放行）；② OPTIONAL-CONTAINER-1
  （IbOptional.receive 统一委托链 + resolve_iterable 识别 Optional）；
  ③ ATTR-READ-1（_default_getattr 未命中改抛 RUN_ATTRIBUTE_ERROR，读取/调用
  一致 fail-fast）。触发用例 D2-09/D2-10/D1-13 全部核销转 PASS；判别性回归 +28。
  详见上方"已完成"节与 WORKLOG。

- **✅ 已完成（2026-08-14，T05/T06 剩余代码缺陷四项全部修复）**：
  **CROSSMOD-LLM-1 跨模块类型注解解析（P1）**——`_resolve_type` 支持 IbAttribute
  点号限定注解（geo.Counter），行为节点 node_to_type 绑定 module 限定 spec，
  D3-02/D2-05 从 KERNEL_ISSUE 转 PASS。**KI-2 统一 Optional 值模型（P2）**——
  `Optional[T]` 空值恒为 IbOptional 包装（变量/参数/返回/字段/容器元素一致），
  `is None`/`is_none()`/`== None` 三等价，伴生根治参数 spec/llmexcept 类符号/
  deep_clone/N==Opt/容器 dict+tuple 等缺陷。**幽灵诊断码根治（P2）**——8 码
  7 发射 + 1 删减（PAR_MULTIPLE_INTENTS）+ RUNTIME_ERROR 默认码替换 +
  CAT-7 可发射性契约。**set_mock_mode 对称开关（P3）**。全量 **2665 passed /
  1 skipped**。设计：`_code_optional_unify.md`/`_code_ghost_codes.md`/
  `_code_set_mock_mode.md`。

- **✅ 已完成（2026-08-14，统一类身份模型 + T06 试用 + docs 治理）**：
  **同名类运行时类表宏观根治（`_code_class_identity_unify.md`）**——S1 run_string
  入口锚点 / S2 入口类 qualified（删 qualify_types 双轨）/ S3 单类表 / S4 KI-1 线程
  侧表 + is_truthy 任务本地化，独立复核放行后 cherry-pick unsafe-vibe-dev，全量
  2616/1。**T06 真实试用**（20 用例 18P+2KI，KI-1 核销，CROSSMOD-LLM-1 登记）。
  **docs/ 全量治理**（DOC_ISSUE-1~23 + T06 新发现，doc-governance）。详见已完成节。

- **✅ 已完成（2026-08-14，跨模块同名类运行期 module 化根治 + T05 批判试用 + 内核分析）**：
  **跨模块同名类运行期类表 module 化（S5 运行期闭环）**——注册键=spec.qualified_name +
  get_class module 感知 + _specialize/artifact_loader/序列化 module 化 + resolve_class_module
  权威父 module 解析；判别性回归 +6（geo.Box=105/graph.Box="hi!"）；独立复核 P1 已整改；
  cherry-pick unsafe-vibe-dev 6e68329c，全量 2614/1。**T05 批判性压力试用**——40 用例
  37P+1G+2KI（跨模块回归 12 全 PASS + 对抗 17P+1G + 真实 LLM 8 全 PASS）+ 文档核验
  23 DOC_ISSUE；内核粗略根因分析 2 项（CROSSMOD-THREAD-1/OPTIONAL-ISNONE-1）。
  详见上方"已完成"节与 `_HANDOFF_T05_ISSUES.md`。

- **✅ 已完成（2026-08-13，unsafe-vibe-dev b0f4d74，全量 2365 passed / 1 skipped）**：
  **G3 继承特化父类字段值丢失 + Finding C any 逃生阀用户类复查 根治**。交接诊断经代码
  实证纠偏：G3 非"特化父类字段未绑定"而是**自动构造器只收自身 body 无默认值字段**
  （文档化 Known Limit §六，按"文档化限制=修复候选"重新定性为真实缺陷）→ 修复为
  **chain-aware auto-init**（构造器参数=继承链全部有效无默认值字段，父类优先、子类同名
  覆盖，与 instantiate 收集同构）；BOUNDARY-G2 非"类型退化"而是试用用例无效（`Node[int]`
  禁止赋 None，None 哨兵不可行；`= any` 默认是非 None truthy any 类对象）+ 底层真实
  缺口 **Finding C**（`_check_type` 对用户类目标无条件跳过运行时复查，any 类对象静默流入，
  §七 契约失效）→ 修复为对动态 any 逃生值强制 `RUN_TYPE_MISMATCH`。+10 e2e；
  KNOWN_LIMITS §六/§七/§十四#1③ + 06_oop 文档同步。

- **✅ 已完成（2026-08-13，unsafe-vibe-dev 620de1c4，全量 2366 passed / 1 skipped）**：
  **试用体系重构（Phase B 收尾 + Phase C + Phase D 全部完成）**。
  1. **T01 LLM 批真实重跑验证**（Phase B 收尾）：57 个 LLM 用例真实重跑 **55 PASS + 2 GUARD**
     （零 HARNESS/零缺陷复现）。断言从基线 `DONE` 精化为稳定确定性行；修复 8 个脚本缺陷
     （5 import 位置 F9 适配遗留 + 2 守卫断言 + 1 API 类型）+ child_llm F9 配置。
  2. **Phase C 干净彻底**：用户原则确立——**套件不冻结历史资产、问题直接重构，唯一底线不为
     规避缺陷改套件（缺陷触发用例保留）**。删除 40 个过期文档（设计/报告/审计/临时 `_code_*`）；
     套件重构（T02 T3/T4/T5 断言改映射有效性 / T04 R1-05/R5-01/R5-04 重构为修复后语义、删 b
     变体）；4 套 register.jsonl classification 写回 **100%**（T01 55P+2G / T02 8P+1L /
     T03 22P+6G+1KI+1H / T04 24P+7G+1KI+1H）。
  3. **Phase D 自动化衔接**：报告自动生成器 `_toolkit/gen_register.py`（register.jsonl→REGISTER
     骨架）+ 收敛流程硬规则 `_toolkit/PHASE_D_AUTOMATION.md`（缺陷修复=根因修复+tests/ 回归双交付
     验收门）。

- **✅ 已完成（2026-08-13，unsafe-vibe-dev 0fee0c43，全量 2377 passed / 1 skipped）**：
  **GEN-5/GEN-6 架构级修复（`GEN_FIX_ARCHITECTURE.md` 四层方案全部落地）**。
  统一根因 = **TypeRef 生命周期双端口径漂移**（构造端扁平化 + 解析端丢实参 + 注册端机制不全）。
  1. **第 3 层（GEN-5，c00c87bb）**：`visit_IbSubscript` 表达式位置复用 `_resolve_type` 递归，
     GEN5-01 核销（PASS）。
  2. **第 1 层（GEN-6A，8f7fff8a）**：运算符结果类型推断改 `resolve_typeref` + 14 个 `.head`
     解析点迁移（记录根因纠偏：触发因子是 `-> Vec[T]` 返回类型，非参数形态）。
  3. **第 2 层（GEN-6B，52e7992f）**：`_param_type_ref` 复用 `from_spec` + engine 扁平残留 +
     `to_typeref`/`from_spec` 双实现收敛（统一委托）；D2-01 核销（PASS）。
  4. **第 4 层（0fee0c43）**：`03_type_system.md` §3.4bis 登记 TypeRef 唯一权威入口 + docstring 标注。
  判别性回归 +11（test_operator_overrides +3 / test_user_class_generics +8）。

- **✅ 已完成（2026-08-13，unsafe-vibe-dev e45dbb75，全量 2519 passed / 1 skipped）**：
  **spec→TypeRef 收敛 + 测试套件重构（反思分析驱动）**。
  **A 内核收敛**（反思揭示三实现分裂）：A1 `_spec_to_typeref` 委托 `from_spec`
  （修复 fn_callable 腐蚀/thread 读错字段/chan 扁平化）+ A2 `from_spec` 补 tuple
  positional 分支 + A3 死接口清理（删 to_typeref/restore，TestToTyperef→TestTypeRefFromSpec）。
  **B 测试套件重构**（测试目标回归"应该具备的行为"）：B1 b 类反向断言改正面契约 +
  B2 空洞测试强化 + B3 47 文件历史锚定措辞清理 + B4 脆弱断言评估（4 类均合理保留）+
  B5 meta docstring 历史锚定扫描规则永久化。

- **✅ 下一 session 主线候选**（按 `PENDING_TASKS.md` §〇 择定）：
  - **✅ 类型体系地基根治已完成（S0-S7 + 遗留边界，全量 2608/1）**：见上方"已完成"节。
  - **✅ 跨模块同名类运行时类表 module 化已根治（2026-08-14，全量 2614/1）**：
    S5 运行期闭环——注册键 = spec.qualified_name + get_class module 感知 + _specialize
    特化名/父链 module 化 + artifact_loader 水化/class_to_node module 化 + 跨引擎
    round-trip qualified 名 + (module,name) 联合匹配。判别性回归 `geo.Box.get()`=105 /
    `graph.Box.get()`="hi!"（方法表不串扰）。设计 `_code_runtime_class_module.md`；
    已知边界（LLM 裸名返回路径 graceful 退化 / 未编译目标引擎用户类重建受封印限制）
    登记 KNOWN_LIMITS §10.2。
  - **供应商感知思考禁用机制**（P2 待设计）：逐供应商参数形态覆盖思考禁用 + 检测失败警告。
  - 或按 `PENDING_TASKS.md` §〇 其余项：CI/CD 重新设计、PT-DEBT-4 `file` 重命名、
    PT-AUDIT-1/2 长期审计。
- **✅ 独立缺陷窗口已完成（2026-08-13，unsafe-vibe-dev 80294a64/447ad35c/7a15c1b9，全量 2559 passed / 1 skipped）**：
  - **内置泛型赋值检查缺失（缺陷一，P1）**：`HANDOFF_GENERIC_ASSIGNABILITY.md` §一。`is_assignable` 同家族结构化实参比较根治，10/11 类拦截，协变/子类型兼容保留。
  - **内建泛型值层类型擦除（缺陷二，P1-P2）**：`HANDOFF_GENERIC_ASSIGNABILITY.md` §二。特化 spec 水化为运行时特化类，`type(list[int]值)=list[int]`，运行时值层类型安全闭环。
  - 详见上方"已完成"节与 `PENDING_TASKS.md` §〇。
- **✅ 值层身份根治已完成**（`_code_generic_value_convergence.md`，2026-08-13）：全部容器字面量产生路径值层身份保真。**剩余已知边界**（独立窗口）：`-> auto` 泛型实参推断（auto 语义固有局限）/ `-> generator[T]` 显式标注二次包裹（预存 c8b89564）/ `*expr` 展开实参（根本限制）。
- **🟡 独立缺陷窗口（不阻塞主线）**：
  - **供应商感知思考禁用机制**（P2 待设计）：逐供应商参数形态覆盖思考禁用 + 检测失败警告。
- **📌 本 session 已完成**（临时问题全部闭环）：T01 LLM 批真实重跑 55P+2G；过期文档删除 40；
  套件重构（不冻结原则）；classification 写回 100%；gen_register 报告生成器 + 收敛流程硬规则；
  **GEN-5/GEN-6 架构级修复（四层）**；**spec→TypeRef 收敛 + 测试套件重构（A+B）**；
  **内置泛型类型身份双轨根治（缺陷一+缺陷二）**。

- **✅ 已完成（2026-08-12）**：**enum 补全 + 嵌套包 import 根治 + 文档批次 + 用户试用**
  （unsafe-vibe-dev，全量 **2308 passed / 1 skipped**）。enum 补全（非 str 枚举 LLM 集成
  真实模型实证 / 迭代 / 数量 / KNOWN_LIMITS §二）+ 嵌套包 `import subpkg.util` INT_INTERNAL_ERROR
  根治（2层/3层/同包多导入合并）+ DOC-ISSUE-001~007 + BOUNDARY-001~005 + 运算符覆盖度核对。
  独立复核 PASS + 用户试用 `_LLM_TRIAL_ENUM_IMPORT_20260812/` 9 例全过（无新增缺陷）。
  详见上方"已完成"节与 `_code_enum_completion.md`。

- **✅ 已完成（2026-08-12）**：**阶段 3 合并执行**——`unsafe-vibe-dev` 全面合并取代 `main`（用户显式授权）。
  `git merge --no-ff`（merge commit `eb4a7d1`），main 树 == unsafe-vibe-dev 树，全量 **2308 passed / 1 skipped**
  验证通过；push main 到 origin。原 unsafe-vibe-dev 本地 + 远端已删除，从新 main 分支出新 unsafe-vibe-dev
  （== origin/unsafe-vibe-dev == eb4a7d1）供后续开发。

- **✅ 已完成（2026-08-12）**：**遗留独立窗口批次**——PT-DEBT-24 call_intent 死代码根治 +
  PT-AUDIT-3 S1-S5 处置（S4 根治 / S5 去重 / S1-S3 已知边界）+ 枚举实例化设计候选评估
  （`_enum_instancing_assessment.md`，维持现状）。独立复核 PASS，全量 2308/1 零回归。

- **✅ 已完成（2026-08-12，unsafe-vibe-dev 35bb2de，全量 2339 passed / 1 skipped）**：**用户类泛型参数（PT-FEAT-3）**——
  设计冻结 `（已清理任务文档）`（6 项开放问题决断）+ 全链路落地（AST/parser/语义/序列化/运行时/
  诊断/文档）。已支持多特化并存/字段·方法参数·返回类型特化/嵌套泛型/多参数/泛型继承；守卫含裸用拦截、
  实参数不匹配、字段-T 冲突、Enum 泛型拒绝、类型参数遮蔽内置拒绝。21 e2e + 2 序列化 round-trip；
  独立复核两轮 PASS（P2-1 父特化恒注册 / P2-2 嵌套实参映射 全整改）。

- **✅ 泛型压力/恶意试用完成（2026-08-12，`_GENERICS_TRIAL_20260812/`，30 次运行全经死循环保护）**：
  D1 核心语义（7）+ D2 正交交叉（泛型×运算符/继承/协议/容器/控制流/函数/并发/生成器/行为/闭包/多文件，
  11）+ D3 恶意挑刺（10，守卫类 PASS）。**发现并全部修复**（深度核验 + 两轮独立复核）：
  ① **G2（编译期）自引用字段 `Node[T]` 特化替换失效**（`from_spec` 扁平化既有行为暴露）——
  修复：TypeDef.type_args+base_name + from_spec 结构化；② **G1（运行期）方法体 `Box[T]`
  类型参数表达式失效**（运行期符号解析）——修复：type_param_uids 编译期收集 +
  方法帧 _bind_type_params 注册；③ **BOUNDARY-G1** 非法特化实参（`Box[42]`/`Box[None]`/
   `Box[void]`）编译期未拦——修复：语义层拦截；④ **双通道设计缺陷** descriptors 两套实现——
   修复：type_args 结构化单一权威源。全量 2339→2350，+11 e2e。详情 REGISTER.md 与 PENDING_TASKS。

- **✅ 泛型修复回归试用完成（2026-08-12，`_GENERICS_TRIAL_FIX_20260812/`，28 用例 + 冒烟全经死循环保护）**：
  修复成果验证：G1 方法体类型参数（标量/嵌套/多参数/交替/生成器/深层嵌套）、G2 自引用基础、
  BOUNDARY-G1 守卫（None/auto/void 按 base/字面量/嵌套）、双通道 descriptors 全 PASS。
  **新发现 2 项既有缺陷**（git worktree 在修复前 35bb2de 复现，非本次引入）：
  ① **G3** 继承特化 + 父类字段值丢失（P1，静默 None——`Linked[int](5).get()` 返回 None）；
  ② **BOUNDARY-G2** 自引用链 while 遍历 `cur = cur.next` 类型退化 any（P2）。登记 PENDING_TASKS。

- **✅ 已完成（2026-08-12，unsafe-vibe-dev a49555b，全量 2311 passed / 1 skipped）**：**F9 显式配置**——
  用户拍板命名 `ai.load_project_config` + 本轮实施。`setup()` 去自动加载段；新增
  `load_project_config()`（ec/project_root 缺失 fail-fast + 路径规范化 + 缺失 no-op + 幂等）；
  vtable 注册；测试（无调用不加载/显式调用加载/fail-fast/符号链接/幂等/语言级可达）；examples
  01/02/03 判断前加显式调用；文档同步（README/guide 01+02/syntax 11+15/config_loader/
  execution_context/catalog/codes）。独立复核 PASS（5 项整改全完成）。设计记录 `_code_ai_autoset.md`
  + 实施记录 `_code_f9_load_project_config.md`。

- **📌 独立窗口（与主线错峰）**：
  - PT-DEBT-4 `file` 重命名（破坏性）；PT-AUDIT-3 S1-S3 已知边界（跨线程 EC 状态共享 /
    dispatch hint 嵌套调度器 / 单写槽线程化，各需设计窗口）；枚举实例化设计冻结
    （`_enum_instancing_assessment.md`）；`import subpkg`（纯包目录）DEP_MODULE_NOT_FOUND
    （Python 同语义，低优先增强）；CI/CD 重新设计（P0，独立规划）；PT-FEAT-13 C4-C7 已落地、
    C8（容器类型改善）远期。

- **📌 已完成支线（2026-08-11 本 session）**：
  - **PT-AUDIT-3 双路径分裂专项审计已执行**（general agent 独立审计 + 主代理核验）：无 P0；
    3 确凿 P2 修复（run_batch 观测 / active_intents 漂移 / _drive 装箱一致）+ generator 兜底
    fail-fast + KNOWN_LIMITS §二十四 修正（commit df1a896）；5 疑似项记录待独立窗口
    （`_PT_AUDIT3_RECORD.md`）。
  - **PT-DEBT-24**（call_intent 死代码）：PT-AUDIT-3 复核确认，登记待独立窗口清理。
  - **F9**（import ai 配置副作用）：评估为**设计意图保持**（fail-fast 契约，测试显式处理）。

- **本 session 已完成批次（供回顾，见 git 历史）**：
  U1-U7 修复 → 意图注入纠错（7339220）→ P1-P4 决断 → T1-T5 泛化审计 → **合并收尾准备
  （doc-health P1/P2 + 版本 0.2.0 + examples 真实跑通 + dispatch 观测修复 + 合并就绪报告）→
  PT-AUDIT-3 → **真实 LLM 全面压力试用重启（2026-08-12）**。全量 **2210 passed / 1 skipped**（零回归）。

- **CI/CD 状态**：**GitHub 侧自动触发已停用（2026-08-11，`.github/workflows/ci.yml` → `workflow_dispatch`）**；
  待单独设计"可靠化/实用化"后重新启用，勿自动恢复。
- **分支政策**：经充分验证零风险/边界清晰改进可**直接合并** unsafe-vibe-dev；大风险仍"独立分支 + 手动 cherry-pick"；永远不触碰 main。
- **剩余长期项**：PT-DEBT-4 `file` 重命名（独立窗口）、P3 VISION、PT-DEBT-24、F9（已评估）、
  PT-AUDIT-3 疑似项 S1-S5（独立窗口）、**PT-DEBT-25~28（2026-08-12 试用发现，独立窗口）**。
- **当前主线（架构健康性优先，用户 2026-08-08 定案）**：**异步地基遗留妥协根治（统一执行模型闭环）——全部收尾（2026-08-09）**。
  审计确认内核层仍有"任务内同步重入调度器"遗留旁路（用户方法 `obj.method()` / `slot.update(fn)` / prompt hint /
  `chan.send` 满阻塞）。**PT-DEBT-12（F1 用户方法 CPS 化）、PT-DEBT-13（B1 chan.send Waitable 化）、
  PT-DEBT-14（F2 slot.update + F3 prompt hint CPS 化）、PT-DEBT-15（M4 LLM 真挂起）已完成（2026-08-08）**；
  **M1（.call 双写收敛）/ M2（驱动去重）已完成（2026-08-09，独立分支 exp/async-m1m2，全量 2137 passed / 1 skipped）**；
  M3（prompt 单源）已确认收敛。**统一执行模型闭环全部收尾**。实施计划与落地状态见 `（已清理任务文档）`（F1→B1→F2/F3→M1-M4）。
  登记 PT-DEBT-12/13/14/15。
  > **注意**：地基闭环后仍有 6 处"任务内同步重入/嵌套调度器"**次要路径遗留**（`_HEALTH_AUDIT_PLAN.md` 异步 A1-A6）——
  > 内联 `@~` 表达式、意图消解、`_SlotUpdateWaitable`、LLM 函数同步阻塞、类构造、协议方法。属"彻底统一"的未完项。
 - **优先级总表（用户 2026-08-08 认可，三维度判断）**：见 `PENDING_TASKS.md` §〇（单一权威源）。
   当前主线后：**P0 阶段 5 增量已完成（2026-08-09）→ PT-FEAT-5 三项已完成（CI/CD 待授权）→
   P1 PT-FEAT-10 已完成 → P2 R4/R5 审计已执行 → 异步地基 M1/M2 已完成（2026-08-09）**；
   剩余 PT-DEBT-4 `file` 重命名（破坏性变更独立窗口）、P3 VISION。
 - **低风险推进已完成（2026-08-09）**：PENDING_REVIEW_ITEMS 状态同步、PT-AUDIT-2 宽 except 核验（A 类保留）、
   docs/ 过时表述修复（yield 已落地）。见 HANDOFF §2.1。
 - **三轴健康盘点（2026-08-09，只读）**：见 `（已清理任务文档）`——异步遗留 A1-A6 + 内核健康
   （深层嵌套/死同步包装/双驱动循环）+ 技术手册健康（P1/P2 待修 + How-to 缺口）。
 - **P0 阶段 5 增量已完成（2026-08-09）**：见上方"已完成"节。`next()` + `yield from` 全落地，设计记录
   `（已清理任务文档）`。
 - **PT-FEAT-5 已完成三项（2026-08-09）**：见上方"已完成"节（诊断码目录 + 符号表/类型绑定导出 + 编译基准）。
   剩余：CI/CD（涉远程 push，须用户显式授权后另行执行；见 `PENDING_TASKS.md`）。
 - **P1 PT-FEAT-10 UID 生成统一已完成（2026-08-09）**：见上方"已完成"节。
 - **P2 审计 R4/R5 已执行（2026-08-09）**：R4 覆盖率核对（12 项，2 处 TRUE_GAP 补测）+ R5 聚焦治理
   （session 改动文档核验）。PT-FEAT-11/12、PT-FEAT-2 均评估为维持现状（见 `PENDING_TASKS.md`）。
- **阶段 5 yield 惰性生成器已完成（2026-08-08）**：见上方"已完成"节。`YIELD_GENERATOR_DESIGN.md`。
- **PT-FEAT-9 阶段 4 已完成（2026-08-07，unsafe-vibe-dev，全量 2021 passed / 1 skipped）**：
  kernel_diagnostic helper（单一记录双投影：警告不门控 + 事件受 observability 门控，rc best-effort）+
  12 处站点迁移（文案逐字）+ e2e 事件投影测试 + `docs/architecture/09_observability.md`。
  详见上方"已完成"节与 `WORKLOG`。
- **R 批次全部完成（2026-08-07，unsafe-vibe-dev，全量 2001 passed / 1 skipped）**：
  - R4+R3（82c9c0f，1988/1）：P3 公开协议（`IbCell.mark_shared_with_main()`）+ D-04 意图修复（`IbThread` 本体满足
    Waitable：`is_done` 改 property、auto-bind 支持 property-backed 方法、`try_result`/`result`、`join()` 返回自身、
    `await t` 可用、语言 `t.is_done()` 保留）+ 修复 auto-yield 缺口（类构造返回 Waitable 不自动挂起）+
    编译期 `await thread[T]`→`thread_result[T]`。
  - R6（35f1437，1995/1）：嵌套函数自动只读捕获（与 lambda 同构，`nonlocal` 仅用于写）；真闭包只读捕获可用；
    P3 写共享 cell 拦截保持。
  - R2（c16b05e/c4c63aa，1998/1）：调度器通知式唤醒（Waitable `register_wake` + `_wake_event` + CommBuffer 回调表 +
    engine `register_spawn_wake`）；根治 poll+park 与"单待决阻塞"。
  - R1（6dc9214，2001/1）：函数调用 trampoline 化（`_vm_call_user_function` CPS + `_UserFunctionCall` 压栈）；
    EXEC-1 根治，深递归 Python 深度恒定（n=5000 深度恒 13，原 ~130 层栈溢出）。
- **2026-08-08 批次已完成（unsafe-vibe-dev，全量 2026 passed / 1 skipped）**：
  穿透根治（d11bad0，事件总线/诊断发射器依赖注入）+ 死代码清理（ffaffc0，删 registry.clone()）+
  文档对账治理（fe80595/5f5e26d/a8de1b1/3368c28，P0/P1/P2 全修复）+ 意图栈历史兼容移除（3ce9b7d）+
  登记 PT-FEAT-10/11/12。详见上方"已完成：2026-08-08 批次"节。
- **阶段 1/3 已完成（2026-08-07，unsafe-vibe-dev）**：地基 1a-1e（调度器执行核心/Waitable 家族/阻塞即挂起/
  协作取消/llmexcept×await/取消覆盖用户函数）+ 统一清理 W1-W5/P3/P4（命名/订阅契约/comm 命名回归/死状态/
  文档/cell 隔离/全局事件总线），全量 **1984 passed / 1 skipped**。
- **已完成（OBSERVABILITY_REFACTOR 主体）**：2C-2 idbg 深度收敛 + 用户层机制改造、2D 测试体系全面重建
  （tests_v2 全域迁移 + 切换 + 矩阵三段式 + tests_docs 治理）、测试规范化清理（弱断言升级 + 短簇参数化），
  全量 **1963 passed / 1 skipped**。
- **本 session 已完成（2026-08-06，unsafe-vibe-dev，11 commits）**：Phase 0 设计冻结、Phase 1 契约修复+死码+零成本穿透替换、
  **2A CORE_DEBUG 整体移除**（88 trace → warnings 8 处/删除，commit 6878986）、**2B 观测骨架测试合作面**
  （EngineTestSnapshot + test_hooks + resolve_plugin_search_paths 公开 + layering 豁免归零，commit 73f373d/ae2209e/feff694）、
  **2C idbg 适配**（删死代码 + show_intents 单一权威源 + fields 协议化，commit 8a0065c）。全量 pytest **1633 passed / 4 skipped**。
- **已完成**：PT-DEBT-7（删 is_nullable 死字段）、PT-DEBT-8（值层分派收敛，重定义原折叠目标）、
  PT-DEBT-6（register_module 可观测性）、PT-DOC-2（定位段收尾）、DOC_AUDIT 文档治理（F0-F4）、
  PT-INTRO-1/PT-DECIDE-1/PT-DEBT-1/2/3、内建函数群完善+遮蔽——详见 `PENDING_TASKS.md` 与 git 历史。
- **待办池**：完整清单见 `PENDING_TASKS.md`。

---

## ✅ 已完成交付

> 全部落地 unsafe-vibe-dev（本地 commit，未 push）。commit 明细见 git 历史。

- **PT-DEBT-7/8 + PT-DEBT-6 + PT-DOC-2（2026-08-06）**：
  - PT-DEBT-7：删 `TypeDef.is_nullable` 死字段（可空性早已由 `Optional[T].wrapped_type` 承载，序列化不消费）。
  - PT-DEBT-8：系统层面重定义"折叠 IbXxx→IbValue"为伪目标（消 isinstance 动机已由 name 分派达成）→
    值层分派收敛审计：`is_sequence_value` 统一容器分派、`IbLLMCallResult.is_uncertain` 统一不确定判断；
    类角色分工固化 `03_type_system.md` §6.4。
  - PT-DEBT-6：`register_module` 用户插件覆盖 kernel-native 时发 warning（原静默忽略）；修正测试配置 bug。
  - PT-DOC-2：14 篇 syntax 定位段核实完成（DOC_AUDIT F3 已补齐），条目移除。
- **DOC_AUDIT 文档治理（2026-08-06）**：docs/ 全量治理（42 篇）分四阶段执行——F0 本批引入修复（KNOWN_LIMITS §二十二重复编号→§二十四、14_concurrency E9、E2 历史叙述）；F1 P0 断链/矛盾 ~17+ 处（以代码为最高真相）；F2 P1 红线批量（日期戳/历史叙述/冻结数字/任务代号清除、KNOWN_LIMITS 章节重排为一~二十二并同步跨文档引用、05_coroutine 任务日志迁 （已清理任务文档）、__prompt__ 待决项迁 （已清理任务文档））；F3 P2 改善（模板统一 13_mock_testing/04_control_flow、A5 去重、侧表/MetadataStore 事实修正、handler 数 43→45）；F4 体系（How-to 层 docs/howto/ 两篇、'深入指引'尾段 23 篇补齐）。**后续清理**：删除自治标注文档 appendix_type_system_rationale.md 与 backup/（未完成规划迁 PENDING_TASKS PT-FEAT-8/PT-DEBT-7/8，media 设计浓缩为 （已清理任务文档））。完整记录见 `（已清理任务文档）`。
- **整合巩固批次（2026-08-06）**：新写 `docs/syntax/14_concurrency.md`（并发语言面，此前缺失）+ KNOWN_LIMITS §二十二（signal 移除）；修复 PT-DEBT-1 文档漂移（`_ibci_registry_id` 残留）；修复 for 循环变量类型恒为 any 缺陷（复合赋值在 for 体内无法定型）；for...if + 复合赋值 e2e 覆盖（PT-TEST-2）。
- **内建函数群完善（2026-08-06）**：类型转换全局函数 `int()`/`str()`/`float()`/`bool()` +
  序列辅助 `enumerate`/`zip`/`sorted`/`reversed`/`sum`/`all`/`min`/`max`；级联修复 for 循环
  元组解包 `for (int x, int y) in`；内建函数名可被用户变量声明遮蔽（`int len = 5`），
  内建类型名与对内建的直接赋值仍禁。`any` 因与动态类型名冲突未纳入。
- **PT-DEBT-1/2/3 内核接口协议化（2026-08-06）**：
  - PT-DEBT-1：`BoundPlugin` 容器替代 `_ibci_registry_id` 私有标记注入；加载期跨引擎
    单例守卫改用 process 级 weak map（安全语义保留）。
  - PT-DEBT-2：`snapshot.py` 改走公开访问器；LLMExecutor 补 `pending_futures_count()`。
  - PT-DEBT-3：RuntimeContextImpl 补 `get_comm_*`/`peek_*`/`get_runtime_coordinator`
    访问器，统一替换 core 与 iruntime 插件的私有槽直接访问。
- **PT-DECIDE-1 裁定落地（2026-08-06）**：行为输出具体类型必须可解析——编译期
  `SEM_BEHAVIOR_OUTPUT_NOT_PARSEABLE` + 运行时 Default 兜底（见 `PENDING_TASKS.md` §二）。
- **PT-INTRO-1 运行时内省体系（2026-08-06）**：
  - `type(f)` 对 fn_callable/behavior 返回含签名类型名（`fn_callable[()->int]` /
    `behavior[(int,str)->bool]`）；其余值仍返回规范名。
  - `f.__return_type__()` 返回类型查询 API（receive 消息 + vtable 原生方法）。
  - 签名在运行时值创建时经 node_to_type 捕获、自持于值，序列化 round-trip 保真；
    lambda 参数节点类型绑定补全（编译期 bind_type）。

- **闭包序列化 + fn_callable round-trip 修复**：作用域 cell 重建 + 按 sym_uid 重链共享；
  value_meta/expected_type JSON 安全。
- **Axiom 家族分裂收敛**：IntentAxiom/IntentContextAxiom 并入 BaseAxiom。
- **EnumAxiom 双通道收敛**：str 契约 + fail-fast。
- **use_intent_context 守卫修复**：删恒真守卫 + 可读错误。
- **R3 异味四 Zone 处置**：修 19 + 复核定案保留 10 + 设计确认保留 6。
- **import-* 精确成员枚举根治**：编译器记录 + 运行时枚举；**IBC 文件跨模块导入三层断裂修复**
  （TypeDef 别名 NameError / Lazy 描述符 members 恒空 / IbModule.get_variable）。
- **`type()` 内建落地**：运行时内省第一项。
- **任务控制文档全面重整**：任务代号按性质分域（FEAT/DEBT/AUDIT/DOC/TEST/DECIDE/SEALED），
  删除已完成/无价值条目与无用设计决策，清理注释任务代号/历史说明。
- **周期清扫启动**：文档清洗与梳理、注释卫生清理、代码复核审查（R1/R2/R3）均已执行，
  周期复核。

---

## ⛔ 工作模式定论（强制，凌驾于本文件一切任务之上）

> **扎实推进，禁止任何形式的快速实现 / 兼容层 / 胶水实现 / tricky 实现。**

1. 禁止 compat shim / 兼容层：新设计就是真设计，旧代码要么真合并、要么真删除。
2. 禁止胶水实现：不在两个不统一的子系统之间塞字符串拼接 / 魔法哨兵 / 隐式约定。
3. 禁止 tricky 实现：不靠隐式字符串变换承载语义；不靠"凑巧相等"；不靠书写顺序掩盖数据依赖。
4. 禁止过程式硬编码分发：同一决策只通过协议驱动（`receive()` / vtable），不写 `if 能力标志位`。
5. 质量优先于速度：技术债必须先清；潜伏 bug 不允许过渡修复。
6. 原则优先于行为维持：既有行为违反一般工程/架构原则时，以原则为准，不以"保持已有行为"为主。
7. 可推翻 IBCI 自身设计缺陷：即使设计思路已在文档记录，也可按更普适、实践更合理的方案重建。
8. 破坏性重构授权：符合一般工程经验且经分析优于现有体系时默认已授权自主推进，详记决策。
9. 大范围破坏性重构分支政策：无法确认边界/危害程度的重构 100% 授权在独立分支实验；
   独立分支禁止直接合并到 unsafe-vibe-dev 或 main；永远不触碰 main。

---

## 当前测试基线

```bash
conda activate ibci
python -m pytest tests/
```

> 基线以实跑为准，不冻结数字。

---

## 独立并行任务

- **测试体系重构**：PT-TEST-1（`TEST_REFACTOR.md`），独立低优先级。
- **技术债审计**：PT-AUDIT-1/2（`CODE_SMELL_AUDIT.md` / `BRANCH_NESTING_AUDIT.md`），独立分支执行。
- **media Phase 4**：PT-SEALED-1，彻底封存（恢复需显式解封）。

---

## 工作规则

- 每次开新分支前，先复跑 `python -m pytest tests/`，把 pass/fail 计数写在 PR 描述里。
- 同一时刻只主推一个 P0 阶段。
- 工作模式定论优先；改动公理层或语义错误集的任务需全量 pytest 评估破坏面。
- 每阶段完成后用描述性 commit 记录，并把对应条目从本文件移除。
- 本文件不冻结具体测试通过数字。
- 重大架构决策记录在技术文档（`docs/ARCHITECTURE.md`、`docs/architecture/02_metadata_ast.md`、
  `docs/architecture/01_principles.md`），不再使用独立 ADR 文件。
