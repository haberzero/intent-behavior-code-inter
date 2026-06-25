# PENDING_TASKS — 阻塞 / 待前置任务的未来规划

> 本文档记录**暂时搁置但经过验证仍有有效性的规划**——每项都有明确的阻塞原因或前置条件。
> 当前最紧要项见 `docs/NEXT_STEPS.md`；已完成事项见 `docs/COMPLETED.md`。
>
> **最后更新**：2026-06-25（PT-ARCH-5 G3 薄提取 / PT-ARCH-10 审计 / PT-TEST-4 全部 5/5 / IbDict 统一 标记完成）
>
> **阅读指南**：
> - 标为 `[P1]` 的条目：前置条件已满足，可由 `NEXT_STEPS.md` 随时提升为当前任务
> - 标为 `[P2]`/`[P3]` 的条目：有明确前置链，需按序解锁
> - 标为 `[VISION]` 的条目：远期愿景，当前无明确用户需求推动
> - 标为 `[DESIGN-DEBT]` 的条目：已有部分基础设施但存在未解决的设计冲突
> - 标为 `[SHELVED]` 的条目：明确搁置，有独立文档记录设计思路
> - 标为 `[DONE]` 的条目：已完成，保留供追溯（将在下次清理时移除）

---

## 一、Semantic Pipeline 后续演进

### PT-SEM-1　生产就绪化 [P2]

> 本条目的完整规划以此处为准；NEXT_STEPS 中仅保留指针（遵守单点真理规则）。

**前置条件**: Semantic 4-Phase pipeline 已稳定运行 ✅

**具体待做**：
1. **错误信息优化**：`SEM_xxx` 错误码转化为用户友好表述
2. **诊断工具**：符号表/类型绑定/行为依赖图 JSON/dot 导出
3. **性能基准**：编译时间基准测试
4. **CI/CD 集成**：语义分析测试套件纳入 CI

**预估工作量**: 15-20 小时

---

### PT-SEM-2　CompilationResult 字段精简 [P3]

**前置条件**: PT-SEM-1 完成 + pipeline 稳定运行 ≥ 1 个月

---

### PT-SEM-3　二层 IR 路线评估 [VISION]

---

## 二、VM 异步/协程层（L3）[SHELVED]

> **独立设计文档**：`docs/COROUTINE_DESIGN_NOTES.md`
> **搁置决策日期**：2026-05-28
> **搁置原因**：当前优先完善多模态功能（Phase 3-5）

> ⚠️ **2026-06-24 全量分析补充**：
> - 搁置理由"dispatch_eager + LLMFuture 已覆盖主要异步需求"有漏洞：`handlers.py` 在 llmexcept 活跃时禁用 dispatch
> - 11 个 `test_e2e_multi_interpreter` 测试与 PT-3.1 相关（已在 P0 修复中解决路径转义问题，测试全绿）

### 阻塞原因
1. 调度器架构需从单根任务升级为多任务挂起/恢复
2. `async`/`await`/`yield` 关键字不在 KEYWORDS 表
3. 快照协议需覆盖协程 yield 点

### 被阻塞的子项

| 编号 | 标题 | 依赖 L3 的原因 |
|------|------|---------------|
| PT-3.1 | `host.run_isolated()` 返回值改进 | 需要协程句柄实现异步等待 |
| PT-3.2 | `ReceiveMode` 枚举演进 | 需要 yield/resume 语义 |

### 恢复条件
详见 `docs/COROUTINE_DESIGN_NOTES.md §六`。核心前提：多模态 Phase 3-5 稳定后 + 出现明确用户需求。

---

## 三、语言级能力扩展

### PT-4.1　Enum 非 str 成员 + 迭代能力 [VISION]

> ⚠️ **2026-06-24 质疑**：原"95% 覆盖"声明未经验证。`primitives.py` 把成员值一律设为名字字符串，数字状态码枚举无法 round-trip。

---

### PT-4.2　`__call__` 协议类型推断一致性 [VISION]

> ⚠️ **2026-06-24 备注**：`__call__` 协议在 3 个文档有 3 种不同定性（KNOWN_LIMITS §一"建议禁用"、AUDIT_REPORT"已知缺陷"、本条目"VISION"），框架应统一。

---

### PT-4.3　语言级协程 [SHELVED]

见 §二 + `docs/COROUTINE_DESIGN_NOTES.md`。

---

### PT-4.4　用户类泛型类型参数 [VISION]

---

### PT-4.5　用户类运算符重载 [VISION]

