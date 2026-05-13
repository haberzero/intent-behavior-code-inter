# IBC-Inter 已知限制（语言级）

> 本文档记录当前版本中**正式承认的语言设计限制**：偏向"用法约束 + 设计取向 + 根源说明"。
> 历史 Bug 修复记录已归档至 `docs/COMPLETED.md`。
> **最后更新**：2026-05-12（当前测试基线 1239 passed）

---

## ~~一、函数返回类型注释：不支持 `-> None`~~ ✅ **已实现（2026-05-10）**

`-> None` 返回类型注释现已受到完整支持。`None` 与 `void` 的语义区别：

- **`void`**：函数不产生任何值，调用结果不可赋值。
- **`None`**：函数显式返回 `None` 类型的值，可以被赋值给 `any` 类型的变量或 `Optional[T]` 参数。

```ibci
func greet(str name) -> None:
    print("Hello, " + name)        # ✅ 允许：隐式 None 返回

func maybe(bool flag) -> None:
    if flag:
        return None                # ✅ 显式 return None
    return                         # ✅ 裸 return 在 -> None 函数中合法（隐式 None）
```

> **实现说明**：`None` 是词法层面的保留关键字（`TokenType.NONE`），解析器类型标注组件（`TypeComponent.parse_type_annotation`）现已显式接受该关键字，并将其解析为名为 `"None"` 的类型名节点，与预置类型表中的 `NONE_SPEC` 对应。

---

## ~~二、`try` / `except` 中的 `as e` 类型窄化局限~~ ✅ **已修复（2026-05-06）**

`try` / `except` / `raise` / `finally` 异常机制**已可用**（包括内置异常层次 `Exception → LLMError → {LLMParseError, LLMRetryExhaustedError, LLMCallError}` 与用户自定义子类）。

**类型窄化现已支持**：`except X as e:` 绑定变量 `e` 的编译期类型现在正确窄化为 `X`（捕获类型），无需 `(X)e` 强转即可访问子类专属字段。

```ibci
class MyError(Exception):
    str detail
    func __init__(self, str msg, str detail):
        self.message = msg
        self.detail = detail

try:
    raise MyError("oops", "deep-context")
except MyError as e:
    print(e.message)        # ✅ 基类字段
    print(e.detail)         # ✅ 子类字段（类型窄化后可直接访问）
```

**元组异常** `except (A, B) as e:` 中 `e` 仍为 `Exception` 类型（安全回退），可通过 `(A)e` 或 `(B)e` 强转访问具体子类字段。

---

## 三、可调用类实例（`__call__` 协议）

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

## 四、`Enum` 语法

**支持状态**：当前版本已提供基础 `Enum` 支持，但存在以下使用约束需要注意。

### 4.1 声明方式

`Enum` 通过继承内置 `Enum` 类实现，成员字段必须显式声明类型（当前版本仅支持 `str` 类型的枚举成员）：

```ibci
class Color(Enum):
    str RED   = "RED"
    str GREEN = "GREEN"
    str BLUE  = "BLUE"
```

### 4.2 访问与比较

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

### 4.3 当前限制

- **仅支持 `str` 类型成员**：枚举成员的底层值目前只能声明为 `str` 类型。`int` 等其他类型成员在未来版本中支持。
- **不支持枚举迭代**：当前无法对枚举类的所有成员进行遍历（如 `for v in Color:`）。
- **不支持枚举数量/序数查询**：`len(Color)`、成员序号等功能暂不支持。
- **LLM 集成**：`Enum` 类型已具备 `has_output_hint_cap = True` 能力，LLM 函数可以直接输出枚举成员名称并自动解析为对应枚举值。

---

## 五、`Uncertain` 内部哨兵值（用户不可见）

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

处理 LLM 失败的正确方式见 §五（llmexcept）和 §4.6（异常体系）。

---

## 六、字符串比较运算符

