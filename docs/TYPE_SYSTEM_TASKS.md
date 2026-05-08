# IBCI 类型系统重构专项任务（最高优先级）

> 本文档为类型系统演进与重构的唯一执行清单。  
> 范围严格对应《IBCI 类型系统：从零开始的全新架构设计》中的目标与阶段（M1-M5）。

---

## 0. 目标与约束（执行基准）

- [ ] 编译期与解释期严格隔离：编译器仅输出扁平中间结构，不包含运行逻辑。
- [ ] 编译器/解释器共享唯一类型定义来源：同一套核心数据定义双端生效。
- [ ] 保持面向对象且层次精炼：内核层与用户层类型关系一一对应。
- [ ] 泛型可结构化表达并可递归推导。
- [ ] 保持与 Python 宿主隔离：通过 IBCI 自身抽象访问运行值。
- [ ] 改造后代码可读性与维护性提升，尽量减少总代码量。

---

## 1. 总体里程碑

- [x] **M1：TypeRef 引入（兼容阶段）** — 完成（2026-05-07）
- [x] **M2：Optional[T] 与空安全落地** — 完成（2026-05-07）
- [x] **M3：TypeDef 单一化（替代多 Spec）** — 完成（2026-05-08）
- [x] **M4：运行时值模型单一化（IbValue）** — 完成（2026-05-08）
- [x] **M5：Axiom 接口统一化** — 完成（2026-05-08）

---

## 2. 详细任务分解

### M1：TypeRef 引入（兼容阶段）— ✅ 完成

- [x] 新增 `TypeRef` 数据结构（不可变、可哈希、支持递归泛型参数）。
  - 位置：`core/kernel/spec/type_ref.py`
  - 字段：`head: str`, `args: tuple[TypeRef,...]`, `module: Optional[str]`
  - 派生属性：`canonical_name`, `qualified_name`
  - 工厂：`TypeRef.of()`, `TypeRef.generic()`, `TypeRef.from_spec()`（桥接旧 Spec）
  - 工具：`substitute(mapping)` 用于泛型形参替换
- [x] 在类型解析链路中引入 `TypeRef`，以桥接方式兼容旧 `name/module` 字段。
  - `IbSpec.type_ref` 属性（base.py）
  - `FuncSpec.return_type_ref`, `FuncSpec.param_type_refs`（specs.py）
  - `ClassSpec.parent_type_ref`（specs.py）
  - `ListSpec.element_type_ref`（specs.py）
  - `TupleSpec.element_type_ref`（specs.py）
  - `DictSpec.key_type_ref`, `DictSpec.value_type_ref`（specs.py）
  - `DeferredSpec.value_type_ref`（specs.py）
  - `MemberSpec.type_ref`（member.py）
  - `MethodMemberSpec.return_type_ref`, `MethodMemberSpec.param_type_refs`（member.py）
- [x] 将函数返回类型、成员类型、容器元素类型的字符串引用逐步映射到 `TypeRef`。
- [x] 更新编译器 side table 与符号表接口，使其可同时读取旧表示与 `TypeRef`。
  - `SpecRegistry.resolve_typeref(ref: TypeRef)` 新增（registry.py）
- [x] 为跨模块类型引用补齐统一表达与解析路径。
  - `TypeRef.of(name, module)` 标准化跨模块引用
  - `resolve_typeref()` 先尝试带模块限定符，再回落到裸名
- [x] 补充最小回归测试：嵌套泛型、跨模块返回类型、成员访问类型传播。
  - 测试文件：`tests/kernel/test_typeref.py`（103 个测试用例）

**M1 DoD**
- [x] 编译器和解释器均可读取 `TypeRef`。
- [x] 现有功能行为不变，测试基线保持通过（1056 → 1159，+103 新测试）。

### M2：Optional[T] 与空安全落地

- [x] 引入 `Optional[T]` 的首批类型表示与注册表特化入口。
  - `OptionalSpec` 新增：`wrapped_type_name` / `wrapped_type_module`
  - `SpecFactory.create_optional()` 新增
  - `OptionalAxiom` 新增并注册到 `AxiomRegistry`
  - `SpecRegistry.resolve_specialization(Optional, [T])` / `resolve_typeref(Optional[T])` 已可用
- [x] 移除/冻结旧 `nullable` 布尔语义入口，改为类型层显式表达。
  - 兼容说明：`is_nullable` 字段保留为迁移期数据字段，但不再参与 `is_assignable` 的可空判定。
