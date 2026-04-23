# 意图注释系统设计说明

> 本文档描述 IBC-Inter 意图注释系统的架构设计和实现细节。

**更新日期**：2026-04-23

---

## 一、设计原则

### 核心设计目标

1. **AST 层独立节点**：意图注释作为独立 AST 节点处理，不依赖编译期侧表
2. **公理体系融入**：意图栈正式成为 IBCI 内置类型（`IbIntentContext` + `IntentContextAxiom`，`is_class=True`）
3. **帧级隔离**：意图上下文随执行帧（`IExecutionFrame`）持有，而非全局单例
4. **快照安全**：`IbIntentContext.fork()` 支持值快照，保证 LLM 流水线 dispatch 时刻意图绑定的安全性
5. **作用域隔离（拷贝传递）**：每次函数调用 fork 调用者的意图上下文，函数内的意图操作不泄漏给调用者

---

## 二、语法与语义

### 2.1 合法语法形式（全集）

意图注释系统的**所有**合法语法形式如下。除此之外的写法均为语法错误。

| 语法形式 | 类别 | 说明 |
|----------|------|------|
| `@ 内容` | 一次性涂抹意图 | 只对**紧跟其后**的下一次 LLM 行为表达式（`@~...~`）有效，调用后自动清除 |
| `@! 内容` | 排他意图（单次覆盖） | 只对**紧跟其后**的下一次 LLM 行为表达式有效，同时屏蔽涂抹意图和持久栈，调用后自动清除 |
| `@+ 内容` | 压入持久意图栈 | 持续有效，直到被显式移除；可独立存在，不需要紧跟 LLM 调用 |
| `@-` | 弹出栈顶 | 无参数，移除持久栈中最近压入的意图；可独立存在 |
| `@- 内容` | 按内容物理移除 | 从持久栈中移除第一条匹配指定内容的意图；可独立存在 |
| `@- #tag` | 按标签物理移除 | 从持久栈中移除第一条匹配指定标签的意图；可独立存在 |

**重要约束**：
- `@`（涂抹）和 `@!`（排他）**只能**紧跟 LLM 行为表达式（`@~...~`），**不能**修饰普通函数调用或其他语句
- `@` 符号与修饰符（`+` / `-` / `!`）之间**不能有空格**（如 `@-#tag` 正确，`@ - #tag` 错误）
- `@!` 不能修饰普通函数调用；函数内部的意图作用域控制应通过显式 API 完成（见 §2.3）

### 2.2 意图系统的启用位置

意图注释系统**在入口文件（entry file）层级启用**。

- 进入程序时，运行时为入口文件的执行上下文初始化一个空的全局意图上下文实例（`IbIntentContext`），作为整个程序生命周期内的**根意图上下文**
- 在入口文件顶层使用 `@+` / `@-` 直接操作该根意图上下文
- 每次**函数调用**进入时，运行时会对当前活跃的意图上下文执行 `fork()`（克隆），被调用函数在该克隆副本上操作，**函数内对意图系统的所有操作不会泄漏到调用者**
- 函数返回后，克隆副本被丢弃，调用者的意图上下文保持不变

```
入口文件
└── 根意图上下文（IbIntentContext，初始为空）
    ├── @+ "全局意图A"        # 直接作用于根上下文
    ├── func foo() 调用
    │   └── 克隆副本 A（fork 自根上下文）
    │       ├── @+ "foo 内的意图"   # 只作用于克隆副本 A
    │       ├── str r = @~ MOCK ~   # 见"全局意图A" + "foo 内的意图"
    │       └── func bar() 调用
    │           └── 克隆副本 B（fork 自克隆副本 A）
    │               └── ...        # 与副本 A 独立
    └── str r = @~ MOCK ~   # 仍然只见"全局意图A"（foo 的操作未泄漏）
```

### 2.3 意图优先级（消解顺序，在 LLM 调用内）

```
@!（排他覆盖）> @（一次性涂抹）> @+（持久栈）> 全局意图
```

`@!` 存在时，其他所有意图均被屏蔽，只使用 `@!` 的内容。

### 2.4 函数调用意图传递语义（拷贝传递）

每次函数调用（普通函数 `IbUserFunction.call()` 和 LLM 函数 `IbLLMFunction.call()`）的意图上下文行为：

