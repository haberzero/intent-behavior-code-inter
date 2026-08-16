# 交接：内核协议化收尾与双轨收敛（下一体系化重构）

> 用途：供下一 session 的智能体接手"内核健康性体系化重构"。
> 背景：协议化大重构（exp/protocol-kernel → unsafe-vibe-dev 直接合并，fast-forward `1b83a698..fbda2098`，
> 2026-08-16）已完成并通过：全量 pytest 2912/1 零回归 + 116 例真实 LLM 试用复跑分类与基线逐例一致。
> 用户明确：**内核健康性/架构体系健康性/宏观长远利益为最高准则；全量重跑与全量试用不是负担，
> 试用测试体系是对智能体的约束**；理论问题清理完毕后将进入宣发与推广实用性阶段。
> 本交接文档为临时任务文档，阶段落地后按惯例归并清理。

---

## 0. 一句话摘要

类型理论地基与执行模型已完成协议化；下一阶段把**同一套协议化/单一权威标准推向 OOP 侧与编译期-运行期边界**，
消除纯字符串分派、硬编码分支、双轨形态与已知边界堆积，之后进入宣发前置工程面。

## 1. 当前基线（最新内核状态）

- 分支：`unsafe-vibe-dev`（本地，未 push——禁 push 硬原则不变）；HEAD `07669897`。
- 全量测试：`conda activate ibci && python -m pytest tests/` = **2912 passed / 1 skipped**（基线以实跑为准）。
- 真实试用：T01-T09 套件（trials/_toolkit harness，本地 qwen3.6-35b-a3b @ 127.0.0.1:1234）。
- 内核要点：协议注册表（`core/kernel/protocol.py` + `core/kernel/spec/registry/_protocol.py`，能力判定单一入口
  `satisfies_protocol`）；CPS 协作调度（TaskScheduler + Waitable 家族 + trampoline + 统一驱动）；
  普通/LLM 函数统一（`IbUserFunction` + `callable_kind`）；方法对象 spec=函数 spec（本轮根治）；
  值层类型身份保真；Optional 统一值模型；模块化类身份（qualified 注册键）。

## 2. 已确认隐患与落后要点清单（逐条处置方向）

> 分级：**P0**=用户明确必须解决（字符串/硬编码、双轨制）｜P1=应解决（边界堆积、声明协议化）｜P2=工程面（宣发前置）。

### 2.1 OOP 侧纯字符串分派与硬编码分支（P0，阶段 A）

| # | 现象 | 位置 | 根因 | 处置方向 |
|---|------|------|------|----------|
| H1 | `receive(message: str, ...)` 字符串消息分派，含硬编码分支 `message == '__call__'` / `'__getattr__'` / `'cast_to'` | `core/runtime/objects/kernel/base.py:41,51,71,87`、`ib_class.py:603,620,626` | OOP 协议（dunder）未进入协议注册表（prompt 协议 5 个已协议化，OOP 核心协议未跟进） | **dunder 协议注册表化**：`__call__`/`__iter__`/运算符 dunder/`cast_to` 等纳入协议注册表，receive 经协议分派（与 `satisfies_protocol`/cap 查询同构）；消除 receive 内硬编码字符串分支 |
| H2 | 属性访问兜底 `_default_getattr` 字符串穿透 | `core/runtime/bootstrapper.py:128` | 属性协议未结构化 | 属性协议化（读取/调用路径统一协议分派；fail-fast 保持） |
| H3 | `_impl_cls()` 按类名字符串解析 Python 实现类 | `ib_class.py:219` | 值对象→实现类映射无结构化注册 | 按 spec kind/axiom 注册表结构化解析 |

### 2.2 公理声明端硬编码（P0 关联，阶段 C）

| # | 现象 | 位置 | 处置方向 |
|---|------|------|----------|
| H4 | 能力声明仍是 axiom 布尔字段：`has_parser_cap`/`has_from_prompt_cap`/`has_output_hint_cap`/`has_payload_prompt_cap`/`has_iter_cap`/`has_subscript_cap`/`has_operator_cap`/`has_converter_cap` | `core/kernel/axioms/primitives/base.py:58-61` 及各 axiom | 判定已协议化（消费端归零直读），**声明未协议化**——把能力声明收敛为协议注册表条目/声明驱动数据，消除"satisfies 走注册表、声明仍布尔"的半缓解 |

### 2.3 双轨形态（P0，阶段 B）

