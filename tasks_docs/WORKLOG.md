# WORKLOG — 自主工作日志

> 原则：**"只记录，不断决"**——能自主决定的记录决定并推进；只有确实无法决定的才标记待决并上报。
>
> **记录策略（2026-08-05 起）**：历史会话中已讨论定案、已落地、已由 `NEXT_STEPS.md`"已完成"节
> 与代码承载的内容，随落地归档（git 历史保留完整版）。本文档只保留**仍有参考价值的决策**
> 与**关键用户裁定**。
> 最后更新：2026-08-05
---

## 〇、会话 17：未修缺陷待办全量处置（2026-08-05）

> 用户指令：根据已知问题自主分析推进修复（未修缺陷待办 = 当前 session 范围），确认后直接
> 高度自主运行，无需再询问。全程本地 commit、禁 push。

### 已完成（commit 序列，每批全量 pytest 零回归）

- **PT-ARCH-31 序列化工作（档位 A+B）** commit 662b83c：
  - 档位 A：`_serialize_symbol` 补 `is_cell`（cell 值优先，与 ScopeImpl.get 单一真相源一致）；
    `_serialize_closure`（lambda→cell 当前值 / snapshot→深克隆种子）；behavior 补 closure、
    fn_callable 补 closure/params_uids/body_uid；可调用实例不再冗余写 `value_meta`（携带
    IbIntentContext/IbCell/TypeDef 非 JSON 值破坏 save_state 落盘——实测 json.dumps 失败）；
    `expected_type` 按 Optional[str] 契约以类型名字符串落盘（运行期经 node_to_type 解析，字段仅元数据）。
  - 档位 B：反序列化新增 fn_callable 分支（此前落 else 空 IbObject 全丢）；is_cell 符号经
    promote_to_cell 语义重建；`_deserialize_closure` 先重建自包含 IbCell + 登记待重链；
    post-pass `_relink_cells` 按 sym_uid 在恢复作用域树中查找持有符号的作用域，promote 共享
    cell 替换闭包槽（修复外层重赋值不可见 + 多闭包共享分叉）；不在树中（闭包持有者作用域
    已退出，LT-2 堆语义）保留自包含 cell。
  - 测试 `tests/runtime/test_closure_serialization.py` 12 用例（snapshot 保真/lambda 自包含/
    参数保真/作用域 cell 重链/双闭包共享/外层重赋值可见/behavior+MOCK 调用一致）。
- **PT-ARCH-32 Axiom 家族分裂** commit 759956b：IntentAxiom/IntentContextAxiom 继承 BaseAxiom，
  删手抄 no-op 与重复 `_m`，仅保留 name/is_class()/get_method_specs 覆盖。行为等价。
- **PT-ARCH-33 EnumAxiom 双通道** commit d82b989：删 to_native/receive hasattr 双轨 + 宽 except；
  按协议契约 str 入参，非 str fail-fast TypeError。测试 test_enum_axiom.py 8 用例。
- **PT-ARCH-34 use_intent_context** commit 661d02c：删三层恒真 hasattr 守卫；非 intent_context
  入参 fail-fast InterpreterError（用户可见 API 行为变更：return False→抛错，已核对调用方全部
  忽略返回值）；返回类型对齐接口声明（-> None）。测试 test_e2e_intent.py +2。

### PT-SMELL-R3 四 Zone 处置（4 general agent 独立取证 + 主会话逐项核验）

- **Zone A+B 批** commit ee7c480：A-D1（lexer NORMAL `$` 失败路径对齐 IN_INTENT，防御纵深）、
  A-D2（DEP_GRAPH_ERROR 统一抛 CompilerError，诊断孤儿消除）、A-D4（nonlocal 兜底注释修正）、
  A-D7（_loc 删双形状 hasattr）、A-D9（registry 删恒真 hasattr）、A-D10（dependencies 删死兜底）、
  B-D1（_obj_to_prompt_str except 收窄 AttributeError）、B-D4（coordinator isinstance(IbFunction)）、
  B-D5（request_collect isinstance 前置 + try 窄化）、B-D7（module_manager 删宽 except 误译）、
  B-D8（tuple 解包照搬 lookup_method 结构化预检）、B-D12（_try_vtable_hint 删 try/except）。
  **B-D6 判为复核定案保留**：尝试改 uid_map 迭代源引入回归（uid_map 含当前模块全部符号含内建），
  dir∩uid_map 交集才是正确白名单，已回退。
