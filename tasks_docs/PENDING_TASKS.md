# PENDING_TASKS — 待办 / 长期规划

> 当前最紧要见 `tasks_docs/NEXT_STEPS.md`；本文档只保留**仍有价值**的待办、长期规划与设计决策。
> 已完成/无价值条目已删除（完整历史在 git）。
> 任务代号体系（2026-08-05 重整，按**性质**分域，一概念一前缀）：
> **PT-INTRO-1** 主线（内省体系剩余）｜**PT-FEAT-\*** 语言特性｜**PT-DEBT-\*** 缺陷/技术债
> ｜**PT-REV-\*** 审查动作｜**PT-DOC-\*** 文档同步｜**PT-TEST-\*** 测试体系
> ｜**PT-AUDIT-\*** 长期周期审计｜**PT-DECIDE-\*** 待用户拍板｜**PT-SEALED-\*** 封存

---

## 一、下一主线：PT-INTRO-1 运行时内省体系剩余（fn/behavior 签名形态 + 返回类型查询）

> `type(x)` 内建已落地（返回 `ib_class.name` 规范类型名，含 fn_callable/用户类）。
> 剩余两项作为下一阶段主线（用户 2026-08-05 裁定）：

1. **fn/behavior 签名形态**：`type(f)` 对 fn_callable/behavior 返回**含签名**的类型名
   （如 `fn_callable[()->int]`）。需内省 `type_ref` 的 params + return。
2. **返回类型查询 API**：草案 `f.__return_type__()`（独立于 `type()` 的签名查询形态）。

**设计参照**：Rust（静态无运行时闭包反射）/ TypeScript（`ReturnType<typeof f>` 类型层）/
Python（`get_type_hints` 运行时）。对齐 idbg 内省哲学（调试/泛型分发场景）。
**前置**：不依赖其它任务（类型体系已稳定）。详细设计先写本 tasks_docs 层，落地后收敛进 `docs/`。

---

## 二、待用户拍板：PT-DECIDE-1 LLM 解析默认策略语义（原 B-D2）

> **位置**：`core/runtime/interpreter/llm_parsing_strategy.py`（DefaultParsingStrategy）。
> **问题**："已声明具体类型但无 `__from_prompt__`/parser" 的 LLM 输出被**静默 box 成成功
> 字符串**（不触发 llmexcept 重试）→ 错误类型可能静默流入。`auto`/无类型 → box 成功合理
> （已有测试依赖）。
> **待决方案**：区分语义——`auto`/None 无类型 → box；已声明且有 spec 但无 parser → uncertain
> （触发 llmexcept）。属**语言级语义变更**，改会回归现有 `auto result = @~ ... ~` 测试。
> **状态**：仅记录，下一 session 作为待讨论项。

---

## 三、待选任务：内核接口协议化（PT-DEBT-1/2/3，原 C-D3 / C-D7 / B-D10）

> 三者同性质：跨对象私有穿透 → 公开访问器/容器，属内部机制打磨（不阻塞）。

| # | 位置 | 内容 | 方案 |
|---|------|------|------|
| PT-DEBT-1 | `native_module.py:41-42` + `loader.py:66-71`（原 C-D3） | `_ibci_registry_id` 私有标记注入（跨引擎隔离，两处硬编码字符串无单一权威源，改名即静默失效） | `(implementation, registry_id)` 包进 `BoundPlugin` 容器，构造时从容器取；不再往实现对象打属性（loader/native_module/object_factory 三处） |
| PT-DEBT-2 | `observability/snapshot.py`（原 C-D7） | 可观测层直接读内核私有槽（`_comm_registry`/`_runtime_coordinator`/`_pending_futures`/`_current_call_info`）+ 宽 except | 给 RuntimeContextImpl/LLMExecutorImpl 补公开只读访问器，snapshot 走公开接口（best-effort 契约有测试） |
| PT-DEBT-3 | `runtime_context.py:381-384` + `vm/handlers/comm.py` 等（原 B-D10） | `_comm_config_store`/`_comm_event_bus` 槽被 core/插件直接 `rc._comm_*` 穿透（注释明文的三方契约，无公开访问器） | 加 `get_comm_registry()`/`get_comm_config_store()`/`get_comm_event_bus()`（惰性创建），统一替换各方直接访问。与 PT-DEBT-2 同方向可合并实施 |

---

## 四、语言特性 / 功能规划（PT-FEAT-*）

| # | 内容 | 说明 |
|---|------|------|
| PT-FEAT-1 | 语言级协程完整形态：async 函数 / `yield` 生成器（原 PT-4.3 剩余） | `await` 表达式已落地；剩余 async 函数/生成器。依赖调度器多任务挂起恢复 + 快照协议覆盖 yield 点。**保持现状规划，不主动推进** |
| PT-FEAT-2 | Enum 非 str 成员 + 迭代能力（原 PT-4.1） | 枚举成员值一律设为名字字符串 → 数字状态码枚举无法 round-trip（VISION） |
| PT-FEAT-3 | 用户类泛型类型参数（原 PT-4.4） | VISION |
| PT-FEAT-4 | 用户类运算符重载（原 PT-4.5） | VISION |
| PT-FEAT-5 | 语义错误用户友好化 + 诊断工具 + 性能基准 + CI/CD（原 PT-SEM-1） | 语义 4 阶段管线已稳定；错误码 `SEM_xxx` 转用户友好表述、符号表/类型绑定 JSON/dot 导出、编译时间基准 |
| PT-FEAT-6 | CompilationResult 字段精简（原 PT-SEM-2） | 前置：PT-FEAT-5 完成 + 管线稳定 ≥ 1 月 |
| PT-FEAT-7 | 二层 IR 路线评估（原 PT-SEM-3） | VISION |

