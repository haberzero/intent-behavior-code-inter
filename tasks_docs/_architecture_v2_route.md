# IBCI 架构 v2 技术路线裁定（R0，2026-09-11）

> 本文件 = 架构 v2 体系化重设计的**技术路线裁定**（用户授权"总体的技术路线由你自己
> 决定，我不过多干涉"，唯一遵守原则 = 代码质量 / 可维护性 / 远期长期收益）。
> 依据 = 用户战略框架八点 + 使命 1 审计结论（Rust 内核 = "Python 语义转录 + 速度"，
> 未利用 Rust 严格性）+ Rust 深扫结论（静默降级系统性 / stringly-typed / 数值契约
> 冲突 / 三重语义实现 / artifact 绑定 Python 格式）。
> 设计阶段文档（tasks_docs/_<task>.md），落地后收敛入 docs/。

---

## 〇、裁定摘要

**核心命题：Rust 不是"换一个执行后端"，而是整个系统底层体系化重设计的契机。**
新架构利用 Rust 的表达力与严格性让内核**更稳固**（typed 值模型、无静默路径、
enum 分派、类型化协议），同时**保持 IBCI 的 DSL 易用性**（语言表面不变或更简，
严格性是内核内部的，不推向用户）。

**内部严格性 ≠ 语言严格性**——这是全路线第一原则：
- 内核内部：typed IR / 无静默路径 / fail-fast / 协议化——用 Rust 严格性
- 语言表面：IBCI 保持易用、自然、领域专用（KB 世界模型 / LLM 融合 / 意图 DSL）
- 用户获得的：更准的错误、更稳的行为、更好的诊断——而非更繁琐的语法
- IBCI 绝不变成"规则繁琐、严格、不易学习的 Rust 式高性能通用语言"

**性能定位（用户⑦）**：AVX/GPU = 以年为单位的战略演进储备，当前只做**接口预留**
（Tensor 值 + 计算基板协议），不做高性能实现。内核易维护/易用/架构稳固 >> 语言性能。
测试体系速度（用户⑧）= 当前最主要的性能关切。

---

## 一、目标分层架构 v2

```
┌──────────────────────────────────────────────────────────────┐
│ 语言面（用户可见）                                            │
│   IBCI DSL：语法/声明形态/控制流/容器/函数/类/KB/LLM/意图     │
│   Python 宿主扩展（HOST-EXT）：用户写 Python 实现自己的功能    │
├──────────────────────────────────────────────────────────────┤
│ 协议层（Rust↔Python 交融的单一规范面——防碎片）                │
│   P1 能力声明（capability）  P2 typed 值通道                  │
│   P3 typed 错误（诊断码+现场）  P4 宿主调用（含 HOST-EXT）     │
│   P5 计算基板（ComputeSubstrate：批量同构计算）               │
├──────────────────────────────────────────────────────────────┤
│ Rust 内核（唯一执行内核——严格性所在）                        │
│   前端：lexer / parser / semantic → typed IR                  │
│   执行核心：重写（typed 值模型 + 无静默路径 + enum 分派）      │
│   值模型：typed 值（scalar owned + 容器共享 + Tensor 批量）    │
│   计算基板：scalar 原生 + SIMD[后续] + GPU 插件[tilelang]      │
│   并发：GIL-free 真并行（任务调度 + 批量计算并行）             │
├──────────────────────────────────────────────────────────────┤
│ Python 宿主面（易用性所在）                                   │
│   HostService：LLM / IO / embedding / journal / budget / 线程 │
│   用户扩展注册（HOST-EXT 协议面） + 编排（engine/CLI）         │
└──────────────────────────────────────────────────────────────┘
```

---

## 二、八点关切逐项裁定

### 2.1 Python 的角色（回应①）——**保留，且升格为协议化一等扩展**

用户保留顶层 Python 的本意 = 易用性（用户写 Python 代码实现自己的功能/逻辑）。
**新架构保留此能力，并协议化为 HOST-EXT（P4 宿主调用协议的一部分）**：

- **用户 Python 代码 = 一等宿主扩展**：经注册协议暴露给 IBCI
  （`register_host_function(name, callable, signature)`），IBCI 内可
  `import py.xxx` / 直接调用——用户自定义逻辑与 IBCI 语言并存。
- **值转换 = typed 通道**（P2）：IBCI 原生值 ↔ Python 对象，显式映射
  （int→int / list→list / quoted→str+标记 / tensor→numpy 兼容形态 / 宿主对象→
  句柄），**废弃 repr 字符串降级**。
