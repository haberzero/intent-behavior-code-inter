# 函数参数机制：默认参数 / 具名参数 / 动态参数

> **状态**：P1（AST+Parser）✅、P2（语义）✅、P2 质量维修 ✅、P3（运行时统一绑定器 + vtable 升级）✅ 已完成，P4（应用 + 文档）待开工。**当前主线**（见 `tasks_docs/NEXT_STEPS.md`）。
> **性质**：临时任务文档，全部 Phase 完成后删除，决策性内容并入 `docs/architecture/`。
> **关联**：`PENDING_TASKS.md` PT-ARCH-28（`file.write` 统一 API，依赖本机制）、PT-PHASE4-1（`register_model(**kwargs)`）。

---

## 〇、P2 质量维修记录（2026-07-31，人工复查驱动）

**用户裁定**：① 描述符单点化按推荐（权威在 type-check 阶段）；② 双路径彻底清理；③ 兜底一律禁止；④ vtable 签名格式**无需兼容旧格式**（无外部用户，内部开发，可大胆改，旧结构果断失效并清理外围）；⑤ `_any_desc` 可空脆弱点一并加固。

**已执行**（全部对应审计 F1-F6）：
- **F3/F6 描述符单点化**：collection pass 不再构建描述符（删除模块级 `annotation_to_typeref`/`build_param_descriptors`）；`_declaration_visitors` 的 `_build_function_signature` 成为唯一权威（type-check 阶段，解析后精度），用户/LLM 函数对称精化；`_sync_class_member` 把精化描述符同步到类成员表（ContractValidator 消费）。已验证：LLM 函数同样拿到 `list[int]` 精度。
- **F4 双路径清理**：`_resolve_call_arguments` 收敛为单一入口三策略——① 有 `param_descriptors` 全量解析；② 仅 `param_types` 位置检查（CALLABLE_SIG 报错 / 容器特化方法保留 SEM_CONTAINER_METHOD_HINT 警告，有测试依赖）；③ 无静态签名动态跳过。visit_IbCall 不再有复制旧块的分支。
- **F2 死分支**：全仓 `IbGenericType` 引用清除（`symbol_collection_pass` 2 处、`type_resolution_pass` 1 处 + docstring），`IbCallableType` 守卫简化为直接 isinstance。
- **F1/F5 + D5 加固**：删除 `arg_type is None → any` 兜底；`_any_desc`/`_void_desc` 等三处构造点（collection/type-resolve/type-check）对 "any" 解析失败 **fail-fast raise**；两个裸注册表测试 fixture（`test_analyzer.py`/`test_symbol_collection_pass.py`）改用 `create_default_registry()`；`hasattr(get_diff_hint)` 探测改为直接调用（该方法存在）。
- **保留**：`getattr(func_type, "param_descriptors"/"param_types", None) or []`——这是按可用元数据选择解析策略的设计分派，非兼容探测。

**维修后基线**：`python -m pytest tests/` 实跑 1229 passed / 4 skipped，零回归。

**遗留（P3 处理）**：
- vtable 签名升级（D4 已裁定不兼容旧格式）：`param_types` → 结构化 `[{"name","type","default","kind"}]`，旧格式字段删除，外围（discovery/loader/全部 `_spec.py`）一并清理；升级后 vtable 函数自动进入 `_resolve_call_arguments` 策略一，策略二中的 vtable 情形随之消失。
- 既有 `hasattr` duck-typing 探测（非本次改动引入）属 PT-HEALTH-1 范畴，不在本维修范围。

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

### P1　AST + Parser ✅ 已完成（2026-07-31）

- `IbArg` 扩展：`default: Optional[IbExpr]` + `kind`（`ARG_POSITIONAL_OR_KEYWORD` / `ARG_VAR_POSITIONAL` / `ARG_VAR_KEYWORD`）
- 新增 `IbStarred` 节点（调用侧 `*expr` 序列解包）
- `IbCall.keywords` 激活落地：`IbKeyword(arg=None)` 表示 `**expr` 字典解包
- `parameters()` 支持 `func f(int a, int b = 1, *rest, **kw)`（含默认值表达式，以 TUPLE 优先级解析避免吞逗号）
- `call()` 支持 `f(1, b=2, *more, **kw)`（具名 + splat）
- 全量 `python -m pytest tests/` 实跑 1229 passed / 4 skipped，零回归
- 影响文件：`core/kernel/ast.py`、`core/compiler/parser/components/declaration.py`、`core/compiler/parser/components/expression.py`
- 序列化器 `vars(node)` 自动携带新字段（`default`/`kind`/`keywords` round-trip 已验证）
- 注意：P1 后新语法可编译但运行期绑定仍为位置参数；P2 已补语义层严格校验，运行期统一绑定器属 P3 范畴（中间态不对外暴露）