| 调用方式 | 函数收到的意图上下文 |
|----------|---------------------|
| `my_func()` | 调用时**当前活跃意图上下文**的 **fork 快照**（拷贝传递）；函数内 `@+`/`@-` 不影响调用者 |

函数内部若需屏蔽/替换继承自调用者的意图，需要在函数体内**显式调用**作用域控制 API：

| API | 语义 |
|-----|------|
| `intent_context.clear_inherited()` | 清空从调用者继承的持久意图栈，从干净起点开始 |
| `intent_context.use(ctx)` | 用指定 `intent_context` 实例的内容替换当前作用域的意图上下文（fork 拷贝，不共享引用） |
| `intent_context.get_current()` | 返回当前作用域正在生效的意图上下文的快照（fork 副本，可检查、可保存） |

**重要原则**：不要滥用 `@!` 来控制函数调用粒度的意图隔离。`@!` 的语义是"对下一次 LLM 调用使用排他意图，屏蔽所有其他意图"，它只修饰 LLM 行为表达式（`@~...~`），不修饰普通函数调用。函数内部的意图管理应通过显式 API 完成。

### 2.5 用户自定义意图对象与作用域替换

用户可以创建自定义 `intent_context` 实例，并用它**完全替换当前作用域的默认意图上下文**。

**替换后的语义**：
- 替换后，当前作用域内的所有意图注释操作（`@+`、`@-`、`@~...~`等）均以**最新活跃的意图上下文对象**为基础进行作用
- 替换操作会在**当前作用域内直接取代原有的意图上下文**（即当前活跃的意图对象被新对象替代）
- 新意图对象同样作为**被克隆的实例**：当前作用域内后续发生的函数调用，会以当前活跃的新意图对象（而不是原先的根上下文）为源头 `fork()` 一个克隆副本传递给被调用函数

```ibci
func my_func():
    # 创建自定义意图上下文
    intent_context custom_ctx = intent_context()
    custom_ctx.push("专注于数据分析")
    custom_ctx.push("使用表格格式")

    # 用自定义上下文替换当前作用域的活跃意图上下文
    # 替换后，自定义上下文成为当前作用域的"根"，
    # 后续所有意图操作都以它为基础
    intent_context.use(custom_ctx)

    # 此后的 @+ 作用于 custom_ctx 的克隆（已替换为 custom_ctx）
    @+ "简洁明了"
    str r = @~ 分析这段数据 ~   # 见 custom_ctx 的意图 + "简洁明了"

    # 后续函数调用同样 fork 当前活跃的 custom_ctx 副本
    inner_func()   # inner_func 收到的是 custom_ctx（含"专注于数据分析"+"使用表格格式"+"简洁明了"）的 fork 快照
```

**关键不变量**：
- `intent_context.use(ctx)` 执行 `fork(ctx)` 而非直接共享引用，保证两个作用域的意图状态互不干扰
- 替换操作只在**当前作用域**生效；函数返回后，调用者的活跃意图上下文不受影响（拷贝传递语义保证）
- 多次调用 `intent_context.use(ctx)` 以最后一次为准

---

## 三、架构组件

### 3.1 AST 节点

```
core/kernel/ast.py
├── IbIntentAnnotation       # @ 和 @! 专用节点（前置意图）
│   └── 语义上紧跟后面的 LLM 调用或函数调用（@! 时）
└── IbIntentStackOperation   # @+ 和 @- 专用节点（栈操作）
    └── 可独立存在
```

`IbIntentInfo` 数据类携带意图的 `mode`（APPEND/OVERRIDE/REMOVE）、`content`（字符串段列表）、`tag`（可选标签）、`pop_top`（无参数 `@-`）。

### 3.2 意图上下文

意图栈已从 `RuntimeContextImpl` 的私有字段群提升为独立的公理化类型：

