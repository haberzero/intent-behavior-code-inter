# IBC-Inter 已知限制（语言级）

> 本文档记录 IBCI 当前版本中正式承认的语言设计限制与使用约束。面向需要了解 IBCI 语言边界的所有开发者和使用者。每个限制条目包含限制说明、根源分析与规避建议。
>
> 语言设计决策与规划见 `docs/ARCHITECTURE.md`；测试基线以 `python -m pytest tests/` 实跑为准。

---

## 一、可调用类实例（`__call__` 协议）

**限制说明**

可调用类实例（即实现了 `__call__` 方法的用户自定义类的实例）在调用方式上存在设计问题，**不建议使用**。

**根源**

`fn` 类型推断对 `__call__` 协议与闭包捕获、意图栈副作用的若干交叉路径存在不一致——尤其是当可调用类实例内部触发 `@~...~` 或意图栈相关副作用时，类型推断与运行时分发之间的错位可能产生静默错误。

```ibci
class MyCallable:
    func __call__():
        ...

MyCallable obj = MyCallable()
obj()  # ⚠️ 可调用类实例的调用方式存在设计问题
```

---

## 二、`Enum` 语法

**支持状态**：当前版本已提供基础 `Enum` 支持，但存在以下使用约束需要注意。

### 2.1 声明方式

`Enum` 通过继承内置 `Enum` 类实现，成员字段必须显式声明类型（当前版本仅支持 `str` 类型的枚举成员）：

```ibci
class Color(Enum):
    str RED   = "RED"
    str GREEN = "GREEN"
    str BLUE  = "BLUE"
```

### 2.2 访问与比较

枚举成员通过类名访问（`Color.RED`），支持 `==` / `!=` 比较：

```ibci
Color c = Color.BLUE

# 访问
print((str)Color.RED)    # 输出: RED

# 比较
if c == Color.BLUE:
    print("blue")

# switch/case（枚举的推荐控制流形式）
switch c:
    case Color.RED:
        print("red")
    case Color.BLUE:
        print("blue")
    default:
        print("other")
```

### 2.3 当前限制

- **仅支持 `str` 类型成员**：枚举成员的底层值目前只能声明为 `str` 类型。`int` 等其他类型成员在未来版本中支持。
- **不支持枚举迭代**：当前无法对枚举类的所有成员进行遍历（如 `for v in Color:`）。
- **不支持枚举数量/序数查询**：`len(Color)`、成员序号等功能暂不支持。
- **LLM 集成**：`Enum` 类型已具备 `has_output_hint_cap = True` 能力，LLM 函数可以直接输出枚举成员名称并自动解析为对应枚举值。

---

## 三、`Uncertain` 内部哨兵值（用户不可见）

`Uncertain`（`IbLLMUncertain`）是 IBCI 内核的**内部机制**，不是用户可编程接口。

**设计语义**：
- `llmexcept` 保护帧内，LLM 调用无法产生确定结果时，VM 在重试循环期间会将目标变量
  临时赋值为 `Uncertain` 哨兵。这是 VM 快照/重试通信令牌，在下一次 `restore_snapshot + retry`
  后会被真实值替换。
- `llmexcept` 块外：uncertain 状态不会出现——infra 失败（网络/鉴权）→ `LLMCallError`；
  内容解析失败 → `LLMParseError`；重试耗尽 → `LLMRetryExhaustedError`。

**用户代码无需处理 uncertain**：
- `llmexcept` 块内处于重试循环，用户只需书写 `retry "hint"` 语句，无需显式检测 Uncertain。
- `is_uncertain()` 内置函数已从用户 API 移除。`Uncertain` 字面量也不应出现在正常业务代码中。

---

## 四、行为表达式不可直接用于 `return` 语句

**限制说明**

行为表达式（`@~ ... ~`）的输出类型和提示词约束由左值类型驱动（即赋值目标的类型）。
在 `return` 语句中直接书写行为表达式时，由于无法从函数返回类型标注中以静态明确的方式推导出提示词约束，编译器**禁止**此写法，报 `SEM_TYPE_MISMATCH` 错误。

