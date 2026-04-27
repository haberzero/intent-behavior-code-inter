# IBC-Inter 近期优先任务

> 记录接下来可以直接开工的具体任务，按优先级排列。  
> 中长期任务见 `docs/PENDING_TASKS.md`，已完成工作见 `docs/COMPLETED.md`。  
> VM 架构长期设想（含三层并发模型、llmexcept 危险悬案）见 `docs/PENDING_TASKS_VM.md`。
>
> **最后更新**：2026-04-27（文档与代码一致性审计；690 个测试通过；str/list * int 乘法、global 语句、is/is not 运算符等均已验证）

---

## 当前整体状态评估

**核心公理化路径已全部完成**（Step 1 → Step 7）：

- ✅ 公理体系（Axiom）：`KernelRegistry` sealed 封印；primitive 类型已完成 Axiom 化
- ✅ vtable 分发：`IbObject.receive()` + `IbClass.lookup_method()` 消息传递模型
- ✅ LLM 执行路径统一：`LLMExecutorImpl` 通过 `capability_registry.get("llm_provider")` 唯一来源
- ✅ `IExecutionFrame` Protocol（Step 5）：`core/base/interfaces.py`，`ContextVar` 帧注册表
- ✅ `IbIntentContext` 公理化（Step 6）：独立意图上下文类型；`RuntimeContextImpl` 完整迁移（6c/6d）
- ✅ `LlmCallResultAxiom` + `IbLLMCallResult`（Step 7）：LLM 结果类型完整接入公理体系
- ✅ `IbLLMCallResult` 全链路接入：`set_last_llm_result()` 自动转换；所有读取点使用 `is_certain`
- ✅ vibe 代码债务清理：`interpreter.py:229` kwargs bug 修复；`engine.py` orchestrator 注入规范化
- ✅ **Step 8-pre（快照隔离完整落地）**：§9.2 SEM_052 编译期 read-only 约束 + §9.3 `_last_llm_result` per-snapshot 化；idbg `last_result()` / `last_llm()` 帧优先模式；`retry_stack()` 含帧私有 `last_result` 详情
- ✅ **`__prompt__` 协议 vtable 修复**：`_parse_result()` + `_get_llmoutput_hint()` 增加用户类 vtable 回退路径；`IbObject.__outputhint_prompt__()` 委托给 vtable 方法
- ✅ **`for...if` / `while...if` 过滤语法**：`visit_IbFilteredExpr` 实现（while 场景）；`visit_IbFor` 拆包 `IbFilteredExpr`，foreach 场景在目标赋值后求值 filter（`continue` 语义），条件驱动 for 场景 filter 失败终止循环（`break` 语义，与 `while...if` 一致）
- ✅ **llmexcept 快照深克隆（方案A）**：`LLMExceptFrame._save_vars_snapshot()` 使用 `_try_deep_clone()`，支持用户自定义 `IbObject` 实例的递归字段克隆；循环引用通过 `memo` dict 安全处理
- ✅ **llmexcept 用户协议快照（方案B）**：`saved_protocol_states` 字段；`_save_vars_snapshot()` 检测 `__snapshot__` vtable 并优先使用；`_restore_vars()` 调用 `__restore__(state)` 原地恢复；方案B优先于方案A，失败时自动降级；方案C（JSON 序列化）已作为 VM 任务记录在 `docs/PENDING_TASKS_VM.md`
- ✅ **函数调用意图隔离（§9.4）**：`IbUserFunction.call()` + `IbLLMFunction.call()` 统一 fork/restore；`@!` 语义恢复为只修饰 LLM 行为表达式（不修饰函数调用）；`intent_context.clear_inherited()`/`use(ctx)`/`get_current()` 三个显式作用域控制 API 在 `builtin_initializer.py` 注册
- ✅ **lambda 参数传递约束**：`deferred_mode='lambda'` 的延迟对象作为函数实参时运行时报错；`snapshot` 不受限
- ✅ **intent_context OOP MVP（§9.5）**：`IntentContextAxiom.is_class=True`；`INTENT_CONTEXT_SPEC = ClassSpec(...)`；实例方法 `__init__/push/pop/fork/resolve/merge/clear` + 作用域控制方法 `clear_inherited/use/get_current` 注册
- ✅ **`in` / `not in` 运算符**：`IbCompare` 支持成员检测；`str`/`list`/`dict` 均实现 `__contains__` vtable
- ✅ **标准库方法补全**：`str.{find_last, is_empty, replace, startswith, endswith, trim, to_upper, to_lower}`；`list.{insert, remove, index, count, contains}`；`dict.{pop, contains, remove}`；`Exception(msg)` 构造 + `e.message` 字段；`list + list` 拼接；610 测试通过
- ✅ **Step 8（架构边界文档化）**：`interpreter.py`/`engine.py`/`service.py` 头部添加边界说明注释
- ✅ **Bug #1 修复（IbBool(False) 假值）**：`result.value if result and result.value` 三处改为 `result is not None and result.value is not None`；修复 `bool b = @~ MOCK:FALSE ~` 报 `Type mismatch` 及 bool/int 零值被误替换为 None
- ✅ **Bug #2 修复（重复 `_stmt_contains_behavior`）**：删除 `semantic_analyzer.py` 中 AI Agent 遗留的残缺重复定义（只处理 `IbExprStmt`/`IbAssign`/`IbReturn`），恢复正确版本（含 `IbIf`/`IbWhile`/`IbFor`）；修复 `llmexcept` 跟在 `if/while/for @~...~:` 后始终报 SEM_050 的问题
- ✅ **Bug #3 修复（泛型专化崩溃）**：三处联合修复：`_resolve_type` 改调 `self.registry.resolve_specialization()`；`SpecRegistry.resolve_specialization` 修正 `hasattr` 检查名称 + 补全新注册 Spec 的方法成员；`list[str]`/`dict[str,int]`/`tuple[int]` 等泛型标注完全可用

