# IBC-Inter 重要架构细节备份

> 本文档记录 IBC-Inter 在历次重构中形成的重要架构细节与设计决策。
> 这些内容已在代码中稳定落地，但因过于具体而不适合放入总体架构说明。
> 供开发者深入理解各模块实现时参考。
>
> **最后更新**：2026-04-17

---

## 一、llmexcept / retry 机制：影子执行驱动模式

### 1.1 架构演进历程

llmexcept 机制经历了三个阶段的演进：

- 阶段一：用 Python try-except 捕获 `LLMUncertaintyError` 异常，逻辑分散于各 visit 方法中，异常冒泡路径难以维护
- 阶段二：引入 `_with_unified_fallback` 统一包装器，对 `visit_IbIf/While/For` 等节点进行隐式 fallback 包裹
- 阶段三（当前）：彻底废弃上述两种方式，采用"影子执行驱动模式"

### 1.2 当前架构：影子执行驱动模式

`_with_unified_fallback` 包装器和 `LLMUncertaintyError` 异常均已完全废弃（代码中不存在）。当前实现的核心思路：

- `visit_IbLLMExceptionalStmt` 是主控外壳，主动调用 `execution_context.visit(target_uid, bypass_protection=True)` 驱动目标节点执行
- LLM 执行器不再抛出异常，改为通过 `LLMResult.is_uncertain` 标志位传递不确定性信号
- `runtime_context.set_last_llm_result(result)` 将每次 LLM 调用的结果存入上下文，供外层轮询检查
- `visit_IbAssign` 检测 `last_llm_result.is_uncertain`，若为 True 则将目标变量赋值为 `IbLLMUncertain` 哨兵对象（而非跳过赋值）
- `visit_IbIf/While/For` 检测 `last_llm_result.is_uncertain`，若为 True 则立即返回空结果，不执行分支体
- 外层 `visit_IbLLMExceptionalStmt` 检测此标志，决定是否进入 llmexcept 块

### 1.3 完整执行流程

```
visit_IbLLMExceptionalStmt
  │
  ├── save_llm_except_state()  → 创建 LLMExceptFrame，保存变量/意图/loop 快照
  │
  └── while frame.should_continue_retrying():
        │
        ├── frame.restore_snapshot()          → 恢复变量/意图/loop 快照
        ├── runtime_context.set_last_llm_result(None)  → 清除上次标志
        ├── execution_context.visit(target_uid)        → 执行目标语句
        │       │
        │       └── [内部] LLM调用
        │                 → LLMResult(is_uncertain=True/False)
        │                 → set_last_llm_result(result)
        │
        ├── 检查 last_llm_result.is_uncertain
        │
        │   [False / None] → break，正常退出
        │
        └── [True] → 清除 last_llm_result（防止 body 内赋值受干扰）
                   → 执行 body 块（llmexcept 块）
                         │
                         └── visit_IbRetry
                                 → 设置 runtime_context.retry_hint
                                 → frame.restore_snapshot()
                                 → frame.should_retry = True
                   → frame.increment_retry()  → 检查是否超过 max_retry
```

### 1.4 LLMExceptFrame：轻量级现场帧

`LLMExceptFrame`（`core/runtime/interpreter/llm_except_frame.py`）保存以下状态：

| 字段 | 内容 |
|------|------|
| `saved_vars` | 可序列化类型的变量快照（IbNone/IbInteger/IbFloat/IbString/IbList/IbDict） |
| `saved_intent_stack` | 意图栈顶节点 `_intent_top` 的引用（IntentNode 链表头） |
| `saved_loop_context` | 循环上下文列表（`_loop_stack` 的浅拷贝） |
| `saved_retry_hint` | 上次保存的 retry 提示词 |
| `max_retry` | 最大重试次数，从 `llm_provider.get_retry()` 读取 |

不参与快照的类型（设计决定）：IbFunction、IbBehavior、IbNativeObject 等引用类型。

