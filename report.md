# IBC-Inter 工程状态报告

> 撰写时间：2026-04-16  
> 测试状态：432 / 432 PASSED（0 failures）  
> 代码规模：约 201 个 Python 源文件，核心引擎约 5400+ 行  

---

## 一、工程概述

IBC-Inter（Intent-Behavior-Code-Inter）是一个**意图驱动的静态强类型编程语言**运行时，用 Python 实现。其核心设计哲学是：将大型语言模型（LLM）的非确定性能力以一等公民的方式嵌入到有类型约束的程序控制流中，同时保留传统编程语言的可预测性与可测试性。

### 1.1 语言特性一览

| 特性 | 说明 |
|------|------|
| 静态强类型 | 编译期类型检查，支持 `int/float/bool/str/list/dict/tuple/any/callable` |
| 行为描述行 | `@~ ... ~` 语法触发 LLM 调用，内联于代码流 |
| 意图栈 | `@ 意图文本` 注解驱动 LLM 上下文注入，支持 `@+`（压栈）`@-`（弹栈）`@!`（排他临时意图） |
| LLM 异常处理 | `llmexcept:` 块捕获 LLM 不确定返回，`retry "提示"` 语法重试 |
| 类与枚举 | `class`/`enum` 声明，支持继承、方法、字段 |
| 插件系统 | 两级插件（非侵入式/核心级），通过 `import ai/net/json/...` 使用 |
| LLM 函数 | `llm funcname ... llmend` 定义 LLM 驱动的函数，支持结构化 sys/user/retry prompt |

---

## 二、架构层次与目录结构

```
intent-behavior-code-inter/
├── core/                         # 核心引擎
│   ├── base/                     # 基础设施（诊断、枚举、序列化）
│   ├── compiler/                 # 编译流水线
│   │   ├── lexer/                # 词法分析器
│   │   ├── parser/               # 语法分析器（递归下降 + Pratt）
│   │   ├── semantic/             # 语义分析（多 Pass）
│   │   ├── serialization/        # AST 序列化（JSON 格式）
│   │   └── scheduler.py          # 编译调度器（依赖图驱动）
│   ├── kernel/                   # 内核抽象（类型系统 + 公理）
│   │   ├── ast.py                # AST 节点定义（dataclass）
│   │   ├── spec/                 # 统一类型描述系统
│   │   │   ├── specs.py          # 具体 Spec 类
│   │   │   ├── registry.py       # SpecRegistry + SpecFactory
│   │   │   └── base.py           # IbSpec 基类
│   │   ├── axioms/               # 类型公理系统
│   │   │   ├── primitives.py     # 内置类型的公理实现
│   │   │   ├── protocols.py      # Capability 接口定义
│   │   │   └── registry.py       # AxiomRegistry
│   │   ├── factory.py            # KernelFactory（创建默认注册表）
│   │   └── registry.py           # KernelRegistry（运行时对象工厂）
│   ├── runtime/                  # 运行时
│   │   ├── bootstrap/            # 引导层（内置类型注册）
│   │   ├── interpreter/          # 树遍历解释器
│   │   │   ├── handlers/         # AST 节点处理器（stmt/expr/import）
│   │   │   ├── llm_executor.py   # LLM 调用执行器
│   │   │   └── runtime_context.py # 运行时上下文
│   │   ├── objects/              # IbObject 类型层次
│   │   │   ├── kernel.py         # 核心对象（IbObject/IbClass/IbFunction...）
│   │   │   └── builtins.py       # 内置类型对象（IbInteger/IbList/IbTuple...）
│   │   └── host/                 # 宿主服务（断点/快照）
│   └── extension/                # 插件扩展接口
├── ibci_modules/                 # 内置插件（10个）
│   ├── ibci_ai/                  # LLM 核心插件（有状态）
│   ├── ibci_net/                 # HTTP 客户端（13个方法）
│   ├── ibci_math/                # 数学运算（22个算子）
│   ├── ibci_json/                # JSON 解析
│   ├── ibci_time/                # 时间操作（14个）
│   ├── ibci_schema/              # 结构验证（5个算子）
│   ├── ibci_file/                # 文件系统（受限）
│   ├── ibci_isys/                # 运行时状态查询（核心级，v2.0 合并了 ibci_sys）
│   ├── ibci_ihost/               # 宿主服务（核心级）
│   └── ibci_idbg/                # 调试器（核心级）
├── ibci_sdk/                     # 零依赖插件开发 SDK
│   ├── gen_spec.py               # 自动生成 _spec.py
│   └── check.py                  # 插件预检验
└── tests/                        # 测试（432 个）
```

---

## 三、编译流水线详解

### 3.1 整体流程

