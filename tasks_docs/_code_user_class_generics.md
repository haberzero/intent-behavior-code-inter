# _code_user_class_generics — 用户类泛型参数主线设计起点

> 2026-08-12 编制。用户裁定：**用户类泛型参数（PT-FEAT-3）提升为主线任务**。
> 本文档 = 地基盘点 + 设计范围 + 开放设计问题（供下一 session 设计冻结）。
> **只盘点，未改代码。**

## 一、目标

```ibci
class Box[T]:
    T value
    func get(self) -> T:
        return self.value

Box[int] bi = Box[int](42)
Box[str] bs = Box[str]("hi")
int v = bi.get()      # 特化返回类型 T→int
```

## 二、地基（已具备，2026-08-12 核实）

| 机制 | 位置 | 现状 |
|------|------|------|
| `GenericTypeRegistry` | `core/kernel/spec/generic.py` | 内置泛型统一注册表：`GenericTypeDeclaration`（含 `resolve_member` 特化回调）+ `_build_*`/`_to_typeref_*`/`_restore_*` 三函数族（create/typeref/restore 全链路） |
| `create_generic_registry()` | generic.py:374 | 注册 list/dict/tuple/Optional/fn_callable/behavior/thread/thread_result/chan/slot/generator 九类 |
| `resolve_specialization` | `core/kernel/spec/registry/_generic.py` | 泛型特化统一入口：`spec.get_base_name()` → `self.generic_types.get(base_name)` → 注册表创建特化 spec。**用户类特化在此扩展** |
| 类型参数 AST | — | `IbClassDef` **无 `type_params` 字段**（ast.py:158-163，仅 name/body/parent/methods/fields）——需新增 |
| 特化成员解析 | `_members.py` resolve_member | 经 `generic_types.get(spec.get_base_name()).resolve_member` 回调做成员特化（列表泛型成员已用此模式） |
| 序列化 | serializer.py + artifact_rehydrator | 内置泛型 `element_type_uid`/`value_type_uid` 等落 artifact + `_restore_*` 重建——用户类特化需同类通道 |

## 三、设计范围（下一 session 设计冻结需覆盖）

1. **语法层**：`class Box[T]:` / `class Box[T, U]:` —— lexer（`[`/`]`/`,` 在类名后）+ parser
   （`parse_class` 识别 type_params）+ AST `IbClassDef.type_params: List[str]`。
2. **语义层**：
   - 类定义收集：`symbol_collection_pass` 把 type_params 落 `TypeDef`（新增字段，如
     `type_params: List[str]`）。
   - 特化解析：`resolve_specialization` 对用户类（含 type_params）创建特化 spec——
     类型实参代入成员类型（字段 `MemberSpec.type_ref` / 方法 `param_types`/`return_type` 中的
     类型参数名 → 实参 TypeRef）。
   - 特化成员：`resolve_member` 对特化用户类解析特化后成员（对齐内置泛型的
     `decl.resolve_member` 回调模式）。
   - 类型检查：`Box[int]`/`Box[str]` 是不同特化（`is_assignable` 区分）；`Box` 裸用（未特化）
     的行为定义（禁止实例化 or 默认 any）。
3. **序列化**：`type_params` 落 artifact + `type_args`（特化 spec 的实参）；rehydrate 重建特化
   （对齐 `_restore_*` 通道）。
4. **运行时**：`registry.create_subclass` 对特化类（`Box[int]`）创建运行时类（name 含特化）；
   特化实例化/方法调用分派。
5. **e2e**：`Box[int]`/`Box[str]` 特化实例化、字段类型、方法返回类型特化、与内置泛型同构
   （`list[Box[int]]` 嵌套）、序列化 round-trip。
6. **文档**：`docs/syntax/06_oop.md`、KNOWN_LIMITS §十四 #1（能力差距 → 已支持）、
   `docs/architecture/02_metadata_ast.md`（AST 新增字段须查）。

## 四、开放设计问题（下一 session 设计冻结时决断）

1. **类型参数约束**：是否支持 bound（`T: Comparable`）？建议首版**无约束**（裸类型参数），
   bound 作后续增量。
2. **类型参数使用面**：字段/方法参数/返回/局部变量注解；是否允许嵌套（`class Box[T]` 内
   `list[T]`）——应支持（与内置泛型同构）。
3. **未特化裸用**：`Box b = ...`（无 type_args）——禁止实例化（报 SEM）还是退化 any？建议
   首版禁止（显式优于隐式），与 KNOWN_LIMITS 现有"list 必须特化"倾向一致。
4. **特化类运行时身份**：`Box[int]` 的 IbClass.name（`Box[int]` 字符串）与 registry 键；
   序列化 round-trip 身份。
5. **方法覆写/继承**：`class SpecialBox[T](Box[T])`——父类特化参数继承。
6. **与 enum 的关系**：枚举是否支持 type_params（`class Color[T]`）？建议首版排除（enum 值模型
   保持）。

## 五、建议实施路径（下一 session）

1. **Phase 0-1**：读本文件 + `core/kernel/spec/generic.py`（_build_list/_restore_list 为模板）+
   `resolve_specialization` + `symbol_collection_pass.visit_IbClassDef` + serializer。
2. **Phase 2 设计冻结**：按"开放设计问题"逐项决断，产出设计记录（本文件扩展或新文件）。
3. **Phase 3-4 实施**（每步全量 pytest 零回归）：
   a. AST/lexer/parser `type_params` → b. `TypeDef.type_params` + symbol collection →
   c. `resolve_specialization` 用户类分支 + 特化 spec 构造 → d. 序列化 →
   e. 运行时特化类 → f. e2e + 文档。
4. **独立复核**（general agent）+ 用户试用覆盖。

## 六、约束

- 全程本地 commit，禁 push（除非用户显式授权）。
- 破坏性重构按分支政策；本任务为增量特性（新增 AST 字段/TypeDef 字段），非破坏性重构，
  边界相对清晰，可直接在 unsafe-vibe-dev 实施（零风险判定后）。
- 不与枚举实例化（独立设计冻结）混做。