**支持状态**：当前版本已支持字符串的 `<`、`<=`、`>`、`>=` 词法顺序比较。

```ibci
bool r1 = "apple" < "banana"    # True（词法顺序）
bool r2 = "zebra" > "alpha"     # True
bool r3 = "abc" <= "abc"        # True
bool r4 = "xyz" >= "abc"        # True
```

比较语义遵循 Unicode 码点顺序（等同于 Python `str` 的比较语义）。

---

## 七、行为表达式不可直接用于 `return` 语句

**限制说明**

行为表达式（`@~ ... ~`）的输出类型和提示词约束由左值类型驱动（即赋值目标的类型）。
在 `return` 语句中直接书写行为表达式时，由于无法从函数返回类型标注中以静态明确的方式推导出提示词约束，编译器**禁止**此写法，报 `SEM_003` 错误。

**行为**

```ibci
# ❌ SEM_003：不允许在 return 中直接使用行为表达式
func get_reply() -> str:
    return @~ 给我一句话 ~
```

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

## ~~八、`str + Uncertain` 拼接：过渡期允许~~ ✅ 已禁止（NS-4，2026-05-12）

历史过渡期允许的 `str + llm_uncertain` 隐式拼接已收紧：

- 编译期：`StrAxiom.resolve_operation_type_name("+", "llm_uncertain")` 不再返回 `"str"`，走常规 SEM_003 类型检查路径。
- 运行期：`IbString.__add__` 检测到右操作数为 `llm_uncertain` 哨兵时，抛 `ThrownException(LLMParseError)`，由 `try/except LLMParseError`（或更外层的 `LLMError`/`Exception`）接管。
- 用户若需观察 uncertain 值仍可使用显式转换 `(str)uncertain_var`（得到字符串 `"uncertain"`）。

详情参考 `docs/COMPLETED.md` 2026-05-12 NS-4 锚点。

---

## ~~九、链式下标 `(expr)[index]` 语法不支持~~ ✅ 已支持（NS-6，2026-05-12）

历史 `(nested[0])[1]` 形式被解析器误判为 `(Type)value` 形式的 cast，已修复：

- `expression.py:grouping()` 推测块内部的 `ParseControlFlowError` 改由 `with` 外侧的 `try/except` 接管，确保 speculate 失败时 `success=False`、temp_tracker 不被合并（这是历史 PAR_001 误报的根因）；
- 当类型节点本身是 `IbSubscript` 且 RPAREN 之后紧跟 `[` 时，立刻触发 PCFE 回退到分组表达式路径；
- 泛型 cast `(list[int])arr` 等非链式下标用法不受影响。

详情参考 `docs/COMPLETED.md` 2026-05-12 NS-6 锚点。

---

## 十、类字段不支持调用表达式作为默认值

类字段初始化表达式中，只有字面量常量（`int` / `str` / `bool` / `list[]` / `dict{}`）可靠工作。函数调用、构造器调用等动态表达式作为字段默认值均不可靠。

**规避方案**：始终通过 `__init__` 构造函数进行动态字段初始化。

---

## 十一、子类 auto-init 不含父类字段

**严重级别**：低（符合 Python 语义，但与 C++/Java 使用者直觉不符）

当子类没有显式 `__init__`，编译器会自动生成一个 `__init__`，**仅接受当前类自身声明的字段**，不包含父类字段。

```ibci
class Animal:
    str name

class Dog(Animal):
    str breed       # Dog 的 auto-init 只接受 breed，不接受 name

Dog d = Dog("Husky")    # 只设置 breed；d.name = None
```

**规避方案**：在子类中显式定义 `__init__` 手动初始化父类字段，或在构造后赋值。

**根源**：auto-init 生成逻辑（`interpreter.py:_hydrate_user_classes`）仅遍历当前类 `body` 中声明的字段。父类字段通过 `default_fields` 继承，但不加入构造函数参数。此设计与 Python 行为一致（子类不自动调用 `super().__init__`）。

