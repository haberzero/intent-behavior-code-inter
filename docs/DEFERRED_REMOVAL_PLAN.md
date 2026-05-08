# `deferred` 概念彻底清理计划

> **目标**：将 `deferred` 这个命名/概念从 IBCI 中彻底移除，使 `lambda`/`snapshot` 产生的可调用实例在语言中的地位与普通函数完全平等，不再携带"延迟执行"的语义标签。  
>
> **设计原则**：行为描述表达式（`@~...~`）在 IBCI 中的地位应当和其它平常的编程表达式完全平等。`lambda`/`snapshot` 产生的可调用实例本质上是函数，只是在**捕获语义**（引用 vs 快照）和**执行引擎**（普通 AST 重访 vs LLM 调用）上有所不同——这些差异通过**类型的区分**（`fn` vs `behavior`）和**值的属性**（`capture_mode`）表达，而不是通过一个叫"deferred（延迟）"的专有概念来表达。
>
> **最后更新**：2026-05-08（初稿）

---

## 背景：什么是 `deferred`，为什么要移除它

### 历史来源

`deferred` 是 IBCI 早期为了处理 `lambda`/`snapshot` 语法而引入的运行时概念，表示"一个被延迟求值的表达式"。在早期架构中，这个概念是必要的，因为 LLM 行为表达式确实需要被"包装"起来延迟到合适的时机执行。

### 为什么它现在是多余的

1. **`TypeKind.DEFERRED` 已被合并**（M3→M5 已完成）：`TypeKind.DEFERRED` + `TypeKind.BEHAVIOR` 已合并为 `TypeKind.CALLABLE_INSTANCE`，`deferred_mode` 已重命名为 `capture_mode`。类型 *kind* 层面的"deferred"概念已经消失。

2. **`lambda`/`snapshot` 产生的就是可调用实例，不是"延迟"**：从语言用户的视角看，`fn f = lambda -> int: expr` 定义的 `f` 就是一个函数，不是一个"延迟对象"。调用 `f()` 就是调用函数，不是"触发延迟求值"。"延迟"这个词是一个实现层的描述，不应该暴露为语言语义。

3. **行为描述表达式（`@~...~`）的地位应与普通表达式平等**：`behavior` 类型的可调用实例（由 `lambda`/`snapshot` 包裹 `@~...~` 产生）与普通 `fn` 的可调用实例应在语言地位上对等。现在 `behavior IS-A deferred`（继承链：`behavior → deferred → callable`）意味着 behavior 被建模为"一种特殊的延迟执行"，这与目标不符。

4. **用户不应看到 `deferred`**：在用户的 IBCI 代码中，`deferred` 这个类型名不应出现，也不应有对应的语法关键字。

### 移除后的语义体系

| 概念 | 替换方案 | 说明 |
|------|----------|------|
| `deferred` 类型 | `fn` 类型（捕获模式 lambda/snapshot） | `fn f = lambda: expr` 产生的是 `fn` 类型的可调用实例 |
| `IbDeferred` 运行时对象 | `IbCallable` 或并入 `IbBehavior` 的 `fn` 变体 | 运行时类名反映语言语义 |
| `DeferredAxiom` | `FnAxiom`（或扩展 `CallableAxiom`） | 公理名称反映语言概念 |
| `DEFERRED_SPEC` | `FN_CALLABLE_SPEC` | spec 常量名称对齐 |
| `create_deferred()` | `create_fn_callable()` | 工厂方法名称对齐 |

---

## 影响清单：所有需要修改的位置

### 层次一：公理与类型系统层（`core/kernel/`）

| 文件 | 当前状态 | 目标状态 |
|------|----------|----------|
| `core/kernel/spec/specs.py:41` | `DEFERRED_SPEC = TypeDef(name="deferred", ...)` | 重命名为 `FN_CALLABLE_SPEC = TypeDef(name="fn_callable", ...)` 或设计为与 `behavior` 对称的 `fn`-callable 体系 |
| `core/kernel/axioms/primitives.py` | `class DeferredAxiom(BaseAxiom): name="deferred"` | 重命名为 `FnCallableAxiom`，name 改为新名称 |
| `core/kernel/axioms/primitives.py` | `BehaviorAxiom.is_compatible: other_name in ("behavior", "deferred", "callable")` | 移除 `"deferred"` 字符串，改为新名称 |
| `core/kernel/axioms/primitives.py` | `register_primitives`: `registry.register(DeferredAxiom())` | 改为注册新公理 |
| `core/kernel/spec/registry.py` | `create_deferred()` 方法，`deferred_name`，`spec._axiom_name = "deferred"` | 方法重命名，axiom name 更新 |
| `core/kernel/spec/type_ref.py` | `if base in ("deferred", "behavior") ...` | 更新字符串 |

