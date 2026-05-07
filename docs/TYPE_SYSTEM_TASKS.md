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
- [ ] **M2：Optional[T] 与空安全落地**
- [ ] **M3：TypeDef 单一化（替代多 Spec）**
- [ ] **M4：运行时值模型单一化（IbValue）**
- [ ] **M5：Axiom 接口统一化**

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

- [ ] 引入 `Optional[T]` 作为标准可空表达。
- [ ] 移除/冻结旧 `nullable` 布尔语义入口，改为类型层显式表达。
- [ ] 调整赋值检查：非 Optional 类型禁止接收 `None`。
- [ ] 提供 Optional 基础能力（如 `or_else` / `unwrap` 等）及语义文档。
- [ ] 完成语义分析器中的可空性检查迁移。

**M2 DoD**
- [ ] 可空逻辑仅由 `Optional[T]` 驱动。
- [ ] 空安全相关用例完整覆盖。

### M3：TypeDef 单一化（替代多 Spec）

- [ ] 设计并落地统一 `TypeDef`（以 `kind` 区分语义类别）。
- [ ] 将旧多 Spec 结构迁移到 `TypeDef` 统一表示。
- [ ] 重写注册表查询入口：统一返回 `TypeDef`。
- [ ] 清理 `isinstance(SpecX)` 分支，改为 `kind` + 通用字段路径。
- [ ] 更新序列化/反序列化协议到单一结构。

**M3 DoD**
- [ ] Spec 体系逻辑等价迁移完成。
- [ ] 关键路径不再依赖旧 Spec 子类判断。

### M4：运行时值模型单一化（IbValue）

- [ ] 引入统一 `IbValue(type_ref, fields, payload)` 模型。
- [ ] 将内置值对象族逐步迁移到 `IbValue` 分发模式。
- [ ] 运行时操作统一走 Axiom 协议，不直接暴露 Python 类型行为。
- [ ] 移除冗余值对象层与重复分发逻辑。

**M4 DoD**
- [ ] 运行时值层只有统一抽象入口。
- [ ] 对外语义不变，核心执行路径回归通过。

### M5：Axiom 接口统一化

- [ ] 将现有分散 capability 协议收敛到统一 Axiom 接口。
- [ ] 编译期类型推断与运行期行为分发共享同一 Axiom 注册入口。
- [ ] 清理重复 capability 粘合代码，保留必要扩展点。
- [ ] 完善 Axiom 文档：编译期职责、运行时职责、LLM 协议职责。

**M5 DoD**
- [ ] Axiom 成为唯一类型行为入口。
- [ ] 旧 capability 兼容层按计划下线。

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
