# _code_llm_prompt_mechanism — IBCI LLM 调用机制整改实施记录

> 2026-08-15 编制并落地（独立分支 exp/llm-prompt-mechanism）。对应 P0 主线：IBCI LLM 调用机制改进
> （交接 `_HANDOFF_LLM_PROMPT_MECHANISM.md` + PENDING_TASKS §〇 P0 行）。
> 本文为实施追踪文档，落地后按文档治理收敛/删除。

## 〇、任务目标（确认）

- A. 修复枚举 `__outputhint_prompt__` 未注入的机制 bug（module 感知注入）。
- B. 强化 behavior 系统提示词程序化调用纪律。
- C. 期望输出类型注入 prompt（behavior 路径；LLM 函数路径保留 provider type prompt）。
- D. llmexcept/retry 自动错误回喂（上次响应 + 解析错误），与用户手写 retry hint 协同。
- E. 结构化输出对齐（长期，本次不实现）。

## 一、设计决策（对照 design-philosophy / 工作模式定论）

1. **单一权威源**：系统提示词追加规则收敛到新模块
   `core/runtime/interpreter/llm_executor/_prompt_assembly.py`；
   `_behavior.py` 的 sync/CPS 与 `_llm_function.py` 的 CPS 共用同一套纯函数。
   消除"同一段拼装逻辑写两遍"的碎片化（behavior sync/CPS 现已重复）。

2. **A 修复**：`_try_axiom_output_hint(type_name, module=None)` 改为
   `meta_reg.resolve(type_name, module=module)`。`_get_llmoutput_hint(_cps)` 的
   node_to_type 分支传入 `node_to_type.module_path`；returns IbName 分支按当前
   execution_context 模块解析（与 `_get_expected_type_hint` 同构）。
   `_try_vtable_hint` 保持 module 感知（已具备）。

3. **B 修复**：behavior 基础系统提示从"你是一个意图行为代码执行器。"升级为
   "你是一个被 IBCI 程序调用的函数。你只返回调用方要求的数据本身；禁止输出
   问候语、解释、提问、拒绝、安全声明或任何与结果无关的文字。"
   命名 LLM 函数的 `__sys__` 是用户自设角色，不强制替换。

4. **C 修复**：behavior 路径组装 sys_prompt 时注入（单一优先级）：
   - provider `get_return_type_prompt(type_hint)`（显式插件/用户契约，最优先）
   - 否则 `__outputhint_prompt__`（有则 `[输出格式要求]`）
   - 否则对非动态/非行为本体类型注入 `[期望输出类型]\n必须返回一个 {type_hint} 值。`
   动态/无契约类型（behavior / fn_callable / any / auto / fn）不注入类型声明，
   避免把内部类型名泄漏给模型。
   LLM 函数路径：保留既有 provider type prompt；不新增泛化类型声明
   （`__sys__` 是用户自设输出契约）。

5. **D 修复**：`LLMExceptFrame` 增加 `last_llm_response` / `last_llm_error`
   只读 property，从 `target_result`（IbLLMCallResult）读取；prompt 组装层
   据 frame 生成 `[重试反馈]` 块，自动回喂上次原始响应 + 解析错误；用户
   `retry`/`__llmretry__` 提示词仍追加在后（与自动反馈不混写）。

6. **分支政策**：prompt 变化影响真实 LLM 输出，属对外行为变更；按"无法确认
   零风险"走独立分支 `exp/llm-prompt-mechanism`。全量 pytest + 判别性回归 +
   独立复核后，再评估手动 cherry-pick 到 unsafe-vibe-dev。

## 二、改动清单

- [x] 新增 `core/runtime/interpreter/llm_executor/_prompt_assembly.py`
- [x] 改 `core/runtime/interpreter/llm_executor/_prompt.py`
  - `_try_axiom_output_hint` module 参数
  - `_get_llmoutput_hint` / `_get_llmoutput_hint_cps` 传 module
- [x] 改 `core/runtime/interpreter/llm_executor/_behavior.py`
  - sync/CPS 共用 `_prompt_assembly.build_behavior_system_prompt`
  - type_hint 提前获取；provider type prompt / 通用类型声明注入
  - 自动重试反馈注入
- [x] 改 `core/runtime/interpreter/llm_executor/_llm_function.py`
  - LLM 函数同样自动重试反馈注入
  - `__outputhint_prompt__` 注入（`-> enum` 返回类型也吃到 hint）
- [x] 改 `core/runtime/interpreter/llm_except_frame.py`
  - `last_llm_response` / `last_llm_error` property
- [x] 新增回归测试：
  - enum behavior 的 sys_prompt 含 `[输出格式要求]` + 枚举 hint
  - behavior 基础 prompt 含程序化调用纪律
  - behavior 期望类型注入（str 无 provider prompt → 通用类型声明；int → provider prompt）
  - llmexcept retry 自动回喂上次响应 + 解析错误
  - LLM 函数返回 enum 时也注入 output hint
- [x] 全量 pytest 零回归 + commit + WORKLOG 同步（NEXT_STEPS 待合并后更新）

## 三、测试与验证

- 基线：2775 passed, 1 skipped（实跑）；整改后 **2787 passed, 1 skipped**（新增 6 项判别性回归 + 6 项 meta 测试随新文件/新测试自动纳入）。
- 判别性回归见上；全量 pytest 唯一命令。
