# IBCI 2.0 架构全方位验证指导书 (Verification Guide)

## 1. 验证原则 (Principles)
- **地基先行 (Foundation First)**：严禁在 Domain/Foundation 层未通过验证前进行 Compiler 或 Runtime 的测试。
- **物理隔离 (Physical Isolation)**：测试必须利用 Registry 的实例隔离特性，确保不同测试用例之间无元数据污染。
- **零字符串魔法 (Zero String Magic)**：所有类型校验必须基于描述符的对象标识 (Object Identity)，而非名称字符串。
- **小步慢走 (Small Steps)**：每个验证阶段拆分为微小的任务单元，确保逻辑链条的绝对可靠。

---

## 2. 第一阶段：Domain & Foundation (地基稳固性) - [已通过]
**目标**：确保 UTS (统一类型系统) 和公理注册机制的绝对纯净与正确。

### **2.1 UTS 描述符验证**
- [x] **唯一性 (Uniqueness)**：通过 `TypeFactory` 创建的相同结构描述符（如 `list[int]`）在同一引擎实例内必须具有相同的内存地址。
- [x] **物理独立性**：验证 `TypeDescriptor` 在不导入 `Symbol` 的情况下能完成基本定义，且 `is_assignable_to` 逻辑不依赖字符串。
- [x] **解包正确性**：验证 `LazyDescriptor` 在多层嵌套下能正确通过 `unwrap()` 还原为原始描述符。

### **2.2 公理系统 (Axioms) 验证**
- [x] **能力发现**：验证各基础公理（Int, List, Exception 等）能正确返回其预定义的方法元数据字典。
- [x] **解析能力**：验证 `ParserCapability` 能正确处理字符串到原生值的转换，且不产生意外侧效应。

### **2.3 注册表 (Registry) 强契约验证**
- [x] **令牌防护**：验证非法令牌（Unauthorized Token）无法调用内核级注册接口。
- [x] **描述符一致性**：验证注册类时，若类名与描述符名不匹配，系统必须抛出 `ValueError`。
- [x] **水化机制 (Hydration)**：验证从公理注入的方法元数据能自动递归绑定到当前注册表实例。

---

## 3. 第二阶段：Compiler (编译器净化) - [已通过]
**目标**：确保 AST 结构纯净，且语义分析侧表完整覆盖了所有涂抹信息。

### **3.1 Parser 扁平化验证**
- [x] **去包装化**：验证意图简写（如 `@ "intent"`）解析后不再产生 `IbAnnotatedStmt`，而是直接产生主体语句节点。
- [x] **暂存正确性**：验证意图信息被正确暂存在节点的私有属性 `_pending_intents` 中。

### **3.2 SemanticAnalyzer 侧表验证**
- [x] **语义涂抹 (Smearing)**：验证 `visit` 后，`node_intents` 侧表正确记录了节点关联的全部意图链。
- [x] **类型标识匹配**：验证类型推导侧表存储的是描述符对象引用，而非名称字符串。
- [x] **泛型深度决议**：验证 `list[dict[str, int]]` 等复杂嵌套泛型能正确递归决议为唯一的描述符对象。
- [x] **绑定方法合成**：验证实例成员访问（`.speak()`）能正确合成 `BoundMethodMetadata` 并注入 Receiver。

### **3.3 序列化完整性 (Serialization) 验证**
- [x] **UID 链路一致性**：验证 `FlatSerializer` 产出的 JSON 中，侧表的 UID 引用能 100% 还原为池中的物理对象。
- [x] **元数据池闭环**：验证 `symbols` 池与 `types` 池之间的交叉引用在扁平化后依然保持逻辑闭环。

---

## 4. 第三阶段：Runtime & Interpreter (运行时对齐) - [已通过]
**目标**：确保运行时实现与公理定义的契约完全对齐，支持物理隔离执行。

### **4.1 加载层 (ArtifactLoader) 验证**
- [x] **水化还原 (Re-Hydration)**：验证 `TypeHydrator` 能将序列化产物中的 UID 还原为当前解释器 Registry 中的物理描述符实例。
- [x] **符号表重建**：验证解释器加载器能根据 `symbols` 池重建运行时符号表，并保持与编译器阶段一致的 UID 映射。

### **4.2 自动化绑定与执行**
- [x] **公理方法动态绑定**：验证 `ArtifactLoader` 能根据描述符关联的公理定义，自动将 Python 原生实现（如 `list.append`）绑定到运行时对象。
- [x] **行为描述行延迟执行**：验证 `node_is_deferred` 侧表标记的节点在运行时被正确包裹为 Lambda/Closure，实现真正的延迟推断。
- [x] **物理分离启动 (Physical Isolation)**：通过清空 `core/__init__.py` 并重构 `BaseFlatSerializer`，验证解释器在不加载任何 `core.compiler` 模块的情况下即可独立运行。

### **4.3 逻辑细节与边界覆盖**
- [x] **意图系统深度验证**：通过 [test_comprehensive_interpreter.py](file:///c:/myself/proj/intent-behavior-code-inter/tests/runtime/test_comprehensive_interpreter.py) 验证了意图的堆栈叠加、`!` 排他模式、`@-` 移除模式以及行级意图 (`@`) 的正确涂抹与恢复。
- [x] **内置公理方法健壮性**：验证了 `list`、`dict`、`str`、`int` 等内置方法在 `unbox=False` 模式下的自适配解包逻辑，确保了 `IbObject` 图的纯净性。
- [x] **OOP 继承与绑定**：验证了运行时对类继承链的正确遍历、方法重写（Overriding）以及绑定方法（Bound Method）的闭包特性。
- [x] **两阶段注册机制**：在 [factory.py](file:///c:/myself/proj/intent-behavior-code-inter/core/domain/factory.py) 中引入两阶段注册，解决了循环依赖下的类型水化（Hydration）失效问题。

---

## 5. 验证工具与环境
- **测试框架**：必须使用 `python -m unittest` 执行。
- **环境隔离**：每个测试类必须在 `setUp` 中创建全新的 `Registry` 和 `MetadataRegistry` 实例。
- **失败定义**：任何 `DeprecationWarning` 或未拦截的局部导入均视为验证失败。
