# IBC-Inter 已知限制（语言级）

> 本文档记录 IBCI 当前版本中正式承认的语言设计限制与使用约束。面向需要了解 IBCI 语言边界的所有开发者和使用者。
>
> **条目结构**：每节标注**类型**——`设计排除`（语言级决定，不随版本演进改变）或
> `已知边界`（当前实现的限制，可能随演进改变）；正文按节内容说明**限制内容**（是什么）、
> **成因**（为什么存在）与**应对**（怎么办/含义），小节标题用词按内容而定，不强制统一。
>
> 语言设计决策与规划见 `docs/ARCHITECTURE.md`；测试基线以 `python -m pytest tests/` 实跑为准。
>
> **书写要求**：新增/修改条目必须按本文尾部「书写格式模板」书写，保持条目结构与格式一致。

---

## 一、可调用类实例（`__call__` 协议）

> **类型**：已知边界（当前实现的限制，可能随演进改变）。

**限制说明**

可调用类实例（即实现了 `__call__` 方法的用户自定义类的实例）基础调用可用（见 `docs/subsystems/03_callable_fn.md`）。`obj()` 调用经**帧内 CPS 驱动**（`_UserCallDrive`，与类构造 `CPSDrivable` 同构）——深递归 `__call__` Python 深度恒定，`__call__` 内含 Waitable（LLM 行为 / `await chan.recv()`）时由调度器协作挂起。`fn f = instance; f()` 与生成器 `__call__`（`for x in gc(n)`）同样支持。

```ibci
class MyCallable:
    func __call__(self, int n) -> int:
        if n <= 1:
            return 1
        return self(n - 1) + 1   # 深递归走 trampoline，不嵌套 Python 栈

MyCallable obj = MyCallable()
int v = obj(400)   # ✅ 400
```

**剩余边界**：`__call__` 方法经 `_UserCallDrive` 驱动时要求 receiver 是用户类实例且方法是 `IbUserFunction`；原生 `__call__` 与类构造（`IbClass.receive`）走各自既有路径，不受影响。

---

## 二、`Enum` 语法

> **类型**：设计排除（语言级决定，不随版本演进改变）。

`Enum` 提供基础支持，但存在以下使用约束。

### 2.1 声明方式

`Enum` 通过继承内置 `Enum` 类实现，成员字段必须显式声明类型（支持 `str` / `int` / `float` / `bool` 类型的枚举成员）：

```ibci
class Color(Enum):
    str RED   = "RED"
    str GREEN = "GREEN"
    str BLUE  = "BLUE"

class Code(Enum):
    int OK  = 200
    int ERR = 500
```

### 2.2 访问与比较

枚举成员通过类名访问（`Color.RED`），支持 `==` / `!=` 比较：

```ibci
Color c = Color.BLUE

# 访问（成员值为其声明的底层值，`(str)Color.RED` 输出 "RED"、`(str)Code.OK` 输出 "200"）
print((str)Color.RED)

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

### 2.3 迭代与数量

```ibci
# 迭代全部成员值（按声明顺序）
for v in Color:
    print((str)v)

# 成员数量
print((str)len(Color))
```

### 2.4 当前限制

- **成员值是底层值，非枚举实例**：`Color.RED` 直接返回其声明的底层值（`str`/`int`/`float`/`bool` 装箱值），
  不是 `Color` 类型的实例。因此**枚举自定义方法不可在成员值上调用**（`Color c = Color.RED; c.my_method()`
  分派到底层类型的方法表）。若需实例化枚举（成员携带 `name`/`value` 与方法），属独立设计方向，当前不支持。
- **LLM 集成**：`Enum` 类型具备 `has_output_hint_cap` / `has_from_prompt_cap` 能力，LLM 输出枚举**成员名**
  后自动映射回**成员值**（非 str 成员亦正确）。
  常量字面量成员（含负数字面量 `int NEG = -1`）可正确映射；**非字面量表达式成员**
  （如 `int CALM = some_var`）在 LLM 解析路径回退"名==值"（LLM 输出成员名时解析为成员名字符串），
  而成员访问返回其求值后的 `static_val`——两者可能不一致，属编译期元数据无法求值表达式的边界。

---

## 三、`Uncertain` 内部哨兵值（用户不可见）

> **类型**：设计排除（语言级决定，不随版本演进改变）。

`Uncertain`（`IbLLMUncertain`）是 IBCI 内核的**内部机制**，不是用户可编程接口。

**设计语义**：
- `llmexcept` 保护帧内，LLM 调用无法产生确定结果时，VM 在重试循环期间会将目标变量
  临时赋值为 `Uncertain` 哨兵。这是 VM 快照/重试通信令牌，在下一次 `restore_snapshot + retry`
  后会被真实值替换。
- `llmexcept` 块外：uncertain 状态不会出现——infra 失败（网络/鉴权）→ `LLMCallError`；
  内容解析失败 → `LLMParseError`；重试耗尽 → `LLMRetryExhaustedError`。

**用户代码无需处理 uncertain**：
- `llmexcept` 块内处于重试循环，用户只需书写 `retry "hint"` 语句，无需显式检测 Uncertain。
- `is_uncertain()` 不是用户 API。`Uncertain` 字面量也不应出现在正常业务代码中。

---

## 四、行为表达式不可直接用于 `return` 语句

> **类型**：设计排除（语言级决定，不随版本演进改变）。

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

### 4.1 行为输出类型必须可被 LLM 解析

**限制说明**

行为输出的具体目标类型必须有解析能力：内建类型的 `from_prompt`/`parser` 公理能力，或用户类的 `__from_prompt__` 方法（含继承）。否则 LLM 字符串输出无法解析回该类型，运行期只能静默 box 成字符串——错误类型流入后续代码。

编译器对以下声明形态报 `SEM_BEHAVIOR_OUTPUT_NOT_PARSEABLE`：

- `fn f = lambda -> T: @~ ... ~`
- `T x = @~ ... ~`
- `obj.field = @~ ... ~` / `obj[i] = @~ ... ~`

**修复方式**：给类型补 `__from_prompt__`，或改用 `-> str` / `-> auto` / `-> any`（仅需原始字符串时）。`auto`/`any`/无类型声明不设输出契约，仍按字符串 box，不受限制。

---

## 五、引用语义与值语义契约

> **类型**：已知边界（当前实现的限制，可能随演进改变）。
>
> 共享引用模型的**权威契约**见 `docs/syntax/02_variables.md` §2.8（值语义：引用、拷贝、赋值与传递）；
> 本节只记录该模型下需要知晓的**边界**，不重复契约正文。

### 5.1 拷贝的不可克隆边界

`copy` / `deepcopy` 对不可克隆值（函数 / 行为 / 原生封装）回退原引用（值语义等价）——"拷贝"不产生副本，仍共享同一对象：

```ibci
fn f = add
fn g = deepcopy(f)   # 函数不可克隆，g 仍引用同一个 add
```

可克隆容器与用户对象字段按拷贝契约独立（`copy` 浅拷贝容器新建+元素共享；`deepcopy` 递归独立副本）。

### 5.2 类字段默认值每实例深克隆

类字段默认值（含可变容器）在每个实例构造时**递归深克隆**（`try_deep_clone`），实例间互不影响——无需在构造函数中手动初始化默认容器：

```ibci
class Stack:
    list[int] items = []   # 每实例独立深克隆，实例间不共享

