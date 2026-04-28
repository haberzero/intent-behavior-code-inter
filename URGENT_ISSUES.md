# 紧急问题清单（Code Review 2026-04-28）

> 来源：代码全链路审查（IbCell / 闭包 / fn / 语义分析器 / 类型系统）  
> 优先级：**高** = 正确性风险或严重误导；**中** = 代码健康度；**低** = 维护性改善  
> 状态：⚠️ 待修复 / ✅ 已记录待下一 PR 处理

---

## 高优先级（正确性风险 / 严重文档误导）

### [H1] `IbDeferred` docstring 严重落后于 M2 实现
**文件**：`core/runtime/objects/builtins.py:705-706`  
**问题**：类 docstring 中仍残留 M1 时代的说明——
```
lambda 模式仍使用 ``captured_scope`` 引用链，
``closure`` 通常为空字典（保留接口以便后续 GC 根扫描接入）
```
这与 M2 后的实际实现**完全相反**：M2 后 lambda 模式同样使用 closure + 共享 IbCell，`captured_scope` 在 lambda 路径下始终为 `None`。  
**风险**：误导维护者认为 lambda 仍使用 `captured_scope` 作用域切换，写出错误代码。  
**修复**：删除 `captured_scope` 相关说明，更新为 M2 语义：自由变量通过共享 IbCell 间接访问。

---

### [H2] `_captured_scope` 僵尸字段存活
**文件**：`core/runtime/objects/builtins.py:715, 724`  
**问题**：`IbDeferred.__init__` 仍接受 `captured_scope` 参数并存储到 `self._captured_scope`，但 M2 后 `IbDeferred.call()` 完全不读取它。`expr_handler.py` 也是显式传 `None`。整个字段是死代码。  
**风险**：增加认知负担，让读者误认为 lambda 路径仍有作用域切换分支。  
**修复**：删除 `captured_scope` 参数、`self._captured_scope` 存储，以及 `expr_handler.py` 中的显式传 `None`。

---

### [H3] `DeferredAxiom.is_compatible` 与自身文档语义矛盾
**文件**：`core/kernel/axioms/primitives.py`（DeferredAxiom.is_compatible 实现）  
**问题**：docstring 明确声明"behavior 是 deferred 的子类型，deferred 槽位不接受 behavior 值"，但代码中有：
```python
or other_name.startswith("behavior[")  # ← 这行允许 deferred 赋值给 behavior 槽位
```
与文档语义矛盾。被 `is_fn_decl` guard 掩盖（fn 声明不走 `is_assignable`），但直接写 `behavior[int] f = lambda: expr` 时会错误通过编译，运行时对象是 IbDeferred 而非 IbBehavior，可能导致 LLM executor 路径混乱。  
**修复**：移除 `or other_name.startswith("behavior[")` 这行，或在 docstring 中明确解释为何故意允许。

---

## 中优先级（代码健康度）

### [M1] IbDeferred.call() 和 IbBehavior.call() 中的"兼容历史"死分支
**文件**：`core/runtime/objects/builtins.py`（IbDeferred.call ~776-785 行，IbBehavior.call ~960-969 行）  
**问题**：两处都有相同的 closure 解包兼容分支：
```python
if isinstance(payload, tuple) and len(payload) == 2:
    name, cell = payload
else:
    # 兼容历史：直接给定 cell（无名称）
    name, cell = None, payload
```
自 M2 后，`visit_IbLambdaExpr` 始终生成 `(name, IbCell)` 元组，`else` 分支是死代码。两处代码完全相同，违反 DRY 原则。  
**修复**：删除 `else` 分支；若需共用，抽取为 `_unpack_closure_payload(payload)` 工具函数。

---

### [M2] `define()` 的 fallback UID hash 生成是 patch 代码
**文件**：`core/runtime/interpreter/runtime_context.py:100-106`  
**问题**：当 `uid=None` 时通过 `hashlib.sha256` 生成内容哈希作为 fallback UID。  
问题一：相同类型+相同值的不同变量会产生相同 fallback UID，导致 `_uid_to_symbol` 条目被静默覆盖。  
问题二：合法的编译路径下语义分析始终提供 UID，此 fallback 是掩盖"UID 未注入"的补丁，而非正确处理。  
**修复**：至少在 `uid=None` 时打印警告或抛出断言；长期方案是要求调用方必须提供 UID（强制合同）。同时将 `import hashlib` 提到模块顶层。

---

