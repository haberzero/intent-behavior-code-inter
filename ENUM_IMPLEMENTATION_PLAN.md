# IBCI Enum 实现可行性分析与工作计划

> 创建日期：2026-04-08
> 状态：可行性分析完成，待实施

---

## 一、背景与目标

本文档分析在 IBC-Inter 语言中实现**继承式 Enum 类**的可行性，以及通过 Enum 实现 **Switch-Case 语法**的方案。

核心目标：
1. 允许 IBCI 脚本编写者定义继承式 Enum 类（类似 Python）
2. 通过 Enum 类的 `__prompt__` 协议，自动提示 LLM 可以输出的内容
3. 实现优雅的 Switch-Case 语法，替代 if-else 链

---

## 二、现有架构检查

### 2.1 类继承机制 ✅ 已完善

| 层级 | 组件 | 状态 | 说明 |
|------|------|------|------|
| **元数据层** | `ClassMetadata` | ✅ | `parent_name` + `resolve_parent()` 支持继承链查找 |
| **运行时层** | `IbClass` | ✅ | `lookup_method()` 实现 MRO |
| **属性访问** | `resolve_member()` | ✅ | 向上递归查找父类成员 |
| **用户类** | Parser | ✅ | 支持 `class Child(Parent):` 语法 |
| **实例化** | `instantiate()` | ✅ | 调用 `__init__` 初始化 |

**核心实现**：

```python
# 元数据层
class ClassMetadata(TypeDescriptor):
    parent_name: Optional[str] = None
    
    def resolve_parent(self):
        if not self.parent_name: return None
        return self._registry.resolve(self.parent_name)

# 运行时层
class IbClass(IbObject):
    def lookup_method(self, name: str):
        if name in self.methods:
            return self.methods[name]
        if self.parent:
            return self.parent.lookup_method(name)  # 递归向上
        return None
```

### 2.2 LLM 交互协议 ✅ 已完善

| 协议方法 | 用户可实现 | 说明 |
|----------|------------|------|
| `__to_prompt__` | ✅ | 对象 → 提示词片段 |
| `__from_prompt__` | ✅ | LLM 响应 → 类型实例 |
| `__llmoutput_hint__` | ✅ | 注入 LLM 输出格式约束 |

**调用链**：

```
用户调用 @~ ... ~
        ↓
execute_behavior_expression()
        ↓
_get_llmoutput_hint() → descriptor._axiom.__llmoutput_hint__()
        ↓
LLM 返回 raw_response
        ↓
_parse_result() → descriptor._axiom.__from_prompt__()
```

### 2.3 用户协议实现 ✅ 已支持

`IbObject` 的 `receive()` 方法通过 `lookup_method()` 查找协议方法，**支持继承链向上查找**：

```python
class IbObject:
    def __to_prompt__(self) -> str:
        res = self.receive('__to_prompt__', [])
        return str(res.value)
    
    def receive(self, message: str, args: List):
        method = self.ib_class.lookup_method(message)
        if method:
            return method.call(self, args)
```

---

## 三、Enum 实现方案

### 3.1 Enum 类型定义

#### 方案 A：继承式 Enum（推荐）

```ibci
# 用户定义枚举类
class Color(Enum):
    RED, GREEN, BLUE

# 使用
Color c = @~ 天空是什么颜色？ ~
switch c:
    case Color.RED: print("红色")
    case Color.GREEN: print("绿色")
    case Color.BLUE: print("蓝色")
```

#### 方案 B：`enum` 关键字语法糖

```ibci
# 更简洁的语法
enum Color(RED, GREEN, BLUE)
```

### 3.2 Enum 基类需要提供的协议

```ibci
class Enum:
    # __llmoutput_hint__：根据枚举值自动生成约束
    func __llmoutput_hint__() -> str:
        return "请只回复: " + self._get_value_names()
    
    # __from_prompt__：解析 LLM 输出
    func __from_prompt__(response: str) -> (bool, Enum):
        # 匹配枚举值名称
        ...
    
    # 内部方法
    func _get_value_names() -> str:
        # 返回: "RED, GREEN, BLUE"
        return ", ".join(self._values)
```

### 3.3 Switch-Case 语法

