# 函数参数机制：默认参数 / 具名参数 / 动态参数

> **状态**：设计阶段（调研已完成，待 P1 开工）。**当前主线**（见 `tasks_docs/NEXT_STEPS.md`）。
> **性质**：临时任务文档，全部 Phase 完成后删除，决策性内容并入 `docs/architecture/`。
> **关联**：`PENDING_TASKS.md` PT-ARCH-28（`file.write` 统一 API，依赖本机制）、PT-PHASE4-1（`register_model(**kwargs)`）。

---

## 一、动机与受益项

- **用户诉求**：函数功能设计僵硬——无法书写默认参数、具名参数、动态多个参数，导致很多函数 API 无法合理设计。
- **PT-ARCH-28**：`file.write(target, data, overwrite_flag="copy"|"overwrite"|"new")` 需命名/动态参数支持。
- **PT-PHASE4-1**：`ai.register_model(name, url, key, model, **kwargs)` 需扩展 `**kwargs` 接收 `modalities`/`endpoint`/`audio_config`。

---

## 二、调研事实（2026-07-31 实测）

| 机制 | 实测结果 | 现状 |
|---|---|---|
| 具名参数 `f(a=1, b=2)` | CompilerError | `IbKeyword` AST 节点已定义但 parser/VM 均不使用（**预留接口未激活**） |
| 默认参数 `func f(int a = 1)` | CompilerError | `IbArg` 仅 `arg`/`annotation` 字段，无 default |
| 动态参数 `*args`/`**kwargs` | CompilerError | 无 vararg 表示 |

**全链路位置参数 only**：
- **lexer**：`STAR` / `STAR_STAR` / `STAR_ASSIGN` / `STAR_STAR_ASSIGN` 标记**已存在**（`core_scanner.py:352-357`），P1 无需 lexer 改动
- **parser**：`IbCall(func=..., args=..., keywords=[])` 硬编码空 keywords（`expression.py:381`）；函数定义参数仅解析位置参数
- **AST**：`IbCall.keywords: List[IbKeyword]` 已存在未使用；`IbKeyword(arg: Optional[str], value)` 已定义
- **语义**：`visit_IbCall`（`_expression_visitors.py:227`）只校验位置参数个数（`SEM_ARG_COUNT_MISMATCH`）与位置类型匹配；`node.keywords` 从不检查
- **运行时**：所有调用路径位置绑定——用户函数（`declarations.py:74` `vm_handle_IbFunctionDef`）、fn-lambda（`_shared.py` `_vm_call_fn_callable`）、behavior（`bind_behavior_call_args`）、llm 函数（`_llm_function.py`）、vtable 模块函数（`loader.py:85` `param_count` 严格匹配）
- **vtable**：`param_types` 固定类型列表，无 default/kind 声明

---

## 三、可行性结论

**可以实现，且架构已预留**（`IbKeyword`/`IbCall.keywords` 的设计意图）。但这是**语言级特性**——lexer/parser/AST/语义/运行时/vtable 全层改动，规模等同一次里程碑，禁止快速实现（遵守工作模式定论）。

---

## 四、相位化实施

### P1　AST + Parser
- `IbArg` 扩展：`default: Optional[IbExpr]` + 参数种类字段（POSITIONAL_OR_KEYWORD / VAR_POSITIONAL / VAR_KEYWORD）
- 激活 `IbKeyword`：`IbCall.keywords` 落地使用
- 解析函数定义：`func f(a, b=1, *rest, **kw)`（含默认值表达式）
- 解析调用：`f(1, b=2, *more, **kw)`（具名 + splat）
- 影响文件：`core/kernel/ast.py`、`core/compiler/parser/components/expression.py`、函数定义解析处

### P2　语义（类型检查 + 实参解析）
- `visit_IbCall` 统一实参解析：位置 → 具名 → 默认填充 → varargs/varkw
- 新增诊断码（语义错误集）：重复具名 / 未知具名 / 缺失必填 / 默认值类型不匹配 / 位置参数放具名后等
- `_declaration_visitors.py` 构建含 default/kind 的参数描述符（`param_types` 扩展）
- 方法覆写契约校验（`contract_validator.py`）适配

### P3　运行时（统一实参绑定器）
- 提取统一参数绑定器（位置 + 具名 + 默认 + `*args` + `**kwargs`），替换现有全部位置绑定：
  - 用户函数 `vm_handle_IbFunctionDef` / `_vm_call_fn_callable`
  - behavior `bind_behavior_call_args`
  - llm 函数 `_vm_invoke_llm_function`
  - vtable 模块函数（`loader.py`）
- 函数对象（IbUserFunction / IbFnCallable / IbBehavior / IbLLMFunction）携带参数元数据
- **vtable 签名扩展**：`_spec.py` 的 `param_types` 升级以声明 default/kind（影响所有 `ai.*`/`file.*` 模块函数）

### P4　应用 + 文档
- 落地 PT-ARCH-28：`file.write(target, data, overwrite_flag=...)` 统一 API（删除 `write_copy`/`write_overwrite`/`write_new` 或改为薄包装）
- `ai.*` 具名调用可用（如 `ai.set_config(model=..., url=...)`）
- 语法手册（`docs/syntax/05_functions.md` 等）+ spec + KNOWN_LIMITS

---

## 五、关键设计决策（待 P1 前确认）

1. **覆盖面**：用户函数 / fn-lambda / behavior / llm 函数 / vtable 全部一次实现，还是分阶段（建议：用户函数 + vtable 优先，behavior/llm 函数随 P3 统一绑定器自然覆盖）
2. **Python 语义对齐程度**：IBCI 是 Python-style，建议对齐——默认值惰性求值、`*args` 后参数为 keyword-only、`**kwargs` 收集、调用端 `*`/`**` splat
3. **vtable 签名格式**：`param_types` 从 `["str", "int"]` 升级为带 default/kind 的结构（如 `[{"name","type","default","kind"}]`），兼容旧格式
4. **诊断码命名**：加入语义错误集，命名遵循 `SEM_*` 规范

---

## 六、验收

- 三种机制 e2e 测试：默认参数、具名参数、动态参数（含 `*args`/`**kwargs`、splat 调用）
- Python 语义对齐的边界用例（默认值、keyword-only、重复/未知具名报错）
- PT-ARCH-28 落地：`file.write` 统一 API 可用，旧三函数清理
- 全量 `python -m pytest tests/` 不退化
