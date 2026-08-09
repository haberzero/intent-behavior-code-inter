# IBCI 语法说明手册

> 本手册是 IBC-Inter (IBCI) 语言的完整语法参考，按章节拆分至 `docs/syntax/`。
> 初学者入门见项目根 `GETTING_STARTED.md`；语言级限制见 `docs/KNOWN_LIMITS.md`；
> 架构设计见 `docs/ARCHITECTURE.md`；子系统设计见 `docs/SUBSYSTEM_DESIGN.md`。

## 语言定位

IBCI 是实验性意图驱动混合编程语言：Python 风格的确定性代码 + LLM 非确定性推理融合。
- **确定性半部**：强类型变量、运算符、控制流、函数、OOP -- 与 Python 高度同构。
- **意图半部**：行为表达式 `@~ ... ~`、LLM 函数 `llm ... llmend`、意图操作符 `@/@+/@-/@!`、`llmexcept` 自愈机制。
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
| 08 | [08_llm_functions](syntax/08_llm_functions.md) | LLM 函数 | `llm ... llmend`、`__sys__`/`__user__`/`__llmretry__` |
| 09 | [09_intent_system](syntax/09_intent_system.md) | 意图系统 | `@`/`@+`/`@-`/`@!`、意图栈、`intent_context` |
| 10 | [10_robustness](syntax/10_robustness.md) | 健壮性与自愈 | `llmexcept`/`llmretry`、快照隔离、LLM 异常体系 |

### 第三部分：模块与标准库

| 章 | 文件 | 标题 | 说明 |
|----|------|------|------|
| 11 | [11_modules](syntax/11_modules.md) | 模块与 import | import 约束、ai/isys/idbg/ihost/file/json |
| 12 | [12_builtins](syntax/12_builtins.md) | 内置函数与方法 | 全局内建（print/len/type/类型转换/序列辅助）+ str/list/dict/tuple 方法 |
| 13 | [13_mock_testing](syntax/13_mock_testing.md) | Mock 测试机制 | TESTONLY 模式、MOCK 指令语法、命名模型 MOCK |
| 14 | [14_concurrency](syntax/14_concurrency.md) | 并发与通信 | chan/slot/subscriber/thread/thread_result |

### 第四部分：诊断与错误

| 章 | 文件 | 标题 | 说明 |
|----|------|------|------|
| 15 | [15_diagnostics](syntax/15_diagnostics.md) | 诊断码参考 | 全量诊断码的触发条件与修复指引（码集合与 catalog 契约一致） |
