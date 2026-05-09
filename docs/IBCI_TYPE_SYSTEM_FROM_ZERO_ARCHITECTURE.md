# IBCI 类型系统：从零开始的全新架构设计

> **实现状态说明（2026-05-09）**  
> 本文档是类型系统重构的架构原文。当前代码已完成 **M1–M5**（全部里程碑）：`TypeRef`、`TypeDef`、`Optional[T]`、`CALLABLE_INSTANCE` 路线，以及以 `IbValue` 为中心的运行时值承载层，Axiom 接口统一化均已落地。  
> 类型系统主线 M1–M5 已全部完成（2026-05-08）。本文保留"设计原文 + 迁移目标"性质，记录当时的架构推演与设计动机。
> 与当前代码对齐的正式设计文档见 `docs/TYPE_SYSTEM_DESIGN.md`；时间线归档见 `docs/COMPLETED.md`。

下面我把自己当作一个被新项目聘请的语言架构师，假定你是产品负责人。我**不会**引用现有 IBCI 代码中的任何具体类名或字段，而是从语言设计的第一性原理推演出整个体系，最后再给你一张"它如何落到 Python 实现"的具体地图。

---

## 第零章：先达成共识——我们到底需要一个什么样的类型系统

在动笔之前，我先把你的六条约束翻译成具体的设计目标，确保我们对"成功的标准"理解一致：

| 你的约束 | 翻译成设计目标 |
|---------|--------------|
| 编译期与解释期良好隔离 | 编译产物是**纯数据**（可序列化/反序列化的扁平结构），不包含任何函数、闭包、Python 引用 |
| 编译器和解释器共享唯一定义来源 | 类型的"身份"和"结构"由**同一组数据类**承载，编译器和解释器都从这一组类读取，谁都不持有自己的版本 |
| 面向对象、层次精炼 | 内核只暴露 **3 个核心概念**：类型引用、类型定义、类型行为。其余皆为这三者的特化 |
| 内核层与用户层互相对应 | 用户在 IBCI 看到的每一个类，对应内核中**且仅对应一个**类型定义对象。两层名字一一映射 |
| 支持泛型 | 类型引用必须是**结构化、递归**的（不是字符串拼接） |
| 与 Python 解耦 | 用户值的运行时表示有自己的对象层，Python 类型只是"实现细节" |
| 代码量尽量减少 | 用**一种通用机制**取代当前的 7 种 `XxxSpec` 平行结构 |

---

## 第一章：三个核心概念，三个文件，三个角色

整个类型系统的全部基础就是这三个概念。我先抽象地讲清楚它们**是什么**和**为什么需要**，然后再给出数据结构。

### 1.1 概念 ①：TypeRef —— 类型的"地址"

一个类型在源代码、AST、符号表、函数签名、容器元素声明中**被引用**的方式。

它是**纯不可变值**。它本身不包含类型的任何能力或成员信息——它只是一个"指向某个类型的标签"。

为什么必须有它？因为类型系统中 90% 的位置只需要**引用**一个类型（例如"这个变量是 int"，"这个函数返回 list[str]"），并不需要立刻知道 int 有什么方法。如果在每一处都内嵌完整的类型定义，会有循环引用（int 的方法返回 int）、序列化困难、内存浪费等一系列问题。

**TypeRef 的关键特性必须是：**
- **可哈希**：能作为字典 key、能放进 set 用于去重缓存
- **递归结构化**：`list[dict[str, int]]` 这种嵌套必须直接能表达，不靠字符串拼接
- **不依赖任何注册表**：构造一个 TypeRef 不需要任何全局状态，纯粹的值
- **可序列化**：能被 JSON / pickle 直接吐出

### 1.2 概念 ②：TypeDef —— 类型的"内容"

一个类型**自己**是什么——它的成员、它的父类、它的泛型形参。

它由编译器在分析阶段填充，由解释器在运行时读取。它存活在一个"注册表"里，通过 TypeRef 来索引。**它是编译产物的核心数据**——编译器输出一份 TypeDef 集合，解释器读取这份集合来理解程序的类型世界。

**TypeDef 的关键特性：**
- **纯数据**：只有字段，没有方法（除了简单的 getter）。所有"行为"由概念 ③ 提供
- **统一形态**：不论是 int、list、用户类、函数类型、模块类型，**全部用同一个 TypeDef 类**来描述。差异化通过其字段的不同填充表达，而**不是**通过子类化
- **闭合于 TypeRef**：TypeDef 内部所有指向"其他类型"的字段，都用 TypeRef，从不直接持有另一个 TypeDef

