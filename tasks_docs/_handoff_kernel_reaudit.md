# 交接文档：内核接口层重审 + 测试体系重设计（2026-09-11 用户转向裁定）

> **本文件 = 交接任务书**。2026-09-11 用户在 P9 ⑦-1c 推进中途（round 8）转向裁定：
> 停止 ⑦ 增量移植，转入 (1) Rust↔Python 接口层/架构审计 (2) 测试体系体系级重设计
> (3) 授权"从 8129af0a 起推翻重来"的引擎级重构。本文档是下一个智能体的开工入口。
> 按 AGENTS.md 纪律：设计阶段文档置 tasks_docs/，落地后择机收敛。

---

## 一、用户裁定（verbatim 要点 + 解读）

1. **审计问题（必须确认的两个问题）**：
   - "到底有没有为了对接已有的测试项而在 rust 和 python 的接口层定义的不干净代码？"
   - "现有的 rust 和 python 的分层、职责分配是不是真的合理？"
2. **测试体系重设计（强制使命）**："我们的内核已经彻底变动，我们的测试脚本体系
   需要全部重新设计，哪怕代价巨大，哪怕涉及上千个测试项，也必须重设计，且必须做
   体系、架构级别的重设计。从而避免旧的测试体系拖累我们的 rust 新内核。"
3. **验证锚点裁定**："初步的 rust 验证停留在 **8129af0a**，而这之后做出的所有
   修改都可能藏着代码异味。"
4. **架构怀疑（用户判断，按此方向审计）**："我很怀疑目前的接口区分、接口设计，
   以及架构层级设计存在问题，绝对有一些没能完全统一化、体系化、形式化处理的
   碎片适配性代码，没有良好地利用某种自动且抽象的转换与处理机制，绝大概率出现了
   一些类似于碎片化 if-else 的层级，哪怕形式上不像是 if-else，但其碎片化内核的
   本质必然存在。"
5. **授权范围**："有必要的话，从 8129af0a 开始整个把接口层、架构设计、甚至是
   整个 ibci 的内核体系全部推翻重来，都可以被允许，做一次代价巨大的引擎级重构，
   去消除这种风险，不计代价，为了更长远未来的发展。"

**解读**：用户怀疑的核心 = ⑦ 增量推进过程中，接口层/引擎层为让既有测试通过而
积累的**测试驱动适配代码**（test-driven accommodation），以碎片化谓词/双路径/
字符串协议/双真相等形式存在——形式上不像 if-else，内核本质是碎片化适配。
本审计的使命 = 确认或证伪这一怀疑，并据审计结果决定增量清理 vs 推翻重来。

---

## 二、当前状态（证据面，2026-09-11 交接时点）

### 2.1 Git 状态

- 分支 `unsafe-vibe-dev`（日常开发主分支；main 永不触碰；禁 push——硬原则不变）。
- **8129af0a** = 用户裁定的"初步 Rust 验证停留点"（3f 续设计提交——rust_run_source
  全管线闭环 + ⑦ 设计文档 v1 前的最后可信锚点）。
- 8129af0a 之后的提交（**全部在审计范围内**）：
  - `08758567` = ⑦-1a/1b（Rust 状态面 run_artifact_state + 路由判定面
    artifact_is_rust_executable + kernels 加载层）
  - `fe1dfcf7` = ⑦-1c（engine 路由接入 + 错误码/现场位置对等 + 数据面语义缺口
    收敛——18 文件 / +1534 行，含 core/runtime/kernels/__init__.py 新建）
  - WIP 提交（本交接时点固化，见 2.2）= ⑦ 缺口批次半成品（host .call 桥会话
    API——**不完整的适配性代码样本**，刻意保留作审计标本）
- 基线（fe1dfcf7 时点全量实跑）：4307 passed / 4 failed / 1 skipped / ~135s。
  4 failed = PT-DEBT-38 登记缺口族（宿主 .call 桥 2 例 + Optional 实例同一性 2 例）。
- 构建：`bash scripts/build_rust_ext.sh`（CARGO_HOME/CARGO_TARGET_DIR pin
  workspace——环境事实见 AGENTS.local.md）。.so = gitignored 可再生产物。

### 2.2 WIP 提交内容（半成品标本——审计重点对象）

为对接 2 个既有测试（test_call_drive_convergence 宿主 .call 薄包装语义）新增：

