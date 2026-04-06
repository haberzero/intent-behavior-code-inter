# IBC-Inter 待实现任务清单

> 本文档记录 IBC-Inter 项目中被搁置或标记为未来实现的任务。
> 每个任务都标注了搁置原因和解决方案方向。
> 采用加法标注模式。核心未完成任务置顶，历史任务标注状态。

---

## 🔴 优先级待办任务 (Priority Unfinished Tasks)

### 0.1 Mock 仿真引擎增强 (P0)
**状态**: `PENDING`
**问题**: 目前 `MOCK:FAIL/REPAIR/TRUE/FALSE` 前缀逻辑未在 `ibci_ai` 中实现，导致 `llmexcept` 无法进行自动化压力测试。
**涉及文件**: `ibci_modules/ibci_ai/core.py`

### 0.2 ai.set_retry() 配置穿透 (P1)
**状态**: `PENDING`
**问题**: `ai.set_retry()` 设置的次数被存储但从未读取，解释器内核 `_with_unified_fallback` 目前硬编码为 3 次。
**涉及文件**: `core/runtime/interpreter/interpreter.py`

### 0.3 vtable 参数签名提取 (P1)
**状态**: `PENDING`
**问题**: `discovery.py` 加载插件 vtable 时未提取 Python 函数签名，导致语义分析阶段无法校验参数数量。
**涉及文件**: `core/runtime/module_system/discovery.py`

---

#### 2.5 IBCI 核心路径解析能力增强 [COMPLETED]
**状态说明**: 此任务已通过 `ibci_sys` 模块及其 `sys.script_dir()` API 完整实现。
- **现状**: 废弃了 `__dir__` 裸调用，统一采用位置无关代码 (PIC) 标准。

**任务**：为 IBCI 语言和标准库提供“当前脚本目录”上下文。

**问题背景**：
- 目前 `ibci_file` 插件直接使用 Python 的 `open()`，路径解析依赖于进程的 `cwd`（通常是项目根目录）。
- 导致位于子目录的脚本（如 `test_target_proj/10_local_llm_test/complex_workflow.ibci`）若使用相对路径 `"system.log"`，文件会产生在根目录，造成污染。
- 脚本作者无法编写位置无关的文件操作代码。

**建议方案**：
1.  **内置变量**：在 `Interpreter` 中注入 `__file__` 或 `sys.script_dir` 内置变量。
2.  **插件增强**：修改 `ibci_file` 插件，允许其接受一个基准目录（Base Directory）参数，或者自动根据当前执行节点的模块路径进行解析。
3.  **规范化临时文件**：在 规范中明确建议脚本在完成验证后使用 `file.remove()` 自行清理临时文件。

## 一、动态宿主（DynamicHost）相关任务

### 1.1 Intent Stack 深拷贝实现 [RESOLVED]
**状态说明**: 此问题已在 中通过 **拓扑序列化 (Topology Serialization)** 彻底解决。
- **现状**: 引入了 `IntentNode` 链表池化技术，反序列化时通过 `intent_cache` 恢复物理引用关系，实现了内存级的结构共享，不再需要传统的递归深拷贝。

**任务**：实现 Intent Stack 的深拷贝机制，解决引用赋值问题

**搁置原因**：
- 当前阶段不继承任何意图栈
- Intent Stack 概念后续可能有大量需要澄清的要点
- 触发条件：`inherit_intents=True`

**技术细节**：
- 问题位置：`interpreter.py:80`
- 当前代码：`self.runtime_context.intent_stack = parent_context.intent_stack`（直接引用赋值）
- 架构要求：必须深拷贝

**解决方案方向**：
1. 确认 Intent Stack 不可变性设计
2. 实现 IntentNode 链表的深拷贝
3. 重新评估继承策略

---

### 1.2 子解释器插件注册 [PENDING]
**任务**：允许子解释器独立注册自己的插件

**搁置原因**：
- 用户决策：当前阶段不允许子解释器独立注册插件
- 所有插件应从主解释器继承

