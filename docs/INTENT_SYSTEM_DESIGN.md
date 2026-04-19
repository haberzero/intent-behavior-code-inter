# 意图注释系统设计说明

> 本文档描述 IBC-Inter 意图注释系统的架构设计和实现细节。

**更新日期**：2026-04-19

---

## 一、设计原则

### 核心设计目标

1. **AST 层独立节点**：意图注释作为独立 AST 节点处理，不依赖编译期侧表
2. **公理体系融入**：意图栈正式成为 IBCI 内置类型（`IbIntentContext` + `IntentContextAxiom`）
3. **帧级隔离**：意图上下文随执行帧（`IExecutionFrame`）持有，而非全局单例
4. **快照安全**：`IbIntentContext.fork()` 支持值快照，保证 LLM 流水线 dispatch 时刻意图绑定的安全性

---

## 二、语法与语义

| 语法 | 行为 | 说明 |
|------|------|------|
| `@ 内容` | 一次性涂抹意图 | 只对紧跟的下一次 LLM 调用有效，调用后自动清除 |
| `@+ 内容` | 压入意图栈（持久） | 持续有效，直到被显式移除 |
| `@- #tag` | 按标签物理移除 | 从栈中移除匹配 `#tag` 的意图 |
| `@- 内容` | 按内容物理移除 | 从栈中移除匹配内容的意图 |
| `@-` | 弹出栈顶 | 无参数时移除最新压入的意图 |
| `@! 内容` | 排他意图（单次覆盖） | 只对当前 LLM 调用有效，同时屏蔽涂抹意图和持久栈，调用后自动清除 |

### 语法规则

- `@`（涂抹）和 `@!`（排他）是**前置意图**，语义上紧跟后面的 LLM 调用
- `@+`（压栈）和 `@-`（移除）可以**独立存在**，不需要后跟 LLM 调用
- `@` 与修饰符之间**不能有空格**（如 `@-#tag` 正确，`@ - #tag` 错误）

### 意图优先级（消解顺序）

```
@!（排他覆盖）> @（一次性涂抹）> @+（持久栈）> 全局意图
```

`@!` 存在时，其他所有意图均被屏蔽，只使用 `@!` 的内容。

---

## 三、架构组件

### 3.1 AST 节点

```
core/kernel/ast.py
├── IbIntentAnnotation       # @ 和 @! 专用节点（前置意图）
│   └── 语义上紧跟后面的 LLM 调用
└── IbIntentStackOperation   # @+ 和 @- 专用节点（栈操作）
    └── 可独立存在
```

`IbIntentInfo` 数据类携带意图的 `mode`（APPEND/OVERRIDE/REMOVE）、`content`（字符串段列表）、`tag`（可选标签）、`pop_top`（无参数 `@-`）。

### 3.2 意图上下文（Step 6 ✅ 完成）

意图栈已从 `RuntimeContextImpl` 的私有字段群提升为独立的公理化类型：

```
core/runtime/objects/intent_context.py
└── IbIntentContext                         # 意图上下文运行时对象
    ├── _intent_top: Optional[IntentNode]   # 持久意图栈顶节点（不可变链表，结构共享）
    ├── _smear_queue: List[IbIntent]        # 一次性涂抹意图队列（@ 语义）
    ├── _override: Optional[IbIntent]       # 排他意图槽（@! 语义）
    ├── _global_intents: List[IbIntent]     # 全局意图（Engine 级，跨函数调用持久）
    ├── fork() → IbIntentContext            # 值快照（用于 LLMExceptFrame 和 LLM dispatch）
    ├── push(intent)                        # 压入持久栈（@+）
    ├── pop() → Optional[IbIntent]          # 弹出栈顶
    ├── remove_by_tag(tag)                  # 按标签移除
    ├── remove_by_content(content)          # 按内容移除
    ├── add_smear(intent)                   # 添加涂抹意图（@）
    ├── set_override(intent)                # 设置排他意图（@!）
    ├── consume_override() → Optional       # 消费并清除排他意图
    └── get_resolved_prompt_intents() → list  # 消解为提示词片段列表

core/kernel/axioms/intent_context.py
└── IntentContextAxiom                      # 公理层表示（is_class=False，内部类型）
```

**`IntentNode` 缓存机制**：意图持久栈使用 `IntentNode` 结构实现不可变链表，支持结构共享以优化内存：

