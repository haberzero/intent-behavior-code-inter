# IBCI 类型系统设计（代码对齐版）

> 本文档是 IBCI 类型系统的**正式设计文档**，与当前代码（`core/kernel/spec/`、`core/kernel/axioms/`、`core/runtime/objects/`）严格对齐。
> 设计原文（架构推演、语言学动机）见 `docs/IBCI_TYPE_SYSTEM_FROM_ZERO_ARCHITECTURE.md`。
> 历史演进时间线见 `docs/COMPLETED.md`。

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

### 3.1 单一统一类（M3 收口）

`core/kernel/spec/base.py:TypeDef` 是**所有类型种类**的统一定义类，**没有** `FuncSpec` / `ClassSpec` / `ListSpec` 等子类（已于 M3 合并删除）。差异通过 `kind` 字段分派。

```python
@dataclass(eq=False)
class TypeDef(IbSpec):
    # ── 通用 ──────────────────────────────────────
    name:           str
    module_path:    Optional[str]
    kind:           str  # 见 TypeKind
    is_nullable:    bool
    is_user_defined: bool
    members:        Dict[str, MemberSpec]
    _axiom_name:    Optional[str]    # axiom 查询 key 重定向

    # ── 函数签名（FUNCTION / BOUND_METHOD / CALLABLE_INSTANCE / CALLABLE_SIG）
    param_types:    List[TypeRef]
    return_type:    TypeRef
    is_llm:         bool

    # ── 类继承（CLASS）
    parent_type:    Optional[TypeRef]

    # ── 容器（LIST / TUPLE / DICT）
    element_type:   TypeRef
    allowed_element_types: List[TypeRef]   # 多类型 list
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
| `FUNCTION` | 函数类型（含 `fn` 哨兵 / `callable`） | 用户 `func`、内置函数、`fn` 推导 |
| `CLASS` | 类（含内置 Exception 系列） | 用户类、`Enum` / `Exception` / `Intent` |
| `LIST` / `TUPLE` / `DICT` | 容器 | `list[int]` 等 |
| `OPTIONAL` | 空安全包装 | `Optional[T]` |
| `BOUND_METHOD` | 已绑定接收者的方法 | `obj.method` 取值 |
| `MODULE` | 模块命名空间 | `import` 后的模块对象 |
| `CALLABLE_INSTANCE` | lambda/snapshot/behavior 产生的可调用实例（M3→M5 合并） | `fn_callable` / `behavior` |
| `CALLABLE_SIG` | 高阶函数签名约束 | `fn[(int)->int]` |
| `LAZY` | 跨模块未解析占位符 | 编译期 forward ref |

> M3→M5 补充：旧 `TypeKind.DEFERRED` + `TypeKind.BEHAVIOR` 已合并为 `TypeKind.CALLABLE_INSTANCE`；区分仅由 `name`（`"fn_callable"` / `"behavior"`）或 `_axiom_name` 决定，不再是类型层语义。

### 3.3 字段存储规范

- **TypeRef-only**：所有指向"其他类型"的字段全部以 `TypeRef` 存储；旧 `*_name` / `*_module` 扁平字符串字段已彻底删除。访问统一走 `spec.X.head` / `spec.X.module` / `spec.X.canonical_name`。
- **MemberSpec 同样 TypeRef 化**：`core/kernel/spec/member.py:MemberSpec.type_ref`、`MethodMemberSpec.return_type` / `param_types` 均为 TypeRef。
- **线协议保留**：序列化 / 反序列化（`core/compiler/serialization/`）仍把 TypeRef 解构为字符串字段（`return_type_name` / `parent_module` 等）以保持艺术品向后兼容；in-memory 模型纯 TypeRef。

### 3.4 注册表 SpecRegistry

`core/kernel/spec/registry.py:SpecRegistry` 是 IBCI 类型系统的**核心门面**：

| 方法 | 作用 |
|------|------|
| `resolve(name, module=None)` | 按名字查找 spec |
| `resolve_typeref(ref)` | 按 TypeRef 查找；带模块优先，回落裸名 |
| `register(spec, ...)` | 注册新 spec（克隆原型） |
| `resolve_specialization(base, args)` | 按需创建/缓存 `list[int]` 等泛型特化 spec（G1/G3 早缓存） |
| `is_assignable(src, target)` | 类型兼容性检查（含 Optional / 类继承链 / 公理委托） |
| `get_base_spec(spec)` | 取泛型特化的底 spec（`list[int]` → `list`） |
| `get_axiom(spec)` | 桥接 AxiomRegistry，按 `spec.get_base_name()` / `_axiom_name` 查询 |
| `get_call_cap` / `get_iter_cap` / `get_subscript_cap` / `get_operator_cap` | 能力门：返回公理（声明对应能力时）或 `None` |
| `resolve_return(spec, args)` / `resolve_op` / `resolve_iter_element` / `resolve_subscript` | 编译期类型推断入口 |

注册表持有的 spec 是原型的克隆，保证多引擎实例间状态隔离（`SpecRegistry.register` 内部 `clone()`）。

### 3.5 SpecFactory

`core/kernel/spec/registry.py:SpecFactory` 提供面向编译器的**字符串入口**（`*_name` / `*_module`），内部统一桥接到 TypeRef 后写入 TypeDef 字段。这是仅有的"字符串构造 API"，TypeDef 本身不接受字符串 kwargs。

| 方法 | 用途 |
|------|------|
| `create_primitive(name, is_nullable)` | 标量类型 |
| `create_func(name, param_type_names, return_type_name, ...)` | 函数 spec（用户 func / 插件 vtable / 内置） |
| `create_class(name, parent_name, is_user_defined)` | 用户类 / 内置类 |
| `create_list / create_tuple / create_dict` | 容器特化 |
| `create_optional(wrapped_name)` | Optional[T] |
| `create_bound_method(...)` | 绑定方法 |
| `create_callable_instance(...)` | fn_callable / behavior |
| `create_callable_sig(...)` | `fn[(...)→(...)]` 签名约束 |

---

## §4 TypeAxiom — 行为分派层（M5 单一接口）

### 4.1 统一 Protocol

`core/kernel/axioms/protocols.py:TypeAxiom` 是**单一**的能力接口；旧 9 个分散 Capability 协议（`CallCapability` / `IterCapability` / `SubscriptCapability` / `OperatorCapability` / `ConverterCapability` / `ParserCapability` / `FromPromptCapability` / `OutputHintCapability` / `WritableTrait`）已全部归并删除。

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

`core/kernel/axioms/primitives.py:BaseAxiom` 提供安全 no-op 默认（所有 `has_*_cap = False`、能力方法返回 `None` / `False` / 空集）。具体公理只重写需要的部分；不再多重继承能力 mixin。

### 4.3 字符串边界

公理层**只**接受/返回**字符串类型名**（`"int"` / `"list[int]"` / `"any"` 等），不导入 `core/kernel/spec/`。这维持了"axiom 不依赖 spec 层"的单向边界——SpecRegistry 调用公理时把 spec 名字串过去，把字符串结果再 resolve 成 spec 返回给调用方。

### 4.4 内置公理清单

`core/kernel/axioms/registry.py:AxiomRegistry` 注册的公理（节选）：

| Axiom | 类型 | 关键能力 |
|-------|------|---------|
| `IntAxiom` / `FloatAxiom` / `StrAxiom` / `BoolAxiom` / `NoneAxiom` | 标量 | `operator` / `converter` / `parser` / `from_prompt` |
| `ListAxiom` / `TupleAxiom` / `DictAxiom` | 容器 | `iter` / `subscript` / `operator(+,in)` |
| `OptionalAxiom` | Optional[T] | `is_compatible` / unwrap 方法集 |
| `EnumAxiom` | 枚举类 | `is_class=True` / `from_prompt`（按字面值解析） |
| `CallableAxiom` / `BoundMethodAxiom` / `FnCallableAxiom` / `BehaviorAxiom` | 可调用 | `call_cap` |
| `ModuleAxiom` | 模块 | `is_module=True` |
| `IntentContextAxiom` | 意图上下文 | `is_class=True` |
| `LlmCallResultAxiom` | LLM 调用结果 | `is_class=True` |
| `ExceptionAxiom` / `LLMErrorAxiom` 系列 | 异常 | 类继承链 |

---

## §5 编译期 ⇄ 运行期分派路径

### 5.1 编译期调用

```
Pass 4/5 SemanticAnalyzer
  └── 表达式类型推断 / 调用返回类型 / 运算结果类型
        └── SpecRegistry.resolve_return(spec, args)        — 函数 / callable_instance / class 构造
        └── SpecRegistry.resolve_op(spec, op, other)       — 二元 / 一元运算
        └── SpecRegistry.resolve_iter_element(spec)        — for 元素类型
        └── SpecRegistry.resolve_subscript(spec, key_spec) — `obj[key]`
              └── 内部按 spec.kind 直分派；其余委托 axiom.resolve_*_type_name
