# 非目的性审视清单（Aimless Review · living list）

> 无目的分析的**潜在参考**记录。非待办清单、不承诺处置。仅沉淀"为何这样设计/带来什么/未来可能问题/能跑但别扭"的观察。
> 纪律：低密度低强度；来源含 `quality-maintenance`/`code-quality` 判定的"维持现状"项；**周期性事实回顾与更新**（随 Tier B 质量维护窗口或里程碑边界），防过期/偏颇干扰主线。
> 记录格式：`[位置] 观察 ｜ 潜在风险 ｜ 来源 ｜ 状态(有效/已失效/已转出)`

---

## 策略演进（Aimless Review 自身策略）

> 每次周期性回顾时审视"审视策略"本身，更新关注点/扫描模式，回写于此。

- 关注点：设计取舍的来源与远期演化、微妙不合理、潜在偏颇。策略更新记录见下（新增观察时顺带更新）。

---

## 观察记录

### 质量维护·维持现状（来自 smell 流程，潜在参考）

| # | 位置 | 观察 | 潜在风险 | 来源 | 状态 |
|---|---|---|---|---|---|
| A1 | `ibci_modules/ibci_isys/core.py` / `ibci_idbg/core.py` | `hasattr/getattr` 防御性内省（可选项注入、调试工具、安全默认） | 协议演进时这些探测可能变恒真/恒假，或漏掉新能力 | 质量维护·维持现状 | 有效 |
| A2 | `ibci_modules/ibci_ai/core.py` `__call__` 未 probe 分支 | 未 probe 时保守按推理模型处理 + 首次告警（设计立场：不推荐 thinking、推荐直接输出） | 未来"直接输出 vs thinking"策略细化后，此回退与告警需同步演进 | 质量维护·维持现状 | 有效 |
| A3 | `llm_parsing_strategy.py` / `_prompt.py` 宽 except | 解析失败→`uncertain`/降级链（LLM 输出不确定→重试语义） | 用户 `__from_prompt__`/`__to_prompt__` 内真异常会被当作"不确定/降级"吞掉 | 质量维护·维持现状 | 有效 |
| A4 | `core/engine.py:388` | axiom 注册失败→log 继续（注册循环健壮性） | 单个 axiom 注册的隐蔽 bug 被静默跳过，难发现 | 质量维护·维持现状 | 有效 |
| A5 | `core/kernel/spec/type_ref.py:128` 等 L1-L10 循环打破局部 import | 标准运行时局部 import 环打破 | 模块环长期存在，未来重构被这些环约束（详见 `PENDING_TASKS.md` 的 PT-SMELL-3 推迟工作记录） | 质量维护·维持现状 | 有效 |

### 无目的审视（设计沉思）

| # | 位置 | 观察 | 潜在风险 | 变化 | 状态 |
|---|---|---|---|---|---|
| B1 | `core/runtime/interpreter/llm_executor/_scheduler.py` `close()`+`__del__` | `close()` 原设计"关闭后不应再调用"但代码静默重建——已按 fail-fast 改为 `_closed` 抛错；`__del__` 仍 `shutdown(wait=False)` | 思考：`wait=False` 的 `__del__` 在解释器退出时是否可靠释放线程资源？未来可复核 | 2026-08-03 | 有效 |
| B2 | `core/runtime/shared/llm_result.py` | 曾存在 `LLMResult.unwrap()`（None 分支构造 `IbNone()` 缺参，潜在 bug）——已作为死代码删除 | 提醒：值类型与"通过 Registry 获取单例"的约定若被绕过，易出此类缺参构造 bug | 2026-08-03 | 已转出（已删除） |

---

> 周期性回顾：每次改写本清单时，对"有效"条目逐条核对当前代码是否仍成立；过期/偏颇即删或标"已失效"；上升为明确缺陷转出到 `PENDING_TASKS`/`code-review`。