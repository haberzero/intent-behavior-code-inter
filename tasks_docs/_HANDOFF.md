# 临时交接文档（下一 session 完成交接后删除）

> 本文件为**临时交接**，记录当前工作状态、已完成、下一步、关键约束与待决项。下一 session 据此继续后，经确认删除本文件。
> 状态：目标已暂停（用户要求）。分支 `unsafe-vibe-dev`，ahead 37（全部本地 commit，未 push）。

---

## 一、当前工作状态

- **主线**：LLM 真正可用的并行化 + 同步异步（`tasks_docs/NEXT_STEPS.md`）。
- **分支**：`unsafe-vibe-dev`（唯一活动分支，`pt-smell` 已合并删除）。
- **测试基线**：以实跑为准；当前全量 `python -m pytest tests/` = **1311 passed / 4 skipped**（约 24.9s）。
- **死锁防护**：`tests/conftest.py` 已加 90s 进程级看门狗（`os._exit(124)` + faulthandler dump），根治"测试死循环导致 pytest 永久挂起"。

## 二、已完成（本次会话，全部本地 commit 未 push）

### 主线（并行可靠性 + 异步）
- `050e8f2` PT-TEST-9：`probe_model` 测试覆盖
- `9d4c087`/`eb0d27e` PT-SYNC-1：并发 dispatch 完整性 + 稳定性
- `8171bc4` PT-SYNC-2：`LLMResult`/`LLMFuture` 语义测试 + 移除 `unwrap` 死代码
- `c1d1124` PT-SYNC-3：线程池 `close()` 后 fail-fast（不再静默重建）
- `530da3e` 移除 `ILLMProvider.__call__` 的 `scene` 残留参数
- `71997a0` `ai.__call__` 未 probe 回退加首次告警 + 记录 thinking 模型立场

### Stage 2 异步地基（本次重点）
- `e27bb33` `TaskScheduler`：多任务协作调度器（纯 stdlib）
- `88c73d3` 用真实 `concurrent.futures.Future` 验证并发
- `78b2666` `Waitable` 为 `runtime_checkable Protocol`，`LLMFuture` 结构符合可被 await
- `4013794` VM 调度器 `_drive_loop_body` → `_drive_loop_gen`（可挂起生成器）+ `run_many` 多根入口
- `dbfb2e9` `run_many` 测试
- `85c4fb6` 设计文档记录 Stage 2 进度（`docs/subsystems/05_coroutine.md` §7.6）

### 工作流/治理
- `120323d` 允许自主解封与目标一致的搁置项（AGENTS.md 上报阈值 + code-workflow Phase 0）
- `112e862` 新增 `quality-maintenance` / `aimless-review` skill + `AIMLESS_REVIEW.md`
- `0725c3c`/`1d9c274` docs/ 定位为纯人类手册（移除智能体元信息）
- `3cb0bcc` 测试死锁看门狗（90s）

## 三、下一步（接续方向）

1. **宿主级异步 PT-3.1**：`run_isolated`/`spawn_isolated` 返回**可 await 句柄 + 多返回值**（当前 `run_isolated` 同步返回 `bool`；`spawn_isolated` 返回 handle、`collect` 阻塞取回）。真正的宿主级并发应是**独立脚本/独立上下文**（非 `run_many` 的共享 context）。
2. **PT-3.2 `ReceiveMode`**：现在全仓无此符号，需定义 yield/resume 语义。
3. **`leaf.py` suspendable resolve**：`vm_handle_IbName`（`core/runtime/vm/handlers/leaf.py:74-78`）当前对 `LLMFuture` 调 `resolve` 阻塞；改为 yield future 给调度器挂起（单脚本内 LLM 阻塞也可挂起）。
4. **Stage 1 待办核验**（来自 `_code_llm_core.md`，将被删除）：`LLMResultParser.parse_result` 线程安全、`_prompt.py`/`_llm_function.py` 实例级状态、意图上下文并行隔离——需核验是否已完成。

## 四、关键约束与原则（必须遵守）

- **交付纪律**：仅本地 commit，禁止 push 到远程（除非用户明确允许）。
- **决策纪律**：需用户拍板的决断项可大胆激进选方案；底线=架构原则、代码质量原则、非妥协/非tricky/非临时兼容层、大方向主线。
- **可推翻 IBCI 自身设计缺陷**：即使文档化也可推翻，按更普适+实践合理方案重建；此类问题通常不询问用户，仅详记。
- **GIL 约束**：Python GIL 限制下，异步/并发只为**服务 LLM 调用**（IO 并发），非 CPU 并行、不追求性能。
- **docs/ 只面向人类**：`docs/` 不允许任何智能体元信息；智能体信息只在 `AGENTS.md` 与 `.opencode/skills/`。
- **工作流**：每任务走 code-workflow Phase 0-5 + 质量门 + 全量 pytest 零回归。

## 五、待决项 / 待清理

- **待决**：PT-3.1/3.2 设计（宿主异步句柄契约、ReceiveMode 语义）——用户可能想先对齐设计。
- **待清理**（本次会话已审查）：
  - `tasks_docs/_code_llm_core.md`（已过期，内容被 NEXT_STEPS/PENDING_TASKS/05_coroutine 取代，待删）
  - `tasks_docs/_work_inquiry.md`（临时工作清单，已用尽，待删）
  - `.tmp_pytest/`（pytest 临时目录，gitignored，可清）
- **非目标**：测试体系重构（TEST_REFACTOR）、media Phase 4、PT-SMELL-1（CODE_SMELL_AUDIT，未开始）。

---

> 交接完成阶段：本文件由下一 session 交接后删除；`_code_llm_core.md` / `_work_inquiry.md` 一并删除。