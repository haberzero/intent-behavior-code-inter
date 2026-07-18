# IBC-Inter 文档中心

> 本文件是 `docs/` 目录的**导航枢纽与治理章程**。新加入者请先读本文件，再按角色选择阅读路径。
> 实时主线状态见 `docs/NEXT_STEPS.md`；完成归档见 `docs/COMPLETED.md`。

---

## 一、目录结构

```
docs/
├── README.md                    本文件（导航 + 治理）
│
├── 状态治理层（实时维护，单点真理）
│   ├── NEXT_STEPS.md            当前最紧要任务（每次开新分支先读）
│   ├── PENDING_TASKS.md         阻塞/待前置任务的未来规划
│   ├── COMPLETED.md             完成节点极简时间线（归档 SSOT）
│   └── HISTORY_LOG.md           更早期的详细演进日志
│
├── 语言参考层（用户面向）
│   ├── IBCI_SYNTAX_REFERENCE.md 完整语法参考（用户侧权威）
│   ├── KNOWN_LIMITS.md          语言级已知限制
│   ├── ARCHITECTURE_PRINCIPLES.md 架构原则与设计理念
│   └── METADATA_ARCHITECTURE.md 元数据（AST/侧表/序列化）架构
│
├── design/                      设计文档（架构推演与实现细节）
│   ├── TYPE_SYSTEM_DESIGN.md       类型系统设计（代码对齐版）
│   ├── VM_AND_INTERPRETER_DESIGN.md VM 与解释器架构
│   ├── VM_SPEC.md                  VM 公理化规范（跨宿主可移植）
│   ├── ARCH_DETAILS.md             重要架构细节备份
│   ├── INTENT_SYSTEM_DESIGN.md     意图注释系统设计
│   ├── MULTIMODAL_BEHAVIOR_DESIGN.md 多模态行为设计规划
│   ├── COROUTINE_DESIGN_NOTES.md   协程层设计笔记（SHELVED 搁置）
│   └── FUNC_DESIGN_NOTES.md        fn/高阶函数设计笔记
│
├── testing/                     测试方法论
│   ├── TEST_PHILOSOPHY.md           测试体系设计原则
│   └── SEMANTIC_COVERAGE_MATRIX.md  语义覆盖矩阵
│
├── decisions/                   架构决策记录（ADR-007~018）
│   └── README.md                    ADR 索引与模板
│
├── archive/                     历史/被取代文档（仅追溯用）
│   ├── IBCI_TYPE_SYSTEM_FROM_ZERO_ARCHITECTURE.md  类型系统设计原文（被 design/TYPE_SYSTEM_DESIGN 取代）
│   ├── MULTIMODAL_ANALYSIS_CONCLUSIONS.md           多模态分析（已并入主设计 + 被 ADR 反转）
│   ├── PHASE1_TECHNICAL_DECISIONS.md                Phase 1 决策便签（被 ADR-008/010 承接）
│   └── AUDIT_REPORT_20260527.md                     2026-05-27 审计快照（发现已全部关闭）
│
└── worklogs/
    └── archive/                 已归档工作日志（已并入 COMPLETED.md）
```

---

## 二、按角色的阅读路径

| 角色 | 推荐阅读顺序 |
|------|------------|
| **新加入的开发者** | 本文件 → `GETTING_STARTED.md`（根目录）→ `ARCHITECTURE_PRINCIPLES.md` → `NEXT_STEPS.md` |
| **写 IBCI 代码的用户** | `README.md`（根目录）→ `IBCI_SYNTAX_REFERENCE.md` → `KNOWN_LIMITS.md` |
| **要改类型系统的人** | `design/TYPE_SYSTEM_DESIGN.md` → `METADATA_ARCHITECTURE.md` → `design/ARCH_DETAILS.md` |
| **要改 VM/解释器的人** | `design/VM_AND_INTERPRETER_DESIGN.md` → `design/VM_SPEC.md` → `design/ARCH_DETAILS.md` |
| **要了解当前进度的人** | `NEXT_STEPS.md`（最紧要）→ `COMPLETED.md`（最近完成）→ `PENDING_TASKS.md`（搁置项） |
| **要做架构决策的人** | `decisions/README.md`（ADR 索引）→ 相关 ADR → 本文件"治理纪律" |

