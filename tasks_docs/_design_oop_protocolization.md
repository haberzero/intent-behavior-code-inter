# 设计冻结：阶段 A——OOP 侧协议化（dunder 协议注册表化）

> 承接 `_HANDOFF_KERNEL_PROTOCOLIZATION.md` 阶段 A（P0）+ 本 session 事实检查微调。
> 本文件为设计阶段临时任务文档，阶段落地后按惯例归并清理。

## 0. 背景与目标

协议化大重构已把 **prompt 侧协议**（to_prompt/from_prompt/validate_prompt/output_hint/
payload_prompt/snapshotable 等）接入协议注册表（`core/kernel/protocol.py` ProtocolDef +
`SpecRegistry.satisfies_protocol` 单一入口）。但 **OOP 侧**（receive 消息分派）仍停留在
字符串比较时代：`receive(message: str)` 内部以 `message == '__call__'` 等硬编码分支分派，
绕过已建成的协议注册表。

**目标**：把同一套协议化/单一权威标准推向 OOP 侧——receive 分派经协议注册表驱动，
消除全部硬编码字符串分派分支；属性访问双通道收敛；op_constants 与协议层双真相以
契约测试锁定。

**验收标准（本阶段）**：
1. `core/runtime/objects/` 下 `message == '...'` / `message in (...)` 硬编码分派分支归零
   （20 处 `==` + 2 处元组分支；`lookup_method(message)` 普通方法路由保持）。
2. 属性访问单一实现（`_default_getattr` 唯一权威，base.py 重复分支删除）。
3. op_constants 与协议 operator 元组一致性契约测试（含 `__pos__` 补齐）。
4. 全量 pytest 零回归 + 独立复核（general agent）+ 真实 LLM 试用复跑
   （T09 + 受影响套件，分类逐例一致）。
5. 文档同步（KNOWN_LIMITS / architecture / syntax 若受影响）。

## 1. 盘点（全仓实证，2026-08-16）

### 1.1 receive 硬编码分支（20 处 `==` + 2 处元组）

| # | 位置 | 分支 | 语义 |
|---|------|------|------|
| 1 | base.py:51 | `'__call__'` | axiom call cap 探测 + IbFunction 直调 + 用户 __call__ → _UserCallDrive |
| 2 | base.py:71 | `'__getattr__'` | 字段→方法查找（与 _default_getattr 重复） |
| 3 | base.py:87 | `'cast_to'` | 转换链（upcast/__to_prompt__ 桥） |
| 4 | ib_class.py:603 | `"__call__"` | 类构造：原生 __call__ 优先 / _ClassInstantiateDrive |
| 5 | ib_class.py:620 | `"__getitem__"` | 泛型特化下标 _specialize |
| 6 | ib_class.py:626 | `"__getattr__"` | 类字段/类方法 |
| 7 | sentinels.py:28 | `'__eq__'` | IbNone 恒等 |
| 8 | sentinels.py:31 | `'__ne__'` | IbNone 恒等 |
| 9 | optional.py:133 | `"__eq__"` | 空 Optional == None 语义 |
| 10 | optional.py:136 | `"__ne__"` | 同上 |
| 11 | optional.py:160 | `"__getattr__"` | 内层委托 + 空值 fail-fast |
| 12 | functions.py:172 | `'__getattr__'` | super() 代理转发 |
| 13 | functions.py:179 | `'__call__'` | super() 代理调用 |
| 14 | native_module.py:54 | `'__getattr__'` | IbNativeObject vtable 后兜底 |
| 15 | native_module.py:121 | `'__getattr__'` | IbModule scope 转发 |
| 16 | callables.py:131 | `"__return_type__"` | FnCallable 内部元数据 |
| 17 | callables.py:134 | `"__call__"` | FnCallable 执行 |
| 18 | callables.py:138 | `"__getattr__"` | FnCallable 委托 |
| 19 | callables.py:351 | `"__return_type__"` | IbBehavior 内部元数据 |
| 20 | callables.py:360 | `"__getattr__"` | IbBehavior 委托 |
| + | callables.py:128/356 | `in ("__get_metadata__","__to_prompt__","node_uid")` | 内部元数据消息 |
| + | runtime_context.py:308 | `'__getattr__'` | 模块 scope 属性 |

> **RuntimeContext 归类说明（复核 P2-5 整改）**：`RuntimeContextImpl` 非 IbObject 子类
> （interpreter 内部 scope 契约，IModuleScope 实现），其 receive 是"符号名 get 委托"，
> 无 ib_class/协议注册表访问——**不属 OOP 协议分派面**，本阶段不迁移。其
> `message == '__getattr__'` 分支是 VM 属性访问的 scope 入口（get 委托契约），
> 与 receive 协议分派不同构；若未来 scope 层协议化（阶段 E 后评估）再统一。

