# IBC-Inter 设计任务与后续工作记录

> 本文档记录 IBC-Inter 项目中已明确方向的设计任务与后续工作。
> 按优先级分类，每项包含结论与实施要点。
>
> **最后更新**：2026-04-18（§4.3 Behavior 完成内容新增 BehaviorSpec 编译期推断条目）

---

## 零、设计结论存档（待讨论与确认）

### Z.1 llmexcept 与 for 循环的语义边界（已澄清）

**结论**：
- `llmexcept` 挂载在 `for` 循环语句后，**只保护 for 循环的条件判断 LLM 调用**（即 `iter_uid` 对应的行为描述），不关心循环体内部细节
- for 循环体内部若需要保护，开发者应在循环体内部**独立编写** `llmexcept`
- 重试时应从"触发失败的行为描述节点"位置重启 LLM 调用，**不应重启整个 for 循环**

**正确语义**（条件驱动循环）：
1. 条件 LLM 调用返回 uncertain → 触发 llmexcept
2. 重试：只重新执行 `iter_uid`（条件行为表达式），不重启循环体
3. 条件确定 true → 执行本次循环体，然后进入下次条件检查
4. 条件确定 false → 干净退出循环

---

### Z.2 callable 关键字废弃决定（设计层面）

**结论**：
- `callable` 关键字（作为用户可见的变量类型声明关键字）已废弃 ✅
- 替换为 `lambda` 和 `snapshot` 两个更语义明确的关键字 ✅
- `callable` 在类型系统内部（`CALLABLE_SPEC`、`BoundMethodAxiom.get_parent_axiom_name()` 等）的使用**保持不变**，不涉及面向用户的语法

---

### Z.3 `(Type) @~...~` 强制类型转换 + 行为描述混用的废弃（设计层面）

**结论**：废弃 `(Type) @~...~` 中将类型转换当作提示词注入的用法。理由：
- 与强制类型转换的传统语义（`(int) expr` 转换结果类型）严重冲突
- `float result = (int) @~ ... ~` 语义不直觉（提示词是 int，接收方是 float）
- 与新的 `int lambda f = @~...~` 语法相比，毫无优势

**迁移方向**：
- 原 `(int) @~...~`（提示词注入用途）→ 改为 `int lambda f = @~...~` 或 `int snapshot f = @~...~`
- 原 `int result = (int) @~...~`（即时执行带类型提示）→ 改为 `int result = @~...~`（LHS 类型自动成为提示词上下文）
- `(int) expr`（对非行为表达式的类型转换）→ **保留**，不受影响

**实现**：已实现（PAR_010 硬错误）✅

---

### Z.4 lambda / snapshot 语法设计方向（设计确认）

**建议采用的语法**：

```ibci
int lambda my_func = @~ 输出一个数字 ~
str snapshot my_handler = @~ 根据 $context 生成回复 ~
```

**语义定义**：

| 关键字 | 语义 | 状态捕获 |
|--------|------|---------|
| `lambda` | 延迟执行，每次调用时感知调用处的所有外部变量引用 | 不捕获变量，不捕获意图栈（使用调用时当前状态） |
| `snapshot` | 延迟执行，定义时深拷贝当前意图栈 + 全局变量 | 捕获意图栈（深拷贝）+ 全局变量快照 |

**返回类型标注规则**：
- LHS 类型（如 `int`）是该 callable 的**返回值类型**，同时作为提示词注入提示
- 无需也不允许再写 `(int)` 在行为描述前
- 无 LHS 类型时默认返回 `str`（与即时执行行为保持一致）

**解析规则**（给解析器的约束）：
- `TypeAnnotation lambda VariableName = @~...~` 是合法变量声明 ✅
- `TypeAnnotation snapshot VariableName = @~...~` 是合法变量声明 ✅
- `SyntaxRecognizer` 识别 `Type lambda/snapshot Name` 三 token 序列为 `VARIABLE_DECLARATION` ✅
- 语义分析器中，`lambda`/`snapshot` 触发 `is_deferred=True`，且分别设置不同的 `deferred_mode` ✅

---

## 一、P0 优先级任务（阻塞性 Bug / 核心设计缺口）

### 1.1 llmexcept 在嵌套块内静默失效 [BUG / P0] ✅ DONE

