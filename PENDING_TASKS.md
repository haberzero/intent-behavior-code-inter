# IBC-Inter 待实现任务清单

> 本文档记录 IBC-Inter 项目中被搁置或标记为未来实现的任务。
> 每个任务都标注了搁置原因和解决方案方向。
> 优先级低于 NEXT_STEPS_PLAN.md，可独立使用。
>
> **生成日期**：2026-03-21
> **版本**：V2.0

---

## 一、DynamicHost 相关任务

### 1.1 Intent Stack 深拷贝实现

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

### 1.2 子解释器插件注册

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

### 1.3 HOST 插件 breakpoint 接口

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

### 2.1 Intent 完整公理化

**任务**：创建 IntentAxiom、完善 RuntimeSerializer 序列化支持

**搁置原因**：
- 公理化相关工作全部暂缓
- Intent 公理化工作量预估 5-9 人天

**当前状态**：
- Intent 相关类型只是 DynamicAxiom 占位符
- 涉及文件：kernel/axioms/primitives.py, kernel/types/descriptors.py, runtime/serialization/runtime_serializer.py, runtime/objects/intent.py

---

### 2.2 Behavior 完整公理化

**任务**：创建 BehaviorAxiom 替代 DynamicAxiom("behavior") 占位符

**搁置原因**：
- 公理化相关工作全部暂缓
- Behavior 公理化工作量预估 2-3 人天

**当前状态**：
- `DynamicAxiom("behavior")` 只是占位符

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

### 3.1 禁止 var 向明确类型隐式赋值

**任务**：实现 var 类型约束机制，禁止 var 向明确类型隐式赋值

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

### 5.1 LLM 输出持久化

**任务**：AI 插件需支持文件保存 LLM 输出

**搁置原因**：
- 与 IssueTracker 持久化机制配合
- 属于扩展性功能

**技术方案**：
- AI 插件添加 save_output 方法
- 通过 file 插件进行显式文件写入

---

### 5.2 子解释器变量深拷贝隔离

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

## 九、IES 2.2 插件系统扩展

### 9.1 零侵入插件注册原生 IBC-Inter 类型

**任务**：让零侵入插件能够注册原生 IBC-Inter 类型（如 float、int），而不需要继承任何核心类

**搁置原因**：
- 当前 vtable 只支持返回 `Callable`（方法）
- 原生 IBC-Inter 类型（如 float）是通过 `Axiom` 定义的，不需要继承
- 核心级插件（AI/IDBG/HOST）目前需要继承是合理的，但理论上有更优雅的方案

**技术方案**：
1. 扩展 `__ibcext_vtable__()` 返回值类型，支持返回 `TypeDescriptor`
2. loader 识别 `TypeDescriptor` 并调用 `registry.register()`
3. 类型行为由 `Axiom` 定义（像 float 一样）

```python
# 零侵入插件示例
def __ibcext_vtable__():
    return {
        "my_type": my_type_descriptor,  # TypeDescriptor，不是 Callable
    }
```

```python
# loader.py 扩展
def _register_types_from_vtable(vtable):
    for name, item in vtable.items():
        if isinstance(item, TypeDescriptor):
            registry.register(name, item)
```

**意义**：
- 统一内置类型和插件类型的注册方式
- 进一步减少核心级插件的特殊性
- 插件可以像 float 一样声明自己的"类型身份"

---

*本文档为 IBC-Inter 待实现任务清单，供未来智能体和开发者参考。*
