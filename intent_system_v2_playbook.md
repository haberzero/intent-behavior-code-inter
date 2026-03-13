# IBC-Inter 意图系统 2.0 重构工作指导书 (Intent System v2 Playbook)

## **1. 核心目标 (Core Objectives)**
- **架构解耦**: 将意图从物理 AST 包装器结构中剥离，转向基于 **UID 绑定 (UID-Binding)** 的侧表存储模式。
- **降维打击**: 通过 **基座拦截 (Base Interception)** 实现意图的自动化管理，消除新增语法的样板代码。
- **极致灵活性**: 支持基于标签（Tag）的精准屏蔽与编程式上下文控制。

---

## **2. 架构设计清单 (Architecture Checklist)**

### **[2.1] Foundation: 领域模型统一**
- [ ] 在 `core.runtime.objects.intent` 中定义 `IbIntent` 类。
- [ ] **关键字段**: `mode` (APPEND/OVERRIDE/REMOVE), `tag` (Optional), `segments` (List[Union[str, IbExpr]]), `raw_content` (str).
- [ ] 移除 `SimpleNamespace` 或 `dict` 形式的零散意图表示。

### **[2.2] Compiler: 语义涂抹 (Smearing) 逻辑**
- [ ] **Parser 调整**:
    - [ ] 废弃 `IbAnnotatedStmt` 和 `IbAnnotatedExpr` 节点类。
    - [ ] `DeclarationComponent` 遇到 `@` 指令时，不生成节点，而是通过 `context.push_pending_intent()` 存入队列。
    - [ ] 确保 `pending_intent` 队列在遇到下一个真正的业务节点（`IbCall`, `IbAssign`, `IbIf` 等）时被“消费”。
- [ ] **Semantic Pass**:
    - [ ] 引入 `node_to_intent` 侧表。
    - [ ] 在 `SemanticAnalyzer` 中，将 `pending_intent` 与当前节点的 `node_uid` 进行绑定。
    - [ ] 验证：即使意图写在 `if` 上方，意图也应绑定到 `IbIf` 的 UID 上。

### **[2.3] Interpreter: 基座自动化拦截**
- [ ] **核心修改**: `interpreter.py` 中的 `BaseInterpreter.visit(node_uid)`.
- [ ] **拦截逻辑**:
    1.  从 `registry.get_intent(node_uid)` 获取绑定意图。
    2.  如果存在，执行 `self.context.push_intent(intent)`。
    3.  执行 `super().visit(node_uid)`。
    4.  `finally` 块中执行 `self.context.pop_intent()`。
- [ ] **验证**: 确保 `visit_IbIf` 内部的 `visit(node.test)` 逻辑能自动继承父节点的意图。

### **[2.4] Runtime: 灵活屏蔽与黑名单机制**
- [ ] **LLMExecutor 重构**:
    - [ ] 重写 `_merge_intents` 逻辑。
    - [ ] 支持 `REMOVE` 模式下的两种匹配：
        - 字符串匹配（匹配 `raw_content`）。
        - 标签匹配（匹配 `tag`）。
- [ ] **AI 组件增强**:
    - [ ] 在 `ai` 内置模块中添加 `mask(tag_pattern)` 方法，向当前栈顶注入一个带有屏蔽语义的特殊 `IbIntent`。

---

## **3. 稳妥性检查点 (Stability Checkpoints)**

### **[3.1] 兼容性测试**
- [ ] 验证函数体内的意图注释是否不再因“空 Body”而瞬间失效。
- [ ] 验证嵌套意图（Global -> Block -> Line）的叠加顺序是否正确。

### **[3.2] 性能与整洁度**
- [ ] 序列化后的 `json` 侧表是否包含 `node_to_intent` 映射。
- [ ] AST 树层级是否显著变浅（扁平化验证）。

### **[3.3] 边界情况**
- [ ] 如果一行代码上方有多个意图，侧表应支持列表存储或自动合并。
- [ ] 意图中的变量引用（`$var`）必须在运行时 `resolve_content` 时才进行插值，禁止 Parser 预合并。

---

## **4. 实施禁令 (Strict Constraints)**
- **禁止** 在每个 `visit_IbXXX` 方法中手动编写意图处理逻辑。
- **禁止** 修改 `IbASTNode` 基类来强加意图属性。
- **禁止** 在未完成 Foundation 层协议对齐前开始修改 Compiler 或 Interpreter。

---

## **5. 负责人签字与下一步**
- **当前状态**: 指导书已就绪。
- **下一步指令**: 开始第一阶段：**[Foundation] 领域模型统一**。
