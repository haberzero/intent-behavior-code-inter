# 通信领域设计完善与统一化 —— 全方位审查记录（2026-08-04）

> 本文件记录对**线程对象模型方向修正（任务 C-F，2026-08-04 自主推进）**的代码全方位审查结果，以及**通信领域（chan/signal/slot）设计完善与统一化检查**的前置审查。
> 审查方法：三个独立 subagent 并行审查 + 对关键证据的直接代码核验。
> 目的：为下一主线（通信领域设计完善）提供完整的问题清单与根因分析。
> **最后更新**：2026-08-04

---

## 一、审查范围与方法

- **范围**：昨天自主推进的线程对象模型方向修正代码（任务 C-F），含线程对象、结果容器、统一泛型模型、err 类型、序列化、清理；以及通信领域（chan/signal/slot）现状。
- **方法**：三个并行 subagent 分别审查（① 线程对象模型一致性 ② 泛型模型/spec 一致性 ③ 通信机制与构造链），随后对关键断言逐一读代码/实跑核验。
- **测试基线**：`python -m pytest tests/` = **1453 passed / 4 skipped**（全绿，但多个缺陷未被测试覆盖）。

---

## 二、已实锤的真实 bug（直接证据核验过）

| # | Bug | 证据 | 严重性 |
|---|-----|------|--------|
| **B1** | **`thread_result` 序列化往返丢数据**：`IbThreadResult` 不是 `IbValue`（`issubclass(IbThreadResult, IbValue) == False`），导致 `runtime_serializer.py:270` 的 `isinstance(obj, IbValue) and cls_name == "thread_result"` 守卫**永不触发** → 序列化为 `{"_type":"object","fields":{}}`，value/error/status 全部静默丢失；反序列化分支（`runtime_serializer.py:582-588`）因此不可达。**任务 C5 声称"已完成"实为半接通**。 | 实测序列化输出 | **high** |
| **B2** | **循环导入**：`thread_result.py:31` `from .primitives.optional import IbOptional`，而 `primitives/__init__.py:9` 反向 `from ..thread_result import IbThreadResult`。直接 `import core.runtime.objects.thread_result` 触发 `ImportError`（依赖先导 primitives 的隐式顺序存活）。分层违规（primitives 包反向再导出包外兄弟模块）。 | 实测 ImportError | **high** |
| **B3** | **`GenericTypeRegistry._by_kind` 索引有损**：共享 kind 后注册者覆盖先注册者——`get_by_kind("callable_instance")` 返回 `behavior`（fn_callable 丢失）；`get_by_kind("task")` 返回 `thread`。承诺"按 kind 索引供序列化/还原复用"不能成立。 | 实测注册表 | medium |
| **B4** | **VP-4 未修**：`vm/handlers/comm.py:32-35`（`_get_comm_registry`）与 `:51-54`（`_get_coordinator`）的 `except Exception: pass` 兜底**原址仍在**。任务 E（commit b0fe530）声称已处理，实际未清。setattr 失败被静默吞掉 → 注册表/协调器每次调用重建，真错被掩盖。 | 亲读代码 | medium |

---

## 三、六大同构 / 碎片化问题（subagent 报告 + 交叉验证）

### G1. 值对象状态承载模式四套并存（机制同构破坏）

| 模式 | 代表 | 位置 |
|------|------|------|
| `__slots__=("core",)` | IbChannel/IbSignal/IbSlot | `kernel/comm.py:33/86/107` |
| `fields` 承载普通 IbObject | IbThread | `objects/thread.py:49-64` |
| `__slots__` + `payload` 双载 | IbOptional | `primitives/optional.py:21-26`（`_inner` 与 payload 同引用双存） |
| `payload` 单载 | 标量值 | `kernel/base.py:186-194` |

