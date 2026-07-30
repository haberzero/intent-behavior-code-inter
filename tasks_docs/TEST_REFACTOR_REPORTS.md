# 测试体系重构调研报告归档（原始文本记录）

> **性质**：4 个独立 subagent 的只读调研原始报告，作为测试体系治理与彻底重构的事实依据归档。
> **生成时间**：2026-07-30
> **状态**：只读归档，不随重构进展修改；重构完成后随规划文档一并处置。
>
> 4 份报告分属独立维度：
> - 报告 A：测试结构与分类体系审计
> - 报告 B：测试冗余/合并/覆盖分析
> - 报告 C：内核测试可用面审计
> - 报告 D：测试方法论与文档一致性审计

---

# 报告 A：测试结构与分类体系审计

## ① 目录结构全貌（含数量统计）

**配置**：`pytest.ini:1-6` - `testpaths=tests`，`addopts=-q --tb=short --strict-markers`，仅注册 `slow`/`fast` 两个 marker。

**基础设施**：
- `tests/conftest.py`（388 行）- 全局唯一 helper/fixture 单点真理，提供 `run_ibci`/`compile_ibci`/`make_vm`/`find_node`/`make_intent` 等（`tests/conftest.py:95-301`）+ 8 个 fixture（`:309-388`）。
- `tests/COVERAGE_MAP.md`（139 行）- 概念->测试入口索引。
- `tests/README.md`（64 行）- 分层职责红线 + 命名规约。

**9 个测试子目录统计**（基于 `pytest --collect-only` 实跑）：

| 目录 | 文件数 | 用例数 | 职责定位 | conftest |
|------|--------|--------|----------|----------|
| `compiler/` | 6 | 180 | compile-only（断言 artifact / `SEM_*`/`PAR_*` 错误码） | 无 |
| `compiler/semantic/` | 7 | 111 | 语义分析 Pass 单元（analyzer/binding/type_system 等） | 有（31 行） |
| `contracts/` | 9 | 150 | 语言公理不变量（INV-* 黑盒，5-15 行最小用例） | 无 |
| `e2e/` | 19 | 308 | 完整程序端到端语义 | 无 |
| `runtime/` | 14 | 245 | 单子系统 + 小段 IBCI 代码（允许访问 internals） | 无 |
| `kernel/` | 4 | 67 | 纯数据结构单元（TypeRef/Spec/Axiom） | 有（42 行） |
| `compliance/` | 3 | 36 | 跨实现公开 API 黑盒合规 | 有（43 行） |
| `sdk/` | 2 | 56 | check_plugin / gen_spec 工具 | 无 |
| `meta/` | 2 | 43 | 测试体系自检（分层红线 + helper 去重） | 无 |
| `fixtures/` | 3（样本） | 0 | 可复用 IBCI 代码样本 | 无 |

**合计：66 个 test 文件，1196 个用例。**

## ② 分类体系现状与边界问题

### 现状
五层红线由 `tests/README.md:32-40` 定义，并由 `tests/meta/test_layering.py` 静态扫描强制：
- `kernel/` 禁启动 Engine（`test_layering.py:63-76`）
- `compiler/` 禁调 `run_ibci`（`test_layering.py:92-105`）
- `e2e/` + `compliance/` 禁 import `core.runtime.*` internals（`test_layering.py:112-151`）

### 边界问题

**P0-1｜compiler 混入 runtime（已知白名单违规）**
`tests/meta/test_layering.py:85-89` 显式白名单 3 个文件"pending split"：
- `tests/compiler/test_generics.py:62` - 调 `run_ibci`
- `tests/compiler/test_import_position.py:116` - 调 `run_ibci`
- `tests/compiler/test_type_annotations.py:281,294,305,320,333` - 5 处调 `run_ibci`

这 3 个文件混合了编译断言与运行时执行，违反 `tests/README.md:37`"compiler 禁止调 run_ibci"。meta 测试用 skip 掩盖了违规而非修复。

**P0-2｜test_path.py 归类错误（runtime->kernel）**
`tests/runtime/test_path.py:13` 仅 import `core.kernel.path`，全文 680 行/121 测试，无任何 `IBCIEngine`、无 `run_ibci`、无 `core.runtime`。其 docstring（`:10`）自述"纯数据结构/逻辑测试，不依赖 IBCIEngine"。按 `tests/README.md:36`（kernel 层"直接构造纯数据结构"），此文件应在 `tests/kernel/`。当前放在 runtime/ 既逃过了 `test_layering.py:63` 的 kernel 红线检查，又模糊了 runtime 层"小段 IBCI 代码"的定位。

**P1-1｜contracts 与 e2e 边界模糊**
两者均为黑盒语义测试，区分依据是 `tests/contracts/__init__.py:8-16`（contracts=最小用例验证单一不变量，INV-* 编号）vs `tests/README.md:39`（e2e=完整程序）。但实际存在重叠：
- 作用域/闭包：`tests/contracts/test_scope_semantics.py`（INV-CELL/INV-SNAPSHOT）与 `tests/e2e/test_e2e_higher_order.py:15-17`（自述"基础隔离语义的公理级覆盖在 contracts，本文件仅保留 e2e 独有场景"）- 边界靠注释维系，易漂移。
- `tests/e2e/test_e2e_nonlocal.py` 测试 nonlocal 作用域语义（211 行/11 测试），本质是 contracts 级单一不变量，却放在 e2e。

**P1-2｜test_multimodal_payload.py 跨层错位**
`tests/runtime/test_multimodal_payload.py:3` docstring 写着 `tests/e2e/test_e2e_multimodal_payload.py`，且其内容（`:18` 仅 `from tests.conftest import run_ibci`，黑盒执行）实为 e2e 级。文件物理位置（runtime/）、docstring 声称位置（e2e/）、实际行为（e2e）三者矛盾。同时 `tests/e2e/test_e2e_multimodal_file_io.py` 已存在，多模态测试被拆到两层。

**P1-3｜test_idbg.py / test_mock_directives.py 是插件单元测试，非 runtime**
`tests/runtime/test_idbg.py:1-3` 直接测 `ibci_modules.ibci_idbg`（pure Python，无 Engine）；`tests/runtime/test_mock_directives.py:11` 直接测 `AIPlugin._handle_mock_response`。两者既非 kernel 数据结构，也非"小段 IBCI 代码 + runtime 子系统"，更接近 sdk/ 或独立的 plugins 层。

## ③ 命名规范审计

`tests/README.md:44-47` 明确规定：文件名 `test_<concept>.py`、类名 `Test<Concept><Aspect>`、**禁止里程碑代号**（`m2/m3d/g1/d3/ns_/pt_/c\d`）。

### 违规

