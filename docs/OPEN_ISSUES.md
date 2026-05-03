# 代码内待处理问题索引（OPEN_ISSUES）

> 本文档汇总代码中所有 `TODO` / `[Future]` / `[临时方案]` 标注，作为代码与任务文档的桥接索引。
> 每条记录包含文件位置、问题描述和对应的文档跟踪位置。
>
> **更新规则**：修复某个问题后，将该条目从此文件删除或标记 `✅ DONE`。

---

## 一、运行时语义待修复项

### OI-1：`str + llm_uncertain` 隐式拼接过渡兼容（2处）

**文件**：
- `core/runtime/objects/builtins.py:326`（运行时）
- `core/kernel/axioms/primitives.py:400`（编译期类型检查）

**问题描述**：
IBCI 的 `try/except` 错误模型尚未与 `llmexcept` / LLM 不确定性体系完整对齐。在此之前，允许 `str + llm_uncertain` 隐式拼接（将 Uncertain 视作字符串 `"uncertain"`）以避免常见调试路径（`"prefix: " + str_var`）在 LLM 失败时崩溃。

**风险**：`str + llm_uncertain` 不报错，不确定性结果可能无声地流入用户可见字符串，掩盖实际 LLM 失败。

**解锁条件**：`try/except` 与 IBCI 错误模型对齐完成后，这两处应改为抛出类型错误。

**文档跟踪**：`docs/NEXT_STEPS.md` 选项 1 — 关联交付项；`docs/KNOWN_LIMITS.md §VIII`

---

### OI-2：`ibci_idbg.protection_map()` 未实现

**文件**：`ibci_modules/ibci_idbg/core.py:267`

**问题描述**：
调试器模块 `ibci_idbg` 的 `protection_map()` 方法当前返回空字典，因为内核尚未暴露 side_table 的只读接口。该方法本应返回节点保护表（供调试器可视化 llmexcept 保护范围）。

**解锁条件**：在 `IExecutionContext` 或 `IStateReader` 协议中新增 `get_side_table(key, uid)` 公共接口。

**文档跟踪**：`docs/PENDING_TASKS.md §11.6`

---

## 二、编译器待修复项

### ~~OI-3：外部模块符号预注入临时妥协~~ ✅ **已解决（2026-05-02）**

**文件**：`core/compiler/scheduler.py`（已清理）

**解决方案**：
1. `Prelude._init_defaults()` 的 `is_user_defined=True` 过滤器已阻止插件模块预注入——无 `import` 时访问插件符号会触发正常的 `SEM_001 Unknown variable` 报错。
2. `scheduler.py` 中的 `[临时方案]` 注释已全部清除。
3. 新增 `SEM_009 SEM_IMPORT_CONFLICT` 诊断代码（`codes.py`）——当 `import X` 与用户定义的同名符号冲突时，编译器现在发出 WARNING 而非静默跳过。

**文档跟踪**：`docs/COMPLETED.md §二十三`

---

## 三、内核/规格层待优化项

### ~~OI-4：`SpecRegistry.resolve_specialization()` 无缓存~~ ✅ **已解决（2026-05-02 G3）**

**文件**：`core/kernel/spec/registry.py`（G1/G3 已修复）

**解决方案**：
1. G1（2026-05-02）：`resolve_specialization` 加入 early-cache hit 逻辑——注册后的特化类型通过 `self.resolve(candidate_key)` 快速命中，不再重复创建。
2. G3（2026-05-02）：`candidate_key` 改用 `a.name`（完整名称）而非 `a.get_base_name()`，嵌套泛型 `list[list[int]]` 可正确缓存和命中。

**文档跟踪**：`docs/COMPLETED.md §二十三`

---

## 四、设计层待跟进项

### OI-5：LLMExceptFrame 重试历史追踪

**文件**：`core/runtime/interpreter/llm_except_frame.py`（`reset_for_retry()` / `LLMExceptFrame`）

**问题描述**：
每次重试时 `reset_for_retry()` 会清除 `last_error`，重试历史不保留。若需在 llmexcept body 内访问历次重试的错误摘要（用于更精细的提示词调整），需要给 `LLMExceptFrame` 添加 `error_history: List` 字段。

**文档跟踪**：`docs/PENDING_TASKS.md §11.4`

---

### OI-6：LLMExceptFrameStack 最大嵌套深度

**文件**：`core/runtime/interpreter/llm_except_frame.py`（`LLMExceptFrameStack.push()`）

**问题描述**：
当前无最大嵌套深度检查。深度嵌套的 llmexcept 块（如循环内多层 llmexcept）在极端情况下可能无界增长。

**文档跟踪**：`docs/PENDING_TASKS.md §11.5`

---

*最后更新：2026-04-30*
