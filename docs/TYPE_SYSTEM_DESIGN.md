# IBCI 类型系统设计说明（当前正式版）

> 本文档是 **当前代码状态** 下的正式类型系统设计参考。以最新实现为准，不保留历史过渡形态。
>
> 设计原文（推演过程与第一性原理背景）：`docs/IBCI_TYPE_SYSTEM_FROM_ZERO_ARCHITECTURE.md`  
> 演进历史（各阶段落地记录）：`docs/COMPLETED.md §二十五/§二十六`  
> 任务执行清单（全部勾选）：`docs/TYPE_SYSTEM_TASKS.md`  
>
> **最后更新**：2026-05-08（M1–M5 全部收口；测试基线 1180 passed）

---

## 一、设计目标

IBCI 类型系统需要同时满足以下约束：

1. **编译期与运行期共享唯一类型定义来源**——同一套核心数据结构在编译器语义分析和运行时行为分发中双端生效。
2. **泛型可结构化表达、可递归推导**——`Optional[T]`、`list[T]`、`fn[(T)->R]` 等泛型组合能在类型引用层面直接表达，不需要字符串解析。
3. **类型行为（能力/公理）统一接口**——类型的操作语义（可调用、可迭代、运算符支持等）通过一套一致的机制声明与分发，不分散于多处 mixin 和 isinstance 检查。
4. **保持与 Python 宿主的隔离**——通过 IBCI 自身的对象模型访问运行值，不直接操作 Python 原生类型。
5. **可调用实例（callable-instance）语义清晰**——`lambda`、`snapshot`、`behavior`、用户函数，以及高阶函数参数类型，共享统一的类型表示路径。

---

## 二、核心数据结构

### 2.1 TypeRef（类型引用）

**位置**：`core/kernel/spec/type_ref.py`

`TypeRef` 是 IBCI 类型系统中的**结构化类型引用**，不可变、可哈希、支持递归泛型参数：

```
TypeRef
├── head: str              # 类型的裸名（如 "int", "list", "Optional", "fn"）
├── args: tuple[TypeRef]   # 泛型参数（如 Optional[str] → args=(TypeRef("str"),)）
└── module: Optional[str]  # 跨模块引用时的模块限定符
```

**派生属性**：
- `canonical_name`：标准名（含 args 展开，用于缓存键）
- `qualified_name`：含模块前缀的全限定名
- `substitute(mapping)`：泛型形参替换

**工厂方法**：
- `TypeRef.of(name, module=None)`：简单类型引用
- `TypeRef.generic(head, *args)`：带泛型参数引用
- `TypeRef.from_spec(spec)`：从旧 Spec 桥接

**关键设计原则**：所有类型关系字段（参数类型、返回类型、元素类型等）在 in-memory 模型中统一使用 `TypeRef`，不再用裸字符串名称表示类型引用。

---

### 2.2 TypeDef（类型定义）

**位置**：`core/kernel/spec/base.py`

`TypeDef` 是统一的类型定义模型，所有类型（函数、类、列表、可调用实例等）共享同一结构，通过 `kind` 字段区分语义类别：

```
TypeDef
├── kind: TypeKind         # 类型类别（见 2.3）
├── name: str              # 类型名
├── module: Optional[str]  # 所属模块
│
│ # 可选关系字段（均为 TypeRef）
├── param_types: List[TypeRef]   # 函数/方法参数类型列表
├── return_type: TypeRef         # 函数/方法返回类型
├── parent_type: TypeRef         # 类的父类型
├── element_type: TypeRef        # list/tuple 元素类型
├── key_type: TypeRef            # dict 键类型
├── value_type: TypeRef          # dict 值类型
├── wrapped_type: TypeRef        # Optional[T] 中的 T
├── receiver_type: TypeRef       # BoundMethod 绑定对象类型
└── allowed_element_types: List[TypeRef]  # 联合类型元素
```

**重要约束**：
- TypeDef 不接受任何 `*_name` / `*_module` 字符串 kwargs（历史兼容层已彻底删除）
- `capture_mode`（`lambda` vs `snapshot`）**不属于**类型层，位于 AST 节点和运行时值层
- 旧 `FuncSpec`/`ClassSpec`/`ListSpec`/`DeferredSpec` 等子类别名**已彻底删除**，只用 `TypeDef`

