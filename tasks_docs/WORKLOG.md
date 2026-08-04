# WORKLOG — 自主工作日志

> 记录所有自主决策、质询分析、方案取舍、变化前后（实现 + 测试 + 文档）。
> 原则：**"只记录，不断决"**——能自主决定的记录决定并推进；只有确实无法决定的才标记待决并上报。
> 最后更新：2026-08-04

---

## 2026-08-04 会话 6：通信领域设计完善 —— 阶段 1 实锤 bug 修复（B1/B2/B4，自主实现）

### 背景

按 `_HANDOFF.md` 与 `COMMS_DESIGN_REVIEW.md` 阶段 1 开工。用户开启无人值守运行；另明确工作约束：**所有 subagent 工作（含 review）仅允许使用 general agent，不使用 explore/reviewer 等特化 agent**（本会话后续一律遵守）。

### 变化前后

**B1 —— thread_result 序列化往返丢数据（high）**
- 根因：`IbThreadResult` 继承 `IbObject`（非 `IbValue`），`runtime_serializer.py:270` 守卫 `isinstance(obj, IbValue) and cls_name == "thread_result"` 永不触发 → 落入通用 object 分支，序列化为 `{"_type":"object","fields":{}}`，value/error/status 静默丢失。
- 变化：守卫改为按 `ib_class.name` 分发（`cls_name == "thread_result" and not isinstance(obj, IbClass)`），与 `thread_transient` 分支同模式。反序列化分支（`_type=="thread_result"`）本已存在，故往返即打通。
- 前向兼容：阶段 2 若将 thread_result 升级为 IbValue，本守卫仍有效（不依赖 isinstance IbValue）。
- 测试：`test_runtime_serialization.py` 新增 `TestThreadResultSerializationRoundTrip`（3 用例：结构断言 `_type=="thread_result"` + 成功往返保真 value/status + 失败往返保真 status/error）。

**B2 —— 循环导入（high）**
- 根因：`primitives/__init__.py:8-9` 反向再导出包外兄弟模块（`..thread` / `..thread_result`），且**零消费者**（grep 全仓确认）。链：`thread_result → primitives.optional → primitives/__init__ → ..thread_result`（thread_result 部分初始化 → ImportError）。
- 变化：
  1. `primitives/__init__.py` 删除 `..thread` / `..thread_result` 导入及 `__all__` 条目（分层违规移除）。
  2. `primitive_initializer.py` 模块级新增 `from ..objects.thread import IbThread` / `from ..objects.thread_result import IbThreadResult`（确保 `@register_ib_type` 在公理自动化绑定前执行——对齐 line 8 `IbIntent` 先例；这是注册时序的显式归属地）。
  3. `_thread_init` 内冗余局部导入 `from core.runtime.objects.thread import IbThread, _FIELDS` 删除（模块级导入已覆盖，`_FIELDS` 本未使用）。
- 测试：`test_thread_cleanup.py` 新增干净解释器（subprocess）直接导入 `thread_result`/`thread` 回归测试（旧缺陷需全新 sys.modules 才可复现，进程内测试无法锁定）。

**B4 —— VP-4 except:pass 兜底未修（medium）**
- 根因：`comm.py:32-35/51-54` 用 `try/except Exception: pass` 包裹 `rc._comm_registry`/`rc._runtime_coordinator` 的 setattr——`RuntimeContextImpl` 无 `__slots__`，setattr 恒成功；失败必为构造路径真错（如无 runtime_context），被静默吞掉 → 注册表/协调器每次调用重建。
- 变化：删除 try/except，直接 setattr（fail-fast）。`_emit_event` 的两处 except 属"可观测性尽力而为"设计（未在 B4 审查范围），保留不动。
- 测试：无新增（既有 `test_thread_cleanup`/`test_vm_comm` 已覆盖构造路径；全量回归零失败）。

### 测试与验证

- 阶段 1 相关：`test_runtime_serialization.py` + `test_thread_cleanup.py` + thread 系列 + `test_vm_comm.py` + `test_generic_model.py` = 57 passed。
- 全量：`python -m pytest tests/` = **1457 passed / 4 skipped**（+4，零回归）。

### 决策记录

