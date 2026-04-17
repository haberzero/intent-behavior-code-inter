# IBC-Inter 架构原则与设计理念

> 本文档是 IBC-Inter 项目的核心架构参考文档，包含设计理念、层级架构、设计原则等关键内容。
> 供未来参与 IBC-Inter 项目的智能体和开发者进行架构对齐使用。
>
> **生成日期**：2026-03-21，**最后更新**：2026-04-17
> **版本**：V2.2
>
> 重要的架构细节（llmexcept 机制、MOCK 系统、类型系统迁移等）详见 [ARCH_DETAILS.md](./ARCH_DETAILS.md)。

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
    ├── spec/                   → 统一类型描述系统（IbSpec / SpecRegistry）
    ├── symbols.py              → 符号系统（Symbol.spec 唯一字段）
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
| **kernel** | 核心语言概念：AST、符号、统一类型描述系统、公理、异常 | symbols.py, spec/, axioms/ |
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

### 3.4 DynamicHost 架构定位

DynamicHost 是**插件接口层**，不是解释器管理层。

| 组件 | 职责 | 说明 |
|------|------|------|
| **DynamicHost** | 接口层 | 暴露 @method 给 IBCI 脚本，不持有解释器实例，纯委托 |
| **HostService** | 服务实现层 | 协调子解释器创建，委托 Engine 执行 |
| **Engine** | 解释器管理层 | 唯一持有 Interpreter 实例，负责 spawn_interpreter() |
| **Interpreter** | 执行层 | 单个解释器的执行上下文 |

**调用链**：
```
IBCI脚本 → DynamicHost → HostService → Engine.spawn_interpreter() → Interpreter
```

**重要**：子解释器和主解释器**地位平等**，都是 Interpreter 实例，区别仅在于创建方式。

### 3.5 DynamicHost "断点" ≠ GDB断点

| 概念 | DynamicHost "断点" | GDB 断点 |
|------|-------------------|----------|
| **目的** | 现场保存/恢复/回溯 | 单步调试/内存观察 |
| **触发方式** | 主动保存或环境退出 | 运行到指定位置 |
| **恢复能力** | 可恢复到之前保存的状态 | 仅能从当前位置继续 |

### 3.6 DynamicHost 最小目标

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

### 5.3 Fallback 策略原则（重要）

IBC-Inter 公理体系中的 fallback 分为两类，必须严格区分：

#### 允许的 Fallback：职责分离型

**设计原则**：公理层声明"行为规范"，描述符层持有"具体类型信息"

| 场景 | 说明 |
|------|------|
| **TypeDescriptor 基类能力访问器** | 返回 None 表示"未知"，子类有义务重写 |
| **FunctionMetadata.resolve_return** | Axiom 优先，静态签名作为编译期后备（双轨制） |
| **LazyDescriptor 正常情况** | 占位符模式，已解析时返回真实描述符 |

#### 禁止的 Fallback：妥协性历史兼容

**设计原则**：公理为唯一真源，任何妥协性 fallback 都是技术债务

| 问题 | 说明 |
|------|------|
| **ListMetadata/DictMetadata fallback** | 描述符同时充当数据存储，违反公理唯一真源原则 |
| **StrAxiom.resolve_item 返回 None** | 公理实现错误，注释明确标注 "Should return STR_DESCRIPTOR" |
| **ExpressionAnalyzer `or self._any_desc`** | 静默掩盖类型错误，应给出精确错误提示 |
| **AxiomHydrator 静默返回** | 配置错误被静默忽略，应抛出 RuntimeError |
| **LazyDescriptor 异常情况** | `resolve()`失败或`_registry`不可用时返回self占位，应抛出错误 |

**关于 LazyDescriptor 的详细说明**：

LazyDescriptor 是**占位符模式**实现，用于解决循环依赖：
- **正常情况**：`unwrap()` 成功解析后返回真实 TypeDescriptor
- **异常情况**：如果 `_registry` 不可用或 `resolve()` 失败，返回 `self` 作为占位符

"返回 self" 作为占位符虽然允许编译继续，但掩盖了**配置错误或解析失败**。理想情况下：
- `_registry` 不可用应该抛出错误（系统配置问题）
- `resolve()` 失败也应该抛出错误（类型未注册）

**违反后果**：妥协性 fallback 会导致类型信息丢失、错误掩盖、难以调试等问题，必须在后续迭代中修复。

---

### 5.4 统一类型描述系统（core/kernel/spec/）

类型描述系统已从旧的 `core/kernel/types/`（已删除）完全迁移至 `core/kernel/spec/`。

