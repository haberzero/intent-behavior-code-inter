# IBC-Inter 语言规范 (v2.0)

IBC-Inter（Interactive/Interpreted Intent Behavior Code）是一种面向过程、意图驱动的交互式编程语言。IBC-Inter 2.0 专注于“一切皆对象”的语义对齐和“侧表化”的平铺池化架构。

## 1. 核心语法规则

### 1.1 变量声明与类型系统
IBC-Inter 采用强类型声明，但支持 `var` 关键字进行自动推断。

```ibc-inter
int count = 10
str name = "IBCI"
var dynamic = 3.14  # 自动推断为 float
callable handler = @~ 处理数据 ~ # 行为描述 Lambda 化
```

### 1.2 行为描述行 (@~ ... ~)
行为描述行是 IBC-Inter 的灵魂，用于触发 LLM 的自然语言处理。

- **立即执行**：作为表达式右值或条件时立即发起调用。
- **延迟执行 (Lambda)**：赋值给变量（如 `var` 或 `callable`）时封装为函数，后续调用执行。
- **自动转换**：赋值给显式类型（如 `int`）时，内核自动解析 LLM 返回的文本。

```ibc-inter
str text = "The quick brown fox"
int words = @~ 数一下 $text 里的单词数 ~ # 立即执行
callable analyzer = @~ 分析情感 ~ # 延迟执行
```

### 1.3 意图系统 (Intents)
意图注释用于动态干预 LLM 的行为。

- **行级意图**：`@ 意图内容` 作用于下一行。
- **意图块**：`intent "场景":` 作用于块内所有 LLM 调用。
- **修饰符**：
  - `@!`：唯一模式（忽略全局意图）。
  - `@+`：叠加模式（默认）。

```ibc-inter
@! 请使用严肃的法律术语
str contract = @~ 生成一份租赁合同 ~
```

### 1.4 控制流
支持标准控制流，并集成了意图驱动的异常处理。

- **if/while**：支持行为描述作为条件。
- **llmexcept**：捕获 LLM 判定失败或不确定性。
- **retry**：重试当前判定的 LLM 请求。

```ibc-inter
if @~ 是否包含负面情绪 ~:
    print("Detected negative")
llmexcept:
    retry # 重新尝试判定
```

- **for 循环**：
  - `for i in list`：标准迭代。
  - `for @~ 条件 ~`：条件驱动循环（无 `in` 关键字）。

### 1.5 类系统 (Class)
IBC-Inter 2.0 强化了 OOP 与 AI 的结合。

- **构造函数**：`__init__`（参数无需显式 `self` 类型标注）。
- **提示词协议**：`__to_prompt__() -> str`。当对象被注入 Prompt 时，调用此方法获取 AI 视角下的表现。

```ibc-inter
class User:
    str name = "Alice"
    func __to_prompt__() -> str:
        return self.name

User u = User()
@~ 你好 $u ~ # AI 看到的是 "你好 Alice"
```

## 2. 运行时与编译器契约

### 2.1 平铺池化架构
编译器产出物不再是嵌套的内存对象，而是扁平化的 UID 引用池。
- **Nodes Pool**: AST 节点。
- **Symbols Pool**: 语义符号。
- **Scopes Pool**: 作用域层级。
- **Types Pool**: 静态类型元数据。

### 2.2 侧表化 (Side-Tabling)
所有的分析结论存储在侧表中，AST 保持只读。
- `node_to_symbol`: 节点到符号池 UID 的映射。
- `node_to_type`: 表达式的推导类型名。
- `node_scenes`: 节点的执行场景（BRANCH, LOOP）。
