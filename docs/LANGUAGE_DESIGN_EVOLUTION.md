# IBCI 语言设计体系化演进评估

> 本文是一份**独立的语言设计评估与架构演进研究文档**，不参与当前主线开发。
> 写作基于对 `README.md`、`docs/` 以及 `core/` 内核源码的阅读；未修改任何现有文件。
> 评估范围不包括性能，重点是从编程语言设计、类型理论、工程抽象、内核一致性的角度，判断 IBCI 当前状态与未来体系化方向。

---

## 0. 摘要

IBCI 当前是一个“以 LLM 为中心的领域专用脚本语言”。它的类型系统不是通用语言意义上的完整类型系统，而是一套**小型名义类型系统 + 结构化泛型 + 封闭能力公理 + 显式动态逃生阀**。

从架构层面看，IBCI 已经具备一些非常好的底层地基：

- `TypeRef / TypeDef / TypeAxiom` 三层分离；
- 结构化、可哈希、可序列化的类型引用；
- 内置泛型容器与用户泛型类；
- 显式 `Optional[T]` 空安全；
- `fn[(...) -> (...)]` 结构可调用签名；
- 类型驱动的 LLM 输入输出协议（`__to_prompt__` / `__from_prompt__` / `__outputhint_prompt__`）。

但这些能力目前大多是**封闭、硬编码、散落多层**的。最核心的问题是：

> IBCI 没有把“接口 / 协议 / 类型类”作为内核的一等公民，而是用固定 dunder、固定公理 flag、固定插件 vtable 在多个层面各自实现了一遍。

因此，未来的体系化演进不应只增加某个语法，而应当把“协议”抽象下沉到 `TypeRef / TypeDef / TypeAxiom / SpecRegistry / 编译器 / 运行时 / 插件 / 意图 / LLM 函数` 的每一层，形成统一的机制。

---

## 1. 当前架构事实（基于内核代码）

### 1.1 类型系统三层：好的地基，但“行为”仍是封闭集合

- `core/kernel/spec/type_ref.py` 提供不可变、递归、可哈希的 `TypeRef`；
- `core/kernel/spec/base.py` 的 `TypeDef` 是统一的纯数据描述；
- `core/kernel/axioms/protocols.py` 的 `TypeAxiom` 是行为分派层。

但 `TypeAxiom` 目前只有一组**固定能力 flag**：

```python
has_call_cap
has_iter_cap
has_subscript_cap
has_operator_cap
has_converter_cap
has_parser_cap
has_from_prompt_cap
has_output_hint_cap
has_llm_call_cap
```

这意味着：语言能识别哪些“能力”，在写内核时就已经被枚举死了。用户不能声明一种新能力，也不能说“这个类型满足某个用户定义的协议”。

### 1.2 Prompt 协议：典型的“写死了逻辑的魔法操作”

当前 prompt 相关协议分散在多个位置，彼此靠**方法名字符串**耦合：

- `core/kernel/axioms/prompt_protocol.py` 硬编码了四个协议方法：
  `__to_prompt__`、`__from_prompt__`、`__outputhint_prompt__`、`__validate_prompt__`；
- `core/kernel/axioms/protocols.py` 的 `TypeAxiom` 中有对应的 `has_from_prompt_cap` / `has_output_hint_cap`；
- `core/compiler/semantic/passes/_declaration_visitors.py` 中有 `PROMPT_PROTOCOL_SIGNATURE_FREE` / `_OVERRIDE_SIGNATURE_FREE` 硬编码集合；
- `core/runtime/interpreter/llm_executor/_prompt.py` 中 `_obj_to_prompt_str()` / `_obj_to_payload()` 通过 `receive('__to_prompt__')` / `receive('__payload_prompt__')` 分派；
- `core/runtime/objects/intent.py` 中 `_intent_segment_to_prompt()` 又单独实现了一遍 `__to_prompt__` 回退；
- `core/runtime/interpreter/llm_executor/_prompt_assembly.py` 用固定顺序拼接“输出纪律 → 输出格式 → 意图”。

结论：**同一个“协议”概念，在编译期、运行期、意图系统、LLM 装配里被多次手工实现。** 这不是“接口化”，而是“魔法方法 + 多处复制”。

### 1.3 意图系统：字符串栈，而不是一等值栈

- `IbIntent` 本质是 `content: str` + 可选的 segments；
- `IbIntentContext` 维护持久栈、smear、override、global；
- `IntentResolver` 最终把意图解析成 `List[str]`。

当前意图可以包含 `$var` / 表达式段，但这仍然是在“求值后转成字符串”的层面。它没有：