**当前实现**：
- `run_isolated()` 中通过 `inherit_plugins` 配置继承主解释器的插件
- 无代码路径允许子解释器独立注册新插件

**未来方案**：
1. 定义插件注册接口
2. 实现运行时插件加载机制
3. 添加隔离策略配置项

---

### 1.3 HOST 插件 breakpoint 接口 [PENDING]
**任务**：为 HOST 插件添加 breakpoint 相关接口

**搁置原因**：
- DynamicHost 现阶段最小目标不包含断点功能
- breakpoint = 现场保存/恢复/回溯能力，不是 GDB 式断点

**技术方案**：
- 定义 `breakpoint_set/breakpoint_clear/breakpoint_list` 接口
- 实现 backtrack 调用栈快照机制
- 需要先完成内核稳定工作

---

## 二、公理化相关任务

### 2.1 Intent 完整公理化 [VISION / FUTURE]
**任务**：创建 IntentAxiom、完善 RuntimeSerializer 序列化支持

**搁置原因**：
- 公理化相关工作全部暂缓
- Intent 公理化工作量预估 5-9 人天

**当前状态**：
- Intent 相关类型只是 DynamicAxiom 占位符
- 涉及文件：kernel/axioms/primitives.py, kernel/types/descriptors.py, runtime/serialization/runtime_serializer.py, runtime/objects/intent.py

**与MVP关系**：不影响MVP核心功能（behavior、llm、llmexcept、llmretry）

---

### 2.2 Behavior 完整公理化 [VISION / FUTURE]
**任务**：创建 BehaviorAxiom 替代 DynamicAxiom("behavior") 占位符

**搁置原因**：
- 公理化相关工作全部暂缓
- Behavior 公理化工作量预估 2-3 人天

**当前状态**：
- `DynamicAxiom("behavior")` 只是占位符

**与MVP关系**：不影响MVP核心功能

**未来演进 - LLM 接收模式 (Receive Mode)**：

**设计目标**：统一 LLM 函数和 behavior 表达式的结果消费语义，支持系统提示词注入。

**三种接收上下文**：
| 上下文 | 枚举值 | 语义 | 返回类型 |
|--------|--------|------|---------|
| 即时执行 | `IMMEDIATE` | behavior 表达式立即执行 LLM 调用 | `str` |
| 延迟执行 | `DEFERRED` | behavior 表达式被包装为 callable | `behavior` |
| 类转换 | `CLASS_CAST` | behavior 执行后进行类型转换 | 目标类型 |

**架构设计**：
```python
# 1. ReceiveMode 枚举
class ReceiveMode(Enum):
    IMMEDIATE = "immediate"   # 即时执行上下文
    DEFERRED = "deferred"     # 延迟执行上下文
    CLASS_CAST = "class_cast" # 类型转换上下文

# 2. SideTable 扩展
class SideTableManager:
    def get_receive_mode(self, node) -> ReceiveMode: ...
    def set_receive_mode(self, node, mode: ReceiveMode) -> None: ...

# 3. 公理扩展 - ParserCapability
class ParserCapability(Protocol):
    def parse_value(self, raw_value: str) -> Any: ...

    # [Future] 获取 LLM 调用时需要的系统提示词片段
    def get_llm_prompt_fragment(self) -> Optional[str]:
        """返回类型相关的提示词，如 '请仅返回一个整数' 或 None"""
        return None

# 4. 公理扩展 - TypeAxiom
class TypeAxiom:
    # [Future] 获取该类型返回值需要的提示词片段
    def get_return_type_hint(self) -> Optional[str]:
        """[LLM Integration] 获取类型特定的返回提示"""
        return None
```

**实施步骤**：
1. Phase 1: 引入 `ReceiveMode` 枚举，替代 `is_deferred` 布尔值
2. Phase 2: 扩展 `SideTable` 支持 `node_receive_mode`
3. Phase 3: 扩展 `ParserCapability.get_llm_prompt_fragment()`
4. Phase 4: 扩展 `TypeAxiom.get_return_type_hint()`
5. Phase 5: 在 `LLMExecutor` 中根据 `receive_mode` 注入不同系统提示词

