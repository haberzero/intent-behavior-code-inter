# 返回类型校验缺失根治（BOUNDARY-NESTED-FUNC-1 根因 + DOC-29）

> 2026-08-14。无人值守 goal 主线任务。承接上一 session 深度分析结论：
> BOUNDARY-NESTED-FUNC-1（函数返回嵌套函数赋 fn_callable[T] 运行时 RUN_TYPE_MISMATCH）
> + DOC-29（空 Optional 错误码不一致）。

## 一、问题重估（深度分析结论）

### BOUNDARY-NESTED-FUNC-1 真实根因（比交接推断更精确）

初步分析认为是"嵌套函数类型身份缺失 + 运行时放行分支缺 CALLABLE_INSTANCE"。
深度调查后**修正定性**：

**真实根因 = 编译期 `visit_IbReturn` 返回类型兼容校验整体缺失**：

1. `visit_IbReturn`（`_statement_visitors.py:438`）只累积 `ret_type`/`auto_return_types`，
   **从不与函数声明返回类型比对**（无 is_assignable 校验）。
2. 影响面实测（均编译期放行）：
   - `-> fn_callable[int]: return inner`（嵌套函数）→ 放行，运行时 RUN_TYPE_MISMATCH
   - `-> fn_callable[int]: return lambda -> str`（签名不匹配 lambda）→ 放行
   - `-> int: return "abc"`（普通类型不匹配）→ 放行
3. 对比：直接赋值路径已有校验——`fn_callable[int] g = inner` 编译期 SEM_TYPE_MISMATCH；
   `fn_callable[int] g = lambda -> str: 42` 编译期拦截。**赋值路径校验完整，返回路径完全缺失**。

### 语义边界（设计意图确认）

- `fn_callable[T]` 槽 = lambda/snapshot/behavior 产生的**可调用实例**（CALLABLE_INSTANCE
  kind，`03_type_system.md` line 127）。普通函数引用（FUNCTION kind）**不属于**该家族。
- `fn_callable f = add`（函数赋 fn_callable 槽）编译期拦截 = **正确设计**。
- 因此 `-> fn_callable[int]: return inner`（返回函数引用）**语义上应编译期拦截**（与直接
  赋值一致），当前放行是缺陷。
- 正确 lambda（fn_callable[int]）返回应放行（`is_assignable(lam_int, fn_int)`=True 已实证）。
- 裸 `fn`（推断哨兵，is_dynamic=True）返回任何可调用应跳过校验（现有 test_higher_order.py
  依赖此）。

### DOC-29 真实根因

空 Optional 操作三处发射点两种码：
- `optional.py:90`（unwrap）与 `iterable.py:39`（for/next）抛 InterpreterError **未指定
  error_code** → 默认 RUN_GENERIC_ERROR。
- `optional.py:174`（receive 委托链空值）显式指定 RUN_ATTRIBUTE_ERROR。
- arch/03 §8 承诺"空 Optional 操作 fail-fast 报 RUN_ATTRIBUTE_ERROR"。

## 二、修复方案

### 修复 1（BOUNDARY-NESTED-FUNC-1 根因）：`visit_IbReturn` 补可调用返回类型校验

**范围**：只校验"非动态、非 CALLABLE_SIG 之外的可调用返回类型"（fn_callable[T]/callable/
behavior[T] 等具体可调用），避免影响面失控。普通类型（int/str/用户类）返回校验属另一
独立问题（既有宽松语义，另议，不并入本次——避免大破坏）。

**判定逻辑**（在 visit_IbReturn 中）：
```
ret_type = self.visit(node.value)
declared = func_returns[-1]   # 当前函数声明返回类型（auto 时为 None）
if declared is not None and not is_auto_return:
    if declared 是可调用类型（FUNCTION/BOUND_METHOD/CALLABLE_SIG/CALLABLE_INSTANCE）：
        if not is_dynamic(declared):
            if not self.registry.is_assignable(ret_type, declared):
                error(SEM_TYPE_MISMATCH, f"Cannot return '{ret_type.name}' from function declared '{declared.name}'")
```

