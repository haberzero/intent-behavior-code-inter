# 设计冻结：内置泛型类型身份双轨根治（缺陷一 + 缺陷二）

> 2026-08-13。依据 `HANDOFF_GENERIC_ASSIGNABILITY.md` + 全代码调研实证。
> 用户授权（2026-08-13）：架构统一性/长期收益/代码质量优先，两缺陷均根治。
> 本文件冻结设计；实现与验证记录另见 WORKLOG。

---

## 〇、统一根因

**内置泛型（list/dict/tuple/thread/chan/slot/generator/fn_callable/behavior/Optional）
与用户类泛型（`Box[T]`）在类型身份模型上双轨不对称**：

| 维度 | 用户类泛型 `Box[int]` | 内置泛型 `list[int]` |
|------|----------------------|---------------------|
| 编译期特化 spec | ✅ `_specialize_user_class`（type_args 结构化） | ✅ `resolve_specialization`（element_type 等结构化） |
| 赋值检查 | ✅ `is_assignable` 正确拦截（无 axiom，name 比较+继承链） | ❌ axiom `is_compatible` 前缀匹配放行（缺陷一） |
| 运行时特化类 | ✅ `_specialize` create_subclass → `get_class("Box[int]")` | ❌ 未水化 → `get_class("list[int]")` 为 None（缺陷二） |
| 值层 type_ref | ✅ `Box[int]` 带实参 | ❌ 擦除为 `list` |

---

## 一、缺陷一：内置泛型赋值类型检查缺失泛型实参校验（P1）

### 1.1 现象（已实证）

`is_assignable` 直调：10/11 类内置泛型 `X[int]→X[str]` 全部放行；Optional 拦截；用户类拦截。
语言层实证：`list[str]`→`list[int]` 参数、`thread[int]`→`thread[str]` 赋值，编译期放行且运行通过。

### 1.2 根因（代码实证）

`core/kernel/spec/registry/_assignability.py` `is_assignable`：

```
:62  name 比较（src.name == target.name）——特化名不同不命中
:81  axiom 分支：src_axiom.is_compatible(target.name)
     内置泛型 axiom is_compatible = 前缀匹配（12 处），无视实参 → True 放行
```

- 12 处前缀匹配：comm.py:54/88/114/156、generator.py:37、callable.py:95/131/132、
  sequences.py:180/249/323、sentinels.py:125（Optional）
- Optional 正确拦截：因 `:47-60` OPTIONAL 专门分支先于 axiom 命中（递归 wrapped_type 比较）
- 用户类正确拦截：无 axiom → name 比较后落继承链 → False

> ⚠️ 交接文档 §1.2 描述"axiom 分支(:72)先执行绕过 name 比较"**顺序描述有误**（实际
> name 比较 :62 在前、axiom :81 在后），但根因结论（axiom 前缀匹配无视实参）属实。

### 1.3 修复方案（方案 A，机制同构于用户类路径）

**在 `:62` name 比较之后、`:81` axiom 分支之前，插入"同泛型实参比较"**：

```python
# 同 base 泛型（src/target 均为特化且 get_base_name 相同）：
#   逐个比较结构化实参（is_assignable 递归）；任一不兼容 → False
#   target 为裸类型（无实参）→ 放行（协变：list[int] → list）
```

关键决策：
1. **结构化实参提取**（各 kind 字段已实证）：
   - list → `element_type`；dict → `key_type`+`value_type`；tuple → `positional_element_types` 或 `element_type`
   - thread/thread_result/chan/slot/generator → `value_type`
   - fn_callable/behavior → `value_type`（语义=返回类型，与用户类泛型实参意义不同，须按"返回类型可赋值"比较）
   - 用户类 → `type_args`（已有正确路径，本分支不重复；仅当无 axiom 时仍走原逻辑）