**字段访问规范**：
```python
# 正确：通过 TypeRef 字段读取
spec.return_type.head        # 返回类型名（如 "int"）
spec.return_type.module      # 返回类型所属模块
spec.param_types[0].head     # 第一个参数的类型名
{t.head for t in spec.allowed_element_types}  # 联合类型集合

# 已删除（不存在）：
# spec.return_type_name / spec.return_type_module
# spec.element_type_name / spec.allowed_element_type_names
```

---

### 2.3 TypeKind（类型分类枚举）

**位置**：`core/kernel/spec/base.py`

```python
class TypeKind(Enum):
    BUILTIN        # int / str / bool / float 等基础原子类型
    CLASS          # 用户定义类 / 结构化内置类（intent_context 等）
    FUNCTION       # 普通函数
    BOUND_METHOD   # 绑定方法（self 已绑定）
    LIST           # 列表类型
    TUPLE          # 元组类型
    DICT           # 字典类型
    OPTIONAL       # Optional[T]
    CALLABLE_INSTANCE  # lambda / snapshot / behavior callable-instance
    DYNAMIC        # auto / any 等动态类型
```

**关键点**：
- `TypeKind.CALLABLE_INSTANCE` 已统一承载历史的 `DEFERRED`（旧延迟求值路线）和 `BEHAVIOR` 路线。
- 区分 `lambda` 和 `snapshot` 的 `capture_mode` 字段位于 AST 节点（`IbLambdaExpr`/`IbBehaviorInstance`）和运行时值层，不在 `TypeDef` 内。
- 序列化/反序列化通过 `type_data["axiom_name"]`（`"deferred"` 或 `"behavior"`）还原公理路由，不再通过 `capture_mode` 字段。

---

### 2.4 SpecRegistry（注册表门面）

**位置**：`core/kernel/spec/registry.py`

SpecRegistry 是类型系统的核心门面，编译器和运行时均通过它完成类型查询：

| 方法 | 说明 |
|------|------|
| `resolve(name)` | 按名字查找 TypeDef |
| `resolve_typeref(ref: TypeRef)` | 按 TypeRef 查找，支持跨模块与泛型特化 |
| `is_assignable(src_spec, target_spec)` | 类型兼容性检查（通过 Axiom 层实现） |
| `get_call_cap(spec)` | 获取可调用能力：FUNCTION/BOUND_METHOD/CLASS 等结构性可调用返回 truthy 标记，公理声明 `has_call_cap=True` 时返回公理，否则返回 `None` |
| `get_iter_cap(spec)` | 获取可迭代能力 |
| `get_subscript_cap(spec)` | 获取可下标访问能力 |
| `get_operator_cap(spec)` | 获取运算符能力 |
| `resolve_iter_element(spec)` | 获取迭代元素类型（list/tuple）|
| `resolve_subscript(spec, key_spec)` | 下标访问返回类型 |

**SpecFactory** 是 SpecRegistry 的内部工厂，提供类型安全的构建方法（`create_func()` / `create_class()` / `create_list()` 等），所有参数以 TypeRef 传入。

---

## 三、公理系统（Axiom Layer）

### 3.1 设计动机

公理系统解决的问题：**类型的"能做什么"（行为语义）与类型的"是什么"（结构定义）应当分离**。TypeDef 描述结构，Axiom 描述行为，两者通过 `SpecRegistry` 的 `get_X_cap()` 方法连接。

### 3.2 TypeAxiom Protocol

**位置**：`core/kernel/axioms/protocols.py`

```python
class TypeAxiom(Protocol):
    """统一公理协议——单一接口替代旧 9 个 Capability 子协议"""
    has_call_cap:        bool  # 可调用
    has_iter_cap:        bool  # 可迭代
    has_subscript_cap:   bool  # 可下标访问
    has_operator_cap:    bool  # 支持运算符
    has_parser_cap:      bool  # 支持 from_prompt 解析
    has_from_prompt_cap: bool  # 自定义 from_prompt
    has_converter_cap:   bool  # 支持类型转换
    has_output_hint_cap: bool  # LLM 提示词输出格式说明
```

`BaseAxiom` 提供所有能力的 `False` 默认值，具体公理只需声明 `has_X_cap = True`。

### 3.3 内置公理一览

**位置**：`core/kernel/axioms/primitives.py`

