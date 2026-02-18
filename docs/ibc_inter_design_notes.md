# IBC-Inter 设计要点说明书

## 1. 概述

本文档旨在为开发者和智能体提供 IBC-Inter 语言实现的深入指南。它涵盖了 Lexer（词法分析器）和 Parser（语法分析器）的设计细节、特殊处理逻辑以及潜在的混淆点。理解这些内容有助于快速定位问题并进行后续开发。

## 2. 核心设计理念

IBC-Inter 被设计为一种**面向意图、流程化执行**的交互式语言。其核心特点在于：

- **位置敏感的关键字**：为了减少自然语言与代码的冲突，绝大多数关键字（如 `if`, `func`, `import`）通常只应该出现在行首。
- **LLM 原生支持**：通过 `llm` 关键字定义自然语言处理函数，并支持运行时意图注入（Intent Injection）。
- **混合编程模式**：支持传统的结构化编程（循环、条件、类型系统）与非结构化的行为描述（Behavior Description）。

## 3. Lexer（词法分析）设计细节

Lexer 采用状态机模式，主要包含两种模式 (`LexerMode`) 和三种子状态 (`SubState`)。

### 3.1 模式与状态

#### 1. LexerMode (主模式)

- **`NORMAL`**: 标准代码解析模式，处理缩进、关键字、表达式等。
- **`LLM_BLOCK`**: 进入 `llm ... :` 后触发。在此模式下，Lexer 暂停生成 `INDENT`/`DEDENT` token，而是专注于寻找 LLM 专用关键字（`__sys__`, `__user__`, `llmend`）。

#### 2. SubState (子状态)

- **`NORMAL`**: 常规扫描。
- **`IN_STRING`**: 正在扫描字符串字面量。支持标准字符串 (`"..."`) 和原始字符串 (`r"..."`)。
- **`IN_BEHAVIOR`**: 正在扫描行为描述 (`~~...~~`)。

### 3.2 特殊处理逻辑

#### 3.2.1 LLM 块的处理

在 `LLM_BLOCK` 模式下：

- **关键字识别**：Lexer 会扫描行首（忽略空格）是否为 `__sys__`, `__user__` 或 `llmend`。
- **缩进警告**：虽然 Lexer 能正确识别带有缩进的 LLM 关键字，但会发出警告。建议这些关键字顶格书写或与 `llm` 定义对齐（视具体规范而定，目前实现偏向于警告任何缩进）。
- **内容处理**：非关键字的内容被视为 `RAW_TEXT`。
- **参数占位符**：识别 `$__param__` 格式的占位符，生成 `PARAM_PLACEHOLDER` token。

#### 3.2.2 行为描述 (`~~...~~`)

- **触发**：遇到 `~~` 进入 `IN_BEHAVIOR` 状态。
- **内容**：大部分字符被视为 `RAW_TEXT`。
- **变量引用**：`$var` 会被识别为 `VAR_REF` token，允许在行为描述中嵌入变量。
- **转义机制**：
  - `\~~` -> 转义为文本 `~~`
  - `\$` -> 转义为文本 `$`
  - `\~` -> 转义为文本 `~`
  - 其他反斜杠保留原样（方便书写路径等）。

#### 3.2.3 意图注释 (`@`)

- 以 `@` 开头的行被识别为 `INTENT` token。
- 内容一直读取到行尾。
- 这是一个**运行时**特性，而非像 `#` 那样的编译时忽略注释。

## 4. Parser（语法分析）设计细节

Parser 采用递归下降分析法，配合 Pratt Parsing 算法处理表达式优先级。

### 4.1 优先级系统 (Pratt Parsing)

表达式优先级从低到高排列（部分）：

1. `ASSIGNMENT` (`=`)
2. `OR` / `AND`
3. `COMPARISON` (`<`, `==`, etc.)
4. `TERM` (`+`, `-`) / `FACTOR` (`*`, `/`)
5. `UNARY` (`not`, `-`, `(Type)`)
6. `CALL` (`()`, `.`)

> **注意**：类型转换 `(Type) expr` 被特殊处理，具有极高的优先级（类比 UNARY），在 `grouping`（括号处理）逻辑中进行超前断言（Lookahead）识别。

### 4.2 意图注入 (`@`) 的绑定规则

