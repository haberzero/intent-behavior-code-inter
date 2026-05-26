# PENDING_TASKS — 阻塞 / 待前置任务

> 本文档**只**记录有明确前置条件、暂不能开工的事项；其余非阻塞低优先级想法不在此处维护。
> 当前最紧要项见 `docs/NEXT_STEPS.md`；已完成事项见 `docs/COMPLETED.md`。
>
> **最后更新**：2026-05-26（清理已完成的 PT-ARCH 系列 + PT-4.6；移除空占位节）

---

## 一、闭包写回语义（PT-CLOSURE 系列）

### PT-CLOSURE-1　`nonlocal` 关键字支持 [P1，前置条件已满足]

**前置条件**: ✅ P0-A/B 已完成，Cell 基础设施稳定。

**问题描述**（2026-05-26 代码验证）：

IBCI 编译器将函数体内的赋值目标一律视为本地变量声明。当内部函数试图修改外部作用域变量时：
```ibci
func make_counter() -> list[fn]:
    int count = 0
    func inc() -> int:
        count = count + 1   # ← 编译器创建 inc:count 局部符号，RUN_003
        return count
    ...
```
SymbolCollectionPass 在 `inc` 作用域创建新符号 `inc:count`，导致运行时未初始化错误。

**解决方案（推荐方案 A：`nonlocal` 关键字）**：

| 层 | 改动 |
|----|------|
| Lexer | 新增 `nonlocal` 关键字 token |
| Parser | 新增 `IbNonlocalStmt(names: List[str])` AST 节点 |
| SymbolCollectionPass | 遇到 `nonlocal x` 时，不为 `x` 创建本地符号，改为向上查找外部符号并建立引用 |
| SymbolResolutionPass | 对已标记 nonlocal 的名称，解析到外部符号的 UID |
| LambdaCaptureAnalyzer | 标记 nonlocal 变量为需要 Cell 提升（write-back） |
| Runtime (vm_handle_IbAssign) | 对 nonlocal 标记的变量，赋值时写入 Cell（而非本地符号） |

**预估工作量**: 8-12 小时

**备选方案**：
- 方案 B（自动推断）：违背 IBCI "显式 > 隐式" 设计原则，不推荐
- 方案 C（无 nonlocal，仅通过 lambda 只读捕获覆盖场景）：保持现状，将 INV-CONTEXT-2 标记为设计限制

---

## 二、Semantic 后续任务（PT-SEM 系列）

### PT-SEM-1　语义分析生产就绪化 [P2]

**前置条件**:
- Semantic pipeline 已作为唯一分析路径稳定运行 ✅

**任务内容**:
- 性能优化（如有必要，基于实际性能对比数据）
- 错误信息优化（提升可读性和可操作性）
- 调试工具（可视化符号表、类型绑定、依赖图）
- CI/CD 集成（自动运行语义分析测试套件）

**预估工作量**: 15-20 小时

### PT-SEM-2　Semantic 后续清理 [P3]

**前置条件**:
- PT-SEM-1 完成
- Semantic pipeline 稳定运行 ≥ 1 个月

**任务内容**:
1. 精简 `CompilationResult` 字段（MetadataStore 三张核心绑定）
2. 清理技术债务（包括 `core/kernel/blueprint.py` 字段精简）

**预估工作量**: 10-15 小时

### PT-SEM-3　二层 IR 路线评估 [VISION]

**前置条件**: PT-SEM-2 完成，单 IR 流水线稳定运行 ≥ 1 个月。

**任务内容**:
- 评估是否要把"AST 规整阶段"（llmexcept 重排、intent 注解附着等）从 Semantic 中剥离出来，产出独立的"结构 IR"。
- Semantic 在结构 IR 上做分析；序列化器输出"执行 IR"。

**为什么搁置**: 当前 IBCI 体量下尚不必做；只有当行为依赖图/intent 分析继续扩展（LLM 调用计费/调度优化等）才会成为必经之路。

---

## 三、待 VM 信号 / 中断 / 异步机制（L3 协程）成熟后才能继续

### PT-3.1　host.run_isolated() 返回值改进 [VISION]
### PT-3.2　ReceiveMode 枚举演进 [VISION]

---

## 四、语言级语义/语法收尾（暂搁置）

### PT-4.1　Enum "非 str 成员"与迭代/序数能力 [VISION]

**现状**：仅支持 str 成员；`EnumAxiom` 实现完整的 `from_prompt`/`__outputhint_prompt__` 能力。不支持 `for v in Color:` 迭代。

**为什么搁置**：与 LLM 输出约定耦合，现有 str 成员能力对绝大多数 LLM 集成已足够。

### PT-4.2　可调用类实例（`__call__` 协议）类型推断 [VISION]

**现状**：编译期识别 `obj()` 语法；运行时通过 vtable 分发。已知灰区：`__call__` 内 intent 合并规则、callable-instance 与 `fn` 兼容性。

**为什么搁置**：触及类型系统兼容性轴（class ↔ callable），用户可用普通方法 + lambda 包装替代。

### PT-4.3　语言级协程（L3）[VISION]

**现状**：VM 单任务调度器；无 async/await/yield 关键字；并发仅限 `dispatch_eager` 后台 LLM 请求。

**为什么搁置**：牵涉调度器架构、关键字系统、快照协议三个独立维度。PT-3.1/3.2 以此为前置。

### PT-4.4　用户类泛型类型参数 [VISION]

**现状**：无 `class Box[T]:` 语法；泛型仅覆盖 axiom 内置类型。

**为什么搁置**：`any` 兜底 + axiom 泛型已覆盖绝大多数用例。

### PT-4.5　用户类运算符重载 [VISION]

**现状**：dunder 协议仅覆盖 `__init__`/`__call__`/`__to_prompt__`/`__from_prompt__`/`__outputhint_prompt__`/`__snapshot__`/`__restore__`。

**为什么搁置**：涉及类型系统兼容性轴 + 编译期方法分派两个独立维度。

### PT-4.7　DDG 并行调度真正接入 VM [DESIGN-DEBT]

**现状**：编译期 `BehaviorDependencyAnalyzer` 已计算 `llm_deps`/`dispatch_eligible`；运行时全同步执行。

**为什么搁置**：错配快照/future 解引用顺序会破坏 retry 隔离语义。

---

## 五、明确排除的方向

- 不引入静态类型检查器作为解释器前置强依赖。
- 不以牺牲运行时可观测性换取短期性能优化。
- 不为优化同一程序内独立 LLM 调用而创建多 Interpreter（这是 L1 流水线的职责）。
- **不允许同一份语义事实在 AST 字段 + 侧表 + MetadataStore 中出现多份副本**（"双写真相"）。
- **不引入完整的约束求解/HM 风格类型推断**——但允许从相关理念中汲取受控的设计思路（如 TypeSlot 单次锁定延迟绑定）。
