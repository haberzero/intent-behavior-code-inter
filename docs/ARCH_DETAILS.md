# IBC-Inter 重要架构细节备份

> 本文档记录 IBC-Inter 在历次重构中形成的重要架构细节与设计决策。
> 这些内容已在代码中稳定落地，但因过于具体而不适合放入总体架构说明。
> 供开发者深入理解各模块实现时参考。
>
> **最后更新**：2026-05-12（按当次事实核查补入 PT-1.2 / PT-1.3 字段、纠正 §1.6 中已过期表述、规整历史小节编号）
>
> **说明**：本文包含若干历史分阶段细节。若与当前代码状态冲突，请优先以 `docs/TYPE_SYSTEM_DESIGN.md`、`docs/VM_AND_INTERPRETER_DESIGN.md`、`docs/NEXT_STEPS.md` 以及对应源码实现为准。文末"§十三 公理化里程碑"与"§十四 公理类型层次"为 2026-04-17 历史归档，仅用于追溯设计决策由来；当前编号系统已收口为 §一..§十一 + §十二（vtable 自动签名）+ 历史归档 §十三/§十四。

---

## 一、llmexcept / retry 机制：影子执行驱动模式

### 1.1 架构演进历程

llmexcept 机制经历了三个阶段的演进：

- 阶段一：用 Python try-except 捕获 `LLMUncertaintyError` 异常，逻辑分散于各 visit 方法中，异常冒泡路径难以维护
- 阶段二：引入 `_with_unified_fallback` 统一包装器，对 `visit_IbIf/While/For` 等节点进行隐式 fallback 包裹
- 阶段三（当前）：彻底废弃上述两种方式，采用"影子执行驱动模式"

### 1.2 当前架构：影子执行驱动模式

`_with_unified_fallback` 包装器和 `LLMUncertaintyError` 异常均已完全废弃（代码中不存在）。当前实现的核心思路：

- `visit_IbLLMExceptionalStmt` 是主控外壳，主动调用 `execution_context.visit(target_uid)` 驱动目标节点执行（C11/P3 完成后，`bypass_protection` 参数已删除——所有 llmexcept 关联通过 AST 字段直接建立，不再有侧表重定向需要绕过）
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
| `saved_vars` | 可序列化类型的变量快照（IbNone/IbInteger/IbFloat/IbString/IbList/**IbTuple**/IbDict） |
| `saved_intent_ctx` | `intent_context.fork()` 产生的意图上下文独立快照（IbIntentContext 值语义）|
| `saved_loop_context` | 循环上下文列表（`_loop_stack` 的深拷贝） |
| `saved_retry_hint` | 上次保存的 retry 提示词 |
| `loop_resume` | for 循环断点恢复映射（`节点UID → 迭代索引`，`restore_context` 故意不重置） |
| `max_retry` | 最大重试次数，从 `llm_provider.get_retry()` 读取 |
| `last_result` | 最后一次 LLM 调用的 `LLMResult`（供 llmexcept body 查询） |
| `error_history` | 按 retry 顺序追加的结构化错误记录（`retry_count` / `error_type` / `error_message` / `response`）— PT-1.2 引入；`set_error()` 追加，`reset_for_retry()` 仅清理当前错误态而不清空历史 |

不参与快照的类型（设计决定）：IbFunction、IbBehavior、IbNativeObject 等引用类型。

`IbTuple` 已在 `_is_serializable()` 中与 `IbList` 并列处理，元素递归序列化。

`LLMExceptFrameStack` 管理嵌套的 llmexcept 块。PT-1.3（2026-05-12）已为其增设 `max_depth`（默认 128）与溢出检查，超限抛 `RuntimeError`；`RuntimeContextImpl.push_llm_except_frame()` 入栈处同步施加上限，保证主运行路径与工具类视图一致。