- **存储**：Parser 遇到 `INTENT` token 时，将其内容暂存入 `self.pending_intent`。
- **消耗与绑定**：
  - `pending_intent` 会被**下一个**遇到的 `Call` 节点（函数调用）或 `BehaviorExpr` 节点（行为描述）消耗。
  - **Scope**：意图只作用于紧邻的下一个可附着对象。
  - **嵌套调用**：在 `outer(inner())` 中，如果在 `outer` 之前有 `@`，意图会附着在 `outer` 上，而不是 `inner`。
  - **示例**：

```ibc-inter
@ 关注性能
result = complex_calc(data)  <-- 意图附着于 complex_calc 调用
```

### 4.3 泛型与类型系统

- 泛型类型如 `List[int]` 在语法层面被解析为 `Subscript`（下标）操作：
  - `value`: `Name(id="List")`
  - `slice`: `Name(id="int")`
- 这使得类型注解的解析复用了现有的表达式解析逻辑。

## 5. 典型代码分析示例

### 示例 1: 带有意图的 LLM 调用

**代码**:

```ibc-inter
@ 语气要在委婉一点
str reply = chat_bot(user_input)
```

**分析结果**:

- `Assign` 节点
  - `targets`: `[Name(id="reply")]`
  - `value`: `Call` 节点
    - `func`: `Name(id="chat_bot")`
    - `args`: `[Name(id="user_input")]`
    - **`intent`**: `" 语气要在委婉一点"` (注意：这是 Call 节点的特殊字段)

### 示例 2: 行为描述中的逻辑判断

**代码**:

```ibc-inter
if ~~ check $user is valid ~~:
    pass
```

**分析结果**:

- `If` 节点
  - `test`: `BehaviorExpr` 节点
    - `content`: `" check  is valid "`
    - `variables`: `["user"]` (提取出的变量名)
  - `body`: `[Pass]`

### 示例 3: 复杂类型定义

**代码**:

```ibc-inter
func process(Dict[str, List[int]] data) -> None:
    pass
```

**分析结果**:

- `FunctionDef` 节点
  - `args`: `[arg]`
    - `annotation`: `Subscript` (对应 Dict[...])
      - `value`: `Name(id="Dict")`
      - `slice`: `Subscript` (对应 List[...]) 的外层结构... *注意：Dict 有两个参数，会被解析为 Tuple 或 ListExpr 形式的 slice*。
      - 实际解析为：`Subscript(value=Name(id="Dict"), slice=ListExpr(elts=[Name(id="str"), Subscript(value=Name(id="List"), slice=Name(id="int"))]))`

## 6. 常见混淆与注意事项

1. **LLM 关键字缩进**：
   虽然 Parser 可能容忍 `__sys__` 前的缩进，但 Lexer 会发出警告。最佳实践是保持 LLM 块内部关键字顶格或统一对齐，不要混用。

2. **意图 (`@`) 的“一次性”特性**：
   `@` 注释一旦被消耗（绑定到某个调用），就会被清除。它不会延续到后续的语句。如果一行中有多个调用，如 `x = func1() + func2()`，根据解析顺序（通常是递归下降），意图可能会绑定到最先被解析到的那个节点（取决于具体实现细节，通常是外层或第一个遇到的 Call）。*当前实现倾向于在解析 Call 的开始处检查并绑定 pending_intent，因此在嵌套结构中需要特别注意解析顺序。*

3. **行为描述中的转义**：
   在 `~~...~~` 中，只有 `~` 和 `$` 是特殊字符。其他字符（如 `\n`, `\t`）通常作为原始文本处理，除非显式使用 `\` 转义了 `~` 或 `$`。

4. **类型转换语法**：
   `(int) x` 是合法的。
   `int(x)` 则是普通的函数调用。
   两者在 AST 中表现不同：前者是 `CastExpr`，后者是 `Call`。

## 7. 调试建议

- **Lexer 调试**：检查 `tokens` 列表，特别是 `INDENT`/`DEDENT` 是否配对，以及 `LLM_BLOCK` 模式是否正确进入和退出。
- **Parser 调试**：利用 `parser.errors` 查看解析失败的具体位置。对于复杂的表达式优先级问题，检查 AST 树的嵌套层级是否符合预期。

## 8. 典型解析场景与边界情况详解

本章节补充了一些典型的代码场景及其对应的 Token 流或 AST 结构，旨在帮助开发者直观理解 Lexer 和 Parser 的行为，特别是边界情况。

### 8.1 意图注释 (`@`) 的作用域与绑定

**场景**：嵌套函数调用时的意图绑定。

**代码**：

```ibc-inter
@ 优先处理
x = outer(inner())
```

**解析逻辑**：

1. Parser 遇到 `@ 优先处理` -> 存储 `pending_intent = "优先处理"`.
2. Parser 解析赋值语句 `x = ...`.
3. 解析右值表达式：
   - 首先进入 `outer` 的 `Call` 解析节点。
   - `Call` 解析规则（`parser.call`）在开始时立即检查并消耗 `pending_intent`。
   - 因此，**`outer`** 函数调用获得了 `intent="优先处理"`。
   - 随后解析参数 `inner()`，此时 `pending_intent` 已为空，**`inner`** 调用无意图。

**AST 结构概览**：

```text
Assign
  targets: [Name(id="x")]
  value: Call(func=Name(id="outer"), intent="优先处理")
    args: [
      Call(func=Name(id="inner"), intent=None)
    ]