| # | 现象 | 位置 | 根因 | 处置方向 |
|---|------|------|------|----------|
| H5 | **方法符号 spec 的 self 形态不一致**：单文件编译路径方法 spec.param_types 含 owner 首参（self），跨模块路径不含——同一事实两种形态 | 编译期 type-check（`_declaration_visitors.visit_IbFunctionDef` 类上下文 self 注入）vs 跨模块符号池产出 | 编译期产出不一致（本轮以 `_init_expected_arity` 成员表权威规避，**未根治编译期差异**） | 编译期统一：方法函数 spec 的 self 形态单一权威（建议统一为含 self 或统一不含 + 全链消费点对齐） |
| H6 | 特化类以字符串名 `"Box[int]"` 为注册键；`_bind_type_params` 用 boxed 特化名做类型参数符号桥 | `ib_class.py qualified_name`、`_shared.py:943` | 特化身份未结构化 | 特化身份结构化：注册键/符号桥改为结构化（基 spec + 实参列表）表示；字符串键残留归零 |
| H7 | 类成员多表：编译期 `spec.members` / 运行期 `methods`/`default_fields`/`member_types` | `ib_class.py:150-161` | 分层边界未收敛 | 成员单一权威（水化驱动；字段双表收敛；方法表与成员表一致性可断言） |
| H8 | auto-init 运行时 Python 闭包生成（`IbNativeFunction` + `_auto_init` 闭包）与用户方法（编译期声明 + `IbUserFunction`）机制不同构；参数数量校验三处并存（`_resolve_call_arguments_runtime` 绑定层 / `_init_expected_arity` 成员表 / auto-init 闭包） | `interpreter.py:798 _make_chain_auto_init`、`ib_class.py _init_expected_arity/_invoke_init(_cps)` | 构造器无编译期声明 | auto-init 声明化（编译期生成构造器声明/描述符，运行期不再闭包）；数量校验单一权威 |

### 2.4 编译期-运行期断裂专项（P0 关联，阶段 B，用户点名）

| # | 断裂点 | 说明 | 处置方向 |
|---|--------|------|----------|
| F1 | `node_to_symbol` 绑定语义双义：方法 def 节点绑定 self 符号（运行期 self 解析依赖）vs 函数符号（declared spec 来源） | 方法水化曾因此拿到类 spec（本轮以 `_method_declared_spec` 符号池匹配绕行，interpreter.py:810——**回退路径依赖符号池形态，属脆弱桥**） | 编译期绑定语义单一权威：方法 def 的符号绑定与 spec 解析源显式分离（如新增专用侧表或绑定规约文档化 + 契约测试锁定） |
| F2 | 符号池（symbol_pool）作为水化回退来源：`_method_declared_spec` 遍历匹配 `node_uid` | 依赖编译期产物形态（含 self 与否随编译路径漂移，见 H5） | H5 根治后回退路径可简化为直接绑定解析 |
| F3 | 字段默认值预求值 `_pre_evaluate_user_classes` 经 `vm.run` 重入（interpreter.py:604） | 类构造/字段初始化仍有一处"任务内同步重入调度器"（A 系列残留同族） | 复核是否可 CPS 化（与 dispatch_eager 同构处理）或确认为宿主路径边界 |
| F4 | auto-init 无编译期声明（H8 同源） | 运行期生成与编译期声明断裂 | B4 声明化 |
| F5 | 序列化契约残留字符串键：特化名（`"Box[int]"`）、boxed 标识（`_bind_type_params`）、`TypeRef.parse` 字符串回退 | 类型/对象层未完全结构化 | 随 H6 结构化收敛 |

### 2.5 已知边界堆积（P1，阶段 D）

KNOWN_LIMITS.md 现有 **26 节**。堆积问题是"灰色地带"：部分节是已闭合设计取舍（应定案收敛），
部分是修复候选（有明确方向但未计划），需逐条三分类处置（详见 §4）。

### 2.6 工程面（P2，阶段 E——宣发/推广前置）

| # | 项 | 现状 | 方向 |
|---|----|------|------|
| E1 | 性能基准 | `bench` 命令已有（编译期基准）；运行期/真实场景无基准 | 真实场景基准（LLM 编排、循环、并发、长程序） |
| E2 | 工具链 | idbg 内省可用；无调试器断点/单步、无包管理 | 评估并补齐宣发最小集 |
| E3 | 文档体系 | 参考手册完备（syntax/architecture）；教程/How-to 偏薄 | 读者旅程补全（快速上手、LLM 编排教程） |
| E4 | 版本 | 0.2.0（2026-08-11） | 理论清理完成后评估 0.3.0 |

## 3. 阶段规划（顺序执行，同一时刻只主推一个 P0 阶段）

### 阶段 A：OOP 侧协议化（P0）
- A1 dunder 协议注册表化（H1）：`__call__`/`__iter__`/运算符/`cast_to`/属性访问纳入协议注册表；
  receive 硬编码字符串分支归零（base.py/ib_class.py 全部 `message ==` 分支）。