**文件**：`core/compiler/semantic/passes/semantic_analyzer.py`

**修复**：`_bind_llm_except()` 现已完整递归进入 `IbFor / IbIf / IbWhile / IbTry / IbSwitch` 的 body，
对各容器节点的 body 及 orelse/finalbody/cases 均调用 `_bind_llm_except_in_body()`。

**注**：此修复与 §Z.1 的语义澄清结合起来理解：
- `llmexcept` 在 for 体外面（sibling）：保护 for 的条件调用（见 1.2 修复）
- `llmexcept` 在 for 体里面（nested）：保护 for 体内的某条行为描述语句（见本任务修复）

---

### 1.2 for @~condition~: + llmexcept 重试语义修复 [BUG / P0] ✅ DONE

**文件**：`core/compiler/semantic/passes/semantic_analyzer.py`（`_bind_llm_except_in_body`），`core/runtime/interpreter/handlers/stmt_handler.py`（`visit_IbLLMExceptionalStmt`）

**修复**：
- `_bind_llm_except_in_body`：检测前一语句是 condition-driven for 循环（`target is None`）时，将保护绑定到 `iter_uid`（条件表达式），而非整个 for 节点
- `visit_IbLLMExceptionalStmt`：捕获 target 执行的返回值并作为自身返回值，使 `visit_IbFor` 的条件求值结果正确透传

---

### 1.3 lambda / snapshot 关键字引入 + callable 废弃 [P0 设计实现] ✅ DONE

**影响文件清单**：
- `core/compiler/common/tokens.py`：新增 `LAMBDA`、`SNAPSHOT` TokenType；移除 `CALLABLE` ✅
- `core/compiler/lexer/core_scanner.py`：新增 `'lambda'`、`'snapshot'` 关键字映射；移除 `callable` ✅
- `core/compiler/parser/core/recognizer.py`：`SyntaxRecognizer.get_role()` 识别 `LAMBDA`/`SNAPSHOT` 触发 `VARIABLE_DECLARATION`；`_is_declaration_lookahead()` 扩展支持 `Type lambda/snapshot Name` 序列 ✅
- `core/compiler/parser/components/declaration.py`：`variable_declaration()` 解析 `Type lambda/snapshot Name = expr` 语法 ✅
- `core/compiler/parser/components/type_def.py`：移除 `CALLABLE` token 处理 ✅
- `core/compiler/parser/core/syntax.py`：移除 `ID_CALLABLE` ✅
- `core/kernel/ast.py`：`IbAssign` 节点新增 `deferred_mode: Optional[str]` 字段 ✅
- `core/compiler/semantic/passes/semantic_analyzer.py`：识别新的 deferred_mode，设置对应的侧表标记（`is_deferred=True` + `deferred_mode` 侧表）；symbol 类型改为 `behavior` ✅
- `core/compiler/semantic/passes/side_table.py`：新增 `node_deferred_mode` 侧表 ✅
- `core/kernel/blueprint.py`：新增 `node_deferred_mode` 字段 ✅
- `core/compiler/serialization/serializer.py`：序列化 `node_deferred_mode` ✅
- `core/runtime/interpreter/handlers/expr_handler.py`：`visit_IbBehaviorExpr` 根据 `deferred_mode` 决定是否捕获意图栈（snapshot 捕获，lambda 不捕获）✅
- `core/runtime/objects/builtins.py`：`IbBehavior` 新增 `deferred_mode` 字段 ✅
- `core/runtime/factory.py` + `core/runtime/interfaces.py`：`create_behavior()` 新增 `deferred_mode` 参数 ✅

---

### 1.4 `(Type) @~...~` 行为描述提示词注入用途废弃 [P0 设计实现] ✅ DONE

**影响文件**：
- `core/compiler/parser/components/expression.py`：`grouping()` 中检测 `(Type) @~...~` 并发出 PAR_010 硬错误 ✅
- `core/compiler/semantic/passes/semantic_analyzer.py`：`visit_IbBehaviorInstance` 改为发出 SEM_DEPRECATED 错误；`visit_IbAssign` 防御性兜底路径同样发出 SEM_DEPRECATED ✅
- `core/compiler/semantic/passes/prelude.py`：移除 `callable` 别名降级 fallback ✅

---

## 二、P1 优先级任务