- [x] 调整赋值检查首批规则：非 Optional 类型禁止接收 `None`；`Optional[T]` 接受 `T` / `None` / `Optional[T]`。
- [x] 提供 Optional 基础能力（如 `or_else` / `unwrap` 等）及语义文档。
- [x] 完成语义分析器中的可空性检查迁移。

**M2 DoD**
- [x] 可空逻辑仅由 `Optional[T]` 驱动。
- [x] 空安全相关用例完整覆盖。

### M3：TypeDef 单一化（替代多 Spec）— ✅ 完成（2026-05-08）

- [x] 设计并落地统一 `TypeDef`（以 `kind` 区分语义类别）。
- [x] 将旧多 Spec 结构迁移到 `TypeDef` 统一表示。
- [x] 重写注册表查询入口：统一返回 `TypeDef` 兼容结构（`kind` 驱动）。
- [x] 清理关键路径 `isinstance(SpecX)` 分支，改为 `kind` + 通用字段路径。
- [x] 更新序列化/反序列化协议到单一结构（统一使用 `kind` 协议）。
- [x] **彻底字段命名清洗（2026-05-08）**：
  - 所有扁平 `*_name` / `*_module` 字符串对字段全部下沉为单一 `TypeRef` 字段
  - `param_types: List[TypeRef]`、`return_type / parent_type / element_type / key_type / value_type / wrapped_type / receiver_type: TypeRef`、`allowed_element_types: List[TypeRef]`
  - 标量便利 @property 全部删除（`return_type_name/_module`、`element_type_name/_module`、`key_type_name/_module`、`value_type_name/_module`、`wrapped_type_name/_module`、`receiver_type_name/_module`、`MemberSpec.type_name/_module`、`parent_name/_module`、`allowed_element_type_names`）
  - 47+ 处读取点全部迁移到 `.X.head` / `.X.module` / TypeRef 直接访问
  - 序列化 / 反序列化协议保留 `parent_name` / `parent_module` / `return_type_name` 作为**线协议字段**（写盘格式），但 in-memory 模型纯 TypeRef
  - 仅保留 `param_type_names` / `param_type_modules` 作为列表迭代便利视图（无标量等价物，纯只读派生）

**M3 DoD**
- [x] Spec 体系逻辑等价迁移完成。
- [x] 关键路径不再依赖旧 Spec 子类判断。
- [x] In-memory 字段命名彻底清洗，无双重表示残留。

### M3→M5 补充：callable-instance 路线 — ✅ 完成（2026-05-08）

- [x] `TypeKind.DEFERRED` + `TypeKind.BEHAVIOR` 合并为 `TypeKind.CALLABLE_INSTANCE`
- [x] `TypeDef.deferred_mode` 字段彻底删除（capture mode 不属于类型层语义）
- [x] 全局重命名：`deferred_mode` → `capture_mode`、`is_deferred` → `is_callable_instance`、`set_deferred` → `set_callable_instance`、`node_is_deferred` → `node_is_callable_instance`、`node_deferred_mode` → `node_capture_mode`
- [x] 序列化通道：`type_data["axiom_name"]` 取代旧 `type_data["capture_mode"]`，反序列化通过 axiom name (`"fn_callable"` / `"behavior"`) 还原原始公理路由
- [x] AST、运行时值、blueprint、side table、registry API 全栈一致

**注**：运行时值类 `IbFnCallable` / `IbBehavior` 是独立 Python 类（M4 范畴）。

### M4：运行时值模型单一化（IbValue）

- [x] 引入统一 `IbValue(type_ref, fields, payload, meta)` 模型。
- [x] 将内置值对象族迁移到 `IbValue` 承载模式（`IbInteger` / `IbFloat` / `IbString` / `IbBool` / `IbList` / `IbTuple` / `IbDict` / `IbNone` / `IbLLMUncertain` / `IbLLMCallResult` / `IbFnCallable` / `IbBehavior` 统一转为 `IbValue` 子体系）。
- [x] 运行时装箱产物统一具备 `type_ref + payload + fields + meta` 四元结构；旧类名保留为兼容包装层，避免一次性打断现有执行路径与测试。
- [x] 运行时序列化 / 调试 /值访问路径已切换到 `IbValue` 中心模型。

**M4 DoD**
- [x] 运行时值层已有统一抽象入口（`IbValue`）。
- [x] 对外语义不变，核心执行路径回归通过（1184 passed）。

### M5：Axiom 接口统一化