| 组件 | 职责 | 文件位置 |
|------|------|----------|
| **IbSpec** | 所有类型描述符的基类 | `kernel/spec/base.py` |
| **FuncSpec / ClassSpec / ListSpec / TupleSpec / DictSpec 等** | 具体类型描述符 | `kernel/spec/specs.py` |
| **SpecRegistry** | 类型注册、兼容性检查、Capability 查询 | `kernel/spec/registry.py` |
| **SpecFactory** | 内置类型工厂（create_list/create_tuple/create_dict 等） | `kernel/spec/registry.py` |
| **MemberSpec / MethodMemberSpec** | 模块成员描述符 | `kernel/spec/member.py` |

`Symbol` 只保留 `.spec` 字段（`IbSpec` 类型），不存在 `.descriptor` 属性或任何兼容 shim。

关于 MetadataRegistry（公理 Capability 查询入口）以及 MetadataRegistry 双轨问题，详见 ARCH_DETAILS.md。

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

## 七、插件系统

### 7.1 模块发现机制

- `ModuleDiscoveryService` 扫描 `ibc_modules/` 和 `plugins/` 目录
- 通过 `_spec.py` 约定自动发现
- SpecBuilder 提供声明式接口构建

### 7.2 插件接口规范

| 文件 | 职责 | 说明 |
|------|------|------|
| `_spec.py` | 元数据注入 | 声明函数签名、类型信息（`__ibcext_vtable__()` 格式或 SpecBuilder） |
| `core.py` | 具体逻辑实现 | 插件的具体 Python 类实现 |
| `__init__.py` | 工厂模式入口 | 只负责导入和 `create_implementation()` 工厂函数 |

**两级插件架构**：

| 级别 | 说明 | 包含插件 |
|------|------|---------|
| 非侵入式 | 不 import 任何 `core.*`，纯 Python 类 | ibci_math / ibci_json / ibci_time / ibci_net / ibci_file / ibci_schema |
| 核心级 | 继承 `IbPlugin`，可访问 `ExtensionCapabilities`；有状态插件实现 `IbStatefulPlugin` | ibci_ai / ibci_ihost / ibci_idbg / ibci_isys |

**示例（AI 插件）**：
- `ibci_modules/ibci_ai/__init__.py` → `from .core import AIPlugin; def create_implementation(): return AIPlugin()`
- `ibci_modules/ibci_ai/core.py` → `class AIPlugin(ILLMProvider, IbStatefulPlugin): ...`
- `ibci_modules/ibci_ai/_spec.py` → `__ibcext_vtable__()` 返回函数签名字典

### 7.3 插件架构愿景（零侵入自动嗅探）

> **设计目标**：插件不再需要 import 任何核心代码，实现真正的零侵入自动注册。

#### 7.3.1 核心设计

| 特性 | 说明 |
|------|------|
| **零侵入** | 插件不继承任何核心代码（甚至不 import ibcext） |
| **协议固定命名** | 插件必须实现固定命名方法（如 `__ibcext_vtable__()`） |
| **全自动嗅探** | AutoDiscoveryService 自动扫描 _spec.py，发现并加载插件 |
| **元数据自注册** | 通过固定命名函数完成元数据注册，无需运行时依赖 |
| **二进制兼容** | 只要保留 Python 解释器，反射机制正常工作 |

#### 7.3.2 固定命名方法约定

| 方法名 | 职责 | 返回值 |
|--------|------|--------|
| `__ibcext_vtable__()` | 提供虚表（方法名映射） | Dict[str, Callable] |
| `__ibcext_metadata__()` | 提供插件元数据 | Dict[str, Any] |
| `create_factory()` | 工厂函数入口 | Callable |
| `create_implementation()` | 实现创建函数 | IbPlugin 实例 |

**示例（插件）**：
```python
# ibc_modules/ai/_spec.py - 不再 import ibcext
def __ibcext_metadata__():
    return {
        "name": "ai",
        "version": "1.0.0",
        "description": "LLM provider plugin",
    }

def __ibcext_vtable__():
    return {
        "complete": lambda self, prompt, context: self._llm.complete(prompt, context),
        "embed": lambda self, text: self._llm.embed(text),
    }

def create_implementation():
    return _AIPluginCore()  # 返回无基类依赖的实现类
```

#### 7.3.3 AutoDiscoveryService 嗅探机制