**正确用法**

先将行为表达式赋值给有类型的局部变量，再 `return` 该变量：

```ibci
# ✅ 正确：通过有类型的局部变量明确输出约束
func get_reply() -> str:
    str reply = @~ 给我一句话 ~
    return reply
```

**设计原因**

行为表达式的目标类型同时决定了注入给 LLM 的输出格式约束（通过 `__outputhint_prompt__`）以及 LLM 返回值的解析方式（通过 `__from_prompt__`）。将其绑定到明确的左值类型可以保证语义清晰、无歧义，而不是将执行语义与函数签名隐式耦合。

---

## 五、引用语义局限性

IBCI 对所有复合对象（`list` / `dict` / 用户类实例）使用**共享引用**语义——与 Python 一致。

### 5.1 赋值是引用复制

```ibci
list a = [1, 2, 3]
list b = a          # b 与 a 指向同一个列表
b.append(4)
print((str)a.len()) # 输出 4
```

**规避方案**：手动构造副本（IBCI 暂未提供 `copy` / `deepcopy` 内建）：

```ibci
list b = []
for int x in a:
    b.append(x)
```

### 5.2 类实例字段的默认引用陷阱

若多个实例共享同一个"默认"列表字段，修改一个实例的字段会影响其他实例。**始终在构造函数中初始化列表 / 字典字段**：

```ibci
class Stack:
    list items
    func __init__(self):
        self.items = []  # 每个实例独立创建
```

### 5.3 `fn` 变量的可调用引用语义

```ibci
fn f = add          # f 持有 add 函数的引用
fn g = f            # g 也引用同一个函数
```

函数本身是不可变的，因此 `fn` 变量的引用语义不会导致副作用问题。

---

## 六、子类 auto-init 不含父类字段

**严重级别**：低（符合 Python 语义，但与 C++/Java 使用者直觉不符）

当子类没有显式 `__init__`，编译器会自动生成一个 `__init__`，**仅接受当前类自身声明的字段**，不包含父类字段。

```ibci
class Animal:
    str name

class Dog(Animal):
    str breed       # Dog 的 auto-init 只接受 breed，不接受 name

Dog d = Dog("Husky")    # 只设置 breed；d.name = None
```

**正确用法**：在子类中显式定义 `__init__` 并通过 `super().__init__(...)` 初始化父类字段：

```ibci
class Dog(Animal):
    str breed
    func __init__(self, str n, str b):
        super().__init__(n)
        self.breed = b
```

> **注意**：`super()` 对所有 IBCI 用户类均有效——所有用户类隐式继承自 `Object` 基类（类似 Python 3）。即使没有显式写 `class Foo(Bar):`，`super()` 也可在方法内使用，此时它指向 `Object`。

**根源**：auto-init 生成逻辑（`interpreter.py:_hydrate_user_classes`）仅遍历当前类 `body` 中声明的字段。父类字段通过 `default_fields` 继承，但不加入构造函数参数。此设计与 Python 行为一致（子类不自动调用 `super().__init__`）。

---

## 七、`auto` / `fn` / `any` 对比

| 关键字 | 用途 | 类型推导时机 | 后续赋值限制 |
|--------|------|------------|------------|
| `auto x = expr` | 通用类型推导，锁定为首次赋值的实际类型 | 编译期 | 只能赋相同类型 |
| `fn f = callable` | 可调用类型推导，RHS 必须是可调用的 | 编译期 | 保持可调用约束 |
| `any x = expr` | 真正的动态类型，不锁定 | 运行时 | 任意类型 |
| `x = expr`（裸赋值）| 隐式 `any` 语义（不推荐） | 运行时 | 任意类型 |

> **注意**：没有类型标注的裸赋值（`x = expr`）编译器会将变量视为 `any` 类型。
> 若需要将此变量用于有类型检查的上下文（如赋给 `int y`），**必须使用强制类型转换**：
> ```ibci
> x = 42
> int y = (int)x    # 必须显式转换，不能直接赋值
> ```

