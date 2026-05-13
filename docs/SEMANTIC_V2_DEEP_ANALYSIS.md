## Semantic Analyzer V2 - 深度交叉检验与重新规划

### 执行摘要

基于用户反馈，重新规划技术路径，优先考虑**逻辑稳定性、正确性、可维护性**，而非性能。采用最激进的约束求解型类型推断系统作为最终目标，当前实现采用渐进式路径。

---

## 一、用户决策解读与影响分析

### 决策 1：遍历模式 - 采纳建议，但调整优先级

**决策**：采用混合遍历模式，但**优先考虑正确性和可维护性而非性能**

**影响分析**：
- ✅ 保持独立 Pass 结构（便于理解和测试）
- ✅ 允许多次遍历（确保逻辑清晰）
- ⚠️ 性能开销可接受（6-8 次遍历也无妨）

**调整后的方案**：
```
Pass 1: Symbol Collection          (遍历 1) - 收集所有符号
Pass 2: Symbol Resolution           (遍历 2) - 解析符号引用
Pass 3: Type Constraint Collection  (遍历 3) - 收集类型约束
Pass 4: Constraint Solving          (非遍历) - 求解约束系统
Pass 5: Type Binding                (遍历 4) - 绑定推断结果
Pass 6: Lambda Capture Analysis     (遍历 5) - 分析捕获
Pass 7: Validation Suite            (遍历 6) - 验证规则
Pass 8: Integrity Check             (遍历 7) - 完整性检查
```

**关键变化**：
- 分离了符号收集和符号解析（更清晰）
- 类型推断分为 3 步：收集约束 → 求解 → 绑定结果
- Lambda 捕获分析独立于类型推断
- 验证和检查明确分离

### 决策 2：类型推断 - 约束求解系统（最激进方案）

**决策**：采用约束求解器，实现最准确的类型推断

**这是一个重大决策**，影响整个架构。需要深入分析：

#### 2.1 约束求解系统的核心概念

**类型变量 (Type Variable)**：
```python
# 未知类型用类型变量表示
τ1, τ2, τ3, ...  # 类型变量

# 例子：
x = ?           # x: τ1 (未知)
y = x + 1       # x: τ2, y: τ3
                # 约束：τ2 = int (因为 +1), τ3 = int
                # 求解：τ1 = τ2 = int, τ3 = int
```

**约束类型**：
1. **等式约束** (Equality): `τ1 = τ2`
2. **子类型约束** (Subtype): `τ1 <: τ2`
3. **实例约束** (Instance): `τ1 = C[τ2, τ3, ...]` (泛型实例化)

**统一算法 (Unification)**：
```
unify(τ1, τ2):
    if τ1 == τ2: return success
    if τ1 is type_var: substitute τ1 → τ2
    if τ2 is type_var: substitute τ2 → τ1
    if τ1 = C[α1,...] and τ2 = C[β1,...]:
        unify(α1, β1) and ... and unify(αn, βn)
    else: fail
```

#### 2.2 IBCI 语言的约束来源分析

**来源 1：字面量**
```ibci
x = 42          # 约束：type(x) = int
y = "hello"     # 约束：type(y) = str
```

**来源 2：运算符**
```ibci
a = b + c       # 约束：type(b) <: Addable, type(c) <: Addable
                #       type(a) = result_type(+, type(b), type(c))
```

**来源 3：函数调用**
```ibci
def foo(x: int) -> str: ...
result = foo(arg)  # 约束：type(arg) <: int, type(result) = str
```

**来源 4：赋值**
```ibci
x: int = expr   # 约束：type(expr) <: int, type(x) = int
```

**来源 5：返回语句**
```ibci
def foo() -> T:
    return expr  # 约束：type(expr) <: T
```

**来源 6：Lambda/Snapshot（复杂情况）**
```ibci
fn f = lambda x: x + 1
# 约束：
#   type(f) = fn_callable[T1 → T2]
#   type(x) = T1
#   T1 supports +
#   type(x + 1) = T2
```

**来源 7：Behavior 表达式（特殊情况）**
```ibci
result = @~计算结果~
# 约束：type(result) = behavior | T (取决于返回类型注解)
```

**来源 8：泛型实例化**
```ibci
list_of_ints: list[int] = []
# 约束：type(list_of_ints) = list[int]
```