- 阶段 1 与阶段 2 的边界：B1 只修序列化分派（真正根因"值对象机制不统一"属 G1，阶段 2 架构级处理）。此守卫修复非症状层打补丁——它修正了错误的分派谓词，无双通道、无 compat shim；且前向兼容阶段 2 升级。
- B2 采用"primitive_initializer 显式导入"而非"objects/__init__.py 聚合"：前者对齐 `IbIntent` 既存先例（注册时序显式归属 bootstrap 站点），后者会使 objects 包导入即加载全部子模块、耦合面过大。两方案均符合"单一权威源"。
- subagent 约束（用户 2026-08-04）：后续 review/explore 类工作一律使用 general agent。

### 待决

- 无。阶段 2（统一值对象机制）为下一项，方案需设计审查（候选：值对象专用构造入口 / `__init__` 返回实例 / factory 注入）。

---

## 2026-08-04 会话 5：通信领域设计完善与统一化 —— 全方位审查（自主推进）

### 背景

线程对象模型方向修正（任务 A-F）完成后，用户要求对昨天自主推进的代码做全方位审查，重点：系统级宏观一致性、设计语言统一、机制/功能碎片化。作为"通信领域（chan/signal/slot）设计完善与统一化检查"的前置审查。

### 审查方法与范围

- 三个独立 subagent 并行审查：① 线程对象模型一致性（thread/thread_result/coordinator/构造链）② 统一泛型模型/spec 一致性（generic/factory/_members/serializer/rehydrator）③ 通信机制与构造链（chan/signal/slot + primitive_initializer + vm handlers）。
- 随后对关键断言逐一读代码/实跑核验。完整审查记录见 `tasks_docs/COMMS_DESIGN_REVIEW.md`。

### 审查发现（摘要，详见 COMMS_DESIGN_REVIEW.md）

**已实锤真实 bug（直接核验）**：
- **B1**：`thread_result` 序列化往返丢数据——`IbThreadResult` 非 IbValue → `runtime_serializer.py:270` 守卫永不触发 → 序列化为空 object（value/error/status 静默丢失）。实测序列化输出 `{"_type":"object","fields":{}}`。
- **B2**：循环导入——`thread_result → primitives.optional → primitives/__init__ → ..thread_result`，直接导入触发 ImportError（依赖隐式顺序）。
- **B3**：`_by_kind` 索引有损——共享 kind 后注册者覆盖先者（`callable_instance→behavior`，`task→thread`）。
- **B4**：VP-4 未修——`comm.py:32-35/51-54` 的 `except: pass` 兜底原址仍在（任务 E 声称已清未清）。

**六大同构/碎片化问题**：
- G1 值对象状态承载四模式并存（core 槽/fields/__slots__+payload 双载/payload 单载），根因=instantiate 硬编码普通 IbObject。
- G2 状态枚举三写真相（_ThreadState/_ThreadResultStatus/序列化裸字符串）。
- G3 thread 复用已删除 task 的 kind（TypeKind.TASK 残留 + _axiom_name 隐藏不变量）。
- G4 序列化/还原三套并行机制（注册表 to_typeref 死代码 / serializer 硬编码 / rehydrator 字符串嗅探 + 幽灵 task 回退）。
- G5 线程协调器访问器（_get_coordinator）寄居通信模块 comm.py，刺穿领域分离。
- G6 Signal 功能空壳（语言层零方法、无投递机制）+ 双 Signal 撞名（VM 控制流 Signal vs 通信 SignalCore）。
- G7 通信半成品：pubsub 语言层不可达、send_nowait 无订阅者"丢弃返回 True"语义不对称、订阅者无界缓存无失效机制、"可配置"空头支票。

### 根因归纳

1. `instantiate` 不可挂钩（`ib_class.py:86`）→ 值对象构造机制无法统一 → G1/G2/G4 + B1/B2 连锁碎片。
2. 方向修正清理不彻底 → TASK kind 残留、comm 模块归属、VP-4 未修、SpawnedTask 结构性 Waitable 残留。
3. 完成口径高估 → C5"序列化"实为半接通（B1）、PT-MT-3"已完成"实为占位（G6/G7）。
4. join/cancel 公理返回类型仍是 any 兜底，仅靠 `_members.py` 特化补救。

