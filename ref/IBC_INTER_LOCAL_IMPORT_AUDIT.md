# IBC-Inter 局部导入全量审计报告 (2026-03-16)

> **审计范围**: `core/`, `ibc_modules/` (排除 `tests/` 目录)  
> **审计目标**: 识别所有在函数或方法内部执行的运行时局部导入，评估其必要性、架构合规性及演进潜力。

---

## 📊 审计结果摘要 (2026-03-16 更新)

本审计共识别出 **24 处** 逻辑位置的局部导入。经过 **Phase 1 治理**，已有 **12 处** 成功修复。

| 评级 | 类别 | 剩余数量 | 已修复 | 描述 |
| :--- | :--- | :--- | :--- | :--- |
| 🔴 | **架构违规** | 3 | 4 | 存在层级击穿或严重的循环依赖妥协，必须在演进中消除。 |
| 🟡 | **技术债** | 2 | 6 | 为了方便而进行的局部导入，应通过依赖注入 (DI) 或工厂模式优化。 |
| 🟢 | **合规/正当** | 7 | 2 | 标准库按需加载或可选第三方库依赖。 |

---

## 🔍 详细清单与分析

### 1. 编译器层 (Compiler Layer) - 4 处

| 文件位置 | 导入语句 | 评级 | 状态 | 原因分析与演进方案 |
| :--- | :--- | :--- | :--- | :--- |
| [declaration.py:L265](file:///c:/myself/proj/intent-behavior-code-inter/core/compiler/parser/components/declaration.py#L265) | `from core.compiler.lexer.lexer import Lexer` | 🔴 | **FIXED** | 已提升至顶部。 |
| [declaration.py:L266](file:///c:/myself/proj/intent-behavior-code-inter/core/compiler/parser/components/declaration.py#L266) | `from core.compiler.parser.core.token_stream import TokenStream` | 🔴 | **FIXED** | 已提升至顶部。 |
| [parser.py:L33](file:///c:/myself/proj/intent-behavior-code-inter/core/compiler/parser/parser.py#L33) | `from core.compiler.diagnostics.issue_tracker import IssueTracker` | 🟡 | **FIXED** | 已提升至顶部。 |
| [token_stream.py:L18](file:///c:/myself/proj/intent-behavior-code-inter/core/compiler/parser/core/token_stream.py#L18) | `from core.compiler.diagnostics.issue_tracker import IssueTracker` | 🟡 | **FIXED** | 已提升至顶部。 |

### 2. 运行时层 (Runtime Layer) - 13 处

| 文件位置 | 导入语句 | 评级 | 状态 | 原因分析与演进方案 |
| :--- | :--- | :--- | :--- | :--- |
| [service.py:L103](file:///c:/myself/proj/intent-behavior-code-inter/core/runtime/host/service.py#L103) | `from core.runtime.objects.kernel import IbObject, IbNativeObject` | 🔴 | **FIXED** | 已通过工厂模式消除。 |
| [factory.py:L35, 45](file:///c:/myself/proj/intent-behavior-code-inter/core/runtime/interpreter/factory.py#L35) | `from core.domain.intent_logic import IntentMode, IntentRole` | 🟡 | **FIXED** | 已提升至顶部。 |
| [interpreter.py:L67](file:///c:/myself/proj/intent-behavior-code-inter/core/runtime/interpreter/interpreter.py#L67) | `from core.runtime.interfaces import IIbBehavior, IIbIntent` | 🔴 | **FIXED** | 已提升至顶部。 |
| [interpreter.py:L421](file:///c:/myself/proj/intent-behavior-code-inter/core/runtime/interpreter/interpreter.py#L421) | `import traceback` | 🟢 | **合规** | 标准库按需加载。 |
| [intrinsics/__init__.py:L50-53](file:///c:/myself/proj/intent-behavior-code-inter/core/runtime/interpreter/intrinsics/__init__.py#L50) | `from .io import register_io` 等 | 🟡 | **FIXED** | 已提升至顶部。 |
| [runtime_context.py:L384](file:///c:/myself/proj/intent-behavior-code-inter/core/runtime/interpreter/runtime_context.py#L384) | `from core.domain.intent_resolver import IntentResolver` | 🔴 | **FIXED** | 已提升至顶部。 |
| [type_hydrator.py:L43](file:///c:/myself/proj/intent-behavior-code-inter/core/runtime/loader/type_hydrator.py#L43) | `from core.runtime.enums import RegistrationState` | 🟡 | **FIXED** | 已提升至顶部。 |
| [discovery.py:L71-72](file:///c:/myself/proj/intent-behavior-code-inter/core/runtime/module_system/discovery.py#L71) | `from core.domain.symbols import SymbolFactory` 等 | 🟡 | **FIXED** | 已提升至顶部。 |
| [intent.py:L7](file:///c:/myself/proj/intent-behavior-code-inter/core/runtime/objects/intent.py#L7) | `from core.runtime.interpreter.llm_executor import LLMExecutorImpl` | 🔴 | **FIXED** | 已移入 `TYPE_CHECKING`。 |

### 3. 域与基础层 (Domain & Foundation) - 2 处

| 文件位置 | 导入语句 | 评级 | 状态 | 原因分析与演进方案 |
| :--- | :--- | :--- | :--- | :--- |
| [symbols.py:L41](file:///c:/myself/proj/intent-behavior-code-inter/core/domain/symbols.py#L41) | `import copy` | 🟡 | **FIXED** | 已提升至顶部。 |
| [core_debugger.py:L133](file:///c:/myself/proj/intent-behavior-code-inter/core/foundation/diagnostics/core_debugger.py#L133) | `import pprint` | 🟢 | **FIXED** | 已提升至顶部。 |

### 4. 扩展模块 (ibc_modules) - 5 处

| 文件位置 | 导入语句 | 评级 | 原因分析与演进方案 |
| :--- | :--- | :--- | :--- |
| [ai/core.py:L59](file:///d:/Proj/intent-behavior-code-inter-master/ibc_modules/ai/core.py#L59) | `from openai import OpenAI` | 🟢 | **合规**：可选第三方依赖。允许在无 API 环境下运行 Mock。 |
| [net/__init__.py:L14](file:///d:/Proj/intent-behavior-code-inter-master/ibc_modules/net/__init__.py#L14) | `import requests` | 🟢 | **合规**：同上。 |
| [ai/core.py:L166](file:///d:/Proj/intent-behavior-code-inter-master/ibc_modules/ai/core.py#L166) | `from core.domain.issue import InterpreterError` | 🔴 | **架构穿透**：插件直接依赖内核异常模型。应通过 SDK 包装抛出。 |
| [net/__init__.py:L22](file:///d:/Proj/intent-behavior-code-inter-master/ibc_modules/net/__init__.py#L22) | `from core.domain.issue import InterpreterError` | 🔴 | **架构穿透**：同上。 |
| [schema/__init__.py:L38](file:///d:/Proj/intent-behavior-code-inter-master/ibc_modules/schema/__init__.py#L38) | `from core.domain.issue import InterpreterError` | 🔴 | **架构穿透**：同上。 |

---

## � 修复路线图与时序建议 (Repair Roadmap)

根据架构演进路线图 ([IES 2.1+](file:///d:/Proj/intent-behavior-code-inter-master/guide/05_evolution_roadmap_and_suggestions.md))，局部导入的修复应按以下时序进行：

### **阶段 1：即时清理 (已完成 ✅)**
*   **目标**: 消除冗余导入，提升标准库及无冲突的 Domain 层枚举。
*   **重点动作**:
    - [DONE] 删除 `declaration.py:L266` 的冗余 `TokenStream` 导入。
    - [DONE] 将 `symbols.py` 的 `copy`、`factory.py` 的 `IntentMode/Role` 提升至顶部。
    - [DONE] 将 `parser.py` 和 `token_stream.py` 中的 `IssueTracker` 提升至顶部。
    - [DONE] 将 `interpreter.py` 中的 `IIbBehavior/IIbIntent` 提升至顶部并合并。
    - [DONE] 将 `runtime_context.py` 中的 `IntentResolver` 提升至顶部。
    - [DONE] 将 `core_debugger.py` 中的 `pprint` 提升至顶部。

### **阶段 2：对齐 P0/P1 路线 (UTS 契约化)**
*   **目标**: 随着 UTS 从身份判定转向契约判定，解除物理导入压力。
*   **重点动作**:
    - [P1] 随着 `converters.py` 逻辑迁移至 `ParserCapability` 公理，消除 `type_hydrator.py` 等处的局部感知。
    - [P1] 处理 `intent.py` 对 `LLMExecutorImpl` 的导入，改为协议接口决议。

### **阶段 3：对齐 P2 路线 (DI 与工厂模式注入)**
*   **目标**: 引入真正的依赖注入，切断编译器与运行时的穿透链。
*   **重点动作**:
    - [P2] 在 `ParserContext` 中建立子解析服务，消除 `declaration.py` 对 `Lexer` 的反向调用。
    - [P2] 在 `discovery.py` 中通过构造函数注入 `SymbolFactory`。
    - [P2] 实现内置函数的动态自注册，清理 `intrinsics/__init__.py` 的硬编码。

### **阶段 4：对齐 P3 路线 (内省协议安全化)**
*   **目标**: 打通宿主环境与内核对象的物理隔离。
*   **重点动作**:
    - [P3] 随着 IES 2.1 引入 `IObjectFactory`，消除 `service.py` 对 `IbObject` 的物理导入。
    - [P3] 将 `runtime_context.py` 中的意图消解逻辑外置到专门的服务中。

### **阶段 5：SDK 级隔离 (终局清理)**
*   **目标**: 实现扩展插件与内核的彻底解耦。
*   **重点动作**:
    - [Final] 统一使用 `core/extension/sdk.py` 提供的错误抛出接口，修复 `ibc_modules` 下的所有架构穿透导入。
    - [Final] 保留 `OpenAI` 和 `requests` 的局部导入作为合规的插件增强机制。

---

## �🛠️ 深度演进建议 (IES 2.1+)

1.  **协议化 (UTS Axioms)**: 通过 `core/domain/axioms/protocols.py` 进一步抽象，使得 `IbObject` 等底层核心不再需要通过具体的类导入来识别类型，从而切断 90% 的物理循环依赖。
2.  **工厂与上下文注入**: 全量实施 `ExecutionContext.factory` 模式。底层组件（如 `Parser` 或 `Interpreter`）在构造时不应知道如何创建其子依赖，而应由上层引擎注入。
3.  **SDK 异常隔离**: 在 `core/extension/sdk.py` 中建立统一的错误报告机制，禁止 `ibc_modules` 跨层级引用 `core.domain.issue`。

---
*记录日期: 2026-03-16*  
*审计状态: 完备 (IES 2.0 阶段)*