### [M3] snapshot 模式自由变量捕获静默失败
**文件**：`core/runtime/interpreter/handlers/expr_handler.py`（_collect_free_refs 附近）  
**问题**：
```python
try:
    val = current_scope.get_by_uid(sym_uid)
except (KeyError, AttributeError):
    val = None
if val is not None:
    closure[sym_uid] = (name, IbCell(val))
```
若某自由变量 UID 查找失败，`val = None` 后静默跳过，snapshot closure 中缺少该变量。后续调用时运行时抛出"UID not found"而非明确的"变量未捕获"诊断，难以定位。  
**修复**：`val is None` 时至少输出 `debugger.trace()` 警告；理想情况下发出编译错误。

---

### [M4] `IbDeferred.to_native()` 和 `IbBehavior.to_native()` 静默返回 self
**文件**：`core/runtime/objects/builtins.py`（IbDeferred.to_native, IbBehavior.to_native）  
**问题**：未执行时 `to_native()` 返回 `self`（IBCI 运行时对象），而非 Python 原生值。调用者期望 Python 原生值，得到的是 IBCI 对象，后续无声地产生类型混淆。  
**修复**：未执行时抛出 `RuntimeError("IbDeferred/IbBehavior has not been executed; call first or use .call()")` 而非静默返回 self。

---

### [M5] `collect_gc_roots()` 用 `hasattr` 做接口检查
**文件**：`core/runtime/interpreter/runtime_context.py:699`  
**问题**：
```python
if hasattr(scope, 'iter_cells'):
    for cell in scope.iter_cells():
```
`iter_cells` 是 `ScopeImpl` 的协议方法，应通过 `isinstance(scope, ScopeImpl)` 或将 `iter_cells` 提升到 `Scope` 接口。`hasattr` 是接口不完整的信号。  
**修复**：将 `iter_cells()` 提升到 `Scope` 协议接口（返回空迭代器作为默认实现），或改用 `isinstance` 判断。

---

## 低优先级（维护性改善）

### [L1] `IbLambdaExpr.returns` 兼容字段生命周期未明确
**文件**：`core/kernel/ast.py:444`，`core/compiler/semantic/passes/semantic_analyzer.py:1753-1755`  
**问题**：`IbLambdaExpr.returns` 字段已标注"解析器不再设置"，但语义分析器中仍有回退路径处理它。这个兼容代码应有明确的删除计划，否则会无限期延续。  
**修复**：在 docstring 中标注"计划在 M3 PR 中删除"；或直接删除（如果旧格式 AST 缓存不存在）。

---

### [L2] `get_vars()` 硬编码内置函数过滤名单
**文件**：`core/runtime/interpreter/runtime_context.py:481`  
**问题**：
```python
if symbol.is_const and name in ("len", "print", "range", "input", "get_self_source"):
```
每次新增内置函数都需要手动维护此列表，容易遗漏。  
**修复**：在 `RuntimeSymbolImpl` 上添加 `is_builtin` 标志位，`builtin_initializer.py` 在注册内置函数时设置该标志，`get_vars()` 通过标志过滤而非硬编码名单。

---

### [L3] `visit_IbAssign` 的 `_pending_fn_return_type` 隐式上下文通道
**文件**：`core/compiler/semantic/passes/semantic_analyzer.py`  
**问题**：`_pending_fn_return_type` 作为 visit_IbAssign → visit_IbLambdaExpr 的隐式信息通道。try/finally 保证了嵌套安全，但这是"隐式魔法"，对维护者不直观。  
**改进建议**：文档注释中明确说明嵌套安全性保证，并注明这是刻意的设计决策（而非未完成的临时方案）。

---

### [L4] `_collect_free_refs` 启发式子节点遍历
**文件**：`core/runtime/interpreter/handlers/expr_handler.py`（_collect_free_refs 内部展开逻辑）  
**问题**：通过"字段值是字符串且存在于 node_pool"来判断是否为子节点 UID，是启发式遍历。理论上任何与 UID 格式碰撞的字符串常量字段都会被误判为子节点。  
**改进建议**：在注释中说明这是启发式，以及为什么 UID 格式设计（UUID/哈希前缀）使碰撞概率极低。

---

## 汇总统计

| 优先级 | 问题数 | 最高风险 |
|--------|--------|---------|
| 高 | 3 | H3 类型系统文档/代码矛盾，可能导致编译器错放 behavior/deferred 赋值 |
| 中 | 5 | M1 死代码累积；M4 to_native 静默失败 |
| 低 | 4 | 维护性/可读性问题，不影响正确性 |
| **合计** | **12** | — |

> 建议在下一个 PR（M3a CPS 骨架之前）先处理 H1、H2、H3 三项，避免为后续 VM 演进埋下隐患。
