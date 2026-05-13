# IBCI 重构优先行动计划 (Refactoring Priority Action Plan)

**创建日期**: 2026-05-13
**基于审计**: CODEBASE_AUDIT_REPORT.md
**聚焦领域**: 超大文件拆分、深层嵌套逻辑优化、局部导入清理

---

## 执行摘要 (Executive Summary)

本计划针对代码库中三大紧要问题提供可操作的重构方案：

1. **超大文件拆分** - 8 个文件 >1000 行需要模块化
2. **深层嵌套逻辑简化** - 7 处复杂条件分支需要重构
3. **局部导入清理** - 10 个非必要局部导入可移至顶层

**预估工作量**: 150-200 开发小时，跨 6-8 周
**风险等级**: 中等（需要全面测试回归验证）

---

## 第一部分：超大文件拆分计划

### 优先级 P0 - 立即执行

#### 任务 1.1: 拆分 `semantic_analyzer.py` (2,192 行 → 4 个模块)

**当前状态**:
- 文件: `/core/compiler/semantic/passes/semantic_analyzer.py`
- 行数: 2,192 行
- 类: SemanticAnalyzer (2,170 行，82 个方法)
- 问题: 所有语义分析逻辑单体打包

**拆分方案**:

```
core/compiler/semantic/passes/
├── semantic_analyzer.py        (保留 300-400 行)
│   └── SemanticAnalyzer (协调器，保留核心类型检查)
├── intent_binding_pass.py      (新建 300-400 行)
│   └── IntentBindingPass (intent 绑定、预加载逻辑)
├── behavior_detection_pass.py  (新建 200-300 行)
│   └── BehaviorDetectionPass (行为表达式检测与分析)
├── contract_validation_pass.py (新建 200-300 行)
│   └── ContractValidationPass (契约验证逻辑)
└── error_reporter.py           (新建 150-200 行)
    └── SemanticErrorReporter (错误/警告报告专用)
```

**具体步骤**:

1. **Phase 1.1.1**: 创建 Pass 基类和接口
   ```python
   # 新文件: semantic_pass_base.py
   class SemanticPass:
       def __init__(self, registry, side_table, scope_manager):
           self.registry = registry
           self.side_table = side_table
           self.scope_manager = scope_manager

       def process(self, node):
           raise NotImplementedError
   ```

2. **Phase 1.1.2**: 提取 IntentBindingPass
   - 移动方法: `_bind_intent_preload`, `_resolve_intent_context_arg`, `_check_intent_binding`
   - 移动 intent 相关的 visit 分支逻辑
   - 预估: 300-400 行

3. **Phase 1.1.3**: 提取 BehaviorDetectionPass
   - 移动方法: `_detect_behavior_expr`, `_analyze_behavior_dependency`
   - 移动 behavior 表达式相关逻辑
   - 预估: 200-300 行

4. **Phase 1.1.4**: 提取 ContractValidationPass
   - 移动契约验证相关方法
   - 预估: 200-300 行

5. **Phase 1.1.5**: 提取 SemanticErrorReporter
   - 移动所有 `self._add_error()`, `self._add_warning()` 调用点的错误构造逻辑
   - 集中错误消息格式化
   - 预估: 150-200 行

6. **Phase 1.1.6**: 重构 SemanticAnalyzer 为协调器
   - 保留核心类型检查逻辑（800-900 行）
   - 添加 pass 调度逻辑
   - 更新测试

**验证标准**:
- `pytest tests/compiler/test_semantic*.py -v` 全部通过
- `pytest tests/contracts/ -v` 全部通过
- 代码覆盖率不低于原水平

**预估工作量**: 40-50 小时

---

#### 任务 1.2: 拆分 `handlers.py` (1,955 行 → 6 个模块)

**当前状态**:
- 文件: `/core/runtime/vm/handlers.py`
- 行数: 1,955 行
- 问题: 43 个 handler 函数混在一个文件中

**拆分方案**:

