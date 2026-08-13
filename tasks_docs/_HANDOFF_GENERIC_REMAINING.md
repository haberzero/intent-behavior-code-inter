# 交接：泛型体系剩余边界——彻底修复可能性分析（下一 session 任务）

> 2026-08-13 编制。用户裁定：下列 7 项全部纳入下一轮检查范围，**考虑彻底修复的可能性**。
> 本文件交接每项的现状 / 根因 / 根治方向 / 工作量 / 风险评估。设计权威承接：
> `_code_generic_type_identity.md` + `_code_generic_value_convergence.md`。
> 当前基线：unsafe-vibe-dev HEAD d797e418，全量 2586 passed / 1 skipped。
>
> **✅ 已根治（2026-08-13，`_TYPE_SYSTEM_REBUILD.md` v2 桩1-3 + S6 + 遗留边界彻底修复）**：本清单 7 项全部收敛——桩1 创建点结构化 TypeRef（#3 generator 嵌套扁平化根治）、桩2 get_base_name 单义 + 句柄类物化（#1/#7 值身份）、桩3 声明驱动（#2 type_pool 匹配 + 序列化结构保真）、S6 元组解包检查（#4）+ 容器字面量带实参推断（#5 -> auto 已覆盖）、**S5 跨模块同名类 module 化根治（e849f36d）**、**#6 *expr 元素级校验（e849f36d）**。明细见 `_TYPE_SYSTEM_REBUILD_PLAN.md` + WORKLOG。

---

## 〇、交接清单总览

| # | 项 | 严重性 | 根治可能 | 层 |
|---|----|--------|---------|----|
| 1 | 句柄类值身份未水化（thread/chan/slot/generator/thread_result） | P3 边界 | **高（机制同构已备）** | 运行时 |
| 2 | `_rehydrate_type_pool_spec` 按 name 匹配（跨引擎多模块同名） | P3 理论 | 中（module 限定） | 运行时 |
| 3 | generator value_type 嵌套扁平化 + `_slice_type_objs_for` 残缺实参 | P3 兜底 | 中（结构化构造） | 内核/运行时 |
| 4 | 元组解包错误类型不检查（`["x"]` 赋 `list[int]`） | P3 语言缺口 | 高（按位置校验） | 编译期 |
| 5 | `-> auto` 泛型实参推断（auto 语义不保留实参） | P3 边界 | 中（推断增强） | 编译期 |
| 6 | `*expr` 展开实参静态不可绑定 | P3 根本限制 | 部分（元素级推断） | 编译期 |
| 7 | 句柄类值身份未水化（编译期已封闭确认） | —— | 同 #1 | 运行时 |

> 注：#7 与 #1 同根因（句柄类运行时值用裸基类），合并处理。

---

## 一、句柄类值身份未水化（#1/#7，根治可能高）

### 现状
`thread[int]`/`chan[int]`/`slot[int]`/`generator[int]`/`thread_result[int]` 值
`type()` 返回裸名（`thread`/`chan`/`slot`/`generator`/`thread_result`）。编译期
类型检查已封闭（实测 `generator[int] g = gen_str()` 编译期 SEM_TYPE_MISMATCH）。

### 根因（代码实证）
值创建点全部用裸基类：
- `core/runtime/vm/handlers/comm.py:43/60`——chan/slot 构造用 `get_class("chan"/"slot")`
- `core/runtime/vm/handlers/leaf.py:373/394` + `user_functions.py:66` + `ib_class.py:118`
  ——generator 创建用 `get_class("generator")`
- `core/runtime/objects/thread.py:157`——join 结果用 `get_class("thread_result")`

`_hydrate_builtin_generic_classes`（artifact_loader.py）只水化 LIST/TUPLE/DICT/OPTIONAL
特化类，未覆盖 THREAD/THREAD_RESULT/CHANNEL/SLOT/GENERATOR。

### 根治方向（机制同构，改动点已明确）
1. **`_hydrate_builtin_generic_classes` 扩 kind**：加 THREAD/THREAD_RESULT/CHANNEL/
   SLOT/GENERATOR → loader 期预水化特化类（`thread[int]` parent=基类 thread）。
2. **值创建点绑特化类**：
   - thread 构造（`primitive_initializer._thread_init`）用 `get_class("thread[int]")`
     ——但构造时无声明类型上下文，需从构造表达式 `thread(callable=...)` 的
     `node_to_type` 拿（或运行时 `_check_type` 升级）。
   - generator 创建（`make_generator_driver`）同理。
   - chan/slot 构造、thread join 返回同理。
