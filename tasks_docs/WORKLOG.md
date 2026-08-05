# WORKLOG — 自主工作日志

> 原则：**"只记录，不断决"**——能自主决定的记录决定并推进；只有确实无法决定的才标记待决并上报。
>
> **记录策略（2026-08-05 起）**：历史会话中已讨论定案、已落地、已由 `NEXT_STEPS.md`"已完成"节
> 与代码承载的内容，随落地归档（git 历史保留完整版）。本文档只保留**仍有参考价值的决策**
> 与**关键用户裁定**。
> 最后更新：2026-08-05

---

## 一、关键用户裁定（长期约束力）

| 裁定 | 内容 | 来源 |
|------|------|------|
| 碎片化判断基准 | **碎片化 = 设计语言（用户语义形态）统一，非实现路径一致**。同类内容内部实现路径差异，只要有语义需求驱动、且不改变用户语义形态，即非碎片 | 会话 12 |
| "不删也不修" | 有缺陷/冗余的机制只能"**根本修复**"或"**彻底删除**"两档，禁止"废弃记录"中间态 | 会话 9 |
| subagent 约束 | 所有 subagent 工作（含 review）**仅允许 general agent**，禁 explore/reviewer 特化 agent | 会话 6 |
| 决策纪律 | 需拍板的决断项可大胆激进选方案；底线 = 架构原则/代码质量原则/非妥协/非 tricky/非临时兼容层/大方向主线 | 会话 1 |
| 禁 push / 破坏性重构授权 / 分支政策 | 见 AGENTS.md（权威源，此处不复制） | — |

## 二、仍有效的设计决策

| 决策 | 内容 |
|------|------|
| 运行时值 `type_ref` 保持基础 spec | 可变值（list/dict）不固有泛型身份（同一对象可被赋给 list[int]/list[str]，语义不自洽）；符号/序列化侧已精确（L7-A），值侧记录为设计决策（会话 12） |
| 通信 `Signal` 抽象移除 | 零消费者空壳 + 与 VM 控制流 Signal 撞名 → 彻底删除；`signal(...)` 语言关键字全链移除（会话 8） |
| `core`/`view` 槽 = 句柄承载 | IbChannel/IbSlot/IbSubscriber 的 core/view 槽与 thread `__slots__` 同构（句柄/内核状态经槽承载），非值对象碎片（会话 12） |
| 瞬态序列化协议 | thread/chan/slot/subscriber 统一 `__transient_state__` 存根；反序列化不复活活体（会话 10） |
| 类型符号 `class_ref` | IbClass 序列化为类名引用、反序列化重绑定 registry 真实类（会话 11） |
| 泛型成员特化协议化 | `resolve_member` per-type 级联收敛为 `GenericTypeDeclaration` 声明回调（会话 9） |

## 三、已完成工作摘要

> 会话 1-12 全部落地 unsafe-vibe-dev（本地 commit，未 push）。批次/commit 明细见
> `NEXT_STEPS.md`"已完成"节；历史会话完整记录在 git（`git log` 追溯）。

- **线程对象模型方向修正（A-F）**：`thread` 取代 spawn/join/cancel/task；async/thread 彻底分离。
- **通信领域设计完善三阶段**：B1-B4 实锤 bug + G1-G7 统一化（值对象机制/序列化/通信域）。
- **收尾 L1-L8 + T2**：_by_kind 删除 / 泛型成员特化协议化 / 序列化清理 / 瞬态序列化协议 /
  类型符号 class_ref / IbOptional 单承载 / 泛型注解符号身份 / `_create_blank` 构造入口统一。
- **R1 完整独立复核（2026-08-05，会话 13）**：三个 general agent 并行独立复核三阶段主线 +
  收尾全部改动（`e217b8b^..80b463e`）。整体正确，无高严重缺陷；新增缺陷 A1/C1/B1-B6/D1-D4
  全部处置（A1 cancel is_done 守卫、C1 multi-type list/tuple positional 序列化持久化、B 组
  死代码清理、D 组文档化）。发现清单与决策见 `PENDING_REVIEW_ITEMS.md` §〇。