---

## 十二、引用语义局限性

IBCI 对所有复合对象（`list` / `dict` / 用户类实例）使用**共享引用**语义——与 Python 一致。

### 12.1 赋值是引用复制

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

### 12.2 类实例字段的默认引用陷阱

若多个实例共享同一个"默认"列表字段，修改一个实例的字段会影响其他实例。**始终在构造函数中初始化列表 / 字典字段**：

```ibci
class Stack:
    list items
    func __init__(self):
        self.items = []  # 每个实例独立创建
```

### 12.3 `llmexcept` 快照不影响容器内容

`llmexcept` 的方案A 深克隆 + 方案B `__snapshot__` 协议目前只快照"标量变量绑定 / 用户对象字段"。若快照前的变量持有列表，LLM 调用体内对该列表的 `append`/`remove` 等**就地修改**在 `retry` 后不会被还原。

**规避方案**：不要在 `llmexcept` 保护块的 LLM 调用路径中就地修改容器；如需可回滚的容器状态，在 `llmexcept` 之前先做深复制（或为类实现 `__snapshot__` / `__restore__` 协议自行决定快照粒度）。

### 12.4 `fn` 变量的可调用引用语义

```ibci
fn f = add          # f 持有 add 函数的引用
fn g = f            # g 也引用同一个函数
```

函数本身是不可变的，因此 `fn` 变量的引用语义不会导致副作用问题。

---

## 十三、`auto` / `fn` / `any` 对比

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

## 十四、容器多类型声明

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

详细泛型容器限制与改进方向见本文件 §十六。

---

## 十五、已废弃语法（产生硬编译错误）

### `(Type) @~...~` 强制类型转换语法（PAR_010）

```ibci
# ❌ 已废弃，产生 PAR_010 编译错误
int sum = (int) @~ 请计算 $a 和 $b 之和 ~

# ✅ 正确写法：LHS 类型自动成为 LLM 输出格式约束
int sum = @~ 请计算 $a 和 $b 之和 ~
str mood = @~ 请判断颜色，回复颜色单词 ~
```

LHS 的变量声明类型会自动被传递给 LLM 作为输出格式提示，无需额外的类型转换语法。

### 旧 fn / lambda 声明语法（PAR_003 / D1/D2 废弃）

```ibci
# ❌ 全部产生 parse error
int lambda f = expr           # 旧声明语法（PAR_001）
auto snapshot g = expr        # 旧声明语法（PAR_001）
fn lambda h = expr            # 旧括号体形式（PAR_001）
lambda(EXPR)                  # 旧括号体形式（PAR_001）
lambda(PARAMS)(EXPR)          # 旧括号体形式（PAR_001）
int fn f = lambda: EXPR       # 声明侧返回类型（PAR_003，D1 废弃）
int fn f = snapshot(int a, int b): EXPR  # 声明侧返回类型（PAR_003，D1 废弃）

# ✅ 正确写法（D1/D2：返回类型标注写在表达式侧）
fn f = lambda: EXPR                          # 无参，返回类型推导
fn f = lambda -> int: EXPR                   # 无参，显式返回类型（D2）
fn f = lambda(int x): EXPR                  # 有参，返回类型推导
fn f = lambda(int x) -> int: EXPR           # 有参，显式返回类型（D2）
fn f = snapshot -> int: EXPR                # snapshot，显式返回类型（D2）
fn f = snapshot(int a, int b) -> str: EXPR  # snapshot 有参（D2）
```

`D1`（2026-04-29）废弃了声明侧返回类型 `TYPE fn NAME = lambda: EXPR` 形式（产生 PAR_003），
改为在表达式侧通过 `-> TYPE` 标注（`D2`）。


---

## 十六、泛型与容器类型限制

当前泛型实现仍有部分限制（G1/G2/G3 改进后已解决多项）。

