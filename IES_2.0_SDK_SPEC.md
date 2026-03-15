# IBCI 2.0 插件 SDK 与 职责下放演进指南 (IES 2.0 SDK SPEC)

## 1. 核心架构：职责下放与能力注入 (Delegation & Injection)
在 IES 2.0 体系中，内核不再主动适配插件的 Python 原生行为。相反，插件通过 **IBCI-SDK (Capabilities)** 接口，主动声明并转换其 Python 逻辑，使其符合 UTS 2.0 契约。

### 1.1 核心转变
- **从“猜测”到“声明”**：内核不再尝试自动猜测 Python 原生类型的 IBCI 身份。
- **从“耦合”到“注入”**：核心插件（AI, IDbg, Host）通过“能力契约”与内核通信，而非直接访问内核私有对象。
- **从“魔法”到“虚表”**：废弃所有装饰器拦截，统一使用显式 `get_vtable` 映射。

---

## 2. 系统级核心扩展适配 (System-Level Extensions)

针对与内核有高度紧密联系的插件（AI, IDbg, 动态宿主），采用 **“基于能力的双向注入”** 模式：

### 2.1 AI 模块 (LLM Provider)
- **协议认领**：在 `setup(capabilities)` 中，插件通过 `capabilities.llm_executor.set_provider(self)` 认领供应者身份。
- **平权调用**：内核通过标准的 `ILLMProvider` 接口与插件通信，实现 AI 实现的可插拔性。

### 2.2 IDbg 模块 (Kernel Observer)
- **权限契约**：在 `_spec.py` 中声明 `required_capabilities=["STACK_INSPECTOR", "STATE_READER"]`。
- **受控观察**：内核注入只读的 `IStackInspector` 视图。插件只能“观察”而不能“篡改”内核，实现权限最小化。

### 2.3 动态宿主 (Host Service)
- **双向平权**：宿主服务的方法通过 `get_vtable` 正式注册为 `IbNativeFunction`。
- **自动转化**：宿主返回的复杂 Python 数据结构，在进入 IBCI 作用域时，由 SDK 的 `box()` 机制根据公理化字典自动转化为 IbDict/IbList，确保脚本中 `.len()`, `.get()` 等方法立即可用。

---

## 3. 插件 SDK 接口设计 (ExtensionCapabilities)

### 3.1 核心方法定义
```python
class ExtensionCapabilities:
    # --- 类型转换与装箱 (Boxing) ---
    def box(self, value: Any) -> IbObject:
        """
        [IES 2.0 Core] 将 Python 原生对象转换为 IBCI 对象。
        - 严格模式：仅在 STAGE_4 及之后可用。
        - 自动识别原生基础类型 (int, str, bool, list, dict)。
        - 自动将 Python 基础容器包装为具备公理能力的 IbDict/IbList。
        """
        pass

    # --- 自定义类型注册 ---
    def register_type(self, py_class: type, descriptor: TypeDescriptor):
        """
        [IES 2.0 Extension] 将自定义 Python 类注册进 UTS 体系。
        - 仅允许在 STAGE_4 阶段调用。
        - 实现 Python 类与 _spec.py 描述符的双向映射。
        """
        pass
```

---

## 4. 内核演进步骤 (Evolutionary Steps)

### 第一阶段：状态机与 SDK 增强
- [ ] 在 `core/foundation/registry.py` 中实现 `RegistrationState` 状态机。
- [ ] 在 `ExtensionCapabilities` 中增加状态断言，确保 `box()` 调用时机合法。
- [ ] 增加 `StageTransitionError` 处理，将静默失败转化为致命断言。

### 第二阶段：ModuleLoader 的“不妥协”重构
- [ ] **虚表隔离检查**：Loader 在加载插件前检查其是否持有旧的虚表，防止测试环境中的单例污染。
- [ ] **拦截器重构**：修改 `ModuleLoader._validate_and_bind`，强制要求 `get_vtable` 并验证其与 `_spec.py` 的对齐度。
- [ ] **自动装箱代理 (Proxy VTable)**：由 Loader 统一拦截返回值，应用 `box()`。

### 第三阶段：解决重水合与循环依赖
- [ ] **两阶段重水合**：在 `MetadataRegistry` 中实现 Shell/Fill 分离加载。
- [ ] **移除猜测逻辑**：彻底清理 `registry.py` 中所有带 `getattr` 默认值的兜底。

---

## 5. 检查清单与要点规定 (Checklist & Requirements)

### 5.1 插件开发者规定
- [ ] **禁止**：禁止直接引入 `core.runtime` 等内核私有模块。
- [ ] **强制**：所有与内核的交互必须通过 `capabilities` 进行。
- [ ] **强制**：必须实现 `get_vtable()` 以暴露接口。
- [ ] **强制**：`_spec.py` 不得引用 `core.py`。
- [ ] **测试环境**：在单元测试中，如果使用了 Mock 或缓存插件，必须确保在 `setUp` 中通过 `Registry` 重置虚表绑定。

---
**规范版本：** v2.2.0 (2026-03-15)
**状态：** 实施中
