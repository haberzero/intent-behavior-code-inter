# `tests/` 目录维护规约

> 本文档是 `tests/` 长期维护守则的**精简版**；完整的体系化重构计划、合并矩阵
> 与执行步骤见 [`docs/TESTS_REORGANIZATION_TASK.md`](../docs/TESTS_REORGANIZATION_TASK.md)。

## 基础设施

- 所有公共 helper / fixture / 常量集中在 [`tests/conftest.py`](./conftest.py)。
- 测试文件**禁止再自行定义**以下函数（应改为 import 或使用 fixture）：
  - `run_and_capture` / `run_ibci` / `run_capture` / `run_code` —— 用 `run_ibci(...)` 或 `helpers.run_ibci(...)`
  - `make_engine` / `_make_engine` —— 直接用 `engine` fixture
  - `make_vm` —— 用 `helpers.make_vm(engine)` 或 import `make_vm`
  - `find_node_uid` / `find_node_uids` / `find_all_node_uids` —— 用 `find_node[_uid(s)]`
  - `native` —— 用 `native(obj)`
  - `ai_setup` / `ai_setup_code` / `_ai_prefix` —— 用常量 `AI_MOCK_PREFIX` 或
    `run_ibci(code, ai=True)`
  - `make_intent` —— 用 `make_intent(registry, content, ...)`
  - `compile_code` —— 用 `compile_ibci` / `compile_or_errors`

## 运行回归

规范命令：

```bash
python -m pytest tests/ -q --tb=short
```

测试套件完整覆盖核心语义不变量。测试重点在于**语义正确性**而非数量。

> 任何 PR 的最终运行结果**应保持测试全绿且覆盖度不降低**。

## 分层职责（红线）

| 目录 | 必须 | 禁止 |
|-----|-----|------|
| `kernel/` | 直接构造 `TypeRef` / `Spec` / `Axiom` / `Symbol` 等纯数据结构 | 启动 `IBCIEngine` 或运行 IBCI 代码 |
| `compiler/` | `compile_ibci(...)` / `compile_or_errors(...)`，断言 artifact、`SEM_*` / `PAR_*` 错误码 | 调 `run_ibci(...)` |
| `runtime/` | 小段（≤30 行）IBCI 代码 + 单子系统单元（VM / Intent / llmexcept / Cell / ...） | 复杂多模块脚本 |
| `e2e/` | 完整 IBCI 程序，验证端到端语言语义 | 直接访问 VM 帧栈/解释器内部 |
| `compliance/` | 仅公开 API（`IBCIEngine` / `host.*`）—— 跨实现合规规约 | 任何 `core/runtime/...` 内部 import |

## 命名规约

- **文件名**：`test_<concept>.py`；`concept` 是语言概念或子系统名，**不允许里程碑代号**（`m2/m3d/g1/d3/ns_/pt_/c\d` 等）。
- **测试类**：`Test<Concept><Aspect>`，例：`TestIntentContextActivePointer`，**不允许**前缀 `TestNS2b...`/`TestPT21...`。
- **测试方法**：描述行为，不写编号，例：`test_smear_intent_is_cleared_after_resolution`。
- 历史代号若必须出现，请放在 **docstring** 里说明，**不要进入文件名/类名/方法名**。

## 新增测试时

1. 先查 [`tests/COVERAGE_MAP.md`](./COVERAGE_MAP.md)（若尚未创建则参考 `docs/TESTS_REORGANIZATION_TASK.md` §5）找对应文件。
2. 找不到对应文件 → 先在 COVERAGE_MAP 加一行 + 写理由 → 再建新文件。
3. 严格遵守"分层职责"与"命名规约"。
4. 用 `conftest.py` 的统一 helper / fixture，不要复刻。

## 修 Bug 添加回归测试时

- 把新测试**并入最贴近问题的 concept 文件**下既有 `Test*` 类（或新建 `TestRegressions` 子类），不要为单个 issue/PR 新建文件。
- 测试 docstring 可引用 issue / `docs/COMPLETED.md` 锚点。

## 删除/修改测试时

- 严禁因"碍事"删除断言；refactor 时必须在 PR 描述逐条说明被改/删测试的语义是否被另一处承接。
- 已落地的功能其"反例测试"需要改为"正例测试"，不要整组删除。
