# 设计：跨模块同名类运行时类表 module 化（S5 运行期根治）

> 2026-08-14 编制。承接 `_HANDOFF_GENERIC_REMAINING.md` §九（用户 2026-08-14 指出）。
> 编译期/元数据层已 module 化（S5，e849f36d）；本设计完成**运行时类表** module 化，
> 从底层到顶层闭环跨模块同名类身份隔离。破坏性重构（用户授权），不留历史包袱、
> 无 compat/tricky/快速修复。独立分支 `exp/runtime-class-module` 实验。
>
> **✅ 已被 `_code_class_identity_unify.md`（S2-S3，2026-08-14）超越**：本设计的
> "入口/单模块与内置类保持裸名"已被推翻——统一类身份模型下入口模块类亦
> qualified（module_path=模块名），Bootstrapper 影子表删除（单类表）。本文件
> 保留为 S5 阶段设计历史，宏观统一见 `_code_class_identity_unify.md`。

## 一、问题定义（实证）

`geo.Box`（`get() -> int`，体 `self.v+100`）与 `graph.Box`（`get() -> str`，
体 `self.name+"!"`）被入口 import 后：`geo.Box[int](5).get()` 报
`int.__add__ failed: unsupported operand type(s) for +: 'int' and 'str'`——
geo 的 `get()` 方法体被 graph 覆盖（运行期 `_classes`/`_class_registry` 均按
裸名 `ib_class.name` 索引，两个同名类坍缩为一个 IbClass，方法表按后编译者覆盖）。

## 二、根因（统一身份模型断裂）

编译期 spec 身份 = `(module_path, name)`（S5 已根治，`spec.qualified_name` 区分）；
**运行期 IbClass 身份 = 裸 `name`**（`KernelRegistry._classes[name]` +
`Bootstrapper._class_registry[ib_class.name]`）。编译期与运行期类身份键不对称，
运行期坍缩使 S5 的编译期隔离在运行期失效。

## 三、设计：运行期类身份 = spec.qualified_name（宏观统一）

**核心原则**：运行期 IbClass 注册键 = `spec.qualified_name`（module_path 非空时
`f"{module}.{name}"`，否则裸名——入口/单模块与内置类保持裸名，零影响）。IbClass.name
保留裸名（`type()` 显示、方法查找、`_impl_cls`）。`get_class` 升级为 module 感知。

### 3.1 IbClass（core/runtime/objects/kernel/ib_class.py）

- 新增属性 `module_path`/`qualified_name`（自 spec 派生，单点真理；spec 绑定于注册期，
  运行期恒可用）。
- `_specialize` module 化：
  - 特化名 = `f"{self.qualified_name}[{args}]"`（`geo.Box[int]`）。
  - `get_class(specialized_name)`（精确键）。
  - `spec_reg.resolve(specialized_name)`（spec registry 键同为 qualified）。
  - 父链：parent_type 无 module 时以 `specialized_spec.module_path` 补全
    （同模块父，parser 仅支持单标识符父名）；`parent_name = p_ref.qualified_name`。

### 3.2 KernelRegistry（core/kernel/registry.py）

- `register_class`：键 = `spec.qualified_name`；校验保持 `spec.name == name`（裸名）。
- `get_class(name, module=None)`：module 且 name 无点 → 先查 `{module}.{name}`，
  miss 回落裸名；module 空或 name 含点 → 精确查键。
- `create_subclass`：键 = `descriptor.qualified_name`；父查找 module 感知
  （`get_class(parent_name, module=descriptor.module_path)`）。
- `make_llm_*` 错误构造器：内置名（module=None）不受影响。

### 3.3 Bootstrapper（core/runtime/bootstrapper.py）

- `_class_registry` 键 = `spec.qualified_name`（镜像 KernelRegistry）。
- `register_class`/`get_class`/`create_subclass` 同步 module 化（含 `[Enum Hook]`
  的 `registry._classes` 回落改用 module 感知 get_class）。
- `box()` 内置名查找不受影响。

### 3.4 artifact_loader（core/runtime/loader/artifact_loader.py）

- 用户类水化：`create_subclass(cls_desc.name, cls_desc, parent_name)`——
  键来自 spec（qualified）；`parent_name` 用 `cls_desc.parent_type.qualified_name`
  （module 缺失以 `cls_desc.module_path` 补全）；重复检查
  `get_class(cls_desc.name, module=cls_desc.module_path)`；父查找
  `get_class(parent_name, module=cls_desc.module_path)`。