**P0-3｜类名含里程碑代号（15 处）**
- `tests/compiler/test_type_annotations.py:71,88,106,506` - `TestM2Optional*`（4 处）
- `tests/compiler/test_type_annotations.py:133,187,221,254,276` - `TestD3*`（5 处，含 `TestD3E2E`）
- `tests/compiler/test_generics.py:73,110,197,259,306,362,392` - `TestG1/G2/G3*`（7 处）

直接违反 `tests/README.md:45`"不允许前缀 TestNS2b.../TestPT21..."。

**P0-4｜COVERAGE_MAP 引用不存在的文件**
`tests/COVERAGE_MAP.md:37` 引用 `tests/compiler/semantic/test_override_and_super.py`，但该文件不存在（实际测试在 `tests/e2e/test_e2e_override_and_super.py`）。索引失真。

**P1-4｜e2e 类名前缀不一致**
e2e/ 共 ~70 个类，其中 ~45 个用 `TestE2E*` 前缀，~25 个不用（如 `TestAINative`、`TestBehaviorExprFieldAssignment`、`TestConcurrency`、`TestFnKeyword`、`TestNonlocalBasicSemantics`、`TestValidatePromptRuntime` 等）。同一目录两种风格分裂。

**P1-5｜runtime 文件名前缀不一致**
14 个文件中 4 个用 `test_runtime_*` 前缀（`test_runtime_getitem_contract.py`/`test_runtime_host_collect.py`/`test_runtime_multimodal_dispatch.py`/`test_runtime_serialization.py`），10 个不用。目录名已是 runtime，前缀冗余且不一致。

**P1-6｜docstring 路径过期（3 处）**
- `tests/e2e/test_e2e_nonlocal.py:2` 写 `tests/compiler/semantic/test_nonlocal.py`
- `tests/runtime/test_kernel_native_modules.py:3` 写 `tests/kernel/test_kernel_native_modules.py`
- `tests/runtime/test_multimodal_payload.py:3` 写 `tests/e2e/test_e2e_multimodal_payload.py`

**P1-7｜局部 `_run` helper 绕过 conftest**
`tests/e2e/test_e2e_kernel_native.py:15-19`、`tests/runtime/test_file_handle.py`、`tests/runtime/test_host_save_state.py`、`tests/runtime/test_idbg.py`、`tests/runtime/test_media_file_handle.py`、`tests/runtime/test_runtime_host_collect.py` 各自定义 `_run`/`_make` 局部函数。虽不在 `test_no_duplicate_helpers.py:52-67` 的 banned 列表内（故 meta 测试不报错），但与 `tests/conftest.py:95` 的 `run_ibci` 重复，违反 `tests/README.md:9`"禁止再自行定义"的精神。

**P2-1｜`test_p2_warnings.py` 文件名含代号**
"p2" 指 Pass 2，属 `tests/README.md:44` 禁止的代号风格。边界案例。

## ④ 文件粒度问题

### 超大文件（>500 行）

| 文件 | 行数 | 用例数 | 问题 |
|------|------|--------|------|
| `tests/runtime/test_path.py` | 680 | 121 | 单文件占 runtime 层 49% 用例；13 个 TestIbPath* 类可拆分 |
| `tests/e2e/test_e2e_higher_order.py` | 650 | 58 | 16 个类混合 fn/lambda/snapshot/behavior/factory，职责过宽 |
| `tests/e2e/test_e2e_classes.py` | 643 | 31 | 8 个类覆盖继承/枚举/相等/upcast/super，可按概念拆 |
| `tests/compiler/test_type_annotations.py` | 600 | 43 | 混合 M2/D3 代号 + compile/run 双关注点（P0-1） |
| `tests/e2e/test_e2e_llmexcept.py` | 597 | 26 | 8 个类，含 `TestE2EConditionUncertainBugA`（bug 代号命名） |
| `tests/compiler/test_pipeline.py` | 520 | 53 | 最大单文件用例数（compiler 层） |

### 过碎文件（≤3 测试）

| 文件 | 用例数 | 问题 |
|------|--------|------|
| `tests/e2e/test_e2e_prompt_protocol.py` | 1 | 单测试单类，从 kernel 分离而来（`:6`），可并入相邻 e2e 文件 |
| `tests/contracts/test_no_redundant_side_tables.py` | 1 | 单测试，contracts 层孤儿文件 |
| `tests/e2e/test_e2e_isolation_plugin_inheritance.py` | 2 | 与 `test_e2e_multi_interpreter.py` 主题相邻 |
| `tests/e2e/test_e2e_plugin_discovery.py` | 3 | 插件发现，可与 `test_e2e_modules.py` 合并 |

## ⑤ 结构不一致清单

| # | 问题 | 证据 | 严重度 |
|---|------|------|--------|
| 1 | compiler 3 文件混入 run_ibci（白名单掩盖） | `test_layering.py:85-89` | P0 |
| 2 | test_path.py 归类 runtime 但实为 kernel 纯单元 | `test_path.py:10,13` | P0 |
| 3 | 类名含 M2/D3/G1-G3 代号（15 处） | `test_type_annotations.py:71` 等 | P0 |
| 4 | COVERAGE_MAP 引用不存在的 override_and_super 文件 | `COVERAGE_MAP.md:37` | P0 |
| 5 | test_multimodal_payload.py 位置/docstring/行为三者矛盾 | `test_multimodal_payload.py:3,18` | P1 |
| 6 | 3 处 docstring 路径过期 | `test_e2e_nonlocal.py:2` 等 | P1 |
| 7 | e2e 类名 ~25/70 无 TestE2E 前缀 | `test_e2e_kernel_native.py:22` 等 | P1 |
| 8 | runtime 文件名 4/14 用冗余 runtime_ 前缀 | `test_runtime_serialization.py` 等 | P1 |
| 9 | 6 处局部 `_run` helper 绕过 conftest | `test_e2e_kernel_native.py:15` 等 | P1 |
| 10 | contracts/e2e 边界靠注释维系，nonlocal 归类存疑 | `test_e2e_nonlocal.py` 全文 | P1 |
| 11 | test_idbg/test_mock_directives 是插件单元，非 runtime | `test_idbg.py:1-3` | P1 |
| 12 | 多模态测试跨 runtime+e2e 两层拆分 | `test_multimodal_payload.py` + `test_e2e_multimodal_file_io.py` | P2 |
| 13 | test_path.py 680 行/121 测试过大 | `test_path.py` | P2 |
| 14 | 4 个过碎文件（≤3 测试） | 见 ④ 节 | P2 |
| 15 | test_p2_warnings.py 文件名含代号 | `test_p2_warnings.py` | P2 |
| 16 | e2e/test_e2e_llmexcept.py 含 `TestE2EConditionUncertainBugA` bug 代号类名 | `test_e2e_llmexcept.py:538` | P2 |

## ⑥ 重构提议

