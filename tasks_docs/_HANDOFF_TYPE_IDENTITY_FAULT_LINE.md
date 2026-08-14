# 交接：函数/可调用类型身份架构断层——三个深层次缺陷的根因与修复方向

> 2026-08-14 编制。用户 2026-08-14 指令：将三个未修复问题提高优先级，深挖可能存在的
> 深层次架构级严重问题，交接下一 session 进一步深挖和修复。
> 用户猜想（2026-08-14）：**fn 设计时泛型体系尚未完善，可能留下历史包袱与妥协性逻辑；
> 泛型地基打好前 IBCI 已实现很多基本功能，很多基本建模可能存在类似的深层次缺陷。**

## 〇、交接结论（先行）

用户猜想**已证实**。三个"表面孤立"的问题经深挖后确认指向**同一架构断层**：

> **编译期/运行期的"类型身份"在函数与可调用类型的关键路径上被扁平化/丢失。**
> 根因是 `fn`/`callable` 函数签名建模基于**早期"字符串级 TypeRef"设计**，
> 泛型地基（TypeRef 结构化 + CALLABLE_SIG + CALLABLE_INSTANCE kind）落地后，
> 核心回填 API（`factory.create_func`）与成员解析（`resolve_member`）**未同步升级**，
> 形成"结构化注解 → 字符串扁平化 → 运行时类型身份丢失"的架构断层。

**这是架构级缺陷，非功能漏洞**。三个问题只是同一断层的不同表现。

---

## 一、三个问题的根因（全部经代码级实证）

### 问题 1：绑定方法建模缺陷（原 F2，`a.calc` → callable 被拒）

- **现象**：`-> callable: return a.calc` 编译期 SEM_TYPE_MISMATCH；`callable f = a.calc` 同样被拒。
- **根因**：`core/kernel/spec/registry/_members.py:43-50` `resolve_member` 对方法成员
  **无条件建模为 `TypeKind.FUNCTION`**——`a.calc` 编译期类型恒为 FUNCTION，从不建模为
  BOUND_METHOD。
- **矛盾点**：`core/kernel/axioms/primitives/callable.py:32-33` `BoundMethodAxiom`
  **明确声明"bound_method IS-A callable"**，但**编译期从未使用该 axiom**（`resolve_member`
  不产出 BOUND_METHOD kind）→ **机制已声明、编译期未接线**（半接通，code-quality §七.4）。
- **运行时对照**：`IbBoundMethod` 是真实 BOUND_METHOD，运行时 axiom 生效。**编译期/运行期
  类型身份不对称**——同一 `a.calc` 编译期是 FUNCTION、运行期是 BOUND_METHOD。
- **修复方向**：`resolve_member` 对方法成员产出 `TypeKind.BOUND_METHOD`（携带签名），
  使 BoundMethodAxiom 生效。需审计所有消费 `resolve_member` 的路径（调用返回推断、
  `fn f = a.calc` 承载、`is_assignable`）。

### 问题 2：函数符号 spec 回填签名丢失（`-> fn[(int,str)->int]` 退化为裸 fn）

- **现象**：`func make() -> fn[(int,str) -> int]: ...` 后 `make()` 返回类型被推断为裸 `fn`
  （kind=function, params=[], ret=auto），`fn[(int,str)->int] f = make()` 报"0 参数"。
- **根因链（逐环实证）**：
  1. `_declaration_visitors.py:123-131`（type_checking）用 `create_func` 回填函数符号 spec：
     ```python
     param_type_names = [(p.name if p else "any") for p in param_types]   # 字符串级
     ret_type_name = ret_type.name if ret_type else "void"                # 只取 name
     updated_spec = self.registry.factory.create_func(name=..., param_type_names=...,
                                                      return_type_name=ret_type_name, ...)
     ```
     `ret_type` 是 `fn[(int,str)->int]`（CALLABLE_SIG spec，name="fn"），`create_func`
     只取 `name` → return_type 降级为**裸 `TypeRef("fn")`**，**CALLABLE_SIG 的 param_types/
     return_type 结构化签名全部丢失**。
  2. `create_func`（`core/kernel/spec/registry/factory.py:59`）是**早期字符串级 API**：
     `return_type=TypeRef.of(return_type_name)`——只接受简单类型名，不支持结构化 TypeRef。
  3. `resolve_call_return`（`_inference.py:89-92`）Layer 1 对 FUNCTION/CALLABLE_SIG 读
     `callee_spec.return_type` → 此时已是裸 fn → 返回裸 fn。
- **扩散面**（`create_func` 8 个调用点，用户函数/方法 spec 回填相关）：
  - `_declaration_visitors.py:125`（函数定义）
  - `_declaration_visiders.py:403`（方法定义）
  - `symbol_collection_pass.py:295`（函数符号收集）
  - `symbol_collection_pass.py:332`（LLM 函数）
  - 其余为 bootstrap/prelude 内置（int/str/len 等，不受影响）
- **连带**：泛型返回（`-> list[int]`）、Optional 返回（`-> Optional[int]`）的**编译期
  spec 签名**同样经此扁平化（运行期靠赋值路径 rebind 补救，但"未赋值直接消费"路径暴露）。