---

## 八、容器多类型声明

`list[int, str, list]` 语法允许声明一个可持有多种类型元素的列表。编译器规则：

- **元素读取**（下标访问 / for 迭代）返回 `any` 类型。若需明确类型，必须显式转换：
  ```ibci
  list[int, str] mixed = [1, "hello"]
  any val = mixed[0]
  int n = (int)val      # 必须先取到 any，再强制转换
  ```
- **不允许** 通过 `auto` 直接承载容器元素取值赋值（编译期推断会失败）：
  ```ibci
  auto x = mixed[0]    # ❌ 不推荐
  any x = mixed[0]     # ✅ 建议始终用 any 中转
  int n = (int)x        # ✅ 再强制转换到目标类型
  ```

---

## 九、已废弃语法（产生硬编译错误）

### `(Type) @~...~` 强制类型转换语法（PAR_DEPRECATED_CAST_SYNTAX）

```ibci
# ❌ 已废弃，产生 PAR_DEPRECATED_CAST_SYNTAX 编译错误
int sum = (int) @~ 请计算 $a 和 $b 之和 ~

# ✅ 正确写法：LHS 类型自动成为 LLM 输出格式约束
int sum = @~ 请计算 $a 和 $b 之和 ~
str mood = @~ 请判断颜色，回复颜色单词 ~
```

LHS 的变量声明类型会自动被传递给 LLM 作为输出格式提示，无需额外的类型转换语法。

### 旧 fn / lambda 声明语法（PAR_INVALID_SYNTAX）

```ibci
# ❌ 全部产生 parse error
int lambda f = expr           # 旧声明语法（PAR_EXPECTED_TOKEN）
auto snapshot g = expr        # 旧声明语法（PAR_EXPECTED_TOKEN）
fn lambda h = expr            # 旧括号体形式（PAR_EXPECTED_TOKEN）
lambda(EXPR)                  # 旧括号体形式（PAR_EXPECTED_TOKEN）
lambda(PARAMS)(EXPR)          # 旧括号体形式（PAR_EXPECTED_TOKEN）
int fn f = lambda: EXPR       # 声明侧返回类型（PAR_INVALID_SYNTAX）
int fn f = snapshot(int a, int b): EXPR  # 声明侧返回类型（PAR_INVALID_SYNTAX）

# ✅ 正确写法：返回类型标注写在表达式侧
fn f = lambda: EXPR                          # 无参，返回类型推导
fn f = lambda -> int: EXPR                   # 无参，显式返回类型
fn f = lambda(int x): EXPR                  # 有参，返回类型推导
fn f = lambda(int x) -> int: EXPR           # 有参，显式返回类型
fn f = snapshot -> int: EXPR                # snapshot，显式返回类型
fn f = snapshot(int a, int b) -> str: EXPR  # snapshot 有参
```

声明侧返回类型 `TYPE fn NAME = lambda: EXPR` 形式已被废弃（产生 PAR_INVALID_SYNTAX），改为在表达式侧通过 `-> TYPE` 标注。

---

## 十、泛型与容器类型限制

### 10.1 `dict` 键类型在下标访问时不校验

`dict[str, int]` 的键类型在运行时下标访问时不校验。键类型安全由用户自行保证，编译器/运行时不提供保护。

---

## 十一、Switch 语句设计未稳定

**限制说明**

`switch`/`case` 语法的 AST 节点位于 `core/kernel/ast.py` 的 `IbSwitch` 类，基本功能可用，但语义设计存在待改进问题。

**根源**

- case 匹配语义不完整（值比较、类型匹配、模式匹配的边界不清晰）
- default 语句的兜底行为需要明确定义
- switch 内控制流（break/continue/return）与其他控制流的一致性待验证
- 与 if/elif/else 的语义差异与使用场景未充分区分

**当前建议**：暂不在生产代码中使用 `switch`/`case` 语句，优先使用 `if`/`elif`/`else` 实现条件分支逻辑。

