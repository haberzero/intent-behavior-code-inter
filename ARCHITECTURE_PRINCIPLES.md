# IBC-Inter 架构原则与设计理念

> 本文档是 IBC-Inter 项目的核心架构参考文档，包含设计理念、层级架构、设计原则等关键内容。
> 供未来参与 IBC-Inter 项目的智能体和开发者进行架构对齐使用。
>
> **生成日期**：2026-03-21
> **版本**：V2.0

---

## 一、设计理念与愿景

### 1.1 核心定位

IBC-Inter (Intent Behavior Code - Interactive) 是一种**混合编程语言**，旨在连接：
- **确定性程序逻辑**（Code）
- **非确定性自然语言推理模型**（LLM）

### 1.2 设计目标

| 目标 | 说明 |
|------|------|
| **高效** | 直接从编程语言层级切入 |
| **可控** | 提供充分可靠的调试工具和监控工具 |
| **可复用** | 不依赖于具体大模型 |
| **易用** | 让普通人也能无痛构建属于自己的最简 Agent |
| **普惠** | 小尺寸开源模型也能参与严肃工作 |

### 1.3 核心理念

| 概念 | 作用 |
|------|------|
| **Code** | 确定性的骨架。负责数据结构定义、状态维护、文件交互、流程控制 |
| **Behavior** | 交互的桥梁。由 LLM 在运行时动态推理执行，并无缝接入代码逻辑 |
| **Intent** | 非确定性的上下文。作为环境的"背景信息栈"动态注入至提示词 |
| **Interactive** | 解释运行。LLM 调用开销使解释器专注于高级交互功能而非运行效率 |

### 1.4 IBC-Inter 建议的 LLM 边界

| LLM 擅长 | LLM 不擅长（应由代码完成） |
|----------|---------------------------|
| 常规自然语言处理 | 精确计算 |
| - | 长期流程控制和动态规划 |
| - | 从冗长上下文中提取 tools/skills |

---

## 二、层级架构定义

### 2.1 层级概览

```
base/ (最底层 - 原子概念，可迁移到任何语言)
    │
    ├── source/source_atomic.py  → Location, Severity
    ├── diagnostics/codes.py     → 错误码常量
    └── diagnostics/debugger.py  → CoreDebugger, DebugLevel
    │
    ▼ 依赖
kernel/ (核心层 - IBC-Inter核心语言概念)
    │
    ├── axioms/                 → 公理系统（类型行为规范）
    ├── types/registry.py      → MetadataRegistry
    ├── types/descriptors.py   → TypeDescriptor等
    ├── symbols.py              → 符号系统
    └── issue.py               → Diagnostic, 各种Error类
    │
    ▼ 依赖
compiler/ (只上不下，输出不可变JSON)
    │
    ├── diagnostics/            → IssueTracker
    └── serialization/          → FlatSerializer输出扁平JSON
    │
    ▼ 输出
runtime/ (只下不上，通过artifact_rehydrator还原)
    │
    └── extension/ (SDK层 - 只出不进)
```

### 2.2 各层职责

| 层级 | 职责 | 关键文件 |
|------|------|----------|
| **base** | 原子概念：位置信息、严重级别、调试基础设施 | source_atomic.py, debugger.py |
| **kernel** | 核心语言概念：AST、符号、类型描述符、公理、异常 | symbols.py, descriptors.py, axioms/ |
| **compiler** | 编译：词法分析、语法分析、语义分析、序列化 | lexer/, parser/, semantic/, serialization/ |
| **runtime** | 解释执行：解释器、宿主服务、插件执行 | interpreter/, host/, objects/ |
| **extension** | 插件SDK：接口定义、能力注入 | ibcext.py, capabilities.py |

---

## 三、核心设计原则

### 3.1 编译器-解释器严格分离

| 原则 | 说明 |
|------|------|
| 编译器输出不可变JSON | 包含完整UID/类型/依赖关系 |
| 解释器只能读取JSON | 通过hydrator还原运行时 |
| 解释器禁止修改原始JSON | 只允许独立运行时管理 |
| 不可变JSON是DynamicHost断点基础 | 保存/恢复/回溯断点的前提 |