```

### 8.2 行为描述 (`~~`) 中的转义与变量

**场景**：需要在行为描述中使用 `~` 和 `$` 符号。

**代码**：

```ibc-inter
str cmd = ~~查找包含 \$100 和 \~~波浪号\~~ 的文本~~
```

**Token 流**：

1. `TYPE_NAME` (`str`)
2. `IDENTIFIER` (`cmd`)
3. `ASSIGN` (`=`)
4. `BEHAVIOR_MARKER` (`~~`)
5. `RAW_TEXT` (`查找包含 $100 和 ~~波浪号~~ 的文本`)
   - 注意：`\$` 被 Lexer 转义为 `$`，`\~~` 被转义为 `~~`，且合并到了 `RAW_TEXT` 中。
6. `BEHAVIOR_MARKER` (`~~`)

**解析结果 (AST)**：

```text
Assign
  value: BehaviorExpr
    content: "查找包含 $100 和 ~~波浪号~~ 的文本"
    variables: [] (因为 $ 被转义了，没有识别为变量引用)
```

**对比**：

如果代码是 `~~查找 $price~~`：

- Token 流包含 `VAR_REF` (`$price`)。
- AST 中 `variables` 列表包含 `["price"]`。

### 8.3 LLM 函数块的 Token 流

**场景**：LLM 函数体内部无缩进 Token 生成。

**代码**：

```ibc-inter
llm ask():
    __sys__
    Content
    llmend
```

**Token 流序列**：

1. `LLM_DEF` (`llm`)
2. `IDENTIFIER` (`ask`) ... `COLON` (`:`)
   - *Lexer 切换到 `LLM_BLOCK` 模式*
3. `NEWLINE` (`\n`)
   - *注意：此处不会生成 `INDENT` Token，即使源码中有缩进*
4. `LLM_SYS` (`__sys__`) (Lexer 忽略行首空格匹配关键字)
5. `NEWLINE` (`\n`)
6. `RAW_TEXT` (`    Content`) (保留了原有的缩进空格作为文本的一部分)
7. `NEWLINE` (`\n`)
8. `LLM_END` (`llmend`)
   - *Lexer 切换回 `NORMAL` 模式*
9. `NEWLINE` (`\n`)

**关键点**：在 LLM 块内，开发者无需担心缩进层级导致的 `INDENT`/`DEDENT` 错误，但关键字最好保持清晰的对齐风格以避免混淆。Lexer 会对缩进的关键字发出警告。

### 8.4 泛型嵌套的解析结构

**场景**：复杂类型注解 `List[Dict[str, int]]`。

**代码**：

```ibc-inter
func process(List[Dict[str, int]] data) -> None:
    pass
```

**AST 结构**：
Parser 复用了 `Subscript` (下标) 表达式来表示泛型。

```text
Subscript (对应 List[...])
  value: Name(id="List")
  slice: Subscript (对应 Dict[...])
    value: Name(id="Dict")
    slice: ListExpr (对应 str, int)
      elts: [
        Name(id="str"),
        Name(id="int")
      ]
