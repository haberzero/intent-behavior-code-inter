# IBCI 元数据架构设计文档

> 本文档澄清 AST、侧表、MetadataStore 的职责边界和设计原则。
> 读者对象：需要修改编译管线数据流或新增 AST 字段/侧表的开发者。

---

## 执行摘要

IBCI 采用**三层数据流架构**，明确分离编译期临时数据、程序结构数据和运行时状态：

1. **AST 层**：程序的不可变蓝图，包含静态结构和分析结果
2. **侧表层**：编译期临时查询结构，使用 Python id() 快速访问
3. **序列化层**：自动转换 id() → UID，输出持久化格式

**核心原则**：依赖信息等静态分析结果**直接写入 AST 节点**，不通过 MetadataStore 中转。

---

## 一、架构概览

### 1.1 数据流图

```
编译期（Compiler）          序列化          运行期（Runtime）
    ↓                         ↓                   ↓
AST + SideTable  ────→  Serializer  ────→  Artifact  ────→  VM
    │                         │                   │
  [分析结果]              [自动转换]          [持久化格式]
    │                    id() → UID              │
  node.llm_deps                               UID 引用
  node.dispatch_eligible
```

### 1.2 各层职责

| 层次 | 数据结构 | 索引方式 | 生命周期 | 主要职责 |
|------|---------|---------|---------|---------|
| **AST** | 节点字段 | 节点自身 | 持久化 | 程序结构 + 静态分析结果 |
| **侧表** | Dict[id, Object] | Python id() | 编译期 | 快速查询 + Pass 间通信 |
| **序列化器** | - | UID 转换 | 边界 | id() → UID 自动转换 |
| **运行时** | Dict[uid, RuntimeSymbol] | UID 字符串 | 执行期 | 动态执行状态 |

---

## 二、AST 层：程序的结构骨架

### 2.1 设计哲学

**AST 是程序的不可变蓝图**，描述"程序写了什么"以及"编译器推断出了什么"。

### 2.2 应该在 AST 上的内容

#### 程序源码结构
```python
class IbBehaviorExpr:
    segments: List[Union[str, IbExpr]]  # 模板片段
    tag: str                             # 标识符
```

#### 静态分析结果（需要持久化）
```python
class IbBehaviorExpr:
    llm_deps: List["IbBehaviorExpr"]     # 依赖的其他 Behavior
    dispatch_eligible: bool               # 是否可并行调度
```

**正确性依据**：
1. **本质属性**：依赖关系是程序结构的一部分，不是"附加元数据"
2. **运行时需要**：VM 调度器直接读取 `dispatch_eligible`
3. **序列化友好**：序列化器自动处理对象引用 → UID 转换

### 2.3 不应该在 AST 上的内容

❌ **编译器内部临时状态**（如当前作用域、类型推断中间结果）  
❌ **编译器配置选项**（优化级别、警告设置）  
❌ **诊断信息**（错误、警告 - 这些通过 PassResult 传递）

### 2.4 类型级属性（`IbSpec`）—— 与 AST/侧表的边界

**类型级属性**（描述"这个类型本身是什么/从哪来/怎么存储"）**不**落在 AST 节点或侧表，而落在 `IbSpec`（`core/kernel/spec/base.py`）——它是"类型身份的单点真理"（single source of truth for type identity），编译期与运行期共用。

**当前类型级轴**：
- **`provenance: Provenance`** —— 来源（`KERNEL_NATIVE`/`AXIOM_PROVIDED`/`USER_DEFINED`/`EXTERNAL_MODULE`）。
- **`visibility: Visibility`** —— 可见性（`PRELUDE_VISIBLE`/`IMPORT_GATED`/`SCOPE_PRIVATE`）。prelude 过滤器据此决定免 import 可见性。
- **`storage_model: StorageModel`** —— 存储模型（`MEMORY_BACKED`/`DISK_BACKED`）。默认 `MEMORY_BACKED`；分发逻辑（deep_clone/序列化器磁盘型分支）按此标志分发。
- **`exported_types: List[str]`** —— 模块级附加类型注入列表。仅 `TypeKind.MODULE` 使用；当模块被 import 时，scheduler 把这些类型名作为符号同时注入当前作用域（约束与注入机制见 `07_kernel_native_modules.md` 的 exported_types 章节）。

