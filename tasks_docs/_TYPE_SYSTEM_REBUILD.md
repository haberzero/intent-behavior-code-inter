# 设计：类型体系地基地基根治——泛型特化机制重建（摆脱历史错误设计）

> 2026-08-13 编制。承接 `_DEEP_ANALYSIS_TYPE_SYSTEM_FOUNDATION.md`。
> 用户裁定（2026-08-13）：演进已到必须脱离原始错误设计思路的位置，**要摆脱历史
> 决策的错误设计**，考虑彻底重构根治方案。
> 本文件冻结根治方向与分阶段实施设计；实现与验证记录另见 WORKLOG。

---

## 〇、根治目标（从原始架构意图出发）

原始类型系统架构文档（git 2138870a）已给出正确设计，M1-M5 迁移未按此改造特化机制。
本重建把特化机制**拉回原始意图 + 修正其过时部分**：

| 原始意图 | 本方案落地 |
|---------|-----------|
| "特化机制是一个**纯函数**……比每特化造 ListSpec 然后注册简洁数十倍"（§8.1） | **特化 spec 由声明驱动的纯函数构建**（`GenericTypeDeclaration.build` 唯一权威），`SpecFactory.create_*` 收尾 |
| "**泛型实参随值走**，不依赖外部上下文"（§7.2） | 值对象 type_ref 携带结构化实参（含句柄类），值创建点统一侧表绑定 |
| "类型引用必须**结构化、递归**（不是字符串拼接）"（§0） | 特化构建接口全面 TypeRef 化，`TypeRef.of(泛型名)` 全禁用 |
| "编译产物纯数据，运行时**不能动态创建新类型**"（§5.3） | 运行时特化类水化收敛到加载期；sealed 后 `_specialize` 字符串魔法回落删除 |

---

## 一、根治方向（统一根因 → 三个桩）

### 桩 1（P0）：`GenericTypeDeclaration.build` + `SpecFactory.create_*` 字符串接口 → 结构化 TypeRef 接口

**现状**：`_assignability.py:275` 把内层实参名（`a.name`）作字符串传给 `build`；
`generic.py:_build_*` 经 `factory.create_list(element_type_name=...)` 用
`TypeRef.of("list[int]")` 扁平化——**这是唯一特化创建点，嵌套实参在此丢失结构**。

**改动**：
- `GenericTypeDeclaration.build` 签名：`(factory, args: List[TypeRef], arg_modules) -> TypeDef`
  （原 `List[str]`）。
- `SpecFactory.create_list/dict/tuple/optional/thread/chan/slot/generator/thread_result/
  fn_callable/behavior` 增加结构化入口（接受 TypeRef），字符串入口保留为兼容壳或删除。
- `resolve_specialization`（_assignability.py:248-295）不再 `arg_names=[a.name]`，
  直接传 `arg_specs` 的 TypeRef；`candidate_key` 用 `TypeRef.canonical_name` 派生（结构化）。
- `_specialize_user_class`（:297-344）`type_args` 存结构化 TypeRef（现 `TypeRef.of(a.name)` 扁平）。

**效果**：`list[list[int]]` 的 `element_type` 变结构化 `TypeRef('list',(int,))`；
`substitute` 可穿透嵌套；descriptor 双真相（缺陷 B）同源治愈；跨引擎水化不再丢内层。

**验收**：`Box[int].make(list[list[str]])` 编译期报 `SEM_TYPE_MISMATCH`（判别性回归）。

### 桩 2（P1）：`get_base_name()` 收敛为单义 + 运行时值层身份统一

**现状**：`base.py:251-254` 三种取值路径（`_axiom_name`/`_KIND_BASE_NAMES`/`self.name`），
用户泛型特化 `Box[int]` 返回含方括号全名，独立 `base_name` 字段旁置；
运行时 `_impl_cls`（ib_class.py:215）取不到族名 → 用户泛型实例回落裸 IbObject。

**改动**：
- `TypeDef.get_base_name()` 统一返回**族名**（读 `base_name` 字段优先，回落
  `_axiom_name`/`_KIND_BASE_NAMES`/`name`），消除"含方括号全名"形态。
- 值层 kind 分派（`_value_base_name`/`is_sequence_value`/deep_clone/runtime_serializer）
  改用统一 `get_base_name()`，删三处平行实现。
- **句柄类值身份**：给 thread/chan/slot/generator/thread_result 值创建点接入
  `node_to_type` 侧表（与容器 `_bind_container_specialization` 同构），值对象按声明
  类型 rebind 特化类；`_check_type` 对句柄值实参校验（thread[int]/thread[str] 运行时区分）。
- sealed 运行时 `_specialize` 字符串魔法回落（ib_class.py:471-481）改为 fail-fast 或
  真实特化类。

**验收**：`type(thread[int]值)=thread[int]`；`thread[int] t = thread_str()` 运行时报错。

### 桩 3（P1）：特化生命周期声明驱动——删 per-kind 手工并联表

**现状**：serializer（11 分支）/ rehydrator shell（16）/ fill（9）/ factory（11）/
from_spec（11）是 6-7 张独立 kind 硬编码表，新增一种泛型需补 ≥7 处（GENERATOR 事件实证）。
`GenericTypeDeclaration` 只剩 build+resolve_member，serialize/restore 不经过它。

**改动**：
- `GenericTypeDeclaration` 增加 `serialize`/`restore` 生命周期钩子（或声明 `kind_fields`
  驱动反射收集），使序列化/还原经声明路由。