**覆盖**：
- `return inner`（嵌套函数/函数引用）→ is_assignable(inner, fn_callable[int])=False → 编译期拦截 ✓
- `return lambda -> str`（fn_callable[str]）→ is_assignable=False → 拦截 ✓
- `return lambda -> int`（fn_callable[int]）→ is_assignable=True → 放行 ✓
- `-> fn: return lambda/inner` → is_dynamic(fn)=True → 跳过 ✓（现有测试不破坏）
- `-> int: return 42` → declared 非可调用 → 跳过（保持既有宽松，不扩大影响面）

**注意**：`func_returns[-1]` 是声明返回类型 spec（ret_type），auto 时为 None。
需处理嵌套函数/闭包场景（func_returns 栈正确性）。

### 修复 2（DOC-29）：空 Optional 错误码统一

**决策**：统一为 `RUN_ATTRIBUTE_ERROR`（与文档 arch/03 §8 承诺 + receive 委托链一致）。
理由：① 文档已承诺；② 15_diagnostics RUN_GENERIC_ERROR 定义"未归类运行时错误"，空
Optional 操作有明确语义（"空 Optional 无此操作"），应归到具体码；③ 三个发射点统一。

**改动**：
- `optional.py:90` unwrap：`raise InterpreterError(..., error_code="RUN_ATTRIBUTE_ERROR")`
- `iterable.py:39` resolve_iterable 空 Optional：`raise InterpreterError(..., error_code="RUN_ATTRIBUTE_ERROR")`

### 修复 3（连带确认）：运行时 `_check_type` 放行分支

经分析**不需要改**：编译期正确拦截后，合法路径（lambda→fn_callable[T]）已被
is_assignable 放行，非法路径（函数→fn_callable[T]）编译期拦截。CALLABLE_INSTANCE
放行分支缺失只在"编译期放行"的路径触发——修复 1 后该路径消失。

## 三、判别性回归测试

### 修复 1（tests/e2e/test_higher_order.py 或新文件）
1. `-> fn_callable[int]: return inner`（嵌套函数）→ 编译期 SEM_TYPE_MISMATCH
2. `-> fn_callable[int]: return lambda -> str` → 编译期 SEM_TYPE_MISMATCH
3. `-> fn_callable[int]: return lambda -> int` → PASS（放行）
4. `-> fn: return inner` / `-> fn: return lambda` → PASS（动态跳过）
5. 直接赋值对照：`fn_callable[int] g = inner` 编译期拦截（既有，回归确认）
6. `-> fn_callable[int]: return lambda -> int` 运行时调用正确

### 修复 2（tests/runtime/test_optional_value_model.py 或新文件）
1. 空 Optional `unwrap()` → RUN_ATTRIBUTE_ERROR
2. 空 Optional `for` 迭代 → RUN_ATTRIBUTE_ERROR
3. 空 Optional `len()` / `e[0]` → RUN_ATTRIBUTE_ERROR（既有 receive 路径，回归确认）

## 四、触发用例核销

- `trials/T07_fixes_critical_stress/cases/E3-nested-func-return.ibci`：期望 RUN_TYPE_MISMATCH
  → 修复后应为**编译期 SEM_TYPE_MISMATCH**（分类从 BOUNDARY 转 PASS/GUARD 语义变化，
  需更新用例断言为编译期拦截）。
- `E1-empty-optional-code.ibci` / `E2-empty-optional-unwrap-code.ibci`：期望
  RUN_ATTRIBUTE_ERROR → 修复后转 PASS。

## 五、风险与影响面

- 修复 1 只影响"显式声明可调用返回类型 + 返回非动态值"路径。现有测试经 `-> fn`（动态）
  返回 lambda 不受影响。全量 pytest 验证。
- 修复 2 只改错误码字符串，不影响功能。全量 pytest 验证。
- 不做普通类型返回校验（int 返回 str 等保持宽松）——独立问题，避免大破坏。