### 3.2 公理化基底独立于Python

- `kernel/axioms/` 定义 IBC-Inter 类型行为规范
- `base/source_atomics.py` 定义位置/严重级别等原子概念
- 这些概念应该可以迁移到 C++ 或任何其他语言

### 3.3 插件系统三大职责边界

| 插件 | 职责 | 设计理念 |
|------|------|----------|
| **AI** | LLM调用接口 | 提供真正的LLM调用能力 |
| **IDBG** | 运行时信息输出 | 意图栈查看/内存分析/栈监控/运行时状态检查，**不影响主逻辑** |
| **HOST** | 环境保存/恢复/跳转 | 断点保存/恢复/回溯，**不是GDB式断点** |

### 3.4 DynamicHost "断点" ≠ GDB断点

| 概念 | DynamicHost "断点" | GDB 断点 |
|------|-------------------|----------|
| **目的** | 现场保存/恢复/回溯 | 单步调试/内存观察 |
| **触发方式** | 主动保存或环境退出 | 运行到指定位置 |
| **恢复能力** | 可恢复到之前保存的状态 | 仅能从当前位置继续 |

### 3.5 DynamicHost 最小目标

1. **能够启动全隔离的运行环境**
2. **能够继承所有来自主解释器的插件/UTS/公理体系**
3. **不做额外的权限控制管理**
4. **运行之后不会干扰主解释器的任何内容**
5. **可以让主解释器正确返回到跳出点的位置**

**信息交互方式**：通过显式的 file 读写进行，不做隐式内存交互。

---

## 四、依赖规则

### 4.1 核心依赖原则

**核心原则**：kernel → base（单向依赖），compiler → kernel，runtime → kernel

| 依赖方向 | 是否允许 | 说明 |
|----------|----------|------|
| kernel → base | ✅ 允许 | kernel 可使用 base 的原子概念 |
| compiler → kernel | ✅ 允许 | 编译器依赖核心语言概念 |
| runtime → kernel | ✅ 允许 | 运行时依赖核心语言概念 |
| kernel → runtime | ❌ 禁止 | 架构穿透严格禁止 |
| runtime → compiler | ❌ 禁止 | 运行时不应依赖编译器 |

### 4.2 架构穿透严格禁止

- kernel 层禁止依赖 runtime 层具体实现
- IExecutionContext 应按职责拆分：
  - **纯数据部分**：可序列化，可存在于任何层
  - **访问接口部分**：定义为 kernel 层的抽象接口

---

## 五、公理体系设计

### 5.1 公理系统架构

| 组件 | 职责 | 文件位置 |
|------|------|----------|
| **TypeAxiom** | 核心公理接口 | axioms/protocols.py |
| **BaseAxiom** | 公理基类，提供默认实现 | axioms/primitives.py |
| **IntAxiom/StrAxiom...** | 具体类型公理 | axioms/primitives.py |
| **AxiomRegistry** | 公理注册表 | axioms/registry.py |
| **AxiomHydrator** | 公理注入器，将公理方法注入到TypeDescriptor | types/axiom_hydrator.py |

### 5.2 公理与类型系统集成

- TypeDescriptor 通过 `_axiom` 字段绑定公理
- AxiomHydrator.inject_axioms() 将公理的 get_methods() 注入到 descriptor.members
- 能力访问器（get_call_trait, get_operator_result 等）全部委托给公理

### 5.3 UTS（统一类型系统）

| 组件 | 职责 | 文件位置 |
|------|------|----------|
| **MetadataRegistry** | UTS元数据注册表，两阶段注册 | kernel/types/registry.py |
| **TypeDescriptor** | 类型元数据描述符 | kernel/types/descriptors.py |
| **TypeFactory** | 类型工厂 | kernel/types/registry.py |

---

## 六、Intent/Behavior 系统

### 6.1 Intent（意图）系统

