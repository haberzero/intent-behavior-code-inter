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