- **Zone C 批** commit 0b9e306：C-D1（删死 vtable 'call' 分支 + isinstance(IbFunction)）、
  C-D2（白名单 getter 异常重抛 InterpreterError）、C-D4（删 IbTypeAnnotatedExpr wrapper 嗅探）、
  C-D6（isinstance(IbClassField)）、C-D9（discovery 删 except ImportError + artifact_loader
  先查 get_class 再创建）。
- **Zone D 批** commit 6c3f25b：D-D1（_extract_reasoning 单一 helper）、D-D2（isys 契约直访 +
  fail-fast，is_sandboxed 保留安全默认）、D-D3（iruntime 直访 + 统一 raise，不再静默 {}）、
  D-D4（双接口复核定案保留 + 消费者删 hasattr/except 收窄）、D-D5（node_pool 直访公开 property）、
  D-D6（run_batch 删 _execution_context 私有穿透）、D-D7（删 localhost '/v1' 字符串嗅探，
  5 个测试文件显式补 /v1）。
- **A-D5 批** commit cef4e94：chan/slot 类型注解 `_expr_name` shape 归一（IbName/IbConstant/
  IbAttribute 全限定名/IbSubscript 基名，删 str() dataclass 垃圾名）+ **修复 chan 关键字参数
  路径坏死**（`self.stream.previous()` 是只读回看不移动光标，`chan(T, mode=...)` 此前永远
  解析失败——A-D5 报告所称"垃圾 mode 进 ChannelCore"实为解析失败，比预想更严重）。测试 +3。

### 设计决策 / 保留项

- **expected_type 落盘为类型名字符串**：运行期由调用点经 node_to_type 侧表解析，字段本身仅
  元数据（serialize_for_debug），按接口契约 Optional[str]。
- **可调用实例不写 value_meta**：meta 冗余拷贝专用分支字段且含非 JSON 值（IbIntentContext/
  IbCell/TypeDef），原样落盘破坏 save_state；专用字段是单一事实来源。
- **PT-SMELL-R3 复核定案保留 10 项 + 设计确认保留 6 项**：明细见 `PENDING_TASKS.md` PT-SMELL-R3
  表（处置列）。其中 B-D2（"已声明类型无 parser → uncertain"）属语言级语义决策记录待用户
  拍板；C-D3/C-D7/B-D10 协议化列入长期项。
- **测试基线**：1532 passed / 6 skipped（以实跑为准）。

### B-D6 复盘根治（会话 17 后补，用户质询触发）

- **用户质询**："uid_map 混有 prelude/内建符号是否正常设计还是设计缺陷？感觉有断层和不统一"。
  实证结论：**命名/契约断层**——`_import_star_uid_map` 读整张模块根作用域表（58 符号含内建），
  却叫"import-* uid 映射"、docstring 声称"为 import-* 成员创建带 uid 的 Symbol"（编译器实际
  未做专属 uid）；正确性依赖下游隐式 `dir(package)` 交集。非功能 bug（可达场景均正确），但
  属"隐式约定"与"结构性信息丢失"（精确契约集合只在编译期存在，未序列化）。
- **根治重构** commit 37be9ca：编译器在 import-* 注入时精确记录成员名 →
  `CompilationResult.import_star_members`（新字段）→ artifact 序列化 → 运行时 `_import_star_members`
  精确枚举；`_import_star_uid_map` 改名 `_module_scope_uids`（诚实语义，仅供按名查 uid）；
  包分支/IBC 分支均改精确枚举，spec 声明但实现缺失显式报错（与具名导入一致）。