- `TypeDef.get_references()` 实现（现返回 `{}` 死通道），`serializer._collect_type`
  结构化收集嵌套实参（`*_uid` 通道复活），rehydrator uid 重建分支不再死代码。
- `_parse_arg_ref`（rehydrator）与 `_build_*` 统一为同一结构化解析语义。

**验收**：新增泛型类型只改 `generic.py` 一处；嵌套 `list[list[int]]` 跨引擎 round-trip
结构保真（`element_type` 结构化断言）。

### 桩 4（P2）：module 身份承载（跨模块同名坍缩）

**现状**：特化 spec `module_path=None` 出生即丢（`_specialize_user_class:319` 不传 module、
内置泛型 factory 全默认 None）→ 多模块同名特化在注册表/type_pool/运行时类表三层坍缩。

**改动**：特化 spec 沿基类 module 填充；`candidate_key`/`specialized_name`/`type_uid`
三处拼接统一带 module；`_rehydrate_type_pool_spec` 按 `(module,name)` 匹配。
（运行时 IbClass 表 name-only 是天花板，随桩 3 声明驱动一并评估。）

---

## 二、分阶段实施计划（独立分支，全量零回归门）

| 阶段 | 内容 | 风险 | 判别性回归 |
|------|------|------|-----------|
| **S0** | 基线固化 + 独立分支 `exp/type-identity-rebuild` + 现状测试快照 | 零 | — |
| **S1** | 桩 1：build/create_* 结构化 TypeRef 接口 + resolve_specialization 改造 | 中（内核 spec 层 + 语义层消费方 45+ resolve_typeref） | `Box[int].make(list[list[str]])` 编译期拦截 |
| **S2** | 桩 1 连带：descriptor 双真相收敛（param_types/param_descriptors 单一构造源） | 中（_declaration_visitors/symbol_collection） | descriptor 与 param_types 结构一致断言 |
| **S3** | 桩 2：get_base_name 单义 + 运行时值层身份统一（句柄类侧表 + _check_type + 删字符串魔法） | 高（运行时值层 70+ ib_class.name 消费点） | 句柄类值 type() 一致 + 运行时实参校验 |
| **S4** | 桩 3：声明驱动序列化/还原 + get_references 复活 | 中（serializer/rehydrator） | 嵌套泛型跨引擎 round-trip 结构断言 |
| **S5** | 桩 4：module 承载 + 三处拼接统一 | 低-中 | 多模块同名特化区分 |
| **S6** | 已知边界重估：`-> auto` 推断 / 元组解包检查 / `*expr` 元素级 | 中 | 每项判别性回归 |
| **S7** | 文档治理：generic.py docstring restore 残留 / 02_metadata_ast §2.4 校准 / L1-L5 重估 | 零 | — |

**每阶段门**：全量 pytest 零回归 + 判别性回归 + 独立复核（general agent）+ commit。
**分支政策**：S1-S6 独立分支 `exp/type-identity-rebuild` 实验；每阶段确认零风险后
手动 cherry-pick 更新 unsafe-vibe-dev；**不触碰 main**。

---

## 三、改造面量化（实测）

| 面 | 数量 | 说明 |
|----|------|------|
| `create_*` 字符串接口调用点 | 43 | 桩 1 主战场 |
| `resolve_typeref` 消费点 | 45 | 桩 1 连带验证 |
| `get_base_name()` 消费点 | 38 | 桩 2 |
| `ib_class.name` 直接使用 | 70 | 桩 2 运行时身份 |
| `TypeRef.of(` 调用 | 112 | 须审计：纯名构造合法 vs 泛型名扁平构造（禁） |
| `substitute(` 调用 | 9 | 桩 1 受益方 |
| 序列化 kind 分支 | 26 | 桩 3 |
| 泛型/特化相关测试 | 49 文件 / 57 用例 | 判别性回归素材 |
| 全量测试 | 124 文件 / 2586 passed | 零回归门 |

---

## 四、风险与对策

1. **TypeRef.of( 112 处审计**：区分"纯名构造（合法）"与"泛型名扁平构造（禁）"——后者
   是缺陷 A 的复现点，逐处迁移到结构化。S1 前置一个全仓扫描，产出"禁点清单"。
2. **运行时值层 70 处 ib_class.name**：多数是分派惯用法（沿基名），随桩 2 的
   `get_base_name()` 统一后自动对齐；须逐处确认无"含方括号全名匹配"依赖。
3. **序列化格式兼容**：编译器产物版本字段（"2.1"）——桩 3 若改线协议字段，须保留
   旧版读取（或版本提升 + 迁移）；评估后决定。
4. **行为漂移**：`is_assignable` 裸→特化方向、协变、Optional 分支等既有语义
   必须保留（全量测试守护）。

---

## 五、非目标（明确不做）

- 不重写 TypeRef 数据结构（已正确）。
- 不重写 Axiom 字符串边界（§4.3，公理层纯字符串是既定架构；结构化交给 spec 层）。
- 不引入用户级泛型 bound 约束 / 更复杂类型推断（PT-FEAT-3 边界不变）。
- 不动 `*expr` 的静态限制本质（仅元素级缓解）。

---

## 六、验收总纲

- **根因级**：`list[list[int]]` spec.element_type 结构化断言（unit）；
  `Box[int].make(list[list[str]])` 编译期拦截（判别性回归）。
- **身份级**：句柄类值 `type()` 一致；`thread[int]`/`thread[str]` 运行时区分。
- **生命周期级**：嵌套泛型跨引擎 round-trip 结构保真；新增泛型只改声明一处。
- **回归级**：全量 pytest 零回归（2586/1 基线）+ 独立复核 + 分支政策。