- **Rust 会话 API**（ibci-ext/src/lib.rs）：`open_session` / `session_call` /
  `session_release` + 全局 `SESSIONS` 注册表（raw pointer + `unsafe impl Send`
  + Python 侧 __del__ 引用计数）——一条**专为主宿主调用面新开的持久会话通道**，
  与既有 `run_artifact_state`（一次性执行）并存 = **两条执行通道并存**（双通道
  嫌疑：同一"执行 artifact"语义的两个入口，生命周期/状态模型不同）。
- **Python 代理**（core/runtime/kernels/__init__.py `RustFunctionProxy`）：
  镜像时把函数声明变量物化为代理对象，.call 委托 session_call。
- **engine 接线**（core/engine.py）：_execute_rust 改用 open_session；镜像
  双路径基础上加第三分支（函数声明 → proxy）。
- **未完成事实**：函数声明变量的 declared_type 解析返回 None（符号池 kind
  过滤仅取 VARIABLE，函数符号 kind = FUNCTION 被过滤）→ proxy 分支未生效 →
  2 个目标测试仍失败（与 WIP 前同态）。**WIP 提交 = 零功能增量 + 纯新增适配
  面**——这正是用户怀疑的"为对接测试项定义接口"的标本。

### 2.3 生产行为现状（⑦-1c 后）

数据面源经 engine.execute → Rust 内核执行（_execute_rust）；LLM/宿主面源 →
Python 运行时。面分区路由 = core/runtime/kernels/__init__.py
`artifact_is_rust_executable`（单一入口，内部 7+ 个独立谓词串联，见 3.2）。

---

## 三、已知嫌疑清单（当前智能体的自曝面——self-grill 纪律，供审计复核/证伪）

> 以下按 ⑦-1a/1b/1c + WIP 的改动面列出**本人（前序智能体）认定的异味嫌疑点**。
> 审计者须独立复核（code-review 纪律：前序报告不等于做完/不等于正确），
> 但此清单是最高价值的起点——每一项都附"为什么可疑"。

### 3.1 碎片化路由谓词堆（用户怀疑的"碎片化 if-else 层级"最大嫌疑）

`artifact_is_rust_executable` 内部 = 7+ 个独立静态谓词的串联短路：

1. 节点类型 ⊆ (Rust node_types − {IbClassDef, IbLambdaExpr})
2. 无宿主模块导入（RUST_NATIVE_MODULES = {meta}）
3. 无单符号元组赋值（_assign_tuple_value_nodes——子树 BFS 扫描）
4. 无内建名重定义（_redefines_intrinsic_name + 硬编码 _INTRINSIC_TYPE_NAMES 集合）
5. 无 meta.compile 属性调用（_uses_meta_compile）
6. 内征引用 ⊆ rust_intrinsic_names（_uses_unsupported_intrinsics）
7. 无对象身份内征（_OBJECT_IDENTITY_INTRINSICS = {knowledge, vec}）
8. 无 Optional 实例同一性角（_optional_instance_identity——node_to_type 扫描）

**为什么可疑**：每个谓词 = ⑦-1c 推进中**由一个失败测试发现的一个语义角**的
静态近似（"某测试失败 → 加一条路由规则把它送 Python"）。这不是从语言/内核能力
面自上而下声明的"Rust 内核能力表"，而是自下而上的**补丁谓词堆**——每加一个
语义移植，就要回来改这里（或加新谓词）。形式上是函数式谓词，内核本质 = 碎片化
if-else 决策链。**正确形态应是**：内核能力 = 单一声明面（每个节点类型/内征/方法
声明其执行归属内核 + 能力前提），路由 = 能力表的查询结果，而非谓词堆。

### 3.2 镜像双路径 + 三补丁（engine._execute_rust 状态镜像）

- **双路径镜像**（declared 家族白名单 {int,float,str,bool,any,list,dict,Optional}
  → define_variable[经 VM _check_type]；其余 → materialize_variable[无检查]）
  + WIP 的第三分支（函数 → proxy）。
- **为什么可疑**：
  - 镜像在**对 Rust 执行结果重跑 Python 的类型检查**（define_variable 触发
    _check_type）= **类型检查语义的两个执行面**（Rust 执行不检查、镜像检查）——
    若 Rust 未来移植检查，这里就是双真相；当前 = 检查语义寄居在状态容器写入
    路径上（执行面与状态面职责混淆）。
  - `materialize_variable`（runtime_context 新增公共 API）= **绕过正常 define
    路径的符号表第二写入通道**，且直接 poke scope._symbols/_uid_to_symbol
    内部（封装纪律侵蚀——为镜像专用开的旁路）。
  - declared 家族白名单 = 又一个硬编码语义分类（与 3.1 谓词堆同族）。
  - 容器特化递归绑定（_bind_container_specialization 助手）= **在 engine 内
    复刻 VM leaf 处理器逻辑**（_bind_container_specialization 的第二实现——
    双真相：同一语义在 VM 与 engine 各写一份，registry 面 vs executor 面）。
  - quoted 物化特例（declared quoted + str → IbQuoted）= 又一路由式特判。