---

## 三、文档治理纪律（强制）

### 3.1 单点真理

| 事实 | 唯一来源 |
|------|---------|
| 当前最紧要任务 | `NEXT_STEPS.md`（一处） |
| 已完成事项 | `COMPLETED.md`（一处） |
| 阻塞/搁置事项 | `PENDING_TASKS.md`（一处） |
| 语言级限制 | `KNOWN_LIMITS.md`（一处） |
| 语法权威 | `IBCI_SYNTAX_REFERENCE.md`（一处） |
| 架构决策 | `decisions/ADR-NNN-*.md`（一处） |

> 同一事实只在一处声明。其它文档引用，不抄录、不重复声明。

### 3.2 数字纪律（测试基线）

- 测试基线**只在 `NEXT_STEPS.md` 顶部或 `COMPLETED.md` 最新条目**写一次，附**运行命令 + 日期**。
- 其它文档**不得冻结具体测试通过数字**，统一用"以 `python -m pytest tests/ -q --tb=no --no-header` 实跑为准"。
- 运行命令统一为：`python -m pytest tests/ -q --tb=no --no-header`

### 3.3 生命周期纪律

- **工作日志**仅存于进行中的 session；合并入 `COMPLETED.md` 后立即移入 `worklogs/archive/`。
- **被 ADR 取代的设计文档**：在顶部加"决策状态导航"横幅（逐条标注被哪个 ADR 反转/接续），价值耗尽后移入 `archive/`。
- **一次性产出**（审计报告、阶段决策便签）：完成后移入 `archive/`，标题下加"⚠️ 历史快照"横幅。
- 每次开新分支前，先复跑测试基线，把当前 pass/fail 计数写在 PR 描述里。

### 3.4 跨文件一致性

`README.md`、`KNOWN_LIMITS.md`、`IBCI_SYNTAX_REFERENCE.md`、`METADATA_ARCHITECTURE.md` 之间对同一语法/限制/架构立场的描述必须用**同一组事实**。改动其一时同步检查其余。

### 3.5 新增文档前的检查

- 新增 AST 字段或侧表前，必须先在 `METADATA_ARCHITECTURE.md` 查证。
- 重大架构决策必须写 ADR（`decisions/ADR-NNN-*.md`）；被取代/修订的 ADR 必须在自身 Status 行标注。
- 新增长期文档前，先确认它不与现有文档重复——若重复，扩展现有文档而非新建。

---

## 四、代码路径约定

多个核心模块已重构为**包（目录）**，文档中引用代码路径时请以实际目录结构为准：

| 文档常见旧路径 | 实际现状 |
|---------------|---------|
| `core/kernel/spec/registry.py` | → 包 `core/kernel/spec/registry/` |
| `core/kernel/axioms/primitives.py` | → 包 `core/kernel/axioms/primitives/` |
| `core/runtime/objects/builtins.py` | → 包 `core/runtime/objects/builtins/` |
| `core/runtime/objects/kernel.py` | → 包 `core/runtime/objects/kernel/` |
| `core/runtime/vm/handlers.py` | → 包 `core/runtime/vm/handlers/`（`build_dispatch_table` 在 `handlers/dispatch.py`） |
| `core/runtime/interpreter/llm_executor.py` | → 包 `core/runtime/interpreter/llm_executor/` |
| `core/runtime/interpreter/handlers/{stmt,expr}_handler.py` | **已删除**（旧 visitor 架构）；现为 `core/runtime/vm/handlers/` CPS 包 |
| `core/compiler/semantic/passes/semantic_analyzer.py` | **已重组**；现为 `core/compiler/semantic/analyzer.py` + 4-Phase 流水线 |

---

## 五、跨文档引用约定

- 文档间引用统一使用**仓库相对路径**（如 `docs/design/VM_SPEC.md`、`docs/NEXT_STEPS.md`），无论引用方身处哪一层目录。
- Markdown 超链接（`[text](relative-path)`）使用**相对于本文件**的路径，迁移文件时必须同步修正。
- 引用 ADR 时写明编号（如 `ADR-016`），不写"那份决策文档"等模糊指代。