### 2.5 ParserCapability LLM 提示词片段扩展

**任务**：扩展 `ParserCapability` 接口，添加 `get_llm_prompt_fragment()` 方法

---

### 二、架构与设计提案 [2026-03-27]

#### 2.1 意图系统对象化 (Intent-as-Object)

**任务**：将意图（Intent）从侧表绑定的元数据，转变为公理体系内的一级公民对象。

**设计目标**：
- 消除“侧表（Side Table）”作为意图存储的中间层，使意图直接作为 AST 节点和运行时对象存在。
- 在 `primitives.py` 中实现 `IntentAxiom`，定义意图类型的行为（如 `merge`, `resolve`, `is_active`）。
- 支持意图变量声明：`intent my_i = @~ "..." ~`。

**实施步骤**：
1. **Parser 层**：将 `@ "..."` 从语句装饰器扩展为独立的表达式节点 `IbIntentExpr`。
2. **Axiom 层**：在 `core/kernel/axioms/primitives.py` 中增加 `IntentAxiom` 实现。
3. **Semantic 层**：支持意图类型的类型检查与推导。
4. **Runtime 层**：统一 `IbIntent` 对象的协议，使其能直接参与运算。

**风险评估**：中等偏大。涉及编译器前端到后端的链路打通

---

#### 2.2 统一 LLM 语义失效信号

**任务**：将所有“LLM 无法满足语义要求”的场景统一通过 `LLMUncertaintyError` 抛出。

**设计目标**：
- 确保 `llmexcept` 能够捕获所有非预期的 LLM 行为。
- **覆盖范围扩展**：
  - 0/1 判定模糊（已实现）。
  - **类型转换失败**：当 `(list) str_val` 无法解析出 JSON 时抛出（已实现，基于 `FuzzyJsonParser`）。
  - **结构化解析失败**：当 `FuzzyJsonParser` 无法在文本中定位到任何有效结构时抛出。

**与 MVP 关系**：极大增强 `llmexcept/retry` 机制的实用价值。

---

#### 2.3 动态类型与 auto 类型推导增强

**任务**：改进 `auto` 关键字的类型推导机制，支持“渐进式强类型”。

- 目前 `auto` 仅在首次赋值时通过侧表（Side Table）绑定类型描述符。
- 目标是实现更智能的流敏感分析（Flow-sensitive Analysis）。

1. **类型松绑**：允许 `auto` 变量在特定条件下重新推导类型。
2. **Union 类型支持**：在编译期为 `auto` 生成 `Union` 描述符。
3. **运行时动态检查**：将类型检查压力部分从编译期移向运行期（针对 `auto`）。

---

#### 2.4 意图插值语法的一等公民化

**任务**：允许 `@~ ... ~` 在任何表达式上下文中使用，而非仅作为语句装饰器或特定的 `IbBehaviorExpr`。

**设计目标**：
- 支持 `str my_prompt = @~ "Current user is $user" ~`。
- 解决目前插值逻辑在 `LLMExecutor` 中重复实现的问题。
- 统一 `ext_ref`（外部资产）的解析链路。

---

## 三、类型系统相关任务**设计目标**：
- 当 LLM 函数的返回值类型被指向某个类时，声明"如何注入系统提示词"
- 替代当前 AIPlugin 中硬编码的 `_return_type_prompts`

**接口设计**：
```python
class ParserCapability(Protocol):
    """解析能力：描述一个类型如何从 LLM 结果中解析出值"""
    def parse_value(self, raw_value: str) -> Any: ...

    # [Future] 获取该类型参与 LLM 调用时需要的系统提示词片段
    def get_llm_prompt_fragment(self) -> Optional[str]:
        """返回类型相关的提示词，如 '请仅返回一个整数作为回答，禁止包含任何其他解释文字。'"""
        return None
```

**与 AIPlugin 的关系**：
- AIPlugin 中的 `_return_type_prompts` 作为 fallback 实现
- 公理层提供类型特定的提示词声明
- 运行时在 `LLMExecutor` 中查询公理获取提示词片段