#### 2.3 约束求解的挑战

**挑战 1：循环类型**
```ibci
class Node:
    next: Node  # 自引用类型

# 约束：type(Node.next) = Node
# 解决：使用递归类型 μX.{next: X}
```

**挑战 2：多态函数**
```ibci
def identity(x):  # 通用函数
    return x

a = identity(42)      # type(a) = int
b = identity("hi")    # type(b) = str

# 约束：identity: ∀T. T → T
# 需要 let-polymorphism 或 Hindley-Milner 系统
```

**挑战 3：子类型与协变/逆变**
```ibci
class Animal: pass
class Dog(Animal): pass

def feed(animals: list[Animal]): ...

dogs: list[Dog] = [Dog()]
feed(dogs)  # 类型错误！list 对类型参数是不变的

# 需要 variance 分析
```

**挑战 4：LLM 行为表达式的类型不确定性**
```ibci
result = @~返回一个数字~
# type(result) = behavior 还是 int？
# 运行时才能确定是否需要重试

# 这需要引入"效果类型"(Effect Types)
```

**挑战 5：Lambda 捕获的类型依赖**
```ibci
x = 42
fn f = lambda: x + 1  # f 捕获 x

x = "hello"  # x 的类型改变了！
# f 的类型是否应该随之改变？

# 需要决定：
# - 捕获时的类型（早绑定）
# - 使用时的类型（晚绑定）
```

#### 2.4 V1 的类型推断局限性分析

**局限 1：一次性推断，无法处理相互依赖**
```ibci
def foo():
    x = bar()  # 需要知道 bar 的返回类型
    return x

def bar():
    y = foo()  # 需要知道 foo 的返回类型
    return y

# V1: 按定义顺序推断，第一个遇到未定义的就返回 any
# 约束系统: 建立约束 τ_foo = τ_bar，统一求解
```

**局限 2：auto 返回类型的临时解决方案**
```python
# V1 代码：
self._auto_return_types: Optional[List[IbSpec]] = None
# 在函数内部累积返回类型，退出时统一
```
这实际上是约束求解的原始形式，但只适用于单个函数。

**局限 3：泛型实例化不完整**
```ibci
def identity(x):
    return x

# V1: identity 的类型是 fn_callable (无参数类型)
# 理想: identity: ∀T. T → T
```

**局限 4：Lambda 的类型推断不精确**
```ibci
fn f = lambda x: x + 1
# V1: f: fn_callable
# 理想: f: int → int (通过约束求解推断)
```

### 决策 3：错误恢复策略 - 按建议定义

**决策**：采用统一的错误恢复策略

**定义**：
```python
class ErrorRecoveryStrategy(Enum):
    # 符号未定义 → 继续分析，类型为 any
    SYMBOL_NOT_FOUND = "continue_with_any"

    # 类型不匹配 → 继续分析，使用期望类型
    TYPE_MISMATCH = "continue_with_expected"

    # 约束无解 → 继续分析，类型为 any
    CONSTRAINT_UNSATISFIABLE = "continue_with_any"

    # 约束违反 → 报错，跳过该节点
    CONSTRAINT_VIOLATION = "skip_node"
```

### 决策 4：Lambda 捕获分析 - 细化流程

**决策**：分离符号捕获和类型推断

**关键洞察**：
1. **符号捕获**只需要符号信息，不需要类型
2. **类型推断**需要知道捕获的变量的类型
3. **两者相互独立**，但有依赖关系

**细化流程**：
```
Pass 1: Symbol Collection
  → 收集所有符号（包括 lambda 参数）

Pass 2: Symbol Resolution
  → 解析所有符号引用（包括 lambda body 中的引用）

Pass 6: Lambda Capture Analysis (独立 Pass)
  → 分析 lambda/snapshot 捕获了哪些符号
  → 确定捕获模式（lambda=cell, snapshot=clone）
  → 标记 cell_captured_symbols
  → 此时不需要类型信息

Pass 3-5: Type Constraint & Solving
  → 收集类型约束（包括 lambda 的约束）
  → Lambda 的约束：
      - 捕获变量的类型约束
      - 参数类型约束
      - 返回类型约束
  → 统一求解所有约束
  → Lambda 的类型自动推导
```

