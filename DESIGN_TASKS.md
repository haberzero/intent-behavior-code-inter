# IBC-Inter 设计任务与后续工作记录

> 本文档记录 IBC-Inter 项目中已明确方向的设计任务与后续工作。
> 按优先级分类，每项包含结论与实施要点。
>
> **最后更新**：2026-04-17

---

## 零、设计结论存档（待讨论与确认）

### Z.1 llmexcept 与 for 循环的语义边界（已澄清）

**结论**：
- `llmexcept` 挂载在 `for` 循环语句后，**只保护 for 循环的条件判断 LLM 调用**（即 `iter_uid` 对应的行为描述），不关心循环体内部细节
- for 循环体内部若需要保护，开发者应在循环体内部**独立编写** `llmexcept`
- 重试时应从"触发失败的行为描述节点"位置重启 LLM 调用，**不应重启整个 for 循环**

**当前 Bug**：`visit_IbFor` 遇到不确定时 `return get_none()`，`visit_IbLLMExceptionalStmt` 重新 `visit(target_uid)` 即重新执行整个 `IbFor` 节点，导致循环从头重启。

**正确语义**（条件驱动循环）：
1. 条件 LLM 调用返回 uncertain → 触发 llmexcept
2. 重试：只重新执行 `iter_uid`（条件行为表达式），不重启循环体
3. 条件确定 true → 执行本次循环体，然后进入下次条件检查
4. 条件确定 false → 干净退出循环

---

### Z.2 callable 关键字废弃决定（设计层面）

**结论**：
- `callable` 关键字（作为用户可见的变量类型声明关键字）应被废弃
- 替换为 `lambda` 和 `snapshot` 两个更语义明确的关键字
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
- `TypeAnnotation lambda VariableName = @~...~` 是合法变量声明
- `TypeAnnotation snapshot VariableName = @~...~` 是合法变量声明
- `SyntaxRecognizer` 需要识别 `Type lambda/snapshot Name` 三 token 序列为 `VARIABLE_DECLARATION`
- 语义分析器中，`lambda`/`snapshot` 触发 `is_deferred=True`，且分别设置不同的 `ReceiveMode`

---

## 一、P0 优先级任务（阻塞性 Bug / 核心设计缺口）

### 1.1 llmexcept 在嵌套块内静默失效 [BUG / P0]

**文件**：`core/compiler/semantic/passes/semantic_analyzer.py`

**问题**：`_bind_llm_except()` 只处理 `IbModule / IbFunctionDef / IbClassDef`，**不递归进入** `IbFor / IbIf / IbWhile / IbTry` 的 body。导致循环体内的 `llmexcept` 在 Pass 3 中 target 永远为 None，运行时静默失效（`visit_IbLLMExceptionalStmt` 遇到 `target=None` 直接 `return get_none()`）。

**修复**：在 `_bind_llm_except()` 增加对 `IbFor`、`IbIf`、`IbWhile`、`IbTry` 等容器节点的递归处理，对其 body 调用 `_bind_llm_except_in_body()`。改动约 15 行，纯扩展，无破坏。

**注**：此修复与 §Z.1 的语义澄清结合起来理解：
- `llmexcept` 在 for 体外面（sibling）：保护 for 的条件调用（见 1.2 修复）
- `llmexcept` 在 for 体里面（nested）：保护 for 体内的某条行为描述语句（见本任务修复）

---

### 1.2 for @~condition~: + llmexcept 重试语义修复 [BUG / P0]

**文件**：`core/runtime/interpreter/handlers/stmt_handler.py`（`visit_IbLLMExceptionalStmt` + `visit_IbFor`）

**问题**：当 `for @~condition~:` 的条件不确定时，`visit_IbFor` 直接 `return get_none()`，`visit_IbLLMExceptionalStmt` 重新 `visit(target_uid)` 等于重启整个 for 循环，不符合预期语义。

**修复方案（方案 A：for 内部感知保护帧）**：

在 `visit_IbFor`（条件驱动分支）中，当条件 LLM 调用返回 uncertain 时，**检查当前节点是否有保护帧**（通过 `get_side_table("node_protection", node_uid)` 查询）：
- 若有保护帧 → 不退出循环，而是触发保护帧的 body 执行（等待 retry），然后**仅重试 `iter_uid`**，基于重试结果决定是否执行本轮 body
- 若无保护帧 → 维持当前行为（`return get_none()`）