- [x] 将现有分散 capability 协议收敛到统一 Axiom 接口。
- [x] 编译期类型推断与运行期行为分发共享同一 Axiom 注册入口。
- [x] 清理重复 capability 粘合代码，保留必要扩展点。
- [x] 完善 Axiom 文档：编译期职责、运行时职责、LLM 协议职责。

**M5 DoD**
- [x] Axiom 成为唯一类型行为入口。
- [x] 旧 capability 兼容层按计划下线。

**M5 收口要点（2026-05-08）**

- 单一 `TypeAxiom` Protocol 替代旧 `CallCapability` / `IterCapability` / `SubscriptCapability` / `OperatorCapability` / `ConverterCapability` / `ParserCapability` / `FromPromptCapability` / `IlmoutputHintCapability` / `WritableTrait` 九个协议子类。
- 公理通过 `has_*_cap` 类属性声明能力，`BaseAxiom` 提供安全 no-op 默认。具体公理不再多重继承能力 mixin，亦不再写 `get_X_capability(): return self` 样板。
- `SpecRegistry.get_X_cap(spec)` 在公理声明对应能力时返回公理本身（结构性可调用 `FuncSpec` / `BoundMethodSpec` / `ClassSpec` 时返回 spec 自身作 truthy marker），否则返回 `None`，保持调用方 `if cap: cap.method()` 习惯。
- 删除 `_FUNC_SPEC_CALL_CAP` 哨兵类与 `WritableTrait` 不可达回填路径，函数 spec 元数据回填全部走 `factory.create_func()`。
- 测试基线维持 1184 passed；净删减约 400 行旧粘合代码。

### M3→M5 补充：`fn` / `lambda` / `snapshot` 可调用实例统一路线

- [x] 将"deferred（延迟求值）"从主类型概念中彻底移除，统一为"可调用实例（callable instance）"语义（`fn_callable`）。
- [x] 明确 `lambda` / `snapshot` 仅作为**右值表达式包装关键字**，不再作为左值声明语义。
- [x] 统一 `fn` 左值关键字语义：
  - [x] 作为可调用实例推导入口（类似 `auto`，但限定 callable）
  - [x] 作为高阶函数类型标注入口（参数/返回签名约束）
- [x] 在 TypeRef/TypeDef 中补齐 callable 实例结构表达，避免 `fn` 哨兵路径导致返回类型退化为 `void`。
- [x] **`fn` callable 实例统一调用分发（M3→M5 补充）** — Axiom 层统一 callable 分发：`FuncSpec` / `lambda` / `snapshot` / `behavior` 全部走 `TypeAxiom` + `has_call_cap` 协议。
- [x] 固化 `lambda` vs `snapshot` 差异语义：
  - [x] `lambda`：引用捕获（读最新值）
  - [x] `snapshot`：值拷贝捕获（冻结定义时值）
  - [x] 二者在意图栈作用域上的差异由统一 callable 语义承载（`fn_callable`/`behavior`）
- [x] callable-instance 路线已收口，原 `fn` 失败用例约束不再适用。

**补充 DoD**
- [x] `fn` 高阶参数/返回值调用链可稳定推导返回类型，不再出现 `void` 回退。
- [x] 测试与主文档已切换到“可调用实例构造”表述；历史归档文档保留旧术语并显式标记为历史记录。
- [x] `deferred` 概念已从整个代码库中彻底删除，以 `fn_callable` 替代。

---

## 3. 交付节奏与管控

- [ ] 每个里程碑单独提交并保持可回滚。
- [ ] 每个里程碑结束后更新 `docs/NEXT_STEPS.md` 进度。
- [ ] 每个里程碑结束后记录测试基线变化。
- [ ] 出现架构分歧时，以本任务文档 + 架构设计文档为唯一裁决依据。

---

## 4. 风险清单

- [ ] 大规模类型表示迁移导致编译器/解释器边界回退耦合。
- [ ] 兼容期双表示并存导致隐性分支膨胀。
- [ ] 运行时值模型单一化期间出现行为漂移。
- [ ] 泛型递归替换在边界场景（嵌套/跨模块）出现回归。

---

## 5. 非目标（当前阶段不做）

- [ ] 不引入历史兼容负担之外的新语法糖扩展。
- [ ] 不在本专项中推进目标语言后端实现。
- [ ] 不把低优先级模块治理任务混入类型系统主线。

---

## 6. 关联文档

- 架构原文：`docs/IBCI_TYPE_SYSTEM_FROM_ZERO_ARCHITECTURE.md`
- 主进度看板：`docs/NEXT_STEPS.md`
- 低优先级待办：`docs/PENDING_TASKS.md`
