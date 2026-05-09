# IBC-Inter 类型系统正式设计说明

> 本文档覆盖 IBC-Inter（IBCI）类型系统的完整架构，包含三层设计（数据层 → 能力层 → 注册表层）、
> 已实现特性说明、核心算法，以及已知限制与演进方向。
>
> **最后更新**：2026-05-09（文档首次正式化；690 测试通过）

---

## 目录

1. [设计原则](#1-设计原则)
2. [三层架构概览](#2-三层架构概览)
3. [数据层：IbSpec 类型描述符体系](#3-数据层ibspec-类型描述符体系)
4. [能力层：Axiom 公理体系](#4-能力层axiom-公理体系)
5. [注册表层：SpecRegistry](#5-注册表层specregistry)
6. [类型赋值与兼容性算法](#6-类型赋值与兼容性算法)
7. [泛型与专化](#7-泛型与专化)
8. [公理类型层次（完整清单）](#8-公理类型层次完整清单)
9. [类型系统在编译器中的使用](#9-类型系统在编译器中的使用)
10. [已知限制与演进方向](#10-已知限制与演进方向)

---

## 1. 设计原则

1. **数据与行为分离**：`IbSpec` 是纯数据记录（无方法、无运行时引用）；所有能力查询通过 `SpecRegistry` 转发给 `AxiomRegistry`。
2. **零循环依赖**：`spec` 层不导入 `axiom` 层；`axiom` 层通过字符串类型名引用 spec，不导入具体 Spec 类。
3. **能力协议优先**：类型能力（可调用？可迭代？支持哪种运算符？）通过 Capability 接口声明，不通过 isinstance 分派。
4. **封印保护**：`KernelRegistry` 在完成初始化后封印（sealed），封印后禁止注册新内置类型，确保类型系统的结构不变性。
5. **泛型通过专化实现**：`list[int]` 等泛型类型是在 `SpecRegistry` 中按需创建的专化 Spec 实例，与基础 `list` Spec 共享公理。

---

## 2. 三层架构概览

```
┌─────────────────────────────────────────────────────┐
│  用户 IBCI 代码                                       │
│  int x = 42 / list[str] items = [...] / IbBehavior  │
└────────────────────────┬────────────────────────────┘
                         │ 编译期 / 运行时类型查询
┌────────────────────────▼────────────────────────────┐
│  层三：SpecRegistry（注册表层）                       │
│  • 按名称查找 IbSpec                                 │
│  • 转发能力查询 → AxiomRegistry                      │
│  • is_assignable() / resolve_member() / get_call_cap()│
│  • resolve_specialization()（泛型专化）              │
└────────────────────────┬────────────────────────────┘
           ┌─────────────┴────────────┐
           ▼                          ▼
┌──────────────────┐       ┌──────────────────────────┐
│ 层二：AxiomRegistry│      │ 层一：IbSpec 数据对象      │
│ （能力层）         │      │ （数据层）                │
│ get_axiom(name)  │      │ • name / module_path      │
│ → TypeAxiom      │      │ • members: Dict[str,MemberSpec]│
│   .is_dynamic()  │      │ • is_user_defined         │
│   .is_class()    │      │ • ClassSpec: parent_name  │
│   .is_compatible()│      │ • ListSpec: element_type_name│
│   .get_call_cap()│      │ • FuncSpec: return_type_name│
│   .get_operator_cap()   │      │ • DeferredSpec / BehaviorSpec│
└──────────────────┘       └──────────────────────────┘
```

---

## 3. 数据层：IbSpec 类型描述符体系

### 3.1 基类：IbSpec

`IbSpec`（`core/kernel/spec/base.py`）是所有类型描述符的根类，是一个 frozen `@dataclass`：

```python
@dataclass(eq=False)
class IbSpec:
    name: str = ""                           # 简单类型名（如 "int", "MyClass"）
    module_path: Optional[str] = None        # 模块限定路径（如 "my_module"）
    is_nullable: bool = True                 # 是否可接受 None 赋值
    is_user_defined: bool = True             # 用户自定义类型（vs 内置类型）
    members: Dict[str, MemberSpec] = ...     # 成员表（纯数据，非 Symbol 引用）
    _axiom_name: Optional[str] = None        # 公理覆盖键（None = 使用 name）
```

`IbSpec` 不持有任何运行时引用或行为。类型能力的查询必须通过 `SpecRegistry`。

### 3.2 具体 Spec 子类

| 子类 | 用途 | 关键字段 |
|------|------|---------|
| `FuncSpec` | 函数类型 | `return_type_name: str`，`is_llm: bool`，`param_names: List[str]` |
| `ClassSpec` | 用户定义类（含 Enum）| `parent_name: str`，`parent_module: str` |
| `ListSpec` | 列表类型（含泛型变体）| `element_type_name: str`，`allowed_element_type_names: List[str]` |
| `DictSpec` | 字典类型（含泛型变体）| `key_type_name: str`，`value_type_name: str` |
| `TupleSpec` | 元组类型 | `element_type_names: List[str]`（按位置类型序列）|
| `DeferredSpec` | 延迟执行类型（lambda/snapshot）| `return_type_name: str`，`deferred_mode: str` |
| `BehaviorSpec` | LLM 行为表达式类型（继承自 DeferredSpec）| `return_type_name: str` |
| `BoundMethodSpec` | 已绑定接收者的方法 | `receiver_type_name: str`，`method_name: str` |
| `ModuleSpec` | 插件模块类型 | `is_user_defined: False` |

### 3.3 内置常量 Spec

全局常量实例（`core/kernel/spec/specs.py`）：

```python
INT_SPEC, FLOAT_SPEC, STR_SPEC, BOOL_SPEC   # 基础标量类型
VOID_SPEC, ANY_SPEC, AUTO_SPEC, NONE_SPEC   # 特殊类型
LIST_SPEC, DICT_SPEC, TUPLE_SPEC            # 容器基础类型
BEHAVIOR_SPEC, DEFERRED_SPEC                # 延迟执行类型
FN_CALLABLE_SPEC                            # fn 类型推断哨兵（等同于 callable）
LLM_CALL_RESULT_SPEC, LLM_UNCERTAIN_SPEC    # LLM 结果类型
INTENT_SPEC, INTENT_CONTEXT_SPEC            # 意图系统类型
```

### 3.4 MemberSpec 和 MethodMemberSpec

成员描述符（`core/kernel/spec/member.py`）：

```python
@dataclass
class MemberSpec:
    """字段成员：name, type_name, module_path, is_optional"""

@dataclass
class MethodMemberSpec(MemberSpec):
    """方法成员：param_names, param_types, return_type_name, return_module"""
```

所有字段都是字符串，不含 Symbol 引用，确保零循环依赖。

---

## 4. 能力层：Axiom 公理体系

### 4.1 TypeAxiom Protocol

`TypeAxiom`（`core/kernel/axioms/protocols.py`）是所有公理必须实现的单一入口协议：

```python
class TypeAxiom(Protocol):
    name: str                              # 公理名称（= 类型名）

    # 类型属性声明
    def is_dynamic(self) -> bool: ...     # True → 类似 any，接受任意赋值
    def is_class(self) -> bool: ...       # True → 可通过 ClassName() 实例化
    def is_behavior(self) -> bool: ...    # True → 是 LLM 行为表达式类型
    def is_compatible(self, other: str) -> bool: ...  # 类型兼容性声明

    # 能力访问（返回 None = 无该能力）
    def get_call_capability(self) -> Optional[CallCapability]: ...
    def get_operator_capability(self) -> Optional[OperatorCapability]: ...
    def get_iter_capability(self) -> Optional[IterCapability]: ...
    def get_subscript_capability(self) -> Optional[SubscriptCapability]: ...
    def get_converter_capability(self) -> Optional[ConverterCapability]: ...
    def get_parser_capability(self) -> Optional[ParserCapability]: ...
    def get_from_prompt_capability(self) -> Optional[FromPromptCapability]: ...
    def get_llmoutput_hint_capability(self) -> Optional[IlmoutputHintCapability]: ...

    # 方法成员声明（公理负责声明其方法的签名）
    def get_method_specs(self) -> Dict[str, MethodMemberSpec]: ...
```

### 4.2 Capability 接口

每种能力通过独立的 Protocol 接口声明（`core/kernel/axioms/protocols.py`）：

| Capability | 关键方法 | 使用场景 |
|-----------|---------|---------|
| `CallCapability` | `resolve_return_type_name(arg_types)→str` | 函数/behavior/bound_method 调用 |
| `OperatorCapability` | `resolve_operation_type_name(op, other)→str` | `+`、`-`、`*` 等双目运算 |
| `IterCapability` | `get_element_type_name()→str` | `for x in iterable` |
| `SubscriptCapability` | `resolve_item_type_name(key_type)→str` | `obj[key]` 下标访问 |
| `ConverterCapability` | `can_convert_from(source)→bool` | `(Type)expr` 强制类型转换 |
| `ParserCapability` | `parse_value(raw)→Any` | 将原始字符串解析为 Python 值 |
| `FromPromptCapability` | `from_prompt(raw, spec)→(bool, Any)` | 将 LLM 原始输出解析为 IBCI 值 |
| `IlmoutputHintCapability` | `__outputhint_prompt__(spec)→str` | 生成 LLM 输出格式提示词 |

### 4.3 BaseAxiom 与具体公理

`BaseAxiom`（`core/kernel/axioms/primitives.py`）是所有具体公理的基类，提供默认实现（所有能力返回 None，`is_dynamic=False`，`is_class=False`，`is_behavior=False`）。

具体公理通过多重继承同时实现 `BaseAxiom` 和所需的 Capability 接口：

```python
class IntAxiom(BaseAxiom, OperatorCapability, ConverterCapability,
               ParserCapability, FromPromptCapability, IlmoutputHintCapability):
    name = "int"
    def is_compatible(self, other: str) -> bool:
        return other in ("int", "float", "any")  # int 可赋给 float 上下文
    def get_operator_capability(self): return self
    def resolve_operation_type_name(self, op, other):
        if other == "float": return "float"
        if other == "int": return "int"
        return None
    ...
```

### 4.4 DynamicAxiom（any / auto）

`DynamicAxiom`（`core/kernel/axioms/primitives.py`）是唯一的"通配"公理：

```python
class DynamicAxiom(BaseAxiom, CallCapability):
    def is_dynamic(self) -> bool: return True
    def is_compatible(self, other: str) -> bool: return True  # 兼容所有类型
    def get_call_capability(self): return self
    def resolve_return_type_name(self, arg_types): return "auto"
```

`any` 和 `auto` 均使用 `DynamicAxiom`。

### 4.5 AxiomRegistry

`AxiomRegistry`（`core/kernel/axioms/registry.py`）是公理的注册表，通过 `get_axiom(name)` 返回对应公理实例。内置公理通过 `register_core_axioms()` 在启动时注册，用户自定义类的公理通过 `_bootstrap_axiom_methods()` 在 Spec 注册时动态创建。

---

## 5. 注册表层：SpecRegistry

### 5.1 职责

`SpecRegistry`（`core/kernel/spec/registry.py`）是类型系统的协调枢纽：
- 维护 `name → IbSpec` 字典（注册表）
- 持有 `AxiomRegistry` 引用
- 提供类型查询、能力查询、兼容性检查、成员解析等统一入口

### 5.2 核心接口

```python
class SpecRegistry:
    # 查找
    def resolve(name, module_path=None) -> Optional[IbSpec]
    def resolve_member(spec, attr_name) -> Optional[MemberSpec]
    def get_base_spec(spec) -> Optional[IbSpec]       # 剥离泛型参数

    # 能力查询（通过 AxiomRegistry 转发）
    def get_call_cap(spec) -> Optional[CallCapability]
    def is_callable(spec) -> bool
    def is_dynamic(spec) -> bool
    def is_behavior(spec) -> bool
    def is_class(spec) -> bool

    # 兼容性
    def is_assignable(src, target) -> bool
    def get_diff_hint(src, target) -> Optional[str]

    # 泛型
    def resolve_specialization(spec, arg_specs) -> Optional[IbSpec]

    # 注册
    def register(spec) -> None                        # 封印前可调用
    def register_user_class(class_spec) -> None       # 编译器注册用户类
```

### 5.3 get_call_cap 能力路由

```python
def get_call_cap(self, spec: IbSpec) -> Optional[CallCapability]:
    if spec.name in ("auto", "any"):
        return _FUNC_SPEC_CALL_CAP         # FuncSpec 的通用 CallCapability
    if isinstance(spec, FuncSpec):
        return _FUNC_SPEC_CALL_CAP
    axiom = self._axiom_registry.get_axiom(spec.get_base_name())
    return axiom.get_call_capability() if axiom else None
```

---

## 6. 类型赋值与兼容性算法

`SpecRegistry.is_assignable(src, target)` 实现以下优先级顺序：

```
1. 恒等检查：src is target → True
2. 动态目标：is_dynamic(target) → True（any 接受一切）
3. 动态源：is_dynamic(src) → 只有 target 也是 dynamic 才接受
4. 名称匹配：src.name == target.name 且 module_path 相同 → True
5. 多类型列表特判：两者均为 ListSpec 时比较 allowed_element_type_names
6. 公理兼容：src_axiom.is_compatible(target.name) → 公理声明的向上兼容
7. 可空接受：target.is_nullable 且 src.name == "None" → True
8. 类继承：src 是 ClassSpec 时递归检查 parent 链
```

**is_compatible() 方向原则**：`src_axiom.is_compatible(target_name)` 表达"我（source 类型）能赋给 target 类型的变量吗"，即子类型向上兼容：

| source | 可赋值给 target | 不可赋值给 target |
|--------|--------------|----------------|
| `behavior` | `behavior`、`deferred`、`callable` | `any type` without behavior in hierarchy |
| `deferred` | `deferred`、`callable` | `behavior` |
| `bool` | `bool`、`int` | `float`（IBCI bool 不是 float）|
| `int` | `int`、`float` | `str` |

---

## 7. 泛型与专化

### 7.1 泛型语法

```ibci
list[int]           # 单类型：element_type_name = "int"
list[int, str]      # 多类型：allowed_element_type_names = ["int","str"], element_type_name = "any"
dict[str, int]      # 键值类型：key_type_name = "str", value_type_name = "int"
tuple[int, str]     # 位置类型序列（固定长度）
```

### 7.2 专化流程

当编译器遇到 `list[int]` 类型注释时：

1. 语义分析器调用 `registry.resolve_specialization(list_spec, [int_spec])`
2. `SpecRegistry` 检查 `ListAxiom` 是否实现了 `resolve_specialization_by_names()`
3. `ListAxiom.resolve_specialization_by_names(registry, ["int"])` 创建新 `ListSpec(element_type_name="int")`
4. 新 Spec 被注册到 registry 并返回
5. 新 Spec 的方法成员通过 `axiom.get_method_specs()` 自动填充

专化的 Spec 与基础 Spec 共享同一公理（`ListAxiom`），只是 element_type_name 不同。

### 7.3 泛型下标访问类型推断

`SubscriptCapability.resolve_item_type_name(key_type)` 返回元素类型名：
- `list[int]`：返回 `"int"`
- `list[int, str]`：返回 `"any"`（多类型混合，运行时才能确定）
- `dict[str, int]`：返回 `"int"`（已知值类型）

---

## 8. 公理类型层次（完整清单）

```
Object（根，隐式）
├─ int         （IntAxiom）          — 整数；is_compatible: int, float, any
├─ float       （FloatAxiom）         — 浮点；is_compatible: float, any
├─ str         （StrAxiom）           — 字符串
├─ bool        （BoolAxiom）          — 布尔；is_compatible: bool, int, any（bool isa int）
├─ list        （ListAxiom）          — 可变列表（含泛型专化 list[T]）
├─ dict        （DictAxiom）          — 键值字典（含泛型专化 dict[K,V]）
├─ tuple       （TupleAxiom）         — 不可变元组
├─ None        （NoneAxiom）          — 空值（可赋给所有 is_nullable=True 的目标）
├─ slice       （SliceAxiom）         — 切片（内部类型，非用户可见）
├─ Exception   （ExceptionAxiom）     — 异常对象
├─ Enum        （EnumAxiom）          — 枚举基类（用户类继承）
├─ llm_uncertain（LLMUncertainAxiom）— LLM 调用结果不确定占位符
├─ llm_call_result（LlmCallResultAxiom）— LLM 调用结果 IBCI 对象
├─ intent      （IntentAxiom）        — 意图对象（is_class=True）
├─ intent_context（IntentContextAxiom）— 意图上下文（is_class=True）
├─ void        （VoidAxiom）          — 无返回值标注（is_dynamic=False，不接受任何赋值）
├─ any / auto  （DynamicAxiom）       — 通配类型（is_dynamic=True）
└─ callable    （CallableAxiom）      — 可调用基类（is_dynamic=False，抽象）
     ├─ bound_method（BoundMethodAxiom）— 已绑定接收者的方法
     └─ deferred（DeferredAxiom）       — 延迟执行容器（lambda/snapshot）
          └─ behavior（BehaviorAxiom）  — LLM 行为表达式（特化 deferred）
```

**重要**：此层次是 IBCI 类型系统（公理层）的声明，与 Python 实现类的继承无关。`IbDeferred` 和 `IbBehavior` 都直接继承自 `IbObject`，不存在 Python 级别的互相继承。

---

## 9. 类型系统在编译器中的使用

### 9.1 Pass 2/3：类型注释解析

语义分析器（`core/compiler/semantic/passes/semantic_analyzer.py`）通过以下步骤处理类型：

1. `_resolve_type(type_name, module)` → `registry.resolve()` 获取 `IbSpec`
2. 泛型类型通过 `registry.resolve_specialization()` 创建专化实例
3. 函数返回类型、参数类型注释写入 `FuncSpec`
4. 用户类定义通过 `registry.register_user_class()` 注册新 Spec

### 9.2 Pass 3+：类型检查

- 赋值检查：`registry.is_assignable(src_spec, target_spec)`
- 运算符结果：`registry.get_call_cap(spec)` 或 `axiom.get_operator_capability()`
- 成员访问：`registry.resolve_member(spec, attr_name)`
- 返回值检查：函数返回类型与 `FuncSpec.return_type_name` 对照

### 9.3 LLM 输出类型传递

行为表达式（`@~...~`）的左值类型自动传递给 LLM 执行路径：
1. 编译器将 LHS 类型名写入 `IbBehaviorExpr.expected_type`
2. 运行时 `LLMExecutorImpl._parse_result()` 通过 `FromPromptCapability.from_prompt()` 解析输出
3. 类型格式提示通过 `IlmoutputHintCapability.__outputhint_prompt__()` 注入到 LLM 提示词

用户自定义类可通过 vtable 实现 `__from_prompt__` 和 `__outputhint_prompt__` 协议参与此流程。

---

## 10. 已知限制与演进方向

### 10.1 当前限制

- **`spec.name` 双重职责**：当前 `spec.name` 同时用作注册表键（如 `"list[int]"`）和语义分类标签（如 `"list"`）。所有语义类型检查必须通过 `spec.get_base_name()`（剥离泛型后缀），而非直接比较 `spec.name`。
- **方法签名为字符串**：`MethodMemberSpec.param_types` / `return_type_name` 均为字符串，不是结构化类型引用。泛型方法的类型传播（如 `list[T].append(T)` → `void`）无法通过当前结构准确表达。
- **没有真正的泛型参数**：泛型专化通过 `resolve_specialization()` 按需创建独立 Spec，没有统一的参数化类型表示（如 `TypeRef(base="list", args=[TypeRef("int")])`）。
- **编译期 `fn` 签名约束不完整**：`fn f = some_func` 的签名约束在调用时不做静态参数匹配；`func[int→int]` 泛型签名标注尚未实现。

### 10.2 长期演进方向（TypeRef 重构，见 PENDING_TASKS.md §十三）

**目标**：引入 `TypeRef` 统一类型引用，实现以下正交性：

| 类型维度 | 当前表示 | TypeRef 目标 |
|---------|---------|-------------|
| 变量类型 | `sym.spec: IbSpec` | `sym.type_ref: TypeRef` |
| 函数返回类型 | `FuncSpec.return_type_name: str` | `FuncSpec.return_type: TypeRef` |
| 容器元素类型 | `ListSpec.element_type_name: str` | `TypeRef.args[0]` |
| 嵌套泛型 | 无法表达 | `TypeRef(args=[TypeRef(args=[...])])` |
| 类成员类型 | `MemberSpec.type_name: str` | `MemberSpec.type_ref: TypeRef` |

`TypeRef` 重构是一项大型变更，需在类型系统稳定后系统推进，不作为近期 P0 目标。

---

*相关文档：`docs/ARCH_DETAILS.md`（运行时公理化架构细节）；`docs/PENDING_TASKS.md §十三`（TypeRef 演进方向）*
