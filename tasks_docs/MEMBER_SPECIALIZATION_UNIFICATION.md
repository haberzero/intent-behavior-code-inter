# 泛型成员特化协议化 —— 设计（下一主线）

> 状态：**设计待实施**（设计审查后开工）
> 依据：`THREAD_ARCH_HARDCODE_INVESTIGATION.md` §三 根因 1（统一泛型模型半落地）+
> `PENDING_REVIEW_ITEMS.md` L2 + T 建议 1/4
> 原则：工作模式定论（禁过程式硬编码分发/禁双通道）+ design-philosophy（单一权威源/机制同构/
> 协议驱动）+ 独立分支政策（触碰 resolve_member 语义核心，独立分支实验后手动应用）
> 最后更新：2026-08-04

---

## 一、问题（L2 + 调查根因 1）

`SpecRegistry.resolve_member`（`core/kernel/spec/registry/_members.py:53-140`）在通用成员
解析流程中，用 **per-type if/elif 硬编码级联**特化泛型类型成员返回类型：

```
spec.kind == LIST         → pop()/__getitem__() → T；append(item: any) → append(item: T)
spec.kind == DICT         → pop/get → V；values → list[V]；keys → list[K]
spec.kind == OPTIONAL     → unwrap/or_else → T
spec.kind == THREAD       → join() → thread_result[T]
spec.kind == THREAD_RESULT→ unwrap() → Optional[T]；unwrap_or/expect → T
```

这是"统一泛型模型半落地"：`GenericTypeDeclaration`（`generic.py`，任务 B）已统一泛型类型的
**build/to_typeref/restore**，但**成员特化未纳入**，仍是硬编码级联。每次新增泛型类型
（thread、subscriber、未来用户泛型类 PT-4.4）都强制往 `_members.py` 塞分支——正是
"过程式硬编码分发"（工作模式定论第 4 条）+ 调查确认的核心架构隐患。

公理层 `join/cancel ret="any"`（`ThreadAxiom`）的"any 兜底"批评，本质即此：特化靠硬编码
补丁而非机制。协议化后公理 `any` 成为**声明层合法默认**（泛型参数不可知），精确化由
机制承担——"禁止 any 兜底"裁定以机制化满足，无需强行改公理。

## 二、设计

### D1. `MemberSpecialization`（特化结果值对象）

```python
@dataclass(frozen=True)
class MemberSpecialization:
    """泛型成员特化结果：成员返回类型与参数类型的精确化。"""
    return_type: TypeRef
    param_types: Optional[List[TypeRef]] = None  # None = 保持 axiom 声明
```

### D2. `GenericTypeDeclaration` 新增可选 `resolve_member` 回调

```python
# 签名：registry（SpecRegistry，特化副作用如 dict.values→list[V] 注册需要）
#       spec（特化 TypeDef，携带泛型实参）attr_name（成员名）member（axiom 声明的 MethodMemberSpec）
resolve_member: Optional[Callable[["SpecRegistry", "TypeDef", str, MethodMemberSpec], Optional[MemberSpecialization]]] = None
```

回调**按名注册**于各泛型声明（list/dict/tuple/Optional/fn_callable/behavior/thread/thread_result），
内部读取 `spec.value_type/wrapped_type/element_type/key_type` 等泛型实参，返回特化结果；
未命中返回 None（保持 axiom 声明原样）。frozen dataclass 保持纯声明性（build/to_typeref/
restore 先例）。

### D3. `resolve_member` 协议驱动化（`_members.py` 重构）

```python
member = spec.members.get(attr_name)
if member is not None and isinstance(member, MethodMemberSpec):
    effective_return = member.return_type.head
    effective_return_module = member.return_type.module
    effective_params = [t.head for t in member.param_types]
    effective_param_modules = [t.module for t in member.param_types]

    decl = self.generic_types.get(spec.get_base_name())
    if decl is not None and decl.resolve_member is not None:
        spec_result = decl.resolve_member(self, spec, attr_name, member)
        if spec_result is not None:
            effective_return = spec_result.return_type.head
            effective_return_module = spec_result.return_type.module
            if spec_result.param_types is not None:
                effective_params = [t.head for t in spec_result.param_types]
                effective_param_modules = [t.module for t in spec_result.param_types]

    resolved_member = TypeDef(name=attr_name, kind=FUNCTION, ...)
    return resolved_member
```

- **`_members.py` 移除全部 per-type if/elif 级联**（LIST/DICT/OPTIONAL/THREAD/THREAD_RESULT 分支）。
- 特化副作用（dict `values/keys` 的 `resolve_specialization(list[V])` 注册）移入回调（经 registry）。
- 非泛型类型（`generic_types.get(base_name)` 为 None）走原路径，行为不变。

### D4. 回调迁移（generic.py）

`_members.py:53-140` 五个分支逻辑原样迁移为 `_resolve_member_list/_dict/_optional/_thread/_thread_result`，
注册于 `create_generic_registry()`。断言逻辑（`allowed_element_types` 排除 multi-type list 等）
逐条保持。

### D5. 公理层不动

`ThreadAxiom.join/cancel ret="any"`、`ThreadResultAxiom.unwrap ret="any"` 保持——`any` 是
声明层默认，精确化由声明回调承担（机制化满足"禁止 any 兜底"裁定）。

## 三、涉及文件

| 文件 | 变化 |
|------|------|
| `core/kernel/spec/generic.py` | `MemberSpecialization` + `GenericTypeDeclaration.resolve_member` 字段 + 5 个迁移回调 + 注册 |
| `core/kernel/spec/registry/_members.py` | resolve_member 移除级联，改查注册表回调 |
| 测试 | `test_generic_model.py` 新增成员特化测试；语义相关测试回归 |

## 四、验证

- 每步全量 `python -m pytest tests/` 零回归（独立分支上）。
- 关键断言：list[T].pop→T、dict[K,V].values→list[V]、Optional[T].unwrap→T、
  thread[T].join→thread_result[T]、thread_result[T].unwrap→Optional[T] 全部由声明回调产出
  （且删除 `_members.py` 级联后测试仍绿）。

## 五、决策记录

- 独立分支执行（触碰 resolve_member 语义核心）。分支名：`member-spec-unify`。
- 回调带 `registry` 参数（dict.values/keys 特化的 resolve_specialization 副作用需要）。
- 不做公理返回类型"字符串化正确"改造——any 是声明层合法默认，机制化即满足裁定。

## 六、待决

- 无。技术路线已定，分支实施。
