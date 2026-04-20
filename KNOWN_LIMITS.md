# IBCI 已知限制与缺陷记录

> 本文件记录通过系统性实测（MOCK 模式 + idbg + print 探查）发现的已知 Bug 与设计限制。  
> 每个条目包含：复现代码、实际行为、预期行为、根因分析、建议修复方向。  
> **最后更新**：2026-04-20（初次建立，来自全面实测分析）

---

## Bug #1：类字段列表 / 字典字面量默认值静默失效

**严重级别**：高（静默产生 `None`，无报错）

**复现**：
```ibci
class Stack:
    list items = []     # 默认值不生效
    dict meta = {}      # 默认值不生效

Stack s = Stack()
print((str)s.items)     # 输出 None，预期 []
```

**实际行为**：`list items = []` 和 `dict meta = {}` 字段在实例化后均为 `None`，而非空列表/字典。无任何编译期或运行时错误。

**正常工作的情况（标量常量默认值）**：
```ibci
class Config:
    int version = 1        # 正常：得到 1
    str name = "IBCI"      # 正常：得到 "IBCI"
    bool debug = false     # 正常：得到 False
```

**根因分析**：  
`IbDeferredField.static_val` 对列表 / 字典字面量（非常量表达式）无法在预评估阶段成功求值，动态求值路径在 `except` 块中静默回退到 `registry.get_none()`，未向用户抛出错误。

**临时规避方案**：
```ibci
class Stack:
    list items

    func __init__(self):
        self.items = []    # 在构造函数中显式初始化
```

**建议修复**：在 `IbDeferredField` 动态求值失败时抛出明确的编译期或运行时错误；或对类字段支持完整的表达式求值（在构造器调用时延迟求值）。

---

## Bug #2：`dict` 类型变量接收 `@~...~` LLM 输出失败（类型错误）

**严重级别**：高（核心用例，运行时崩溃）

**复现**：
```ibci
import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")

dict d = @~ MOCK:DICT:{"a":1} ~
# → RUN_002: Type mismatch: Cannot assign 'str' to 'dict[any,any]' for variable 'd'
```

**对比**（`list` 类型正常工作）：
```ibci
list l = @~ MOCK:LIST:[1,2,3] ~   # 正常运行
```

**根因分析**：  
`LLMExecutorImpl._parse_result()` 收到的 `type_name` 是 `"dict[any,any]"`（带泛型参数），而 `meta_reg.resolve("dict[any,any]")` 返回 `None`（SpecRegistry 中无此 key），导致 `DictAxiom.from_prompt` 从未被调用，JSON 字符串被直接装箱为 `IbString`，赋值到 `dict` 类型时类型校验失败。

`list` 类型不受影响，因为其 `type_name` 被解析为 `"list"`（不含泛型），可正常找到 `ListAxiom`。

**建议修复**：在 `_parse_result()` 中，若 `meta_reg.resolve(type_name)` 失败，尝试剥离泛型参数后重新解析基础类型名（`"dict[any,any]"` → `"dict"`）。

---

## Bug #3：Enum 类型从 LLM 输出解析失败（永远得到 None）

**严重级别**：高（Enum + LLM 是核心用例组合）

**复现**：
```ibci
import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")

class Direction(Enum):
    str NORTH = "NORTH"
    str SOUTH = "SOUTH"

Direction d = @~ MOCK:STR:SOUTH ~   # d 得到 None，不是 Direction.SOUTH
switch d:
    case Direction.SOUTH:
        print("south")           # 永远不执行
    default:
        print("none")            # 永远走这里
```

**实际行为**：变量 `d` 得到 `None`（或 `IbNone`），switch 进入 default 分支。无错误报出。

**根因分析（双重缺陷）**：  

1. **Axiom 查找失败**：`_parse_result` 调用 `meta_reg.get_from_prompt_cap(Direction_spec)`，内部用 `get_axiom("Direction")` 在 AxiomRegistry 中查找，但 AxiomRegistry 只有 `"enum"` key，没有 `"Direction"` key，导致 `from_prompt_cap = None`。（与 Bug #2 根因相似：用户自定义类型名找不到对应 Axiom。）

2. **兜底路径产生 `IbString` 后类型校验失败**：兜底路径 `registry.box(raw_res)` 将 `"SOUTH"` 包装为 `IbString`；当赋值到 `Direction` 类型变量时，类型校验失败，最终变量得到 `IbNone`。

**建议修复**：  
- 在 `EnumAxiom` 的 `is_compatible` 逻辑中，对用户自定义 Enum 子类，`get_axiom` 应通过 ClassSpec 继承链找到 `EnumAxiom`（如检查 `spec.parent_name == "enum"` 或 `spec.is_enum`）。
- `EnumAxiom.from_prompt` 找到匹配的成员名后，应返回实际的枚举 IbObject 实例（通过 `registry.get_enum_member(spec, val_str)`），而非裸字符串。

**临时规避方案**：
```ibci
# 使用 str 类型接收 LLM 输出，再用 if/else 手动映射
str mood_str = @~ MOCK:STR:HAPPY ~

if mood_str == "HAPPY":
    print("识别到 happy 情感")
else:
    if mood_str == "SAD":
        print("识别到 sad 情感")
    else:
        print("未知情感: " + mood_str)
```

---

## Bug #4：`none`（小写）关键字在运行时未定义（崩溃）

**严重级别**：中（编译期应拦截但未拦截）

**复现**：
```ibci
any val = @~ MOCK:FAIL test ~
bool is_none = val == none    # 编译通过，运行时崩溃
```

