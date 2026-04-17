# IBC-Inter 近期优先任务

> 本文档从 PENDING_TASKS.md 中提取最紧急、最值得近期开展的任务，作为下一阶段的工作指导。
> 优先级判断依据：修复成本低、风险低、对运行时正确性影响大，或是无需理解大量上下文即可独立完成。
>
> **最后更新**：2026-04-17

---

## 一、立即可修复（改动范围极小，无需上下文理解）

### 1.1 删除 collector.py 中的废弃字段名

**文件**：`core/compiler/semantic/passes/collector.py:200`

**问题**：`llm_fallback` 字段已从 AST 中移除，`getattr(node, "llm_fallback", None)` 永远返回 `None`，此分支永远不会执行，属于无效代码。

**操作**：将 `"llm_fallback"` 从遍历属性元组中删除。

**当前代码**：
```python
for attr in ("body", "orelse", "finalbody", "llm_fallback"):
```

**修改为**：
```python
for attr in ("body", "orelse", "finalbody"):
```

**风险**：极低，属于删除死代码，无行为变化。

---

### 1.2 清理 runtime_context.py 中的过期 TODO 注释

**文件**：`core/runtime/interpreter/runtime_context.py`

**问题**：`push_llm_except_frame`、`pop_llm_except_frame`、`get_current_llm_except_frame`、`save_llm_except_state`、`restore_llm_except_state` 这五个方法的 docstring 中均有：
```
TODO [优先级: 高]: 完成后移除此注释
```
功能已完整实现，TODO 属于历史遗留，应删除以保持代码整洁。

**操作**：逐一删除上述 5 处 TODO 行及其上下空行（如有）。

**风险**：零，仅删除注释。

---

### 1.3 澄清 interop.py 中的 Protocol 继承 TODO

**文件**：`core/runtime/interpreter/interop.py:7`

**问题**：注释 `# TODO 这里有问题，为什么继承了protocol？` 实际上并无问题——继承 `Protocol` 在 Python 的 `typing` 体系中是允许的，相当于同时作为 Protocol 的实现类和 ABC 使用，无副作用。

**操作**：将该 TODO 替换为说明性注释（或直接删除）：
```python
# InterOpImpl 继承自 Protocol 接口，确保所有接口方法被实现（类似 ABC）。
# Python 允许此用法，isinstance 检查需要 @runtime_checkable 装饰。
```

**风险**：零，仅修改注释。

---

## 二、优先修复（影响运行时正确性，改动局限于单文件）

### 2.1 IbTuple 纳入 llmexcept 变量快照

**文件**：`core/runtime/interpreter/llm_except_frame.py`

**问题**：`_is_serializable()` 方法不处理 `IbTuple`，导致在 `llmexcept` 语句保护的代码块中，若存在 tuple 类型变量，重试时该变量无法被快照恢复。

**当前代码**（约第 149-160 行）：
```python
from core.runtime.objects.builtins import IbInteger, IbFloat, IbString, IbList, IbDict

if isinstance(val, (IbNone, IbInteger, IbFloat, IbString)):
    return True
if isinstance(val, IbList):
    return all(self._is_serializable(e) for e in val.elements)
if isinstance(val, IbDict):
    ...
return False
```

**修改方案**：
```python
from core.runtime.objects.builtins import IbInteger, IbFloat, IbString, IbList, IbDict, IbTuple

if isinstance(val, (IbNone, IbInteger, IbFloat, IbString)):
    return True
if isinstance(val, (IbList, IbTuple)):
    return all(self._is_serializable(e) for e in val.elements)
if isinstance(val, IbDict):
    ...
return False
```

**风险**：低，仅扩展类型判断范围，不改变已有逻辑。

---

### 2.2 IbTuple 纳入宿主状态序列化

**文件**：`core/runtime/serialization/runtime_serializer.py`

**问题**：`_process_value()` 方法中处理 IbList 之后，缺少 IbTuple 的分支，导致宿主快照（`HostService.snapshot()`）中的 tuple 变量序列化时走 else 分支，以"普通用户定义对象"方式处理，与 IbTuple 的实际结构不符，反序列化时会失败。

**修改方案**：在 IbList 分支之后紧接添加：
```python
from core.runtime.objects.builtins import IbTuple

elif isinstance(obj, IbTuple):
    data["_type"] = "tuple"
    data["elements"] = [self._process_value(e) for e in obj.elements]
```

同时在 `RuntimeDeserializer` 的对应 `elif` 分支中添加 tuple 反序列化逻辑（参照 list 处理方式，最终用 `IbTuple(elements=..., ib_class=ib_class)` 构造）。

**风险**：低，局限于 runtime_serializer.py 内。

---

## 三、近期可启动（有明确方向，但可能涉及多文件修改）

### 3.1 清理 scheduler.py 中的符号冲突静默处理

**文件**：`core/compiler/scheduler.py`（约第 464-503 行）

**问题**：多处 `pass` 静默跳过符号冲突，不发出任何警告，开发者难以察觉 import 被忽略。

**建议方案**：在 DEBUG 模式下（或 `strict_mode=True` 时）输出编译期警告（通过 `IssueTracker.add_warning()`），不改变运行时行为。

**参考文件**：`core/compiler/diagnostics/issue_tracker.py`（查找 `add_warning` 方法）

---

### 3.2 vtable 参数签名自动提取

**文件**：`core/runtime/module_system/discovery.py`

**问题**：见 PENDING_TASKS.md 0.3 节。

**建议启动方式**：先研究现有 `_build_spec_from_dict` 方法，了解 `MethodMemberSpec` 的构造方式，再在 `_load_spec` 协议1路径中补充 `inspect.signature()` 调用。

---

### 3.3 behavior 延迟执行时 call_intent 传递

**文件**：`core/runtime/interpreter/handlers/expr_handler.py`（约第 194-206 行）

**问题**：见 PENDING_TASKS.md 11.5 节。当 `@!` 修饰的表达式被延迟执行时，`call_intent` 字段未被设置。

**建议方案**：扩展 `create_behavior()` 工厂方法以支持 `call_intent` 参数，并在 `is_deferred=True` 路径中传入当前的 `call_intent`。涉及 `IbBehavior` 对象工厂和 `IbBehavior` 类本身。

---

*本文档记录 IBC-Inter 近期优先任务，供下一阶段开发参考。*
*详细背景和完整任务列表见 PENDING_TASKS.md。*
