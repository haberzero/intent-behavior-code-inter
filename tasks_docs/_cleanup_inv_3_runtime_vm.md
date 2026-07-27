# 注释卫生清单 #3 — runtime/vm · interpreter · objects · modules

> 范围：`core/runtime/vm/`、`core/runtime/interpreter/`、`core/runtime/objects/`、`core/runtime/modules/`
> 模式：只读分析，未改任何代码。本文件为清理建议清单，非已执行清理。
> 行号以实跑仓库当前状态为准（CRLF / UTF-8）。

## 分类图例

| CATEGORY | 规则 |
|---|---|
| TC / ADR / PT / DATE / DOC / CODE / DOCREF | 删除指针 / 代号 / 章节号 / 历史叙述，**保留**功能说明 |
| ERR (SC / LT / CF / OM / SEM / DEP / PAR / INV) | **KEEP+normalize**（保留，必要时轻量规整） |

代号捕获集：G1-G6 / D1-D6 / H1-H3 / NS-x / P0-P7 / C2-C13 / B1-B2 / 方案A-B / SC-x / LT-x / CF-x / OM-x / GC-x / PT-* / ADR-* / §节号 / tasks_docs 指针 / 历史叙述。
**不 flagged**：功能性"锚点"(path anchor)、"Layer N/Phase N/STAGE N"(算法阶段)、"重试错误历史"(retry error log)。

> 说明：SC-x / LT-x 在 ERR 名单内 → KEEP；GC-x 不在 ERR 名单 → 按 CODE 处理（删代号、留功能说明）。

---

## 清单

