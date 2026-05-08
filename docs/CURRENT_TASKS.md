# 当前任务控制文档

> 本文档描述类型系统主线（M1–M5）收口后的下一阶段工作。  
> **最后更新**：2026-05-08（类型系统五大里程碑全部完成；测试基线 1180 passed）
>
> **背景文档**：  
> - 类型系统设计：`docs/TYPE_SYSTEM_DESIGN.md`  
> - VM/解释器设计：`docs/VM_INTERPRETER_DESIGN.md`  
> - 意图系统设计：`docs/INTENT_SYSTEM_DESIGN.md`  
> - fn/lambda/snapshot 语法决策：`docs/FN_LAMBDA_SYNTAX_REDESIGN.md`  
> - 低优先级挂起任务：`docs/PENDING_TASKS.md`、`docs/PENDING_TASKS_VM.md`

---

## 一、callable-instance 术语与代码清洗（P1）

### 背景

类型系统 M3 已将 `TypeKind.DEFERRED`/`TypeKind.BEHAVIOR` 统一为 `TypeKind.CALLABLE_INSTANCE`，并完成全局重命名（`deferred_mode → capture_mode`、`is_deferred → is_callable_instance` 等）。然而，**运行时值层**（出于 M4 兼容性考虑）仍保留了旧名称作为包装层：

- `IbDeferred`（`core/runtime/objects/builtins.py`）仍存在，注解中仍使用"延迟执行""deferred"等旧术语
- 公理注册名 `"deferred"` 仍是 registry 中的字符串 key（`builtin_initializer.py:94`）
- `vm/handlers.py` 中的 `_vm_call_deferred()` 函数名和注释仍使用 deferred 语言
- `IbBehavior` 文档注释仍称"IbDeferred 延迟的是普通表达式求值"——这个说法是错误的

### 正确的语义表述

**lambda/snapshot 不是"延迟求值（deferred）"，而是"可调用实例（callable-instance）"**，其含义更接近于：

> 将一个表达式包装成一个可调用实例，该实例在被调用时才执行这个表达式，且在包装时明确了输入和输出类型结构。

它们与普通函数（`func`）在地位上完全对等，区别在于：
- **lambda**：引用捕获（读最新值）+ 调用时使用当前生效意图栈
- **snapshot**：值拷贝捕获（冻结定义时值）+ 使用创建时冻结的意图栈快照

"延迟求值"是早期技术路线的术语，在类型层面已被统一废除。当前代码中残留的 "deferred" 字符串主要作为序列化兼容标识符和运行时包装类名，应当在可以安全重命名的地方逐步清理。

### 工作项

1. **代码注释清洗**（低风险，优先推进）
   - `core/runtime/objects/builtins.py`：`IbDeferred` 类注释从"延迟执行"改为"callable-instance（lambda/snapshot）"，删除"deferred family"等旧表述
   - `core/runtime/objects/builtins.py`：`IbBehavior` 注释中"IbDeferred 延迟的是普通表达式求值"改为"IbDeferred 是 lambda/snapshot 表达式的 callable-instance"
   - `core/runtime/vm/handlers.py`：`_vm_call_deferred()` 函数名和注释审查，内部注释从"延迟执行"改为"callable-instance 执行"

2. **序列化字符串兼容性评估**（需要仔细评估，不急）
   - `axiom_name = "deferred"` 在序列化协议中是线格式标识符，若已有存量 artifact，不可轻易改名
   - 评估是否需要添加 `"callable_instance"` 作为新格式并保留 `"deferred"` 作为旧格式兼容读取
   - **当前结论**：暂不改变序列化格式，只清理注释和文档

3. **`create_deferred()` 工厂方法**
   - `RuntimeObjectFactory.create_deferred()` / `interfaces.py` 中的协议
   - 评估是否需要添加 `create_callable_instance()` 别名，或直接重命名
   - 考虑对现有调用点的影响范围

---

## 二、fn 高阶函数类型标注能力补全（P2）

### 背景

M3 完成后，类型系统已具备完整的 TypeRef 结构化表达能力（泛型、递归、跨模块）。`fn[(...)->(...)]` 语法已落地（D3，2026-04-29），但当前在以下场景中仍存在表达力不足：

1. **高阶函数的返回类型推导**：当函数返回 `fn[...]` 类型的 callable 时，调用者侧的类型推导可能退化为 `auto` 或 `void`
2. **嵌套 fn 签名约束**：`fn[(fn[(int)->int]) -> int]`（接受一个 int->int 函数的高阶函数）这类嵌套签名的解析和匹配是否完整
3. **fn 作为 lambda/snapshot 的类型覆盖标注**：`fn[(int)->str] f = lambda(int x) -> str: ...` 场景下类型一致性检查是否完整

