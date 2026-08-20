# PENDING_TASKS — 远期任务规划

> 本文档是 IBCI 的**远期任务正式清单**（单一权威源）。按 `tasks_docs/GOVERNANCE.md`
> 治理章程维护：已完成条目从本文档移除（历史由 git 承载）；条目状态变更随任务推进更新。
> 当前主线与下一步候选见 `tasks_docs/NEXT_STEPS.md`。
>
> **书写要求**：新增/修改条目必须按本文尾部「书写模式」模板与格式书写，保持一致。

## 〇、概览

| 域 | 活跃 | 搁置 | 封存 | 说明 |
|----|------|------|------|------|
| FEAT（功能） | 3 | 0 | 0 | 语言/工具链功能愿景（PT-FEAT-15 provider 分离/原生绑定两段式主干已完成移除） |
| DEBT（技术债） | 2 | 1 | 0 | 架构缺陷与清理项（PT-DEBT-35/36 已排入阶段 B；PT-DEBT-5 搁置） |
| AUDIT（审计） | 3 | 0 | 0 | 周期审计与健康检查 |
| DOC（文档） | 1 | 0 | 0 | 文档体系缺口 |
| TEST（测试） | 1 | 0 | 0 | 测试体系缺口 |
| DECIDE（决策） | 1 | 0 | 1 | 待裁定设计问题（PT-DECIDE-3 项②④ 剩余；PT-DECIDE-2 已封存） |
| SEALED（封存） | 0 | 0 | 2 | 显式封存（恢复需解封评估） |
| VISION（愿景） | 4 | 0 | 0 | 远期方向（无排期） |

---

## 一、功能规划（FEAT）

### PT-FEAT-5 语义错误用户友好化 + 诊断工具 + CI/CD

- **状态**：active（剩余：CI/CD 可靠化设计窗口）｜**域**：FEAT｜**优先级**：P2
- **动机**：语义错误（`SEM_xxx`）转用户友好表述、符号表/类型绑定导出、编译基准，服务语言易用性与可诊断性。
- **成因**：语义 4 阶段管线稳定后暴露的错误可读性/工具链缺口。
- **当前理解**：前三项已落地（诊断码目录 + 符号表/类型绑定导出 + `bench` 编译基准）；CI/CD 的 GitHub 侧自动触发已停用（用户裁定：现 CI 与本机 pytest 区别不大、必要性不足）——待单独设计"可靠化/实用化"（真实 LLM e2e / 跨平台 / 发布产物）后重新启用并补充，另行规划。
- **关联**：PT-FEAT-6（前置条件引用）。

### PT-FEAT-6 CompilationResult 字段精简

- **状态**：active（远期·近期不处理，用户 2026-08-19 划为更远期项目）｜**域**：FEAT｜**优先级**：P3
- **动机**：编译产物字段承载冗余信息，精简后利于序列化契约稳定与维护者心智负担。
- **成因**：管线演进中字段逐步累积，未做过系统性收敛。
- **前置**：PT-FEAT-5 完成 + 管线稳定 ≥ 1 月（诊断/导出/基准就绪）。
- **当前理解**：无独立设计文档，需先盘点 CompilationResult 消费方再定精简面。

### PT-FEAT-12 AST 节点 UID 字段（编译期可见）

- **状态**：active（远期·近期不处理，用户 2026-08-19 划为更远期项目）｜**域**：FEAT｜**优先级**：P3
- **动机**：UID 现仅序列化时生成、编译期不可见；编译期可见的 UID 可供诊断工具与
  元数据导出直接引用。
- **成因**：原 `docs/architecture/02_metadata_ast.md` 愿景内容（§九 优化4）。
- **当前理解**：涉及 AST 结构变更（新增可选字段），实施前须查 `02_metadata_ast.md`
  元数据规约；低优先级，无阻塞。

---

## 二、技术债（DEBT）

### PT-DEBT-5 全项目文件命名清理