- **连带发现并修复：IBC 文件跨模块导入三层断裂（零测试覆盖，功能完全不可用）**：
  ① scheduler:407 裸 `TypeDef`（被别名 `ModuleMetadata` 后 NameError → INT_INTERNAL_ERROR，
     所有 `from <ibci文件> import x` 编译即崩）；② 文件模块元数据用 Lazy 空描述符，members
     恒空 → 全 SEM_UNDEFINED_SYMBOL（改 `registry.resolve` 取真实 meta，依赖图拓扑序保证
     依赖先编译）；③ 运行时 `module_instance.get_variable`（IbModule 无此方法）→ AttributeError
     （改 `scope.get`）。
- **测试**：新增 tests/runtime/test_ibc_file_imports.py 9 用例（具名/星号/别名/多模块/artifact
  契约）。全量 1547 passed / 6 skipped 零回归。
- **教训**：复核定案"保留"某机制前，应核实该机制的名称/文档与实际语义是否一致；subagent
  建议与实现之间的断层要靠测试+用户视角质询暴露。B-D6 初判"保留"经用户质询后证明为误判，
  已升级为根治。

---

## 一、关键用户裁定（长期约束力）

| 裁定 | 内容 | 来源 |
|------|------|------|
| 碎片化判断基准 | **碎片化 = 设计语言（用户语义形态）统一，非实现路径一致**。同类内容内部实现路径差异，只要有语义需求驱动、且不改变用户语义形态，即非碎片 | 会话 12 |
| "不删也不修" | 有缺陷/冗余的机制只能"**根本修复**"或"**彻底删除**"两档，禁止"废弃记录"中间态 | 会话 9 |
| subagent 约束 | 所有 subagent 工作（含 review）**仅允许 general agent**，禁 explore/reviewer 特化 agent | 会话 6 |
| 决策纪律 | 需拍板的决断项可大胆激进选方案；底线 = 架构原则/代码质量原则/非妥协/非 tricky/非临时兼容层/大方向主线 | 会话 1 |
| behavior/fn 闭包序列化 = 明确设计缺陷 | R3 后用户裁定：closure 序列化丢失属**明显设计缺陷**，必须记录为未来改进任务（→ `PENDING_TASKS.md` PT-ARCH-31） | 会话 16 |
| permissive any 需重审 | 用户裁定：类型系统已成熟（LHS 目标类型 / 标注 / 泛型），any 兜底不再默认合理，需按实际可达面重审（→ 会话 16 分析结论） | 会话 16 |
| 禁 push / 破坏性重构授权 / 分支政策 | 见 AGENTS.md（权威源，此处不复制） | — |

## 二、仍有效的设计决策

| 决策 | 内容 |
|------|------|
| 运行时值 `type_ref` 保持基础 spec | 可变值（list/dict）不固有泛型身份（同一对象可被赋给 list[int]/list[str]，语义不自洽）；符号/序列化侧已精确（L7-A），值侧记录为设计决策（会话 12） |
| 通信 `Signal` 抽象移除 | 零消费者空壳 + 与 VM 控制流 Signal 撞名 → 彻底删除；`signal(...)` 语言关键字全链移除（会话 8） |
| `core`/`view` 槽 = 句柄承载 | IbChannel/IbSlot/IbSubscriber 的 core/view 槽与 thread `__slots__` 同构（句柄/内核状态经槽承载），非值对象碎片（会话 12） |
| 瞬态序列化协议 | thread/chan/slot/subscriber 统一 `__transient_state__` 存根；反序列化不复活活体（会话 10） |
| 类型符号 `class_ref` | IbClass 序列化为类名引用、反序列化重绑定 registry 真实类（会话 11） |
| 泛型成员特化协议化 | `resolve_member` per-type 级联收敛为 `GenericTypeDeclaration` 声明回调（会话 9） |

## 三、已完成工作摘要

> 会话 1-12 全部落地 unsafe-vibe-dev（本地 commit，未 push）。批次/commit 明细见
> `NEXT_STEPS.md`"已完成"节；历史会话完整记录在 git（`git log` 追溯）。