**示例**：
```ibci
x = 42
fn f = lambda: x + 1

# Pass 1: 收集符号
#   x: Symbol(name="x")
#   f: Symbol(name="f")
#   lambda 参数：无

# Pass 2: 解析引用
#   lambda body 中的 "x" → 解析到外层的 x

# Pass 6: 捕获分析
#   f 捕获 {x}
#   模式：lambda → x 需要 cell
#   标记：cell_captured_symbols.add(x.uid)

# Pass 3: 收集约束
#   C1: type(x) = int (字面量)
#   C2: type(f) = fn_callable[() → T1]
#   C3: T1 = type(x + 1)
#   C4: type(x) supports +
#   C5: T1 = int (+ 运算符规则)

# Pass 4: 求解约束
#   type(x) = int
#   type(f) = fn_callable[() → int]
```

---

## 二、约束求解系统的设计方案

### 2.1 架构设计

```
┌─────────────────────────────────────┐
│   Constraint Collection Pass        │
│   - 遍历 AST                         │
│   - 为每个表达式生成类型变量         │
│   - 收集约束                         │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   Constraint Store                   │
│   - 存储所有约束                     │
│   - 类型变量管理                     │
│   - 约束图构建                       │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   Constraint Solver                  │
│   - Unification 算法                 │
│   - Subtyping 求解                   │
│   - 循环检测                         │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   Type Binding Pass                  │
│   - 将求解结果绑定回 AST             │
│   - 更新元数据存储                   │
└─────────────────────────────────────┘
```

### 2.2 数据结构设计

**类型变量**：
```python
@dataclass
class TypeVariable:
    """类型变量 τ"""
    id: str  # 唯一标识符
    node_uid: Optional[str] = None  # 关联的 AST 节点
    bounds: List[IbSpec] = field(default_factory=list)  # 类型上界

    def __repr__(self):
        return f"τ{self.id}"
```

**约束**：
```python
@dataclass
class Constraint:
    """类型约束基类"""
    pass

@dataclass
class EqualityConstraint(Constraint):
    """等式约束：τ1 = τ2"""
    left: Union[TypeVariable, IbSpec]
    right: Union[TypeVariable, IbSpec]
    origin: str  # 约束来源（用于错误报告）

@dataclass
class SubtypeConstraint(Constraint):
    """子类型约束：τ1 <: τ2"""
    subtype: Union[TypeVariable, IbSpec]
    supertype: Union[TypeVariable, IbSpec]
    origin: str

@dataclass
class InstanceConstraint(Constraint):
    """实例化约束：τ = C[τ1, τ2, ...]"""
    var: TypeVariable
    constructor: str  # 类型构造器名称
    args: List[Union[TypeVariable, IbSpec]]
    origin: str
```

**约束存储**：
```python
class ConstraintStore:
    """约束存储和管理"""
    def __init__(self):
        self.type_vars: Dict[str, TypeVariable] = {}
        self.constraints: List[Constraint] = []
        self.substitution: Dict[str, Union[TypeVariable, IbSpec]] = {}

    def fresh_var(self, node_uid: Optional[str] = None) -> TypeVariable:
        """生成新的类型变量"""

    def add_constraint(self, constraint: Constraint) -> None:
        """添加约束"""

    def substitute(self, var: TypeVariable, typ: Union[TypeVariable, IbSpec]) -> None:
        """记录替换 τ → T"""
```

### 2.3 算法设计

**Unification 算法（核心）**：
```python
def unify(t1: Type, t2: Type, store: ConstraintStore) -> bool:
    """统一两个类型

    Returns:
        True if unification succeeds
        False if types are incompatible
    """
    # 应用当前替换
    t1 = apply_substitution(t1, store)
    t2 = apply_substitution(t2, store)

    # 规则 1：相同类型
    if t1 == t2:
        return True

    # 规则 2：τ = T (类型变量)
    if isinstance(t1, TypeVariable):
        if occurs_check(t1, t2, store):  # 检查循环引用
            return False
        store.substitute(t1, t2)
        return True

    if isinstance(t2, TypeVariable):
        if occurs_check(t2, t1, store):
            return False
        store.substitute(t2, t1)
        return True

    # 规则 3：C[α1,...] = C[β1,...]
    if isinstance(t1, IbSpec) and isinstance(t2, IbSpec):
        if t1.name != t2.name:
            return False  # 不同的类型构造器

        # 统一泛型参数
        args1 = get_generic_args(t1)
        args2 = get_generic_args(t2)
        if len(args1) != len(args2):
            return False

        for a1, a2 in zip(args1, args2):
            if not unify(a1, a2, store):
                return False
        return True

    # 规则 4：子类型关系
    if is_subtype(t1, t2, store):
        return True

    return False
```

