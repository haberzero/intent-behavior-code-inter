# _DOC_HEALTH_20260811 — docs/ 全量健康检查与完善

> 依据 doc-governance skill Phase 0-8 + docs/WRITING_GUIDE.md。5 并行 subagent 全量审计（45 篇，禁止抽检）。
> 事实矛盾以代码为最高真相。范围：docs/ 全部 + WRITING_GUIDE 自身。

## Phase 2 审计发现汇总（合并去重）

### P0（红线违规 / 事实矛盾 / 死代码引用）——立即修复
| # | 位置 | 问题 | 修复 |
|---|------|------|------|
| P0-1 | `WRITING_GUIDE.md:11` | 规范自身含日期戳+里程碑代号 `（2026-08-06，OBSERVABILITY_REFACTOR 4）`，自相矛盾 | 删括号，留功能表述 |
| P0-2 | `KNOWN_LIMITS.md:548` | 残留任务编号 `（PT-DEBT-9）` | 删编号，留功能 |
| P0-3 | `architecture/02_metadata_ast.md:195` | 残留任务编号 `（PT-FEAT-10）` | 删编号，留功能 |
| P0-4 | `architecture/04_vm_interpreter.md:244` | 引用已删除同步 `execute_behavior_expression()` | 改 `execute_behavior_expression_cps`（CPS 帧内） |

### P1（红线/格式/跨层泄漏/一致性）
| # | 位置 | 问题 |
|---|------|------|
| P1-1 | `syntax/14_concurrency.md:118` | "类构造不自动挂起" 与 A5 冲突 → 限定"含原生 __init__ 的类（thread）" |
| P1-2 | `architecture/01_principles.md:335-354` | §7.3.3 完整类实现代码（跨层泄漏 A.7） |
| P1-3 | `architecture/01_principles.md:125-126` | E9 混合抽象层级（轻度） |
| P1-4 | `architecture/03_type_system.md:133` | E2 历史演变 + E3 完成标记 |
| P1-5 | `architecture/04_vm_interpreter.md:195/193/194/233` | E3 完成/状态标记 |
| P1-6 | `architecture/04:6` + `01:470` + `03:5` + `05:7` | E2 历史演变（"已重构为包"） |
| P1-7 | `architecture/09_observability.md:149` | 章节编号 `四·五` 不一致 |
| P1-8 | `architecture/09 §3.4` | KDIAG 码表不完整（缺 KDIAG_RUNTIME_ENV_LIMIT），与 syntax/15 分裂 → 标注唯一码源 |
| P1-9 | `syntax/06_oop.md` vs `KNOWN_LIMITS §六` | auto-init/super 边界多处描述 → 归属唯一化 |
| P1-10 | `subsystems/05_coroutine.md` | E3/E7 整篇状态/完成文档 |
| P1-11 | `subsystems/01_intent_system.md` | E9 语法使用说明 + L620 断链（kernel.py 不存在） |
| P1-12 | `syntax/05_functions.md:32` vs `07:131-135` | `-> auto` 推断矛盾 |
| P1-13 | `syntax/04_control_flow.md:201,211` | 小节编号错位 |
| P1-14 | `syntax/15_diagnostics.md` | 条目格式/标题层级不一致 |
| P1-15 | `syntax/11_modules.md` §11.3-11.9 | 平行模块小节未遵循 §D 模板 |
| P1-16 | `syntax/15:23` + `13_mock_testing.md:201-202` | E9 实现模块路径出现在 syntax 层 |

### P2（改善/变更反映/读者旅程/体系）
| # | 位置 | 问题 |
|---|------|------|
| P2-1 | `architecture/04/05` | A5 类构造帧内 CPS 未文档化（变更反映缺口） |
| P2-2 | `README.md §二` | 阅读路径未涵盖 howto/subsystems/diagnostics |
| P2-3 | howto 层仅 2 篇 | 生成器/并发/llmexcept/隔离缺操作指南 |
| P2-4 | `subsystems/01` L203/257/616 | 已删除文件/错误位置引用 |
| P2-5 | `subsystems/01:536` | E7 验证记录 |
| P2-6 | `subsystems/02:47/162` + `04:52` | E4 未实现设计（已标注，评估） |
| P2-7 | `guide/02:101` + `03:122` | 死引用定义 |
| P2-8 | `KNOWN_LIMITS.md:351` | "当前状态" 标签 |
| P2-9 | `howto/debug_llm_calls.md:78` | 指针不精确（§四→§4.1） |
| P2-10 | `01_principles.md:102` | "应该" 未标注推测 |
| P2-11 | `03_type_system.md:3` | 定位段薄弱 |
| P2-12 | `09_observability.md:149-165` | TestHooks 表未按模板 |

## Phase 4 执行顺序
1. P0（红线 4 处）
2. P1（红线/一致性/跨层）
3. P2（改善 + A5 变更反映 + 读者旅程 + howto 补充）
4. Phase 5 交叉核验扫描
5. Phase 6-7 读者视角 + 体系建设
6. Phase 8 最终复查 + 汇报

## 执行进度（2026-08-11，因用户要求暂停文档工作，改为晚上自主进行）
**已完成（本次已提交）**：
- P0-1 WRITING_GUIDE.md:11（删日期戳+代号）
- P0-2 KNOWN_LIMITS.md:548（删 PT-DEBT-9）
- P0-3 architecture/02_metadata_ast.md:195（删 PT-FEAT-10）
- P0-4 architecture/04_vm_interpreter.md:244（execute_behavior_expression → _cps）
- P1-1 syntax/14_concurrency.md:118（类构造例外限定原生 __init__）
- P1-4 architecture/03_type_system.md:133（删"旧...已彻底删除"）

**剩余待做（晚上自主，按 P1→P2 顺序）**：
- P1-2/3 01_principles.md（§7.3.3 类代码跨层泄漏、:125-126 E9）
- P1-5/6 04_vm_interpreter.md:195/193/194/233（E3 状态标记）+ 各文件"已重构为包"（E2）
- P1-7/8 architecture/09（章节编号四·五、KDIAG 码表唯一码源标注）
- P1-9 syntax/06_oop vs KNOWN_LIMITS §六（auto-init/super 归属）
- P1-10 subsystems/05_coroutine.md（E3/E7 状态文档）
- P1-11 subsystems/01_intent_system.md（E9 语法说明 + L620 断链）
- P1-12 syntax/05_functions.md:32 vs 07（-> auto 推断矛盾）
- P1-13/14/15 syntax/04/15/11（小节编号、条目格式、平行模板）
- P1-16 syntax/15:23 + 13_mock_testing.md:201-202（E9 模块路径）
- P2-1~12（A5 变更反映、README 读者旅程、howto 补充、死引用、定位段等）

## 干净文件（无需改动）
ARCHITECTURE.md、06/07/08_path、syntax/01/02/03/06/08/09/10/12、SYNTAX_REFERENCE.md、guide/00/01/04/05/06/07、howto/write_user_plugin.md、subsystems/03、README.md
