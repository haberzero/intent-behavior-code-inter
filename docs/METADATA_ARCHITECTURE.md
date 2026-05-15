# IBCI 元数据架构设计文档

**创建日期**: 2026-05-13  
**状态**: 已实施  
**目的**: 澄清 AST、侧表、MetadataStore 的职责边界和设计原则

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

#### ✅ 程序源码结构
```python
class IbBehaviorExpr:
    segments: List[Union[str, IbExpr]]  # 模板片段
    tag: str                             # 标识符
```

#### ✅ 静态分析结果（需要持久化）
```python
class IbBehaviorExpr:
    llm_deps: List["IbBehaviorExpr"]     # 依赖的其他 Behavior
    dispatch_eligible: bool               # 是否可并行调度
```

**为什么正确**：
1. **本质属性**：依赖关系是程序结构的一部分，不是"附加元数据"
2. **运行时需要**：VM 调度器直接读取 `dispatch_eligible`
3. **序列化友好**：序列化器自动处理对象引用 → UID 转换

### 2.3 不应该在 AST 上的内容

❌ **编译器内部临时状态**（如当前作用域、类型推断中间结果）  
❌ **编译器配置选项**（优化级别、警告设置）  
❌ **诊断信息**（错误、警告 - 这些通过 PassResult 传递）

---

## 三、侧表层：编译期的临时工作区

### 3.1 设计哲学

**侧表是编译器内部的瞬时映射**，用于 Pass 之间高效传递信息。

### 3.2 SideTableManager 的设计

```python
class SideTableManager:
    # ✅ 临时映射：使用 id() 快速查询
    node_to_symbol: Dict[Any, Symbol]      # AST节点 → 符号定义
    node_to_type: Dict[Any, IbSpec]        # AST节点 → 类型信息
    node_is_callable_instance: Dict[Any, bool]
    node_capture_mode: Dict[Any, str]
    
    # ⚠️ 特殊：需要持久化的分析结果（使用 UID）
    cell_captured_symbols: Set[str]        # 被 Cell 捕获的符号 UID
```

### 3.3 为什么混用 id() 和 UID？

**性能 vs 持久化的权衡**：

| 字段 | 索引方式 | 原因 |
|------|---------|------|
| `node_to_symbol` | id() | 编译期频繁查询，性能优先 |
| `node_to_type` | id() | 同上 |
| `cell_captured_symbols` | UID | 需要传递给 Pass 5 和运行时 |

### 3.4 侧表的生命周期

```python
# Pass 2: Symbol Resolution
side_table.bind_symbol(node, symbol)  # 写入

# Pass 3: Type Checking
sym = side_table.get_symbol(node)     # 读取

# 序列化时：自动转换
for node, sym in side_table.node_to_symbol.items():
    node_uid = collect_node(node)      # id(node) → UID
    sym_uid = collect_symbol(sym)      # id(sym) → UID
    output[node_uid] = sym_uid         # 输出 UID 映射
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

**确定性 UID**：保证相同内容生成相同 UID

```python
# 符号 UID：基于名字和作用域深度
symbol.uid = f"{name}@{depth}"

# 节点 UID：基于内容哈希
content = json.dumps(node_data, sort_keys=True)
node_uid = hashlib.sha256(content).hexdigest()[:16]