```
core/runtime/objects/intent_context.py
└── IbIntentContext                         # 意图上下文运行时对象（Python 层）
    ├── _intent_top: Optional[IntentNode]   # 持久意图栈顶节点（不可变链表，结构共享）
    ├── _smear_queue: List[IbIntent]        # 一次性涂抹意图队列（@ 语义）
    ├── _override: Optional[IbIntent]       # 排他意图槽（@! 语义）
    ├── _global_intents: List[IbIntent]     # 全局意图（Engine 级，跨函数调用持久）
    ├── fork() → IbIntentContext            # 值快照（不可变副本，用于 LLMExceptFrame 和函数调用隔离）
    ├── push(intent)                        # 压入持久栈（@+）
    ├── pop() → Optional[IbIntent]          # 弹出栈顶
    ├── remove(tag, content)               # 按标签或内容移除（重建链表，不原地修改）
    ├── add_smear(intent)                   # 添加涂抹意图（@）
    ├── set_override(intent)                # 设置排他意图（@!）
    ├── has_override() → bool              # 检查是否有待消费的排他意图
    ├── consume_override() → Optional      # 消费并清除排他意图
    └── get_active_intents() → list        # 返回持久栈展平列表（不含 smear/override）

core/kernel/axioms/intent_context.py
└── IntentContextAxiom                      # 公理层表示（is_class=True，可实例化）
    ├── 方法：fork, resolve, push, pop, merge, clear
    └── INTENT_CONTEXT_SPEC = ClassSpec("intent_context")
```

**`IntentNode` 链表结构**：持久意图栈通过不可变链表实现结构共享：

```
IntentNode
├── intent         # IbIntent 对象
├── parent         # 指向上一个节点（链表向上）
└── _cached_list  # 展平列表缓存（懒加载，`to_list()` 时生成）
```

**重要**：`@-` 移除操作通过**重建链表**（而非原地修改 `previous.parent`）来保证结构共享安全。在存在 `fork()` 快照的情况下，原地修改会破坏快照的不可变性（已于 2026-04-19 修复此 Bug）。

### 3.3 运行时上下文（当前实际结构）

```
core/runtime/interpreter/runtime_context.py
└── RuntimeContextImpl
    ├── _intent_ctx: IbIntentContext     # 意图上下文（统一持有四类意图状态）
    │
    │   # 以下为对 _intent_ctx 的委托接口：
    ├── push_intent(intent)              # 压入持久栈 → _intent_ctx.push()
    ├── add_smear_intent(intent)         # 添加涂抹意图 → _intent_ctx.add_smear()
    ├── set_pending_override_intent()    # 设置排他意图 → _intent_ctx.set_override()
    ├── consume_pending_override_intent() # 消费排他意图 → _intent_ctx.consume_override()
    ├── remove_intent(tag/content)       # 移除意图 → _intent_ctx.remove()
    ├── set_global_intent()              # 全局意图 → _intent_ctx.set_global_intents()
    └── fork_intent_snapshot()           # 值快照 → _intent_ctx.fork()
```

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

### 4.2 @! 排他意图的消解（LLM 调用时）

```python
# RuntimeContextImpl.get_resolved_prompt_intents()
override = self._intent_ctx.consume_override()
if override:
    return [override.resolve_content()]  # 排他：屏蔽所有其他意图

# 无排他意图：涂抹意图 + 持久栈 + 全局意图（按优先级合并）
smears = self._intent_ctx.consume_smear()
...
```

### 4.3 函数调用意图作用域控制（显式 API）

函数调用时采用**拷贝传递**：`IbUserFunction.call()` 和 `IbLLMFunction.call()` 均 fork 调用者的 `_intent_ctx`，让被调用函数在独立副本上操作，操作结果不回流给调用者。

被调用函数若需控制本地意图上下文，应在函数体内显式调用：

```ibci
func process():
    # 清空继承自调用者的持久意图栈，从干净起点开始
    intent_context.clear_inherited()
    @+ "只以 JSON 格式回复"
    str r = @~ 处理数据 ~   # 只见 @+ 的意图

func process_with_ctx(any data):
    # 创建自定义上下文，完全替换当前作用域的意图上下文
    intent_context my_ctx = intent_context()
    my_ctx.push("简洁明了")
    my_ctx.push("用中文")
    intent_context.use(my_ctx)
    str r = @~ $data ~      # 只见 my_ctx 中的意图

func inspect_intents() -> any:
    # 获取当前作用域意图上下文的快照（不影响当前作用域）
    intent_context saved = intent_context.get_current()
    return saved.resolve()
```

**实现层**：这三个方法通过 `from core.runtime.frame import get_current_frame` 获取当前帧的 `_intent_ctx`，与 `IbUserFunction.call()` 使用相同的 ContextVar 机制，安全且协程/线程隔离。

### 4.4 @- 移除意图