`get_retry_info()` 同步暴露 `error_history_count` / `error_history` 字段，供调试器（`ibci_idbg`）与日志直接消费。

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

### 1.6 快照隔离模型（llmexcept 的概念框架）

llmexcept 机制的底层概念框架是**快照隔离（Snapshot Isolation）**，类比数据库事务：

```
数据库 SI:                            llmexcept 快照模型:
─────────────────────                 ──────────────────────────────────
BEGIN TRANSACTION                     LLM 语句进入执行
  read from snapshot                    从快照读取变量/意图栈
  private writes                        LLM 调用（retry 在内部循环）
  on success: COMMIT                    成功：commit 到目标变量（单赋值）
  on failure: ROLLBACK + propagate      失败：restore_snapshot + 向外传播
END TRANSACTION
```

**快照内的变量访问规则**（语义规范，当前部分落地）：

| 操作 | 规范 | 当前状态 |
|------|------|--------|
| 读取外部变量 | 允许（读到快照时刻值） | 已实现 |
| 写入 `retry_hint` | 允许（retry-scoped，不 commit 外部）| 已实现 |
| 写入普通外部变量 | **禁止**，应产生 SEM_xxx 编译期错误 | 未加限制（`restore_snapshot` 提供运行时回滚但无编译期保障；见 `KNOWN_LIMITS §十二.3`）|
| 快照失败后传播 | 应抛出统一的 LLM 错误对象 | 已实现：retry 耗尽 → `LLMRetryExhaustedError`；无保护裸赋值 → `LLMParseError`；provider 层失败 → `LLMCallError`（详见 `KNOWN_LIMITS §二`、`COMPLETED.md` OI-7 锚点）|

**为什么快照模型使 llmexcept 与并发无关**：
- 每个 LLM 语句（无论串行还是并行 dispatch）都进入独立快照，与其他语句的执行状态完全隔离
- llmexcept body 不修改外部状态，因此多个快照同时运行不会产生竞争条件
- 成功时的 commit（单变量写入）是整个快照的唯一输出，串行发生（使用点解引用）

**已落地的快照基础设施**（代码现状）：
- `LLMExceptFrame.save_context()` → 保存 vars/intent_ctx/loop_ctx/retry_hint 的完整快照
- `LLMExceptFrame.restore_snapshot()` → 每次 retry 前恢复快照，使 LLM 看到一致的输入状态
- `intent_context.fork()` → 意图上下文值快照（NS-2c 落地后改为 fork-and-replace 而非 merge）
- `LLMExceptFrame.error_history` → PT-1.2 引入的重试错误追踪
- `LLMExceptFrameStack.max_depth` → PT-1.3 引入的嵌套深度上限（默认 128，主运行路径同步施加）

