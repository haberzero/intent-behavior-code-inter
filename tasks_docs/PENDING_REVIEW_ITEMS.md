# 完整复核审查工作清单

> 状态：**下一阶段核心清单**（2026-08-05，用户准备开启完整复核审查工作流程）
> 用途：会话 1-12 所有改动（通信领域三阶段主线 + 收尾 L1-L8 + 泛型成员特化协议化等）的
> **完整独立复核审查**清单。R 系列为审查动作；L/D 系列为已完成项（供审查时验证）+ 未同步项。
> 审查完成后经确认删除本文件；各决策记录详见 `WORKLOG.md` 会话 6-12。

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