```
源代码 (.ibci)
   │
   ▼
Lexer（词法分析）
   │ Token 流
   ▼
Parser（语法分析）
   │ AST（Python dataclass）
   ▼
Serializer（AST JSON 序列化）
   │ 序列化 AST（key: node_uid）
   ▼
SemanticAnalyzer（语义分析）
   │ SideTable（类型绑定 + 延迟标记 + 作用域）
   ▼
Artifact（ImmutableArtifact = 序列化 AST + SideTable）
   │
   ▼
Interpreter（树遍历解释器）
   │ IbObject
   ▼
输出 / 宿主回调
```

### 3.2 Lexer（`core/compiler/lexer/`）

词法分析分为两部分：

- **`core_scanner.py`**（806 行）：处理正常代码中的词法单元，同时有一个特殊子状态机处理行为表达式（`@~...~` 块）和 LLM 函数体内的 RAW_TEXT/VAR_REF。
- **`llm_scanner.py`**：专门处理 `llm...llmend` 内部的 sys:/user:/retry: 段落扫描。

关键设计：**行为表达式的词法状态切换**。进入 `@~...~` 后，扫描器进入 `BehaviorMode`，此时：
- 普通字母/数字/标点 → `RAW_TEXT` token
- `"..."` 或 `'...'` → `STRING` token（内容不含引号）
- `$变量名` → `VAR_REF` token
- `~` → `BEHAVIOR_MARKER`（退出）

**已修复的 Bug（Fix 1）**：在 `core/compiler/parser/components/expression.py` 的 `behavior_expression()` 方法中，`STRING` token 没有被处理，`else: self.stream.advance()` 静默丢弃了它们。结果是 `@~ MOCK:["a","b","c"] ~` 被解析为 `[,,]`（空逗号列表）。修复方案是对 `STRING` 类型的 token 加上双引号后追加到 segments，对其他未知 token 将其 `.value` 追加（不再静默丢弃）。

### 3.3 Parser（`core/compiler/parser/`）

采用**递归下降 + Pratt 表达式解析器**的混合方式：

- `parser.py`：顶层调度，分发到各组件
- `components/statement.py`：语句级解析（if/for/while/try/assignment/llmexcept 等）
- `components/expression.py`：表达式解析（Pratt 优先级绑定）
- `components/declaration.py`：class/function/enum/llm 函数声明
- `components/type_def.py`：类型注解解析

AST 节点全部是 Python `@dataclass`，定义在 `core/kernel/ast.py`，共约 50 种节点类型。每个节点有 `_uid` 字段（编译期 UUID），这是**后续序列化与运行时分发的核心键**。

### 3.4 Serializer（`core/compiler/serialization/`）

AST 被序列化为 Python `dict`，key 是 node_uid，value 是节点的字段字典（包含 `_type` 字段用于运行时分发）。这使得：
1. 运行时不需要 Python AST 对象，避免了 GC 压力
2. AST 可以被缓存（`ImmutableArtifact`）并反序列化重用
3. 跨进程/断点继续执行成为可能

### 3.5 SemanticAnalyzer（`core/compiler/semantic/passes/semantic_analyzer.py`，1376 行）

这是整个编译流水线中**最复杂的部分**，执行多项工作：

1. **符号表与作用域管理**（`ScopeManager`）：收集所有变量、函数、类的定义，构建多级作用域链。
2. **类型推断与类型检查**（通过 `SpecRegistry.is_assignable()`）：检查赋值兼容性、函数参数类型匹配等。
3. **SideTable 填充**：
   - `node_to_type`：每个表达式节点对应的类型描述符（`IbSpec`）
   - `node_is_deferred`：行为描述表达式是否延迟执行（即赋值给 `callable` 类型时延迟）
4. **行为描述延迟标记**（关键逻辑，`semantic_analyzer.py:690-718`）：
   - 若 `behavior = @~...~` 目标是 `callable` 类型 → 标记 `is_deferred=True`（运行时包装为 `IbBehavior` 对象，不立即调用 LLM）
   - 否则 → 立即执行，将赋值目标类型绑定到行为节点，供 `_get_expected_type_hint()` 使用
5. **插件符号注入**（`Prelude._init_defaults()` + `Scheduler` 中的 import 处理）

---

## 四、运行时详解

### 4.1 解释器架构

解释器是一个**树遍历解释器**（`core/runtime/interpreter/interpreter.py`），通过 dispatch 模式将 node `_type` 分发到对应的 handler 方法。分三个 handler：

- `StmtHandler`（`handlers/stmt_handler.py`）：语句节点
- `ExprHandler`（`handlers/expr_handler.py`）：表达式节点
- `ImportHandler`（`handlers/import_handler.py`）：import 语句

分发机制：`visit(node_uid)` → 取 `node_data["_type"]` → 调用 `visit_<_type>(node_uid, node_data)`。

### 4.2 类型系统（`core/kernel/spec/`）

统一类型系统，**已彻底删除旧的 `core/kernel/types/` 目录**。核心概念：

