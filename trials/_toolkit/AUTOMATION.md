# AUTOMATION — 缺陷收敛与报告自动生成

> 本文档规定试用体系的两个自动化机制：试用缺陷向 `tests/` 确定性回归的收敛流程，
> 与 REGISTER 报告骨架的自动生成。面向执行试用与缺陷修复的工作者。
> 用例契约与缺陷状态机的权威定义见 `_toolkit/CONTRACT_FORMAT.md`；分类与编号见
> `_toolkit/CLASSIFICATION.md`。

---

## 一、收敛流程（缺陷 → tests/ 回归）

缺陷状态机（CONTRACT_FORMAT §五）的执行细化：

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

## 二、报告自动生成（`_toolkit/gen_register.py`）

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

## 三、验收判据

- 任一新 KERNEL_ISSUE 修复 commit 必含 `tests/` 回归（判别性：修复前失败）。
- 任一试用批次收尾用 `gen_register.py` 生成 REGISTER 骨架（人工补结论后覆盖）。
- 全量 pytest 零回归是收敛验收门。

## 四、关联

- `_toolkit/CONTRACT_FORMAT.md` §五（缺陷状态机）
- `_toolkit/CLASSIFICATION.md`（分类/级别/编号）
- `_toolkit/REGISTER_TEMPLATE.md`（报告格式基线）
- `trials/INDEX.md`（缺陷状态单一权威源）
