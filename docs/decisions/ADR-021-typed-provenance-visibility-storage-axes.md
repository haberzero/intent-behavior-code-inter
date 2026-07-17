# ADR-021: 类型化来源/可见性/存储轴 —— Provenance/Visibility/StorageModel 取代 IbSpec/Symbol 平 bool flag

## Status
**Accepted (2026-07-17)**。实现归属 PT-ARCH-23 **G1.5**（数据结构迁移改善），须先于 G2 内核原生化落地。本 ADR 固化经 6 项碎片化实证（F1-F7）收敛的决策。

## Date
2026-07-17

## Context

启动期 flag/state 数据结构审计（2026-07-17）发现 `IbSpec`/`Symbol`/`RuntimeSymbolImpl` 三层的控制变量是"一 flag 一含义、无底层完备数据结构"的碎片设计。项目负责人提出"这些 flag 是否碎片化"的质询后，经全仓逐处实证，确认碎片化成立：

### 碎片化实证（F1-F7，均已代码验证）
- **F1**：`is_user_defined`（`spec/base.py:87`）一字段扛两正交概念——对类/函数=**来源**（`interpreter.py:456,624,658`、`runtime_context.py:69`），对模块=**可见性**（`discovery.py:141,149` 强制设 True、`prelude.py:58` 按可见性读）。
- **F2**："intrinsic" 概念三种编码并存——`Symbol.metadata["is_intrinsic"]`（编译层 dict 键）、`RuntimeSymbolImpl.is_intrinsic`（运行层 bool）、UID 前缀 `"intrinsic:"`（标识层）。
- **F3**：`is_llm` 三处编码两处死/漏——`TypeDef.is_llm`（`base.py:184`，**未被 `serializer.py:161-162` 序列化**，round-trip 静默丢失）；`Symbol.metadata["is_llm"]`（`symbol_collection_pass.py:246`，纯只写零读者）；唯一真在用的是 `SymbolKind.LLM_FUNCTION` 枚举。
- **F4**：`metadata["axiom_provided"]` 纯只写死字段（仅 `symbols.py:203` 写入，零读者）。
- **F5**：`SymbolTable.define`（`symbols.py:147-150`）用自由 dict 键拼 4 行真值表决定重定义兼容——违 ⛔#4 禁过程式硬编码分发。
- **F6**：应存在而未存在的枚举——无 `Provenance`、无 `Visibility`、无 `StorageModel`。
- **F7**：新增平 bool 若不同步改 `serializer.py` + `artifact_rehydrator.py`，必重蹈 `is_llm` 漏序列化覆辙。

### 与既有 ADR 的冲突
- **ADR-020 §A**：kernel-native（可用性）与 import-gating（可见性）是**正交**两轴。F1 把二者焊死在 `is_user_defined` 一个 bool 上——直接违反。ADR-020 G2 现写法 "`is_user_defined=False` → 恒可解析/不可覆盖；import-gating 保留"（`PENDING_TASKS §九`）正是 F1 的延续，**按字面执行会经 prelude 过滤器意外解除 import-gating**。
- **ADR-016 §1/§3**：`storage_model` 类型级属性被明令"枚举化、协议驱动、禁标志位分支"。若 storage_model 以平 bool 落地则直接违反；且 storage_model 是首个被强制枚举化的正交轴，其它轴却仍是平 bool 将造成数据结构半新半旧。

## Decision

### 1. 三枚举轴取代平 bool（`core/base/enums.py`）
```python
class Provenance(Enum):
    KERNEL_NATIVE = auto()     # 内核原生（int/str/list… + ADR-020 内核桥）
    AXIOM_PROVIDED = auto()    # 来自 axiom 虚表（取代 metadata["axiom_provided"]）
    USER_DEFINED = auto()      # 用户代码/用户类
    EXTERNAL_MODULE = auto()   # 经 import 引入（取代 metadata["is_external_module"]）

class Visibility(Enum):
    PRELUDE_VISIBLE = auto()   # 免 import 自动可见（print/len/range + 类型）
    IMPORT_GATED = auto()      # 需 import（ADR-020 §A 轴 2）
    SCOPE_PRIVATE = auto()     # 作用域私有/不导出

class StorageModel(Enum):      # ADR-016 §1 一等落地
    MEMORY_BACKED = auto()     # 默认（当前全部类型）
    DISK_BACKED = auto()       # media / FileHandle（G3 起用）
```

### 2. IbSpec 承载三轴
- `is_user_defined: bool` → `provenance: Provenance = Provenance.USER_DEFINED`。
- 新增 `visibility: Visibility = Visibility.IMPORT_GATED`（prelude 过滤器 `prelude.py:58` 改读 `spec.visibility == Visibility.PRELUDE_VISIBLE`；`discovery.py:141,149` 设 `spec.visibility = Visibility.IMPORT_GATED`，不再借 `is_user_defined`）。
- 新增 `storage_model: StorageModel = StorageModel.MEMORY_BACKED`（**仅落字段，不落分发逻辑**；dispatch 分发留待 G3 随 deep_clone/serializer 分支启用，见"强耦合"说明）。

