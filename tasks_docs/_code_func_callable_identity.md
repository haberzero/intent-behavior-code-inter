# 设计/实施记录：函数/可调用类型身份架构断层根治

> 2026-08-14 编制。承接 `_HANDOFF_TYPE_IDENTITY_FAULT_LINE.md`（逐环实证根因 + 修复方向）
> 与本 session 深化分析（实证复核 + 扩散面扫描 + 方案验证）。独立分支
> `exp/func-callable-identity` 实验，确认零风险后更新 unsafe-vibe-dev。

## 〇、交接结论（复核确认）

三个问题全部实证复现（探针 q1_bound/q2_fnret/q3_optchain/q8_lambda_optret），根因与交接
文档一致，且深挖出更精确的机制与扩散面：

1. **问题 1（绑定方法）**：`resolve_member`（`_members.py:43-50`）无条件 FUNCTION kind、
   name=attr_name → `callable f = a.calc` 编译期 SEM_TYPE_MISMATCH。BoundMethodAxiom
   （bound_method IS-A callable）编译期从未接线。
2. **问题 2（函数符号回填签名丢失）**：type_checking `visit_IbFunctionDef` 用 create_func
   `.name` 字符串重建 spec，**覆盖了 symbol_collection 已产出的结构化 spec**。
   `-> fn[(int,str)->int]` 退化为裸 fn（CALLABLE_SIG name="fn" 不含签名，注册表无法
   名称回绕，故彻底失效）；`-> list[int]`/`-> Optional[int]` 因 canonical-name 回绕仍可用。
3. **问题 3（返回 Optional 包装缺失）**：`vm_handle_IbReturn` 原样返回 + 三个函数调用
   消费点（`_vm_call_user_function`/`_vm_call_fn_callable`/`_vm_invoke_llm_function`）
   提取 Signal.value 不做 wrap_optional → 跳过 define_variable 包装路径的直接消费
   （链式/type()/传参）得到裸 int。

## 一、根因（三层系统性断层）

> 用户猜想"fn 设计早于泛型体系存在历史包袱"**完全证实**，且比交接文档更进一步：
> 断层是三层系统性的，不是 create_func 单点。

1. **spec→TypeRef 转换无单一权威**：`TypeRef.from_spec` 未覆盖 FUNCTION/BOUND_METHOD/
   CALLABLE_SIG 三种 kind → 现存 3 个部分实现：
   - `scheduler._spec_to_typeref`（FUNCTION/BOUND_METHOD → `fn[(args)->ret]`）
   - `_declaration_visitors._param_type_ref`（CALLABLE_SIG 特殊 + from_spec）
   - `TypeRef.from_spec`（其余）
2. **编译期回填用字符串覆盖好 spec**：symbol_collection 的 `_annotation_to_typeref`
   已产出结构化 return_type/param_types，type_checking 回填（create_func `.name` 字符串）
   把结构化 spec 扁平化。
3. **序列化侧字符串级**：CALLABLE_SIG 持久化用 `.head` 字符串（`serializer.py:202-205` /
   `rehydrator.py:127-128`）。

## 二、修复方案（按序）

### A. `TypeRef.from_spec` 补全（单一权威源核心）
补三个 kind 分支：
- **CALLABLE_SIG** → `TypeRef('fn', (TypeRef('__args__', params), ret))`，params/ret 递归
  结构化（保留嵌套泛型，如 `fn[(list[int])->int]`）。
- **FUNCTION** → `TypeRef('fn', (TypeRef('__args__', params), ret))`（同构于
  `scheduler._spec_to_typeref` 的 FUNCTION 分支；仅当函数 spec 自身作"被返回的可调用"
  时消费）。
- **BOUND_METHOD** → `TypeRef('bound_method', ())` 或 `fn[(args)->ret]`？——决策：
  BOUND_METHOD 语义是"已绑定 receiver 的可调用"，其签名（不含 self）应保真。
  与 FUNCTION 同构产 `fn[(args)->ret]`（head="fn"），与 `_matches_callable_sig`
  对 BOUND_METHOD 读 return_type/param_types 的消费一致。
- 收敛 `scheduler._spec_to_typeref` 与 `_param_type_ref` 到 from_spec（或 from_spec
  委托它们的既有逻辑），消除双通道。

### B. `create_func` 升级
签名升级为接受结构化 `return_type: Optional[TypeRef]` + `param_types: Optional[List[TypeRef]]`
（保留字符串参数向后兼容——bootstrap/prelude 16+ 调用点均为简单名，`TypeRef.parse`/
`TypeRef.of` 转换即可）。
4 个编译期回填点（`_declaration_visitors` 函数/LLM 函数 + `symbol_collection` 函数/LLM
函数）传 `TypeRef.from_spec(resolved_spec)` 结构化 ref。