**测试覆盖**：e2e 层有 `tests/e2e/test_e2e_classes.py::TestE2EEnums::test_switch_case`，但尚无契约测试（INV-SWITCH-*）。

---

## 十二、`intent_context` 类静态调用的"静默无效"陷阱

**限制说明**

`intent_context.push("X")` / `intent_context.pop()` / `intent_context.fork()` / `intent_context.merge()` / `intent_context.combine()` / `intent_context.clear()` 在"未持有具体 `intent_context` 实例"时直接当作类静态调用使用，**不会影响当前作用域生效的意图栈**——这些方法操作的是 receiver 实例字段 `_ctx`（见 `core/runtime/bootstrap/builtin_initializer.py` 中 `intent_context` 方法注册段）。当 receiver 是临时的"类对象"占位时，对该占位 `_ctx` 的修改无人引用，对外**完全无效**。

**有效路径**：

```ibci
# 1) 用 @+ / @ / @! 语法直接写入"当前作用域"的意图栈（推荐）
@+ "持久意图"
str r = @~ ... ~

# 2) 显式持有 ctx 实例，再用 use(ctx) 安装到当前作用域
intent_context ctx = intent_context.get_current()   # 取当前快照（fork 副本）
ctx.push("via API")
intent_context.use(ctx)                              # ← 必须 use，否则上一步无效
str r = @~ ... ~
```

**作用域控制方法（在类上调用也生效）**：仅 `intent_context.clear_inherited()` / `intent_context.use(ctx)` / `intent_context.get_current()` 这三个方法被特别实现为"直接操作当前执行帧的 `_intent_ctx`"——它们对类静态调用和实例调用语义等价（见 `core/runtime/bootstrap/builtin_initializer.py` 中对应方法注册段的注释）。

**编译期防护（SEM_INTENT_STATIC_CALL）**：TypeCheckingPass 现已对 `intent_context.push(...)` / `pop()` / `fork()` / `merge(...)` / `combine(...)` / `clear()` 在类对象上的调用发出 SEM_INTENT_STATIC_CALL warning，提示用户先通过 `get_current()` 获取实例。`use()`/`get_current()`/`clear_inherited()` 不触发警告（这些在类上调用也生效）。

**测试覆盖**：`tests/compiler/semantic/test_p2_warnings.py::TestIntentContextStaticCallWarning`（9 个测试）。

---

## 十三、`@` 意图注释的放置约束

**当前状态**：以下规则由编译期 `SEM_INTENT_PLACEMENT` 与 VM 语句调度共同保证：

1. `@`（smear）与 `@!`（override）必须紧跟**下一条可执行语句**（可以是普通函数调用、赋值、控制流语句等），不能作为块末尾孤立存在。
2. `@` / `@!` 是"语句级 one-shot"：绑定到紧随其后的**一条语句执行窗口**。该语句执行期间若触发 LLM 调用会消费它；若该语句路径没有任何 LLM 调用，窗口结束后也会被清理，不会泄漏到后续语句。
3. 连续两个 `@` / `@!`（one-shot）不允许：编译期报 `SEM_INTENT_PLACEMENT`。`@+` / `@-` 作为栈操作可独立存在并与 one-shot 组合。
4. `@-` 是合法语法：支持无参弹栈、按内容移除、按标签移除（`@- #tag`）。

**根源**：意图注释设计为对"下一条语句执行窗口"的修饰；该规则让编译期能确定 one-shot 的归属，同时让运行时在无 LLM 路径上也保持无泄漏的一致语义。

---

## 十四、用户类相关能力差距

以下是面向"用户自定义类"的能力差距。这些差距并非 bug，而是设计未覆盖。

