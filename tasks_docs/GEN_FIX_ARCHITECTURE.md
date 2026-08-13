# GEN-5/GEN-6 架构级修复方案（宏观统一根因）

> 2026-08-13 编制。用户要求：宏观架构级、彻底且长远的修复方案；允许经证实的破坏性变更
> （有效 + 长期收益 + 架构更合理）；不做最小/快速修复。本文件为设计阶段任务控制文档，
> 落地后按治理纪律收敛入 docs/。

---

## 一、缺陷清单（内核实证复核结论，2026-08-13）

三个独立缺陷 + 一个残留，统一根因见 §二。

### KERNEL_ISSUE-GEN-6（P1）——记录根因被纠偏

- **根因 A（编译错误直接根因）**：`core/kernel/spec/registry/_inference.py:254`
  运算符结果类型推断用 `resolve(method_member.return_type.head, ...)` 丢弃类型实参，
  特化已正确产出的 `TypeRef('Vec',(int,))` 被降级为基类 `Vec` → is_assignable False →
  `SEM_TYPE_MISMATCH`。触发因子是 `-> Vec[T]` 返回类型（非参数形态）。
  决定性反证：`func __add__(self, T other) -> Vec[T]`（裸 T 参数）同样报错。
- **根因 B（独立第二缺陷）**：`core/compiler/semantic/passes/_declaration_visitors.py:440`
  `_param_type_ref` 对泛型类参数走 `TypeRef.of(name)` 扁平化为 `TypeRef('Vec[T]')`
  （head 含方括号、args 空），`TypeRef.substitute`（type_ref.py:250）对扁平形态无法替换
  → 特化类 param_descriptors 保持 `Vec[T]` → 显式方法调用报 `expected 'Vec[T]'`。
  非运算符特有——任何 `Vec[T]` 形态参数的普通方法都中招。

### KERNEL_ISSUE-GEN-5（P2）——记录根因属实

- `core/compiler/semantic/passes/_expression_visitors.py:686-721` 表达式位置
  `visit_IbSubscript` 注册分支只处理 `ast.IbName` slice（裸 `Box[int]`），嵌套
  `IbSubscript`（`Box[list[int]]`）落在分支外 → 无特化注册 → 运行时
  `_specialize`（ib_class.py:444）metadata spec 缺失抛错。注解路径
  （type_resolution_pass:112 / symbol_collection_pass:400）已有递归 slice 解析，
  机制同构缺失。实证 `Pair[str,int]`/`Box[dict[str,int]]` 同病；预存缺陷（35bb2de 引入）。

### 残留：`engine.py:174` `TypeRef.of("list[int]")`

- 方法 `read_bytes` 返回类型用 `TypeRef.of("list[int]")` —— 扁平字符串编入 head。
  同一扁平形态模式的独立实例。

---

## 二、统一根因（架构诊断）

**类型引用在"结构化（TypeRef args 保留）"与"扁平化（实参编入字符串/丢弃）"两套表示间漂移。**

泛型系统存在两条解析文化，未收敛为单一权威：

| 路径 | 构造 | 解析 | 实参保留 | 缺陷 |
|------|------|------|---------|------|
| 结构化（正确） | `TypeRef.from_spec`（type_ref.py:118，已覆盖全部泛型 kind） | `resolve_typeref`（registry/_base.py:115，含懒构建特化） | ✅ | — |
| 扁平化（缺陷源） | `TypeRef.of(name)` / `.head` | `resolve(head)` | ❌ | GEN-6A/B、GEN-5、engine 残留 |

三缺陷是同一根因的不同消费端：
- **GEN-6A**：消费端用扁平解析（`resolve(head)`）消费本已结构化的 TypeRef
- **GEN-6B**：构造端用扁平工厂（`TypeRef.of(name)`）绕过结构化分支
- **GEN-5**：注册端未复用注解路径的递归机制（同构机制缺失）

---

## 三、架构级修复方案（四层，每层独立 commit + 判别性回归 + 回归试用核销）

### 设计目标（design-philosophy §一单一权威源 + §四机制同构 + §八命名统一）

1. **构造端单一权威**：所有 spec→TypeRef 一律走 `TypeRef.from_spec`；消灭 `TypeRef.of(泛型名)`。
2. **解析端单一权威**：所有 TypeRef→spec 一律走 `resolve_typeref`；消灭 `resolve(head)` 消费泛型 TypeRef。
3. **注册端递归统一**：抽共享 helper 递归解析 slice → resolve_specialization，注解/表达式共用。