---

## ✅ COMPLETED：__prompt__ 系列协议对用户自定义类的局限性

~~**问题描述（已修复）**：~~

已完成修复（2026-04-19）：

| 协议 | 用户 IBCI 自定义类 | Python Axiom 内置类型 |
|------|-------------------|----------------------|
| `__to_prompt__` | ✅ 有效（vtable 消息传递路由） | ✅ 有效 |
| `__from_prompt__` | ✅ **已修复**（vtable 回退路径） | ✅ 有效 |
| `__outputhint_prompt__` | ✅ **已修复**（vtable 回退路径） | ✅ 有效 |

**修复内容**：
1. `_parse_result()`（`llm_executor.py`）：Axiom 路径无匹配时，通过 `registry.get_class(type_name).lookup_method('__from_prompt__')` 调用用户 vtable 方法（以 `IbClass` 为 receiver，类方法语义）。返回值约定为 `(bool, any)` 元组（成功标志 + 解析值）。
2. `_get_llmoutput_hint()`（`llm_executor.py`）：Axiom 路径无匹配时，通过 vtable 查找 `__outputhint_prompt__`（以 `IbClass` 为 receiver）。
3. `IbObject.__outputhint_prompt__()`（`kernel.py`）：委托给 vtable `receive('__outputhint_prompt__', [])`，vtable 缺失时退回默认字符串。

**用户 IBCI 类实现约定**：
```ibci
class MyType:
    str field

    func __from_prompt__(str raw) -> tuple:
        # 解析 raw，返回 (True, parsed_value) 或 (False, "错误提示")
        return (True, raw)

    func __outputhint_prompt__(self) -> str:
        return "请返回一个 JSON 格式的 MyType 对象"
```

---

## Step 8：概念边界文档化 [✅ COMPLETED — 2026-04-20]

三个核心文件头部已添加架构边界说明注释：

- `core/runtime/interpreter/interpreter.py` 头部：明确 Interpreter = 执行隔离单元，不是 LLM 并发单元
- `core/engine.py` 头部：明确 Engine = 组装者，不参与执行
- `core/runtime/host/service.py` 头部：明确 DynamicHost（HostService）= 编排者，不亲自执行 IBCI 代码

---

