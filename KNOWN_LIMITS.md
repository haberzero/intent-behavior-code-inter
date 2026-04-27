# IBCI 已知限制与缺陷记录

> 本文件记录通过系统性实测（MOCK 模式 + idbg + print 探查）发现的已知 Bug 与设计限制。  
> 每个条目包含：复现代码、实际行为、预期行为、根因分析、建议修复方向。  
> **最后更新**：2026-04-20（初次建立，来自全面实测分析）；2026-04-20（Bug #1/#2/#4 已修复）

---

## ✅ Bug #1：类字段列表 / 字典字面量默认值静默失效（已修复）

**严重级别**：高（静默产生 `None`，无报错）

**状态**：**已修复** — `core/runtime/interpreter/interpreter.py`，`core/kernel/registry.py`

**修复内容**：
1. `Interpreter.__init__` 不再用一次性的 `get_kernel_token()` 覆盖调用方传入的 `_kernel_token`，从而确保 `set_execution_context()` 被正确调用。
2. `KernelRegistry.set_execution_context()` 移除了 `_is_structure_sealed` 的过度限制（执行上下文属于运行时绑定，非结构性注册）。
3. 运行时限制变量（`instruction_count` 等）和 handler（含 `_visitor_cache`）在 `_pre_evaluate_user_classes()` 之前初始化，避免 `visit()` 中出现 `AttributeError`。

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

## ✅ Bug #2：`dict` 类型变量接收 `@~...~` LLM 输出失败（已修复）

**严重级别**：高（核心用例，运行时崩溃）

**状态**：**已修复** — `core/runtime/interpreter/llm_executor.py`

**修复内容**：`_parse_result()` 中，当 `meta_reg.resolve(type_name)` 返回 `None`（如 `type_name="dict[any,any]"` 含泛型参数时），先剥离泛型参数重试（`"dict[any,any]"` → `"dict"`），确保 `DictAxiom.from_prompt` 被正确调用。

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

## ✅ Bug #3：Enum 类型从 LLM 输出解析失败（已修复，已确认）

**严重级别**：高（Enum + LLM 是核心用例组合）

**状态**：**已确认工作正常** — `_check_type` 对 `is_user_defined=True` 的 `ClassSpec` 跳过类型校验，`IbString("SOUTH")` 赋值到 `Direction` 类型变量可正常通过，`switch/case` 也正常工作。

---

## ✅ Bug #4：`none`（小写）关键字在运行时未定义（已修复）

**严重级别**：中（编译期应拦截但未拦截）

**状态**：**已修复** — `core/compiler/semantic/passes/semantic_analyzer.py`

**修复内容**：在 `visit_IbName()` 中检测到 `node.id == "none"` 且 `uid == "builtin:none"` 时，立即发出 `SEM_001` 编译期错误，提示用户使用 `None`（首字母大写）。

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

## ✅ 已知限制 #6：`dict` 类型接收 LLM 输出（已修复，随 Bug #2 一并解决）

`dict` 类型变量通过 `@~...~` 接收 LLM 输出现在**完全支持**：

```ibci
import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")

dict d = @~ MOCK:DICT:{"key":"value"} ~   # ✅ 正常工作
```

`dict` + LLM 输出已在 Bug #2 修复中同时解决。详见 Bug #2 条目。

---

## 已知限制 #7：类字段不支持调用表达式作为默认值

与 Bug #1 相关：类字段初始化表达式中，只有字面量常量（`int`/`str`/`bool`）可靠工作。函数调用、构造器调用等动态表达式作为字段默认值均不可靠。

**规避方案**：始终通过 `__init__` 构造函数进行动态字段初始化。

---

## 已知限制 #8：子类 auto-init 不含父类字段

**严重级别**：低（符合 Python 语义，但与 C++/Java 使用者直觉不符）

当子类没有显式 `__init__`，编译器会自动生成一个 `__init__`（auto-init），**仅接受当前类自身声明的字段**，不包含父类字段。

**示例**：
```ibci
class Animal:
    str name

class Dog(Animal):
    str breed        # Dog 的 auto-init 只接受 breed，不接受 name
```

构造 `Dog` 时只能传入 `breed`；父类字段 `name` 保持为 `None`（未初始化）：

```ibci
Dog d = Dog("Husky")    # 只设置 breed；d.name = None
print(d.name)           # 输出 None
```

**规避方案**：在子类中显式定义 `__init__`，手动初始化父类字段：

```ibci
class Dog(Animal):
    str breed

    func __init__(self, str dog_name, str dog_breed):
        self.name = dog_name    # 手动赋值父类字段
        self.breed = dog_breed

Dog d = Dog("Rex", "Husky")
print(d.name)           # 输出 Rex
print(d.breed)          # 输出 Husky
```