- **正确形态应是**：状态容器写入 = 单一物化机制（值 → 目标对象模型的抽象
  转换表），类型检查归属执行核心（Rust 内），engine 不做语义判断。

### 3.3 错误跨边界字符串协议

- Rust 边界消息 = `IBCI: uncaught exception: {Class}: {msg}@{line}:{col}`
  （ad-hoc 字符串格式），engine 侧 = **正则解析**（`uncaught exception: (\w+)`
  + `@(\d+):(\d+)$` 两段独立正则）+ 类名→错误码映射表 _RUST_ERROR_CODES。
- **为什么可疑**：跨语言错误契约 = 非类型化字符串协议（格式漂移 = 静默丢失
  位置/码）；映射表 = 第二真相（Python 侧异常类型→码映射 functions.py 已有
  同族逻辑）；RecursionError 特殊分支（字符串 contains 判断）= 又一特判。
- **正确形态应是**：类型化错误契约（结构化返回：class/code/line/col 字段），
  或 Rust 侧直接持有诊断码映射（单一真相）。

### 3.4 内征集合双真相

- `rust_intrinsic_names()`（lib.rs 硬编码 Vec<&str>）= 路由判定用"Rust 已实现
  内征集"；**与 interpreter call_function 的 match 臂是两份真相**——移植新内征
  时若忘了同步该列表 = 路由静默分叉（该源走 Python 或误走 Rust，无报警）。
- 同族：_INTRINSIC_TYPE_NAMES / RUST_NATIVE_MODULES / _OBJECT_IDENTITY_INTRINSICS
  / _DATA_PLANE_EXCLUSIONS = 4 个硬编码语义分类集合分散在 Python 路由层。

### 3.5 双真相语言语义面（结构性，最大）

- 语言运行时语义（值运算/类型检查/错误发射/方法面）当前**两处实现**：Python VM
  （handlers）+ Rust 解释器（逐测试移植中）。⑦ 的终点目标是单内核（Rust），
  但**中间态 = 两个语义实现并存 + 一个把两者粘合的适配层（engine 镜像 + 路由
  谓词堆）**。测试体系（见 3.7）持续验证的是 Python 时代的契约形态。
- **为什么可疑**：这不是"过渡期的临时双通道"（过渡期有终点 + 无适配层增长），
  而是**适配层在随移植进度单调增长**（⑦-1a/1b/1c 三批：kernels 加载层 →
  路由谓词 +1 → 镜像/错误/位置/会话 +5 机制）。若无体系化收敛机制，
  ⑦ 完成后 Python VM 退役时，适配层的每一层都要再拆一次。

### 3.6 WIP 会话 API（2.2）

- 两条执行通道并存（run_artifact_state 一次性 vs open_session 持久）；
- unsafe raw pointer 会话注册表 + Python __del__ 引用计数（跨语言生命周期
  协议，无类型保证）；
- 该 API 的**唯一动机 = 2 个既有测试**——若按"宿主函数调用"重新设计接口
  （HostService 面的统一 callable 协议），大概率不需要此形态。

### 3.7 测试体系（使命 2 的现状面）

- 全量 4311 测试，按 Python-VM 时代分层：contracts（VM 内部契约）/ compiler
  （前端）/ runtime（VM 白盒：get_variable payload 类型、符号表内部、deep_clone
  内部、registry 特化内部……）/ e2e（行为）/ diff_harness（Rust vs Python 差分
  ——⑦ 设计中的**临时机制，⑦ 阶段 ③ 退场**）。
- **问题**：
  1. 大量 runtime/ 白盒测试断言 **VM 实现内部形态**（payload 类型、符号表、
     作用域对象）——内核换 Rust 后这些断言的"被断言面"整体不存在/异构；
  2. conftest 助手（run_ibci / expect_runtime_error[异常**消息子串**匹配] /
     engine fixture）= 测试与 VM 时代错误形态耦合（消息文本协议 = 3.3 同族）；
  3. diff_harness 语料/探针 = 目前唯一面向"内核无关行为"的资产（34 语料 + 探针
     的 print 数据面 + 五池 artifact 面）——**它是新测试体系的种子，但目前寄生
     在"临时差分机制"的壳里**；
  4. ⑦-1c 过程中，多个测试的"修复"= 路由规则（测试驱动适配的实证——3.1）
     或超时校准改数（test_ihost_* 的 100000→15000000 迭代：测试假设了
     VM 执行速度——内核变了，测试的隐含假设破了，只能改数适配）。