`LLMExceptFrameStack` 管理嵌套的 llmexcept 块，支持多层嵌套场景（当前阶段主要使用单层）。

### 1.5 max_retry 配置穿透

```
用户脚本: ai.set_retry(5)
    → AIPlugin._config["retry"] = 5
    → AIPlugin.get_retry() 返回 5

visit_IbLLMExceptionalStmt:
    → capability_registry.get("llm_provider") → AIPlugin 实例
    → llm_provider.get_retry() → 5
    → max_retry = 5
```

`max_retry` 默认值为 3，通过 `ai.set_retry()` 可覆盖。

---

## 二、LLMResult 不确定性信号机制

LLM 调用结果统一通过 `LLMResult`（`core/runtime/interpreter/llm_result.py`）传递：

```python
@dataclass
class LLMResult:
    success: bool
    value: Optional[IbObject]    # 成功时的结果对象
    is_uncertain: bool           # True 表示应触发 llmexcept
    raw_response: str            # LLM 原始响应
    retry_hint: Optional[str]    # 重试提示词（注入下次 LLM 调用的 sys_prompt）
```

`is_uncertain=True` 的三种触发场景：

1. MOCK:FAIL/REPAIR 哨兵被检测（在 `_parse_result` 调用之前拦截）
2. 公理层 `from_prompt(raw_str, spec)` 解析失败（返回 `(False, retry_hint_str)`）
3. LLM 调用底层失败（网络错误、客户端未初始化等）

`LLMResult` 通过 `runtime_context.set_last_llm_result()` 存储，由外层 `visit_IbLLMExceptionalStmt` 轮询检查，不走异常链。

---

## 三、MOCK 仿真系统设计

`ibci_ai` 插件的 `_handle_mock_response()` 在 URL 为 `TESTONLY`（或环境变量 `IBC_TEST_MODE=1`）时激活。

### 3.1 哨兵值约定

| 指令 | 返回值 | 后续处理位置 |
|------|--------|------------|
| `MOCK:FAIL text` | `"MAYBE_YES_MAYBE_NO_this_is_ambiguous"` | llm_executor 中检测，返回 `LLMResult.uncertain_result()` |
| `MOCK:REPAIR` 首次 | `"__MOCK_REPAIR__"` | llm_executor 中检测，返回 `LLMResult.uncertain_result()` |
| `MOCK:REPAIR` 第二次 | `"1"` | 正常返回，触发重试成功 |
| `MOCK:TRUE` | `"1"` | 正常返回 |
| `MOCK:FALSE` | `"0"` | 正常返回 |

### 3.2 哨兵检测位置

两条 LLM 调用路径（`execute_llm_function` 和 `execute_behavior_expression`）中，哨兵检测均在 `_parse_result()` 调用**之前**进行，确保哨兵值不会被公理层的 `from_prompt()` 误判为正常字符串：

```python
# 检测 MOCK:REPAIR
if raw_res == "__MOCK_REPAIR__":
    return LLMResult.uncertain_result(raw_response="__MOCK_REPAIR__", ...)

# 检测 MOCK:FAIL
if raw_res == "MAYBE_YES_MAYBE_NO_this_is_ambiguous":
    return LLMResult.uncertain_result(raw_response=..., ...)
```

### 3.3 二级类型指令

`MOCK:INT:42`、`MOCK:FLOAT:3.14`、`MOCK:STR:text`、`MOCK:BOOL:TRUE`、`MOCK:LIST:[...]`、`MOCK:DICT:{...}` 支持精确控制 LLM 返回值的类型和内容，方便测试类型转换路径。

### 3.4 MOCK:REPAIR 的状态管理

`AIPlugin` 通过 `_mock_retry_counts` 字典按 key 管理重试计数，保证多个 MOCK:REPAIR 调用点相互独立。重试计数在 `reset_mock_state()` 调用后清零，用于测试隔离。

---