### 关联的类型系统背景

类型系统 M1–M5 已完成以下基础：
- `TypeRef` 支持递归泛型（可以表达 `fn[(fn[(int)->int])->int]`）
- `TypeKind.CALLABLE_INSTANCE` 统一分发
- `TypeAxiom.has_call_cap` 统一调用协议
- `SpecRegistry.is_assignable()` 支持结构化比较

但是否已正确贯穿到以下环节，需要专项测试确认：
- 语义分析器（`semantic_analyzer.py`）在 fn 变量声明时的类型推导
- 函数调用点参数类型检查（`fn[...] predicate` 参数与实际传入 callable 的结构匹配）
- 返回值类型在调用链中的传播

### 工作项

1. **fn 高阶函数端到端测试补充**
   - 覆盖场景：(a) 嵌套签名、(b) 高阶函数返回类型传播、(c) 泛型 callable 参数约束
   - 目标：发现当前推导失败或静默退化为 `auto`/`void` 的场景

2. **语义分析器 fn 类型推导修复**（根据测试结果）
   - `semantic_analyzer.py` 中的 fn 变量声明类型推导路径
   - `call_handler.py` 或等价位置中的 callable 参数结构匹配

3. **文档更新**
   - 在 `docs/TYPE_SYSTEM_DESIGN.md §四` 补充"当前局限"消除记录
   - 在 `docs/FN_LAMBDA_SYNTAX_REDESIGN.md` 增加测试覆盖状态说明

---

## 三、llm_uncertain 与字符串真值检查（P2）

### 背景

`IbLLMUncertain` 在代码库中是正确实现了布尔语义的：
- `to_bool = lambda self: 0`（始终为 falsy）——通过 `builtin_initializer.py:258`
- `vm_handle_IbIf`/`IbWhile`/`IbFor` 通过 `ec.is_truthy(cond)` 调用到 `value.receive('to_bool', [])` 路径，会正确检测 llm_uncertain 为 false

### 字符串真值检查现状（已确认正常）

```python
# builtin_initializer.py:298
_reg_native(string_class, 'to_bool', lambda self: len(self.value) > 0)
```

字符串空值检查走 `to_bool`→`len(value) > 0` 路径，已注册在 vtable 中，`is_truthy()` 可正确识别空字符串为 falsy。这部分**已随类型系统演进保持了正确性**。

### 已知问题：`str + llm_uncertain` 兼容拼接

在 `IbString.__add__()` 中存在一个已知的技术债务（`builtins.py:322-330`）：

```python
def __add__(self, other: IbObject) -> Any:
    # TODO(future): 当 IBCI 完善 try/except 机制后，此处对 llm_uncertain 的
    # 隐式拼接将被禁止，并改由统一的不确定性异常处理路径接管。
    # 现阶段为避免静默崩溃打断常见的 `"prefix: " + str_var` 调试路径，
    # 暂时允许将 Uncertain 视作 "uncertain" 字符串参与拼接。
    if other.ib_class.name == "llm_uncertain":
        return self.value + "uncertain"
    ...
```

**现状**：用户自定义异常体系（try/except）已于 2026-05-06 落地，TODO 注释中提到的前置条件已满足。`str + llm_uncertain` 的隐式拼接现在可以改为显式错误。

**当前行为的问题**：
- `"prefix: " + uncertain_var` 静默生成 `"prefix: uncertain"` 字符串，可能隐藏 LLM 不确定性问题
- 正确行为应该是：抛出 `TypeError`（或 `LLMUncertaintyError`），让用户用 `llmexcept` 显式处理

### 工作项

1. **移除 `str + llm_uncertain` 兼容拼接**（P2）
   - `IbString.__add__()` 中的 `ib_class.name == "llm_uncertain"` 分支改为抛出类型错误
   - 新错误消息应明确提示用户使用 `llmexcept` 处理 LLM 不确定性
   - 同步检查是否有其他运算符（`str * llm_uncertain` 等）有类似兼容逻辑

2. **llm_uncertain 在比较操作中的行为确认**
   - `handlers.py:207-215` 中的 `isinstance(right, IbLLMUncertain)` 检查是 `== / !=` 比较的特殊处理
   - 确认：`uncertain_var == "something"` 应返回 False，`uncertain_var != "something"` 应返回 True
   - 这部分当前已实现，确认是否有其他比较运算符需要同样处理