- **线程对象模型方向修正（A-F）**：`thread` 取代 spawn/join/cancel/task；async/thread 彻底分离。
- **通信领域设计完善三阶段**：B1-B4 实锤 bug + G1-G7 统一化（值对象机制/序列化/通信域）。
- **收尾 L1-L8 + T2**：_by_kind 删除 / 泛型成员特化协议化 / 序列化清理 / 瞬态序列化协议 /
  类型符号 class_ref / IbOptional 单承载 / 泛型注解符号身份 / `_create_blank` 构造入口统一。
- **R1 完整独立复核（2026-08-05，会话 13）**：三个 general agent 并行独立复核三阶段主线 +
  收尾全部改动（`e217b8b^..80b463e`）。整体正确，无高严重缺陷；新增缺陷 A1/C1/B1-B6/D1-D4
  全部处置（A1 cancel is_done 守卫、C1 multi-type list/tuple positional 序列化持久化、B 组
  死代码清理、D 组文档化）。发现清单与决策见 `PENDING_REVIEW_ITEMS.md` §〇。
- **R1 修正批（2026-08-05，D 系列重分类）**：用户质询"文档化是否违反不删也不修"触发自我
  质询重新取证，纠正初判误分类——D1（chan/slot 半接通，axiom docstring 声称 value_type
  承载未落地）、D3（send 泄漏 CommClosedError 给生产者）、D4（close 后 subscriber_count
  失真）、D6（自然完成线程 is_done() 误报 False，真 bug）均**根本修复**并补测试；D2/D5
  确认为真设计限制/效率，文档化合理。修正记录见 `PENDING_REVIEW_ITEMS.md` §〇 D 系列。
- **注释卫生清理（2026-08-05）**：用户指出近期工作（会话 6-13）在代码注释/docstring 大量
  引入任务代号/进度标记。全仓清理 66 文件：删除 L7-A/R1-Dx/G7/D1-D6/B1-B4/L8/C1/A1、
  任务 A-F/C0-C2、PT-MT-\*、阶段 2/3、疏漏 N、VP-/F-、MERGED、THREAD_DESIGN_REVISION、
  WORKLOG 会话、日期戳、文档章节号（§3.1/§8.1）等标记，保留功能说明；INV-\* 契约不变式
  码（等价公理码）保留。全量 pytest 零回归。commit db3c610（仅本地）。
- **R2 健康诊断 + 二次复核（2026-08-05，会话 14）**：code-quality 健康诊断十查，四个
  general agent 并行独立诊断（编译/类型层、运行时核心层、对象/通信/插件层、测试/引导层），
  发现约 50 项。随后用户裁定——所有"需讨论/设计限制/倾向文档化"项经四个独立 subagent
  二次复核（架构层面 + IBCI 设计思路：功能必要性/设计目的/修复长久收益），用户偏好彻底
  修复优先。**结论**：30 项升格为彻底修复/删除（批次 A-E），12 项确认真设计决策保留+文档化，
  其余保留+局部修复。**用户确认两项关键决策**：① `IbSlot.update(fn)` 方案 A 接通语言面
   RMW（复用 SlotCore 已测 CAS 机器）；② `Task* → Thread*` 语言面改名授权。完整清单见
   `PENDING_REVIEW_ITEMS.md` §〇b 与 §二次复核决策记录。