```ibci
switch 表达式:
    case 值1: 语句块1
    case 值2: 语句块2
    default: 语句块3
```

---

## 四、实现路径

### 第一阶段：Enum 基类（Python 层面）

| 任务 | 文件 | 内容 |
|------|------|------|
| 创建 EnumAxiom | `core/kernel/axioms/enum.py` | 实现 `__llmoutput_hint__` + `__from_prompt__` |
| 创建 IbEnum | `core/runtime/objects/enum.py` | 运行时枚举值对象 |
| 注册 EnumAxiom | `core/kernel/axioms/registry.py` | 注册到 axiom_registry |

### 第二阶段：Enum 语法（IBCI 层面）

| 任务 | 文件 | 内容 |
|------|------|------|
| 添加 enum token | `core/compiler/lexer/core_scanner.py` | 添加 `ENUM` 关键字 |
| 解析 enum 语法 | `core/compiler/parser/components/declaration.py` | 解析 `enum Name(VAL1, VAL2)` |
| 语义分析 | `core/compiler/semantic/passes/` | 分析枚举成员，推导类型 |

### 第三阶段：Switch-Case 语法

| 任务 | 文件 | 内容 |
|------|------|------|
| AST 节点 | `core/kernel/ast.py` | 添加 `IbSwitch`, `IbCase` |
| Parser | `core/compiler/parser/components/statement.py` | 解析 switch-case 语法 |
| Interpreter | `core/runtime/interpreter/handlers/stmt_handler.py` | 实现 `visit_IbSwitch` |

---

## 五、协议自动化填充机制详解

### 5.1 新方案：动态公理协议（推荐）

**核心思想**：内置 `Enum` 公理的 `__prompt__` 协议方法是**动态的**——它们在运行时查询具体枚举类的成员，自动生成提示和解析逻辑。

**不需要**：
- ❌ 编译时注入方法 AST
- ❌ 运行时注册新方法
- ❌ 用户手动编写 `__llmoutput_hint__`

**只需要**：
- ✅ 加强公理协议接口，传递 `TypeDescriptor` 上下文
- ✅ `EnumAxiom` 实现动态查询枚举成员

### 5.2 架构设计

```
┌─────────────────────────────────────────────────────────────────────┐
│                     动态公理协议执行流程                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  用户书写: Color c = @~ 天是什么颜色？ ~                            │
│                                                                      │
│  1. LLM 调用时获取 __llmoutput_hint__                              │
│     descriptor = meta_reg.resolve("Color")  → ColorDescriptor        │
│     hint_cap = descriptor._axiom.get_llmoutput_hint_capability()   │
│     hint = hint_cap.__llmoutput_hint__(descriptor)  ← 传递 descriptor│
│                                                                      │
│  2. EnumAxiom.__llmoutput_hint__ 动态查询                           │
│     members = descriptor.members  → {"RED": ..., "GREEN": ..., ...} │
│     enum_values = [name for name in members if name.isupper()]      │
│     return f"请只回复 {', '.join(enum_values)} 之一"                 │
│     → "请只回复 RED、GREEN 或 BLUE 之一"                            │
│                                                                      │
│  3. LLM 返回 "BLUE"                                                │
│                                                                      │
│  4. __from_prompt__ 动态解析                                        │
│     result = __from_prompt__("BLUE", descriptor)                    │
│     → (True, Color.BLUE)                                           │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.3 关键技术：协议接口扩展

**现有接口**（静态）：
```python
class IlmoutputHintCapability(Protocol):
    def __llm__(self) -> str:  # 不接收上下文
        ...
```

**新接口**（动态）：
```python
class IlmoutputHintCapability(Protocol):
    def __llmoutput_hint__(self, descriptor: Optional['TypeDescriptor'] = None) -> str:
        """
        返回期望的 LLM 输出格式描述。
        如果提供了 descriptor，则可以根据具体类型动态生成提示。
        """
        ...