## Step 8-pre：llmexcept 快照隔离约束完整落地 [✅ COMPLETED — 2026-04-19]

快照隔离模型已在代码层面完全自洽：

1. **§9.2 编译期 read-only 约束**（SEM_052）✅：llmexcept body 内向外部作用域变量的任何赋值（含类型标注重声明）产生 `SEM_052` 编译期错误；body-local 新声明变量和 `retry` 语句不受限制。新增 `TestLLMExceptBodyReadOnly` 覆盖 6 个测试场景。
2. **§9.3 `_last_llm_result` per-snapshot 化** ✅：读取后立即清零共享字段（不再依赖 `finally` 块恢复）；`LLMExceptFrame.last_result` 是 per-snapshot 权威来源；idbg `last_result()` / `last_llm()` 改为帧优先模式；`retry_stack()` 含帧私有 `last_result` 详情（替代始终为 None 的 `last_llm_response`）。
3. **§9.4 用户自定义对象深克隆快照** ✅：`LLMExceptFrame._try_deep_clone()` 递归克隆用户 IBCI 对象实例，字段回滚在 retry 时生效；函数/行为/原生对象不参与快照（跳过，不影响正确性）。
4. **§9.5 用户协议快照（方案B）** ✅：`LLMExceptFrame` 新增 `saved_protocol_states`；`_save_vars_snapshot()` 检测 vtable 中的 `__snapshot__` 方法，优先调用（方案B）；`_restore_vars()` 对方案B对象调用 `__restore__(state)` 原地恢复，方案A对象替换变量绑定；`__snapshot__` 调用失败时自动降级到方案A。

---

## Step 9：VM CPS 调度循环 [P2 - IExecutionFrame 接口完整后可推进]

**前提**：Step 5 IExecutionFrame 接口已完整（✅ 已具备）

**本质**：消除当前解释器的 Python 递归调用栈，改用 CPS（Continuation-Passing Style）调度循环，支持：
- 解释器不再受 Python 调用栈深度限制
- 为 Layer 2 多 Interpreter 并发（`DynamicHost.spawn` 线程化）铺路

详见 `docs/PENDING_TASKS_VM.md`。

---

## Step 10：Layer 1 LLM 流水线 [P2 - Step 6 意图 fork 完成后可推进]

**前提**：Step 6 `IbIntentContext.fork()` 已完整（✅ 已具备）

**本质**：DDG 编译器 + `LLMScheduler` 实现 dispatch 时刻意图绑定，支持 LLM 调用并行化。

详见 `docs/PENDING_TASKS_VM.md`。

---

## Step 11：Layer 2 多 Interpreter 并发 [P3 - Step 5 ContextVar 完整后]

**前提**：Step 5 ContextVar（多线程下帧状态隔离）已完整（✅ 已具备）

**本质**：`DynamicHost.spawn` 线程化，每个 Interpreter 实例持有独立 ContextVar 槽位。

详见 `docs/PENDING_TASKS_VM.md`。

---

## 任务依赖图（历史完成路径）

```
Step 4b（完成）
    │
    ├──→ Step 5a（IExecutionFrame Protocol 定义）[✅ 完成]
    │        │
    │        └──→ Step 5b（ContextVar，IbUserFunction 去除 context 参数）[✅ 完成]
    │                    │
    │                    └──→ Step 6a（IntentContextAxiom）[✅ 完成]
    │                                 │
    │                                 ├──→ Step 6b（IbIntentContext 运行时对象）[✅ 完成]
    │                                 │            │
    │                                 │            └──→ Step 6c（RuntimeContextImpl 迁移）[✅ 完成]
    │                                 │                         │
    │                                 │                         └──→ Step 6d（LLMExceptFrame 修复）[✅ 完成]
    │                                 │
    │                                 └──→ Step 7（LlmCallResultAxiom + IbLLMCallResult 接入）[✅ 完成]
    │
    └──→ Step 8（文档化，随时可做）
```

**下一优先路径**：Step 9（CPS 调度循环）→ Step 10（LLM 流水线，含 10a/10b/10c 三阶段）→ Step 11（多 Interpreter 并发）→ Step 12（可移植性参考实现）→ **Step 12.5（fn 参数化 lambda/snapshot 新语法 + IbCell 机制）**

