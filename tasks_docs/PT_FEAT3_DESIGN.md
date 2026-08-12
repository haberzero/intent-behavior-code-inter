# PT-FEAT-3 用户类泛型参数 — 设计冻结

> 2026-08-12。设计起点 `_code_user_class_generics.md`（地基盘点 + 6 项开放设计问题）。
> 本文档 = 设计冻结：对 6 项开放问题逐项决断 + 实施蓝图。**落地前先查
> `docs/architecture/02_metadata_ast.md`（新增 AST 字段）与 KNOWN_LIMITS §十四 #1。**

## 一、目标（不变）

```ibci
class Box[T]:
    T value
    func get(self) -> T:
        return self.value

Box[int] bi = Box[int](42)
Box[str] bs = Box[str]("hi")
int v = bi.get()      # 特化返回类型 T→int
```

## 二、6 项开放设计问题决断

### 1. 类型参数约束 —— **首版无约束（裸类型参数）**

无 bound（`T: Comparable` 不做），无 upper/lower。类型参数仅是类体内类型
标注的"占位名"，特化时替换为实参。bound 作后续增量（不在本任务范围）。

### 2. 类型参数使用面 —— **字段/方法参数/返回/局部变量注解 + 嵌套泛型**

- 字段：`T value`
- 方法参数/返回：`func get(self) -> T`、`func set(self, T v) -> void`
- 局部变量：方法体内 `T tmp = ...`（经类型参数符号解析）
- 嵌套：`class Box[T]` 内 `list[T] items`、`func f(self) -> list[T]`——与内置
  泛型同构（`resolve_specialization` 把 T 解析为实参后再套 list）
- **首版实现**：类型参数名 T 在**类作用域内**注册为类型参数符号
  （`TypeSymbol(kind=TYPE_PARAM, spec=TypeDef(name=T, kind=TYPE_PARAM))`），
  语义层 `_resolve_type`/`_annotation_to_typeref` 对 IbName 命中类型参数符号
  时解析为 `TypeRef(T)`（占位），而非报 SEM_UNRESOLVED_TYPE。
- **特化替换**：特化 spec 构造时遍历成员（字段 MemberSpec.type_ref、方法
  MethodMemberSpec.param_types/return_type/type_ref），把 `TypeRef(head=T)`
  递归替换为实参 TypeRef（含 args 递归）。嵌套 `list[T]` 的 `TypeRef(list, (T,))`
  替换内层 T。

### 3. 未特化裸用 —— **禁止实例化（编译期 SEM）**

`Box b = ...`（基类无 type_args 直接声明/实例化）→ 编译期报错
`SEM_GENERIC_TYPE_NEEDS_ARGS`（新诊断码，进 catalog）：
"泛型类 'Box' 需要类型参数，如 Box[int]"。
裸用行为对齐 KNOWN_LIMITS 现有"list 必须特化"倾向（显式优于隐式）。
**注**：泛型类定义本身（`class Box[T]`）合法；仅"实例化/声明裸 Box"被禁。
父类引用（`class SpecialBox[T](Box[T])`）以特化形式出现，不算裸用。

### 4. 特化类运行时身份 —— **name="Box[int]" + registry 按全名注册**

- 特化 spec：`TypeDef(name="Box[int]", kind=CLASS, type_params=[], ...)`，
  父类 = 基类 parent（特化后 parent 若为泛型也替换）。
- registry 键：`resolve_specialization` 缓存键 `"Box[int]"`（与内置泛型
  `f"{base_name}[{','.join(arg_names)}]"` 同构）。
- 运行时 IbClass：`create_subclass("Box[int]", spec, parent_name)` → 
  `registry.get_class("Box[int]")`。方法经 `_hydrate_user_classes` 从 AST
  绑定（与普通类同路径，`get_class(name)` 命中特化名）。
- 序列化：type_pool 里 Box 与 Box[int] 各一 TypeDef；成员类型在特化 spec 中
  已替换，round-trip 保真。