### 原则
- 保留全部现有覆盖，仅重组（不增删断言）。
- 每层有且仅有一种文件名风格、一种类名风格。
- 让 meta 测试红线能无白名单通过（删除 `test_layering.py:85-89` 的 skip）。

### 提议目录结构

```
tests/
├── conftest.py                 # 不变
├── README.md / COVERAGE_MAP.md # 同步修正
├── kernel/                     # 纯数据结构单元（禁 Engine）
│   ├── test_path.py            # ← 从 runtime/ 迁入（P0-2）
│   ├── test_config.py
│   ├── test_media_axioms.py
│   ├── test_prompt_protocol.py
│   └── test_resolve_call_return.py
├── compiler/
│   ├── test_lexer.py
│   ├── test_pipeline.py
│   ├── test_generics.py        # 拆出 run_ibci 部分 -> e2e；类名去 G1/G2/G3 代号
│   ├── test_type_annotations.py# 拆出 run_ibci 部分 -> e2e；类名去 M2/D3 代号
│   ├── test_import_position.py # 拆出 run_ibci 部分 -> e2e
│   ├── test_symbol_collection_pass.py
│   └── semantic/               # 保持子包
│       ├── test_analyzer.py
│       ├── test_binding_analysis_pass.py
│       ├── test_pass_warnings.py   # ← rename test_p2_warnings.py（去代号）
│       ├── test_pass_fixes.py
│       ├── test_scoped_visitor.py
│       ├── test_type_inference_state.py
│       └── test_type_system.py
├── runtime/                    # 单子系统 + internals 访问
│   ├── test_file_handle.py
│   ├── test_host_save_state.py
│   ├── test_media_file_handle.py
│   ├── test_multimodal_dispatch.py  # ← rename（去冗余前缀）
│   ├── test_getitem_contract.py
│   ├── test_host_collect.py
│   ├── test_serialization.py
│   ├── test_storage_model_dispatch.py
│   └── test_kernel_native_modules.py
├── plugins/                    # ← 新层：插件单元测试
│   ├── test_idbg.py
│   ├── test_mock_directives.py
│   └── test_plugin_implementations.py
├── contracts/                  # 不变量公理（INV-*，最小用例）
│   ├── ...（含 test_nonlocal_semantics.py ← 从 e2e 迁入）
├── e2e/                        # 完整程序端到端
│   ├── ...（统一去 e2e_ 前缀由目录承载层义；test_multimodal.py 合并）
├── compliance/                 # 不变
├── sdk/                        # 不变
├── meta/
│   ├── test_layering.py        # 删除白名单
│   └── test_no_duplicate_helpers.py  # 扩展 banned 列表
└── fixtures/                   # 不变
```

### 执行优先级
1. **P0**：拆分 compiler 3 文件的 run_ibci 部分->e2e；迁 test_path.py->kernel；去 M2/D3/G1-G3 类名代号；修正 COVERAGE_MAP.md:37。
2. **P1**：统一 e2e 文件名/类名；统一 runtime 文件名去冗余前缀；修 3 处 docstring；新建 plugins/ 层；迁 test_multimodal_payload->e2e 并合并。
3. **P2**：拆 test_path.py / test_e2e_higher_order.py / test_e2e_classes.py；合并 ≤3 测试的过碎文件；扩展 meta banned helper 列表禁 `_run`。

### 风险提示
- 迁移 test_path.py 后需确认 `tests/kernel/conftest.py` 的 `spec_reg`/`factory` fixture 不被误触发。
- 拆分 compiler 混合文件时，`test_type_annotations.py:276 TestD3E2E` 整个类是 run_ibci，应整体迁出。
- 新建 `tests/plugins/` 层需同步更新 `test_layering.py` 的扫描范围与 README 分层表。

---

# 报告 B：测试冗余/合并/覆盖分析

> 范围：`tests/` 全量（41 文件，collect 约 1183 项）。基线 `1173 passed / 10 skipped`。

## ① 冗余/重复测试清单

### A. 真冗余（可安全剔除/合并）

**R1. `tests/contracts/test_scope_semantics.py:150-152` - 重复执行 + 重复断言**
`test_snapshot_each_call_independent`（INV-SNAPSHOT-3）对同一段代码连续 `run_ibci(code)` 两次，且第二次的 4 条断言与第一次**完全相同**。确定性语义下第二次运行无新增信息。**处置：删除 :150-152 的第二次 `run_ibci` 及其两条断言。** 覆盖不变。

**R2. `tests/e2e/test_e2e_llm_basic.py:24-62` - MOCK 基本协议与 contracts 重复**
`TestE2EAIMockBasic` 的 4 个测试与 `tests/contracts/test_llm_integration.py:30-58`（`TestMOCKProtocol`）验证**同一不变量**。两者唯一差异是 e2e 用 `str result` + 断言 `"1"`，contracts 用 `bool result` + 断言 `"True"`。**处置：contracts 保留；e2e 的 4 个可删。但 `test_mock_float_type` (:48) 独有（contracts 未参数化 FLOAT），应迁入 contracts 的 `parametrize` 再删 e2e。**

**R3. `tests/e2e/test_e2e_llmexcept.py:104-124` 与 contracts 部分重叠**
"耗尽抛 LLMRetryExhaustedError"核心不变量已被 `contracts/test_llmexcept_guarantees.py:136-147` 覆盖。e2e 版**额外**断言了"catch 后作用域不被污染"（独有值）。**处置：不可直接删--拆出 scope-clean 部分保留，纯耗尽断言视为已被 contracts 承接。**

### B. 假重复（测不同层/不同关注点，不可剔除）

**F1. `tests/runtime/test_runtime_getitem_contract.py` vs `tests/contracts/test_collection_semantics.py`**
runtime 层直接操作 `IbList`/`IbTuple`/`IbDict`/`IbString` 对象（验证对象协议层、`to_native()` 拆箱、键 unboxing）；contracts 走完整编译+运行管线（验证语言级可观察语义）。runtime 的 `TestGetitemKeyUnboxing` 是 contracts 无法触及的路径。**不可删，互补。**

**F2. `tests/compiler/semantic/test_type_system.py` vs `tests/contracts/test_type_invariants.py`**
compiler/semantic 验证 Pass 机制；contracts 黑盒验证语言不变量。**不可删。**

**F3. `tests/compliance/test_memory_model.py` vs `tests/contracts/test_scope_semantics.py`**
compliance 仅用公开 API（跨实现合规规约）；contracts 用 `run_ibci`（验证语言语义）。TEST_PHILOSOPHY §Q5 明确定义此区分。**不可删。**

**F4. `tests/compliance/test_execution_isolation.py` vs `tests/e2e/test_e2e_multi_interpreter.py`**
compliance 黑盒公开 API；e2e 全栈集成（额外测并发时序、IBCI 层 ihost API）。**不可删。**