Stack a = Stack()
Stack b = Stack()
a.items.append(1)
print((str)b.items.len())  # 0 —— b 不受 a 影响
```

**边界**：不可克隆的默认值（函数 / 行为等）回退共享引用（值语义等价）。

### 5.3 `fn` 变量的可调用引用语义

```ibci
fn f = add          # f 持有 add 函数的引用
fn g = f            # g 也引用同一个函数
```

函数本身是不可变的，因此 `fn` 变量的引用语义不会导致副作用问题。

---

## 六、子类 auto-init 合并继承链无默认值字段

> **类型**：已知边界（当前实现的限制，可能随演进改变）。

当子类没有显式 `__init__`，自动获得一个位置参数构造器（auto-init），**参数 = 继承链上全部无默认值字段（父类优先、子类同名覆盖）**；构造器参数声明在水化期生成（成员表单一权威），执行经共享实现（无运行时闭包）。

```ibci
class Animal:
    str name

class Dog(Animal):
    str breed

Dog d = Dog("Husky", "Lab")    # name="Husky"; breed="Lab"
```

**自定义构造（副作用/变换）**：显式定义 `__init__` 并通过 `super().__init__(...)` 初始化父类字段（`super()` 用法见 `docs/syntax/06_oop.md` §6.5）。显式 `__init__` 优先于自动构造器：

```ibci
class Dog(Animal):
    str breed
    func __init__(self, str n, str b) -> auto:
        super().__init__(n)
        self.breed = b
