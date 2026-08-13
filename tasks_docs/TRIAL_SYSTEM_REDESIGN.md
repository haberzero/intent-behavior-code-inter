# TRIAL_SYSTEM_REDESIGN — 试用体系重构任务控制文档

> 2026-08-13 编制。用户指示（2026-08-13）：试用体系规范化必须**成体系重构**（用例/监控/
> 命名/报告全维度），未来并入自动化测试体系；重命名/代号/文档报告规范化**不留历史包袱、
> 干净彻底**。本文件记录回顾分析结论 + 重构方案 + 执行状态（单一权威源）。

---

## 一、回顾分析结论（用户质询"试用例修改合理性"后的深度自审）

### 1.1 试用例修改的合理性判定框架

| 判据 | 合理 ✅ | 危险 ⚠️/❌ |
|------|--------|-----------|
| 修改依据 | 被测系统语义**正确变化**（修复后符合新契约） | 为通过而绕开真实缺陷 |
| 覆盖影响 | 覆盖不丢失（被改路径另有用例） | 被绕过的路径从此无证据 |
| 历史证据 | 原始脚本/logs/register 冻结保留 | 历史证据与脚本脱节、不可复现 |
| 记录 | 变更原因 + 变更前后记录 | 静默修改 |

**方法论铁律**（本 session 教训，写入 CLASSIFICATION 规范）：
- **历史试用 = 冻结资产**：用例脚本、logs、register 一旦归档不得改动（历史证据）。
- **语义变更 = 新用例**：被测系统行为正确变化后，用**新增用例**（如 `R1-05b`）验证，
  不修改历史用例。
- **真实缺陷 = 保留触发用例**：发现真实缺陷时，触发用例**不得被简化规避**——保留并标注
  `KERNEL_ISSUE` 分类，作为缺陷持续复现证据；修复后由回归试用核销。
- 修改/新增用例必须记录：变更原因、变更前后（实现 + 测试 + 文档）。

### 1.2 本 session 操作评价（自审）

| 操作 | 评价 | 处置 |
|------|------|------|
| R1-05/R5-01 单参→多参 | 合理（G3 语义正确变化适配）但方法缺陷 | **恢复原始脚本**，新增 `R1-05b` 等适配用例 |
| R5-04 while 哨兵修正 | 合理（该模式在 Node[int] 编译期不可行，从未可验证） | 恢复原始脚本（保留历史证据），新用例覆盖合法遍历 |
| R5-04 Box[list[int]]→Box[int] 简化 | **危险——修改用例规避真实缺陷 GEN-5** | 恢复原始；**新增 GEN-5 独立触发用例**（标注 KERNEL_ISSUE） |
| register.jsonl classification 0% | 流程缺口：人工判定未回流机械记录 | Phase B 断言自动化 + Phase C 补齐 |

### 1.3 体系化差距（现状 vs 要求）

| 维度 | 现状 | 体系化要求 |
|------|------|-----------|
| 用例 | 无断言，PASS 靠人工判定 | **用例即契约**：期望输出/退出码/诊断码，harness 自动判定 |
| 监控 | 死循环保护 + 机械记录 | + 断言监控 + 覆盖矩阵 + 缺陷闭环状态机 |
| 命名 | 缺陷编号统一；用例 ID 三套混用（D1-01-001/R1-01/T1） | 单一命名体系（试用/维度/用例/缺陷全统一） |
| 报告 | REGISTER 人工汇总 | 自动生成骨架 + 人工结论 |
| 自动化衔接 | 无 | 用例→契约断言，缺陷收敛为 tests/ 回归测试 |
| 缺陷闭环 | 人工搬运 PENDING_TASKS | 发现→登记→修复→回归→核销 状态机 |

### 1.4 干净彻底清单（历史包袱清零）

1. **旧编号 85 处 + 旧路径 42 处**全量替换（`KERNEL_ISSUE-<域>-<n>` / `trials/T0x`），
   旧编号旧路径只存在于 git 历史。
