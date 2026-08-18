# 临时任务文档：P4b LLMCallable 装配路径设计定稿

> **性质**：临时任务控制文档（code-workflow §二 设计交付物）。P4b 落地后删除（git 承载）。
> **承接**：`NEXT_STEPS.md` 候选 #1 P4b；设计权威 `_five_foundation_P1_design.md` §2.2/§2.4，
> 决策权威 `_five_foundation_redesign.md` §五。
> **状态**：Phase 0-2 调研 + 设计定稿；实现按 §四 落地顺序推进（P4b-1 本轮）。

## 一、目标与范围

P1 §2.4 消费路径统一：
```
[可调用实例] ── has LLMCallable ──► __llm_call__(装配上下文) ──► LLMCallRequest
                                        ▼
                          _call_and_parse（统一 worker：_call_llm + _parse_result）
```
本阶段把"行为值 / 用户 llm 可调用类 / 匿名可调用实例"统一为**同一消费路径**，
`satisfies_protocol(..., 'llm_callable')` 为唯一入口判定（P4a 已注册协议）。

**本轮闭合件（P4b-1）**：
- 装配上下文内核对象 `IbLLMCallAssemblyCtx`（IBCI 一等对象，用户 `__llm_call__` 消费）。
- 统一装配入口 `assemble_llm_callable_request_cps`（协议门 + 行为/用户类两路推进）。
- 执行入口 `invoke_llm_callable_cps`（装配 → 统一 worker `_call_and_parse`）。
- 用户 llm 类 `__llm_call__` 支持 + 判别测试；行为路由经统一入口（零行为变化）。

**不做**：`llm ... llmend` 语法删除（P4c）；retry 高阶化（P4d）；run_batch/stream 全量
统一（P4b-2/P4b-3）。

## 二、设计难点与解决（self-grill 产出）

### 2.1 装配上下文形态（用户可消费面）

- **`__llm_call__` 的装配上下文 = IBCI 一等对象**（`IbLLMCallAssemblyCtx`，注册为内核
  类型 `llm_call_ctx`），封装装配所需内核原始信息 + 用户可写槽：
  - 只读：`intents`（意图块三层：active/global/merged，消解结果）；
    `expected_type` / `output_hint`（输出契约输入）；`target_model`；`node_uid`；
  - 可写：`set_user_prompt(str)`；`add_prompt_slot(kind, text)`（自定义槽，替代旧
    `__sys__` 的 `user_sys` 槽形态）；`set_output_hint(str)`；`set_model(str)`。
- **为何对象化而非 dataclass**：用户 `__llm_call__` 在语言层互操作（方法调用/字段），
  须为一等对象；LLMCallRequest 保持底层 dataclass（base 层契约，不 DbObject 化，P1 §2.3）。

### 2.2 用户 `__llm_call__` 契约（self-grill 钉死）

- 形态：`func __llm_call__(self, llm_call_ctx ctx) -> void`（**ctx 变异式**，非返回式）。
  用户方法设置 ctx 的 user_prompt / prompt_slots / output_hint / model；
  返回 None。内核装配入口在调用后把 ctx 变异结果映射为 LLMCallRequest。
- 理由：LLMCallRequest 非语言类型，用户无法/不应直接构造；ctx 变异 = IBCI 既有
  "配置对象变异"模式（`ai.load_project_config` 同构），且不引入语言类型构造底层
  契约的耦合。**机制同构**（design-philosophy §四）。

### 2.3 CPS 段求值 vs 同步 receive 分派（关键张力）

- 行为装配需要 CPS 段求值（`_evaluate_segments_cps` yield 嵌入 VM 帧栈）；
  用户 `__llm_call__` 是语言方法（可能含 Waitable）。
- **解决**：统一装配入口 `assemble_llm_callable_request_cps` 是 **CPS 生成器**
  （调用方 `yield from`）。对用户类：`yield UserFunctionCall(inst, [ctx], receiver)`
  由 VM 调度循环驱动（普通函数同步执行，含 Waitable 则调度器挂起）。对行为值：
  内核原生装配（`_prepare_behavior_call_cps` 语义槽贡献），入口内 yield from。
- `__llm_call__` 作为协议方法存在 = satisfies 判定与 `dunder_names` 索引用；
  实际分派经 executor 的 CPS 装配入口（不直接同步 receive——避免 CSP 分裂）。

### 2.4 行为 vs 用户类的装配差异承载

- 差异经**协议方法自身**承载（mechanism同构，禁 `if 标志位` 过程分派，G3/D11）：
  - 行为值 `__llm_call__` = 内核原生装配（语义槽模型，现有 `_build_behavior_call_request`）。
  - 用户 llm 类 `__llm_call__` = 用户方法（ctx 变异）。
- 统一入口只做"协议查询 → 经类型自身的 `__llm_call__` 取请求 → 统一 worker 执行"。

## 三、现状调研（实证基线）

- 行为路径：`_behavior.py` — `execute_behavior_expression_cps` → `_prepare_behavior_call_cps`
  （段求值 yield + 意图消解 + hint）→ `BehaviorCallSpec` → `_call_and_parse`（worker）。
- `_call_and_parse`（`_behavior.py` L276）已通用：取 `spec.request` → `_call_llm` → `_parse_result`。
- `satisfies_protocol(..., 'llm_callable')`（P4a）当前仅用户类结构判定（spec.members
  含 `__llm_call__`）；行为值不满足（其 spec 无此成员）——行为满足 llm_callable 由
  P4b-1 的"行为 `__llm_call__` 存在性"承载（内核注册行为方法表条目或经 execute 入口判定）。
- `run_batch` 目前 `isinstance(behavior, IbValue) and name=="behavior"` 窄校验。

## 四、落地顺序（勿半接通）

- **P4b-1（本轮）**：装配上下文 `IbLLMCallAssemblyCtx` + 统一入口
  `assemble_llm_callable_request_cps` + 执行入口 `invoke_llm_callable_cps`；
  用户 llm 类（`__llm_call__(ctx)` ctx 变异）经统一 worker mock 调用判别；
  行为路径**零行为变化**地经统一入口路由（回归证明）。
- **P4b-2**：`run_batch`/`stream` 接受"任何 LLMCallable 实例"（移除 `isinstance(behavior,
  name=="behavior")` 窄校验）；行为值满足 llm_callable 的显式化（内核注册）。
- **P4b-3**：`__intent__` / `__retry__` 可选协议方法运行时发现 + 装配上下文承载。

## 五、验证门

- 判别：用户 llm 类经统一入口 → mock provider 收到其 ctx 装配的 user_prompt；
  行为经统一入口 == 直接路径（LLMCallRequest 等价）。
- 全量 pytest 零回归 + 本地 commit；低风险可 merge unsafe-vibe-dev（用户授权）。

## 六、用户侧蓝图（P4b-2 示例，llm 可调用类用户写法）

```ibci
# 用户定义具名 llm 可调用类（替代 llm 函数）
class Translator:
    # 装配上下文 ctx（llm_call_ctx 类型，any 槽位接收）：
    # 用户方法变异 ctx → 内核装配入口映射为 LLMCallRequest
    func __llm_call__(self, any ctx):
        str prompt = "将「" + $self.text + "」翻译为" + self.target_lang
        ctx.set_user_prompt(prompt)
        ctx.set_output_hint("只输出译文，不要解释")

    str text = ""
    str target_lang = "英语"

Translator tr = Translator()
tr.text = "hello"
# 经 run_batch / stream（P4b-2）或统一执行入口消费 tr（LLMCallable 实例）
```

