# _GENERICS_TRIAL_20260812 — 用户类泛型参数（class Box[T]）压力/恶意试用设计

> 2026-08-12。**试用与记录任务，不是修复任务**。目标：对新增的**用户类泛型语法**
> （PT-FEAT-3）做系统性正交/交叉/多可能性/多文件/恶意挑刺试用，找内核边界与隐性问题。
> 发现的缺陷只记录、登记，不在本任务修复。

## 一、背景

用户类泛型（class Box[T]）2026-08-12 落地（commit 35bb2de），已通过 21 e2e + 2 round-trip
+ 两轮独立复核（全量 2339 passed / 1 skipped）。**但未做系统性压力/恶意试用**——本任务补上，
对齐 `_LLM_TRIAL_20260812` 的 D1/D2/D3 方法论，聚焦**新增语法与既有语言面的正交交互**。

## 二、工作模式与硬约束（沿用用户 2026-08-12 定案）

| 约束 | 内容 |
|------|------|
| 死循环保护 | 每例经 OS 进程级硬超时（SIGKILL 进程组）+ --max-inst 指令上限双层兜底；harness 无超时不运行 |
| 记录优先 | 只记录登记，不改内核代码；文件化确定性记录（logs/ + register.jsonl + REGISTER.md） |
| 文档为主要来源 | 按 docs/ 手册撰写期望；手册问题记录 DOC-ISSUE |
| 禁 push | 全程本地 commit |

> 本试用为**纯编译/运行时语法试用**（mock 模式，无真实 LLM）。所有用例无超时不运行。

## 三、三层保护

复用 `harness/run_one.py`（进程组 SIGKILL + --max-inst + timeout 必需参数）。mock api_config
（defaults.mock:true），用例显式 `ai.set_mock_mode()`（F9 显式配置契约）。

## 四、试用矩阵设计

### D1 — 泛型核心语义（编译期/运行时单特性）

| 组 | 用例 | 目标 |
|----|------|------|
| D1-01 | 单参数特化 int/str/float/bool | 基础特化正确性 |
| D1-02 | 多参数 Pair[K,V] / 三参数 Triple[A,B,C] | 多参数映射顺序 |
| D1-03 | 嵌套实参 Box[list[int]] / Box[dict[str,int]] / list[Box[int]] | 嵌套特化身份 |
| D1-04 | 字段/方法参数/返回/局部变量 全使用面 | 类型参数在各类位置替换 |
| D1-05 | 特化后方法参数类型检查（正/负） | 类型安全 |
| D1-06 | 泛型类 as 值类型 / type() 内省 | 运行时身份 |
| D1-07 | 序列化 round-trip（含继承） | 持久化保真 |

### D2 — 正交交叉（泛型 × 既有语言面）★核心

| 组 | 交叉维度 | 目标 |
|----|---------|------|
| D2-01 | × 运算符覆写（__eq__/__add__/__getitem__ 等）| 泛型 + 运算符协议 |
| D2-02 | × 继承（多级 Sub1[T](Base[T]) / Sub2[T](Sub1[T])）| 继承链特化传递 |
| D2-03 | × Enum / × protocol 方法（__to_prompt__/__from_prompt__/__call__/__iter__）| 泛型 + 协议 |
| D2-04 | × 容器（list[Box[int]] / dict[str,Box[str]] / tuple 内）| 泛型 + 容器泛型 |
| D2-05 | × 控制流（for 迭代 Box[int] 列表 / switch 泛型值 / if 泛型字段）| 泛型 + 控制流 |
| D2-06 | × 函数（参数/返回泛型类 / fn_callable 泛型 / lambda 泛型）| 泛型 + 函数 |
| D2-07 | × 并发（thread 内构造泛型类 / chan 传泛型 / slot 存泛型）| 泛型 + 并发 |
| D2-08 | × 生成器（yield 泛型类实例 / yield from 泛型）| 泛型 + 生成器 |
| D2-09 | × 意图/行为（@~ 返回泛型类 / llmexcept 保护泛型字段）| 泛型 + LLM 面（mock）|
| D2-10 | × 闭包/嵌套函数（方法内闭包捕获泛型字段 / 泛型类内闭包）| 泛型 + 闭包 |
| D2-11 | × import/多文件（跨模块泛型类 / 泛型类 import 后特化）| 泛型 + 模块 |

### D3 — 恶意挑刺（边界/反例/半成品探测）

| 组 | 攻击面 | 目标 |
|----|--------|------|
| D3-01 | 特化数量不匹配（少参/多参/零参）| 守卫一致性 |
| D3-02 | 非法特化实参（Box[42] / Box[None] / Box[behavior] 等非常规类型）| 特化实参边界 |
| D3-03 | 类型参数名怪异（_T / T2 / 多字符 / 与成员重名 / 遮蔽内置）| 命名守卫 |
| D3-04 | 泛型自引用（class Node[T] 内 Node[T] 字段 / 递归特化 Node[Node[int]]）| 递归特化 |
| D3-05 | 继承边界（裸 Sub(Box[int]) / Sub[T](Box[T]) 少参 / 多继承? / 循环继承）| 继承链守卫 |
| D3-06 | 特化类身份（Box[int] 与 Box[str] 互赋值 / Box[int] 赋 Box / any 混入）| 类型隔离 |
| D3-07 | 运行时特化表达式（print(Box[int]) / 赋值 Box[int] / 特化 as 函数参数）| 表达式位置特化 |
| D3-08 | 组合轰炸（嵌套特化 + 继承 + 容器 + 控制流 多层叠加）| 组合爆炸边界 |
| D3-09 | 边界值（空 body 泛型类 / 无字段泛型类 / 仅方法泛型类）| 退化形态 |
| D3-10 | LLM 交叉（mock 返回泛型实例 / @~ 初始化泛型字段 / llmexcept 恢复泛型）| 泛型 + LLM 状态 |

## 五、分类与严重级别

- 分类：PASS | KERNEL_ISSUE | DOC_ISSUE | LIMIT | BOUNDARY
- 级别：P0（崩溃/死循环）/ P1（明确缺陷）/ P2（较轻）/ P3（文档/体验）
- 确认过守卫生效的"预期报错"用例标 PASS（守卫是特性）。

## 六、记录与收尾

- 每例 harness 跑 → logs/ + register.jsonl → REGISTER.md 汇总。
- 确凿缺陷登记 PENDING_TASKS（不修复）。
- 收尾同步 NEXT_STEPS/HANDOFF/WORKLOG。