2. 用例 ID 统一重编号（历史套标注"历史编号"，新套用统一格式）。
3. register.jsonl classification 写回（0%→100%）。
4. 过时设计文档归档/重写：`TRIAL_SYSTEM_DESIGN.md`（已实施的设计起点）、历史报告
   （`_REAL_LLM_TRIAL_REPORT_20260812.md` 等）→ `trials/archive/` 或标注历史。

---

## 二、重构方案（阶段计划）

### Phase A — 立即纠正（历史证据完整性）✅ 执行中
1. 恢复 R1-05/R5-01/R5-04 为原始版本（git 还原，历史证据冻结）。
2. 新增适配用例（`R1-05b` 多参构造 / `R5-04b` 合法遍历 / GEN-5 触发用例）。
3. GEN-5 触发用例标注 `KERNEL_ISSUE` 分类，缺陷有持续复现证据。

### Phase B — 体系重构（用例即契约）
1. 用例格式升级：`.ibci` + 期望断言（期望输出/退出码/诊断码），harness 自动判定，
   classification 自动填充（消除 0%）。
2. 覆盖矩阵规范：D1-D3 维度映射到 `docs/syntax/01-15` 特性清单，追踪覆盖缺口。
3. 缺陷闭环状态机：`KERNEL_ISSUE-<域>-<n>` 状态（发现/登记/修复/回归/核销），
   `trials/INDEX.md` 为单一状态权威。

### Phase C — 干净彻底（历史包袱清零）
1. 旧编号/旧路径全量替换。
2. 用例 ID 统一重编号。
3. register.jsonl classification 写回。
4. 过时设计文档归档/重写。

### Phase D — 自动化衔接
1. 试用→确定性测试收敛流程规范化（发现缺陷必须落 `tests/` 回归）。
2. 报告自动生成（register.jsonl 为数据源 → REGISTER 骨架）。

---

## 三、执行状态

| 阶段 | 状态 | 记录 |
|------|------|------|
| Phase A-1 恢复历史用例 | ✅ 完成 | commit 25365e63 |
| Phase A-2 新增适配用例 | ✅ 完成 | R1-05b/R5-01b/R5-04b（同上） |
| Phase A-3 GEN-5 触发用例 | ✅ 完成 | GEN5-01（同上，根因方向精确化：表达式位置特化注册缺失） |
| Phase B 用例即契约机制 | ✅ 完成 | harness 断言自动判定 + CONTRACT_FORMAT + run_batch 分层并发（f31ee634/09a8eca0/3f0f4d3d） |
| Phase B 断言迁移 | ✅ T04/T03/T02 | 32+29+9 用例判定已验证 |
| Phase B 断言迁移 | ✅ T01（2026-08-13 真实重跑） | 57 个 LLM 用例真实重跑 **55 PASS + 2 GUARD**（零 HARNESS/零缺陷复现）；断言从基线 `DONE` 精化为确定性行；修复 8 个脚本缺陷（5 import 位置 + 2 守卫断言 + 1 API 类型）；child_llm F9 适配 |
| Phase C 干净清理 | ✅ 过期文档删除（2026-08-13） | 用户裁定：任务控制文档不做编号替换；直接删除 40 个过期文档（设计/报告/审计/记录/临时 `_code_*`），git 历史保留可追溯 |
| Phase C 干净清理 | ✅ 套件重构 + classification 写回（2026-08-13） | 用户原则：**不冻结历史资产，问题直接重构**（唯一底线：不为规避缺陷改套件，缺陷触发用例保留）。T02 T3/T4/T5 断言重构（映射有效性）；T04 R1-05/R5-01/R5-04 重构为修复后语义、删 b 变体；4 套 register.jsonl classification 100%（T01 55 PASS+2 GUARD / T02 8 PASS+1 LIMIT / T03 22 PASS+6 GUARD+1 KI+1 HARNESS / T04 24 PASS+7 GUARD+1 KI+1 HARNESS） |
| Phase D 自动化衔接 | ✅ 设计+工具落地（2026-08-13） | `_toolkit/gen_register.py` 报告生成器（register.jsonl→REGISTER 骨架）+ 收敛流程硬规则落档 `_toolkit/PHASE_D_AUTOMATION.md`（缺陷修复=根因修复+tests/ 回归双交付验收门） |