1. **用户类无法定义泛型参数**：`class Box[T]:` 在词法 / 语法 / AST（`IbClassDef` 无 `type_params`）/ 语义层均未实现。内置 `list[T]` / `dict[K,V]` / `Optional[T]` / `tuple[T,...]` 全部走内置 axiom 的 `resolve_specialization_by_names` 路径，用户类型无对应入口。
2. **用户类无法重载二元/比较运算符**：`__add__` / `__eq__` / `__lt__` / ... 等运算符 dunder 协议在 `core/runtime/objects/kernel/`（包）的 IbClass 中无注册机制；内置 axiom（Integer/Float/Str 等）可派遣 `+` / `==` / `<`，用户类不能。`==` 在用户类上退化为身份比较。

**未来演进思路（不构成承诺）**：涉及用户类泛型参数与运算符重载能力扩展，具体规划见任务文档。

---

## 十五、DDG 分析已完成但并发调度已禁用

**当前状态**：编译期 `BehaviorDependencyAnalyzer`（Phase 3 Binding）仍为每个 `IbBehaviorExpr` 计算 `llm_deps` 字段（供未来接通使用），但 `dispatch_eligible` 一律置 `False`（`behavior_dependency_pass.py`）。运行时 `assignment.py` 检测到 `dispatch_eligible=False` 即走同步求值路径，`LLMScheduler.dispatch_eager()` 代码存在但不会被触发。所有 `@~ ... ~` 行为表达式按 AST 序串行执行。

**根源**：dispatch_eager 曾被半接通（`dispatch_eligible` 默认 `True`），但后台线程执行完整的 `execute_behavior_expression`（含 prompt 段求值），重入共享 `VMExecutor` 导致 `_current_stack`/`step_count`/`last_call_info`/`retry_hint` 数据竞争。已显式禁用并降级为专项重做。

**接通前置条件**：
1. 修 `BehaviorDependencyPass` 实现 spec §3.1 规则（插值依赖/Cell/llmexcept 强制 `False`）
2. 拆分 `execute_behavior_expression` 为"主线程预求值 prompt"+"后台仅 HTTP 调用"
3. `retry_hint` 线程安全（`last_call_info` 已去共享：call_info 绑定到 `LLMResult`，executor 仅保留主线程单写槽）
4. 补"插值 + 真实并发"合规测试

**未来演进思路**：具体规划见任务文档。

---

## 十六、`__prompt__` 协议家族：已知问题与待决策项

### 16.1 用户类 `__from_prompt__` 返回的实例字段访问风险

**现象**：当用户自定义类实现 `__from_prompt__`，在特定条件下返回实例的 `.field` 访问可能返回 `None` 而非实际赋值内容。

**当前状态**：`VTableParsingStrategy` 已加入 `is_instance_of_target` 类身份检查——当 `__from_prompt__` 返回目标类的正确实例时跳过 auto-boxing。但若类身份比对失败（如跨模块加载导致类对象不同一），仍可能触发二次封装覆写字段。

**待决策**：
- 是否应该在 `__from_prompt__` 返回的对象类型已匹配目标类时，完全跳过 auto-boxing？
- 是否需要强制要求 `__from_prompt__` 返回的第二元素必须是目标类的实例？

### 16.2 `__validate_prompt__` 协议的执行时机语义

**问题**：当 `__validate_prompt__` 在 `VTableParsingStrategy` 中执行时，它仅覆盖了通过用户类 vtable 路径解析的类型。对于 axiom 内置类型（`int`/`float`/`bool`/`str`/`list`/`dict`/`enum`），pre-flight 校验走的是 axiom 自身的 `from_prompt` 内部逻辑，不经过 `__validate_prompt__`。

**待决策**：
- 是否应该为内置类型也提供 `__validate_prompt__` 扩展点？
- 当前设计是否足够——内置类型的 `from_prompt` 已含校验逻辑（返回 `(False, hint)` 时即触发 retry）？

### 16.3 `__to_prompt__` 的异常处理（已加可观测性）

**现状**：`LLMExecutorImpl._obj_to_prompt_str()` 统一了 prompt 序列化路径，内部 `try/except` 在 `__to_prompt__()` 抛异常时回退到 `str(val)` / `str(val.to_native())`。降级行为保留（LLM 调用不因 prompt 序列化失败而中断）。