#### IbSpec 层次

```python
IbSpec (base.py)
├── FuncSpec          # 函数类型
├── ClassSpec         # 类/枚举类型
├── ListSpec          # 列表类型（带 element_type_name）
├── TupleSpec         # 元组类型（新增，带 element_type_name）
├── DictSpec          # 字典类型
├── BoundMethodSpec   # 绑定方法类型
├── ModuleSpec        # 模块类型
└── LazySpec          # 延迟解析模块类型
```

内置原型常量（全大写，如 `INT_SPEC`、`LIST_SPEC`、`TUPLE_SPEC`）在 `specs.py` 末尾定义，并通过 `core/kernel/spec/__init__.py` 公开。

#### SpecRegistry 与 SpecFactory

`SpecRegistry`（`registry.py`，633 行）是运行时的核心门面，提供：
- `is_assignable(src, target)`：类型兼容性检查（走公理系统）
- `resolve(name)`：按名字查找 Spec
- `get_call_cap(spec)`：获取可调用能力（对 FuncSpec 返回 `_FUNC_SPEC_CALL_CAP` 哨兵）
- `resolve_iter_element(spec)`：获取迭代元素类型
- `resolve_subscript(spec, key_spec)`：下标访问返回类型

`SpecFactory` 提供 `create_list(elem_type_name)`、`create_tuple(elem_type_name)`、`create_dict()` 等工厂方法。

### 4.3 公理系统（`core/kernel/axioms/`）

公理系统是类型行为的"规则库"，将**类型语义**从运行时对象中解耦出来。每个内置类型有对应的 Axiom 类，实现相关 Capability 接口：

| Axiom | Capabilities |
|-------|-------------|
| `IntAxiom` | Parser, Converter, FromPrompt, IlmoutputHint |
| `FloatAxiom` | Parser, Converter, FromPrompt, IlmoutputHint |
| `BoolAxiom` | Parser, Converter, FromPrompt |
| `StrAxiom` | Parser, Converter, FromPrompt, IlmoutputHint |
| `ListAxiom` | Iter, Subscript, Parser, Converter, FromPrompt, IlmoutputHint |
| `TupleAxiom` | Iter, Subscript, Parser, Converter, FromPrompt（新增，不可变） |
| `DictAxiom` | Subscript, Parser, Converter, FromPrompt |
| `DynamicAxiom` | 全部接受 |
| `EnumAxiom` | FromPrompt, IlmoutputHint |
| `ExceptionAxiom` | Converter |
| `BoundMethodAxiom` | Call |
| `NoneAxiom` | Converter |

关键 Capability 接口（`protocols.py`）：

- `ParserCapability.parse_value(raw: str) -> Any`：将字符串转为 Python 原生值（用于内置赋值）
- `FromPromptCapability.from_prompt(raw: str, spec) -> (bool, Any)`：将 LLM 返回字符串转为原生值，失败时返回 `(False, retry_hint)`（触发 llmexcept）
- `ConverterCapability.cast_to(value, target_class) -> IbObject`：强制类型转换
- `IterCapability.resolve_iter_element(spec) -> IbSpec`：for 循环迭代元素类型
- `SubscriptCapability.resolve_subscript(spec, key_spec) -> IbSpec`：下标返回类型
- `IlmoutputHintCapability.__outputhint_prompt__(spec) -> str`：注入 LLM 输出格式提示

### 4.4 运行时对象层次（`core/runtime/objects/`）

#### kernel.py

```
IbObject                     # 所有 IBCI 对象的基类
├── IbNativeObject            # 封装任意 Python 对象
├── IbModule                  # 插件模块对象
├── IbClass                   # 类型对象（类型即值）
├── IbFunction (base)
│   ├── IbNativeFunction      # 注册的 Python 函数
│   ├── IbBoundMethod         # 绑定方法
│   ├── IbUserFunction        # 用户定义函数
│   └── IbLLMFunction         # LLM 函数（llm...llmend）
├── IbNone                    # null 单例
└── IbLLMUncertain            # LLM 不确定值哨兵（用于 llmexcept 检测）
```

#### builtins.py

```
IbObject
├── IbInteger                 # 整数（内部 .value = int）
├── IbFloat                   # 浮点数
├── IbBool                    # 布尔值（继承 IbInteger）
├── IbString                  # 字符串
├── IbException               # 异常对象
├── IbList                    # 可变列表（.elements: list of IbObject）
├── IbTuple                   # 不可变元组（.elements: tuple of IbObject，新增）
├── IbDict                    # 字典（.fields: dict）
└── IbBehavior                # 延迟行为对象（callable = @~...~）
```

`@register_ib_type("typename")` 装饰器将 Python 类注册到 `IbTypeMapping`，用于 `KernelRegistry.box()` 的类型分发。

### 4.5 装箱机制（Boxing）