### 1.2 已协议化先例（参照）

- `satisfies_protocol`（_protocol.py:57）单一入口；8 个消费点已走注册表（LLM executor/
  type_checking/prompt_renderer/parsing_strategy）。
- 内置 13 协议已注册（protocol.py:111-178）：callable/iterable/subscriptable/operator/
  converter/parser/to_prompt/from_prompt/validate_prompt/output_hint/payload_prompt/
  snapshotable。
- 但 receive 分派**绕过**注册表；`lookup_method('__snapshot__')` 等 8 处 dunder 名查询
  散落（llm_except_frame/llm_parsing_strategy/_prompt/ib_class/primitive_initializer/_shared）。

### 1.3 属性访问双通道（A2 证据）

- base.py:71-79（receive '__getattr__' 分支）：字段→方法，未命中落 :82 lookup_method。
- bootstrapper.py:115-131 `_default_getattr`（注册为 ObjectClass.__getattr__）：字段→方法→
  fail-fast。**语义等价**（分支命中路径相同；未命中都经 :82 lookup_method('__getattr__')
  调用 _default_getattr → fail-fast）。→ 分支可整体删除，单一实现保留。

### 1.4 op_constants 双真相（A1 关联）

- `core/runtime/shared/op_constants.py`：OP_MAPPING（19 符号）+ AST_OP_MAP（14 AST 节点）
  + UNARY_OP_MAPPING（4 符号，含 `'+': '__pos__'`）。
- `core/kernel/protocol.py:128-135` operator 元组（22 方法，**无 __pos__**）。
- 层边界：kernel 禁导入 runtime（用户红线）→ 不可代码合并；处置 = **契约测试锁一致性
  + 补齐 __pos__**（code-quality §八：层约束导致的镜像常量 → 一致性测试取代人工同步）。

### 1.5 _impl_cls 现状（A3 评估）

- `get_base_name()` 已结构化（base.py:314-321 读 `base_name` 字段 + `_KIND_BASE_NAMES`）。
- `_impl_cls`（ib_class.py:219-235）已沿 `spec.get_base_name()` 解析特化类实现类。
- **结论：A3 主体已由类型地基重构完成**；本阶段仅补契约测试（特化类 _impl_cls 解析
  路径锁定），深度结构化并入阶段 B2（特化身份结构化）。

## 2. 设计

### 2.1 核心机制：dunder 协议索引 + 命名处理器分派

**不变式**：dunder 特殊消息名的权威集合 = 协议注册表全部协议 methods 的并集
（ProtocolRegistry 提供 `dunder_names()` 查询，从注册条目派生——单一权威）。

**receive 新骨架**（IbObject 基类，各子类覆写处理器）：

```python
# 协议注册表（spec registry）提供 dunder 名索引；处理器为可覆写命名方法。
_PROTOCOL_INDEX = None  # 惰性构建：{dunder_name: protocol_name}，来自 ProtocolRegistry

def receive(self, message, args):
    # 1. dunder 协议消息 → 命名处理器（类型感知、可覆写、无字符串比较）
    if message in self._dunder_names():
        handler = getattr(self, f"_dispatch_{message.strip('_')}", None)
        if handler is not None:
            return handler(message, args)
    # 2. 普通消息路由（vtable，正当形态）
    method = self.ib_class.lookup_method(message)
    if method is not None:
        return method.call(self, args)
    # 3. cast_to 特殊兜底（普通方法名 + 转换语义，见 2.4）
    if message == 'cast_to':
        return self._dispatch_cast_to(message, args)
    raise AttributeError(f"Object of type '{self.ib_class.name}' has no method '{message}'")
```

- `_dunder_names()`：委托 spec registry 的协议注册表（惰性缓存 + 引擎隔离）。
- 处理器命名规约：`_dispatch_<dunder>`（`__call__` → `_dispatch_call`），基类提供默认
  实现（含现有分支语义），子类（IbClass/IbNone/IbOptional/IbSuperProxy/IbNativeObject/
  FnCallable/IbBehavior/RuntimeContext）按需覆写。
- **行为零变更**：处理器体 = 原分支逻辑原样搬移（先重构后清理，不做语义改动）。

### 2.2 处理器映射（20 处分支 → 处理器）