### 层次二：运行时对象层（`core/runtime/objects/`）

| 文件 | 当前状态 | 目标状态 |
|------|----------|----------|
| `core/runtime/objects/builtins.py:694` | `@register_ib_type("deferred")` / `class IbDeferred(IbValue)` | 类重命名为 `IbFnCallable`（或等价名称），`@register_ib_type` 更新 |
| `core/runtime/objects/builtins.py` | class docstring 中大量"deferred"/"延迟"语义说明 | 更新为"可调用实例"语义 |
| `core/runtime/objects/builtins.py` | `IbBehavior` docstring: "behavior 是 deferred 的特化子类型" | 更新为"behavior 是 LLM 驱动的可调用实例，fn_callable 是普通表达式驱动的可调用实例" |
| `core/runtime/objects/kernel.py` | `from core.runtime.objects.builtins import IbDeferred, IbBehavior` | 更新导入 |

### 层次三：工厂与基础设施层

| 文件 | 当前状态 | 目标状态 |
|------|----------|----------|
| `core/runtime/factory.py:10` | `from ... import IbBehavior, IbDeferred, ...` | 更新导入 |
| `core/runtime/factory.py:44-46` | `create_deferred()` 方法 | 方法重命名为 `create_fn_callable()` |
| `core/runtime/interfaces.py` | `IObjectFactory.create_deferred` 抽象方法 | 抽象方法重命名 |
| `core/runtime/bootstrap/builtin_initializer.py` | `core_axioms = [..., "deferred", ...]` | 更新公理名称字符串 |

### 层次四：VM 调度层（`core/runtime/vm/`）

| 文件 | 当前状态 | 目标状态 |
|------|----------|----------|
| `core/runtime/vm/handlers.py:232` | `_vm_call_deferred()` 函数名 | 重命名为 `_vm_call_fn_callable()` |
| `core/runtime/vm/handlers.py:313` | `func.ib_class.name == "deferred"` 特判 | 更新字符串 |
| `core/runtime/vm/handlers.py:1353` | `create_deferred(...)` 调用 | 更新为新方法名 |
| `core/runtime/vm/handlers.py` | 注释中大量"IbDeferred"/"lambda/snapshot"/"deferred 模式"说明 | 更新为新命名 |

### 层次五：解释器与执行器层

| 文件 | 当前状态 | 目标状态 |
|------|----------|----------|
| `core/runtime/interpreter/interpreter.py` | `from ... import IbDeferred, IbBehavior` | 更新导入 |
| `core/runtime/interpreter/llm_except_frame.py:210-232` | `_try_deep_clone` 中对 `"deferred"` 类型的排除逻辑 | 更新字符串 |
| `core/runtime/serialization/runtime_serializer.py` | `cls_name == "deferred"` / `data["_type"] = "deferred"` | 更新字符串（注意向后兼容性） |

### 层次六：加载器（`core/runtime/loader/`）

| 文件 | 当前状态 | 目标状态 |
|------|----------|----------|
| `core/runtime/loader/artifact_rehydrator.py` | `factory.create_deferred(...)` 调用 | 更新为新方法名 |
| `core/runtime/loader/artifact_rehydrator.py` | 注释中"deferred/behavior axiom"说明 | 更新注释 |

### 层次七：编译器层（`core/compiler/`）

| 文件 | 当前状态 | 目标状态 |
|------|----------|----------|
| `core/compiler/semantic/passes/semantic_analyzer.py` | `self._deferred_desc = self.registry.resolve("deferred")` | 更新为新名称 |
| `core/compiler/semantic/passes/semantic_analyzer.py` | `self.registry.factory.create_deferred(...)` | 更新为新方法名 |
| `core/compiler/semantic/passes/semantic_analyzer.py` | `return self._deferred_desc` | 更新变量名 |
| `core/compiler/serialization/serializer.py` | 注释中"deferred / behavior"序列化说明 | 更新注释 |

### 层次八：测试层（`tests/`）

| 文件 | 当前状态 | 目标状态 |
|------|----------|----------|
| `tests/e2e/test_e2e_deferred.py` | 整个文件以 `deferred` 命名 | 文件重命名为 `test_e2e_fn_callable.py`（或 `test_e2e_lambda_snapshot.py`），测试描述更新 |
| `tests/runtime/test_ib_value.py` | `"deferred"` 字符串出现处 | 更新为新名称 |
| `tests/kernel/test_typeref.py` | `"deferred"` 字符串出现处 | 更新为新名称 |
| `tests/e2e/test_e2e_m2_higher_order.py` | `deferred` 相关测试描述 | 更新描述 |
| `tests/e2e/test_e2e_ai_mock.py` | `deferred` 相关测试描述 | 更新描述 |
| `tests/e2e/test_e2e_llm_pipeline.py` | `deferred` 相关测试描述 | 更新描述 |
| `tests/compiler/test_compiler_pipeline.py` | `deferred` 相关测试描述 | 更新描述 |