- **用户裁定**：必须做体系/架构级重设计（不冻结历史资产——2026-09-11 用户
  裁定过期/不正确测试可自由处理，重构质量原则大于维持现状）。

---

## 四、使命分解（下一个智能体的任务书）

### 使命 1：接口层/架构审计（第一优先）

**方法**：
1. `git log 8129af0a..HEAD` + 逐提交 diff，把 8129af0a 之后的**每个接口元素**
   （API/函数/集合/协议/路径分支）列入审计表，逐项三分类：
   - (a) 契约驱动（从语言契约/内核能力面自上而下设计——合理保留）；
   - (b) 测试驱动适配（为让某测试通过而定义——需重设计或删除）；
   - (c) 碎片化（形式合理但本质是补丁堆积——需统一化/形式化）。
2. 审计轴 = 用户两个问题：(i) 有没有为对接测试项定义的不干净接口代码；
   (ii) 分层/职责分配是否真的合理（engine / kernels 层 / Rust 解释器 /
   runtime_context / VM handlers 之间的职责边界）。
3. 对照 self-grill 七问逐项质询；对照 design-philosophy（单一权威源/机制同构/
   配合模式统一/一致性先于便利）判定。
4. **产出**：审计结论文档（tasks_docs/）——嫌疑清单 3.1-3.7 的复核结果
   （证实/证伪/新增）+ 每个 (b)/(c) 项的重设计方向 + 总体判定：
   **增量清理可解 vs 须推翻重来**（判定基准：适配层与语义双真相的耦合深度——
   若"路由谓词堆 + 镜像双路径 + 字符串协议 + 双真相语义面"在增量清理下
   无法收敛为单一声明面 + 单一物化机制 + 类型化契约，则推翻重来）。

### 使命 2：测试体系重设计（与使命 1 并行/紧随）

**设计轴（建议起点，须自顶向下重构，非修补）**：
1. **层重划**：
   - 语言行为层（源 → 可观察面：print 数据面 / 错误码+现场位置 / 状态读回 /
     artifact 五池——**内核无关**，经公共 engine API 验证，Rust/Python 内核
     皆可过——当前 diff_harness 语料/探针 = 此层的种子资产，须正式升格）；
   - 内核内部层（Rust 侧：parser/deserializer/interpreter 的单元/集成测试——
     经 Rust 测试或内核 API，**不经 Python 测试垫片**）；
   - 前端层（编译器/语义/序列化——Python 前端独立测试面）；
   - 契约层（公开契约：诊断码表、错误现场格式、artifact 格式、HostService
     面——稳定契约面，跨内核不变）；
   - 宿主面（HostService：LLM/IO/线程/对象系统——Python 宿主契约）。
2. **断言面纪律**：测试断言**可观察面**（数据面/错误码/位置/状态值语义），
   不断言实现内部形态（payload 对象类型/符号表结构——VM 时代白盒断言整体
   降级或删除）；错误断言经**诊断码 + 结构化现场**，不经异常消息子串。
3. **临时机制退场纪律**：diff_harness（差分）= ⑦ 终点退场；其语料/探针资产
   迁入语言行为层后，差分机制本身删除（不留双内核对比面）。
4. **速度/成本**：当前全量 ~135s（4311 项）；新体系目标 = 语言行为层
   秒级（纯进程内 + Rust 执行快）+ 内核层（Rust cargo test）独立高速。
5. **历史资产处理**（2026-09-11 用户裁定授权）：过期/VM 内部耦合的测试可
   自由重构/修正/删除——**但删除前必须确认其契约面已被新体系承接**
   （契约不留空洞：每个被删测试的断言 = 可观察面/契约面 的显式迁移映射，
   记入重设计文档）。

### 使命 3：（条件触发）引擎级推翻重来

**触发条件** = 使命 1 审计判定"增量清理不可收敛"。**授权范围（用户 verbatim）**：
从 8129af0a 起，接口层 / 架构设计 / 整个内核体系均可推翻重来；代价巨大可接受。
**执行纪律**（沿用硬约束）：
- 大范围破坏性重构 = 独立分支（100% 授权隔离分支实验；零风险确认后方可 merge
  unsafe-vibe-dev；merge 即删分支；main 永不触碰；禁 push）；