| 处理器 | 提供者（基类默认 + 覆写） |
|--------|--------------------------|
| `_dispatch_call` | base（默认：axiom cap 探测 + _UserCallDrive）/ IbClass（构造）/ IbSuperProxy / FnCallable / IbBehavior |
| `_dispatch_getattr` | base（默认：委托 lookup_method('__getattr__') → _default_getattr 单一实现）/ IbClass（类字段）/ IbOptional（内层委托）/ IbSuperProxy / IbNativeObject / IbModule / FnCallable / IbBehavior / RuntimeContext |
| `_dispatch_getitem` | IbClass（_specialize 特化）；实例默认走 vtable |
| `_dispatch_eq` / `_dispatch_ne` | base 默认走 vtable（_default_eq）；IbNone（恒等）/ IbOptional（None 语义）覆写 |
| `_dispatch_return_type` | FnCallable / IbBehavior（内部元数据消息——见 2.3） |
| `_dispatch_cast_to` | base（转换链） |

### 2.3 内部元数据消息（callables 元组分支）+ 协议缺口补充

**self-grill 修正（2026-08-16）**：审计 BUILTIN_PROTOCOLS 发现 `__getattr__`/`__setattr__`
不在任何既有协议 methods 中（属性访问无协议覆盖）。修正：
- **新增内置协议 `attribute`**：methods=(`__getattr__`, `__setattr__`)——属性访问协议
  （读写两条），与 iterable/subscriptable 同族（能力名命名）。
- `("__get_metadata__", "node_uid")`：非语言级协议，是对象内省消息——收敛为
  FnCallable/IbBehavior 类内部消息常量（集中一处声明，消除散落字符串），
  `_dispatch_metadata` 处理器承载。若未来有第二个消费者再升级注册表协议。
- `__to_prompt__`（元组内）：属 to_prompt 协议方法——FnCallable 覆写
  `_dispatch_to_prompt`（返回原元组分支语义）。
- `__return_type__`：FnCallable/IbBehavior 内部消息（无协议）——入内部消息常量 +
  `_dispatch_return_type` 处理器。

### 2.3bis `_dispatch_getattr` 三段式（self-grill 修正）

**必须保留原顺序**：字段 → `lookup_method(attr_name)` → 未命中 → `lookup_method('__getattr__')`
调用（用户覆写或 `_default_getattr` fail-fast）。理由：删除分支后若直接
`lookup_method('__getattr__')`，用户自定义 `__getattr__` 将在字段查找之前接管——
破坏"字段/方法优先于用户 __getattr__"的既有语义（Python `__getattr__` 语义）。
`_default_getattr` 内部不再查 `__getattr__` 方法（防递归），三段式收尾保证 fail-fast。

### 2.4 cast_to 特殊兜底定位

`cast_to` 是普通方法名但语义特殊（converter 协议 methods 已含 `cast_to`）。设计：
receive 骨架将其保留为显式兜底分支（一处），处理器 `_dispatch_cast_to` 承载转换链。
协议注册表 converter 协议已声明该方法名——`_dunder_names()` 应包含协议方法名集合
（含普通名的协议方法），使 cast_to 也走协议索引（第 1 步命中）→ `_dispatch_cast_to`。
即 converter 协议方法名进入索引，cast_to 无特殊分支。

### 2.5 A2 属性协议化（双通道收敛）

- 删除 base.py:71-79 分支；`_dispatch_getattr` 默认实现 = `lookup_method('__getattr__')`
  调用（未命中方法时报原 AttributeError）。
- 实例属性单一实现 = bootstrapper `_default_getattr`（字段→方法→fail-fast）。
- IbClass `_dispatch_getattr` 覆写保留类字段/类方法语义（原 626-640 逻辑）。

### 2.6 op_constants 一致性（契约测试）

- `BUILTIN_PROTOCOLS` operator 元组**补齐 `__pos__`**（22→23 方法）。
- 新契约测试 `tests/kernel/test_protocol_op_constants_consistency.py`：
  - `OP_MAPPING.values()` ∪ `UNARY_OP_MAPPING.values()` ⊆ operator.methods；
  - operator.methods ⊆ `OP_MAPPING.values()` ∪ `UNARY_OP_MAPPING.values()`
    ∪ `{"__contains__", "__not__"}`（VM 固定发出点）；
  - AST_OP_MAP 值 ⊆ OP_MAPPING ∪ UNARY_OP_MAPPING 键。
- 同时覆盖 `__eq__/__ne__` 空白区：断言 operator 协议含 ==/!= 对应方法。

### 2.7 lookup_method dunder 名查询（8 处）处置

