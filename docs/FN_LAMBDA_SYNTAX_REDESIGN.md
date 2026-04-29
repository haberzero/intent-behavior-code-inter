# fn / lambda / snapshot 类型系统重设计决策记录

> 本文档记录 2026-04-29 设计讨论会形成的完整语法重设计决策。  
> 所有决策均**尚未实现**，等待未来 PR 落地。  
> 对应实现任务已收录于 `docs/PENDING_TASKS.md`（待补充）。  
>
> **最后更新**：2026-04-29

---

## 一、背景与动机

当前 `fn` / `lambda` / `snapshot` 的语法存在以下设计耦合问题：

1. `int fn f = lambda: EXPR`——返回类型 `int` 写在声明左侧，通过编译器内部隐式通道
   `_pending_fn_return_type`（`semantic_analyzer.py:75`）传递给 `visit_IbLambdaExpr`。
   这使得 `fn` 承担了本不属于它的"携带输出类型"职责，与其"callable 类型推导关键字"的
   定位相矛盾。

2. PAR_005 主动拒绝表达式侧 `lambda -> TYPE: EXPR`，理由是"返回类型语义上属于声明侧"——
   这一立场在新设计中被反转。

3. `fn` 在参数类型标注中不具备 callable 签名约束能力（无法写 `fn[(int)->int]`），使高阶函数
   无法在编译期进行结构签名检查。

---

## 二、设计决策

### D1：`fn` 完全等同于 `auto`，不承载任何类型标注

**决策**：`fn` 在变量声明中起到与 `auto` 完全对称的作用，**只做可调用类型推导，不承载任何
输出类型信息**。

合法形式（`fn` 一侧不写任何类型）：

```ibci
fn f = myFunc                          # 推导 f 的类型 = myFunc 的 FuncSpec
fn g = lambda(int x) -> int: x + 1    # 推导 g 的类型 = DeferredSpec(int, lambda)
fn h = lambda: @~ compute ~            # 推导 h 的类型 = DeferredSpec(auto, lambda)
fn s = snapshot(str name) -> str: name # 推导 s 的类型 = DeferredSpec(str, snapshot)
```

**废弃**：`int fn f = lambda: EXPR`（声明侧带返回类型的 fn 形式）。

此形式在新语法落地后将产生编译错误（具体错误码 TBD，暂建议复用 PAR_005 或新增 PAR_006）。

---

### D2：lambda / snapshot 返回类型标注迁移至表达式侧

**决策**：`lambda` 和 `snapshot` 统一采用如下语法，全部参数类型与返回类型标注均在**表达式
定义侧**书写，`fn` 与两者彻底解耦：

```
lambda(<param_type_list>) -> <return_type> : <expr>
snapshot(<param_type_list>) -> <return_type> : <expr>
```

各变体示例：

| 写法 | 含义 |
|------|------|
| `lambda: EXPR` | 无参，返回类型自动推导 |
| `lambda -> int: EXPR` | 无参，返回 `int` |
| `lambda(int x): EXPR` | 有参，返回类型推导 |
| `lambda(int x, str s) -> bool: EXPR` | 有参，显式返回 `bool` |
| `snapshot: EXPR` | 无参 snapshot，返回类型推导 |
| `snapshot(int n) -> str: EXPR` | 有参 snapshot，返回 `str` |

**规则**：
- `lambda` 和 `snapshot` **只允许单一返回值**（返回类型位置只写一个类型名）。
- 用 `fn f = ...` 接收时，`f` 的类型完全由表达式侧推导，左值只需写 `fn`。
- 对于普通 `func` 函数定义，多值返回通过 `tuple` 实现（不受此限制），可调用类实例同理。

**移除的语法**（PAR_005 范围扩展）：  
`int fn f = lambda: EXPR`（所有声明侧带类型的 fn + lambda/snapshot 组合）全部成为编译错误。

---

### D3：`fn[(...)->(...)]` 用于高阶函数参数的 callable 签名标注

**决策**：当 `fn` 出现在**参数类型标注位置**（即 `func` 参数声明、`auto`/`fn` 变量声明的类型
注解覆盖位置）时，采用方括号书写 callable 签名约束：