- 8129af0a 之前的资产（Rust 构建链/parser/deserializer/serializer/差分 harness
  资产/3e-3f 全管线证明）= 可信地基，优先复用（其本身在"初步 Rust 验证"范围内）；
- 语言语义红线（公理 + contracts 语义错误集）不变——推翻重来的是**内核接口/
  分层/测试体系**，不是语言语义（docs/KNOWN_LIMITS.md 必查）。

---

## 五、开工入口（下一个智能体的第一步序列）

1. 读 AGENTS.md（硬规则/自主工作循环/上报阈值）+ 本文档 +
   tasks_docs/NEXT_STEPS.md（当前状态锚点）+ tasks_docs/_p9_switch.md（⑦ 设计
   v1——含面分区路由原设计，审计时对照"设计意图 vs 实现漂移"）+
   tasks_docs/WORKLOG.md（⑦-1a/1b/1c 三批全记录——每批的决策依据/变化前后/
   实证面都在里面，审计的主要史料源）。
2. 环境自检：`.venv/bin/python -m pytest tests/` 跑一次确认基线
   （WIP 提交后应 = 4309 passed / 2 failed / 1 skipped——2 failed =
   test_call_drive_convergence 宿主 .call 面[WIP 未接线，预期失败]）。
3. 使命 1 审计开工（git log 8129af0a..HEAD 逐提交 diff + 嫌疑清单 3.1-3.7
   复核）。**先审计后动手**——审计结论决定增量清理 vs 推翻重来。
4. 使命 2 测试体系重设计（设计文档先行：tasks_docs/_test_redesign.md，
   含层重划/断言面纪律/历史资产迁移映射/新体系骨架）。
5. 每步：本地 commit + WORKLOG 详尽记录（"只记录，不断决"——能自主决断的
   记决定推进；确实无法决断的按上报阈值处理）。

---

## 六、硬约束（不变面，继承全部）

- **禁 push**（硬原则——除非用户明确指示；无论自主推进范围多大）。
- **main 永不触碰**；日常开发 unsafe-vibe-dev；大范围破坏性重构走独立隔离分支。
- 交付纪律：描述性中文 commit（heredoc -F）；WORKLOG 详尽记录（决策依据/
  方案取舍/变化前后）；文档单点真理纪律（docs/ 不冻结数字，以实跑为准）。
- 语言语义红线：公理 + contracts 语义错误集（Rust 化/重构均不得改变语言语义）。
- 验证门：merge/放行门全量 pytest（硬规则）；语义错误集变更全量评估。
- 用户 2026-09-11 裁定：过期或被证不正确的测试可自由处理；全量 pytest 按需自由。
- 构建环境事实：AGENTS.local.md（CARGO pin workspace / venv / 端点）。

---

## 附：嫌疑项速查表（审计工作起点——逐项复核三分类）

| # | 位置 | 形态 | 初判 |
|---|------|------|------|
| 3.1 | kernels/__init__.py 路由谓词堆（8 谓词 + 4 硬编码集合） | 静态谓词链 | (c) 碎片化——须收敛为内核能力声明表 |
| 3.2 | engine._execute_rust 镜像（双路径 + 特化复刻 + quoted 特判 + materialize_variable 旁路） | 状态面做执行面判断 | (b)+(c)——职责混淆 + 双实现 |
| 3.3 | 错误字符串协议 + 正则解析 + _RUST_ERROR_CODES + RecursionError 特判 | 非类型化跨边界协议 | (c)——须类型化/单一真相 |
| 3.4 | rust_intrinsic_names vs call_function 臂（+ 4 硬编码集合） | 双真相 | (b)——移植驱动的双写 |
| 3.5 | VM handlers vs Rust 解释器（语义双实现 + 适配层单调增长） | 结构性双真相 | (c)——须单内核收敛机制（⑦ 终点）|
| 3.6 | WIP 会话 API（open_session/session_call/proxy/unsafe raw ptr） | 测试驱动新通道 | (b)——为 2 个测试开的适配通道 |
| 3.7 | 测试体系（VM 白盒断言 / 消息子串匹配 / 速度假设 / 差分临时壳） | 时代错位 | 使命 2 重设计对象 |
| ? | diff_harness 语料/探针（34 语料 + 探针） | 内核无关行为资产 | (a)——新体系种子资产，须升格保留 |