- **根因**：`IbClass.instantiate`（`kernel/ib_class.py:86`）硬编码 `instance = IbObject(self)`——thread 实例永远是普通 `IbObject`，`__init__` 原生函数拿到的 receiver 无实现类槽位，状态只能塞 fields。`IbThread` 类**从不成为实例类型**，只是"字段操作函数命名空间"（axiom auto-bind 把其方法绑到类 vtable）。
- **后果**：`IbThreadResult` 不是 IbValue → 无 `type_ref` → `thread_result[int]` 泛型身份在运行时丢失（B1 根因）。
- **附带**：`IbThread` 用模块级 `_ensure_started` 函数（`thread.py:184-196`）绕路——实例非 IbThread，`self._ensure_started()` 不可用。

### G2. 状态枚举三写真相

- `_ThreadState`（`thread.py:39-46`，5 态）+ `_ThreadResultStatus`（`thread_result.py:34-39`，3 态，语义子集）+ 序列化裸字符串 `"done"`（`runtime_serializer.py:273/585`）。
- `thread.py join()` 手动映射 `_ThreadState → _ThreadResultStatus`（`:144-148`），139-148 两段平行 if/else 只为让两套常量同源。
- 改名/加态需四处联动，无编译器保护。违反"单一权威源"。

### G3. thread 复用已删除 task 的 kind（历史包袱挂统一机制）

- `thread` 用 `TypeKind.TASK.value`（task 类型已删，commit 24baa3e，但 kind 值保留）；`thread_result` 新建 `TypeKind.THREAD_RESULT`——兄弟类型不同构。
- 正确性依赖 `_axiom_name="thread"` 在 5 处调用点（factory/specs/_members/serializer/rehydrator）各写一遍的**隐藏不变量**；kind 本身不再标识类型身份。
- `base.py:61` `TASK = "task"  # 任务句柄（spawn/join/cancel 载体）` 注释仍是删掉的关键字时代；`base.py:257` `_KIND_BASE_NAMES[TASK]="task"` 指向已删除类型名。
- **实测陷阱**：TASK 无 `_axiom_name` 时 `get_base_name()=="task"`（指向已删类型）；THREAD_RESULT 无 `_axiom_name` 时方括号漏进 head。

### G4. 序列化 / 还原机制三套并行（单一权威源未兑现）

| 路径 | 状态 |
|------|------|
| 注册表 `to_typeref` | **生产路径死代码**（仅 `tests/kernel/test_generic_model.py` 调用） |
| `serializer.py` 硬编码 kind 分支 | thread 靠 `kind==TASK and get_base_name()=="thread"` 双判；thread_result 靠纯 kind 独占——判断模式不统一 |
| `rehydrator.py` | `startswith("thread")` 字符串嗅探 + `name or "task"` 幽灵回退分支（kind 丢失、静默降级 PRIMITIVE） |

- `TypeRef.from_spec`（`type_ref.py:117-180`）无 TASK/THREAD_RESULT 分支 → `thread_result[int]` 值对象序列化落成 `TypeRef("thread_result")`，泛型参数丢失。
- `_to_typeref_callable`（`generic.py:174-179`）以"callable"之名服务 thread/thread_result 两个非 callable 类型，掩盖语义差异。
- thread_result 水化"shell 一次成型"，thread 水化"shell + fill 两阶段耦合"——两套机制。

### G5. 线程协调器归属碎片化（领域分离刺穿）

- `_get_coordinator`（thread 协调器访问器）寄居**通信模块** `vm/handlers/comm.py:39-55`；`primitive_initializer.py:615` thread 构造导入它。
- 与方向修正最高原则"async 与 thread 必须彻底分离"、"thread 是一等对象"矛盾——线程领域依赖通信 handler。
- 附带：`_get_comm_registry` / `_get_coordinator` 均含 `try/except Exception: pass`（见 B4）。

### G6. Signal 功能空壳 + 双 Signal 撞名

- `signal("cancel")` 创建**纯惰性数据**：`SignalAxiom` 无 `get_method_specs` 覆盖（`comm.py:112-120`）→ 语言层零方法；无投递/接收/广播机制；"定向/广播/抢占式/一次性"仅 docstring。
- **双 Signal 撞名**：VM 控制流 `Signal`（`shared/signals.py:29-45`，frozen dataclass + `ControlSignal` Enum，有真实帧栈传播机制）vs 通信 `SignalCore`（`shared/comm/signal.py`，frozen dataclass + `SIGNAL_KINDS` str 白名单，空壳）——双 kind 词汇表，一真一空。
- 口径矛盾：`PENDING_TASKS.md:20` 宣称 PT-MT-3"已完成"，`ast.py` docstring 写"创建/**发送** Signal"，但实际零投递机制。