### 第 1 层：消费端统一（GEN-6A + 同类 `.head` 解析点）
- `_inference.py:254` 改 `resolve_typeref(return_type)`；逐点分类约 20+ `.head` 解析点，
  只迁移"类型推断/类型检查"类（需保留实参），"能力/合法性查询"类（丢实参无害）不动。
- 判别性回归：D2-01 修复后期望 `cx=4|cy=6|eq=True|neq=False` 达成。

### 第 2 层：构造端统一（GEN-6B + engine 扁平残留）
- `_param_type_ref` 复用 `TypeRef.from_spec`（保留 CALLABLE_SIG 结构化分支）；`engine.py:174`
  改结构化 `TypeRef.generic("list", TypeRef.of("int"))`。
- 判别性回归：特化类方法参数校验正确（`Vec[int]` 方法收 `str` 参数报 SEM_TYPE_MISMATCH）。

### 第 3 层：注册端递归统一（GEN-5）
- 抽共享 helper（递归解析 slice → resolve_specialization），表达式 `visit_IbSubscript`
  与注解路径（type_resolution_pass / symbol_collection_pass）共用；覆盖嵌套/多参/非法实参拦截。
- 判别性回归：`type(Box[list[int]])` / `Pair[str,int]` / `Box[dict[str,int]]` 表达式位置可用。

### 第 4 层：规则永久化
- 治理文档登记"TypeRef 构造/解析统一入口"规则；`resolve_typeref`/`from_spec` docstring
  标注唯一权威入口；新代码禁 `TypeRef.of(泛型)` 与 `resolve(head)` 消费泛型 TypeRef。

---

## 四、破坏性变更授权评估（用户 2026-08-13 澄清）

- 本方案属**破坏性重构**（触及 `_inference.py`/`_param_type_ref`/`visit_IbSubscript` 等
  既有消费路径），但符合：一般工程经验 + 普适性 + 架构更合理（单一权威源收敛）+ 长期收益
  （根治而非治标、同类新模式自动受约束）。
- 按 AGENTS.md "破坏性重构授权"默认已授权自主推进，需详尽记录决策依据与工作内容。
- 大范围破坏性重构分支政策：若确认边界清晰（四层各自独立、判别性回归可证）可走
  unsafe-vibe-dev 直接合并；若某层边界无法确认则独立分支实验。

## 五、最后复核调研结论（2026-08-13，代码实证）

### 风险 1：第 1 层 22 个 `.head` 解析点分类（已逐一核查）

| 文件:行 | 语义 | 判定 |
|---------|------|------|
| `_statement_visitors:59` | 赋值 val_type TypeRef 兜底 | **迁移**（类型检查需保留实参） |
| `_statement_visitors:82/:94` | ICE_TYPE_LEAK 错误路径兜底 | 迁移（一致性，低风险） |
| `_statement_visitors:335-336` | callable 签名返回类型对比 | **迁移**（泛型 callable 返回对比需实参） |
| `_expression_visitors:60` | ICE 路径兜底 | 迁移（一致性） |
| `_expression_visitors:738` | tuple 位置元素推断 | **迁移**（元素可为泛型） |
| `_type_checking_base:128` | 沿父链查方法（能力查询） | 可迁移（更稳妥），非必需 |
| `_type_checking_base:183/:192` | is_assignable TypeRef 兜底 | **迁移**（泛型赋值对比需实参） |
| `typeref_resolution_pass:53` | 符号 spec 解析 | 迁移 |
| `_inference:254` | 运算符结果类型推断 | **迁移（GEN-6A 核心）** |
| `_inference:266/269/288/290` | 迭代/下标元素推断 | **迁移**（list[list[int]] 等需实参） |
| `_assignability:48/52` | Optional 内层推断 | **迁移**（Optional[list[int]] 需实参） |
| `_assignability:245/258` | 父类特化递归 | 已结构化正确，仅核对 |
| `_base:148/159` | resolve_typeref 内部 | 正确（fallback 到 head） |

结论：22 点中约 **14 点应迁移**（类型推断/检查类），8 点能力查询/内部正确。迁移统一用 `resolve_typeref`。

### 风险 2：`_param_type_ref` CALLABLE_SIG 分支与 from_spec 复用