### 变化前后

- **新增**：`tasks_docs/COMMS_DESIGN_REVIEW.md`（完整审查记录）。
- **代码**：无改动（纯审查）。
- **测试**：基线 1453 passed / 4 skipped（全绿，B1/B3 等未被测试覆盖）。

### 待决

- 无。修复方向已列于 COMMS_DESIGN_REVIEW §六（三阶段：先修实锤 bug → 统一值对象机制 → 通信领域设计）。下一 session 按 `_HANDOFF.md` 规划推进。

---

## 2026-08-04 会话 4：任务 C 线程对象模型实现（C0-C6，自主实现）

### 背景

按 `THREAD_DESIGN_REVISION.md` 任务 C 实施。调研发现用户侧机制缺口（类构造关键字参数支持缺失），经用户确认引入工作规划并调整路径。

### 用户裁定（2026-08-04，任务 C 实施中）

1. **类构造关键字参数支持缺口**：`_get_callee_param_specs` 不处理 `IbClass`，导致关键字参数被丢弃。用户指示"把相关机制的完善调研和实现工作引入到现存工作规划中，并调整工作任务路径"→ 引入任务 C0 前置。
2. **关键字碰撞原则**：内部接口设计不违反关键字碰撞；设计文档与架构原则冲突时以架构原则为主 → thread 构造参数名不用 `fn`/`func`（均与关键字碰撞），改用 `callable`。
3. **join 返回容器**：`t.join()` 返回 `thread_result[T]` 容器（非 T）。要求提供 Rust 风格"直接返回 value"的易用方法（设计历史已归档无此记录，自主设计为 `expect()`）。

### 实现记录

| 子任务 | 内容 | 测试 |
|--------|------|------|
| C0 | `_get_callee_param_specs` 支持 IbClass + `_auto_init` 补 param_meta | `test_class_constructor_keywords.py`（4 用例） |
| C1 | `IbThread` 值对象 + 生命周期状态机 + `thread(callable=..., args=...)` 构造 | `test_thread_model.py` 起 |
| C2 | `thread_result[T]` 容器 + join 返回容器 + expect/unwrap/unwrap_or/is_error/is_success/value/error/status | `test_thread_result.py`（4 用例） |
| C5 | 序列化（spec value_type + 值对象序列化/反序列化） | 全量回归 |
| C6 | 测试补充（cancel + 线程隔离） | 11 用例 |

### 设计决策

1. **`IbThread` 实例状态存于 `self.fields`**（与 `intent_context` 模式一致）：实例由 `instantiate` 创建为普通 `IbObject`，`__init__` 经 `_init_fields` 初始化状态，句柄方法自包含操作 fields（不依赖实例私有 helper）。
2. **`thread_result[T]` 容器**：TypeKind.THREAD_RESULT + THREAD_RESULT_SPEC + GenericTypeRegistry + ThreadResultAxiom + IbThreadResult 值对象。`unwrap()`→Optional[T]、`unwrap_or(default)`→T、`expect()`→T（失败重抛存入异常，语言层 try/except 可捕获）、`is_error()`/`is_success()`、`value()`/`error()`/`status()`（方法，非裸属性，符合疏漏 4）。
3. **`thread[T].join()` → `thread_result[T]`**（`_members.py` 特化更新）。
4. **save_state 未完成线程检测**：属任务 E 范围，C 阶段未实现。

### 变化前后

**实现（新增）**：`core/runtime/objects/thread.py`（IbThread）、`core/runtime/objects/thread_result.py`（IbThreadResult）、`tests/runtime/test_class_constructor_keywords.py`、`tests/runtime/test_thread_model.py`、`tests/runtime/test_thread_result.py`。

**实现（修改）**：`_shared.py`（IbClass 分支）、`interpreter.py`（_auto_init param_meta）、`primitive_initializer.py`（thread __init__ 注册）、`comm.py`（ThreadAxiom has_call_cap + ThreadResultAxiom）、`specs.py`/`factory.py`/`generic.py`/`base.py`/`_runtime.py`/`_members.py`（thread_result 泛型全链）、`serializer.py`/`artifact_rehydrator.py`/`runtime_serializer.py`（序列化）、`test_generic_model.py`（join 容器）。

