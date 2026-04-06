# 意图注释改造计划

> 本文档记录 IBC-Inter 意图注释系统的架构改造计划。

**创建日期**：2026-04-06
**状态**：规划中
**版本**：v1.0

---

## 一、背景与目标

### 1.1 当前实现问题

1. **Tag 解析使用正则表达式**：在 Parser 层使用 `re.match()` 解析 `#tag`，这是临时方案
2. **解析逻辑分散**：部分在 Lexer（`IN_INTENT` 状态），部分在 Parser
3. **意图栈未正式集成**：意图栈是手动链表实现，不是 IBCI 内置类
4. **AST 层意图注释不是独立节点**：意图是"涂抹式元数据"而非一等公民

### 1.2 改造目标

1. **AST 层改造**：意图注释作为独立 AST 节点处理
2. **编译器职责简化**：语法检查更清晰
3. **公理体系融入**：意图栈正式成为 IBCI 内置类型

---

## 二、设计方案

### 2.1 方案 1：AST 层改造（强烈推荐）

#### 设计目标
将意图注释从"涂抹式元数据"改造为**独立 AST 节点**

#### 节点设计

```python
# core/kernel/ast.py 新增节点

@dataclass(kw_only=True, eq=False)
class IbIntentAnnotation(IbStmt):
    """
    意图注释节点 - @ 和 @! 专用
    替代涂抹式关联，实现意图注释的 AST 级别独立表示。
    """
    mode: IntentMode                    # APPEND, OVERRIDE
    tag: Optional[str]                  # 可选标签
    content: str                         # 静态意图内容
    segments: Optional[List[IbExpr]]     # 动态插值片段
    scope: IntentScope = IntentScope.LINE  # 作用域

@dataclass(kw_only=True, eq=False)
class IbIntentStackOperation(IbStmt):
    """
    意图栈操作节点 - @+ 和 @- 专用
    允许独立存在，作为全局意图栈操作
    """
    operation: Literal["push", "pop"]   # 操作类型
    mode: IntentMode                    # APPEND, REMOVE
    tag: Optional[str]                  # 可选标签
    content: Optional[str]               # 内容（push 时需要）
    segments: Optional[List[IbExpr]]     # 动态插值片段
```

#### 与现有 IbIntentInfo 的关系

- `IbIntentInfo` 保留作为**意图元数据**的数据结构
- `IbIntentAnnotation` 组合使用 `IbIntentInfo` 作为其内部表示
- 块级 `intent` 语句仍使用 `IbIntentInfo`

### 2.2 方案 2：编译器职责简化

#### 语法检查规则

| 意图模式 | 规则 | 说明 |
|----------|------|------|
| `@` (APPEND) | 必须后续紧跟 LLM 调用 | 单行意图必须有目标 |
| `@!` (OVERRIDE) | 必须后续紧跟 LLM 调用 | 排他意图必须有目标 |
| `@+` (APPEND) | 允许独立存在 | 栈叠加操作 |
| `@-` (REMOVE) | 允许独立存在 | 栈移除操作 |

#### 作用域概念

```python
class IntentScope(Enum):
    LINE = auto()     # 行级：必须紧跟 LLM 调用
    BLOCK = auto()    # 块级：作用于整个代码块
    MODULE = auto()   # 模块级：作用于整个模块
```

#### 编译期检查示例

```ibc-inter
# 合法用法
@ 用中文回复
str result = @~打个招呼~

# 合法用法
@+ 添加全局约束
str result = @~打个招呼~

# 非法用法 - @ 必须紧跟 LLM 调用
@ 没有后续调用的意图
str x = 1  # 这不是 LLM 调用！

# 错误信息
Error: Intent annotation '@' must be followed by an LLM call expression
  --> example.ibci:5:5
  |
5 | @ 没有后续调用的意图
  | ^^^^ Intent annotation without following LLM call
```

### 2.3 方案 3：公理体系融入

#### 设计目标
意图注释对应一个**全局意图栈类实例**，是操作这个实例的**语法糖**

#### IntentStack 内置类