```python
# visit_IbIntentStackOperation（stmt_handler.py）
if intent_info.pop_top:
    runtime_context.pop_intent()                       # @-（无参数）：弹出栈顶
elif intent_info.tag:
    runtime_context.remove_intent(tag=intent_info.tag) # @-#tag：按标签移除
elif intent_info.content:
    runtime_context.remove_intent(content=intent_info.content)  # @- 内容：按内容移除
```

### 4.5 意图消解（IntentResolver）

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

### 4.6 LLMExceptFrame 中的意图快照

`llmexcept` 进入时通过 `intent_context.fork()` 保存意图状态的值快照：

```python
# LLMExceptFrame.save_context()
frame.saved_intent_ctx = runtime_context.fork_intent_snapshot()  # → _intent_ctx.fork()

# LLMExceptFrame.restore_snapshot()（每次 retry 前调用）
runtime_context._intent_ctx = frame.saved_intent_ctx.fork()  # 恢复到快照时刻
```

### 4.7 snapshot 行为表达式的意图捕获

`snapshot` 关键字修饰的行为表达式（`int snapshot x = @~...~`）在创建时捕获调用位置意图栈的完整值快照：

```python
# expr_handler.py
deferred_mode = self.get_side_table("node_deferred_mode", node_uid)
# snapshot 语义：捕获当前作用域正在生效的意图栈的值快照（IbIntentContext.fork()）
# lambda 语义：不捕获意图状态，每次调用时使用调用位置的当前意图栈
captured_intents = None if deferred_mode == "lambda" else self.runtime_context.fork_intent_snapshot()
```

---

## 五、IbIntent 对象

意图在运行时表示为 `IbIntent` 对象（`core/runtime/objects/intent.py`），已通过 `IntentAxiom` 纳入公理体系：

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

## 六、intent_context OOP MVP（已落地）

用户可以在 IBCI 代码中显式创建和操作意图上下文对象：

```ibci
# 创建空意图上下文
intent_context ctx = intent_context()

# 压入意图
ctx.push("用中文回复")
ctx.push("保持简洁", "style")   # 带 tag

# 移除 / 弹出
ctx.pop()                       # 弹出最近压入的意图

# fork（创建不可变副本）
intent_context ctx_copy = ctx.fork()

# 查询
any resolved = ctx.resolve()    # 返回已消解的意图字符串列表

# 合并（将另一个上下文状态写入 self）
ctx.merge(ctx_copy)

# 清空持久栈（实例方法）
ctx.clear()

# --- 作用域控制 API（可在类上或实例上调用，均作用于当前帧意图上下文）---

# 清空当前作用域从调用者继承的持久意图栈
intent_context.clear_inherited()   # 等价于 ctx.clear_inherited()

# 以指定实例的内容替换当前作用域的意图上下文（拷贝，非引用）
intent_context.use(ctx)            # 等价于 ctx.use(ctx)

# 获取当前作用域意图上下文的 fork 副本（不影响当前作用域）
intent_context saved = intent_context.get_current()
```

**实现层**：`IntentContextAxiom.is_class() = True`，`INTENT_CONTEXT_SPEC = ClassSpec(name="intent_context")`，所有方法在 `builtin_initializer.py` 注册。实例的 `_ctx` 字段持有底层 `IbIntentContext` Python 对象。`clear_inherited()`/`use()`/`get_current()` 通过 `get_current_frame()` ContextVar 访问当前帧的 `_intent_ctx`，操作当前作用域的意图上下文。

---

## 七、调试工具

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

`last_result()` 和 `last_llm()` 采用**帧优先模式**：优先从活跃的 `LLMExceptFrame` 读取 `frame.last_result`，无活跃帧时回退到 `RuntimeContextImpl._last_llm_result` 共享字段。

---

## 八、验证示例

