# IBC-Inter 待实现任务清单

> 本文档记录 IBC-Inter 项目中被搁置或标记为未来实现的任务。
> 每个任务都标注了搁置原因和解决方案方向。
> 采用加法标注模式。核心待完成任务置顶，历史任务标注状态。
>
> **最后更新**：2026-04-18（更新 §11.9 OOP×Protocol 边界清理 PR-A 已完成）

---

## 优先级待办任务（已完成的历史条目）

| 条目 | 状态 | 详见 |
|------|------|------|
| 0.1 Mock 仿真引擎增强 | ✅ COMPLETED | ARCH_DETAILS.md 第三章 |
| 0.2 ai.set_retry() 配置穿透 | ✅ COMPLETED | ARCH_DETAILS.md 第一章 1.5 节 |
| 0.3 vtable 参数签名提取 | ✅ COMPLETED | `discovery.py` `_extract_signature()` |
| 2.5 IBCI 核心路径解析 | ✅ COMPLETED | `ibci_sys` 模块，`sys.script_dir()` API |

---

## 一、动态宿主（DynamicHost）相关任务

### 1.1 Intent Stack 深拷贝实现 [RESOLVED]
**状态**：已通过 **拓扑序列化** 彻底解决。`IntentNode` 链表池化 + `intent_cache` 恢复物理引用，实现内存级结构共享。

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
- 涉及文件：`kernel/axioms/primitives.py`、`runtime/objects/intent.py`

**与MVP关系**：不影响MVP核心功能（behavior、llm、llmexcept、llmretry）

---

### 2.2 Behavior 完整公理化 [COMPLETED ✅]

**状态**：已完整实现（PR: copilot/ibc-inter-design-review + copilot/check-architecture-and-documentation）。

**已完成内容**：
- `BehaviorAxiom` 替换 `DynamicAxiom("behavior")`，`is_dynamic()=False`
- `BehaviorCallCapability` 提供 `get_call_capability()`，返回类型为 `"auto"`（编译期延迟）
- `IbBehavior.call()` 通过 `registry.get_llm_executor().invoke_behavior()` 自主执行
- `_execute_behavior()` 旁路从 `BaseHandler` 彻底删除
- `IILLMExecutor` 接口定义于 `core/base/interfaces.py`
- `KernelRegistry.register_llm_executor()` / `get_llm_executor()` 完整注入链路
- **`BehaviorSpec(value_type_name=...)` 编译期返回类型推断**：`int lambda f = @~...~; int result = f()` 编译期不产生 SEM_003。`SpecRegistry.resolve_return()` 对 DeferredSpec/BehaviorSpec 直接推断 value_type_name。（PR: copilot/check-architecture-and-documentation）

详见 `AXIOM_OOP_ANALYSIS.md` Step 1 + Step 2 + §6.4。

### 2.5 ParserCapability LLM 提示词片段扩展

**任务**：扩展 `ParserCapability` 接口，添加 `get_llm_prompt_fragment()` 方法，替代 AIPlugin 中硬编码的 `_return_type_prompts`。

**实施位置**：`core/kernel/axioms/protocols.py`、`core/kernel/axioms/primitives.py`、`core/runtime/interpreter/llm_executor.py`

---

### 2.3 Intent Stack 不可变性约束

**任务**：实现 Intent Stack 不可变性约束

**搁置原因**：依赖 Intent 公理化完成；Intent Stack 概念后续可能还有大量需要澄清的要点。

---

### 2.4 符号同步深拷贝

**任务**：修复 `_sync_variables_from()` 直接传递 symbol 引用的问题

**搁置原因**：变量继承已禁用，当前不影响核心功能。问题位置：`interpreter.py:93-99`

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

### 5.0 审计新发现 P0 紧急问题 ⚠️ [2026-03-25 审计] — 全部已解决

