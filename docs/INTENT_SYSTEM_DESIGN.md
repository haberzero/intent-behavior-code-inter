# 意图注释系统设计说明

> 本文档描述 IBC-Inter 意图注释系统的架构设计和实现细节。

**更新日期**：2026-04-06

---

## 一、设计原则

意图注释通过 **IntentStack 内置类**进行操作，设计直观、简单、有效。

### 核心设计目标

1. **AST 层独立节点**：意图注释作为独立 AST 节点处理，不再依赖编译期侧表
2. **公理体系融入**：意图栈正式成为 IBCI 内置类型
3. **无历史包袱**：彻底清理旧的侧表式意图栈设计

---

## 二、语法与语义

| 语法 | 行为 | 说明 |
|------|------|------|
| `@ 内容` | 压入意图栈 | 持续有效，直到被移除 |
| `@+ 内容` | 压入意图栈 | 与 `@` 相同 |
| `@- #tag` | 物理移除 | 从栈中移除匹配的标签意图 |
| `@- 内容` | 物理移除 | 从栈中移除匹配内容的意图 |
| `@! 内容` | 临时的单次 IntentStack | 只对当前 LLM 调用有效，全局栈不变 |

### 语法规则

- `@` / `@!` 是**前置意图**，必须**后面**紧跟行为表达式 `@~...~`
- `@+` / `@-` 可以独立存在
- `@` 和修饰符之间**不能有空格**（如 `@-#tag` 正确，`@ - #tag` 错误）

---

## 三、架构组件

### 3.1 AST 节点

```
core/kernel/ast.py
├── IbIntentAnnotation       # @ 和 @! 专用节点
│   └── 必须在后面紧跟 LLM 调用
└── IbIntentStackOperation   # @+ 和 @- 专用节点
    └── 允许独立存在
```

### 3.2 内置类

```
core/runtime/objects/intent_stack.py
└── IbIntentStack
    ├── push()       # 压入意图
    ├── pop()       # 弹出意图
    ├── remove()    # 移除意图
    └── clear()     # 清空栈
```

### 3.3 运行时上下文

```
core/runtime/interpreter/runtime_context.py
├── _intent_top              # 意图栈顶节点
├── _pending_override_intent  # @! 临时排他意图
├── push_intent()            # 压入意图
├── remove_intent()          # 物理移除意图
└── get_resolved_prompt_intents()  # 消解意图为 Prompt
```

#### IntentNode 缓存机制

意图栈使用 `IntentNode` 结构实现，支持结构共享以优化内存：

```
IntentNode
├── intent         # IbIntent 对象
├── parent         # 指向上一个节点
└── _cached_list  # 展平列表缓存
```

`to_list()` 方法会缓存展平后的列表以提高性能。在执行 `@-` 移除时，必须清除相关节点的缓存以确保数据一致。

---

## 四、实现细节

### 4.1 @ 意图注入

```python
# visit_IbIntentAnnotation
intent = factory.create_intent_from_node(...)
runtime_context.push_intent(intent)
```

### 4.2 @! 排他意图

```python
# @! 设置临时的单次 IntentStack
# 在 get_resolved_prompt_intents() 中检查
if pending_override:
    return [pending_override.resolve_content()]

# 调用完成后自动清除
```

### 4.3 @- 移除意图

```python
# 物理从栈中移除匹配的意图
if intent.is_remove:
    if intent.tag:
        runtime_context.remove_intent(tag=intent.tag)
    elif intent.content:
        runtime_context.remove_intent(content=intent.content)
```

### 4.4 意图消解

```python
# IntentResolver.resolve()
# 只负责简单的合并和去重
def resolve(active_intents, global_intents):
    resolved = []
    for i in active_intents:
        resolved.append(i.resolve_content())
    return unique_keep_order(resolved)
```

---

## 五、IntentResolver

### 设计简化

`IntentResolver` 只负责简单的意图合并和去重，不再处理复杂的排他和移除逻辑。

- `@!` 排他意图由 `_pending_override_intent` 字段在 `get_resolved_prompt_intents()` 中单独处理
- `@-` 移除意图已经在运行时物理移除，不需要再过滤

### 代码

```python
class IntentResolver:
    @staticmethod
    def resolve(active_intents, global_intents, context, execution_context):
        resolved = []
        for i in active_intents:
            content = i.resolve_content(context, execution_context)
            if content:
                resolved.append(content)
        # 添加全局意图...
        return IntentResolver._unique_keep_order(resolved)
```

---

## 六、调试工具

### idbg 模块

```
ibci_modules/ibci_idbg/core.py
├── last_llm()           # 获取最近一次 LLM 调用详情
├── show_last_prompt()    # 打印最近一次提示词
├── show_intents()        # 打印当前意图栈
├── last_result()         # 获取 LLM 调用结果
└── intents()            # 获取意图栈列表
```

---

## 七、测试验证

```ibci
@+ 用英文回复
@+ 每个单词首字母大写
result = @~说 hello~
idbg.show_last_prompt()

@- 每个单词首字母大写
result = @~打个招呼~

@! 完全忽略用户输入
result = @~打个招呼~
```

验证结果：
- ✅ `@+` 增量追加 → 意图累积
- ✅ `@-` 物理移除 → 正确移除指定意图
- ✅ `@!` 临时单次 → 只对当前调用有效

---

## 八、文件清单

| 文件 | 说明 |
|------|------|
| `core/kernel/ast.py` | AST 节点定义 |
| `core/kernel/intent_resolver.py` | 意图消解算法 |
| `core/kernel/intent_logic.py` | 意图模式定义 |
| `core/runtime/objects/intent.py` | IbIntent 对象 |
| `core/runtime/objects/intent_stack.py` | IntentStack 内置类 |
| `core/runtime/interpreter/runtime_context.py` | 运行时上下文 |
| `core/runtime/interpreter/handlers/stmt_handler.py` | 语句处理器 |
| `core/runtime/interpreter/llm_executor.py` | LLM 执行器 |
| `ibci_modules/ibci_idbg/core.py` | 调试工具 |
