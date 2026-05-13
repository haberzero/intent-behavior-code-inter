# PENDING_TASKS — 阻塞 / 待前置任务

> 本文档**只**记录有明确前置条件、暂不能开工的事项；其余非阻塞低优先级想法不在此处维护。
> 当前最紧要项见 `docs/NEXT_STEPS.md`；已完成事项见 `docs/COMPLETED.md`。
>
> **最后更新**：2026-05-13（测试体系契约化完成）

---

## 一、llmexcept 相关后续（PT-1.x）— 已全部完成

> PT-1.1~PT-1.3 已于 2026-05-12 完成，详见 `docs/COMPLETED.md`。

## 二、NS-2（intent OOP 化收口）相关 — 已全部完成

> PT-2.1 / PT-2.2 已于 2026-05-12 完成，详见 `docs/COMPLETED.md`。

---

## 三、待 VM 信号 / 中断 / 异步机制（L3 协程）成熟后才能继续

### PT-3.1　host.run_isolated() 返回值改进 [VISION]
### PT-3.2　ReceiveMode 枚举演进 [VISION]

---

## 四、语言级语义/语法收尾（暂搁置；基于真实代码事实）

> 本节三项均经过事实核查。每项均给出"现阶段真实代码状态 + 未来演进思路"，确保文档不误导后续开发者。

### PT-4.1　Enum 类型系统的"非 str 成员"与迭代/序数能力 [VISION]

**现阶段真实代码状态**

- 公理：`core/kernel/axioms/primitives.py:1071-1164` 的 `EnumAxiom`。
  - `has_from_prompt_cap = True` / `has_output_hint_cap = True` / `has_converter_cap = True`。
  - `_get_enum_index_map(spec)` 遍历 `spec.members`，**过滤掉 `_` 开头字段与内建方法名**后建立 `{name → name}` 映射；映射本身**不携带成员声明类型**——它把成员"名字本身"当作字符串值返回给 LLM。
  - `can_convert_from(src) == (src == "str")`：只允许 `(MyEnum)str_var` 显式 cast；`(MyEnum)int_var` 不被接受（编译期未启用时仅运行期路径生效）。
  - `from_prompt(...)` 把 LLM 返回值大写化后在 index 中查表，命中即返回 `val_str`（仍是字符串）；未命中返回 `(False, retry_hint)` 走 llmexcept 重试。
  - `__outputhint_prompt__` 仅列出成员名，**不附带底层值**。
- 运行时：`core/runtime/objects/enum.py` 的 `IbEnumValue` / `IbEnum` / `IbEnumAdapter`，所有比较都退化到 `name` 字符串等价（大小写不敏感的 `IbEnumValue.__eq__`、`IbEnum.__eq__`）。`IbEnumAdapter.cast_to("int")` 根据成员**在类成员表中的迭代序号**返回索引（非声明值）。
- 内置类：`core/runtime/bootstrap/builtin_initializer.py:155-204` 注册 `Enum` 基类（继承 `Object`），并把对应 `EnumAxiom` 注入；用户写 `class Color(Enum)` 即继承该基类。
- 字段持有方式：用户写 `str RED = "RED"` 会被通常的类字段路径采纳；`Color.RED` 实际取出的是 `IbString("RED")`（不是 `IbEnumValue`）。"枚举身份"目前**完全由字符串等价模拟**。
- 已知限制（同步登记在 `KNOWN_LIMITS.md §四`）：
  - 仅支持 `str` 成员（写 `int RED = 1` 时 `EnumAxiom.from_prompt` 仍按名字字符串匹配，与底层 `1` 不一致；`Color.RED` 取出是 `IbInteger(1)`，与 `IbEnumValue` 等价路径失联）。
  - 不支持 `for v in Color:` 迭代。
  - 不支持 `len(Color)` 或成员序数显式查询（运行时 `cast_to("int")` 内部走的是迭代序号，但无 IBCI 端入口）。

**未来演进思路（不构成承诺）**

