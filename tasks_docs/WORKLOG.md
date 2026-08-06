# WORKLOG — 自主工作日志

> 原则：**"只记录，不断决"**——能自主决定的记录决定并推进；只有确实无法决定的才标记待决并上报。
> 本文件只保留**仍有长期约束力的关键用户裁定**；历史叙述与 commit 明细在 git（`git log` 追溯）。
> 最后更新：2026-08-05

---

## 关键用户裁定（长期约束力）

| 裁定 | 内容 |
|------|------|
| 碎片化判断基准 | **碎片化 = 设计语言（用户语义形态）统一，非实现路径一致**。同类内容内部实现路径差异，只要有语义需求驱动、且不改变用户语义形态，即非碎片 |
| "不删也不修" | 有缺陷/冗余的机制只能"**根本修复**"或"**彻底删除**"两档，禁止"废弃记录"中间态 |
| subagent 约束 | 所有 subagent 工作（含 review）**仅允许 general agent**，禁 explore/reviewer 特化 agent |
| 决策纪律 | 需拍板的决断项可大胆激进选方案；底线 = 架构原则/代码质量原则/非妥协/非 tricky/非临时兼容层/大方向主线 |
| permissive any 需重审 | 类型系统已成熟（LHS 目标类型 / 标注 / 泛型），any 兜底不再默认合理，需按实际可达面重审 |
| 禁 push / 破坏性重构授权 / 分支政策 | 见 AGENTS.md（权威源，此处不复制） |
| PT-INTRO-1 已完成 | fn/behavior 签名形态（`type(f)`）+ `__return_type__()` 返回类型查询 **已落地（2026-08-06）**；设计决策见 PENDING_TASKS §十 |
| PT-DECIDE-1 裁定 | 行为输出具体类型必须可被 LLM 解析（用户 2026-08-06 拍板采纳推荐方案）：编译期 `SEM_BEHAVIOR_OUTPUT_NOT_PARSEABLE` + 运行时 Default 兜底 uncertain，禁止静默 box 成字符串。不采用原"uncertain"提案——无 parser 类型在 llmexcept 下重试必然空转（每轮重新调用 LLM，白耗后 `LLMRetryExhaustedError`），编译期零成本暴露根因更符合 fail-fast |
| PT-DEBT-1/2/3 完成 | 内核接口协议化（2026-08-06）：① `BoundPlugin` 容器承载 `(implementation, registry_id)` 替代 `_ibci_registry_id` 私有标记注入（隔离身份随容器流动，无硬编码字符串）；加载期跨引擎单例守卫改用 process 级 WeakKeyDictionary 保留安全语义。② RuntimeContextImpl 补通信域/协调器访问器（get_* 惰性创建 + peek_* 纯只读），LLMExecutor 补 `pending_futures_count()`；snapshot/comm/assignment/host/coordinator/iruntime 全部改走公开接口。设计要点：peek/get 双形态避免快照与开关检查产生创建副作用 |
| 内建函数群完善（2026-08-06） | 用户选推荐集：① 类型转换全局函数 `int()`/`str()`/`float()`/`bool()`（此前仅 `(int) x` 强转可用）——根因是编译期 `get_call_cap` 对 PRIMITIVE 返回 None 且 `IbClass.receive` 把类 `__call__` 一律路由到 instantiate（原生 `_int_call` 等成死代码）；修复：调用点放宽（能力层不放开，避免 `fn f = 42` 误判可调用）+ 类自身原生 `__call__`（IbNativeFunction）优先于 instantiate。② 序列辅助 `enumerate`/`zip`/`sorted`。③ **丢弃 `sum`**：与常见变量名 `sum` 冲突（`Cannot redefine constant`，dict.values 测试实证），且本属可选。④ 级联修复：for 循环元组解包 `for (int x, int y) in` 编译器符号注册缺陷（symbol_resolution_pass 只处理裸 IbName 元素）——enumerate/zip 可用的前置 |
| 内建可被用户变量遮蔽（2026-08-06） | 用户拍板实现：内建**函数**（is_intrinsic=True）是可遮蔽默认绑定，用户声明同名变量即遮蔽（`int len = 5`）；内建**类型**（is_intrinsic=False，setup_context 注入未打 is_intrinsic 标记）不可遮蔽；对内建名的直接赋值仍被拒绝（编译期 SEM_TYPE_MISMATCH + 运行时 assign 的 is_const 路径）。实现点：`ScopeImpl.define` 的 const 检查加 `not existing.is_intrinsic` 条件 + 遮蔽时清除旧 intrinsic uid 绑定（防孤儿符号）。后果：`sum` 冲突已无（`int sum = 0` 合法），内建集可放心扩充 |
| 内建集二次扩充（2026-08-06） | 遮蔽就绪后重新纳入 `sum`，并追加 `reversed`/`all`/`min`/`max`（集合与多参两种形态，Python 兼容）。**丢弃 `any`**：与 IBCI 动态类型名 `any` 冲突（`any` 是预置类型，实测调用落到 Python 的 any），命名碰撞无法消解——`all` 保留（无类型冲突） |

---

## 仍有效的设计决策

> 收敛至 `PENDING_TASKS.md` §十（单一事实来源，避免双维护）。本文件不再复制。
