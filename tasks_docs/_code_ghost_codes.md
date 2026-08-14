# 幽灵诊断码根治（T05 §六.3）

> 2026-08-14。承接 `_HANDOFF_T05_ISSUES.md` §六.3：8 个诊断码全仓零发射。
> 处置原则：每个目录码必须有真实发射点（杜绝幽灵码）；无发射点的码删减（杜绝死契约）。
> 用户授权宏观体系彻底重构，不做表面修复。

## 一、现状（代码实证）

8 个幽灵码仅 codes.py/catalog.py 注册、生产代码零引用；越界/除零/属性缺失报裸
`RUNTIME_ERROR`（issue.py 默认码，本身也未注册）；`indent_processor` 误用
`LEX_INVALID_ESCAPE` 上报缩进失配；快照篡改静默恢复。

## 二、逐码决断

| 码 | 处置 | 依据 |
|---|---|---|
| RUN_DIVISION_BY_ZERO | **实现发射** | `int/float.__truediv__/__floordiv__/__mod__` 除零 → `IbNativeFunction.call` 异常类型映射 |
| RUN_INDEX_ERROR | **实现发射** | `IbList.__getitem__` IndexError / `IbDict.__getitem__` KeyError 已抛 `InterpreterError("IndexError...")`，补 error_code |
| RUN_ATTRIBUTE_ERROR | **实现发射** | base.py receive 对缺失方法抛 AttributeError → 经 leaf.py call-failed 映射 |
| RUN_PERMISSION_ERROR | **实现发射** | `PermissionManager.validate_path`（file_impl/file_handle 运行时文件 I/O 沙箱）已抛 InterpreterError，补 error_code |
| RUN_LLMEXCEPT_SNAPSHOT_VIOLATION | **实现发射（警告）** | `verify_snapshot_integrity` 检测篡改处发 `kernel_diagnostic` 警告（恢复是确定性行为，故为警告非错误） |
| LEX_INVALID_NUMBER | **实现发射** | 词法器 `_scan_number`：0x/0b/0o 无数字、数字后紧跟字母（12abc）→ 报 LEX_INVALID_NUMBER（修 `0x` 误报 INT_INTERNAL_ERROR 的隐藏 bug） |
| PAR_INDENTATION_ERROR | **实现发射（改码）** | `indent_processor` 缩进失配从误用 `LEX_INVALID_ESCAPE` 改为本码 |
| PAR_MULTIPLE_INTENTS | **删减** | 语言无"同位置多意图"约束（意图注释是独立语句，无冲突检查点），保留即死契约 |

### 附：`RUNTIME_ERROR` 默认码

`InterpreterError` 默认 `error_code or "RUNTIME_ERROR"`（未注册字符串）。改为
`"RUN_GENERIC_ERROR"`（已注册等价码："未归类运行时错误"），消灭未注册默认码。

## 三、发射机制

1. **`core/runtime/objects/kernel/functions.py`** 新增 `_runtime_error_code_for(exc)`：
   ZeroDivisionError→RUN_DIVISION_BY_ZERO、IndexError/KeyError→RUN_INDEX_ERROR、
   AttributeError→RUN_ATTRIBUTE_ERROR、PermissionError→RUN_PERMISSION_ERROR。
   `IbNativeFunction.call` 异常包装处按类型映射（取代裸 RUNTIME_ERROR）。
2. **`core/runtime/vm/handlers/leaf.py`** `vm_handle_IbCall` call-failed 分支同样经
   `_runtime_error_code_for` 映射（AttributeError 等直接经 receive 抛出的路径）。
3. collections `__getitem__` 显式 error_code=RUN_INDEX_ERROR。
4. permissions `validate_path` 显式 error_code=RUN_PERMISSION_ERROR。
5. llmexcept 篡改检测发 `kernel_diagnostic(RUN_LLMEXCEPT_SNAPSHOT_VIOLATION)` 警告。
6. lexer `_scan_number` 补 LEX_INVALID_NUMBER 校验（0x/0b/0o 残缺 + 数字后字母）。
7. `indent_processor` 缩进失配 → PAR_INDENTATION_ERROR。

## 四、契约测试

- **CAT-7**（`tests/contracts/test_diagnostic_catalog.py`）：每个目录码在生产代码
  （core/ + ibci_modules/，排除 codes/catalog/__init__）有真实引用点——杜绝幽灵码
  回归。全码零孤儿（当前 86 码全通过）。
- **判别性回归**（`tests/contracts/test_diagnostic_emission.py`，10 项）：除零/
  下标/键缺失/属性/权限/快照警告/0x/12abc/缩进/删减码。

## 五、文档

`docs/syntax/15_diagnostics.md`：7 码去除"未发射"标注 + PAR_MULTIPLE_INTENTS 节删除 +
RUN_LLMEXCEPT_SNAPSHOT_VIOLATION 级别 ERROR→WARNING（警告不阻断）。

## 六、验证

全量 pytest **2654 passed / 1 skipped** 零回归。9 个警告均为快照篡改测试触发的
RUN_LLMEXCEPT_SNAPSHOT_VIOLATION（预期新观测性，非回归）。
