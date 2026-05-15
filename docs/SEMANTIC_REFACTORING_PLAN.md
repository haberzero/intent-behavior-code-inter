# IBCI Semantic Analyzer 重构计划

**创建日期**: 2026-05-13
**最后更新**: 2026-05-15（与 `docs/ARCHITECTURE_REVIEW_2026-05-15.md` 立场对齐：MetadataStore 字段收敛、删除"AST 不放分析结果"误导口号、明确 llmexcept 双通道绑定）
**状态**: 规划中（v2 当前未挂到 scheduler；具体下一步见 `docs/NEXT_STEPS.md`）
**优先级**: P0（高优先级架构改进）

---

> **2026-05-15 立场更新（必读，覆盖本文档其余段落中可能与之冲突的描述）**
>
> 1. **AST 是唯一可序列化的真相**。结构性产物（`llm_deps`、`dispatch_eligible`、`free_vars`、`llmexcept_handler`、`IbLLMExceptionalStmt.target`、`capture_mode`、`is_callable_instance`、`target_type_name` 等）**必须**写在 AST 字段上。**不**写到 MetadataStore；**不**写到侧表的副本。
> 2. **MetadataStore 不取代侧表，它只承载 C2/C3 绑定**。`symbol_bindings: Dict[node_uid, Symbol]` / `type_bindings: Dict[node_uid, IbSpec]` / `loc_bindings: Dict[node_uid, Location]` 是合法字段；`callable_instances` / `capture_modes` / `annotations` 必须删除；`cell_captured_symbols` 保留（无 AST 对应字段）。
> 3. **TypeEnvironment 不引入约束求解**。删除 `constraints` / `generic_instances`，仅保留 `auto_return_accumulator`。
> 4. **llmexcept 在 AST 上有两条并存通道**：正则情形写 `IbLLMExceptionalStmt.target=prev_stmt`；条件 for 循环写 `IbFor.llmexcept_handler=stmt`。v2 必须在适当 Pass 中显式做 body 重写（pop + replace），不能依赖 parser 的初值。
> 5. **不可变 Context 的承诺不下沉到 MetadataStore 内部字典级别**。bind 操作允许 mutable in-place，但调用面只允许在 Pass 内部——避免 `{**self.x, k: v}` 拷字典的 O(n²) 反模式。
> 6. **侧表本身不是 v1 的"设计缺陷"**——序列化产物中侧表已经是 5 张 `Dict[str, str]`（UID→UID），id() 仅是编译期内部细节。v2 真正的价值是收敛"双写真相"和补完核心 IBCI 设计原则（auto 锁定、any 永久、llm_uncertain、公理调度、行为依赖、意图窗口、llmexcept 双通道），而不是搬迁 id() → UID。
>
> 完整说明见 `docs/ARCHITECTURE_REVIEW_2026-05-15.md` 报告 B 章节 B.2 / B.4。本文档下方 Phase 1 / Phase 2 / Phase 3 的旧措辞中若与上述立场冲突，**以本节为准**。

---

## 📋 目录

