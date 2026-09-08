# IBCI 语法说明手册

> 本手册是 IBC-Inter (IBCI) 语言的完整语法参考，按章节拆分至 `docs/syntax/`。
> 初学者入门见项目根 `GETTING_STARTED.md`；语言级限制见 `docs/KNOWN_LIMITS.md`；
> 架构设计见 `docs/ARCHITECTURE.md`；子系统设计见 `docs/SUBSYSTEM_DESIGN.md`。

## 语言定位

IBCI 是实验性意图驱动混合编程语言：Python 风格的确定性代码 + LLM 非确定性推理融合。
- **确定性半部**：强类型变量、运算符、控制流、函数、OOP——与 Python 高度同构。
- **意图半部**：行为表达式 `@~ ... ~`、LLM 可调用类 `__llm_call__`、意图操作符 `@/@+/@-/@!`、`llmexcept` 自愈机制。
- 两半共享同一类型系统与异常体系（`LLMError` 是 `Exception` 的子树）。

## 目录

### 第一部分：核心语法（确定性）

| 章 | 文件 | 标题 | 说明 |
|----|------|------|------|
| 01 | [01_types](syntax/01_types.md) | 类型系统 | 基础类型、泛型容器、Optional[T]、类型转换 |
| 02 | [02_variables](syntax/02_variables.md) | 变量声明与赋值 | 有类型/auto/any、元组解包、global、nonlocal |
| 03 | [03_operators](syntax/03_operators.md) | 运算符 | 算术（含幂/位运算）、比较、逻辑、成员、身份 |
| 04 | [04_control_flow](syntax/04_control_flow.md) | 控制流 | if/while/for/switch、try/except/raise/finally、pass |
| 05 | [05_functions](syntax/05_functions.md) | 函数 | 声明、递归、嵌套、fn 引用、fn[...] 高阶签名 |
| 06 | [06_oop](syntax/06_oop.md) | 面向对象 | 类、继承、super、Enum、协议方法表 |

### 第二部分：LLM 语法（意图驱动）

| 章 | 文件 | 标题 | 说明 |
|----|------|------|------|
| 07 | [07_behavior_expressions](syntax/07_behavior_expressions.md) | 行为描述语句 | `@~ ... ~`、lambda/snapshot、命名模型路由、多模态 |
| 08 | [08_llm_callable](syntax/08_llm_callable.md) | LLM 可调用类 | `__llm_call__`、装配 dict（`user_prompt`/`prompt_slots`/`expected_type`）、直接调用/`run_batch`/`stream` |
| 09 | [09_intent_system](syntax/09_intent_system.md) | 意图系统 | `@`/`@+`/`@-`/`@!`、意图栈、`intent_context` |
| 10 | [10_robustness](syntax/10_robustness.md) | 健壮性与自愈 | `llmexcept`/`retry`、快照隔离、LLM 异常体系 |

### 第三部分：模块与标准库

| 章 | 文件 | 标题 | 说明 |
|----|------|------|------|
| 11 | [11_modules](syntax/11_modules.md) | 模块与 import | import 约束、ai/isys/idbg/ihost/file/json |
| 12 | [12_builtins](syntax/12_builtins.md) | 内置函数与方法 | 全局内建（print/len/type/类型转换/序列辅助）+ str/list/dict/tuple 方法 |
| 13 | [13_mock_testing](syntax/13_mock_testing.md) | Mock 测试机制 | MOCK 模式、MOCK 指令语法、命名模型 MOCK |
| 14 | [14_concurrency](syntax/14_concurrency.md) | 并发与通信 | chan/slot/subscriber/thread/thread_result |

### 第四部分：诊断与错误

| 章 | 文件 | 标题 | 说明 |
|----|------|------|------|
| 15 | [15_diagnostics](syntax/15_diagnostics.md) | 诊断码参考 | 全量诊断码的触发条件与修复指引（码集合与 catalog 契约一致） |

## 保留词（关键字）

> 以下为 IBCI 的保留词单点清单（词法器关键字表）——**不可用作标识符**（变量/函数/类/
> 模块名等）。以保留词命名会产生解析歧义（如函数名 `fn` 与 `fn` 关键字碰撞）。
> 大小写敏感：`True`/`False`/`None`/`Uncertain` 为关键字，小写 `true`/`false`/`none`
> 不是（见 `docs/syntax/01_types.md` 布尔字面量）。

| 类别 | 保留词 |
|------|--------|
| import / 模块 | `import` `from` `as` `bind` |
| 函数 / 高阶 | `func` `return` `lambda` `fn` `yield` `await` |
| 作用域 / 流程控制 | `global` `nonlocal` `pass` `break` `continue` |
| 控制流 | `if` `elif` `else` `switch` `case` `default` `for` `while` `in` |
| 异常处理 | `try` `except` `finally` `raise` |
| 类型 / 声明 | `auto` `class` `protocol` `implements` `impl` `self` |
| 并发 / 结构 | `chan` `slot` `overlay` `with` |
| 逻辑 | `and` `or` `not` `is` |
| 常量 / 特殊 | `True` `False` `None` `Uncertain` |
| LLM / 健壮性 | `llmexcept` `retry` `snapshot` |

完整语法见各章（`docs/syntax/01`–`15`）。