### 1.3 概念 ③：Axiom —— 类型的"行为"

一个类型**能做什么**——能否被调用、能否被迭代、`+` 运算的结果是什么类型、如何把 LLM 的字符串输出解析成这个类型的值。

Axiom 是**纯逻辑**：它不持有任何状态，只回答问题。它是类型的"虚表/dispatcher"。

**Axiom 的关键特性：**
- 是 Python 端的**代码**（接口的具体实现），不是 IBCI 数据
- 被注册到一个"行为注册表"里，**通过 TypeDef 上的一个字符串 key 关联**
- 编译器查询 Axiom 来做类型推断（"int + float 结果是什么？"）
- 解释器查询 Axiom 来做实际计算（"调用 to_bool 应该怎么转换？"）
- 是编译期和运行期**唯一共享**的逻辑入口

### 1.4 三者的关系

```
┌─────────────────────────────────────────────────────────────┐
│                    符号表 / AST 节点                          │
│   (变量声明、函数签名、表达式类型……都只持有 TypeRef)            │
└──────────────────────────┬──────────────────────────────────┘
                           │  resolve(ref, registry)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│         TypeRegistry (TypeDef 集合，编译产物核心)              │
│   { canonical_name → TypeDef, ... }                          │
│   纯数据，可序列化，编译器写入，解释器读取                       │
└──────────────────────────┬──────────────────────────────────┘
                           │  TypeDef.axiom_key
                           ▼
┌─────────────────────────────────────────────────────────────┐
│        AxiomRegistry (Axiom 集合，纯 Python 逻辑)             │
│   { axiom_key → Axiom 实例, ... }                            │
│   编译器和解释器共享同一份                                     │
└─────────────────────────────────────────────────────────────┘
```

**这个三层分离就是整个设计的支柱**。下面我把每一层的数据结构具体化。

---

## 第二章：数据结构定义（伪代码，语言无关）

### 2.1 TypeRef

```
TypeRef (frozen, hashable):
    head:    str                  # 基础类型名："int", "list", "MyClass"
    args:    tuple[TypeRef, ...]  # 泛型实参，空元组表示非泛型
    module:  str | None           # 跨模块限定符，None 表示当前/内置

    # 派生属性（不是字段）
    canonical_name:  str  →  "list[dict[str,int]]" 这样的标准化字符串
    qualified_name:  str  →  module + canonical_name
```

**注意 TypeRef 里没有的东西**：
- 没有 `nullable`：可空性是类型组合，不是属性（详见第八章）
- 没有 `members`：那是 TypeDef 的事
- 没有指向 TypeDef 的指针：通过 registry 查询

**几个例子：**

| IBCI 语法 | TypeRef 字面表示 |
|----------|----------------|
| `int` | `TypeRef("int")` |
| `list[int]` | `TypeRef("list", (TypeRef("int"),))` |
| `dict[str, list[int]]` | `TypeRef("dict", (TypeRef("str"), TypeRef("list", (TypeRef("int"),))))` |
| `mymod.Foo` | `TypeRef("Foo", (), module="mymod")` |
| `fn[(int,str)->bool]` | `TypeRef("fn", (TypeRef("__args__", (TypeRef("int"), TypeRef("str"))), TypeRef("bool")))` |

### 2.2 TypeDef

注意这里**只有一个类**，所有种类的类型都用它表达，差异通过 `kind` 字段和不同字段的填充来区分：

```
TypeDef (mutable during compile, frozen after):
    name:          str                       # 简单名
    module:        str | None                # 来源模块
    kind:          TypeKind                  # 见下文
    
    # 继承 —— 一切类型都有父
    parent:        TypeRef | None            # None 仅 Object 是
    
    # 泛型形参 —— ["T"], ["K","V"], 或 []
    type_params:   list[str]
    
    # 成员 —— 字段、方法（包括 LLM 方法）
    members:       dict[str, MemberDef]
    
    # Axiom 关联 —— 字符串 key 指向 AxiomRegistry
    axiom_key:     str                       # 默认 == name
    
    # 元信息
    is_user_defined: bool
    
    # 仅 kind 为 FUNCTION/METHOD 时使用
    func_signature:  FuncSignature | None
    
    # 仅 kind 为 GENERIC_INSTANTIATION 时使用
    base:            TypeRef | None          # 例如 list[int].base == TypeRef("list")
```

```
TypeKind = enum {
    OBJECT,      # 唯一根类型 Object
    PRIMITIVE,   # int, str, bool, float —— 无用户可见成员，由 Axiom 提供能力
    CONTAINER,   # list, dict, tuple —— 内置泛型容器
    CLASS,       # 用户定义类
    FUNCTION,    # 函数/方法类型，func_signature 字段有效
    MODULE,      # 模块命名空间
    SPECIAL,     # any, void, None, Optional —— 类型系统的"标记类型"
}
```