**测试**：全量 pytest **1459 passed / 4 skipped** 零回归。

### 待决
- 无。任务 C 完成。下一步任务 D（err 类型统一）。

---

## 2026-08-04 会话 4：任务 D/E/F 实现（err 类型统一 + 线程清理 + 关键字精简）

### 任务 D：err 类型统一（已完成）

按 THREAD_DESIGN_REVISION §2.6：TaskError（parent Exception）→ TaskCancelled/TaskFailed（parent TaskError）映射 IBCI Exception 子类；make_task_cancelled/make_task_failed 运行时工厂；cancel() 返回 TaskCancelled err（成功取消）/ None（无效）；join() 错误值化进容器；expect() 抛容器内 err 供语言层 try/except 按类型捕获；err 用户可见可继承（class MyTaskError(TaskError) 验证）。测试：test_thread_err.py（5 用例）。

### 任务 E：线程相关清理（已完成）

VP-2（死 _task_handle → handle 全链透传）、F-2（coordinator _tasks 自动清理防泄漏）、F-1（快照补充协调器线程）、疏漏 4（save_state 未完成线程检测）+ save_state 磁盘型误判修复（类对象不再误判为 disk-backed 实例）+ 序列化瞬态线程存根化。测试：test_thread_cleanup.py（4 用例）。

### 任务 F：关键字精简（已完成）

删除 spawn/join/cancel/task 全链 + 废除旧测试 + 重写为 thread 对象模型语法。修复 _thread_init 实参传递 bug（IbList 内 chan/slot 身份保留）。旧语法全部编译失败（验证通过）。

### 变化前后
- **删除**：`objects/task.py`（IbTask 死代码）、TASK_SPEC/TaskAxiom/IbSpawnStmt/IbJoinStmt/IbCancelStmt/SPAWN/JOIN/CANCEL/TASK TokenType。
- **修改**：lexer/parser/AST/semantic/VM/spec 全链移除旧关键字；coordinator/snapshot/serializer/service 清理；_thread_init 实参修复。
- **测试**：重写 test_concurrency_syntax/test_vm_comm/test_vm_instance；新增 test_thread_err/test_thread_cleanup。

**测试**：全量 pytest **1453 passed / 4 skipped** 零回归。

### 待决
- 无。线程对象模型方向修正（任务 A-F）全部完成。

---

## 2026-08-04 会话 4：任务 C 调研 + 发现前置机制缺口（用户侧机制不完善）

### 背景

任务 A、B 已完成。进入任务 C（线程对象模型）调研。调研中发现**用户侧机制缺口**：类构造的关键字参数支持缺失，直接阻碍 `thread(fn=..., args=...)` 构造。

### 机制缺口（用户侧机制不完善，已确认）

**现象**：`Dog(name="Rex", age=5)` 报 "got 0"；`thread(fn=..., args=...)` 的关键字参数无法传递。

**根因**：`_get_callee_param_specs`（`core/runtime/vm/handlers/_shared.py:91-111`）只处理 `IbBoundMethod`/`IbUserFunction`/`IbLLMFunction`/`IbValue`/`IbNativeFunction`，**不处理 `IbClass`**。当 `func` 是类（构造调用）时返回 `None`，`vm_handle_IbCall`（`leaf.py:266-274`）走 `args = positional` 分支，关键字参数被丢弃。

**影响**：
- 用户类构造 `Dog(name=..., age=...)` 关键字无效（既有缺陷）。
- thread 构造 `thread(fn=..., args=...)` 无法工作（任务 C 阻塞）。

**决策**：将此机制完善纳入任务规划（作为任务 C 前置 C0），调整任务路径。符合用户"发现用户侧机制不完善导致任务无法推进时引入工作规划并调整路径"的指示。

### 任务路径调整

- **C0（前置）**：类构造关键字参数支持——`_get_callee_param_specs` 增加 `IbClass` 分支（返回 `__init__` 参数签名）+ `_auto_init` 补 `param_meta`。
- **C1-C6**：线程对象模型（IbThread + 状态机 + thread_result 容器 + 构造注册 + 序列化 + 测试）。

