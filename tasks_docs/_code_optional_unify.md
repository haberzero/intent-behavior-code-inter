# Optional[T] 值模型统一根治（KI-2 + is_none + is None 语义）

> 2026-08-14。用户授权宏观体系彻底重构（允许破坏性、不留历史包袱、禁兼容/tricky/快速修复）。
> 承接 `_HANDOFF_T05_ISSUES.md` §六.2（KI-2：`Optional[int] a = None; a is None` → False + `is_none()` 缺失）。
> 用户警告：is_none 缺失与 is None 错误背后可能藏有更深的根源问题——本设计经全路径实证确认属实。

## 一、根因（全路径实证）

**`Optional[T]` 空值有两个不一致的运行时表示，取决于值创建路径**：

| 值创建路径 | 空值表示 | `is None` | `== None` | `is_some()` | `type()` |
|---|---|---|---|---|---|
| 局部变量 define/assign/assign_by_uid | `IbOptional(is_some=False)` | **False** | True | 可用 | `Optional[int]` |
| 函数返回 → 变量绑定（带 declared_type） | `IbOptional(is_some=False)` | False | True | 可用 | `Optional[int]` |
| 函数参数绑定（CPS 路径，无 declared_type） | 裸 `IbNone` | **True** | True | 抛错 | `None` |
| 类字段默认值求值（`_eval_field_defaults`） | 裸 `IbNone` | **True** | True | 抛错 | `None` |
| 类字段赋值（`_default_setattr`） | 裸 `IbNone` | **True** | True | 抛错 | `None` |
| 容器元素（list/dict/tuple 字面量 + setitem） | 裸 `IbNone` | **True** | True | 抛错 | `None` |
| thread_result.unwrap（is_some=True 分支） | `IbOptional` | — | — | 可用 | `Optional[int]` |
| 序列化反序列化 | `IbOptional` | — | — | 可用 | `Optional[int]` |

**核心事实**：`_wrap_optional`（runtime_context.py:167）声称"Optional 运行时值的单一绑定入口——所有变量定义/赋值/函数参数/LLMFuture 解析均经此包装"，但**实为谎言**：
- 函数参数绑定（`_shared.py:341/493/224`、`callables.py:180`）经 `define_variable` **不传 declared_type** → 不包装
- 类字段（`_eval_field_defaults`、`_default_setattr`、`_make_chain_auto_init`）裸写 `IbNone`
- 容器元素（`vm_handle_IbListExpr/Dict/Tuple`、`IbList.__setitem__` 等）裸写

**"单一绑定入口"声明与实际实现不符 = 单一权威源被破坏**（design-philosophy 违规）。同一个 `Optional[int]` 类型，空值在变量/返回路径是 `IbOptional` 包装对象，在字段/参数/容器路径是裸 `IbNone` → 一切"按路径分叉"的可观测行为（`is None`/`is_some()`/`type()`）随之分叉。

## 二、设计：统一 Optional 值模型

**核心原则**：`Optional[T]` 空值**恒为** `IbOptional(is_some=False)` 包装对象，任何值创建路径不得产生裸 `IbNone` 作为 Optional 空值。`None` 单例（`IbNone`）仍存在，但**只属于非 Optional 上下文**（`any` 变量、无类型值等）。

### 2.1 单一包装权威（消除"声明 vs 实际"分裂）

`_wrap_optional` 从 `ExecutionContextImpl` 的私有方法提升为**全局权威函数**，所有值创建点经它：

```python
def wrap_optional(value, declared_type, registry) -> value:
    """Optional 空/非空值统一包装权威。幂等。"""
    # declared_type 为 Optional spec（或含 wrapped_type 的 TypeRef/字符串名）时包装；
    # 否则原样返回。is_some = not isinstance(value, IbNone)。
```

签名与放置：`core/runtime/objects/primitives/optional.py`（与 `IbOptional` 同文件，模块级函数），输入 `(value, declared_type, registry)`。`runtime_context._wrap_optional` 委托它（去双实现）。

### 2.2 覆盖全部值创建路径（补齐缺失包装点）