**Occurs Check（防止无限类型）**：
```python
def occurs_check(var: TypeVariable, typ: Type, store: ConstraintStore) -> bool:
    """检查 τ 是否出现在 T 中（防止 τ = list[τ]）"""
    typ = apply_substitution(typ, store)

    if var == typ:
        return True  # 循环！

    if isinstance(typ, IbSpec):
        args = get_generic_args(typ)
        return any(occurs_check(var, arg, store) for arg in args)

    return False
```

**约束求解主循环**：
```python
def solve_constraints(store: ConstraintStore) -> SolverResult:
    """求解所有约束

    Returns:
        SolverResult with substitutions or errors
    """
    changed = True
    iterations = 0
    max_iterations = 1000  # 防止无限循环

    while changed and iterations < max_iterations:
        changed = False
        iterations += 1

        for constraint in store.constraints:
            if isinstance(constraint, EqualityConstraint):
                if unify(constraint.left, constraint.right, store):
                    changed = True
                else:
                    return SolverResult.fail(
                        f"Cannot unify {constraint.left} and {constraint.right}",
                        constraint.origin
                    )

            elif isinstance(constraint, SubtypeConstraint):
                if not check_subtype(constraint.subtype, constraint.supertype, store):
                    return SolverResult.fail(
                        f"{constraint.subtype} is not a subtype of {constraint.supertype}",
                        constraint.origin
                    )

            elif isinstance(constraint, InstanceConstraint):
                # 实例化约束处理
                pass

    if iterations >= max_iterations:
        return SolverResult.fail("Constraint solving did not converge")

    return SolverResult.ok(store.substitution)
```

### 2.4 Lambda 类型推断的约束生成

**示例 1：简单 Lambda**
```ibci
fn f = lambda x: x + 1

# 生成：
#   τ_f = fresh_var()
#   τ_x = fresh_var()
#   τ_body = fresh_var()
#   C1: τ_f = fn_callable[τ_x → τ_body]
#   C2: τ_body = result_type(+, τ_x, int)
#   C3: τ_x supports + (运算符约束)
#
# 求解：
#   τ_x = int (因为 +1 要求 int)
#   τ_body = int
#   τ_f = fn_callable[int → int]
```

**示例 2：捕获变量的 Lambda**
```ibci
x = 42
fn f = lambda: x + 1

# Pass 6 已确定：f 捕获 {x}

# 生成：
#   τ_f = fresh_var()
#   τ_x = fresh_var() (外层 x 的类型变量)
#   τ_body = fresh_var()
#   C1: τ_f = fn_callable[() → τ_body]
#   C2: τ_x = int (字面量约束)
#   C3: τ_body = result_type(+, τ_x, int)
#
# 求解：
#   τ_x = int
#   τ_body = int
#   τ_f = fn_callable[() → int]
```

**示例 3：Snapshot（克隆捕获）**
```ibci
x = 42
fn s = snapshot: x + 1

# Pass 6：s 捕获 {x}，模式 = snapshot

# 约束与 lambda 相同，但：
# - snapshot 在定义时克隆值
# - 类型推断时使用定义时的 x 类型
```

**示例 4：嵌套 Lambda**
```ibci
fn outer = lambda x: lambda y: x + y

# 生成：
#   τ_outer = fresh_var()
#   τ_x = fresh_var()
#   τ_inner = fresh_var()
#   τ_y = fresh_var()
#   τ_result = fresh_var()
#
#   C1: τ_outer = fn_callable[τ_x → τ_inner]
#   C2: τ_inner = fn_callable[τ_y → τ_result]
#   C3: τ_result = result_type(+, τ_x, τ_y)
#   C4: τ_x supports +, τ_y supports +
#
# 求解：
#   如果 + 要求相同类型：τ_x = τ_y = τ_result = int (假设)
#   τ_outer = fn_callable[int → fn_callable[int → int]]
```

### 2.5 实现阶段规划

