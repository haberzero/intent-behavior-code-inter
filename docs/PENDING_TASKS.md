# PENDING_TASKS（低优先级任务池）

> 本文档仅记录低优先级事项。  
> 高优先级类型系统主线不在此处维护，统一见 `docs/NEXT_STEPS.md` 与 `docs/TYPE_SYSTEM_TASKS.md`。

> **最后更新**：2026-05-08（§6.2 MetadataRegistry 双轨已解决）

---

## 一、动态宿主（DynamicHost）相关

### 1.1 子解释器插件注册 [PENDING]
- 在子解释器初始化链路中补齐插件注册策略。
- 明确主解释器与子解释器的插件边界与可见性。

### 1.2 HOST 插件 breakpoint 接口 [PENDING]
- 补齐 HOST 侧 breakpoint 能力的统一入口。
- 明确调试态下的可重入行为。

---

## 二、公理化相关

### 2.1 Intent Stack 不可变性约束 [PENDING]
- 增强 Intent Stack 写时约束，避免跨阶段污染。

### 2.2 符号同步深拷贝 [PENDING]
- 在符号同步链路中补齐深拷贝策略。

### 2.3 ParserCapability LLM 提示词片段扩展 [PENDING]
- 补齐提示词片段扩展机制与校验。

### 2.4 Axiom Capability 内部委托对象模式重构 [FUTURE / INDEPENDENT]
- 评估 capability 内部委托模式，减少重复逻辑。

---

## 三、语法功能（非高优先级）

### 3.1 `(str n) @~ ... ~` 语法完善 [PENDING]
- 完善语法边界行为与错误提示。

### 3.2 llmretry 后缀语法澄清 [PENDING]
- 澄清语义边界并补齐文档说明。

---

## 四、intent_context 完整 OOP 化（待后续）

### 4.1 intent_context 实例作为函数调用参数 [PARTIAL / PENDING]
### 4.2 intent_context 作为函数参数类型 [PENDING]
### 4.3 intent_context 作为函数作用域默认上下文 [PENDING]
### 4.4 更复杂的意图上下文操作 [VISION]

---

## 五、其他功能

### 5.1 LLM 输出持久化 [PENDING]
### 5.2 子解释器变量深拷贝隔离 [PENDING]

---

## 六、架构与基础设施

### 6.1 ImmutableArtifact `__deepcopy__` [PENDING]
### 6.2 MetadataRegistry 双轨统一 [已解决]

主引擎路径（`discover_all(registry)` + `HostInterface(external_registry=...)`）已于 2026-05-08 统一为单一 SpecRegistry 实例。
`discover_all()` 现在若传入 registry 但其 `get_metadata_registry()` 返回 None，会主动抛出 `ValueError` 以防止静默双轨。
孤立使用（无 registry）时仍会创建独立实例，但主引擎路径不再受影响。

---

## 七、插件系统

### 7.1 插件显式引入完整实现 [PENDING]
### 7.2 模块符号去重机制 [PENDING]

---

## 八、llmexcept / retry 机制后续

### 8.1 重试策略配置扩展 [PENDING]

---

## 九、代码健康（审计遗留）

### 9.1 意图标签解析迁移到 Lexer [PENDING]
### 9.2 engine.py / service.py 历史妥协点继续清理 [PENDING]
### 9.3 instance_id 默认值碰撞风险 [PENDING]
### 9.4 LLMExceptFrame 重试历史追踪 [PENDING]
### 9.5 LLMExceptFrameStack 最大嵌套深度 [PENDING]
### 9.6 ibci_idbg side_table 接口暴露 [PENDING]

---

## 十、远期架构目标

### 10.1 host.run_isolated() 返回值改进 [VISION]
### 10.2 ReceiveMode 枚举演进 [VISION]
### 10.3 VM 信号 / 中断 / 异步机制 [VISION]

---

## 十一、明确排除的设计

- 不引入静态类型检查器作为解释器前置强依赖。
- 不以牺牲运行时可观测性换取短期性能优化。