| 公理 | 名称 | 能力标志 | 说明 |
|------|------|----------|------|
| `IntAxiom` | `int` | operator, parser, from_prompt, converter | 整数运算与 LLM 解析 |
| `FloatAxiom` | `float` | operator, parser, from_prompt, converter | 浮点运算 |
| `StrAxiom` | `str` | operator, iter, subscript, parser, from_prompt | 字符串操作 |
| `BoolAxiom` | `bool` | operator, parser, from_prompt, converter | 布尔运算 |
| `ListAxiom` | `list` | iter, subscript, operator | 列表操作 |
| `TupleAxiom` | `tuple` | iter, subscript | 只读元组（无修改方法） |
| `DictAxiom` | `dict` | subscript | 字典操作 |
| `OptionalAxiom` | `Optional` | — | 可空包装语义 |
| `CallableAxiom` | `callable` | call | 可调用抽象根 |
| `DeferredAxiom` | `deferred` | call | callable-instance（lambda/snapshot，继承 CallableAxiom） |
| `BehaviorAxiom` | `behavior` | call | behavior callable-instance |
| `VoidAxiom` | `void` | — | 无返回值语义 |
| `AnyAxiom` | `any` | — | 动态兼容任意类型 |
| `LLMUncertainAxiom` | `llm_uncertain` | — | LLM 不确定性结果占位 |
| `NoneAxiom` | `None` | — | 空值 |
| `IntentContextAxiom` | `intent_context` | call（is_class=True） | 意图上下文实例化 |

### 3.4 公理注册与查找

`AxiomRegistry`（`core/kernel/axioms/registry.py`）持有 `name → TypeAxiom` 映射。`SpecRegistry.get_X_cap()` 通过 spec 的名字查找公理，检查 `has_X_cap`，决定返回什么。

---

## 四、callable-instance 语义统一

### 4.1 历史背景

早期 IBCI 有两条分支路线：
- `lambda`/`snapshot` 走 `DeferredSpec` → `TypeKind.DEFERRED`，称为"延迟求值"
- `@~...~` 行为表达式走 `BehaviorSpec` → `TypeKind.BEHAVIOR`

两者的本质相同：都是"包装一个表达式，构造一个可调用实例"。旧名称"延迟求值"是历史误用，造成认知混乱。

### 4.2 当前统一状态

- `TypeKind.CALLABLE_INSTANCE` 统一表示所有 callable-instance 类型（M3 完成，2026-05-08）
- `DeferredAxiom`（`capture_mode="lambda"/"snapshot"`）和 `BehaviorAxiom` 在公理层均声明 `has_call_cap = True`
- 运行时值类 `IbDeferred` / `IbBehavior` 保留为兼容包装层（均继承 `IbValue`）
- `capture_mode` 明确位于：AST 节点侧表（`node_capture_mode`）和运行时值层，**不**位于 TypeDef

### 4.3 lambda vs snapshot 语义

语义差异**不是延迟求值 vs 立即求值**，而是：

| | `lambda` | `snapshot` |
|--|----------|------------|
| 变量捕获 | 引用捕获（读最新值） | 值拷贝捕获（冻结定义时值） |
| 意图栈 | 调用时使用当前生效意图栈 | 创建时冻结意图栈，调用时忽略当前意图栈 |
| 自包含性 | 依赖外部作用域状态 | 完全自包含 |

### 4.4 fn 关键字的双重角色

`fn` 在不同上下文中扮演两种完全不同的角色：

**角色一：变量声明侧（类 auto 关键字）**

```ibci
fn f = myFunc                          # 推导 f 的类型 = myFunc 的 FuncSpec
fn g = lambda(int x) -> int: x + 1    # 推导 g 的类型 = callable-instance[int]
fn s = snapshot(str name) -> str: name # 推导 s 的类型 = callable-instance[str]
```

`fn` 在声明侧只做**可调用类型推导**，不承载任何输出类型信息。旧的 `int fn f = lambda: EXPR` 形式已废弃（产生 PAR_003）。

**角色二：类型标注侧（高阶函数签名约束）**

```ibci
# 高阶函数参数标注：接受 (int, str) -> bool 签名的 callable
func apply(fn[(int, str) -> bool] predicate, int x, str s) -> bool:
    return predicate(x, s)

# 返回值也可以是带签名的 fn
func make_adder(int n) -> fn[(int) -> int]:
    fn adder = lambda(int x) -> int: x + n
    return adder
```

`fn[(...)->(...)]` 只出现在**类型标注上下文**（函数参数类型、返回类型位置）。

**当前局限**（后续工作）：在嵌套泛型与高阶函数组合路径上，`fn` 的类型推导和错误提示仍有改进空间——这是类型系统主线完成后的下一个关注点。

---

## 五、运行时值模型

### 5.1 IbValue 统一承载层