- 给 `EnumAxiom._get_enum_index_map` 升级为携带"成员名 → (声明类型, 值)"的映射；`__outputhint_prompt__` 改为同时呈现名与底层值，from_prompt 同时接受名字或字面值。
- 为 `Enum` 基类注册 `__iter__` / `__len__` / `members()` 方法（在 `builtin_initializer.py` 中按 `EnumAxiom._get_enum_index_map` 派生）。
- 重写 `Color.RED` 访问路径，使其返回 `IbEnumAdapter` 包装而非原始 `IbString`/`IbInteger`，统一身份与比较语义。

**为什么搁置**

- 与 LLM 输出约定耦合：把底层值写入 prompt 提示词需要重新审视用户期望（"reply with RED" vs "reply with 1"）。
- 与"成员迭代"相关的设计需要 VM 端为 `Enum` 类型实例化静态迭代器，触及内置类型注册顺序与 lazy-init 路径。
- 现有 str 成员能力对绝大多数 LLM 集成已足够；先收口语言收尾项（NS-4..NS-7）。

---

### PT-4.2　可调用类实例（`__call__` 协议）的类型推断与副作用一致性 [VISION]

**现阶段真实代码状态**

- 语义识别：`core/compiler/semantic/passes/semantic_analyzer.py:1129-1145, 1804-1825`。
  - `visit_IbCall` 时若 `val_type.members` 含 `__call__`，沿 `registry.resolve_member(func_type, '__call__')` 推断返回类型（line 1813-1825）。
  - 编译期允许"类实例当函数用"，并在 missing `__call__` 时输出建议性错误（"Add 'func __call__(self, ...)' to ..."）。
- 运行时分发：
  - `core/runtime/objects/kernel.py:580-587, 733`：`IbClass.receive("__call__")` 走实例化；`IbObject.receive("__call__")` 通过 vtable 查找用户实例方法。
  - `core/runtime/vm/handlers.py:512`：`vm_handle_IbCall` 在通用路径上对任意 `func` 都派发 `func.receive("__call__", args)`，因此 `obj()` 在 VM 主路径上是受支持的。
- side_table：`core/compiler/semantic/passes/side_table.py:35,45` 通过 `set_callable_instance` / `is_callable_instance` 标注节点是否走 callable-instance 调度路径；`vm/handlers.py:1393-1483` 据此分发。
- 已知限制（同步登记在 `KNOWN_LIMITS.md §三`）："不建议使用"——`fn` 类型推断对 `__call__` 协议与闭包捕获、意图栈副作用的若干交叉路径存在不一致；当可调用类实例内部触发 `@~...~` 或意图栈相关副作用时，类型推断与运行时分发之间的错位可能产生静默错误。
- 真实存在的灰区（核查所得）：
  1. `__call__` 内部 `@~...~` 行为表达式：其意图栈 / 行为执行上下文以"调用现场"为准（NS-3 已校准），但 `__call__` 是实例方法，`self.intent_context` 字段与调用现场 `intent_context` 是否合并需要更显式的合同。
  2. 类内 `__call__` 推断返回类型时：`resolve_member(func_type, '__call__')` 走 `MethodMemberSpec.ret`；若用户写 `auto` 或省略返回类型，目前回落到 `auto`，未与调用站的左值类型协商，可能与"显式返回类型才安全"的 `KNOWN_LIMITS §七`（行为表达式不能直接用于 return）的设计原则相违背。
  3. `is_compatible(fn_callable)` 视角：可调用实例的 spec 是 `TypeKind.CLASS`（其类是 `TypeKind.CLASS`），与 `fn_callable` 公理不在同一兼容轴；写 `fn f = obj`（`obj` 是带 `__call__` 的类实例）的语义未被显式涵盖，主路径有可能落入 `auto` 兜底。

**未来演进思路（不构成承诺）**