```
fn[(<input_type_list>) -> (<output_type_list>)]
```

示例：

```ibci
# 高阶函数：接受一个 (int, str) -> bool 的 callable 参数
func apply(fn[(int, str) -> bool] predicate, int x, str s) -> bool:
    return predicate(x, s)

# 无参、返回 int 的 callable
func run_deferred(fn[() -> int] task) -> int:
    return task()

# 接受任意 callable（不约束签名）
func call_any(fn f) -> auto:
    return f()

# 返回值也可以是带签名的 fn
func make_adder(int n) -> fn[(int) -> int]:
    fn adder = lambda(int x) -> int: x + n
    return adder
```

**规则**：
- `fn[...]` 只出现在**类型标注上下文**（函数参数类型、`auto`/`fn` 覆盖类型、返回类型位置）。
- `fn` 裸形式（不带 `[...]`）用于变量声明，表示"推导具体可调用类型"。
- 两种形式在语法上无歧义：`SyntaxRecognizer` 只在语句起始位置分派，参数类型解析走
  `parse_type_annotation()`，两者路径不交叉。

---

### D4：`fn` 在变量声明和高阶函数类型标注两种场景下不需要引入新关键字

**决策**：**不需要新关键字**。

语法层面区分依据：
- `fn NAME = EXPR`（行首 `fn`）→ `SyntaxRecognizer` 识别为 `VARIABLE_DECLARATION`，走声明路径。
- `fn[...] PARAM_NAME`（出现在 `func` 参数列表内）→ 类型解析器路径，产生 callable 签名约束节点。

语义层面区分依据：
- 变量声明 `fn f = ...` → 符号表中 `f` 持有推导得到的具体 `FuncSpec` 或 `DeferredSpec`。
- 类型标注 `fn[(int)->int]` → 产生 callable 签名约束（结构化匹配），不对应具体 spec 名。

两者通过 AST 节点形状（`IbName("fn")` vs `IbSubscript(IbName("fn"), ...)` + 新增
callable signature 专用节点）在语义分析阶段明确区分。

---

### D5：跨模块导入必须明确完整导入符号

**决策**：维持并明确强化现有策略——跨模块引用的符号**必须通过完整的 `from module import name`
或 `import module` 后以 `module.name` 访问**，编译器不支持从当前作用域隐式引用外部模块的符号。

这一策略与现有 `LazySpec` + `SpecRegistry` 的强制显式解析路线一致，不做变更。

---

### D6：向前引用（Forward Reference）

**决策**：

| 场景 | 当前状态 | 决策 |
|------|---------|------|
| **模块级向前引用**（函数 A 调用文件中位置更靠后的函数 B） | ✅ 已支持（Pass 1 在 Pass 4 前收集所有模块级符号） | 无需变更 |
| **局部变量向前引用**（函数体内使用尚未赋值的局部变量） | ❌ 不支持 | 维持不支持（无需求） |
| **跨文件向前引用**（循环依赖模块间的编译期类型检查） | ⚠️ 部分：`LazySpec` 占位，运行时解析 | 可选扩展：基于 `scheduler.py` 现有依赖图做"全工程两轮扫描"（先收集所有模块 Pass 1，再统一 Pass 2），技术可行性无疑问，工程代价中等，**暂不列入近期目标** |

---

## 三、与当前代码库的对照（变更清单）

### 需要删除的内容

| 位置 | 内容 | 原因 |
|------|------|------|
| `core/compiler/semantic/passes/semantic_analyzer.py:75` | `_pending_fn_return_type` 字段及全部存取逻辑 | D1/D2：返回类型移到表达式侧，隐式通道不再需要 |
| `core/compiler/parser/components/expression.py:492-498` | PAR_005 对 `->` 的拒绝逻辑 | D2：表达式侧 `-> TYPE` 合法化 |
| `core/compiler/parser/components/declaration.py:120-132` | `int fn f = ...`（`IbSubscript(fn, TYPE)`）解析路径 | D1：fn 侧不再承载类型 |
| `core/compiler/semantic/passes/semantic_analyzer.py` | `visit_IbAssign` 中的 `DeferredSpec(value_type_name≠auto)` 注入逻辑 | D1/D2：不再需要注入 |