## ② 可合并清单（含等价性论证）

**M1. contracts `TestMOCKProtocol` 参数化扩展吸收 e2e 独有项**
将 `MOCK:FLOAT:3.14`、`MOCK:STR:"hello world"` 加入 contracts `parametrize`。合并后 e2e 的 `TestE2EAIMockBasic`（4 个重复项）+ `TestE2EMockStrQuoted`（3 项）可精简为 contracts 的 1 个参数化测试，覆盖等价。

**M2. `test_e2e_llmexcept.py` for-loop 系列可参数化合并**
`TestE2ELLMExceptForLoopMock`（`:139-253`）6 个测试结构高度同构（仅 SEQ 序列与断言数字不同）。提取为 1 个 `parametrize` 测试类，参数为 `(seq, expected_handler_count, expected_count, fail_item=None)`。注意 `test_inner_llmexcept_prints_correct_item_when_failing`（`:215`）有顺序断言，需单独保留或参数化时携带 `expected_item`。

**M3. `test_e2e_exceptions.py` `TestExceptionAcrossFunctionBoundary` 可参数化合并**
4 个测试（`:272-368`）结构同构，参数化为 `(exception_def, raise_call, except_clause, expected_asserts)`。需先补 H1 缺口（见 ④）。

## ③ 覆盖缺口

**G1. INV-STR-6 字符串不可变性 - 名存实亡（严重）**
`test_collection_semantics.py:245-257` 的 `test_str_immutability` **未测不可变性**。代码仅做 `str s2 = s` 赋值后打印，注释自承"For now, just verify string operations don't mutate"。全仓库无任何测试尝试 `s[0] = "H"` 并期望报错。**需补：对 `str` 下标赋值应断言编译期/运行期错误。**

**G2. 控制流基础语法文件已删除（矩阵标 🔶）**
if/elif/else、while、for-in、for...if 过滤均标 🔶"需要补充集成测试"。在 contracts/llmexcept 中有间接覆盖，但**无专项集成测试**。

**G3. 模块缓存机制 / 模块重新加载（矩阵标 ❌）**
§7.1 `模块缓存机制` ❌、§7.3 `模块重新加载` ❌。

**G4. bound_method 语义（矩阵标 ❌）**
§8.3 `bound_method 语义` ❌，标注"需要评估"。

**G5. INV-LAMBDA-3 / INV-SCOPE-1 - SKIPPED（设计限制，非缺口）**
属设计限制，非紧急缺口。

**G6. `test_e2e_llm_basic.py:159-194` `TestE2EStaleResultIsolation` 整组 SKIPPED**
依赖 `dispatch_eager`（已禁用）。4 个测试全 skip。接通并发调度前为已知限制。

## ④ `_defect_review` 6 项测试项核验

**D1. `test_runtime_getitem_contract.py:13` - 陈旧 module docstring** ✅ 仍存在 / 严重度：低 / 处置：修
模块 docstring 称"IbDict 缺键抛原始 `KeyError`"，但同文件 `test_missing_key_raises_interpreter_error`（:63-69）已断言 `InterpreterError`。**代码已修复，docstring 未同步。**

**D2. `test_collection_semantics.py:256` - INV-STR-6 未测变异** ✅ 仍存在 / 严重度：中 / 处置：修（补真测试）
见 ③G1。**处置：将测试改为对 `s[0] = "H"` 断言编译期/运行期错误。**

**D3. `test_scope_semantics.py:155` - 冗余重复断言** ✅ 仍存在 / 严重度：低 / 处置：删
见 ①R1。**处置：删除 :150-152。**

**D4. `test_e2e_exceptions.py:276` - H1 覆盖缺口** ✅ 仍存在 / 严重度：中 / 处置：补
当前仅覆盖：用户子类、用户子类+额外字段、LLMRetryExhaustedError、两层嵌套。**缺口**：LLMParseError 跨边界、两级用户继承链跨边界、用户 LLMError 子类跨边界、`except X as e` 中 e 类型精确性跨边界。**处置：补 2-3 个跨边界测试。**

**D5. `test_e2e_llmexcept.py:497` - 部分快照协议未验状态** ✅ 仍存在 / 严重度：中 / 处置：修
`test_snapshot_only_defined_no_restore_is_safe`（:495-516）仅断言 `"ok" in lines`，**未验证** `__snapshot__` 是否被调用、`saved_protocol_states` 是否记录。对比同组 `test_user_object_snapshot_protocol`（:470-493）明确断言了 `"protocol_snap"`/`"protocol_restore"`。**处置：补 `__snapshot__` 调用断言 + 对象值不变断言。**

**D6. `test_meta/test_layering.py:85` - 混合测试白名单** ✅ 仍存在 / 严重度：中 / 处置：拆分
`_COMPILER_KNOWN_RUN_IBCI_VIOLATIONS`（:85-89）白名单 3 文件。**处置**：将各文件中 `run_ibci` 调用的测试迁至 `tests/e2e/`，保留 `compiler/` 仅 `compile_ibci`/`compile_or_errors`，然后从白名单移除。`test_generics.py` 的本地 helper 须一并改用 `conftest.run_ibci`。

## ⑤ 覆盖保活策略

**P1. 前后 collect 数对照（强制）**
重构前后各跑 `python3 -m pytest tests/ --collect-only -q`，记录 per-file 计数。任何文件测试数下降须在 PR 逐条说明被删测试的语义由哪条承接。

**P2. 语义矩阵对照**
重构后逐条核对 `SEMANTIC_COVERAGE_MATRIX.md` 的 INV-* 编号：每个 ✅ 项须仍能定位到至少一个测试（file:line）。

**P3. 分批小步 + 全绿门禁**
每批只处理一个 R/M/D 项，每批后跑 `python3 -m pytest tests/` 必须不退化（skipped 数不增）。meta 测试必须保持通过（D6 拆分后 layering 白名单应收缩）。

**P4. 删除前先承接**
对 R2/R3 类"删 e2e 保 contracts"的合并，**先确认 contracts 测试确实通过**，再删 e2e 项；对 M2/M3 参数化合并，**先写新参数化测试并跑通**，再删旧散测。禁止"先删后补"。

**P5. 缺口先行**
③G1（INV-STR-6）、D2、D4、D5 属于"名义覆盖实则未测"，应在重构**之前或同时**补真测试。

**P6. 不碰设计限制项**
G5、G6 属设计限制，重构不应试图取消 skip。

**核心结论**：真冗余极少（仅 R1 完全可安全删，R2/R3 需"先迁后删"）；多数"看似重复"是分层互补（F1-F4 不可删）。最大风险不是冗余而是**名义覆盖实为空**（③G1 INV-STR-6、D2/D4/D5）。D6 白名单拆分是独立的层级治理工作。

---