**边界原则**：`Symbol`（编译期符号表）与 `RuntimeSymbolImpl`（运行时符号）**不复写**这些轴——`Symbol` 的 `provenance` 仅缓存符号层面的来源（复用同一 `Provenance` 枚举），其类型真相仍以 `spec`（IbSpec）为准，避免 AST 字段 / 侧表 / IbSpec 三处同时存储同一语义事实。

### 2.5 调用与参数节点

函数定义与调用共用一组参数节点（`core/kernel/ast.py`），参数种类常量与 Python 对齐：

| 常量 | 含义 |
|------|------|
| `ARG_POSITIONAL_OR_KEYWORD` | 普通参数（位置或具名传入） |
| `ARG_KEYWORD_ONLY` | `*args` 之后的参数，只能具名传入 |
| `ARG_VAR_POSITIONAL` | `*args`，收集多余位置实参 |
| `ARG_VAR_KEYWORD` | `**kwargs`，收集未声明具名实参 |

- **`IbArg`**（声明侧）：`arg`（参数名）、`annotation`（类型标注）、`default`（默认值表达式，仅普通 / keyword-only 参数可携带）、`kind`。`*args` / `**kwargs` 参数无标注与默认值。
- **`IbCall`**（调用侧）：`args`（位置实参列表，序列解包 `*expr` 以 `IbStarred` 节点出现在其中）、`keywords`（`List[IbKeyword]`）。
- **`IbStarred`**：`*expr` 序列解包表达式，仅出现在调用实参位置。
- **`IbKeyword`**：具名实参；`arg=None` 表示 `**expr` 字典解包。

这些节点由解析器组件 `parameters()`（`core/compiler/parser/components/declaration.py`）与 `call()`（`core/compiler/parser/components/expression.py`）共享，用户函数、fn-lambda、behavior 与 LLM 函数因此天然获得同一参数语法。序列化器对 AST 节点字段通用序列化（`vars(node)`），`default` / `kind` / `keywords` 随节点自动持久化，无需额外映射。

### 2.6 类定义节点

`IbClassDef`（`core/kernel/ast.py`）承载类声明：

```python
class IbClassDef(IbStmt):
    name: str
    body: List[IbStmt]
    parent: Optional[str] = None      # 父类名（裸名）
    parent_args: List[str] = []       # 父类泛型实参名（class Sub[T](Box[T]) → ["T"]）
    type_params: List[str] = []       # 泛型类型参数名（class Box[T] → ["T"]）
    methods: List[IbFunctionDef | IbLLMFunctionDef]
    fields: List[IbAssign]
```

- `type_params` / `parent_args` 是**程序源码结构**（AST 固有属性），随节点序列化。
  泛型类型参数的语义（占位 spec、特化替换）落在 `TypeDef.type_params`
  （`core/kernel/spec/base.py`）——类型级属性归 IbSpec（见 §2.4），AST 只存
  源码结构。
- 父类泛型引用（`class Sub[T](Box[T])`）经 `parent_args` 承载，语义层把
  `parent_type` 构造为泛型 TypeRef（`TypeRef.generic("Box", TypeRef("T"))`），
  特化时递归替换。

### 2.7 协议与 retroactive implementation 节点

`IbProtocolDef`（`core/kernel/ast.py`）承载协议声明：`name` / `parent` /
`type_params` / `body` / `methods`。协议是编译期契约：方法体被忽略（占位
`pass`），仅签名进入协议成员表，语义层注册 PROTOCOL-kind TypeDef 与内核
`ProtocolDef`。

`IbImplDef` 承载 retroactive implementation 声明：