**仍未落地的快照完整性约束**（仅剩一项；其余条目已闭合）：
- 编译期 read-only 约束（SEM 错误）：禁止 llmexcept 块的 LLM 调用路径中对外部变量进行**就地修改**（如 `list.append` / `dict[k] = v`）。当前仅文档级告诫（`KNOWN_LIMITS §十二.3`），无编译期保障。
  - 历史曾登记的"`_last_llm_result` 从 `RuntimeContextImpl`（全局共享）迁移到 `LLMExceptFrame`（per-snapshot）"已被推翻：当前架构有意保留共享通道并通过"读后立即 `set_last_llm_result(None)`"消费（`vm/handlers.py:986-988` 等多处）缩短生命周期至快照内通信，与 retry/llmexcept 的语义实测一致。本条不再视为遗留约束。

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
├── base.py       → IbSpec 基类 + TypeDef 统一类型模型 + TypeKind
├── specs.py      → 内置类型原型常量（INT_SPEC、FLOAT_SPEC、STR_SPEC 等）
├── registry.py   → SpecRegistry（核心门面）+ SpecFactory（工厂）
└── member.py     → MemberSpec / MethodMemberSpec
```

`Symbol` 只保留 `.spec` 字段（`IbSpec` 类型），无任何兼容 shim。

### 4.3 SpecRegistry 核心接口

| 方法 | 说明 |
|------|------|
| `is_assignable(src, target)` | 类型兼容性检查，通过公理系统实现 |
| `resolve(name)` | 按名字查找 Spec |
| `get_call_cap(spec)` | 获取可调用能力；FUNCTION/BOUND_METHOD/CLASS 等结构化可调用类型返回 axiom 或 spec 作 truthy 标记；不可调用类型返回 `None` |
| `resolve_iter_element(spec)` | 获取迭代元素类型（list/tuple） |
| `resolve_subscript(spec, key_spec)` | 下标访问返回类型 |

---

## 五、Tuple 类型全栈实现

Tuple 类型通过以下六层完整实现，与 List 类型对称但保持不可变约束：

| 层级 | 组件 | 位置 |
|------|------|------|
| Spec 常量 | `TUPLE_SPEC` | `core/kernel/spec/specs.py` |
| Spec 工厂 | `SpecFactory.create_tuple()` | `core/kernel/spec/registry.py` |
| 公理层 | `TupleAxiom` | `core/kernel/axioms/primitives.py` |
| 运行时对象 | `IbTuple` | `core/runtime/objects/builtins.py` |
| 装箱器 | `_box_tuple` | `core/runtime/bootstrap/builtin_initializer.py` |

**不可变性约束**（由 TupleAxiom 强制实现）：不提供 `append`、`pop`、`sort`、`clear`、`__setitem__` 方法，任何修改操作均抛出类型错误。

`IbTuple.elements` 字段为 Python `tuple`（不可变）；`IbList.elements` 为 Python `list`（可变）。Python `tuple` 通过专用 `_box_tuple` 装箱为 `IbTuple`，不复用 `_box_list`。

元组解包赋值（`stmt_handler.py` 中 `_assign_to_target`）同时支持 `IbTuple` 和 `IbList`：

```python
if isinstance(value, (IbList, IbTupleObj)):
    vals = list(value.elements)
```

---

## 六、IbLLMUncertain 哨兵对象

`IbLLMUncertain`（`core/runtime/objects/kernel.py`）是 `IbObject` 的子类，用作 llmexcept 保护帧内"LLM 调用结果不确定"时的变量赋值占位符。

**当前真实行为**（核查 `core/runtime/vm/handlers.py:732-745` 与 `core/kernel/axioms/primitives.py:947-1005`）：

- **保护帧内**：`vm_handle_IbAssign` 检测到 `last_llm_result.is_certain=False` 且当前存在 llmexcept 保护帧时，将目标变量赋值为 `IbLLMUncertain` 单例。llmexcept 主控循环随后会执行 `restore_snapshot` + retry，下一轮成功时哨兵被真实值覆盖。
- **保护帧外**：同一信号路径**不再**写入哨兵，而是直接 `raise ThrownException(LLMParseError)`（`handlers.py:738-745`、`handlers.py:118-126`、`handlers.py:1682-1689`）。Uncertain 不会泄漏到无保护代码。
- **retry 耗尽**：抛 `LLMRetryExhaustedError`；外层 `try/except` 可捕获。
- **provider 层失败**：抛 `LLMCallError`（OI-7 已闭合）。

`IbLLMUncertain.is_compatible` 返回 True（`primitives.py:995-997`），允许哨兵被写入任何类型槽位——这是 retry 循环内"变量已定义、待覆盖"语义的必要约束，不应理解为"用户可以让 uncertain 进入业务路径"。

历史过渡兼容 `str + Uncertain` 隐式拼接已在 NS-4（2026-05-12）收紧；详见 `KNOWN_LIMITS.md §八`、`COMPLETED.md` 2026-05-12 NS-4 锚点。

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

## 十、MetadataRegistry 双轨并行（已解决）

主引擎路径已于 M3 重构后统一至单一 SpecRegistry 实例（2026-05-08）：

```
Engine.__init__()
    │
    ├── KernelRegistry() + initialize_builtin_classes()
    │       └──→ SpecRegistry（唯一实例）
    │
    └── _ensure_plugins_discovered() → discover_all(self.registry)
                └──→ HostInterface(external_registry=SpecRegistry)
                        └──→ HostInterface.metadata = 同一 SpecRegistry 实例（已统一）
