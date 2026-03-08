# IBC-Inter 编译器架构重构指南：内置运算行为的元数据化

**状态**：进行中 (In Progress) - 核心逻辑已转移至 [symbols.py](file:///c:/myself/proj/intent-behavior-code-inter/core/domain/symbols.py)，待完全 UTS 化。
**当前位置**：[symbols.py](file:///c:/myself/proj/intent-behavior-code-inter/core/domain/symbols.py)

## 1. 背景与现状 (Context)
在目前的 IBC-Inter 编译器实现中，[symbols.py](file:///c:/myself/proj/intent-behavior-code-inter/core/domain/symbols.py) 的 `BuiltinType.get_operator_result` 方法中包含了一部分硬编码的运算规则（如 `int + int = int`）。

虽然这部分代码已被封装在语义对象内部，实现了物理隔离，但它在逻辑上依然属于“影子解释器”行为——编译器在代码层面模拟了解释器的运行逻辑。为了实现极致的架构正义和跨平台一致性，这部分硬编码逻辑应被重构为**元数据驱动 (Metadata-driven)**。

## 2. 目标状态 (Target Architecture)
- **零硬编码**：编译器不再包含任何关于 `int`、`str` 等内置类型的先验运算知识。
- **元数据驱动**：所有的运算规则（一元、二元运算符及其结果类型）都声明在 [core/foundation/types/base.py](file:///core/foundation/types/base.py) 的 `TypeDescriptor` 中。
- **协议化决议**：编译器仅负责读取 UTS (Unified Type System) 元数据并按图索骥。

## 3. 改造步骤 (Refactoring Steps)

### 第一步：增强 UTS 描述符 (Foundation 层)
在 `TypeDescriptor` 类中增加 `operator_rules` 字段，用于描述该类型支持的运算协议。

```python
# core/foundation/types/base.py

@dataclass
class TypeDescriptor:
    name: str
    # ... 现有字段 ...
    
    # 运算规则表: { "op": { "other_type_name": "result_type_name", "_unary_": "result_type_name" } }
    operator_rules: Dict[str, Dict[str, str]] = field(default_factory=dict)
```

### 第二步：更新内置类型元数据 (Metadata 层)
在 `core/foundation/types/builtins.py`（或相关预定义位置）中，为内置类型填入规则。

```python
# 示例：int 类型的描述符定义
INT_DESCRIPTOR = TypeDescriptor(
    name="int",
    operator_rules={
        "+": {"int": "int", "float": "float"},
        "-": {"int": "int", "float": "float"},
        "~": {"_unary_": "int"},
        ">": {"int": "bool", "float": "bool"}
    }
)
```

### 第三步：重构语义决议逻辑 (Compiler 层)
修改 `BuiltinType` 的 `get_operator_result` 方法，将其改为查表逻辑。

```python
# core/compiler/semantic/symbols.py

class BuiltinType(StaticType):
    def get_operator_result(self, op: str, other: Optional['StaticType'] = None) -> Optional['StaticType']:
        if not self.descriptor or not self.descriptor.operator_rules:
            return super().get_operator_result(op, other)
            
        rules = self.descriptor.operator_rules.get(op)
        if not rules:
            return None
            
        # 处理一元运算
        if not other:
            res_name = rules.get("_unary_")
            return get_builtin_type(res_name) if res_name else None
            
        # 处理二元运算
        res_name = rules.get(other.name)
        return get_builtin_type(res_name) if res_name else None
```

## 4. 验证要点 (Verification)
1. **基础类型全覆盖**：确保 `int`, `str`, `float`, `bool` 的所有运算组合在元数据中均有定义。
2. **隐式提升校验**：验证 `int + float` 是否能正确决议为 `float`。
3. **错误捕获**：验证 `str - int` 等非法操作是否能通过元数据缺失正确触发 `SEMANTIC_ERROR`。

## 5. 预期收益
- **彻底解耦**：编译器代码与具体内置类型的业务逻辑完全隔离。
- **无痛扩展**：引入新类型（如 `Complex` 或 `Vector`）时，只需增加元数据文件，无需触碰编译器核心。
- **协议一致性**：解释器可以直接读取这些 `operator_rules` 来动态绑定其执行函数，确保“所见即所得”。

---
**本指南作为 IBC-Inter 编译器架构正义的最后一块拼图，旨在指导未来的开发者完成从“代码模拟”到“元数据协议”的最终跨越。**