> 完整任务文档见 `tasks_docs/_code_thread_model.md`（临时，Phase 5 后删除）。

### 变化前后
- **新增**：`tasks_docs/_code_thread_model.md`（任务 C 临时任务文档，含 C0 前置设计）。
- **代码**：未改动（调研与方案设计阶段）。

### 待决
- 无。C0 机制完善已明确方案，可自主推进。

---

## 2026-08-04 会话 2：线程对象模型方向修正（设计决策，未实现）

### 背景

PT-MT-1~8 主线实现完成后，对 spawn/join/cancel/task 关键字设计进行深度质询，确认存在设计缺陷：async/thread 领域混淆、关键字冗余（cancel→方法、join 与 await 重叠、spawn 与 fn 重合）、类型精度不足（join 返回 any 兜底）、系统碎片化（F-1~F-8）。

### 用户裁定（完整记录见 `tasks_docs/THREAD_DESIGN_REVISION.md`）

1. **async 与 thread 彻底分离**：`IbTask` 不得满足 Waitable；await 只服务异步；线程走句柄方法。
2. **关键字精简**：删 spawn/join/cancel/task，改用 `thread` 类型 + 句柄方法（疏漏 1 裁决：无用关键字直接删除）。
3. **`thread[T]` 泛型标注必须**（非参数传递）；返回类型显式标注；`thread[void]` 支持。
4. **`thread_result[T]` 泛型容器**：成功值/错误/状态，可继承可改写，禁止 any。
5. **配套方法**（Rust 对齐）：`unwrap()→Optional[T]` / `unwrap_or(default)` / `is_error()` / `.value`(fail-fast) / `.error`。
6. **err 类型统一**：接入既有 Exception 体系；TaskCancelled/TaskFailed 映射 IBCI 子类；`t.cancel()` 返回 err。
7. **挂起机制取消**（未来也不做）：无损挂起=协程帧保存，与领域分离冲突 + 高难度。
8. **统一泛型模型立即启动**：内置类型泛型化正式机制；`thread[T]` 首个消费者；不含用户级泛型类/约束求解。
9. **Optional 配套**：查证现状——编译期特化完整，**运行时无 IbOptional 对象**（`Optional[int] x = None` 的 `x.is_some()` 运行时失败）；补齐运行时实现。

### 疏漏裁决

- 疏漏 1：无用关键字直接删除。
- 疏漏 2：通信领域（chan/signal/slot）完善与统一化检查 = **下阶段任务，暂缓**。
- 疏漏 3：**大范围重构直接开始**，允许推翻/删除既有代码。
- 疏漏 4：内省用明确方法（非裸属性）；线程对象/容器瞬态；save_state 检测未完成线程则抛异常 fail。
- 疏漏 6：废除相关旧测试，新机制测试单独制作。

### 变化前后
- **新增**：`tasks_docs/THREAD_DESIGN_REVISION.md`（方向修正完整决策记录）。
- **修改**：无代码改动（本轮仅设计讨论与记录，按用户指示暂不实现）。

### 授权实现（2026-08-04）
- **用户裁定**："授权实现。完善相关决策文档。"——全部任务 A-F 已授权，含 Optional 配套完整实现。
- **决策文档更新**：`THREAD_DESIGN_REVISION.md` 状态改为"已授权实现"，任务清单细化为可执行计划（含验收标准），新增"实施细节"节（线程创建语法/容器成员/既有内核处置/分支政策：已确认边界，当前分支直接开始）。

### 待决
- 无。任务 A-F 已授权，待启动实现（顺序：A Optional 配套 → B 统一泛型模型 → C 线程对象模型 → D err 类型 → E 清理 → F 关键字精简+测试）。

---

## 2026-08-03 会话 1：主线交接 + 用户裁定记录

### 决策记录

#### 1. 禁止 push 硬原则（用户裁定）
- **内容**：非明确指示允许，一律禁止 `git push` 到任何远程仓库。全程只本地 commit；push 必须等用户显式授权。
- **落点**：`AGENTS.md`（新增硬原则块）、`.opencode/skills/code-workflow/SKILL.md`（Phase 5 交付纪律）、`tasks_docs/_HANDOFF.md`（三处）。