```

### 5.4 EnumAxiom 实现

```python
class EnumAxiom(TypeAxiom):
    def __llmoutput_hint__(self, descriptor: Optional[TypeDescriptor] = None) -> str:
        if descriptor is None:
            return "请回复有效的枚举值"
        
        # 查询描述符的成员
        members = descriptor.members or {}
        
        # 收集枚举值（约定：大写字段视为枚举值）
        enum_values = []
        for name in members:
            if name.isupper() and not name.startswith('_'):
                enum_values.append(name)
        
        if not enum_values:
            return "请回复有效的枚举值"
        
        # 生成动态提示
        if len(enum_values) == 1:
            return f"请只回复 {enum_values[0]}"
        
        return f"请只回复 {', '.join(enum_values[:-1])} 或 {enum_values[-1]} 之一"
    
    def from_prompt(self, raw_response: str, descriptor: Optional[TypeDescriptor] = None) -> Tuple[bool, Any]:
        if descriptor is None:
            return (False, "无法解析枚举值")
        
        # 查询成员并匹配
        members = descriptor.members or {}
        val = raw_response.strip().upper()
        
        for name in members:
            if name.upper() == val:
                return (True, name)  # 返回枚举值名称
        
        return (False, f"无法解析 '{raw_response}'，请回复有效枚举值")
```

### 5.5 用户覆盖机制

用户可以在枚举类中显式定义协议方法，**覆盖公理提供的默认实现**：

```ibci
class Color(Enum):
    RED, GREEN, BLUE
    
    # 用户自定义覆盖
    __llmoutput_hint__: str = "用中文回答：红、绿、蓝"
```

**优先级**：
1. 用户显式定义的方法 → 使用用户定义
2. 公理动态生成的方法 → 兜底实现

### 5.6 方案对比

| 方案 | 可行性 | 侵入性 | 说明 |
|------|--------|--------|------|
| 运行时动态注册 | ❌ 不可行 | - | 类封印在脚本执行前已完成 |
| 语义分析时注入 | ✅ 可行 | 中等 | 编译时修改 AST |
| **动态公理协议** | ✅ 可行 | **低** | **公理自己会查询成员，无需注入** |

---

## 六、完整的用户代码示例

```ibci
# 简洁写法：公理自动生成协议方法
class Color(Enum):
    RED, GREEN, BLUE

# 使用（系统自动约束 LLM 输出）
Color c = @~ 天是什么颜色？ ~

# 用户覆盖：使用自定义提示
class Mood(Enum):
    HAPPY, SAD, ANGRY
    __llmoutput_hint__: str = "用中文回答：开心、难过或生气"
```

---

## 七、风险评估

| 影响项 | 风险等级 | 说明 |
|--------|----------|------|
| 现有类型系统 | **无风险** | 仅新增 axiom，不修改现有类型 |
| LLM 交互协议 | **无风险** | 复用现有协议 |
| Parser | **中风险** | 需要新增 token 和语法规则 |
| 向后兼容 | **无破坏** | 完全向后兼容 |

---

## 七、可行性结论

| 评估项 | 结论 | 说明 |
|--------|------|------|
| 类继承机制 | ✅ 完善 | 完全支持用户定义类继承 |
| 协议方法继承 | ✅ 完善 | `receive()` 支持 MRO 查找 |
| 用户可定义 Enum | ✅ 是 | 继承机制已就绪 |
| 动态公理协议 | ✅ 可行 | 公理自己查询成员，运行时生成协议 |
| 架构侵入性 | ✅ 低 | 仅扩展协议接口，不破坏核心 |

**最终结论**：实现继承式 Enum **完全可行**，采用**动态公理协议**方案，无需编译时注入，架构侵入性最低。

---

## 七、待办事项

### 第一阶段：核心机制

- [ ] 扩展协议接口，传递 `TypeDescriptor` 上下文
- [ ] 创建 EnumAxiom，实现动态 `__llmoutput_hint__` 和 `__from_prompt__`
- [ ] 创建 IbEnum 运行时对象
- [ ] 注册 EnumAxiom 到 axiom_registry

### 第二阶段：语法支持

- [ ] Parser 支持 `enum` 关键字语法
- [ ] 实现 switch-case 语法
- [ ] 用户覆盖机制验证

### 第三阶段：测试与文档

- [ ] 编写测试用例
- [ ] 更新 IBCI_SPEC.md

---

*本文档为后续工作的基准对齐文件，如有更新请同步修改。*