**实施位置**：
- `core/kernel/axioms/protocols.py` - 添加方法到 `ParserCapability`
- `core/kernel/axioms/primitives.py` - 实现各原子类型的 `get_llm_prompt_fragment()`
- `core/runtime/interpreter/llm_executor.py` - 调用公理获取提示词片段

---

### 2.3 Intent Stack 不可变性约束

**任务**：实现 Intent Stack 不可变性约束

**搁置原因**：
- 依赖 Intent 公理化完成
- Intent Stack 概念后续可能还有大量需要澄清的要点

---

### 2.4 符号同步深拷贝

**任务**：修复 `_sync_variables_from()` 直接传递 symbol 引用的问题

**搁置原因**：
- 变量继承已禁用
- 当前不影响核心功能

**技术细节**：
- 问题位置：`interpreter.py:93-99`
- `_sync_variables_from()` 直接传递 symbol 引用

---

## 三、类型系统相关任务

### 3.1 禁止 auto 向明确类型隐式赋值

**任务**：实现 auto 类型约束机制，禁止 auto 向明确类型隐式赋值

**搁置原因**：
- 最低优先级
- 允许现在的瑕疵

**技术方案**：
- 在类型检查阶段加强约束
- 需要修改语义分析器

---

### 3.2 ib_type_mapping 完善

**任务**：完善 `runtime/objects/ib_type_mapping.py` 的类型映射实现

**搁置原因**：
- 当前只是一个极简存根，无实际类型注册
- 不影响核心功能，优先级低

**当前状态**：
- `_IB_TYPE_TO_CLASS` 是空字典
- 没有实际类型注册

---

## 四、语法/功能相关任务

### 4.1 (str n) @~ ... ~ 语法完善

**任务**：验证并完善 callable 闭包参数传递语法

**搁置原因**：
- 手册中描述的语法需要确认是否完整实现
- 闭包参数传递机制需要更明确的设计

---

### 4.2 llmretry 后缀语法

**任务**：明确 llmretry 后缀的当前实现状态

**搁置原因**：
- 当前实现为声明式 llmexcept + retry
- 手册描述的单行后缀语法已被重构

---

## 五、其他未解决问题

### 5.0 审计新发现 P0 紧急问题 ⚠️ [2026-03-25 审计]

> 以下问题在本次审计中被发现，之前未被记录，必须在MVP之前确认或修复。

#### 5.0.1 llmexcept 机制设计缺陷 [FIXED]
**状态说明**: 已完成。`visit_IbIf/While/For` 均已使用 `_with_unified_fallback` 包装。

**问题**：`visit_IbIf/While/For` 没有使用 `_with_unified_fallback` 包装，异常捕获路径断裂

**影响**：
- llmexcept 块永远不会执行
- AI 判断模糊时程序会直接崩溃，而不是进入 except 分支
- **MVP 的 llmexcept/retry 核心亮点无法展示**

**涉及文件**：
- `core/runtime/interpreter/handlers/stmt_handler.py:132-143`

**解决方案方向**：
1. 修改 `visit_IbIf/While/For` 使用 `_with_unified_fallback` 包装 LLM 调用
2. 确保子节点抛出的 `LLMUncertaintyError` 能被父节点 llmexcept 捕获

**与MVP关系**：🔴 **直接影响MVP核心亮点，必须修复**

---

#### 5.0.2 Mock 机制 MOCK:FAIL/REPAIR 未实现 [PENDING - P0]
**状态**: 见顶部 0.1 章节。

**问题**：文档声称的 `MOCK:TRUE/FALSE/FAIL/REPAIR` 前缀检测**完全不存在**，TESTONLY 模式总是返回 "1"

**影响**：
- 无法模拟 AI 判断模糊的场景
- **llmexcept/retry 测试无法进行**

**涉及文件**：
- `ibci_modules/ibci_ai/core.py:165-184`

**解决方案方向**：
1. 实现 `MOCK:FAIL` - 触发 llmexcept
2. 实现 `MOCK:TRUE/FALSE` - 返回固定判定值
3. 实现 `MOCK:REPAIR` - 首次返回模糊值，重试后返回确定值