2. **协变方向**：仅允许"特化→裸"（`list[int]`→`list`），禁止"裸→特化"（`list`→`list[int]`）。当前 `:66-77` LIST 分支有部分处理（`:71` target 裸 any 放行、`:75` 子集比较），须与新分支统一、消双写。
3. **axiom is_compatible 保留**：`bool isa int` 等非泛型子类型兼容不破坏（`:81` 分支仍对非泛型生效）。
4. **Optional 不破坏**：`:47-60` 专门分支保持在前。
5. **嵌套泛型实参**：`list[list[int]]`→`list[list[str]]` 递归比较（is_assignable 递归天然支持）。

### 1.4 判别性回归

- 10/11 类 `X[int]→X[str]` 报 SEM_TYPE_MISMATCH（compile-only + is_assignable 直调）
- 协变保留：`list[int]→list` 放行、`list→list[int]` 拦截（新增方向断言）
- Optional/用户类/嵌套泛型不回归
- 触发用例：`trials/T0X` 形态（按 Phase D 义务，缺陷修复=根因修复+tests/ 回归双交付）

---

## 二、缺陷二：内建泛型运行时值层类型擦除（P1-P2 架构缺陷）

### 2.1 现象（已实证）

`type(Box[int]值)=Box[int]` vs `type(list[int]值)=list`。编译 `list[int]` 后
spec_reg 有特化 spec 但 `get_class("list[int]")` 为 None。

### 2.2 根因链（代码实证）

1. **特化 spec 未水化**：编译期 `resolve_specialization` 注册 `list[int]` spec，
   但运行时只注册基类 `list`。`IbClass._specialize`（ib_class.py:405）对无
   `type_params` 的内建类走"boxed 特化名字符串"路径（`:420-422`），不 create_subclass。
2. **值对象绑基类**：`factory.py:50/55/59` `create_list/tuple/dict` 硬编码
   `get_class("list")` 基类；`primitive_initializer._box_list` 等装箱器同样
   用 `reg.get_class("list")`（`:490-511`）。
3. **type_ref 擦除**：`IbValue.__init__`（base.py:254-255）从 `ib_class.spec` 构造
   type_ref → 基类 spec 无实参 → `list`。
4. **序列化擦除**：`runtime_serializer._collect_instance` `class_name=obj.ib_class.name`
   = `list`（基类名）→ 反序列化 `_get_instance` 用 `get_class("list")` → 实参丢失。

### 2.3 判定

初期设计妥协（早期内建容器单类+擦除最快实现），用户类泛型引入特化类后未回填内建泛型
→ 机制同构缺失（design-philosophy §四）+ 设计语言分裂（§二）。

### 2.4 根治方案：内置泛型特化 spec 水化为运行时特化类

**方向**：与用户类泛型机制同构——编译期特化 spec → 运行时 create_subclass 特化类
→ 值对象绑特化类 → type_ref 带实参 → 序列化保真。

**改动面**：
1. **`IbClass._specialize` 对内置泛型也 create_subclass**：当 `self._spec` 无
   `type_params` 但 `self.name` 在 `generic_types` 中（list/dict/tuple/Optional/...）时，
   查/建特化类（`spec_reg.resolve("list[int]")` → `create_subclass("list[int]", ...)`），
   parent 指向基类（list 特化类 parent=list 基类，保证方法继承与 is_assignable 继承链）。
   现有 `:417-425` boxed 字符串路径保留仅用于非泛型类下标（Box[42] 守卫）或
   内建泛型类下标（Box[list[int]] 嵌套实参需要特化名字符串——保留此功能）。
2. **值对象创建按特化选类**：`factory.create_list/tuple/dict` 增加"可选特化 spec/class"
   参数或查 registry 特化类；装箱器 `_box_list` 等传特化类。值创建点（字面量 VM handler /
   反序列化 / LLM 解析 / 参数传递）须能感知编译期类型。
3. **编译期类型传递**：赋值/参数绑定点 `bind_type(rhs, target_type)` 已存在
   （`_statement_visitors.py:114/154/172` 仅 behavior 特例）——扩展为容器字面量也绑定
   target_type（`list[int] li = [1,2]` 使 `[1,2]` 节点 node_to_type=list[int]）。
   VM `vm_handle_IbListExpr`（leaf.py:463）查 node_to_type → 有特化则按特化建值。