# 报告 C：内核测试可用面审计

## ① 当前交互面盘点

### A. 正式公开的 Engine API（`core/engine.py`）
| 入口 | file:line | 用途 |
|---|---|---|
| `IBCIEngine(root_dir=, auto_sniff=, core_debug_config=, inherited_plugin_paths=, inherited_global_plugin=)` | `core/engine.py:67` | 构造引擎；`auto_sniff=False` 是测试默认 |
| `run_string(code, variables, output_callback, silent, prepare_interpreter)` | `core/engine.py:481` | 测试主力入口 |
| `run(entry_file, ..., silent)` | `core/engine.py:502` | 文件级执行 |
| `compile_string(code, variables, silent)` | `core/engine.py:451` | 仅编译 |
| `compile(entry_file, variables, silent)` | `core/engine.py:548` | 文件级编译 |
| `check(entry_file, silent)` | `core/engine.py:635` | 静态检查 |
| `execute(artifact, variables, output_callback)` | `core/engine.py:586` | 执行已编译产物 |
| `set_variable / get_variable` | `core/engine.py:620,628` | 注入/读取解释器变量 |
| `register_native_module(name, impl, metadata)` | `core/engine.py:418` | 注册原生模块 |
| `request_spawn_isolated / request_collect` | `core/engine.py:744,784` | 隔离 spawn/collect |
| `resolve_semantics(module, raise_on_error, analyzer)` | `core/engine.py:661` | 暴露中间语义分析产物 |
| 公开属性 `registry / debugger / capability_registry / host_interface / object_factory / rt_scheduler / interpreter / scheduler / root_dir / auto_sniff` | `core/engine.py:82-206` | 测试直接读取 |

### B. 正式公开的 Interpreter / ServiceContext / KernelRegistry 接口
- `Interpreter` 公开 property：`execution_context`（`interpreter.py:318`）、`runtime_context`（:326）、`node_pool`（:334）、`logical_stack`（:342）、`stack_inspector`（:346）、`registry`（:314）、`symbol_view`（:322）、`service_context`（:190/215）、`current_module_name`（:306）。
- `ServiceContext` Protocol 公开 property：`registry/issue_tracker/llm_executor/module_manager/object_factory/interop/permission_manager/host_service/source_provider/orchestrator/debugger/scheduler/capability_registry`（`core/runtime/interfaces.py:313-340`）。
- `KernelRegistry` 公开 getter：`get_class/get_all_classes/get_none/get_llm_executor/get_host_service/get_stack_inspector/get_state_reader/get_execution_context/get_metadata_registry/get_intrinsic_instance/is_sealed`（`core/kernel/registry.py:141-261,337-346`）。
- `ExecutionContextImpl` 公开可观测字段：`llmexcept_body_depth`（`execution_context.py:183`，含 `enter_llmexcept_body/exit_llmexcept_body`）、`stack_inspector`（:128）、`strict_mode`（:196）、各 pool（:88-125）、`get_call_stack_depth/get_active_intents/get_instruction_count/get_current_script_path`（:228-252）。

### C. conftest 统一 helper（`tests/conftest.py`）
`run_ibci/compile_ibci/compile_or_errors/expect_compile_error/expect_runtime_error`（:95-201）；`make_vm`（:208）；`find_node(s)/find_node_uid(s)`（:218-268）；`native`（:271）、`make_intent`（:280）；`AI_MOCK_PREFIX`（:83）；fixtures（:309-388）；`pytest_configure`（:73，强制 basetemp）。

### D. 确定性 LLM mock 机制
- `AIPlugin.set_config(url,key,model,**kwargs)`（`ibci_ai/core.py:110`）- 设 `TESTONLY` 进入 mock 模式。
- `AIPlugin.__call__` -> `_handle_mock_response`（:354,543）- MOCK 指令 DSL（FAIL/TRUE/FALSE/REPAIR/INT/STR/FLOAT/BOOL/LIST/DICT/SEQ）。
- `reset_mock_state()`（:59）；`get_last_call_info()`（:316）；`probe_model()`（:191）。

### E. ibci_sdk 工具
`check_plugin(plugin_dir)`（`ibci_sdk/check.py:53`）；`_load_module`（:228）自管 sys.path 清理 + `importlib.invalidate_caches()`；`gen_spec/gen_spec_file`（`ibci_sdk/__init__.py:9`）。

### F. silent 参数
`compile_string/run_string/run/compile/check` 均有 `silent: bool = False`（`engine.py:451,481,502,548,635`），同步到 `self.debugger.silent`（:565）。测试统一传 `silent=True`。

## ② 私有属性穿透清单

| # | 穿透点 | file:line | 访问对象 | 现有公开替代？ |
|---|---|---|---|---|
| 1 | `engine.interpreter._execution_context` | `tests/conftest.py:213`；`test_runtime_serialization.py:32,106,117` | Interpreter 私有字段 | ✅ 有公开 property `interpreter.execution_context`（`interpreter.py:318`）- **可直接替换，属明显遗漏** |
| 2 | `eng._spawned_tasks_lock` / `eng._spawned_tasks` | `test_e2e_multi_interpreter.py:228-229` | Engine 私有任务表 + 锁 | ❌ 无公开替代 |
| 3 | `eng._resolve_plugin_search_paths(project_root)` | `test_e2e_engine_lifecycle.py:192,286,305` | Engine 私有方法 | ❌ 无公开替代 |
| 4 | `eng._install_path` | `test_e2e_engine_lifecycle.py:192` | Engine 私有字段 | ❌ 无公开替代 |
| 5 | `eng._explicit_root` | `test_e2e_engine_lifecycle.py:108,114,158` | Engine 私有字段 | ❌ 无公开替代 |
| 6 | `eng._cwd` | `test_e2e_engine_lifecycle.py:164` | Engine 私有字段 | ❌ 无公开替代 |
| 7 | `eng._path_ctx` | `test_e2e_engine_lifecycle.py:176,361,370,376,383,395,403` | Engine 私有 PathContext | ❌ 无公开替代 |
| 8 | `executor._pending_futures` | `test_e2e_llm_pipeline.py:54,67,81,108,121` | LLMExecutorImpl 私有 future 表 | ❌ 无公开替代 |
| 9 | `file_module._file_handle_class()` | `test_media_file_handle.py:107,115,123` | FileLib 私有方法 | ❌ 无公开替代 |

## ③ 测试预留机制现状

### 3.1 MOCK 指令系统（`ibci_ai/core.py:543-751`）
完整字符串 DSL，集中于 `_handle_mock_response`。问题：无注册口（硬编码在 AIPlugin）；哨兵字符串 `"__MOCK_REPAIR__"` / `"MAYBE_YES_MAYBE_NO_this_is_ambiguous"` 跨模块靠魔法字符串耦合（共 6+ 处）；`MOCK:SEQ` 计数器跨测试不自动隔离。