**Phase 2A: 基础约束系统**（当前实现，10-12小时）
- 实现 TypeVariable, Constraint, ConstraintStore
- 实现基础 Unification 算法
- 实现 ConstraintCollectionPass（简单约束）
- 实现 SimpleSolver（只处理等式约束）

**Phase 2B: 完整约束求解**（中期目标，20-25小时）
- 实现完整 Unification（包括泛型）
- 实现 Subtyping 求解
- 实现 Occurs Check
- 处理循环依赖

**Phase 2C: Lambda/Snapshot 约束**（后期目标，15-20小时）
- Lambda 参数类型推断
- 捕获变量类型传播
- 嵌套 Lambda 约束
- Snapshot 克隆语义

**Phase 2D: LLM Behavior 效果类型**（远期目标，15-20小时）
- 引入效果类型 (Effect Types)
- behavior 类型的约束处理
- 不确定性类型传播

**Phase 2E: 高级特性**（未来扩展，20-30小时）
- Let-polymorphism (∀ 类型)
- Variance 分析
- 类型类 (Type Classes)

---

## 三、调整后的完整 Pass 设计

### Pass 1: Symbol Collection（符号收集）
**职责**：收集所有符号定义
**输入**：AST
**输出**：Context with populated symbol_table
**不做**：类型推断、引用解析

**实现要点**：
- 遍历所有定义节点（IbFunctionDef, IbClassDef, IbAssign 等）
- 创建 Symbol 对象，但类型字段留空
- 处理作用域嵌套

### Pass 2: Symbol Resolution（符号解析）
**职责**：解析所有符号引用
**输入**：Context with symbol_table
**输出**：Context with resolved references in metadata
**不做**：类型推断

**实现要点**：
- 遍历所有 IbName 节点
- 查找符号定义
- 绑定到 metadata (node_uid → symbol)
- 检测未定义符号（报错）

### Pass 3: Type Constraint Collection（类型约束收集）
**职责**：为每个表达式生成类型变量并收集约束
**输入**：Context with resolved symbols
**输出**：Context with constraint_store
**不做**：求解约束

**实现要点**：
- 为每个表达式节点生成 TypeVariable
- 根据节点类型生成相应约束：
  - IbConstant → EqualityConstraint
  - IbBinOp → 运算符约束
  - IbCall → 函数调用约束
  - IbAssign → 赋值约束
  - IbLambdaExpr → Lambda 约束（复杂）
  - IbBehaviorExpr → 效果类型约束

### Pass 4: Constraint Solving（约束求解）
**职责**：求解约束系统
**输入**：Context with constraint_store
**输出**：Context with type substitutions
**不做**：AST 遍历

**实现要点**：
- 运行 Unification 算法
- 迭代求解直到收敛
- 检测不可满足约束
- 生成类型替换映射

### Pass 5: Type Binding（类型绑定）
**职责**：将求解结果绑定回 AST
**输入**：Context with substitutions
**输出**：Context with type_bindings in metadata
**不做**：约束求解

**实现要点**：
- 遍历 AST
- 应用类型替换
- 绑定到 metadata (node_uid → type)
- 处理未解析的类型变量（默认 any）

### Pass 6: Lambda Capture Analysis（Lambda 捕获分析）
**职责**：分析 Lambda/Snapshot 捕获的符号
**输入**：Context with symbol resolution
**输出**：Context with capture metadata
**不做**：类型推断

**实现要点**：
- 遍历所有 IbLambdaExpr 和 IbSnapshotExpr
- 分析 body 中引用的外部符号
- 区分参数和捕获变量
- 标记 cell_captured_symbols
- 记录捕获模式（lambda/snapshot）

**关键：此 Pass 不需要类型信息，只需要符号信息**

### Pass 7: Validation Suite（验证套件）
**职责**：各种语义规则验证
**输入**：Context with all metadata
**输出**：Context with validation diagnostics
**不做**：推断或绑定

**子验证器**：
- Intent Validator（Intent 注释规则）
- LLMExcept Validator（llmexcept 绑定规则）
- Behavior Dependency Analyzer（行为依赖分析）
- Contract Validator（契约一致性）

### Pass 8: Integrity Check（完整性检查）
**职责**：最终一致性检查
**输入**：Context with all passes completed
**输出**：Final diagnostics
**不做**：修改 context