---

## 五、缺陷 / 技术债（PT-DEBT-4/5/6）

| # | 内容 | 说明 |
|---|------|------|
| PT-DEBT-4 | `file` 模块重命名（原 PT-ARCH-30） | `file` 影子化 Python 内建，长期重命名（如 `fs`/`io`）。当前过渡措施已实施 |
| PT-DEBT-5 | 全项目文件命名清理（原 PT-ARCH-22） | 过短/欠层次/欠区分度/影子化内建的代码文件命名排查。暂缓，独立窗口执行 |
| PT-DEBT-6 | `register_module()` 可观测性缺口（原 PT-ARCH-23） | 静默忽略与 kernel-native 同名的用户插件，无 warning。待诊断体系稳定后专项处理 |

---

## 六、审查动作与文档同步（PT-REV-* / PT-DOC-*）

### PT-REV-1 覆盖率核对（原 R4）
新增测试是否覆盖全部新行为（subscriber 生命周期 / class_ref / 泛型特化分支 / 瞬态协议 /
构造入口 / 闭包序列化 round-trip / IBC 文件跨模块导入）。

### PT-REV-2 doc-governance 审计 docs/（原 R5）
配合 PT-DOC-1 文档收敛。

### PT-DOC-1 docs/ 技术手册同步（原 D1-D5）
| # | 内容 |
|---|------|
| D1 | `signal` 关键字/类型移除 → 通信/并发章节、语法文档、KNOWN_LIMITS |
| D2 | pubsub 语言面打通 + `subscriber` 新类型 |
| D3 | 通信 Signal 移除裁定 |
| D4 | `send_nowait` 语言面补齐 + 语义变化（无订阅者 False） |
| D5 | 线程对象模型细化（thread 槽位化 / thread_result IbValue / 瞬态序列化协议） |

### PT-DOC-2 语法手册定位段补充（原 PT-DOC-1）
`docs/syntax/*.md` 各章节缺 `docs/README.md` §六.3 要求的定位段。

---

## 七、测试体系（PT-TEST-*）

| # | 内容 | 说明 |
|---|------|------|
| PT-TEST-1 | 测试体系治理与彻底重构（TEST_REFACTOR） | 独立低优先级：新建从零 → 并行共存 → 全面替换 → 深入内核（正式测试内省 API）。铁律：Phase 0 设计冻结前不启动代码改动。详见 `TEST_REFACTOR.md` |
| PT-TEST-2 | e2e 测试覆盖率提升（原 PT-TEST-6） | `for...if` 过滤、复合赋值运算符零 e2e 测试 |
| PT-TEST-3 | 测试名与覆盖矩阵同步（原 PT-TEST-7） | `tests_docs/SEMANTIC_COVERAGE_MATRIX.md` 测试名与实际文件不同步 |

---

## 八、长期周期审计（PT-AUDIT-*，周期任务，时不时启动）

| # | 内容 | 文档 |
|---|------|------|
| PT-AUDIT-1 | 代码异味核对分析（原 PT-SMELL-1） | `CODE_SMELL_AUDIT.md`（单一事实来源），独立分支执行 |
| PT-AUDIT-2 | 条件分支与异常嵌套复杂度审计（原 PT-SMELL-2） | `BRANCH_NESTING_AUDIT.md`（AST 基线：深度≥5 共 14 文件 / 70 处宽 except / 5 处嵌套 try），独立分支执行 |

---

## 九、封存（PT-SEALED-1：media Phase 4 多模态容器）

> **已彻底封存（2026-08-01，无限期搁置）**：恢复需显式解封并重估。代码层零启动
> （仅设计文档 `docs/backup/02_multimodal_behavior.md`）。前置（路径统一/内核原生化/磁盘型
> 存储）已完成。解封时需实现三项（原 PT-PHASE4-1/2/3）：
> 1. 多模态模型注册字段（`ai.register_model` 存 modalities/endpoint/audio_config）；
> 2. 非聊天端点推理绕过（endpoint 字段强制非推理，跳过 reasoning prompt 注入）；
> 3. 磁盘型响应解析协议（`from_response` 平行协议 + `has_multimodal_response_cap` flag）。

---

## 十、设计决策（保留——防止未来误解）

### 仍有效的设计决策

| 决策 | 内容 |
|------|------|
| 运行时值 `type_ref` 保持基础 spec | 可变值（list/dict）不固有泛型身份（同一对象可赋给 list[int]/list[str]，语义不自洽）；符号/序列化侧已精确 |
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