- **修复方向**：`create_func` 升级为接受结构化 `return_type: TypeRef` / `param_types:
  List[TypeRef]`（或新增 `create_func_sig`），回填处传解析后的 spec 而非 name 字符串。
  这是**架构级 API 升级**，8 个调用点需审计。

### 问题 3：函数返回值 Optional 包装缺失（`maybe(5).unwrap()` 报 int 无 unwrap）

- **现象**：`func maybe(int n) -> Optional[int]: return n` 后 `maybe(5).unwrap()` 报
  `'int' object has no attribute 'unwrap'`；`Optional[int] r = maybe(5)` 正常。
- **根因**：`core/runtime/vm/handlers/control_flow.py:114-122` `vm_handle_IbReturn`：
  ```python
  value = yield value_uid   # 直接取返回值
  return Signal(ControlSignal.RETURN, value)   # 原样返回，不做 wrap_optional
  ```
  **函数返回值路径的 Optional 包装缺失**。赋值路径正常是因为 `define_variable` 按
  declared_type 包装；链式/`type()`/直接方法调用跳过赋值 → 裸 int 进入消费路径。
- **同源**：`_vm_call_user_function`（`_shared.py:370-374`）`return seq_result.value`
  同样不做 wrap。两个返回路径都缺包装。
- **修复方向**：函数调用返回点（VM `vm_handle_IbReturn` / `_vm_call_user_function` /
  `_vm_call_fn_callable` / `_vm_invoke_llm_function` 等）按函数声明返回类型 wrap_optional。
  需确定单一权威 wrap 点（编译期在 func_returns 栈标记返回类型，运行期在返回处消费）。

---

## 二、共同架构根因（用户猜想验证）

**`fn`/`callable` 函数签名建模基于早期"字符串级 TypeRef"设计，泛型地基后未同步升级。**

时间线证据（git）：
- `create_func` 是早期 API（`TypeRef.of(return_type_name)` 字符串级）。
- CALLABLE_INSTANCE / CALLABLE_SIG kind 是后补（TypeRef 结构化重构 + 泛型体系）。
- 泛型体系落地后，`create_func` 与 `resolve_member` **未跟随升级**——它们仍以
  "简单类型名"构建函数 spec，结构化签名（fn[签名]/泛型实参/Optional wrapped_type）
  在函数符号回填与成员解析路径被扁平化。

**这符合用户猜想"泛型地基没打好时已实现的基本功能存在类似深层次缺陷"**：
函数签名建模是 IBCI 最早期的能力之一，其类型身份机制未跟上 TypeRef 结构化演进。

## 三、架构判断

| 项 | 判定 |
|----|------|
| 性质 | **架构级缺陷**（类型身份断层），非功能漏洞 |
| 用户猜想 | **证实**（历史包袱 + 早期字符串级 API 未升级） |
| 涉及子系统 | 编译期 spec 构造（create_func）/ 成员解析（resolve_member）/ 运行期返回值（vm_handle_IbReturn） |
| 修复性质 | **破坏性重构**（create_func API 升级影响 8 调用点）——符合"破坏性重构默认已授权"原则，但须独立分支验证 |
| 扩散面 | 所有函数/方法/可调用类型的签名保真；泛型/Optional/fn[签名] 返回 |

## 四、修复方向建议（下一 session）

1. **create_func 结构化升级**（核心，问题 2 根因）：改为接受 `return_type: TypeRef` +
   `param_types: List[TypeRef]`，回填处传解析后的 spec。审计 8 个调用点。判别性回归：
   `-> fn[(int,str)->int]` 函数返回、`-> list[int]` 泛型返回、`-> Optional[int]` 返回。
2. **resolve_member 产出 BOUND_METHOD**（问题 1 根因）：方法成员建模 BOUND_METHOD kind，
   激活 BoundMethodAxiom。审计消费点（调用返回推断 / fn 承载 / is_assignable）。
3. **函数返回 wrap_optional**（问题 3 根因）：VM 返回路径按声明返回类型包装。判别性回归：
   链式 `maybe(5).unwrap()`、`type(maybe(5))`、`maybe(5).is_some()`。
4. **系统性扫描**：搜索其他"字符串级 TypeRef"构造残留（`TypeRef.of(name)` / `p.name` /
   `ret_type.name` 用于重建 spec 的路径），确认断层是否蔓延到更多基本建模。

## 五、验证基线

- 触发用例（trials/ 探针，非正式用例）：
  - `q1_bound.ibci`：绑定方法赋 callable（问题 1）
  - `q2_fnret.ibci`：函数返回 fn[签名]（问题 2）
  - `q3_optchain.ibci`：链式 Optional unwrap（问题 3）
- 全量 pytest：当前 2717 passed / 1 skipped（基线，修复须零回归）。
- 判别性回归建议：每项修复含编译期 + 运行期 + 类型身份（type()）断言。

## 六、交接纪律

- 全程本地 commit、禁 push；不触碰 main。
- 大范围破坏性重构（create_func 升级）100% 授权在独立分支实验，确认零风险后手动更新
  unsafe-vibe-dev。
- 修复走 code-workflow Phase 0-5 + code-quality 红线（禁止双通道/半修复）+ design-philosophy
  对照（单一权威源：函数 spec 构造收敛为 create_func 单入口 + 结构化 TypeRef）。
- 每项修复后全量 pytest 零回归 + WORKLOG 详尽记录变化前后。