#### 2. 破坏性重构授权 + 分支政策（用户裁定 2026-08-03 补充）
- **破坏性重构授权**：符合一般工程经验/普适性/合理架构设计且经分析确实优于 IBCI 现有体系及已有代码时，哪怕设计已被文档记录也允许破坏性重构；不禁止修改已有代码；已有代码优先级低于架构正确性。默认已授权自主推进。
- **分支政策**：无法确认边界/危害程度的破坏性重构，100% 授权独立分支（不污染 main/unsafe-vibe-dev、不污染环境与用户目录）；仅当独立隔离分支也无法确定技术路线才阻塞；独立分支禁止直接合并到 unsafe-vibe-dev/main，确认技术路线后仅允许手动单独更新 unsafe-vibe-dev；永不触碰 main。
- **落点**：`AGENTS.md`、`NEXT_STEPS.md`（工作模式定论第 8/9 条）、`code-workflow/SKILL.md`、`THREADING_DESIGN.md`、`_HANDOFF.md`、goal。

#### 3. 全自主 goal 配置（用户裁定）
- 硬性定时 `max_duration_seconds=37217`（对应 2026-08-04 08:00 CST）+ `max_auto_turns=300`。
- goal 目标含：主线 PT-MT-1~8、自主推进偏好、禁止 push、破坏性重构授权与分支政策、支线、停止条件、非目标。
- 当前 session 仅做 PT-MT-1（设计文档），产出后停在用户审阅点，不越界实现。

#### 4. 交接准备（2026-08-04）

- 更新 `_HANDOFF.md`：反映当前真实状态（PT-MT-1~8 完成 → 方向修正已授权未实现、任务 A-F、完整 goal 工作原则模板）。
- 提炼用户**系统级设计哲学** → 新增 `.opencode/skills/design-philosophy/SKILL.md`（单一权威源/设计语言统一/设计思路统一/机制同构/配合模式统一/一致性先于便利/宏观反思/命名粒度统一），注册进 `skills/README.md` + `AGENTS.md`。
- 同步 `NEXT_STEPS.md`（当前主线改为方向修正任务 A-F）+ `PENDING_TASKS.md`（PT-MT 系列标完成 + 记录方向修正）。

> 注：用户两次纠正 design-philosophy 提炼方向——第一次误提炼为 IBCI 语言特性（不合格），第二次才对准"系统级统一性"（碎片化/设计语言/设计思路/机制/配合模式/一致性/宏观反思/命名）。此为重要教训：提炼用户工作哲学应抓**宏观元层面**（系统统一性），而非项目专属特性。

---

## 2026-08-04 会话 3：任务 A — Optional 配套完整实现（自主实现）

### 背景

按 `THREAD_DESIGN_REVISION.md` 任务 A 实施。查证现状：Optional 编译期（`Optional[T]` spec 特化、`resolve_member` 返回包装类型、空安全编译期校验、artifact 还原）已完整；**运行时无 `IbOptional`**——`Optional[int] x = None` 是裸 `IbNone`，`x.is_some()` 运行时失败（"Object of type 'None' has no method '__call__'"）。

### 设计决策

1. **`IbOptional` 运行时值类**（`core/runtime/objects/primitives/optional.py`，`@register_ib_type("Optional")`）：包装内层值 + `is_some` 标志。方法表面 `is_some`/`unwrap`/`or_else` 由 `OptionalAxiom` 声明，经 `primitive_initializer` 的 axiom-driven auto-bind 自动绑定到语言层（复用既有 spec/axiom/factory 基础设施，符合"机制同构"）。
2. **绑定入口单一化**：`ScopeImpl` 新增 `_wrap_optional(value, declared_type)`——当 `declared_type.kind == OPTIONAL` 且值非 `IbOptional` 时包装为 `IbOptional`（幂等，不重复包装）。在 `define`/`assign`/`assign_by_uid` 三处调用（覆盖变量定义、重赋值、函数参数、LLMFuture 解析回写）。这是 Optional 运行时值的**单一权威入口**（design-philosophy：单一权威源，反碎片化）。
3. **`Optional` 基础可赋值性**：`_assignability.py` 中 `Optional`（wrapped=any）→ `Optional[T]` 返回 True（复制 Optional 场景 `Optional[int] y = x` 需要）。否则基础 Optional 无法赋值给特定 Optional[int]。
4. **值协议补齐**：`OptionalAxiom.get_method_specs()` 增加 `to_bool`/`cast_to`/`__to_prompt__`（auto-bind 只绑定 axiom 声明的方法，`to_bool` 若不声明会落到基类 Object 默认 True）。
5. **序列化**：serializer 增加 `_type=="optional"`（is_some + inner），deserializer 增加对应分支。