---

## Step 12.5：fn 参数化 lambda/snapshot 新语法 [P2 - 独立，可在 Step 9 之后推进]

> **来源**：2026-04-27 架构讨论，用户已确认接受本方案。  
> **前提**：Step 9（VM CPS 调度循环）完成后，或独立推进（无强依赖）。  
> **关联**：`docs/PENDING_TASKS_VM.md` §10.6（IbCell 机制）、`docs/INTENT_SYSTEM_DESIGN.md` §9（延迟对象意图规则）。

### 背景

当前的 `lambda`/`snapshot` 语法（`TYPE lambda NAME = EXPR`）存在以下问题：
1. **不支持参数传递**：延迟对象调用时不能传入参数，表达能力受限（见 `docs/PENDING_TASKS.md` §4.3）
2. **变量捕获语义不明确**：自由变量通过 `captured_scope` 引用捕获，未引入 `IbCell` 机制，不满足词法闭包正式语义（见 `docs/PENDING_TASKS_VM.md` §10.2）
3. **声明风格与 fn 关键字不对齐**：旧语法 `TYPE lambda NAME = EXPR` 与 `fn NAME = FUNC_REF` 风格不一致

**本 Step 的目标**：用新的统一 `fn` 声明语法替代旧语法，同时引入参数传递能力和明确的捕获语义。

---

### 新语法规范

#### 无参数形式（替代当前 `auto/TYPE lambda NAME = EXPR`）

```ibci
# 无参 lambda：捕获自由变量的 cell，调用时 deref 最新值
fn my_fn = lambda(n * 2)

# 无参 snapshot：定义时对自由变量值拷贝，定义时对意图栈 fork，结果缓存
fn my_fn = snapshot(n * 2)

# 带返回类型标注
fn int my_fn = lambda(n * 2)
fn str my_fn = snapshot(@~ 翻译 $text ~)
```

#### 有参数形式（新增）

```ibci
# 带参 lambda（词法闭包 + 参数）
fn int my_fn = lambda(int x)(x + n)
# 含义：每次调用传入 int x；n 是自由变量，cell 捕获；返回 x + current(n)

# 带参 snapshot（冻结闭包 + 参数）
fn int my_fn = snapshot(int x)(x + n)
# 含义：每次调用传入 int x；n 在定义时值拷贝为常量；返回 x + frozen(n)

# 带参 behavior（意图规则见 §9）
fn str translate = lambda(str text)(@~ 翻译 $text ~)
fn str translate = snapshot(str text)(@~ 翻译 $text ~)
```

#### 多行函数体形式

```ibci
fn int my_fn = lambda(int x):
    int doubled = x * 2
    return doubled + n        # n 是 cell 捕获的自由变量

fn int my_fn = snapshot(int x):
    return x + n              # n 在定义时已被冻结
```

#### 高阶函数示例

```ibci
# 工厂函数：返回 lambda 闭包
func make_formatter(str prefix) -> fn:
    fn str result = lambda(str s)(prefix + ": " + s)
    # prefix 是 cell 捕获，s 是参数
    return result

fn str fmt = make_formatter("INFO")
str msg = fmt("hello")    # → "INFO: hello"
```

---

### 与旧语法的对比

| 旧语法 | 新语法 | 说明 |
|--------|--------|------|
| `int lambda f = @~ ... ~` | `fn int f = lambda()(@~ ... ~)` | 无参 lambda + behavior |
| `str snapshot b = @~ ... ~` | `fn str b = snapshot()(@~ ... ~)` | 无参 snapshot + behavior |
| `auto lambda lazy = x + 5` | `fn lazy = lambda(x + 5)` | 无参 lambda + 普通表达式 |
| `auto snapshot cached = x + 5` | `fn cached = snapshot(x + 5)` | 无参 snapshot + 普通表达式 |
| `fn f = my_func`（现有，不变） | `fn f = my_func`（保持不变） | 函数引用赋值，不变 |

---

### 实现任务清单