## 四、类型系统迁移：从 kernel/types/ 到 kernel/spec/

### 4.1 旧体系（已删除）

`core/kernel/types/` 目录（包含 `descriptors.py`、`registry.py`）已被彻底删除。`Symbol.descriptor` 属性和相关的 `TypeDescriptor`/`FunctionMetadata`/`ListMetadata` 等类不再存在，亦不存在任何 shim 兼容层。

### 4.2 新体系：core/kernel/spec/

```
core/kernel/spec/
├── base.py       → IbSpec 基类（所有类型描述符的公共基础）
├── specs.py      → 具体 Spec 子类
│                   FuncSpec / ClassSpec / ListSpec / TupleSpec
│                   DictSpec / BoundMethodSpec / ModuleSpec / LazySpec
├── registry.py   → SpecRegistry（核心门面）+ SpecFactory（工厂）
└── member.py     → MemberSpec / MethodMemberSpec
```

`Symbol` 只保留 `.spec` 字段（`IbSpec` 类型），无任何兼容 shim。

### 4.3 SpecRegistry 核心接口

| 方法 | 说明 |
|------|------|
| `is_assignable(src, target)` | 类型兼容性检查，通过公理系统实现 |
| `resolve(name)` | 按名字查找 Spec |
| `get_call_cap(spec)` | 获取可调用能力，FuncSpec/BoundMethodSpec 返回 `_FUNC_SPEC_CALL_CAP` 哨兵 |
| `resolve_iter_element(spec)` | 获取迭代元素类型（ListSpec/TupleSpec） |
| `resolve_subscript(spec, key_spec)` | 下标访问返回类型 |
| `get_metadata_registry()` | 获取 MetadataRegistry（公理 Capability 查询入口） |

### 4.4 `_FUNC_SPEC_CALL_CAP` 哨兵

`get_call_cap(spec)` 对 `FuncSpec`/`BoundMethodSpec` 返回 `_FUNC_SPEC_CALL_CAP` 哨兵常量，而非 `None`（`None` 表示"该类型不支持调用"）。调用方用 `get_call_cap(spec) is _FUNC_SPEC_CALL_CAP` 检测，将两种语义严格区分。

---

## 五、Tuple 类型全栈实现

Tuple 类型通过以下六层完整实现，与 List 类型对称但保持不可变约束：

| 层级 | 组件 | 位置 |
|------|------|------|
| Spec 层 | `TupleSpec` | `core/kernel/spec/specs.py:84-95` |
| Spec 常量 | `TUPLE_SPEC` | `core/kernel/spec/specs.py`（末尾原型常量区） |
| Spec 工厂 | `SpecFactory.create_tuple()` | `core/kernel/spec/registry.py` |
| 公理层 | `TupleAxiom` | `core/kernel/axioms/primitives.py:548-640` |
| 运行时对象 | `IbTuple` | `core/runtime/objects/builtins.py:382-443` |
| 装箱器 | `_box_tuple` | `core/runtime/bootstrap/builtin_initializer.py:301-306` |

**不可变性约束**（由 TupleAxiom 强制实现）：不提供 `append`、`pop`、`sort`、`clear`、`__setitem__` 方法，任何修改操作均抛出类型错误。

`IbTuple.elements` 字段为 Python `tuple`（不可变）；`IbList.elements` 为 Python `list`（可变）。Python `tuple` 通过专用 `_box_tuple` 装箱为 `IbTuple`，不复用 `_box_list`。

元组解包赋值（`stmt_handler.py` 中 `_assign_to_target`）同时支持 `IbTuple` 和 `IbList`：

```python
if isinstance(value, (IbList, IbTupleObj)):
    vals = list(value.elements)
```

---

## 六、IbLLMUncertain 哨兵对象

`IbLLMUncertain`（`core/runtime/objects/kernel.py`）是 `IbObject` 的子类，用作"LLM 调用结果不确定"时的变量赋值占位符：