---

### PT-4.7　DDG 并行调度真正接入 VM [DESIGN-DEBT]

> ⚠️ **2026-06-24 修正**：原"snapshot × future-deref"误诊。真实失败模式是 `dispatch_eager` 捕获 `execution_context` 按引用传递给后台线程 → 数据竞争。与 L3 同根因。

---

## 四、设计原则与明确排除方向

### 坚持的设计原则

1. **显式优于隐式**
2. **单点真理**
3. **公理调度 + 单次锁定**
4. **运行时可观测性优先**

> ⚠️ **2026-06-24 备注**：
> - 原则 1 在 `ibci_ai/core.py` 有违反（未探测模型静默 `is_reasoning_model = True`）—— ADR-010 已决策修复方案
> - 原则 4 在多模态设计中有冲突（D3 磁盘卸载透明性 vs 可观测性）—— ADR-007 已裁决

### 明确排除的方向

- ❌ 静态类型检查器作为解释器前置强依赖
- ❌ 为优化独立 LLM 调用而创建多 Interpreter
- ❌ 完整的 HM 风格类型推断
- ❌ AST 字段 + 侧表 + MetadataStore 三处同时存储同一语义事实

> ⚠️ **2026-06-24 备注**："静态检查器非强依赖"排除正变得自相矛盾——4-Phase pipeline 已达 ~1491 行 type_checking_pass。

---

## 五、架构健康改善项

> 来源：2026-06-24 全量分析。**大部分已完成**，此处仅保留未完成项。

### [DONE] PT-ARCH-1 提取 `core/runtime/shared/` ✅
### [DONE] PT-ARCH-2 拆分 `HostInterface` ✅
### [DONE] PT-ARCH-3 移动 `fuzzy_json.py` ✅
### [DONE] PT-ARCH-4 拆分 7 个 god modules ✅（全部 7 个已完成）
### [DONE] PT-ARCH-5 Group 1+2 折叠重复分支 ✅

### PT-ARCH-5 Group 3　CPS/non-CPS 薄提取 [部分 DONE — 薄提取 ✅ / 深统一推迟]
- ✅ 薄提取（2026-06-25）：提取 `LLMExecutorCore._finalize_invoke_result`，4 个 `invoke_*` 后处理统一。
- ⏳ 深统一（3 对 `execute_*`，~100 行/对）仍推迟：需先统一 `_evaluate_segments`/`_cps` 段求值器，~6h，风险较高。无用户需求推动时可继续推迟。

---

### [DONE] PT-ARCH-7　静默吞异常治理 ✅（2026-06-25）
- Phase 1-3：7 处关键修复 + 4 处裸 except: 收窄（core/ 中零裸 except:）。
- Phase 4-5：11 处 `except Exception: pass` → `core_debugger.trace` 可观测化（`_prompt.py`×3 / `base.py`×2 / `_shared.py`×3 / `engine.py` / `interpreter.py` / `media.py`）。`_scheduler.py __del__` 按惯例保持静默。
- 附带：IbDict 缺键 `KeyError` → `InterpreterError` 统一 + 删除一处重复 `__getitem__`。

### [DONE] PT-ARCH-10　剩余 ~24 处 except Exception 审计 ✅（2026-06-25）
- 审计 core/ 的 ~35 处 `except Exception:`：12 处真静默补日志（`runtime_serializer`×4 / `host/service`×2 / `auto_discovery`×1 / `llm_except_frame`×2 / `intent`×1 / `llm_parsing_strategy`×2）；~11 处确认非静默（已 re-raise/log/record）；~4 处编译层错误恢复保留；2 处良性（`module_manager:88` 有 raise、`io:27` stdout best-effort）。
- **结论**：运行时层无一处掩盖真实 bug 的漏网吞异常。

---

### [DONE] PT-ARCH-6 删除死代码 ✅
- `IbStatelessPlugin` 删除
- `IbInteger.__hash__` 修复
- `_check_type` 死分支删除

### [DONE] PT-ARCH-8 → 推迟　`CapabilityRegistry` 类型化键 [P3]
**现状**：字符串键 service locator，无真实多 provider 竞争用例。低优先级。

### [DONE] PT-ARCH-9 → 推迟　`AutoDiscoveryService` 健壮性 [P3]
**现状**：一个 broken plugin 中止全部 discovery。低优先级。

---

## 六、Phase 3 多模态决策 [DONE — ADR-007~012]

