# IBCI 2.0 核心重构主计划 (Master Refactor Plan)

## 1. 总体进度概要 (Project Status)
目前项目处于 **Phase 4 (第四阶段) 重构的中后期**。地基层 (Domain/Foundation) 已基本完成物理去耦和公理化改造。编译器层 (Compiler) 的净化工作已接近尾声，正在向运行时 (Runtime) 的对齐与同步迈进。

### **已完成里程碑 (Completed)**
- **地基去耦**：实现了 `AxiomRegistry` (行为) 与 `MetadataRegistry` (结构) 的物理分离。
- **编译器净化 (Phase 4.1 部分)**：
    - `Scheduler` 移除了 `TypeBridge` 等遗留逻辑，统一了符号构建。
    - `SemanticAnalyzer` 实现了初步的去字符串化，改用 `is_dynamic()`。
    - 移除了 Domain 层的局部导入，解决了物理循环依赖。
- **意图系统 2.0 启动**：
    - 建立了 `IbIntent` 标准对象并接入 `Bootstrapper`。
    - 解释器初步适配了意图栈管理。

---

## 2. 核心隐患与技术债 (Critical Risks & Debt)
*摘自审计报告 AUDIT_REPORT_DEEP.md & AUDIT_REPORT_COMPILER.md*

1.  **真相源断层 (Truth Gap)**：
    - `ListAxiom` 定义了 `pop`, `clear` 等方法，但运行时 `builtin_initializer.py` 尚未实现这些绑定。
    - **后果**：代码能通过语义分析，但会在运行时因 `Method not found` 崩溃。
2.  **字符串滥用 (String Abuse)**：
    - `SemanticAnalyzer` 和 `builtin_initializer.py` 中仍存在大量 `if "int" in name` 类型的模糊匹配。
3.  **加载链路纠缠**：
    - 解释器仍直接参与产物水化 (Hydration)，缺乏独立的加载层。

---

## 3. 下阶段执行路线图 (Refined Roadmap)

### **Phase 4.2: 运行时同步 (Runtime Synchronization) - 优先级：最高**
- [x] **公理驱动初始化**：重构 `builtin_initializer.py`，遍历 `Axiom.get_methods()` 自动绑定 Python 实现方法。
- [x] **补齐缺失方法**：在 `builtins.py` 中实现 `List.pop`, `List.clear`, `Dict.keys`, `Dict.values`。
- [x] **彻底消除模糊匹配**：
    - 在 `builtin_initializer.py` 中，使用 `is_assignable_to` 或类型 ID 替换 `if "int" in name`。
    - 在 `SemanticAnalyzer` 中，将基于字符串名称的决议逻辑替换为基于 `TypeDescriptor` 原型的直接对比。
- [x] **类型校验强化**：在运行时使用 `is_assignable_to` 替换所有字符串包含检查。

### **Phase 4.3: 架构终极对齐 (Architectural Alignment) - 优先级：高**
- [ ] **强描述符约束**：重构 `Registry.register_class`，强制要求提供 `TypeDescriptor`，拒绝裸类。
- [ ] **独立加载层 (ArtifactLoader)**：将水化逻辑从解释器剥离，实现“不可变执行环境”。
- [ ] **描述符驻留池 (Interning)**：完善 `TypeFactory` 的结构哈希缓存，将类型检查复杂度降至 $O(1)$。
- [ ] **合成类型标准化**：正式实施 `BoundMethodMetadata` 校验，废弃 `startswith` 检查。

### **意图系统 2.0 剩余任务 (Intent System v2)**
- [ ] **语义涂抹 (Smearing)**：重构 Parser，废弃 `IbAnnotatedStmt`，改用侧表绑定。
- [ ] **基座拦截 (Interception)**：在 `BaseInterpreter` 中实现自动化的意图栈压入/弹出。
- [ ] **灵活屏蔽机制**：支持基于 `tag` 的意图动态过滤。

---

## 4. 实施禁令 (Strict Constraints)
- **禁止** 在 Domain/Foundation 层引入任何局部函数内导入。
- **禁止** 在运行时使用字符串匹配作为类型校验的“兜底”方案。
- **禁止** 在 `core/runtime` 之外手动构造描述符，必须通过 `TypeFactory` 获取。
- **优先** 保证编译器产出的蓝图 (Blueprint) 符合 UTS 契约，再修复运行时。

---
*本文件合并了 AUDIT_REPORT, REFACTOR_PLAN, SPEC, PLAYBOOK 等文档，作为接下来的唯一权威指导。*