`KernelRegistry.box(value, memo=None)` 将 Python 原生值包装为 IbObject：

```python
# builtin_initializer.py 中注册的 boxer：
int      → IbInteger.from_native(v, ...)
bool     → IbBool(v, ...)
float    → IbFloat(v, ...)
str      → IbString(v, ...)
list     → IbList（递归 box 每个元素）
tuple    → IbTuple（递归 box 每个元素）   ← 新增，之前错误地复用 _box_list
dict     → IbDict（递归 box key/value）
```

`memo` 参数用于处理循环引用（通过 id(val) 作为键缓存已装箱对象）。

### 4.6 LLM 执行器（`core/runtime/interpreter/llm_executor.py`，536 行）

`LLMExecutorImpl` 负责所有与 LLM 的交互，核心方法：

#### `execute_llm_function(node_uid, execution_context)`
处理 `llm...llmend` 定义的函数调用：
1. 解析 sys/user/retry prompt 段落（`_evaluate_segments`）
2. 收集意图栈（`IntentResolver.resolve()`）
3. 调用 `_call_llm(sys_prompt, user_prompt, node_uid)`
4. 检测特殊哨兵值（`__MOCK_REPAIR__`、`MAYBE_YES_MAYBE_NO_this_is_ambiguous`）
5. 通过 `_parse_result(raw_res, type_name)` 解析结果（走 Axiom 的 from_prompt）

#### `execute_behavior_expression(node_uid, execution_context)`
处理行为描述行 `@~...~`：
1. 用 `_evaluate_segments` 把带变量插值的 segments 拼成字符串
2. 通过 `_get_expected_type_hint` 获取目标类型（来自 SideTable）
3. 调用 LLM
4. 同样检测特殊哨兵值
5. `_parse_result` 解析

#### `_parse_result(raw_res, type_name, node_uid)`
通过 `MetadataRegistry` 找到类型的 Axiom，调用 `from_prompt(raw_res, spec)` 解析。失败时返回 `LLMResult.uncertain_result(retry_hint=...)` 触发 `llmexcept`。

#### `LLMResult`（`llm_result.py`）
```python
@dataclass
class LLMResult:
    success: bool
    value: Optional[IbObject]    # 成功时的结果
    is_uncertain: bool           # 是否触发 llmexcept
    raw_response: str
    retry_hint: Optional[str]    # 重试提示词
```

### 4.7 llmexcept 处理机制

`llmexcept:` 块是 IBCI 中处理 LLM 不确定性的核心机制，执行流程如下：

1. `visit_IbBehaviorExpr` 执行 LLM 调用，调用 `runtime_context.set_last_llm_result(result)`
2. `visit_IbAssign` 检测 `last_llm_result.is_uncertain`：若为 True，赋值 `IbLLMUncertain` 哨兵
3. `visit_IbLLMExceptionalStmt`：
   - 检测 `last_llm_result.is_uncertain`
   - 若为 True：清除 last_llm_result，执行 except 块（`retry "..."` 设置重试提示），然后重新执行整个赋值语句（带 retry_hint 重新调用 LLM）
   - 若为 False：跳过 except 块

**已修复的 Bug（Fix 2）**：`MOCK:FAIL` 的哨兵值 `"MAYBE_YES_MAYBE_NO_this_is_ambiguous"` 没有在 LLM 执行器中被检测，导致它像普通字符串一样被成功装箱，`is_uncertain=False`，llmexcept 块完全不触发。修复方案是在两个执行路径（`execute_llm_function` 和 `execute_behavior_expression`）中，于 `_parse_result` 调用**之前**检测这个哨兵并直接返回 `LLMResult.uncertain_result()`（与 `MOCK:REPAIR` 的处理方式完全平行）。

---

## 五、插件系统

### 5.1 两级插件架构

IBCI 有两种插件类型（定义见 `core/extension/ibcext.py`）：

#### 非侵入式插件（Non-Invasive）
不 import 任何 `core.*`，只需提供：
- `core.py`：Python 类，方法即指令
- `_spec.py`：类型描述（可用 `ibci_sdk.gen_spec()` 自动生成）

包括：`ibci_math`、`ibci_json`、`ibci_time`、`ibci_net`、`ibci_file`、`ibci_schema`

#### 核心级插件（Core-Level）
继承 `IbPlugin`，可访问 `PluginCapabilities`（registry、interpreter 等），可实现 `IbStatefulPlugin`（状态快照）或 `IbStatelessPlugin`：

包括：`ibci_ai`（有状态）、`ibci_ihost`、`ibci_idbg`、`ibci_isys`

### 5.2 ibci_ai 插件的 MOCK 模式

`ibci_ai` 的 `AIPlugin` 类实现了一个完整的 MOCK 测试框架（`_handle_mock_response()`），当 URL 为 `"TESTONLY"` 时激活：