4. **序列化**：值对象 class_name=`list[int]` → 反序列化 `_get_instance` 时
   `get_class("list[int]")` 需存在（特化类已注册）或按需水化。round-trip 保真。
5. **运行时类型检查联动**：值绑特化类后 `runtime_context._check_type`（`:101-111`）
   `val_spec` = 特化 spec → `is_assignable(list[int], list[int])` 正确拦截 → 缺陷一修复后
   编译期+运行时双层一致。

### 2.5 边界评估与分支政策

- 改动面大（内核 + 编译器 + 运行时 + 序列化 + 装箱器），跨子系统。
- 涉及"值创建点感知类型"的语义设计（字面量/反序列化/LLM 解析/参数传递均需类型上下文），
  存在未知边界（如 `for x in list[int]` 迭代、泛型函数返回、嵌套容器、闭包捕获）。
- **按分支政策**：无法确认边界的破坏性重构 → 独立分支 `exp/generic-type-identity`
  实验，确认技术路线后手动 cherry-pick 更新 unsafe-vibe-dev；**不触碰 main**。
- **实施顺序**：缺陷一（独立可修，先做）→ 缺陷二（独立分支，后做）。

### 2.6 已确认边界（独立复核核实，非本次核心，记录待增量）

1. **函数返回字面量**：`func f() -> list[int]: return [1,2]` → `type(f())` = `list`。
   返回语句的容器字面量未绑函数返回类型。
2. **函数调用实参字面量**：`f([1,2])`（形参 `list[int]`）→ `type(items)` = `list`。
3. **下标/属性赋值字面量**：`m[0] = [9]`（`m: list[list[int]]`）→ `type(m[0])` = `list`。
4. **嵌套容器内层元素**：`list[list[int]] n=[[1],[2]]` → 外层 `n` 保真为 `list[list[int]]`，
   内层 `n[0]` 擦除为 `list`。根因：内层 IbListExpr 节点 `node_to_type` 未绑 `list[int]`
   （编译期只 bind 顶层 RHS）。补齐需编译期递归类型传播（外层特化 element_type → 内层节点）。
5. **容器切片**：`li[0:2]` 返回裸 list（`collections.py` 切片 `registry.box`）。
6. **Optional 值身份**：`Optional[int]` 值绑基类 `Optional`（`_wrap_optional`），type() 返回
   `Optional`。Optional 有专门分支（编译期/运行时 is_assignable 正确），值层身份为独立增量。
7. **跨引擎反序列化**：目标引擎 spec_reg 无该特化时回退基类（安全不保真；同引擎 round-trip
   保真）。可增强：反序列化从序列化 type_pool 重建 spec。

以上均不构成回归（修复前即为擦除行为），属值层身份根治的后续增量。

---

## 三、文档同步计划

- `docs/architecture/03_type_system.md` §6：type_ref "运行时类型身份（结构化）" 声明 vs
  内建泛型实际擦除的漂移 → 修复后收敛一致。
- `docs/syntax/12_builtins.md`：内建泛型值层身份现状（若维持部分擦除补现状说明；
  根治后删除）。
- `docs/KNOWN_LIMITS.md`：登记/移除对应限制。
- `HANDOFF_GENERIC_ASSIGNABILITY.md`：标记两缺陷修复状态。
- `PENDING_TASKS.md` / `NEXT_STEPS.md` / `WORKLOG.md`：同步。

---

## 四、测试计划

- **缺陷一**：`tests/compiler/test_generics.py` 增 TestGenericAssignability（10/11 类
  拦截 + 协变双向 + Optional/用户类/嵌套不回归）；`tests/e2e/` 增判别性 e2e（编译期
  报错触发用例）。
- **缺陷二**：`tests/e2e/test_generics_runtime.py` 增值层身份断言（type() 一致）；
  序列化 round-trip（list[int] 值保真）；运行时 _check_type 拦截。
- 全量 pytest 零回归基线。