原先的静默吞异常已改为 `core_debugger.trace(CoreModule.LLM, DebugLevel.DETAIL, ...)` 日志——用户实现的 `__to_prompt__` 若抛异常（如字段未初始化的 AttributeError），开启调试（默认 NONE 级，零开销）即可观测，不再完全无感知。同样的处理已应用到 `__payload_prompt__` / `to_native` 回退链。

### 16.4 协议签名校验（SEM_PROTOCOL_SIGNATURE）的强度选择

**问题**：当前 `SEM_PROTOCOL_SIGNATURE` 是 warning 而非 error——用户可以声明签名不匹配协议约定的 `__from_prompt__`（如 0 个参数），编译仍通过。运行时如果 axiom 路径命中就不会调用 vtable，但如果确实调用到 vtable 则会在运行时失败。

**待决策**：
- 是否应该将 SEM_PROTOCOL_SIGNATURE 从 warning 提升为 error（阻止编译）？
- 或保持 warning——鉴于协议方法签名本身属于 `_OVERRIDE_SIGNATURE_FREE`（允许自由修改签名以适配不同场景）？

---

## 十七、MOCK 模式下无法验证的 LLM 功能

以下功能需要连接真实 LLM API 才能完整验证，MOCK/TESTONLY 模式无法覆盖：

1. `__to_prompt__` 协议对真实 LLM 提示词的实际影响
2. `__from_prompt__` 解析真实 LLM 非结构化输出
3. `__outputhint_prompt__` 对真实 LLM 输出格式的约束效果
4. `__payload_prompt__` 多模态协议（图片/音频/视频提交给 LLM）
5. 意图系统（`@`/`@+`/`@!`）对真实 LLM 行为的影响
6. `llmexcept` retry hint 注入到真实 LLM 系统提示词的效果
7. `__llmretry__` 块定义的 retry hint 在 LLM 函数重试时的注入效果
8. 命名模型路由（`@NAME~`）连接真实 LLM provider
9. `ai.probe_model()` / `ai.has_api_key()` 探测真实 API
10. `ai.set_timeout()` 超时行为
11. 行为描述语句（`@~...~`）的真实推理能力
12. LLM 函数（`llm...llmend`）的真实提示词组装与变量替换效果
13. `__snapshot__`/`__restore__` 协议在真实 LLM 重试中的状态恢复

---

## 十八、Optional[T] 运行时方法分发缺失

**限制说明**

`Optional[T]` 的方法（如 `.or_else()`）在编译期已通过类型契约检查（编译能通过），但运行时方法分发未接通，实际调用会在运行时失败。

```ibci
Optional[int] x = None
int y = x.or_else(0)  # 编译通过，运行时失败
```

**根源**

内置 `Optional[T]` 走 axiom 的 `resolve_specialization_by_names` 路径，编译期类型签名已就位；但运行时 axiom 未实现 Optional 专属的方法分发（`or_else`/`is_none`/`unwrap` 等），调用会退化为普通对象属性查找并失败。

**当前建议**：暂不在生产代码中使用 `Optional[T]` 的方法链；用 `if`/`else` 显式判空替代。

---

## 十九、设计排除的语法

以下语法被明确排除出 IBCI 语言设计，不是 bug，不会支持：

### 19.1 walrus 运算符（`:=`）

IBCI 不支持 walrus 运算符（`:=`），也不支持 lambda 体内赋值。这是设计决策，非实现遗漏。

### 19.2 if-block 内重声明同名变量

`SEM_REDEFINITION` 禁止在 if-block 内重声明与外层同名的变量：

```ibci
int x = 10
if cond:
    int x = 20  # SEM_REDEFINITION：禁止重声明
```

这是设计决策（与 Python 不同），目的是避免作用域歧义。

---

## 二十、禁止循环导入

**限制说明**

模块间的 `import` 依赖图必须为有向无环图（DAG）。循环导入（A 导入 B，B 导入 A）会触发致命编译错误 `DEP_CIRCULAR_IMPORT`。