| 指令 | 行为 |
|------|------|
| `MOCK:TRUE` | 返回 `"1"` |
| `MOCK:FALSE` | 返回 `"0"` |
| `MOCK:FAIL text` | 返回 `"MAYBE_YES_MAYBE_NO_this_is_ambiguous"` → 触发 llmexcept |
| `MOCK:REPAIR` | 首次返回 `"__MOCK_REPAIR__"`（触发 llmexcept），第二次返回 `"1"` |
| `MOCK:INT:42` | 返回 `"42"` |
| `MOCK:FLOAT:3.14` | 返回 `"3.14"` |
| `MOCK:STR:text` | 返回 `"text"` |
| `MOCK:["a","b","c"]` | 直接返回 JSON 字符串（已修复解析 Bug） |
| `MOCK:HELLO` | 返回 `"HELLO"` |

---

## 六、过程中遇到的问题与解决方案

### 6.1 类型系统重构遗留问题：`core/kernel/types/` 已删除

**问题**：在早期开发阶段，类型系统存在于 `core/kernel/types/`（旧体系）。后来统一迁移到 `core/kernel/spec/`（新体系 IbSpec/SpecRegistry）。在迁移过程中，代码的多个地方存在 `.descriptor` 属性的引用（旧接口），以及 `Symbol.spec` vs `Symbol.descriptor` 的命名混乱。

**解决**：彻底删除 `core/kernel/types/`，`Symbol` 只保留 `.spec` 字段，不再有 `.descriptor` 属性（无 shim 兼容层）。所有代码统一使用 `IbSpec` 体系。

### 6.2 插件可见性 Bug（Prelude 注入问题）

**问题**：`Prelude._init_defaults()` 错误地把所有插件的 `ModuleSpec` 都加入了 `builtin_modules`（并设置 `user_defined=True`），导致插件在没有 `import` 的情况下就能被访问，完全绕过了 `import` 语句的预期语义。

**解决**：`Prelude._init_defaults()` 只初始化真正的内置类型（int/str/list 等），插件的符号表注入**只在** `Scheduler` 处理 `import` 语句时触发。

### 6.3 元组被列表装箱（Tuple-as-List 问题）

**问题**：`builtin_initializer.py` 中 Python `tuple` 的 boxer 直接复用了 `_box_list`，导致 `tuple → IbList`，丧失了不可变性语义，且无法与 `list` 在类型系统中区分。

**解决**：全栈新增 `tuple` 类型支持：
- `TupleSpec`（`core/kernel/spec/specs.py`）
- `TUPLE_SPEC` 原型常量
- `SpecFactory.create_tuple()`
- `TupleAxiom`（`core/kernel/axioms/primitives.py`，不可变：无 append/pop/sort/clear/`__setitem__`）
- `IbTuple(IbObject)`（`core/runtime/objects/builtins.py`，`elements` 字段是 Python `tuple`）
- 专用 `_box_tuple` boxer（`Python tuple → IbTuple`）
- `stmt_handler.py` 中的元组解包支持同时处理 `IbTuple` 和 `IbList`

### 6.4 行为描述块中带引号字符串被丢弃

**问题**：词法分析器在 `@~...~` 内正确识别了 `"abc"` 这样的字符串字面量（生成 `TokenType.STRING` token），但 parser 的 `behavior_expression()` 方法：
```python
else:
    self.stream.advance()  # 静默丢弃！
```
导致所有 STRING token 的内容消失，`@~ MOCK:["a","b","c"] ~` → 拼接后得到 `MOCK:[,,]`。

**解决**：在 `behavior_expression()` 中添加对 `TokenType.STRING` 的显式处理，将其值包裹双引号后追加到 segments：
```python
elif self.stream.match(TokenType.STRING):
    segments.append('"' + self.stream.previous().value + '"')
else:
    segments.append(self.stream.previous().value if self.stream.advance() else "")
```

### 6.5 MOCK:FAIL 哨兵不触发 llmexcept

**问题**：`MOCK:FAIL` 的 mock 返回值 `"MAYBE_YES_MAYBE_NO_this_is_ambiguous"` 进入 `_parse_result()` 后，被 `StrAxiom.from_prompt()` 作为普通字符串成功装箱（`success=True`），导致 `LLMResult.is_uncertain=False`，llmexcept 块从不触发。

而 `MOCK:REPAIR` 的 `"__MOCK_REPAIR__"` 哨兵恰好在 `_parse_result()` 调用之前有专门检测，这是代码设计上的不一致性。

**解决**：在 `execute_llm_function` 和 `execute_behavior_expression` 的 `__MOCK_REPAIR__` 检测之后，立即添加对 `"MAYBE_YES_MAYBE_NO_this_is_ambiguous"` 的检测，两处均返回 `LLMResult.uncertain_result()`：
```python
if response == "MAYBE_YES_MAYBE_NO_this_is_ambiguous":
    return LLMResult.uncertain_result(
        raw_response="MAYBE_YES_MAYBE_NO_this_is_ambiguous",
        retry_hint="MOCK:FAIL - 模拟 LLM 返回不确定结果，请通过 llmexcept 处理"
    )
```