### 3. Symbol 清理 + 协议化
- `Symbol.metadata["is_intrinsic"]`/`["is_external_module"]` 升级为类型化 `Symbol.provenance`（复用同一 `Provenance` 枚举）。
- **删除两个死字段**：`metadata["axiom_provided"]`（F4）与 `metadata["is_llm"]`（F3，与 `SymbolKind.LLM_FUNCTION` 重复）。`metadata: Dict[str,Any]` 保留为非 flag 的临时数据逃生口（content hash / debug hint），不再存来源/可见性。
- `SymbolTable.define` 的 4 行真值表（`symbols.py:147-150`）替换为 `existing.provenance.compatible_with(sym.provenance)`——分发回归协议方法（ADR-020 §A）。

### 4. 序列化同步（杜绝 F7 复发）
`serializer.py` + `artifact_rehydrator.py` 同步持久化三枚举字段；`is_llm` 在 G1.5 中**全仓删除**（死字段 + 漏序列化 = 只删不补）。

### 5. 读取点机械迁移
原 `is_user_defined` 读取点（~12 处）机械迁移到 `spec.provenance == Provenance.USER_DEFINED`；`Symbol.metadata.get("is_intrinsic")` 读取点迁移到 `sym.provenance in (KERNEL_NATIVE, AXIOM_PROVIDED)`。不留兼容垫层（⛔#1）。

## Alternatives Considered

### Alternative A：保留平 bool，仅加 `prelude_visible: bool`
- Pros：改动面最小（~5 站点）
- Cons：不解 F1-F7，仅 F1；TypeDef 进入"flag 袋子"模式（is_nullable/is_user_defined/is_llm/prelude_visible/storage_model 互无关联的平 bool 串）；违背 ADR-016 对 storage_model 的枚举化强制
- Rejected：治标，且与 ADR-016 直接冲突

### Alternative B：分组 dataclass 嵌套记录（`TypeProvenance`/`TypeVisibility`/`TypeStorage`）
- Pros：为 ADR-016 backing 子字段（FileBacking/GeneratedBacking）预留结构
- Cons：改动面最大；需 `@property is_user_defined` 兼容垫层迁移（违 ⛔#1）；来源/可见性当前仅单枚举值，分组是投机
- Rejected：过度工程；待 ADR-016 backing 真正要带子属性时再升级

## Consequences

### 单点真理收敛
- `is_user_defined` 的"重载"消除：**来源**（`provenance`）与**可见性**（`visibility`）成为两个独立字段，ADR-020 §A 的正交轴在代码层面真正落地。kernel-native 模块可用 `provenance=KERNEL_NATIVE + visibility=IMPORT_GATED` 一行表达——这正是 ADR-020 G2 的正确写法。
- `Symbol.metadata` 的 4 个自由 dict 键收敛为类型化 `Symbol.provenance`；2 个死字段删除。
- `symbols.py:147-150` 的真值表被 `Provenance.compatible_with` 取代——分发从过程式分支回归协议方法。

### 与 ADR-016 协同（G1.5 与 G3 的边界）
- `StorageModel` 枚举在 G1.5 落地为 IbSpec 一等字段（默认 `MEMORY_BACKED`），让 ADR-016 §1 的类型级属性**提前就位**。
- **铁律**：G1.5 **只落字段，不落逻辑**。`storage_model` 字段在 G1.5 期间默认写死 `MEMORY_BACKED`，**禁止任何 workflow 读取/分发**；分发机制（G3 的 deep_clone/序列化器磁盘型分支）才真正消费它。这避免 G1.5 变成"G3 半成品"而违强耦合禁止（ADR-014/016 G3-G6 不可拆分）。

### 阻塞与前置
- G1.5 **必须先于 G2**（ADR-020 G2 的 `is_user_defined` 写法依赖本 ADR 重写为 provenance/visibility）。
- `Provenance`/`Visibility` 也为 G4 FileHandle 的 axiom 注册提供干净字段（`provenance=KERNEL_NATIVE + visibility=IMPORT_GATED`）。
- 本 ADR 不改变 ADR-013/014/015/016 的任何结论；它修正 ADR-020 G2 的实现措辞（见 Supersedes 记录）。

## 与其它 ADR 关系
- **协同**：ADR-016（storage_model 一等字段提前就位）、ADR-020（其 §A 正交轴真正落地；其 G2 写法被本 ADR 修正）。
- **修正**：ADR-020 `PENDING_TASKS §九` G2 行 "`is_user_defined=False` → 恒可解析/不可覆盖" → 改为 "`provenance=KERNEL_NATIVE + visibility=IMPORT_GATED` → 恒可解析/不可覆盖 + import-gated 保留"。
- **不冲突**：ADR-013/014/015/017/019。

## 里程碑归属
实现归属 **PT-ARCH-23 阶段 G1.5（数据结构迁移改善）**，紧跟 G1（重分类基础设施）之后、路径收尾与 G2 之前。依赖序与任务分配见 `PENDING_TASKS §九 PT-ARCH-23`。