- **状态**：shelved｜**域**：DEBT｜**优先级**：P3
- **动机**：过短/欠层次/欠区分度/影子化内建的代码文件命名排查。
- **搁置原因**：破坏面大纯机械，独立窗口执行。
- **当前理解**：无明确清单，启动时先做命名扫描。

### PT-DEBT-35 `_ctx` 内部契约完整形式化（intent_context 判别单一权威）

- **状态**：active（阶段 B 排布，2026-08-20 不再推迟）｜**域**：DEBT｜**优先级**：P2
- **动机**：`intent_context` 封装对象的 `fields["_ctx"]` 槽是全仓 ~20 处共享的半文档化内部契约；
  `_helpers.py:32` 用字段探测判别意图上下文实参（缺 `isinstance(IbIntentContext)` 校验，任何
  `fields["_ctx"]` 非 None 的普通对象误激活）——判别机制"侧表注解 + 字段探测"双轨并存。
- **成因**：Tier C 审计（2026-08-20，_helpers:32 层穿透项）；用户决策：本次仅最小收紧
  （补 isinstance 校验），**完整形式化登记为独立任务**。
- **当前理解**：完整形式化 = 定义 `_ctx` 契约单一权威（类型/协议判别），收敛 ~20 处访问，
  消除字段探测双轨；触及架构边界。**已排入阶段 B（B 序列位），不再推迟**（用户 2026-08-20 裁定）。

### PT-DEBT-36 intent_context 方法族结构重构 + axiom 声明能力契约校验

- **状态**：active（阶段 B 排布，2026-08-20 不再推迟）｜**域**：DEBT｜**优先级**：P2
- **动机**：primitive_initializer 中 intent_context OOP 方法族（L546-728）+ 帧探测簇聚集
  10 处恒真死守卫；bootstrap 建议"axiom 声明能力静默未绑定 → 加契约校验"（L44/L128 宿主实现
  类魔法方法检查无绑定验证）。
- **成因**：Tier C 审计（2026-08-20，bootstrap 组深层次 A/C）；用户决策：死守卫本次清除，
  **方法族结构重构 + axiom 能力契约校验登记为独立任务**（与 contract_validator:63 公理契约
  校验主题相关，可合并评估）。
- **当前理解**：涉及 axiom 声明面与 bootstrap 绑定面的契约（与 PT-DEBT-35 `_ctx` 契约相关），
  **已排入阶段 B（B 序列位），不再推迟**（用户 2026-08-20 裁定；与 PT-DEBT-35 `_ctx` 契约相关，可合并评估）。

---

## 三、周期审计（AUDIT）

### PT-AUDIT-1 代码异味核对分析

- **状态**：active（周期，用户 2026-08-20 裁定推迟到真实试用后）｜**域**：AUDIT｜**优先级**：P2
- **动机**：按 code-quality/code-odor 技能周期回顾；历史 CODE_SMELL_AUDIT 结论（A/B/C/D 全量定案）已并入 WORKLOG 与 git。
- **当前理解**：A/B/C/D 全量定案已完成；**D2「hasattr 全量逐点分类」已由 Tier C 专项审计完成**
  （2026-08-20，113 处位点分类：58 合法保留 / 50 简单异味 / 4 真缺陷 / 4 深层次，处置见
  NEXT_STEPS Tier C + WORKLOG 审计记录）；周期复核。

### PT-AUDIT-2 条件分支与异常嵌套复杂度审计

- **状态**：active（独立窗口）｜**域**：AUDIT｜**优先级**：P2
- **动机**：巨型 elif 分派链（`runtime_serializer._collect_instance` 深度 16、
  `_get_instance` 17、`core_scanner` 10、`binding_analysis_pass` 9）——方向：
  分派表/守卫子句。