- 把“一个用户定义对象”作为意图值；
- 把“一个函数实例 / behavior / llm function”作为意图值；
- 让意图渲染与普通 prompt 渲染共用同一套协议；
- 让用户自定义类型通过接口控制自己在意图中的呈现。

另外，`core/runtime/objects/kernel/_helpers.py` 中通过“参数类型名是不是 `intent_context`”以及“对象有没有 `_ctx` 字段”来触发意图上下文激活，这是一种典型的魔法字段判断，而不是协议/接口判断。

### 1.4 LLM 函数与普通函数：两条平行执行路径

- `IbUserFunction` 与 `IbLLMFunction` 都是 `IbFunction` 子类；
- 但执行路径分别是 `_vm_call_user_function` 与 `_vm_invoke_llm_function`；
- 编译期也有 `IbFunctionDef` 与 `IbLLMFunctionDef` 两个 AST 节点；
- 类型层面都通过 `fn` 可调用，但缺少一个统一的“Callable 协议”来描述：
  - 普通函数：确定性执行；
  - LLM 函数：有 prompt 模板、返回类型解析、retry hint；
  - behavior：即时或延迟 LLM 调用；
  - snapshot/lambda：捕获策略不同。

这种平行结构在短期内清晰，但长期会阻碍“把函数作为一等值放入意图、放入数据结构、被协议约束”等需求。

### 1.5 OOP：有类、继承、dunder，但没有接口/抽象/封装

- 有单继承、`super()`、泛型类、自动构造器、运算符重载；
- 没有用户可定义的接口 / trait / type class；
- 没有抽象类 / 抽象方法；
- 没有访问控制 / 封装；
- 枚举成员是底层值，不是真正的枚举实例；
- 方法覆写检查存在，但偏宽松。

### 1.6 泛型：有类泛型，但没有泛型约束和泛型函数

- 支持 `class Box[T]`；
- 但不支持 `T: Bound`；
- 不支持 `func map[T, U](...)` 这类泛型函数；
- 类型推断不是约束求解，`auto` 只是首次赋值锁定。

---

## 2. 演进原则

用户给出的原则应当成为所有架构决策的过滤器：

1. **任何机制不能是孤立的**：新增协议/接口/类型类，必须同时体现在类型表示、编译器、运行时、序列化、动态宿主、插件、意图、LLM 装配、诊断、测试中。
2. **设计语言必须统一**：不能让“dunder 协议是一套、插件 vtable 是一套、意图渲染是一套、LLM 函数是一套”。
3. **长期稳定可控**：协议解析、实现冲突、覆盖规则、序列化格式都需要在第一天定义清楚，否则后期会变成兼容性沼泽。
4. **从底层到顶层**：如果引入 interface/type class，它不能只是语法糖，而应成为 `TypeRef / TypeDef / TypeAxiom / SpecRegistry` 的正式成员。
5. **所有语法都不是孤立的**：例如“意图注释”与“函数值”、“用户类”、“LLM 函数”应当通过同一套可渲染/可调用/可约束机制正交组合。

---

## 3. 架构级演进方向

### 3.1 将 Protocol / Interface / TypeClass 提升为内核一等公民

建议在类型系统中引入正式的 `PROTOCOL` / `INTERFACE` 种类，而不是继续依赖固定 dunder。

具体来说：

- 在 `TypeKind` 中新增 `PROTOCOL`；
- 在 `TypeDef` 中增加协议方法签名、父协议、关联类型（如果需要）等字段；
- 在 `TypeRef` 中允许协议名作为类型头；
- 在 `SpecRegistry` 中维护“类型 → 满足的协议集合”；
- 在运行时 `IbClass` / `IbObject` 中增加协议方法表，而不是只靠 `lookup_method('__to_prompt__')`。

这样，现有 dunder 可以重新定义为**内建协议的内置实现**，例如：

```text
protocol Promptable:
    func __to_prompt__() -> str

protocol FromPrompt:
    func __from_prompt__(str raw) -> tuple[bool, any]

protocol OutputHint:
    func __outputhint_prompt__() -> str
```

用户以后可以写：

```text
protocol Serializable:
    func to_dict() -> dict

class Point implements Serializable:
    ...
```

这不是简单加一个关键字，而是让“协议”成为编译期和运行期都能查询、约束、序列化的一等实体。

### 3.2 把能力公理从固定 flag 改为协议满足关系

当前 `TypeAxiom` 的 `has_*_cap` 是封闭集合。演进方向是：

- `TypeAxiom` 保留为“类型行为的实现载体”；
- 但能力查询从“有没有某个 flag”变成“是否实现了某个协议”；
- `SpecRegistry` 提供 `get_protocol_cap(spec, protocol)`；
- 编译器在检查 `T: SomeProtocol` 时，通过协议注册表查询；
- 运行时分派通过协议方法表，而不是散落的 `receive('__xxx__')`。