```

> 注意：auto-init 只绑定字段值，不调用祖先的显式 `__init__`（其副作用不会执行）。需要祖先自定义构造逻辑时须显式 `__init__` + `super`。

---

## 七、`auto` / `fn` / `any` / 裸赋值 对比

> **类型**：设计排除（语言级决定，不随版本演进改变）。

| 关键字 | 用途 | 类型推导时机 | 后续赋值限制 |
|--------|------|------------|------------|
| `auto x = expr` | 通用类型推导，锁定为首次赋值的实际类型 | 编译期 | 只能赋相同类型 |
| `fn f = add` | 可调用类型推导，RHS 必须是可调用的；`fn` 参数/返回处＝"任意可调用"（强制） | 编译期 | 保持可调用约束 |
| `any x = expr` | 真正的动态类型，不锁定（**唯一**的动态逃生阀） | 运行时 | 任意类型 |
| `x = expr`（裸赋值）| **等同 `auto`**：从首次赋值推断并锁定 | 编译期 | 只能赋相同类型 |

> **`callable` 是内部类型名**：`callable` 不作为用户可写类型
> 注解（`callable f` / `-> callable` / `list[callable]` 报 `SEM_UNRESOLVED_TYPE`，引导用
> `fn`）。它是**运行期函数对象基类名**（`type(make)`="callable"）+ 公理族根（fn_callable/
> behavior/bound_method 的父公理），属内部细节。用户面表达"可调用"统一用 `fn`（声明推断 /
> 抽象槽强制可调用 / `fn[(...)]` 签名约束）。`thread(callable=fn, args=[...])` 的
> `callable` 是内置函数参数名，非类型。
>
> **`fn` 参数/返回强制可调用**：`func apply(fn cb)` 的实参与 `-> fn` 的
> 返回表达式必须是可调用（`apply(42)`、`-> fn: return 42` 编译期 `SEM_TYPE_MISMATCH`）；
> 动态实参/返回（`any`/`auto`）静态不可判，放行交运行期裁决。`fn` 接受裸函数/lambda/
> 绑定方法/可调用类实例。

> **裸赋值语义**：无类型标注的裸赋值（`x = expr`）采用 `auto` 语义——编译期从首次赋值推断实际类型并锁定，不隐式退化为动态 `any`（那会击穿静态类型设计）。异类型重赋产生 `SEM_TYPE_MISMATCH`。需要真正的动态语义时，**必须显式声明 `any`**。
>
> **any 逃生后的重处理机制**：`any` 值用于有类型检查的上下文（如赋给 `int y`）时，
> **编译期放行，运行时强制类型校验**——值类型不匹配即抛 `RUN_TYPE_MISMATCH`。这与
> TypeScript `any` / Dart `dynamic` 的渐进类型模型一致：`any` 是逃生阀，运行时复查是
> 逃生阀的"明确重处理机制"，而非编译期禁止。**仅当值本身携带 any 类装箱标记时**才触发
> 运行时拦截（`any` 类对象流入用户类变量）；普通 `any` 值（真实类型实例经 `any` 变量
> 传递）不校验，静默流入目标类型。需要时用强制类型转换（`(int)x`）取得目标类型使检查
> 通过：
> ```ibci
> any x = 42
> int y = x          # 编译通过；运行时值类型匹配（42 是 int）→ 成功
> int z = (int)x     # 显式强转，语义等价
> ```

---

## 八、容器多类型声明

> **类型**：设计排除（语言级决定，不随版本演进改变）。

**`list[int, str]` 多类型 list 不支持**——无 union 类型机制，多元素 list
的"元素读取返回 any"实为隐式异构，击穿元素类型设计。异构容器必须**显式声明 `list[any]`**，
否则产生 `SEM_MULTI_TYPE_LIST_REMOVED` 编译错误。`tuple[T1, T2, ...]` 位置元素类型
（定长异构元组）是合法特性，不受影响。

`list[any]` 显式异构的读取规则（元素读取返回 `any`）：

- **元素读取**（下标访问 / for 迭代）返回 `any` 类型。若需明确类型，必须显式转换：
  ```ibci
  list[any] mixed = [1, "hello"]
  any val = mixed[0]
  int n = (int)val      # 必须先取到 any，再强制转换
  ```
- **`auto` 承载容器元素取值**：`auto x = mixed[0]` 编译通过，`x` 锁定为该元素的
  **具体类型**（`list[any]` 元素读取类型为 `any`，此时锁定为 `any`——`auto` 语义
  从首次赋值推断并锁定）。若需后续重新赋值不同类型，用 `any` 中转：
  ```ibci
  auto x = mixed[0]    # 锁定为该元素的实际类型
  any x2 = mixed[0]    # 保持动态，可重新赋值
  int n = (int)x2      # 再强制转换到目标类型
  ```

---

## 九、废弃语法（产生硬编译错误）

> **类型**：设计排除（语言级决定，不随版本演进改变）。

### `(Type) @~...~` 强制类型转换语法（PAR_DEPRECATED_CAST_SYNTAX）

```ibci
# ❌ 废弃，产生 PAR_DEPRECATED_CAST_SYNTAX 编译错误
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