- **当前理解**：ibci_ai 窄化、auto_discovery fail-fast 生效（A 类保留）。**前提复核（本 session）**：
  实测核心模块最大 if/elif 平铺链长 2、最大缩进 24 空格（6 层，多来自 for+if 组合嵌套）——
  未发现 >5 层纯 if/elif 分派链；`_collect_instance`/`_get_instance`/`core_scanner` 的"深度
  16/17/10"主张与现状不符（历史代码已重构摊平）。条目收窄为对 for+if 组合嵌套的可读性抽查
  （低优先级，随主线顺带）。

### PT-AUDIT-3 代码复核审查循环（R 系列）

- **状态**：active（周期，用户 2026-08-20 裁定推迟到真实试用后）｜**域**：AUDIT｜**优先级**：P2
- **动机**：R1-R5 已执行；复核清单按 code-review 技能流程执行（历史 PENDING_REVIEW_ITEMS 结论已入 git）。
- **当前理解**：随主线阶段边界择机启动。

---

## 四、文档（DOC）

### PT-DOC-3P2 How-to 层补齐（读者旅程）

- **状态**：active｜**域**：DOC｜**优先级**：P2
- **动机**：Reference→How-to 读者旅程断裂——生成器/并发/llmexcept/隔离等场景缺
  操作指南（现 howto 5 篇：调试/试用/生成器/并发/插件）。
- **成因**：三轴盘点登记（Reference→How-to 读者旅程缺口）。
- **当前理解**：按 WRITING_GUIDE 评估补齐优先级（快速上手/LLM 编排教程优先）。

---

## 五、测试（TEST）

### PT-TEST-2 e2e 测试覆盖率提升

- **状态**：active（阶段 B 主体已补齐，剩余随主线顺带）｜**域**：TEST｜**优先级**：P2
- **动机**：覆盖缺口由 `tests/COVERAGE_MATRIX.md` 矩阵 `🔶 缺失` 项承接。
- **当前理解**：`for...if` 过滤、复合赋值运算符 e2e 已补；**阶段 B 缺口全收敛（B1，2026-08-20）**
  ——新增判别测试 17 项（INV-CAST-2 隐式转换 / INV-INTENT-PRIORITY-2 / INV-INTENT-FLOW-3 /
  INV-MOCK-3 / 模块缓存 / 循环 import / switch 内 return）+ 矩阵卫生（INV-INTENT-SCOPE-3 已有
  snapshot 冻结测试、INV-LLMEXCEPT-CATCH-4→5 重号、switch 已有 break+continue）+ §7 模块重载
  =设计排除（无热重载机制，违反解释器不修改代码原则，见 `docs/architecture/01_principles.md`）；
  剩余缺口随主线顺带补齐。

---

## 六、决策（DECIDE）

### PT-DECIDE-2 供应商感知的模型思考禁用机制

- **状态**：sealed（用户 2026-08-19 裁定：短期不再考虑启动）｜**域**：DECIDE｜**优先级**：P2（解封后）
- **动机**：本机 qwen3.6-35b-a3b 已通过 LM Studio 界面替换提示模板实现非思考模式
  （开发试用基线）；但 API 参数 `enable_thinking=false` 在纯 GGUF（无 model.yaml）
  下无效的机制问题仍在——IBCI 侧需按供应商参数形态实现思考禁用/检测失败覆盖，
  对未应用界面预设的部署环境有效。
- **成因**：真实 LLM 试用环境调查实证（LM Studio model.yaml 机制）。
- **当前理解**：机制边界已由 LLM 调用层插件化定案——思考禁用/探测是**provider 侧
  能力**，`LLMCallRequest.thinking_mode` 是供应商无关声明，各供应商字段映射
  （LM Studio/llama.cpp `enable_thinking`、vLLM、Ollama、OpenAI `reasoning.effort`、
  Anthropic `thinking.budget_tokens`、Gemini `thinkingConfig`）在各自 provider 实现
  内完成。推荐 provider 已含 LM Studio + Qwen 思考抑制适配；其它供应商参数映射
  为按需求的后续实现窗口（默认 provider 覆盖缺口依旧）。与 LLM 调用层插件化主线
  （F4 provider 自定义经宿主绑定统一）收敛。