| 路径 | 现状 | 修复 |
|---|---|---|
| 局部变量 define/assign/assign_by_uid | ✓ 已包装 | 委托 2.1 |
| 函数参数绑定 | ✗ 不包装 | `_vm_call_user_function`/`_vm_invoke_llm_function`/`_vm_call_fn_callable`/`bind_behavior_call_args` 绑定前经 2.1 包装（declared_type 从符号 declared_type 取） |
| 类字段默认值 | ✗ 不包装 | `_eval_field_defaults`/`_eval_field_defaults_cps` 写 instance.fields 前按字段类型包装（字段类型经 `ib_class.spec.members[name].type_ref` 解析） |
| 类字段赋值 | ✗ 不包装 | `_default_setattr`（bootstrapper）写 fields 前按字段类型包装；`_make_chain_auto_init` 同 |
| 容器元素 | ✗ 不包装 | 容器字面量 handler（leaf.py `vm_handle_IbListExpr/Dict/Tuple`）建元素时按元素类型包装；`IbList.__setitem__`/`IbDict.__setitem__` 同 |
| thread_result.unwrap | ✓ 已包装 | 保持 |
| 序列化 | ✓ 已包装 | 保持 |

**字段/元素类型解析**（运行时可得）：
- 字段：`ib_class.spec.members[name]` → `MemberSpec.type_ref` → `registry.resolve_typeref`（probe 实证 `field: kind=field type_ref=Optional[int]`）。
- 容器元素：容器值 `ib_class.spec`（`list[Optional[int]]` 的 spec `element_type`/`value_type`/`positional_element_types`）或字面量节点 `node_to_type`。

### 2.3 统一读取语义（is None / is_some 对齐）

**`is`/`is not` 的 None 分支**（leaf.py:268-281）：从 `isinstance(left, IbNone)` 改为**同时识别** `IbNone` 与空 `IbOptional`（`is_some==False`）——即"值是 None 语义"（`is None` ↔ `== None` 一致）。对称 `is not`。

```python
def _is_none_value(v):
    return isinstance(v, IbNone) or (isinstance(v, IbOptional) and not v._is_some)
```

### 2.4 补 `is_none()` 方法

- `OptionalAxiom.get_method_specs`（sentinels.py）声明 `is_none: () -> bool`（当前无）。
- `IbOptional.is_none()`：`return box(not self._is_some)`。
- `is_some`/`is_none` 对称，文档统一判空 API（`== None`/`is None`/`is_none()` 三者等价）。

### 2.5 顺带根治深挖暴露的伴生缺陷

1. **`try_deep_clone` 对 IbOptional 丢 `_is_some`**（deep_clone.py:110-123 通用 IbValue 分支只复制 payload/meta/fields，不复制 `_is_some` slot）→ 克隆产物 `_is_some` 未初始化。加 IbOptional 专门分支复制 `_is_some`（且 payload 深克隆）。
2. **`member_types` 死字段**（ib_class.py:161 全仓无填充）——本设计用它缓存字段声明类型（消除每次写字段重复解析 spec.members），作为 2.2 的字段类型单一权威缓存。填充点：`_hydrate_user_classes`（interpreter.py:680-695 注册字段处）从 spec.members 填。
3. **函数参数符号 spec 恒为 any**（symbol_resolution_pass.py:136 `_register_params` 硬编码 `spec=registry.resolve("any")`）——参数声明类型从不进入运行时符号池，是参数路径 Optional 值无法包装的**真正根因**。修复：从参数注解解析 spec（含泛型/模块限定，与 symbol_collection `_resolve_annotation` 同构）。连带使运行时 `_check_type` 对参数生效（此前 any 跳过）。
4. **llmexcept 快照误捕获类/类型符号**（llm_except_frame.py:173 遍历当前作用域全部符号，类对象 `IbClass` 也作为协议变量快照；类声明 `__snapshot__`/`__restore__` 时以类为 receiver 调 `__restore__` 且参数类型检查失败）——参数类型修复暴露此预存缺陷。修复：快照循环跳过 `IbClass` 值（只快照真实实例/值）。
5. **`None == 空 Optional` 不对称**（sentinels.py `IbNone.__eq__` 仅 `isinstance(right, IbNone)`，`x == None` True 但 `None == x` False）——统一判空权威 `is_none_value` 双向对齐。
6. **`None is 空 Optional` 不对称**（leaf.py `is`/`is not` 分支按 `isinstance(right, IbNone)` 判定走 None 分支，`x is None` True 但 `None is x` False）——分支判据改 `is_none_value(right)`。**复核修正**：分支判据维持 `isinstance(right, IbNone)`（字面量 None），仅结果计算用 `is_none_value(current_left)`——避免 `a is b`（两个不同空 Optional 实例）被误判为同一（恒等语义不吞并）。
7. **`_element_spec_for` dict value_type 被遮蔽**（collections.py：dict spec 的 `element_type` 恒为 `TypeRef("any")` 非 None，先取 element_type 后取 value_type → dict 永远解析到 any，`dict[str,Optional[int]]` setitem/update 不包装）——按 kind 分派：DICT 优先 `value_type`。
8. **`IbList.__add__`/`__mul__` 产物元素不规范化**（拼接/重复产物直接 `IbList(list+list, ib_class)`，未按元素类型重包装；`list[Optional[int]] c = a + [None]` 的 `[None]` 元素经幻影 `list[None]` 特化被 `_bind_container_specialization` 跳过）——`__add__`/`__mul__` 产物元素经 `_wrap_element_value` 归一化。
9. **LLM 解析策略二兜底注入裸写字段**（llm_parsing_strategy.py `auto_instance.fields[first_field] = parsed_val` 绕过 `_wrap_field_value`）——改经 `ib_class._wrap_field_value`。
10. **死导入**（runtime_context.py `IbNone`/`IbOptional` 委托 wrap_optional 后无代码引用）——移除。