- **R1 修正批（2026-08-05，D 系列重分类）**：用户质询"文档化是否违反不删也不修"触发自我
  质询重新取证，纠正初判误分类——D1（chan/slot 半接通，axiom docstring 声称 value_type
  承载未落地）、D3（send 泄漏 CommClosedError 给生产者）、D4（close 后 subscriber_count
  失真）、D6（自然完成线程 is_done() 误报 False，真 bug）均**根本修复**并补测试；D2/D5
  确认为真设计限制/效率，文档化合理。修正记录见 `PENDING_REVIEW_ITEMS.md` §〇 D 系列。
- **注释卫生清理（2026-08-05）**：用户指出近期工作（会话 6-13）在代码注释/docstring 大量
  引入任务代号/进度标记。全仓清理 66 文件：删除 L7-A/R1-Dx/G7/D1-D6/B1-B4/L8/C1/A1、
  任务 A-F/C0-C2、PT-MT-\*、阶段 2/3、疏漏 N、VP-/F-、MERGED、THREAD_DESIGN_REVISION、
  WORKLOG 会话、日期戳、文档章节号（§3.1/§8.1）等标记，保留功能说明；INV-\* 契约不变式
  码（等价公理码）保留。全量 pytest 零回归。commit db3c610（仅本地）。
- **R2 健康诊断 + 二次复核（2026-08-05，会话 14）**：code-quality 健康诊断十查，四个
  general agent 并行独立诊断（编译/类型层、运行时核心层、对象/通信/插件层、测试/引导层），
  发现约 50 项。随后用户裁定——所有"需讨论/设计限制/倾向文档化"项经四个独立 subagent
  二次复核（架构层面 + IBCI 设计思路：功能必要性/设计目的/修复长久收益），用户偏好彻底
  修复优先。**结论**：30 项升格为彻底修复/删除（批次 A-E），12 项确认真设计决策保留+文档化，
  其余保留+局部修复。**用户确认两项关键决策**：① `IbSlot.update(fn)` 方案 A 接通语言面
   RMW（复用 SlotCore 已测 CAS 机器）；② `Task* → Thread*` 语言面改名授权。完整清单见
   `PENDING_REVIEW_ITEMS.md` §〇b 与 §二次复核决策记录。
- **R2 处置完成（2026-08-05，会话 15）**：按批次 A-E + 补充项全部落地（本地 commit 序列：
  381d30e/1ee2bcb/77d0863/7473a8b/94c8e86/末批），每批全量 pytest 零回归后提交。涵盖：
  机械清理（负数误lex/CJK/动态槽/去BOM）、fail-fast（反序列化/能力查询/前缀碰撞/插件状态/
  run()）、半接通语言面（IbSlot.update 方案A 接通 CAS/media 假值/IsolationPolicy 收敛/
  str 别名/chan(T) 保真/**Task→Thread 改名**）、结构单点（泛型名结构化 TypeRef/运算符映射/
  hasattr/生成器中央化/VMTaskResult/check-gen_spec 格式对齐）、测试健康（make_context/
  root/去skip/LRU/白盒下沉+红线/Engine死API/状态断言）、补充项（enum/SnapshotManager/
  死方法簇/erasure统一/can_return_from_isolated 删除/TypeInferenceState 文档化/AI MOCK 前缀
  收敛/依赖测试改写）。保留+文档化 12 项。**验证**：全量 pytest = 1506 passed / 6 skipped
  零回归（以实跑为准）。
- **测试基线**：`python -m pytest tests/` = 1506 passed / 6 skipped（以实跑为准）。

## 四、遗留 / 待办

- **下一阶段（完整复核审查）**：`tasks_docs/PENDING_REVIEW_ITEMS.md`（R1 ✅ / R2 ✅ / R3-R5 待做 + D1-D5 docs 同步）。
- **长期规划**：`tasks_docs/PENDING_TASKS.md`（PT-SEM/PT-4.x/PT-ARCH/PT-SMELL/TEST_REFACTOR 等）。
- **固定化内容**：`tasks_docs/HANDOFF.md`（常驻交接文档：工作流程/原则/goal 模板）。
