# IBCI 类型系统设计

> 本文档是 IBCI 类型系统的正式设计文档，与当前代码（`core/kernel/spec/`、`core/kernel/axioms/`、`core/runtime/objects/`）严格对齐。
>
> 面向需要扩展或验证类型系统的编译器/运行时开发者。覆盖类型描述体系（`IbSpec`/`TypeDef`）、公理驱动分派、可空性/泛型/签名形态，以及类型在序列化与值层的呈现。阅读前需了解 AST 节点类型（`docs/architecture/02_metadata_ast.md`）。
>
> **路径说明**：以下模块为包结构（目录），正文中 `*.py` 路径请以实际目录为准：
> `kernel/spec/registry/`、`kernel/axioms/primitives/`、`runtime/objects/{primitives,kernel}/`、
> `runtime/vm/handlers/`、`runtime/interpreter/llm_executor/`。

---

## §1 三件套核心概念

IBCI 类型系统由 **TypeRef / TypeDef（IbSpec）/ TypeAxiom** 三个层级承载，分别对应"地址 / 内容 / 行为"。

| 概念 | 角色 | 文件位置 | 关键性质 |
|------|------|---------|---------|
| `TypeRef` | 类型引用（"地址"） | `core/kernel/spec/type_ref.py` | 不可变、可哈希、递归结构化、无注册表依赖 |
| `IbSpec` / `TypeDef` | 类型定义（"内容"） | `core/kernel/spec/base.py` | 纯数据；统一一个 `TypeDef` 类，按 `kind` 字段分派 |
| `TypeAxiom` | 类型行为（"虚表"） | `core/kernel/axioms/protocols.py`、`primitives.py` | 单一统一接口；通过 `has_*_cap` 类属性声明能力 |

三者协作：
```
AST / 符号表 ──持有── TypeRef
                       │ resolve(ref, registry)
                       ▼
                  SpecRegistry ──持有── IbSpec / TypeDef
                       │ get_axiom(spec)
                       ▼
                  AxiomRegistry ──持有── TypeAxiom 实例
```

---

## §2 TypeRef — 类型引用层

### 2.1 数据结构

`core/kernel/spec/type_ref.py:TypeRef`：

```python
@dataclass(frozen=True)
class TypeRef:
    head:   str                  # 基础类型名（"int" / "list" / "MyClass"）
    args:   Tuple["TypeRef",...] # 泛型实参，空元组表示非泛型
    module: Optional[str]        # 跨模块限定符（None 表示当前/内置）
```

### 2.2 关键性质

- **不可变 + 可哈希**：可作为 `dict` key、可放入 `set`，被序列化器、缓存、特化解析复用。
- **递归结构化**：`list[dict[str,int]]` 直接以 `TypeRef("list", (TypeRef("dict", (TypeRef("str"), TypeRef("int")))))` 表达，不依赖字符串拼接。
- **零注册表依赖**：构造一个 `TypeRef` 不需要任何全局状态，纯值。

### 2.3 工厂与衍生属性

| 入口 | 用途 |
|------|------|
| `TypeRef.of(name, module=None)` | 标准化构造 |
| `TypeRef.generic(head, args, module=None)` | 泛型构造（`list[T]` / `dict[K,V]` / `Optional[T]`） |
| `TypeRef.from_spec(spec)` | 从已注册 `IbSpec` 桥接构造 |
| `TypeRef.replace_head(new_head)` | 替换头名（用于哨兵切换：`auto`→`void` 等） |
| `TypeRef.substitute(mapping)` | 泛型形参替换（递归） |
| `canonical_name` | 规范字符串（如 `"list[dict[str,int]]"`） |
| `qualified_name` | `"module.head"`（带模块限定符时） |

---

## §3 IbSpec / TypeDef — 类型定义层

### 3.1 单一统一类

`core/kernel/spec/base.py:TypeDef` 是**所有类型种类**的统一定义类，**没有** `FuncSpec` / `ClassSpec` / `ListSpec` 等子类。差异通过 `kind` 字段分派。