```

`discover_all()` 必须传入已初始化的 `KernelRegistry`；若未传入 registry（仅限孤立测试场景），
`HostInterface()` 会创建独立 SpecRegistry 实例，但主引擎路径不会走此分支。

---

## 十一、已知代码健康问题（2026-04-17 深度审计）

以下为深度分析时发现的遗留问题，已修复的条目已标注；仍待处理的条目详见 `docs/NEXT_STEPS.md` 与 `docs/PENDING_TASKS.md` 当前条目。

### 11.1 IbTuple 未纳入快照和序列化（已修复）

`llm_except_frame.py` 的 `_is_serializable()` 和 `runtime_serializer.py` 的 `_collect_instance()` / `_get_instance()` 均已补充 `IbTuple` 分支（cache-before-recurse 模式，与 IbList 对称）。

### 11.2 ibci_file 的 core 依赖与"非侵入"定义存在轻微偏差（已修正）

`ibci_file/core.py` 导入 `from core.runtime.path import IbPath` 并通过 `capabilities.execution_context.resolve_path()` 进行路径解析，而文档将 `ibci_file` 归类为非侵入式插件。`IbPath` 是纯数据类（`@dataclass(frozen=True)`），无解释器状态依赖，属于可接受的工具类导入。

**已修正**：`ibcext.py` 注释和 `ARCHITECTURE_PRINCIPLES.md` 插件表格已新增"非侵入式（轻量依赖）"分类，将 `ibci_file` 单独列出并注明原因。

### 11.3 scheduler.py 中的临时方案符号冲突静默处理（已修复）

`_inject_plugin_symbols` 方法中多处符号冲突检查从 `pass` 静默跳过升级为 `self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL/BASIC, ...)` 调用，调试模式下冲突可见。

### 11.4 collector.py / runtime_context.py / interop.py 技术债务（已修复）

- `collector.py:200`：删除 `"llm_fallback"` 无效属性遍历
- `runtime_context.py`：清理 5 处过期 TODO 注释
- `interop.py:7`：Protocol 继承 TODO 替换为解释性注释

---

## 十二、IbBehavior.call_intent 与 vtable callable 签名自动提取

### 12.1 IbBehavior.call_intent 字段

`IbBehavior`（`core/runtime/objects/builtins.py`）新增 `call_intent: Optional[Any] = None` 字段，用于保存 `@!` 排他意图，确保其在延迟执行路径中不丢失。

**修改链路**：

| 位置 | 变更 |
|------|------|
| `IbBehavior.__init__` | 新增 `call_intent` 参数和字段 |
| `IObjectFactory.create_behavior()` 协议 | 新增 `call_intent` kwarg |
| `RuntimeObjectFactory.create_behavior()` | 传递 `call_intent` |
| `expr_handler.py`（`is_deferred=True` 路径） | 创建 `IbBehavior` 时传入 `call_intent` |
| `RuntimeSerializer._collect_instance()` | 序列化 `call_intent` 字段（非 None 时） |
| `RuntimeDeserializer._get_instance()` | 反序列化时恢复 `call_intent` |

**背景**：旧实现中，当 `@! "intent text"` 修饰的 behavior 表达式遇到非立即执行路径时，`call_intent` 未被传入 `create_behavior()`，导致排他意图在执行时丢失。

### 12.2 vtable callable 签名自动提取

`discovery.py` 的 `_build_spec_from_dict()` 现支持 callable 类型的 vtable 条目：

```python
# 两种格式均支持：
"functions": {
    "parse": {"param_types": ["str"], "return_type": "dict"},  # 显式字典格式
    "auto_sig_func": some_callable,                            # callable 格式，自动提取
}
```

`_extract_signature(func)` 通过 `inspect.signature()` 提取参数和返回类型注解，映射到 IBCI 类型名（`_PY_TYPE_TO_IBCI` 字典）。规则：

- 跳过首个 `self`/`cls` 参数
- 有注解 → 按 `_PY_TYPE_TO_IBCI` 映射，未知类型 → `"any"`
- 无注解 → `"any"`
- 返回类型无注解 → `"any"`（使用 `inspect.Signature.empty` 判断，注意与 `inspect.Parameter.empty` 的区别）

---

# 历史归档

> 以下小节为 2026-04-17 公理化里程碑前后的阶段性设计说明，**仅作追溯参考**。
> 对应能力已稳定多版，当前实现以源码与正文 §一..§十二 为准；如下表述与现状不一致以代码为准。

## 十三、公理化 / 万物皆对象框架（2026-04-17 重大里程碑 — 历史归档）

本章记录 PR `copilot/ibc-inter-design-review` 完成的全局架构变更——IBC-Inter 公理化体系的核心阻塞点已被彻底突破。

### 13.1 IILLMExecutor 接口 + KernelRegistry 注入（Step 1）

**问题根因**：`IbBehavior` 是 IBC-Inter 对象（有 `IbClass`、有 Spec），但执行时需要 `LLMExecutor`。由于 `LLMExecutor` 在 `ServiceContext` 层，`IbBehavior.call()` 无法在不产生架构穿透的情况下合法取得它，因此只能抛 `RuntimeError`，实际执行权交给 handler 层的 `_execute_behavior()` 旁路。

**解决方案**：在内核层建立 LLM 服务的合法通道。

```
core/base/interfaces.py
    IILLMExecutor (Protocol)
        invoke_behavior(behavior, context) → IbObject
        execute_behavior_expression(node_uid, context, ...) → LLMResult
        execute_behavior_object(behavior, context) → LLMResult
        get_last_call_info() → Dict