```
core/runtime/vm/handlers/
├── __init__.py                 (分派表构建器，100 行)
├── expression_handlers.py      (新建 400 行)
│   ├── vm_handle_IbConstant
│   ├── vm_handle_IbName
│   ├── vm_handle_IbBinOp
│   ├── vm_handle_IbUnaryOp
│   ├── vm_handle_IbCompare
│   ├── vm_handle_IbSubscript
│   ├── vm_handle_IbAttribute
│   └── vm_handle_IbCastExpr
├── statement_handlers.py       (新建 300 行)
│   ├── vm_handle_IbIf
│   ├── vm_handle_IbWhile
│   ├── vm_handle_IbPass
│   ├── vm_handle_IbBreak
│   ├── vm_handle_IbContinue
│   └── vm_handle_IbReturn
├── assignment_handlers.py      (新建 250 行)
│   ├── vm_handle_IbAssign
│   ├── vm_handle_IbAugAssign
│   └── _assign_to_target (辅助函数)
├── control_flow_handlers.py   (新建 400 行)
│   ├── vm_handle_IbFor
│   ├── vm_handle_IbTry
│   └── vm_handle_IbLLMExcept
├── callable_handlers.py        (新建 350 行)
│   ├── vm_handle_IbCall
│   ├── vm_handle_IbLambda
│   └── vm_handle_IbBehaviorExpr
└── helpers.py                  (新建 200 行)
    ├── _vm_call_fn_callable
    ├── _vm_invoke_behavior
    └── _vm_invoke_llm_function
```

**具体步骤**:

1. **Phase 1.2.1**: 创建目录结构和 __init__.py
   - 创建 `handlers/` 目录
   - 实现分派表构建逻辑
   - 预估: 2-3 小时

2. **Phase 1.2.2**: 提取 expression_handlers.py
   - 移动简单表达式 handler (77-151 行区域)
   - 移动复杂表达式 handler
   - 预估: 8-10 小时

3. **Phase 1.2.3**: 提取 statement_handlers.py
   - 移动语句 handler
   - 预估: 6-8 小时

4. **Phase 1.2.4**: 提取 assignment_handlers.py
   - 移动赋值相关逻辑 (658-919 行区域)
   - 预估: 8-10 小时

5. **Phase 1.2.5**: 提取 control_flow_handlers.py
   - 移动 For, Try, LLMExcept handler
   - **特别注意**: 这些是最复杂的 handler，需要额外测试
   - 预估: 12-15 小时

6. **Phase 1.2.6**: 提取 callable_handlers.py 和 helpers.py
   - 移动调用相关逻辑
   - 提取辅助函数
   - 预估: 8-10 小时

7. **Phase 1.2.7**: 更新所有导入和测试
   - 更新 interpreter.py 中的导入
   - 运行完整测试套件
   - 预估: 4-6 小时

**验证标准**:
- `pytest tests/runtime/ -v` 全部通过
- `pytest tests/e2e/ -v` 全部通过
- 性能测试无明显退化

**预估工作量**: 50-60 小时

---

### 优先级 P1 - 高优先级

#### 任务 1.3: 拆分 `primitives.py` (1,328 行 → 5 个模块)

**当前状态**:
- 文件: `/core/kernel/axioms/primitives.py`
- 行数: 1,328 行
- 问题: 71 个公理类顺序定义，无语义分组

**拆分方案**:

```
core/kernel/axioms/
├── primitives.py               (保留为导出入口，50-100 行)
├── numeric_axioms.py           (新建 300-350 行)
│   ├── IntAxiom
│   ├── FloatAxiom
│   ├── ComplexAxiom
│   └── BoolAxiom
├── collection_axioms.py        (新建 350-400 行)
│   ├── ListAxiom
│   ├── TupleAxiom
│   ├── DictAxiom
│   └── SetAxiom
├── string_axiom.py             (新建 200-250 行)
│   └── StringAxiom (及相关辅助)
├── builtin_axioms.py           (新建 200-250 行)
│   ├── NoneAxiom
│   ├── ExceptionAxiom
│   └── 其他内置类型公理
└── behavior_axioms.py          (新建 150-200 行)
    ├── BehaviorAxiom
    └── FnCallableAxiom
```

**具体步骤**:

1. **Phase 1.3.1**: 创建模块结构
   - 创建 5 个新文件
   - 保留 primitives.py 作为重导出入口
   - 预估: 2-3 小时

2. **Phase 1.3.2**: 按类别移动公理类
   - 移动数值公理
   - 移动集合公理
   - 移动字符串公理
   - 移动内置公理
   - 移动行为公理
   - 预估: 10-12 小时