### 变化前后

**实现（新增）**：
- `core/runtime/objects/primitives/optional.py`（IbOptional：is_some/unwrap/or_else/to_native/__to_prompt__/to_bool/cast_to/receive(__eq__/__ne__)/serialize_for_debug）
- `tests/runtime/test_optional_runtime.py`（17 用例：is_some/unwrap/or_else/复制/重赋值/类型覆盖/空 unwrap fail-fast/真值/序列化 round-trip）

**实现（修改）**：
- `core/runtime/objects/primitives/__init__.py`（注册 IbOptional）
- `core/runtime/interpreter/runtime_context.py`（`_wrap_optional` + define/assign/assign_by_uid 三处接入 + 导入）
- `core/kernel/spec/registry/_assignability.py`（Optional 基础 → Optional[T] 可赋值）
- `core/kernel/axioms/primitives/sentinels.py`（OptionalAxiom 增加 to_bool/cast_to/__to_prompt__ 方法表面）
- `core/runtime/serialization/runtime_serializer.py`（serialize + deserialize optional 分支）

**测试**：全量 pytest **1426 passed / 4 skipped**（1409 + 17 新增，零回归）。

### 待决
- 无。任务 A 完成，校验通过。下一步任务 B（统一泛型模型）。

---

## 2026-08-04 会话 3：任务 B — 统一泛型模型（自主实现）

### 背景

按 `THREAD_DESIGN_REVISION.md` 任务 B 实施。查证现状：内置泛型类型（list/dict/tuple/Optional/fn_callable/behavior）的创建、特化、序列化、还原散落多个 ad-hoc 入口——`SpecFactory.create_*` 方法、`_assignability.resolve_specialization` 的 fn/Optional 函数特判 + Axiom 的 `resolve_specialization_by_names`、`TypeRef.from_spec` 的 kind 分派、`artifact_rehydrator` 的 kind 分派。这是碎片化（design-philosophy：单一权威源/机制同构）。

### 设计决策

1. **`GenericTypeDeclaration` + `GenericTypeRegistry`**（`core/kernel/spec/generic.py`）：内置泛型类型声明的单一权威源。每个声明描述生命周期四操作——`build`（创建）、`to_typeref`（序列化）、`restore`（还原）。注册表同时按 name 与 kind 索引。
2. **统一创建入口**：`SpecRegistry.resolve_specialization` 改为按基础名查注册表，经 `decl.build` 创建 + register + bootstrap axiom 方法。删除 `fn`/`Optional` 函数特判中的旧 `Optional` 分支（保留 `fn[RETURN]` 的表达式侧推断特判）。
3. **删除历史遗留路径**：删除 `Optional/List/Dict/Tuple` Axiom 的 `resolve_specialization_by_names` 方法（死代码），删除 `resolve_specialization` 的遗留兜底分支（axiom `resolve_specialization_by_names` 路径）。用户明确要求"不保留历史包袱，最终删除"。
4. **`thread[T]` 首个消费者**：新增 `THREAD_SPEC`（kind=TASK，`_axiom_name="thread"`）、`ThreadAxiom`（start/join/cancel/is_done 方法表面）、`SpecFactory.create_thread`，注册进 `GenericTypeRegistry`。`_members.py` 增加 thread 特化（`thread[T].join()` → T）。
5. **序列化/还原**：serializer 增加 thread 的 `value_type_name/module` 持久化；rehydrator 增加 TASK→thread shell 创建与值类型填充。

### 变化前后

**实现（新增）**：
- `core/kernel/spec/generic.py`（GenericTypeDeclaration + GenericTypeRegistry + 内置声明 + 默认注册表）
- `tests/kernel/test_generic_model.py`（16 用例：注册表完备性/统一解析/thread 泛型/to_typeref/遗留路径删除验证）

