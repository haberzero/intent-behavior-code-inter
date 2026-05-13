# 代码内待处理问题索引（OPEN_ISSUES）

> 本文档汇总代码中所有 `TODO` / `[Future]` / `[临时方案]` 标注，作为代码与任务文档的桥接索引。
> 每条记录包含文件位置、问题描述和对应的文档跟踪位置。
>
> **更新规则**：修复某个问题后，将该条目从此文件删除或标记 `✅ DONE`。

---

## 一、运行时语义待修复项

### ~~OI-1：`str + llm_uncertain` 隐式拼接过渡兼容（2处）~~ ✅ **已解决（2026-05-12，NS-4）**

**文件**：
- `core/runtime/objects/builtins.py:IbString.__add__`（运行时）
- `core/kernel/axioms/primitives.py:StrAxiom.resolve_operation_type_name`（编译期）

**解决方案**：
- 编译期：`StrAxiom.resolve_operation_type_name` 移除 `llm_uncertain` 放行分支；走常规 SEM_003 类型检查。
- 运行期：`IbString.__add__` 检测到 `llm_uncertain` 哨兵时直接 `raise ThrownException(LLMParseError)`；同时 `IbNativeFunction.call` 增设 `ThrownException` 直通，保证语言级异常穿透原生函数边界。
- 用户的合法观察路径保留为 `(str)uncertain_var` 显式 cast。

**文档跟踪**：`docs/COMPLETED.md`（2026-05-12 NS-4 锚点）

---

### ~~OI-2：`ibci_idbg.protection_map()` 未实现~~ ✅ **已解决（2026-05-12）**

**文件**：`ibci_modules/ibci_idbg/core.py`

**解决方案**：
`idbg.protection_map()` 现基于当前 `ExecutionContext.node_pool` 构建保护映射：
- `IbLLMExceptionalStmt.target -> handler_uid`
- `IbFor.llmexcept_handler` 路径下（含 `IbFilteredExpr`）的条件节点 -> handler_uid  
并新增 `show_protection_map()` 打印入口。

**文档跟踪**：`docs/COMPLETED.md`（2026-05-12 PT-3.3 锚点）

---

## 二、编译器待修复项

### ~~OI-3：外部模块符号预注入临时妥协~~ ✅ **已解决（2026-05-02）**

**文件**：`core/compiler/scheduler.py`（已清理）

**解决方案**：
1. `Prelude._init_defaults()` 的 `is_user_defined=True` 过滤器已阻止插件模块预注入——无 `import` 时访问插件符号会触发正常的 `SEM_001 Unknown variable` 报错。
2. `scheduler.py` 中的 `[临时方案]` 注释已全部清除。
3. 新增 `SEM_009 SEM_IMPORT_CONFLICT` 诊断代码（`codes.py`）——当 `import X` 与用户定义的同名符号冲突时，编译器现在发出 WARNING 而非静默跳过。

**文档跟踪**：`docs/COMPLETED.md`

---

## 三、内核/规格层待优化项

### ~~OI-4：`SpecRegistry.resolve_specialization()` 无缓存~~ ✅ **已解决（2026-05-02 G3）**

**文件**：`core/kernel/spec/registry.py`（G1/G3 已修复）

**解决方案**：
1. G1（2026-05-02）：`resolve_specialization` 加入 early-cache hit 逻辑——注册后的特化类型通过 `self.resolve(candidate_key)` 快速命中，不再重复创建。
2. G3（2026-05-02）：`candidate_key` 改用 `a.name`（完整名称）而非 `a.get_base_name()`，嵌套泛型 `list[list[int]]` 可正确缓存和命中。

**文档跟踪**：`docs/COMPLETED.md`

---

## 四、设计层待跟进项

### ~~OI-5：LLMExceptFrame 重试历史追踪~~ ✅ **已解决（2026-05-12）**

**文件**：`core/runtime/interpreter/llm_except_frame.py`（`reset_for_retry()` / `LLMExceptFrame`）

**解决方案**：
`LLMExceptFrame` 新增 `error_history`，`set_error()` 按重试顺序追加结构化错误记录；`reset_for_retry()` 清理当前错误态但保留历史；`get_retry_info()` 暴露 `error_history_count/error_history`。

**文档跟踪**：`docs/COMPLETED.md`（2026-05-12 PT-1.2 锚点）

---

### ~~OI-6：LLMExceptFrameStack 最大嵌套深度~~ ✅ **已解决（2026-05-12）**

**文件**：`core/runtime/interpreter/llm_except_frame.py`（`LLMExceptFrameStack.push()`）

**解决方案**：
为 `LLMExceptFrameStack` 增加 `max_depth` 与溢出检查；并在 `RuntimeContextImpl.push_llm_except_frame()` 入栈处同步施加深度上限，保证主运行路径生效。

**文档跟踪**：`docs/COMPLETED.md`（2026-05-12 PT-1.3 锚点）

---

### ~~OI-7：`LLMCallError` 已注册但 VM 不自动抛出~~ ✅ **已解决（2026-05-06）**

**文件**：`core/runtime/interpreter/llm_executor.py:_call_llm`（已修复）

**解决方案**：
选择方向 1（接入触发路径）：`_call_llm()` 中 LLM provider 层的所有 Python 异常现在直接
`raise ThrownException(registry.make_llm_call_error(...))` 跳过 llmexcept retry，
让外层 `try except LLMCallError`（或 `try except LLMError` / `try except Exception`）捕获。

**设计决策说明**：
- `llmexcept` 的作用是保护 LLM 内容质量（幻觉/格式错误），通过 retry 循环纠正 LLM 输出。
- Provider 层失败（网络错误、鉴权失败等）与 LLM 输出内容无关，retry 对其无效，语义上不属于
  `llmexcept` 的保护范围。
- 用户代码应在外层 `try except LLMCallError` 中处理基础设施问题。
- 未来 VM 信号/中断机制（远期愿景，详见 `docs/VM_AND_INTERPRETER_DESIGN.md §5.1` L3 层）将提供更优雅的语言层面处理方案。

**文档跟踪**：`docs/COMPLETED.md`

---

*最后更新：2026-05-12*