```python
@dataclass(eq=False)
class TypeDef(IbSpec):
    # ── 通用 ──────────────────────────────────────
    name:           str
    module_path:    Optional[str]
    kind:           str  # 见 TypeKind
    provenance:     Provenance       # 来源：KERNEL_NATIVE / AXIOM_PROVIDED / USER_DEFINED / EXTERNAL_MODULE
    visibility:     Visibility       # 可见性：PRELUDE_VISIBLE / IMPORT_GATED / SCOPE_PRIVATE
    storage_model:  StorageModel     # 存储模型：MEMORY_BACKED / DISK_BACKED
    members:        Dict[str, MemberSpec]
    _axiom_name:    Optional[str]    # axiom 查询 key 重定向

    # ── 函数签名（FUNCTION / BOUND_METHOD / CALLABLE_INSTANCE / CALLABLE_SIG）
    param_types:    List[TypeRef]
    return_type:    TypeRef
    param_descriptors: List[ParamDescriptor]   # 参数名/种类/默认值存在性（FUNCTION，见 §3.6）

    # ── 类继承（CLASS）
    parent_type:    Optional[TypeRef]

    # ── 容器（LIST / TUPLE / DICT）
    element_type:   TypeRef
    allowed_element_types: List[TypeRef]   # 兼容性检查用的允许元素类型集合（与 element_type 并列）
    key_type:       TypeRef
    value_type:     TypeRef                # DICT 的 value 类型，CALLABLE_INSTANCE 的载值类型

    # ── Optional[T]（OPTIONAL）
    wrapped_type:   TypeRef

    # ── 绑定方法（BOUND_METHOD）
    receiver_type:  TypeRef
    func_spec_name: str

    # ── callable 签名约束（CALLABLE_SIG）
    required_capabilities: List[str]
```

### 3.2 TypeKind 枚举

`core/kernel/spec/base.py:TypeKind`：

| 枚举值 | 含义 | 典型实例 |
|--------|------|---------|
| `PRIMITIVE` | 标量基础类型 | `int` / `float` / `str` / `bool` / `void` / `any` / `auto` / `None` / `slice` |
| `FUNCTION` | 函数类型（含 `fn` 哨兵；`callable` 为内部基类名，非用户可写类型） | 用户 `func`、内置函数、`fn` 推导 |
| `CLASS` | 类（含内置 Exception 系列） | 用户类、`Enum` / `Exception` / `Intent` |
| `LIST` / `TUPLE` / `DICT` | 容器 | `list[int]` 等 |
| `OPTIONAL` | 空安全包装 | `Optional[T]` |
| `BOUND_METHOD` | 已绑定接收者的方法 | `obj.method` 取值 |
| `MODULE` | 模块命名空间 | `import` 后的模块对象 |
| `CALLABLE_INSTANCE` | lambda/snapshot/behavior 产生的可调用实例 | `fn_callable` / `behavior` |
| `CALLABLE_SIG` | 高阶函数签名约束 | `fn[(int)->int]` |
| `LAZY` | 跨模块未解析占位符 | 编译期 forward ref |

> `TypeKind.CALLABLE_INSTANCE` 统一 fn_callable 与 behavior 两类可调用实例；区分仅由 `name`（`"fn_callable"` / `"behavior"`）或 `_axiom_name` 决定，不再是类型层语义。

### 3.3 字段存储规范

- **TypeRef-only**：所有指向"其他类型"的字段全部以 `TypeRef` 存储，访问统一走 `spec.X.head` / `spec.X.module` / `spec.X.canonical_name`。
- **MemberSpec 同样 TypeRef 化**：`core/kernel/spec/member.py:MemberSpec.type_ref`、`MethodMemberSpec.return_type` / `param_types` 均为 TypeRef。类方法另以 `MethodMemberSpec.param_descriptors` 携带参数描述符（与 `TypeDef.param_descriptors` 对齐，见 §3.6），由 `_declaration_visitors._sync_class_member` 同步，供方法覆写契约校验消费。
- **MethodMemberSpec 变异声明**：`MethodMemberSpec.mutating: bool`（默认 False）声明该方法是否修改接收者状态；`MethodMemberSpec.llmexcept_safe: bool`（默认 False）标记该方法在 llmexcept body 内对被保护变量的调用是否被豁免。这两个字段是 `SEM_LLMEXCEPT_MUTATING_CALL` 编译期检查的公理层数据源，由 `binding_analysis_pass.py` 在 BindingPhase 消费。
- **线协议保留**：序列化 / 反序列化（`core/compiler/serialization/`）仍把 TypeRef 解构为字符串字段（`return_type_name` / `parent_module` 等）以保持向后兼容；in-memory 模型纯 TypeRef。