| 条目 | 状态 | 详见 |
|------|------|------|
| 5.0.1 llmexcept 机制设计缺陷 | ✅ COMPLETED | ARCH_DETAILS.md 第一章（影子执行驱动模式） |
| 5.0.2 Mock MOCK:FAIL/REPAIR 未实现 | ✅ COMPLETED | ARCH_DETAILS.md 第三章 |
| 5.0.3 意图标签解析缺失 | ✅ 已修复 | `parser/components/statement.py` |
| 5.0.4 Symbol.Kind typo | ✅ 已修复 | `scope_manager.py:44` |
| 5.0.5 OVERRIDE 意图内容丢失 | ✅ 已修复 | `intent_resolver.py:46-48`（`override_content` 变量） |
| 5.0.6 ai.set_retry() 未实现 | ✅ COMPLETED | ARCH_DETAILS.md 第一章 1.5 节 |

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

**任务**：让零侵入插件能够注册原生 IBC-Inter 类型，而不需要继承任何核心类

**当前状态**：
- ✅ `discovery.py` 已实现 `__ibcext_vtable__()` 加载逻辑，将 callable 条目转换为 `MethodMemberSpec` 并注册到 `ModuleSpec.members`
- ✅ 参数签名自动提取（`_extract_signature()` via `inspect.signature()`）已实现（见 0.3/9.5）
- `__ibcext_vtable__()` 支持两种格式：`callable` 直接传入（自动提取签名）或 `{"param_types": [...], "return_type": "..."}` 字典格式

**意义**：使插件方法在语义分析阶段可见，遵循 `__ibcext_vtable__()` 扩展协议。

**未来演进**：支持 `__ibcext_vtable__()` 返回完整 `IbSpec` 对象直接注册，允许插件原生类型参与公理体系（类型行为由 `Axiom` 定义）。

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

### 9.4 多值返回与 Tuple 类型系统 [COMPLETED]

**状态**: ✅ 已完整实现。详见 ARCH_DETAILS.md 第五章。

---

### 9.5 vtable 参数签名提取 [COMPLETED]

**状态**: ✅ 已完整实现。见 0.3 条目及 `discovery.py` `_extract_signature()`。

---

## 十、llmexcept / retry 机制后续改进

基础实现已完成（影子执行驱动模式，详见 ARCH_DETAILS.md 第一章）。以下为仍待完善的方向。

### 10.1 Loop 上下文完整恢复 (P1) [PENDING]

**问题**: 当前 `LLMExceptFrame` 保存了 `_loop_stack` 的列表副本（浅拷贝），但循环迭代器状态（`for item in list` 中当前迭代位置）未被完整恢复。重试后循环会从头开始而不是从失败点之前的状态继续。

**涉及文件**: `core/runtime/interpreter/llm_except_frame.py`

### 10.2 重试策略配置 (P1) [PENDING]

**当前状态**: 只支持固定次数重试（`ai.set_retry(n)`）。

**待完善**:
- 指数退避（Exponential Backoff）
- 固定延迟（Fixed Delay）
- 条件重试（基于错误类型）

### 10.3 嵌套 llmexcept 完善 (P1) [PENDING]

**当前状态**: `LLMExceptFrameStack` 已支持多层嵌套帧的压栈/弹栈，但嵌套场景下的作用域隔离和帧交互未经过系统性测试。

### 10.4 重试诊断日志 (P1) [COMPLETED]

**已实现**：在 `stmt_handler.py` 的 `visit_IbLLMExceptionalStmt` 重试循环中新增 4 处 `self.debugger.trace()` 调用：

- **DETAIL**：进入 llmexcept 帧时输出 `target_uid` 和 `max_retry`
- **DETAIL**：每次 while 循环迭代开始时输出当前尝试编号（`attempt N/M`）
- **DETAIL**：正常退出（LLM 结果确定）时输出成功信息
- **BASIC**：LLM 返回 UNCERTAIN 时输出原始响应预览（前 60 字符）
- **BASIC**：重试次数耗尽时输出 max_retry 和 target_uid