---

## 五、本 session 发现的潜藏 bug（试用迁移/调试期）

| 编号 | 严重级别 | 现象 | 状态 |
|------|----------|------|------|
| **KERNEL_ISSUE-GEN-5** | P2 | 用户泛型类下标在**表达式位置**（`type(Box[list[int]])`）编译期未注册特化 spec → 运行时 `_specialize` 报 "no registered specialization"（注解位置正常） | 待修复，独立窗口，触发用例 `GEN5-01` |
| **KERNEL_ISSUE-GEN-6** | P1 | 泛型**运算符方法参数含 T**（`__add__(self, Vec[T] other) -> Vec[T]`）特化未生效（G1 修复不完整，T04 回归参数均为裸 T 未覆盖此形态）→ `Cannot assign 'Vec' to 'Vec[int]'` | 待修复，独立窗口，触发用例 `D2-01` |
| **G3 语义变更破坏面** | — | chain-aware auto-init 使"依赖 auto-init 只收自身字段"的既有用例构造参数变化 → T03 D2-02 / T01 D2-30 / T03 D3-04 已适配多参构造/默认值 | 已适配 |
| **Finding C**（any 用户类复查） | — | `_check_type` 对用户类目标跳过运行时复查，any 静默流入 → 已修复（b0f4d74） | 已修复 |
| **LLM 运行配置缺失旧文案** | — | F9 后忘记 load_project_config 的提示只提 set_config → 已统一引导（2a259d8e） | 已修复 |
| **思考禁用失败**（qwen3.6 强制思考） | — | LM Studio 上 enable_thinking 全参数无效；已实现禁用失败警告 + 用户已手动应用禁用思考预设 | 警告已实现；供应商感知机制待设计 |
| **run_one SIGKILL 兜底** | — | SIGKILL 后 communicate 卡住（顽固子进程）→ 已加最终超时兜底 | 已修复 |
| **脚本误覆盖用例** | — | smoke/deadloop_probe 被清理脚本覆盖丢代码 → 已恢复 | 已修复 |

## 六、交接要点（下一 session）

1. **✅ T01 LLM 批真实重跑验证**（Phase B 收尾）：57 个 LLM 用例真实重跑 **55 PASS + 2 GUARD**（零 HARNESS/零缺陷复现）。
2. **✅ Phase C 干净彻底**：过期文档删除（40 个）+ 套件重构（用户原则：不冻结、问题直接重构）+ register classification 写回 100%。
3. **✅ Phase D 自动化衔接**：报告自动生成 `_toolkit/gen_register.py` + 收敛流程硬规则 `_toolkit/PHASE_D_AUTOMATION.md`（缺陷修复=根因+tests/ 回归双交付）。
4. **独立缺陷窗口**：GEN-5 / GEN-6（PENDING_TASKS 已登记 + 触发用例）。
5. **供应商感知思考禁用机制**（待设计）。

## 七、相关文件

| 用途 | 路径 |
|------|------|
| 本任务控制文档 | `tasks_docs/TRIAL_SYSTEM_REDESIGN.md` |
| 试用体系规范（Phase 1-2 产物） | `tasks_docs/trials/_toolkit/CLASSIFICATION.md` |
| 用例即契约（Phase B） | `tasks_docs/trials/_toolkit/CONTRACT_FORMAT.md` |
| 报告自动生成器（Phase D） | `tasks_docs/trials/_toolkit/gen_register.py` |
| 收敛流程+自动化设计（Phase D） | `tasks_docs/trials/_toolkit/PHASE_D_AUTOMATION.md` |
| 跨套索引/编号映射 | `tasks_docs/trials/INDEX.md` |
| 缺陷登记（GEN-5 等） | `tasks_docs/PENDING_TASKS.md` |