- **解封条件**：出现多供应商思考模式部署需求时评估重启。

### PT-DECIDE-3 LLM prompt 协议家族待决项

- **状态**：active（剩余 ②④；①③ 已定案落地 2026-08-19 收敛阶段 6-7）｜**域**：DECIDE｜**优先级**：P2
- **动机**：① 用户类 `__from_prompt__` 返回目标类实例的 auto-boxing 二次封装边界；
  ② `__validate_prompt__` 是否扩展至内置类型；③ `SEM_PROTOCOL_SIGNATURE` 强度
  （warning vs error）；④ `__to_prompt__`/`__payload_prompt__` 异常回退可观测性复核。
- **定案记录（2026-08-19）**：① 选 B 单向契约——`__from_prompt__` 返回值必须是目标类型
  实例，非实例=契约违约（诊断+uncertain），删除 `_auto_box_value` 三级启发式兜底（对齐
  06_oop §6.7 既有文档契约）；③ 选 B——required 协议成员签名违约升编译错误（fail-fast），
  optional 成员（`__intent__`/`__retry__`）运行期 fail-fast 不经此路径。
- **剩余待决**：② `__validate_prompt__` 扩展至内置类型（需评估内置解析器是否统一走该协议）；
  ④ prompt 协议异常回退可观测性复核。
- **成因**：PROMPT_DESIGN_REVIEW 收敛。
- **实证补充（2026-08-18，exp/protocol-vtable）**：D2 `to_prompt` 协议**零消费者**
  （核心无 `satisfies_protocol(...,'to_prompt')` 调用；所有内置类型 satisfies=F 但运行期均经
  vtable `__to_prompt__` 渲染）——真激活须接 PromptRenderer 协议前置，**归 P5**；
  D1 `PROMPT_PROTOCOL_SPECS`（4 方法，无 `__payload_prompt__`）与 `BUILTIN_PROTOCOLS` 的
  `payload_prompt` 双注册表——补 `__payload_prompt__` 会激活 `validate_prompt_protocol_signature`
  （L565 警告级）对用户声明的校验；`trials/T08/D2-05-payload.ibci` 与 test_multimodal_* mock
  类有此声明，契约须按 axiom 签名 `(self,value,spec=None)` 定，需核验不产生伪警告——**归 P5**。
  另：str 已补齐 output_hint（D4，exp 分支 `eb8ecd30`）——PT-DECIDE-3 项②若涉 str 现有基础确认。

## 七、封存（SEALED）

### PT-SEALED-1 media Phase 4 多模态容器

- **状态**：sealed（无限期搁置）｜**域**：SEALED｜**优先级**：—
- **动机与成因**：多模态为远期愿景；前置（路径统一/内核原生化/磁盘型存储）已完成，
  但因语言主线（类型地基/协议化）长期优先而显式封存。
- **解封条件**：恢复需显式解封并重估；代码层零启动，设计要点在 git 历史。
  解封需实现：① 多模态模型注册字段（`ai.register_model` 存 modalities/endpoint/
  audio_config）；② 非聊天端点推理绕过；③ 磁盘型响应解析协议。
- **现有基础**：`__payload_prompt__` 协议与 `audio`/`image`/`video` 类型
  （见 `docs/syntax/07_behavior_expressions.md` §7.6、`docs/subsystems/02_file_container.md`）。

---

## 八、愿景（VISION）

### VISION-1 二层 IR 路线

- **动机**：为诊断、优化与跨后端铺路的中间表示层。概念验证阶段，前置条件多
  （编译器管线稳定 + 基准就绪）；与 PT-FEAT-7 同源。

### VISION-3 真实 LLM 压力试用扩展（T08 延续）

- **动机**：T08 第一轮（41 例）完成后待扩展的压力维度——更长 prompt（>4k token）、
  多轮长对话、批量并发上限、多模态真实媒体文件（media 封存除外）。