`lookup_method('__init__')`×4、`__snapshot__/__restore__`、`__from_prompt__`、
`__validate_prompt__`、`__outputhint_prompt__`、`__to_prompt__`：
- `__init__`：构造器查询属 vtable 正常路由（方法名查询，非分派分支）——保持；
  数量校验归一属阶段 B4。
- 其余协议方法查询：**保持 lookup_method**（这是 vtable 查找协议实现，正当形态），
  但前提是消费点已先经 `satisfies_protocol` 判定（大部分已做，见 1.2）。
  本阶段仅审计确认无"裸字符串查询绕过判定"的残留（iterable.py:46 除外——见 2.8）。

### 2.8 iterable 能力探测迁移

- `iterable.py:46` `lookup_method("__iter__")` → 改 `satisfies_protocol(spec, "iterable")`
  （spec 侧判定）+ 方法获取仍 lookup_method（职责分离：判定走协议、获取走 vtable）。
- `iterable.py:56` / `_shared.py:921` `to_list` 兜底：to_list 非协议方法（迭代物化
  内部约定），保持（审计后确认为内部契约，非协议化范围）。

## 3. 非目标（本阶段）

- 阶段 B 事项（self 形态统一/特化身份结构化/成员单一权威/auto-init 声明化）不提前做。
- 不新增用户面协议语法（阶段 C 后评估）。
- 不动 axiom 布尔字段（阶段 C）。
- 不改序列化格式（阶段 B2）。

## 4. 风险与对策

| 风险 | 对策 |
|------|------|
| 处理器重构引入行为漂移（如 __call__ 分支的 CPS drive 语义） | 处理器体原样搬移，逐类跑既有测试；判别性回归锁定（_UserCallDrive/_ClassInstantiateDrive 相关测试） |
| `_dunder_names()` 惰性构建的引擎隔离（多引擎并发） | 索引挂 spec registry（每引擎独立），惰性缓存 + 注册表变更失效 |
| __getattr__ 收敛后属性路径行为差异 | 先删除分支后全量测试 + T07 ATTR-READ 触发用例复跑 |
| op_constants 契约测试过度约束（未来新增运算符） | 测试断言方向按"⊆"单侧 + 显式豁免集（__contains__/__not__），新增运算符时同步更新协议元组（测试驱动） |

## 5. 实施顺序（Phase 3 计划）

1. 协议注册表：`ProtocolRegistry.dunder_names()` + 惰性索引；operator 元组补 `__pos__`。
2. IbObject 新 receive 骨架 + 默认处理器（base.py 分支搬移）。
3. 各子类处理器覆写（ib_class/optional/sentinels/functions/native_module/callables/
   runtime_context）。
4. A2：删除 base.py:71-79，_dispatch_getattr 默认实现收敛。
5. iterable.py 判定迁移 + lookup_method 审计。
6. 契约测试（op_constants 一致性 + 特化 _impl_cls + 处理器分派判别性）。
7. 全量 pytest 零回归 → 独立复核（general agent）→ 真实 LLM 复跑（T09+受影响）→
   文档同步 → commit。

## 6. 决策记录

- **D1（处理器 vs 协议条目携带行为）**：处理器为命名方法（`_dispatch_<dunder>`）而非
  ProtocolDef 扩展字段——ProtocolDef 保持纯数据（name+methods），行为归实现类
  （职责分离：协议声明行为规范、实现类持有实现细节，符合 code-quality 职责分离型
  fallback 判定与 design-philosophy 单一权威）。
- **D2（元组分支不入注册表）**：FnCallable/IbBehavior 内部元数据消息收敛为该类内部
  消息常量（集中声明），不注册为语言级协议（无第二个消费者，注册即死契约）。
- **D3（op_constants 不合并）**：kernel 层禁 runtime 导入红线 → 镜像常量以一致性
  契约测试锁定（code-quality §八 层约束处置），非"双写真相"放任。
- **D4（A3 评估为基本完成）**：get_base_name 已结构化，_impl_cls 已沿 spec 基名解析；
  本阶段补契约测试，深度结构化并入 B2。
- **D5（__getattr__ 收敛为单一实现）**：base.py:71-79 与 _default_getattr 语义等价
  （实证），删分支保 _default_getattr 为唯一属性实现（原则：双通道禁止，真合并）。
- **D6（新增 attribute 协议）**：__getattr__/__setattr__ 无协议覆盖（盘点缺口），
  新增内置协议 attribute（能力名命名，与 iterable/subscriptable 同族）。
- **D7（__getattr__ 三段式保留）**：字段→方法→__getattr__ 方法顺序不可变（用户
  覆写接管语义），处理器承载三段式，非简化为单次 lookup。