# ✅ 正确写法：返回类型标注写在表达式侧且必须声明
fn f = lambda -> int: EXPR                   # 无参，显式返回类型
fn f = lambda -> auto: EXPR                  # 无参，-> auto 从 body 推断
fn f = lambda(int x) -> int: EXPR           # 有参，显式返回类型
fn f = lambda(int x) -> auto: EXPR          # 有参，-> auto 推断
fn f = snapshot -> int: EXPR                # snapshot，显式返回类型
fn f = snapshot(int a, int b) -> str: EXPR  # snapshot 有参
```

> **返回标注强制**：`fn f = lambda: EXPR` 等省略返回标注形式产生
> `SEM_MISSING_RETURN_ANNOTATION` 编译错误（不静默回填 any），必须显式 `-> TYPE` 或
> `-> auto`。声明侧返回类型 `TYPE fn NAME = lambda: EXPR` 形式仍废弃（PAR_INVALID_SYNTAX）。

---

## 十、泛型与容器类型限制

> **类型**：已知边界（当前实现的限制，可能随演进改变）。

### 10.1 `dict` 键类型在下标访问时不校验

`dict[str, int]` 的键类型在运行时下标访问时不校验。键类型安全由用户自行保证，编译器/运行时不提供保护。

### 10.2 跨模块同名类身份（统一类身份模型）

多模块编译时两个模块定义**同名类**（`geo.Box` / `graph.Box`）：*每一个用户类
（含入口模块类）的身份 = `(module_path, name)`*，module_path = 其定义模块名。
编译期 `geo.Box`/`graph.Box`/`main.Box` 独立 spec；运行期 `KernelRegistry._classes`
（单类表，Bootstrapper 委托）注册键 = `spec.qualified_name`，
`get_class(name, module)` module 感知查找，方法表不串扰（`geo.Box[int](5).get()` =
105 / `graph.Box[str]("hi").get()` = "hi!"）。`get_class` 裸名回落仅命中内置/内核类
（module_path=None），不再命中任何用户类（确定性合法回退）。内置类键 = 裸名，
行为不变。run_string 入口模块名锚定为 `__string_exec__`（稳定可复现）。

**已知边界**：
- LLM 输出解析到跨模块用户类（`__from_prompt__`/`__outputhint_prompt__`）：**parse 链与输出约束注入均 module 感知**（type_name 为 qualified 名，`_get_expected_type_hint` 优先 node_to_type spec；`returns` IbName 裸名按当前模块上下文解析；`_get_llmoutput_hint` 的 axiom/vtable 查找同模块解析）。**qualified 注解路径已验证可用**（`geo.Counter c = @~...~` 跨模块类型注解解析；枚举输出约束注入经 module 感知修复）。
- 跨引擎 round-trip 的**未编译目标引擎**用户类特化重建受注册表封印限制（`create_subclass` sealed 后禁用）——用户类特化跨引擎**身份保真**须目标引擎已编译该类（内置泛型特化同构：加载期预创建；密封+异产物场景内置亦回落基类）。重建失败时值**优雅回落基类**（`geo.Box[int]`→`geo.Box`）：字段保留、基类方法可经 `receive` 分派，仅特化身份丢失（判别测试 `test_cross_engine_sealed_base_fallback`）；不生成 `ib_class=None` 坏对象。

### 10.3 容器字面量类型推断 + *expr 元素级校验

容器字面量推断带实参：`[1,2]` → `list[int]`、`{"k":1}` → `dict[str,int]`、`(1,2)` → `tuple[int,int]`；元素类型不一致/含动态/空 → 裸容器。`auto x = [1,2]` 推断 `list[int]`；显式裸声明（`list bare = [1,2]`）值层保持裸 `list`。`-> auto` 函数返回容器也带实参。

`*expr` 展开实参：特化容器（`list[int]`）展开时元素类型与目标形参做可赋值校验（`list[str] *-> f(int)` 编译期拦截）；裸容器/动态/数量不足由运行期裁决（静态数量未知是本质限制）。**仅保证 `*expr` 位于位置实参末尾时的目标形参偏移正确**（`f('x', *l)` 首元素对应第二形参）；中置/前导星（`f(10, *l, 30)`）的计数偏移为既有局限性。

### 10.4 `fn[(...) -> ...]` 签名内嵌套泛型实参

`fn[(list[int]) -> int]` / `fn[(Box[int]) -> int]` 等**签名内部**的嵌套泛型实参
结构化处理（CALLABLE_SIG 签名模型：构造经 `TypeRef.from_spec` 结构化、
`resolve_typeref` 重建保真、匹配统一为逐参数类型检查、`TypeRef.substitute` 可穿透
嵌套类型参数）。扁平构造（`TypeRef.of(p.name)`）无法穿透嵌套 `T`，且仅按参数数量
+返回类型检查会漏掉参数类型不符的签名——`fn[(Box[int]) -> int]` 收 `get2(str)->int`
（参数类型不符）、`Host[int]` 特化后 `fn[(Box[T]) -> int]` 收错误签名，均编译期拦截。

---

## 十一、Switch 语句使用约束

> **类型**：设计排除（语言级决定，不随版本演进改变）。

**限制说明**

`switch`/`case` 基本功能可用（值比较 / 字符串匹配 / Enum 匹配 / `default` 兜底 / 匹配后自动跳出均正常）。

**使用约束**

- **`case` 分支体必须换行书写**：`case 1: print("x")` 单行形式不支持（报 `PAR_EXPECTED_TOKEN`），须
  ```ibci
  case 1:
      print("x")
  ```
- **匹配后自动跳出 case**（无 C 语言 fall-through）：命中分支执行后自动跳过其余 `case`。因此 **case 内 `break` 是冗余但合法的**（消费为 no-op，不会报错）；`continue` 透传给外层循环（switch 本身不是循环）。

**建议**：分支逻辑清晰、值匹配确定时使用 `switch`；复杂模式匹配（类型/结构匹配）仍用 `if`/`elif`/`else`。

---

## 十二、`intent_context` 类静态调用的"静默无效"陷阱

> **类型**：设计排除（语言级决定，不随版本演进改变）。

**限制说明**

`intent_context.push("X")` / `intent_context.pop()` / `intent_context.fork()` / `intent_context.merge()` / `intent_context.combine()` / `intent_context.clear()` 在"未持有具体 `intent_context` 实例"时直接当作类静态调用使用，**不会影响当前作用域生效的意图栈**——这些方法操作的是 receiver 实例字段 `_ctx`（见 `core/runtime/bootstrap/primitive_initializer.py` 中 `intent_context` 方法注册段）。当 receiver 是临时的"类对象"占位时，对该占位 `_ctx` 的修改无人引用，对外**完全无效**。

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

**作用域控制方法（在类上调用也生效）**：仅 `intent_context.clear_inherited()` / `intent_context.use(ctx)` / `intent_context.get_current()` 这三个方法被特别实现为"直接操作当前执行帧的 `_intent_ctx`"——它们对类静态调用和实例调用语义等价（见 `core/runtime/bootstrap/primitive_initializer.py` 中对应方法注册段的注释）。

**编译期防护（SEM_INTENT_STATIC_CALL）**：TypeCheckingPass 对 `intent_context.push(...)` / `pop()` / `fork()` / `merge(...)` / `combine(...)` / `clear()` 在类对象上的调用发出 SEM_INTENT_STATIC_CALL **编译期警告**（记录于编译器 issue tracker，可经 `compile` API / 诊断工具读取）。该警告是编译期诊断，**不在运行时输出打印**（`run` 成功路径不展示非致命编译警告）。`use()`/`get_current()`/`clear_inherited()` 不触发警告（这些在类上调用也生效）。

---

## 十三、`@` 意图注释的行为

> **类型**：设计排除（语言级决定，不随版本演进改变）。

`@`（smear）与 `@!`（override）是**语句级 one-shot**，行为由 VM 语句调度保证：

1. `@` / `@!` 绑定到紧随其后的**一条语句执行窗口**。该语句执行期间若触发 LLM 调用会
   消费它；若该语句路径没有任何 LLM 调用，窗口结束后也会被清理，不会泄漏到后续语句。
2. 连续两个 `@` / `@!`（one-shot）：**后者覆盖前者**，编译期不拦截。
3. 块末尾悬空的 one-shot（下一条语句不存在）：**静默丢弃**，编译期不拦截。
4. `@+` / `@-` 作为栈操作可独立存在并与 one-shot 组合。`@-` 支持无参弹栈、按内容移除、
   按标签移除（`@- #tag`）。