1. **词法分析器**：`lambda`/`snapshot` 关键字已有，确认与新语法解析路径兼容
2. **语法解析器**：
   - 新增 `fn` 声明中识别 `= lambda(...)` / `= snapshot(...)` 形式
   - 区分无参形式 `lambda(EXPR)` 和有参形式 `lambda(PARAMS)(BODY)`
   - 支持多行块形式 `lambda(PARAMS):\n BODY`
3. **语义分析器**：
   - 分析自由变量并标注 Cell 变量（SC-2）
   - 在 `closure` 字典中记录 Cell 引用（SC-4）
   - 区分 `lambda`（cell 捕获）和 `snapshot`（值拷贝）的自由变量处理方式
4. **运行时**：
   - 引入 `IbCell` 类型（`docs/PENDING_TASKS_VM.md` §10.6）
   - 更新 `IbDeferred.call()` / `IbBehavior.call()` 支持参数传递
   - 更新意图上下文交互（`docs/INTENT_SYSTEM_DESIGN.md` §9）
5. **测试**：
   - 重写 `tests/e2e/test_e2e_deferred.py` 中已注释的旧语法测试
   - 补充参数传递、Cell 生命周期、意图交互的新测试

---

### 旧语法的废弃路径

1. Step 12.5 **实现阶段**：新旧语法并存，旧语法输出 `DEP_001` 废弃警告
2. Step 12.5 **稳定后**：旧语法产生 `PAR_001` 解析错误，正式移除
3. 已注释的旧语法测试（`test_e2e_deferred.py`）在新语法稳定后重写

---

> **来源**：2026-04-27 实测核实。

### 现状摘要（2026-04-27 更新）

| 写法 | 行为 | 备注 |
|------|------|------|
| `int a, int b = t` | ✅ **已修复**（裸列形式元组解包） | 与 Python `a, b = t` 对齐 |
| `(int a, int b) = t` | ✅ 正常，按 `tuple → 两个 int` 解包 | 等价写法 |
| `(int a, int b) = (1, 2, 3)` | ❌ 运行期 `RUN_001: Unpack error: expected 2 values, got 3` | 元数检查正确 |
| `(int a, str b) = (1, "x")` | ✅ 正常，混合类型解包正确 | — |
| `for (int x, int y) in list[tuple]` | ✅ **已修复** | 解析为元组解包目标，每个分量按各自标注类型定义 |
| `tuple t = (1, 2); auto a = t[0]; auto b = t[1]` | ✅ 正常 | 下标访问可用 |
| `tuple` 函数返回值再下标 | ✅ 正常 | `(int)r[0]` 可用 |

### 已完成（小任务，2026-04-27）

1. ✅ **裸列形式 `int a, int b = t` 元组解包**：解析器在解析单变量声明后探测 `,` 折叠为元组解包目标（`core/compiler/parser/components/declaration.py:variable_declaration`）；支持 `auto` / 类型混搭；`deferred_mode` 修饰下保持单变量语义不变。
2. ✅ **`for (int x, int y) in coords:` 类型标注元组目标**：根因在语义分析的 `visit_IbFor` 对 `get_assigned_names` 输出的去重缺失——同名 `IbName` 条目以 `element_type` 覆盖了 `IbTypeAnnotatedExpr` 已写入的精确类型；修复后逐分量类型与注解一致（`core/compiler/semantic/passes/semantic_analyzer.py:visit_IbFor`）。
3. ✅ **错误路径自然消解**：`for (int x, int y) in list[tuple]` 不再误用整体 `tuple` 类型作为分量类型，旧的 `RUN_002` 误导信息不再可达。元组目标但缺少注解的元素现在保持 `any`，避免错误的兜底类型。


### 临时规避

- 无类型 / `auto` 解包：`auto a = t[0]; auto b = t[1]`
- `for tuple pair in coords:` + `auto x = pair[0]; auto y = pair[1]`
- 多返回值场景使用 `(int a, int b) = func()` （加括号）

---

*本文档记录近期可执行任务。VM 架构长期设想（三层并发/llmexcept危险悬案）见 `docs/PENDING_TASKS_VM.md`。*

