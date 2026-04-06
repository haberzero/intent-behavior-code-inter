# IBC-Inter LLM调用增强体系重构计划

> 本文档记录ibc-inter项目中LLM调用相关机制的重构目标和规划，作为后续工作的指导和对齐基准。

---

## 一、目标概述

本次重构的目标是构建一套完整的、可控的、面向对象的LLM调用增强体系，涵盖从输入转换到输出解析的完整链路。

### 核心目标

1. **统一输入输出机制**：建立明确的`__to_prompt__`和`__from_prompt__`配对机制
2. **消除历史包袱**：彻底移除scene/decision_map等过渡性机制
3. **增强开发者控制**：提供清晰的retry hint控制能力
4. **简化执行流程**：通过面向对象的方式统一处理LLM调用

### 设计原则

- **面向对象**：类应该定义自身如何被序列化为提示词，以及如何从提示词解析
- **开发者控制**：错误信息和重试提示由开发者显式控制，不泄露到外部
- **彻底重构**：不留任何deprecated标记，不保留兼容性代码
- **接口清晰**：输入和输出机制职责分明

---

## 二、概念定义

### 2.1 输入机制：__to_prompt__

当一个变量作为参数被送入LLM调用过程时，该变量如何被转化为提示词的一部分。

**定位**：定义"如何将对象发送给LLM"

**调用时机**：在`_evaluate_segments()`中遍历参数时调用

### 2.2 输出约束：__llmoutput_hint__

描述期望的LLM输出格式，作为提示词注入的一部分。

**定位**：定义"期望从LLM得到什么样的回复"

**调用时机**：在构建LLM系统提示词时注入

### 2.3 输出解析：__from_prompt__

定义如何从LLM返回的原始文本中解析为目标类型的值。

**定位**：定义"如何将LLM的回复转换为我的类型"

**返回值格式**：`Tuple[bool, Any]`
- `(True, value)` - 解析成功，返回解析后的值
- `(False, retry_hint)` - 解析失败，返回错误提示信息

**调用时机**：LLM调用返回后进行解析时

### 2.4 不确定性机制

当`__from_prompt__`返回`(False, retry_hint)`时，视为"不确定性结果"。

**与旧机制的区别**：
- 旧：`is_uncertain`标记由LLMExecutor内部设置
- 新：统一由`__from_prompt__`的返回值表达

### 2.5 llmexcept与retry

**llmexcept**：当LLM调用产生不确定性结果时，进入处理块

**retry**：在llmexcept块中显式触发重试，可携带hint

**retry hint传播**：
- 优先级：运行时`context.retry_hint` > 函数定义中的hint
- 作用域：仅在llmexcept块内生效，不泄露到外部
- 清除时机：LLM调用执行后清除

---

## 三、架构设计

### 3.1 接口层次

```
IIbObject (协议层)
├── __to_prompt__() -> str                    # 输入转换
├── __from_prompt__(raw: str) -> Tuple[bool, Any]  # 输出解析
└── __llmoutput_hint__() -> str              # 输出约束
```

### 3.2 类型系统集成

```
TypeDescriptor
├── name: str
└── _axiom: TypeAxiom
    ├── parse_value(raw) -> Any              # 现有，保持兼容
    ├── from_prompt(raw) -> Tuple[bool, Any] # 新增
    └── get_llmoutput_hint() -> str          # 新增
```

### 3.3 执行流程

```
LLM调用请求
    │
    ├── 1. 获取__llmoutput_hint__() → 注入系统提示词
    │
    ├── 2. 调用LLM
    │
    └── 3. 调用__from_prompt__(raw_response)
            │
            ├── (True, value) → 成功赋值
            │
            └── (False, hint) → 触发llmexcept
                    │
                    └── llmexcept块内可以retry(hint)
```

---

## 四、需删除的旧机制

### 4.1 Scene机制

**问题**：Scene机制用于区分"分支场景"、"循环场景"等，与新的面向对象设计理念不符。

**需删除内容**：
- `IbScene`枚举定义
- `node_scenes`侧表
- scene栈管理
- scene相关绑定逻辑

