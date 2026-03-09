# IBCI 2.0 架构与实现深度审计报告 (v2.0 阶段)

## 1. 概述
本报告对 IBCI 2.0 “动态宿主”重构后的核心代码进行了全面审计。审计范围涵盖：解释器内核、对象模型、序列化引擎及协调器模式实现。报告旨在识别当前系统中的重大缺陷、安全风险及架构债，为后续修复与优化提供指导。

---

## 2. 核心缺陷与重大 BUG (Critical Issues)

### 2.1 序列化逻辑覆盖 BUG
- **位置**：[runtime_serializer.py](file:///c:/myself/proj/intent-behavior-code-inter/core/runtime/serialization/runtime_serializer.py#L188)
- **描述**：`RuntimeDeserializer` 类中连续定义了两次 `deserialize_context` 方法。
- **后果**：
    - 后一个定义（L188）覆盖了前一个（L163）。
    - 前一个定义中包含的 **意图栈恢复 (Intent Stack)**、**全局意图恢复** 以及 **作用域链深度重建** 的关键代码被完全废弃。
    - 在恢复快照后，AI 代理的上下文感知能力将降级，且作用域链可能出现断裂。
- **修复建议**：立即合并两个方法，确保所有状态字段（包括意图、作用域、池数据）在单一入口内完整恢复。

### 2.2 原生对象属性泄露 (安全沙箱穿透)
- **位置**：[kernel.py](file:///c:/myself/proj/intent-behavior-code-inter/core/runtime/objects/kernel.py#L119-120)
- **描述**：`IbNativeObject.receive` 在虚函数表（VTable）未命中时，会回退到执行 `getattr(self.py_obj, target_name)`。
- **风险**：
    - 允许 IBCI 脚本访问底层 Python 对象的私有属性（如 `__class__`, `__subclasses__`）。
    - 恶意脚本可能借此执行任意 Python 代码或逃逸沙箱。
- **修复建议**：移除默认的 `getattr` 穿透。引入显式的 **属性白名单 (Attribute Whitelist)** 机制，仅允许访问插件明确暴露的属性。

---

## 3. 架构性缺陷与技术债 (Architectural Debt)

### 3.1 模块导入权限缺失
- **位置**：[interpreter.py](file:///c:/myself/proj/intent-behavior-code-inter/core/runtime/interpreter/interpreter.py#L942)
- **描述**：`visit_IbImport` 直接调用 `module_manager.import_module`。
- **缺陷**：虽然系统初始化了 `PermissionManager`，但在 `import` 的执行路径上并未强制执行权限校验。
- **后果**：子脚本理论上可以绕过父环境的限制，导入未授权的敏感模块。

### 3.2 反射分发性能瓶颈
- **位置**：[interpreter.py](file:///c:/myself/proj/intent-behavior-code-inter/core/runtime/interpreter/interpreter.py#L465)
- **描述**：`visit` 方法在每一步执行中都使用 `getattr(self, f"visit_{type}")` 进行动态分发。
- **优化建议**：将 `visit_` 方法预先映射到静态字典中，避免运行时的字符串拼接和反射开销。

### 3.3 异常匹配逻辑缺失
- **位置**：[interpreter.py](file:///c:/myself/proj/intent-behavior-code-inter/core/runtime/interpreter/interpreter.py#L920)
- **描述**：`visit_IbTry` 仍标记为 `TODO: 类型匹配检查`。
- **后果**：目前的 `except` 块会无差别捕获所有异常，无法根据异常类进行精细化分发。

---

## 4. 代码质量与规范性问题 (Code Quality)

### 4.1 局部导入滥用
- **位置**：[kernel.py](file:///c:/myself/proj/intent-behavior-code-inter/core/runtime/objects/kernel.py)
- **描述**：在 `IbObject` 和 `IbClass` 的核心方法内部大量使用 `from .kernel import IbBoundMethod`。
- **建议**：由于处于同一文件，应通过合理的初始化顺序或类型标识消除此类动态导入，减少函数调用开销。

### 4.2 逻辑重叠与冗余
- **位置**：[runtime_serializer.py](file:///c:/myself/proj/intent-behavior-code-inter/core/runtime/serialization/runtime_serializer.py#L139)
- **描述**：`_collect_instance` 对 `IbNativeFunction` 的逻辑标识处理与基类逻辑存在重叠。

### 4.3 序列化快照格式定义缺失
- **描述**：目前 JSON 快照的 UID 结构和 LogicID 映射关系完全依赖代码实现。
- **风险**：缺乏正式规范（如 JSON Schema），导致版本间的持久化数据难以保持长期兼容。

---

## 5. 深度审计补遗：架构与逻辑隐患 (v2.0 深度分析)

### 5.1 解释器递归陷阱 (Critical)
- **位置**：[interpreter.py](file:///c:/myself/proj/intent-behavior-code-inter/core/runtime/interpreter/interpreter.py)
- **描述**：`visit` 模式依赖 Python 原生调用栈。
- **后果**：面对深度嵌套或复杂 AI 生成逻辑时，易触发 `RecursionError` 导致解释器崩溃。
- **修复评估**：
    - **难度**：高。需重构为跳板循环（Trampoline Loop）模式。
    - **代价**：大。核心调度逻辑重写。
    - **风险**：高。可能破坏现有的状态恢复与异常分发流。

### 5.2 脆弱的 LLM 响应解析 (Major)
- **位置**：[llm_executor.py](file:///c:/myself/proj/intent-behavior-code-inter/core/runtime/interpreter/llm_executor.py)
- **描述**：过度依赖正则表达式从非结构化文本中提取 JSON。
- **后果**：AI 回答中的 Markdown 代码块或干扰性文字会导致解析失败。
- **修复评估**：
    - **难度**：中。需引入括号平衡算法或多级解析器。
    - **代价**：小。模块化程度高。
    - **风险**：低。

### 5.3 意图栈内存膨胀 (Major)
- **位置**：[runtime_context.py](file:///c:/myself/proj/intent-behavior-code-inter/core/runtime/interpreter/runtime_context.py), [builtins.py](file:///c:/myself/proj/intent-behavior-code-inter/core/runtime/objects/builtins.py)
- **描述**：Lambda 行为对象（IbBehavior）创建时采用暴力深拷贝意图栈。
- **后果**：长周期、高频交互下会导致内存线性增长，甚至 OOM。
- **修复评估**：
    - **难度**：中。需引入意图链表或结构共享机制。
    - **代价**：中。涉及上下文契约变更。
    - **风险**：中。

### 5.4 反序列化循环引用死锁 (Minor)
- **位置**：[runtime_serializer.py](file:///c:/myself/proj/intent-behavior-code-inter/core/runtime/serialization/runtime_serializer.py)
- **描述**：`IbBoundMethod` 等对象反序列化时未采用“创建与填充分离”模式。
- **后果**：复杂的对象引用图可能导致反序列化死循环。
- **修复评估**：
    - **难度**：低。统一采用延迟填充模式。
    - **代价**：极小。
    - **风险**：极低。

### 5.5 UID 碰撞风险 (Architectural Debt)
- **位置**：[serializer.py](file:///c:/myself/proj/intent-behavior-code-inter/core/compiler/serialization/serializer.py), [runtime_serializer.py](file:///c:/myself/proj/intent-behavior-code-inter/core/runtime/serialization/runtime_serializer.py)
- **描述**：8 位 Hex UID 空间有限。
- **后果**：大型项目或长周期运行下，UID 可能发生碰撞导致数据篡改。
- **修复评估**：
    - **难度**：低。升级 UID 长度。
    - **代价**：小。
    - **风险**：中（涉及快照兼容性）。

---

## 6. 结论与下一步行动

当前 IBCI 2.0 架构在**解耦性**上取得了重大进展，但在**实现的健壮性**和**安全性**上仍需补课。

**优先修复路径：**
1. **合并 `RuntimeDeserializer.deserialize_context`**，确保意图栈恢复。
2. **重构 `IbNativeObject`**，封死 `getattr` 漏洞。
3. **补齐 `visit_IbTry` 的类型匹配**。
4. **清理 `kernel.py` 的局部导入**。

---
*审计执行人：IBCI 核心协助代理*
*审计日期：2026-03-09*
