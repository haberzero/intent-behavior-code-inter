# 试用体系规范化 — 设计记录（下一阶段主要目标）

> 2026-08-12 编制。**只设计未实施**。目标：把 IBCI 的"试用/压力测试"从"临时脚本 + 每套独立文档"
> 升级为**体系化、规范化、可复用的正式机制**，并把历史 4 套试用记录统一整理定型。
> 本文件是下一阶段任务的**设计起点与实施规划**（先 tasks_docs/ 设计，落地后按 docs 治理收敛）。
>
> **✅ 已实施（2026-08-13）**：Phase 1 机制规范化 + Phase 2 历史定型基本完成——
> 单一 harness `trials/_toolkit/run_one.py`（4 套复制改软链引用）+ `CLASSIFICATION.md`
> （统一分类/级别/编号 + 登记前分诊闸门）+ DESIGN/REGISTER 模板 + 4 套 git mv 迁移
> （`trials/T01_llm_full` 等）+ REGISTER 编号映射 + `trials/INDEX.md`。
> 详细进度与剩余项见 PENDING_TASKS §〇"试用体系规范化"行。

## 一、现状盘点（2026-08-12 代码级核实）

现有 4 套试用地基（`tasks_docs/`）：

| 试用地基 | 目标 | 用例 | 日志 | 分类体系 |
|----------|------|------|------|----------|
| `_LLM_TRIAL_20260812/` | 真实 LLM 全语法/压力/批判 | 104 | 153 logs | PASS/KERNEL_ISSUE/DOC_ISSUE/LLM_BEHAVIOR/LIMIT/BOUNDARY/HARNESS |
| `_LLM_TRIAL_ENUM_IMPORT_20260812/` | enum/import 用户试用 | 9 | 10 logs | 同上（复用） |
| `_GENERICS_TRIAL_20260812/` | 泛型压力/恶意试用 | 31 | 31 logs | PASS/KERNEL_ISSUE/BOUNDARY/GUARD |
| `_GENERICS_TRIAL_FIX_20260812/` | 泛型修复回归试用 | 35 | 33 logs | 同上 |

**已统一**：
- harness：4 份 `run_one.py` md5 一致（进程组 SIGKILL + --max-inst + timeout 强制参数 + register.jsonl 机械记录）
- register.jsonl 字段：15 字段一致（case_id/script/dim/doc/expected/timeout_s/max_inst/exit_code/timed_out/duration_s/out_head/err_head/classification/severity/note）
- api_config.json：mock 模式

**碎片化（规范化对象）**：
1. **命名**：`_LLM_TRIAL_` vs `_GENERICS_TRIAL_` vs `_LLM_TRIAL_ENUM_IMPORT_`——主题前缀（LLM/GENERICS）+ 无统一序号
2. **分类体系**：LLM 试用 7 类 vs 泛型试用 4 类（GUARD 仅泛型用；LLM_BEHAVIOR/DOC_ISSUE 仅 LLM 用）——无统一分类基准
3. **REGISTER 格式**：头部/总览/明细表结构略有差异；缺陷编号不统一（`KERNEL-ISSUE-001` vs `KERNEL-ISSUE-G1` vs `G3`）
4. **记录时效**：每套独立，无跨套索引/汇总；缺陷登记散落 PENDING_TASKS 各表
5. **重复维护**：harness 虽 md5 一致但物理 4 份复制，非单一权威源（改一处需同步 4 处）

## 二、规范化目标（设计原则对照 design-philosophy）

1. **单一权威源**：harness 收敛为**单一 `tools/trial_harness/`**（或 `tasks_docs/_TRIAL_TOOLKIT/`），各试用地基引用而非复制；分类/级别/命名规范为**单一规范文档**。
2. **机制同构**：所有试用地基同构——统一目录骨架（`DESIGN.md`/`cases/`/`harness 引用`/`logs/`/`REGISTER.md`/`api_config.json`）、统一运行入口、统一产出格式。
3. **设计语言统一**：缺陷编号统一命名空间（如 `KERNEL-ISSUE-<域>-<n>` 或全局递增）；分类统一（PASS/GUARD/KERNEL_ISSUE/BOUNDARY/DOC_ISSUE/LIMIT/HARNESS/LLM_BEHAVIOR 全部归一到统一清单，按需使用）。
4. **可追溯**：每试用地基一个索引入口，跨套缺陷登记汇总到单一处。

## 三、规范设计草案

