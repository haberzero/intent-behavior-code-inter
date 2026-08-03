# 临时交接文档（下一 session 完成交接后删除）

> 本文件为**临时交接**，记录当前工作状态、已完成、下一步、关键约束与待决项。下一 session 据此继续后，经确认删除本文件。
> 状态：上一主线（LLM 并行化 + 同步异步）已完成并推送；下一主线（运行时多线程 + 通信机制 + 内省/控制）已确立，设计决策已记录。分支 `unsafe-vibe-dev`。

---

## 一、当前工作状态

- **上一主线完成**：LLM 并行化 + 同步异步（Stages 1-4 + `await` 表达式 + PT-SEM-4 + PT-4.2 + PT-SYNC-1/2/3 + PT-TEST-9），已推送。
- **下一主线确立**：IBCI 运行时多线程 + 统一通信机制（Channel/Signal/Slot）+ 内省/控制 + 多 VM 实例 + 编译器改造。
- **分支**：`unsafe-vibe-dev`（唯一活动分支）。
- **测试基线**：以实跑为准；当前全量 `python -m pytest tests/` = **1322 passed / 4 skipped**（约 26s）。

## 二、已完成（本次会话，已推送）

### 上一主线（LLM 并行化 + 同步异步）
- Stage 1：executor 共享状态去共享化（`_current_call_info` 主线程单写槽、`_result_parser` fail-fast、`scene` 参数删除）
- Stage 2：`TaskScheduler` 多任务协作调度器 + `run_many` + 结果按提交序 + `TaskScheduler` 测试
- Stage 4：宿主异步统一 `Waitable` 协议（`HostAwaitable`/`box` 透传/`vm_handle_IbCall` yield/统一 API）
- Stage 3：语言级 `await` 表达式（lexer/AST/parser/semantic/VM 五层）
- PT-SEM-4：`resolve_call_return` 兜底双通道收敛
- PT-4.2：`__call__` 协议 3 文档定性统一
- PT-SYNC-1/2/3、PT-TEST-9
- Stage 1 三项核验（parse_result 线程安全 / `_prompt`+`_llm_function` 无实例级可变状态 / 意图 fork 隔离完整）

## 三、下一主线设计（已定，见 `tasks_docs/THREADING_DESIGN.md`）

**核心**：一等通信机制（Channel/Signal/Slot）+ 内省（快照+事件流）+ 控制（统一启停）+ 多 VM 实例 + 用户代码多线程 + 编译器改造。接受破坏性改造。

**任务序列（PT-MT-*）**：
1. **PT-MT-1 详细设计文档**（先经用户审阅）→ 2. PT-MT-2 编译器地基 → 3. PT-MT-3 统一通信内核 → 4. PT-MT-4 内省层 → 5. PT-MT-5 控制层 → 6. PT-MT-6 流式+并行 → 7. PT-MT-7 多 VM 实例 → 8. PT-MT-8 用户代码多线程

**下一步（开工）**：产出 **PT-MT-1 详细设计文档**（架构/AST 变更/接口/并发正确性/测试策略），经用户审阅后落地实现。

## 四、关键约束与原则（必须遵守）

- **交付纪律**：本次已推送；后续 push 需用户明确允许（除非用户再次授权）。
- **决策纪律**：需用户拍板的决断项可大胆激进选方案；底线=架构原则/代码质量原则/非妥协/非 tricky/非临时兼容层/大方向主线。
- **工作模式定论**：禁 compat shim/胶水/tricky/过程式硬编码；质量优先；原则优先于行为维持；可推翻 IBCI 自身设计缺陷。
- **文档治理**：设计/决策先写任务控制文档（`tasks_docs/`），**不写进技术手册 `docs/`**（用户明确要求）；落地后按治理择机写入。
- **隔离运行的自我进化窗口**：跨引擎通信现阶段不做，保持文件/序列化机制，仅维护 + 同步演进。
- **不做跨进程/CPU 并行**（性能瓶颈在 IBCI 包装）。
- **工作流**：每任务走 code-workflow Phase 0-5 + 质量门 + 全量 pytest 零回归。

## 五、待决项 / 待清理

- **待决**：PT-MT-1 详细设计文档产出后需用户审阅（尤其编译器改造范围、多 VM 实例共享只读数据边界）。
- **待清理**：本 `_HANDOFF.md` 交接后删除。
- **非目标**：media Phase 4、跨进程/CPU 并行、跨引擎通信、完整通用异步（async 函数/生成器）。

---

> 交接完成阶段：本文件由下一 session 交接后删除。