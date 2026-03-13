# **IBCI 2.0 架构基底对齐规范 (Architectural Alignment Spec) - 终极版**

## **1. 核心愿景 (Vision)**
消除“静态元数据”与“运行时对象”之间的消费断层，将 IBCI 2.0 从“具备强类型检查的动态引擎”升级为“由统一类型系统 (UTS) 驱动的结构化执行环境”。**拒绝任何形式的运行时“兜底”与“回退”**，确立 UTS 描述符作为系统内唯一真理来源。

---

## **2. 核心问题定义与深度审计 (Issues)**

### **[2.1] 运行时校验的双轨制 (Double-track Verification)**
- **现状**：`IbClass.is_assignable_to` 优先尝试 UTS 描述符，失败后回退到 Python 类继承链检查。
- **根源**：`Registry` 允许注册不带描述符的“裸”类，导致插件系统集成不彻底。
- **风险**：**泛型擦除**。回退逻辑无法感知 `list[int]` 等复杂约束，导致运行时安全性降级。

### **[2.2] 解释器职责过载与加载纠缠 (Overloaded Interpreter)**
- **现状**：`Interpreter` 亲自参与 `TypeHydrator` 的初始化，存在局部 Import 避开循环依赖。
- **根源**：执行引擎与产物加载逻辑（Artifact Loading & Hydration）高度纠缠。
- **风险**：架构层次模糊，难以独立测试加载逻辑，波及执行核心稳定性。

### **[2.3] 意图数据模型的非正交性 (Intent Non-orthogonality)**
- **现状**：解释器 `visit_IbIntentStmt` 仍保留对字符串意图的兼容逻辑。
- **根源**：编译器前端在处理简易语法时产出的数据结构不统一。
- **风险**：弱化 IES 2.0 的强类型契约，增加运行时分支复杂度。

### **[2.4] 合成类型的 ad-hoc 处理 (Ad-hoc Synthetic Types)**
- **现状**：`bound_method` 在引导层手动注册，其类型检查依赖 `startswith` 字符串匹配。
- **根源**：UTS 缺乏“合成类型”生成机制，无法描述运行时的动态产物。
- **风险**：类型匹配不精确，无法支持高阶类型匹配和协变/逆变校验。

### **[2.5] 内核引导的“元数据真空期” (Bootstrap Metadata Gap)**
- **现状**：引导阶段先创建类后绑定关系，导致注册时无法即时提供描述符。
- **风险**：破坏“描述符强制化”的普适性，导致内核类成为特殊例外。

---

## **3. 根本性修复方案与全链路逻辑 (Solutions)**

### **[3.1] 强描述符约束协议 (Strict Descriptor Contract)**
- **变更**：重构 `Registry.register_class`，强制要求 `TypeDescriptor` 为必填项。
- **执行**：运行时 `Scope.assign` 发现无描述符的类时，**直接抛出致命错误**。不再支持向前兼容。
- **目标**：运行时类对象必须是其 UTS 描述符的物理镜像。

### **[3.2] 产物加载层彻底剥离 (Artifact Loader Component)**
- **设计**：引入独立的 `ArtifactLoader` 组件作为解释器的前置工序。
- **链路**：`Raw Pools` -> `ArtifactLoader` (含 `TypeHydrator`) -> `Fully Hydrated RuntimeContext` -> `Interpreter`。
- **结果**：解释器不再接触原始池字典，实现真正的“不可变执行环境”。

### **[3.3] 元数据先行引导策略 (Metadata-First Bootstrapping)**
- **对策**：引入 `VirtualDescriptor` 机制。
- **逻辑**：在 `IbClass` 创建前先由 `MetadataRegistry` 生成 Shell 描述符，创建类时即刻注入。引导结束前通过 `reify()` 补全成员元数据。
- **目标**：消除硬编码逻辑，实现内核类与普通类的逻辑归一化。

### **[3.4] 描述符驻留池 (Descriptor Interning)**
- **设计**：在 `core/domain/types` 引入具备缓存机制的 `TypeFactory`。
- **逻辑**：基于结构哈希（Structural Hashing）确保同构描述符（如多次出现的 `list[int]`）在内存中仅存一份。
- **意义**：将类型校验复杂度从 $O(Structural Depth)$ 降低至 $O(1)$ 指针对比。

### **[3.5] 循环水化防御算法 (Cycle Resolution)**
- **协议**：执行“Shell-then-Fill”两阶段加载。
- **逻辑**：`hydrate(UID)` 第一时间创建空 Shell 并入 `memo` 缓存，随后再递归填充成员字段。
- **目标**：确保任意复杂的循环引用图在 $O(N)$ 时间内安全水化，绝不锁死。

### **[3.6] 语义化签名匹配 (Structural Matching)**
- **变更**：定义 `BoundMethodMetadata` 元数据类。
- **算法**：重写 `is_assignable_to`，实现基于协变/逆变（Covariance/Contravariance）的签名匹配，彻底废弃字符串 `startswith` 检查。

---

## **4. 详细实施计划与拆解 (Phases)**

### **Phase 1: 基础设施与内核自举 (Foundation & Bootstrap)**
- [ ] **[1.1] 升级 Registry 契约**：修改 `core/foundation/registry.py`，将 `descriptor` 设为 `register_class` 的必需参数。
- [ ] **[1.2] 实现描述符驻留池**：在 `core/domain/types/descriptors.py` 中增加 `TypeFactory` 和 `interning` 装饰器。
- [ ] **[1.3] 重构 Bootstrapper**：实施“元数据先行”策略，为 `Object`, `Type` 等预生成虚拟描述符。
- [ ] **[1.4] 定义合成类型**：正式加入 `BoundMethodMetadata` 结构定义。

### **Phase 2: 加载链路重塑 (Artifact Loading Layer)**
- [ ] **[2.1] 抽取 ArtifactLoader**：新建 `core/runtime/interpreter/artifact_loader.py`。
- [ ] **[2.2] 升级 TypeHydrator**：应用“Shell-then-Fill”两阶段算法，集成驻留池。
- [ ] **[2.3] 清理 Interpreter 构造函数**：移除所有池解析和局部 Import 逻辑。

### **Phase 3: 编译器与执行期闭环 (Closure & Cleanup)**
- [ ] **[3.1] 意图强制结构化**：修改 `FlatSerializer`，确保 `node_intents` 侧表只包含结构化对象。
- [ ] **[3.2] 移除兼容代码**：删除 `interpreter.py` 中所有的字符串意图处理和 `IbClass` 的继承链回退逻辑。
- [ ] **[3.3] 升级赋值断言**：在 `runtime_context.py` 中实施断裂式强校验。

---

## **5. 风险与约束 (Constraints)**
- **兼容性**：**明确放弃**对旧插件的二进制或源代码兼容。
- **性能**：由于引入了 Interning 和 强断言，加载期耗时可能略增，但执行期类型检查性能将提升。
- **开发约束**：禁止在 `core/runtime` 之外手动构造描述符，必须通过 `TypeFactory` 获取。