### 2.1 llmexcept 循环迭代器状态恢复 [P1]

**文件**：`core/runtime/interpreter/llm_except_frame.py`

**问题**：`_save_vars_snapshot()` 保存的是浅拷贝，for 循环迭代器的当前索引（`_loop_stack`）未完整恢复。修复依赖 1.2 任务先完成。

---

### 2.2 `"behavior"` 类型名称硬编码替换 [P1]

**文件**：`core/compiler/semantic/passes/semantic_analyzer.py`（`visit_IbFor` 两处字符串比较）

**修复**：在 `SpecRegistry` 添加 `is_behavior(spec)` 方法，替换直接字符串比较。约 5 行改动。

---

### 2.3 §9.2 Phase 1：metadata `kind` 字段引入 [P1]

**文件**：所有 `ibci_modules/*/` 的 `_spec.py`，`core/compiler/semantic/passes/prelude.py`

**任务**：在 `__ibcext_metadata__()` 返回值新增 `"kind": "method_module"` 字段；`Prelude._init_defaults()` 根据 kind 过滤，仅将真正的内置类型模块加入 builtin_modules。

---

## 三、P2 优先级任务（稳定后改进）

### 3.1 重试策略配置扩展 [P2]

**文件**：`ibci_modules/ibci_ai/core.py`、`core/runtime/interpreter/handlers/stmt_handler.py`

**任务**：支持指数退避（Exponential Backoff）和条件重试（基于错误类型）。

---

### 3.2 嵌套 llmexcept 系统性测试 [P2]

`LLMExceptFrameStack` 已支持多层嵌套，但嵌套场景下作用域隔离和帧交互未经过系统性测试。

---

### 3.3 意图标签解析从 Parser 迁移到 Lexer [P2]

**文件**：`core/compiler/parser/components/statement.py`（约第 278-289 行的 inline `import re` 临时方案）

---

## 四、VISION / 远期任务

### 4.1 lambda 的闭包引用问题

**未解决的设计问题**：`lambda` 被作为回调函数传递进其他函数体时，参数引用如何处理？捕获位置的变量还是传入位置的变量？

**当前策略**：暂不设计 lambda 的跨作用域传递语义，限制 lambda 只在定义作用域内使用。

---

### 4.2 host.run_isolated() 返回值改进

**当前妥协**：返回简化布尔值。

**远期目标**：在多返回值、元组解包语法实现后，改为 `tuple(exit_code: int, result: str | dict)`，与 IBC-Inter 类型系统深度整合。

---

### 4.3 Behavior / Intent 完整公理化

**状态**：**Behavior 已完成** ✅（PR: copilot/ibc-inter-design-review）

**Behavior 完成内容**：
- `BehaviorAxiom` + `BehaviorCallCapability` 完整落地
- `IbBehavior.call()` 自主执行，`_execute_behavior()` 旁路已彻底删除
- `BehaviorSpec(value_type_name=...)` 编译期返回类型推断已完成（PR: copilot/check-architecture-and-documentation）
  - `int lambda f = @~...~; int result = f()` 编译期不再产生 SEM_003
  - 详见 `AXIOM_OOP_ANALYSIS.md` §6.4 COMPLETED
- 详见 `AXIOM_OOP_ANALYSIS.md` Step 1 + Step 2

**Intent 状态**：Intent **不是** `DynamicAxiom` 占位符——`AxiomRegistry` 中不存在 intent 专属 Axiom。
当前正确描述：Intent 通过 `Bootstrapper.initialize()` 注册为内置 `ClassSpec`，`IbIntent` 是真正的 `IbObject`
子类，`IntentStack` 已有完整的原生方法注册。完整公理化（专用 `IntentAxiom`）工作量预估 3-5 人天，
不阻塞当前功能。见 `AXIOM_OOP_ANALYSIS.md` §6.2。

---

### 4.4 ReceiveMode 枚举演进

**当前**：`is_deferred: bool` 侧表。

**远期**：迁移至 `ReceiveMode(IMMEDIATE / LAMBDA / SNAPSHOT)` 枚举，替代布尔值，支持 §Z.3/Z.4 中新语义的完整实现。

---

*本文档为 IBC-Inter 设计任务与工作记录。供后续开发智能体和贡献者参考。*