### ~~16.1 下标访问的类型推断返回 `any`~~ ✅ 已解决（G1/G3）

`list[int]` 下标访问（`[]` 运算符）现在通过 `registry.resolve_subscript()` 正确返回元素类型 `int`，而非 `any`。`list[T].__getitem__` 方法成员亦通过 G3 改进返回 `T`（详见 `docs/COMPLETED.md`）。

### ~~16.2 泛型特化的 axiom 方法引导不完整~~ ✅ 已解决（G1/G2/G3）

`resolve_specialization()` 已在 G1 加入 early-cache hit 逻辑，G3 修复了嵌套泛型的 key 计算（使用 `spec.name` 而非 `get_base_name()`）。OI-4 已关闭，详见 `docs/OPEN_ISSUES.md`。

### ~~16.3 嵌套容器的链式下标类型推断缺失~~ ✅ 已解决（G3）

`list[list[int]][0]` 现在正确返回 `list[int]` 类型，`list[list[int]][0][0]` 正确返回 `int`。修复方案：`resolve_specialization` 使用 `arg.name` 而非 `arg.get_base_name()` 确保嵌套键 `"list[list[int]]"` 而非 `"list[list]"`。

### 16.4 `dict` 键类型在下标访问时不校验

`dict[str, int]` 的键类型在运行时下标访问时不校验。键类型安全由用户自行保证，编译器/运行时不提供保护。

### ~~16.5 `tuple` 无元素类型标注~~ ✅ 已解决（NS-7，2026-05-12）

`tuple` 现在支持 `tuple[T1, T2, ...]` 的位置元素类型标注：
- 字面量 int 下标访问时返回精确的位置类型（`tuple[int, str]` 的 `t[0]` 是 `int`，`t[1]` 是 `str`）；
- 变量索引或越界访问回退到 `any`，与 `dict` 的非校验路径对称；
- `tuple[A, B]` 仍可赋值给裸 `tuple`；不同位置组合 spec 互相不兼容；
- `tuple[T]` 单类型路径保留 `element_type` 单字段语义，向后兼容。

实现：`TypeDef.positional_element_types`（与 `LIST.allowed_element_types` 平行）、`SpecFactory.create_tuple(positional_element_type_names=...)`、`SemanticAnalyzer.visit_IbSubscript` 中识别字面量 int 索引并精确推断。`SpecRegistry.resolve_specialization` 的早缓存键不再 sort 多参数列表，保证 `tuple[int,str]` 与 `tuple[str,int]` 不再误共用同一缓存项。

### ~~16.6 泛型实例赋值兼容性规则不完整~~ ✅ 已解决（G3 / axiom covariance）

`list[int]` 与 `list` 的赋值兼容性通过 `ListAxiom.is_compatible("list")` 实现（`is_compatible` 返回 True）。`list[int] x; list y = x` 不再触发 SEM_003。详见 `tests/compiler/test_g3_generics.py::TestG3Covariance`。

---

## 十七、Switch 语句设计未稳定

**当前状态**：`switch`/`case` 语法的 AST 节点已实现（`core/kernel/ast.py:217 class IbSwitch`），但语义设计存在待改进问题。

**已知问题**：
- case 匹配语义不完整（值比较、类型匹配、模式匹配的边界不清晰）
- default 语句的兜底行为需要明确定义
- switch 内控制流（break/continue/return）与其他控制流的一致性待验证
- 与 if/elif/else 的语义差异与使用场景未充分区分

**当前建议**：暂不在生产代码中使用 `switch`/`case` 语句，优先使用 `if`/`elif`/`else` 实现条件分支逻辑。

**测试覆盖**：暂无契约测试（INV-SWITCH-*），待语义设计稳定后补充。详见 `docs/SEMANTIC_COVERAGE_MATRIX.md §10.3`。

---

*最后更新：2026-05-13（添加 Switch 语句设计未稳定说明）*