**检查项**：
- 所有引用节点都有符号绑定
- 所有表达式节点都有类型绑定
- 元数据一致性

---

## 四、技术演进路径

### 第一阶段：V2 基础版（当前 → +30小时）

**目标**：实现完整的 Pass 架构，但使用简化的类型推断

**Pass 实现**：
- Pass 1-2: Symbol Collection & Resolution（完整实现）
- Pass 3-5: 简化约束系统（只处理基本约束）
- Pass 6: Lambda Capture Analysis（完整实现）
- Pass 7-8: Validation & Integrity（完整实现）

**类型推断策略**：
- 使用 V1 风格的直接推断
- 支持基本的等式约束
- 不处理复杂的子类型关系

**目的**：
- 验证 Pass 架构正确性
- 建立测试框架
- 识别 V1 问题

### 第二阶段：约束系统增强（+20-25小时）

**目标**：实现完整的 Unification 算法

**增强内容**：
- 完整的 Occurs Check
- 泛型类型的 Unification
- 子类型约束求解
- 循环类型处理

**类型推断提升**：
- 支持相互依赖的函数
- 支持泛型实例化
- 更准确的错误报告

### 第三阶段：Lambda 类型推断（+15-20小时）

**目标**：精确推断 Lambda/Snapshot 类型

**实现内容**：
- Lambda 参数类型约束
- 捕获变量类型传播
- 嵌套 Lambda 约束
- Snapshot 克隆语义的类型处理

**关键技术**：
- 约束生成时考虑捕获上下文
- 求解时处理闭包类型

### 第四阶段：效果类型系统（+15-20小时）

**目标**：处理 LLM Behavior 的不确定性

**实现内容**：
- 引入效果类型 (Effect Types)
- behavior[T] 类型的约束
- 不确定性传播规则
- llmexcept 的类型安全

**理论基础**：
- Algebraic Effects
- Monadic Types

### 第五阶段：高级类型特性（+20-30小时）

**目标**：支持 Hindley-Milner 级别的类型系统

**实现内容**：
- Let-polymorphism (∀ 类型)
- Variance 分析（协变/逆变/不变）
- Type Classes（可选）
- Higher-kinded Types（可选）

---

## 五、立即行动计划（Phase 2A）

### 任务分解

**任务 2A-1：实现约束系统数据结构**（3-4小时）
- TypeVariable, Constraint, ConstraintStore
- Substitution 管理
- 约束图可视化（调试用）

**任务 2A-2：实现 Pass 1-2（符号收集与解析）**（6-8小时）
- SymbolCollectionPass
- SymbolResolutionPass
- 测试：基本符号查找

**任务 2A-3：实现简化约束收集**（8-10小时）
- ConstraintCollectionPass（只处理简单约束）
- 字面量约束
- 赋值约束
- 函数调用约束（基础）

**任务 2A-4：实现简单求解器**（5-6小时）
- SimpleSolver（只处理等式约束）
- 基础 Unification
- 错误报告

**任务 2A-5：实现 Pass 6（Lambda 捕获）**（6-8小时）
- LambdaCaptureAnalysisPass
- 自由变量收集
- 捕获模式标记
- cell_captured_symbols 管理

**任务 2A-6：实现管道协调器**（2-3小时）
- SemanticPipeline
- Pass 依赖管理
- 错误传播

**总计**：30-39 小时

### 验收标准

1. **所有 Pass 可独立测试**
2. **基本类型推断工作**（简单表达式）
3. **Lambda 捕获分析正确**
4. **错误恢复策略统一**
5. **与 V1 输出可对比**

---

## 六、关键技术问题与解决方案

### 问题 1：Lambda 捕获时机 vs 类型推断时机

**问题描述**：
```ibci
x = 42          # x: int
fn f = lambda: x + 1  # f 捕获 x

x = "hello"     # x 的类型改变！
```

**两种语义**：
1. **早绑定**：f 的类型在定义时确定（x: int → f: () → int）
2. **晚绑定**：f 的类型随 x 变化（x: str → f 类型错误）

**IBCI 的选择**：
- Lambda：晚绑定（通过 IbCell 共享）
- Snapshot：早绑定（克隆值）

**类型系统影响**：
- Lambda 的类型约束必须考虑捕获变量的**当前类型**
- 如果捕获变量类型改变，Lambda 类型也应改变（理论上）
- 但实践中，V1 在定义时确定类型