### 3.2 TESTONLY 配置判定（散落 4 处，逻辑重复且不一致）
| 位置 | file:line | 判定条件 |
|---|---|---|
| `_init_client` | `ibci_ai/core.py:83-86` | `url=="TESTONLY"` OR `os.environ["IBC_TEST_MODE"]=="1"` |
| `_get_named_client` | `ibci_ai/core.py:159-162` | 同上（重复） |
| `probe_model` | `ibci_ai/core.py:197` | `key=="MOCK_KEY"` OR `url=="TESTONLY"` - **多了 `MOCK_KEY`，不一致** |
| `__call__` | `ibci_ai/core.py:355-358` | 同 `_init_client`（重复） |

4 处复制粘贴；`MOCK_KEY` 孤儿；测试入口双轨（TESTONLY 字符串 vs `IBC_TEST_MODE` 环境变量）未统一文档化。

### 3.3 AI_MOCK_PREFIX 常量散落（违反 conftest 自身的"单一真理"声明）
conftest.py:43 自称 single source of truth，实际重复：`tests/conftest.py:83`、`tests/fixtures/llm_samples.py:11`（`AI_SETUP`）、`tests/compliance/test_concurrent_llm.py:33-35`（`AI_SETUP`）、`tests/e2e/test_e2e_file_kernel_native.py:19`、`tests/e2e/test_e2e_multimodal_file_io.py:24-28`（变体）、`tests/compiler/test_import_position.py`（7 处内联）、`tests/e2e/test_e2e_multi_interpreter.py:353,389`、`tests/e2e/test_e2e_kernel_native.py:44`。

### 3.4 silent 参数
统一 `silent` 形参，同步 `debugger.silent`。问题：`silent` 同时承担"抑制用户错误打印"和"抑制内核 trace"两职责，语义过载；spawn 子引擎硬编码 `silent=True`（:770）。

### 3.5 llmexcept_body_depth（`execution_context.py:183-193`）
显式 test-observable 字段，`enter/exit_llmexcept_body` 成对调用。**唯一一个显式为测试可观测性设计的内核字段**，设计清晰，可作为后续 test hook 的范式。

### 3.6 ibci_sdk/check.py 的 sys.path 清理
`_load_module`（:228-286）自管 `sys.path.insert` + `finally` 清理 + `importlib.invalidate_caches()`。与 Engine 的 plugin 加载各自独立，无统一"模块加载清理 API"。

## ④ 封装纪律问题

### 4.1 `hasattr` 动态属性探测
`tests/compiler/semantic/test_binding_analysis_pass.py:164` `assert hasattr(behavior, 'llm_deps')`；:166/202 同。`llm_deps`/`dispatch_eligible` 是 `BehaviorDependencyPass` 运行时动态注入到 AST 节点的属性，未在 `IIbBehavior` Protocol（`interfaces.py:259-267`）声明。应在 Protocol 或 pass 产物上正式暴露。

### 4.2 私有字段直接读写（见 ② 节，9 类）
最严重 #1：`engine.interpreter._execution_context` 在 4 处使用，而公开 property `execution_context` 早已存在-**纯遗留穿透，零成本可修**。`tests/contracts/__init__.py:14` 明文禁 internals（如 node_pool），但 `node_pool` 实为公开 property-纪律文档需校准。

### 4.3 测试内联构造 Dummy 双胞（`tests/runtime/test_idbg.py`）
`_DummyKernelRegistry`/`_DummyExecutionContext`/`_DummyStateReader`/`_DummyStackInspector`/`_DummyCapabilities`（:6-72）-测试自造内核协议替身。Protocol 已 `@runtime_checkable`，但测试不引用内核 Protocol 做契约校验，Dummy 可能漂移；无内核提供的 test-double 基类。

## ⑤ 内核改进提议（正式测试接口）

**提议 1**：`Interpreter.execution_context` 替代 `_execution_context` 穿透（零内核改动，纯测试侧）。
**提议 2**：`IBCIEngine.test_snapshot()` / `inspect_state()` 内省 API-返回 frozen dataclass（explicit_root/cwd/path_ctx/plugin_search_paths/install_path/spawned_handles/root_initialized）。替代 ②#2-7 的 12 处穿透。
**提议 3**：`resolve_plugin_search_paths()` 公开为正式方法（去下划线或经 snapshot 暴露）。
**提议 4**：`LLMExecutor` 暴露 `pending_future_count()` / `has_pending(node_uid)` 观测口（线程安全读 `_pending_futures`）。替代 ②#8 的 5 处穿透。
**提议 5**：统一 LLM mock 注册口（取代 TESTONLY 散落判定）。`is_test_mode` 收敛为单一私有方法；废弃 `IBC_TEST_MODE` 或显式声明优先级。
**提议 6**：MOCK 哨兵字符串常量化（`MOCK_REPAIR_SENTINEL`/`MOCK_AMBIGUOUS_SENTINEL`），AIPlugin 与 executor 共同引用。替代 6 处魔法字符串。
**提议 7**：`IIbBehavior` Protocol 正式声明 `llm_deps`/`dispatch_eligible`。替代 ④.1 的 `hasattr` 探测。
**提议 8**：`FileLib` 暴露 `get_file_handle_class()` 或经 `registry.get_class` 获取。替代 ②#9。
**提议 9**：内核提供 test-double 基类（`NullStackInspector`/`NullStateReader`/`DummyServiceContext`），供 test_idbg 等复用。
**提议 10**：统一模块加载清理 API（`path_scoped_import` 上下文管理器），`check_plugin` 与 `ModuleLoader` 共用。

**优先级**：提议 1（零成本）-> 提议 7（Protocol 契约化）-> 提议 5+6（mock 收敛）-> 提议 2+3+4（内省 API）-> 提议 9+10（test 基建）-> ⑥ 预留字段（渐进）。

## ⑥ 预留字段建议

**6.1 `IsolationPolicy`**：增 `test_mode: bool = False`（取代隐式 `silent=True` 硬编码于 :770）；`mock_provider: Optional[str] = None`（声明子环境使用的 mock provider）。
**6.2 `ServiceContext`**：增 `test_hooks: Optional[TestHooks]` property。`TestHooks` 为 Protocol，含 `on_llm_call`/`on_dispatch`/`on_llmexcept_enter/exit` 等可选回调；生产 None、测试注入。
**6.3 `ExecutionContextImpl`**：增 `last_llm_call: Optional[LLMCallRecord]`（含 sys_prompt/user_prompt/scene/response/raw_response）；`reset_test_state()` 方法清空所有测试可观测字段。
**6.4 `IBCIEngine`**：增 `test_snapshot()` + `reset_test_state()` 方法（重置 Engine 级测试可观测状态，含 spawned_tasks 残留）。
**6.5 不建议预留**：`AIPlugin._config`（`set_config` 已公开，TESTONLY 应被提议 5 取代）；`KernelRegistry`（getter 已完备，封装最干净）。