```
MemberDef:
    name:        str
    kind:        FIELD | METHOD | LLM_METHOD
    type_ref:    TypeRef                    # 字段类型 / 方法返回类型
    func_sig:    FuncSignature | None       # 仅方法
    
FuncSignature:
    params:      list[(name: str, type: TypeRef)]
    returns:     TypeRef
    is_llm:      bool
```

**为什么要把 `FuncSpec`/`ClassSpec`/`ListSpec` 等等折叠成单一 `TypeDef`？**

因为它们之间的差别只是**有哪些字段被填充**，没有任何操作是只对其中一种类型有意义的。当前的多子类设计强迫每处代码都做 `isinstance` 分支，反而把简单的"读字段"复杂化。统一成一个数据类，配合 `kind` 字段，使得：
- 序列化变成单一格式
- 注册表只管一种东西
- isinstance 分支大量消失
- 新增一个类型种类只需新增一个 `kind` 枚举值，不用建一个新类

### 2.3 Axiom

Axiom 是 Python 接口（不是 IBCI 数据）：

```
class Axiom (interface):
    # —— 编译期查询 ——
    can_assign_from(self, src_ref: TypeRef, target_ref: TypeRef, registry) -> bool
    operator_result(self, op: str, other_ref: TypeRef | None) -> TypeRef | None
    member_lookup(self, name: str, type_ref: TypeRef, registry) -> MemberDef | None
        # 用于泛型特化：list[int].__getitem__ → int
    
    # —— 运行时操作 ——
    construct(self, args, registry, vm) -> IbValue           # 实例化
    iterate(self, value, vm) -> Iterator[IbValue]            # 迭代协议
    call(self, value, args, vm) -> IbValue                   # 调用协议
    subscript(self, value, key, vm) -> IbValue               # 下标
    binop(self, op, lhs, rhs, vm) -> IbValue                 # 二元运算
    
    # —— LLM 协议 ——
    output_hint(self, type_ref: TypeRef) -> str              # 给 LLM 的输出指引
    parse_output(self, raw: str, type_ref: TypeRef) -> IbValue   # 从 LLM 输出反序列化
```

每个内置类型实现一个 Axiom 子类。用户定义类共用同一个 `UserClassAxiom`（由 TypeDef 的成员驱动行为）。

**关键点**：Axiom **只接收 TypeRef 和值，不接收 TypeDef**。因为在很多场景下 TypeRef 是足够的（"int 加 int 的结果是 int"），而需要 TypeDef 时（比如查方法）通过 `registry.resolve(ref)` 临时取出。这让 Axiom 写起来非常简单，且天然支持泛型特化。

---

## 第三章：内核类型层级（用户视角的类继承图）

这是 IBCI 用户在语言层看到的类型层级——**注意它只有一棵树，没有平行节点**：

```
Object                        ← 唯一根，TypeKind.OBJECT
├── Primitive (抽象)           ← 内核内部分类，用户层可见为 Object 的子类
│   ├── int
│   ├── float
│   ├── bool      (extends int 在数值上下文，但名义上仍 Primitive)
│   ├── str
│   └── None
├── Container (抽象)
│   ├── list[T]
│   ├── dict[K, V]
│   └── tuple[T...]
├── Callable (抽象)
│   ├── fn         (普通函数类型)
│   ├── method     (绑定方法)
│   └── behavior   (LLM-生成的可调用)
├── Type           (元类，类对象本身的类型)
├── Module
├── Exception
│   └── LLMError
│       ├── LLMParseError
│       ├── LLMRetryExhaustedError
│       └── LLMCallError
├── Optional[T]    (空安全包装，见第八章)
└── 用户定义类...   (默认 extends Object)
```

**抽象类**（Primitive/Container/Callable）只是为了在 `is_assignable_to` 检查时形成有意义的中间层级，**不**对用户开放 `extends Primitive`。这通过 TypeDef 的元数据标记 `is_abstract_kernel = True` 实现。

**特殊类型**（不在树中的"标记类型"）：
- `any`：渐进类型的逃生阀。和所有类型双向兼容。
- `void`：函数无返回值。**不是** `None` 的别名（详见 §3.2）。
- `auto`：编译期推断占位符，推断完成后被替换为具体 TypeRef。

### 3.1 为什么这棵树长这样