### 3.4 注册表 SpecRegistry

`core/kernel/spec/registry.py:SpecRegistry` 是 IBCI 类型系统的**核心门面**：

| 方法 | 作用 |
|------|------|
| `resolve(name, module=None)` | 按名字查找 spec |
| `resolve_typeref(ref)` | 按 TypeRef 查找；带模块优先，回落裸名 |
| `register(spec, ...)` | 注册新 spec（克隆原型） |
| `resolve_specialization(base, args)` | 按需创建/缓存 `list[int]` 等泛型特化 spec |
| `is_assignable(src, target)` | 类型兼容性检查（含 Optional / 类继承链 / 公理委托） |
| `get_base_spec(spec)` | 取泛型特化的底 spec（`list[int]` → `list`） |
| `get_axiom(spec)` | 桥接 AxiomRegistry，按 `spec.get_base_name()` / `_axiom_name` 查询 |
| `get_call_cap` / `get_converter_cap` / `get_parser_cap` / `get_from_prompt_cap` / `get_llm_output_hint_cap` | 能力门：返回公理（声明对应能力时）或 `None` |
| `resolve_call_return(spec, args)` / `resolve_op` / `resolve_iter_element` / `resolve_subscript` | 编译期类型推断入口（iter/subscript/operator 经 `resolve_*` 推断，非独立能力门） |

注册表持有的 spec 是原型的克隆，保证多引擎实例间状态隔离（`SpecRegistry.register` 内部 `clone()`）。

### 3.4bis TypeRef 唯一权威入口

TypeRef 生命周期两端口径必须收敛，避免"结构化 vs 扁平化"两套表示漂移。扁平
`TypeRef('Vec[T]')` 的 head 含方括号、args 为空，`substitute` 无法替换；
`resolve(head)` 消费泛型 TypeRef 会丢失实参：

| 方向 | 唯一权威入口 | 禁止 |
|------|-------------|------|
| **构造**（spec → TypeRef） | `TypeRef.from_spec(spec)` | `TypeRef.of(泛型名)`（如 `of("list[int]")`）；需手写 per-type 分支 |
| **解析**（TypeRef → spec） | `SpecRegistry.resolve_typeref(ref)` | `resolve(ref.head)` 消费泛型 TypeRef（丢实参） |
| **字符串 → 结构** | `TypeRef.parse(name)`（递归嵌套解析） | 手写字符串切分/扁平 `of` |

- 泛型类方法参数 descriptor 构造必须走 `from_spec`（`_param_type_ref`），保证特化
  `substitute` 可替换。
- 表达式位置泛型下标（`Box[list[int]]` 作表达式）须复用 `_resolve_type` 递归解析，
  与注解路径同构，保证编译期特化注册。
- 运算符结果类型推断须经 `resolve_typeref(return_type)` 保留实参。
- 例外：`scheduler._spec_to_typeref` 的 FUNCTION/BOUND_METHOD/CALLABLE 分支产出
  `fn[...]` 签名形态，是模块导入导出专用（head 语义与 `fn_callable` 不同），非重复实现。
- **创建点结构化**：`GenericTypeDeclaration.build` 接受结构化实参 `List[TypeRef]`
  （非字符串），`SpecFactory.create_*` 类型承载字段经 `TypeRef.parse` 结构化——
  嵌套泛型实参（`list[list[int]]`）不再扁平化，`substitute` 可穿透。
- **声明驱动序列化/还原**：`GenericTypeDeclaration.payload_fields` 声明泛型承载字段，
  serializer/rehydrator 据此统一收集/还原（消除 per-kind 手工分支）。

### 3.5 SpecFactory

`core/kernel/spec/registry.py:SpecFactory` 提供面向编译器的**字符串入口**（`*_name` / `*_module`），内部统一桥接到 TypeRef 后写入 TypeDef 字段。这是仅有的"字符串构造 API"，TypeDef 本身不接受字符串 kwargs。