### P2　语义（类型检查 + 实参解析） ✅ 已完成（2026-07-31）

- `TypeDef.param_descriptors` + `ParamDescriptor`（member.py：name/kind/type_ref/has_default）；`MethodMemberSpec.param_descriptors` 同步
- `build_param_descriptors()`（symbol_collection_pass 共享纯函数）：用户函数 / LLM 函数 / 类方法构建描述符
- `visit_IbCall` 统一实参解析：位置 → 具名 → 默认填充 → varargs/varkw（`_resolve_call_arguments` + `_check_call_arg_type`）
  - 有描述符（用户/LLM 函数）：严格结构校验；无描述符（vtable/内置/axiom）：保留旧行为
  - 位置实参先于具名实参绑定（`f(1, a=2)` → SEM_DUPLICATE_KEYWORD）
  - `**kwargs` 参数吸收未声明具名实参；调用侧 `*expr`/`**expr` 抑制静态缺参/超参校验
- 新增诊断码：`SEM_DUPLICATE_KEYWORD` / `SEM_UNKNOWN_KEYWORD` / `SEM_MISSING_REQUIRED_ARG` / `SEM_DEFAULT_TYPE_MISMATCH` / `SEM_TOO_MANY_POSITIONAL` / `PAR_POSITIONAL_AFTER_KEYWORD`
  - 注：`位置实参放具名后` 在 parser 层强制（Python 语法级错误），故用 PAR_ 码而非 SEM_ 码
- 默认值定义处校验：包围作用域求值（symbol_resolution_pass `_visit_param_defaults`）+ 类型可赋值性（`SEM_DEFAULT_TYPE_MISMATCH`）
- KEYWORD_ONLY 参数种类：`*args` 之后参数只能具名传入（Python 对齐）；parser 强制单 `*args`/`**kwargs`、`**kwargs` 居末、默认值后禁无默认普通参数
- 方法覆写契约适配：子类允许增加带默认值 / varargs 参数（`contract_validator.py` + `_check_override_compatibility`），非默认额外参数仍报 SEM_DUAL_ASSIGNABLE
- 全量 `python -m pytest tests/` 实跑 1229 passed / 4 skipped，零回归
- 影响文件：`core/kernel/spec/{member,base,__init__}.py`、`core/compiler/semantic/passes/{symbol_collection_pass,symbol_resolution_pass,_expression_visitors,_declaration_visitors,contract_validator}.py`、`core/compiler/parser/components/{declaration,expression}.py`、`core/base/diagnostics/codes.py`、`core/kernel/ast.py`

### P3　运行时（统一实参绑定器）　待开工
- `visit_IbCall` 统一实参解析：位置 → 具名 → 默认填充 → varargs/varkw
- 新增诊断码（语义错误集）：重复具名 / 未知具名 / 缺失必填 / 默认值类型不匹配 / 位置参数放具名后等
- `_declaration_visitors.py` 构建含 default/kind 的参数描述符（`param_types` 扩展）
- 方法覆写契约校验（`contract_validator.py`）适配

### P3　运行时（统一实参绑定器） ✅ 已完成（2026-07-31）

- **统一绑定器**（`_shared.py` `_resolve_call_arguments_runtime`）：位置 → 具名 → 默认填充 → varargs/varkw，在 `vm_handle_IbCall` 调用点统一解析，产出**按声明序的最终实参列表**；各 callee 路径保持按索引绑定不变（改动面最小化）
  - `*expr`/`**expr` splat 展开（`_expand_starred`/`_merge_dstar`）
  - 用户函数 / 类方法（含 `IbBoundMethod` 解包）/ fn-lambda / behavior / LLM 函数 / 原生模块函数统一走该路径
  - 默认表达式惰性求值（`yield` 经 VM 调度）