core/kernel/registry.py  (KernelRegistry)
    _llm_executor: Any = None
    register_llm_executor(executor, token)  # 内核令牌保护
    get_llm_executor() → IILLMExecutor
    clone()  # 传播 _llm_executor 引用

core/runtime/interpreter/llm_executor.py  (LLMExecutorImpl)
    invoke_behavior(behavior, ctx) → IbObject
        → execute_behavior_object(behavior, ctx)
        → ctx.runtime_context.set_last_llm_result(result)
        → return result.value or registry.get_none()

core/engine.py  (_prepare_interpreter, 末尾)
    llm_executor = getattr(self.interpreter.service_context, 'llm_executor', None)
    if llm_executor:
        self.registry.register_llm_executor(llm_executor, self._kernel_token)
```

**设计约束**：
- `kernel` 层只知道 `IILLMExecutor` 接口，不 import `LLMExecutorImpl`
- 注入时机：`_prepare_interpreter()` 末尾（封印完成之后），因此 `register_llm_executor()` 免封印检查
- `clone()` 传播引用，确保子解释器也能访问 executor

### 13.2 BehaviorAxiom（Step 2）

`BehaviorAxiom` 替换了 `DynamicAxiom("behavior")`，`behavior` 从此是具体的一等公民类型。`BehaviorAxiom` 继承 `BaseAxiom`，通过 `has_call_cap = True` 声明可调用能力，`resolve_return_type_name` 返回 `"auto"`（编译期延迟；运行期由 `IbBehavior.call()` 按 expected_type 解析）。

**类型系统验证**：
```
is_dynamic(behavior_spec)    → False   （不再是 any）
is_behavior(behavior_spec)   → True    （已支持）
is_assignable(behavior, str) → False   （严格）
is_assignable(behavior, behavior) → True（已支持）
```

### 13.3 IbBehavior 公理化重构（Step 2）

`IbBehavior` 从被动数据描述符演进为**自主执行单元**，与 `IbUserFunction` 同构。

```python
class IbBehavior(IbObject, IIbBehavior):
    def __init__(self, ..., execution_context=None):
        self._execution_context = execution_context  # 创建时捕获

    def call(self, receiver, args) → IbObject:
        executor = self.ib_class.registry.get_llm_executor()
        return executor.invoke_behavior(self, self._execution_context)