# 类型 UID：基于完全限定名
type_uid = f"type_{module_path}.{name}"
```

---

## 五、V1 vs V2：设计对比

### 5.1 V1 的正确设计（应该保留）

✅ **AST 节点包含依赖信息**
```python
# V1: 正确 - 直接写入 AST
node.llm_deps = [dep1, dep2]
node.dispatch_eligible = True
```

✅ **侧表使用 id() 快速查询**
```python
# V1: 正确 - 性能优先
side_table.node_to_symbol[node] = symbol  # 使用 id(node)
```

✅ **序列化器自动转换**
```python
# V1: 正确 - 职责分离
serializer._collect_node(node)  # 自动 id() → UID
```

### 5.2 V2 的过度设计（已修复）

❌ **试图将 AST 固有属性移到 MetadataStore**
```python
# V2 旧实现：错误 - 重复存储
new_metadata.behavior_metadata['behavior_dependencies'][node_uid] = deps
```

**问题**：
1. 违反单一数据源原则（AST 和 MetadataStore 重复）
2. 同步问题（需要保持两处一致）
3. 序列化冲突（序列化器已经处理 AST）

✅ **V2 修复后**
```python
# V2 新实现：正确 - 直接写 AST
node.llm_deps = deps
node.dispatch_eligible = True
# 无需修改 metadata
```

---

## 六、MetadataStore 的重新定位

### 6.1 当前角色（临时中介）

**MetadataStore 是侧表的 UID 版本**，主要用于支持不可变上下文传递：

```python
@dataclass
class MetadataStore:
    """编译期查询索引（UID-based）"""
    symbol_bindings: Dict[str, str]      # node_uid → symbol_uid
    type_bindings: Dict[str, str]        # node_uid → type_uid
    callable_instances: Set[str]
    cell_captured_symbols: Set[str]
    capture_modes: Dict[str, str]
```

### 6.2 职责边界

**✅ 应该存储的**：
- 编译器生成的临时绑定（符号绑定、类型绑定）
- 需要 UID 索引的分析结果（cell_captured_symbols）

**❌ 不应该存储的**：
- AST 固有属性（llm_deps, dispatch_eligible）
- 程序源码信息（已在 AST 上）
- 运行时状态（属于 VM）

### 6.3 长期愿景：统一序列化

**目标**：消除 MetadataStore 的独立性，直接从侧表序列化

```python
# 理想架构（未来）
class Serializer:
    def serialize(self, context: CompilerContext) -> Artifact:
        # 自动将 side_table 转换为 UID 映射
        # AST 中的对象引用自动转换为 UID
        # 输出统一的 Artifact 格式
        pass
```

**优势**：
- 消除中间层（MetadataStore）
- 简化数据流（侧表 → 序列化器 → Artifact）
- 编译器内部仍用 id() 保证性能

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

## 九、实施状态

### 9.1 已完成的改进

- ✅ Pass 5：直接写入 AST 节点（`node.llm_deps`, `node.dispatch_eligible`）
- ✅ Pass 6：移除对 behavior_metadata 的检查
- ✅ 文档：本架构设计文档

### 9.2 待优化项（长期愿景）

#### 优化 1：统一 UID 生成策略
**当前问题**：符号 UID、节点 UID、类型 UID 的生成逻辑分散

**建议**：创建统一的 `UIDGenerator` 类
```python
class UIDGenerator:
    @staticmethod
    def for_symbol(name: str, depth: int) -> str:
        return f"{name}@{depth}"
    
    @staticmethod
    def for_node(node_data: dict) -> str:
        content = json.dumps(node_data, sort_keys=True)
        return hashlib.sha256(content).hexdigest()[:16]
    
    @staticmethod
    def for_type(module: str, name: str) -> str:
        return f"type_{module or 'root'}.{name}"
```

#### 优化 2：简化 MetadataStore
**当前问题**：MetadataStore 试图通用化，但实际只用于特定场景

**建议**：重命名为 `CompilerBindings`，明确为"编译器临时绑定"
```python
@dataclass
class CompilerBindings:
    """编译器临时绑定（序列化中介）
    
    职责：在序列化时提供 UID 索引，不存储 AST 固有属性
    """
    symbol_bindings: Dict[str, str]  # node_uid → symbol_uid
    type_bindings: Dict[str, str]    # node_uid → type_uid
    
    # 特殊分析结果（需要 UID 持久化）
    cell_captured_symbols: Set[str]
    capture_modes: Dict[str, str]
```

#### 优化 3：序列化器自动化
**当前问题**：需要手动调用 `_collect_node()`, `_collect_symbol()`

**建议**：实现自动类型识别
```python
def _process_value(self, value):
    """智能处理任意值的序列化"""
    if isinstance(value, ast.IbASTNode):
        return self._collect_node(value)
    if isinstance(value, Symbol):
        return self._collect_symbol(value)
    if isinstance(value, IbSpec):
        return self._collect_type(value)
    if isinstance(value, list):
        return [self._process_value(v) for v in value]
    # ... 其他类型
    return value  # 原始值
