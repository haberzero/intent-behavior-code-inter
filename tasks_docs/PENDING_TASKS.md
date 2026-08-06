# PENDING_TASKS — 待办 / 长期规划

> 当前最紧要见 `tasks_docs/NEXT_STEPS.md`；本文档只保留**仍有价值**的待办、长期规划与设计决策。
> 已完成/无价值条目已删除（完整历史在 git）。
> 任务代号体系（2026-08-05 重整，按**性质**分域，一概念一前缀）：
> **PT-INTRO-1**（内省体系，已完成）｜**PT-FEAT-\*** 语言特性｜**PT-DEBT-\*** 缺陷/技术债
> ｜**PT-AUDIT-\*** 长期周期清扫（审查/审计/文档与注释治理，持续周期工作）
> ｜**PT-DOC-\*** 文档同步｜**PT-TEST-\*** 测试体系｜**PT-DECIDE-\*** 待用户拍板
> ｜**PT-SEALED-\*** 封存

---

## 一、运行时内省体系（PT-INTRO-1，已完成）

> `type(x)` 内建 + fn/behavior 签名形态 + `__return_type__()` 返回类型查询 **全部落地（2026-08-06）**。
> 完成形态：
> 1. `type(f)` 对 fn_callable/behavior 返回含签名类型名（`fn_callable[()->int]` /
>    `behavior[(int,str)->bool]`）；其余值返回 `ib_class.name` 规范名。
> 2. `f.__return_type__()` 返回返回类型规范名；签名随序列化 round-trip 保真。
>
> 设计决策（签名属值层属性）见 §十。

---

## 二、待用户拍板：PT-DECIDE-1 LLM 解析默认策略语义

> **位置**：`core/runtime/interpreter/llm_parsing_strategy.py`（DefaultParsingStrategy）。
> **问题**："已声明具体类型但无 `__from_prompt__`/parser" 的 LLM 输出被**静默 box 成成功
> 字符串**（不触发 llmexcept 重试）→ 错误类型可能静默流入。`auto`/无类型 → box 成功合理
> （已有测试依赖）。
> **待决方案**：区分语义——`auto`/None 无类型 → box；已声明且有 spec 但无 parser → uncertain
> （触发 llmexcept）。属**语言级语义变更**，改会回归现有 `auto result = @~ ... ~` 测试。
> **状态**：仅记录，作为待讨论项。

---

## 三、待选任务：内核接口协议化（PT-DEBT-1/2/3）

> 三者同性质：跨对象私有穿透 → 公开访问器/容器，属内部机制打磨（不阻塞）。

| # | 位置 | 内容 | 方案 |
|---|------|------|------|
| PT-DEBT-1 | `native_module.py:41-42` + `loader.py:66-71` | `_ibci_registry_id` 私有标记注入（跨引擎隔离，两处硬编码字符串无单一权威源，改名即静默失效） | `(implementation, registry_id)` 包进 `BoundPlugin` 容器，构造时从容器取；不再往实现对象打属性（loader/native_module/object_factory 三处） |
| PT-DEBT-2 | `observability/snapshot.py` | 可观测层直接读内核私有槽（`_comm_registry`/`_runtime_coordinator`/`_pending_futures`/`_current_call_info`）+ 宽 except | 给 RuntimeContextImpl/LLMExecutorImpl 补公开只读访问器，snapshot 走公开接口（best-effort 契约有测试） |
| PT-DEBT-3 | `runtime_context.py:381-384` + `vm/handlers/comm.py` 等 | `_comm_config_store`/`_comm_event_bus` 槽被 core/插件直接 `rc._comm_*` 穿透（注释明文的三方契约，无公开访问器） | 加 `get_comm_registry()`/`get_comm_config_store()`/`get_comm_event_bus()`（惰性创建），统一替换各方直接访问。与 PT-DEBT-2 同方向可合并实施 |

---

## 四、语言特性 / 功能规划（PT-FEAT-*）

| # | 内容 | 说明 |
|---|------|------|
| PT-FEAT-1 | 语言级协程完整形态：async 函数 / `yield` 生成器 | `await` 表达式已落地；剩余 async 函数/生成器。依赖调度器多任务挂起恢复 + 快照协议覆盖 yield 点。**保持现状规划，不主动推进** |
| PT-FEAT-2 | Enum 非 str 成员 + 迭代能力 | 枚举成员值一律设为名字字符串 → 数字状态码枚举无法 round-trip（VISION） |
| PT-FEAT-3 | 用户类泛型类型参数 | VISION |
| PT-FEAT-4 | 用户类运算符重载 | VISION |
| PT-FEAT-5 | 语义错误用户友好化 + 诊断工具 + 性能基准 + CI/CD | 语义 4 阶段管线已稳定；错误码 `SEM_xxx` 转用户友好表述、符号表/类型绑定 JSON/dot 导出、编译时间基准 |
| PT-FEAT-6 | CompilationResult 字段精简 | 前置：PT-FEAT-5 完成 + 管线稳定 ≥ 1 月 |
| PT-FEAT-7 | 二层 IR 路线评估 | VISION |