5. `SEM_INTENT_PLACEMENT` 仅对 `nonlocal`/`global` 关键字的误用位置发射，与 one-shot
   放置无关。
6. **`run_batch` 内的 one-shot**：`run_batch` 是单条语句但含多个 LLM 调用——当前实现
   为批内每个调用独立 fork 意图快照，语句级 `@` / `@!` 会注入批内**每一个**调用
   （不是只作用于首个调用）。约束批内部分调用需拆分语句或用 `@+` / `@-` 控制
   （文档：`docs/syntax/09_intent_system.md`）。

**根源**：意图注释设计为对"下一条语句执行窗口"的修饰；运行时在无 LLM 路径上保持无
泄漏的一致语义，但不做编译期放置约束（悬空/连续由语言语义自然处理）。

---

## 十四、用户类相关能力差距

> **类型**：已知边界（当前实现的限制，可能随演进改变）。

以下是面向"用户自定义类"的能力差距。这些差距并非 bug，而是设计未覆盖。

1. **用户类泛型参数**：`class Box[T]:` 全链路支持——语法（`[T]`）/ AST（`IbClassDef.type_params`）/ 语义（`TypeKind.TYPE_PARAM` 占位 + 特化 spec 构造）/ 序列化（`type_params` 落 artifact + rehydrate）/ 运行时（`Box[int]` 特化类 + `IbClass.__getitem__` 类型特化）。**支持**：多特化并存、字段/方法参数/返回类型特化（含嵌套实参 `Box[list[int]]` 的参数类型检查）、嵌套泛型（`list[Box[int]]`）、多类型参数（`Pair[K,V]`）、泛型继承（`class Sub[T](Box[T])`，父特化恒注册）。**边界**：① 泛型类必须特化使用（裸 `Box b` 注解或 `x = Box(1)` 实例化均报 `SEM_GENERIC_TYPE_NEEDS_ARGS`）；② 实参数须与声明一致（`SEM_GENERIC_TYPE_ARG_COUNT`）；③ 自动生成构造器合并继承链的无默认值字段（父类优先，见 §六）；④ 协议 bound 约束已支持（`class Box[T: SomeProtocol]`，特化时编译期检查实参满足协议；`func call[T: Proto](...)` 调用点推断）；⑤ `class Sub(Box[int])`（非泛型子类继承具体特化）fail-fast 报错；⑥ Enum 不支持类型参数；⑦ 类型参数名不得遮蔽内置类型（`class Box[int]` 报错）；⑧ 父引用嵌套实参（`class Sub[T](Box[list[T]])`）语法不支持（parser fail-fast）。
2. **运算符重载覆盖有限**：用户类可定义 dunder 方法并被运算符分派调用：**比较类** `==`(`__eq__`)/`!=`(`__ne__`)/`<`(`__lt__`)/`>`(`__gt__`)/`<=`(`__le__`)/`>=`(`__ge__`)、**算术类** `+`(`__add__`)/`-`(`__sub__`)/`*`(`__mul__`)/`/`(`__truediv__`)/`//`(`__floordiv__`)/`%`(`__mod__`)/`**`(`__pow__`)、**位运算类** `&`(`__and__`)/`|`(`__or__`)/`^`(`__xor__`)/`<<`(`__lshift__`)/`>>`(`__rshift__`)、**一元类** `-`(`__neg__`)/`+`(`__pos__`)/`~`(`__invert__`)/`not`(`__not__`)、**成员** `in`(`__contains__`) 均可覆写。**`is` 恒为身份比较，不可覆写**（与 Python 一致）。该机制经 `IbClass.receive` 的 vtable 分派实现；与内置 axiom 的能力级分派（Integer/Float/Str 的 `+`/`==`/`<`）是两套路径，未覆写的运算符在用户类上退化为身份比较（`==`）或运行时错误。

---

## 十五、DDG 并发调度的行为边界

> **类型**：已知边界（当前实现的限制，可能随演进改变）。

> 编译期依赖图（DDG）与运行期并发 dispatch 的完整机制见 `docs/architecture/04_vm_interpreter.md` §5。

**行为边界**：