```python
# core/runtime/objects/intent_stack.py (新建)
class IbIntentStack(IbObject):
    """
    意图栈类：作为 IBCI 内置类，封装全局意图栈操作。
    实现 UTS 协议，可被 IBCI 代码直接操作。
    """
    def __init__(self, ib_class: IbClass):
        super().__init__(ib_class)
        self._stack: List[IbIntent] = []
    
    def push(self, intent: IbIntent) -> None:
        """压入意图"""
        if intent.mode == IntentMode.OVERRIDE:
            self._stack.clear()  # 排他模式清空栈
        self._stack.append(intent)
    
    def pop(self, tag: Optional[str] = None) -> Optional[IbIntent]:
        """弹出意图"""
        if tag:
            # 按标签移除
            for i, intent in enumerate(self._stack):
                if intent.tag == tag:
                    return self._stack.pop(i)
            return None
        return self._stack.pop() if self._stack else None
    
    def clear(self) -> None:
        """清空栈"""
        self._stack.clear()
    
    def get_active(self) -> List[IbIntent]:
        """获取活跃意图列表"""
        return list(self._stack)
    
    def resolve(self, call_intent: Optional[IbIntent] = None) -> List[str]:
        """消解为 Prompt 字符串"""
        return IntentResolver.resolve(
            active_intents=self._stack,
            call_intent=call_intent
        )
```

#### 语法糖映射

| 意图注释 | 等价操作 |
|----------|----------|
| `@ "content"` | `IntentStack.push(Intent(content, APPEND))` |
| `@+ "content"` | `IntentStack.push(Intent(content, APPEND))` |
| `@! "content"` | `IntentStack.push(Intent(content, OVERRIDE))` |
| `@- #tag` | `IntentStack.pop(tag=tag)` |

#### 未来扩展：多栈支持

```ibc-inter
# 创建命名意图栈
@my_stack.push "用户想要完成订单"
str result = @~处理订单~

# 插件可创建自定义意图栈
import agent_stack from "agent_plugin"
agent_stack.push("Agent 特定意图")
```

---

## 三、实施计划

### Phase 1：AST 层改造

**优先级**：P1（高）
**预计时间**：2-3 天

| 任务 | 文件 | 复杂度 | 说明 |
|------|------|--------|------|
| 新增 `IbIntentAnnotation` 节点 | `ast.py` | 简单 | 意图注释节点 |
| 新增 `IbIntentStackOperation` 节点 | `ast.py` | 简单 | 栈操作节点 |
| 修改 `at_intent_shorthand()` | `statement.py` | 高 | 返回独立节点 |
| 修改 `_parse_intent_info()` | `statement.py` | 中等 | 支持新节点 |
| 更新序列化器 | `serializer.py` | 中等 | 支持新节点 |

### Phase 2：编译器语法检查

**优先级**：P1（高）
**预计时间**：1-2 天

| 任务 | 文件 | 复杂度 | 说明 |
|------|------|--------|------|
| 新增意图-LLM 绑定检查 Pass | `semantic_analyzer.py` | 高 | @/@! 必须紧跟 LLM 调用 |
| 实现 `_is_llm_call()` 辅助方法 | `semantic_analyzer.py` | 中等 | 判断是否为 LLM 调用 |
| 处理嵌套作用域 | `semantic_analyzer.py` | 中等 | for/while/if 嵌套 |
| 优化错误信息 | `issue_tracker.py` | 简单 | 提供修复建议 |

### Phase 3：公理体系融入

**优先级**：P2（中）
**预计时间**：2-3 天

| 任务 | 文件 | 复杂度 | 说明 |
|------|------|--------|------|
| 定义 `IntentStack` 内置类 | `intent_stack.py` (新) | 中等 | 实现 IbObject |
| 实现 UTS 协议 | `intent_stack.py` | 中等 | Iter/Callable 能力 |
| 注册为内置类型 | `builtin_initializer.py` | 简单 | 初始化时注册 |
| 设计语法糖映射 | `statement.py` | 简单 | 注释 → 栈操作 |

### Phase 4：Runtime 集成

**优先级**：P2（中）
**预计时间**：1-2 天