| 方法 | 用途 |
|------|------|
| `create_primitive(name)` | 标量类型 |
| `create_func(name, param_type_names, return_type_name, provenance, visibility, ...)` | 函数 spec（用户 func / 插件 vtable / 内置） |
| `create_class(name, parent_name, provenance, visibility)` | 用户类 / 内置类 |
| `create_list / create_tuple / create_dict` | 容器特化 |
| `create_optional(wrapped_name)` | Optional[T] |
| `create_bound_method(...)` | 绑定方法 |
| `create_fn_callable(...)` | fn_callable 签名实例 |
| `create_behavior(value_type_name)` | behavior 实例 |

### 3.6 参数描述符 ParamDescriptor

**ParamDescriptor**（`core/kernel/spec/member.py`）是单个可调用参数的解析后描述：名称、种类、类型引用、默认值存在性。用户函数、LLM 函数与原生模块函数共用这一结构，使语义层实参解析与 vtable 声明共享同一数据形态。

**继承/组合关系**：独立 frozen dataclass；被 `TypeDef.param_descriptors`（用户/LLM 函数）与 `MethodMemberSpec.param_descriptors`（类方法与模块成员）持有。

**字段**：

| 字段 | 语义 |
|------|------|
| `name` | 参数名 |
| `kind` | 参数种类，对齐 `core.kernel.ast` 的 `ARG_*` 常量（见 `docs/architecture/02_metadata_ast.md` §2.5） |
| `type_ref` | 参数类型（TypeRef） |
| `has_default` | 是否带默认值 |
| `default_value` | 原生默认字面值；仅原生模块声明使用，其余为 `None` |

**核心不变量**：
- `param_types` 只存类型；`param_descriptors` 携带名称、种类、默认值存在性，二者并列，实参解析以描述符为权威。
- 描述符在 type-check 阶段构建（`_declaration_visitors._build_function_signature`），用户函数与 LLM 函数对称精化；类方法由 `_sync_class_member` 同步到成员表。
- 用户级函数默认值是 AST 表达式，运行期惰性求值，描述符只记 `has_default=True`；原生模块函数默认值是声明给出的 Python 字面值，存入 `default_value`。

**与其他机制的交互**：
- 语义层 `visit_IbCall` 以描述符为权威做结构/类型校验（见 §5.1 编译期调用）。
- 语义层与运行期共用同一绑定算法核心（`core/kernel/arg_binding.py`），见 `docs/architecture/04_vm_interpreter.md` §2.6。
- 原生模块函数的描述符由 discovery 从 vtable `params` 声明构建（格式见 `docs/subsystems/04_plugin_system.md` §4）。

---

## §4 TypeAxiom — 行为分派层

### 4.1 统一 Protocol

`core/kernel/axioms/protocols.py:TypeAxiom` 是**单一**的能力接口；9 个分散 Capability 协议（`CallCapability` / `IterCapability` / `SubscriptCapability` / `OperatorCapability` / `ConverterCapability` / `ParserCapability` / `FromPromptCapability` / `OutputHintCapability` / `WritableTrait`）的职责归并于此。

```python
@runtime_checkable
class TypeAxiom(Protocol):
    @property
    def name(self) -> str: ...

    # 能力声明（默认 False，子类按需置 True）
    has_call_cap:        bool
    has_iter_cap:        bool
    has_subscript_cap:   bool
    has_operator_cap:    bool
    has_converter_cap:   bool
    has_parser_cap:      bool
    has_from_prompt_cap: bool
    has_output_hint_cap: bool
    has_llm_call_cap:    bool

    # 能力方法（默认 no-op）
    def resolve_return_type_name(args)         -> Optional[str]: ...
    def get_element_type_name()                -> str:           ...
    def resolve_item_type_name(key_name)       -> Optional[str]: ...
    def resolve_operation_type_name(op, other) -> Optional[str]: ...
    def can_convert_from(source_name)          -> bool:          ...
    def parse_value(raw)                       -> Any:           ...
    def from_prompt(raw, spec)                 -> Tuple[bool,Any]: ...
    def __outputhint_prompt__(spec)            -> str:           ...

    # 元数据
    def get_method_specs() -> Dict[str, MethodMemberSpec]: ...
    def get_operators()    -> Dict[str, str]:               ...
    def is_dynamic()       -> bool: ...
    def is_compatible(other_name) -> bool: ...
    def is_class()         -> bool: ...
```

### 4.2 BaseAxiom

