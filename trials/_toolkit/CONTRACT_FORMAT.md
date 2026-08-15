# CONTRACT_FORMAT — 用例即契约格式规范（单一权威源）

> 2026-08-13 编制（试用体系重构 Phase B）。**试用用例 = 语言语义契约的断言**，
> 非"跑一遍看结果"。harness 读取用例头部断言 → 运行 → **自动判定分类**并写入
> register.jsonl（消除人工判定，address classification 0% 缺口）。
> 本规范是 `CLASSIFICATION.md` 的配套（分类/级别/编号权威仍在 CLASSIFICATION）。

## 一、用例头部断言格式

用例（`.ibci`）头部以 `# expect-*:` 结构化注释声明**机器可判定的期望**。harness
解析这些行做自动判定。

```
# <人类可读描述，任意行>
# expect-class: <PASS | GUARD | KERNEL_ISSUE | BOUNDARY | DOC_ISSUE | LLM_BEHAVIOR | LIMIT | HARNESS>
# expect-out: <精确输出行；多行用 | 分隔；按出现顺序匹配（允许间隔）>
# expect-exit: <0 | 1 | nonzero>
# expect-code: <诊断码，如 SEM_TYPE_MISMATCH / RUN_TYPE_MISMATCH；可多值逗号分隔>
# expect-llm: <true | false>   # 可选；true = 依赖真实 LLM（本机服务见 LLM_SERVICE.md）
```

- `expect-llm: true` 用例须本机 LLM 服务可达才跑（批量运行器分层：先 mock 后 llm，
  单用例超时 SIGKILL 不拖垮整批，见 `run_batch.py`）。
- 用例注释**只保留功能说明与 `# doc:` 引用**；不得含时间戳、任务代号、缺陷编号、
  决策/过程叙述（与逻辑无关的标记，见 docs/README §3.6 精神）。
- `expect-class` 必填；`expect-out`/`expect-exit`/`expect-code` 至少一个（否则无法判定）。
- **无断言的用例判 `HARNESS`**（不保留人工判定双轨，历史用例一律补断言，见 §六）。
- 所有断言**全过**才判定为目标分类；任一失败 → `HARNESS`（防"跑通即 PASS"掩盖断言缺口）。
- `expect-llm` 为元信息（批量分层），不参与单用例判定。

### 分类 → 断言语义

| expect-class | 断言判定 | 示例 |
|--------------|----------|------|
| `PASS` | expect-out 全出现 + expect-exit 匹配 | `# expect-out: total=6 | DONE` |
| `GUARD` | expect-code 出现（守卫生效）+ expect-exit nonzero | `# expect-code: SEM_GENERIC_TYPE_NEEDS_ARGS` |
| `KERNEL_ISSUE` | expect-out 为**修复后期望**（核销判据）；当前实际输出即缺陷证据 | `# expect-out: box_slice=Box[list[int]]`（当前崩） |
| `BOUNDARY` | 行为事实记录（expect-out 为实际行为） | 文档化边界 |
| `LIMIT` | 命中文档化限制（expect-code 或 expect-out 为限制行为） | 待修候选池 |
| `DOC_ISSUE` | 文档对照（note 记录文档位置） | — |
| `LLM_BEHAVIOR` | 真实 LLM 行为记录 | — |
| `HARNESS` | 试用地基/用例自身问题 | — |

## 二、harness 判定逻辑（run_one.py 集成）

```
1. 解析 .ibci 头部 # expect-*: 行 → 断言 dict。
2. 运行用例（死循环保护不变），收集 stdout、exit_code、诊断码（stdout/stderr 提取）。
3. 判定：
   - 无断言 → classification="HARNESS", note="<无断言...>"
   - 有断言 → 逐项比对；全过 → classification=expect-class；
     任一失败 → classification="HARNESS", note="<断言失败详情>"
4. 写 register.jsonl（classification 自动填充）。
```

诊断码提取：正则 `\b(SEM|PAR|LEX|DEP|INT|RUN|KDIAG|CFG)_[A-Z0-9_]+\b`（对齐
`core/base/diagnostics/codes.py` 命名制前缀）。

## 六、历史用例迁移（不留历史兼容）

历史 4 套用例（无 `# expect-*:` 断言）**全部补断言**，来源：
- `REGISTER.md` 明细表的"期望/实际"列 → `expect-out` / `expect-class`；
- 负例/守卫用例（`SEM_*`/`RUN_*`）→ `expect-code` + `expect-exit: nonzero`；
- `KERNEL_ISSUE` 触发用例 → `expect-class: KERNEL_ISSUE` + `expect-out: <修复后期望>`。

迁移后重跑确认判定：`PASS` 用例断言全过；`GUARD` 用例命中诊断码。迁移记录写入
`trials/INDEX.md`（每套一行迁移状态）。

## 三、用例骨架（新用例从模板起步）

```
# <T<nn>-<dim>-<seq> 人类可读描述>   ← 用例 ID 规范见 CLASSIFICATION §五
# doc: <docs/syntax/ 章节>
# expect-class: <分类>
# expect-out: <期望输出>
# expect-exit: <0/nonzero>
import ai
ai.set_mock_mode()
...
```

## 四、覆盖矩阵（每套 DESIGN.md）

每套 DESIGN.md 维护"维度 → 语法章节 → 用例组"映射表，harness/agent 依此核对覆盖缺口：

| 维度 | 覆盖特性 | 语法章节 | 用例组 | 覆盖状态 |
|------|----------|----------|--------|----------|
| D1 | 基础语义 | 01_types ~ 15_diagnostics | D1-* | 全覆盖/有缺口 |

## 五、缺陷闭环状态机（INDEX.md 单一状态权威）

`KERNEL_ISSUE-<域>-<n>` 生命周期状态：

```
发现 → 登记（PENDING_TASKS + INDEX.md）→ 修复（tests/ 补回归）→ 回归试用（触发用例核销）
→ 已修复
```

- INDEX.md 为状态单一权威源；REGISTER/PENDING_TASKS 引用一致。
- 触发用例保留至核销（修复后 expect-out 应通过）；核销后用例改标 PASS 或归档。
- 触发用例 `expect-class: KERNEL_ISSUE` + `expect-out: <修复后期望>` 即为核销判据。