- **循环体 / 函数体内行为不可 dispatch**：同一 `node_uid` 多次执行会覆写 `_pending_futures` 条目导致解析错乱与泄漏。此类行为走同步路径，不确定结果无 llmexcept 保护即在赋值点抛 `LLMParseError`。
- **call_info 时点**：`ai.get_current_call_info()` 返回"最近一次 resolve 的调用"（dispatch 在首次读取时写入），非赋值点。
- **流式调用不入观测**：`stream_call` / `stream_channel` 调用不产生 `call_info`——`ai.get_current_call_info()` 在流式调用后为空。观测 API 对流式路径的覆盖属待评估边界（是否扩展观测另行定案）。
- **未读取的 dispatched 变量**：在 `_pending_futures` 残留（无读则无 resolve），属已知泄漏面。
- **MOCK 验证能力**：内联 MOCK（`AIPlugin._handle_mock_response`）是进程内纯函数，零延迟控制、零基础设施失败注入，无法实测并发时序与 provider 异常传播路径。机制类验证（时序/失败/并发）须经 MOCK HTTP 服务（`MockServer`，`ibci_modules/ibci_ai/mock_service.py`）走真实 `OpenAI` 客户端路径；指令解析与场景状态由 `MockScenarioEngine` 统一实现（线程安全）。

---

## 十六、MOCK 模式下无法验证的 LLM 功能

> **类型**：设计排除（语言级决定，不随版本演进改变）。

以下功能需要连接真实 LLM API 才能完整验证，MOCK 模式无法覆盖：

1. `__to_prompt__` 协议对真实 LLM 提示词的实际影响
2. `__from_prompt__` 解析真实 LLM 非结构化输出
3. `__outputhint_prompt__` 对真实 LLM 输出格式的约束效果
4. `__payload_prompt__` 多模态协议（图片/音频/视频提交给 LLM）
5. 意图系统（`@`/`@+`/`@!`）对真实 LLM 行为的影响
6. `llmexcept` retry hint 注入到真实 LLM 系统提示词的效果
7. `__retry__` 协议（重试策略声明，规划中）与 llmexcept retry 注入真实 LLM 提示词的效果
8. 命名模型路由（`@NAME~`）连接真实 LLM provider
9. `ai.probe_model()` / `ai.has_api_key()` 探测真实 API
10. `ai.set_timeout()` 超时行为
11. 行为描述语句（`@~...~`）的真实推理能力
12. LLM 可调用类（`__llm_call__`）的真实提示词组装与变量绑定效果
13. `__snapshot__`/`__restore__` 协议在真实 LLM 重试中的状态恢复

---

## 十七、设计排除的语法

> **类型**：设计排除（语言级决定，不随版本演进改变）。

以下语法被明确排除出 IBCI 语言设计，不是 bug，不会支持：

### 17.1 walrus 运算符（`:=`）

IBCI 不支持 walrus 运算符（`:=`），也不支持 lambda 体内赋值。这是设计决策，非实现遗漏。

### 17.2 if-block 内重声明同名变量

`SEM_REDEFINITION` 禁止在 if-block 内重声明与外层同名的变量：

```ibci
int x = 10
if cond:
    int x = 20  # SEM_REDEFINITION：禁止重声明
```

这是设计决策（与 Python 不同），目的是避免作用域歧义。

---

## 十八、禁止循环导入

> **类型**：设计排除（语言级决定，不随版本演进改变）。

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

## 十九、模块可见性隔离与无状态约定

> **类型**：设计排除（语言级决定，不随版本演进改变）。

**限制说明**

IBC-Inter 的多 Interpreter 隔离（动态宿主）在**模块层**采用**可见性隔离**，而非 Python 代码/内存层的强隔离：

- 每个 Engine 拥有独立的 `HostInterface` / `InterOp` 注册表；IBCI 脚本只能 `import` 到**本引擎注册表**中登记的模块。引擎 A 的 IBCI 代码无法看到引擎 B 的模块--可见性是每引擎隔离的。
- 模块的 **Python 实现代码**仍由 Python 的 `importlib` 按进程级常规机制加载：`sys.modules` 全局缓存、按模块名命中。同一进程内，**同名模块按"先加载者胜"作为身份唯一性**--后启动的引擎拿到的是进程已缓存的那个模块对象。宿主绑定（`import python "..."`）同样经 `sys.modules` 加载，适用同一边界。
- 模块的**实例**是每引擎独立的：`create_implementation()` 每次调用产出新实例，绑定引擎 registry 身份（经 `BoundPlugin` 容器承载，跨引擎误用实例会抛 `RegistryIsolationError`）。

因此，**隔离的边界落在"IBCI 可见性与实例"层，不落在"Python 模块代码"层**。IBC-Inter 不插手 Python 的 import 机制（不装自定义 finder、不篡改 `sys.modules`），因为那既脆弱又是泄漏的抽象。

**无状态约定（期望遵守，IBC-Inter 无强制力）**

内置模块应尽可能保持**无状态**：所有可变数据应放在模块实例的字段里（每引擎独立），而非 Python 模块级全局变量。该约定服务于三个目标：

1. **行为隔离**：不同引擎调用同一模块得到互不干扰的行为。
2. **数据不互相污染**：一个引擎对模块状态的修改不泄漏到另一引擎。
3. **可重入**：同一模块可被多个引擎并发/反复调用而不产生共享状态竞争。

IBC-Inter 对此**没有强制力**：模块实现若在 `.py` 文件顶层声明可变全局（如 `_cache = {}`），该状态会被同进程所有引擎共享，IBC-Inter 无法从原理上阻止（任何非进程级隔离方案都做不到）。这是模块实现者的责任，不是 IBCI 的隔离缺陷。内置模块（`ai`/`ihost`/`idbg`/`isys` 等）均遵守此约定，使用实例级状态。宿主绑定的 Python 模块同理：其模块级全局在同进程内共享。