- 当 `visit_IbAssign` 检测到 `last_llm_result.is_uncertain=True` 时，将目标变量赋值为 `IbLLMUncertain`（而非跳过赋值，保证变量已定义）
- `IbLLMUncertain` 在布尔上下文中返回 `False`，支持 `(type) uncertain_val` 强制类型转换
- 若 llmexcept 块重试成功，该变量被正确的 LLM 结果覆盖
- 若重试耗尽，变量保持 `IbLLMUncertain` 状态，后续操作会产生类型错误（当前错误提示有待改进）

单例在 `initialize_builtin_classes()` 中通过 `registry.register_llm_uncertain()` 注册，运行时通过 `registry.get_llm_uncertain()` 访问。

---

## 七、behavior_expression() 中 STRING token 的修复

词法分析器在 `@~...~` 内正确识别 `"..."` 字符串字面量（生成 `TokenType.STRING` token），但 Parser 的旧 `behavior_expression()` 方法中：

```python
else:
    self.stream.advance()  # 静默丢弃 STRING token
```

导致 `@~ MOCK:["a","b","c"] ~` 解析后 segments 拼接为 `MOCK:[,,]`（引号内容全丢）。

修复后（`core/compiler/parser/components/expression.py`）：

```python
elif self.stream.match(TokenType.STRING):
    segments.append('"' + self.stream.previous().value + '"')
else:
    segments.append(self.stream.previous().value if self.stream.advance() else "")
```

---

## 八、插件可见性修复：Prelude 注入问题

**旧问题**：`Prelude._init_defaults()` 将所有插件的 `ModuleSpec` 以 `user_defined=True` 加入 `builtin_modules`，导致插件在未 `import` 时即可被访问，完全绕开了显式引入语义。

**当前机制**（`core/compiler/semantic/passes/prelude.py:37-52`）：

- `Prelude._init_defaults()` 只初始化真正的内置类型（int/str/list/dict/tuple/bool/callable 等）
- 插件的符号注入只在 `Scheduler` 处理 `import X` 语句时触发
- `import ai` 后 `ai` 才在当前编译单元的符号表中可见

---

## 九、IbStatefulPlugin 状态快照机制

有状态插件（如 `ibci_ai`）实现 `IbStatefulPlugin`（`core/extension/ibcext.py`）协议：

```python
class IbStatefulPlugin(ABC):
    @abstractmethod
    def save_plugin_state(self) -> dict: ...

    @abstractmethod
    def restore_plugin_state(self, state: dict) -> None: ...
```

`HostService.snapshot()`（`core/runtime/host/service.py`）在保存宿主状态时，遍历所有注册插件，对 `IbStatefulPlugin` 实例调用 `save_plugin_state()`；恢复时调用 `restore_plugin_state(saved_state)`。

`ibci_ai` 保存内容：`_config`（url/key/model/timeout/retry 等配置）、`_return_type_prompts`、`_retry_prompts`。不保存 `_client`（OpenAI 连接对象，恢复后由 `_init_client()` 重建）。

---

## 十、MetadataRegistry 双轨并行（历史遗留）

当前架构中 MetadataRegistry 存在两个并行实例：

```
Engine.__init__()
    │
    ├── KernelRegistry() + initialize_builtin_classes()
    │       └──→ MetadataRegistry (轨A) → 内置类型/函数的公理 Capability
    │
    └── discover_all()
            └──→ HostInterface()
                    └──→ MetadataRegistry (轨B) → 插件元数据
```

两轨相互独立，不共享实例。不影响当前功能（两条查询路径分别服务编译期类型检查和运行时 LLM 输出解析），但在复杂场景下存在元数据不一致的潜在风险。

长期修复方向：实现 `.ibc_meta` 文件机制，将编译阶段的元数据获取与运行时实例解耦（见 PENDING_TASKS.md）。

---

*本文档为 IBC-Inter 重要架构细节备份，记录已稳定落地的设计决策。*