### G7. 通信领域其它半成品（subagent 报告）

- **pubsub 语言层不可达**：`IbChannel` 无 `subscribe`（`kernel/comm.py:29-79`），`ChannelAxiom` 未声明（`comm.py:100-106`）→ `chan(pubsub)` 可创建、不可订阅、`recv()` 即抛 `CommClosedError`。
- **`send_nowait` 无订阅者"丢弃返回 True"**（`channel.py:79-81`）：与 message/stream 模式 `False=拒绝` 语义不对称——广播丢弃被报告为"投递成功（被零人接收）"。
- **订阅者无界缓存无失效机制**：`channel.py:121` 硬编码 `CommBuffer(0)`（纯无界 deque），注释声称"设计 D5：默认无界，可配置"但 `subscribe()` 无 size 参数——"可配置"是空头支票。触碰 code-quality"无失效机制的无界缓存"红线。
- **线程协调器构造无契约校验**：`_thread_init`（`primitive_initializer.py:605-637`）无 spec，`instantiate` 实参校验被 `init_method.spec` 门控（`ib_class.py:142-151`）→ 构造契约无校验，纯按 `args[0]/args[1]` 索引读取。
- **构造签名双真值源**：chan 的构造签名烤进 parser 关键字（mode/buffer/name），thread 的构造签名只存在于运行时 param_meta——双源真值。

---

## 四、根因归纳

1. **`instantiate` 不可挂钩**（`ib_class.py:86` 硬编码普通 IbObject）→ 值对象构造机制无法统一 → G1/G2/G4 连锁碎片 + B1/B2。
2. **方向修正清理不彻底** → TASK kind 残留（G3）、comm 模块归属（G5）、VP-4 未修（B4）、SpawnedTask 结构性 Waitable 残留（协调器.py:45-50 注释仍说"结构性满足 Waitable"）。
3. **完成口径高估** → C5"序列化"实为半接通（B1）、PT-MT-3"已完成"实为占位（G6/G7）。
4. **join/cancel 公理返回类型仍是 any 兜底**：`ThreadAxiom.get_method_specs` 声明 `"join": _m("join", ret="any")`（`comm.py:42`）——"禁止 any 兜底"裁定仅靠 `_members.py:121-127` 硬编码特判补救；`_members.py:53-140` 的特化逻辑已成长成 per-type if/elif 级联（list/dict/Optional/thread/thread_result），机制碎片化在扩张。

---

## 五、审查完整性问题（未全覆盖项）

- 序列化 thread/thread_result 分支（`serializer.py:187-197`、`rehydrator.py:142-150`）**无任何测试断言**（grep `value_type_name/value_type_module` 于 tests/ 无命中）——这是 B1 未被发现的原因。
- `TypeRef.from_spec` 对线程类型的处理缺失未验证具体影响路径。

---

## 六、修复方向建议（供下一 session 参考，非最终方案）

按工作模式定论（质量优先、不留历史包袱、原则优先于行为维持），建议三阶段：

1. **先修实锤 bug**：B1（thread_result 序列化，含补测试）、B2（循环导入）、B4（VP-4）——低风险高价值。
2. **统一值对象机制**：解决 `instantiate` 不可挂钩根因（G1）——统一状态承载，顺带消除 G2/G4 碎片。此为架构级改造，方案需设计审查（候选：值对象专用构造入口 / `__init__` 返回实例 / factory 注入）。
3. **通信领域设计完善**：Signal 投递语义设计（G6）、pubsub 语言层打通（G7）、TASK kind 清理（G3）、协调器归属修正（G5）。

> 本文件是审查记录。修复实施走 `code-workflow`，实施后核验回 `code-review`。详细决策与进度记录于 `WORKLOG.md` 与 `_HANDOFF.md`。