3. **Phase 1.3.3**: 提取通用模式
   - 创建 `SequenceAxiomMixin`
   - 创建 `MappingAxiomMixin`
   - 预估: 4-6 小时

4. **Phase 1.3.4**: 更新导入和测试
   - 更新 registry.py 中的导入
   - 验证所有公理仍可访问
   - 预估: 3-4 小时

**验证标准**:
- `pytest tests/ -k axiom -v` 全部通过
- 公理注册表完整性检查通过
- 类型推断行为无变化

**预估工作量**: 20-25 小时

---

#### 任务 1.4: 拆分 `llm_executor.py` (1,016 行 → 3-4 个模块)

**当前状态**:
- 文件: `/core/runtime/interpreter/llm_executor.py`
- 行数: 1,016 行
- 类: LLMExecutorImpl (994 行，36 个方法)

**拆分方案**:

```
core/runtime/interpreter/
├── llm_executor.py             (保留 300-400 行)
│   └── LLMExecutorImpl (核心编排)
├── llm_parser.py               (新建 300-350 行)
│   └── LLMResultParser (解析策略)
├── llm_type_inference.py       (新建 250-300 行)
│   └── LLMTypeInferencer (类型推断)
└── llm_segment_evaluator.py   (新建 200-250 行)
    └── SegmentEvaluator (段评估逻辑)
```

**具体步骤**:

1. **Phase 1.4.1**: 提取 LLMResultParser
   - 移动 `_parse_result` 及相关方法
   - 实现责任链模式简化回退逻辑
   - 预估: 10-12 小时

2. **Phase 1.4.2**: 提取 LLMTypeInferencer
   - 移动类型推断相关方法
   - 简化嵌套条件
   - 预估: 8-10 小时

3. **Phase 1.4.3**: 提取 SegmentEvaluator
   - 移动段评估逻辑
   - 预估: 6-8 小时

4. **Phase 1.4.4**: 重构主类为编排器
   - 保留核心 LLM 调用逻辑
   - 更新测试
   - 预估: 4-6 小时

**验证标准**:
- `pytest tests/runtime/test_llm*.py -v` 全部通过
- LLM mock 测试通过
- E2E LLM 测试通过

**预估工作量**: 30-35 小时

---

#### 任务 1.5: 拆分 `kernel.py` (objects, 1,160 行 → 3-4 个模块)

**当前状态**:
- 文件: `/core/runtime/objects/kernel.py`
- 行数: 1,160 行
- 问题: 职责过多（对象基类、函数、特殊值、辅助函数）

**拆分方案**:

```
core/runtime/objects/
├── kernel.py                   (保留 300-400 行)
│   ├── IbObject
│   ├── IbValue
│   └── IbClass
├── functions.py                (新建 350-400 行)
│   ├── IbFunction
│   ├── IbUserFunction
│   ├── IbLLMFunction
│   └── IbBoundMethod
├── special_values.py           (新建 150-200 行)
│   ├── IbNone
│   ├── IbLLMUncertain
│   └── 其他特殊值
└── helpers.py                  (新建 250-300 行)
    └── _should_activate_intent_context_arg (及其他辅助)
```

**具体步骤**:

1. **Phase 1.5.1**: 提取 functions.py
   - 移动所有函数相关类
   - 预估: 8-10 小时

2. **Phase 1.5.2**: 提取 special_values.py
   - 移动特殊值类型
   - 预估: 4-6 小时

3. **Phase 1.5.3**: 提取和简化 helpers.py
   - 移动辅助函数
   - **重点**: 简化 `_should_activate_intent_context_arg` (1,107 行)
   - 预估: 10-12 小时

4. **Phase 1.5.4**: 更新导入和测试
   - 更新循环导入处理
   - 预估: 4-6 小时

**验证标准**:
- `pytest tests/runtime/test_objects*.py -v` 全部通过
- 对象系统功能无退化

**预估工作量**: 26-34 小时

---

## 第二部分：深层嵌套逻辑优化计划

### 优先级 P0 - 立即执行

#### 任务 2.1: 简化 LLM 结果解析回退逻辑

**位置**: `/core/runtime/interpreter/llm_executor.py:366-478`

