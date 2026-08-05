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
| **D1** | 设计限制 | `symbol_collection_pass` | `chan[str]`/`slot[int]` 注解实参不保留（chan/slot 不在统一泛型模型，pre-existing） | ✅ 文档化 KNOWN_LIMITS §10.2 | R1 提交 |
| **D2** | 设计限制 | `channel.py send_nowait` | 多订阅者部分满时返回 False 但消息已部分投递 | ✅ docstring 明确语义边界 | R1 提交 |
| **D3** | 设计限制 | `channel.py send` | fan-out 与订阅者并发 close 竞态（pre-existing） | ✅ docstring 记录竞态边界 | R1 提交 |
| **D4** | 设计限制 | `channel.py close` | close 后 subscriber_count 仍计入已关订阅者（纯内省瑕疵） | ✅ docstring 记录边界 | R1 提交 |

### C1 根因补充（比预期深）

实证发现 multi-type list 注解在**编译期构建**即退化为 `list[]`：`factory.create_list` 用
`zip(names, modules)` 且 modules 为空时产出空对 → `list[]` 且 allowed 丢失。修复：modules
缺省补 `[None]*len`，配合 serializer/rehydrator 持久化闭环后 `list[int,str]` 往返保真。

### R1 复核范围

`git diff e217b8b^..80b463e`（三阶段主线 + 收尾 L1-L8，19 commit，53 文件）。

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
