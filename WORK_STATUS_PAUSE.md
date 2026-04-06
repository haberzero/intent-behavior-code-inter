# IBC-Inter LLM调用机制重构 - 工作状态暂停记录

> 本文档记录当前工作状态，供后续工作接手参考。

---

## 一、已完成的工作

### 1.1 新增接口协议

**文件**: `core/kernel/axioms/protocols.py`
- 新增 `FromPromptCapability` 协议
- 新增 `IlmoutputHintCapability` 协议
- 在 `TypeDescriptor` 中添加对应获取方法

**文件**: `core/runtime/interfaces.py`
- 在 `IIbObject` 协议中添加 `__from_prompt__` 和 `__llmoutput_hint__` 方法定义

**文件**: `core/runtime/objects/kernel.py`
- 在 `IbObject` 基类中实现默认的 `__from_prompt__` 和 `__llmoutput_hint__` 方法

### 1.2 Axiom实现

**文件**: `core/kernel/axioms/primitives.py`
- 为 `IntAxiom`、`FloatAxiom`、`BoolAxiom`、`StrAxiom`、`ListAxiom`、`DictAxiom` 实现 `from_prompt` 和 `__llmoutput_hint__` 方法

### 1.3 LLMExecutor集成

**文件**: `core/runtime/interpreter/llm_executor.py`
- 新增 `_get_llmoutput_hint()` 方法获取输出约束
- 新增 `_get_expected_type_hint()` 方法获取预期类型
- 修改 `_parse_result()` 方法优先使用 `from_prompt` 机制
- 修改 `execute_behavior_expression()` 注入 `__llmoutput_hint__`

### 1.4 删除旧机制

**已删除的内容**:
| 文件 | 删除内容 |
|------|---------|
| `core/kernel/ast.py` | `IbScene` 枚举 |
| `core/compiler/semantic/passes/side_table.py` | `node_scenes`、`decision_maps` |
| `core/compiler/semantic/passes/scope_manager.py` | scene栈管理 |
| `core/compiler/semantic/passes/semantic_analyzer.py` | 部分scene绑定逻辑 |
| `core/compiler/serialization/serializer.py` | scene/decision_map序列化 |
| `core/kernel/blueprint.py` | `node_scenes`、`decision_maps` 字段 |
| `core/runtime/interpreter/llm_executor.py` | 部分scene参数和decision_map查找逻辑 |
| `ibci_modules/ibci_ai/core.py` | `get_scene_prompt`、`get_decision_map`、`set_decision_map` |
| `ibci_modules/ibci_ai/_spec.py` | decision_map相关方法定义 |

### 1.5 文档更新

**文件**: `IBCI_SPEC.md`
- 新增 3.1.1 节：输入机制 `__to_prompt__`
- 新增 3.1.2 节：输出约束 `__llmoutput_hint__`
- 新增 3.1.3 节：输出解析 `__from_prompt__`

### 1.6 新增示例文件

**新增文件**:
- `examples/01_getting_started/03_flow_control_and_behavior.ibci` - 流控与行为描述结合
- `examples/01_getting_started/04_mock_and_llmexcept.ibci` - Mock机制与llmexcept

### 1.7 Git提交

已完成8个commit记录所有修改。

---

## 二、当前问题

### 2.1 已提交但未验证的错误

**问题**: `ibci_ai/_spec.py` 中删除了 `get_scene_prompt` 方法，但运行时仍在检查该方法存在性。

**错误信息**:
```
Plugin implementation error: Module 'ai' is missing required method 'get_scene_prompt' declared in _spec.py
```

**原因**: `_spec.py` 中仍然声明了 `get_scene_prompt`，但 `core.py` 中已删除该方法。

**解决方案**: 需要在 `_spec.py` 中也删除 `get_scene_prompt` 的声明。

### 2.2 语义分析中的LLM函数识别问题

**问题**: `_expr_contains_behavior` 方法需要正确识别LLM函数调用。

**当前状态**:
- 已修改 `_expr_contains_behavior` 来检查 `SymbolKind.LLM_FUNCTION` 或 `sym.metadata.get("is_llm")`
- 但 `_spec.py` 中的方法检查导致插件加载失败
- 需要先修复 2.1 问题后才能继续验证

### 2.3 DEBUG代码残留

**文件**: `core/compiler/semantic/passes/semantic_analyzer.py`
- 第 265-275 行有 `print(f"[DEBUG] ...")` 语句
- 需要在最终完成后移除

---

## 三、待完成的工作

### 3.1 紧急：修复插件加载问题

1. 在 `ibci_modules/ibci_ai/_spec.py` 中删除 `get_scene_prompt` 的方法声明
2. 验证插件能正常加载

### 3.2 验证LLM函数识别

1. 确认 `_expr_contains_behavior` 能正确识别LLM函数调用（如 `翻译(...)`）
2. 运行 `01_hello_world.ibci` 测试意图注释是否正确工作

### 3.3 移除DEBUG代码

1. 删除 `semantic_analyzer.py` 中的 DEBUG print 语句

### 3.4 清理llm_executor.py

1. 检查并移除不再需要的 scene 相关代码
2. 确保 `execute_behavior_expression` 和 `execute_llm_function` 都正确使用新机制

### 3.5 测试验证

1. 运行所有示例文件验证
2. 确保现有功能不受影响

---

## 四、关键代码位置

### 4.1 插件规范文件
**文件**: `ibci_modules/ibci_ai/_spec.py`
- 需要删除 `get_scene_prompt` 声明

### 4.2 语义分析
**文件**: `core/compiler/semantic/passes/semantic_analyzer.py`
- `_expr_contains_behavior` 方法（第257行）
- DEBUG代码（第265-275行）

### 4.3 LLM执行器
**文件**: `core/runtime/interpreter/llm_executor.py`
- `_get_llmoutput_hint` 方法（第254行）
- `_get_expected_type_hint` 方法（第267行）
- `_parse_result` 方法（第280行）

---

## 五、建议的后续步骤

1. **立即修复**: 在 `_spec.py` 中删除 `get_scene_prompt` 声明
2. **运行验证**: 执行 `python main.py run examples/01_getting_started/01_hello_world.ibci`
3. **观察结果**: 检查意图注释是否正确绑定到LLM函数调用
4. **清理代码**: 移除DEBUG语句
5. **完整测试**: 运行所有示例文件

---

*记录时间: 2026-04-07*
*记录人: AI Assistant*
