# tests/ — 测试体系

IBC-Inter 测试套件，单一分层模型（以实际目录为准）。

## 分层模型

| 层 | 定位 | 红线 |
|---|---|---|
| `kernel/` | 纯数据结构单元（TypeRef/Spec/Axiom） | 禁构造 IBCIEngine、禁运行 IBCI 代码 |
| `compiler/` | compile-only（含 `semantic/` 子包） | 禁 `run_ibci`（运行时用例归 e2e） |
| `runtime/` | 单子系统 + 小段 IBCI 代码（白盒） | 允许 internals |
| `plugins/` | 插件单元测试（pure Python，无 Engine） | — |
| `contracts/` | 语言不变量公理（INV-*，最小黑盒用例） | 黑盒，禁 internals |
| `e2e/` | 完整程序端到端（黑盒） | 禁 import `core.runtime.*` internals、禁私有属性穿透 |
| `compliance/` | 跨实现公开 API 黑盒合规 | 禁 internals |
| `sdk/` | SDK 工具（check_plugin / gen_spec） | — |
| `meta/` | **测试规范执行器**：分层/命名/helper 去重/矩阵同步机器校验 | — |
| `fixtures/` | 可复用 IBCI 样本 | — |

## 命名规范

- 文件名 `test_<concept>.py`；类名 `Test<Concept><Aspect>`。
- 禁里程碑代号（G1/M2/D3/NS/PT 等）。
- e2e 文件禁 `test_e2e_` 前缀（目录承载层义）；runtime 文件禁冗余 `test_runtime_` 前缀。

## 基础设施

- `conftest.py`：黑盒 API（`run_ibci`/`compile_ibci`/`compile_or_errors`/`expect_compile_error`/
  `expect_runtime_error`）+ `AI_MOCK_PREFIX`（单点真理）+ 会话 fixtures。
- `runtime/conftest.py`：白盒 helper（`make_vm`/`find_node*`/`native`/`make_intent`）。
- 禁止本地复刻统一 helper（meta `test_no_duplicate_helpers` 强制）。

## 覆盖矩阵

`COVERAGE_MATRIX.md`：`file::class::method` 三段式引用，meta `test_matrix_sync` 机器校验。

## 运行

```bash
conda activate ibci
python -m pytest tests/
```
