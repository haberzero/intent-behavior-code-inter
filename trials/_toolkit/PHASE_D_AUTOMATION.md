# PHASE_D_AUTOMATION — 试用→确定性测试收敛 + 报告自动生成设计

> 2026-08-13 编制（试用体系重构 Phase D）。目标：把试用暴露的缺陷**自动收敛为
> `tests/` 确定性回归**，并**自动生成 REGISTER 报告骨架**。单一权威源：
> `_toolkit/CONTRACT_FORMAT.md`（用例即契约）与 `_toolkit/CLASSIFICATION.md`（分类/编号）。

---

## 一、背景与差距

现状（Phase A-C 已就绪）：
- 用例即契约：`.ibci` 头部 `# expect-*:` 断言 + harness 自动判定（classification 自动写入 register.jsonl）。
- 缺陷状态机已定义（CONTRACT_FORMAT §五）：发现→登记→修复（tests/ 补回归）→回归试用核销。
- 但**收敛义务未落地为可执行机制**：缺陷修复后是否真的补了 `tests/` 回归，无自动/半自动核验；
  报告（REGISTER.md）仍靠人工按模板手写。

## 二、设计

### 2.1 收敛流程（缺陷 → tests/ 回归）

状态机（CONTRACT_FORMAT §五）细化：

```
发现（试用 KERNEL_ISSUE 触发用例）
  → 登记（PENDING_TASKS + trials/INDEX.md，触发用例保留 = 复现证据）
  → 修复（code-workflow，根因修复，禁规避/禁症状层补丁）
  → 收敛（修复 commit 必须包含 tests/ 确定性回归：`tests/runtime|e2e/test_<缺陷域>.py`）
      验收门：
        a. 新增回归测试复现原始缺陷（修复前失败，修复后通过）——判别性
        b. 全量 pytest 零回归（python -m pytest tests/）
  → 回归试用（重跑触发用例：expect-class KERNEL_ISSUE + expect-out 修复后期望达成
      → harness 自动判 PASS + note"待核销"）
  → 核销（INDEX.md 状态"已修复"，触发用例改标 PASS 或归档）
```

**硬规则（用户原则）**：
- 触发用例不得简化/规避（真实缺陷复现证据）。
- 缺陷修复 = 根因修复 + tests/ 回归（双交付）；缺任一即未完成。
- 语义变更（修复后正确行为变化）→ 用例重构为新语义（不冻结），原缺陷证据经 git 历史追溯。

### 2.2 报告自动生成（`_toolkit/gen_register.py`）

数据源：`<trial>/logs/register.jsonl`（run_one.py 机械记录 + harness 自动判定）。

```
python _toolkit/gen_register.py <试用地基根目录> [--smoke <name>]
```

产出（stdout）：
- **总览**：PASS/GUARD/KERNEL_ISSUE/BOUNDARY/DOC_ISSUE/LLM_BEHAVIOR/LIMIT/HARNESS 计数。
- **缺陷登记骨架**：KERNEL_ISSUE 触发用例清单（触发用例/exit/note，根因/级别/状态留人工）。
- **逐例明细**：case_id / 分类 / exit / 判定 note。

使用规范：
- register.jsonl 每 case 最新一条为权威（`B-` 前缀与单独运行去重，保留后出现者）。
- 生成骨架后人工补：KERNEL_ISSUE 根因分析、级别、修复状态、commit；LIMIT 待修候选评估；结论节。
- 覆盖 REGISTER.md（模板 `_toolkit/REGISTER_TEMPLATE.md` 为格式基线）。

## 三、落地清单

| # | 项 | 状态 |
|---|----|------|
| 1 | `gen_register.py` 报告生成器 | ✅ 已实现（本 phase） |
| 2 | 收敛流程硬规则（2.1）落文档 | ✅ 本文件 |
| 3 | 缺陷收敛义务核验（修复 commit 含 tests/ 回归） | 随 code-workflow 执行，登记 PENDING_TASKS 引用本文件 |
| 4 | 回归试用核销（触发用例 expect-out 达成） | harness 已支持（run_one.py KERNEL_ISSUE 判定分支） |

## 四、验收判据

- 任一新 KERNEL_ISSUE 修复 commit 必含 `tests/` 回归（判别性：修复前失败）。
- 任一试用批次收尾用 `gen_register.py` 生成 REGISTER 骨架（人工补结论后覆盖）。
- 全量 pytest 零回归是收敛验收门。

## 五、关联

- `_toolkit/CONTRACT_FORMAT.md` §五（缺陷状态机）
- `_toolkit/CLASSIFICATION.md`（分类/级别/编号）
- `_toolkit/REGISTER_TEMPLATE.md`（报告格式基线）
- `trials/INDEX.md`（缺陷状态单一权威源）