- **继承链**：`Box[int]` 的 parent 是基类 Box 的 parent（如 Object），而非
  Box 本身（Box 是泛型模板非实体）。`Box[int] is_assignable_to Box` 经
  spec is_assignable（kind 相同 + name 前缀？）——首版：特化 spec 与基类
  spec 不做互相 assignable（`Box[int]` 不 assignable 到 `Box`，因裸 Box
  已被禁；`Box[int]` 与 `Box[str]` 不互相 assignable，因类型参数不同）。

### 5. 方法覆写/继承 —— **首版：父类泛型继承（`class SpecialBox[T](Box[T])`）**

- 子类 `SpecialBox[T]` 的 type_params 含 T，父类 `Box[T]` 的父引用
  `TypeRef(Box, (T,))`——T 在子类作用域内解析为类型参数。
- 特化 `SpecialBox[int]` 时：type_params 映射 T→int，同时父引用
  `TypeRef(Box, (T,))` 替换为 `TypeRef(Box, (int,))`，并解析父特化
  `Box[int]`（递归 resolve_specialization）。
- 方法覆写校验（`_check_override_compatibility`）：父类方法签名经特化替换后
  比较（`Box[T].get -> T` vs `SpecialBox[T].get -> T`，特化后均 →int）。
- **首版范围收敛**：仅支持 `class Sub[T](Base[T])`（子类类型参数与父类参数
  同名/同序传递）。`class Sub(Box[int])`（非泛型子类继承具体特化）作为后续
  增量（本任务不实现，登记 KNOWN_LIMITS 边界）。

### 6. 与 enum 的关系 —— **首版排除**

枚举不支持 type_params（`class Color[T]` 报 SEM）。enum 值模型保持
（成员 = 底层值非实例，泛型实例化与值模型冲突）。落地时在语义层对
`node.parent == "Enum"` 且含 type_params 报 SEM。

## 三、实施蓝图（Phase a-f）

### a. AST + lexer + parser
- `IbClassDef.type_params: List[str]`（默认空表）——**新增字段，先查
  `docs/architecture/02_metadata_ast.md`**。
- lexer：无需新 token（`[`/`]`/`,` 已存在）。
- parser `class_declaration()`：类名后 `match(LBRACKET)` → 解析逗号分隔
  IDENTIFIER 列表至 `RBRACKET`，落 `type_params`。语法错误报 LEX/PAR 诊断。
- 位置：`class Name[T]`（name 与 `[` 间无空格）；父类仍 `(Parent)`。

### b. TypeDef.type_params + symbol collection
- `TypeDef.type_params: List[str]`（默认空表）——CLASS kind 专用。
- `symbol_collection_pass.visit_IbClassDef`：把 `node.type_params` 落
  `cls_meta.type_params`；对每个类型参数名在类作用域内 `_define`
  `TypeSymbol(kind=SymbolKind.TYPE_PARAM, spec=TypeDef(name=T, kind=TYPE_PARAM))`。
  - **TypeKind 新增** `TYPE_PARAM`（`core/kernel/spec/base.py` TypeKind 枚举 +
    `_KIND_BASE_NAMES` 不映射——占位型，无 axiom）。
  - `SymbolKind` 新增 `TYPE_PARAM`。
  - **注意**：类型参数符号不进类 members（成员表只放字段/方法）。
- `_annotation_to_typeref`/`_resolve_type`：IbName 解析时先查当前类作用域
  类型参数符号（经符号表链），命中 → `TypeRef(name=T)` 占位。

### c. resolve_specialization 用户类分支
- `_assignability.resolve_specialization`：`decl is None` 分支前加用户类
  检测：`spec.kind == CLASS and spec.type_params`。
  - 校验 `len(arg_specs) == len(spec.type_params)`，不等报 SEM（新诊断码）。
  - 建立映射 `{param_name: arg_spec}`。
  - 构造特化 spec：
    - 复制基类 spec（factory.create_class，name=`"Box[int]"`，parent 替换）
    - 递归替换成员：字段 `MemberSpec.type_ref`、方法 `MethodMemberSpec` 的
      `param_types`/`return_type`/`type_ref` 中的 `TypeRef(head=param) → 实参`
    - 注册 + axiom bootstrap（无 axiom，跳过）
  - **TypeRef 递归替换工具**：`core/kernel/spec/type_ref.py` 加
    `TypeRef.substitute(mapping) -> TypeRef`（纯函数，递归 args）。