- **成因**：试用主线；被协议化重构主线占用而顺延。
- **当前理解**：真实 LLM 套件与工具链就绪（`trials/_toolkit`）；理论清理完成后
  按用户意愿恢复。

### VISION-4 类型理论加固（五大地基改造 · P7）

- **动机**：五大地基"完整改造"最终目标的一部分（用户 2026-08-18 定方向，决策 6 列为
  远期，P1-P6 稳定后重估）。
- **当前理解**：ADT（enum 升级为实例化成员）/联合类型可选；模式匹配 `match`（建立在协议+
  泛型上，`docs/LANGUAGE_DESIGN_EVOLUTION.md` §3.7/Phase 4）；轻量约束收集推断扩展（非完整
  HM，HM 仍非目标）；fn[...] 变体规则形式化。调研与总路线见 `tasks_docs/_five_foundation_redesign.md` §四 P7。

### VISION-5 函数式地基补齐（五大地基改造 · P8）

- **动机**：五大地基"完整改造"最终目标的一部分（用户 2026-08-18 定方向，决策 6 列为
  远期，P1-P6 稳定后重估）。
- **当前理解**：协议化高阶组合子（map/filter/reduce/fold 经协议/impl）；部分应用/柯里化
  （可选）；不可变/纯函数标注（可选，评估价值）。依赖 P2/P4 协议化地基（组合子经协议）。
  调研与总路线见 `tasks_docs/_five_foundation_redesign.md` §四 P8。

---

## 九、设计决策保留（防止未来误解）

### 9.1 仍有效的设计决策

| 决策 | 内容 |
|------|------|
| 运行时值 `type_ref` 保持基础 spec | 可变值（list/dict）不固有泛型身份（同一对象可赋给 list[int]/list[str]，语义不自洽）；符号/序列化侧已精确 |
| callable 签名属值层属性 | fn_callable/behavior 的签名在运行时值创建时经 node_to_type 捕获、自持于值（JSON 安全字符串，序列化保真）；不落 CALLABLE_INSTANCE 类型 spec |
| 通信 `Signal` 抽象移除 | 零消费者空壳 + 与 VM 控制流 Signal 撞名 → 彻底删除（KNOWN_LIMITS §二十二） |
| 瞬态序列化协议 | thread/chan/slot/subscriber 统一 `__transient_state__` 存根；反序列化不复活活体 |
| 类型符号 `class_ref` | IbClass 序列化为类名引用、反序列化重绑定 registry 真实类 |
| 泛型成员特化协议化 | `resolve_member` per-type 级联收敛为 `GenericTypeDeclaration` 声明回调 |
| 行为体 fn `-> auto` = str 强制 | LLM 输出默认字符串；要其它类型必须显式 `-> T` |
| 可调用实例不写 value_meta | meta 冗余拷贝专用字段且含非 JSON 值；专用字段是单一事实来源 |
| `expected_type` 落盘为类型名字符串 | 运行期由调用点经 node_to_type 解析；字段本身仅元数据 |

### 9.2 设计排除（语言级限制，已写入 `docs/KNOWN_LIMITS.md`）

| 排除 | 原因 |
|------|------|
| walrus `:=` / lambda 体赋值 | 设计排除（KNOWN_LIMITS §十七） |
| if-block 内重声明同名变量 | 设计排除（KNOWN_LIMITS §十七） |
| loader 与 check.py 签名校验收敛 | 设计隔离：SDK 离线校验不初始化运行时，强制收敛引入 SDK↔runtime 错误耦合，不收敛 |

---

## 十、推迟工作记录：循环打破局部 import tradeoff

> 原则：理想上应永远避免循环依赖。允许少量"设计合理、能显著减少工作量"的局部 import
> 作为谨慎 tradeoff。以下为保留的循环打破局部 import，待架构重构（依赖方向下沉/
> 接口上移）时逐项复核。