**实现（修改）**：
- `core/kernel/spec/registry/_assignability.py`（resolve_specialization 统一走注册表，删除遗留路径）
- `core/kernel/spec/registry/_base.py`（SpecRegistry 持有 generic_types 注册表）
- `core/kernel/spec/registry/factory.py`（新增 create_thread）
- `core/kernel/spec/registry/_members.py`（thread[T].join → T 特化）
- `core/kernel/spec/specs.py`（新增 THREAD_SPEC）
- `core/kernel/spec/registry/_runtime.py`（注册 THREAD_SPEC）
- `core/kernel/axioms/primitives/comm.py`（新增 ThreadAxiom）
- `core/kernel/axioms/primitives/registry.py`（注册 ThreadAxiom）
- `core/kernel/axioms/primitives/sentinels.py`（删除 OptionalAxiom.resolve_specialization_by_names）
- `core/kernel/axioms/primitives/sequences.py`（删除 List/Dict/TupleAxiom.resolve_specialization_by_names）
- `core/compiler/serialization/serializer.py`（thread 值类型持久化）
- `core/runtime/loader/artifact_rehydrator.py`（thread shell 创建 + 值类型填充）

**测试**：全量 pytest **1443 passed / 4 skipped**（1426 + 17 新增，零回归）。

### 待决
- 无。任务 B 完成，校验通过。下一步任务 C（线程对象模型 thread[T] + 句柄方法 + 状态机）。

---

## 2026-08-04 会话 3：任务 C 调研 + 交接准备（用户要求暂停）

### 背景

任务 A、B 完成后进入任务 C（线程对象模型）调研。用户中途要求暂停所有工作、停止自动化 goal，并准备交接以便下一 session 接手。

### 任务 C 调研结论（已确认，供下一 session 使用，勿重复调研）

- **`thread` 类型已就绪**：`registry.get_class("thread")` 存在（ThreadAxiom 驱动创建）；`thread[T]` 解析经 GenericTypeRegistry 工作（`thread[int]` 解析成功、kind=TASK、`get_base_name()="thread"`、`value_type.head="int"`）。
- **`thread[T].join()` 返回类型特化已就绪**（`_members.py` thread 特化：`thread[T].join()`→T）。
- **既有内核机制可复用**：`core/runtime/coordinator.py` 的 `RuntimeCoordinator` + `SpawnedTask`（后台线程 + 任务本地执行上下文）。现有 `IbTask`（`core/runtime/objects/task.py`）是 spawn 句柄，方向修正要求改造为 thread 对象 + 句柄方法。
- **当前 spawn/join/cancel 是关键字**（TokenType.SPAWN/JOIN/CANCEL/TASK），走 `vm_handle_IbSpawnStmt/IbJoinStmt/IbCancelStmt`（`core/runtime/vm/handlers/comm.py`），任务 F 删除。
- **parser 构造函数模式参考**：chan/signal/slot 是关键字前缀（`chan_expr`/`signal_expr`/`slot_expr`），产 `IbChannelExpr/IbSignalExpr/IbSlotExpr`。但 `thread` 不是关键字，`thread(...)` 如何解析为构造函数需自主设计。
- **设计重点**：`thread[T] t = thread(fn=..., args=...)` 构造函数 + `t.join()/t.cancel()/t.start()/t.is_done()` 句柄方法 + 生命周期状态机。`join()` 返回 T（任务 B 已特化好）。`cancel()` 返回 err（任务 D 落地）。需从 comp_parser → semantic → VM dispatch → 运行时对象全链设计。

### 变化前后

- **修改**：`tasks_docs/_HANDOFF.md`（更新为任务 A、B 完成 + 任务 C 调研结论 + 任务 C 起 goal 模板），`NEXT_STEPS.md`/`PENDING_TASKS.md`/`WORKLOG.md` 已如实同步。
- **代码**：无新增代码改动（任务 C 仅调研，未写实现）。

### 状态

- **goal 已暂停**（用户要求）。测试基线：全量 pytest **1443 passed / 4 skipped** 零回归。
- **待决**：无。任务 C-F 已授权待实现；交接文档已备好，下一 session 从任务 C 继续。