- 序列化：`type_params` 落 artifact（serializer `_collect_type` + rehydrator
  `_fill_descriptor` CLASS 分支补 `type_params`/`parent_module` 已存）。
- `resolve_specialization` 对用户类的缓存键：`f"{base_name}[{args}]"` 与内置
  同构（当前 resolve() 已按 candidate_key 查）。

### d. 序列化
- serializer `_collect_type` CLASS 分支：持久化 `type_params: List[str]`。
- rehydrator `_create_shell` CLASS 分支 + `_fill_descriptor`：重建
  `type_params`；特化 spec（name 含 `[`）按名注册（create_class 已按 name）。

### e. 运行时特化类
- `artifact_loader` 预注册用户类循环天然处理特化 spec（parent 已替换，
  name="Box[int]"）。
- `_hydrate_user_classes`：`get_class("Box[int]")` 命中特化 IbClass，方法从
  AST 绑定（owner_class=特化类），字段从 AST 建 IbClassField。
- `vm_handle_IbCall` 对 func 为 `Box[int]`（IbSubscript 表达式）的求值路径：
  **关键——`Box[int](42)` 中 func 是 IbSubscript(value=Box, slice=int)**。
  运行时 `vm_handle_IbSubscript` 目前调 `value.receive("__getitem__")`——
  Box 是 IbClass，无 __getitem__ → 需处理。方案：
  - 编译期把 `Box[int](42)` 的 func 视为"类型特化构造"，语义层绑定类型为
    特化 spec；运行时 vm_handle_IbCall 对 IbSubscript func 走特化类解析：
    **在语义层把 func 节点标记/改写为特化类名解析**（见下方"运行时求值"）。
  - 或运行时 vm_handle_IbSubscript 对 IbClass value 特判：slice 是类型名时
    经 registry 查特化类并返回 IbClass 对象（`Box[int]` 表达式求值为特化类
    对象，`(42)` 再调 instantiate）。**方案 B 更贴近现有 VM 架构**（IbClass
    是对象，`Box[int]` 求值为类对象 → `__call__` 构造）。
  - **决断**：方案 B。`Box[int]` 表达式 = IbSubscript，运行时求值 Box（IbClass）
    再 `__getitem__(int)`——在 `IbClass.receive("__getitem__")` 增加"类型特化"
    处理：slice 为类型标识（int 类对象）时经 registry 特化查/建 IbClass 返回。
    需确认 IbClass.__getitem__ 现状与 slice 求值形态（int 作为类型名求值）。

### f. e2e + 文档
- e2e：`Box[int]`/`Box[str]` 特化实例化、字段类型、方法返回类型特化、嵌套
  `list[Box[int]]`、序列化 round-trip、未特化裸用报 SEM、父类泛型继承。
- 文档：`docs/syntax/06_oop.md`（泛型类章节）、KNOWN_LIMITS §十四 #1
  （能力差距 → 已支持）、`docs/architecture/02_metadata_ast.md`（IbClassDef
  type_params 字段）。
- catalog：新诊断码 SEM（裸用/参数数量）登记 + 15_diagnostics.md 同步。

## 四、开放风险与后续增量（本任务不实现，登记）

- 非泛型子类继承具体特化（`class Sub(Box[int])`）——后续增量。
- bound 约束（`T: Comparable`）——后续增量。
- 类型参数在方法体外的模块级使用（`Box` 裸引用，非实例化）——首版禁实例化，
  裸名引用待定（当前语义仅实例化处拦截）。
- enum 泛型——后续增量。

## 五、约束

- 全程本地 commit、禁 push。
- 增量特性（新增 AST 字段/TypeKind/诊断码），边界清晰，直接 unsafe-vibe-dev。
- 每步全量 pytest 零回归。
- 不与枚举实例化混做。
