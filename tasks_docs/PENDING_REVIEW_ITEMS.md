# 待复核 / 待处理清单（用户逐个处理）

> 状态：**登记中**（2026-08-04 会话 9 建立）
> 用途：记录"通信领域设计完善阶段 1-3 实施后尚未进行的审查复核内容" + 用户指出的
> thread 架构/类型系统隐患调查线索。用户将**逐个**处理，本文件为逐项清单。
> 每项处理后勾选并记录结果；全部处理完毕且经确认后删除本文件。

---

## 一、未做的正式审查复核

| # | 内容 | 说明 |
|---|------|------|
| R1 | 阶段 1-3 实施后**正式 code-review 复核**未做 | COMMS_DESIGN_REVIEW §六 要求"实施后核验回 code-review"；三阶段后仅做了轻量残留扫描，未跑完整独立复核。约束：subagent 仅可用 general agent |
| R2 | **code-quality 健康诊断十查**未做 | 全仓健康审计（残留扫描/历史痕迹/双通道等），本轮仅针对性 grep |
| R3 | **code-odor 全面异味扫描**未做 | 本轮仅扫了旧符号残留，未跑完整特征扫描（嵌套分支/能力探测/兜底字样） |
| R4 | **覆盖率核对**未做 | 新增测试未系统核对是否覆盖全部新行为（subscriber 生命周期、cancel 路径、序列化往返边界等） |
| R5 | **doc-governance 审计**未做 | docs/ 治理流程未跑（见 §三 docs/ 未同步项） |

## 二、COMMS_DESIGN_REVIEW 遗留项（本轮未纳入范围）

| # | 内容 | 位置/现状 | 处置建议 |
|---|------|----------|---------|
| L1 | **B3 `_by_kind` 索引有损** | ✅ **已完成（commit 149dd63）**——彻底删除 `_by_kind`/`get_by_kind`（kind 不唯一有损 + 生产零调用死代码），测试改按名 `get(name)`；未来按 kind 分发的正确形态（多值索引 + 声明驱动）记录于 class docstring | 已删除 |
| L2 | **根因 4：join/cancel 返回 `any` 兜底** | ✅ **已完成（commit 8e0ada9）**——泛型成员特化协议化根治：`resolve_member` 级联收敛为 `GenericTypeDeclaration` 声明回调；`any` 成为声明层合法默认，精确化由机制承担。设计见 `MEMBER_SPECIALIZATION_UNIFICATION.md` | 已根治 |
| L3 | **G2 未完全兑现**：序列化端 `"done"` 字面量 | ✅ **已完成（commit 149dd63）**——`runtime_serializer.py` thread_result 分支改用 `ThreadStatus.DONE`（序列化+反序列化） | 已修复 |
| L4 | **SpawnedTask "结构性满足 Waitable" 注释残留** | ✅ **已完成（commit 149dd63）**——`result()` 死方法删除（全仓零消费者），docstring 明确"不满足 Waitable"（async/thread 彻底分离） | 已清理 |
| L5 | **G1 残留：值对象承载未完全统一** | ✅ **已完成（commit 80b463e）**——IbOptional 删 `_inner` 双载槽（统一 payload）；core/view 槽判定为合理句柄承载（与 thread slots 同构），记录为设计决策 | 已收敛 |
| L6 | **chan/slot/subscriber 序列化空壳** | ✅ **已完成（commit 3a2e5d1）**——瞬态序列化协议化：`__transient_state__` 协议 + 统一 `transient` 存根，thread_transient 专用分支删除；数据不再丢失。设计见 `TRANSIENT_SERIALIZATION_UNIFICATION.md` | 已修复 |
| L7 | **运行时泛型身份全系统有损** | ✅ **部分完成（commit 80b463e，L7-A）**——符号/序列化侧精确化：`_resolve_annotation` 支持泛型注解 + serializer 持久化 list/dict/tuple 实参 + rehydrator 重建特化 spec；运行时 declared_type 实测精确。**剩余**：值 `type_ref` 保持基础 spec（设计决策：可变值不固有泛型身份） | L7-A 已落地 |
| L8 | **类型符号序列化类型身份破坏（此前未知缺陷）** | `RuntimeDeserializer.deserialize_context` 把全局作用域内置类型符号（IbClass）重建为对应类的空普通实例（IbObject）——实测 `slot` 符号 IbClass→IbObject，`slot(...)` 调用失败。根因：serializer 对 IbClass 落 else object 分支（类引用当实例构造）。`rt_scheduler.restore` 无重绑定 → 真实破坏；`HostService.load_state` 被 `setup_context(force=True)` 掩盖 | **已修复（commit 见 WORKLOG 会话 11）**：serializer 序列化为 `class_ref`（类名引用），反序列化重绑定 `registry.get_class(name)` |