- **Object 唯一性**：满足你最初的设计意图——所有类型都从 Object 继承。`int`、`list`、`MyClass` 在内核层面都通过 `parent: TypeRef("Object")` 显式连接。这消除了当前 "PRIMITIVE 类型用 base IbSpec、用户类用 ClassSpec" 的不对称。
- **抽象中间层**：Primitive / Container / Callable 的存在让 `is_assignable_to(int, Primitive)` 这种查询变得有意义，将来要做"接受任意原始类型的函数"时能直接表达。
- **Type 是元类**：保留你原有的"一切皆对象，类本身也是 Object"的设计。`Object.parent = None`，`Type.parent = Object`，`int.parent = Primitive`，`Primitive.parent = Object`。

### 3.2 void vs None vs any 的区别

| 类型 | 含义 | 可作为变量类型？ | 可作为返回类型？ |
|------|------|----------------|----------------|
| `None` | 真实存在的单例值（占位符语义） | 可以，但通常用 `Optional[T]` | 可以 |
| `void` | "本函数不返回值" 的语法标注 | **不可** | 仅返回类型可用 |
| `any` | 渐进类型逃生阀，禁用静态检查 | 可以 | 可以 |

这三个的区分**必须**在文档中讲清楚——它们在用户代码里看起来"都不返回什么"但语义截然不同。

---

## 第四章：编译期流水线（一份扁平产物的诞生）

整个编译期的核心目标是：**输出一份纯数据的"程序类型快照"**，让解释器拿着这份快照就能完整理解程序的类型世界。

### 4.1 编译期的产物形态

```
CompiledProgram (pure data, serializable):
    types:        dict[qualified_name → TypeDef]    # 所有类型的定义
    symbols:      dict[scope_id → SymbolTable]      # 所有作用域的符号
    ast:          IbAst                              # 已类型标注的 AST
    annotations:  dict[node_id → TypeRef]           # AST 节点 → 类型引用的侧表
```

注意 `annotations` 的存在：AST 节点本身只持有 TypeRef（如果有），需要类型 dispatching 时通过 `resolve(ref, registry)` 拿 TypeDef，再通过 `axiom_key` 拿 Axiom。

### 4.2 编译期 Pass 顺序

```
Pass 1  Lex/Parse              → 原始 AST（无类型）
Pass 2  Type Collection        → 扫描所有 class 声明，建立 TypeDef 骨架（仅 name+kind+parent+type_params）
Pass 3  Member Resolution      → 填充 TypeDef.members 和 FuncSignature
Pass 4  Symbol Resolution      → 名字解析，每个变量/参数写入 TypeRef
Pass 5  Type Inference         → 表达式 → TypeRef 推断，写入 annotations 侧表
Pass 6  Type Checking          → 调用 Axiom.can_assign_from / operator_result 校验
Pass 7  Lowering               → 生成最终 CompiledProgram
```

每一 Pass 都**只读 TypeRef、写 TypeRef**，TypeDef 由 Pass 2-3 一次性填好，之后只读。这意味着：
- 同一个 TypeRef 在多处复用，结构哈希后可以缓存推断结果
- 编译器不需要任何"运行时"概念
- 调试容易：dump 出 `CompiledProgram` 的 JSON 就能看完整状态

### 4.3 编译期遇到泛型怎么办

`list[int]` 在源码中出现时，编译器**不**为它创建一个新的 TypeDef，而是构造一个 TypeRef：

```
TypeRef("list", (TypeRef("int"),))
```

这个 TypeRef 在符号表里直接使用。**特化**的发生时机是在查询 `member_lookup("list[int]", "__getitem__")` 时——这时由 `ContainerAxiom` 临时计算返回类型 `int`（用 type_params 替换规则），不需要落地新的 TypeDef。

只有当用户**显式**为 `list[int]` 添加方法时（IBCI 不一定支持，但保留可能），才需要落地特化的 TypeDef。

---

## 第五章：运行时（解释器）侧

### 5.1 运行时的对象层

完全不依赖 Python 类型，自己有一套对象模型：

```
class IbValue:                       # 用户值的根
    type_ref:  TypeRef               # 这个值是什么类型
    fields:    dict[str, IbValue]    # 实例字段（仅 CLASS 类型有）
    payload:   Any                   # Python 端的实现细节（仅内核可见）
```

**要点**：
- `IbValue` 是**唯一**的运行时值类型。`int`、`str`、用户类实例**全都**是 `IbValue`，区别只在 `type_ref` 和 `payload`。
- `payload` 是封装的 Python 原值（`int`、`str`、`list[IbValue]` 等）。**用户代码看不到 payload**，所有访问通过 Axiom dispatch。
- 没有 `IbInteger`/`IbFloat`/`IbList`/...10 个并行类——大量代码消失。

