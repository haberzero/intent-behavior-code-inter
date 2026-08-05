# 完整复核审查工作清单

> 状态：**下一阶段核心清单**（2026-08-05，用户准备开启完整复核审查工作流程）
> 用途：会话 1-12 所有改动（通信领域三阶段主线 + 收尾 L1-L8 + 泛型成员特化协议化等）的
> **完整独立复核审查**清单。R 系列为审查动作；L/D 系列为已完成项（供审查时验证）+ 未同步项。
> 审查完成后经确认删除本文件；各决策记录详见 `WORKLOG.md` 会话 6-12。
>
> **R1 已完成（2026-08-05）**：三个 general agent 并行独立复核（编译/类型层 + 运行时对象层 +
> 通信内核/VM 层）+ 亲自实证关键发现。新增缺陷 A1/B1-B6/C1/D1-D4 全部处置完毕，全量
> 1477 passed / 4 skipped 零回归（commit 见 git log）。

---

## 〇、R1 复核结果（2026-08-05，已完成）

### 独立复核执行

- **方法**：三个 general agent 并行独立复核（禁 explore/reviewer）；每 agent 读 diff + 完整
  当前版本 + 交叉契约侧；关键发现由主会话亲自实证（cancel 生命周期 / multi-type 序列化
  链路 / 未使用 import / 不可达分支）。
- **总体结论**：三阶段主线 + 收尾 L1-L8 整体正确。L2 重构语义等价、G3/G6 移除彻底、
  L7-A 与 G7 契约一致、B1 往返闭环、L5 单承载收敛、L8 class_ref 重绑定正确、瞬态协议一致。
  无高严重性缺陷。

### 新增缺陷处置（按"不删也不修"两档）

| 编号 | 分类 | 位置 | 断言 | 处置 | commit |
|------|------|------|------|------|--------|
| **A1** | 真bug | `objects/thread.py:151-161` | `cancel()` 未检查 `is_done`：已结束线程调用返回 `TaskCancelled` 并翻转状态为 CANCELLED，违背 docstring"未启动或已结束→None" | ✅ 根本修复（is_done 守卫）+ 4 测试改确定性挂起场景 + 新增已结束 cancel 测试 | R1 提交 |
| **B1** | 死代码 | `generic.py:330` | `_resolve_member_thread` 的 `"result"` 分支不可达（ThreadAxiom 无 result 成员） | ✅ 彻底删除 | R1 提交 |
| **B2** | 死代码 | `vm/handlers/comm.py:16` | 未使用 import（IbClass/IbUserFunction/IbValue） | ✅ 彻底删除 | R1 提交 |
| **B3** | 死代码 | `recognizer.py:63` | 注释残留 signal（G6 后 chan/slot 而已） | ✅ 清理注释 | R1 提交 |
| **B4** | 死代码 | `registry.py:19` | docstring kind 残留 signal/task | ✅ 清理注释 | R1 提交 |
| **B5** | 死代码 | `_assignability.py:134-135` | 重复 `return None` | ✅ 删除一行 | R1 提交 |
| **B6** | 格式 | `_runtime.py:22,107` | 缩进不一致（8 vs 4 空格） | ✅ 对齐 | R1 提交 |
| **C1** | 半接通 | `serializer.py`/`rehydrator`/`factory` | multi-type list `allowed_element_types` 未持久化（`list[int,str]` 序列化退化为裸 list）；tuple positional module 未持久化 | ✅ 根本修复（持久化 allowed/positional 名+模块）+ 2 测试 | R1 提交 |
| **D1** | 半接通 | `symbol_collection_pass` | `chan[str]`/`slot[int]` 注解实参不保留——`ChannelAxiom`/`SlotAxiom` docstring 声称"value_type 承载"但 chan/slot 不在统一泛型模型，注释实参实际丢弃。**（初判"设计限制"有误——声称的协议未落地 = 半接通，按定论第 7 条可推翻）** | ✅ 根本修复（chan/slot 纳入 GenericTypeDeclaration + factory create_chan/create_slot + serializer/rehydrator/TypeRef 持久化）+ 测试；KNOWN_LIMITS §10.2 已移除 | R1 修正提交 |
| **D2** | 设计限制 | `channel.py send_nowait` | 多订阅者部分满时返回 False 但消息已部分投递——pubsub 广播固有语义（全有全无需原子性），非缺陷 | ✅ docstring 明确语义边界（文档化合理） | R1 提交 |
| **D3** | 真缺陷 | `channel.py send` | fan-out 与订阅者并发 close 竞态，`CommClosedError` 从单个订阅者泄漏给生产者。**（初判"文档化"过保守——真实异常泄漏路径）** | ✅ 根本修复（send 捕获跳过已关订阅者，与 send_nowait 语义对齐）+ 测试 | R1 修正提交 |
| **D4** | 真缺陷 | `channel.py close` | close 后 `subscriber_count` 仍计入已关订阅者（snapshot 内省与状态不一致）。**（初判"文档化"有误——可观测性失真）** | ✅ 根本修复（close 清空 _subscribers）+ 测试 | R1 修正提交 |
| **D5** | 设计限制 | `objects/kernel/comm.py` | `_create_blank` 默认 core 立即被覆盖（纯效率损耗，无行为/泄漏/注册表副作用） | ✅ 无需动作（构造协议正常代价，文档化合理） | R1 提交 |
| **D6** | 真bug | `objects/thread.py is_done()` | 线程自然完成未 join 时 `is_done()` 读滞后的 `_state`（running）误报 False，`_spawned.is_done` 才是权威。**（初判"设计决策"严重有误——用户可见错误行为）** | ✅ 根本修复（is_done 读真实后台状态）+ 测试 | R1 修正提交 |

