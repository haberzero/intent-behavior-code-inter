# IBC-Inter 文档中心

> 本文件是 `docs/` 目录的**导航枢纽与治理章程**。
>
> **文档分工**：
> - `docs/` -- 设计文档与用户手册（6 个主手册 + 4 个子目录）
> - `tasks_docs/` -- 任务控制、决策记录、完成日志
> - `tests_docs/` -- 测试方法论

---

## 一、目录结构

```
docs/
├── README.md                        本文件（导航 + 治理）
├── WRITING_GUIDE.md                 技术文档书写准则（强制）
├── SYNTAX_REFERENCE.md              语法说明手册（索引）
├── ARCHITECTURE.md                  架构设计手册（索引）
├── SUBSYSTEM_DESIGN.md              子系统设计手册（索引）
├── KNOWN_LIMITS.md                  语言级已知限制
│
├── guide/                           入门教程（按序阅读）
│   ├── 00_environment.md
│   ├── 01_setup.md
│   ├── 02_first_call.md
│   ├── 03_handling_errors.md
│   ├── 04_intents.md
│   ├── 05_llm_functions.md
│   ├── 06_multistep.md
│   └── 07_testing.md
│
├── howto/                           操作指南（按问题查阅）
│   ├── debug_llm_calls.md
│   └── write_user_plugin.md
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
│   ├── 13_mock_testing.md
│   └── 14_concurrency.md
│
├── architecture/                    架构设计详细章节
│   ├── 01_principles.md
│   ├── 02_metadata_ast.md
│   ├── 03_type_system.md
│   ├── 04_vm_interpreter.md
│   ├── 05_vm_specification.md
│   ├── 06_path_system.md
│   ├── 07_kernel_native_modules.md
│   └── 08_storage_model.md
│
├── subsystems/                      子系统设计详细章节
│   ├── 01_intent_system.md
│   ├── 02_file_container.md
│   ├── 03_callable_fn.md
│   ├── 04_plugin_system.md
│   └── 05_coroutine.md

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
| **新加入的开发者** | `README.md`（根目录）-> `GETTING_STARTED.md` -> `docs/guide/00_environment.md` -> `docs/guide/01_setup.md` -> `docs/guide/` -> `SYNTAX_REFERENCE.md` -> `ARCHITECTURE.md` |
| **写 IBCI 代码的用户** | `README.md`（根目录）-> `docs/guide/` 教程 -> `SYNTAX_REFERENCE.md`（查语法）-> `KNOWN_LIMITS.md`（查边界） |
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
| 诊断码 | `SEM_TYPE_MISMATCH`/`PAR_EXPECTED_TOKEN`/`LEX_INVALID_CHAR` 等命名制诊断码（定义见 `core/base/diagnostics/codes.py`），是功能性错误码 |
| 公理码 | `SC-3`/`LT-2`/`EXEC-2`/`ISO-4`/`OM-2`/`GC-2`/`LLM-1`/`IC-1` 等 VM 规范公理编号（定义见 `docs/architecture/05_vm_specification.md §8`），是规范契约码 |
| 功能性术语 | "锚点"（path anchor）、"Layer N / Phase N / STAGE N"（算法阶段）是功能描述 |
| 诊断码常量赋值 | `SEM_TYPE_MISMATCH = "SEM_TYPE_MISMATCH"` 是代码，不是注释 |

**诊断码使用规则**：生产代码中不得使用字符串字面量（如 `code="SEM_TYPE_MISMATCH"`）引用诊断码，必须从 `core/base/diagnostics/codes.py` 导入常量引用（如 `code=SEM_TYPE_MISMATCH`）。新增诊断码时在 `codes.py` 中定义新常量即可，无需分配编号。

---

## 四、代码路径约定

多个核心模块已重构为**包（目录）**，文档中引用代码路径时请以实际目录结构为准：

| 文档常见旧路径 | 实际现状 |
|---------------|---------|
| `core/kernel/spec/registry.py` | -> 包 `core/kernel/spec/registry/` |
| `core/kernel/axioms/primitives.py` | -> 包 `core/kernel/axioms/primitives/` |
| `core/runtime/objects/builtins.py` | -> 包 `core/runtime/objects/primitives/` |
| `core/runtime/objects/kernel.py` | -> 包 `core/runtime/objects/kernel/` |
| `core/runtime/vm/handlers.py` | -> 包 `core/runtime/vm/handlers/` |
| `core/compiler/semantic/passes/semantic_analyzer.py` | -> `core/compiler/semantic/analyzer.py` + 4-Phase 流水线 |

---

## 五、跨文档引用约定

- 文档间引用统一使用**仓库相对路径**。
- Markdown 超链接使用**相对于本文件**的路径，迁移文件时必须同步修正。

---

## 六、技术文档书写准则

IBCI 全部技术文档的书写准则已独立为 `docs/WRITING_GUIDE.md`。任何新增或修改 `docs/` 下技术文档时，必须以该文件为强制参考。

`WRITING_GUIDE.md` 覆盖：文档体系设计（四分法、归属唯一、层间正交）、单篇骨架（定位段、渐进披露、信息密度）、段落行文（论证单元、行文四规则、术语管理、示例设计）、条目格式模板（五类模板 + 骨架速查）、红线（禁止书写的内容）、引用与代码片段规范、质量检验（段落级 + 文档级 + 体系级 + 健康检查清单）、文档评审流程。