---

# 报告 D：测试方法论与文档一致性审计

## ① 方法论现状

**TEST_PHILOSOPHY 阐述的分层模型**（`tests_docs/TEST_PHILOSOPHY.md:50-71`）为**四层金字塔**：`Examples`（5%）、`Compliance`（20%）、`Contracts`（70%）、`Regression`（5%）。

**不变量体系**：`INV-XXX-N` 编号系统（`L362-371`），建议设计文档分配编号、测试 docstring 引用。黄金法则：最小化（一测试一不变量）、黑盒优先、参数化复用、IBCI 代码 ≤15 行（`L196-202`）。

**MOCK 策略**（`L17`）：测试验证 MOCK 协议正确性而非 LLM 实际输出；统一前缀 `AI_MOCK_PREFIX`（`conftest.py:83`），通过 `run_ibci(code, ai=True)` 注入。

**SEMANTIC_COVERAGE_MATRIX 覆盖模型**（`MATRIX:18-22`）：四态标记 `✅充分/🔶需集成/❌缺失/⚠️待评估`，按 13 个语义域组织，每行映射 `语义特性 -> INV 编号 -> 测试位置`。

## ② 文档与实践脱节清单

### 脱节 A：分层模型三方不一致（最严重）
- `TEST_PHILOSOPHY.md:54-71` 定义四层 `Examples/Compliance/Contracts/Regression`，但**实际无 `regression/`、无 `examples/` 目录**。
- `tests/README.md:34-40` 定义**另一套**五层表 `kernel/compiler/runtime/e2e/compliance`，与哲学文档完全不同，且**不含 `contracts/`**。
- 实际目录有 8 个（含 `contracts/meta/sdk/fixtures`），两份文档都未完整覆盖。`meta/` 在两份文档中均无定位。

### 脱节 B：矩阵"测试位置"列大面积虚构测试名
矩阵引用的测试函数名与实际严重不符。抽样核验（grep 实际 `def` 定义）：

| 矩阵引用名（虚构） | 矩阵行 | 实际名 | 实际位置 |
|---|---|---|---|
| `test_optional_accepts_none` | `MATRIX:42` | `test_optional_accepts_value_of_T` | `test_type_invariants.py:46` |
| `test_optional_rejects_wrong_type` | `MATRIX:43` | `test_optional_is_some_compile_contract` | `test_type_invariants.py:59` |
| `test_optional_chaining_safe` | `MATRIX:44` | （不存在） | - |
| `test_smear_intent_one_shot` | `MATRIX:169` | `test_smear_intent_cleared_after_use` | `test_intent_propagation.py:177` |
| `test_stack_intent_persists` | `MATRIX:170` | `test_append_adds_to_existing` | `test_intent_propagation.py:88` |
| `test_remove_intent_works` | `MATRIX:171` | `test_remove_clears_intents` | `test_intent_propagation.py:97` |
| `test_override_clears_stack` | `MATRIX:177` | `test_override_replaces_existing` | `test_intent_propagation.py:79` |
| `test_function_call_intent_isolated` | `MATRIX:192` | `test_function_intent_isolated` | `test_intent_propagation.py:163` |
| `test_return_clears_smear` | `MATRIX:202` | `test_smear_intent_cleared_after_use` | `test_intent_propagation.py:177` |
| `test_mock_str_deterministic` 等 3 条 | `MATRIX:212-214` | `test_mock_true_returns_truthy` 等 | `test_llm_integration.py:30` |
| `test_behavior_expr_executes_llm` 等 4 条 | `MATRIX:220-223` | （均不存在） | - |
| `test_llm_function_definition` | `MATRIX:229` | `test_llm_function_definition_and_call` | `test_llm_integration.py:115` |
| `test_retry_block_executes` | `MATRIX:257` | `test_retry_executes_on_error` | `test_llmexcept_guarantees.py:43` |
| `test_error_history_tracked` | `MATRIX:265` | `test_error_history_accumulates` | `test_llmexcept_guarantees.py:88` |
| `test_depth_limit_enforced`/`test_excessive_depth_fails` | `MATRIX:272-273` | `test_reasonable_depth_succeeds`/`test_exhausted_retries_raises` | `test_llmexcept_guarantees.py:120,136` |
| `test_uncertain_flag_propagates`/`test_uncertain_blocks_operations` | `MATRIX:279-280` | `test_uncertain_value_isolated`/`test_str_plus_uncertain_concatenates` | `test_llmexcept_guarantees.py:158,168` |
| `test_cell_shared_reference_visible`/`test_cell_mutation_visible_to_all` | `MATRIX:125-126` | `test_cell_captures_reference`/`test_multiple_closures_share_cell` | `test_scope_semantics.py:30,43` |
| `test_lambda_captures_outer_variable`/`test_snapshot_deep_clone_at_definition` | `MATRIX:132,140` | （均不存在，名不同） | - |

**结论**：矩阵"测试位置"列基本是一份**设计期愿望清单**，非实际测试索引，无法用作"概念->测试"导航。

### 脱节 C：契约测试只验编译，不验运行时语义
`test_type_invariants.py:28-32` 的 `test_optional_none_access_raises` docstring 自承"Runtime method dispatch for Optional is not yet wired"，实际仅 `assert compile_ibci(code) is not None`。哲学称 contracts 验证"语言语义不变量"（运行时），但 Optional 契约只测编译期--标 ✅ 与实际测试深度不符。

### 脱节 D：COVERAGE_MAP 缺失 10 个 e2e 文件
实际存在但未索引：`test_e2e_engine_lifecycle.py`、`test_e2e_file_kernel_native.py`、`test_e2e_isolation_plugin_inheritance.py`、`test_e2e_kernel_native.py`、`test_e2e_model_routing.py`、`test_e2e_multimodal_file_io.py`、`test_e2e_nonlocal.py`、`test_e2e_override_and_super.py`、`test_e2e_plugin_discovery.py`、`test_e2e_prompt_protocol.py`。COVERAGE_MAP 自定规则"新增测试必须先在本表登记"（`COVERAGE_MAP.md:4`），但已破窗。

### 脱节 E：矩阵引用已删文件
`MATRIX:61,370,405,412` 仍引用 `test_e2e_control_flow.py`/`test_e2e_tuple_unpack.py` 并标注"已删除"--历史残留。

## ③ conftest 体系化评估

**优点**：根 `tests/conftest.py` 体系化程度较高-顶部有完整 API 文档头，按职责分组，命名一致（`run_ibci`/`compile_ibci`/`compile_or_errors`/`expect_*` 正负样本对称）。子目录分层 conftest 各司其职。