### C1 根因补充（比预期深）

实证发现 multi-type list 注解在**编译期构建**即退化为 `list[]`：`factory.create_list` 用
`zip(names, modules)` 且 modules 为空时产出空对 → `list[]` 且 allowed 丢失。修复：modules
缺省补 `[None]*len`，配合 serializer/rehydrator 持久化闭环后 `list[int,str]` 往返保真。

### D 系列分类修正（2026-08-05，R1 修正批）

> **自我质询反思**：初判把 D1/D3/D4/D6 归为"设计限制/文档化"是**过度保守的误分类**——
> 用"设计限制"标签回避了可低成本根本修复的真实缺陷，违反"不删也不修"精神
> （D2/D5 为真设计限制/效率，文档化合理）。用户质询触发重新取证，逐项实证修正：

| 项 | 初判 | 证据 | 修正 |
|---|---|---|---|
| D1 | 设计限制 | `ChannelAxiom`/`SlotAxiom` docstring 声称"value_type 承载"但实现未落地（半接通） | 根本修复：chan/slot 纳入统一泛型模型 + 序列化持久化 + 测试 |
| D3 | 文档化 | send fan-out 对已关订阅者 `CommClosedError` 泄漏给生产者（真实异常路径） | 根本修复：send 跳过已关订阅者 + 测试 |
| D4 | 文档化 | 实证 close 后 `subscriber_count` 仍为 2（可观测性失真） | 根本修复：close 清空 _subscribers + 测试 |
| D6 | 设计决策 | 实证自然完成线程 `is_done()` 误报 False（`_spawned.is_done` 为权威） | 根本修复：is_done 读真实后台状态 + 测试 |
| D2 | 文档化 | pubsub 广播部分投递固有语义（全有全无需原子性），非缺陷 | 保持文档化（正确） |
| D5 | 无需动作 | `_create_blank` 默认 core 立即覆盖为纯效率损耗 | 保持无需动作（正确） |

### R1 复核范围

`git diff e217b8b^..80b463e`（三阶段主线 + 收尾 L1-L8，19 commit，53 文件）。

---

## 〇b、R2 健康诊断结果（2026-08-05）

> **方法**：code-quality 健康诊断十查，四个 general agent 并行独立诊断（编译/类型层、
> 运行时核心层、对象/通信/插件层、测试/引导层）+ 主会话亲自实证关键项。
> **总体结论**：主链健康（序列化往返/TaskScheduler/并发 dispatch/线程模型均零回归）；
> 发现约 50 项问题，其中真缺陷集中在死代码、损坏空壳、双通道/双写真相、半接通、兜底。
> 处置原则：按"不删也不修"两档（根本修复或彻底删除），设计限制文档化。
>
> **二次复核（2026-08-05）**：用户裁定——所有"需讨论/设计限制/倾向文档化"项经独立
> subagent 二次复核（架构层面 + IBCI 设计思路：功能必要性/设计目的/修复长久收益），
> 用户偏好彻底修复优先，文档化仅限根深蒂固不可维修项。复核结论：30 项升格为
> 彻底修复/删除，12 项确认真设计决策保留，其余保留+局部修复。

