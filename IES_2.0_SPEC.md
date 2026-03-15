# IBCI 2.0 插件系统演进规范 (IES 2.0 SPEC)

## 1. 概述 (Overview)
IBCI 2.0 插件系统（Intent-Extension System 2.0）是基于 **UTS 2.0 (Unified Type System)** 和 **物理分离架构** 的核心扩展机制。本规范旨在彻底消除历史包袱，实现插件与内置函数在技术实现上的完全平权，同时保持开发模式的纯净性。

## 2. 核心设计原则 (Design Philosophy)
- **元数据先行 (Metadata First)**：编译器仅通过静态描述符识别插件能力，不触发任何 Python 逻辑加载。
- **显式契约 (Explicit Contract)**：废弃所有 `Decorator-based`（基于装饰器）的魔法注册，改用显式虚表映射。
- **按需权限 (On-demand Permissions)**：插件通过元数据声明所需权限，内核根据契约进行受控注入。
- **物理分离 (Physical Isolation)**：插件逻辑与 IBCI 内核代码在物理层面无直接依赖。

## 3. 插件物理布局 (Physical Layout)
标准插件目录必须遵循以下三层分离结构：

```text
ibc_modules/[plugin_name]/
├── _spec.py          # [静态契约] UTS 描述符定义，编译器专属。
├── core.py           # [逻辑实现] 纯净的 Python 类与函数实现。
├── providers.py      # [可选] 辅助组件或第三方库封装。
└── __init__.py       # [加载门面] 仅负责导出实现实例或工厂。
```

### 3.1 `_spec.py` 细节要求
- **命名规范**：必须以下划线开头，明确其“内核私有”属性。
- **职责**：定义 `ModuleMetadata`。
- **禁止项**：禁止在该文件中引入 `core.py` 或执行任何耗时逻辑。
- **示例**：
  ```python
  from core.domain.types.descriptors import ModuleMetadata, FunctionMetadata

  metadata = ModuleMetadata(
      name="idbg",
      required_capabilities=["STACK_INSPECTOR", "SIDE_TABLE_ACCESS"],
      members={
          "vars": FunctionMetadata(name="vars", param_types=[], return_type="dict"),
          "env": FunctionMetadata(name="env", param_types=[], return_type="dict")
      }
  )
  ```

### 3.2 `core.py` 细节要求
- **职责**：承载插件的真实 Python 逻辑。
- **显式注册接口**：必须实现 `get_vtable(self) -> Dict[str, Callable]`。
- **权限接收**：通过 `setup(self, capabilities)` 接收内核注入。
- **示例**：
  ```python
  class MyPlugin:
      def setup(self, capabilities):
          self.ctx = capabilities.service_context

      def my_native_method(self, *args):
          return "Hello from Native"

      def get_vtable(self):
          return {
              "greet": self.my_native_method
          }
  ```

### 3.3 `__init__.py` 细节要求
- **职责**：作为 `ModuleLoader` 的发现入口。
- **规范**：仅允许导出 `implementation` (实例) 或 `create_implementation` (工厂)。

## 4. 注册生命周期与状态机 (Registration Lifecycle & State Machine)
为了彻底消除循环引用带来的不确定性，并确保插件系统的安全性，IES 2.0 引入严格的六阶段注册状态机。

### 4.1 状态阶段定义
| 阶段 | 状态名称 | 职责描述 | 严格限制与边界 |
| :--- | :--- | :--- | :--- |
| **STAGE 1** | `BOOTSTRAP` | 注册 Python 基础原生类（`int`, `str`, `dict` 等）。 | 此时 IBCI 概念尚未建立，禁止任何业务逻辑。 |
| **STAGE 2** | `CORE_TYPES` | 注入 IBCI 内置基础类契约（Axioms）。 | `IbInteger`, `IbString` 等与 UTS 描述符完成初步绑定。 |
| **STAGE 3** | `PLUGIN_METADATA` | 扫描并加载所有插件的 `_spec.py`。 | **禁止加载插件实现（core.py）**，只准加载元数据。 |
| **STAGE 4** | `PLUGIN_IMPL` | 加载插件实现并执行 `setup(capabilities)`。 | 强制校验实现是否符合 STAGE 3 契约。不符则直接报错。 |
| **STAGE 5** | `HYDRATION` | 加载用户代码产物并执行类型重水合。 | 所有引用类型必须在 STAGE 2/3 已存在。找不到即报错。 |
| **STAGE 6** | `READY` | 解释器状态封印，开始执行。 | 禁止任何形式的动态类型注册或契约修改。 |

### 4.2 状态跃迁规则
- **单向性**：状态只能按顺序向前跃迁，不可回溯。
- **原子性**：任何阶段失败都必须导致整个引擎初始化中断，严禁“带病运行”。
- **阶段门禁 (Stage Gatekeeper)**：访问历史阶段产出的数据是允许的（通过 `verify_state_at_least`），但严禁超前访问未就绪阶段的数据。