---

## 五、缺陷 / 技术债（PT-DEBT-4/5/6）

| # | 内容 | 说明 |
|---|------|------|
| PT-DEBT-4 | `file` 模块重命名 | `file` 影子化 Python 内建，长期重命名（如 `fs`/`io`）。当前过渡措施已实施 |
| PT-DEBT-5 | 全项目文件命名清理 | 过短/欠层次/欠区分度/影子化内建的代码文件命名排查。暂缓，独立窗口执行 |
| PT-DEBT-6 | `register_module()` 可观测性缺口 | 静默忽略与 kernel-native 同名的用户插件，无 warning。待诊断体系稳定后专项处理 |

---

## 六、长期周期清扫（PT-AUDIT-*，持续周期工作，随主线阶段边界择机启动）

> 审查/审计/治理均为**周期性持续清扫**，非一次性完成——每轮主线改动后按需复核，
> 与"文档清洗与梳理 / 注释卫生清理"同性质。执行记录见 git 历史。

| # | 内容 | 说明 |
|---|------|--------------|
| PT-AUDIT-1 | 代码异味核对分析 | `CODE_SMELL_AUDIT.md`（单一事实来源），独立分支执行 |
| PT-AUDIT-2 | 条件分支与异常嵌套复杂度审计 | `BRANCH_NESTING_AUDIT.md`（AST 基线），独立分支执行 |
| PT-AUDIT-3 | 代码复核审查循环（R 系列） | R1 正式 review / R2 健康诊断 / R3 异味扫描 **已执行（2026-08-05）**；R4 覆盖率核对、R5 doc 审计待做。复核清单见 `PENDING_REVIEW_ITEMS.md` |
| PT-AUDIT-4 | 任务控制文档清洗与梳理（文档治理周期） | 删除已完成/无价值任务、无用设计决策、任务代号重整、交叉一致性核对。**已执行（2026-08-05）**，周期复核 |
| PT-AUDIT-5 | 注释卫生清理（周期） | 删除代码注释中的任务代号、历史实现方案、修复过程叙述，保留功能设计语义。**已执行（2026-08-05）**，周期复核 |

## 七、文档同步（PT-DOC-*）

### PT-DOC-1 docs/ 技术手册同步
| # | 内容 |
|---|------|
| D1 | `signal` 关键字/类型移除 → 通信/并发章节、语法文档、KNOWN_LIMITS |
| D2 | pubsub 语言面打通 + `subscriber` 新类型 |
| D3 | 通信 Signal 移除裁定 |
| D4 | `send_nowait` 语言面补齐 + 语义变化（无订阅者 False） |
| D5 | 线程对象模型细化（thread 槽位化 / thread_result IbValue / 瞬态序列化协议） |

### PT-DOC-2 语法手册定位段补充
`docs/syntax/*.md` 各章节缺 `docs/README.md` §六.3 要求的定位段。

---

## 八、测试体系（PT-TEST-*）

| # | 内容 | 说明 |
|---|------|------|
| PT-TEST-1 | 测试体系治理与彻底重构（TEST_REFACTOR） | 独立低优先级：新建从零 → 并行共存 → 全面替换 → 深入内核（正式测试内省 API）。铁律：Phase 0 设计冻结前不启动代码改动。详见 `TEST_REFACTOR.md` |
| PT-TEST-2 | e2e 测试覆盖率提升 | `for...if` 过滤、复合赋值运算符零 e2e 测试 |
| PT-TEST-3 | 测试名与覆盖矩阵同步 | `tests_docs/SEMANTIC_COVERAGE_MATRIX.md` 测试名与实际文件不同步 |

---

## 九、封存（PT-SEALED-1：media Phase 4 多模态容器）

> **已彻底封存（2026-08-01，无限期搁置）**：恢复需显式解封并重估。代码层零启动
> （仅设计文档 `docs/backup/02_multimodal_behavior.md`）。前置（路径统一/内核原生化/磁盘型
> 存储）已完成。解封时需实现三项：
> 1. 多模态模型注册字段（`ai.register_model` 存 modalities/endpoint/audio_config）；
> 2. 非聊天端点推理绕过（endpoint 字段强制非推理，跳过 reasoning prompt 注入）；
> 3. 磁盘型响应解析协议（`from_response` 平行协议 + `has_multimodal_response_cap` flag）。

---

## 十、设计决策（保留——防止未来误解）

### 仍有效的设计决策

