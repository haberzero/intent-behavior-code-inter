# IBCI 2.0 代码质量终极检查清单 (Active Checklist)

本清单汇总了当前工程中所有**未解决**的缺陷、架构风险以及审计发现的技术债。

## 1. 物理隔离与安全性 (Critical)

- [x] **[Item 12] 跨引擎描述符污染**：在 `MetadataRegistry.register` 中强制执行 `clone()`，严禁物理单例共享。
- [x] **[Bug] 导入路径错误**：修正 `artifact_loader.py` 中的 `RegistryIsolationError` 导入路径。
- [x] **[Security] 封印后门清理**：移除 `stmt_handler.py` 中 `visit_IbClassDef` 的动态回退逻辑（L324-333），严禁在 STAGE 6 之后创建新描述符。
- [x] **[Security] 异常等级升级**：将 `ArtifactLoader` 的 Linker 警告升级为致命错误，防止 broken inheritance 进入运行时。

## 2. 架构解耦 (God Object Remediation)

- [x] **[Arch] 解释器组合解耦**：废弃 `Interpreter` 对 `IExecutionContext` 和 `IStackInspector` 的继承，改为持有 `ExecutionContextImpl` 实例。
- [x] **[Data] StackState 提取**：逻辑调用栈的状态数据已从解释器逻辑中分离，通过组合容器管理。

## 3. 上下文正规化 (Context Regularization)

- [x] **[Arch] ServiceContext 物理剥离**：将 `ServiceContext` 定义从 Foundation 迁移至 Runtime，并创建独立的 `service_context.py` 实现文件。
- [x] **[Arch] 穿透路径清理**：彻底删除 `ServiceContext` 对 `Interpreter` 实例的持有，改为纯服务协议持有。
- [x] **[Arch] 职责单一化**：从 `ServiceContext` 中移除 `runtime_context` 代理，确保“服务”与“状态”路径不重叠。
- [x] **[Injection] 最小特权注入**：重构 `LLMExecutor`、`ModuleManager` 等组件，改为注入特定的数据结构（如 `Registry`）而非全量上下文。
- [ ] **[Audit] 穿透禁令审计**：全量 Grep 检查，严禁出现 `context.interpreter` 或 `context.runtime_context.registry` 等违规链条。

## 4. 意图管理解耦 (Intent Management Decoupling)

- [x] **[Arch] 栈管理职责收拢**：将 `execute_behavior_object` 中的意图栈切换逻辑从 `LLMExecutor` 移至 `BaseHandler._execute_behavior`。
- [x] **[Clean] 意图消解逻辑下沉**：重构 `RuntimeContext`，封装 `IntentResolver` 的调用，使得 `LLMExecutor` 仅需消费最终结果。
- [x] **[Decouple] 意图解析去回调化**：移除 `EvaluatorShim` 及其对应的回调机制。意图解析现通过 `IExecutionContext` 完成。

## 3. 逻辑完备性与时序 (High)

- [ ] **[Init] 复杂字段求值**：重构类实例化流程，支持在环境闭合后评估类字段的复杂表达式（如 `int x = a + b`）。
- [ ] **[Verification] STAGE 6 深度校验**：实现方法签名、参数数量及类型的静态一致性验证。
- [ ] **[Symbols] 内置符号冲突校验**：在 `SymbolTable.define` 中增加对内置符号覆盖时的类型一致性检查。

## 4. 维护性与硬编码清理 (Medium/Low)

- [ ] **[Bootstrap] 内置引导下沉**：将 `builtin_initializer.py` 中的硬编码 Axiom 映射表完全迁移至公理定义层。
- [ ] **[Clean] 调试逻辑下沉**：将 `interpreter.py` 中的池化校验（L592-607）迁移至 `ReadOnlyNodePool`。
- [ ] **[Clean] 硬编码压栈驱动**：移除 `interpreter.py` 中的压栈节点白名单（L627-639），改为元数据驱动。
- [ ] **[Discovery] Legacy 模式移除**：清理 `discovery.py` 中对无 spec 模块的冗余兼容逻辑。
- [ ] **[Compat] UTS 伪装层移除**：在 UTS 完全接管语义分析后，移除描述符中的 `type_info` 兼容属性。

---
*版本：Active Checklist v3.1 (2026-03-15)*
*详细审计背景请参阅：[IBCI_2_0_ENGINEERING_MANIFEST.md](file:///c:/myself/proj/intent-behavior-code-inter/IBCI_2_0_ENGINEERING_MANIFEST.md)*