- **生命周期 = 句柄协议**：宿主对象经引用计数句柄管理，**废弃 unsafe 全局注册表**。
- **Python 的架构角色收敛为两层**：宿主服务（LLM/IO/embedding/线程）+ 用户扩展面。
  Python **不再是内核**（不执行语言语义）；Python 参考内核 = 开发期差分参考，
  随 Rust 内核成熟明确退场路径。

### 2.2 pip 安装（回应②）——**maturin wheel 打包**

- `pyproject.toml` 用 maturin（已装 1.15.0）构建 pyo3 扩展 → **`pip install ibci`
  即得含 Rust 内核的 wheel**；开发期 `pip install -e ".[dev]"`。
- 当前 `scripts/build_rust_ext.sh`（CARGO pin workspace）保留为开发构建路径；
  发布构建 = maturin（同一 crate）。
- 计算基板插件（GPU 后端等）= **独立 wheel 可选扩展**（如 `ibci-compute-tilelang`），
  核心零耦合。
- Python 参考内核 = dev 依赖（差分开发期），不进发布 wheel 的必需面。

### 2.3 计算基板与 GPU/tilelang（回应③⑥⑦）——**协议统一 + 实现独立**

- **P5 ComputeSubstrate trait**（Rust 内核内）：批量同构数值计算的单一协议面
  （元素级 / 规约 / GEMM / 嵌入运算），实现可替换：
  - scalar 回退（当前，正确性优先）
  - SIMD/AVX（后续，经 std::simd 或便携 crate）
  - GPU（未来战略期，经 tilelang 后端插件 crate）
- **Tensor 值入值模型**（R0 就加）：一等 bulk 数值值（dtype + shape + 数据），
  承载 vector 面 / embedding / 未来 GPU 结果。值语义（owned/不可变共享）。
- **tilelang 集成形态（用户提议评估）**：IBCI 提供 `compute` 内建/DSL 块——用户
  写 tilelang 内核代码，IBCI **只做值编组与调度**（IBCI 值 → 后端输入 → 后端
  执行 → 结果取回 = IBCI 原生 Tensor 值，或按用户指定直接返回 Python 成员）。
  **IBCI 不解释 tilelang 语义、不包装**——符合"ibci 传递代码给底层、只取结果"。
- **裁定**：统一化 = 协议统一（P5 + Tensor）；实现 = 各自独立库（scalar 原生 /
  AVX crate / tilelang-GPU 插件）。**当前只做接口预留，不实现 AVX/GPU**（⑦）。

### 2.4 Rust↔Python 交融协议化（回应④）——**五协议，禁碎片**

- P1 能力声明：Rust 导出能力清单（节点/内征/模块/未移植角），Python 路由 = 查询
  （消灭路由谓词堆 + 硬编码集合）。
- P2 typed 值通道：值 + 类型标签跨边界（消灭 repr 降级 / JSON 大字符串往返）。
- P3 typed 错误：结构化 class/code/line/col/detail（消灭消息子串 + 正则回拆）。
- P4 宿主调用：统一 callable 协议（含 HOST-EXT 用户扩展 + 对象生命周期句柄）。
- P5 计算基板：批量计算协议（Tensor 面）。
- **纪律**：一切跨边界 = 经协议；禁 ad-hoc 字符串、禁双通道、禁谓词堆、禁
  unsafe 全局状态。此即使命 3 D1-D5 的扩展。

### 2.5 特性保留 + 合理重设计（回应⑤）——**保留清单 + 打破清单（无负向收益论证）**

见 §四、§五。

### 2.6 执行核心推倒重写 + 真正多线程（回应⑥）

**执行核心：推倒重写（用户授权）。形态裁定 = typed tree-walking 重写（非 bytecode VM）**：
- **typed 值模型**：scalar 值 owned（Int/Float/Str/Bool/None），容器共享
  （List/Dict 保留 Rc<RefCell>——语言共享可变语义必需），Tensor 值 owned。
- **无静默路径硬规则**：每处"未覆盖/错误"= 正确实现 或 结构化显式错误；**禁止
  静默返回错误值**（list 元素赋值、split() 无参、kb 治理门失败等 13+ 已确认实例
  全部清零）。
- **enum 分派**：运算符/方法/异常类 = enum 或分发表，消灭 stringly-typed。
- **Result 全链**：错误携带 typed ErrorKind + 现场位置，消灭字符串类名。
- **借用纪律**：容器借用集中管理，消灭"值克隆出借用语境"规避 hack。
- **结构保持 tree-walking**（非 bytecode）：易维护 / 易诊断 / 易测试 >> 性能（⑦）。
  bytecode VM = 未来性能里程碑的后续评估项，非当前目标。
