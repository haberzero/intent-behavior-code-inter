# PT-AUDIT-3 — 双路径分裂专项审计记录

> 2026-08-11 执行。general agent 独立审计（只读）+ 主代理交叉核验 + 确凿项修复。
> 审计范围：异步统一 A1-A6 / run_batch CPS / yield 生成器 / generator IbClass / llmexcept / M1-M2 调用收敛。

## 一、审计结论

**无 P0（错误行为/契约破坏）**。三类历史病（孪生语义分裂、快照半消费、自审计误标）
在本批未复现为严重形态。发现 3 个确凿 P2 双路径漂移 + 5 个疑似项。

## 二、确凿问题（已修复，commit df1a896）

| # | 问题 | 位置 | 修复 |
|---|------|------|------|
| P2-1 | `ai.run_batch` 批路径不记录主线程单写槽 → `get_current_call_info()`/`idbg.current_llm()` 返回空 dict（与单调用路径"立即可见"契约漂移） | `_behavior.py:492-501` | `_run_batch_cps` 聚合后记录首项 call_info；+回归测试 `TestRunBatchObservability` |
| P2-2 | inline 路径 `call_info.active_intents` 恒空（dispatch 路径已填充）——观测字段漂移 | `_behavior.py:178-180/269-270` | 无 captured_intents 分支补 `context.get_active_intents()`（sync/CPS 两版） |
| P2-3 | `_RunBatchDrive._drive` 同步兜底返回未装箱 list，cps_drive 返回 boxed——同一 Waitable 两驱动路径产出形态不一致 | `_behavior.py:87-93` | `_drive` 补 `registry.box`，与 cps_drive 契约一致 |
| P2-4 | leaf.py generator 类兜底链 `get_class("generator") or "callable" or ib_class` 为死代码且掩盖错误（兜底到 callable 导致 to_list 未绑定、迭代才 AttributeError） | `leaf.py:372-374/392-394` | fail-fast：generator 类必注册（bootstrap 不变量），缺失抛 RuntimeError |
| P2-5 | KNOWN_LIMITS §二十四 机制描述过期（"同步解析不产生 Waitable" 实为 LLMFuture + generic_next 阻塞等待） | `KNOWN_LIMITS.md:554` | 修正机制描述 |

## 三、疑似项（记录待独立窗口，不在本批自主修改）