**当前问题**:
- 多重回退路径（Axiom → Parser → VTable → Default）
- 每个回退增加一层嵌套
- 异常处理分散

**重构方案**: 责任链模式

```python
# 新增: llm_parser.py
class ParsingStrategy:
    def can_handle(self, raw_res, descriptor):
        raise NotImplementedError

    def parse(self, raw_res, descriptor):
        raise NotImplementedError

class AxiomParsingStrategy(ParsingStrategy):
    def can_handle(self, raw_res, descriptor):
        return meta_reg.get_from_prompt_cap(descriptor) is not None

    def parse(self, raw_res, descriptor):
        from_prompt_cap = meta_reg.get_from_prompt_cap(descriptor)
        success, result = from_prompt_cap.from_prompt(raw_res, descriptor)
        return (success, result)

class ParserCapParsingStrategy(ParsingStrategy):
    # ...

class VTableParsingStrategy(ParsingStrategy):
    # ...

class LLMResultParser:
    def __init__(self):
        self.strategies = [
            AxiomParsingStrategy(),
            ParserCapParsingStrategy(),
            VTableParsingStrategy(),
            DefaultParsingStrategy()
        ]

    def parse_result(self, raw_res, descriptor):
        for strategy in self.strategies:
            if strategy.can_handle(raw_res, descriptor):
                try:
                    return strategy.parse(raw_res, descriptor)
                except Exception as e:
                    # 记录并继续下一个策略
                    continue
        return LLMResult.uncertain_result(...)
```

**步骤**:
1. 创建 ParsingStrategy 接口和实现类
2. 重构 `_parse_result` 使用责任链
3. 添加单元测试
4. 验证所有 LLM 测试通过

**预估工作量**: 12-15 小时

---

#### 任务 2.2: 提取 LLMEXCEPT 重试状态机

**位置**: `/core/runtime/vm/handlers.py:922-1015`

**当前问题**:
- 重试循环有多个退出条件（break, return, raise）
- 状态转换隐式且分散
- finally 块增加复杂度

**重构方案**: 状态机模式

```python
# 新增: llmexcept_state_machine.py
class LLMRetryState(Enum):
    INITIALIZED = "initialized"
    RETRYING = "retrying"
    SUCCESS = "success"
    EXHAUSTED = "exhausted"

class LLMRetryStateMachine:
    def __init__(self, frame, executor, max_retries):
        self.frame = frame
        self.executor = executor
        self.max_retries = max_retries
        self.state = LLMRetryState.INITIALIZED

    def should_continue(self):
        return self.state == LLMRetryState.RETRYING

    def process_result(self, result):
        if result is None or result.is_certain:
            self.state = LLMRetryState.SUCCESS
            return True

        if not self.frame.increment_retry():
            self.state = LLMRetryState.EXHAUSTED
            return False

        self.state = LLMRetryState.RETRYING
        return True

    def enter_retry(self):
        self.frame.restore_snapshot(self.executor.runtime_context)
        self.state = LLMRetryState.RETRYING

    def exit_with_error(self):
        error = self.executor.registry.make_llm_retry_exhausted_error(...)
        raise ThrownException(error)
```

**步骤**:
1. 创建状态机类
2. 重构 `vm_handle_IbLLMExcept` 使用状态机
3. 添加状态机单元测试
4. 验证 llmexcept 测试通过

**预估工作量**: 10-12 小时

---

#### 任务 2.3: 拆分 For 循环双路径逻辑

**位置**: `/core/runtime/vm/handlers.py:1589-1787`

**当前问题**:
- 200+ 行函数有两条完全不同的执行路径
- 条件驱动循环 vs. 标准 foreach
- 代码重复

**重构方案**: 策略模式

```python
# 新增: control_flow_handlers.py
class ForLoopStrategy:
    def execute(self, node_data, executor):
        raise NotImplementedError

class ConditionalForStrategy(ForLoopStrategy):
    """条件驱动循环: for (condition)"""
    def execute(self, node_data, executor):
        # 提取 100+ 行条件驱动逻辑
        pass

class ForeachStrategy(ForLoopStrategy):
    """标准 foreach: for item in iterable"""
    def execute(self, node_data, executor):
        # 提取 50+ 行 foreach 逻辑
        pass

def vm_handle_IbFor(node_data: Dict[str, Any], executor: "VMExecutor"):
    target_uid = node_data.get("target")

    if target_uid is None:
        strategy = ConditionalForStrategy()
    else:
        strategy = ForeachStrategy()

    return strategy.execute(node_data, executor)
```