- **数值语义**：typed 运算分离 Int/Float 路径（消灭 f64 全包）；**int = i128
  有界**（超界 = 显式错误，无静默）——语言契约变更，登记打破清单，论证无负向收益
  （行为更正确，DSL 表面不变；Python 参考的大整数案例 = 差分登记或路由）。

**真正多线程（三个层面，均为"高速大量同构计算"的自然归宿）**：
1. **批量计算并行**（计算基板层）：Tensor 运算经 ComputeSubstrate 并行化
   （SIMD 向量化 / GPU 线程池）——同构大量计算的主战场。
2. **任务/artifact 并行**（调度层）：保留 TaskPool + run_artifacts_parallel
   （GIL-free 真并行，已有基础）——多 artifact/任务并行。
3. **语言级并行**（谨慎）：如需 = `parallel` 内建经调度器（保持 DSL 简单，
   先评估必要性再引入；当前不设计）。
- 执行核心本身 = 单 artifact 顺序执行（可维护优先；RefCell 风险限于单线程路径）。

### 2.7 测试体系全量重构（回应⑧）——**五层 + 速度目标**

- 使命 2 五层：语言行为层（内核无关，公共 engine API）/ 契约层（诊断码表+错误
  现场+artifact 格式+语义红线）/ 内核内部层（**Rust cargo test**，不经 Python
  垫片）/ 前端层（Python 独立面）/ 宿主面（LLM/IO/线程/对象系统）。
- 断言面纪律：可观察面 + 诊断码 + 结构化现场；**禁** payload 类型/符号表内部/
  消息子串。
- **速度目标**：语言行为层秒级（纯进程内）+ 内核层 cargo test 独立高速；
  当前全量 140s → 目标大幅收缩（差分面退役 + 白盒断言降级删除）。
- 碎片 Python 测试代码 = 重构/删除（迁移映射登记，契约不留空洞）。

---

## 三、五协议定义（协议层）

| 协议 | 内容 | 消灭的旧碎片 |
|------|------|-------------|
| P1 能力声明 | Rust `capability()` JSON：node_types / intrinsic_names（分发表派生）/ native_modules / unported_corners[{feature, reason}] | 路由谓词堆 8 谓词 + 4 硬编码集合 + rust_intrinsic_names 双真相 |
| P2 typed 值通道 | {kind, value} 跨边界（int/float/str/bool/none/list/dict/function/quoted/vector/tensor/knowledge/error/host） | repr 字符串降级 + 镜像再水化特判 + JSON 大字符串往返 |
| P3 typed 错误 | RustRuntimeError{error_class, code, line, column, detail} + 诊断码单一权威 error_code_for_class | 消息子串 + 正则回拆 + _RUST_ERROR_CODES 双真相 + RecursionError contains |
| P4 宿主调用 | 统一 callable 协议（函数值 .call / HOST-EXT 用户扩展注册 / 对象句柄生命周期） | WIP 会话 API（unsafe 全局注册表 + 双执行通道） |
| P5 计算基板 | ComputeSubstrate trait：批量数值运算（元素级/规约/GEMM/嵌入）+ Tensor 值 | 未来碎片化 SIMD/GPU 各自为政 |

---

## 四、特性保留清单（不破坏，用户⑤）

- **语言表面**：语法 / 声明形态（TYPE x = v / auto / fn / 泛型 / 解包）/ 控制流
  （if/for/while/switch/try）/ 容器 / 函数 / 类 / lambda / 链式比较 / 切片。
- **KB 世界模型面**：27 方法面 + 治理门 + 墓碑/版本化 + 磁盘格式 + artifact 契约
  （v2 加法演进先例保留）。
- **自指面**：quote / eval / quoted 值。
- **值面**：vector / embedding（并入 Tensor 值模型，行为不变）。
- **LLM/意图/宿主面**：LLM 15 节点语义（宿主面）/ intent / behavior / memory /
  ihost / overlay / journal / budget / deterministic 模式 / 模块与包系统。
- **契约面**：诊断码表（RUN_*/SEM_*）、错误现场格式、artifact 五池格式（UID 机制
  除外，见打破清单 7）。
- 每项保留 = 测试体系契约层/行为层承接（迁移映射）。

## 五、打破清单（登记 + 无负向收益论证，用户⑤）