- 在 `MethodMemberSpec` 上为 `__call__` 增设"is_callable_proxy"标记，让类型系统对持有此方法的类自动认作 `callable` 子型。
- 显式规定 `__call__` 内 `@~...~` 的 intent_context 合并规则（参考 NS-2c 的 fork-and-replace 思路），并补全测试。
- 评估是否要求 `__call__` 的返回类型必须显式声明（与 NS-2c 对行为表达式的同类约束对齐）。

**为什么搁置**

- 触及类型系统兼容性轴（class ↔ callable 系列），改动面跨 axiom / spec / semantic / vm 四层。
- 用户目前可用"普通方法 + lambda 包装"作为可调用实例的替代方案，规避成本低。

---

### PT-4.3　语言级协程（L3）[VISION]

**现阶段真实代码状态**

- VM 层基础设施：
  - `core/runtime/vm/task.py:34` 的 `ControlSignal(Enum)` 已定义控制流信号类型（break/continue/return/llm_uncertain 等）；`Signal` 类承载信号在帧栈中向上传播。
  - `core/runtime/vm/vm_executor.py` 与 `vm/handlers.py` 已统一走 CPS 风格的 `yield` 调度循环（NS-1 / segments CPS 化），`frame_stack_depth` 已暴露给观测层（`COMPLETED.md` 2026-05-11 NS-1 锚点）。
  - 当前 VM 是单任务调度器：一次 `vm.run(uid)` 起一个根任务，没有挂起/恢复其他任务的能力。
- 语言层面：
  - 没有 `async` / `await` / `yield` / `coroutine` 关键字；`core/compiler/lexer/core_scanner.py:28-51` 的 KEYWORDS 表未含相关 token。
  - 没有"任务对象""协程对象"作为一等公民类型；`callable` 公理及子类（fn_callable / behavior / bound_method）只覆盖同步调用。
  - 现有"并发"语义仅限 `ai.dispatch_eager(...)` 后台线程提交 LLM 请求（`llm_executor.py` 与 `vm/handlers.py:700-725` 的 `dispatched_future` 路径），主调用线程通过 `LLMFuture.get()` / `vm_handle_IbName` 解引用阻塞等待——这是"异步 LLM"而非"协程"。
- 设计文档：`docs/VM_AND_INTERPRETER_DESIGN.md §5.1` 把"L3 信号 / 中断 / 异步"作为远期愿景层；`PENDING_TASKS §三`（PT-3.1 / PT-3.2）已显式声明阻塞条件——这些条目"待 VM 信号 / 中断 / 异步机制（L3 协程）成熟后才能继续"。
- `docs/COMPLETED.md` 历次 NS-x 锚点记录的 CPS 化、`_evaluate_segments` 入帧等改动，**目标是把"递归 visit"全部搬到 VM 帧栈**——这是协程化的前置（统一中断点），但本身并不构成协程语言层面。

**未来演进思路（不构成承诺）**

- 在 VM 层增设多任务调度队列（基于现有 `frame_stack` 的多实例化），允许 `Signal.YIELD` 之类的语义把当前帧切下并把控制权交还给调度器。
- 设计语言层关键字（如 `yield value` 或 IBCI 风格的 `defer` / `await`），需要与现有 `@~...~`、`llmexcept`、`try/except`、`intent_context` 的快照模型仔细对齐——尤其是协程暂停时如何快照意图栈与 llmexcept 帧栈。
- 优先级低：当前 LLM 工作负载下，`dispatch_eager` 已覆盖最主要的"异步等待"需求。

**为什么搁置**

- 牵涉到调度器架构、关键字系统、快照协议三个独立维度的协同变更，单次 PR 难以收口。
- 与 NS-4..NS-7 等语言收尾项相比，缺乏明确的用户需求来源。
- PT-3.1 / PT-3.2 显式以此为前置——只要 L3 不动，它们也不能动。

---

## 五、明确排除的方向

- 不引入静态类型检查器作为解释器前置强依赖。
- 不以牺牲运行时可观测性换取短期性能优化。
- 不为优化同一程序内独立 LLM 调用而创建多 Interpreter（这是 L1 流水线的职责）。