**步骤**:
1. 创建 ForLoopStrategy 接口和实现
2. 提取条件驱动和 foreach 逻辑
3. 提取通用信号处理逻辑
4. 验证循环测试通过

**预估工作量**: 8-10 小时

---

### 优先级 P1 - 高优先级

#### 任务 2.4: 简化类型推断级联条件

**位置**: `/core/runtime/interpreter/llm_executor.py:440-459`

**重构方案**: 早期返回 + 提取方法

```python
def _infer_variable_type(self, var_name, declared_type, val_type, node, sym):
    """简化后的类型推断"""

    # 早期返回: 有声明类型的情况
    if declared_type:
        return self._infer_with_declared_type(declared_type, val_type, node)

    # 早期返回: 无声明类型的情况
    return self._infer_without_declared_type(var_name, val_type, node, sym)

def _infer_with_declared_type(self, declared_type, val_type, node):
    if val_type.name == "fn":
        return self._infer_fn_type(node, declared_type, val_type)

    if self.registry.is_dynamic(declared_type):
        if declared_type.name == "any":
            return self._any_desc
        return self._str_desc if self.registry.is_behavior(val_type) else val_type

    return declared_type

def _infer_without_declared_type(self, var_name, val_type, node, sym):
    spec_is_any = sym is not None and sym.spec is not None and sym.spec.name == "any"

    if not sym:
        return self._define_var(var_name, self._any_desc, node, allow_overwrite=False).spec

    if self.registry.is_dynamic(sym.spec or self._any_desc) and not spec_is_any:
        return self._define_var(var_name, val_type, node, allow_overwrite=True).spec

    return sym.spec
```

**预估工作量**: 6-8 小时

---

#### 任务 2.5-2.7: 其他嵌套逻辑优化

根据审计报告中识别的其他嵌套逻辑问题，按优先级处理：

- **任务 2.5**: 简化迭代器类型解析 (semantic_analyzer.py:1272-1365) - 6-8 小时
- **任务 2.6**: 简化可调用类型验证 (semantic_analyzer.py:1114-1163) - 4-6 小时
- **任务 2.7**: 简化 Try-except 处理 (handlers.py:1790-1895) - 6-8 小时

**总预估工作量**: 16-22 小时

---

## 第三部分：局部导入清理计划

### 优先级 P0 - 立即执行（无风险）

#### 任务 3.1: 清理标准库局部导入

**可安全移至顶层的导入**:

1. **ibci_net/core.py** - 10 处局部导入
   ```python
   # 当前: 在每个方法中
   def get(self, url):
       import requests
       import base64

   # 改为: 文件顶部
   import requests
   import base64
   ```

2. **ibci_json/core.py** - 1 处
   ```python
   # 移至顶部
   import copy
   ```

3. **ibci_sdk/check.py** - 1 处
   ```python
   # 移至顶部
   import sys
   ```

4. **tests/compiler/test_lexer.py** - 1 处
   ```python
   # 移至顶部
   from core.compiler.lexer.token_types import TokenType
   ```

5. **tests/compiler/test_type_annotations.py** - 1 处
   ```python
   # 移至顶部
   from core.kernel.spec.factory import SpecFactory
   ```

**步骤**:
1. 批量移动标准库导入到文件顶部
2. 运行对应模块测试
3. 提交

**预估工作量**: 2-3 小时

---

### 优先级 P1 - 优化冗余导入

#### 任务 3.2: 整合重复局部导入

**intent_context.py 中的重复导入**:

```python
# 当前: 在 4 个方法中重复
def method1(self):
    from core.runtime.interpreter.runtime_context import IntentNode
    # ...

def method2(self):
    from core.runtime.interpreter.runtime_context import IntentNode
    # ...

# 改为: 使用 TYPE_CHECKING guard
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.runtime.interpreter.runtime_context import IntentNode
```

**位置**:
- `/core/runtime/objects/intent_context.py` (第 85, 158, 207, 231 行)

**步骤**:
1. 添加 TYPE_CHECKING guard
2. 移除 4 个重复的局部导入
3. 运行测试验证