| # | 打破项 | 现语义（Python 转录） | v2 语义 | 无负向收益论证 |
|---|--------|----------------------|---------|---------------|
| 1 | bound_method last-wins | artifact 内容依赖书写顺序（非 canonical） | 确定性规则（首定义优先 + 显式覆盖门） | 消除顺序依赖脆弱性；确定性 = 更稳；用户语义不变（罕见歧义场景显式报错） |
| 2 | Optional 实例同一性 | 空 Optional = 每赋值新实例，`a is b`=False | 值语义（None == None，is 与 == 同真） | 消除包装实现 artifact；值语义更符合直觉；原行为无语言目标支撑 |
| 3 | handler/异常变量全局泄漏 | try handler 变量越块全局可见 | 词法作用域绑定（handler 内可见） | 消除全局污染；更符合作用域直觉；无语言目标依赖泄漏 |
| 4 | 错误消息子串协议 | 消息文本 + 正则匹配 | 诊断码 + 结构化现场 | 诊断更准更友好（易用性提升）；契约面稳定 |
| 5 | f64 全包算术 + i64 int | 全部算术经 f64，int=i64 | typed 运算（Int i128 / Float f64 路径分离），超界显式错误 | 消除 >2^53 精度静默丢失与 2**100 失真；行为更正确；DSL 表面不变 |
| 6 | 静默降级路径（13+ 实例） | list 元素赋值 no-op / split() 无参逐字符 / kb 治理门失败 None_ 等 | 正确实现 或 结构化显式错误 | 消灭静默错误结果 = 最直接的正确性提升 |
| 7 | artifact UID 绑定 Python json.dumps | node_uid = sha256(Python json 字节) | 语义 canonical 内容哈希（语言级 IR） | 消灭手写序列化器 + Python 格式耦合；artifact 文件 v2 版本化迁移（已有 v1→v2 先例） |
| 8 | Python 语义转录文化 | "Python 实证"注释遍布 | 语义权威源 = 公理 + 契约文档 | 从"探测 Python 行为"转为"从语言规范推导"；可维护性/正确性双升 |

**不打破**：语言宏观目标（意图驱动 + LLM 融合 + 世界模型 + DSL 易用性）、语义错误集
契约面（RUN_*/SEM_* 码）、公理层类型推导方向（type_inference.rs 已示范"对齐公理"）。

---

## 六、实施路线（R1-R5，每阶段全量门 + commit + WORKLOG）

| 阶段 | 内容 | 分支 | 门 |
|------|------|------|-----|
| R0 | 本文档（架构裁定） | 当前分支 | 文档 commit |
| R1 | 接口协议化：P1 能力声明 / P2 typed 值通道 / P3 typed 错误 / P4 callable（含删会话 API）/ 单一执行入口 | kernel-interface-rebuild（已建） | 全量 pytest 零回归 + smoke + 差分门 |
| R2 | 执行核心推倒重写：typed 值模型 + 无静默路径 + enum 分派 + i128 数值 + Tensor 值 | 新独立分支（推倒授权） | 全量门 + 打破清单逐项落地验证 |
| R3 | 测试体系五层重构（使命 2 设计落地）：语言行为层升格 / 白盒降级删除 / cargo test 内核层 / 差分机制退场准备 | unsafe-vibe-dev 或独立 | 新体系全绿 + 迁移映射完整 |
| R4 | HOST-EXT 协议落地（用户 Python 扩展）+ maturin wheel 打包（pip install ibci） | 独立分支 | pip 安装验证 + 扩展 e2e |
| R5 | 计算基板：Tensor 值全面 + ComputeSubstrate trait（scalar 实现）；AVX/GPU = 战略期接口预留 | 独立分支 | 行为不变 + 基板协议测试 |
| 后续 | AVX（std::simd）/ GPU（tilelang 插件）= 未来以年为单位的战略期，另行立项 | — | — |

**顺序依据**：R1 协议化 = 一切的基础（接口规范先行）；R2 执行核心重写 = 内核本体
（依赖 R1 的协议面）；R3 测试重构 = 承接新内核断言面；R4 宿主协议 + 打包 = 用户面
能力；R5 计算基板 = 接口预留（不阻塞主线）。

---

## 七、硬约束与纪律

- **禁 push**（硬原则，须用户显式授权）；main 永不触碰；大范围破坏性重构走独立
  隔离分支，零风险确认后 merge unsafe-vibe-dev 即删分支。
- 工作模式定论九条凌驾一切（禁 compat shim / 胶水 / tricky / 过程式硬编码分发；
  质量优先于速度；原则优先于行为维持）。
- 每阶段：受影响子集 + smoke + 全量门（合并时）+ commit（描述性中文）+
  WORKLOG 详尽记录（决策依据/方案取舍/变化前后，含打破清单逐项）。
- 测试数字以实跑为准，不冻结。
- 本设计文档 = R0 裁定；各阶段细化设计 = 阶段内 tasks_docs/_<task>.md 先行。