```python
class IbImplDef(IbStmt):
    protocol_name: str
    type_name: str
    body: List[IbStmt] = []       # 方法定义（func）；空 = 仅声明形式
```

- `body` 是**程序源码结构**（AST 固有属性，随节点序列化）。带 body 时 impl
  为既有用户类补充协议缺失方法：方法经四个语义 pass 以目标类成员上下文
  收集/解析/精化（与类方法同构），运行期在水化阶段（封印前）注册到目标类。
- 方法体可读 `self`（self/super 注入与 node_to_symbol 绑定与类方法一致）。
- v1 边界：目标须为同模块用户类（非泛型、非内置）；body 仅 `func` 方法；
  与类自身成员同名冲突 fail-fast。

---

## 三、侧表层：编译期的临时工作区

### 3.1 设计哲学

**侧表是编译器内部的瞬时映射**，用于 Pass 之间高效传递信息。

### 3.2 MetadataStore 的设计

编译期侧表由 `core/compiler/semantic/metadata/metadata_store.py:MetadataStore` 承载，
存放 Pass 之间传递的分析结果（字段与职责见 §6.1 唯一权威定义）。

### 3.3 id() 与 UID 的取舍

**性能 vs 持久化的权衡**：

| 字段 | 索引方式 | 原因 |
|------|---------|------|
| `node_to_symbol` | id() | 编译期频繁查询，性能优先 |
| `node_to_type` | id() | 同上 |
| `cell_captured_symbols` | UID | 需要传递给 BindingPhase 和运行时 |

### 3.4 侧表的生命周期

编译期在 `MetadataStore` 中写入绑定，序列化时经 `side_tables` 承载转换为 UID 映射，运行时经 `ExecutionContext.get_side_table` 读取：

```python
# Pass 2: Symbol Resolution
metadata.node_to_symbol[node] = symbol   # 写入

# Pass 3: Type Checking
sym = metadata.get_symbol(node)          # 读取

# 序列化时：MetadataStore.to_dict() 输出 UID 映射 → 序列化器 side_tables
# 运行时：executor.ec.get_side_table("node_to_symbol", node_uid)
```

---

## 四、序列化层：边界转换器

### 4.1 设计哲学

**序列化器负责 id() → UID 的自动转换**，是编译器内存布局和持久化格式之间的桥梁。

### 4.2 核心转换逻辑

#### 转换 1：侧表映射
```python
# 输入：Dict[id, Object]
for node, sym in result.node_to_symbol.items():
    node_uid = self._collect_node(node)  # 生成或查找 UID
    sym_uid = self._collect_symbol(sym)
    output[node_uid] = sym_uid

# 输出：Dict[str, str]  (UID → UID)
```

#### 转换 2：AST 对象引用
```python
class IbBehaviorExpr:
    llm_deps: List[IbBehaviorExpr]  # 对象引用列表

# 序列化时自动转换为 UID 列表
def _process_value(self, value):
    if isinstance(value, list):
        return [self._process_value(v) for v in value]
    if isinstance(value, ast.IbASTNode):
        return self._collect_node(value)  # 转换为 UID
    # ...

# 输出：llm_deps: [uid1, uid2, ...]
```

### 4.3 UID 生成策略

**确定性 UID**：保证相同内容生成相同 UID。

**单一权威源**：序列化/符号 UID 格式收敛于 `core/base/uid.py`——调用方
（symbols / serialization / context / runtime_serializer）经 `UIDGenerator` 系列
函数生成，**禁止内联格式字符串**。边界：运行时调度器的解释器实例注册键
（`inst_<uuid8>`/`inst_<id>`）为进程内查找键，非序列化 UID，不并入。