3. **运行时 `_check_type` 升级**：值绑基类、声明特化时，把值对象 rebind 到特化类
   （与容器 `_bind_container_specialization` 同构，但句柄类无字面量节点，需走声明
   类型上下文）。

### 工作量/风险
- 改动点 5-7 处（loader + 4 类值创建 + 运行时升级），机制同构已备（容器水化先例）。
- **关键难点**：句柄类值**创建点无字面量节点**（构造表达式/函数返回），类型上下文
  获取不同于容器（容器有 node_to_type，句柄靠 `_check_type` 绑定点升级）。需设计
  "值对象 rebind 特化类"的运行时机制（容器已实现，可复用模式）。
- 收益：`type()` 内省一致（与用户类泛型 `Box[int]` 对齐）。
- 风险：中。句柄类有生命周期语义（thread 状态机/chan 缓冲），rebind ib_class 须验证
  不破坏方法查找（`_impl_cls` 沿 base 名解析已备）。

---

## 二、`_rehydrate_type_pool_spec` 按 name 匹配（#2，根治可能中）

### 现状
跨引擎反序列化时 `_rehydrate_type_pool_spec` 用 `next((u for u, d in type_pool.items() if d.get("name") == cls_name))`——**按 name 而非 module+name 匹配**。多模块同名特化才可能选错。

### 根因
`runtime_serializer.py` 的 `_hydrate_specialized_class` → `_rehydrate_type_pool_spec`。

### 根治方向
- 序列化端 `_collect_instance` 已存 `class_name`（`obj.ib_class.name`），可**补充
  `class_module`**（`obj.ib_class.spec.module_path`），反序列化端按 `(module, name)`
  匹配 type_pool。
- 或反序列化端从 type_pool 的 `module_path` 字段 + name 联合匹配。

### 工作量/风险
- 低（2 处字段 + 1 处匹配逻辑）。
- 收益：消除多模块同名理论误选。
- 风险：极低。**注意**：内置泛型无 module 限定（module_path=None），用户类特化跨模块
  同名罕见——实际触发面小，但修复成本低，值得做。

---

## 三、generator value_type 嵌套扁平化 + `_slice_type_objs_for` 残缺实参（#3，根治可能中）

### 现状
- `generator[list[int]]` 的 `value_type = TypeRef('list[int]', args=())`（head 含方括号
  扁平，非递归结构化）。
- `_slice_type_objs_for`（leaf.py）嵌套实参类未水化时静默跳过，可能构造残缺特化名。

### 根因
- `factory.create_generator(value_type_name=...)` 接受 **name 字符串**，内部
  `TypeRef.of(value_type_name)` 扁平化。thread/chan/slot/thread_result 同理（
  `generic.py` `_build_*` 用 arg_names 字符串）。
- `_slice_type_objs_for` 对 `node_spec.element_type`（可能是扁平 `list[int]`）取
  `ref.head` → `get_class("list[int]")`，若未水化则 None → 跳过。

### 根治方向
1. **value-bearing 泛型结构化构造**：`create_generator/thread/chan/slot/thread_result`
   支持结构化 TypeRef（`TypeRef.generic` 递归），`from_spec` 时反构嵌套 args
   （`TypeRef.from_spec` 已有 GENERATOR 分支，但依赖 `value_type` 结构化）。
2. **`_slice_type_objs_for` 健壮化**：任一实参解析失败时整个 fallback 返回 None
   （值保持基类），而非残缺实参构造。

### 工作量/风险
- 中（内核 factory 多处 + 运行时 helper）。
- 收益：嵌套 `generator[list[list[int]]]` 跨引擎保真；消除残缺特化兜底。
- 风险：中。`create_*` 签名改动可能影响现有调用方（`generic.py` `_build_*`、
  `_declaration_visitors` generator 修复、rehydrator）——需全量核对。

---

## 四、元组解包错误类型不检查（#4，根治可能高）

### 现状
`list[int] a, list[str] b = ["x"], [1]` 编译通过（`["x"]` 赋 `list[int]` 未拦截），
运行时 `["x"]` 静默流入。

### 根因
`_statement_visitors._handle_assign_target` 的 IbTuple 解包分支（`:195-198`）各元素
用 `_any_desc`（不做类型检查）。值层身份已收敛（B1 修复），但**类型检查**仍缺失。

