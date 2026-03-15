# IBCI 2.0 代码质量终极检查清单 (Active Checklist)

本清单汇总了当前工程中所有**未解决**的缺陷、架构风险以及审计发现的技术债。

## 1. 物理隔离与安全性 (Critical)

- [ ] **[Item 12] 跨引擎描述符污染**：在 `MetadataRegistry.register` 中强制执行 `clone()`，严禁物理单例共享。
- [ ] **[Bug] 导入路径错误**：修正 `artifact_loader.py` 中的 `RegistryIsolationError` 导入路径。
- [ ] **[Security] 封印后门清理**：移除 `stmt_handler.py` 中 `visit_IbClassDef` 的动态回退逻辑（L324-333），严禁在 STAGE 6 之后创建新描述符。
- [ ] **[Security] 异常等级升级**：将 `ArtifactLoader` 的 Linker 警告升级为致命错误，防止 broken inheritance 进入运行时。

## 2. 架构解耦 (God Object Remediation)

- [ ] **[Arch] 解释器持有脱离 (Foundation)**：从 `Registry` 中移除对 `Interpreter` 实例的直接持有（L143-148）。
- [ ] **[Arch] 解释器持有脱离 (Kernel)**：从 `IbClass`, `IbUserFunction`, `IbLLMFunction` 中移除对 `Interpreter` 实例的持有。
- [ ] **[Data] ExecutionContext 设计**：定义纯数据结构的上下文包，作为 Kernel 获取运行时状态的唯一合法途径。

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
