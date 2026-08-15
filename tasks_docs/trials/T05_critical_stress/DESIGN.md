# T05_critical_stress — 批判性压力试用（2026-08-14，跨模块类表 module 化后内核）

> 2026-08-14。**试用与记录任务，不是修复任务**。目标：对跨模块同名类运行期
> module 化根治（S5 运行期闭环）后的最新内核做**全方位批判性压力试用**——以
> 挑刺/对抗态度触碰边界与易出 bug 场景，结合真实 LLM，同步核验 docs/ 全部
> 技术文档（含 KNOWN_LIMITS）。发现的缺陷只记录登记，不修复。
>
> 基线：unsafe-vibe-dev 6e68329c，全量 2614 passed / 1 skipped。

## 一、工作模式与硬约束

| 约束 | 内容 |
|------|------|
| 死循环保护 | 每例经 harness 硬超时 SIGKILL 进程组兜底；无超时不运行 |
| 记录优先 | 只记录登记，不改内核；logs/ + register.jsonl + REGISTER.md 确定性记录 |
| 分层 | mock 用例（快）+ 真实 LLM 用例（qwen3.6-35b-a3b @ 127.0.0.1:1234，先探测） |
| 文档核验 | docs/ 全量（含 KNOWN_LIMITS）；文档错误 = DOC_ISSUE 同等记录 |
| 禁 push | 全程本地 commit |

## 二、试用矩阵

### D1 — 跨模块同名类根治回归 + 边界（mock）

| 用例 | 目标 |
|------|------|
| D1-01 | geo.Box/graph.Box 方法表隔离（105/hi!） |
| D1-02 | 同模块多特化并存（geo.Box[int] vs geo.Box[str]） |
| D1-03 | 跨模块同名**非泛型**类隔离 |
| D1-04 | 模块限定类型注解（geo.Box[int] a = ...） |
| D1-05 | 三模块同名类（geo/graph/data） |
| D1-06 | 嵌套包同名类（a.sub.Box vs b.sub.Box） |
| D1-07 | 泛型继承同模块父 + 同名冲突模块并存 |
| D1-08 | 跨模块类作内置泛型实参（list[geo.Box[int]]） |
| D1-09 | 跨模块类作函数参数/返回 |
| D1-10 | 跨模块类作 thread 值类型 + 结果读取 |
| D1-11 | 同名类序列化 round-trip（type()/值访问） |
| D1-12 | 入口模块类 + 导入同名类共存（遮蔽） |

### D2 — 边界/对抗组合（mock，挑刺）

| 用例 | 目标 |
|------|------|
| D2-01 | 深递归（fib depth=200）+ 深递归线程体 |
| D2-02 | 遮蔽内建（int/len/print 用户定义） |
| D2-03 | Optional None 流（包装/解包/比较） |
| D2-04 | any 逃生（动态 any 赋用户类变量 → 守卫） |
| D2-05 | 容器边界（空 list 类型、嵌套、切片、负下标） |
| D2-06 | 生成器 yield from + break + next + 提前终止 |
| D2-07 | 闭包捕获/改写（nonlocal/cell 共享） |
| D2-08 | enum 迭代/数量/非 str 值 |
| D2-09 | switch/case 边界（default/无 fallthrough/字符串） |
| D2-10 | llmexcept 收敛 + 重试耗尽 |
| D2-11 | thread/chan/slot 并发 + 生成器组合 |
| D2-12 | 字符串操作边界（split/join/format/空串） |
| D2-13 | lambda 捕获模式（snapshot vs lambda） |
| D2-14 | auto 容器推断（混合/嵌套/空） |
| D2-15 | 元组解包类型检查边界 |
| D2-16 | 运算符重载泛型（Vec[T] __add__/__eq__） |
| D2-17 | import 星号/具名 + 同名符号碰撞 |
| D2-18 | while true + break 守卫（防死循环） |
| D2-19 | 嵌套容器身份（list[list[int]] 全层） |
| D2-20 | 函数默认参数容器/深克隆隔离 |

### D3 — 真实 LLM 批判试用（qwen3.6-35b-a3b）

| 用例 | 目标 |
|------|------|
| D3-01 | 意图 @/@! 赋值路径（真实模型遵循） |
| D3-02 | @~ 行为输出解析到类型值 |
| D3-03 | llmexcept 重试收敛 |
| D3-04 | enum LLM 成员名→值（非 str） |
| D3-05 | LLM 函数 + 意图注入 + auto_intent |
| D3-06 | LLM 输出数字/列表解析边界 |
| D3-07 | mock + 真实 LLM 混合同运行 |
| D3-08 | LLM 长提示注入保持（C1 类） |

### D4 — 文档核验（docs/ 全量，含 KNOWN_LIMITS）

经 D4-* 用例 + 并行 subagent 系统对照 docs/syntax、docs/architecture、
KNOWN_LIMITS 与实测行为，逐条记录 DOC_ISSUE。

## 三、分类与级别

- 分类：PASS | KERNEL_ISSUE | BOUNDARY | LIMIT | DOC_ISSUE | LLM_BEHAVIOR | GUARD | HARNESS
- 级别：P0（崩溃/死循环）/ P1（明确缺陷）/ P2（较轻）/ P3（文档/体验/边界）
- 非 PASS 用例登记前须对照 KNOWN_LIMITS/docs 分诊（CLASSIFICATION §四闸门）。

## 四、记录与收尾

- 每例 harness 跑 → logs/ + register.jsonl → REGISTER.md 汇总。
- 确凿缺陷登记 PENDING_TASKS（不修复）；文档错误登记 DOC_ISSUE。
- 收尾同步 NEXT_STEPS/HANDOFF/WORKLOG。全程本地 commit、禁 push。