### 根治方向
IbTuple 解包分支：按位置解析各元素声明类型（`elt` 若 `IbTypeAnnotatedExpr` 取
annotation），对 RHS 对应元素做 `is_assignable` 校验（与简单变量赋值 `:144` 同构）。
RHS 非元组字面量（变量/函数返回）时，逐个元素校验（解包后的元素类型来自 RHS 的
`positional_element_types` 或运行时）。

### 工作量/风险
- 中（编译期 1 处分支扩展 + 判别性回归）。
- 收益：元组解包类型安全闭环（消除静默类型混淆）。
- 风险：中。元组解包有多种形态（字面量/变量/函数返回/嵌套解包），需逐一核对
  不误报（如解包 `any` 变量、`tuple[int,str]` 特化变量）。

---

## 五、`-> auto` 泛型实参推断（#5，根治可能中）

### 现状
`func f() -> auto: return [1,2]` 推断返回类型为裸 `list`（非 `list[int]`），
`list[int] r = f()` 值擦除为裸 list。

### 根因
`_declaration_visitors.py:165-186` auto 推断收集 `visit_IbReturn` 的 `ret_type`
（`self.visit(node.value)` 返回字面量**推断的裸类型**）。`visit_IbListExpr` 返回裸
`list`（无实参推断）。

### 根治方向
1. **容器字面量自身推断带实参**：`visit_IbListExpr/IbDict/IbTuple` 对元素做类型
   联合推断（`[1,2]` → `list[int]`；`[1,"a"]` → `list` 或 `list[any]` 按既有语义）。
   这是**类型推断增强**，会影响 auto 函数/auto 变量的推断精度。
2. **或 auto 推断后回溯**：auto 返回类型推断出裸 `list` 后，若函数体 return 的是
   容器字面量，回溯其元素类型（改动面小但需二次遍历）。

### 工作量/风险
- 中（编译期字面量推断 + auto 路径）。
- 收益：`-> auto` 泛型语义完整；auto 变量/函数容器类型精确。
- 风险：中。`list[int]` 联合推断可能改变现有 auto 行为（如 `auto x = [1,"a"]`
  现为裸 list，推断后可能 `list[any]`）——需全量测试评估。

---

## 六、`*expr` 展开实参（#6，根治可能部分）

### 现状
`f(*lst)` 静态数量未知，`*expr` 展开实参无法静态绑定字面量到形参。

### 根因
`_expression_visitors.py:358-362` `starred_specs` 只收集 `visit(arg.value)` 的类型，
`*lst` 展开后数量/位置运行时才知。

### 根治方向（部分）
- `*expr` 若展开源是**容器字面量/定型容器**，其元素类型已知（`resolve_iter_element`），
  可对展开源字面量绑定元素类型（值层身份保真），但**形参类型校验**仍需运行时
  （展开后逐个校验）。
- 静态绑定字面量到形参（`f([1,2])` 形参 `list[str]`）在 `*` 混合实参下无法精确
  （位置偏移未知）——**根本限制**，仅可缓解元素级身份。

### 工作量/风险
- 低-中（运行时展开校验 + 元素级绑定）。
- 收益：`*expr` 容器元素值身份保真（非形参校验闭环）。
- 风险：低。完全校验（编译期拦截 `f(*[1], 2)` 类型错）不可行（静态限制），仅
  值层身份缓解。

---

## 七、建议处理顺序（按根治可能 × 风险）

1. **#2 `_rehydrate_type_pool_spec` module 匹配**（低风险低成本，先做）
2. **#4 元组解包类型检查**（根治可能高，收益明确）
3. **#1/#7 句柄类值身份水化**（机制同构已备，需设计值 rebind 机制）
4. **#3 generator value_type 结构化 + `_slice_type_objs_for` 健壮化**
5. **#5 auto 泛型实参推断**（类型推断增强，需评估行为影响）
6. **#6 `*expr` 部分缓解**（元素级值身份）

## 八、验证与纪律

- 每项修复：判别性回归 + 全量 pytest 零回归（`~/miniconda3/envs/ibci/bin/python -m pytest tests/`；
  仅在必要时全量，其余定向）。
- 走 code-workflow Phase 0-5 + code-review 复核；破坏性重构默认已授权（用户裁定）。
- 分支政策：无法确认边界走独立分支；确认零风险可直接合并 unsafe-vibe-dev；不触碰 main。
- 全程本地 commit、禁 push。
- WORKLOG 详尽记录决策与变化前后。
