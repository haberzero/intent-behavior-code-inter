# IBC-Inter 2.0 未完成任务与深度审计发现 (Pending Tasks & Issues)

本文件是 IBC-Inter 项目当前所有已知缺陷、架构风险、技术债以及后续演进方向的**唯一权威清单**。本文件内容不允许进行精简或总结，所有条目必须保留原始审计细节。

## 1. 架构违规与“不可容忍”项 (Critical)

### **1.1 局部 Import 规避循环引用 (Architecture Compromise)**
- **[DONE]** 已全量清理 `stmt_handler.py`、`kernel.py`、`declaration.py` 和 `service.py` 中的关键局部导入。
- **[NEW AUDIT]** 全量扫描发现仍然有部分和架构演进阵痛高度相关的局部依赖，它们会随着架构演进逐渐被修复/变成可以无痛迁移至文件顶部的import

### **1.2 穿透禁令审计 (Penetration Audit)**
- **任务**: 进行全量 Grep 检查，严禁出现 `context.interpreter` 或 `context.runtime_context.registry` 等违规链条。
- **[DONE]** 发现 `Interpreter._setup_context` 显式将 `self` 注入 `RuntimeContext._interpreter` ([interpreter.py:L397-404](file:///c:/myself/proj/intent-behavior-code-inter/core/runtime/interpreter/interpreter.py#L397-404))。已重构为通过 `ExecutionContext` 传递池引用。
- **[DONE]** `RuntimeContextImpl` 暴露了 `registry` 属性 ([runtime_context.py:L423-424](file:///c:/myself/proj/intent-behavior-code-inter/core/runtime/interpreter/runtime_context.py#L423-424))。已移除该公开属性。
- **[DONE]** `RuntimeHostService` 直接跨实例操作子解释器的 `runtime_context` 内部属性 ([service.py:L149-150](file:///c:/myself/proj/intent-behavior-code-inter/core/runtime/host/service.py#L149-150))。已重构为使用 `sync_state` 接口。
- **风险**: 穿透调用会破坏组合解耦的物理隔离。

## 2. 逻辑完备性与执行时序 (High)

### **2.1 [DONE] 类字段初始化求值盲区 (Evaluation Gap)**
- **[DONE]** 已实现 `STAGE 5.5: PRE_EVAL` 预评估阶段。
- **[IES 2.1 REFACTOR]** 已将原始的 `(uid, value)` 元组黑盒重构为正式的 `IbDeferredField` 描述符。
- **[FIX]** 修复了预评估阶段缺失模块上下文的问题，现在支持基于定义模块（Lexical Scope）的延迟求值。
- **[FIX]** 实现了实例化时的 JIT 缓存机制，避免重复求值。

### **2.2 [DONE] STAGE 6 深度契约校验 (Verification)**

### **2.3 内置符号冲突校验 (Symbols)**
- **任务**: 在 `SymbolTable.define` 中增加对内置符号覆盖时的类型一致性检查。
- **风险**: 同名但不同类型的内置符号冲突会导致不可预知的解析结果。

### **2.4 [DONE] 意图捕获逻辑实现**
- **任务**: 实现 `Interpreter.get_captured_intents` ([interpreter.py:L66](file:///c:/myself/proj/intent-behavior-code-inter/core/runtime/interpreter/interpreter.py#L66))。已实现针对 `IbBehavior` 的意图捕获。

## 3. 技术债清理与硬编码移除 (Medium)

### **3.1 [DONE] 元数据驱动作用域判定 (Metadata-Driven Scope)**

### **3.2 调试逻辑与池化校验下沉 (Clean)**
- **任务**: 将 `interpreter.py` 中的池化校验（L592-607）迁移至 `ReadOnlyNodePool`。
- **任务**: 移除 `interpreter.py` 中的硬编码压栈节点白名单（L627-639），改为元数据驱动。

### **3.3 Legacy 模式与伪装层移除 (Clean)**
- **任务**: 清理 `discovery.py` 中对无 spec 模块的冗余兼容逻辑。
- **[DONE]** 已在 `discovery.py` 中实现 Fail-fast 加载机制。
- **[DONE]** 已在 UTS 完全接管后，移除描述符中的 `type_info` 兼容属性。
- **任务**: 清理 `type_hydrator.py` 中硬编码的 `"StaticType"` 字符串 fallback。

### **3.4 [DONE] llm_fallback 逻辑重构**
- **任务**: 将 `BaseHandler._with_llm_fallback` 逻辑进行专业化重构，针对不同 AST 节点（如 `IbIf`, `IbWhile`）提供差异化的意图注入和重试策略，消除目前的通用化膨胀。

## 4. 深度审计清单遗留项 (Audit Findings)

- **[DONE] [Audit Item 13]**: `discovery.py` 契约加载失败已改为 Fail-fast 抛出异常。
- **[DONE] [Audit Item 14]**: `stmt_handler.py` 已实现 STAGE 6 模式下的深度契约校验。
- **[DONE] [Audit Item 15]**: `stmt_handler.py` 已移除动态回退逻辑，强制执行预水化检查。

## 5. 发现的新问题 (New Findings)

- **[DONE] llm_fallback 逻辑膨胀**: `BaseHandler` 中的 `_with_llm_fallback` 逻辑过于泛化，缺乏针对不同节点的差异化处理。
- **[IGNORED] 资产加载安全性**: 缺乏对外部 Prompt 资产的哈希指纹（SHA-256）校验。此项在开源环境下目前非首要目标，暂时忽略。
- **[DONE] TODO 标记**:
  - `interpreter.py:L66`: `# TODO: 适配新的意图捕获逻辑` (已记录在 2.4 节)
- **[DONE] 跨组件反向污染**: `Interpreter` 实例被注入到 `RuntimeContext` 中，导致数据层持有逻辑层引用。
- **[PARTIAL] 局部导入残留**: 虽然核心局部导入已清理，但在 `factory.py`、`runtime_context.py` 和 `parser.py` 中仍存在用于打破硬性循环引用的局部导入，需评估是否可通过工厂模式进一步消除。

## 6. 深度治理执行路线图 (Detailed Execution Roadmap)

### **Phase 3: 执行细节修复与技术债清理 (Execution Level)**
*   **目标**: 解决具体的功能性缺陷和时序问题。
*   **3.1 [DONE] 类字段延迟评估 (Late Evaluation)**
*   **3.2 深度契约校验实施**:
    *   在 `IbClassDef` 访问器中，对比 `node_data` 定义的方法与 `Registry` 中注册的描述符。
    *   校验参数个数、位置及默认值占位符。
*   **3.3 局部导入全面清理**:
    *   全量替换 `stmt_handler.py` 等文件中的局部 `import` 为 `execution_context.factory.create_xxx()`。

## 7. 后续演进方向 (Roadmap - Phase 4.4+)

### **7.1 核心演进方向 (非即时任务)**
- **idbg 2.0 (交互式调试器)**: 实现回溯、帧选择、意图感知调试。
- **内核 Core Dump**: 导出 `.ibdump` 文件（CallStack + Registry + VariablePool）。
- **issue_tracker 2.0 (上下文诊断)**: 错误报告关联源码片段和语义意图链。

---

## 附录：合并文档参考 (No Data Loss Reference)

### **A. 核心哲学与架构三层模型 (From architecture_design_guide.md)**
- **蓝图层 (Domain)**: AST (只读), Symbols, Types, Artifact (契约)。
- **生产层 (Compiler)**: Multi-Pass 语义分析 (Collector, Resolver, Analyzer), Side-Tabling (侧表化存储分析结论)。
- **消费层 (Runtime)**: Flat Pooling (UID 16位 Hex), UID-Based Walking, Rebinding Protocol (热替换)。

---
*记录日期: 2026-03-16*
*状态: 深度治理期 (IES 2.1)*