`core/kernel/axioms/primitives/base.py:BaseAxiom` 提供安全 no-op 默认（所有 `has_*_cap = False`、能力方法返回 `None` / `False` / 空集）。具体公理只重写需要的部分；不再多重继承能力 mixin。

### 4.3 字符串边界

公理层能力方法只接受/返回**字符串类型名**（`"int"` / `"list[int]"` / `"any"` 等）。这维持了"axiom 能力逻辑不依赖 spec 层查询/解析"的单向边界——SpecRegistry 调用公理时把 spec 名字串过去，把字符串结果再 resolve 成 spec 返回给调用方。

边界细则：axiom 层可 import `core.kernel.spec` 的**原子数据结构构造器**（`TypeRef` / `MethodMemberSpec`，用于声明协议方法签名），但不得依赖 spec 层的注册表/解析逻辑（`SpecRegistry` 查询、`resolve_*`）。

### 4.4 内置公理清单

`core/kernel/axioms/registry.py:AxiomRegistry` 注册的公理（节选）：

| Axiom | 类型 | 关键能力 |
|-------|------|---------|
| `IntAxiom` / `FloatAxiom` / `StrAxiom` / `BoolAxiom` / `NoneAxiom` | 标量 | `operator` / `converter` / `parser` / `from_prompt` |
| `ListAxiom` / `TupleAxiom` / `DictAxiom` | 容器 | `iter` / `subscript` / `operator(+,in)` |
| `OptionalAxiom` | Optional[T] | `is_compatible` / unwrap 方法集 |
| `EnumAxiom` | 枚举类 | `is_class=True` / `from_prompt`（按字面值解析） |
| `CallableAxiom` / `BoundMethodAxiom` / `FnCallableAxiom` / `BehaviorAxiom` | 可调用 | `call_cap` |
| `IntentContextAxiom` | 意图上下文 | `is_class=True` |
| `LlmCallResultAxiom` | LLM 调用结果 | 内核内部类型（不参与常规运算，不可用户声明） |
| `ExceptionAxiom` / `LLMErrorAxiom` 系列 | 异常 | 类继承链 |

---

## §5 编译期 ⇄ 运行期分派路径

### 5.1 编译期调用

```
Pass 4/5 SemanticAnalyzer
  └── 表达式类型推断 / 调用返回类型 / 运算结果类型
        └── SpecRegistry.resolve_call_return(spec, args)   — 函数 / callable_instance / class 构造
        └── SpecRegistry.resolve_op(spec, op, other)       — 二元 / 一元运算
        └── SpecRegistry.resolve_iter_element(spec)        — for 元素类型
        └── SpecRegistry.resolve_subscript(spec, key_spec) — `obj[key]`
              └── 内部按 spec.kind 直分派；其余委托 axiom.resolve_*_type_name
```

实参解析在 `visit_IbCall` 按调用体可用的静态签名选择策略：

| 策略 | 触发条件 | 解析内容 |
|------|---------|---------|
| ① 全量解析 | 有 `param_descriptors`（用户/LLM 函数、已声明参数的 vtable 模块函数） | 位置 → 具名 → 默认填充 → varargs/varkw；结构/类型错误用 SEM_* 码报告 |
| ② 轻量检查 | 仅 `param_types`（`fn[...]` 签名约束、容器特化方法） | 只做位置数量与类型检查 |
| ③ 动态跳过 | 无静态签名（内置构造器 / axiom-backed） | 不报告 |

三策略的输入统一为调用体的位置 / 具名 / splat 实参列表，输出位置实参类型列表供返回类型推断使用。

策略①的绑定算法与运行期同源，收敛于 `core/kernel/arg_binding.py`（共享纯核心，见 §3.6 交互与 `docs/architecture/04_vm_interpreter.md` §2.6）。

### 5.2 运行期调用（VM 层）

```
VMExecutor handler
  └── 取值 IbValue → ib_class.spec → SpecRegistry.get_axiom(spec)
        └── axiom.parse_value / from_prompt / __outputhint_prompt__   — LLM 路径
        └── axiom.resolve_operation_type_name                          — 仅诊断 / dump，不参与运行
  └── 运行期取分支不再走 isinstance(IbXxx)；统一通过 IbValue + ib_class.name + spec.kind
```