```ibci
# a.ibci
import b

# b.ibci
import a   # DEP_CIRCULAR_IMPORT: 循环依赖
```

**根源**

IBCI 编译器按拓扑序编译模块（依赖先编译）。循环依赖使得拓扑排序不存在，后编译方无法获得先编译方的完整类型信息。IBC-Inter 不是通用系统编程语言，LLM 调用开销决定了工程规模有限，模块间循环依赖无实际必要。此设计与 Rust（禁止循环 crate）、Go（禁止循环 package）一致。

**规避方式**

将共享类型/接口提取到独立的底层模块，使依赖关系保持单向。

---

## 二十一、插件可见性隔离与无状态约定

**限制说明**

IBC-Inter 的多 Interpreter 隔离（动态宿主）在**插件层**采用**可见性隔离**，而非 Python 代码/内存层的强隔离：

- 每个 Engine 拥有独立的 `HostInterface` / `InterOp` 注册表；IBCI 脚本只能 `import` 到**本引擎注册表**中登记的插件。引擎 A 的 IBCI 代码无法看到引擎 B 的插件--可见性是每引擎隔离的。
- 插件的 **Python 实现代码**仍由 Python 的 `importlib` 按进程级常规机制加载：`sys.modules` 全局缓存、按模块名命中。同一进程内，**同名插件按"先加载者胜"作为身份唯一性**--后启动的引擎若发现同名插件，拿到的是进程已缓存的那个模块对象。
- 插件的**实例**是每引擎独立的：`create_implementation()` 每次调用产出新实例，并以 `_ibci_registry_id` 戳标记所属 registry，跨引擎误用实例会抛 `RegistryIsolationError`。

因此，**隔离的边界落在"IBCI 可见性与实例"层，不落在"Python 模块代码"层**。IBC-Inter 不插手 Python 的 import 机制（不装自定义 finder、不篡改 `sys.modules`），因为那既脆弱又是泄漏的抽象。

**无状态约定（期望遵守，IBC-Inter 无强制力）**

插件应尽可能保持**无状态**：所有可变数据应放在插件实例的字段里（每引擎独立），而非 Python 模块级全局变量。该约定服务于三个目标：

1. **行为隔离**：不同引擎调用同一插件得到互不干扰的行为。
2. **数据不互相污染**：一个引擎对插件状态的修改不泄漏到另一引擎。
3. **可重入**：同一插件可被多个引擎并发/反复调用而不产生共享状态竞争。

IBC-Inter 对此**没有强制力**：插件若在 `.py` 文件顶层声明可变全局（如 `_cache = {}`），该状态会被同进程所有引擎共享，IBC-Inter 无法从原理上阻止（任何非进程级隔离方案都做不到）。这是插件作者的责任，不是 IBCI 的隔离缺陷。内置插件（`ai`/`ihost`/`idbg`/`isys` 等）均遵守此约定，使用实例级状态。

**根源**

可见性隔离是把隔离职责放在 IBCI 能完全控制的层（注册表 / `HostInterface`，new 一个实例即隔离），而非 Python 进程全局 import 状态（`sys.modules` 是 CPython 全局单例，IBC-Inter 无法 per-engine 实例化）。试图在 Python import 层做强隔离需要自定义 meta-path finder 或绕开 `import_module`，既触碰 Python 内部、又存在大量边界情况（namespace package、相对导入、循环导入等），不符合"质量优先、不写 tricky 实现"的原则。

**规避方式**

- 插件作者：把所有可变状态放进实例字段（`self.xxx`），通过 `create_implementation()` 工厂返回的实例持有；不要在模块顶层放可变全局。
- 跨 project_root 部署：若多个 project_root 在同一进程内运行且各自携带同名但内容不同的用户插件，**这是不支持的用法**（同名=同身份，先加载者胜）。若需加载不同代码，请使用不同的插件目录名。

---

## 二十二、llmexcept retry body 内禁止文件写/删（含固有边界）

**限制说明**