**根源**

可见性隔离是把隔离职责放在 IBCI 能完全控制的层（注册表 / `HostInterface`，new 一个实例即隔离），而非 Python 进程全局 import 状态（`sys.modules` 是 CPython 全局单例，IBC-Inter 无法 per-engine 实例化）。试图在 Python import 层做强隔离需要自定义 meta-path finder 或绕开 `import_module`，既触碰 Python 内部、又存在大量边界情况（namespace package、相对导入、循环导入等），不符合"质量优先、不写 tricky 实现"的原则。

**规避方式**

- 模块实现者：把所有可变状态放进实例字段（`self.xxx`），通过 `create_implementation()` 工厂返回的实例持有；不要在模块顶层放可变全局。
- 宿主绑定使用者：避免绑定依赖模块级可变全局的 Python 包；同一进程内同名 Python 模块只加载一次（`sys.modules` 缓存），多个引擎绑定同一模块时共享其模块级状态。

---

## 二十、llmexcept retry body 内禁止文件写/删（含固有边界）

> **类型**：设计排除（语言级决定，不随版本演进改变）。

**限制说明**

`llmexcept` 快照对磁盘型对象（`file_handle`/`audio`/`image`/`video`）保存的是**浅路径引用**（`__clone_ref__` 仅复制路径，不物化字节）。retry body 内任何文件写/删都会污染黄金快照：原地覆写改变 backing 内容、删除令 handle 悬空、即便是"创建新文件"模式（`overwrite_flag="new"`）若路径撞上已有 backing 同样污染。

因此 retry body 内**禁止全部 `fs` 模块写/删函数**：`fs.write` / `remove`。只读操作（`open` / `read` / `read_bytes` / `exists`）允许。

防护为编译期 + 运行时双层（公理 IC-5）：
- **编译期** `SEM_LLMEXCEPT_FILE_WRITE`：spec 驱动判定，拦截 retry body 内直接调用与经用户函数递归传导的间接调用（含 `import fs as f` 别名）。
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

## 二十一、布尔上下文中的行为表达式定型与字符串真值语义

> **类型**：设计排除（语言级决定，不随版本演进改变）。

**行为定型**

类型推断把**布尔位置**中的行为表达式定型为 `bool`——与直接条件（`while @~...~:` / `if @~...~:`）完全一致，并递归覆盖复合布尔位置：

- `@~...~ and True` / `@~...~ or ...` 的操作数
- 逻辑 `not @~...~` 的操作数
- 条件表达式 `x if @~...~ else y` 的 test
- `for ... if @~...~` 的 filter

因此 `while @~ 判定完成，返回 1 或 0 ~ and True:` 中行为被定型 `bool`，LLM 收到 0/1 输出约束、结果按 bool 解析，`"0"` 判假、循环正常终止。比较运算（`@~...~ == 42`）中的行为仍按另一操作数适配（`int`），不被强制为 bool——那是值比较语义。

**残余边界（有意保留，非妥协）**

若用户**显式**把行为表达式定型为 `str`（如 `str s = @~...~`）再用于布尔判定（`if s:`），`"0"` 按 Python 非空字符串真值语义判真。这是用户显式选择 str 类型后的 Python 语义，符合"显式优于隐式"——确定性代码语义不受 LLM 输出污染。需要布尔判定时，把行为表达式定型为 `bool`（或直接用布尔位置）即可。

**根源**

布尔上下文（条件测试）是行为表达式的类型上下文之一；若类型推断仅对**直接**作为条件的行为绑定 `bool`，不传播到复合布尔表达式内部，行为会落到 `behavior` 占位符、运行期装箱为 `str`。

---

## 二十二、通信原语面

> **类型**：设计排除（语言级决定，不随版本演进改变）。

**`signal` 不是关键字，语言面无此原语**：`signal` lex 为普通标识符。原因：零投递机制的通信抽象与 VM 控制流 `Signal` 撞名，且无消费者空壳。需要消息传递时使用 `chan`/`slot`/`subscriber`（见 `docs/syntax/14_concurrency.md`）。

**通信/线程原语**：`chan`/`slot`/`subscriber`/`thread`/`thread_result` 是语言一等公民（构造、方法、类型注解、序列化 round-trip）。线程创建统一使用 `thread[T]` 对象模型，不存在 `spawn`/`task` 形态。`thread_result[T]` 经 `expect()` 解封，失败 fail-fast。

**`chan(T, ...)` 特化实参降级（已知边界）**：`T` 实参传**裸类型类对象**（`chan(str, "stream")` → `chan[str]`）正常；传**特化类对象**（`chan(Box[int], "message")`）时特化实参被降级为裸类（`chan[Box]`）。普适写法是**类型在声明处、构造只传运行时参数**（`chan[E] ch = chan()`）——详细说明见 `docs/syntax/14_concurrency.md`。

---

## 二十三、递归深度受宿主栈限制（环境限制异常根因保留）

> **类型**：设计排除（语言级决定，不随版本演进改变）。

**函数调用经 trampoline（`UserFunctionCall`）使 VM 调用链不消耗 Python 递归栈**，深递归（数百层）可正常执行。但**作用域链符号解析**（`get_symbol_by_uid` 沿父作用域链向上查找）仍以 Python 递归实现，受 `sys.setrecursionlimit`（默认 1000）限制——深递归到约 980 层时触发宿主 `RecursionError`。