**例子**：
```
int 42:   IbValue(type_ref=TypeRef("int"), payload=42)
"hello":  IbValue(type_ref=TypeRef("str"), payload="hello")
[1,2,3]:  IbValue(type_ref=TypeRef("list",(TypeRef("int"),)), payload=[IbValue, IbValue, IbValue])
MyClass(x=5): IbValue(type_ref=TypeRef("MyClass"), fields={"x": IbValue(int,5)}, payload=None)
```

### 5.2 一个方法调用的全过程

用户写：`x.foo(1, 2)`，其中 `x: MyClass`。

```
1. VM 拿到 IbValue x
2. ref = x.type_ref                                # TypeRef("MyClass")
3. type_def = registry.resolve(ref)                # TypeDef for MyClass
4. member = type_def.members["foo"]                # MemberDef，kind=METHOD
5. axiom = axiom_registry.get(type_def.axiom_key)  # 通常是 UserClassAxiom
6. axiom.call_method(x, member, [arg1, arg2], vm)
   └ 内部走方法体（编译产物中的字节码/AST），创建新的栈帧执行
```

如果 `x` 是 `int`，则第 5 步拿到的 axiom 是 `IntAxiom`，第 6 步走的是该 Axiom 内置的 `call_method` 实现（直接调用 Python `int` 的对应运算）。

**整个调用链上没有 isinstance 分支**——这是统一 IbValue + Axiom 分发的最大好处。

### 5.3 运行时如何与编译产物对接

解释器启动时：
1. 加载 `CompiledProgram`（纯数据）
2. 用 `CompiledProgram.types` 初始化 `TypeRegistry`
3. 用编译期已绑定的 `axiom_key` 字符串关联到 Python 端 `AxiomRegistry`（启动时注册一次）
4. 开始执行 AST

**重点**：解释器**不重新分析类型**。所有类型信息已经由编译器写好。运行时遇到的所有 TypeRef 都来自编译产物，运行时只能"读取和创建实例"，不能动态创建新类型（除非显式支持 eval / 动态类，那是另一个话题）。

这就实现了你的"编译期解释期良好隔离"——它们通过**纯数据 CompiledProgram** 通信，没有任何函数引用穿越边界。

---

## 第六章：Bootstrap（系统启动顺序）

Bootstrap 必须解决"鸡生蛋"问题：`Object` 的 TypeDef 引用了 `parent=None`，但 `Type` 的 TypeDef 引用了 `parent=TypeRef("Object")`，而构造 TypeRef("Object") 又要求 Object 已经存在。

新设计下 bootstrap 比现在简单得多，因为 TypeRef **不需要**注册表存在就能构造（它只是一个值，可以包含一个尚未注册的名字）。所以流程是纯线性的：

```
Stage 0 — 创建空注册表
    type_registry  = TypeRegistry()
    axiom_registry = AxiomRegistry()

Stage 1 — 注册 Axiom（纯代码注册，无依赖）
    axiom_registry.register("Object",   ObjectAxiom())
    axiom_registry.register("int",      IntAxiom())
    axiom_registry.register("str",      StrAxiom())
    ... 所有内置 Axiom

Stage 2 — 注册根类型 TypeDef
    type_registry.register(TypeDef(
        name="Object", kind=OBJECT, parent=None,
        axiom_key="Object", members={...}))

Stage 3 — 按拓扑顺序注册其他内置 TypeDef
    Primitive (parent=Object)
    int       (parent=Primitive)
    bool      (parent=int)
    str       (parent=Primitive)
    ...
    Container (parent=Object)
    list      (parent=Container, type_params=["T"])
    ...

Stage 4 — 密封注册表
    type_registry.seal()    # 之后不允许改 TypeDef

Stage 5 — 用户代码加载
    用户的 class 声明被编译时追加到 type_registry（在 sealed 之前的 staging 区）
```

**整个 bootstrap 没有任何"先创建空壳，再回填字段"的循环依赖处理**——因为 TypeRef 是值，可以指向暂未注册的名字。注册表在 Stage 4 后会做一次完整性校验（每个 TypeRef 都能解析）。

---

## 第七章：场景演示

### 7.1 场景一：用户写一个类

```ibci
class Animal:
    str name
    
    fn greet() -> str:
        return "I am " + self.name

class Dog(Animal):
    int age
    
    fn bark() -> void:
        print("Woof!")
```

#### 编译期发生的事