```

**意图栈管理**移入 `execute_behavior_object()`：
- 保存/切换 `runtime_context.intent_stack`（使用 `captured_intents`）
- 执行 `execute_behavior_expression(behavior.node, ctx, ...)`
- 恢复意图栈

### 6.4 旁路彻底清除（Step 2）

| 删除 / 改变 | 位置 |
|-----------|------|
| `_execute_behavior()` 方法 **彻底删除** | `base_handler.py` |
| `visit_IbCall` `is_behavior()` 特殊路由 **删除** | `expr_handler.py` |
| `visit_IbExprStmt` → `res.call(none, [])` | `stmt_handler.py` |
| `create_behavior()` 新增 `execution_context` 参数 | `factory.py`, `interfaces.py` |
| `visit_IbBehaviorExpr` 传入 `execution_context` | `expr_handler.py` |

**质量门控**：446 个测试全部通过，零回归，CodeQL 0 alerts。

---

## 十四、公理类型层次（2026-04-17 历史归档 / 参考）

> 此节归档自原 `AXIOM_OOP_ANALYSIS.md` §一。AXIOM_OOP_ANALYSIS.md 文件已删除，内容拆分到 `docs/COMPLETED.md`、`docs/ARCHITECTURE_PRINCIPLES.md`、`docs/VM_AND_INTERPRETER_DESIGN.md` 与本文件。

### 14.1 完整公理类型层次（声明视角）

```
Object（根）
  ├─ int / float / str / bool / list / tuple / dict / None / slice / Exception / Enum
  ├─ void           (VoidAxiom, is_dynamic=False) — 无返回值的函数返回类型标注
  ├─ intent_context (IntentContextAxiom)          — 意图上下文对象（Step 6）
  ├─ llm_call_result (LlmCallResultAxiom)         — LLM 调用结果类型（Step 7）
  └─ callable       (CallableAxiom, is_dynamic=False) — 可调用对象的公理父类型
       ├─ bound_method  (BoundMethodAxiom) — 已绑定接收者的方法
       ├─ fn_callable   (FnCallableAxiom) — 普通可调用实例（lambda/snapshot 产生）
       └─ behavior      (BehaviorAxiom) — LLM 行为可调用实例（fn_callable 特化）
```

**说明**：此层次是 IBCI 类型系统（公理层）的声明，与 Python 实现类的继承无关。
`IbFnCallable` 与 `IbBehavior` 都直接继承自 `IbObject`——两者执行机制（AST 重访 vs LLM 调用）完全不同，
不共享 Python 实现，仅共享 IBCI 类型系统中的父子关系。

### 14.2 `is_compatible()` 方向原则

| source | 可赋值的目标类型 |
|--------|---------------|
| behavior | behavior、fn_callable、callable |
| fn_callable | fn_callable、callable |
| callable | callable（仅自身） |
| bound_method | bound_method、callable |

子类型向上兼容、父类型不向下兼容；`callable→fn_callable`、`fn_callable→behavior` 等反向赋值均为非法。


---

*本文档为 IBC-Inter 重要架构细节备份，记录已稳定落地的设计决策。*
*正文 §一..§十二 为当前真实状态；§十三 / §十四 为历史归档，仅供追溯。*