| 任务 | 文件 | 复杂度 | 说明 |
|------|------|--------|------|
| 新增 `visit_IbIntentAnnotation` | `interpreter.py` | 高 | 处理意图注释 |
| 新增 `visit_IbIntentStackOperation` | `interpreter.py` | 高 | 处理栈操作 |
| 更新 `push_intent`/`pop_intent` | `runtime_context.py` | 中等 | 与 IntentStack 同步 |
| 重构 `IntentResolver.resolve()` | `intent_resolver.py` | 高 | 公理化消解算法 |

### Phase 5：测试与文档

**优先级**：P1（高）
**预计时间**：1-2 天

| 任务 | 说明 |
|------|------|
| Lexer 单元测试 | 覆盖 `@`, `@+`, `@-`, `@!` 语法 |
| Parser 单元测试 | 新节点解析正确性 |
| 语义分析测试 | 语法检查规则 |
| 集成测试 | 端到端场景 |
| 文档更新 | IBCI_SPEC.md, SYNTAX_REFERENCE.md |

---

## 四、文件改动汇总

### 4.1 编译期文件

| 文件 | 改动类型 | 复杂度 |
|------|----------|--------|
| `core/compiler/common/tokens.py` | 可能新增 TokenType | 简单 |
| `core/compiler/lexer/core_scanner.py` | 调整意图扫描 | 中等 |
| `core/compiler/parser/components/statement.py` | **核心重构** | 高 |
| `core/compiler/parser/components/declaration.py` | 移除涂抹逻辑 | 中等 |
| `core/compiler/semantic/passes/semantic_analyzer.py` | **新增检查** | 高 |
| `core/compiler/semantic/passes/side_table.py` | 调整绑定 | 简单 |
| `core/kernel/ast.py` | **新增节点** | 简单 |
| `core/compiler/serialization/serializer.py` | 支持新节点 | 中等 |

### 4.2 运行时文件

| 文件 | 改动类型 | 复杂度 |
|------|----------|--------|
| `core/runtime/objects/intent.py` | 扩展支持 | 简单 |
| `core/runtime/objects/intent_stack.py` | **新建** | 中等 |
| `core/runtime/interpreter/runtime_context.py` | **重构** | 高 |
| `core/runtime/interpreter/interpreter.py` | **新增访问器** | 高 |
| `core/runtime/interpreter/llm_executor.py` | 调整接口 | 简单 |
| `core/kernel/intent_resolver.py` | **重构算法** | 高 |

### 4.3 新增文件

| 文件 | 职责 |
|------|------|
| `core/runtime/objects/intent_stack.py` | IntentStack 内置类 |
| `core/compiler/semantic/passes/intent_validator.py` | 意图-LLM 绑定检查 |

---

## 五、风险与缓解

| 风险点 | 影响 | 概率 | 缓解措施 |
|--------|------|------|----------|
| 向后兼容破坏 | 高 | 中 | 保持 IbIntentInfo 作为兼容层 |
| Lexer 状态冲突 | 中 | 低 | 复用现有 IN_INTENT 状态 |
| 意图栈同步问题 | 高 | 中 | 设计单向数据流 |
| 测试覆盖不足 | 中 | 中 | 增量测试策略 |

---

## 六、依赖关系图

```
tokens.py ──────────────────────────────┐
      │                                  │
      ▼                                  ▼
core_scanner.py ──────────────────► statement.py
      │                                  │
      │                                  ▼
      │                           declaration.py
      │                                  │
      │                                  ▼
      └──────────────┐           semantic_analyzer.py
                     │                  │
                     │                  ▼
                     │           side_table.py
                     │                  │
                     │                  ▼
                     │           serializer.py
                     │                  │
                     └──────────────────┤
                                        │
                                        ▼
                              runtime_context.py ◄──┐
                                        │            │
                                        ▼            │
                              interpreter.py ───────┤
                                        │            │
                                        ▼            │
                              llm_executor.py ───────┤
                                        │            │
                                        ▼            │
                              intent_resolver.py ───┘
```

---

## 七、成功标准

1. **功能完整性**：所有四种意图注释模式正常工作
2. **编译期检查**：@/@! 必须紧跟 LLM 调用
3. **向后兼容**：现有代码无需修改即可运行
4. **测试覆盖**：核心路径 100% 覆盖
5. **文档完整**：IBCI_SPEC.md 同步更新

---

*最后更新：2026-04-06*