### 6.6 SpecRegistry 中 `get_call_cap()` 的哨兵设计

**问题**：早期设计中，`get_call_cap()` 对 `FuncSpec` 返回 `None`（和"没有 callable 能力"的情况相同），导致 callable 检查逻辑无法区分"这是一个函数类型"和"这个类型不支持调用"。

**解决**：引入 `_FUNC_SPEC_CALL_CAP` 哨兵常量，`FuncSpec`/`BoundMethodSpec` 时返回该哨兵，调用方用 `get_call_cap(spec) is _FUNC_SPEC_CALL_CAP` 检测。

---

## 七、当前已知的历史包袱与兼容性问题

### 7.1 `else: self.stream.advance()` 模式的遗留风险

**位置**：`core/compiler/parser/components/expression.py:behavior_expression()`  
**问题**：本次 Fix 1 虽然修复了 STRING token 丢失的问题，但 `else` 分支现在会把所有未知 token 的 `.value` 追加到 segments。如果 lexer 在 `@~...~` 内部生成了意料之外的 token（如 INDENT、NEWLINE 等），这些 token 的 value 会进入 segments，可能导致 LLM 收到多余字符。**建议**：为 `behavior_expression()` 添加一个明确的"允许 token 类型白名单"，对非预期 token 发出编译警告而非静默追加。

### 7.2 意图注释中的字符串处理（`_scan_intent_char`）

**位置**：`core/compiler/lexer/core_scanner.py:_scan_intent_char()`  
**问题**：意图行（`@ 意图文本`）中的字符串字面量进入 `IN_STRING` 子状态，最终生成 STRING token。但在 `_scan_intent_char` 的主逻辑中，对 STRING 的处理走的是 `push_state(SubState.IN_STRING)`，与行为表达式中调用 `_scan_string_in_behavior()` 的路径不同。两个路径生成的 token 类型一致（均为 STRING），但处理逻辑有细微差异。若意图文本含引号，可能有细节问题。

### 7.3 `IbLLMUncertain` 作为赋值占位符

**位置**：`stmt_handler.py:visit_IbAssign()`  
**问题**：当 LLM 返回不确定结果时，赋值语句会把目标变量赋值为 `IbLLMUncertain` 哨兵。若 llmexcept 块重试成功，变量会被重新赋值为正确值。但若重试仍然失败，该变量保持 `IbLLMUncertain` 状态，后续任何对它的访问（类型检查、方法调用）都会导致运行时错误。目前运行时没有针对性的"未初始化变量访问"错误提示，调试体验较差。

### 7.4 行为描述对象（IbBehavior）的 call_intent 传递问题

**位置**：`expr_handler.py:visit_IbBehaviorExpr()`（第 199-204 行注释）  
原代码注释：
```python
# 目前 IbBehavior 的工厂方法可能还不支持传递 call_intent，
# 暂时保持现状，等待下一步重构 behavior 对象。
```
**问题**：当行为描述表达式被标记为延迟执行（`is_deferred=True`），它被包装为 `IbBehavior` 对象返回，但此时 `call_intent`（行内的 `@intent~ ... ~` 格式）没有被传入 `IbBehavior`。等到 behavior 对象后来被调用时（比如通过函数参数传递），call_intent 已经丢失。这是一个已知的设计缺陷，影响延迟行为对象的意图传播。

### 7.5 `ibci_isys` v2.0 合并了 `ibci_sys` 后的历史代码

**问题**：`ibci_sys`（旧）被合并进 `ibci_isys`（v2.0）。但代码库中可能还存在对旧 `import sys` 语法的引用或测试用例注释，需要核实是否已全部清理。

### 7.6 `IbDeferredField` 在类定义中的处理

**位置**：`core/runtime/objects/kernel.py:IbDeferredField`  
**问题**：类的字段默认值如果是复杂表达式（如另一个对象的引用），在类定义时无法立即求值，被包装为 `IbDeferredField` 延迟到实例化时求值。目前这个机制的完整性和边界情况（如循环引用默认值）未被系统性测试。

### 7.7 IBCI_SPEC.md 与实现的同步

`IBCI_SPEC.md` 中描述了 `tuple` 类型，但在 Tuple 功能完整实现前（本轮工作完成后），该文档已经存在 tuple 的说明，说明文档超前于实现。目前文档内容是基本准确的，但 Tuple 的具体约束（不可变、无 append 等方法）在文档中未被明确列出，建议在文档中补充。

---

## 八、技术细节深度解析

### 8.1 SideTable：编译期与运行期的桥梁

