# IBC-Inter 已知限制（语言级）

> 本文档记录当前版本中**正式承认的语言设计限制**：偏向"用法约束 + 设计取向 + 根源说明"，
> 不收录尚在跟进的临时 Bug。
>
> **与顶层 `BUG_REPORTS.md` 的分工**：
> | 文件 | 定位 | 内容风格 |
> |------|------|----------|
> | `BUG_REPORTS.md` | 短期问题登记簿；属于"未归档的现场记录" | 实测复现 + 临时规避 + 修复跟进 |
> | `docs/KNOWN_LIMITS.md`（本文件） | 正式语言限制说明 | 设计意图、根源描述、推荐写法 |
>
> **最后更新**：2026-04-27（明确与 `BUG_REPORTS.md` 的分工；为各条限制补充"根源"说明；移除已修复条目的 `del` 文档化；`fn` 强调后续改造计划；`@!` 单次性语义重申；690 个测试通过）

---

## 一、函数返回类型注释：不支持 `-> None`

**限制说明**

函数声明中的返回类型注释（`-> <type>`）目前**不支持** `None` 作为返回类型。

**根源**

`None` 是词法层面的保留关键字（`TokenType.NONE`），类型注释解析器（`TypeComponent.parse_type_annotation`）只接受标识符（IDENTIFIER）、`auto` 和 `fn` 三种形式，无法识别 `None` 关键字作为类型名。要支持 `-> None` 需在 type annotation 解析路径中显式接受 `NONE` token。

**行为**

```ibci
# ❌ 当前会引发解析错误 (PAR_001)
func my_func() -> None:
    print("hello")
```

**建议替代方案**

使用 `void` 作为"无返回值"的显式类型注释：

```ibci
# ✅ 正确用法 —— 显式声明无返回值
func my_func() -> void:
    print("hello")

# ✅ 也可以省略返回类型注释（省略时默认使用 auto，编译器自动推断）
func my_func():
    print("hello")
```

---

## 二、`try` / `except` 语法

**限制说明**

当前 `try` / `except` / `finally` 语法自身存在设计问题，**强烈不建议使用**，将在未来版本中完善。

**根源**

`try`/`except` 是早期为兼容传统语言习惯而保留的关键字，但 IBCI 的核心健壮性叙事是
"LLM 不确定性 → `llmexcept` 快照隔离"。`try`/`except` 自身的异常类型层级、`raise` 语义、
`finally` 资源释放路径在当前解释器实现中并未与 `LLMExceptFrame` / `IbLLMCallResult` 对齐——
词法 / 解析层接受 `try`/`except`/`raise`/`finally`，运行时按顺序执行各分支，但**不会真正捕获**
非语言级的运行时异常。后续会与"unification with `llmexcept`"或"完整 try/except 重构"一并落地。

```ibci
# ⚠️ 强烈不建议使用——存在设计问题，行为可能不符合预期
try:
    ...
except SomeException as e:
    ...
finally:
    ...
```

如需处理 LLM 不确定性结果，请优先使用专为此场景设计的 `llmexcept` 语法。

---

## 三、`fn` 变量与可调用类实例

**限制说明**

当前 `fn` 变量语法以及所有的可调用类实例（即实现了 `__call__` 方法的用户自定义类的实例）自身存在设计问题，**强烈不建议使用**。`fn` 相关语法将在后续版本中进行深入改造，现阶段保持"不建议使用"状态。

**根源**

`fn` 类型推断在跨场景调用、与 OOP `__call__` 协议解析、闭包捕获、与 `lambda`/`snapshot` 互通的若干路径上存在不一致——尤其是当 `fn` 持有的可调用对象内部又触发 `@~...~` 或意图栈相关副作用时，类型推断与运行时分发之间的错位可能产生静默错误。彻底修复需要等待 `fn` 语义的整体重设计。

```ibci
# ⚠️ 强烈不建议使用——存在设计问题，行为可能不符合预期
fn f = some_function

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
- **LLM 集成**：`Enum` 类型已具备 `IlmoutputHintCapability`，LLM 函数可以直接输出枚举成员名称并自动解析为对应枚举值。

---

## 五、`Uncertain` 字面量与 `is_uncertain()` 函数

### 5.1 `Uncertain` 字面量

`Uncertain` 是全局可见的特殊字面量（与 `None` 保持命名一致），表示 LLM 调用因重试耗尽而无法得到确定结果时产生的特殊值。

```ibci
# Uncertain 字面量用法
auto x = Uncertain

# 布尔上下文中为假
if x:
    print("不会执行")
else:
    print("Uncertain 是假值")

# 强制转换为字符串得到 "uncertain"
print((str)x)    # 输出: uncertain
```

### 5.2 `is_uncertain(r)` 内置函数

提供专用内置函数 `is_uncertain(r)` 用于检测一个值是否为 `Uncertain`：

```ibci
auto result = Uncertain
if is_uncertain(result):
    print("结果不确定")

# 与 None 的区别
auto n = None
print(is_uncertain(n))       # False —— None 不是 Uncertain
print(is_uncertain(Uncertain)) # True
```

### 5.3 与 `None` 的区别

| 特性 | `None` | `Uncertain` |
|------|--------|-------------|
| 语义 | 空值/无值 | LLM 调用结果不确定 |
| 布尔值 | 假 | 假 |
| `(str)` 强转 | `"None"` | `"uncertain"` |
| 检测函数 | 无专用函数（用 `== None` 比较） | `is_uncertain(r)` |
| 来源 | 手动赋值或函数无返回 | LLM 调用重试耗尽后自动赋值 |

### 5.4 暂不支持的用法

当前版本**不提供** `r.is_uncertain()` 实例方法形式，请统一使用全局函数 `is_uncertain(r)`。

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

## 八、`str + Uncertain` 拼接：过渡期允许，未来将禁止

**当前行为（过渡期）**

`str` 类型变量在运行时持有 `Uncertain`（例如 `llmretry` 重试耗尽后）时，与字符串的 `+` 拼接被允许，且 `Uncertain` 被视作字符串 `"uncertain"` 参与拼接。这是为了避免 `print("结果: " + r)` 这类常见调试模式在 LLM 失败后立刻 RUNTIME_ERROR 的"安静崩溃"路径。

```ibci
# ✅ 当前过渡期允许
str r = @~ MOCK:FAIL ~ llmretry "..."
print("结果: " + r)    # 输出："结果: uncertain"
```

**未来计划**

后续解释器架构升级（引入更完善的 except / 不确定性异常机制）后，本行为将被禁止：`str + Uncertain`
将不再隐式 coerce，相关错误路径将由统一的 `try/except`（或与之等价的不确定性异常处理器）接管。
届时 `Uncertain` 必须由 `is_uncertain(r)` 显式判断后再处理。

**根源**

`IbString.__add__` 与 `StrAxiom.resolve_operation_type_name` 当前对 `llm_uncertain` 操作数做了
显式放行（参见 `core/runtime/objects/builtins.py` / `core/kernel/axioms/primitives.py` 中的 TODO 注释）。