### 3.1 试用地基命名
```
tasks_docs/trials/                     # 试用地基统一根
  T01_llm_full/                        # 原 _LLM_TRIAL_20260812
  T02_enum_import/                     # 原 _LLM_TRIAL_ENUM_IMPORT_20260812
  T03_user_class_generics/             # 原 _GENERICS_TRIAL_20260812
  T04_generics_fix_regression/         # 原 _GENERICS_TRIAL_FIX_20260812
  _toolkit/                            # 规范文档 + 单一 harness（非复制）
    run_one.py
    DESIGN_TEMPLATE.md
    REGISTER_TEMPLATE.md
    CLASSIFICATION.md                  # 统一分类/级别/命名规范
```
命名规则：`T<nn>_<主题>`（T = trial，序号递增，主题 kebab-case）。

### 3.2 统一分类体系（CLASSIFICATION.md 单一权威源）
| 分类 | 含义 | 何时用 |
|------|------|--------|
| `PASS` | 期望行为达成 | 所有 |
| `GUARD` | 守卫生效（预期报错/拦截）| 守卫类试用 |
| `KERNEL_ISSUE` | 内核缺陷（P0/P1/P2）| 所有 |
| `BOUNDARY` | 边界行为（非缺陷但需记录）| 所有 |
| `DOC_ISSUE` | 文档错误/过时/矛盾 | 文档对照 |
| `LLM_BEHAVIOR` | LLM 模型行为（非内核缺陷）| 真实 LLM 试用 |
| `LIMIT` | 已知限制（文档化边界）| 所有 |
| `HARNESS` | 试用地基自身问题 | 所有 |

级别统一：P0（崩溃/死循环/数据损坏）/ P1（明确缺陷，重要语义错误）/ P2（缺陷，较轻）/ P3（文档/体验）。

### 3.3 缺陷编号统一
```
KERNEL-ISSUE-<域>-<序号>    # 域：GEN（泛型）/LLM / VM / IMPORT / ...
BOUNDARY-<域>-<序号>
DOC-ISSUE-<全局序号>
```
历史编号映射表（旧 → 新）在规范化实施时维护，PENDING_TASKS 引用同步。

### 3.4 REGISTER 统一模板
```
# REGISTER — <试用名>
> 日期 / 目标 / 参考规范（CLASSIFICATION.md 版本）。
> 总览：用例数 / PASS 数 / GUARD 数 / 缺陷数 / 级别分布 / 冒烟验证结果。
> 缺陷登记：统一格式（编号/现象/证据日志/根因/修复状态/commit）。
> 逐例明细表：case_id | 目标 | 期望 | 实际 | 分类 | 级别 | 证据日志。
```

### 3.5 目录骨架模板（DESIGN_TEMPLATE.md）
```
DESIGN.md            # 目标/矩阵/硬约束（死循环保护）/分类/记录
cases/               # 用例脚本（.ibci）
api_config.json      # mock 配置
harness -> _toolkit/run_one.py   # 引用（或软链）单一 harness
logs/                # <case>.log + register.jsonl（机械字段由 harness 写）
REGISTER.md          # 人工汇总（分类/级别/缺陷登记）
```

## 四、实施规划（下一阶段）

### Phase 1 — 机制规范化（先做，工具化）
1. 建 `tasks_docs/trials/_toolkit/`：单一 harness（从现 4 份中抽取）+ CLASSIFICATION.md + DESIGN/REGISTER 模板。
2. 各试用地基改造：引用 `_toolkit/run_one.py`（软链或 import 路径），删 4 份复制。
3. 历史 4 套按新命名迁移目录（保留 git 历史：`git mv`）。

### Phase 2 — 历史记录定型
4. 4 套 REGISTER 按统一模板重排（分类映射到统一清单、缺陷编号统一、格式统一）。
5. 维护"历史编号映射表"（旧编号 → 新编号），PENDING_TASKS 引用同步。
6. 建 `trials/INDEX.md` 跨套索引（各套主题/日期/用例数/缺陷数/修复状态）。

### Phase 3 — 收尾
7. 全量 pytest 零回归（试用体系是文档+脚本，不涉内核代码）。
8. docs 治理：试用体系规范是否入 docs/（面向人类的"测试/验证方法论"）按 WRITING_GUIDE 评估。
9. 新试用从模板起步（避免再产生碎片化）。

## 五、约束
- 全程本地 commit；禁 push。
- 不触碰 main；零风险可直接合并 unsafe-vibe-dev。
- 工作模式定论：不因规范化而破坏既有试用证据（历史记录保留原始 logs，仅 REGISTER 重排格式）。
- 与泛型缺陷修复（G3/BOUNDARY-G2，见 `_HANDOFF_GENERICS_FIX.md`）错峰——本任务不混入修复。