### 4.2 Decision Map机制

**问题**：Decision Map是过渡性机制，应该被`__from_prompt__`统一替代。

**需删除内容**：
- `decision_maps`侧表
- decision_map查找逻辑
- `get_decision_map`方法
- scene关键词判断逻辑

### 4.3 is_uncertain机制

**问题**：`is_uncertain`标记分散在多处，应该被`__from_prompt__`的返回值统一表达。

**需删除内容**：
- `LLMResult.is_uncertain`字段（替换为通过from_prompt返回值判断）
- 相关检测和处理逻辑

---

## 五、需保留的机制

### 5.1 llmexcept/retry/llmretry

这些语句是用户控制重试的重要手段，必须保留。

**保留内容**：
- `IbRetry` AST节点
- `IbLLMExceptionalStmt` AST节点
- `visit_IbRetry`执行逻辑
- `visit_IbLLMExceptionalStmt`执行逻辑
- `retry_hint`传播机制

### 5.2 LLMExceptFrame

用于管理重试状态和上下文快照。

**保留内容**：
- 帧栈管理
- 现场保存与恢复
- 重试计数
- `ai.set_retry()`/`ai.get_retry()`配置接口

### 5.3 LLMResult

虽然`is_uncertain`标记会被移除，但基础结构保留。

**保留内容**：
- 成功结果携带value
- 失败结果携带retry_hint

---

## 六、实施阶段

### 阶段一：接口协议扩展

**目标**：定义新的接口协议和基类实现

**主要工作**：
- 在`protocols.py`中定义新协议
- 在`interfaces.py`中扩展`IIbObject`
- 实现基类默认行为

### 阶段二：Axiom实现

**目标**：为内置类型实现新的接口

**主要工作**：
- 修改Axiom基类
- 为Int、Bool、Str、List、Dict等实现`from_prompt`和`__llmoutput_hint__`

### 阶段三：LLMExecutor集成

**目标**：将新接口集成到LLM调用流程中

**主要工作**：
- 修改`execute_behavior_expression`
- 修改`execute_llm_function`
- 移除decision_map查找逻辑

### 阶段四：清理旧机制

**目标**：彻底删除scene/decision_map/is_uncertain相关代码

**主要工作**：
- 删除`IbScene`枚举
- 删除scene侧表和绑定逻辑
- 删除decision_map相关代码
- 简化`visit_IbIf`等执行逻辑

### 阶段五：文档和验证

**目标**：更新文档，确保功能正常

**主要工作**：
- 更新IBCI_SPEC.md
- 验证现有示例
- 编写新的示例代码

---

## 七、核心逻辑要点

### 7.1 __from_prompt__返回值语义

```python
def __from_prompt__(self, raw_response: str) -> Tuple[bool, Any]:
    """
    解析LLM返回的原始文本。

    Returns:
        (True, parsed_value) - 解析成功
        (False, retry_hint)  - 解析失败，retry_hint用于提示重试方向
    """
```

### 7.2 llmexcept触发条件

当LLM调用的`__from_prompt__`返回`(False, retry_hint)`时，触发llmexcept块执行。

### 7.3 retry hint控制权

- 运行时`context.retry_hint`：由llmexcept块内的retry语句设置
- 函数定义中的hint：作为fallback
- 开发者可自由选择是否使用`__from_prompt__`返回的hint

### 7.4 重试次数限制

通过`ai.set_retry(n)`配置，避免死循环。LLM调用是高成本操作，需要保护。

---

## 八、命名约定

| 命名 | 说明 |
|------|------|
| `__to_prompt__` | 输入转换，已存在 |
| `__llmoutput_hint__` | 输出约束，新增 |
| `__from_prompt__` | 输出解析，新增 |

---

## 九、注意事项

1. **分阶段实施**：每个阶段完成后进行验证，确保功能正常
2. **彻底删除**：不留任何旧机制的痕迹，包括注释中的提示
3. **接口一致性**：所有类型应遵循相同的接口约定
4. **向后验证**：修改后应能运行现有通过验证的示例