| 决策 | 内容 |
|------|------|
| 运行时值 `type_ref` 保持基础 spec | 可变值（list/dict）不固有泛型身份（同一对象可赋给 list[int]/list[str]，语义不自洽）；符号/序列化侧已精确 |
| callable 签名属值层属性 | fn_callable/behavior 的签名（param_types + return_type）在运行时值创建时经 node_to_type 捕获、自持于值（JSON 安全字符串，序列化保真）；不落 CALLABLE_INSTANCE 类型 spec（该 spec 仅载 value_type）。`type(f)`/`__return_type__()` 据此内省 |
| 通信 `Signal` 抽象移除 | 零消费者空壳 + 与 VM 控制流 Signal 撞名 → 彻底删除 |
| 瞬态序列化协议 | thread/chan/slot/subscriber 统一 `__transient_state__` 存根；反序列化不复活活体 |
| 类型符号 `class_ref` | IbClass 序列化为类名引用、反序列化重绑定 registry 真实类 |
| 泛型成员特化协议化 | `resolve_member` per-type 级联收敛为 `GenericTypeDeclaration` 声明回调 |
| 行为体 fn `-> auto` = str 强制 | LLM 输出默认字符串；要其它类型必须显式 `-> T` |
| 可调用实例不写 value_meta | meta 冗余拷贝专用字段且含非 JSON 值（IbIntentContext/IbCell/TypeDef）；专用字段是单一事实来源 |
| `expected_type` 落盘为类型名字符串 | 运行期由调用点经 node_to_type 解析；字段本身仅元数据 |

### 设计排除（语言级限制，已写入 `docs/KNOWN_LIMITS.md`）

| 排除 | 原因 |
|------|------|
| walrus `:=` / lambda 体赋值 | 设计排除（KNOWN_LIMITS §十九.1） |
| if-block 内重声明同名变量 | 设计排除（KNOWN_LIMITS §十九.2） |
| loader 与 check.py 签名校验收敛 | 设计隔离：SDK 离线校验不初始化运行时，强制收敛引入 SDK↔runtime 错误耦合，不收敛 |

---

## 十一、推迟工作记录：循环打破局部 import tradeoff（待架构重构时复核）

> 原则：理想上应永远避免循环依赖。但允许少量"设计合理、能显著减少工作量"的局部 import 作为
> **谨慎 tradeoff**。以下为保留的循环打破局部 import，列为未来推迟工作，待架构重构
> （依赖方向下沉 / 接口上移）时逐项复核。

| 记录 | 位置 | 引用 | 保留理由（tradeoff） | 未来复核方向 |
|---|---|---|---|---|
| L1 | `core/runtime/objects/kernel/base.py:31/32` | `from .functions import IbBoundMethod` / `from .ib_class import IbClass` | 运行时构造/分派所需，base↔functions/ib_class 环 | 下沉共享基类到独立叶子 |
| L2 | `core/runtime/objects/kernel/ib_class.py:165` | `from .functions import IbBoundMethod` | 运行时构造，ib_class↔functions 环 | 同上 |
| L3 | `core/kernel/spec/type_ref.py:128` | `from .base import TypeKind` | 运行时 kind 比较分派，base↔type_ref 环 | 下沉 TypeKind 到叶子 |
| L4 | `core/kernel/spec/registry/_members.py:121` | `from ..base import TypeDef` | 运行时构造 TypeDef | 下沉 TypeDef 到叶子 |
| L5 | `core/kernel/spec/registry/_runtime.py:90` | 相对导入 | 运行时（审计标注循环打破） | 复核定位并下沉 |
| L6 | `core/runtime/interpreter/interpreter.py:466` | `from vm.vm_executor import` | interpreter↔vm 环 | 延迟属性引用评估 |
| L7 | `core/runtime/objects/kernel/user_functions.py:42/79/140` | `from ..primitives` / `..cell` / `..signals` | 运行时（热路径） | 复核能否去环 |
| L8 | `core/runtime/shared/llm_result.py:56/130` | `from ..objects.primitives/kernel` | 运行时 | 复核能否去环 |
| L9 | `core/runtime/path/install.py:36/40` | `import ibci_modules` / `import core` | 模块加载期 | 重构加载顺序 |
| L10 | `ibci_modules/ibci_ai/core.py:298` | `from core.runtime.frame import` | 插件↔core 环 | 接口上移 |
| L15 | `core/engine.py:119/123` | `kernel_native_modules` / `file_impl` | 构造期延迟加载重型实现 | 核验是否可去除 |
| L17 | `core/compiler/semantic/context.py:117` | `from ...passes.prelude import Prelude` | context↔passes 环 | 依赖方向重构 |
| L18 | `core/runtime/bootstrap/kernel_native_modules.py:75` | `from kernel.host_interface import` | 环（审计待核验） | 复核定位并下沉 |

> 复核触发：任一处所在模块发生架构重构、或引入新的循环依赖、或出现相关技术债时，返回本表
> 逐项复核该 tradeoff 是否仍成立。