### 层次九：文档层（`docs/`）

| 文件 | 处理方式 |
|------|----------|
| `docs/ARCH_DETAILS.md` | 更新继承链描述，移除 `deferred` 子层；更新类型兼容表 |
| `docs/IBCI_SYNTAX_REFERENCE.md` | 更新 `fn` / `lambda` / `snapshot` 的类型说明，移除 `deferred` 作为类型标签的出现 |
| `docs/COMPLETED.md` | 历史记录，保留原始描述，但在相关章节顶部加注"当前实现已移除 deferred 概念，见 DEFERRED_REMOVAL_PLAN.md" |
| `docs/PENDING_TASKS_VM.md` | 更新 `_vm_call_deferred` 相关描述 |
| `docs/INTENT_SYSTEM_DESIGN.md` | 更新提到 `deferred` 的章节 |

---

## 执行阶段划分

### 阶段 D1：核心命名决策（前置，需要确认）

在动手之前，需要先确定以下命名，以保持一致性：

**问题 1**：`lambda`/`snapshot` 产生的普通（非 LLM）可调用实例的新类型名是什么？

选项：
- **`fn_callable`**：显式区分于"behavior callable"，突出"fn 型可调用实例"
- **`lambda`**：用语法关键字作为类型名（类似 Python 的 lambda 对象），语义清晰但与关键字重名
- **`callable`**（直接归入）：不区分，`lambda`/`snapshot` 产生的实例 IS-A `callable`，不再有独立子类型

**当前倾向**：使用 `callable` 路线——`lambda`/`snapshot` 产生的可调用实例不需要在类型层有单独名称，它们是带有 `capture_mode` 属性的 `callable`；类型系统层面用 `fn` 关键字推断即可。`behavior` 保持独立子类型，因为它确实需要 `has_llm_call_cap` 区分。

> ⚠️ **此决策影响所有后续步骤，必须在开工前确认。**

**问题 2**：序列化向后兼容策略？

现有的 artifact（`.ibci.json`）中可能包含 `"axiom_name": "deferred"` 字段。移除后需要决定：
- **策略 A**：完全不向后兼容，旧 artifact 需要重新编译
- **策略 B**：加载时别名映射（读取旧名称时自动映射到新名称）

**当前倾向**：策略 B（加载时别名映射），在 artifact rehydrator 中加一个名称迁移表，让旧 artifact 在过渡期内仍可加载。

---

### 阶段 D2：类型系统与公理层（独立，无外部依赖）

**工作内容**：
1. `core/kernel/spec/specs.py`：移除 `DEFERRED_SPEC` 常量（若选择"直接归入 callable"路线），或重命名
2. `core/kernel/axioms/primitives.py`：删除 `DeferredAxiom` 类（若归入 callable），或重命名为 `FnCallableAxiom`；更新 `BehaviorAxiom.is_compatible` 中的 `"deferred"` 字符串
3. `core/kernel/spec/registry.py`：删除/重命名 `create_deferred()` 方法；更新 axiom 名称字符串
4. `core/kernel/spec/type_ref.py`：更新 `base in ("deferred", "behavior")` 处

**验收标准**：类型系统层无 `deferred` 字面量残留；`deferred` 公理不再独立注册。

---

### 阶段 D3：运行时对象层

**工作内容**：
1. `core/runtime/objects/builtins.py`：`IbDeferred` 重命名（或与其他类型合并），更新 `@register_ib_type`，更新 docstring 中的"延迟"语义说明
2. `core/runtime/objects/builtins.py`：`IbBehavior` docstring 更新，移除"behavior 是 deferred 的特化"描述，改为"LLM 驱动的可调用实例"
3. `core/runtime/objects/kernel.py`：更新导入

**验收标准**：`IbDeferred` 类名不再存在（或作为显式弃用别名），运行时对象不再携带"延迟"概念。

---

### 阶段 D4：工厂与基础设施层

**工作内容**：
1. `core/runtime/factory.py`：`create_deferred()` 重命名，更新导入
2. `core/runtime/interfaces.py`：抽象方法重命名
3. `core/runtime/bootstrap/builtin_initializer.py`：更新公理名称列表

**验收标准**：工厂 API 不再暴露 `deferred` 相关名称。

---