| 记录 | 位置 | 引用 | 保留理由（tradeoff） | 未来复核方向 |
|---|---|---|---|---|
| L1 | `core/runtime/objects/kernel/base.py` | `from .functions import IbBoundMethod` / `from .ib_class import IbClass` | 运行时构造/分派所需，base↔functions/ib_class 环 | 下沉共享基类到独立叶子 |
| L2 | `core/runtime/objects/kernel/ib_class.py` | `from .functions import IbBoundMethod` | 运行时构造，ib_class↔functions 环 | 同上 |
| L3 | `core/kernel/spec/type_ref.py` | `from .base import TypeKind` | 运行时 kind 比较分派，base↔type_ref 环 | 下沉 TypeKind 到叶子 |
| L4 | `core/kernel/spec/registry/_members.py` | `from ..base import TypeDef` | 运行时构造 TypeDef | 下沉 TypeDef 到叶子 |
| L5 | `core/kernel/spec/registry/_runtime.py` | 相对导入 | 运行时（审计标注循环打破） | 复核定位并下沉 |
| L6 | `core/runtime/interpreter/interpreter.py` | `from vm.vm_executor import` | interpreter↔vm 环 | 延迟属性引用评估 |

---

## 附、书写模式（本文档专用模板，书写必须参照）

> 本节是本文档条目书写的**唯一权威模板**（模板归属 = 文档自身；`GOVERNANCE.md`
> §三 仅做索引）。新增/修改条目一律按下列模板与规则书写。

### 1. 条目编号

- 格式：`PT-<域代号>-<序号>`，序号在域内**递增分配**（不重用已移除序号）。
- 域代号：FEAT / DEBT / AUDIT / DOC / TEST / DECIDE / SEALED。
- VISION 条目用 `VISION-<序号>`，独立编号。
- 编号是纯标识符，不承载优先级或时间信息。

### 2. 域分类（条目必须归属且仅归属一个域）

| 域 | 含义 |
|----|------|
| FEAT | 语言/工具链功能愿景 |
| DEBT | 架构缺陷与清理项 |
| AUDIT | 周期审计与健康检查 |
| DOC | 文档体系缺口 |
| TEST | 测试体系缺口 |
| DECIDE | 待裁定设计问题 |
| SEALED | 显式封存（恢复需解封评估） |
| VISION | 远期方向（无排期） |

### 3. 条目模板

```markdown
### PT-XXX 任务名（短名词短语）

- **状态**：active（活跃）/ shelved（搁置）/ sealed（封存）/ done（完成）
- **域**：<域代号>｜**优先级**：P0 / P1 / P2 / P3
- **动机**：为什么想实现（用户驱动 / 架构统一 / 实际需求）
- **成因**：问题从哪来（历史妥协 / 演进缺口 / 缺陷暴露）
- **搁置原因**：（shelved 时必填）为什么停止
- **当前理解**：现状边界 + 已确认方向（如有）
- **关联**：相关文档/代码/其他任务（指针，不复制内容）
```

VISION 条目模板（仅保留规划价值字段）：

```markdown
### VISION-N 名称

- **动机**：远期方向与价值
- **成因**：（如有）从哪来
- **当前理解**：（如有）现状边界
```

### 4. 字段规则

| 字段 | 规则 |
|------|------|
| 状态 | 值域 `active` / `shelved` / `sealed` / `done`；`shelved` 必须填搁置原因；`sealed` 必须给解封条件 |
| 优先级 | P0 > P1 > P2 > P3（维度：架构健康性 > 易用性 > 长远收益）；shelved/sealed 可标注"恢复后"优先级 |
| 动机/成因 | 各 1 句，说清"为什么想要"与"从哪来"，不写历史叙述（git 承载） |
| 关联 | 只放指针（文档路径/代码路径/任务编号），不复制正文（单点真理） |

### 5. 概览表与生命周期

- 概览表统计（各域 活跃/搁置/封存 计数）在条目增删/状态变更时**同步更新**。
- 条目完成：标 `done` 或从本文档移除（历史由 git 承载），同时更新概览表。
- 条目不承载已完成内容的历史叙述；需要追溯时用 `git log`。