3. **llm_uncertain 类型标注和文档**
   - `IbLLMUncertain` 目前在类型系统中有独立的 `llm_uncertain` 公理，但 `TypeKind` 中没有专门的枚举值——它走 `TypeKind.BUILTIN` 或 `TypeKind.DYNAMIC` 路径？需确认
   - 在 `docs/TYPE_SYSTEM_DESIGN.md` 中补充 `llm_uncertain` 类型的正式设计说明

---

## 四、意图注释系统后续工作（P3）

### 背景

意图注释系统已完整落地（见 `docs/INTENT_SYSTEM_DESIGN.md`），以下为仍需推进的后续工作：

### 4.1 intent_context 完整 OOP 化（来自 PENDING_TASKS.md §四）

当前 `intent_context` MVP 已可用（`§六` 已落地），但以下场景仍不支持：
- **作为函数参数类型**：`func foo(intent_context ctx)`——接受意图上下文实例作为参数
- **作为函数返回类型**：`func get_ctx() -> intent_context`
- **更复杂的意图操作**：`merge`（合并两个意图上下文）、条件意图（根据变量动态决定意图内容）

### 4.2 意图标签解析迁移到 Lexer（来自 PENDING_TASKS.md §9.1）

当前意图标签（`@+ "text" #tag`）解析在 Parser 层，违反分层原则，应迁移到 Lexer。

### 4.3 Intent Stack 不可变性约束（来自 PENDING_TASKS.md §2.1）

`llmexcept` 快照隔离中，编译期 read-only 约束尚未落地：用户在 llmexcept body 内写入外部变量时应产生编译期 `SEM_xxx` 错误，而当前只有运行时回滚保护。

---

## 五、VM 调度系统后续工作（P3）

### 背景

VM CPS 调度系统（M3a–M3d）和 LLM 并发调度（M5a–M5c）全部完成。以下为中长期方向（见 `docs/PENDING_TASKS_VM.md`）：

### 5.1 ImmutableArtifact `__deepcopy__`（来自 PENDING_TASKS.md §6.1）

序列化反序列化路径中，`ImmutableArtifact` 缺少 `__deepcopy__` 实现，可能在多 Interpreter 并发场景下引发意外共享。

### 5.2 子解释器变量深拷贝隔离（来自 PENDING_TASKS.md §5.2）

`collect(handle)` 返回的值字典目前直接从 `ScopeImpl` 提取，复杂对象（list/dict）可能与子 Interpreter 运行时对象共享引用，应在 `collect()` 时做一次深拷贝。

### 5.3 VM 信号/中断/异步机制（远期目标）

当前 VM 不支持：
- 外部中断（用户 Ctrl-C 映射到 VM 层）
- 异步任务（async/await 语义）
- VM 级别的超时控制

---

## 六、行为描述语句（behavior expression）后续工作（P3）

### 背景

`@~...~` 行为描述语句和 `IbBehaviorExpr` 已完整落地。以下为改进方向：

### 6.1 行为描述中的类型约束提示

当前 `@~...~` 的 `$var` 插值只做符号解析，不传递类型信息到 LLM 提示词中。可以在 prompt 构建时注入变量的类型注释，提升 LLM 理解精度。

### 6.2 behavior 意图栈与 fn HOF 的交叉场景

当 behavior 表达式被包装为 callable-instance（`fn f = lambda: @~...~`），且该 callable 作为高阶函数参数传递时，意图栈的 lambda/snapshot 语义是否正确传递需要专项验证：
- `lambda` 模式：调用 `f()` 时应使用**调用点**的意图栈
- `snapshot` 模式：应使用 `f` **创建时**冻结的意图栈
- 具体实现见 `handlers.py` 中 `_vm_call_deferred()` 的意图栈传递逻辑

---

## 七、当前阶段任务优先级总览

| 优先级 | 任务 | 状态 |
|--------|------|------|
| P1 | callable-instance 注释与代码清洗 | 待开工 |
| P2 | fn 高阶函数类型标注端到端测试补充 | 待开工 |
| P2 | str + llm_uncertain 兼容拼接移除 | 待开工 |
| P2 | llm_uncertain 在类型系统中的正式定位确认 | 待开工 |
| P3 | intent_context 完整 OOP 化 | 挂起（见 PENDING_TASKS §四）|
| P3 | ImmutableArtifact deepcopy | 挂起（见 PENDING_TASKS §6.1）|
| P3 | 意图标签解析迁移到 Lexer | 挂起（见 PENDING_TASKS §9.1）|
| P3 | behavior + HOF 意图栈交叉场景验证 | 挂起 |