亦可在构造后手动赋值：

```ibci
Dog d = Dog("Husky")
d.name = "Rex"
```

**根因**：auto-init 生成逻辑（`interpreter.py:_hydrate_user_classes`）仅遍历当前类 `body` 中声明的字段。父类字段通过 `default_fields` 继承，在实例化时被初始化为默认值或 `None`，但不加入构造函数参数。此设计与 Python 行为一致（子类不自动调用 `super().__init__`）。

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
| `for...if` 过滤 | ✅ | 含 AI 行为作为过滤条件 |
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
| 类字段 list/dict 字面量默认值 | ✅ | `list items = []` / `dict meta = {}` 正常（Bug #1 已修复）|
| `dict` 类型 + LLM 输出 | ✅ | `dict d = @~ MOCK:DICT:{...} ~` 正常（Bug #2 已修复）|
| Enum + LLM 输出 | ✅ | `Direction d = @~ MOCK:STR:SOUTH ~` 正常（Bug #3 已确认）|

---

## 引用语义局限性说明

> **最后更新**：2026-04-22（新增引用语义文档）

IBCI 目前对所有复合对象（`list`、`dict`、用户类实例）使用**共享引用**语义——与 Python 一致。这意味着：

### 已知行为与限制

#### 1. 赋值是引用复制，不是值复制

```ibci
list a = [1, 2, 3]
list b = a          # b 与 a 指向同一个列表对象
b.append(4)
print((str)a.len()) # 输出 4，不是 3
```

**规避方案**：手动构造副本列表：

```ibci
list a = [1, 2, 3]
list b = []
for int x in a:
    b.append(x)
```

#### 2. 类实例字段的默认引用陷阱

若多个实例共享同一个"默认"列表字段，修改一个实例的字段会影响其他实例。请始终在构造函数中初始化列表/字典字段：

```ibci
class Stack:
    list items          # 不要在字段声明处赋值（共享引用陷阱）

    func __init__(self):
        self.items = [] # 每个实例独立创建
```

#### 3. `llmexcept` 快照隔离不影响容器内容

`llmexcept` 的 `__snapshot__`/`__restore__` 协议目前只快照并恢复**标量变量绑定**（即变量名→对象的映射）。若快照前的变量持有一个列表，LLM 调用体内对该列表的 `append`/`remove` 等**就地修改**在 `retry` 后不会被还原。

**规避方案**：不要在 `llmexcept` 保护块的 LLM 调用路径中就地修改容器；若需要可回滚的容器状态，在 `llmexcept` 之前先做深复制。

#### 4. `fn` 变量的可调用引用语义

```ibci
fn f = add          # f 持有 add 函数的引用
fn g = f            # g 也引用同一个函数
```

函数本身是不可变的，因此 `fn` 变量的引用语义不会导致副作用问题。

---

## `auto` 与 `fn` 与 `any` 对比

| 关键字 | 用途 | 类型推导时机 | 后续赋值限制 |
|--------|------|------------|------------|
| `auto x = expr` | 通用类型推导，锁定为首次赋值的实际类型 | 编译期 | 只能赋相同类型 |
| `fn f = callable` | 可调用类型推导，RHS 必须是可调用的 | 编译期 | 保持可调用约束 |
| `any x = expr` | 真正的动态类型，不锁定 | 运行时 | 任意类型 |
| `x = expr`（裸赋值）| 隐式 `any` 语义（不推荐，见下方说明） | 运行时 | 任意类型 |

> **注意**：没有类型标注的裸赋值（`x = expr`）编译器会将变量视为 `any` 类型。
> 若需要将此变量用于有类型检查的上下文（如赋给 `int y`），**必须使用强制类型转换**：
> ```ibci
> x = 42
> int y = (int)x    # 必须显式转换，不能直接赋值
> ```

---

## 容器多类型声明说明

`list[int, str, list]` 语法允许声明一个可持有多种类型元素的列表。编译器规则如下：

- **元素读取**（下标访问 `items[i]`、for 迭代）返回 `any` 类型。若需要明确类型，必须显式转换：
  ```ibci
  list[int, str] mixed = [1, "hello"]
  any val = mixed[0]
  int n = (int)val      # 必须先取到 any，再强制转换
  ```
- **不允许** 通过 `auto` 直接承载容器元素取值赋值（编译期推断会失败）：
  ```ibci
  auto x = mixed[0]    # ❌ 不推荐，可能导致类型推断错误
  any x = mixed[0]     # ✅ 建议始终用 any 中转
  int n = (int)x        # ✅ 再强制转换到目标类型
  ```