```

#### 优化 4：AST UID 字段
**当前问题**：UID 在序列化时才生成，编译期不可见

**建议**：在 AST 节点上添加可选的 UID 字段
```python
@dataclass
class IbASTNode:
    uid: Optional[str] = None  # 可选：编译器可设置
```

**优势**：
- 编译期可以使用 UID 进行查询
- 序列化时优先使用节点自带的 UID
- 向后兼容（旧代码不设置 UID，序列化器自动生成）

---

## 十、参考资料

### 10.1 相关文档
- `SEMANTIC_REFACTORING_PLAN.md` - V2 重构计划
- `TYPE_SYSTEM_ANALYSIS_REPORT.md` - 类型系统分析
- `core/compiler/serialization/serializer.py` - 序列化实现

### 10.2 关键代码位置
- AST 定义：`core/kernel/ast.py`
- 侧表管理：`core/compiler/semantic/passes/side_table.py`
- 序列化器：`core/compiler/serialization/serializer.py`
- V2 Passes：`core/compiler/semantic_v2/passes/`

---

## 附录：常见问题解答

### Q1：为什么不在编译期就使用 UID？
**A**：性能考虑。编译期频繁查询（Pass 之间传递），使用 Python id() 比字符串 UID 快得多。序列化时才转换为 UID，是性能和持久化的最佳平衡点。

### Q2：为什么行为依赖要写在 AST 上？
**A**：三个原因：
1. 运行时需要（VM 调度器直接读取）
2. 是程序结构的一部分（不是临时元数据）
3. 序列化器已经处理对象引用转换（无需手动管理）

### Q3：MetadataStore 未来会被移除吗？
**A**：不会完全移除，但会重新定位为"序列化中介"。长期目标是让序列化器直接从侧表转换，MetadataStore 变成可选的中间表示。

### Q4：如何判断新的分析结果应该存在哪里？
**A**：参考第八章的决策流程图。核心判断：运行时需要 → AST，仅编译期查询 → 侧表。

---

**文档维护者**: Claude Sonnet 4.5
**最后更新**: 2026-05-15（追加"附录 B：2026-05-15 回顾性事实核查的关键订正"；
修正 §3.2 中关于侧表字段的描述，删除已确认为"双写"的两条字段）

---

## 附录 B：2026-05-15 回顾性事实核查的关键订正

> 完整报告见 `docs/ARCHITECTURE_REVIEW_2026-05-15.md`。本附录将与本文（METADATA_ARCHITECTURE）冲突的部分一次性收口。

### B.1 关于 §3.2 SideTableManager 的当前真实字段

§3.2 列举的 `node_is_callable_instance` 与 `node_capture_mode` 是**双写真相**的产物——这两份信息同时存在于 AST 字段（`IbBehaviorInstance.is_callable_instance`、`IbAssign.capture_mode` / `IbLambdaExpr.capture_mode`）与侧表中，运行时 VM 实际是从侧表读取的（`core/runtime/vm/handlers.py:710-712, 1431, 1445`）。这违反了本文第八章"反模式警告"的第一条："不要将 AST 固有属性复制到 MetadataStore/侧表"。

**结论**：这两条侧表字段计划删除（NEXT_STEPS 下一步 P0 任务"双写真相收敛"），VM 直接读取 AST 字段。删除后侧表只保留：
- `node_to_symbol`（C2，编译期对象身份索引；序列化时统一展平为 UID）
- `node_to_type`（C3，同上）
- `node_to_loc`（仅诊断用）
- `cell_captured_symbols`（UID 集合，跨边界字段；保留）

### B.2 关于 §6 MetadataStore 字段定位的修订

v2 `MetadataStore` 当前实现含 6 个字段：`symbol_bindings`、`type_bindings`、`callable_instances`、`capture_modes`、`cell_captured_symbols`、`annotations`。其中：

- `callable_instances` / `capture_modes`：**AST 字段副本**，应当删除（同 §B.1）。
- `annotations`：**通用口袋字段**，会被滥用为"再加一份保险"的便捷出口，应当删除。
- `cell_captured_symbols`：**保留**（确实是跨 Pass 传递的 UID 集合，无 AST 对应字段）。

同时 v2 `BindingAnalysisPass.run()` 写入了三个 `MetadataStore` 未声明的字段：`llmexcept_bindings`、`intent_annotations`、`behavior_metadata`——这三个字段**不应当被声明**。正确做法：

- `llmexcept_bindings`：直接写回 AST（`IbLLMExceptionalStmt.target` / `IbFor.llmexcept_handler`，两个并存的 AST 通道，见下 §B.3）。
- `intent_annotations`：写回 AST 或写回 `symbol_bindings`/`type_bindings`。
- `behavior_metadata`：拆解成具体字段（dispatch_eligible / llm_deps）写回 AST，**避免通用口袋**。

### B.3 关于 llmexcept 的 AST 双通道绑定（必须明文记录）

`IbLLMExceptionalStmt` 在 parser 阶段 `target=None`；语义阶段 `_bind_llm_except`（`core/compiler/semantic/passes/semantic_analyzer.py:235-285`）按情形分两路写入：

- **正则情形**（assign / if / return / while 等含 `@~...~` 的语句）：`IbLLMExceptionalStmt` 在 body 中**替换**前一句，`stmt.target = prev_stmt`。
- **条件驱动 for 循环情形**：`IbLLMExceptionalStmt` **不**进入 body，而是挂在 `IbFor.llmexcept_handler` 字段，`stmt.target` 保持 None。

这是历史上"侧表 → AST 字段"反向迁移（删除旧 `node_protection` 侧表，C11/P3）的最终形态。**v2 重构必须同时处理这两条 AST 通道**，不可以只读其中一个。

### B.4 关于 `TypeEnvironment` 字段的修订

v2 `TypeEnvironment` 当前含 `constraints` / `generic_instances` / `auto_return_accumulator` 三个字段。前两者来源于 Python 流派"约束求解 + 泛型实例化"思维，**不符合 IBCI 静态强类型 + auto 单次锁定的设计承诺**，应当在被写入前删除。仅保留 `auto_return_accumulator`，这是 `-> auto` 函数实现的唯一合法瞬态。

### B.5 关于 §4.3 UID 生成策略的两个潜在地雷（待整改）

- **类型 UID 冲突**：`type_{module}.{name}` 对结构化 `CALLABLE_SIG` 名字均为 "callable" 或匿名，会塌成同一 UID。当前未爆是因为 fn 推断少；D3（HOF 参数签名匹配）开始落地时会成为故障源。**改法**：CALLABLE_SIG 的 UID 改为 `sig_<sha16(return_head + ','.join(param_heads))>`。
- **节点内容哈希的"语义重影"**：两个语法相同但语义不同的节点（如不同作用域的两个 `IbName("x")`）会被哈希到同一 UID，被侧表共用同一份绑定。当前能跑是因为 semantic 阶段用 `id()` 写、序列化前不重复；**只要哈希恰好相同就会塌**。改法见 `docs/ARCHITECTURE_REVIEW_2026-05-15.md` 报告 B 章节 B.3.2。

### B.6 关于 "MetadataStore.bind 返回新 store" 的反模式

v2 当前实现采用 `{**self.symbol_bindings, k: v}` 拷整张字典模式（在 `metadata_store.py` 中）。节点上千就是 O(n²) 开销。改法：bind 改为 mutable in-place 更新，但**只允许从 Pass 内部调用**——这等价于 v1 的 SideTableManager 的成熟方案。"不可变 Context" 的设计承诺**不需要落到 MetadataStore 内部字典级别**。

### B.7 反模式警告的扩充（取代 §8.3）

在第八章"反模式警告"的基础上追加：

❌ **不要**给 MetadataStore 新增 `behavior_metadata` / `annotations` 这种通用口袋字段——它会立刻被滥用，把侧表的债换个名字续命。
❌ **不要**让 `TypeEnvironment` 演化出"按节点-约束键"的字段——这是元数据膨胀的种子。
❌ **不要**忽略 llmexcept 的两条 AST 通道（`stmt.target` 与 `IbFor.llmexcept_handler`）——v2 必须同时处理。
❌ **不要**重复存放"捕获模式"和"callable 实例标志"——AST 字段已是真相，删侧表副本。