- A2 属性协议化（H2）。A3 `_impl_cls` 结构化（H3）。
- 验收：`receive` 内零硬编码字符串分派；全量 pytest 零回归；独立复核（general agent）；
  真实 LLM 试用复跑（T09 + 受影响套件，分类与基线逐例一致）。

### 阶段 B：双轨收敛（P0）
- B1 方法符号 self 形态编译期统一（H5/F1/F2）。B2 特化身份结构化（H6/F5）。
- B3 成员单一权威（H7）。B4 auto-init 声明化 + 数量校验归一（H8/F4）。B5 `_impl_cls`（若 A3 未覆盖）。
- 验收：spec↔运行期对象身份同构白盒契约测试；字符串特化键/boxed 名桥残留归零；
  全量零回归 + 独立复核 + 真实试用复跑。

### 阶段 C：公理声明协议化（P0 关联）
- H4：能力布尔字段 → 协议注册表声明驱动；axiom 声明与 satisfies 单点真理。
- 验收：能力声明无布尔字段双写；全量零回归 + 复核。

### 阶段 D：已知边界堆积处置（P1）
- KNOWN_LIMITS 26 节逐条三分类（§4 初稿，复核后终判）：修复候选随 A/B/C 消解或立专项；
  设计定案正文精确化（不含"待修复但无计划"灰色表述）；复核维持。
- 验收：26 节全部有明确归属；无灰色堆积。

### 阶段 E：宣发/推广前置（P2，理论清理完成后）
- E1-E4（性能基准/工具链/文档旅程/版本评估）。
- 验收：与用户确认宣发范围后执行。

## 4. KNOWN_LIMITS 26 节归类终判（2026-08-16 复核后定案，替代初稿）

> 初稿经 general agent 逐节复核（代码实证）后终判：4 节降档、2 节拆分、
> 2 节独立专项；其余维持。**26 节全部有明确归属，无灰色堆积。**

| 节 | 终判归类 | 处置 |
|----|----------|------|
| §一 可调用类 `__call__` | 设计定案 | 已 CPS 化（_UserCallDrive），正文核验维持 |
| §二 Enum | 设计定案 | 实例化枚举=独立候选（维持，见 §7） |
| §三 Uncertain 哨兵 | 设计定案 | 正文核验维持 |
| §四 行为不可 return | 设计定案 | 编译期拦截已实现 |
| §五 引用语义 | **设计定案**（初稿复核候选降档） | 与 Python 一致已闭合；**copy/deepcopy 内建已落地**（2026-08-16，§5.1 更新） |
| §六 子类 auto-init | **修复候选→已消解** | B4 auto-init 声明化（2026-08-16）消解机制缺陷；正文行为描述仍准确 |
| §七 auto/fn/any | 设计定案 | 已收敛（方向 A） |
| §八 容器多类型声明 | **设计定案**（初稿复核候选降档） | SEM_MULTI_TYPE_LIST_REMOVED 已实现，规则封闭 |
| §九 废弃语法 | 设计定案 | 硬错误 |
| §十 泛型与容器限制 | 复核候选（**拆分**） | 已闭合：10.2 跨模块（S2/S5）、10.4 签名（已根治）；**未闭合子边界**：10.1 dict 键不校验、10.3 中置星偏移、跨引擎 round-trip 封印——随类型地基后续窗口 |
| §十一 switch 约束 | 设计定案 | 纯约束文档 |
| §十二 intent_context 陷阱 | 设计定案 | 编译期警告已实现 |
| §十三 @ 意图行为 | 设计定案 | 纯文档 |
| §十四 用户类能力差距 | 修复候选（**备注修正**） | #1 泛型已落地（PT-FEAT-3）；#2 运算符双路径=vtable 派发（**实证完整**：__pow__/__floordiv__/__contains__ 全可用，2026-08-16）；机制路径随阶段 A 消解 |
| §十五 DDG 并发边界 | 复核候选（**拆分**） | 循环体/函数体 dispatch 静态限制=设计定案；**_pending_futures 泄漏面=修复候选专项**（PT-DEBT-31） |
| §十六 MOCK 限制 | 设计定案 | 纯文档 |
| §十七 设计排除语法 | 设计定案 | 硬错误 |
| §十八 循环导入 | 设计定案 | Python 同语义 |
| §十九 插件隔离 | 设计定案 | 可见性隔离取舍 |
| §二十 llmexcept 文件写禁 | 设计定案 | 编译期+运行时双层 |
| §二十一 布尔上下文行为 | **设计定案**（初稿复核候选降档） | 正文自标"有意保留，非妥协" |
| §二十二 通信原语面 | **设计定案**（初稿复核候选降档） | 语言面已定；signal 复活=独立大功能候选（维持，见 §7） |
| §二十三 递归深度 | 设计定案 | 环境限制根因保留 |
| §二十四 生成器消费同步阻塞 | 修复候选→**独立专项** | generic_next 协作化（方向明确）；PT-DEBT-29 |
| §二十五 yield from 序列委托 | 修复候选→**独立专项** | 编译期生成器/序列区分（方向明确）；PT-DEBT-30 |
| §二十六 协议与 impl 限制 | 设计定案 | fail-fast 边界，正文核验维持 |