这会把“Prompt 协议”“可调用协议”“可迭代协议”“运算符协议”统一成同一套机制。

### 3.3 Prompt 协议接口化，并统一 Prompt 装配流水线

当前 prompt 相关逻辑分散在：

- `_prompt.py`（对象到文本/多模态）；
- `_prompt_assembly.py`（系统提示词段落）；
- `_llm_function.py`（LLM 函数）；
- `_behavior.py`（行为表达式）；
- `intent.py`（意图渲染）。

建议：

1. 定义统一的 `PromptContributor` / `PromptPart` 协议；
2. 所有能向 prompt 提供内容的实体（类型、意图、函数、输出约束、retry hint）都实现该协议；
3. 提示词装配不再是“固定字符串拼接”，而是“按协议收集有序 PromptPart 列表”；
4. 新增一种上下文来源时，不需要修改核心装配代码，只需要注册新的 `PromptContributor`。

这样 `__to_prompt__`、`__payload_prompt__`、意图、`__llmretry__`、`__outputhint_prompt__` 就不再是魔法，而是统一协议的不同实现。

### 3.4 泛型约束与泛型函数

在协议成为一等公民后，下一步是让泛型参数可以被约束：

```text
func max[T: Comparable](T a, T b) -> T:
    ...
```

这需要：

- 泛型参数声明支持 `T: ProtocolName`；
- 编译期检查实参类型是否满足协议；
- 特化时把 `T` 替换为具体类型，并继续沿用现有 `TypeRef.substitute`；
- 支持泛型函数（不限于泛型类）；
- 类型推断可以先用“轻量约束检查”，不必一开始就上完整 Hindley-Milner。

### 3.5 意图系统正交化：从字符串栈到 Promptable 值栈

建议把意图从“字符串栈”升级为“可渲染值栈”：

- `IbIntent` 的 `content` 不再只是 `str`，而可以是任意实现了 `Promptable` 的值；
- 意图栈保存的是“意图对象”，而不是已经渲染好的字符串；
- `IntentResolver` 在最终渲染时调用统一协议；
- 用户自定义类可以作为意图值；
- 函数实例、behavior、LLM function 也可以作为意图值，由它们自己决定如何呈现。

例如：

```text
@+ my_policy_object          # 用户类实例作为意图
@+ my_llm_function           # 函数实例作为意图
```

语义上可以定义为：

- 普通对象：调用 `__to_prompt__` 渲染；
- 函数 / behavior：默认渲染其名称与签名，或者由用户通过协议自定义；
- 未来甚至可以定义“调用式意图”：在渲染时调用函数得到动态上下文。

但要注意：**调用式意图会引入副作用和执行时机问题**，必须与现有 CPS、snapshot、llmexcept、并发调度统一设计，不能作为孤立语法加入。

### 3.6 函数实例与意图 / LLM 上下文的一等交互

当前函数实例（`IbUserFunction` / `IbLLMFunction` / `IbBehavior` / `IbFnCallable`）没有统一的“prompt 呈现”协议。建议：

- 为所有可调用对象提供默认 `__to_prompt__` 实现，输出名称、参数签名、返回类型等；
- 允许用户通过接口/协议自定义函数在 LLM 上下文中的呈现；
- 允许函数作为意图值、作为 prompt 段、作为数据结构字段；
- 在类型层面把“可调用”和“可提示”组合起来，例如 `fn[(...) -> T] & Promptable`。

这会让“把函数放进意图”不是魔法，而是协议组合的自然结果。

### 3.7 OOP 抽象补全

在协议之上，OOP 可以自然补全：

- 抽象类 / 抽象方法可以通过“必须实现某协议”表达；
- 接口 / trait 可以通过 `PROTOCOL` 表达；
- 多实现可以通过“一个类型满足多个协议”表达，而不需要多继承；
- 访问控制可以作为独立但正交的机制加入，不与协议耦合；
- 枚举可以升级为真正的代数数据类型，成员是实例，可携带方法。

### 3.8 模块 / 插件协议化

当前插件用 `_spec.py` + vtable 声明接口，这套机制可以纳入统一协议体系：

- 插件模块的公开接口可以声明为协议；
- 插件实现类可以声明 `implements SomeProtocol`；
- `HostInterface` / `ModuleLoader` 通过协议注册表查询能力，而不是靠 `hasattr` / 固定方法名；
- 这会让“语言内用户协议”和“插件扩展协议”使用同一套机制。

---

## 4. 阶段性落地路线

### Phase 0：固化现有协议，不改变用户语法