## 5. 类型重水合机制 (Type Re-hydration Mechanism)
水合是连接静态编译产物与运行时对象的桥梁。

### 5.1 两阶段加载协议
1.  **Phase 1: 外壳创建 (Shelling)**：遍历 `type_pool`，为每个 UID 创建描述符“空壳”（如 `ClassMetadata`）。此时不填充成员，仅在 `MetadataRegistry` 占位，解决循环引用。
2.  **Phase 2: 详细填充 (Filling)**：在所有外壳存在后，递归连通引用关系（填充 `element_type` 等）。

### 5.2 严格查找原则 (No-Guessing Rule)
- **禁止猜测**：若水合过程中发现未定义的类型 UID，严禁回退到 `Any` 或猜测为 `Primitive`。
- **确定性来源**：所有类型必须追溯到内置 Axioms 或已注册插件的 `_spec.py`。
- **致命断言 (Fatal Assertion)**：在 `STAGE 4` 及之后，若基础协议类（如 `callable`）缺失，系统必须立即抛出 `StageTransitionError`，而非产生 `None` 引用。

## 6. 内核集成与加载流程 (Integration & Loading)

### 6.1 静态扫描阶段 (Static Scan)
1. `ModuleDiscoveryService` 扫描 `ibc_modules/` 目录。
2. 发现目录后，仅加载 `_spec.py` 中的 `metadata`。
3. 编译器将元数据注册到当前 `MetadataRegistry`，完成类型占位。

### 6.2 动态加载阶段 (Runtime Load)
1. `ModuleLoader` 导入插件的 `__init__.py`。
2. 获取实现对象，调用 `get_vtable()` 获取映射关系。
3. **签名对齐校验**：Loader 自动校验 `vtable` 的映射是否覆盖了 `_spec.py` 中声明的所有成员。
4. **自动装箱代理 (Proxy VTable)**：
   - **参数拆箱**：进入插件前自动将 `IbObject` 转为 Python 原生类型。
   - **结果装箱**：插件返回后自动应用 `capabilities.box()` 包装为 `IbObject`。
5. **虚表封印与隔离**：
   - 每个插件实例在加载时必须绑定当前引擎的 `Registry`。
   - 严禁跨引擎复用已关联 `_ibci_vtable` 的插件对象，检测到跨引擎渗透必须抛出 `RegistryIsolationError`。

## 7. 权限与能力注入协议 (Capability Injection)
插件通过 `setup(capabilities: ExtensionCapabilities)` 接收特权：
- **职责下放 (Responsibility Delegation)**：插件通过 `capabilities.box()` 自行决定数据如何包装。
- **核心能力**：`STACK_INSPECTOR` (栈内省), `INTENT_MANAGER` (意图管理), `STATE_READER` (状态只读)。

## 8. 严格契约与报错准则 (Strict Contract & Error Reporting)
IES 2.0 坚决反对“温柔”的兜底机制。

### 8.1 禁用项清单
- **禁止使用 `getattr(obj, name, default)`**：访问虚表成员必须使用明确的 key 访问，缺失必须抛出 `AttributeError`。
- **禁止静默回退**：元数据缺失、签名不匹配、权限未声明等情况必须立即抛出 `InterpreterError`。
- **禁止局部 import**：Loader 等运行时核心严禁在函数内使用局部 import 避开依赖检查。

### 8.2 错误类型定义
- `ContractViolationError`：实现与 `_spec.py` 声明不符。
- `StageTransitionError`：违反注册生命周期顺序。
- `CapabilityAccessError`：尝试访问未在元数据中声明的权限。

## 9. 实施步骤 (Implementation Steps)

### 阶段 1：内核协议与状态机
- [ ] 在 `Registry` 中引入 `RegistrationState` 枚举及状态校验逻辑。
- [ ] 实现 `MetadataRegistry` 的两阶段水合逻辑。
- [ ] 增强 `ModuleLoader` 强制执行 `get_vtable` 并实现 `Proxy VTable`。

### 阶段 2：移除防御性代码
- [ ] 审计 `kernel.py`，移除所有非引导必需的 `getattr` 兜底。
- [ ] 审计 `loader.py`，移除所有静默失败的逻辑。

### 阶段 3：现有插件平移
- [ ] **idbg 重构**：应用三层分离，利用 `capabilities` 进行栈内省。
- [ ] **ai 重构**：利用 `capabilities.box()` 实现复杂返回值的自动装箱。

### 阶段 4：测试验证
- [ ] 编写状态机跃迁测试：验证在 `READY` 状态后尝试注册插件是否被拦截。
- [ ] 编写安全性测试：验证未声明权限的插件无法获取 `stack_inspector`。

---
**版本控制：**
- v2.0.0 (2026-03-14): 初始版本，完全适配 UTS 2.0 架构。
