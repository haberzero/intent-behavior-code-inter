# 工作日志：P1 架构健康修复 + 测试基础设施 + 文档修复

> **里程碑**：P1 全量完成（9/9 项）
> **日期**：2026-06-24
> **分支**：unsafe-vibe-dev
> **基线**：886 passed, 5 skipped, 0 failed

---

## 一、完成项清单

### P1-A 提取 `core/runtime/shared/` — 打破 3 个 runtime 内循环 ✅
- 创建 `shared/op_constants.py`（从 `interpreter/constants.py` 移出）
- 创建 `shared/llm_result.py`（从 `interpreter/llm_result.py` 移出）
- 创建 `shared/signals.py`（从 `vm/task.py` 提取 `ControlSignal`/`Signal`/`UnhandledSignal`）
- 更新所有跨包消费者直接从 shared/ 导入
- 消除 `interpreter↔vm`、`objects↔interpreter`、`objects↔vm` 三个延迟导入循环

### P1-B 拆分 HostInterface — 修复 compiler→runtime 层级反转 ✅
- HostInterface 仅依赖 `core.kernel.*`，无 runtime 依赖
- 移至 `core/kernel/host_interface.py`
- 更新 3 个编译器消费者（scheduler/parser/context）从 kernel 导入
- 原位置保留重导出垫片

### P1-C 移动 `fuzzy_json.py` → `core/base/support/` ✅
- 恢复 "kernel 永不导入 runtime" 不变量
- 最便宜的架构修复（仅 1 个 import 变更）

### P1-D 拆分 `handlers.py`（2022 行 → 8 个子模块）✅
- `_shared.py`（398 行）：10 个跨类别辅助函数
- `leaf.py`（250 行）：16 个叶子表达式处理器
- `control_flow.py`（358 行）：11 个控制流处理器
- `assignment.py`（141 行）：4 个赋值处理器
- `declarations.py`（136 行）：6 个声明处理器
- `llm_behavior.py`（290 行）：7 个 LLM/行为处理器
- `dispatch.py`（112 行）：`build_dispatch_table()` 聚合器
- `__init__.py`：重导出 2 个公共 API
- 纯机械拆分，零逻辑变更

### P1-E `pytest.ini` + `.github/workflows/ci.yml` ✅
- pytest.ini：testpaths、strict-markers、slow/fast markers
- ci.yml：矩阵测试（Ubuntu+Windows，Python 3.10+3.12）

### P1-F 层级元测试 + 迁移 4 个违规文件 ✅
- 新增 `tests/meta/test_layering.py`（31 个参数化检查）
- 迁移：test_nonlocal → e2e、test_override_and_super → e2e、prompt_protocol runtime 类 → e2e、multimodal_payload → runtime
- 3 个混合文件加入已知违规白名单（待后续拆分）

### P1-G MOCK 指令独立测试 ✅
- 新增 `tests/runtime/test_mock_directives.py`（20 个测试）
- 覆盖 TRUE/FALSE/FAIL、INT/STR/FLOAT/BOOL/LIST/DICT、SEQ、REPAIR、验证

### P1-H 标注 AUDIT_REPORT 已解决发现 ✅
- 4 个发现全部标注 "✅ 已关闭 2026-05-27"
- 添加 header 说明（KNOWN_LIMITS 旧编号映射）

### P1-I 修复 hub 文档锚点 ✅
- TEST_PHILOSOPHY.md：更新测试计数（781/778/3 → 866/5/49 文件）
- FUNC_DESIGN_NOTES.md：修复 KNOWN_LIMITS §三 → §一/§七 指针
- ARCH_DETAILS.md §1.2：更新 BUG #A 后的 if/while 语义（静默吞错 → raise LLMParseError）

---

## 二、架构健康度改善总结

### 循环依赖消除
| 改善前 | 改善后 |
|--------|--------|
| interpreter↔vm 循环（延迟导入掩盖） | 两包都从 shared/ 导入，无循环 |
| objects↔interpreter 循环（延迟导入掩盖） | objects 从 shared/ 导入，无循环 |
| objects↔vm 循环（延迟导入掩盖） | objects 从 shared/ 导入，无循环 |
| compiler→runtime 反向依赖（HostInterface） | compiler→kernel（HostInterface 已移至 kernel） |
| kernel→runtime 反向依赖（fuzzy_json） | kernel→base（fuzzy_json 已移至 base） |

### God module 拆分
| 文件 | 改善前 | 改善后 |
|------|--------|--------|
| handlers.py | 2022 行（1 个文件） | 8 个子模块（最大 398 行） |

### 测试基础设施新增
| 项目 | 改善前 | 改善后 |
|------|--------|--------|
| pytest 配置 | 无 | pytest.ini + strict-markers |
| CI | 无 | GitHub Actions 矩阵（2 OS × 2 Python） |
| 层级强制 | 仅约定 | tests/meta/test_layering.py（31 个静态检查） |
| MOCK 测试 | 无独立测试 | 20 个独立 MOCK 指令测试 |

---

## 三、修改文件清单

### 新建文件
- `core/runtime/shared/__init__.py`、`op_constants.py`、`llm_result.py`、`signals.py`
- `core/kernel/host_interface.py`
- `core/base/support/__init__.py`、`fuzzy_json.py`
- `core/runtime/vm/handlers/`（8 个子模块）
- `pytest.ini`、`.github/workflows/ci.yml`
- `tests/meta/test_layering.py`
- `tests/runtime/test_mock_directives.py`
- `tests/runtime/test_multimodal_payload.py`（从 e2e/ 迁移）
- `tests/e2e/test_e2e_nonlocal.py`、`test_e2e_override_and_super.py`、`test_e2e_prompt_protocol.py`（从 compiler/ 迁移）

### 删除文件
- `core/runtime/vm/handlers.py`（拆分为 handlers/ 包）
- `core/runtime/support/fuzzy_json.py`（移至 base/support/）

### 转为垫片
- `core/runtime/interpreter/constants.py`、`llm_result.py`
- `core/runtime/host/host_interface.py`

---

## 四、验证结果

```
python -m pytest tests/ -q --tb=short
886 passed, 5 skipped in 5.98s
```

- 886 = 838（P0 后基线）+ 28（层级元测试通过项）+ 20（MOCK 测试）
- 5 skipped = 2（设计限制）+ 3（混合文件白名单）
- 零回归
