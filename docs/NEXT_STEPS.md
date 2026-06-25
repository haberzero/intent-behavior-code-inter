# NEXT_STEPS — 当前最紧要项

> 本文档**只**记录当前周期内最紧要、可立即开工的下一步。
> 阻塞 / 等前置项见 `docs/PENDING_TASKS.md`；历史归档见 `docs/COMPLETED.md`。
> 已知语言级限制见 `docs/KNOWN_LIMITS.md`。
>
> **最后更新**：2026-06-25（PT-ARCH-7 治理 + IbDict 错误统一完成；即时 P0/P1 清空；基线 1057 passed）

---

## 当前测试基线（每次开新分支前必须复跑确认）

```bash
python -m pytest tests/ -q --tb=no --no-header
```

**2026-06-25 实测结果**：`1057 passed, 5 skipped`（0 failures，无环境变量 workaround）

> ✅ 基线可信。5 个 skipped：2 个设计限制（`INV-LAMBDA-3`/`INV-SCOPE-1`）+ 3 个层级元测试白名单（混合文件待拆分）。

---

## ✅ P0 已完成（2026-06-25）：Phase 3 多模态 — 用户面 I/O API + e2e 测试

> 详见 `docs/COMPLETED.md` 2026-06-25 条目。
> 实际工时：~5 小时（实现 + e2e）+ ~2 小时（注册缺口排查与修复）。原"3-5 天"估时严重高估。
> **重要发现**：e2e 测试暴露并修复了三处 Phase 3 注册断链（IbSpec 缺口 / get_axiom 调用错误 / 闭包晚绑定）—— 此前"注册路径已完成"的声称不实。

---

## ✅ P0 已完成（2026-06-25）：PT-TEST-4 覆盖缺口填补（5/5 全部完成）

> 详见 `docs/COMPLETED.md` 2026-06-25 条目。
> 5 个区域：`runtime/path`（85 测试 + 5 bug）/ `serialization`（11 测试 + 1 bug）/ `engine` 生命周期（7 测试）/ `__getitem__` 契约（13 测试）/ `host/service collect` 委托（4 测试）。
> **累计 +120 测试，修复 2 个潜伏回归级 bug**（反序列化协议混淆；Phase 3 注册三处断链另计）。

---

## ✅ P0 已完成（2026-06-25）：PT-ARCH-7 Phase 4-5 静默吞异常治理 + IbDict 错误统一

> 详见 `docs/COMPLETED.md` 2026-06-25 条目。
> PT-ARCH-7：11 处 `except Exception: pass` → `core_debugger.trace` 可观测化（纯日志，无行为变更）；`_scheduler __del__` 按惯例保持静默。
> IbDict：缺键 `KeyError` → `InterpreterError` 统一（附带删除一处重复 `__getitem__` 定义）。
> **发现**：core/ 实际 ~35 处 `except Exception:`（文档曾称 10），剩余 ~24 处多为编译层错误恢复，已记入 PENDING_TASKS 作独立审计。

---

## P0（当前最紧要）：PT-ARCH-5 Group 3（CPS/non-CPS 薄提取）

> Group 1+2 已完成。Group 3 剩余 5 对 sync/CPS 方法。即时高优先项（Phase 3 / PT-TEST-4 / PT-ARCH-7）均已清空，此项从 P2 提升。

**可做**：2 对薄 `invoke_*` 方法（各 7-18 行，委托到 `execute_*` + 相同后处理）→ 提取共享后处理 helper
**推迟**：3 对 `execute_*` 方法（各 ~100 行，body 90% 相同但 segment evaluator 不同）→ 需先统一 `_evaluate_segments`/`_evaluate_segments_cps`

**预估工作量**：薄提取 ~2h；完整统一 ~6h（推迟）

---

## P3 候选（远景；详见 PENDING_TASKS）

- 多模态 Phase 4：`media` 全模态容器 + 响应解析
- 多模态 Phase 5：磁盘卸载与生命周期管理
- `isinstance()` 运行时类型检查
- 二层 IR 路线
- 用户级泛型 (`class Box[T]:`)
- 协程层（搁置中，详见 `docs/COROUTINE_DESIGN_NOTES.md`）

---

## 确认为设计决策（不修复）

| 测试 ID | 原因 | 处理 |
|---------|------|------|
| **INV-LAMBDA-3** | IBCI 无 walrus (`:=`) / lambda 体赋值语法 | 保持 SKIP，标注为"设计限制" |
| **INV-SCOPE-1** | SEM_002 禁止 if-block 内重声明同名变量 | 保持 SKIP，标注为"设计限制" |

---

## 工作规则

- **每次开新分支前**，先复跑 `python -m pytest tests/ -q --tb=no --no-header`，把当前 pass/fail 计数写在 PR 描述里。
- **跨盘环境注意**：`conftest.py` 的 `pytest_configure` 已将 basetemp 设为 repo 下 `.tmp_pytest`，无需手动设置环境变量。
- 同一时刻只主推一项 P0 任务（或一项 P1）；其余项保留待选。
- 任何改动公理层公约或语义错误集的任务，需在分支早期跑全量 pytest 评估破坏面。
- 每项完成后，把摘要追加到 `docs/COMPLETED.md`，并把对应条目从本文件移除。
- **本文件不冻结具体测试通过数字**——任何"X 测试通过"的表述都必须附运行命令或日期锚点。

---

## 维护守则

1. **先复跑、后下结论**。任何关于"测试基线红线"的表述，必须以"附完整 pytest 输出 + 日期 + 分支 + 环境条件"的方式说服读者。
2. **不要相信"昨日完成"的总结**。`docs/COMPLETED.md` 的最新一两条锚点，必须能用一条具体 git 提交或一次具体 pytest 输出佐证。
3. **示例必须可零配置跑通**。任何"用户跟着 README 复制粘贴"的代码块，必须在 mock 模式下端到端跑通。
4. **已知 bug 与已修 bug 之间要勤更**。
5. **跨文件状态保持一致**。`README.md`、`docs/KNOWN_LIMITS.md`、`docs/IBCI_SYNTAX_REFERENCE.md`、`docs/METADATA_ARCHITECTURE.md` 之间对同一语法/限制/架构立场的描述必须用同一组事实。
6. **避免重复声明、单点真理**。一条已完成项写一次（在 `COMPLETED.md`），一条已知限制写一次（在 `KNOWN_LIMITS.md`），一条紧要项写一次（在 `NEXT_STEPS.md`），一条搁置项写一次（在 `PENDING_TASKS.md`）。
7. **新增 AST 字段或侧表前必须先在 `METADATA_ARCHITECTURE.md` 中查证**。
8. **重大架构决策必须写 ADR**。新增决策在 `docs/decisions/` 建对应 ADR 文件。