### R2 处置清单（已全部处理）

| 组 | 编号 | 位置 | 断言 | 处置 |
|----|------|------|------|------|
| P0 | R2-1 | `serialization/immutable_artifact.py:83-85` | `ImmutableArtifact.__hash__` 声明即坏——实测 `hash()` 抛 `TypeError: unhashable type: 'dict'`（嵌套 dict 不可哈希） | ✅ 根本修复（规范化不可变键哈希）+ 测试 |
| P0 | R2-2 | `objects/intent_stack.py:88-91` + `interfaces.py:126` | `IntentStack.resolve()` 传不存在的 `call_intent` kwarg → 实现签名不匹配必抛 TypeError（协议签名漂移） | ✅ 根本修复（签名对齐）+ 测试 |
| P0 | R2-3 | `objects/intent_stack.py:47-57` | `pop(tag)` docstring 声称按 tag 弹出，实现忽略参数 | ✅ 根本修复（按 tag 移除语义）+ 测试 |
| P0 | R2-4 | `compiler/scheduler.py:382-383` | `registry` 可空分支自毁：else 建 ModuleMetadata 后下一行无条件 `registry.register` 必 AttributeError | ✅ 根本修复（registry 必填，删恒假 guard）+ 测试 |
| P0 | R2-5 | `parser/components/statement.py:378-379` | switch 无 case 时 `stream.error` 参数颠倒（message/token 对调）+ 未 raise | ✅ 根本修复（参数纠正 + raise） |
| P0 | R2-6 | `parser/components/expression.py:156-162` | 前导零数字 `017` 触发未捕获 ValueError（`int("017", 0)`），穿透诊断机制 | ✅ 根本修复（lexer 拒绝前导零 / parser 报 PAR 诊断）+ 测试 |
| P0 | R2-7 | `vm/handlers/assignment.py:98-108` | dispatch resolve 失败 `except Exception: sync_result=None` 静默兜底，掩盖双路径/双重提交风险 | ✅ 根本修复（fail-fast raise）+ 测试 |
| P0 | R2-8 | `ibci_net/core.py` | requests 缺失时静默返回 MOCK 假数据（生产假成功）——**实测为显式测试契约**（`test_function_params.py:142` 断言 MOCK GET），模块级设计取舍 | ✅ 文档化（设计限制：模块离线 mock 能力，测试显式依赖） |
| P1 | R2-9 | `objects/enum.py` 整模块 | IbEnum/IbEnumAdapter/IbEnumValue 全仓零消费者（真实枚举是 primitive_initializer 的 IbClass-based）——两套枚举表示并存 | ✅ 彻底删除 + 外围引用检查 |
| P1 | R2-10 | `vm/task.py:46-77` | `VMTaskResult` 整类零消费者（实际用 Signal 直接返回），docstring 与实际矛盾 | ✅ 彻底删除 |
| P1 | R2-11 | `serialization/snapshot_options.py:116-159` | `SnapshotManager` 占位 stub 整模块零消费者（create 恒 `{"data": None}`，apply 不做恢复），docstring 与实际不符 | ✅ 彻底删除 |
| P1 | R2-12 | 死方法簇 | `_has_call_cap`/`get_iter_cap`/`get_subscript_cap`/`get_operator_cap`/`is_callable_instance`/`_started`/`is_in_fallback`/`save_snapshot`/`_bind_operator_method`/`LLMExceptFrameStack`/`collect_gc_roots` 等零消费者 | ✅ 彻底删除 |
| P1 | R2-13 | `type_ref.py` vs `generic.py` | spec→TypeRef 双序列化器（from_spec vs to_typeref），实测 tuple-positional/multi-list 身份漂移 | ✅ 收敛单一入口 |
| P1 | R2-14 | `type_resolution_pass.py:105-112` vs `symbol_collection_pass.py` | 双注解解析精度矛盾（erasure vs preserve 并存）——双写真相 | ✅ 统一为 preserve |
| P1 | R2-15 | `module_system/loader.py:118-120` | 插件 vtable 旧格式 `param_types` 与新格式 `params` 双格式兼容（历史包袱） | ✅ 删旧格式，单一新格式 |
| P1 | R2-16 | `sdk/check.py:131-138` | 校验只认旧格式 `param_types`，真实插件全用 `params`——协议漂移 | ✅ 改为校验新格式 |
| P2 | R2-17 | `_capabilities.py` `can_return_from_isolated` | 全链路声明（协议+注册表+8 axiom）零接线 | ✅ 整链路删除（或文档化激活） |
| P2 | R2-18 | `semantic/metadata/type_environment.py` | `TypeInferenceState`/`TypeSlot` 设计未接线（生产零消费，仅测试覆盖） | ✅ 明确废弃/接线 |