> 全部 7 个决策矛盾已通过 ADR 解决：
> - ADR-007: snapshot 策略（DEC-5/6 裁决）+ 代码修复 `type() is` → `isinstance`
> - ADR-008: `register_model` API 形态（D4 裁决）
> - ADR-009: `_call_llm_raw` 引入（D6/DEC-4 裁决）
> - ADR-010: per-model 能力探测（R5 裁决）
> - ADR-011: `runtime/shared/` 叶子包
> - ADR-012: 多模态类型作为普通类名（DEC-1 裁决）

---

## 七、文档健康改善项

> 来源：2026-06-24 全量分析。**部分已完成**。

### [DONE] PT-DOC-1 标注 AUDIT_REPORT 已解决发现 ✅
### [DONE] PT-DOC-2 修复 hub 文档锚点 ✅
### [DONE] PT-DOC-3 IBCI_SYNTAX_REFERENCE 补充 ✅（`@NAME~` + `__payload_prompt__`）
### [DONE] PT-DOC-5 SEMANTIC_COVERAGE_MATRIX 刷新 ✅
### [DONE] PT-DOC-6 VM_SPEC 幽灵引用修复 ✅

### PT-DOC-4　ARCH_DETAILS.md §1.2 更新 [P2]
- "if/while 检测 uncertain → 立即返回空结果"已更新为 BUG #A 后语义 ✅
- 但 §1.2 整体仍需与当前 handler 分包结构对齐

### PT-DOC-7　清理 HISTORY_LOG 旧编号 [P3]
- 4 处引用 KNOWN_LIMITS 旧编号（§十九/§二十三/§二十四/§二十五）→ 死指针

### PT-DOC-8　README 补全 [P2]
- 补测试命令 `python -m pytest tests/ -q --tb=short`
- 补架构概览 + 链接 NEXT_STEPS/COMPLETED
- 加 CONTRIBUTING.md

### PT-DOC-9　评估合并/删除小文档 [P3]
- `FUNC_DESIGN_NOTES.md`（48 行，冻结）→ 评估合并入 KNOWN_LIMITS
- `MULTIMODAL_ANALYSIS_CONCLUSIONS.md`（已归档）→ 评估删除

### PT-DOC-10　TYPE_SYSTEM_DESIGN.md §5.1 更新 [P3]
- "Pass 4/5 SemanticAnalyzer" → 4-Phase pipeline

### PT-DOC-11　VM_AND_INTERPRETER_DESIGN.md §12 更新 [P3]
- "目前无新增 P0/P1/P2" → 更新为当前状态

---

## 八、测试基础设施改善项

> 来源：2026-06-24 全量分析。**部分已完成**。

### [DONE] PT-TEST-1 pytest.ini + CI ✅
### [DONE] PT-TEST-2 层级元测试 + 文件迁移 ✅
### [DONE] PT-TEST-3 MOCK 独立测试 ✅
### [DONE] PT-TEST-4 Area 3 (path) ✅（85 个测试 + 5 个 bug 修复）
### [DONE] PT-TEST-5 BUG #A 回归测试 ✅
### [DONE] PT-TEST-9 IbString.to_bool 越层修复 ✅

### [DONE] PT-TEST-4　覆盖缺口填补 ✅（2026-06-25，5/5 全部完成）

| # | 区域 | 测试数 | 状态 |
|---|------|--------|------|
| 1 | `runtime/serialization/` round-trip | 11 | ✅（+1 反序列化 bug 修复） |
| 2 | `engine.py` 生命周期 | 7 | ✅ |
| 3 | `kernel/__getitem__` 契约 | 13 | ✅（+ IbDict 错误统一） |
| 4 | `host/service.py` collect 委托 | 4 | ✅ |
| (Area 3) | `runtime/path/` | 85 | ✅（早前完成，+5 盘符 bug） |
> 详见 `docs/COMPLETED.md` 2026-06-25 条目。本会话累计 +46 测试，暴露并修复 2 个潜伏回归 bug。

### PT-TEST-6　删除死 fixtures + 统一 MOCK 前缀 [P3]
- 3 个 orphan fixtures 无测试导入
- `AI_SETUP` 重复定义

### PT-TEST-7　清理 stale 引用 [P3]
- `tests/kernel/conftest.py` 引用不存在的文件
- `tests/COVERAGE_MAP.md` 计数过时

### PT-TEST-8　修复测试命名违规 [P3]
- 6 个 `TestM2*`/`TestD3*` 类名违反 `tests/README.md` 规范