日志在 `CoreModule.INTERPRETER` 调试频道输出，只在对应级别启用时可见，不影响生产运行。

### 10.5 技术债务清理 (P2) [COMPLETED]

- `collector.py:200`：✅ 已删除 `"llm_fallback"` 无效属性遍历。
- `runtime_context.py`：✅ 5 处 `TODO [优先级: 高]: 完成后移除此注释` 已全部清理。
- `interop.py:7`：✅ 已将疑惑性 TODO 替换为解释性注释（Protocol 继承在 Python typing 体系中是合法的）。

---

## 十一、代码健康分析（2026-04-17 深度审计）

本章记录在 2026-04-17 深度健康分析中发现的问题，包括历史包袱、tricky 操作、补丁式修复和暂时性妥协。

### 11.1 IbTuple 未纳入快照/序列化体系 (P1) [COMPLETED]

**状态说明**：已修复。在两个关键路径中均补充了 IbTuple 支持：
- `llm_except_frame.py` 的 `_is_serializable()` 和 `_save_vars_snapshot()` 已将 IbTuple 与 IbList 并列处理
- `runtime_serializer.py` 的序列化路径（`_collect_instance()`）和反序列化路径（`_get_instance()`）均已添加 `"tuple"` 分支，并更新了导入

### 11.2 ibci_file 的 core 依赖与"非侵入"分类不符 (P2) ✅ 已修正（文档）

**问题**：`ibci_file/core.py` 导入 `from core.runtime.path import IbPath` 并使用 `capabilities.execution_context`，但文档将其归类为"非侵入式"插件（零内核依赖）。

**已修正**：`ibcext.py` 注释新增"轻量依赖型"例外说明，`ARCHITECTURE_PRINCIPLES.md` 插件表格拆分为三行（非侵入式 / 非侵入式轻量依赖 / 核心级），将 `ibci_file` 单独列出。`IbPath` 是纯数据类，无解释器状态依赖，属可接受的工具类导入。

### 11.3 调度器 import 注入中的多处 [临时方案] (P1) [COMPLETED]

**当前状态**：所有静默 `pass` 已替换为 `self.debugger.trace(CoreModule.SCHEDULER, DebugLevel.DETAIL/BASIC, ...)` 调用，调试模式下可见冲突信息。长期方案（严格遵循显式引入原则）仍在规划中，见 9.2 节。

**涉及文件**：`core/compiler/scheduler.py`（`_inject_plugin_symbols` 方法）

### 11.4 意图标签解析临时方案（parser 层）(P2) [PENDING]

**问题描述**：`statement.py:278` 有注释 `TODO 应该从lexer开始就提供支持。现在是临时方案`。当前 `#tag` 的解析使用 inline `import re` + 正则表达式在 parser 的字符串处理循环中完成，属于词法层的职责被推后到语法层处理。

**影响**：轻微的性能开销（多次 regex 调用），更主要的问题是 lexer 不感知 tag，导致 tag 语法在 token stream 中不可见，未来若需要对 tag 做语义分析（如检查 `@- #tag` 中的 tag 是否已定义）会比较困难。

**涉及文件**：`core/compiler/parser/components/statement.py`（约第 278-289 行）

### 11.5 behavior 对象延迟执行路径的 call_intent 传递 (P2) [COMPLETED]

**状态说明**：已修复。`IbBehavior` 增加了 `call_intent` 字段，`create_behavior()` 工厂方法（`factory.py`、`interfaces.py`）已更新签名，`expr_handler.py` 的延迟执行路径现在正确传入 `call_intent`。序列化/反序列化路径（`runtime_serializer.py`）也已同步更新，确保快照中 `call_intent` 不丢失。

### 11.6 engine.py 和 service.py 中的 vibe 妥协标注 (P3) [PENDING]