**与MVP关系**：🔴 **直接影响MVP测试验证，必须修复**

---

#### 5.0.3 意图标签解析缺失 ✅ [2026-03-26 已修复]

**状态**: 已实现 `#tag` 解析逻辑。
**文件**: `core/compiler/parser/components/statement.py`

---

#### 5.0.4 Symbol.Kind typo ✅ [2026-03-26 已修复]

**状态**: 已修正为 `SymbolKind.VARIABLE`。
**文件**: `core/compiler/semantic/passes/scope_manager.py:44`

---

#### 5.0.5 OVERRIDE 意图内容丢失 🔴 P1 ✅ 已修复

**问题**：`@!` 修饰的意图内容不会被注入到 prompt

**涉及文件**：
- `core/kernel/intent_resolver.py:46-48`

**解决方案方向**：修复 intent_resolver 确保 `@!` 内容被正确追加

**修复内容**：
- 添加 `override_content` 变量跟踪排他意图内容
- 在遇到 `@!` 时清空 `resolved_block_intents` 并只保留 `@!` 的内容
- 修复后 `@!` 行为：屏蔽意图栈，只应用 `@!` 本身的内容（一次性调用，不影响栈状态）

**与MVP关系**：🟡 **属于语义正确性问题**

---

#### 5.0.6 ai.set_retry() 功能未实现 🔴 P1

**问题**：重试次数配置被存储但从未读取，硬编码为 3

**涉及文件**：
- `ibci_modules/ibci_ai/core.py:86-87`
- `core/runtime/interpreter/interpreter.py`

**解决方案方向**：让 `_with_unified_fallback` 读取配置的重试次数

**与MVP关系**：🟡 **用户无法配置重试次数，但有默认值可工作**

---

### 5.2 LLM 输出持久化

**任务**：AI 插件需支持文件保存 LLM 输出

**搁置原因**：
- 与 IssueTracker 持久化机制配合
- 属于扩展性功能

**技术方案**：
- AI 插件添加 save_output 方法
- 通过 file 插件进行显式文件写入

---

### 5.3 子解释器变量深拷贝隔离

**任务**：实现 `RuntimeContext.inject_variable()` 方法

**搁置原因**：
- 变量继承已禁用，无需实现
- `inherit_variables=False` 时不触发

---

## 六、已明确排除的设计

以下设计被明确排除，不需要实现：

| 排除项 | 理由 |
|--------|------|
| 进程级隔离 | 实例级隔离已足够 |
| 核心级 IPC | 通过外部 file 插件实现 |
| GDB 式断点 | DynamicHost 断点是现场保存/恢复/回溯 |
| hot_reload_pools | 违反解释器不修改代码原则 |
| generate_and_run | 动态生成IBCI应由显式的IBCI生成器进行 |

---

## 七、ImmutableArtifact 补充

### 7.1 添加 __deepcopy__ 方法

**任务**：为 ImmutableArtifact 添加 `__deepcopy__` 方法

**搁置原因**：
- 当前深拷贝行为可接受
- 不影响当前核心功能

**技术方案**：
```python
def __deepcopy__(self, memo):
    return self  # 不可变对象，深拷贝返回自身即可
```

---

## 八、MetadataRegistry 双轨问题

### 8.1 统一注册表管理

**任务**：解决 MetadataRegistry 双轨并行问题

**搁置原因**：
- 当前轻微问题
- 不影响核心功能

**技术细节**：
- `engine.py` 初始化 `KernelRegistry` 内的 `MetadataRegistry`
- `bootstrapper.py` 独立创建另一个 `MetadataRegistry`
- `HostInterface` 使用自己的 `MetadataRegistry` 实例

**未来方案**：
1. 统一 MetadataRegistry 实例管理
2. 消除多实例并行现象
3. 确保内置类型元数据一致性

---

## 九、插件系统扩展

### 9.1 零侵入插件注册原生 IBC-Inter 类型

**任务**：让零侵入插件能够注册原生 IBC-Inter 类型（如 float、int），而不需要继承任何核心类

