# IBCI 类型系统设计说明（当前正式版）

> 本文档描述**当前代码状态**下的正式类型系统设计。
> 旧阶段文档仅作历史参考，不作为现行规范。
>
> 最后更新：2026-05-08

---

## 1. 核心目标

- 编译期与运行期共享统一类型模型
- 类型引用统一为 `TypeRef`
- 类型定义统一为 `TypeDef`
- 类型行为统一经 `TypeAxiom` 分发

---

## 2. 核心数据结构

### 2.1 TypeRef（类型引用）
- 结构化表示：`head + module + args`
- 用于跨模块与泛型引用

### 2.2 TypeDef（类型定义）
- 单一类型定义模型，按 `kind` 区分语义
- 关系字段统一使用 `TypeRef`
- 不再接受历史 `*_name/*_module` 旧式 kwargs

### 2.3 TypeKind 关键状态
- `CALLABLE_INSTANCE` 已统一承载历史 deferred/behavior 类型分支
- `capture_mode` 不属于类型层，归属 AST/运行时值层

---

## 3. 公理层接口

- 统一协议：`TypeAxiom`
- 能力声明：`has_*_cap` 类属性
- `SpecRegistry.get_X_cap()` 统一返回公理对象或结构化 spec 标记

---

## 4. callable-instance 语义

- `lambda` / `snapshot` 在右值中构造 callable-instance
- `fn` 在左值中：
  - 作为可调用实例推导入口（类似 auto，但限定 callable）
  - 作为高阶函数签名标注入口：`fn[(...)->(...)]`

---

## 5. 运行时值模型接口关系

- 运行时统一值承载：`IbValue(type_ref, payload, fields, meta)`
- 兼容类名（如 `IbInteger` / `IbBehavior`）保留为实现层封装
- 类型分发应以 `IbValue + ib_class.name` 为准，而非历史具体类分支

---

## 6. 当前已知后续焦点（非类型主线）

- `fn` 在泛型/高阶函数路径上的表达与推导增强
- callable-instance 相关历史术语与命名收敛
- 与 VM/Intent 语义交叉处的边界一致性（特别是 lambda/snapshot 与意图栈）
