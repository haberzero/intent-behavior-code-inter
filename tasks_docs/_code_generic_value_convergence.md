# 设计：值层身份彻底收敛——统一"类型上下文 → 字面量"传递机制

> 2026-08-13。承接 `_code_generic_type_identity.md` §2.6 边界增量（用户要求彻底收敛）。
> 用户关切：边界是长期隐患，不完全符合架构统一性/代码质量原则，要求评估彻底收敛方案与工作量。

---

## 〇、统一根因

值创建点类型化（缺陷二根治）的机制是：**编译期把"目标特化类型"绑到容器字面量节点
（`bind_type`）→ VM 字面量 handler 查 `node_to_type` 水化特化类**。

但该传递只实现于**简单变量赋值**一个上下文（`_statement_visitors.py:158-160`）。
其他 6 类能产生容器字面量值的上下文（函数返回 / 调用实参 / 下标赋值 / 嵌套内层 /
切片 / Optional 包装 / 跨引擎反序列化）都缺"类型上下文 → 字面量节点"的传递，
值运行时仍擦除为裸 `list`/`Optional`。

**这是同一机制缺口的多种表现**，非 7 个独立缺陷。彻底收敛 = 统一传递机制推广到全部
上下文（机制同构，design-philosophy §四）。

---

## 一、边界清单与根因（独立复核实证 + 本次复核）

| # | 场景 | 根因 | 层 |
|---|------|------|----|
| 1 | 函数返回字面量 `func f()->list[int]: return [1,2]` | `visit_IbReturn` 只 bind 字面量自身推断类型（裸 list），无函数返回类型上下文 | 编译期 |
| 2 | 调用实参字面量 `consume([1,2])`（形参 list[int]） | 实参解析有形参类型但未 bind 实参字面量节点 | 编译期 |
| 3 | 下标赋值字面量 `m[0]=[9]` | `:170` 分支 RHS 未 bind（下标 target_type 可得） | 编译期 |
| 4 | 嵌套内层 `list[list[int]] n=[[1],[2]]` | 外层 bind 后未递归内层元素节点 | 编译期 |
| 5 | 切片 `li[0:2]` | `collections.py` slice 分支 `registry.box` 裸容器，无特化感知 | 运行时 |
| 6 | Optional 值 `Optional[int] o=5` | `_wrap_optional` 用基类 `Optional`，未用特化类 | 运行时 |
| 7 | 跨引擎反序列化 | `_hydrate_specialized_class` 用目标引擎 spec_reg（无该特化），未用序列化 type_pool 重建 | 运行时 |

---

## 二、统一收敛方案

### 2.1 编译期统一 helper（核心）

`TypeCheckBase._bind_literal_with_type(node, spec)` 递归：

```python
def _bind_literal_with_type(self, node, spec):
    """把目标特化类型绑到容器字面量节点（含递归内层元素）。

    与 _bind_container_specialization（运行时）对称：编译期建立
    node_to_type = 特化类型，运行时据此水化特化类。
    仅容器字面量 + 内置泛型特化目标参与；其余原样（不改变既有行为）。
    """
    if not isinstance(node, (ast.IbListExpr, ast.IbDict, ast.IbTuple)):
        return
    if spec is None or spec.kind not in (LIST, TUPLE, DICT, OPTIONAL):
        return
    if spec.name == 基类名（list/dict/tuple/Optional）:  # 裸类型，无需特化
        return
    self.bind_type(node, spec)
    # 递归内层元素：从 spec 提取元素类型
    if isinstance(node, ast.IbListExpr) and spec.kind == LIST:
        elem = self.registry.resolve_typeref(spec.element_type) or self._any_desc
        for elt in node.elts:
            self._bind_literal_with_type(elt, elem)
    elif isinstance(node, ast.IbDict) and spec.kind == DICT:
        val = self.registry.resolve_typeref(spec.value_type) or self._any_desc
        for v in node.values:
            self._bind_literal_with_type(v, val)
    elif isinstance(node, ast.IbTuple) and spec.kind == TUPLE:
        # positional 或单 element，逐位置对应
        ...
```

### 2.2 调用点扩展（覆盖边界 1/2/3/4）

| 调用点 | 代码位置 | 覆盖 |
|--------|---------|------|
| 简单变量赋值 RHS | `_statement_visitors.py:158-160`（现有改为调用 helper） | 保持 + 递归内层 |
| 函数返回 | `_statement_visitors.visit_IbReturn` + 函数定义处建立 `func_return_types` 栈 | 边界 1 |
| 调用实参 | `_expression_visitors._resolve_with_descriptors`（位置+具名）+ 策略二 | 边界 2 |
| 下标赋值 RHS | `_statement_visitors.py:170-187` 分支 | 边界 3 |

**函数返回类型栈**：`_declaration_visitors.py:141-190` 函数定义处 push 返回类型
（`updated_spec.return_type` 解析为 spec），`finally` pop；`visit_IbReturn` 读栈顶 bind。

### 2.3 运行时 3 点（机制同构复用）

| 改动点 | 方案 | 覆盖 |
|--------|------|------|
| `collections.py:75-77/206-207` | slice 分支用 `self.ib_class` 构造新 IbList/IbTuple（切片对象自身已是特化类） | 边界 5 |
| `runtime_context._wrap_optional` | `declared_type.name` 查特化类（`get_class("Optional[int]")`，loader 已水化），回退基类 | 边界 6 |
| `runtime_serializer._hydrate_specialized_class` | 优先用 `self.type_pool` 重建 spec（`ArtifactRehydrator` 或直接 spec 构造），再 create_subclass | 边界 7 |

---

## 三、工作量评估

| 层 | 改动文件 | 预估改动量 | 风险 |
|----|---------|-----------|------|
| 编译期 helper | `_type_checking_base.py` | ~40 行 | 低（纯 metadata 写入） |
| 编译期调用点×4 | `_statement_visitors.py` / `_expression_visitors.py` / `_declaration_visitors.py` | ~60 行 | 中（须核对各上下文 target 类型可得性） |
| 运行时切片 | `collections.py` | ~10 行 | 低 |
| 运行时 Optional | `runtime_context.py` | ~8 行 | 低 |
| 跨引擎反序列化 | `runtime_serializer.py` | ~20 行 | 低 |
| 判别性回归 | `test_generics_runtime.py` + `test_generic_value_identity.py` | ~30 行 | — |
| 文档 | `_code_generic_type_identity.md` §2.6 移除 + 各文档 | ~20 行 | — |

**总工作量：约 1 个独立窗口（半天量级）**。风险集中在编译期调用点（4 处 target 类型
可得性需逐一核对），运行时 3 点均为低风险机制复用。

**关键考量**：
- 编译期类型安全（缺陷一核心）已在全部场景生效（实证 SEM_TYPE_MISMATCH），本次收敛
  解决的是**内省一致性 + 运行时值层完整身份**——属"根治完整性"而非"修复漏洞"。
- 机制已建立（helper + 特化类水化），推广是增量，非破坏性重构；但涉及编译期多 visitor
  状态共享，按分支政策仍建议独立分支实验确认零风险后 cherry-pick。

## 四、验证计划

- 判别性回归：边界 1-7 各 1+ 用例（type() 断言 + 运行时 is_assignable + round-trip）
- 全量 pytest 零回归
- 嵌套递归正确性（`list[list[list[int]]]` 三层）
- Optional 特化类 round-trip
