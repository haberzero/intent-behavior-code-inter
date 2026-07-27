# IBC-Inter 文档中心

> 本文件是 `docs/` 目录的**导航枢纽与治理章程**。
>
> **文档分工**：
> - `docs/` -- 设计文档与用户手册（5 个主手册 + 3 个子目录）
> - `tasks_docs/` -- 任务控制、决策记录、完成日志
> - `tests_docs/` -- 测试方法论

---

## 一、目录结构

```
docs/
├── README.md                        本文件（导航 + 治理）
├── SYNTAX_REFERENCE.md              语法说明手册（索引）
├── ARCHITECTURE.md                  架构设计手册（索引）
├── SUBSYSTEM_DESIGN.md              子系统设计手册（索引）
├── KNOWN_LIMITS.md                  语言级已知限制
│
├── syntax/                          语法说明详细章节
│   ├── 01_types.md
│   ├── 02_variables.md
│   ├── 03_operators.md
│   ├── 04_control_flow.md
│   ├── 05_functions.md
│   ├── 06_oop.md
│   ├── 07_behavior_expressions.md
│   ├── 08_llm_functions.md
│   ├── 09_intent_system.md
│   ├── 10_robustness.md
│   ├── 11_modules.md
│   ├── 12_builtins.md
│   └── 13_mock_testing.md
│
├── architecture/                    架构设计详细章节
│   ├── 01_principles.md
│   ├── 02_metadata_ast.md
│   ├── 03_type_system.md
│   ├── 04_vm_interpreter.md
│   ├── 05_vm_specification.md
│   ├── 06_path_system.md
│   ├── 07_kernel_native_modules.md
│   ├── 08_storage_model.md
│   └── appendix_type_system_rationale.md
│
└── subsystems/                      子系统设计详细章节
    ├── 01_intent_system.md
    ├── 02_multimodal_behavior.md
    ├── 03_callable_fn.md
    ├── 04_plugin_system.md
    └── 05_coroutine.md

tasks_docs/                          任务控制
├── NEXT_STEPS.md
└── PENDING_TASKS.md

tests_docs/                          测试方法论
├── TEST_PHILOSOPHY.md
└── SEMANTIC_COVERAGE_MATRIX.md
```

---

## 二、按角色的阅读路径

| 角色 | 推荐阅读顺序 |
|------|------------|
| **新加入的开发者** | `README.md`（根目录）-> `GETTING_STARTED.md` -> `ARCHITECTURE.md` -> `tasks_docs/NEXT_STEPS.md` |
| **写 IBCI 代码的用户** | `README.md`（根目录）-> `SYNTAX_REFERENCE.md` -> `KNOWN_LIMITS.md` |
| **要改类型系统的人** | `architecture/03_type_system.md` -> `architecture/02_metadata_ast.md` |
| **要改 VM/解释器的人** | `architecture/04_vm_interpreter.md` -> `architecture/05_vm_specification.md` |
| **要了解当前进度的人** | `tasks_docs/NEXT_STEPS.md` -> `tasks_docs/PENDING_TASKS.md` |

---

## 三、文档治理纪律（强制）

### 3.1 单点真理

| 事实 | 唯一来源 |
|------|---------|
| 当前最紧要任务 | `tasks_docs/NEXT_STEPS.md` |
| 阻塞/搁置事项 | `tasks_docs/PENDING_TASKS.md` |
| 语言级限制 | `docs/KNOWN_LIMITS.md` |
| 语法权威 | `docs/SYNTAX_REFERENCE.md` + `docs/syntax/` |
| 架构设计 | `docs/ARCHITECTURE.md` + `docs/architecture/` |
| 子系统设计 | `docs/SUBSYSTEM_DESIGN.md` + `docs/subsystems/` |

### 3.2 数字纪律（测试基线）

- 测试基线**只在 `tasks_docs/NEXT_STEPS.md` 顶部**写一次。
- 其它文档**不得冻结具体测试通过数字**，统一用"以 `python -m pytest tests/` 实跑为准"。

### 3.3 生命周期纪律

- 重大架构决策直接写入 `docs/architecture/` 对应章节，不再使用独立 ADR 文件。
- 已实现且无延迟项的设计内容可从任务文档中删除。
- 每次开新分支前，先复跑测试基线。

### 3.4 跨文件一致性