### R2 二次复核决策记录（2026-08-05）

> 以下为独立 subagent 二次复核后经用户确认的处置决策（用户偏好彻底修复，文档化仅限
> 根深蒂固不可维修项）。**全部按此执行，不再逐项上报**。

| 决策 | 结论 | 依据 |
|------|------|------|
| **IbSlot.update(fn)** | ✅ **方案 A 接通语言面 RMW**（用户确认） | 实测当前 `slot.update(fn)` 传 IBCI 函数必崩（`callable()` 判定失败落 set→`to_native()` 抛裸错）；底层 `SlotCore.update` CAS 机器完整已测，缺口仅在语言面接线。实现：`ib_class.name in ("fn_callable","behavior")` 判定（与 leaf.py 既有模式一致），fn 走同步 `.call`（fn_callable→vm.run / behavior→invoke_behavior，均同步后备）；docstring 注明 fn 锁外执行、无副作用、behavior 重试重复推理；补 3 个语言面测试（set/fn/并发） |
| **Task\* → Thread\*** | ✅ **改名授权**（用户确认） | task 模型已删、thread 唯一，语言面 `catch TaskError` 概念漂移。`TaskError/TaskCancelled/TaskFailed` → `ThreadError/ThreadCancelled/ThreadFailed`。机械改名 ~10 文件，无序列化格式依赖（错误对象运行时构造）。内部 `SpawnedTask`/`spawn` 为可选次要清理（无用户可见收益） |
| 其余二次复核项 | 按复核结论执行 | 30 项彻底修复/删除（批次 A-E），12 项确认真设计决策保留+文档化，其余保留+局部修复。见 WORKLOG 会话 14 记录 |
| P2 | R2-19 | `host/isolation_policy.py` | `level` 等字段只写不读，docstring 表格语义未实现 | ✅ 文档化实际生效字段 |
| P2 | R2-20 | `observability/events.py` | 声明 11 种事件仅 3 种有发射点（超卖） | ✅ 文档收敛为实际支持 |
| P2 | R2-21 | `engine.py:694-698` | `inherit_plugins` List 选择性继承退化全量 | ✅ 实现过滤或文档化 |
| 测试 | R2-22 | `tests/` AI MOCK 前缀 15 处镜像 | `AI_MOCK_PREFIX` 单点真理被复制 15 处 | ✅ 收敛 conftest 单点 |
| 测试 | R2-23 | `compliance/test_concurrent_llm.py:101-112` | 依赖测试名不副实（声称测数据依赖实际独立） | ✅ 改写为真依赖用例 |
| 测试 | R2-24 | `meta/test_layering.py` + `e2e` | e2e 白盒穿透内部 + 红线检测空壳 | ✅ 下沉白盒测试/修红线 |
| 测试 | R2-25 | `e2e/test_e2e_model_routing.py:85-99` | tag 大小写测试名不副实（声称报错实际验证成功） | ✅ 改写/改名 |
| 测试 | R2-26 | Engine 公开 API 零覆盖 | `register_native_module`/`set_variable`/`get_variable`/`resolve_semantics` 零测试 | ✅ 补黑盒用例 |
| 测试 | R2-27 | 其他测试卫生 | 宽捕获 `pytest.raises(Exception)`、kernel conftest 死 fixture、`make_context` 双实现、BOM 混用 | ✅ 逐项收敛 |

---

## 一、审查动作（R 系列——完整复核审查的核心）