SideTable（`core/compiler/semantic/passes/side_table.py`）是连接编译期语义分析和运行期解释器的关键数据结构：

```python
class SideTable:
    node_to_type: Dict[node_uid, IbSpec]        # 表达式 → 类型
    node_is_deferred: Dict[node_uid, bool]       # 行为描述是否延迟
    # ... 其他绑定
```

在 `ImmutableArtifact` 中，SideTable 随序列化后的 AST 一起打包，运行时通过 `execution_context.get_side_table(table_name, node_uid)` 访问。这使得运行时不需要重新进行类型推断，编译期的全部分析结果直接被运行时使用。

### 8.2 `_get_expected_type_hint()` 的双路径设计

`LLMExecutorImpl._get_expected_type_hint()` 有两条路径：

**路径 1（优先）**：AST 节点的 `returns` 字段  
`llm` 函数定义中的 `-> type` 注解会生成 `returns` 字段，直接读取类型名。

**路径 2（后备）**：SideTable 中的 `node_to_type` 绑定  
当行为描述表达式是 `str result = @~...~` 这种形式时，语义分析器会把 `str` 这个类型通过 `side_table.bind_type(inner_behavior_expr, str_spec)` 绑定到行为表达式节点，运行时从 SideTable 读取。

这个双路径设计是为了兼容两种场景（LLM 函数 vs 行内行为描述）的类型推断。

### 8.3 `from_prompt` 与 `parse_value` 的区别

- `parse_value(raw: str) -> native`：**简单确定性转换**，如 `"42"` → `42`（int）。用于 IBCI 代码中的字面量常量求值（如 `int x = 42`）。
- `from_prompt(raw: str, spec) -> (bool, native)`：**LLM 结果解析**，更宽松，能处理 LLM 可能返回的各种格式（如 `"The answer is 42."` 也尝试提取 42），失败时返回 `(False, retry_hint)`，而非抛出异常。

两者均在 Axiom 中实现，StrAxiom 的 `from_prompt` 最宽松（几乎永远成功），而 IntAxiom 的 `from_prompt` 会尝试正则提取数字，失败时触发 llmexcept。

### 8.4 `IbBehavior` 对象的生命周期

当 `callable result = @~...~` 时：
1. 语义分析期：标记 `is_deferred=True`，不绑定类型
2. 运行时：`visit_IbBehaviorExpr` 发现 `is_deferred=True`，调用 `object_factory.create_behavior(node_uid, captured_intents, expected_type)`，返回 `IbBehavior` 对象
3. 当 `result()` 被调用时（如函数调用语法），`visit_IbCall` 检测到 `IbBehavior` 实例，调用 `_execute_behavior(func)` 或 `llm_executor.execute_behavior_object(behavior, execution_context)`

`IbBehavior` 持有 `captured_intents`（捕获调用时刻的意图栈快照），确保延迟执行时意图上下文的正确性。

### 8.5 LLM 调用的意图解析流程

每次 LLM 调用前，`IntentResolver.resolve()` 会合并：
1. **当前节点的 call_intent**（行内意图 `@intent~ ... ~`）
2. **运行时意图栈**（由 `@` 注解压入的意图）
3. **全局意图**（通过 `ai.add_global_intent()` 设置的持久意图）

合并后的意图列表注入到 system prompt 中，格式为：
```
当前上下文意图：
- 意图1
- 意图2
```

### 8.6 `HostService` 的状态快照机制

`core/runtime/host/service.py` 中的 `HostService.snapshot()` 实现了运行时状态的完整捕获，用于断点继续执行（checkpoint-resume）：

1. 调用栈快照（`CallStack`）
2. 变量符号表快照
3. 有状态插件快照（仅 `IbStatefulPlugin` 实现者，如 `ibci_ai` 的 `_config`、`_retry_prompts` 等）
4. 意图栈快照

`_rebind_environment(plugin_states=...)` 恢复插件状态，这是 `IbStatefulPlugin` 协议存在的意义。

---

## 九、接下来可能的改善与梳理工作

### 9.1 高优先级（影响稳定性）

#### 9.1.1 behavior_expression() 的 token 白名单化

**当前状态**：`else` 分支追加所有未知 token 的 value  
**建议**：改为白名单模式，对 `INDENT`、`NEWLINE`（已 break）、`COMMENT` 等 token 发出 warning 或 error

#### 9.1.2 `IbLLMUncertain` 访问时的友好报错

**当前状态**：访问 `IbLLMUncertain` 值会得到各种诡异错误  
**建议**：在 `IbObject.receive()` 或各类型的方法中，对 `IbLLMUncertain` 对象的访问抛出特定的 `LLMUncertainAccessError`，并给出建议（"请使用 llmexcept 处理不确定结果"）

#### 9.1.3 IbBehavior 的 call_intent 修复