> 运行期的"做"（数学加法、列表 append 等）由具体 `IbValue` 子类的方法实现，而非走 axiom；axiom 在运行期只承担 LLM 边界（`from_prompt` / `parse_value` / `__outputhint_prompt__`）。

### 5.3 跨模块类型占位

跨模块未解析符号在编译期经 `scheduler` 预注册空的 `ModuleMetadata`（`create_module`）占位（`core/compiler/scheduler.py`）；模块类型判定经 `is_module_spec`（先查 `spec.kind == MODULE`）。解析阶段强制成功，**异常**情况应抛错而非静默回填（见 `01_principles.md §5.3`）。

---

## §6 运行时值层（IbValue 单一承载）

> 所有运行时值统一通过 `core/runtime/objects/kernel/base.py:IbValue` 承载；`IbInteger` / `IbFloat` / `IbString` / `IbBool` / `IbList` / `IbTuple` / `IbDict` / `IbNone` / `IbLLMUncertain` / `IbLLMCallResult` / `IbFnCallable` / `IbBehavior` 是该模型的子体系。

### 6.1 IbValue 四元结构

```python
class IbValue(IbObject):
    __slots__ = ('type_ref', 'payload', 'meta')

    type_ref: TypeRef                  # 运行时类型身份（结构化）
    payload:  Any                      # 标量原值 / 容器底层 / callable handle
    fields:   Dict[str, Any]           # 来自 IbObject：实例字段（CLASS 类型用）
    meta:     Dict[str, Any]           # callable 闭包 / capture_mode / call_intent 等
```

### 6.2 储值约定

| 子类 | payload 用途 | 备注 |
|------|-------------|------|
| `IbInteger / IbFloat / IbString / IbBool` | 原生 Python 标量 | `value` 属性 = `payload` 别名；`__slots__=()` |
| `IbList / IbTuple` | Python `list` / `tuple`，元素均为 `IbValue` | `elements` 属性等价于 `payload` |
| `IbDict` | dict（同步镜像在 `IbObject.fields`） | — |
| `IbFnCallable` | 目标 AST 节点 uid | `meta` 持有 `closure` / `capture_mode` / `params` 等 |
| `IbBehavior` | 同上 | 额外 `call_intent`（`@!` 排他意图） |

### 6.3 类型分派要点

- `isinstance(obj, IbValue) and obj.ib_class.name == "list"` 是分派 list 类型的惯用法（`IbClass` 自指 `ib_class=self` 会让裸 `ib_class.name` 误中，必须先做 `IbValue` 判定）。**内置泛型特化值（`list[int]`）沿 spec 基类名分派**：特化类 `ib_class.name` 含方括号（`"list[int]"`），值层 kind 判定统一走 `spec.get_base_name()`（如 `runtime_serializer._value_base_name` / `deep_clone._value_base_name` / `base.is_sequence_value`），基类名 `"list"` 命中。
- 容器分派收敛为单一判定入口：`core/runtime/objects/kernel/base.py:is_sequence_value(value)`（原生序列 list/tuple 判断，沿 spec 基名），VM 与 intrinsics 统一经它。
- 工厂入口：`core/runtime/factory.py:RuntimeObjectFactory` 提供 `create_int / create_str / create_list / create_tuple / create_dict / create_fn_callable / create_behavior` 等方法，**不**在调用方导入具体类。内置泛型特化值（`list[int]`）由特化类水化（ArtifactLoader 加载期预创建 + VM 字面量 handler 绑定）承载。
- **句柄类值身份物化**：`thread/chan/slot/generator/thread_result` 值经声明类型上下文 rebind 特化类（`_check_type` 在赋值绑定点生效，仅限值承载句柄 kind）——`type(thread[int]值)=thread[int]`，运行时区分 `thread[int]`/`thread[str]`（any 逃生路径 `RUN_TYPE_MISMATCH`）。`get_base_name()` 单义（特化 spec 读 `base_name` 字段返回族名），值层 kind 分派统一沿族名。

### 6.4 类角色分工（设计决策）

值层具体类（`IbInteger` / `IbString` / `IbList` / …）**不是**需要折叠消除的平行结构，而是**领域方法的实现载体**——`IbValue` 提供统一值形态（`type_ref`/`payload`/`fields`/`meta`），具体类各自实现其领域行为（`IbString.upper`、`IbList.append`、运算符 dunder 等），经 `_reg_native`/`_auto_bind_operators` 挂类注册、走 vtable 调用。