| # | 内容 | 说明 |
|---|------|------|
| **R1** | 正式 code-review 复核 | 对三阶段主线 + 收尾全部改动做独立复核（general agent）。改前会话仅做轻量残留扫描，从未完整独立复核 |
| **R2** | code-quality 健康诊断十查 | 全仓健康审计（残留扫描/历史痕迹/双通道/双写真相/fail-fast/封装纪律） |
| **R3** | code-odor 全面异味扫描 | 特征扫描（嵌套分支/能力探测/兜底字样/反射变体） |
| **R4** | 覆盖率核对 | 新增测试是否覆盖全部新行为（subscriber 生命周期/class_ref/泛型特化分支/瞬态协议/构造入口） |
| **R5** | doc-governance 审计 | docs/ 治理流程（配合 §三 D 系列文档收敛） |

> 约束：subagent **仅可用 general agent**；每批全量 pytest 零回归；新缺陷按"不删也不修=不可接受"
> 两档处置（根本修复或彻底删除）；commit 留痕（仅本地，禁 push）。

## 二、已完成项（L 系列——审查时逐项验证）

| # | 内容 | 处置 | 决策记录 |
|---|------|------|---------|
| L1 | B3 `_by_kind` 索引有损 | ✅ 彻底删除（commit 149dd63） | WORKLOG 会话 9 |
| L2 | 根因 4：join/cancel any 兜底 | ✅ 泛型成员特化协议化根治（commit 8e0ada9） | WORKLOG 会话 9 |
| L3 | 序列化 `"done"` 字面量 | ✅ 改用 ThreadStatus（commit 149dd63） | WORKLOG 会话 9 |
| L4 | SpawnedTask Waitable 残留 | ✅ result() 死方法删除（commit 149dd63） | WORKLOG 会话 9 |
| L5 | G1 残留：值对象承载 | ✅ IbOptional 单承载收敛（commit 80b463e）；core/view 槽判定为合理句柄承载 | WORKLOG 会话 12 |
| L6 | chan/slot/subscriber 序列化空壳 | ✅ 瞬态序列化协议化（commit 3a2e5d1） | WORKLOG 会话 10 |
| L7 | 运行时泛型身份有损 | ✅ L7-A 符号/序列化侧精确化（commit 80b463e）；值 type_ref 保持基础（设计决策） | WORKLOG 会话 12 |
| L8 | 类型符号序列化身份破坏 | ✅ class_ref 类引用（commit af3ee21） | WORKLOG 会话 11 |

## 三、docs/ 技术手册未同步（D 系列——随 R5 收敛）

| # | 内容 | 影响文档 |
|---|------|---------|
| D1 | `signal` 关键字/类型移除 | `docs/subsystems` 通信/并发章节、语法文档、`KNOWN_LIMITS.md` |
| D2 | pubsub 语言面打通 + `subscriber` 新类型 | 通信/并发文档、类型参考 |
| D3 | 通信 Signal 移除裁定（零消费者空壳 + 撞名） | 相关设计记录 |
| D4 | `send_nowait` 语言面补齐 + 语义变化（无订阅者 False） | 通信文档 |
| D5 | 线程对象模型细化（thread 槽位化/thread_result IbValue/瞬态序列化协议） | 线程/值对象文档 |

## 四、thread 架构/类型系统隐患调查（T 系列——调查完成，结论浓缩于此）

> 用户观察（2026-08-04）：通用流程中针对 thread 的突兀硬编码分支 + 公理机制不统一，
> 疑 thread 架构缺陷 + 底层类型系统/公理体系隐患。调查文档已归档，结论如下。

- **确认成立**：thread 特有突兀分支 5 处（serializer 瞬态存根/thread_result 分支/_thread_init
  手工构造/instantiate 挂钩/普通调用构造路径）+ 构造机制三轨。
- **系统层根因**：统一泛型模型半落地——`resolve_member` 泛型成员特化未协议化（`_members.py`
  per-type 级联）。thread 是症状暴露最充分的成员，非独立病灶。
- **落地**：建议 1（成员特化协议化）✅ L2；建议 3（瞬态序列化协议化）✅ L6；建议 4（公理
  any 机制化满足）✅；建议 2（构造机制）重新裁定为设计语言统一、非碎片，可统一点
  `_create_blank` ✅ 已应用。完整决策见 WORKLOG 会话 9/10/12。
