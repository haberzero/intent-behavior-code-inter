# IBC-Inter 架构与代码质量审计报告 (2026-03-26)

## 1. 核心架构风险 (待决断)

### 1.1 循环依赖链条 (Circular Dependency)
- **依赖路径**: `Interpreter` (interpreter.py) → `HostService` (service.py) → `RuntimeSerializer` (runtime_serializer.py) → `RuntimeContextImpl` (runtime_context.py) → `Interpreter`。
- **现状**: 系统通过局部 `import` 和 `callback` 勉强维持运行，模块化封闭性极差。
- **修复方案建议**: 引入 `IHostService` 和 `ISerializer` 接口，通过依赖注入 (DI) 解耦具体实现。

### 1.2 实现类泄露与动态宿主架构不一致 (Implementation Leakage & Dynamic Host)
- **现状**: `RuntimeSerializer` 直接引用 `RuntimeContextImpl` 的私有属性，违反 IES 2.1 物理隔离原则。
- **现状**: `InterOpImpl` 直接持有 `HostInterface` 具体实现类，导致解释器层对宿主层有非预期的强感知。
- **动态宿主机制问题**: 
    1. **组件形态不一**: 动态宿主 (Dynamic Host) 实现方式与 `ai`、`idbg` 等标准插件不一致，存在类似 `ai_server` 的格格不入模块，而非标准 `llm_provider` 模式。
    2. **层级混乱**: 解释器本应只负责微观执行，但目前与动态宿主、序列化器等组件耦合过深。
    3. **引用越权**: 动态宿主与序列化器等组件直接或间接持有解释器实例引用，违反了“仅通过上下文/回调交互”的解耦原则。

---

## 2. 架构重构提议：RuntimeScheduler (待评估)

### 2.1 引入 `rt_scheduler` 层
- **定位**: 位于 `core/runtime` 根目录，对应编译器的 `scheduler`。
- **职责**: 
    - 统一管理 `Interpreter`、`RuntimeSerializer`、`DynamicHost` 的生命周期与调度。
    - 持有 `Interpreter` 实例，而其它组件（如动态宿主、序列化器）仅通过 `rt_scheduler` 提供的通知或上下文实例进行交互。
    - 承接 `Engine` 层的指令，处理宏观层面的运行流转（如动态宿主申请创建新实例并跳入）。

### 2.2 解释器纯净化
- **职责**: 仅负责代码层面的微观执行与状态流转。
- **解耦**: 彻底移除对宿主环境、序列化细节的直接感知。

---

## 2. 代码质量问题 (独立修复任务)

### 2.1 AI 客户端初始化冗余 (ibci_ai/core.py)
- **问题**: `__call__` 方法每次调用都会重新实例化 `OpenAI` 客户端。
- **风险**: 高频调用时会导致性能抖动和连接池溢出。
- **修复方案**: 实现客户端单例化/复用逻辑。

### 2.2 提示词硬编码 (llm_executor.py)
- **问题**: 存在 `"你还需要特别额外注意的是："`、`"当前上下文意图："` 等中文字符串。
- **修复方案**: 建议常量化或抽取到配置文件/i18n。

### 2.3 魔术字符串场景 (llm_executor.py)
- **问题**: `("BRANCH", "LOOP", ...)` 硬编码场景名称。
- **修复方案**: 使用 `IbScene` 枚举。

---

## 3. 代码规范问题 (低风险修复)

### 3.1 重复 Import
- **文件**: `llm_executor.py`, `stmt_handler.py` 等。
- **现象**: 分行导入同源接口，如 `from core.runtime.interfaces import LLMExecutor` 和 `from core.runtime.interfaces import IExecutionContext` 分开写。

### 3.2 延迟导入泛滥
- **现象**: 过多使用函数内局部 `import` 规避循环引用，而非从架构上解决。

---

## 4. 健康度总结
- **功能完备性**: 95/100 (MVP 验证通过)
- **符号系统**: 98/100 (UID 链路纯净)
- **架构解耦度**: **65/100 (红色警告)**
- **代码规范性**: 75/100
