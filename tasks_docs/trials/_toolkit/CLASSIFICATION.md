# CLASSIFICATION — 试用地基统一分类 / 级别 / 命名规范（单一权威源）

> 所有试用地基的用例分类、严重级别、缺陷编号、目录骨架、运行入口必须遵循本规范。
> 新增/修改本文件视为对试用体系契约的变更，需同步 `trials/INDEX.md` 与既有 REGISTER 引用。

## 一、统一分类体系

| 分类 | 含义 | 何时用 | 处置 |
|------|------|--------|------|
| `PASS` | 期望行为达成 | 所有用例的正常结果 | 归档 |
| `GUARD` | 守卫生效（预期报错/拦截，含 fail-fast 诊断码） | 守卫/负例类用例 | 归档 |
| `KERNEL_ISSUE` | 内核缺陷（编译/运行时行为错误） | 经"登记前分诊"确认为真缺陷 | 登记 PENDING_TASKS 待修 |
| `BOUNDARY` | 边界行为（非缺陷但需记录的设计事实） | 文档化边界、设计事实 | 记录 + 视情文档化 |
| `DOC_ISSUE` | 文档错误/过时/矛盾 | 文档对照类用例 | 登记待修（DOC-ISSUE-<n>） |
| `LLM_BEHAVIOR` | LLM 模型行为（非内核缺陷） | 真实 LLM 试用 | 记录，不作内核处置 |
| `LIMIT` | 已知限制（文档已列） | 命中 KNOWN_LIMITS/docs 的用例 | **≠ 免罪**：登记并进待修候选池（见 §四） |
| `HARNESS` | 试用地基/工具自身问题 | harness/脚本异常 | 修 harness |

## 二、统一级别

- `P0`：崩溃 / 死循环 / 数据损坏 / 进程无法终止
- `P1`：明确缺陷，重要语义错误（静默错误值 / 错误路径崩溃 / 契约失效）
- `P2`：缺陷，较轻（边缘路径 / 可观测性问题）
- `P3`：文档 / 体验 / 边界记录（无缺陷，仅记录）

## 三、缺陷编号统一命名空间

```
KERNEL_ISSUE-<域>-<序号>     # 域：GEN（泛型）/ LLM / VM / IMPORT / CONFIG / ...
BOUNDARY-<域>-<序号>
DOC_ISSUE-<全局序号>
```

- 编号全局唯一（跨试用地基），由 `trials/INDEX.md` 汇总。
- 历史编号（如 `KERNEL-ISSUE-001`、`KERNEL-ISSUE-G1`、`G3`）经映射表归一到新格式
  （见各 REGISTER 与 INDEX.md），PENDING_TASKS 引用同步。

## 四、登记前分诊闸门（强制）

**任何非 PASS 用例在写入分类前，必须先对照 `docs/KNOWN_LIMITS.md`、`docs/syntax/`、
设计文档与既有 REGISTER 做分诊**，按以下顺序判定：

1. 命中文档化已知限制 → `LIMIT`（记录引用章节），并**登记进待修候选池**
   （PENDING_TASKS 或各 REGISTER 的 LIMIT 节）——**文档列出限制 ≠ 免罪**：
   已知限制可能是真实缺陷的合理化（先例：G3 auto-init 继承限制原为 KNOWN_LIMITS §六，
   代码实证后按真实缺陷修复）。限制是否值得修，由质量维护周期评估。
2. 用例本身违反文档规定用法（如未按文档用显式 `__init__`）→ 标记 `HARNESS`/用例错误
   （note 注明违反的文档条款），修正用例而非登记内核缺陷。
3. 其余经复现 + 代码/文档实证确认 → 按上述分类登记。

**登记缺陷时附三件套**：复现用例路径 / 证据日志路径 / 根因分析起点（或实证结论）。
未复现、未实证的现象不得登记为 `KERNEL_ISSUE`。

## 五、统一目录骨架（DESIGN_TEMPLATE.md）

```
trials/T<nn>_<主题>/
  DESIGN.md            # 目标/矩阵/硬约束（死循环保护）/分类/记录
  cases/               # 用例脚本（.ibci）
  api_config.json      # mock 配置（真实 LLM 试用可替换）
  harness/run_one.py   # 软链 → _toolkit/run_one.py（单一权威源，非复制）
  logs/                # <case>.log + register.jsonl（机械字段由 harness 写）
  REGISTER.md          # 人工汇总（分类/级别/缺陷登记），模板见 REGISTER_TEMPLATE.md
```

## 六、统一运行入口

```bash
python tasks_docs/trials/_toolkit/run_one.py cases/<case>.ibci \
    --label <case_id> --dim <dim> --doc <章节> --expected <描述> \
    --timeout <秒，必填> --max-inst <默认 5e6> --root <试用地基根目录>
```

- `--timeout` 必填（无超时不运行，死循环保护硬约束）。
- `--root` 指向试用地基根（含 api_config.json / cases / logs）。
- 仓库根自动从 `--root` 上溯查找（main.py），或用 `--repo-root` 显式覆盖。