```
IntentNode
├── intent         # IbIntent 对象
├── parent         # 指向上一个节点（链表向上）
└── _cached_list  # 展平列表缓存（懒加载，`to_list()` 时生成）
```

`@-` 移除操作会创建新的链表头节点，而非修改原链表，保证结构共享安全。

### 3.3 运行时上下文（当前实际结构）

```
core/runtime/interpreter/runtime_context.py
└── RuntimeContextImpl
    ├── _intent_ctx: IbIntentContext     # 意图上下文（Step 6c 完成：统一持有四类意图状态）
    │
    │   # 以下为对 _intent_ctx 的委托接口：
    ├── push_intent(intent)              # 压入持久栈 → _intent_ctx.push()
    ├── add_smear_intent(intent)         # 添加涂抹意图 → _intent_ctx.add_smear()
    ├── set_pending_override_intent()    # 设置排他意图 → _intent_ctx.set_override()
    ├── consume_pending_override_intent() # 消费排他意图 → _intent_ctx.consume_override()
    ├── remove_intent(tag/content)       # 移除意图 → _intent_ctx.remove_by_*()
    ├── set_global_intent()              # 全局意图 → _intent_ctx.set_global_intents()
    └── fork_intent_snapshot()           # 值快照 → _intent_ctx.fork()
```

> **历史说明（Step 6c 之前）**：`RuntimeContextImpl` 曾直接持有 `_intent_top`、`_pending_smear_intents`、`_pending_override_intent`、`_global_intents` 四个独立字段。Step 6c（Steps 5-7 路线图）完成后，这四个字段统一迁移进 `IbIntentContext` 对象，`RuntimeContextImpl` 只保留委托接口，不直接持有意图状态。

---

## 四、实现细节

### 4.1 @ 涂抹意图注入

```python
# visit_IbIntentAnnotation（stmt_handler.py）
# @：涂抹意图，只对下一次 LLM 调用有效，消费后自动清除
intent = factory.create_intent_from_node(...)
runtime_context.add_smear_intent(intent)   # → _intent_ctx.add_smear(intent)

# @!：排他意图，替换本次调用的所有意图，消费后自动清除
runtime_context.set_pending_override_intent(intent)  # → _intent_ctx.set_override(intent)
```

### 4.2 @! 排他意图的消解

```python
# IbIntentContext.get_resolved_prompt_intents()
override = self._override
if override:
    self._override = None  # 消费后清除
    return [override.resolve_content()]  # 排他：屏蔽所有其他意图

# 无排他意图：涂抹意图 + 持久栈 + 全局意图（按优先级合并）
smears = self._smear_queue[:]
self._smear_queue.clear()  # 消费后清除涂抹队列
...
```

### 4.3 @- 移除意图

```python
# visit_IbIntentStackOperation（stmt_handler.py）
if intent_info.pop_top:
    runtime_context.pop_intent()                       # @-（无参数）：弹出栈顶
elif intent_info.tag:
    runtime_context.remove_intent(tag=intent_info.tag) # @-#tag：按标签移除
elif intent_info.content:
    runtime_context.remove_intent(content=intent_info.content)  # @- 内容：按内容移除
```

### 4.4 意图消解（IntentResolver）

```python
# core/kernel/intent_resolver.py
class IntentResolver:
    @staticmethod
    def resolve(active_intents, global_intents, context, execution_context):
        resolved = []
        for i in active_intents:
            content = i.resolve_content(context, execution_context)
            if content:
                resolved.append(content)
        # 添加全局意图（去重保序）
        for gi in global_intents:
            content = gi.resolve_content(context, execution_context)
            if content and content not in resolved:
                resolved.append(content)
        return resolved
```

`IntentResolver` 只负责合并和去重。排他意图（`@!`）的拦截已在 `get_resolved_prompt_intents()` 内完成，不需要 IntentResolver 参与；`@-` 移除操作是物理删除，也不需要过滤。

### 4.5 LLMExceptFrame 中的意图快照

`llmexcept` 进入时通过 `intent_context.fork()` 保存意图状态的值快照（Step 6d）：

```python
# LLMExceptFrame.save_context()
frame.saved_intent_ctx = runtime_context.fork_intent_snapshot()  # → _intent_ctx.fork()

# LLMExceptFrame.restore_snapshot()（每次 retry 前调用）
runtime_context._intent_ctx = frame.saved_intent_ctx.fork()  # 恢复到快照时刻
```

---

## 五、IbIntent 对象