- [执行摘要](#执行摘要)
- [当前状态分析](#当前状态分析)
- [重构目标与原则](#重构目标与原则)
- [Phase 1: 基础设施](#phase-1-基础设施)
- [Phase 2: 核心分析器实现](#phase-2-核心分析器实现)
- [Phase 3: 验证与集成](#phase-3-验证与集成)
- [实施计划](#实施计划)

---

## 执行摘要

### 背景

IBCI 的语义分析器（`semantic_analyzer.py`，2,192 行）存在严重的 God Class 反模式，需要进行架构级重构。经过对 IBCI 类型系统的深度分析（详见 `TYPE_SYSTEM_ANALYSIS_REPORT.md`），确认 **IBCI 是静态强类型语言**，这一发现大幅简化了重构的技术路径。

### 核心发现

1. ✅ **IBCI 类型系统是静态的**：变量类型在声明/推断后固定，不可改变
2. ✅ **不需要复杂的约束求解系统**：简单的一次性类型推断即可满足需求
3. ✅ **V1 的类型推断逻辑是正确的**：问题主要在于架构组织，而非算法本身
4. ⚠️ **真正的问题**：God Class、对象身份侧表、多阶段耦合、错误恢复不一致

### 简化后的工作量

| 阶段 | 原估算 | 修正后 | 说明 |
|------|--------|--------|------|
| Phase 1: 基础设施 | 12h | 10h | 已完成大部分 |
| Phase 2: 核心实现 | 80-100h | 35-45h | 删除约束求解系统 |
| Phase 3: 验证集成 | 10h | 10h | 保持不变 |
| **总计** | **102-122h** | **55-65h** | **减少约 50%** |

---

## 当前状态分析

### V1 的核心问题

#### 问题 1: God Class 反模式 ⚠️ **严重**

**现象**：
```python
class SemanticAnalyzer:  # 2,192 行，82 个方法
    def __init__(...):
        # 13+ 个可变实例变量
        self.symbol_table: SymbolTable
        self.registry: TypeRegistry
        self.side_table: SideTableManager
        self._auto_return_types: Optional[List[IbSpec]]
        self.in_function_def: bool
        self.in_class_def: bool
        self.in_behavior_expr: bool
        # ... 更多状态变量
```

**影响**：
- 认知负担极高（需理解整个 2000+ 行文件）
- 难以测试（无法独立测试各个阶段）
- 难以扩展（添加新分析需要修改核心类）

#### 问题 2: 对象身份侧表 ⚠️ **中等**

**现象**：
```python
class SideTableManager:
    self.node_to_symbol: Dict[Any, Symbol] = {}  # 使用 Python id()
    self.node_to_type: Dict[Any, 'IbSpec'] = {}
```

**问题**：
- 依赖 Python 对象的 `id()`，序列化后失效
- 无法跨进程共享
- 不支持增量编译缓存

#### 问题 3: 多阶段耦合 ⚠️ **中等**

**现象**：
```python
def analyze(self, node):
    # Pass 1: 符号收集（SymbolCollector）
    # Pass 2: 类型检查（self.visit - 主遍历）
    self.visit(node)
    # Pass 3: llmexcept 绑定（self._bind_llm_except）
    self._bind_llm_except(node)
    # Pass 3.5: Intent 验证（self._validate_intent_annotation_context）
    self._validate_intent_annotation_context(node)
    # Pass 5: Behavior 依赖（BehaviorDependencyAnalyzer）
    # Pass 6: 完整性检查（self._validate_integrity）
```

**问题**：
- Pass 3/3.5/5 需要二次遍历 AST
- 无法利用访问者模式的统一遍历
- 无法并行化或独立优化

#### 问题 4: 错误恢复策略不一致 ⚠️ **低**

**现象**：
```python
# 方式 1：返回 any
if not sym:
    return self._any_desc

# 方式 2：返回 None
if error:
    return None

# 方式 3：抛出异常（通过 error()）
self.error("Type mismatch", node)
return self._any_desc  # 继续执行
```

**问题**：
- 用户可能只看到第一个错误
- 不同类型错误的处理不一致
- 难以预测分析器行为

### V1 的正确设计

经过深度分析（`TYPE_SYSTEM_ANALYSIS_REPORT.md`），确认以下方面是**正确的**：

✅ **类型推断算法**：
- 一次性推断策略对于静态类型系统是充分的
- `auto` 变量从右侧表达式直接推断类型
- `-> auto` 函数从 return 语句推断返回类型
- 不存在需要约束求解的复杂场景

✅ **类型检查机制**：
- SEM_002: 变量重复声明检查
- SEM_003: 类型不匹配检查
- 类型兼容性验证（`is_assignable`）

✅ **Lambda/Snapshot 处理**：
- Lambda 捕获自由变量（通过 IbCell 共享）
- Snapshot 克隆值（早绑定）
- 类型在捕获时确定，之后不会改变

✅ **Behavior 表达式处理**：
- 编译期绑定目标类型到 behavior 节点
- 运行时通过 `__from_prompt__` 解析 LLM 输出
- 不涉及类型变化，只是输出质量控制

---

## 重构目标与原则

### 重构目标

1. **解决 God Class 问题**：将 2,192 行拆分为独立的、可测试的模块
2. **消除对象身份依赖**：使用 UID-based 元数据存储
3. **统一错误处理**：实现 Error-as-Data 模式
4. **提升可维护性**：清晰的职责分离和模块边界

### 重构原则

1. **保持 V1 的正确逻辑**：不改变类型推断算法，只改进架构
2. **优先正确性**：不追求性能优化，多次遍历可接受
3. **渐进式验证**：通过并行验证确保与 V1 行为一致
4. **最小化变更**：只解决明确的问题，不过度设计

### 非目标

❌ **不实现的功能**：
- ❌ 约束求解系统（Hindley-Milner 级别）
- ❌ 类型变量与 unification 算法
- ❌ 增量类型推断与类型细化
- ❌ Lambda/Snapshot 类型稳定性验证（静态类型已保证）

这些功能在之前的分析中被误认为需要，但经过核实，IBCI 的静态类型系统不需要它们。

---

## Phase 1: 基础设施

**目标**：建立新架构的核心基础设施
**工作量**：10 小时
**状态**：✅ 已完成（2026-05-13）

### 1.1 已完成的模块

#### 核心数据结构

**semantic_v2/result.py** (168 行)
```python
@dataclass
class Diagnostic:
    """诊断信息（错误/警告）"""
    level: DiagnosticLevel
    message: str
    code: str
    node_uid: Optional[str] = None

@dataclass
class PassResult:
    """Pass 执行结果（Error-as-Data）"""
    context: 'SemanticContext'
    metadata: Dict[str, Any]
    diagnostics: List[Diagnostic]
    success: bool

    @staticmethod
    def ok(context, metadata=None, diagnostics=None):
        """成功结果"""
        return PassResult(context, metadata or {}, diagnostics or [], True)

    @staticmethod
    def fail(context, diagnostics):
        """失败结果"""
        return PassResult(context, {}, diagnostics, False)
```

**semantic_v2/context.py** (170 行)
```python
@dataclass(frozen=True)
class SemanticContext:
    """不可变分析上下文"""
    ast: IbASTNode
    registry: Any
    module_name: str
    symbol_table: 'SymbolTableContext'
    type_environment: 'TypeEnvironment'
    metadata: 'MetadataStore'

    def with_symbol_table(self, new_table) -> 'SemanticContext':
        """创建新上下文（不可变更新）"""
        return replace(self, symbol_table=new_table)
```

#### 元数据存储

**semantic_v2/metadata/metadata_store.py** (175 行)
```python
@dataclass
class MetadataStore:
    """UID-based 元数据存储（可序列化）"""
    symbol_bindings: Dict[str, Any]  # node_uid → Symbol
    type_bindings: Dict[str, Any]    # node_uid → Type
    llmexcept_bindings: Dict[str, Any]
    intent_annotations: Dict[str, Any]
    behavior_metadata: Dict[str, Any]
```

**关键改进**：
- 使用字符串 UID 而非 Python `id()`
- 可序列化、可跨进程、可缓存
- 不依赖 Python 对象生命周期

#### Pass 基础设施

**semantic_v2/passes/base_pass.py** (63 行)
```python
class BasePass(ABC):
    """Pass 抽象基类"""

    @abstractmethod
    def run(self, context: SemanticContext) -> PassResult:
        """执行 Pass

        参数：
            context: 输入上下文

        返回：
            PassResult: 包含更新后的上下文和诊断信息
        """
        pass
```

### 1.2 创建的文件清单

```
core/compiler/semantic_v2/
├── __init__.py                           (48 行) - 模块导出
├── result.py                             (168 行) - 结果类型
├── context.py                            (170 行) - 上下文
├── metadata/
│   ├── __init__.py                       (8 行)
│   ├── metadata_store.py                 (175 行) - 元数据存储
│   ├── symbol_table.py                   (99 行) - 符号表封装
│   └── type_environment.py               (95 行) - 类型环境
└── passes/
    ├── __init__.py                       (8 行)
    └── base_pass.py                      (63 行) - Pass 基类
```

**总计**：9 个文件，857 行代码

---

## Phase 2: 核心分析器实现

**目标**：实现简化的语义分析 Pass 架构
**工作量**：35-45 小时（从原 80-100 小时大幅简化）

### 2.1 Pass 架构设计

**修正后的 Pass 顺序**（基于静态类型系统）：

```
Pass 1: Symbol Collection (符号收集)
  - 预扫描所有定义
  - 创建符号，记录声明的类型
  - 不做类型推断

Pass 2: Symbol Resolution (符号解析)
  - 解析所有符号引用
  - 绑定到 metadata (node_uid → symbol)
  - 检测未定义符号

Pass 3: Type Checking (类型检查)
  - 遍历 AST，为每个表达式确定类型
  - 推断 auto 变量和 -> auto 函数的类型
  - 检查类型兼容性，报 SEM_003 错误
  - 一次性推断，不需要约束求解

Pass 4: Binding Analysis (绑定分析)
  - LLMExcept 绑定分析
  - Intent 上下文验证
  - Lambda/Snapshot 捕获分析

Pass 5: Behavior Dependency (行为依赖分析)
  - 构建 LLM 依赖图
  - 检测循环依赖

Pass 6: Integrity Check (完整性检查)
  - 验证符号表完整性
  - 验证类型绑定完整性
```

**关键简化**：
- ❌ 不需要 Pass 3-5 分为"约束收集 → 求解 → 绑定"
- ✅ Pass 3 直接完成类型检查和推断（V1 风格）
- ✅ 简化的 Pass 4 合并所有绑定分析

### 2.2 Pass 实现详细设计

#### Pass 1: SymbolCollectionPass

**职责**：收集所有符号定义
**输入**：AST
**输出**：Context with populated symbol_table
**工作量**：8-10 小时

**实现要点**：
```python
class SymbolCollectionPass(BasePass):
    """符号收集 Pass"""

    def run(self, context: SemanticContext) -> PassResult:
        visitor = SymbolCollector(context)
        visitor.visit(context.ast)

        new_context = context.with_symbol_table(visitor.symbol_table)
        return PassResult.ok(new_context, diagnostics=visitor.diagnostics)

class SymbolCollector(ASTVisitor):
    """符号收集访问者"""

    def visit_IbFunctionDef(self, node):
        # 创建函数符号
        sym = Symbol(name=node.name, kind=SymbolKind.FUNCTION, ...)
        self.symbol_table.define(node.name, sym)

    def visit_IbClassDef(self, node):
        # 创建类符号
        sym = Symbol(name=node.name, kind=SymbolKind.CLASS, ...)
        self.symbol_table.define(node.name, sym)

    def visit_IbAssign(self, node):
        # 创建变量符号
        if isinstance(node.targets[0], ast.IbTypeAnnotatedExpr):
            # 有类型标注
            sym = Symbol(name=..., declared_type=..., ...)
        else:
            # 无类型标注
            sym = Symbol(name=..., declared_type=None, ...)
        self.symbol_table.define(name, sym)
```

**不做**：
- 类型推断
- 符号引用解析
- 类型检查

#### Pass 2: SymbolResolutionPass

**职责**：解析所有符号引用
**输入**：Context with symbol_table
**输出**：Context with resolved references
**工作量**：6-8 小时

**实现要点**：
```python
class SymbolResolutionPass(BasePass):
    """符号解析 Pass"""

    def run(self, context: SemanticContext) -> PassResult:
        visitor = SymbolResolver(context)
        visitor.visit(context.ast)

        new_metadata = context.metadata.with_symbol_bindings(visitor.bindings)
        new_context = context.with_metadata(new_metadata)
        return PassResult.ok(new_context, diagnostics=visitor.diagnostics)

class SymbolResolver(ASTVisitor):
    """符号解析访问者"""

    def visit_IbName(self, node):
        # 查找符号定义
        sym = self.symbol_table.lookup(node.id)
        if not sym:
            self.error(f"Undefined symbol '{node.id}'", node)
            return

        # 绑定到 metadata
        self.bindings[node.uid] = sym
```

#### Pass 3: TypeCheckingPass（简化版）

**职责**：类型检查和推断
**输入**：Context with resolved symbols
**输出**：Context with type_bindings
**工作量**：15-20 小时

**实现要点**：
```python
class TypeCheckingPass(BasePass):
    """简化的类型检查 Pass（适配静态类型系统）"""

    def run(self, context: SemanticContext) -> PassResult:
        visitor = TypeCheckingVisitor(context)
        visitor.visit(context.ast)

        new_metadata = context.metadata.with_type_bindings(visitor.type_bindings)
        new_context = context.with_metadata(new_metadata)
        return PassResult.ok(new_context, diagnostics=visitor.diagnostics)

class TypeCheckingVisitor(ASTVisitor):
    """类型检查访问者"""

    def visit_IbAssign(self, node):
        val_type = self.visit(node.value)

        for target in node.targets:
            var_name, declared_type = self.resolve_target(target)

            if declared_type:
                # 有类型标注：固定类型
                target_type = self.resolve_type(declared_type)
                sym = self.define_var(var_name, target_type, node)
            else:
                # 无类型标注
                sym = self.lookup_symbol(var_name)
                if not sym:
                    # 首次定义：any 语义
                    sym = self.define_var(var_name, self.any_desc, node)
                elif self.is_auto_type(sym.spec):
                    # auto 变量首次赋值：推断并固定类型
                    inferred_type = val_type
                    sym.spec = inferred_type  # 固定类型
                # else: 符号已存在且类型已固定，复用

            # 类型兼容性检查
            if not self.is_assignable(val_type, sym.spec):
                self.error(f"Cannot assign '{val_type.name}' to '{sym.spec.name}'",
                          node, code="SEM_003")

    def visit_IbFunctionDef(self, node):
        # 处理 -> auto 函数
        if node.returns and node.returns.name == "auto":
            # 收集所有 return 语句的类型
            return_types = []
            for ret_node in self.find_returns(node.body):
                ret_type = self.visit(ret_node.value)
                return_types.append(ret_type)

            # 统一返回类型
            if return_types:
                inferred_ret = self.unify_types(return_types)
                # 更新符号的返回类型
                self.update_function_return_type(node, inferred_ret)
```

**关键简化**：
- 不需要收集约束
- 不需要多次迭代
- 不需要类型细化
- 只需要：推断 → 固定 → 检查

#### Pass 4: BindingAnalysisPass

**职责**：各种绑定分析
**输入**：Context with type_bindings
**输出**：Context with binding metadata
**工作量**：8-10 小时

**实现要点**：
```python
class BindingAnalysisPass(BasePass):
    """绑定分析 Pass"""

    def run(self, context: SemanticContext) -> PassResult:
        # 子分析器
        llmexcept_analyzer = LLMExceptBindingAnalyzer(context)
        intent_validator = IntentContextValidator(context)
        lambda_analyzer = LambdaCaptureAnalyzer(context)

        # 运行子分析
        llmexcept_analyzer.analyze()
        intent_validator.validate()
        lambda_analyzer.analyze()

        # 合并结果
        diagnostics = (llmexcept_analyzer.diagnostics +
                      intent_validator.diagnostics +
                      lambda_analyzer.diagnostics)

        return PassResult.ok(context, diagnostics=diagnostics)
```

#### Pass 5: BehaviorDependencyPass

**职责**：行为依赖分析
**输入**：Context with all bindings
**输出**：Context with dependency metadata
**工作量**：4-6 小时

**实现要点**：
- 复用 V1 的 `BehaviorDependencyAnalyzer` 逻辑
- 适配新的上下文和元数据接口

#### Pass 6: IntegrityCheckPass

**职责**：完整性检查
**输入**：Context with all passes completed
**输出**：Final diagnostics
**工作量**：2-3 小时

**实现要点**：
```python
class IntegrityCheckPass(BasePass):
    """完整性检查 Pass"""

    def run(self, context: SemanticContext) -> PassResult:
        diagnostics = []

        # 检查所有引用节点都有符号绑定
        for node_uid in self.find_all_reference_nodes(context.ast):
            if node_uid not in context.metadata.symbol_bindings:
                diagnostics.append(Diagnostic.error(
                    f"Missing symbol binding for node {node_uid}",
                    code="INTEGRITY_001"
                ))

        # 检查所有表达式节点都有类型绑定
        for node_uid in self.find_all_expression_nodes(context.ast):
            if node_uid not in context.metadata.type_bindings:
                diagnostics.append(Diagnostic.error(
                    f"Missing type binding for node {node_uid}",
                    code="INTEGRITY_002"
                ))

        return PassResult.ok(context, diagnostics=diagnostics)
```

### 2.3 管道协调器

**工作量**：2-3 小时

```python
class SemanticPipeline:
    """语义分析管道"""

    def __init__(self, passes: List[BasePass]):
        self.passes = passes

    def run(self, context: SemanticContext) -> PassResult:
        """运行所有 Pass"""
        current_result = PassResult.ok(context)

        for pass_instance in self.passes:
            if not current_result.success:
                # 累积错误，但继续执行
                pass

            pass_result = pass_instance.run(current_result.context)

            # 合并诊断信息
            current_result = PassResult(
                context=pass_result.context,
                metadata=pass_result.metadata,
                diagnostics=current_result.diagnostics + pass_result.diagnostics,
                success=current_result.success and pass_result.success
            )

        return current_result

# 使用示例
def create_semantic_pipeline(registry, module_name):
    passes = [
        SymbolCollectionPass(),
        SymbolResolutionPass(),
        TypeCheckingPass(),
        BindingAnalysisPass(),
        BehaviorDependencyPass(),
        IntegrityCheckPass()
    ]
    return SemanticPipeline(passes)
```

---

## Phase 3: 验证与集成

**目标**：确保 V2 与 V1 行为一致
**工作量**：10 小时

### 3.1 并行验证

**实现方式**：
```python
def validate_semantic_v2():
    """并行运行 V1 和 V2，对比输出"""
    test_cases = load_test_cases()

    for test_case in test_cases:
        # 运行 V1
        v1_result = run_v1_semantic_analyzer(test_case.ast)

        # 运行 V2
        v2_result = run_v2_semantic_pipeline(test_case.ast)

        # 对比输出
        diff = compare_results(v1_result, v2_result)
        if diff:
            report_difference(test_case, diff)
```

**对比内容**：
1. 符号表结构和内容
2. 类型绑定（node → type）
3. 错误信息（数量、类型、位置）
4. 元数据（llmexcept、intent、behavior）

### 3.2 测试策略

**单元测试**：
- 每个 Pass 独立测试
- Mock 输入上下文
- 验证输出结果

**集成测试**：
- 运行完整管道
- 使用真实 IBCI 代码
- 对比 V1 和 V2 输出

**回归测试**：
- 运行现有测试套件
- 确保无破坏性变更

---

## 实施计划

### 时间表

| 阶段 | 任务 | 工作量 | 状态 |
|------|------|--------|------|
| Phase 1 | 基础设施 | 10h | ✅ 已完成 |
| Phase 2.1 | SymbolCollectionPass | 8-10h | ⏸️ 待开始 |
| Phase 2.2 | SymbolResolutionPass | 6-8h | ⏸️ 待开始 |
| Phase 2.3 | TypeCheckingPass | 15-20h | ⏸️ 待开始 |
| Phase 2.4 | BindingAnalysisPass | 8-10h | ⏸️ 待开始 |
| Phase 2.5 | BehaviorDependencyPass | 4-6h | ⏸️ 待开始 |
| Phase 2.6 | IntegrityCheckPass | 2-3h | ⏸️ 待开始 |
| Phase 2.7 | 管道协调器 | 2-3h | ⏸️ 待开始 |
| Phase 3 | 验证与集成 | 10h | ⏸️ 待开始 |
| **总计** | | **55-65h** | |

### 里程碑

**Milestone 1**: Phase 1 完成 ✅
- 日期：2026-05-13
- 交付物：基础设施代码（9 个文件，857 行）

**Milestone 2**: Phase 2 完成
- 预计日期：TBD
- 交付物：完整的 Pass 实现和管道协调器

**Milestone 3**: Phase 3 完成
- 预计日期：TBD
- 交付物：验证报告和集成文档

### 成功标准

1. ✅ 所有 Pass 可独立测试
2. ✅ 基本类型推断工作（简单表达式）
3. ✅ Lambda 捕获分析正确
4. ✅ 错误恢复策略统一
5. ✅ 与 V1 输出可对比（差异 < 5%）
6. ✅ 测试覆盖率不低于 V1
7. ✅ 文件大小 < 500 行/文件

---

## 风险管理

### 风险识别

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| V2 与 V1 行为不一致 | 高 | 并行验证（Phase 3） |
| 破坏现有功能 | 高 | 每步运行完整测试套件 |
| 工作量超出预期 | 中 | 渐进式开发，每阶段评估 |
| 性能回退 | 低 | 用户不关心性能（多次遍历可接受） |

### 回滚策略

- 每个阶段在独立分支进行
- 每 2-4 小时提交一次
- 发现严重问题立即回退
- 保持 V1 稳定，V2 作为可选实现

---

## 附录

### A. 相关文档

- `TYPE_SYSTEM_ANALYSIS_REPORT.md`: 类型系统深度分析报告
- `CODE_HEALTH_REFACTORING.md`: 代码健康度审计
- `SEMANTIC_COVERAGE_MATRIX.md`: 语义分析覆盖矩阵

### B. 已废弃的设计

以下设计在 `SEMANTIC_V2_DEEP_ANALYSIS.md` 中提出，但经过类型系统分析后确认**不需要**：

❌ **约束求解系统**：
- TypeVariable, Constraint, ConstraintStore
- Unification 算法
- 约束收集与统一求解
- 原因：IBCI 是静态类型，不需要复杂的类型推断

❌ **增量类型推断**：
- 多次迭代细化类型
- 类型稳定性检查
- 原因：静态类型天然稳定

❌ **Lambda 捕获类型验证**：
- 独立的类型稳定性验证 Pass
- 原因：静态类型保证了捕获变量类型不会改变

### C. 与原计划的对比

| 项目 | 原计划 (SEMANTIC_V2_DEEP_ANALYSIS.md) | 修正后 (本文档) |
|------|--------------------------------------|-----------------|
| Pass 数量 | 8 个（含约束收集、求解、绑定） | 6 个（简化） |
| 类型推断 | 约束求解系统 | 一次性推断（V1 风格） |
| 工作量 | 102-122h | 55-65h |
| 主要目标 | 改进类型推断算法 | 改进架构组织 |

---

**文档版本**: 1.0
**生成时间**: 2026-05-13
**作者**: Claude Sonnet 4.5
**状态**: 规划中，等待用户确认