| # | location | CATEGORY | current_snippet | proposed_cleaning |
|---|---|---|---|---|
| 1 | core/runtime/modules/file_impl.py:4 | ADR/CODE | `Kernel-native IBCI ``file`` 模块实现（ADR-020 G6）。` | 删 `（ADR-020 G6）`；留 "Kernel-native IBCI file 模块实现。" |
| 2 | core/runtime/modules/file_impl.py:7 | DATE | `…不是 Python 的 ``file`` 内建对象（Python 2 历史内建）。` | 删 "历史"；留 "Python 2 内建"（功能性 shadowing 说明） |
| 3 | core/runtime/modules/file_impl.py:17-18 | TC/DOCREF | `长期规划：…（见 ``tasks_docs/PENDING_TASKS.md §PT-ARCH-30``）。` | 删 `（见 tasks_docs/PENDING_TASKS.md §PT-ARCH-30）` 指针；前向"长期规划/计划未来迁移"指针一并删 |
| 4 | core/runtime/modules/file_impl.py:36 | DATE | `与旧 ``ibci_file`` 插件不同：` | 删 "与旧 ibci_file 插件不同：" 历史框架；留功能性 bullet |
| 5 | core/runtime/modules/file_impl.py:191 | PT | `# PT-ARCH-27：llmexcept retry body 中禁用 overwrite 写入，避免污染快照。` | 删 `PT-ARCH-27：`；留 "llmexcept retry body 中禁用 overwrite 写入，避免污染快照。" |
| 6 | core/runtime/modules/file_impl.py:206 | PT | `# PT-ARCH-27：llmexcept retry body 中禁用 overwrite 写入。` | 删 `PT-ARCH-27：`；留功能性说明 |
| 7 | core/runtime/objects/deep_clone.py:6-10 | DATE | `历史\n----\n原实现集中在 LLMExceptFrame._try_deep_clone…` | 删 "历史" 小节头 + "原实现集中在…" 历史叙述；留 "snapshot 路径也需深克隆能力，抽到独立模块避免循环依赖与重复实现" |
| 8 | core/runtime/objects/deep_clone.py:85-87 | PT | `调用 fork() 得到值快照。PT-2.1：使 intent_context 作为类字段参与 llmexcept 快照/恢复…` | 删 `PT-2.1：`；留 "使 intent_context 作为类字段参与 llmexcept 快照/恢复获得独立副本语义" |
| 9 | core/runtime/objects/deep_clone.py:96-98 | DATE | `之前 type(val) is KernelIbObject 的严格判定会让所有 IbValue 子类直接滑落为"不可克隆"…` | 删 "之前…静默丢失" 历史 bug 叙述；留 "内存型 IbValue 子类（如 media/file_handle）：克隆 payload 与字段。" |
| 10 | core/runtime/objects/cell.py:8 | ERR(SC) | `* SC-3 (Cell 语义): Cell 变量通过 IbCell 间接存储…` | KEEP+normalize（公理引用） |
| 11 | core/runtime/objects/cell.py:11 | ERR(SC) | `* SC-4 (自由变量捕获): …` | KEEP+normalize |
| 12 | core/runtime/objects/cell.py:14 | ERR(LT) | `* LT-2 (Cell 延长生命周期): …` | KEEP+normalize |
| 13 | core/runtime/objects/cell.py:16 | ERR(LT) | `* LT-3 (snapshot 自包含性): …` | KEEP+normalize |
| 14 | core/runtime/objects/cell.py:29 | CODE | `* 提供 trace_refs() 钩子供未来 GC 根集合扫描使用 (公理 GC-2)。` | 删 `(公理 GC-2)`；留 "供 GC 根集合扫描使用" |
| 15 | core/runtime/objects/cell.py:31 | CODE | `本模块为 fn 新语法（IbCell 集成）与 GC 根集合（公理 GC-2）提供基础原语；` | 删 `（公理 GC-2）`；留功能性 |
| 16 | core/runtime/objects/cell.py:58 | ERR(SC) | `(公理 SC-3 / SC-4)。` | KEEP+normalize |
| 17 | core/runtime/objects/cell.py:123 | CODE | `# GC 钩子（供追踪式 GC 根集合扫描使用，公理 GC-2）` | 删 "公理 GC-2"；留 "GC 钩子（供追踪式 GC 根集合扫描使用）" |
| 18 | core/runtime/objects/file_handle.py:43 | PT | `# PT-ARCH-24: path 是 field，无 I/O。` | 删 `PT-ARCH-24: `；留 "path 是 field，无 I/O。" |
| 19 | core/runtime/objects/media_types.py:6 | ADR | `Per ADR-014/016: 三种 media 类型现在是 IbFileHandle 的磁盘型子类…` | 删 `Per ADR-014/016: ` + "现在"；留 "三种 media 类型是 IbFileHandle 的磁盘型子类…" |
| 20 | core/runtime/objects/media_types.py:9 | ADR | `Per ADR-012: 作为普通类名注册（非关键字）。` | 删 `Per ADR-012: `；留 "作为普通类名注册（非关键字）。" |
| 21 | core/runtime/objects/media_types.py:60 | PT | `# PT-ARCH-24: format 是 field，从文件名扩展名推导，无 I/O。` | 删 `PT-ARCH-24: `；留功能性 |
| 22 | core/runtime/objects/media_types.py:94 | PT | `# PT-ARCH-24: format 是 field，从文件名扩展名推导，无 I/O。` | 删 `PT-ARCH-24: `；留功能性（同 #21） |
| 23 | core/runtime/objects/media_types.py:129 | PT | `# PT-ARCH-24: format 是 field，从文件名扩展名推导，无 I/O。` | 删 `PT-ARCH-24: `；留功能性（同 #21） |
| 24 | core/runtime/objects/media_types.py:153-155 | PT | `# PT-ARCH-25: media 静态构造入口：audio.from_file / image.from_file / video.from_file` | 删 `PT-ARCH-25: `；留 "media 静态构造入口：…" |
| 25 | core/runtime/objects/media_backing.py:11 | CODE | `- 无 ``MemoryBacking``：内存型 media 在 G5 后整体淘汰。` | 删 "在 G5 后整体淘汰"；留 "无 MemoryBacking" |
| 26 | core/runtime/objects/intent_context.py:170 | DATE | `这是 LLMExceptFrame restore 历史路径与 intent_context.merge(other) OOP API 共享的实现…` | 删 "LLMExceptFrame restore 历史路径与" 历史；留 "intent_context.merge(other) 的实现：均为'用 other 内容覆盖 self'" |
| 27 | core/runtime/objects/intent_context.py:191 | PT | `典型场景（PT-2.1 多 intent_context 组合）::` | 删 `（PT-2.1 多 intent_context 组合）`；留 "典型场景::" |
| 28 | core/runtime/objects/intent_context.py:249 | DATE | `（旧代码通过原地修改 previous.parent 破坏共享结构的 Bug 已修复）。` | 删整段历史 bug 注释 |
| 29 | core/runtime/objects/intent_context.py:272 | DATE | `（旧代码通过原地修改 previous.parent 破坏共享结构的 Bug 已修复）。` | 删整段历史 bug 注释（同 #28） |
| 30 | core/runtime/objects/intent_context.py:297 | PT | `用于 PT-2.1：把 intent_context 实例注入到 behavior 表达式的…` | 删 `用于 PT-2.1：`；留 "把 intent_context 实例注入到 behavior 表达式的…" |
| 31 | core/runtime/interpreter/execution_context.py:49 | DOCREF | `# 规范路径解析器（entry_dir 单锚点，§6.1 契约的唯一实现）。` | 删 `§6.1 契约的唯一实现`；留 "规范路径解析器（entry_dir 单锚点）。"（单锚点=path anchor 保留） |
| 32 | core/runtime/interpreter/execution_context.py:133 | CODE | `"""C13：当前 ExecutionContext 关联的 VMExecutor（由 Interpreter 注入）。` | 删 `C13：`；留功能性 |
| 33 | core/runtime/interpreter/execution_context.py:175 | PT | `"""PT-ARCH-25: 由 Interpreter 注入，供 file_handle/media I/O 做沙箱校验。"""` | 删 `PT-ARCH-25: `；留功能性 |
| 34 | core/runtime/interpreter/execution_context.py:184 | PT | `"""PT-ARCH-27: 当前处于 llmexcept retry body 的嵌套深度（0 = 不在其中）。"""` | 删 `PT-ARCH-27: `；留功能性 |
| 35 | core/runtime/interpreter/execution_context.py:188 | PT | `"""PT-ARCH-27: 进入 llmexcept retry body 时调用。"""` | 删 `PT-ARCH-27: `；留功能性 |
| 36 | core/runtime/interpreter/execution_context.py:192 | PT | `"""PT-ARCH-27: 退出 llmexcept retry body 时调用（需与 enter 配对）。"""` | 删 `PT-ARCH-27: `；留功能性 |
| 37 | core/runtime/interpreter/execution_context.py:278 | DOCREF | `所有相对路径的统一解析入口（委托 PathResolver，§6.1 契约的唯一实现）。` | 删 `§6.1 契约的唯一实现`；留功能性 |
| 38 | core/runtime/interpreter/permissions.py:14 | ADR/CODE | `# ADR-019 D2/Stage D：root_dir 已由 engine 规范化，消费者信任，仅 IbPath 包装。` | 删 `ADR-019 D2/Stage D：`；留 "root_dir 已由 engine 规范化，消费者信任，仅 IbPath 包装。" |
| 39 | core/runtime/interpreter/runtime_context.py:29 | DATE | `# 替代历史的硬编码名单 (``"len", "print", "range", ...``)。` | 删 "历史的"；留 "替代硬编码名单 (...)" |
| 40 | core/runtime/interpreter/runtime_context.py:211 | ERR(SC) | `将符号提升为 Cell 变量（公理 SC-3）。` | KEEP+normalize |
| 41 | core/runtime/interpreter/runtime_context.py:218 | ERR(SC) | `若本作用域没有该 UID，向上查找父作用域递归处理（SC-4 向外层捕获）。` | KEEP+normalize |
| 42 | core/runtime/interpreter/runtime_context.py:243 | CODE/DATE | `…是否已提升为 Cell 变量（C12 封装替代私有 _cell_map 探测）。` | 删 `（C12 封装替代私有 _cell_map 探测）`；留功能性 |
| 43 | core/runtime/interpreter/runtime_context.py:251 | CODE | `低级符号写入：绕过类型检查与 box 操作（VM 特殊路径专用，C12）。` | 删 `，C12`；留功能性 |
| 44 | core/runtime/interpreter/runtime_context.py:280 | CODE | `枚举本作用域…的所有 IbCell（公理 GC-2 根集合扫描入口）。` | 删 "公理 GC-2"；留 "根集合扫描入口" |
| 45 | core/runtime/interpreter/runtime_context.py:336 | PT | `# 最大 llmexcept 嵌套深度限制（PT-1.3）` | 删 `（PT-1.3）`；留 "最大 llmexcept 嵌套深度限制" |
| 46 | core/runtime/interpreter/runtime_context.py:340 | DATE | `# 已升级为 IbLLMCallResult IBCI 类型；set_last_llm_result() 负责转换。` | 删 "已升级为"；留 "IbLLMCallResult IBCI 类型；set_last_llm_result() 负责转换。" |
| 47 | core/runtime/interpreter/runtime_context.py:558 | DATE | `# 替代历史的硬编码名单 ("len", "print", "range", "input", "get_self_source")。` | 删 "历史的"；留功能性（同 #39） |
| 48 | core/runtime/interpreter/runtime_context.py:582 | DATE | `# IDBG 过滤策略：目前为了对齐旧测试，过滤掉非基础类型和下划线变量` | 删 "目前为了对齐旧测试"；留 "IDBG 过滤策略：过滤掉非基础类型和下划线变量" |
| 49 | core/runtime/interpreter/runtime_context.py:837 | CODE | `枚举 GC 根集合中的所有 IbObject（公理 GC-2）。` | 删 `（公理 GC-2）`；留功能性 |
| 50 | core/runtime/interpreter/runtime_context.py:845 | CODE | `本方法是 IBCI 规范层 GC-2 的接口落地。` | 删 "GC-2"；留 "IBCI 规范层 GC 根集合接口落地" |
| 51 | core/runtime/interpreter/llm_except_frame.py:73 | CODE | `saved_vars: 方案A深克隆变量快照 {变量名 -> 克隆值}` | 删 "方案A"；留 "深克隆变量快照" |
| 52 | core/runtime/interpreter/llm_except_frame.py:74 | CODE | `saved_protocol_states: 方案B用户协议快照 {变量名 -> (原始对象, __snapshot__()返回值)}` | 删 "方案B"；留 "用户协议快照" |
| 53 | core/runtime/interpreter/llm_except_frame.py:83 | CODE | `快照策略（方案B优先，方案A兜底）:` | 删 "方案B/方案A" 代号；改 "用户协议优先，深克隆兜底" |
| 54 | core/runtime/interpreter/llm_except_frame.py:89 | CODE | `对于未定义 ``__snapshot__`` 的类型，自动使用方案A（``_try_deep_clone``）。` | 删 "方案A"；留 "自动使用深克隆" |
| 55 | core/runtime/interpreter/llm_except_frame.py:117 | CODE | `# 方案B：用户协议快照（__snapshot__ / __restore__）` | 删 `方案B：`；留 "用户协议快照" |
| 56 | core/runtime/interpreter/llm_except_frame.py:119 | CODE | `# 当用户 IBCI 类定义了 func __snapshot__ / func __restore__，此字段优先于方案A…` | 删 "方案A"；留 "优先于深克隆" |
| 57 | core/runtime/interpreter/llm_except_frame.py:176 | CODE | `**方案B（用户协议，优先）**：` | 删 "方案B"；留 "用户协议，优先" |
| 58 | core/runtime/interpreter/llm_except_frame.py:180 | CODE | `如果 ``__snapshot__`` 调用出现异常，自动降级到方案A` | 删 "方案A"；留 "自动降级到深克隆" |
| 59 | core/runtime/interpreter/llm_except_frame.py:182 | CODE | `**方案A（自动深克隆，回退）**：` | 删 "方案A"；留 "自动深克隆，回退" |
| 60 | core/runtime/interpreter/llm_except_frame.py:199 | CODE | `# 方案B 优先：用户类定义了 __snapshot__ / __restore__ 协议方法` | 删 "方案B"；留功能性 |
| 61 | core/runtime/interpreter/llm_except_frame.py:208 | CODE | `continue  # 跳过方案A克隆` | 删 "方案A"；留 "跳过克隆" |
| 62 | core/runtime/interpreter/llm_except_frame.py:212 | CODE | `# 方案A：自动深克隆` | 删 `方案A：`；留 "自动深克隆" |
| 63 | core/runtime/interpreter/llm_except_frame.py:282 | CODE | `**方案B（用户协议，原地恢复）**：` | 删 "方案B"；留功能性 |
| 64 | core/runtime/interpreter/llm_except_frame.py:288 | CODE | `**方案A（替换绑定）**：` | 删 "方案A"；留 "替换绑定" |
| 65 | core/runtime/interpreter/llm_except_frame.py:296 | CODE | `# 方案B：通过 __restore__ 协议原地恢复用户对象` | 删 `方案B：`；留功能性 |
| 66 | core/runtime/interpreter/llm_except_frame.py:310 | CODE | `# 方案A：每次恢复时从黄金快照重新深克隆，防止上一轮 llmexcept body 修改了快照对象` | 删 `方案A：`；留功能性 |
| 67 | core/runtime/interpreter/llm_executor/_core.py:3 | DATE | `本模块是 ``llm_executor`` 包拆分后的"核心"切片…` | 删 "拆分后的" 历史；留 "llm_executor 包的核心切片…" |
| 68 | core/runtime/interpreter/llm_executor/_core.py:135 | PT | `PT-ARCH-5 Group 3：消除 4 个 ``invoke_*`` 方法的近重复后处理。` | 删 `PT-ARCH-5 Group 3：`；留 "消除 invoke_* 方法的近重复后处理" |
| 69 | core/runtime/interpreter/llm_executor/_core.py:151 | CODE/compat | `- str: 纯文本用户提示词（向后兼容路径）` | 删 "（向后兼容路径）" 或改 "（纯文本路径）"；留功能性 |
| 70 | core/runtime/interpreter/llm_executor/_core.py:187-190 | TC/DOCREF | `NOTE [未来演进 - VM 信号/中断机制]: …（见 PENDING_TASKS §十四）…` | 删 `（见 PENDING_TASKS §十四）` 指针 + 前向 NOTE；留功能性 "LLM provider 层失败…llmexcept retry 无效…直接抛 ThrownException" |
| 71 | core/runtime/interpreter/llm_executor/_prompt.py:109 | CODE/compat | `"""同步版段求值（兼容入口）。` | 删 "（兼容入口）" 或改 "同步版段求值入口"；留功能性 |
| 72 | core/runtime/interpreter/llm_executor/_prompt.py:114 | DATE | `- 不经 VM 调度的旧测试路径` | 删 "旧"；留 "不经 VM 调度的测试路径" |
| 73 | core/runtime/interpreter/llm_executor/_prompt.py:121 | CODE/compat | `- str: 纯文本内容（向后兼容路径）` | 删 "（向后兼容路径）" |
| 74 | core/runtime/interpreter/llm_executor/_prompt.py:153 | CODE/compat | `- 纯文本情况：返回拼接后的 str（向后兼容）` | 删 "（向后兼容）" |
| 75 | core/runtime/interpreter/llm_executor/_prompt.py:199 | CODE/compat | `# 向后兼容：全部为纯文本时返回拼接 str` | 删 "向后兼容："；留 "全部为纯文本时返回拼接 str" |
| 76 | core/runtime/interpreter/llm_executor/_behavior.py:79 | DATE | `# 历史的 IntentNode 链表 / 已展平 list 路径已无产生方；命中即为契约违反。` | 删 "历史的 IntentNode 链表 / 已展平 list 路径已无产生方；" 历史；留 "命中即为契约违反" |
| 77 | core/runtime/interpreter/llm_executor/_scheduler.py:9-10 | DATE | `分隔注释块 (LLMScheduler - dispatch_eager / resolve / 线程池管理) 原位于 ``llm_executor.py`` 第 517-519 行。` | 删整段 "分隔注释块…原位于…第 517-519 行" 历史叙述 |
| 78 | core/runtime/interpreter/llm_executor/__init__.py:3 | DATE | `原单文件 ``llm_executor.py`` (~1132 行) 拆分为以下切片…` | 删 "原单文件…拆分为以下切片" 历史；留 "llm_executor 包通过 mixin 组合为 LLMExecutorImpl" |
| 79 | core/runtime/interpreter/llm_result.py:1 | TC/compat | `# 向后兼容垫片 -- 实际定义已移至 core/runtime/shared/llm_result.py` | compat 垫片文件 + 注释；flag（整文件为 compat 垫片，违反"禁止 compat shim"） |
| 80 | core/runtime/interpreter/constants.py:1 | TC/compat | `# 向后兼容垫片 -- 实际定义已移至 core/runtime/shared/op_constants.py` | compat 垫片文件 + 注释；flag（同 #79） |
| 81 | core/runtime/interpreter/interpreter.py:8 | CODE | `# 架构边界说明：Interpreter = 纯协调器（P7 后最终架构）` | 删 `（P7 后最终架构）`；留 "Interpreter = 纯协调器" |
| 82 | core/runtime/interpreter/interpreter.py:13 | CODE/DATE | `# 最终文件结构（P2-P7 全部完成后）：` | 删 `（P2-P7 全部完成后）`；留 "最终文件结构：" |
| 83 | core/runtime/interpreter/interpreter.py:26 | CODE/compat(stale) | `# 不存在任何向后兼容包装层或残留 visit() 路径。` | 陈旧断言（与 #79/#80/#96 矛盾）；删除或更正——compat 垫片实际存在 |
| 84 | core/runtime/interpreter/interpreter.py:134 | TC/DOCREF | `# 注意：instance_id 默认值 "main" 在多解释器场景下存在碰撞风险（见 PENDING_TASKS.md §10.3）` | 删 `（见 PENDING_TASKS.md §10.3）`；留 "instance_id 默认值 main 在多解释器场景下存在碰撞风险" |
| 85 | core/runtime/interpreter/interpreter.py:495 | CODE | `C13 增强：构造完成后立即把引用写入 ExecutionContext.vm_executor…` | 删 `C13 增强：`；留功能性 |
| 86 | core/runtime/interpreter/interpreter.py:636-637 | CODE/DATE | `# P1：使用 _get_vm_executor().run() 代替旧递归 visit()，消除一处双轨制锚点…` | 删 `P1：` + "代替旧递归 visit()" 历史；留 "使用 _get_vm_executor().run() 预求值（CPS 主路径）" |
| 87 | core/runtime/interpreter/interpreter.py:681 | CODE | `# P0-3: 显式绑定运算符方法（统一初始化路径）` | 删 `P0-3: `；留 "显式绑定运算符方法（统一初始化路径）" |
| 88 | core/runtime/vm/vm_executor.py:59 | CODE | `# 通过 frame_stack_depth 属性暴露，供调试器 / NS-1 测试观察 CPS 栈深度。` | 删 "NS-1"；留 "供调试器/测试观察 CPS 栈深度" |
| 89 | core/runtime/vm/vm_executor.py:84-85 | CODE | `（NS-1：_vm_invoke_behavior / _vm_invoke_llm_function yield 后，本属性应 ≥ 2）` | 删 `NS-1：`；留功能性 |
| 90 | core/runtime/vm/vm_executor.py:122 | CODE | `# P4b：所有 AST 节点类型均已有 CPS handler…` | 删 `P4b：`；留功能性 |
| 91 | core/runtime/vm/vm_executor.py:134 | CODE | `"""C10 + C6 + C11：执行一个语句列表（模块或函数体）。` | 删 `C10 + C6 + C11：`；留 "执行一个语句列表（模块或函数体）。" |
| 92 | core/runtime/vm/vm_executor.py:136-137 | CODE/DATE | `C11 后：body 中的 IbLLMExceptionalStmt 节点已经是正则 stmt（替换了原来的 target）…` | 删 `C11 后：` + 规整 "替换了原来的 target"；留 "body 中的 IbLLMExceptionalStmt 节点已是正则 stmt，直接 run() 即可" |
| 93 | core/runtime/vm/vm_executor.py:139-141 | DATE | `替代 Interpreter.execute_module() 与 IbUserFunction.call() 中各自维护的内联 body 循环…` | 删 "替代…各自维护的内联 body 循环" 历史；留 "确保多 Interpreter 并发场景下两条路径保持一致" |
| 94 | core/runtime/vm/vm_executor.py:150 | CODE | ```UnhandledSignal``（C6）：顶层未消费的控制信号直接以 UnhandledSignal 形式向调用方传播。` | 删 `（C6）`；留功能性 |
| 95 | core/runtime/vm/vm_executor.py:251 | CODE | `# P4b：dispatch table 覆盖所有 43 个节点类型…` | 删 `P4b：`；留功能性 |
| 96 | core/runtime/vm/task.py:24 | CODE | `:class:UnhandledSignal 是唯一的边界异常（C5）…` | 删 `（C5）`；留功能性 |
| 97 | core/runtime/vm/task.py:28-30 | TC/compat | `注：…此处重新导出以保持 vm 包内 ``from core.runtime.vm.task import ControlSignal`` 的向后兼容。` | 删 "以保持…向后兼容" compat 指针；留 "重新导出 vm 包内 ControlSignal"（或评估该 re-export 是否仍必要） |
| 98 | core/runtime/vm/handlers/__init__.py:42-43 | DATE | `本包由原单文件 ``core/runtime/vm/handlers.py`` 机械拆分而来…` | 删 "由原单文件…机械拆分而来" 历史；留 "按节点类别组织为子模块" |
| 99 | core/runtime/vm/handlers/_shared.py:4-5 | DATE | `本模块由原 ``core.runtime.vm.handlers`` 纯机械拆分而来，无任何逻辑改动；函数体逐字保留。` | 删整段历史叙述；留 "跨类别 CPS 辅助函数" |
| 100 | core/runtime/vm/handlers/_shared.py:33 | DATE | `将原来 ``IbFnCallable.call()`` 中的 ``ec.visit(target_uid)`` 替换为 ``yield target_uid``…` | 删 "将原来…替换为" 历史；留 "使 lambda/snapshot 体完全在 VM CPS 循环中执行" |
| 101 | core/runtime/vm/handlers/_shared.py:104 | CODE | `…the practical snapshot / debug-visibility guarantee called for by NS-1.` | 删 "called for by NS-1"；留功能性 |
| 102 | core/runtime/vm/handlers/_shared.py:110 | CODE | `NS-3：始终使用**调用现场**的 ``executor.ec`` 作为执行机制…` | 删 `NS-3：`；留功能性 |
| 103 | core/runtime/vm/handlers/llm_behavior.py:4 | DATE | `由原 ``core.runtime.vm.handlers`` 纯机械拆分而来，无逻辑改动。` | 删整段历史叙述 |
| 104 | core/runtime/vm/handlers/llm_behavior.py:25 | DATE | `把原来 ``StmtHandler.visit_IbLLMExceptionalStmt`` 中的 Python try/except retry 循环迁移到 VMExecutor…` | 删 "把原来…迁移到" 历史；留 "llmexcept 语句的 CPS 调度器实现" |
| 105 | core/runtime/vm/handlers/llm_behavior.py:34 | DATE | `c. CPS 执行 target（yield target_uid；若未支持则 fallback）` | 删 "若未支持则 fallback" 历史；留 "CPS 执行 target（yield target_uid）" |
| 106 | core/runtime/vm/handlers/llm_behavior.py:81 | CODE/DATE | `# P4：dispatch table 覆盖所有 43 个节点类型，else 分支为死代码已删除。` | 删 `P4：` + "else 分支为死代码已删除" 历史；留 "dispatch table 覆盖所有节点类型" |
| 107 | core/runtime/vm/handlers/llm_behavior.py:100 | PT | `# PT-ARCH-27：在 retry body 中禁用 write_overwrite 写入。` | 删 `PT-ARCH-27：`；留功能性 |
| 108 | core/runtime/vm/handlers/llm_behavior.py:129 | CODE/compat | `"""``@`` / ``@!`` 单次意图注释节点的兼容执行路径。"""` | 删 "兼容" 或改 "执行路径"；留 "@ / @! 单次意图注释节点执行路径" |
| 109 | core/runtime/vm/handlers/llm_behavior.py:293 | ERR(SC) | `"""lambda / snapshot 表达式：构造 IbFnCallable 或 IbBehavior（公理 SC-3/SC-4）。"""` | KEEP+normalize |
| 110 | core/runtime/vm/handlers/llm_behavior.py:300 | ERR(SC) | `* **lambda**：自由变量通过共享 IbCell 捕获（SC-4）。` | KEEP+normalize |
| 111 | core/runtime/vm/handlers/llm_behavior.py:342 | ERR(SC) | `# lambda：共享 IbCell（promote_to_cell 返回 None 表示全局变量，SC-4）。` | KEEP+normalize |
| 112 | core/runtime/vm/handlers/control_flow.py:4 | DATE | `由原 ``core.runtime.vm.handlers`` 纯机械拆分而来，无逻辑改动。` | 删整段历史叙述 |
| 113 | core/runtime/vm/handlers/control_flow.py:184-186 | DATE | `此方案通过 AST 字段…直接引用 handler，避免了旧 ``node_protection`` 侧表 + ``_apply_protection_redirect`` 重定向机制…` | 删 "避免了旧 node_protection 侧表…隐式覆写问题" 历史；留 "通过 AST 字段直接引用 handler" |
| 114 | core/runtime/vm/handlers/declarations.py:4 | DATE | `由原 ``core.runtime.vm.handlers`` 纯机械拆分而来，无逻辑改动。` | 删整段历史叙述 |
| 115 | core/runtime/vm/handlers/declarations.py:34 | DATE | `无需递归 ``visit()``，故无 yield--``if False: yield`` 满足调度协议。` | 删 "无需递归 visit()" 历史；留 "if False: yield 满足调度协议（维持生成器签名）" |
| 116 | core/runtime/vm/handlers/dispatch.py:4 | DATE | `由原 ``core.runtime.vm.handlers`` 纯机械拆分而来，无逻辑改动。` | 删整段历史叙述 |
| 117 | core/runtime/vm/handlers/leaf.py:4 | DATE | `由原 ``core.runtime.vm.handlers`` 纯机械拆分而来，无逻辑改动。` | 删整段历史叙述 |
| 118 | core/runtime/vm/handlers/leaf.py:199 | CODE | `# IbBehavior / IbLLMFunction: CPS 内联以使 LLM 帧受 VM 调度管理（NS-1）。` | 删 `（NS-1）`；留 "CPS 内联以使 LLM 帧受 VM 调度管理" |
| 119 | core/runtime/vm/handlers/leaf.py:294-295 | DATE | `此逻辑从 IbString.cast_to() 迁移至此，因为 LLM 不确定性检测属于 VM handler 层职责…` | 删 "此逻辑从 IbString.cast_to() 迁移至此" 历史；留 "LLM 不确定性检测属于 VM handler 层职责" |
| 120 | core/runtime/vm/handlers/assignment.py:4 | DATE | `由原 ``core.runtime.vm.handlers`` 纯机械拆分而来，无逻辑改动。` | 删整段历史叙述 |
| 121 | core/runtime/vm/handlers/assignment.py:35 | DATE | `…均通过 CPS ``_vm_assign_to_target`` 处理，不再穿透到 ``StmtHandler._assign_to_target`` 递归路径。` | 删 "不再穿透到 StmtHandler._assign_to_target 递归路径" 历史；留功能性 |
| 122 | core/runtime/vm/handlers/assignment.py:37-38 | DATE | `is_callable_instance 路径改用 ``yield value_uid``--…无需 fallback_visit。` | 删 "改用" + "无需 fallback_visit" 历史；留功能性 |
| 123 | core/runtime/vm/handlers/assignment.py:105-106 | DATE | `# is_callable_instance 路径：…故无需 fallback_visit--直接 yield 走 CPS 调度。` | 删 "无需 fallback_visit" 历史；留功能性 |
| 124 | core/runtime/objects/primitives/callables.py:287 | CODE | `NS-3：EC 解析优先级 -- 调用现场 ContextVar > 定义时刻字段。` | 删 `NS-3：`；留 "EC 解析优先级：调用现场 ContextVar > 定义时刻字段" |

---

## 备注（非 flagged 项，记录判定依据）

- `llm_except_frame.py:126 "重试错误历史，按发生顺序追加。"` — retry error log，不 flag。
- `llm_except_frame.py:368 "…保留 error_history 作为跨重试可追踪历史。"` — retry error log，不 flag。
- `execution_context.py:49/278 "entry_dir 单锚点"` — path anchor，保留（仅删 §6.1 章节号）。
- `interpreter.py:20 "execute_module, STAGE 1-5 初始化"` — 算法阶段，不 flag。
- 各处 "公理化设计 / 公理层 / 类型公理"（kernel/*, primitives/*, sentinels.py 等）— 功能性设计词汇，无代号，不 flag。
- `interpreter.py:90 "详见 core.runtime.objects.primitives.IbBehavior"` — 经核实 IbBehavior 确在 `primitives/callables.py:167`，路径准确，属功能性 path anchor，不 flag。
- "旧值"（callables.py:301）/ "兼容面"（collections.py:217）/ "可观测性/兼容性"（media_types.py:64）/ "compatibility check"（runtime_context.py:81, ib_class.py:64）/ "not compatibility shims"（kernel/base.py:188）— 功能性语义，不 flag。
