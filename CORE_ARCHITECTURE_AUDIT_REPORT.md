# IBC-Inter 核心架构深度审计报告 (IES 2.1 Final Audit)

## 1. 原始核查结论 (Subagent Raw Conclusions)

### 1.1 循环导入与非合规局部导入 (Subagent 1 & 5)
*   **[结论]** 识别出多处为了切断循环引用而被迫采用的局部导入，部分属于“架构穿透”违规：
    *   **插件层向内核的“非法回溯”**：
        *   `ibc_modules/ai/core.py:L166`、`ibc_modules/net/__init__.py:L22`、`ibc_modules/schema/__init__.py:L38`：在 `__call__` 或插件方法内局部 `from core.domain.issue import InterpreterError`。
        *   **性质**：架构穿透。插件层本应通过 SDK 提供的抽象接口或 `capabilities` 容器抛出异常，目前的做法是直接穿透核心定义，且为了规避 `core -> ai -> core` 的循环引用而被迫在函数内导入。
    *   **内核组件间的“权宜之计”**：
        *   `tests/base.py:L216`：在 `run_code` 内局部导入 `FlatSerializer`。
        *   **性质**：逻辑断层。这反映了测试框架与编译器工具链之间的依赖图谱尚未理清，被迫在运行时动态加载以避开静态循环。

### 1.2 插件系统深度逻辑缺陷 (Subagent 2 & 6)
*   **[结论]** 插件体系存在严重的“空心化”风险，导致插件被迫进行非合规导入：
    *   **虚表（VTable）生成断层**：
        *   `loader.py:L34` 强制要求插件实现 `get_vtable()`，但 `host`、`sys`、`file` 等核心插件大量使用 `@ibci.method` 装饰器却并未提供该方法。这会导致插件在加载阶段直接崩溃，或迫使开发者通过局部导入内核组件来手动拼凑虚表。
    *   **能力注入契约失效**：
        *   `sys/__init__.py:L9` 和 `host/__init__.py:L13`：其 `setup` 方法签名不符合 `ModuleLoader` 的强制要求（必须包含 `capabilities` 参数名）。这种“摇摆不定”的实现直接导致了插件系统无法闭环。
    *   **SDK 隔离性不足**：
        *   插件无法在不导入 `core` 的情况下定义错误、获取服务或操作权限。

### 1.3 硬编码与 UTS 体系旁路 (Subagent 3 & 7)
*   **[结论]** 底层设施仍存在大量“纯字符串”驱动的逻辑：
    *   **类型标签硬编码**：`builtins.py:L51` 等处的调试序列化使用了 `"Integer"`、`"String"` 等。这绕过了 `TypeDescriptor.name`（系统公理名为 `int`）。这种不一致性会导致调试器与元数据注册表脱节。
    *   **类型转换硬路径**：`converters.py:L26` 仍在使用 `is STR_DESCRIPTOR` 进行判定。在 IES 2.1 多引擎隔离下，描述符会被克隆，基于地址的 `is` 判定会失效，必须改为基于公理契约的 `is_assignable_to()`。
    *   **协议消息原子性**：`'__call__'`、`'__getattr__'` 等在 `kernel.py:L47` 中有硬编码的特殊拦截逻辑。虽然作为消息名是合理的，但拦截逻辑应下沉至公理层。

### 1.4 架构不确定性实锤 (Subagent 4 & 8)
*   **[结论]** 注释中透露出的不确定性表明系统在关键模型上仍有架构欠账：
    *   **`IbBehavior` 的“奇异点”**：`builtins.py:L295` 抛出 `Behavior cannot execute itself.`。这破坏了“一切皆对象”的原则，导致调试工具（如 `idbg`）在扫描包含行为的对象成员时会触发 `RuntimeError` 崩溃。
    *   **变量遮蔽 (Shadowing) 缺失**：由于编译器为了简化闭包逻辑而复用 `Symbol` 实例，导致内外层变量在“扁平池”中共享同一个 UID，目前系统无法支持真正的变量遮蔽。
    *   **防御性 Hack**：`scheduler.py:L345` 显式承认 `re-lex` 是“纯粹的防御机制”，反映了系统对缓存同步模型的不信任。

---

## 2. 维修建议 (Maintenance Suggestions)

### 2.1 插件系统 SDK 化 (SDK Solidification)
*   **统一异常网关**：在 `core/extension/sdk.py` 中导出统一的异常基类，插件仅允许继承该基类，禁止直接引用 `core.domain.issue`。
*   **自动化虚表生成**：重构 `@ibci.module` 装饰器，利用元编程在类加载时自动根据 `@ibci.method` 扫描并生成符合 `get_vtable()` 契约的字典。
*   **标准化 Setup 契约**：强制所有插件遵循 `setup(self, capabilities: ExtensionCapabilities)` 签名。

### 2.2 UTS 契约全面公理化
*   **消除身份判定**：将 `converters.py` 中所有的 `is XXX_DESCRIPTOR` 替换为 `is_assignable_to()` 或基于公理名称的判定。
*   **协议下沉**：将 `kernel.py` 中对 `__call__` 等魔术消息的特殊处理逻辑转移到对应的 `CallCapability` 公理实现中。
*   **序列化标准化**：修改 `builtins.py` 中的调试序列化，强制通过 `obj.ib_class.name` 获取类型标签，严禁使用硬编码字符串。

### 2.3 核心模型补完
*   **行为自愈**：修改 `IbBehavior.receive`，使其在收到查询类消息（如获取元数据）时不再崩溃，仅在尝试“执行行为本身”且无上下文时才限制。
*   **作用域重构**：引入 `ScopeUID` 概念，将变量的标识由 `(name)` 升级为 `(name, scope_depth)`，以支持真正的变量遮蔽。

---

## 3. 风险评估 (Risks)
*   **循环依赖爆发**：在切断局部导入、进行协议化重构的过程中，如果层级划分不当，极易引发大规模的静态循环导入错误，导致系统无法启动，可接受，系统正在进行深度清理，清理完毕后可以恢复健康。
*   **插件兼容性破碎**：强制标准化 `setup` 签名和 `get_vtable` 会导致现有所有未适配的插件（如 `host`, `sys` 等）暂时不可用，可接受，插件系统和现有插件本就在后续的进一步完善清单中。
*   **性能损耗**：将硬编码的字符串比对或身份判定改为基于公理的能力探测，在超大规模对象访问场景下可能会有轻微的 CPU 开销增加，可接受，llm调用的开销远远大于此。

---

## 4. 涉及文件 (Involved Files)
*   **内核层**：
    *   `core/runtime/objects/kernel.py`
    *   `core/runtime/objects/builtins.py`
    *   `core/runtime/support/converters.py`
    *   `core/runtime/module_system/loader.py`
*   **领域层**：
    *   `core/domain/ast.py`
    *   `core/domain/symbols.py`
    *   `core/domain/factory.py`
*   **扩展层**：
    *   `core/extension/sdk.py`
    *   `ibc_modules/*/core.py`
    *   `ibc_modules/*/__init__.py`

---

## 5. 维修代价 (Maintenance Cost)
*   **工作量**：预计需要 3-5 个完整迭代周期。
*   **影响范围**：覆盖了从 Parser 到 Interpreter 再到所有外部插件的链路。