**位置**：`core/runtime/objects/kernel.py`

```
IbValue
├── type_ref: TypeRef      # 类型引用（指向 SpecRegistry 中的 TypeDef）
├── payload: Any           # 主要值载荷（Python 原生值）
├── fields: Dict           # 命名字段（用户定义类实例、复合对象）
└── meta: Dict             # 元数据（调试信息等）
```

**派生便利属性**：
- `.value` = `self.payload`（`IbInteger`/`IbFloat`/`IbString`/`IbBool` 统一通过 `.value` 访问）
- `IbList.elements` / `IbTuple.elements` = `self.payload` 的 property 别名

**实现层类族**（均继承 IbValue，保留为兼容包装层）：
```
IbValue
├── IbInteger, IbFloat, IbString, IbBool  # 原子值类型（__slots__=()，无独立存储）
├── IbList, IbTuple, IbDict               # 容器类型
├── IbNone                                # 空值
├── IbLLMUncertain                        # LLM 不确定性哨兵
├── IbLLMCallResult                       # LLM 调用结果
├── IbDeferred                            # lambda/snapshot callable-instance
├── IbBehavior                            # behavior callable-instance
└── IbException                           # 用户异常对象
```

### 5.2 类型分发规范

在运行时代码中分发类型时，**正确做法**：

```python
# 正确：通过 ib_class.name 分发（ib_class 是 IbClass 对象，name 是类型名字符串）
if isinstance(obj, IbValue) and obj.ib_class.name == "list":
    ...

# 错误（旧方式，已全面替换）：
# if isinstance(obj, IbList):
#     ...
```

**唯一例外**：`IbNone` 在 `kernel.py` 的 VM 比较操作中有 `isinstance` 检查，属于**哨兵检查**而非类型分发，是有意的。

### 5.3 RuntimeObjectFactory

**位置**：`core/runtime/factory.py`

提供类型安全的运行时对象构造方法，避免直接 import 具体实现类名：

| 方法 | 说明 |
|------|------|
| `create_list(elements)` | 构造 IbList |
| `create_tuple(elements)` | 构造 IbTuple |
| `create_dict(pairs)` | 构造 IbDict |
| `create_behavior(...)` | 构造 IbBehavior（callable-instance） |
| `box(python_value)` | 自动装箱 Python 原生值到 IbValue |

---

## 六、类型体系分层视图

```
                        ┌─────────────────────────────────────┐
编译器语义分析层          │  TypeRef + TypeDef + TypeKind        │
(semantic analyzer)     │  SpecFactory, SpecRegistry           │
                        └────────────────┬────────────────────┘
                                         │ resolve / is_assignable
                        ┌────────────────▼────────────────────┐
公理层                   │  TypeAxiom Protocol                  │
(axiom layer)           │  BaseAxiom + 具体公理实现             │
                        │  has_*_cap 能力声明                   │
                        └────────────────┬────────────────────┘
                                         │ 行为分发
                        ┌────────────────▼────────────────────┐
运行时值层               │  IbValue (type_ref, payload, ...)    │
(runtime objects)       │  IbInteger / IbList / IbDeferred ... │
                        │  RuntimeObjectFactory                 │
                        └─────────────────────────────────────┘
```

---

## 七、序列化/反序列化协议

编译器输出（artifact）中的类型表示与 in-memory TypeDef 略有不同：

- **线协议字段**（artifact 存盘格式）：仍使用 `parent_name` / `parent_module` / `return_type_name` 等字符串字段（保证向后兼容）
- **in-memory 模型**：一律使用 TypeRef 字段，通过 `artifact_rehydrator.py` 在装载时转换
- `axiom_name` 字段（`"deferred"` / `"behavior"`）用于还原 callable-instance 的公理路由

---

## 八、关联文档

| 文档 | 内容 |
|------|------|
| `docs/IBCI_TYPE_SYSTEM_FROM_ZERO_ARCHITECTURE.md` | 设计原文，从第一性原理推演整个类型系统 |
| `docs/TYPE_SYSTEM_TASKS.md` | 五大里程碑 M1–M5 完整任务清单（全勾选）|
| `docs/FN_LAMBDA_SYNTAX_REDESIGN.md` | fn/lambda/snapshot 语法重设计决策（D1–D6）|
| `docs/COMPLETED.md §二十五/§二十六` | M1–M5 落地详情 |
| `docs/CURRENT_TASKS.md` | 当前工作聚焦（类型系统收口后的下一步方向）|