## 三、docs/ 技术手册未同步（按治理纪律设计阶段先写 tasks_docs/）

| # | 内容 | 影响文档 |
|---|------|---------|
| D1 | `signal` 关键字/类型移除 | `docs/subsystems` 通信/并发章节、语法文档、`KNOWN_LIMITS.md` |
| D2 | pubsub 语言面打通 + `subscriber` 新类型 | 通信/并发文档、类型参考 |
| D3 | 通信 Signal 移除裁定（零消费者空壳 + 撞名） | 相关设计记录 |
| D4 | `send_nowait` 语言面补齐 + 语义变化（无订阅者 False） | 通信文档 |
| D5 | 线程对象模型细化（thread 槽位化/thread_result IbValue） | 线程/值对象文档 |

## 四、用户指出的 thread 架构/类型系统隐患（2026-08-04，调查中）

> 用户观察：thread 实例/类处理存在特殊 if-else 分支；公理/底层方法与现存机制存在不统一；
> 怀疑 thread 架构设计有缺陷，甚至底层类型系统/公理体系有隐患。
> 缺陷特征：**通用型、全对称、全协议化的处理流程中，突兀出现针对特定类型的硬编码分支**。

| # | 线索 | 状态 |
|---|------|------|
| T1 | 通用流程中针对 thread 的硬编码分支清单 | ✅ 调查完成（2026-08-04）——见 `THREAD_ARCH_HARDCODE_INVESTIGATION.md` §二 A/B |
| T2 | thread 公理/底层方法与现存机制的不统一点 | ✅ 调查完成——同上 §二 C（构造机制三轨 + any 兜底） |
| T3 | 类型系统/公理体系深层根本成因 | ✅ 调查完成——同上 §三/§四（核心：统一泛型模型半落地，resolve_member 特化未协议化） |

> 调查结论摘要：用户观察**确认成立**。thread 有 5 处特有突兀分支（A1-A5）+ 公理构造机制双轨；
> 但系统层隐患归因为**泛型成员特化机制缺失**（`_members.py` per-type 级联，list/dict/Optional/thread 通用模式），
> 非 thread 独立病灶。完整分析见 `THREAD_ARCH_HARDCODE_INVESTIGATION.md`。
>
> **建议落地状态**：建议 1（成员特化协议化）✅ 已落地（commit 8e0ada9，根治 L2/T1）；
> 建议 4（公理返回类型正确化）✅ 以机制化满足（any 为声明层合法默认）；建议 3（瞬态序列化协议化 = L6）
> ✅ 已落地（commit 3a2e5d1）。
> **建议 2（kernel 构造机制统一）重新裁定（会话 12）**：三轨判定为**设计语言统一、非碎片**
> （用户纠正判断基准：碎片化 = 用户语义形态统一，非实现路径一致）；可统一点（实例创建入口
> `_create_blank` 协议）✅ 已应用（commit 80b463e）；三轨其余差异记录为设计决策，不强制统一。
