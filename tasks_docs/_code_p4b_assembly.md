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

### 2.2 用户 `__llm_call__` 契约（self-grill 钉死 → P4b-2a 修订：返回 dict 形态）

- **P4b-2a 契约（修订，记录理由）**：`func __llm_call__(self) -> dict`——用户方法**返回
  装配配置 dict**（`user_prompt` / `output_hint` / `expected_type` / `model` 键），
  内核装配入口把返回 dict 映射为 `LLMCallRequest`。
  - **为何修订**：避免为新装配上下文引入内核对象类型注册（bootstrap 类 + 公理 + 注册，
    成本高、风险大）；"函数返回配置数据"较"变异上下文对象"更 IBCI 惯用（返回值传递），
    且 P4b-2a 不需要用户读取输入意图。
  - **装配上下文 `IbLLMCallAssemblyCtx`（IBCI 一等对象）降级为 P4b-2b 扩展**：当用户
    `__llm_call__` 需**读取**输入（意图三层/输出契约/目标模型）时，引入 ctx 对象作为
    **额外只读入参**（`__llm_call__(self, any ctx)` 读 + 返回 dict 写）；本阶段不引入。
- 仅当后续发现"返回 dict"不足以表达自定义槽等多种装配时，才按 §2.1 设计方案
  实现 `IbLLMCallAssemblyCtx`（可写槽 + 只读信息）。

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

- **P4b-1（已完成）**：设计定稿。
- **P4b-2a（本轮）**：统一装配入口 `assemble_llm_callable_request_cps` + 执行入口
  `invoke_llm_callable_cps`；用户 llm 类 `__llm_call__(self) -> dict`（返回配置 dict）经统一
  worker mock 调用判别；行为路径零变化（行为经各自路径，纳入统一入口在 P4b-2b 收敛）。
- **P4b-2b**：`run_batch`/`stream` 接受"任何 LLMCallable 实例"（移除 `isinstance(behavior,
  name=="behavior")` 窄校验）；行为经统一装配入口路由（机制同构收敛）；装配上下文
  `IbLLMCallAssemblyCtx`（只读意图入参）按需引入。
- **P4b-3（拆分两个子增量，勿半接通）**：
  - **P4b-3a**：`__intent__` 可选协议方法运行时发现 + 装配改写合并闭环。
  - **P4b-3b**：`stream_call`/`stream_channel` 统一消费 LLMCallable（llm 类流式装配语义
    设计 + 行为经统一装配入口；字符串形态消费方迁移面评估后处理）。
- **P4d 预留（不在 P4b-3 落地）**：`__retry__` 可选协议方法——P1 §2.2 契约已定（重试
  策略声明 / 快照策略 / hint，决策 5 输入）；装配消费与 P4d retry 高阶化一并落地，避免
  零消费者死代码（半接通）。发现机制与 `__intent__` 同一 `lookup_method` 通道，P4d 复用。
- **`IbLLMCallAssemblyCtx` 按需引入**：`__intent__` 直接收意图 dict、`__llm_call__` 返回
  配置 dict——当前无消费者需要读"只读上下文"，**不引入**（避免无消费者空壳对象）；
  P4d `__retry__` 若需上下文再引入（§2.2 已定形态）。

### P4b-3a 设计定稿：`__intent__` 可选协议方法

- **契约（用户语言层）**：`func __intent__(self, dict intents) -> dict`。
  - 入参：`{"active": [str], "global": [str], "merged": [str]}`——装配时消解的意图三层
    （与 `LLMCallRequest.intents` 对齐；active=活跃一次性意图、global=全局意图、
    merged=合并消解结果）。
  - 返回：dict，键为三层任意子集；存在的键**替换**对应层（消解/增删/重排），缺失的键
    **保持**原层（合并语义，镜像"装配 dict 基础上扩展 `__intent__` 结果合并"）。
  - 返回非 dict / 层值非 str 列表 / 参数数非 1 → fail-fast TypeError（契约违约显式暴露）。
- **发现机制**：`assemble_llm_callable_request_cps` 内 `ib_class.lookup_method("__intent__")`
  ——receive 分派同源虚表查找（非 getattr 能力探测）；未声明 → 意图原样透传（行为默认
  透传，P1 §2.2）；声明了非用户函数方法 → fail-fast。
- **调用机制**：经 `UserFunctionCall` CPS 调用（与 `__llm_call__` 同机制——避免同步
  receive 的 CPS 分裂，§2.3）。
- **合并点**：`_resolve_llm_callable_intents_cps` 之后、构造 `LLMCallRequest` 之前。
- **影响面**：单调用 `invoke_llm_callable_cps` 与 `run_batch` 逐项（共用统一装配入口）
  自动继承；行为值路径零变化（行为不走统一装配入口）。

## 五、验证门

- 判别：用户 llm 类经统一入口 → mock provider 收到其 ctx 装配的 user_prompt；
  行为经统一入口 == 直接路径（LLMCallRequest 等价）。
- 全量 pytest 零回归 + 本地 commit；低风险可 merge unsafe-vibe-dev（用户授权）。

## 六、用户侧蓝图（P4b-2a 示例，llm 可调用类用户写法）

```ibci
# 用户定义具名 llm 可调用类（替代 llm 函数）
class Translator:
    # 用户 `__llm_call__` 返回装配配置 dict → 内核映射为 LLMCallRequest
    func __llm_call__(self) -> dict:
        str prompt = "将「" + $self.text + "」翻译为" + self.target_lang
        return {
            "user_prompt": prompt,
            "output_hint": "只输出译文，不要解释",
        }

    str text = ""
    str target_lang = "英语"

Translator tr = Translator()
tr.text = "hello"
# 经 run_batch / stream（P4b-2b）或统一执行入口消费 tr（LLMCallable 实例）
```

