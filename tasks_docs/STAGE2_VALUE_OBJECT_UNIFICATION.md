# 阶段 2 设计：统一值对象机制（instantiate 可挂钩 + G1/G2/G4）

> 状态：**设计待实施**（设计评审后开工）
> 依据：`tasks_docs/COMMS_DESIGN_REVIEW.md` 阶段 2 + §四 根因归纳 1
> 原则：工作模式定论 + design-philosophy（单一权威源 / 机制同构 / 设计语言统一）+ 独立分支政策（本改造跨核心构造路径，危害程度无法预先确认 → 独立分支实验，确认路线后手动更新 unsafe-vibe-dev）
> 最后更新：2026-08-04

---

## 一、问题（G1 根因）

`IbClass.instantiate`（`core/runtime/objects/kernel/ib_class.py:86`）硬编码 `instance = IbObject(self)`：
- 任何 `ClassName(...)` 语言构造产生的实例**永远**是普通 `IbObject`，Python 实现类（`get_ib_implementation(name)`）从不成为实例类型。
- 后果：值对象状态承载四模式并存（G1）——core 槽（chan/signal/slot）/ fields 承载（thread）/ `__slots__`+payload 双载（Optional）/ payload 单载（标量）；`IbThreadResult` 非 IbValue → 无 type_ref → 泛型身份丢失（B1 深根因）；thread 方法退化为模块级函数操作 fields（`_ensure_started`）。

## 二、设计（技术路线）

### D1. instantiate 挂钩 —— 协议驱动 `_create_blank`

在 `IbObject` 增加类方法 `_create_blank(ib_class)`（默认返回 `IbObject(ib_class)`，即现行为）。值对象实现类覆写返回其类型化空实例。`instantiate` 改为：

```python
impl_cls = get_ib_implementation(self.name)
instance = impl_cls._create_blank(self) if impl_cls is not None else IbObject(self)
```

- 协议驱动（非 `if 能力标志位` 硬编码分发）：类是否产生类型化实例由其 `_create_blank` 覆写决定。
- 前向兼容：用户类（impl None）与未覆写的内核类（默认返回普通 IbObject）行为不变。
- 避免特化 agent（仅 general）。本方案为"值对象专用构造入口"候选，未选"__init__ 返回实例"（破坏 Python 构造语义）与"factory 注入"（增加注册表耦合）。

### D2. thread 值对象化（消除 G1 "fields 承载" 模式）

- `IbThread` 状态从 `fields` 迁移到 `__slots__`（`_coordinator`/`_spawned`/`_callable`/`_args`/`_state`）。
- 方法（start/join/cancel/is_done）改为真实例方法；删除模块级 `_ensure_started` 与静态 `_init_fields`（实例非空壳，不再需要绕路）。
- `_create_blank` 返回 `IbThread(ib_class)`（Python `__init__` 仅做空槽位初始化；语言层 `__init__` 仍是 `_thread_init`，无命名冲突——ThreadAxiom 不声明 `__init__`）。
- 消费方同步：`primitive_initializer._thread_init` 写槽位；`runtime_serializer` thread_transient 分支读槽位。

### D3. thread_result → IbValue（修复 B1 深根因）

- `IbThreadResult` 继承 `IbValue`，`payload` 承载成功值，保留 `_status`/`_error` 槽位；`super().__init__(ib_class, payload=value)` 使 `type_ref` 生效。
- 序列化守卫已按类名分发（阶段 1），升级为 IbValue 后仍命中，无需改动。

### D4. G2 状态枚举统一（单一权威源）

- 新单一枚举 `ThreadStatus`（IDLE/RUNNING/DONE/CANCELLED/FAILED）替换 `_ThreadState`（thread.py）与 `_ThreadResultStatus`（thread_result.py）两套常量。thread 用全 5 态，thread_result 用子集 3 态；序列化字符串与枚举 `.value` 同源。

### D5. G4 序列化/还原统一

- `TypeRef.from_spec`（`type_ref.py:118`）补 TASK / THREAD_RESULT 分支 → `thread_result[int]` 泛型实参保留。
- `artifact_rehydrator.py:142-146` 移除 `startswith("thread")` 字符串嗅探与 `name or "task"` 幽灵回退 → TASK 分支直接 `create_thread`（task 类型已删除，回退为死路径）。
- `generic.py:174-179` `_to_typeref_callable` 以"callable"之名服务 thread/thread_result（非 callable）——拆为专用 `_to_typeref_thread`/`_to_typeref_thread_result`（语义名实相符）。

## 三、涉及文件

| 文件 | 变化 |
|------|------|
| `core/runtime/objects/kernel/ib_class.py` | instantiate 挂钩 `_create_blank` |
| `core/runtime/objects/kernel/base.py` | `IbObject._create_blank` 默认实现 |
| `core/runtime/objects/thread.py` | 槽位状态 + 实例方法 + 单一枚举 + `_create_blank` |
| `core/runtime/objects/thread_result.py` | 继承 IbValue + payload + 单一枚举 |
| `core/runtime/bootstrap/primitive_initializer.py` | `_thread_init` 写槽位 |
| `core/runtime/serialization/runtime_serializer.py` | thread_transient 读槽位 |
| `core/kernel/spec/type_ref.py` | from_spec TASK/THREAD_RESULT 分支 |
| `core/runtime/loader/artifact_rehydrator.py` | 移除嗅探 + 幽灵回退 |
| `core/kernel/spec/generic.py` | `_to_typeref` 拆分 |
| 测试 | thread/thread_result/serialization 系列同步 |

## 四、验证

- 每子任务全量 `python -m pytest tests/` 零回归（在独立分支上）。
- 关键断言：thread 实例 `isinstance(instance, IbThread)`；`thread_result[int]` type_ref 泛型实参保留；序列化往返保真。

## 五、决策记录

- 独立分支执行（危害程度无法预先确认，触碰最核心构造路径）。分支名：`comms-stage2-valueobj`。
- `_create_blank` 命名与默认行为：默认返回普通 IbObject 保证零行为变化；覆写即升级为类型化实例。
- 不在阶段 2 处理：Optional 双载收敛、chan/signal/slot 序列化空壳（G7 属阶段 3）、TASK kind 本体清理（G3 属阶段 3）。

## 六、待决

- 无。技术路线已定，分支实施。