**Pass 2（Type Collection）** 看到两个 class 声明，建立骨架：
```
TypeDef(name="Animal", kind=CLASS, parent=TypeRef("Object"),
        type_params=[], members={}, axiom_key="__user_class__")
TypeDef(name="Dog",    kind=CLASS, parent=TypeRef("Animal"),
        type_params=[], members={}, axiom_key="__user_class__")
```

注意 `axiom_key="__user_class__"`——所有用户类共享同一个通用 Axiom，它的行为完全由 TypeDef.members 驱动。

**Pass 3（Member Resolution）** 填充成员：
```
Animal.members = {
    "name":  MemberDef(kind=FIELD,  type_ref=TypeRef("str")),
    "greet": MemberDef(kind=METHOD, type_ref=TypeRef("str"),
                       func_sig=FuncSignature(params=[], returns=TypeRef("str"))),
}
Dog.members = {
    "age":  MemberDef(kind=FIELD, type_ref=TypeRef("int")),
    "bark": MemberDef(kind=METHOD, type_ref=TypeRef("void"),
                      func_sig=FuncSignature(params=[], returns=TypeRef("void"))),
}
# 注意：Dog.members 不包含从 Animal 继承的成员，那是查询时通过 parent 链动态查的
```

**Pass 5/6** 校验方法体：`"I am " + self.name` 通过 `StrAxiom.operator_result("+", TypeRef("str")) → TypeRef("str")` 验证；`self.name` 通过 lookup_member 链找到字段，类型对得上。

**编译产物**包含 Animal 和 Dog 的完整 TypeDef，连同方法体的 AST。**没有任何 Python 类被生成**，没有 vtable 被构建。

#### 运行时发生的事

解释器加载 CompiledProgram，把 Animal 和 Dog 的 TypeDef 注册进 `type_registry`。**就这样**。

当用户执行 `dog = Dog()` 时：
1. VM 看到 `Dog` 标识符 → 查 symbol → 这是一个 Type 类型的值
2. VM 看到调用 → 调用 UserClassAxiom.construct
3. UserClassAxiom 创建 `IbValue(type_ref=TypeRef("Dog"), fields={"name": <None>, "age": <None>})`
4. 如果有 `__init__`，调用之

调用 `dog.greet()`:
1. lookup_member("greet") on type_ref=TypeRef("Dog") → 在 Dog.members 没找到 → 沿 parent 链 → 在 Animal.members 找到
2. 拿到 MemberDef，看到 kind=METHOD → 启用方法调用栈帧
3. 执行方法体 AST

**整个继承链就是 `parent: TypeRef` 这一个字段递归走出来的。简单得过分。**

### 7.2 场景二：用户定义一个变量

```ibci
list[int] nums = [1, 2, 3]
Optional[Dog] my_dog = None
```

#### 编译期

**Pass 4（Symbol Resolution）** 看到声明：
- `nums` 的符号项：`type_ref = TypeRef("list", (TypeRef("int"),))`
- `my_dog` 的符号项：`type_ref = TypeRef("Optional", (TypeRef("Dog"),))`

**Pass 5（Type Inference）** 看到右侧表达式：
- `[1, 2, 3]` → 推断为 `TypeRef("list", (TypeRef("int"),))`
- `None` → `TypeRef("None")`

**Pass 6（Type Checking）**:
- 调用 `ListAxiom.can_assign_from(src=list[int], target=list[int])` → True ✓
- 调用 `OptionalAxiom.can_assign_from(src=None, target=Optional[Dog])` → True（因为 Optional[T] 总能接受 None） ✓

#### 运行时

执行 `nums = [1, 2, 3]`:
1. 字面量 `[1,2,3]` → ListAxiom.construct → `IbValue(type_ref=TypeRef("list",(int,)), payload=[IbValue(int,1), IbValue(int,2), IbValue(int,3)])`
2. 把这个 IbValue 写入当前作用域 `nums` 槽

执行 `nums[0]`:
1. 看到 subscript 操作 → axiom.subscript(nums_value, key=IbValue(int,0))
2. ListAxiom.subscript：直接 `nums.payload[0]` 返回，**已经是 IbValue**，无需装箱

注意 `nums.type_ref` 的 args 部分（`(TypeRef("int"),)`）让 `subscript` 调用时能精确知道返回类型是 int。**泛型实参随值走**，不依赖外部上下文。

---

## 第八章：泛型与可空性

### 8.1 泛型工作机制

泛型的全部秘密在两件事：

**① 泛型类型 = TypeDef 上有 `type_params`**
```
TypeDef(name="list", kind=CONTAINER, type_params=["T"], members={
    "__getitem__": MemberDef(type_ref=TypeRef("T"), 
                             func_sig=FuncSignature([("idx", TypeRef("int"))], TypeRef("T"))),
    "append":      MemberDef(func_sig=FuncSignature([("item", TypeRef("T"))], TypeRef("void"))),
    ...
})
```