**预估工作量**: 1-2 小时

---

### 优先级 P2 - 文档化架构性导入（保持原样）

#### 任务 3.3: 为必要的局部导入添加注释

**保持局部导入但添加说明注释**:

```python
# interpreter.py:501
def _execute(self, ...):
    # 局部导入: 打破 interpreter ↔ vm_executor 循环依赖
    from core.runtime.vm.vm_executor import VMExecutor
    # ...

# kernel.py:905-907
def _initialize_builtins(self):
    # 局部导入: 打破 kernel ↔ builtins 循环依赖
    from core.runtime.objects.builtins import IbInteger, IbString
    # ...
```

**位置（需要添加注释）**:
- interpreter.py:501
- interpreter.py:464-467
- kernel.py:905-907
- kernel.py:997-999
- llm_executor.py 中的多个局部导入
- handlers.py 中的多个局部导入

**步骤**:
1. 为每个架构性局部导入添加注释
2. 说明为何必须局部导入（循环依赖）
3. 更新架构文档

**预估工作量**: 2-3 小时

---

## 第四部分：执行顺序与时间表

### Phase 1: 快速胜利（第 1-2 周）

**目标**: 完成所有 P0 任务，展示立即效果

- **Week 1**:
  - 任务 3.1: 清理标准库局部导入 (2-3 小时) ✓
  - 任务 2.1: 简化 LLM 结果解析 (12-15 小时) ✓
  - 开始任务 1.1: 拆分 semantic_analyzer.py

- **Week 2**:
  - 完成任务 1.1: 拆分 semantic_analyzer.py (40-50 小时)
  - 任务 2.2: LLMEXCEPT 状态机 (10-12 小时) ✓

**交付物**:
- 局部导入清理完成
- 2 个关键嵌套逻辑优化完成
- semantic_analyzer.py 拆分完成

---

### Phase 2: 核心重构（第 3-5 周）

**目标**: 完成最大的两个文件拆分

- **Week 3-4**:
  - 任务 1.2: 拆分 handlers.py (50-60 小时)

- **Week 5**:
  - 任务 2.3: 拆分 For 循环逻辑 (8-10 小时) ✓
  - 任务 3.2: 整合重复导入 (1-2 小时) ✓
  - 开始任务 1.3: 拆分 primitives.py

**交付物**:
- handlers.py 模块化完成
- For 循环逻辑优化完成
- 局部导入优化完成

---

### Phase 3: 补充重构（第 6-8 周）

**目标**: 完成剩余 P1 任务

- **Week 6**:
  - 完成任务 1.3: 拆分 primitives.py (20-25 小时)
  - 任务 2.4: 简化类型推断 (6-8 小时) ✓

- **Week 7**:
  - 任务 1.4: 拆分 llm_executor.py (30-35 小时)

- **Week 8**:
  - 任务 1.5: 拆分 kernel.py (26-34 小时)
  - 任务 2.5-2.7: 其他嵌套逻辑优化 (16-22 小时)
  - 任务 3.3: 文档化导入 (2-3 小时) ✓

**交付物**:
- 所有超大文件拆分完成
- 所有嵌套逻辑优化完成
- 导入策略文档化完成

---

## 第五部分：风险管理与验证策略

### 风险识别

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| 破坏现有功能 | 高 | 每步都运行完整测试套件 |
| 循环依赖引入 | 中 | 保持导入层次清晰，使用依赖图工具 |
| 性能退化 | 中 | 运行性能基准测试 |
| 测试覆盖率下降 | 低 | 在拆分前后测量覆盖率 |
| 合并冲突 | 中 | 小步提交，频繁合并 |

### 验证检查清单

**每个任务完成后必须执行**:

```bash
# 1. 运行对应模块测试
pytest tests/[module]/ -v

# 2. 运行完整测试套件
pytest tests/ -v --tb=short

# 3. 运行契约测试
pytest tests/contracts/ -v

# 4. 运行 E2E 测试
pytest tests/e2e/ -v

# 5. 检查代码覆盖率
pytest tests/ --cov=core --cov-report=term-missing

# 6. 运行类型检查（如果适用）
mypy core/ --ignore-missing-imports

# 7. 检查导入循环依赖
# 使用工具如 pydeps 或手动检查
```