**问题**：
1. **`helpers` 聚合 fixture 近乎死亡**（`conftest.py:367-388`）：全仓库仅 `test_scoped_visitor.py` 1 处真用。形成"双路径 API（import 或 fixture）但一条近乎废弃"的冗余。
2. **kernel conftest 别名 workaround 违反工作模式定论**（`tests/kernel/conftest.py:6-7,29-32`）：因"不同文件用 `ax_reg` 与 `axiom_registry` 两种命名"，用别名同时暴露两者-AGENTS.md 禁止的 compat shim 思路。
3. **跨 conftest 命名碰撞、语义不同**：`axiom_registry` 在 `kernel/conftest.py:31`（module scope，已 populate core axioms）与 `compiler/semantic/conftest.py:14`（function scope，空 `AxiomRegistry()`）**同名不同义**。
4. **白盒 helper 混入"黑盒"基础设施**：`make_vm`（:208-215）访问 `engine.interpreter._execution_context` 私有属性；`find_node*` 遍历 `node_pool`。哲学强调黑盒，但核心 helper 本身是白盒-与 e2e/compliance 层红线存在张力。
5. **`find_node` 语义自相矛盾**（:240-248）：docstring 说"不严格要求唯一"，却又在无匹配时抛 `AssertionError`。

**应抽取为正式 test utility**：`make_vm`/`find_node*` 应从"通用 conftest"剥离到 `tests/_internals.py` 或 `tests/runtime/conftest.py`，按层隔离。

## ④ meta 测试定位与扩展建议

**现状定位**：`tests/meta/` 仅 2 文件，静态扫描强制测试套件自身的结构边界：`test_layering.py`（五层红线）、`test_no_duplicate_helpers.py`（禁本地复刻 helper）。

**对"结构统一化"的作用**：当前**唯一**能机器化守住测试规范的机制，方向正确，但覆盖严重不足。

**缺口**：
1. **禁列不完整**（`test_no_duplicate_helpers.py:52-67`）：禁 `make_engine`/`run_and_capture`/`compile_code` 等，但**漏禁** `run_ibci`/`compile_ibci`/`compile_or_errors`/`expect_compile_error`/`expect_runtime_error`/`find_node`/`find_nodes`。且禁 `compile_code`（错误名，真实是 `compile_ibci`）-禁列与 conftest 真实 API 脱节。本地 `def run_ibci()` 能逃过检测。
2. **层级红线有 3 文件白名单**（`test_layering.py:85-89`）：已知 mixed-concerns 却 `pytest.skip`-红线未真正强制。
3. **`__init__.py:8-11` 声称的职责未实现**：列出"Consistent naming conventions / Proper use of fixtures / Test organization"，但**无任何 meta 测试**强制命名规范、无 docstring 不变量检查、无 COVERAGE_MAP/矩阵同步检查。
4. **`test_conftest_provides_helpers`（:105-134）只查 5 项**，不覆盖全 API。

**扩展建议**（按优先级）：
- 新增 `test_naming_conventions.py`：正则扫描禁里程碑代号。
- 扩展 `test_no_duplicate_helpers` 禁列为 conftest 全 API（从 conftest 源码自动派生，避免漂移）。
- 新增 `test_coverage_map_sync.py`：扫描 `tests/**/*.py` 与 `COVERAGE_MAP.md` 双向对账。
- 收紧 `test_layering` 白名单：3 个 mixed-concerns 文件转为失败或限期 TODO。

## ⑤ 数字纪律核验

AGENTS.md 规定"不在文档中冻结测试通过数字"。核验发现**多处冻结且互相矛盾**：

| 位置 | 冻结数字 | 性质 |
|---|---|---|
| `TEST_PHILOSOPHY.md:617` | "1070 passed / 5 skipped（2026-06-25）"自称"最近一次基线" | **违规**：以"当前基线"口吻冻结 |
| `COVERAGE_MAP.md:134` | "41 文件 / 781 用例 / 778 passed / 3 skipped"（2026-05-26） | 历史快照，但属冻结数字 |
| `SEMANTIC_COVERAGE_MATRIX.md:588` | "2026-05-13 的快照比例" + `:551-558,615-616` "25 个测试/21 个测试" | 冻结具体计数 |
| `NEXT_STEPS.md:29` | "1173 passed, 10 skipped（2026-07-27）" | **唯一合规**的活基线 |

三处历史快照（1070 / 781 / 1173）**互相矛盾**。`TEST_PHILOSOPHY:617` 尤其违规。

**治理缺口**：`docs/WRITING_GUIDE.md:9` 明示"`tasks_docs/` 和 `tests_docs/` 不在本准则管辖范围内"。因此测试文档不受 WRITING_GUIDE 红线约束，导致 `TEST_PHILOSOPHY.md:615,625`、`MATRIX.md:2-3,6-10` 充斥日期戳/版本号/过程叙述。测试文档体系**无强制书写准则**，是治理盲区。

## ⑥ 方法论改进提议

**P0：建立测试文档的书写准则（闭合治理盲区）**
将 `tests_docs/` 纳入 WRITING_GUIDE 或新建 `tests_docs/TEST_DOC_GUIDE.md`，至少约束：禁冻结通过数字（仅指向 `NEXT_STEPS.md` 顶部锚点）、禁过程叙述/日期戳、矩阵必须可机器校验。

**P1：矩阵与测试名双向同步机制（治理脱节 B）**
- 矩阵"测试位置"列改为 `file::class::method` 三段式精确引用。
- 新增 meta 测试 `test_matrix_sync.py`：解析矩阵引用 -> 用 `pytest --collect-only` 拿真实 nodeid 集合 -> 逐条对账，引用不存在即失败。

**P2：统一分层模型（治理脱节 A）**
三份文档（TEST_PHILOSOPHY / README / COVERAGE_MAP）的分层描述必须收敛为**单一模型**。以实际目录为准（kernel/compiler/runtime/e2e/compliance/contracts/meta/sdk），TEST_PHILOSOPHY 的 Examples/Regression 层要么落地为目录、要么从哲学文档移除。`contracts/` 必须进 README 分层表。

**P3：扩展 meta 测试为"测试规范执行器"**
把 README/PHILOSOPHY 里所有"软约束"转为 meta 测试硬门禁。

**P4：conftest 治理**
- 删除或激活 `helpers` fixture。
- 统一 kernel `ax_reg`/`axiom_registry` 命名，移除别名 shim。
- 解决跨 conftest `axiom_registry` 同名碰撞。
- 白盒 helper 下沉到 runtime 层 conftest。

**P5：契约测试深度对齐（治理脱节 C）**
矩阵 `✅` 标记应区分"编译期契约"与"运行时不变量"。Optional 等只验编译的条目应标 `🔶编译期` 而非 `✅`。