| # | 问题 | 位置 | 评估 |
|---|------|------|------|
| S1 | dispatch 路径 `__outputhint_prompt__` 同步 `.call` 嵌套调度器（hint 含 Waitable 时） | `_prompt.py:268` vs `:328-332` | **登记为已知边界（2026-08-12 复核）**：同步 `_get_llmoutput_hint` 由 dispatch_eager（主 VM 线程任务内同步预求值）与 run_batch 调用；vtable hint 分支经 `method.call` → `_drive_generator` 嵌套 TaskScheduler（EXEC-1 违反）。**可观察危害仅当用户 `__outputhint_prompt__` 含依赖外层调度器的 Waitable**（chan.recv 等）——hint 按惯例为纯字符串格式化，属极端 niche（与 A6 同性质：niche + 条件触发）。CPS 路径（`_get_llmoutput_hint_cps`）已用 UserFunctionCall 帧内驱动（F3）。彻底根治需 dispatch_eager 预求值 CPS 化（改造面大），不本批做 |
| S2 | `IbClass.receive('__call__')` 捕获主 EC，spawned task 内类构造跨线程改写主 EC 模块名 | `ib_class.py:327/273-284` | **登记为已知边界（2026-08-12 复核）**：`receive('__call__')` 捕获共享主 EC（`registry.get_execution_context()`），同步 `instantiate` 的 `_eval_field_defaults` 瞬态改写 `context.current_module_name`。需 worker 线程同步构造用户类（LLM 解析 `__from_prompt__` 中 `Class(...)`）且与主 VM 读模块名并发才竞态；且 worker 构造返回 drive 非实例（该路径本就非预期）。VM 主路径已 CPS 化（`_instantiate_cps` 同线程安全）。跨线程 EC 状态共享为架构层面，根治需 EC 线程隔离，独立设计窗口 |
| S3 | task 线程内生成器驱动写主线程单写槽（`_record_current_call_info` 契约"仅主线程"） | `_core.py:173` | **登记为已知边界（2026-08-12 复核）**：线程体经 `_drive_generator` → `_drive_loop_gen` → `execute_behavior_expression_cps` 的 resolve 点调用 `_record_current_call_info`（任务线程写共享单写槽）→ 与主线程写 `_current_call_info` 竞态（GIL 下无崩溃，仅 idbg/`get_current_call_info` 显示值不确定）。纯可观测性影响，非语义正确性。根治需单写槽线程化，独立设计窗口 |
| S4 | call_intent 短路仅 inline 可达（dispatch/run_batch 不传，AST 无 intent 字段，`_behavior.py:150-162/238-252` 死代码） | `_behavior.py:150-162/238-252` | **✅ 已根治（2026-08-12，PT-DEBT-24）**：AST 均无 intent 字段 → call_intent 恒 None → 死代码全链清理（_prepare_behavior_call 短路分支 / BehaviorCallSpec.pre_resolved / execute_behavior_expression_cps 参数 / LLM 函数穿透参数 / IbBehavior.call_intent 值字段+序列化）。保留 `get_resolved_prompt_intents` 的 call_intent 协议预留参数（docstring 注明未消费） |
| S5 | `_get_llmoutput_hint` 与 `_cps` 双实现（除驱动方式外同构） | `_prompt.py:243-359` | **✅ 部分处置（2026-08-12）**：共享 axiom 查找抽为 `_try_axiom_output_hint` 单一实现（两路径共用，消"改一处忘一处"漂移面）。vtable 驱动分支保持各自实现（sync `.call` / CPS `UserFunctionCall`——驱动机制不同，非双写真相） |

## 四、已核对干净区域

- sync vs CPS 孪生（prompt 构建/意图消解/hint/type_hint/target_model/retry_hint 逐行对照）：一致
- `resolve_content` vs `resolve_content_cps`、`resolve_to_prompts` vs `_cps`、`get_resolved_prompt_intents` vs `_cps`：委托同一 `IbIntentContext` 方法，一致
- `IntentResolver.resolve` vs `resolve_cps`：一致
- `_evaluate_segments` vs `_cps`：同一生成器复用，仅驱动方式不同
- `instantiate` vs `_instantiate_cps` / `_eval_field_defaults` vs `_cps` / `_invoke_init` vs `_cps`：结构对齐，thread 句柄语义保持
- `_run_batch_sync` vs `_run_batch_cps`（除 P2-1/P2-3）：意图快照/作用域/聚合/错误粒度一致
- `LLMBatchFuture`：保序/is_done/try_result/register_wake/异常重抛一致
- M1/M2 四个 callable `.call()` 薄包装：均收敛同一 `_vm_*` CPS 路径，无双写
- `LLMExceptFrame` + `_retry_llm_uncertain`：fork/refork 全槽位保存恢复、重试计数/restore/re-raise 正确
- fork 快照全槽位消费：resolve_to_prompts 读 override/smear/active/global 全槽位
- dispatch 单写槽时序（`_record_dispatch_call_info` → resolve 点覆盖）：d6d28e1 声明与实际一致
- generator 驱动/`resolve_iterable`/seq 内建：单一权威源，无死路径

## 五、处置记录

- PENDING_TASKS §〇 PT-AUDIT-3 条目更新为"已执行 + 修复 + 疑似项待独立窗口"
- PT-DEBT-24 条目补充 PT-AUDIT-3 复核确认（call_intent 死代码）
- F9（import ai 配置副作用）：**评估为设计意图保持**——`set_config` 对真实配置急切 `_init_client` 是 fail-fast 契约（测试显式处理"openai 未装但 mock 标志已清"）；延迟到首次调用是设计变更，独立窗口
- 全量 pytest 2209 passed / 1 skipped 零回归