| 家族 | 函数 | 形态 | 确定性 |
|------|------|------|--------|
| 根作用域 | `scope_uid(name)` | `scope_{name}`（无 name → `scope_global`） | 是 |
| 子作用域 | `child_scope_uid(parent, name, anon_id)` | `{parent}/{child}`（无 name → `anon_{n}`） | 是 |
| 符号 | `symbol_uid(scope, name)` | `{scope}:{name}` | 是 |
| 内建符号 | `intrinsic_uid(name)` | `intrinsic:{name}` | 是 |
| 节点 | `node_uid(content)` | `node_{sha256[:16]}` | 是（内容哈希） |
| 类型 | `type_uid(module, name)` | `type_{module}.{name}`（root → `type_root.{name}`） | 是 |
| 匿名符号 | `anon_symbol_uid(hash)` | `sym_anon_{hash}` | 是 |
| 文本资产 | `asset_uid(text)` | `asset_{sha256[:16]}` | 是（内容哈希） |
| 运行时作用域 | `rt_scope_uid()` | `rt_scope_{uuid16}` | 否（瞬态） |
| 运行时意图节点 | `rt_intent_uid()` | `intent_{uuid16}` | 否（瞬态） |
| 运行时意图上下文 | `rt_intent_ctx_uid()` | `intentctx_{uuid16}` | 否（瞬态） |
| 序列化运行时实例 | `rt_instance_uid()` | `inst_{uuid16}` | 否（瞬态） |

**不变量**：集中格式不改变已产出的 UID 值（round-trip 保真）；`tests/contracts/test_uid_generator.py` 固化格式与确定性。

---

## 五、设计决策：正确 vs 错误模式

### 5.1 正确的设计模式

**AST 节点包含依赖信息**
```python
# 正确 - 直接写入 AST
node.llm_deps = [dep1, dep2]
node.dispatch_eligible = True
```

**侧表使用 id() 快速查询**
```python
# 正确 - 性能优先
side_table.node_to_symbol[node] = symbol  # 使用 id(node)
```

**序列化器自动转换**
```python
# 正确 - 职责分离
serializer._collect_node(node)  # 自动 id() → UID
```

### 5.2 反模式：将 AST 固有属性移到 MetadataStore

❌ **试图将 AST 固有属性移到 MetadataStore**
```python
# 错误 - 重复存储
new_metadata.behavior_metadata['behavior_dependencies'][node_uid] = deps
```

**问题**：
1. 违反单一数据源原则（AST 和 MetadataStore 重复）
2. 同步问题（需要保持两处一致）
3. 序列化冲突（序列化器已经处理 AST）

正确做法：
```python
# 正确 - 直接写 AST
node.llm_deps = deps
node.dispatch_eligible = True
# 无需修改 metadata
```

---

## 六、MetadataStore 的职责边界

### 6.1 数据结构

`MetadataStore` 键为 AST 节点对象（Python object identity），由 Pipeline 在所有 Phase 完成后从合并的 PassOutput 构建（不可变 dataclass）：

```python
@dataclass(frozen=True)
class MetadataStore:
    node_to_symbol: Dict[Any, Any]      # AST 节点 → 符号定义
    node_to_type: Dict[Any, Any]        # AST 节点 → 类型信息
    node_to_loc: Dict[Any, Any]         # AST 节点 → 源码位置
    cell_captured_symbols: Set[str]     # 被 Cell 捕获的符号 UID
    get_symbol(node) / get_type(node) / get_location(node) / is_cell_captured(uid)
```

对象键在序列化阶段由 FlatSerializer 统一转换为确定性哈希 UID（`node_{sha256[:16]}`）。

### 6.2 职责边界

**应该存储的**：
- 编译器生成的临时绑定（符号绑定、类型绑定、位置绑定）
- 需要按节点查询的分析结果（cell_captured_symbols）

**❌ 不应该存储的**：
- AST 固有属性（llm_deps, dispatch_eligible）
- 程序源码信息（已在 AST 上）
- 运行时状态（属于 VM）

---

## 七、运行时层：独立的执行世界

### 7.1 设计哲学

**运行时只接受 UID**，完全独立于编译器内存布局。

### 7.2 运行时的 UID 使用

```python
class ScopeImpl:
    _symbols: Dict[str, RuntimeSymbol]      # 名字 → 运行时符号
    _uid_to_symbol: Dict[str, RuntimeSymbol]  # UID → 运行时符号
    _cell_map: Dict[str, IbCell]            # UID → Cell 变量
```