```

*注意：当下标内有逗号分隔的多个元素时，Parser 会将其解析为 `ListExpr` (或 Tuple)，这与 Python 的 `ExtSlice` 或 `Index` 略有不同，是 IBC-Inter 的简化处理。*

### 8.5 比较运算符链

**场景**：`a < b <= c`。

**解析逻辑**：
Parser 在处理比较运算时，会进行特殊“扁平化”处理。

1. 解析 `a < b` -> `Compare(left=a, ops=['<'], comparators=[b])`
2. 发现后续还有 `<=` `c`。
3. 递归或循环中检测到左侧已是 `Compare` 节点。
4. 将新的运算符 `<=` 和操作数 `c` 追加到现有的 `ops` 和 `comparators` 列表中。

**AST 结构**：

```text
Compare
  left: Name(id="a")
  ops: ["<", "<="]
  comparators: [Name(id="b"), Name(id="c")]
```

这意味着后端解释器需要能够处理这种链式比较结构。

### 8.6 类型转换 vs 函数调用

**场景区分**：

1. `(int) x` -> **CastExpr**
2. `int(x)` -> **当前不支持 (Parse Error)**

**解析差异**：

- **CastExpr (`(Type)`)**：
  - 优先级极高（类比 UNARY）。
  - Parser 在遇到 `(` 时，会**向前看 (Lookahead)** 两个 Token。如果发现是 `(TypeName)` 结构，则直接按 Cast 解析。
  
- **Call (`Func()`)**：
  - 虽然设计上允许 `int(x)` 作为构造函数调用，但由于 `int` 是保留的 `TYPE_NAME` 关键字，且当前 Parser 未定义 `TYPE_NAME` 作为表达式前缀的规则，因此 `int(x)` 会抛出 "Expect expression" 错误。
  - **解决方案**：请统一使用 `(int) x` 语法。

**AST 结构对比**：

- `(int) x` -> `CastExpr(type_name="int", value=Name(id="x"))`

### 8.7 数值类型与 AST 常量表示

**场景**：数值字面量的解析规则。

**行为规范**：
Parser 根据 Token 的字符串内容区分整数和浮点数：

- 包含 `.` 或指数符号 (`e/E`) 的，解析为 `float`。
- 其他情况解析为 `int`。

**AST 表现**：

- `1` -> `Constant(value=1)` (int)
- `1.0` -> `Constant(value=1.0)` (float)

**注意**：此行为对列表索引等位置有直接影响，解释器在处理 `Subscript` 时可能依赖于此类型区分。

### 8.8 下标与切片 (Subscript)

**场景**：`my_list[0]`, `my_dict["key"]` 或泛型 `List[int]`。

**解析规则**：

- `[` (LBRACKET) 被注册为中缀运算符，优先级为 `Precedence.CALL`。
- 左侧表达式作为 `value`，方括号内的表达式作为 `slice`。

**AST 结构**：

- `Subscript(value=..., slice=..., ctx='Load')`

**语义**：
该节点在不同上下文中具有不同含义：

1. **类型注解**：表示泛型参数（如 `List[int]`）。
2. **表达式**：表示容器访问（如 `data[0]`）。
解释器或静态分析工具需根据上下文判断具体行为。

## 9. API 参考与交互契约

本章节定义了核心组件的公共接口与数据规范，作为模块间交互的契约。

### 9.1 Lexer API

```python
class Lexer:
    def __init__(self, source_code: str): ...
    
    def tokenize(self) -> List[Token]:
        """
        扫描源代码并返回 Token 列表。
        自动处理 EOF 和尾部 DEDENT。
        """
```

**Token 数据规范**：

- `TokenType.NUMBER`: `value` 属性始终为**原始字符串**（如 `"123"`, `"3.14"`）。Lexer **不执行** 数值类型转换，该责任由 Parser 承担。
- `TokenType.RAW_TEXT`: `value` 包含未处理的文本内容，可能包含换行符。

### 9.2 Parser API

```python
class Parser:
    def __init__(self, tokens: List[Token], warning_callback: Optional[Callable[[str], None]] = None): ...
    
    def parse(self) -> ast.Module:
        """
        解析 Token 流并返回 AST 根节点 (Module)。
        如果解析失败，将抛出 ParserError 或在 self.errors 中积累错误。
        """
```

**AST 节点语义契约**：

- **`Subscript`**: 是多态节点。在 `Load` 上下文中，既可以表示泛型类型（如 `List[int]`），也可以表示列表/字典访问（如 `data[0]`）。后端消费者（解释器/编译器）需根据运行时对象的类型来动态分发行为。
- **`Constant`**: `value` 属性存储已转换好的 Python 原生类型 (`int`, `float`, `str`, `bool`)。消费者无需再次解析字符串。
