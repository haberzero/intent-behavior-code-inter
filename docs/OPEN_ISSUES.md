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
为避免常见调试路径（`"prefix: " + str_var`）在 LLM 失败时崩溃，当前允许 `str + llm_uncertain` 隐式拼接（将 Uncertain 视作字符串 `"uncertain"`）。
注：异常体系（E1-E5）已在 2026-04-30 与 `llmexcept` 对齐 —— retry 耗尽抛 `LLMRetryExhaustedError`，无保护裸赋值的后续读取抛 `LLMParseError`，但本节涉及的 `+` 隐式拼接的过渡兼容仍保留以避免破坏现有调试代码。

**风险**：`str + llm_uncertain` 不报错，不确定性结果可能无声地流入用户可见字符串，掩盖实际 LLM 失败。

**解锁条件**：用户代码统一以 `is_uncertain(r)` 显式判断 + `try except LLMParseError` 捕获后，本兼容层可移除并改为类型错误。

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

### OI-7：`LLMCallError` 已注册但 VM 不自动抛出

**文件**：
- `core/kernel/axioms/primitives.py:LLMCallErrorAxiom`（公理已注册）
- `core/kernel/spec/specs.py:LLM_CALL_ERROR_SPEC`（spec 已注册）
- `core/kernel/registry.py:make_llm_call_error`（工厂方法已实现）
- `core/runtime/interpreter/llm_executor.py:_call_llm`（**应抛出未抛出处**）

**问题描述**：
`LLMCallError` 是 E1-E5 异常体系（2026-04-30）设计中区分"LLM provider 层硬失败"
（认证错误、网络错误、HTTP 4xx/5xx）与"内容解析失败"（`LLMParseError`）的类型，
含独立字段 `provider_error`。基础设施完备，IBCI 用户可手动 `raise LLMCallError(...)` 并被
`except LLMCallError`/`except LLMError`/`except Exception` 正确捕获（参见
`tests/e2e/test_e2e_ai_mock.py::TestE2EUserDefinedException::test_llm_call_error_user_raise_and_catch`）。

但 `llm_executor._call_llm()` 当前对所有 provider 层 Python 异常一律 `str(e)` 后转为
`error_msg`，进而走"不确定 → 重试"路径，**从未由 VM 自动抛出 `LLMCallError`**。

**影响**：
永久性失败（如 401 认证错误）会被白白消耗重试次数后以 `LLMRetryExhaustedError` 收尾，
而非语义上更准确的 `LLMCallError`。用户层无法在 `except` 分支中区分"LLM 内容不靠谱"与
"LLM provider 服务不可用"。

**两条可选解决方向**（任选其一以消除"设计有意图但代码无触发路径"的暧昧状态）：
1. **接入触发路径**：在 `_call_llm` 中按 Python 异常类型分类——永久性错误（如认证、配额）
   直接 `raise ThrownException(registry.make_llm_call_error(...))` 跳过重试；瞬时网络错误
   保持现有"转 uncertain → 重试"路径。
2. **裁剪为用户层类型**：保持当前实现，明确 `LLMCallError` 是**仅供用户手动 raise** 的语义类型
   （类似业务用 `class AppError(Exception):` 自定义异常的预定义版本），并在
   `IBCI_SYNTAX_REFERENCE.md §4.6.1` 已加注说明。

**文档跟踪**：`docs/IBCI_SYNTAX_REFERENCE.md §4.6.1`、`docs/PENDING_TASKS.md`（待入条目）

---

*最后更新：2026-05-06*