`README.md`、`KNOWN_LIMITS.md`、`SYNTAX_REFERENCE.md`、`ARCHITECTURE.md` 之间对同一语法/限制/架构立场的描述必须用**同一组事实**。

### 3.5 新增文档前的检查

- 新增 AST 字段或侧表前，必须先在 `architecture/02_metadata_ast.md` 查证。
- 新增长期文档前，先确认它不与现有文档重复--若重复，扩展现有文档而非新建。

### 3.6 代码注释卫生纪律

> **核心原则**：代码注释只应注明**功能设计**与**已知问题**，不应承载项目过程信息（任务指针、设计代号、历史叙述、文档章节引用）。过程信息属于任务文档与 git 历史，不属于代码。

**禁止在 `.py` 文件的注释与 docstring 中出现的内容**：

| 类别 | 违规示例 | 处置 |
|------|---------|------|
| 任务文档指针 | `见 NEXT_STEPS.md`/`PENDING_TASKS §四`/`tasks_docs/` | 删指针，留功能说明 |
| ADR 编号 | `Per ADR-019：`/`（ADR-020 §A）` | 删编号前缀/后缀，留设计解释 |
| PT 任务编号 | `PT-ARCH-28：`/`PT-4.7：` | 删编号前缀，留功能说明 |
| 设计代号 | `G1-G6`/`D1-D6`/`H1-H3`/`NS-x`/`P0-P7`/`方案A-B`/`C2-C11` | 删代号标签，留功能说明 |
| 历史叙述 | `原实现采用…`/`历史上…`/`旧 bug`/`修复见PR`/`合并自`/`Source:`/`legacy` | 改写为现在时或删除 |
| 文档章节号 | `§6.1`/`§9.2`/`§三` | 删章节号，留功能说明 |
| 文档路径指针 | `docs/architecture/…`/`docs/KNOWN_LIMITS.md` | 删指针行/分句 |

**保留的内容**（不视为违规）：

| 类别 | 说明 |
|------|------|
| ERR 码 | `SEM_xxx`/`DEP_xxx`/`PAR_xxx`/`INV-x`/`SC-x`/`LT-x`/`CF-x`/`OM-x` 是功能性错误码/契约码 |
| 功能性术语 | "锚点"（path anchor）、"Layer N / Phase N / STAGE N"（算法阶段）是功能描述 |
| 错误码常量赋值 | `SEM_UNDEFINED_SYMBOL = "SEM_001"` 是代码，不是注释 |

**新增代码时的自查**：提交前对自己的改动运行以下检查，确保未引入违规：

```bash
# 搜索违规模式（ADR/PT/任务文档指针/章节号）
grep -rnE 'ADR-[0-9]|PT-ARCH|PT-[0-9]|Per ADR|§[0-9]|tasks_docs/|PENDING_TASKS|NEXT_STEPS' --include='*.py' <changed-files>
# 搜索设计代号
grep -rnE '\b(G[1-6]|D[1-6]|H[1-3]|NS-[0-9]|P[0-7]-[0-9A-Z])\b' --include='*.py' <changed-files>
# 搜索历史叙述
grep -rnE 'legacy|历史|旧 bug|修复见PR|合并自|Source:' --include='*.py' <changed-files>
```

命中后逐条判断：是注释/docstring 则清洁（删标记留功能），是 ERR 码或功能性术语则保留。

---

## 四、代码路径约定

多个核心模块已重构为**包（目录）**，文档中引用代码路径时请以实际目录结构为准：

| 文档常见旧路径 | 实际现状 |
|---------------|---------|
| `core/kernel/spec/registry.py` | -> 包 `core/kernel/spec/registry/` |
| `core/kernel/axioms/primitives.py` | -> 包 `core/kernel/axioms/primitives/` |
| `core/runtime/objects/builtins.py` | -> 包 `core/runtime/objects/primitives/`（G1 重命名） |
| `core/runtime/objects/kernel.py` | -> 包 `core/runtime/objects/kernel/` |
| `core/runtime/vm/handlers.py` | -> 包 `core/runtime/vm/handlers/` |
| `core/compiler/semantic/passes/semantic_analyzer.py` | -> `core/compiler/semantic/analyzer.py` + 4-Phase 流水线 |

---

## 五、跨文档引用约定

- 文档间引用统一使用**仓库相对路径**。
- Markdown 超链接使用**相对于本文件**的路径，迁移文件时必须同步修正。