**问题描述**：多处被明确标注为"智能体快速 vibe 实现，未经严格审查"的代码片段：
- `engine.py:136`：强制向 service_context 回写 orchestrator，属于双向引用注入
- `service.py:173`：`host_run()` 内置函数的返回值被简化为布尔值 IbObject 封装，隐藏了实际执行结果
- `rt_scheduler.py:40-44`：`_resolve_builtin_path()` 使用 `ibci_modules.__file__` 动态发现内置模块路径
- `scheduler.py:81`：`compile_to_artifact_dict()` 方法本身是否合理存疑

这些点尚未引起实际 bug，但属于设计上的模糊区域，需要在某次审计中专门处理。

**涉及文件**：`core/engine.py`、`core/runtime/host/service.py`、`core/runtime/rt_scheduler.py`、`core/compiler/scheduler.py`

### 11.7 behavior 类型的语义分析硬编码检查 (P2) [COMPLETED]

**状态说明**：已修复。`semantic_analyzer.py` 的 `visit_IbFor` 中原有的两处字符串 `"behavior"` 直接比较：
```python
if not self.registry.is_dynamic(iter_type) and not (iter_type.name == "behavior") and iter_type.name != "bool":
if (iter_type.name == "behavior"):
```
现已全部改为 `self.registry.is_behavior(iter_type)`，通过 `SpecRegistry.is_behavior()` 方法进行判断，消除了硬编码。
对应方法 `SpecRegistry.is_behavior()` 已在 `core/kernel/spec/registry.py:331-335` 中实现。

### 11.8 instance_id 默认值为字符串 "main" (P3) [PENDING]

**问题描述**：`interpreter.py:108` 有 TODO 标注：`instance_id: str = "main"` 这一参数默认值可能导致多个解释器实例 ID 碰撞（若调用方未传入唯一 ID）。当前代码中 `self.instance_id = instance_id or f"inst_{id(self)}"` 提供了一定的 fallback 保护，但 `"main"` 作为默认值仍是潜在隐患。

**涉及文件**：`core/runtime/interpreter/interpreter.py`

### 11.9 OOP × Protocol 边界清理 (P1) [COMPLETED]

**状态说明**：已完整修复（PR-A）。

根本问题：`IIbObject` Protocol 中存在 `@property def descriptor` 幽灵字段，在 Python 3.12 的 `@runtime_checkable` 机制下，该字段导致 `IbObject` 无法结构满足 `IIibObject`，进而引发 `IbBehavior`/`IbIntent`/`AIPlugin` 等被迫显式继承 Protocol 类的补丁链条，以及 5 处 Protocol isinstance 调用、2 处死代码/遗留兼容检查。

**全部修复内容**：
- `core/runtime/interfaces.py`：删除 `IIibObject.descriptor` 幽灵字段
- `core/runtime/objects/builtins.py`：`IbBehavior(IbObject, IIibBehavior)` → `IbBehavior(IbObject)`
- `core/runtime/objects/intent.py`：`IbIntent(IbObject, IntentProtocol)` → `IbIntent(IbObject)`
- `ibci_modules/ibci_ai/core.py`：`AIPlugin(ILLMProvider, IbStatefulPlugin)` → `AIPlugin(IbStatefulPlugin)`
- `stmt_handler.py`/`interpreter.py`/`service.py`/`llm_executor.py`：5 处 Protocol isinstance → 具体实现类 isinstance
- `llm_executor.py`：`_get_llmoutput_hint` 死代码路径修复为 `meta_reg.resolve(type_name)`
- `loader.py`：删除 `isinstance(context.llm_executor, ILLMExecutor)` 遗留兼容检查
- 6 处死 import 全部清理（`expr_handler.py`、`base_handler.py`、`runtime_context.py`、`ibci_idbg/core.py`）

---

*本文档为 IBC-Inter 待实现任务清单，供未来智能体和开发者参考。*