```ibci
# ── 入口文件层级：直接操作根意图上下文 ──────────────────────────────

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


# ── 函数调用：意图上下文拷贝传递，不泄漏 ───────────────────────────

@+ "格式要求"

func clear_func():
    # 方式1：清空继承的意图，从干净起点开始
    intent_context.clear_inherited()
    @+ "本函数的意图"
    str r = @~ MOCK ~       # 只见"本函数的意图"，不含调用者的"格式要求"

clear_func()
result = @~ MOCK ~          # 调用者的"格式要求"仍然有效（fork 语义保证不泄漏）


# ── 用户自定义意图对象：替换当前作用域活跃意图上下文 ────────────────

func func_with_custom_ctx():
    # 方式2：创建自定义意图对象并替换当前作用域的活跃意图上下文
    intent_context custom = intent_context()
    custom.push("专属意图A")
    custom.push("专属意图B")

    # 替换：custom 成为当前作用域的活跃意图上下文
    # 此后所有意图操作、函数调用均基于 custom（不是原先继承自调用者的上下文）
    intent_context.use(custom)

    @+ "追加意图C"        # 作用于 custom 的克隆
    str r = @~ MOCK ~     # 见"专属意图A" + "专属意图B" + "追加意图C"

    # 后续函数调用 fork 当前活跃的 custom 副本，而非原始根上下文
    inner_func()          # inner_func 收到的是含上述三个意图的 fork 快照
```

验证结果：
- ✅ `@` 一次性涂抹意图 → 调用后自动清除，不残留
- ✅ `@+` 增量追加 → 意图在持久栈中累积
- ✅ `@-` 物理移除 → 正确重建链表，不破坏结构共享
- ✅ `@!` 临时排他（LLM 调用）→ 只对当前调用有效，完全屏蔽其他意图
- ✅ 普通函数调用 → fork 拷贝传递，函数内意图操作不泄漏给调用者
- ✅ `intent_context.clear_inherited()` → 函数内清空继承意图，从干净起点开始
- ✅ `intent_context.use(ctx)` → 用自定义对象替换当前作用域活跃意图上下文（fork 拷贝，非引用共享）
- ✅ `intent_context.use(ctx)` 后的函数调用 → fork 的源头是替换后的自定义意图对象，而非原始根上下文
- ✅ `intent_context.get_current()` → 返回当前作用域意图上下文的快照副本

---

## 九、文件清单

| 文件 | 说明 |
|------|------|
| `core/kernel/ast.py` | AST 节点定义（`IbIntentAnnotation`、`IbIntentStackOperation`、`IbIntentInfo`） |
| `core/kernel/intent_resolver.py` | 意图消解算法（合并+去重） |
| `core/kernel/intent_logic.py` | 意图模式定义（`IntentMode`、`IntentRole`） |
| `core/kernel/axioms/intent.py` | `IntentAxiom`（公理层，`is_class=True`） |
| `core/kernel/axioms/intent_context.py` | `IntentContextAxiom`（公理层，`is_class=True`） |
| `core/kernel/spec/specs.py` | `INTENT_CONTEXT_SPEC = ClassSpec("intent_context")` |
| `core/runtime/objects/intent.py` | `IbIntent` 运行时对象 |
| `core/runtime/objects/intent_context.py` | `IbIntentContext` 运行时对象（Python 层，不可实例化为 IbObject） |
| `core/runtime/objects/intent_stack.py` | `IbIntentStack`（遗留接口层，提供 `push/pop/clear` 等 IBCI 可调用方法） |
| `core/runtime/bootstrap/builtin_initializer.py` | `intent_context` 类原生方法绑定（`__init__/push/pop/fork/resolve/merge/clear`） |
| `core/runtime/interpreter/runtime_context.py` | 运行时上下文（持有 `_intent_ctx: IbIntentContext`） |
| `core/runtime/interpreter/handlers/stmt_handler.py` | 语句处理器（`visit_IbIntentAnnotation`、`visit_IbIntentStackOperation`） |
| `core/runtime/interpreter/handlers/expr_handler.py` | `snapshot` 捕获 `fork_intent_snapshot()` 值快照 |
| `core/runtime/interpreter/llm_executor.py` | LLM 执行器（调用 `get_resolved_prompt_intents()` 组装提示词） |
| `core/runtime/interpreter/llm_except_frame.py` | LLM 异常帧（`save_context` 使用 `fork()` 保存意图快照） |
| `core/runtime/objects/kernel.py` | `IbUserFunction`/`IbLLMFunction` fork/restore 意图上下文（拷贝传递语义）；lambda 参数约束 |
| `core/compiler/semantic/passes/semantic_analyzer.py` | `@` 和 `@!` 语义校验：两者均只能修饰 LLM 行为表达式 |
| `ibci_modules/ibci_idbg/core.py` | 调试工具（帧优先模式读取意图/结果状态） |