### 需要新增的内容

| 位置 | 内容 | 原因 |
|------|------|------|
| `core/kernel/ast.py:IbLambdaExpr` | `returns: Optional[IbExpr] = None` 字段 | D2：表达式侧返回类型存储 |
| `core/compiler/parser/components/expression.py:lambda_expr()` | `-> TYPE` 的消费逻辑（在 `:` 之前） | D2：表达式侧返回类型解析 |
| `core/compiler/semantic/passes/semantic_analyzer.py:visit_IbLambdaExpr` | 从 `node.returns` 读取返回类型（替代 `_pending_fn_return_type`） | D2 |
| `core/compiler/parser/components/type_def.py:parse_type_annotation()` | `fn[...]` callable 签名解析专用路径 `_parse_fn_signature()` | D3 |
| `core/kernel/ast.py` | 新增 `IbCallableType` 节点（或复用 `IbSubscript` + 语义标记）用于携带 callable 签名约束 | D3 |
| `core/compiler/semantic/passes/semantic_analyzer.py` | call site 结构签名匹配逻辑（按签名形状检查，而非 FuncSpec 名字） | D3 |

### 需要修改的内容

| 位置 | 内容 | 原因 |
|------|------|------|
| `core/compiler/parser/components/expression.py:lambda_expr()` | 拒绝行为改为硬错误：`int fn f = lambda: ...` 形式 | D1 |
| `core/compiler/parser/core/recognizer.py:_is_declaration_lookahead` | 确认 `int fn f` lookahead 分支在新语法下仍能正确报错而非静默误判 | D1 |
| `docs/IBCI_SYNTAX_REFERENCE.md` | 更新 §5（fn/lambda/snapshot 语法）、§十五（废弃语法列表）、§十三（auto/fn/any 对比表） | 文档同步 |
| `docs/KNOWN_LIMITS.md` | 删除/更新 §三（`fn` 变量设计问题）的"不建议使用"警告 | D1/D2 落地后该限制消除 |

---

## 四、实施顺序（建议）

D1、D2 是**耦合变更**，必须在同一 PR 中完成，原因：废除 `int fn f = ...` 后，原先唯一的
返回类型声明路径消失，必须同时开放表达式侧 `-> TYPE` 才能维持功能完整性。

D3（`fn[...]` 高阶签名）与 D1/D2 **相互独立**，可单独 PR。

```
Phase 1（耦合，一个 PR）：
    └── D1: 删除 int fn f = ... 形式 + _pending_fn_return_type
    └── D2: IbLambdaExpr.returns + 表达式侧 -> TYPE + 移除 PAR_005

Phase 2（独立 PR）：
    └── D3: fn[...] callable 签名解析 + 语义层结构匹配

D4: 结论（无代码变更需要）
D5: 维持现有强制显式路线（无代码变更需要）
D6: 跨文件向前引用暂不列入近期目标
```

---

## 五、测试影响

Phase 1 需要同步更新以下测试：
- 所有使用 `int fn f = lambda: ...` / `int fn f = snapshot: ...` 形式的测试用例
  （涉及 `tests/unit/` 和 `tests/e2e/` 中 fn/lambda/snapshot 相关测试）。
- PAR_005 触发的负向测试用例需更新触发条件（旧形式 `lambda -> TYPE:` 现在合法；
  新的非法形式是 `int fn f = lambda: ...`）。

Phase 2 应同步新增：
- `fn[(int)->int]` 参数类型标注的解析单元测试。
- 高阶函数签名不匹配的负向语义测试（SEM_005 扩展或新错误码）。

---

*本文档为完整的设计决策参考，实现 PR 应在完成对应 Phase 后将本文档中相应条目移至
`docs/COMPLETED.md`，并更新 `docs/IBCI_SYNTAX_REFERENCE.md`、`docs/KNOWN_LIMITS.md`。*