```python
class AutoDiscoveryService:
    """全自动插件发现服务"""
    
    def discover_plugins(self, plugin_dirs: List[str]) -> List[PluginSpec]:
        discovered = []
        for plugin_dir in plugin_dirs:
            for spec_file in Path(plugin_dir).glob("*/_spec.py"):
                spec = self._load_spec(spec_file)
                if self._is_valid_ies22_plugin(spec):
                    discovered.append(self._create_plugin_spec(spec))
        return discovered
    
    def _load_spec(self, spec_path: Path) -> Dict[str, Any]:
        """通过 importlib 加载 _spec.py 并调用固定命名方法"""
        spec_module = importlib.import_module(spec_path.stem, spec_path.parent.name)
        metadata = getattr(spec_module, '__ibcext_metadata__', lambda: {})()
        vtable_func = getattr(spec_module, '__ibcext_vtable__', None)
        return {"metadata": metadata, "vtable": vtable_func}
```

#### 7.3.4 函数名映射机制

插件编写者可以在 `__ibcext_vtable__()` 内部自定义函数名映射：

```python
def __ibcext_vtable__():
    return {
        # IBCI脚本看到的名字 → 实际实现函数
        "complete": _real_llm_complete,
        "embed": _real_embedding,
        # 自定义特殊映射，利用 Python 特性实现高级用法
        "__custom_meta__": _register_special_metadata,
    }
```

这允许插件编写者：
- 使用与实现函数不同的对外名称
- 利用 Python 特性实现特殊的元数据注册机制
- 极大提高插件编写者的自由度

#### 7.3.5 二进制打包兼容性

| 打包场景 | 兼容性 | 说明 |
|----------|--------|------|
| **PyInstaller 打包** | ✅ 完全兼容 | Python 解释器完整保留 |
| **Nuitka 打包** | ✅ 完全兼容 | 反射机制正常工作 |
| **未来语法迁移** | ✅ 完全兼容 | Python 作为胶水层保留 |

**核心保障**：只要保留完整的 Python 解释器，所有 `__attr__` 反射机制、`importlib`、`dir()` 等都能正常工作。

#### 7.3.6 向后兼容策略

| 场景 | 处理方式 |
|------|----------|
| **混合使用** | 同时支持 `@ibcext.method` 和 `__ibcext_vtable__()` |

#### 7.3.7 编译构建流程（静态类型检查保留）

> **核心洞察**：编译器在 STAGE_3 (PLUGIN_METADATA) 之后进行静态类型检查。只要在编译前完成 `discover_all()` 并将元数据注册到 `MetadataRegistry`，静态类型检查完全保留。

**当前架构流程**：
```
Engine.__init__()
    ↓
discovery_service.discover_all() → HostInterface.metadata
    ↓
compiler/scheduler 使用 HostInterface.metadata 做静态类型检查
```

**架构流程**：
```
┌─────────────────────────────────────────────────────────────────────┐
│ 构建阶段（ibcc 命令）                                                │
│                                                                      │
│ 1. AutoDiscoveryService.discover_all()                               │
│    ↓                                                                │
│ 2. 生成 .ibc_meta 文件（JSON格式的元数据快照）                       │
│    ↓                                                                │
│ 3. 编译器读取 .ibc_meta → MetadataRegistry                          │
│    ↓                                                                │
│ 4. 静态类型检查通过 → FlatSerializer 生成扁平JSON                   │
├─────────────────────────────────────────────────────────────────────┤
│ 运行时阶段（ibci 命令）                                              │
│                                                                      │
│ 1. AutoDiscoveryService.discover_all()                              │
│    ↓                                                                │
│ 2. 发现 __ibcext_vtable__() 和 create_implementation()              │
│    ↓                                                                │
│ 3. 运行时加载插件实现                                                │
│    ↓                                                                │
│ 4. 通过 setup() 注入 service_context（IssueTracker等）              │
└─────────────────────────────────────────────────────────────────────┘
```

**关键保证**：
| 保证 | 说明 |
|------|------|
| **静态类型检查保留** | 编译器通过 .ibc_meta 文件获取完整的 TypeDescriptor 信息 |
| **扁平流生成保留** | FlatSerializer 依赖 TypeDescriptor.get_references()，与发现机制无关 |
| **运行时零侵入** | 插件不需要 import ibcext 就能被发现和加载 |
| **二进制兼容** | 只要有 Python 解释器，运行时发现正常工作 |