**② 特化 = 用 TypeRef.args 替换 TypeRef("T")**

辅助函数 `substitute(ref, mapping)`:
- 如果 `ref.head` 是形参名（`"T"`）且在 mapping 中 → 返回 mapping[ref.head]
- 否则递归 args：`TypeRef(ref.head, tuple(substitute(a, mapping) for a in ref.args), ref.module)`

`member_lookup` 流程：
```
list[int].__getitem__:
    type_ref = TypeRef("list", (TypeRef("int"),))
    type_def = resolve(type_ref) → list 的 TypeDef
    raw_member = type_def.members["__getitem__"]  # type_ref=TypeRef("T")
    mapping = {"T": TypeRef("int")}                # 由 args 与 type_params 配对生成
    specialized_type_ref = substitute(TypeRef("T"), mapping) → TypeRef("int")
    return MemberDef(type_ref=TypeRef("int"), ...)
```

**整个特化机制是一个纯函数**，无状态，无需缓存（虽然可以缓存）。这比当前那种"为每个 list[int] 实例造一个 ListSpec 然后注册"的设计简洁数十倍。

### 8.2 可空性：用 Optional[T] 而不是布尔标志

我推荐**完全删除任何 nullable 字段**，改用 `Optional[T]` 类型构造器。原因：

| 设计 | 缺点 |
|------|------|
| `IbSpec.is_nullable: bool`（现状） | 每个变量都默认 nullable=True，编译器实际上没在做空安全检查 |
| TypeRef 上加 nullable 标记 | TypeRef 不再纯净，破坏哈希一致性，需要特殊处理 |
| **Optional[T]** | 与泛型机制完全一致；非空就是非空，要可空就显式包装 |

**Optional[T] 的实现：**

它就是注册表里的一个普通泛型 TypeDef：
```
TypeDef(name="Optional", kind=SPECIAL, type_params=["T"],
        parent=TypeRef("Object"), axiom_key="Optional", members={...})
```

`OptionalAxiom`:
- `can_assign_from(src, Optional[T])`: 接受 `T` 或 `None` 或 `Optional[T]`
- 提供 `unwrap()`、`or_else(default)`、`is_some()` 等方法

用户代码：
```ibci
Optional[int] maybe_x = None        # OK
int x = 5                            # OK，编译期保证不为 None
int y = None                         # ❌ 编译错误：can_assign_from(None, int) = False
int z = maybe_x                      # ❌ 编译错误：必须 unwrap
int w = maybe_x.or_else(0)           # ✓
```

**这才是真正的"静态强类型 + 空安全"**。不会出现运行时空指针，因为编译器在源头就拒绝了可疑赋值。

`int? x` 这种 Kotlin/Swift 风格的语法糖可以在 parser 层 desugar 成 `Optional[int]`，零成本。

---

## 第九章：IBCI 类型系统的明确身份

经过上面的设计，我可以**正式给 IBCI 类型系统下定义**：

> **IBCI 是一个静态名义类型语言，采用渐进类型系统（gradual typing），通过 `Optional[T]` 实现空安全，并以 LLM 语义类型作为原创扩展。**

逐条解释：

| 性质 | 对 IBCI 的具体表现 |
|------|------------------|
| **静态** | 所有类型在编译期确定。运行时不做类型推断，只做类型分发 |
| **名义** | `class A` 和 `class B` 即使结构相同也是不同类型；继承通过 `extends` 显式建立 |
| **强类型** | 不存在隐式转换：`int + str` 是编译错误，必须显式 `cast_to` |
| **渐进** | `any` 是逃生阀：变量声明为 `any` 后，类型检查在该变量上停用，但运行时仍是强类型 |
| **空安全** | 默认所有类型非空；`Optional[T]` 显式声明可空 |
| **LLM 扩展** | `behavior`、`@~...~`、LLM 异常族是普通类型——它们和 int 一样在系统里是平等公民，不是"特殊语法" |

这一段定义应该写进 `docs/IBCI_TYPE_SYSTEM.md` 的第一行，作为**所有未来设计决策的判断标准**——任何新提案都要回答："这违反了静态/名义/强/渐进/空安全/LLM 扩展中的哪一条？为什么例外？"

---

## 第十章：与现有代码的映射（让你能评估改造量）

为了让你能判断这个方案的可行性，我给出**新结构 → 旧结构**的对应：

