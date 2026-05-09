# 泛型与容器相关设计问题

> 状态：**已知问题，暂不处理**。此文件作为未来深度优化的追踪记录。

---

## 背景

IBCI 当前支持基础容器类型 `list`、`dict`、`tuple`，以及通过下标语法声明的泛型形式（`list[int]`、`dict[str, int]` 等）。但当前的泛型实现是浅层的、不完整的，存在若干已知设计缺陷与限制，需要在未来进行系统性改进。

---

## 已知问题一览

### 1. 下标访问的类型推断不完整

**现象**：`list[int]` 类型的变量通过下标访问时，返回类型被推断为 `any` 而非 `int`。

```ibci
list[int] nums = [1, 2, 3]
int x = nums[0]          # ✅ 编译期可能通过（any → int 赋值）
```

**根因**：`ListAxiom.__getitem__` 的返回类型被声明为 `any`，泛型参数未被传播到下标运算结果的类型推断中。

**影响**：类型安全性降低；在严格类型检查场景下，用户需要手动临时变量承接。

---

### 2. 泛型特化（specialization）的运行时 axiom 方法未引导

**现象**：动态创建的泛型特化（如 `list[str]`）在 `SpecRegistry.resolve_specialization()` 中注册，但新注册的特化 spec 没有经过 `_bootstrap_axiom_methods()`，导致部分 axiom 方法在特化类型上不可用。

**当前缓解**：`resolve_specialization` 中有手工调用 `_bootstrap_axiom_methods` 的逻辑作为补偿。但此逻辑覆盖不完整，边界情况下仍可能失败。

**影响**：特化容器类型（如 `list[str]`）的方法调用在部分场景下可能返回 `any` 或引发运行时错误。

---

### 3. 嵌套容器的链式下标类型推断缺失

**现象**：对嵌套容器（如 `list[list[int]]`）进行链式下标访问时，内层访问结果的类型无法正确推断。

```ibci
list items = [[1, 2], [3, 4]]
any inner = items[0]           # inner 推断为 any（无法进一步推断为 list[int]）
any x = inner[0]               # 可用，但类型不安全
```

**根因**：当前下标访问在语义分析阶段不追踪泛型参数，无法实现嵌套泛型的类型传播。

---

### 4. `dict` 的键值类型在下标访问时未检查

**现象**：`dict[str, int]` 的键类型不被运行时下标访问代码验证。

```ibci
dict[str, int] d = {"a": 1}
int v = d["a"]                  # ✅ 运行时正确
int v2 = d[42]                  # ⚠️ 键类型不匹配，但运行时不报错
```

**影响**：字典键类型安全由用户自行保证，编译器/运行时不提供保护。

---

### 5. `tuple` 无泛型元素类型支持

**现象**：`tuple` 类型不支持元素类型标注（如 `tuple[int, str]`），元素访问始终返回 `any`。

**影响**：元组在 IBCI 中只能作为无类型的多值容器使用，无法进行元素级别的类型检查。

---

### 6. 泛型类型实例的 `is_assignable` 兼容性规则不完整

**现象**：`list[int]` 与 `list` 的赋值兼容性（子类型关系）未通过公理明确定义。

```ibci
list[int] specific = [1, 2, 3]
list generic = specific          # ⚠️ 可能触发 SEM_003 或运行时错误
```

**根因**：`SpecRegistry.is_assignable` 的泛型协变/不变规则未实现。

---

## 未来优化方向

1. **泛型参数传播**：`ListAxiom`、`DictAxiom` 的 `__getitem__` 返回类型应通过泛型参数动态推导（而非硬编码 `any`）。
2. **泛型协变规则**：建立 `list[T]` isa `list`、`list[T]` isa `list[U]`（当 T isa U 时）的类型兼容规则。
3. **嵌套泛型推断**：扩展语义分析器的下标类型推断，支持链式下标的逐层解包。
4. **特化 axiom 自动引导**：`resolve_specialization` 应自动完整地为新特化 spec 绑定所有 axiom 方法。
5. **`tuple` 类型标注**：考虑支持 `tuple[T1, T2, ...]` 语法，为固定结构的多值返回提供类型安全。

---

*最后更新：2026-04-22*
