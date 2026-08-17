# _code_llm_providerization.md — LLM 调用层插件化主线（批 2+3 合并执行）

> 临时任务控制文档。完成后按 AGENTS.md / GOVERNANCE 删除（git 承载历史）。

## 目标

把内核 LLM 调用收敛到「产出 `LLMCallRequest` → 委托给 `LLMProvider`」单一动作，
供应商适配（request 组装 / 响应解析 / 思考抑制 / 探测 / api_config.json 读取）
全部下沉到可插拔 provider 实现。本批次 **批 2（内核收口）+ 批 3（provider 插件化）
在独立分支 `exp/llm-providerization` 原子完成**（二者在集成点不可拆分）。

## 决策记录

- **D1 契约层落点**：`core/base/llm_protocol/`（批 1 已 commit `efd3c6f4`，
  零破坏纯新增）。
- **D2 无双通道**：旧 `ILLMProvider`（标量签名）与旧 `_prompt_assembly` 拼串
  逻辑**真删除**，不留旧路径。新 `LLMProvider`/`PromptSlot` 是唯一权威。
- **D3 推荐模板下沉**：`_prompt_assembly` 的段落编排文本（discipline /
  type_constraint / intent / retry 的措辞与顺序）平移为 **默认 provider 内部
  的组装模板**（推荐格式），内核不再拼串、只产出 `PromptSlot` 结构。
- **D4 思考模式/探测下沉**：`enable_thinking`/`reasoning` 探测/ANSWER 后处理
  移入默认 provider 实现（LLM Studio + Qwen 适配），内核只声明
  `request.thinking_mode`。
- **D5 配置读取下沉**：`config_loader.py` 平移为默认 `ConfigSourceAdapter`
  实现；`api_config.json` schema 不再由内核唯一规定（提供推荐格式）。

## 变更清单

1. 内核 `llm_executor`：
   - `_core.py._call_llm`：改收 `LLMCallRequest`，经 `llm_callback.call(request)`
     调 provider（替换标量 `__call__`）。返回 `LLMCallResult.content` 供解析。
   - `_prompt_assembly.py`：新增 `build_prompt_slots()`（产出 `PromptSlot` 列表），
     旧拼串函数移除/平移为 provider 模板。
   - `_behavior.py` / `_llm_function.py`：spec 装配改为产出 `LLMCallRequest`。
2. provider `ibci_ai`：
   - `AIPlugin` 实现 `LLMProvider`（`call`/`stream`/`get_retry`/
     `is_auto_intent_injection_enabled`/`get_current_call_info`/`probe`）。
   - request→OpenAI payload 组装 + 供应商响应→`LLMCallResult` 解析。
   - `config_loader.py` 改为 `ConfigSourceAdapter` 实现。
3. 内省：`call_info` 记录 `LLMCallRequest.as_dict()`（全量原始语义）。
4. 测试：适配既有 provider 相关测试到新契约；新增 request→provider 合约测试。
5. 文档：`docs/architecture` 补中间层章节；`KNOWN_LIMITS` 登记边界；
   `PENDING_TASKS` 收尾 PT-DECIDE-2 / PT-FEAT-14。

## 验证

- 全量 pytest 零回归：**3027 passed / 1 skipped**（基线 3007 collected 全部通过；
  含新契约测试 + 既有 provider 测试同义迁移）。
- 真实 LLM 复跑：本地 qwen3.6-35b-a3b 非思考模式，T09 协议化影响套件 8/8 PASS
  （N1-N8 含并发 dispatch / llmexcept 真实重试 / from_prompt 类解析 / 类内 LLM 方法）。
- 复核：无旧 `ILLMProvider`/旧拼串残留（`grep` 双通道扫描零命中）；移除 `ILLMProvider`
  死代码。

## 完成状态

- 批 1（契约层）`efd3c6f4` 已合入 unsafe-vibe-dev。
- 批 2+3（内核收口 + provider 插件化）`9891e7e3` 在独立分支。
- 批 4（内省对齐 + 文档 + PT 登记）待复核放行后随分支更新。

## 分支政策

批 2+3 为破坏性重构（对外 provider 契约变更）→ 独立分支 `exp/llm-providerization`
实验；确认零风险 + 全量 pytest + 复核放行后，手动 cherry-pick 单独更新
`unsafe-vibe-dev`。**永不触碰 main；不 push。**