- **vtable 签名升级**（D4 裁定，不兼容旧格式）：`param_types` 数组 → `params` 结构化（`{"name","type","default","kind"}`）；`ParamDescriptor.default_value` 承载原生默认字面值；全部 9 个 `_spec.py` 转换（参数名与实现签名对齐）
- `discovery.py`：`params` 解析 → `MethodMemberSpec.param_descriptors`；inspect 路径自动提取名称/种类/默认值
- `loader.py`：从 `param_descriptors` 构建运行时参数元数据附加到 proxy；**具名参数契约校验**（声明名称必须被实现接受，否则加载失败）
- 语义层：`resolve_member` 与调度器 `_rebuild_external_symbol` 携带模块成员 `param_descriptors` → 原生函数具名/默认实参也受编译期校验
- e2e：`tests/e2e/test_function_params.py` 25 项（默认/具名/varargs/splat/dstar/keyword-only/类方法/behavior/LLM/原生 + 负样本）
- 全量 `python -m pytest tests/` 实跑 **1255 passed / 4 skipped**（+26 新测试，零回归）

**已知待办（P4 或专项）**：
- 原生函数 `VAR_KEYWORD`（**kwargs）dispatch 未接通：绑定器把 varkw 打包为 dict 位置实参，`def f(*a, **kw)` 实现无法按位置接受。当前无原生函数声明 VAR_KEYWORD（`register_model` **kwargs 属 PT-PHASE4-1），出现时需扩展原生调用适配（位置 + kwargs 分传）
- 语义 `_resolve_with_descriptors` 与运行时 `_resolve_call_arguments_runtime` 存在同算法双实现（~30 行），候选收敛为共享纯算法核心
- `_ibci_param_meta` 作为 proxy 私有属性跨模块读取（设计通道，未穿透对外对象）；可形式化为 IbNativeFunction 字段
- `file` 模块（kernel-native，engine.py 内联 spec）尚未声明参数名 → `file.*` 具名调用与 `file.write` 统一 API 属 P4

### P4　应用 + 文档
- 落地 PT-ARCH-28：`file.write(target, data, overwrite_flag=...)` 统一 API（删除 `write_copy`/`write_overwrite`/`write_new` 或改为薄包装）
- `ai.*` 具名调用可用（如 `ai.set_config(model=..., url=...)`）
- 语法手册（`docs/syntax/05_functions.md` 等）+ spec + KNOWN_LIMITS

---

## 五、关键设计决策（已落定 2026-07-31，按文档建议）

1. **覆盖面**：全链路一次实现。P1 的 AST/parser 改动天然覆盖所有可调用形式（用户函数 / fn-lambda / behavior / llm 函数共享 `parameters()` 与 `call()`）；P2 语义侧重用户函数 + vtable；behavior/llm 函数随 P3 统一绑定器自然覆盖。
2. **Python 语义对齐**：对齐——默认值惰性求值（调用时求值）、`*args` 后参数为 keyword-only、`**kwargs` 收集、调用端 `*`/`**` splat。
3. **vtable 签名格式**：`param_types` 从 `["str", "int"]` 升级为带 default/kind 的结构化格式，兼容旧格式（P3 落实）。
4. **诊断码命名**：语义错误集，`SEM_*` 规范（P2 落实）。

### P2 落实的语义错误集（新增）

- `SEM_DUPLICATE_KEYWORD`：同一具名实参重复传入
- `SEM_UNKNOWN_KEYWORD`：调用方传入了函数未声明的具名实参
- `SEM_MISSING_REQUIRED_ARG`：必填参数缺失（无默认值且未传入）
- `SEM_DEFAULT_TYPE_MISMATCH`：默认值表达式类型与参数标注不匹配
- `PAR_POSITIONAL_AFTER_KEYWORD`：具名实参后出现位置实参（parser 层语法错误）
- `SEM_TOO_MANY_POSITIONAL`：位置实参数量超过参数上限

---

## 六、验收

- 三种机制 e2e 测试：默认参数、具名参数、动态参数（含 `*args`/`**kwargs`、splat 调用）
- Python 语义对齐的边界用例（默认值、keyword-only、重复/未知具名报错）
- PT-ARCH-28 落地：`file.write` 统一 API 可用，旧三函数清理
- 全量 `python -m pytest tests/` 不退化