### 阶段 D5：VM 层与编译器层

**工作内容**：
1. `core/runtime/vm/handlers.py`：`_vm_call_deferred()` 重命名，更新 `func.ib_class.name` 字符串特判，更新 `create_deferred()` 调用，更新注释
2. `core/runtime/interpreter/llm_except_frame.py`：更新 `_try_deep_clone` 中的类型名字符串
3. `core/runtime/serialization/runtime_serializer.py`：更新序列化字符串（配合向后兼容策略）
4. `core/runtime/loader/artifact_rehydrator.py`：更新加载路径，加入迁移别名映射（如采用策略 B）
5. `core/compiler/semantic/passes/semantic_analyzer.py`：更新变量名和方法调用
6. `core/compiler/serialization/serializer.py`：更新注释

**验收标准**：VM 和编译器中无 `deferred` 字面量（注释中历史记录除外）。

---

### 阶段 D6：测试层

**工作内容**：
1. 重命名 `tests/e2e/test_e2e_deferred.py`
2. 更新所有测试文件中的 `"deferred"` 断言字符串和描述字符串

**验收标准**：全量测试通过（当前基线 1184 tests）；测试名称/描述中无 `deferred`。

---

### 阶段 D7：文档层

**工作内容**：更新 `docs/ARCH_DETAILS.md`、`docs/IBCI_SYNTAX_REFERENCE.md`、`docs/PENDING_TASKS_VM.md`、`docs/INTENT_SYSTEM_DESIGN.md` 中的相关描述。

**验收标准**：所有面向用户的文档中不再有 `deferred` 作为语言概念出现；技术历史文档（`COMPLETED.md`）中的历史记录保留，但加注说明。

---

## 阶段间依赖关系

```
D1（命名决策）
    ↓
D2（类型系统/公理）── D3（运行时对象）
    ↓                      ↓
    └──────────────── D4（工厂/基础设施）
                           ↓
                   D5（VM/编译器）
                           ↓
                   D6（测试）
                           ↓
                   D7（文档）
```

D1 是前置决策，D2 和 D3 可以并行，D4 依赖 D2+D3，D5 依赖 D4，D6 依赖 D5，D7 可在任意阶段推进。

---

## 关于 `behavior` 类型的定位

本次清理**不**移除 `behavior` 类型和 `BehaviorAxiom`。`behavior` 保留独立子类型的原因：

1. 它确实有独特的能力标记（`has_llm_call_cap = True`），编译期 DDG（数据依赖图）通过此能力识别 LLM 调用节点
2. 它与 `fn` 的根本区别是**执行引擎**（LLM vs 普通 AST 求值），这个差异需要在类型层可见
3. `behavior` 类型的可调用实例（`@~...~` 包裹在 `lambda`/`snapshot` 中）仍然需要被 LLMExecutor 特殊处理

**目标继承链（移除 deferred 后）**：
```
Object
  └── callable          (has_call_cap)
       ├── fn_callable   (has_call_cap)   ← lambda/snapshot 产生的普通可调用实例
       │                                    capture_mode: lambda | snapshot
       └── behavior      (has_call_cap + has_llm_call_cap)   ← LLM 可调用实例
                                            capture_mode: lambda | snapshot
```

或者，如果采用"直接归入 callable"路线：
```
Object
  └── callable          (has_call_cap)   ← lambda/snapshot 产生的普通可调用实例
       └── behavior      (has_call_cap + has_llm_call_cap)   ← LLM 可调用实例
```

> ⚠️ 最终选择哪种继承结构取决于阶段 D1 的命名决策。

---

## 关于"行为描述表达式地位与普通表达式平等"的一致性说明

移除 `deferred` 后，语言语义将体现以下一致性：

- `fn f = lambda -> int: expr` → `f` 的类型为 `fn`（或 `callable`），`f()` 就是函数调用
- `fn[()->behavior] g = lambda -> behavior: @~ LLM task ~` → `g()` 就是函数调用，返回 behavior 类型
- `behavior h = snapshot -> str: @~ LLM task ~` → `h` 就是一个 behavior 可调用实例，`h()` 触发 LLM

用户不需要知道"deferred 对象"的存在，只需要知道"函数可以用 lambda/snapshot 定义，behavior 函数由 LLM 驱动"。

---

## 当前状态与可开工条件

**当前状态**：本文档为计划草稿，尚未开始实施。

**开工前置条件**：
1. 阶段 D1 命名决策已确认（"fn_callable" 还是"直接归入 callable"，序列化兼容策略）
2. 在开始 D2 之前，运行 `python -m pytest tests/ -q --tb=short` 确认当前基线（预期 1184 tests passed）