- 把现有 dunder 协议在内部建模为“内建协议声明”；
- 建立 `ProtocolRegistry` 作为唯一权威源；
- 让编译器、运行时的协议查询都走 `ProtocolRegistry`；
- 消除 `_obj_to_prompt_str`、`_intent_segment_to_prompt`、`_prompt_assembly` 中的重复魔法字符串。

目标：不引入新语法，先统一内核机制，验证协议抽象能承载现有功能。

### Phase 1：用户可定义协议

- 新增 `protocol` 语法；
- 支持 `class C implements P`；
- 支持协议继承；
- 编译期方法签名检查；
- 运行时协议方法表；
- 序列化 / 动态宿主 / 插件隔离中支持协议信息。

### Phase 2：泛型约束与泛型函数

- 支持 `T: SomeProtocol`；
- 支持泛型函数；
- 编译器在特化时检查协议满足；
- 类型推断扩展为“轻量约束检查”。

### Phase 3：Prompt / Intent / LLM Function 统一

- 所有 prompt 来源实现 `PromptContributor`；
- 意图栈改为可渲染值栈；
- 函数实例可作为意图值；
- LLM 函数与普通函数统一到同一 Callable 协议族；
- `llmexcept`、snapshot、并发调度与新的意图值语义协同。

### Phase 4：代数数据类型 / 模式匹配（可选）

如果 IBCI 要处理更复杂的 LLM 输出建模，可以引入：

- `enum` 升级为真正的 ADT；
- `Result[T, E]` / 联合类型；
- `match` 结构模式匹配。

这些应建立在协议和泛型之上，而不是孤立语法。

---

## 5. 风险与稳定性控制

1. **协议一致性**：必须定义“一个类型是否允许实现多个协议”“协议实现是否允许重复”“父协议与子协议的关系”等规则。
2. **序列化兼容**：协议信息会进入 `TypeDef` / artifact，必须设计向后兼容的序列化格式。
3. **动态宿主隔离**：不同引擎的协议注册表必须隔离，避免协议身份跨引擎串扰。
4. **性能不是目标，但复杂度要可控**：协议查找不能变成无约束的反射，应有明确的注册与解析路径。
5. **魔法字段清理**：如 `_ctx` 自动激活、`__to_prompt__` 字符串分派等，应逐步被协议查询替代。
6. **文档与测试同步**：协议是跨层机制，必须同步更新 `docs/architecture/03_type_system.md`、`docs/KNOWN_LIMITS.md`、诊断码、测试矩阵。

---

## 6. 结论

IBCI 已经有一个比大多数脚本语言更认真的类型地基，尤其是：

- 结构化类型表示；
- 显式空安全；
- 可调用签名；
- 类型驱动的 LLM 合约。

但从“体系化演进”角度看，它目前最大的瓶颈不是缺少某个语法糖，而是**缺少一个贯穿内核的协议/接口/类型类抽象**。

如果 IBCI 的目标继续是“实验性 LLM 胶水语言”，当前架构可以继续演进；但如果目标是“实用、工程化、现代化”，那么最值得投入的方向是：

> 把协议作为内核一等公民，让 Prompt 协议、意图、LLM 函数、泛型约束、插件扩展全部收敛到同一套协议机制上。

这不是一次语法更新，而是一次从 `TypeRef / TypeDef / TypeAxiom / SpecRegistry` 到编译器、运行时、插件、意图、LLM 装配的体系化重构。

---

## 附：`exp/protocol-kernel` 分支实验进度

> 本节记录实际分支推进情况，随实验更新。

### 已完成（第一轮协议内核化）

- 新增 `ProtocolDef` / `ProtocolRegistry`，作为内核协议身份的唯一权威。
- **用户协议语法已可用**：`protocol Name:` 声明、`class Foo implements Bar:` 实现、
  `protocol Child(Parent):` 继承，以及编译期协议方法完整性检查。
- `SpecRegistry` 新增 `satisfies_protocol()`，支持内建协议与用户注册协议的结构化满足判断。
- `TypeKind` 新增 `PROTOCOL`，为未来协议类型实体预留位置。
- 新增统一 `PromptRenderer`，LLM executor 与 intent 系统均委托到该渲染器。
- 新增 `PromptPart` / `assemble_prompt_parts` / `build_prompt_parts`，统一 behavior prompt 的段落装配模型。
- 编译器与运行时的 LLM parse/output-hint 能力查询开始走协议注册表。
- 新增协议注册表、PromptRenderer、PromptAssembly 测试。

### 尚未开始（后续阶段）

- 用户可写 `protocol` / `implements` 语法。
- 泛型约束 `T: SomeProtocol` 与泛型函数。
- 意图值栈与函数型意图。
- LLM 函数与普通函数的执行路径完全统一。
- 协议注册表的序列化 / 动态宿主隔离 / 诊断码。