### 回滚策略

- 每个任务在独立分支进行
- 保持小步提交（每 2-4 小时提交一次）
- 标记关键检查点以便回滚
- 发现严重问题立即停止，回退到最后稳定点

---

## 第六部分：成功指标

### 代码健康度指标

**拆分完成后的目标**:

| 指标 | 当前 | 目标 | 改进 |
|------|------|------|------|
| 文件 >1000 行 | 8 | 0 | -100% |
| 文件 >500 行 | 22 | <10 | -55% |
| 类 >500 行 | 15 | <5 | -67% |
| 函数 >100 行 | 26 | <15 | -42% |
| 最大嵌套深度 | 11 层 | <6 层 | -45% |
| 非必要局部导入 | 10 | 0 | -100% |

### 可维护性指标

- **模块内聚度**: 每个模块单一职责明确
- **模块耦合度**: 减少跨模块直接依赖
- **测试独立性**: 可以独立测试每个新模块
- **文档完整性**: 每个新模块有清晰的职责说明

### 开发体验指标

- **导航效率**: 找到特定功能的时间减少 50%
- **理解速度**: 新开发者理解模块的时间减少 40%
- **修改信心**: 修改代码的回归风险降低
- **测试速度**: 针对性测试运行时间减少

---

## 第七部分：后续维护建议

### 代码审查标准

**在 PR 模板中添加检查项**:

```markdown
## 代码健康度检查

- [ ] 新增/修改的文件不超过 400 行
- [ ] 新增/修改的类不超过 300 行
- [ ] 新增/修改的函数不超过 50 行
- [ ] 嵌套深度不超过 4 层
- [ ] 无不必要的局部导入（标准库、非循环依赖）
- [ ] 循环依赖的局部导入有注释说明
```

### CI/CD 集成

**添加自动检查**:

```yaml
# .github/workflows/code-health.yml
name: Code Health Check

on: [pull_request]

jobs:
  check-file-size:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Check file sizes
        run: |
          # 检查是否有文件超过 500 行
          find core/ -name "*.py" -exec wc -l {} \; | awk '$1 > 500 {print; exit 1}'

  check-complexity:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Check complexity
        run: |
          pip install radon
          radon cc core/ -n C  # 圈复杂度阈值
          radon mi core/ -n B  # 可维护性指数阈值
```

### 定期审计

**每季度执行**:
1. 运行代码度量工具
2. 识别新的超大文件/类
3. 更新重构计划
4. 回顾重构效果

---

## 附录 A：工具和命令

### 有用的分析命令

```bash
# 查找超大文件
find core/ -name "*.py" -exec wc -l {} \; | sort -rn | head -20

# 查找超大类
grep -r "^class " core/ | while read line; do
    file=$(echo $line | cut -d: -f1)
    class=$(echo $line | cut -d: -f2 | awk '{print $2}')
    # 计算类大小的逻辑
done

# 查找超大函数
grep -r "^def " core/ | while read line; do
    # 类似逻辑
done

# 查找局部导入
grep -r "^\s*import\|^\s*from.*import" core/ | grep -v "^[^:]*:[^:]*import"

# 检查循环依赖
pip install pydeps
pydeps core/ --show-deps
```

### 推荐工具

- **radon**: 代码复杂度分析
- **pylint**: 代码质量检查
- **pydeps**: 依赖关系可视化
- **coverage.py**: 代码覆盖率
- **pytest**: 测试框架

---

## 附录 B：参考文档更新清单

**需要同步更新的文档**:

1. **ARCHITECTURE_PRINCIPLES.md**
   - 更新模块结构图
   - 添加新的模块组织原则

2. **ARCH_DETAILS.md**
   - 更新语义分析器架构说明
   - 更新 VM handler 架构说明
   - 更新公理系统组织说明

3. **VM_AND_INTERPRETER_DESIGN.md**
   - 更新 handler 分派机制说明
   - 更新状态机模式说明

4. **NEXT_STEPS.md**
   - 添加重构计划链接
   - 标记受重构影响的任务

5. **COMPLETED.md**
   - 记录每个重构里程碑

---

**文档版本**: 1.0
**最后更新**: 2026-05-13
**下次审查**: 完成 Phase 1 后（预计 2026-05-27）