## 4bis. 阶段 A/B/C 完成登记（2026-08-16）

- **阶段 A（OOP 侧协议化）**：receive dunder 协议注册表化（37f2c03c + 复核整改 d6266fd2）——20 处 `message ==` 硬编码归零、attribute 协议新增、op_constants↔协议一致性契约测试、iterable 判定迁移；全量 2944/1 + T09 8/8 + T01 54/57 与基线一致。
- **阶段 B（双轨收敛）**：B1 self 形态统一（dad9a4f2）/ B2 特化身份结构化（056a84eb+2738dd0d，独立分支实验 + 复核放行）/ B3 成员单一权威（db8afcaa）/ B4 auto-init 声明化（438b8b2c）/ B5 F3 预评估诊断（0cb0eacf）；全量 2987/1 + T09 8/8 + T01 54/57 一致。
- **阶段 C（公理声明+判定链双协议化）**：协议条目判定声明数据驱动 satisfies（5c2e150c + 复核 P2 整改 417599e5）；全量 3006/1 + T09 8/8 一致。
- **独立候选**：copy/deepcopy 内建落地（417599e5）；枚举实例化/运算符覆盖（实证完整）/signal 评估见 §7。

## 5. 工作纪律（硬约束，与 AGENTS.md 一致）

1. **禁 push**：全程本地 commit；push 必须用户显式授权。
2. **零回归门**：每阶段全量 `python -m pytest tests/` 零回归；基线以实跑为准。
3. **独立复核**：大改动（阶段 A/B/C 均属）须 general agent 独立复核后整改闭环。
4. **真实试用确认**：涉及 LLM 面/执行模型的改动，真实 LLM 试用复跑（T09 + 受影响套件），
   分类与基线逐例一致——**全量重跑不是负担，是对智能体的约束**（用户明确）。
5. **文档同步**：代码/测试/文档三同步；KNOWN_LIMITS/architecture 随阶段更新；
   设计先写 `tasks_docs/_<task>.md`，落地后归并。
6. **工作模式定论**：禁 compat shim/胶水/tricky/过程式硬编码分发；单一权威；机制同构。
7. **记录纪律**：WORKLOG"只记录，不断决"；自主决策详记变化前后。
8. **同一时刻只主推一个 P0 阶段**。

## 6. 下一个智能体启动指引

1. 读本交接文档 §1-§4 → `tasks_docs/NEXT_STEPS.md` 顶部 → `tasks_docs/PENDING_TASKS.md` §〇。
2. 加载 skill：`code-workflow`/`code-quality`/`user-principles`/`design-philosophy`
   （分析/实现/重构均须加载，按 AGENTS.md skill 加载模式）。
3. 先做**阶段 A 的设计冻结**（`tasks_docs/_design_oop_protocolization.md`）：
   - 盘点全部 dunder/字符串消息消费点（grep `receive(`/`message ==`/`lookup_method(` 全仓）；
   - 对照 prompt 协议（`__from_prompt__` 等 5 个已协议化先例）设计 OOP 协议注册表扩展；
   - self-grill 后冻结设计再动代码。
4. 每阶段：设计 → 实现 → 全量零回归 → 独立复核 → 真实试用复跑 → 文档/记录同步 → 汇报。
5. 阶段 D 逐条复核 §4 归类初稿（实证后终判），处置结果回写 KNOWN_LIMITS 与 PENDING_TASKS。

## 7. 待用户确认事项（2026-08-16 更新：独立候选已纳入自主工作处置）

- 阶段 E（宣发/推广）的具体范围与节奏（理论清理完成后与用户对齐）。
- **独立候选窗口处置结论（用户 2026-08-16 授权纳入自主工作）**：
  - `copy`/`deepcopy` 内建——**已落地**（2026-08-16，KNOWN_LIMITS §5.1 更新）；
  - 运算符覆盖广度（§十四 #2）——**实证已完整**（__pow__/__floordiv__/__contains__ 等
    vtable 派发全可用），维持现状；
  - `signal` 复活（§二十二）——评估维持现状（撞名 + 语言面已定，独立大功能候选）；
  - 实例化枚举（§二）——维持现状（`_enum_instancing_assessment.md` 既有结论）；
  - 供应商感知思考禁用（PT-DECIDE）——维持既有待设计项；
  - §二十四/§二十五——独立专项 **PT-DEBT-29/30**；§十五 泄漏面——**PT-DEBT-31**。