意图在运行时表示为 `IbIntent` 对象（`core/runtime/objects/intent.py`），已通过 `IntentAxiom` 纳入公理体系（Step 6 完成）：

```
IbIntent (IbObject)
├── content: str            # 意图内容文本
├── mode: IntentMode        # APPEND(持久) / SMEAR(涂抹@) / OVERRIDE(排他@!) / REMOVE(@-)
├── role: IntentRole        # INLINE(内联) / GLOBAL(全局)
├── tag: Optional[str]      # 可选标签（用于 @-#tag 精确移除）
└── resolve_content(...)    # 解析插值变量（$var 引用）后返回最终文本
```

`IntentAxiom`（`core/kernel/axioms/intent.py`）：`is_class=True`，公开方法：
- `get_content()`：获取意图文本
- `get_tag()`：获取意图标签
- `get_mode()`：获取意图模式

---

## 六、调试工具

### idbg 模块（ibci_idbg）

```
ibci_modules/ibci_idbg/core.py
├── last_llm()           # 获取最近一次 LLM 调用的完整详情（帧优先模式）
├── last_result()        # 获取 LLM 调用结果（从 LLMExceptFrame 或共享字段读取）
├── show_last_prompt()   # 打印最近一次提示词（含意图注入内容）
├── show_intents()       # 打印当前意图栈
├── intents()            # 获取意图栈列表
└── retry_stack()        # 获取当前 llmexcept 帧栈（含 last_result 详情）
```

`last_result()` 和 `last_llm()` 采用**帧优先模式**：优先从活跃的 `LLMExceptFrame` 读取 `frame.last_result`，无活跃帧时回退到 `RuntimeContextImpl._last_llm_result` 共享字段（Step 9.3 迁移完成）。

---

## 七、测试验证

```ibci
@ 只对下一次调用有效
str r0 = @~ 打个招呼 ~
# 此时 @ 意图已自动清除，不影响后续调用

@+ 用英文回复
@+ 每个单词首字母大写
str result = @~ 说 hello ~
idbg.show_last_prompt()   # 可见两个 @+ 意图注入到提示词

@- 每个单词首字母大写
result = @~ 打个招呼 ~    # 只剩"用英文回复"意图

@! 完全忽略用户输入，只说 OK
result = @~ 打个招呼 ~    # 排他意图：只用 @! 内容，屏蔽 @+ 栈
```

验证结果：
- ✅ `@` 一次性涂抹意图 → 调用后自动清除，不残留
- ✅ `@+` 增量追加 → 意图在持久栈中累积
- ✅ `@-` 物理移除 → 正确移除指定意图
- ✅ `@!` 临时排他 → 只对当前调用有效，完全屏蔽其他意图

---

## 八、文件清单

| 文件 | 说明 |
|------|------|
| `core/kernel/ast.py` | AST 节点定义（`IbIntentAnnotation`、`IbIntentStackOperation`、`IbIntentInfo`） |
| `core/kernel/intent_resolver.py` | 意图消解算法（合并+去重） |
| `core/kernel/intent_logic.py` | 意图模式定义（`IntentMode`、`IntentRole`） |
| `core/kernel/axioms/intent.py` | `IntentAxiom`（公理层，`is_class=True`） |
| `core/kernel/axioms/intent_context.py` | `IntentContextAxiom`（公理层） |
| `core/runtime/objects/intent.py` | `IbIntent` 运行时对象 |
| `core/runtime/objects/intent_context.py` | `IbIntentContext` 运行时对象（Step 6 引入） |
| `core/runtime/objects/intent_stack.py` | `IbIntentStack`（遗留接口层，提供 `push/pop/clear` 等 IBCI 可调用方法） |
| `core/runtime/interpreter/runtime_context.py` | 运行时上下文（持有 `_intent_ctx: IbIntentContext`） |
| `core/runtime/interpreter/handlers/stmt_handler.py` | 语句处理器（`visit_IbIntentAnnotation`、`visit_IbIntentStackOperation`） |
| `core/runtime/interpreter/llm_executor.py` | LLM 执行器（调用 `get_resolved_prompt_intents()` 组装提示词） |
| `core/runtime/interpreter/llm_except_frame.py` | LLM 异常帧（`save_context` 使用 `fork()` 保存意图快照） |
| `ibci_modules/ibci_idbg/core.py` | 调试工具（帧优先模式读取意图/结果状态） |