- **R2 处置完成（2026-08-05，会话 15）**：按批次 A-E + 补充项全部落地（本地 commit 序列：
  381d30e/1ee2bcb/77d0863/7473a8b/94c8e86/末批），每批全量 pytest 零回归后提交。涵盖：
  机械清理（负数误lex/CJK/动态槽/去BOM）、fail-fast（反序列化/能力查询/前缀碰撞/插件状态/
  run()）、半接通语言面（IbSlot.update 方案A 接通 CAS/media 假值/IsolationPolicy 收敛/
  str 别名/chan(T) 保真/**Task→Thread 改名**）、结构单点（泛型名结构化 TypeRef/运算符映射/
  hasattr/生成器中央化/VMTaskResult/check-gen_spec 格式对齐）、测试健康（make_context/
  root/去skip/LRU/白盒下沉+红线/Engine死API/状态断言）、补充项（enum/SnapshotManager/
  死方法簇/erasure统一/can_return_from_isolated 删除/TypeInferenceState 文档化/AI MOCK 前缀
  收敛/依赖测试改写）。保留+文档化 12 项。**验证**：全量 pytest = 1506 passed / 6 skipped
  零回归（以实跑为准）。
- **R3 code-odor 全面异味扫描（2026-08-05，会话 16）**：4 个 general agent 独立扫描
  （Zone A compiler+kernel / B interpreter+vm / C objects+shared+base / D ibci_modules+sdk），
  26 项疑似真缺陷 + 46 项需讨论；主会话逐项实证核验后按 4 批处置（commit 序列：
  f5d3f94/cb2edbd/c73914d/a1ffbbe/bffe195，每批全量 pytest 零回归）。涵盖：
  **批次A 死代码/不可达清除**（lexer 无作用 try / axiom 重复 return / 解析链死 fallback /
  snapshot 恒假 scheduler 探测 / idbg 悬空 `is_in_fallback`（帧无此字段，命中即
  AttributeError 潜伏崩溃）/ check.py 死常量 dir() 误用 / engine 静默 axiom 注册 /
  删除不可达 `vm_handle_IbBehaviorInstance`）；
  **批次B 恒真守卫移除**（registry hasattr / axiom get_diff_hint / method return_type /
  llm 帧 / interpreter 防御分支 / capture_mode getattr / native_module 白名单 / service
  runtime_context 直访 / parallel 简化；并删除 hydration 参数计数死检查——水化 spec 不
  携带签名信息，字段名 `params` 自始不存在，检查从未生效）；
  **批次C except 窄化/fail-fast**（module_manager try 仅包 getattr / 事件总线
  CommClosedError / iruntime 去静默 try / ibci_net 9 处收窄 RequestException /
  type_def 解析检查点 / scheduler lexer 诊断 / coordinator 去死兜底）；
  **批次D 真缺陷重构**（assignment 复杂目标不再 dispatch——消除"复杂目标先 dispatch 再
  撤销"双通道：该路径吞异常后对同一 LLM 表达式二次调用、且同步成功路径绕过 llmexcept
  不确定性协议；behavior 序列化 round-trip 修复——captured_intents 此前展开为 list 违反
  None|IbIntentContext 契约且二次序列化抛 TypeError，现存 intent_context uid + 补
  capture_mode/params_uids，round-trip 已用真实 engine 验证）。
  **保留+文档化**：axiom 家族分裂（IntentAxiom/IntentContextAxiom 未并入 BaseAxiom，
  设计观察）、LAZY→any/分层 any permissive 语义、deep_clone `type() is` 精确判别、
  media 封存零改动、llm_except best-effort 协议兜底、ibci_ai 宽 except（已记录待决策）、
  behavior closure 序列化限制（与 fn_callable 一致，lambda cell 活引用不可重链）。
  **验证**：全量 pytest = 1506 passed / 6 skipped 零回归（以实跑为准，每批均验证）。

## 四、R3 复核后续处置（会话 16 尾，用户逐项裁定）

- **permissive any 重审结论**（用户裁定"any 不再默认合理"，按类型系统实际可达面重审）：
  - `_members.py` LAZY→any 分支**实证为死代码**（全仓无 `TypeKind.LAZY` 创建点，scheduler 改
    用裸 TypeDef）→ **已删除**。
  - resolve_call_return 的 any 兜底按可达面三分：
    (a) **动态类型语义**（`any` 变量 / 裸赋值 / 容器元素读，`KNOWN_LIMITS §七` 文档化）——保留；
    (b) **auto 推断失败兜底**——保留（推断机制的诚实回退）；
    (c) **未标注可调用定义静默变 any**（`func f():`/`llm f():`/`fn x = lambda:` 无返回标注 →
      语义层直接回填 any，`_declaration_visitors:78/311`、`_expression_visitors:724`）——**属掩盖
      缺口**：语言已有标注/LHS 类型/auto/泛型，却未强制标注，any 静默吸收缺失标注。真实可达
      （tests 中 `func helper():`、未标注 lambda behavior 均有效）。
  - **改进建议（待用户拍板语言变更）**：对 `func`/`llm`/lambda 缺失返回标注发 SEM 错误（要求
    `-> T` / `-> auto` / 显式 `-> any`），替代静默 any。影响面：现有未标注测试需补标注。
- **_values_equal 收窄**（用户裁定"直接改进"）：异常降级由 `return a is b` 改为显式保守
  `return False`（调用方已排除同对象恒等），docstring 明确降级链路设计机制（fail-safe 方向：
  宁可误报篡改触发恢复，不漏报）。
- **ibci_ai 宽 except 收窄**（用户裁定"分析修复方案，自主决断"）：新增 `_PROVIDER_ERRORS =
  (openai.OpenAIError, RuntimeError, ValueError)`（provider 失败契约 = openai 家族 +
  本仓约定的 RuntimeError 信号 + 响应格式 ValueError），收窄 5 处（客户端 init / 命名模型 /
  probe 保守降级 / 非流式 / 流式）；TypeError/AttributeError 等内部缺陷原样传播（fail-fast）。
  probe 保守降级仅对 provider 异常生效，避免内部探测缺陷静默误分类模型。executor
  `_core.py:185` 保留为 provider 协议安全网（任意 provider 异常 → LLMCallError），补充注释。
- **behavior/fn closure 序列化**（用户裁定"必须记录为未来改进"）：已记录为明确设计缺陷 →
  `PENDING_TASKS.md` PT-ARCH-31（lambda 活 cell 不可重链 / snapshot 种子丢失；需设计闭包
  序列化语义并与 fn_callable 一并处理）。
- commit：本轮处置已随会话提交。

## 五、类型强化（2026-08-05，会话 16 尾，用户裁定"any 兜底击穿类型设计"）

> 设计依据：`docs/architecture/01_principles.md §5.3`（`or self._any_desc` 列为禁止的妥协
> fallback）+ `appendix_type_system_rationale.md §九`（静态名义强类型 + 渐进 any 显式逃生阀）。
> 三项收紧全部落地 unsafe-vibe-dev（本地 commit 序列：4991c19/56f8447/95af889/f7f7010），
> 每项全量 pytest 零回归（1506 passed / 6 skipped，以实跑为准）。

- **Task1 强制返回标注**：`func`/`llm`/lambda 缺失返回标注 → `SEM_MISSING_RETURN_ANNOTATION`
  编译错误（替代静默回填 any）。先补 lambda `-> auto` body 推断（非行为 body 推断并锁定；
  行为 body 保持 behavior 动态语义）。~80 个测试点补标注（`-> auto`/`-> T`/`-> void`）。
- **Task2 裸赋值 auto 语义**：裸赋值 `x = expr` 从隐式 any 改为 `auto`（symbol_collection 以
  auto 占位 + 类型检查走 `_infer_target_type_from_declared` 推断锁定）。异类型重赋现在
  `SEM_TYPE_MISMATCH`。显式 `any` 保留为唯一动态逃生阀；any 值用于类型化上下文时运行时
  强制校验（`RUN_TYPE_MISMATCH`，必须显式强转）。
- **Task3 多类型 list 移除**：`list[int,str]` → `SEM_MULTI_TYPE_LIST_REMOVED`（无 union 机制，
  强制显式 `list[any]`）。`tuple[T1,T2,...]` 位置元素类型保留（合法特性）。
- **行为体 fn 的 `-> auto` 唯一 = str（用户裁定强制规则）**：行为 body 的 `-> auto` 不再保持
  behavior 动态语义，而是**唯一推断为 str**（LLM 输出默认字符串，无其它自动推断）；要其它
  类型必须显式 `-> T`（同时设定 LLM expected_type）。附带修复 `fn[()->T]` 声明侧签名约束对
  CALLABLE_INSTANCE（行为/fn lambda）的返回类型校验缺口——此前被跳过导致 `fn[()->int] f =
  lambda -> auto: @~...~` 编译通过而运行期返回 str（声明承诺 int 实际 str），现按 value_type
  校验返回类型（参数约束由调用处实参解析覆盖），不匹配即 `SEM_TYPE_MISMATCH`。
- **验证**：any→typed 运行时强校验、裸赋值锁定、标注强制、多类型移除在各声明上下文生效；
  行为体 auto=str 全套语义（str 承接 / int 报错 / fn[()->str] 匹配 / fn[()->int] 报错 / 带参
  不误伤）实证通过；残留扫描确认 Python lambda 与 tuple 位置元素未误伤。

## 六、fn[...] 签名体系补齐（2026-08-05，会话 16 尾）

> 用户裁定：① 行为体 `-> auto` = str 无条件保留但手册标注"允许但不推荐"，明确推荐 `-> str`；
> ② 补齐 fn[...] 调用点校验缺口。

- **行为体 `-> auto` = str 强制**（`_expression_visitors.visit_IbLambdaExpr`）：行为 body 的
  `-> auto` 唯一推断 str（LLM 输出默认字符串，无其他自动推断）；要其它类型必须显式 `-> T`
  （同时设定 LLM expected_type）。手册（syntax 07 / architecture 03 §7）标注"允许但不推荐，
  需要 str 用 `-> str`"。
- **调用点 fn[...] 校验缺口修复**（根因是 `fn[...]` 参数标注被扁平化为 `TypeRef('fn')`，
  调用点只见裸 fn（动态）而跳过校验，导致 `fn[()->int] f = lambda -> auto: ...` 编译通过、
  运行期返回 str 不一致）：
  1. `_assignability.is_dynamic`：CALLABLE_SIG（`fn[...]`）非动态（裸 fn FUNCTION 仍动态）；
     `is_assignable` 对 CALLABLE_SIG 目标走 `_matches_callable_sig`（参数数量 + 返回类型，
     动态源放行，lambda 参数签名不携带则跳过）。
  2. `_declaration_visitors._param_type_ref`：fn[...] 参数 descriptor 保留结构化 TypeRef
     （`TypeRef('fn', (TypeRef('__args__', params), ret))`），不再扁平化。
  3. `_base.resolve_typeref`：从结构化 fn ref 重建 CALLABLE_SIG。
  - 效果：`apply(lambda -> auto: @~...~)`（fn[()->int] 参数）现在编译错误；`-> int` 匹配通过。
- **连带确认（既有限制，非本次引入）**：带参 lambda（`lambda(int n) -> int: ...`）作为**实参
  内联**存在 parser 限制（基线即失败，声明上下文可用）；`fn[(int)->int]` + 带参 lambda 实参
  属既有未覆盖，记录非本次范围。
- 文档同步：syntax 07、architecture 03 §7。
- 验证：1507 passed / 6 skipped 零回归（新增调用点校验回归测试）。
- 文档同步：`KNOWN_LIMITS.md` §七/八/九、`syntax/02_variables.md`、`05_functions.md`、
  `07_behavior_expressions.md`、`01_types.md`、`architecture/03_type_system.md` §7、
  `01_principles.md` §5.3。
- **测试基线**：`python -m pytest tests/` = 1506 passed / 6 skipped（以实跑为准）。

## 四、遗留 / 待办

- **下一阶段（完整复核审查）**：`tasks_docs/PENDING_REVIEW_ITEMS.md`（R1 ✅ / R2 ✅ / R3 ✅ / R4-R5 待做 + D1-D5 docs 同步）。
- **长期规划**：`tasks_docs/PENDING_TASKS.md`（PT-SEM/PT-4.x/PT-ARCH/PT-SMELL/TEST_REFACTOR 等）。
- **固定化内容**：`tasks_docs/HANDOFF.md`（常驻交接文档：工作流程/原则/goal 模板）。