### 2.6 文档同步

- `docs/syntax/03_operators.md`：`is None` 对空 Optional 返回 True 的说明（当前 doc-governance 已改"Optional 判空用 == None"，改为"三等价"表述）。
- `docs/architecture/03_type_system.md` §8：补 `is_none` 声明 + 统一值模型表述。
- `docs/KNOWN_LIMITS.md`：如有 Optional 空值表示相关边界则更新。
- `docs/syntax/15_diagnostics.md`：不涉。

## 三、判别性回归（tests/）

新增 `tests/runtime/test_optional_value_model.py`：
1. `Optional[int] a = None; a is None` → True（修复前 False）
2. `Optional[int] a = None; a is not None` → False
3. `Optional[int] a = None; a.is_none()` → True；`a.is_some()` → False
4. `Optional[int] b = 5; b.is_none()` → False；`b is None` → False
5. `any c = None; c is None` → True（不回归，IbNone 路径）
6. `None == None` → True（不回归）
7. 函数参数 `func f(Optional[int] p) -> bool: return p is None`；`f(None)` → True（修复前 False）
8. 类字段 `class B: Optional[int] f`；`B b = B(None); b.f is None` → True（修复前 True 但 type 为 None；现应 type=Optional[int] 且 `b.f.is_none()` 可用）
9. 容器元素 `list[Optional[int]] l = [None]; l[0] is None` → True + `l[0].is_none()` 可用
10. 深克隆：Optional 空值 try_deep_clone 后 `is_none()`/`is_some()` 可用（_is_some 保真）
11. 既有 `test_optional_runtime.py` 全量保持（is_some/unwrap/or_else/to_bool 不变）
12. `None == x` / `None is x` 对称（空 Optional 双向 True）
13. `Optional[Optional[int]]` 嵌套空值统一包装
14. 函数返回 Optional 空值 is_none 可用
15. 字段重赋值（None→值 / 值→None）包装

## 四、风险与分支政策

- 影响面：核心值模型 + VM 赋值/参数/字段/容器多条路径。**破坏性大**，按 AGENTS.md 分支政策走**独立分支**实验，全量 pytest 零回归 + 判别性回归 + 独立复核后手动 cherry-pick unsafe-vibe-dev。
- 不触碰 main。
- 全程本地 commit、禁 push。

## 五、非目标

- 不改变 Optional 的编译期类型检查（`is_assignable`/SEM 规则）。
- 不引入 Optional 运算符自动解包（`Optional[int] + int` 仍编译期拒绝——既有语义）。
- 不改 `Optional` 泛型特化/序列化格式（既有 round-trip 保真保留）。