**不折叠为单一 `IbValue`**：
- 折叠的原始动机（消除 `isinstance(IbXxx)` 分派）已通过 `isinstance(obj, IbValue) and obj.ib_class.name` 统一分派达成——运行时精确 `isinstance` 具体值类分派仅剩类内运算符重载处。
- 具体类的存在价值是**领域方法归属**（单一职责），非类型分派依据；折叠会把 180+ 方法灌入巨型 `IbValue`，违反单一职责。
- 值身份权威已是 `type_ref`（单一源），具体类不构成第二个身份源。

**分工规则**：
- `IbValue` = 统一值载体（值形态 + 身份）。
- 具体类 = 领域方法实现载体（行为），按 `ib_class.name` 分派。
- `IbNone` / `IbLLMUncertain` / `IbOptional` 为哨兵值，身份判断用 `isinstance`（Python 惯用）；`IbLLMCallResult` 的不确定性判断用 `is_uncertain` 属性。

---

## §7 fn / lambda / snapshot / behavior 类型语义

### 7.1 表达式侧产物

| 源语法 | AST 节点 | 运行时值 | 类型 |
|--------|---------|---------|------|
| `lambda(...) -> T: EXPR` | `IbLambdaExpr(capture_mode="lambda")` | `IbFnCallable` | `TypeKind.CALLABLE_INSTANCE`，name=`fn_callable`，value_type=T |
| `snapshot(...) -> T: EXPR` | `IbLambdaExpr(capture_mode="snapshot")` | `IbFnCallable`（snapshot 模式） | 同上 |
| `@~ ... ~`（含 `@! ...`） | `IbBehaviorExpr` | `IbBehavior` | `TypeKind.CALLABLE_INSTANCE`，name=`behavior` |

> `lambda` / `snapshot` 不是 behavior 专属包装；`IbLambdaExpr` 覆盖任意表达式 body，semantic pass 按 body 是否为 `IbBehaviorExpr` 分流到 `fn_callable` 或 `behavior`。
>
> **返回标注强制**：`lambda`/`snapshot`/`func`/`llm` 缺失返回标注产生
> `SEM_MISSING_RETURN_ANNOTATION` 编译错误。行为 body 的 `-> auto` 唯一推断为 `str`
> （LLM 输出默认字符串）；要其它类型必须显式 `-> T`（同时设定 LLM 输出 expected_type）。
> 语法规格见 `docs/syntax/07_behavior_expressions.md`。

### 7.2 声明侧关键字 `fn`

`fn` 等同 `auto` 类型推导，只承担"推导可调用类型"职责，不携带返回类型：
- `fn f = myFunc` ⇒ 推导 `f` 类型为 `myFunc` 的 FuncSpec
- `fn g = lambda(int x) -> int: x+1` ⇒ 推导 g 类型为 `CALLABLE_INSTANCE[int]`
- `fn h = lambda -> auto: @~ ... ~` ⇒ 行为体 `-> auto` 唯一推断 str ⇒ `CALLABLE_INSTANCE[str]`

**`fn` 参数/返回位置＝"任意可调用（强制）"**：`fn` 作为参数
类型或返回类型（裸 `fn` 哨兵，非 `fn[(...)]`）时，实参/返回表达式必须是可调用——
`apply(42)`、`-> fn: return 42` 编译期 `SEM_TYPE_MISMATCH`；动态实参/返回（`any`/
`auto`）静态不可判，放行交运行期裁决。`fn` 接受裸函数 / lambda / snapshot /
绑定方法 / 可调用类实例。用户可写类型中**无 `callable`**（内部基类名 + 公理族根，
`type(make)`="callable" 为内部身份，不可作类型注解）。

### 7.3 类型标注侧 `fn[(...)→(...)]`

`fn[(int,str)->bool]` 表达高阶函数签名约束：
- AST: `IbCallableType(IbExpr)`（`core/kernel/ast.py`）
- TypeDef: `kind=CALLABLE_SIG`，`param_types` / `return_type` 已填充
- 兼容性：与具体可调用 spec 通过结构匹配比对（参数数量 / 各位置 assignable / 返回类型 assignable）

### 7.4 捕获模式 `capture_mode`