**状态更新**：[2026-03-25 审计修订]
- ✅ [2026-03] `discovery.py` 中实现 `__ibcext_vtable__()` 加载逻辑
- ⚠️ 但 vtable 参数签名提取**未实现**（见 9.5）

**技术实现**：
```python
# core/runtime/module_system/discovery.py _load_spec()
# 1. 加载 __ibcext_metadata__() → 注册 ModuleMetadata
# 2. 加载 __ibcext_vtable__() → 将 Callable 转换为 FunctionMetadata 注册到 members
if hasattr(mod, '__ibcext_vtable__'):
    vtable = mod.__ibcext_vtable__()
    for method_name, method_impl in vtable.items():
        func_meta = FunctionMetadata(name=method_name, ...)
        metadata.members[method_name] = func_meta
```

**意义**：
- 遵循 协议（`__ibcext_vtable__()` 是协议的一部分）
- 使插件方法在语义分析阶段可见（解决 `Type 'ai' has no member 'set_config'` 问题）
- 为未来"插件原生类参与语义检查"奠定基础

**未来演进**：
- 支持 `__ibcext_vtable__()` 返回 `TypeDescriptor` 而非仅 `Callable`
- loader 识别 `TypeDescriptor` 并调用 `registry.register()`
- 类型行为由 `Axiom` 定义（像 float 一样）

---

### 9.2 显式引入原则 (Explicit Import Principle)

**任务**：重构插件注册机制，严格遵循"必须显式 import 才能使用"原则

**设计原则**：
- 插件必须显式 `import` 才能在 IBCI 代码中可见
- 不应该有隐式的全局插件注册
- 以前：`import ai` 只意味着"导入了一个名为 ai 的组件，里面有一些可用函数"
- 未来：`import ai` 应该是"导入了一个名为 ai 的原生类型"

**当前问题**：
- `discover_all()` 在 `Engine.__init__()` 时无条件调用
- 所有 ibc_modules 下的模块元数据被注册到 MetadataRegistry
- `Prelude._init_defaults()` 从 MetadataRegistry 自动加载所有模块到 `builtin_modules`
- 导致 `import ai` 前 `ai` 就已经是内置符号，违反显式引入原则

**临时方案（当前）**：
- 接受插件元数据在 Engine 初始化时注册（用于静态类型检查）
- 但区分"METHOD 模块"和"原生类型模块"
- 通过 metadata 标记模块类型：
  ```python
  # _spec.py
  def __ibcext_metadata__() -> Dict[str, Any]:
      return {
          "name": "ai",
          "version": "0.0.1",
          "kind": "method_module",  # 标记为方法模块，不是类型模块
          ...
      }
  ```

**长期方案（演进目标）**：
1. 延迟 `discover_all()` 调用
   - 不在 Engine 初始化时调用
   - 改为首次 import 或显式调用时触发
2. 明确内置模块列表
   - 只将真正的内置模块（sys, time 等）放入 `builtin_modules`
   - 其他插件模块必须显式 import
3. 支持"方法模块"和"类型模块"两种注册方式
   - 方法模块：通过 `import` 导入，提供函数调用
   - 类型模块：通过 `import` 导入，提供原生 IBC-Inter 类型

**实施步骤**：
1. Phase 1: 在 metadata 中添加 `kind` 字段区分模块类型
2. Phase 2: 修改 `Prelude._init_defaults()` 只加载类型模块
3. Phase 3: 修改 Scheduler 符号注入逻辑，标记外部模块符号
4. Phase 4: 延迟 discover_all() 到首次 import 时

---

### 9.3 模块符号去重机制

**任务**：解决外部模块符号与用户定义符号的冲突问题

**问题场景**：
```
用户代码:
import ai              # Scheduler 注入 MODULE 符号 "ai"
class ai:             # Pass 1 尝试收集 CLASS 符号 "ai"
    pass              # 冲突! symbol_table["ai"] 已存在
```