| 新概念 | 替代旧代码 |
|--------|----------|
| `TypeRef` | 替代所有 `xxx_type_name: str` + `xxx_type_module: Optional[str]` 的字段对 |
| `TypeDef` (单类) | 替代 `IbSpec` + `FuncSpec` + `ClassSpec` + `ListSpec` + `TupleSpec` + `DictSpec` + `BoundMethodSpec` + `ModuleSpec` + `EnumSpec` + `DeferredSpec`（共 ~10 个类） |
| `Axiom` 接口 | 与现有 `protocols.py` 的 `TypeAxiom` + `CallCapability`/`IterCapability`/... 大致对应，但合并为单一接口（不再 7 个 capability 协议） |
| `IbValue` (单类) | 替代 `IbObject` + `IbInteger` + `IbFloat` + `IbString` + `IbBool` + `IbList` + `IbDict` + `IbTuple` + `IbNone` + `IbLLMUncertain` + `IbDeferred` + `IbBehavior` + `IbBoundMethod` + `IbNativeFunction` + `IbNativeObject` + `IbModule` + `IbClass` 中的**值层部分** |
| `Optional[T]` 内置 TypeDef | 替代散落在每处的 `is_nullable: bool` 检查 |

**预期净代码减少**：
- `core/kernel/spec/` 当前约 1500 行 → 预计 ~600 行
- `core/runtime/objects/` 当前约 2000 行 → 预计 ~700 行
- `core/kernel/axioms/` 大致持平（逻辑总量相同，只是接口更统一）

**总减少约 1500-2000 行，外加大量 isinstance 分支消失带来的可读性提升。**

---

## 第十一章：迁移路径（如果决定执行）

我假设你不会一次性全换（即使你说不在意成本，工程上也应当分阶段以保证 1056 测试始终绿色）。我建议的最小可独立推进的阶段：

| 阶段 | 内容 | 风险 | 测试影响 |
|------|------|------|---------|
| **M1** | 引入 TypeRef 类，所有 spec 字段从 `xxx_name+xxx_module` 改为 `xxx_ref: TypeRef`。**保留** IbSpec 子类层级 | 中 | 全程保持 1056 通过 |
| **M2** | 引入 `Optional[T]`，删除 `is_nullable` 字段，更新 `is_assignable` | 低 | 加新测试，旧测试通过 |
| **M3** | 把 `IbSpec` 子类全部折叠为单个 `TypeDef` + `kind` 字段 | 高 | 大面积改动，需逐文件验证 |
| **M4** | 把运行时 `IbXxx` 对象族折叠为 `IbValue` + `payload` | 高 | 最大风险，但代码净减少最多 |
| **M5** | Axiom 接口合并（去掉 7 个 capability 协议） | 中 | 内部重构，行为不变 |

每个阶段独立可发布，独立可回滚。M1+M2 完成就已经显著改善现状；M3-M5 是把改善推到极致。

---

## 总结：我向你交付的设计原则清单

1. **三层分离**：TypeRef（地址）/ TypeDef（内容）/ Axiom（行为），每层职责清晰
2. **单一 TypeDef 类**：不再 10 个并行 Spec 子类，用 kind 字段区分
3. **单一 IbValue 类**：不再 17 个 IbXxx 对象，用 type_ref + payload 区分
4. **Object 唯一根**：所有内核类型显式 `parent → ... → Object`，与用户层一一对应
5. **TypeRef 是纯值**：可哈希、可序列化、递归结构化，泛型天然支持
6. **编译产物纯数据**：CompiledProgram 是注册表 + AST + 标注，可 dump 可 load
7. **Axiom 是唯一行为入口**：编译期推断与运行时执行共享同一份逻辑
8. **空安全用 Optional[T]**：删除 nullable 标志，类型系统真正能拦住空指针
9. **类型系统身份明确**：静态 + 名义 + 强 + 渐进 + 空安全 + LLM 扩展

---

## 我建议你接下来做的决策

在你下令开工之前，我希望你只回答 **3 个问题**：

1. **第三章的类型继承树**（Object 唯一根，Primitive/Container/Callable 抽象中间层）你接受吗？是否需要调整 IBCI 用户可见的层级？
2. **第八章的可空性方案**（删除 nullable 标志，全面用 Optional[T]）你接受吗？这会影响所有现有的可空赋值代码。
3. **第十一章的迁移阶段**你倾向于走完 M1-M5 全程，还是先到 M2 看效果再决定？

这三个问题确认后，我就有足够明确的指令开始 M1 阶段的实施了。在那之前我不会动一行代码——这正是你说的"我无法下达让你开始工作的指令"应有的对待方式。
