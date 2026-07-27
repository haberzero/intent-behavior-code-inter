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