同时修改 `visit_IbLLMExceptionalStmt`：当 target 为 `IbFor` 时，**不 re-visit 整个 `IbFor`**，只重新执行 `iter_uid`（从 target 的 node_data 中取 `iter` 字段）。

**依赖**：需要在 `visit_IbFor` 中能访问 `node_protection` 侧表。当前已有 `get_side_table()` 接口，可直接使用。

---

### 1.3 lambda / snapshot 关键字引入 + callable 废弃 [P0 设计实现]

**影响文件清单**：
- `core/compiler/common/tokens.py`：新增 `LAMBDA`、`SNAPSHOT` TokenType；可标注 `CALLABLE` 为 `@deprecated`
- `core/compiler/lexer/core_scanner.py`：新增 `'lambda'`、`'snapshot'` 关键字映射
- `core/compiler/parser/core/recognizer.py`：`SyntaxRecognizer.get_role()` 识别 `LAMBDA`/`SNAPSHOT` 触发 `VARIABLE_DECLARATION`；`_is_declaration_lookahead()` 扩展支持 `Type lambda/snapshot Name` 序列
- `core/compiler/parser/components/declaration.py`：`variable_declaration()` 解析 `Type lambda/snapshot Name = expr` 语法
- `core/compiler/parser/components/type_def.py`：`TypeComponent` 不需要改（类型解析照旧）
- `core/kernel/ast.py`：`IbAssign` 节点或新增 `IbDeferredBehaviorDecl` 节点，携带 `deferred_mode: DeferredMode` 字段（`LAMBDA` 或 `SNAPSHOT`）
- `core/compiler/semantic/passes/semantic_analyzer.py`：识别新的 deferred_mode，设置对应的侧表标记（`is_deferred=True` + 新增 `deferred_mode` 侧表）
- `core/compiler/semantic/passes/side_table.py`：新增 `node_deferred_mode` 侧表
- `core/runtime/interpreter/handlers/expr_handler.py`：`visit_IbBehaviorExpr` 根据 `deferred_mode` 决定是否捕获意图栈（snapshot 捕获，lambda 不捕获）
- `core/runtime/objects/builtins.py`：`IbBehavior` 新增 `deferred_mode` 字段区分 lambda/snapshot 行为（主要影响 invoke 时的上下文恢复逻辑）
- `docs/PENDING_TASKS.md`：更新 §4.1 和 §2.2

---

### 1.4 `(Type) @~...~` 行为描述提示词注入用途废弃 [P0 设计实现]

**影响文件**：
- `core/compiler/parser/components/expression.py`：`grouping()` 中 `IbBehaviorInstance` hook 移除，或改为发出 deprecated 警告
- `core/compiler/semantic/passes/semantic_analyzer.py`：`visit_IbAssign` 中对 `IbCastExpr + IbBehaviorExpr` 的特殊处理路径标注 deprecated，后续删除
- `core/kernel/ast.py`：`IbBehaviorInstance` 节点在此方案下可以被废弃（或保留用于插件/元编程场景）
- `docs/PENDING_TASKS.md`：更新 §4.1

**废弃策略**（渐进式）：
1. Phase 1：编译时 WARNING（`SEM_DEPRECATED`）：`(Type) @~...~` 用于提示词注入已废弃，请使用 `Type lambda/snapshot varname = @~...~`
2. Phase 2：编译时 ERROR

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

**状态**：`DynamicAxiom("behavior")` / `DynamicAxiom("callable")` 占位符。依赖 `lambda`/`snapshot` 关键字完成后推进。

---

### 4.4 ReceiveMode 枚举演进

**当前**：`is_deferred: bool` 侧表。

**远期**：迁移至 `ReceiveMode(IMMEDIATE / LAMBDA / SNAPSHOT)` 枚举，替代布尔值，支持 §Z.3/Z.4 中新语义的完整实现。

---

*本文档为 IBC-Inter 设计任务与工作记录。供后续开发智能体和贡献者参考。*