不属于类型层语义，属于值层属性：
- `lambda`：引用语义。自由变量通过 `ScopeImpl.promote_to_cell()` 升为共享 `IbCell`，调用时读最新值。
- `snapshot`：值语义。定义时刻对所有自由变量做深克隆形成只读种子，并对意图栈 `fork_intent_snapshot()`。每次调用前再次对种子深克隆注入子作用域——snapshot 不缓存任何结果，是完全无状态且可重入的可调用实例。

**嵌套函数只读捕获**：嵌套函数体内引用的外层只读变量**自动捕获**为共享 `IbCell`（与 lambda 捕获机制同构，`binding_analysis_pass` 分析外层自由变量）。`nonlocal` 声明仅标记**写访问**——读捕获自动、写外层局部须显式 `nonlocal`。真闭包（外层返回后调用）只读捕获可用；写共享 cell 的隔离约束对任务内写主线程共享 cell 保持拦截。

---

## §8 Optional[T] 与空安全

- 空安全由 `Optional[T]` 显式表达。
- 赋值规则：
  - 非 `Optional` 类型**禁止**接收 `None`；
  - `Optional[T]` 接受 `T` / `None` / `Optional[T]`；
- 解封 API：`OptionalAxiom` 暴露 `unwrap` / `or_else` / `is_some` / `is_none` / `to_bool` / `cast_to` 方法。
- **统一 Optional 值模型**：`Optional[T]` 空值**恒为**
  `IbOptional(is_some=False)` 包装对象，任何值创建路径（模块级与函数作用域
  局部变量定义/赋值、函数参数、返回、类字段默认值与赋值、容器元素、
  闭包捕获与 cell 写）均经单一包装权威 `wrap_optional` 统一包装——不产生
  裸 `IbNone` 作为 Optional 空值。裸 `IbNone` 仅属于非 Optional 上下文
  （`any` / 无类型）。由此：
  - `is None` / `is not None` 对空 `Optional` 返回 `True`/`False`
    （None 语义检测，与 `== None` 对齐）；
  - `is_none()` / `is_some()` / `unwrap()` / `or_else()` 在任何路径可用；
  - `type()` 内省一致（空 Optional 报 `Optional[T]`）。
- **Optional 容器委托**：`Optional[T]` 是 `T` 的透明包装——
  持有值时，`T` 的容器操作与成员访问按 `T` 语义可用（`len(o)` / `o[i]` /
  `for x in o` / `o.to_list()` 等经内层值委托）；空 `Optional` 上这些操作
  fail-fast 报 `RUN_ATTRIBUTE_ERROR`（明确"空 Optional 无此操作"，不静默）。
  Optional 专属方法（`unwrap` / `or_else` / `is_some` / `is_none`）优先于委托。
- `None == 空 Optional` 与 `空 Optional == None` 对称（`==` / `!=`）。
- `None` 的运行时单例由 `KernelRegistry._none_instance`（`core/kernel/registry.py`）持有；运行时 `isinstance` 检查仍保留作哨兵比较（不属于类型分派）。

---

## §9 设计不变量

1. **三层闭合**：AST / 符号表 / FuncSignature 中的所有"另一类型"引用必须经过 `TypeRef`；TypeDef 不直接持 TypeDef。
2. **公理无 spec 依赖**：axiom 层能力方法仅在签名中接受/返回字符串类型名；可 import `core.kernel.spec` 原子数据结构构造器（`TypeRef` / `MethodMemberSpec`），不得依赖 spec 注册表/解析逻辑。
3. **运行时分派路径**：所有类型分派经 `isinstance(obj, IbValue) and obj.ib_class.name == "..."`；仅 `IbNone` 哨兵比较是例外。
4. **编译产物纯数据**：`CompilationResult` 与序列化协议中不出现 Python 函数引用、闭包或可变对象。
5. **kind 驱动**：所有"按类型种类分派"必须读 `spec.kind`（或 `kind in (X, Y)`），禁止 `isinstance(spec, FuncSpec)` 这类子类判断。

---

## §10 深入指引

- 架构原则与设计理念：`docs/architecture/01_principles.md`
- VM 与解释器架构：`docs/architecture/04_vm_interpreter.md`
- VM 公理化规范：`docs/architecture/05_vm_specification.md`
- 已知语言限制：`docs/KNOWN_LIMITS.md`
