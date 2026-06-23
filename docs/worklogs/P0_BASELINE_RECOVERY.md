# 工作日志：P0 基线修复与 Critical Bug 修复

> **里程碑**：P0 全量完成
> **日期**：2026-06-24
> **分支**：unsafe-vibe-dev
> **基线**：838 passed, 2 skipped, 0 failed（无环境变量 workaround）

---

## 一、工作目标

恢复测试基线可信度，修复全量分析发现的 2 个 Critical 代码 bug 和 1 个并发数据竞争，使基线从"声称 838 passed 但实测 11 failed"变为"实测 838 passed, 0 failed"。

---

## 二、完成项清单

### P0-A-1 修复 6 个环境性测试失败

**问题**：`tests/compiler/semantic/test_analyzer.py:306` 的 `open(example_file)` 缺少 `encoding='utf-8'`。Windows GBK locale 下读取含中文的 .ibci 示例文件时 `UnicodeDecodeError`。

**修复**：`open(example_file, encoding='utf-8')`

**验证**：`test_analyzer.py` 28 passed

### P0-A-2 修复 5 个真实 ihost.collect 回归

**问题**：`tests/e2e/test_e2e_multi_interpreter.py` 中 5 个测试失败，`KeyError: 'answer'` / `'score'` / `'name'`。

**根因调查**：
- Python API 测试（`TestEngineLayerAPI`）全通过，仅 IBCI 层测试失败
- 追踪到 `ihost.spawn_isolated("D:\proj\...\tests\e2e\tmpXXXX.ibci")` 中 Windows 路径的反斜杠 `\t` 被 IBCI 词法器解析为 TAB 转义符（`core_scanner.py:442` `ESCAPE_SEQUENCES['t'] = '\t'`）
- 路径损坏后子引擎找不到文件，`run()` 静默返回 `False`（不抛异常），`collect` 返回空 dict
- `test_spawn_returns_str_handle_in_ibci` 表面通过但实际是"假阳性"：仅检查 handle 前缀，未检查 collect 内容

**修复**：新增 `_ibci_path()` 辅助函数将反斜杠转为正斜杠（Windows Python API 兼容），在所有 6 处路径嵌入点使用。

**验证**：`test_e2e_multi_interpreter.py` 17 passed

### P0-A-3 跨盘硬化

**问题**：`core/compiler/scheduler.py` 4 处 `os.path.relpath` + `core/project_detector.py` 1 处，在 Windows 跨盘场景（如 C: TEMP vs D: repo）抛 `ValueError: path is on mount 'C:', start on mount 'D:'`，导致默认环境下 504 个假失败。

**修复**：
1. 新建 `core/base/path_utils.py` 提供 `safe_relpath(path, start)` 函数，跨盘时回退到绝对路径
2. `scheduler.py` 4 处 + `project_detector.py` 1 处全部替换为 `safe_relpath`
3. `tests/conftest.py` 添加 `pytest_configure` hook，将 pytest `basetemp` 设为 repo 下 `.tmp_pytest`，确保所有临时文件与 repo 同盘

**验证**：不设置任何环境变量，`python -m pytest tests/ -q` → 838 passed

### P0-B-1 修复 interpreter.py symbol.spec 属性错误

**问题**：`core/runtime/interpreter/interpreter.py:128` `_sync_variables_from` 调用 `symbol.spec`，但 `RuntimeSymbolImpl` 无 `.spec` 属性（只有 `.declared_type`/`.current_type`）。此外 `symbol.spec`（类型对象）被错误地作为 `value` 参数传入 `define()`，而非作为 `declared_type`。

**修复**：`current_scope.define(name, symbol.value, declared_type=symbol.declared_type, is_const=symbol.is_const, force=True)`

### P0-B-2 修复 kernel.py 裸 except 吞异常

**问题**：`core/runtime/objects/kernel.py:947,1112` `IbUserFunction.call`/`IbLLMFunction.call` 中裸 `except: pass` 吞掉 `import_module` 失败，函数体在错误的 scope 中运行。

**修复**：替换为 `except Exception as e:` + `core_debugger.trace` 记录 + `raise InterpreterError` 传播。两处同时修复。

### P0-C-1 修复 _pending_futures 无锁数据竞争

**问题**：`core/runtime/interpreter/llm_executor.py:50,552,563` `_pending_futures` 字典无锁，`dispatch_eager` 后台线程写入 + 主线程 `resolve` 读取 → 数据竞争。

**修复**：添加 `threading.Lock`，在 `dispatch_eager` 写入和 `resolve` 读取时加锁。

---

## 三、修改文件清单

| 文件 | 修改类型 |
|------|---------|
| `tests/compiler/semantic/test_analyzer.py` | 加 `encoding='utf-8'` |
| `tests/e2e/test_e2e_multi_interpreter.py` | 新增 `_ibci_path()` + 6 处路径嵌入修复 |
| `tests/conftest.py` | 新增 `pytest_configure` hook 设置 basetemp |
| `core/base/path_utils.py` | **新建** — `safe_relpath()` 跨盘路径工具 |
| `core/compiler/scheduler.py` | 4 处 `os.path.relpath` → `safe_relpath` |
| `core/project_detector.py` | 1 处 `os.path.relpath` → `safe_relpath` |
| `core/runtime/interpreter/interpreter.py` | `symbol.spec` → `symbol.value` + `declared_type=symbol.declared_type` |
| `core/runtime/objects/kernel.py` | 2 处裸 `except:` → `except Exception as e:` + 记录 + 传播 |
| `core/runtime/interpreter/llm_executor.py` | 添加 `threading.Lock` 保护 `_pending_futures` |

---

## 四、工作思路与决策日志

### 决策 1：路径转义修复方式

**选项**：(a) 使用 IBCI raw string `r"path"` (b) 转为正斜杠 (c) 双反斜杠转义

**选择**：(b) 转为正斜杠。理由：
- 正斜杠在 Windows Python 文件 API 中等价于反斜杠
- 无需修改 IBCI 代码语法（raw string 需要用户知道这个语法）
- 最简洁、最可读、最可移植

### 决策 2：跨盘 relpath 修复方式

**选项**：(a) 每处 try/except (b) 统一工具函数

**选择**：(b) 统一 `safe_relpath()` 函数放在 `core/base/path_utils.py`。理由：
- 5 处调用避免重复 try/except
- `core/base/` 是基础层，所有上层模块可安全导入
- 符合单点真理原则

### 决策 3：pytest basetemp 配置方式

**选项**：(a) `pytest.ini` 配置 (b) `conftest.py` `pytest_configure` hook

**选择**：(b) `pytest_configure` hook。理由：
- 不需要额外配置文件（P1-E 才创建 pytest.ini）
- `conftest.py` 已有 REPO_ROOT 常量，直接可用
- hook 在任何 pytest 运行方式下都生效

### 决策 4：kernel.py 异常处理策略

**选项**：(a) 记录后继续（静默跳过 scope 切换）(b) 记录后传播（抛出 InterpreterError）

**选择**：(b) 传播。理由：
- 如果 module import 失败，函数体在错误 scope 中运行会导致更隐蔽的 bug
- "显式优于隐式"原则要求错误可见
- 原始 `except: pass` 是全量分析识别的 Critical 级问题

---

## 五、验证结果

```
python -m pytest tests/ -q --tb=no --no-header
838 passed, 2 skipped in 6.49s
```

- 无需任何环境变量 workaround
- 2 skipped 为确认的设计限制（INV-LAMBDA-3、INV-SCOPE-1）
- 基线可信度恢复：所有"0 回归"声明现在有实测支撑
