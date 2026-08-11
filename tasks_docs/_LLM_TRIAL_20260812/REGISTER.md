# REGISTER — 真实 LLM 全面压力试用结果寄存器

> 2026-08-12。每例一行：用例 / 文档引用 / 期望 vs 实际 / 分类 / 严重级别 / 证据日志 / 备注。
> 分类：PASS | KERNEL_ISSUE | DOC_ISSUE | LLM_BEHAVIOR | LIMIT | BOUNDARY | HARNESS。
> 级别：P0（崩溃/死循环/数据损坏）/ P1（明确缺陷，重要语义错误）/ P2（缺陷，较轻）/ P3（文档/体验）。
> 详细机械记录见 `logs/register.jsonl`；完整运行输出见 `logs/<case_id>.log`。

## 执行批次 1（D1 01-02 章，确定性核心）

| case_id | 文档引用 | 期望 | 实际 | 分类 | 级别 | 证据 | 备注 |
|---------|---------|------|------|------|------|------|------|
| D1-01-001-basetypes | 01_types §1.1 | 基础类型赋值 + type() 规范名 | a_type=int b_type=float c_type=str d_type=bool e_type=list f_type=tuple g_type=dict DONE | PASS | - | logs/D1-01-001-basetypes.log | |
| D1-01-002-containers | 01_types §1.2/§1.3.1 | 泛型容器 + Optional API | first=1 n=b alice=95 or_else=0 unwrap=1 is_some=True DONE | PASS | - | logs/D1-01-002-containers.log | |
| D1-01-003-casts | 01_types §1.4/§1.3 | 类型转换 + None 语义 | 见 log（exit=0 DONE） | PASS | - | logs/D1-01-003-casts.log | |
| D1-02-001-auto | 02_variables §2.2/§2.3 | auto 推断锁定 + 裸赋值 | exit=0 DONE | PASS | - | logs/D1-02-001-auto.log | |
| D1-02-002-unpack | 02_variables §2.4/§2.5 | 元组解包 + 交换 | a=10 b=20 xyz=pqr after_swap 2/1 DONE | PASS | - | logs/D1-02-002-unpack.log | |
| D1-02-003-scope | 02_variables §2.6/§2.7 | global/nonlocal/自动捕获 | 见下 DOC-ISSUE-001 + KERNEL-ISSUE-001 | MIXED | P1 | logs/D1-02-003-scope.log | |
| D1-02-003b-global-min | 02_variables §2.6 | global 最小复现 counter=1 | RUN_UNDEFINED_VARIABLE: `scope_.../bump:counter` is not defined | KERNEL_ISSUE | P1 | logs/D1-02-003b-global-min.log | 确认缺陷，见 KERNEL-ISSUE-001 |

## 缺陷记录

### DOC-ISSUE-001 — `02_variables.md §2.6` 示例缺返回标注
- **复现**：`func increment():` 无 `-> TYPE` → `SEM_MISSING_RETURN_ANNOTATION` 编译错误。
- **文档**：docs/syntax/02_variables.md §2.6 示例（与 05_functions.md §5.1 强制标注矛盾）。
- **实际**：示例直接照抄会编译失败。
- **级别**：P3（文档）。
- **处置**：本 trial 用例按 05_functions 正确用法补 `-> void` 后继续。

### KERNEL-ISSUE-001 — `global` 写访问在函数内运行时未定义变量
- **复现**：`int counter = 0; func bump() -> void: global counter; counter = counter + 1` 调用 `bump()` →
  `[ERROR][RUN_UNDEFINED_VARIABLE]: Variable UID 'scope_cases.../bump:counter' is not defined`。
- **文档**：docs/syntax/02_variables.md §2.6 明确 `global` 应使函数内读写作用于模块级变量。
- **实际**：编译通过但运行时按函数局部作用域查找 UID 失败（UID 前缀含 `bump:` 局部作用域）。
- **级别**：P1（明确语义错误）。
- **证据**：cases/D1-02-003b-global-min.ibci + logs/D1-02-003b-global-min.log。
- **备注**：tests/ 无任何 `global` 关键字覆盖（grep 仅命中 global_intents 无关项）——机制或从未被测试。

### KERNEL-ISSUE-002 — 整模块 `import mod` + 成员访问触发编译器 INT_INTERNAL_ERROR
- **复现**：模块 `greeting_mod.ibci` 导出函数 `func greet() -> str`，主文件 `import greeting_mod` +
  `greeting_mod.greet()` → `INT_INTERNAL_ERROR: 'FunctionSymbol' object has no attribute 'type_ref'`。
  变量导出同样触发（`'VariableSymbol' object has no attribute 'type_ref'`）。
- **文档**：docs/syntax/11_modules.md §11.1（模块导出规则：导出成员含用户定义符号；`import ai` 等
  整模块导入为文档化用法）+ KNOWN_LIMITS §十八（跨模块 import 合法，仅禁循环）。
- **实际**：整模块 `import` + 成员访问在编译期崩溃；`from helper import square` 命名导入**正常**
  （D1-11-002g 通过）——缺陷限定在整模块导入+属性访问路径。
- **级别**：P1（编译器内部错误，正常输入触发）。
- **证据**：cases/D1-11-002d/e-modimport-*.ibci + logs/D1-11-002d/e-modimport-*.log。
- **备注**：tests/runtime/test_ibc_file_imports.py 仅覆盖命名导入与 import-*，无整模块+成员访问覆盖。