- Intent 是非确定性的上下文
- 作为环境的"背景信息栈"动态注入至提示词
- 支持 @/@+/@-/@! 修饰符

### 6.2 Behavior（行为）系统

- Behavior 通过 `@~ ... ~` 语法触发 LLM 调用
- Callable 类型支持延迟执行的 Behavior（闭包封装）

### 6.3 意图栈继承策略

- **当前阶段不继承任何意图栈**
- `IsolationPolicy.inherit_intents` 默认值为 `False`

---

## 七、插件系统（IES 2.0）

### 7.1 模块发现机制

- `ModuleDiscoveryService` 扫描 `ibc_modules/` 和 `plugins/` 目录
- 通过 `_spec.py` 约定自动发现
- SpecBuilder 提供声明式接口构建

### 7.2 插件接口规范

- `_spec.py`：定义插件导出的函数签名、类型信息及所需权限
- `__init__.py`：具体的 Python 逻辑实现
- 内置函数（print, input, len等）应通过 `_spec.py` + SpecBuilder 声明

---

## 八、信息交互原则

> "更倾向于某种比较显式的信息交互，主要通过硬盘以及文件读写"
> "子环境的 llm 输出也可以直接进行硬盘保存"
> "有利于开发者绝对控制可被交互的信息"
> "内存交互实在过分复杂而沉重，不符合易用性设计理念"

**核心原则**：信息交互应通过显式的 file 读写进行，不做隐式内存交互。

---

## 九、自动注册/自动嗅探机制

> "99%的情况严格禁止硬编码，一切不管是内置函数/内置关键字/语法糖等，还是外部插件的主动注册，都应该自动完成，而且享有基本上同等地位。"

| 机制 | 位置 | 说明 |
|------|------|------|
| **ModuleDiscoveryService** | module_system/discovery.py | 扫描 ibc_modules/，通过 _spec.py 自动发现 |
| **SpecBuilder** | extension/spec_builder.py | 声明式自动构建插件接口 |
| **两阶段注册** | kernel/types/registry.py | 占位阶段 + 填充阶段 + 公理注入 |

---

## 十、命名前缀规范

| 层级 | 建议前缀 | 示例 |
|------|----------|------|
| base | 直接用描述性名称 | `source_atomics.py`, `debugger.py` |
| kernel | 无需前缀（kernel已经是限定词） | `axiom_hydrator.py`, `issue.py` |
| runtime | `rt_` 或 `runtime_` | `rt_artifact_rehydrator.py` |
| compiler | 无需前缀（compiler已经是限定词） | `issue_tracker.py`, `formatter.py` |
| extension | `ext_` 或 `extension_` | `extension_ibcext.py` |

---

## 十一、已明确的排除项

| 排除项 | 理由 |
|--------|------|
| 进程级隔离 | 实例级隔离已足够 |
| 核心级 IPC | 通过外部 file 插件实现 |
| GDB 式断点 | DynamicHost 断点是现场保存/恢复/回溯 |
| hot_reload_pools | 违反解释器不修改代码原则 |
| generate_and_run | 动态生成IBCI应由显式的IBCI生成器进行 |

---

## 附录：关键文件索引

| 文件 | 重要性 | 说明 |
|------|--------|------|
| core/kernel/registry.py | 高 | KernelRegistry |
| core/kernel/types/registry.py | 高 | MetadataRegistry，两阶段注册 |
| core/kernel/symbols.py | 中 | 符号系统 |
| core/runtime/interpreter/execution_context.py | 高 | ExecutionContextImpl |
| core/runtime/host/service.py | 高 | HostService，run_isolated/save_state |
| core/compiler/serialization/serializer.py | 高 | FlatSerializer |
| core/base/diagnostics/debugger.py | 中 | CoreDebugger |
| ibc_modules/idbg/core.py | 中 | IDBG 插件实现 |
| ibc_modules/ai/core.py | 中 | AI 插件实现 |
| ibc_modules/host/__init__.py | 中 | HOST 插件实现 |

---

*本文档为 IBC-Inter 架构原则参考文档，供未来项目参与人员进行架构对齐使用。*