- `_hydrate_builtin_generic_classes`：仅内置 kind（module=None），不受影响。
- `class_to_node` 键改 `(module_name, name)` 元组（消跨模块同名键碰撞）。

### 3.5 interpreter._hydrate_user_classes（core/runtime/interpreter/interpreter.py）

- class_to_node 键（元组）→ 运行期类键（entry 模块裸名 / 非 entry qualified）。
- 特化类映射：`get_all_classes()` 键已 qualified，`"["` 前缀解析仍正确
  （`geo.Box[int]` → `geo.Box`）。
- 两 pass 均按运行期类键 `get_class(qname)` 查找。

### 3.6 VM / 类型解析消费点

- `vm_handle_IbClassDef`：`get_class(name, module=executor.ec.current_module_name)`。
- `leaf.py _resolve_specialized_class`：`specialized_name = ref.qualified_name`；
  `get_class(ref.head, module=ref.module)`；递归实参同。
- `leaf.py _bind_container_specialization`：内置容器（module=None）不受影响；
  `specialized_name` 经 spec（builtin 裸名）保留。
- `leaf.py vm_handle_IbCastExpr`：`get_class(target_descriptor.name,
  module=target_descriptor.module_path)`。
- `runtime_context._check_type`（句柄 rebind 分支）：`get_class(declared_type.name,
  module=declared_type.module_path)`。`_wrap_optional`（OPTIONAL 内置 kind，
  module_path=None，键=裸名）无需 module 化（实现保持）。
- `_shared.py _resolve_type_identifier`：`get_class(arg_ref.head, module=arg_ref.module)`。

### 3.7 序列化 round-trip（core/runtime/serialization/runtime_serializer.py）

- `_collect_instance`/`_collect_class_ref`：存 `ib_class.qualified_name`（内置/
  入口类 qualified==裸名，零影响；跨模块用户类存 `geo.Box[int]`）。
- `_get_instance`：`get_class(cls_name)` 精确键。
- `_hydrate_specialized_class`：`resolve(cls_name)`（qualified 键）；父 = 
  `get_class(spec.get_base_name(), module=spec.module_path)`（`geo.Box[int]` 父 `geo.Box`）；
  `create_subclass(cls_name, spec, parent_name=<qualified 父>)`。
- `_rehydrate_type_pool_spec`：按 `(module_path, name)` 联合匹配（修 #2 按 name 匹配）。

### 3.8 编译期父引用 module 补全（S5 遗留缺口）

- `symbol_collection_pass.visit_IbClassDef`：`parent_type` 构造时解析父 spec 的
  module_path（非入口模块内 `resolve(parent_head)` 经 current_module 命中带 module
  的父 spec）→ `TypeRef.generic(..., module=parent_module)`。序列化已存 parent_module，
  round-trip 保真。

### 3.9 LLM 类型解析（边界，尽力而为）

- `_prompt.py` node_to_type 路径：`get_class(type_name, module=node_to_type.module_path)`
  （已同步 module 化）。
- `returns_data` 裸名路径（AST `IbName` 无 module）：跨模块 LLM 输出类型为 niche
  边界，登记 KNOWN_LIMITS §10.2（graceful 退化：`can_handle` 查不到 → 默认解析，
  不误配到异模块同名类）。

## 四、判别性回归（缺陷=根因修复+tests/ 双交付）

1. `geo.Box[int](5).get()` = 105（int 语义）；`graph.Box[str]("hi").get()` = "hi!"
   （str 语义）——方法表不串扰（现有测试只查 `type()`，未触及方法体语义，补强）。
2. 同名非泛型类跨模块（`geo.Wrap`/`graph.Wrap`）互不干扰。
3. 跨引擎 round-trip：geo.Box 实例序列化→反序列化 class_name 保真。
4. 泛型继承同模块父（`class Sub[T](Box[T])` in geo）特化父链正确。
5. 既有单模块/入口类全部零回归（键=裸名，行为不变）。

## 五、纪律

- 独立分支 `exp/runtime-class-module`；全量 pytest 零回归 + 判别性回归 + 独立复核。
- 确认零风险后手动 cherry-pick 更新 unsafe-vibe-dev；不触碰 main；禁 push。
- WORKLOG 详尽记录决策与变化前后。