**当前状态**：延迟行为对象丢失行内意图  
**建议**：在 `create_behavior()` 接口中增加 `call_intent` 参数，并在 `execute_behavior_object()` 中使用

### 9.2 中优先级（提升完整性）

#### 9.2.1 Tuple 类型的完整支持

目前已有：字面量、解包、基本迭代、下标访问、to_list 转换  
尚缺：
- 编译期 tuple 类型注解（如 `tuple[int] result = ...` 的正式语法）
- 与 `list` 之间的显式转换语法（`(list)my_tuple`）
- 多元素类型的 TupleSpec（heterogeneous tuple，目前只有 `element_type_name` 单一类型）

#### 9.2.2 `callable` 类型的完整化

`callable` 目前可以存储行为描述对象，但：
- 没有函数签名类型（如 `callable(int, str) -> bool`）
- 不能存储用户自定义函数引用（first-class functions）
- `callable` 变量的调用语义与普通函数调用的语义分支逻辑散布在多处

建议将 `callable` 重新定位为专属"行为对象类型"（即只能存储 `IbBehavior`），与一等函数类型区分开来。

#### 9.2.3 IBCI_SPEC.md 的同步更新

当前文档未反映：
- Tuple 是不可变类型（无 append/pop/sort）
- `MOCK:FAIL` 的哨兵值细节
- `behavior_expression` 内字符串字面量现在正确支持

#### 9.2.4 枚举类型（Enum）的完整性

枚举目前支持基本的 `enum`/`EnumAxiom`/`IbEnum` 运行时对象，但：
- 枚举成员的比较（`==`）需要确认通过 LLM from_prompt 返回时的匹配逻辑
- 枚举的序列化（用于 snapshot）未被系统性测试

### 9.3 低优先级（技术债清理）

#### 9.3.1 `fuzzy_json.py` 的使用范围

`core/runtime/support/fuzzy_json.py` 实现了一个容错 JSON 解析器（用于解析 LLM 可能返回的非标准 JSON）。目前其使用范围不够统一，部分 Axiom 的 `from_prompt` 用它，部分直接用 `json.loads`。建议统一为 fuzzy_json 路径。

#### 9.3.2 测试覆盖的空白

目前 432 个测试主要覆盖：语言基础特性、E2E AI mock、插件实现。以下场景测试较少：
- `IbBehavior`（延迟行为对象）的完整生命周期
- HostService 的 snapshot/restore
- 深层嵌套的 llmexcept 重试链
- 用户自定义类的方法调用中触发 LLM

#### 9.3.3 `import_handler.py` 中插件加载的错误处理

当 `import` 一个不存在的插件时，目前的错误信息较为 cryptic。建议在 `ImportHandler` 中增加友好的插件未找到错误提示（列出所有可用插件名称）。

#### 9.3.4 `core/runtime/async/llm_tasks.py` 的异步路径

该模块定义了 `LLMTask` 和 `TaskState`（QUEUED/RUNNING/DONE/FAILED），看起来是为异步 LLM 调用设计的，但当前主执行路径中没有使用（所有 LLM 调用都是同步的）。这个模块是历史规划的残留，或者是为未来的异步支持预留的。目前状态：存在但未被集成到主流程。

---

## 十、测试结构概览

```
tests/
├── compiler/               # 编译器单元测试
│   ├── test_lexer.py       # 词法分析测试
│   ├── test_parser.py      # 语法分析测试
│   └── test_semantic.py    # 语义分析测试
├── runtime/                # 运行时单元测试
│   ├── test_builtins.py    # 内置类型测试
│   ├── test_plugin_implementations.py  # 插件实现测试
│   └── ...
├── e2e/                    # 端到端测试
│   ├── test_e2e_basic.py   # 基础语言特性
│   ├── test_e2e_ai_mock.py # AI/LLM mock 测试（16个，全部通过）
│   ├── test_e2e_advanced.py # 高级特性（类/枚举/Tuple等）
│   └── ...
└── sdk/                    # SDK 测试
    └── test_sdk.py
```

**当前状态**：432 / 432 测试通过，0 失败，1 个 DeprecationWarning（`datetime.utcnow()` 弃用，不影响功能）。

---

## 十一、总结

IBC-Inter 是一个设计思路新颖、架构层次清晰的语言运行时。经过本轮工作，核心问题已全部修复：

1. **Tuple 类型**从"列表装箱的临时 hack"升级为有专属 Spec/Axiom/Object 的一等公民类型
2. **行为描述块中的引号字符串**从"静默丢失"修复为"正确保留"
3. **MOCK:FAIL 哨兵**从"被当作成功字符串返回"修复为"正确触发 llmexcept"

工程现状健康，主要的历史包袱集中在：延迟行为对象的 call_intent 传递、`IbLLMUncertain` 的访问保护、以及异步 LLM 路径的集成规划。