**根因**：
- `import ai` 在 Pass 1 之前注入 MODULE 符号
- 用户代码 `class ai` 在 Pass 1 中收集 CLASS 符号
- 两者在同一符号表中定义同一名称

**临时方案**：
- 在符号表中区分 MODULE 符号和 CLASS 符号
- 允许同名但不同 kind 的符号共存
- 或者：在注入 import 符号时检查是否已存在用户定义的同名符号

**长期方案**：
- 严格遵循显式引入原则
- 外部模块符号不预注入到编译时符号表
- 只在运行时通过 InterOp 访问

---

---

### 9.4 多值返回与 Tuple 类型系统

**任务**：实现 `return a, b, c` 多值返回语法和 tuple 类型系统

**问题场景**：
```
用户期望：
    def foo():
        return 1, "hello", [1, 2, 3]
    a, b, c = foo()
    # 或
    result = foo()  # result 是 tuple
```

**当前状态**：
| 层级 | 状态 | 问题 |
|------|------|------|
| 语法解析 | ✅ | `return a, b` 被解析为 `IbTuple` |
| AST 定义 | ✅ | `IbTuple(elts, ctx)` 定义完整 |
| 语义分析 | ❌ | 无 `visit_IbTuple`，编译错误 |
| 运行时执行 | ❌ | 无 `visit_IbTuple`，执行崩溃 |
| 类型系统 | ❌ | 无 `TupleType`/`TupleMetadata` |

**技术缺口**：
1. `IbTuple` 在语义分析阶段没有 `visit_IbTuple` 方法处理
2. `expr_handler.py` 没有 `visit_IbTuple` 运行时处理器
3. 类型系统缺少 `TupleType` 元数据类型描述符
4. Python tuple 返回时无法正确拆包到 IBC tuple

**影响文件**（预估 7-8 个）：
- `core/kernel/types/descriptors.py` - 添加 TupleMetadata
- `core/kernel/axioms/primitives.py` - 添加 TupleAxiom
- `core/compiler/semantic/passes/semantic_analyzer.py` - 添加 visit_IbTuple
- `core/runtime/objects/` - 添加 IbTuple 运行时对象
- `core/runtime/interpreter/handlers/expr_handler.py` - 添加 visit_IbTuple
- `core/compiler/semantic/passes/semantic_analyzer.py` - tuple 拆包赋值逻辑

**实施步骤**：
1. Phase 1: 添加 `TupleMetadata` 类型描述符
2. Phase 2: 实现 `visit_IbTuple` 语义分析
3. Phase 3: 实现 `IbTuple` 运行时对象和 `visit_IbTuple`
4. Phase 4: 实现 tuple 拆包多重赋值

**优先级**：中等（不影响核心编译流程）

---

### 9.5 vtable 参数签名提取

**任务**：修复 discovery.py 加载 vtable 时未提取 Python 函数签名信息的问题

**问题场景**：
```
用户调用插件方法时：
    ai.set_config("url", "key", "model")
    
语义分析阶段：
    ❌ 无法校验参数数量（param_types 为空列表）
    
运行时阶段（loader.py:117-118）：
    ❌ 比较 Python 实现的参数数量 vs spec_desc.param_types（空列表）
    ❌ 比较无意义，签名校验失效
```

**根因**：
discovery.py 第 145-149 行创建 FunctionMetadata 时只传递了 name 和 module_path：
```python
func_meta = FunctionMetadata(
    name=method_name,
    module_path=module_name,
    members={}
    # param_types = [] ← 空列表
)
```

**解决方案**：
在 vtable 加载时使用 `inspect.signature()` 提取 Python 函数的参数类型：
```python
import inspect
sig = inspect.signature(method_impl)
param_types = [self._type_from_python(p.annotation) for p in sig.parameters.values() if p.name != 'self']
```

**影响文件**：
- `core/runtime/module_system/discovery.py` - 添加签名提取逻辑
- `core/runtime/module_system/loader.py` - 修复 param_types 比较逻辑

**优先级**：高（影响插件方法调用校验）

---

*本文档为 IBC-Inter 待实现任务清单，供未来智能体和开发者参考。*