### C. `resolve_member` 产出 BOUND_METHOD
- **CLASS 实例方法**（spec.kind==CLASS）：产出 BOUND_METHOD kind，name="bound_method"，
  携带 `return_type=effective_return` + `param_types=effective_params`（member.param_types
  不含 self——symbol_collection 构造，已实证）+ `receiver_type`（spec 自身）+ 保留
  param_descriptors。
- **MODULE 函数**（spec.kind==MODULE）：保持 FUNCTION（模块函数无 receiver）。
- 容器 axiom 方法（list.append 等）：spec.kind 为 LIST/DICT 等 → 产出 BOUND_METHOD。
  与 CLASS 分支同路（实例方法语义正确）。
- 扩散面审计：
  - `_expression_visitors.visit_IbAttribute:811/816` 已含 BOUND_METHOD kind ✓
  - `_inference.resolve_call_return` Layer 4 已处理 BOUND_METHOD ✓
  - `_inference.resolve_callable_instance_return:203` kind 检查（FUNCTION/CALLABLE_SIG）
    **须补 BOUND_METHOD**（class_scope_lookup 走 owned_scope 返回 FUNCTION 不受影响，
    但 resolve_member fallback 路径受影响）
  - `_assignability._matches_callable_sig` 已处理 BOUND_METHOD（读 return_type/param_types）✓
  - `_capabilities.get_call_cap/is_callable` 已含 BOUND_METHOD ✓
  - 运行时 `_check_type`（runtime_context.py:84-91）已放行 BOUND_METHOD→可调用槽 ✓
  - `contract_validator.py:58` resolve_member 消费：检查其对 kind 的使用（只比对签名，
    不受 kind 影响）
- 实证（registry 直测）：BOUND_METHOD+签名 → callable 槽放行 / fn[(int)->int] 槽放行 /
  fn_callable[int] 槽正确拒绝（bound 非零参）/ resolve_call_return Layer 4 正常 /
  axiom 路由 BoundMethodAxiom。

### D. 函数返回值 Optional 包装
新增单一 helper（如 `_wrap_return_value(executor, func, value)`），按
`func.spec.return_type` resolve 为 spec 后 `wrap_optional`（幂等安全——赋值路径
define 包装后值再经本 helper 不重复包装）。三个消费点统一调用：
- `_vm_call_user_function`（RETURN Signal 提取后）
- `_vm_call_fn_callable`（RETURN Signal 提取后）
- `_vm_invoke_llm_function`（invoke_llm_function_cps 结果）——LLM 函数返回经
  `_parse_result`（type_name 字符串路径），需核验是否需同包装；若 LLM 返回解析
  已按目标类型 box 则只需 Optional 目标时补 wrap。

### E. CALLABLE_SIG 序列化保真
`serializer.py:202-205` 持久化改 `canonical_name`（嵌套保真）；`rehydrator.py:127-128`
改 `TypeRef.parse` 恢复。BOUND_METHOD 序列化侧（若 spec 落 artifact）签名保真。

## 三、判别性回归

每项含编译期 + 运行期 + type() 类型身份断言：
- q1：`callable f = a.calc` 编译放行 + `fn f = a.calc` 运行 + `fn[(int)->int] f = a.calc` 放行 + `f(5)` 正确
- q2：`-> fn[(int,str)->int]` 返回放行 + `fn[(int,str)->int] f = make()` + `f(1,"a")` 正确 + 签名不匹配编译期拦截
- q3/q8：`maybe(5).unwrap()` 链式 + lambda Optional 返回 + `type(maybe(5))` 身份
- 连带：`-> list[int]`/`-> Optional[int]` 返回在"未赋值直接消费"路径（`type(make())`、`make()[0]`、`make().unwrap()`）
- 反转 `tests/e2e/test_return_type_validation.py TestBoundMethodReturn` 旧预期（
  `-> callable: return a.calc` 从 SEM 拦截 → 放行）

## 四、执行纪律

- 独立分支 `exp/func-callable-identity`；全程本地 commit、禁 push、不触碰 main。
- 每步全量 pytest 零回归；完成后独立复核（general agent）+ 残留扫描。
- 确认零风险后手动更新 unsafe-vibe-dev；大风险则保留独立分支并上报。
- WORKLOG 详尽记录变化前后。