**解决方案**：
- Pass 6（捕获分析）：确定捕获哪些符号
- Pass 3（约束收集）：为被捕获的变量生成**稳定类型约束**
- 如果捕获变量后续类型改变，报类型错误

**示例**：
```ibci
x: int = 42
fn f = lambda: x + 1  # OK, x: int

x = "hello"  # 类型错误！x 已被 lambda 捕获，类型不能改变
```

### 问题 2：Behavior 表达式的类型

**问题描述**：
```ibci
result = @~返回一个数字~
# result 的类型是什么？
# 运行时可能返回 int, 也可能是 str（解析失败）
```

**类型选项**：
1. `behavior`（不确定类型）
2. `int | llm_uncertain`（联合类型）
3. `Effect[int]`（效果类型）

**V1 的做法**：
- 如果有类型注解，使用注解类型
- 否则使用 `behavior` 类型

**V2 的改进**：
- 引入效果类型：`behavior[T]` 表示"可能返回 T 或需要重试"
- 类型推断时，`behavior[T]` 可以赋值给 `T`（需要运行时检查）
- llmexcept 捕获的是 `behavior[T]` 类型

**约束生成**：
```ibci
result: int = @~返回一个数字~

# 生成约束：
#   τ_result = int
#   τ_behavior = behavior[T]
#   behavior[T] <: int (需要运行时检查)
#   T = int
```

### 问题 3：嵌套 Lambda 的约束传播

**问题描述**：
```ibci
fn make_adder = lambda x: lambda y: x + y
adder = make_adder(10)
result = adder(5)  # 15

# 约束网络非常复杂
```

**解决方案**：
- 嵌套 Lambda 生成嵌套的类型变量
- Unification 自动处理约束传播
- 测试用例覆盖嵌套场景

---

## 七、文档更新计划

### 需要更新的文档

1. **SEMANTIC_V2_ANALYSIS.md**
   - 添加约束求解系统详细设计
   - 更新 Pass 架构图
   - 记录技术演进路径

2. **NEXT_STEPS.md**
   - 更新 Phase 2A 任务列表
   - 记录约束系统作为长期目标
   - 标记当前采用简化实现

3. **CODE_HEALTH_REFACTORING.md**
   - 记录 semantic_v2 进度
   - 更新完成的任务

4. **新建：CONSTRAINT_SOLVING_DESIGN.md**
   - 约束求解系统完整设计文档
   - 算法说明
   - 示例和测试用例

---

## 八、风险评估与缓解

### 风险 1：约束求解器实现复杂度高 ⚠️ **高风险**

**影响**：可能需要比预估更多的时间

**缓解**：
- 第一阶段使用简化实现
- 参考现有实现（Hindley-Milner 有大量开源实现）
- 增量开发，每个特性独立测试

### 风险 2：Lambda 类型推断与 V1 行为不一致 ⚠️ **中风险**

**影响**：可能破坏现有代码

**缓解**：
- 详细对比测试
- 保留 V1 作为参考
- 提供兼容模式

### 风险 3：性能问题 ⚠️ **低风险**（用户不关心）

**影响**：约束求解可能较慢

**缓解**：
- 用户明确性能不是首要考虑
- 可以后期优化（缓存、剪枝）

---

## 九、总结与下一步

### 关键决策确认

1. ✅ **遍历模式**：多次遍历（7-8次），优先正确性
2. ✅ **类型推断**：最终目标是约束求解，当前简化实现
3. ✅ **错误恢复**：统一策略
4. ✅ **Lambda 捕获**：独立 Pass，在符号解析后、类型推断前

### 技术路径确认

**短期（Phase 2A）**：
- 实现完整 Pass 架构
- 简化的类型推断
- Lambda 捕获分析

**中期（Phase 2B-C）**：
- 完整约束求解器
- Lambda 类型推断
- 效果类型系统基础

**长期（Phase 2D-E）**：
- 完整效果类型
- Hindley-Milner 级别类型系统
- 高级特性

### 立即行动

我将：
1. 更新所有相关文档
2. 创建详细的约束求解设计文档
3. 开始实现 Phase 2A 任务
4. 定期向您汇报进度和发现的问题

**请您确认以上分析和计划是否符合您的预期。**