**需要的代码配合**：
| 组件 | 修改 | 说明 |
|------|------|------|
| **ibcc 构建命令** | 新增 `--pre-scan-specs` 参数 | 扫描 _spec.py 并生成 .ibc_meta |
| **AutoDiscoveryService** | 增加 `export_metadata()` 方法 | 将元数据序列化为 JSON |
| **Scheduler** | 增加 `load_metadata_from_file()` | 编译前读取 .ibc_meta |

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
| **ModuleDiscoveryService** | `module_system/discovery.py` | 扫描 ibci_modules/，通过 _spec.py 自动发现 |
| **SpecBuilder / vtable** | `extension/spec_builder.py` 或 `_spec.py` | 声明式自动构建插件接口 |
| **两阶段注册** | `kernel/spec/registry.py` | 占位阶段 + 填充阶段 + 公理注入 |

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
| `core/engine.py` | 高 | IBCIEngine，解释器管理层，spawn_interpreter() |
| `core/kernel/registry.py` | 高 | KernelRegistry，运行时对象工厂 |
| `core/kernel/spec/registry.py` | 高 | SpecRegistry + SpecFactory，统一类型描述系统 |
| `core/kernel/spec/specs.py` | 高 | 具体 IbSpec 子类及内置类型原型常量 |
| `core/kernel/axioms/primitives.py` | 高 | 内置类型公理实现（register_core_axioms） |
| `core/kernel/symbols.py` | 中 | Symbol 系统（Symbol.spec 唯一类型字段） |
| `core/runtime/interpreter/execution_context.py` | 高 | ExecutionContextImpl |
| `core/runtime/interpreter/llm_executor.py` | 高 | LLMExecutorImpl，LLM 调用与结果解析 |
| `core/runtime/interpreter/llm_except_frame.py` | 高 | LLMExceptFrame，llmexcept 现场帧 |
| `core/runtime/interpreter/handlers/stmt_handler.py` | 高 | 语句节点处理（含 visit_IbLLMExceptionalStmt） |
| `core/runtime/host/service.py` | 高 | HostService，断点快照/恢复 |
| `core/runtime/host/dynamic_host.py` | 高 | DynamicHost，插件接口层 |
| `core/runtime/host/host_interface.py` | 高 | HostInterface，宿主环境接口注册器 |
| `core/runtime/bootstrap/builtin_initializer.py` | 高 | 内置类型注册与装箱器 |
| `core/compiler/serialization/serializer.py` | 高 | FlatSerializer |
| `core/compiler/scheduler.py` | 高 | 编译调度器，import 注入 |
| `core/base/diagnostics/debugger.py` | 中 | CoreDebugger |
| `core/runtime/module_system/discovery.py` | 高 | ModuleDiscoveryService，插件发现服务 |
| `core/extension/ibcext.py` | 高 | IbPlugin / IbStatefulPlugin / IbStatelessPlugin |
| `ibci_modules/ibci_ai/core.py` | 高 | AI 插件（LLM Provider 核心实现） |
| `ibci_modules/ibci_ihost/core.py` | 中 | HOST 插件实现（核心级） |
| `ibci_modules/ibci_idbg/core.py` | 中 | IDBG 调试插件实现 |

---

## 附录：已知架构问题（历史遗留）

> 以下问题已在代码中发现，将在后续版本中修复。详细技术背景见 ARCH_DETAILS.md。

### A.1 MetadataRegistry 双轨问题

**问题描述**：
- `KernelRegistry.get_metadata_registry()` 在 builtin 初始化时创建（轨A）
- `HostInterface.metadata` 在 discover_all 时创建（轨B）
- 两轨使用同名 `MetadataRegistry` 类，但实例不同，相互独立

**根因**：架构演进中的设计妥协，builtin 类型系统和插件系统分别发展后未及时统一。

**修复方向**：实现 `.ibc_meta` 文件机制，compiler 通过文件获取元数据而非通过 HostInterface 间接访问。

### A.2 HOST 插件游离问题

**问题描述**：
- DynamicHost 是核心接口层实现，`ibci_ihost` 是用户级模块实现，两者对同一宿主能力有双路暴露
- 历史上存在 `run()` vs `run_isolated()` 方法名不一致的问题

**当前架构**：
```
IBCI脚本 ──→ host_run() 内置函数 ──→ DynamicHost ──→ HostService
                (builtin_initializer)    (内核暴露)    (实际执行)

IBCI脚本 ──→ import ihost ──→ ibci_ihost/core.py ──→ HostService
               (ModuleDiscovery)   (插件实现)
```

### A.3 符号去重：import 与用户定义同名冲突

**问题描述**：若用户定义与已导入插件同名的 class/variable，Pass 1 符号收集阶段会与 Scheduler 注入的模块符号冲突。

**临时方案**：在符号表中区分 MODULE 符号和 CLASS 符号。**长期方案**：严格遵循显式引入原则，外部模块符号不预注入到编译时符号表（详见 PENDING_TASKS.md 章节九）。

**涉及文件**：
- `core/kernel/axioms/primitives.py`

---

*本文档为 IBC-Inter 架构原则参考文档，供未来项目参与人员进行架构对齐使用。*
*最后更新：2026-03-25（添加代码审计新增问题附录 B）*
