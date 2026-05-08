# `deferred` 概念彻底清理计划

> **状态：✅ 已完成（2026-05-08）**
>
> **目标**：将 `deferred` 这个命名/概念从 IBCI 中彻底移除，使 `lambda`/`snapshot` 产生的可调用实例在语言中的地位与普通函数完全平等，不再携带"延迟执行"的语义标签。
>
> **设计原则**：行为描述表达式（`@~...~`）在 IBCI 中的地位应当和其它平常的编程表达式完全平等。`lambda`/`snapshot` 产生的可调用实例本质上是函数，只是在**捕获语义**（引用 vs 快照）和**执行引擎**（普通 AST 重访 vs LLM 调用）上有所不同——这些差异通过**类型的区分**（`fn_callable` vs `behavior`）和**值的属性**（`capture_mode`）表达，而不是通过一个叫"deferred（延迟）"的专有概念来表达。
>
> **最后更新**：2026-05-08（已落地）

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

| 旧概念 | 新名称 | 说明 |
|--------|--------|------|
| `deferred` 类型 | `fn_callable` | `fn f = lambda: expr` 产生的是 `fn_callable` 类型的可调用实例 |
| `IbDeferred` 运行时对象 | `IbFnCallable` | 运行时类名反映语言语义 |
| `DeferredAxiom` | `FnCallableAxiom` | 公理名称反映语言概念 |
| `DEFERRED_SPEC` | `FN_CALLABLE_SPEC` | spec 常量名称对齐 |
| `create_deferred()` | `create_fn_callable()` | 工厂方法名称对齐 |
| `IbDeferredField` | `IbClassField` | 纯 Python 字段描述符，与 IBCI 类型无关 |

---

## 影响清单（已全部完成 ✅）

所有层次的修改已落地，IBCI 核心代码中不再出现任何与"延迟求值/deferred"概念相关的命名、字符串或变量名。

---

## 执行阶段划分（✅ 所有阶段已完成）

### 阶段 D1：核心命名决策 ✅

**已确定的命名方案**：

- `deferred` 类型名 → **`fn_callable`**（显式区分"behavior callable"，突出"fn 型可调用实例"）
- `IbDeferred` Python 类 → **`IbFnCallable`**
- `DeferredAxiom` → **`FnCallableAxiom`**，`name = "fn_callable"`
- `DEFERRED_SPEC` 常量 → **`FN_CALLABLE_SPEC`**，`name = "fn_callable"`
- `create_deferred()` → **`create_fn_callable()`**
- `_deferred_desc` 变量 → **`_fn_callable_desc`**
- `_vm_call_deferred()` 函数 → **`_vm_call_fn_callable()`**
- `IbDeferredField`（字段描述符）→ **`IbClassField`**（纯 Python 实现概念，与 IBCI 类型无关）
- 继承链：`behavior IS-A fn_callable IS-A callable → Object`
- 序列化策略：**无向后兼容**，旧 artifact 需要重新编译

### 阶段 D2：类型系统与公理层 ✅

已完成：`specs.py`、`axioms/primitives.py`、`spec/registry.py`、`spec/type_ref.py`、`spec/__init__.py`。

### 阶段 D3：运行时对象层 ✅

已完成：`builtins.py`（`IbFnCallable`）、`kernel.py`（`IbClassField`）、`cell.py`。

### 阶段 D4：工厂与基础设施层 ✅

已完成：`factory.py`、`interfaces.py`、`builtin_initializer.py`、`engine.py`。

### 阶段 D5：VM 层与编译器层 ✅

已完成：`handlers.py`、`llm_except_frame.py`、`runtime_serializer.py`、`artifact_rehydrator.py`、`semantic_analyzer.py`、`serializer.py`。

### 阶段 D6：测试层 ✅

已完成：`test_e2e_deferred.py` → `test_e2e_fn_callable.py`；所有断言字符串更新。全量 1180 tests passed。

### 阶段 D7：文档层 ✅

已完成：`ARCH_DETAILS.md`、`IBCI_SYNTAX_REFERENCE.md`、`PENDING_TASKS_VM.md`、`TYPE_SYSTEM_TASKS.md` 相关描述更新。

---

## 关于 `behavior` 类型的定位

本次清理**不**移除 `behavior` 类型和 `BehaviorAxiom`。`behavior` 保留独立子类型的原因：

1. 它确实有独特的能力标记（`has_llm_call_cap = True`），编译期 DDG（数据依赖图）通过此能力识别 LLM 调用节点
2. 它与 `fn_callable` 的根本区别是**执行引擎**（LLM vs 普通 AST 求值），这个差异需要在类型层可见
3. `behavior` 类型的可调用实例（`@~...~` 包裹在 `lambda`/`snapshot` 中）仍然需要被 LLMExecutor 特殊处理

**已实现的继承链**：
```
Object
  └── callable          (has_call_cap)
       ├── fn_callable   (has_call_cap)   ← lambda/snapshot 产生的普通可调用实例
       │                                    capture_mode: lambda | snapshot
       └── behavior      (has_call_cap + has_llm_call_cap)   ← LLM 可调用实例
                                            capture_mode: lambda | snapshot
```


---

## 关于"行为描述表达式地位与普通表达式平等"的一致性说明

移除 `deferred` 后，语言语义体现以下一致性：

- `fn f = lambda -> int: expr` → `f` 的类型为 `fn_callable`，`f()` 就是函数调用
- `fn[()->behavior] g = lambda -> behavior: @~ LLM task ~` → `g()` 就是函数调用，返回 behavior 类型
- `behavior h = snapshot -> str: @~ LLM task ~` → `h` 就是一个 behavior 可调用实例，`h()` 触发 LLM

用户不需要知道"fn_callable 对象"的内部实现，只需要知道"函数可以用 lambda/snapshot 定义，behavior 函数由 LLM 驱动"。

---