**错误信息**：
```
[ERROR][RUN_001]: Execution Error: Symbol with UID 'builtin:none' (name: 'none') is not defined in current context.
```

**根因**：词法器将 `None`（首字母大写）识别为 `TokenType.NONE`，但 `none`（全小写）被当作普通标识符处理，在运行时找不到对应变量而崩溃。

**建议修复**：语义分析器或词法器层面捕获 `none` 小写形式，输出明确的编译期错误提示（例如："请使用 `None` 而非 `none`"）。

**正确写法**：使用 `None`（首字母大写）。

---

## 已知限制 #5：链式下标 `(expr)[index]` 语法不支持

**严重级别**：低（可用临时变量规避）

**复现**：
```ibci
tuple nested = ((1, 2), (3, 4))
print((str)(nested[0])[1])   # PAR_001 编译错误
```

**错误信息**：`PAR_001: Expect type name.`

**根因**：解析器将 `(nested[0])` 中的括号识别为强制类型转换语法 `(TypeName)`，而非分组表达式，导致 `[1]` 无法正确解析。

**规避方案**：
```ibci
tuple inner = (tuple)nested[0]
print((str)inner[1])    # 正常工作
```

---

## 已知限制 #6：`dict` 类型接收 LLM 输出（等待 Bug #2 修复）

由于 Bug #2，以下模式当前无法工作：

```ibci
dict result = @~ MOCK:DICT:{"key":"value"} ~   # 类型错误
```

临时方案：以 `str` 类型接收，再通过 `json.parse()` 转换：
```ibci
import json
str raw = @~ MOCK:DICT:{"key":"value"} ~
dict result = json.parse(raw)
```

---

## 已知限制 #7：类字段不支持调用表达式作为默认值

与 Bug #1 相关：类字段初始化表达式中，只有字面量常量（`int`/`str`/`bool`）可靠工作。函数调用、构造器调用等动态表达式作为字段默认值均不可靠。

**规避方案**：始终通过 `__init__` 构造函数进行动态字段初始化。

---

## 已废弃语法（产生编译硬错误）

### `(Type) @~...~` 强制类型转换语法（PAR_010）

```ibci
# ❌ 已废弃，产生 PAR_010 编译错误
int sum = (int) @~ 请计算 $a 和 $b 之和 ~
Color c = (Color) @~ 请判断颜色 ~

# ✅ 正确写法：LHS 类型自动成为 LLM 输出格式约束
int sum = @~ 请计算 $a 和 $b 之和 ~
str mood = @~ 请判断颜色，回复颜色单词 ~
```

LHS 的变量声明类型会自动被传递给 LLM 作为输出格式提示，无需额外的类型转换语法。

---

## 实测确认正常工作的功能列表

以下功能经过 MOCK 模式实测验证（通过 idbg + print 探查中间变量确认）：

| 功能 | 状态 | 备注 |
|------|------|------|
| 基础类型（int/str/bool/float）运算 | ✅ | 含整数除法、模运算 |
| `list` / `tuple` 操作 | ✅ | append/insert/remove/len/contains 等 |
| `dict` 直接操作（非 LLM 路径）| ✅ | get/keys/values/contains 等 |
| 字符串方法链 | ✅ | trim/to_upper/replace/startswith/endswith 等 |
| 类定义 + auto-init | ✅ | 无显式 `__init__` 时按字段顺序自动生成 |
| 类继承 + 方法覆盖 | ✅ | 多层继承正常 |
| Enum + switch/case（非 LLM）| ✅ | 直接赋值或 `Direction.NORTH` 模式正常 |
| `@~...~` 行为表达式 + `$var` 插值 | ✅ | 含复杂插值（方法调用结果等）|
| MOCK 完整指令集 | ✅ | INT/STR/FLOAT/BOOL/LIST/SEQ/FAIL/TRUE/FALSE/REPAIR |
| `list` 类型 + LLM 输出 | ✅ | `list l = @~ MOCK:LIST:[...] ~` 正常 |
| `llmexcept` + `retry` | ✅ | 快照隔离 + restore 正常 |
| `llmretry` 语法糖 | ✅ | 单行后缀正常工作 |
| `@+`/`@-` 意图块 | ✅ | 正确注入系统提示词 |
| `@!` 一次性意图 | ✅ | 只影响紧随其后的一条 LLM 调用 |
| `lambda`/`snapshot` 延迟表达式 | ✅ | 意图栈捕获语义正确 |
| `intent_context` OOP | ✅ | push/pop/fork/use/get_current/clear_inherited 均可用 |
| `for...if` / `while...if` 过滤 | ✅ | 含 AI 行为作为过滤条件 |
| try/except/raise | ✅ | 含嵌套、函数内 raise |
| `in` / `not in` 运算符 | ✅ | str/list/dict 均可用 |
| idbg 模块 | ✅ | last_result/last_llm/retry_stack 正常 |
| 多模块 import（ai/file/isys/idbg）| ✅ | 正常协作 |
| 插件系统 | ✅ | 本地 plugins/ 目录插件正常加载 |
| 动态宿主 + 子解释器隔离 | ✅ | parent/child.ibci 沙箱隔离正常 |
| `__snapshot__`/`__restore__` 协议 | ✅ | llmexcept retry 时正确调用 |
| SEM_052 编译期 llmexcept 只读约束 | ✅ | llmexcept body 内写外部变量产生编译错误 |
| 泛型类型（list[str]/dict[K,V]）| ✅ | 编译期可用（非 LLM 路径）|
| 递归函数 | ✅ | fib(15)=610 正常 |
| 类字段标量常量默认值 | ✅ | int/str/bool 字面量默认值正常 |