### 7.3 VM 如何使用 AST 依赖信息

```python
# VM 调度器读取 AST 节点属性
def dispatch_behavior(node: IbBehaviorExpr):
    if not node.dispatch_eligible:
        # 串行执行（有循环依赖）
        return execute_sync(node)
    
    # 检查依赖是否满足
    for dep in node.llm_deps:
        if not is_resolved(dep):
            wait_for(dep)
    
    # 并行调度
    return dispatch_async(node)
```

**关键点**：
- VM 直接读取 `node.dispatch_eligible`（无需查询侧表）
- `node.llm_deps` 在反序列化时已经重建为对象引用
- 运行时不依赖编译器的内存布局

---

## 八、设计原则总结

### 8.1 核心原则

1. **AST 是数据的源头**：静态分析结果写在 AST 上
2. **侧表是查询加速器**：编译期临时结构，性能优先
3. **序列化器是边界转换器**：负责 id() → UID 的转换
4. **运行时是独立世界**：只接受 UID，不依赖编译器

### 8.2 决策流程图

```
新的分析结果 X 应该存储在哪里？
    │
    ├─ 运行时需要？ ────→ 是 ────→ AST 节点字段
    │                              (llm_deps, dispatch_eligible)
    │
    ├─ 需要持久化？ ────→ 是 ────→ AST 节点字段 或
    │                              cell_captured_symbols (UID 集合)
    │
    └─ 仅编译期查询？ ──→ 是 ────→ 侧表 (id() 索引)
                                   (node_to_symbol, node_to_type)
```

### 8.3 反模式警告

❌ **不要**将 AST 固有属性复制到 MetadataStore  
❌ **不要**在序列化器外部手动进行 id() → UID 转换  
❌ **不要**混用 id() 和 UID（除非清楚理解原因）  
❌ **不要**在运行时依赖编译器内存布局

---

## 九、参考资料

### 9.1 相关文档

- `core/compiler/serialization/serializer.py` - 序列化实现

### 9.2 关键代码位置
- AST 定义：`core/kernel/ast.py`
- 侧表管理：经 `ExecutionContext.get_side_table` 读取 + 序列化器 `side_tables` 承载
- 序列化器：`core/compiler/serialization/serializer.py`
- Semantic Passes：`core/compiler/semantic/passes/`

### 9.3 语义分析 4-Phase 流水线

`core/compiler/semantic/pipeline.py:create_semantic_pipeline()` 创建标准管道：

| Phase | 类 | 子步骤 | 职责 |
|-------|------|--------|------|
| 1. SymbolPhase | `symbol_phase.py` | SymbolCollectionPass → SymbolResolutionPass → **TypeRefResolutionPass** | 收集所有符号定义；解析符号引用；将残留 TypeRef spec 统一解析为 IbSpec（循环导入已禁止，resolve 失败即真错误） |
| 2. TypePhase | `type_phase.py` | TypeResolutionPass → TypeCheckingPass | 解析声明标注；类型推断与兼容性检查 |
| 3. BindingPhase | `binding_phase.py` | BindingAnalysisPass → BehaviorDependencyPass | llmexcept 绑定 + body 保护约束；行为依赖图 |
| 4. IntegrityPhase | `integrity_phase.py` | IntegrityCheckPass | 完整性校验 |

Phase 间通过 `PassOutput`（symbol_bindings / type_bindings / diagnostics）传递产物，Pipeline 合并为最终 `MetadataStore`。

---

## 十、Symbol 冲突解析

`Symbol.provenance: Provenance` 是符号来源的唯一标志。`SymbolTable.define` 使用 `existing.provenance.compatible_with(sym.provenance)` 做冲突检测，分发通过协议方法完成。

---

## 深入指引

- 类型系统与字段存储：docs/architecture/03_type_system.md
- 编译产物序列化：docs/architecture/04_vm_interpreter.md