`llmexcept` 快照对磁盘型对象（`file_handle`/`audio`/`image`/`video`）保存的是**浅路径引用**（`__clone_ref__` 仅复制路径，不物化字节）。retry body 内任何文件写/删都会污染黄金快照：原地覆写改变 backing 内容、删除令 handle 悬空、即便是"创建新文件"的 `write_new`/`write_copy` 若路径撞上已有 backing 同样污染。

因此 retry body 内**禁止全部 7 个 `file` 模块写/删函数**：`write_copy` / `write_copy_bytes` / `write_new` / `write_new_bytes` / `write_overwrite` / `write_overwrite_bytes` / `remove`。只读操作（`open` / `read` / `read_bytes` / `exists`）允许。

防护为编译期 + 运行时双层（公理 IC-5）：
- **编译期** `SEM_LLMEXCEPT_FILE_WRITE`：spec 驱动判定，拦截 retry body 内直接调用与经用户函数递归传导的间接调用（含 `import file as f` 别名）。
- **运行时** `llmexcept_body_depth` 守卫：兜底编译期无法静态追踪的情形（如经 `fn` 动态分派）。

**固有边界（不可由 IBCI 拦截）**

外部进程（非 IBCI 代码，如子进程、其它引擎同进程直接写磁盘、OS 层变更）触碰 backing 文件，IBCI 在编译期与运行时均**无法拦截**。这是磁盘态快照零拷贝设计与进程外 I/O 不可控性的根本结果，任何非进程级隔离方案都做不到。磁盘型变量参与 `llmexcept` 时，用户须自行保证 backing 文件在 retry 期间不被外部修改。

**根源**

浅路径引用是为避免对大媒体（audio/image/video，可能 GB 级）在每次受 retry 保护的 LLM 调用上深拷贝字节而做的性能取舍。深拷贝能保证快照独立但代价不可接受；浅引用便宜但共享 backing 文件，故用"retry body 内禁写"作为补偿约束。外部进程不在 IBCI 管辖，是该取舍下无法消除的残余风险。

**规避方式**

- 文件 I/O 放在 `llmexcept` 块之外；retry body 内仅用 `retry "hint"` 提供修正指引。
- 若 retry 期间需记录诊断信息，使用 `print`（console，retry body 内允许）或待 retry 退出后再落盘。
- 磁盘型变量参与 retry 时，确保 backing 文件不被外部进程并发修改。

---

## 二十三、布尔上下文中的行为表达式定型为 `str` 的恒真陷阱

**限制说明**

行为表达式嵌套在复合布尔表达式（如 `@~...~ and True`）中时，编译器将其定型为 `str` 而非 `bool`。此时 LLM 返回的 `"0"` / `"false"` / `"no"` 等字符串按 Python 非空字符串真值语义（`IbString.to_bool()` → `bool(self.value)`）判真，导致条件恒真——`while` 循环可能永不终止。

```ibci
# ⚠️ 危险：@~...~ 在 BoolOp 中定型为 str，"0" 被判定为真，while 永不退出
int count = 0
while @~ 判定是否完成，返回 1 或 0 ~ and True:
    count = count + 1
```

**根源**

类型推断在布尔上下文中未将行为表达式约束为 `bool`；字符串真值语义遵循 Python 规则（非空即真）。两者叠加使 `"0"` / `"false"` 字符串在布尔判定中恒真。此问题与 llmexcept 机制无关（不加 llmexcept 亦可复现），是独立于确定性控制流的类型/语义缺陷。

**当前建议**

- 条件判定使用直接形式 `while @~...~:` / `if @~...~:`——该上下文下编译器将行为表达式定型为 `bool`，`"0"` 会被解析为假值。
- 若需复合条件，先把行为表达式赋值给 `bool` 类型变量，再参与组合。

**独立调研**

类型推断层修复（布尔上下文中将行为表达式定型为 `bool`）已单独立项，见 `tasks_docs/PENDING_TASKS.md`（布尔上下文类型推断）。本条目不随 llmexcept 机制统一任务消解。