**行为**：此类 `RecursionError`（连同 `MemoryError`/`SystemError`）被判定为**环境限制异常**，在 VM 语义错误包装站点（`Symbol not defined` / `VM: Call failed` / 模块导入 / try-except）**原样重抛**，保留真实根因与调用栈，**不被包装成语义错误**。同时发射 `KDIAG_RUNTIME_ENV_LIMIT` 诊断事件（`core/runtime/shared/env_limits.py` 判定；`core/runtime/observability/diagnostics.py` `handle_environment_limit`）。

**含义**：超出宿主递归深度时，用户看到的是 `RecursionError: maximum recursion depth exceeded`（可提升 `sys.setrecursionlimit` 后重试），而非误导性的符号未定义/调用失败信息。递归深度上限本质是宿主栈限制，非语言可配置上限。

## 二十四、用户协议与 retroactive implementation 限制

> **类型**：设计排除（语言级决定，不随版本演进改变）。

**用户协议（`protocol` / `implements`）与 retroactive implementation（`impl`）已支持**（语法与示例见 `docs/syntax/06_oop.md` §6.8）。

- **协议**：声明 / 继承 / 泛型协议（`protocol Container[T]:`）/ 泛型 bound（§十四 #1 ④）/ 方法签名兼容校验（参数数量、参数类型可放宽、返回协变）。
- **`impl` 声明式**（空 body）：校验类型已满足协议并记录，类型必须已提供全部协议方法。
- **`impl` 方法补充**（带 body）：为既有类型补充缺失的协议方法（可读 `self` 与字段、子类经继承链可见、多 `impl` 块合并；`llm func` 方法是旧机制，已删除，方法恒普通 `func`）。
- **限制（fail-fast）**：① 目标须为**本模块用户类 / 宿主绑定类 / 内置具体值类型**（跨模块 dotted 目标不支持）；② **泛型类**目标不支持（方法体类型参数与特化成员替换未接线）；③ 内置目标中动态逃生类型（`any`/`auto`）、`void`、`module` 不支持；内置 `impl` 不得定义 `__init__`（内置构造走原生路径，永不分派 impl 构造器）；④ 方法名与目标既有成员（含内置类型的公理声明方法与公理运算符）同名报编译期错误（`SEM_REDEFINITION`）；仅运行期注册的内置原生方法（如 `__to_prompt__`/`__call__`，不进 spec.members/公理声明面）同名在水化期 fail-fast；⑤ 协议未覆盖全部必需方法、或方法签名不兼容，报编译期错误。
- **内置 `impl` 的作用域语义**：内置类型属内核根命名空间（无 module 限定），其 `impl` **引擎全局**生效——同一编译的全部模块共享（成员写入共享内置 spec，方法注册进引擎级运行期 vtable）。改写内置既有协议方法（覆层机制）是独立设计项，落地前同名一律按冲突拒绝。

---

## 二十五、LLM 可调用类返回类型解析边界

> **类型**：已知边界（当前实现的限制，可能随演进改变）。

**LLM 可调用类不声明 `expected_type` 时按字符串解析**——`expected_type` 缺失时输出无解析目标，返回原始字符串。需要纯副作用调用时使用行为表达式（`@~ ... ~`）。

**规避建议**：LLM 可调用类按需声明可解析的 `expected_type`（标量/容器/用户类——解析规则见 `docs/syntax/08_llm_callable.md` §8.5）；需要纯副作用调用时使用行为表达式（`@~ ... ~`）。

---

## 附、书写格式模板（本文档专用，书写必须参照）

> 本节是本文档条目书写的**唯一权威模板**（模板归属 = 文档自身）。新增/修改条目
> 必须按下列结构与格式书写，并同时遵守 `docs/WRITING_GUIDE.md` 通用书写准则。

### 1. 章节结构

```markdown
## N、标题（短名词短语，点明限制主题）

> **类型**：设计排除（语言级决定，不随版本演进改变）/
> 已知边界（当前实现的限制，可能随演进改变）

**<限制内容>**（是什么；必要处给最小可复现示例，用 ibci 代码块标注 ✅/❌ 期望结果）

**<成因>**（为什么存在：设计取舍 / 实现限制 / 宿主限制；标题可用
  限制说明 / 根源 / 行为 / 含义 等，按节内容而定）

**<应对>**（怎么办 / 含义；无规避时写明原因；标题按内容而定）

**剩余边界**（可选：未覆盖的细分边界清单，逐条一句话）
```

### 2. 书写规则

| 规则 | 说明 |
|------|------|
| 编号 | 中文数字连续编号（一、二、…）；新增条目排末尾取下一号，不重排既有编号 |
| 类型标注 | 每节必须标注：`设计排除`（语言级决定，不随版本演进改变）/ `已知边界`（当前实现的限制，可能随演进改变） |
| 事实基准 | 以当前代码实现为准；引用代码路径用仓库相对路径 |
| 示例 | 最小可复现示例；关键语句用 `# ✅` / `# ❌` 注释标注期望结果 |
| 引用 | 指向语法/架构文档用相对路径指针，不复制正文（单点真理） |
| 正文红线 | 不出现日期戳、任务编号（PT-xxx）、历史叙述、agent 元信息（见 `docs/WRITING_GUIDE.md` 红线） |
| 内部互引 | 引用本文档其它节用 `§N` 编号；引用具体条目用小节号（如 `§十四 #1 ④`） |