- `_param_type_ref` 仅 1 个调用点（`_declaration_visitors:423`，构造方法参数 descriptor）。
- CALLABLE_SIG 结构化分支必须保留（fn_callable 参数契约）。
- **新发现第四处双实现**：`generic.py` `_to_typeref_*`（to_typeref 注册表声明）与
  `type_ref.py` `from_spec`（kind 分派）是**两套 spec→TypeRef 实现**（同语义双写，
  design-philosophy §四违规）。`to_typeref` 未被主路径消费（仅 symbol_collection 辅助）。
  → 第 2 层应**收敛为单一 from_spec 权威**（to_typeref 改委托 from_spec 或删除）。

### 风险 3：GEN-5 共享 helper 可行性

- **`_type_checking_base._resolve_type`（:215-320）的 IbSubscript 分支已是完整递归实现**：
  IbTuple 多参递归、嵌套 IbSubscript 递归、非法实参拦截（None/auto/void）、list 多参拒绝、
  实参数量校验（SEM_GENERIC_TYPE_ARG_COUNT）。
- `visit_IbSubscript` 表达式位置只需以 `self._resolve_type(node.slice)` 作为 slice 解析入口
  （替换/扩展当前仅裸名分支），即与注解路径机制同构。**无需新写递归逻辑，复用现成 helper**。

### 风险 4：resolve_typeref 懒构建覆盖

- `create_generic_registry()`（generic.py:374）注册 11 种内置泛型：
  list/dict/tuple/Optional/fn_callable/behavior/thread/thread_result/chan/slot/generator。
- `resolve_typeref` 懒构建（`_base.py:146-157`）依赖此表 + `resolve_specialization` 用户类
  分支，覆盖全部泛型 kind。**无缺口**。

---

## 六、最终修复方案（定案）

**统一根因**：TypeRef 生命周期两端口径漂移（构造端扁平化 + 解析端丢实参 + 注册端机制不全）。

**四层实施**（每层独立 commit + 判别性回归 + 回归试用核销 D2-01/GEN5-01）：

### 第 1 层：解析端统一（GEN-6A + 14 个 `.head` 解析点迁移）
- `_inference.py:254` 及其余 14 个"类型推断/检查类"`.head` 解析点改 `resolve_typeref`。
- 判别性回归：D2-01 修复后期望 `cx=4|cy=6|eq=True|neq=False` 达成。
- 全量 pytest 零回归验证无副作用。

### 第 2 层：构造端统一（GEN-6B + engine 残留 + to_typeref/from_spec 双实现收敛）
- `_param_type_ref` 复用 `TypeRef.from_spec`（保留 CALLABLE_SIG 分支）。
- `engine.py:174` `TypeRef.of("list[int]")` → 结构化 `TypeRef.generic("list", TypeRef.of("int"))`。
- `generic.py` `_to_typeref_*` 收敛：委托 `TypeRef.from_spec`（消除双实现）。
- 判别性回归：特化类方法参数校验正确（`Vec[int]` 方法收 `str` 报 SEM_TYPE_MISMATCH）。

### 第 3 层：注册端统一（GEN-5）
- `visit_IbSubscript` 表达式位置用 `self._resolve_type(node.slice)` 作为 slice 解析入口
  （复用现成递归），覆盖嵌套/多参/非法实参拦截。
- 判别性回归：`type(Box[list[int]])` / `Pair[str,int]` / `Box[dict[str,int]]` 表达式位置可用。

### 第 4 层：规则永久化
- 治理文档登记"TypeRef 构造/解析唯一权威入口"：构造走 `from_spec`、解析走 `resolve_typeref`；
  禁 `TypeRef.of(泛型)`、禁 `resolve(head)` 消费泛型 TypeRef。
- `from_spec`/`resolve_typeref` docstring 标注唯一权威；新代码同则。

---

## 七、破坏性变更授权评估（用户 2026-08-13 澄清确认）

- 本方案为**破坏性重构**（触及 _inference/_param_type_ref/visit_IbSubscript/generic.to_typeref
  等既有路径 + engine 扁平残留）。符合授权条件：
  - **有效性**：三缺陷 + 一处残留同根因根治，判别性回归可证。
  - **长期收益**：单一权威源收敛，同类新模式自动受规则约束，不再逐点打补丁。
  - **架构更合理**：TypeRef 生命周期两端统一（design-philosophy §一/§四/§八），
    消除 to_typeref/from_spec 双实现（§四机制同构）。
- 四层各自独立、边界清晰（判别性回归可证）→ 走 unsafe-vibe-dev 直接合并，
  每层独立 commit；若某层验证中出现边界不确定 → 切独立分支实验后再应用。