```

### 5.2 运行期调用（VM 层）

```
VMExecutor handler
  └── 取值 IbValue → ib_class.spec → SpecRegistry.get_axiom(spec)
        └── axiom.parse_value / from_prompt / __outputhint_prompt__   — LLM 路径
        └── axiom.resolve_operation_type_name                          — 仅诊断 / dump，不参与运行
  └── 运行期取分支不再走 isinstance(IbXxx)；统一通过 IbValue + ib_class.name + spec.kind
```

> 运行期的"做"（数学加法、列表 append 等）由具体 `IbValue` 子类的方法实现，而非走 axiom；axiom 在运行期只承担 LLM 边界（`from_prompt` / `parse_value` / `__outputhint_prompt__`）。

### 5.3 LazySpec 占位符

跨模块未解析符号在编译期暂以 `LazySpec` 占位（`core/kernel/spec/`）；解析阶段强制成功，**异常**情况应抛错而非静默回填（见 `ARCHITECTURE_PRINCIPLES.md §5.3`）。

---

## §6 运行时值层（IbValue 单一承载）

> M4 收口：所有运行时值统一通过 `core/runtime/objects/kernel.py:IbValue` 承载；`IbInteger` / `IbFloat` / `IbString` / `IbBool` / `IbList` / `IbTuple` / `IbDict` / `IbNone` / `IbLLMUncertain` / `IbLLMCallResult` / `IbFnCallable` / `IbBehavior` 是该模型的子体系。

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

- `isinstance(obj, IbValue) and obj.ib_class.name == "list"` 是分派 list 类型的唯一惯用法（`IbClass` 自指 `ib_class=self` 会让裸 `ib_class.name` 误中，必须先做 `IbValue` 判定）。
- 工厂入口：`core/runtime/factory.py:RuntimeObjectFactory` 提供 `create_int / create_str / create_list / create_tuple / create_dict / create_fn_callable / create_behavior` 等方法，**不**在调用方导入具体类。

---

## §7 fn / lambda / snapshot / behavior 类型语义

### 7.1 表达式侧产物

| 源语法 | AST 节点 | 运行时值 | 类型 |
|--------|---------|---------|------|
| `lambda(...) -> T: EXPR` | `IbLambdaExpr(capture_mode="lambda")` | `IbFnCallable` | `TypeKind.CALLABLE_INSTANCE`，name=`fn_callable`，value_type=T |
| `snapshot(...) -> T: EXPR` | `IbLambdaExpr(capture_mode="snapshot")` | `IbFnCallable`（snapshot 模式） | 同上 |
| `@~ ... ~`（含 `@! ...`） | `IbBehaviorExpr` | `IbBehavior` | `TypeKind.CALLABLE_INSTANCE`，name=`behavior` |

> `lambda` / `snapshot` 不是 behavior 专属包装；`IbLambdaExpr` 覆盖任意表达式 body，semantic pass 按 body 是否为 `IbBehaviorExpr` 分流到 `fn_callable` 或 `behavior`。

### 7.2 声明侧关键字 `fn`

`fn`（D1 后等同 `auto`）只承担"推导可调用类型"职责，不携带返回类型：
- `fn f = myFunc` ⇒ 推导 `f` 类型为 `myFunc` 的 FuncSpec
- `fn g = lambda(int x) -> int: x+1` ⇒ 推导 g 类型为 `CALLABLE_INSTANCE[int]`
- `fn h = lambda: @~ ... ~` ⇒ 推导 h 类型为 `behavior` 路由的 `CALLABLE_INSTANCE[auto]`

### 7.3 类型标注侧 `fn[(...)→(...)]`

`fn[(int,str)->bool]` 表达高阶函数签名约束（D3）：
- AST: `IbCallableType(IbExpr)`（`core/kernel/ast.py`）
- TypeDef: `kind=CALLABLE_SIG`，`param_types` / `return_type` 已填充
- 兼容性：与具体可调用 spec 通过结构匹配比对（参数数量 / 各位置 assignable / 返回类型 assignable）

### 7.4 捕获模式 `capture_mode`

不属于类型层语义，属于值层属性：
- `lambda`：引用语义。自由变量通过 `ScopeImpl.promote_to_cell()` 升为共享 `IbCell`，调用时读最新值。
- `snapshot`：值语义。定义时刻深拷贝值到独立 `IbCell`，并对意图栈 `fork_intent_snapshot()`。

---

## §8 Optional[T] 与空安全（M2）

- 空安全由 `Optional[T]` 显式表达，不依赖 `is_nullable` 布尔。
- `is_nullable` 字段保留为迁移期数据字段，不再参与 `is_assignable` 决策。
- 赋值规则：
  - 非 `Optional` 类型**禁止**接收 `None`；
  - `Optional[T]` 接受 `T` / `None` / `Optional[T]`；
- 解封 API：`OptionalAxiom` 暴露 `unwrap` / `or_else` / `is_some` / `is_none` 方法。
- `None` 的运行时单例由 `KernelRegistry._builtin_instances["IbNone"]` 持有；运行时 `isinstance` 检查仍保留作哨兵比较（不属于类型分派）。

---

## §9 设计不变量

1. **三层闭合**：AST / 符号表 / FuncSignature 中的所有"另一类型"引用必须经过 `TypeRef`；TypeDef 不直接持 TypeDef。
2. **公理无 spec 依赖**：axiom 层仅在签名中接受/返回字符串类型名，禁止 `from core.kernel.spec`。
3. **运行时分派路径**：所有 `isinstance(IbXxx)` 已被 `isinstance(obj, IbValue) and obj.ib_class.name == "..."` 替换；仅 `IbNone` 哨兵比较是例外。
4. **编译产物纯数据**：`CompilationResult` 与序列化协议中不出现 Python 函数引用、闭包或可变对象。
5. **kind 驱动**：所有"按类型种类分派"必须读 `spec.kind`（或 `kind in (X, Y)`），禁止 `isinstance(spec, FuncSpec)` 这类已删除的子类判断。

---

## §10 当前状态（2026-05-08 锚点）

- M1 / M2 / M3 / M3→M5 callable-instance 路线 / M4 / M5 全部完成（详见 `docs/COMPLETED.md`）。
- 主线债务：无。
- 测试基线：`python -m pytest tests/ -q --tb=short` 全量通过。

---

## §11 关联文档

- 设计原文（架构推演、动机、与旧体系对照）：`docs/IBCI_TYPE_SYSTEM_FROM_ZERO_ARCHITECTURE.md`
- VM 与解释器架构（执行边界、CPS、Signal、LLM Scheduler）：`docs/VM_AND_INTERPRETER_DESIGN.md`
- VM 正式规范（公理化）：`docs/VM_SPEC.md`
- 架构原则：`docs/ARCHITECTURE_PRINCIPLES.md`
- 运行时与解释器细节备份：`docs/ARCH_DETAILS.md`
- 历史时间线：`docs/COMPLETED.md`
