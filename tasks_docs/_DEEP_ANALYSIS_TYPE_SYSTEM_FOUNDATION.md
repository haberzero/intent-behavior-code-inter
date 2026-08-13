# 深度分析：类型体系地基——泛型剩余边界背后的统一根因

> 2026-08-13 编制。用户怀疑"表面边界不是本质，整个泛型体系/类型体系地基存在
> 从未被注意的设计失误或历史妥协"。经三路并行 general subagent 交叉比对
> （编译端 / 运行时值层 / 特化生命周期）+ 主代理实证探针，**怀疑证实**。
> 本文档记录根因链、证据、历史来源与根治方向。全量基线 2586 passed / 1 skipped。

---

## 〇、核心结论（一句话）

**类型身份自始就是"扁平字符串名"单一权威 + "结构化 TypeRef"平行并存的双轨模型；
泛型特化在唯一创建点把嵌套实参扁平化；所有"剩余边界"都是这条地基缺陷在不同
生命周期环节的投影。** 表面 7 项边界不是本质，本质是——**类型身份没有单一
结构化权威模型**。

---

## 一、七项表面边界 → 统一根因的映射

| # | 表面边界（交接文档） | 本质根因 | 层 |
|---|----------------------|---------|----|
| 1/7 | 句柄类值身份未水化（thread/chan/slot/generator/thread_result 值 type() 裸名） | 值层类型身份单一真源=ib_class，而 ib_class 特化只在"容器字面量"路径被维护；句柄类值创建点无 node_to_type 侧表接入，实参进不了值对象 | 运行时值层 |
| 2 | `_rehydrate_type_pool_spec` 按 name 匹配（跨引擎多模块同名误选） | 特化 spec module_path 出生即 None（`_specialize_user_class` 不传 module），多模块同名三层坍缩；补 module 只是表面，先修 module 承载 | 序列化 |
| 3 | generator value_type 嵌套扁平 + `_slice_type_objs_for` 残缺实参 | 嵌套泛型实参在 resolve_specialization 创建点被扁平化（TypeRef('list[T]') head 含方括号、args 空），substitute 无法穿透 | 编译端构建 |
| 4 | 元组解包错误类型不检查 | 编译端类型检查本身是"点状补丁"而非结构化传递；解包分支用 _any_desc 跳过的根因与 ① 同一地基（无结构化身份可查） | 编译端 |
| 5 | `-> auto` 泛型实参推断 | visit_IbListExpr 返回裸 list（无实参推断）——auto 推断拿不到结构化实参 | 编译端推断 |
| 6 | `*expr` 展开实参 | 静态数量未知的**根本限制**（真局部，仅可元素级缓解） | 编译端 |
| — | GEN-5/GEN-6/spec→TypeRef 收敛/值层身份收敛（已修） | 全部是"在字符串身份上补结构"的**症状层修复**，从未回填根基 | 全部 |

> 结论：除 #6 是语言级根本限制外，其余六项都是同一地基缺陷的不同投影。

---

## 二、地基缺陷清单（按严重性）

### 缺陷 A（P0，最深根因）：内置泛型特化在唯一创建点扁平化嵌套实参

**现象（实证）**：`list[list[int]]` 特化 spec 的 `element_type = TypeRef('list[int]')`
（head 含方括号、args 空），而非结构化 `TypeRef('list',(TypeRef('int'),))`。

**证据链**：
```
_assignability.py:275  arg_names = [a.name for a in arg_specs]   # 内层名字符串
_assignability.py:282  decl.build(self.factory, arg_names, ...)  # 构建协议只吃字符串
generic.py:106-109      _build_list → factory.create_list(element_type_name=names[0])
factory.py:126-131      list_name = f"list[{element_type_name}]"
                        element_type = TypeRef.of("list[int]")   # ← 扁平化落点
```

**为什么这是根**：扁平化发生在**所有内置泛型特化的唯一创建点**（resolve_specialization），
随后被 from_spec / 赋值 / 迭代 / 成员特化四处消费。下游一切正确性押注"内层名字
恰好注册在注册表里"（`_base.py:152` 未注册即 `or resolve("any")` 静默降级）。

**历史来源**：specs.py 从首版（29d144a0）就是 string-based（`param_type_names`），
TypeRef 在 M1（3f2be172）作为"**并存不替换**的兼容桥"引入（原 docstring 明言
"TypeRef 与现有 IbSpec 体系并存，不替换"）——**双轨从第一天就存在，从未统一**。

### 缺陷 B（P0）：同一方法签名 param_types / param_descriptors 双真相

**现象（实证）**：`Box[int].make` 特化后：
```
param_types:       [TypeRef('list',(TypeRef('list',(TypeRef('int'),)),))]   # 已替换+结构化
param_descriptors: [ParamDescriptor(type_ref=TypeRef('list',(TypeRef('list[T]'),)))]  # 未替换+扁平
```

**证据链**：同一签名两个独立构造源——
- param_types：symbol_collection `_annotation_to_typeref`（symbol_collection_pass.py:426-436）
  从 AST **直接递归构造结构化 TypeRef** → substitute 成功。
- param_descriptors：type-check `_param_type_ref` → `TypeRef.from_spec(arg_type)`
  （_declaration_visitors.py:459-484）→ arg_type 已被缺陷 A 扁平化 → substitute 失败。

**危害（实证）**：`Box[int].make(list[list[str]])` 编译通过（错误实参静默放行）——
调用侧 `_resolve_call_arguments` 优先消费 descriptors（_expression_visitors.py:463-468），
恰好消费损坏的那份。违反 design-philosophy §一 单一权威源。

### 缺陷 C（P1）：get_base_name() 双轨 + base_name 字段旁置

**现象（实证）**：
```
list[int]:  get_base_name()='list'     # 经 _KIND_BASE_NAMES
Box[int]:   get_base_name()='Box[int]' # 走 self.name fallback（含方括号）
            base_name 字段='Box'        # 有独立权威字段却不被读取
```
base.py:251-254 的 get_base_name() 不读 base.py:218-220 的 base_name 字段。
运行时 `_impl_cls`（ib_class.py:215）拿 `get_base_name()='Box[int]'` 查实现类
永远失败 → 用户泛型类实例回落裸 IbObject（基类名解析机制失效）。
编译端因用户类无 axiom 而"碰巧无害"，是掩盖而非解决。

### 缺陷 D（P1）：值层类型身份地基——句柄类值创建点无特化绑定

**现象**：`type(thread[int]值)` = `thread`（裸名），`type_ref` 无实参。

**证据链**：
- 水化白名单硬编码只含 LIST/TUPLE/DICT/OPTIONAL（artifact_loader.py:76-81）。
- 值创建点全部硬编码裸基类名且**无 node_to_type 侧表**：comm.py:43/60、thread.py:157、
  user_functions.py:66、ib_class.py:118、leaf.py:373/394、primitive_initializer.py:725。
- 全仓唯一"值→特化类重绑点"是容器 `_bind_container_specialization`（leaf.py:478-530）。
- `_check_type`（runtime_context.py:56）只校验不重绑；对裸 spec（src_args 空）恒经
  axiom 前缀匹配放行（_assignability.py:96-97/115-117）→ thread[int]/thread[str]
  运行时无法区分。

**判定**：容器有"侧表+重绑"机制，句柄没有——**不对称是结构性设计缺口**。仅把
THREAD 等加入水化白名单不足：水化出的特化类无人引用；必须给句柄值创建点接入
与容器同构的"声明类型→特化类重绑"机制。

### 缺陷 E（P1）：sealed 运行时字符串魔法回落是活路径

**现象**：`_specialize`（ib_class.py:423-499）三条路径中两条返回 boxed 字符串
（`registry.box(f"{name}[...]")` → 真实 IbString 值，非类型对象）。sealed 是
运行时常态（engine.py:385 STAGE_7 seal）。

**危害（实证）**：`t = list[int]` 表达式（sealed）求值返回 IbString → `type(t)`='str'
身份撒谎；`_bind_container_specialization` 以 `isinstance(IbClass)` 鸭子守卫静默降级。
违反"禁止字符串魔法"且无 fail-fast。

### 缺陷 F（P1）：特化生命周期是手工并联表，声明机制半成品

**证据**：新增一种泛型需同步补 ≥7 处（factory + generic 声明 + serializer + rehydrator
shell + fill + from_spec + _generic_spec_args + artifact_loader），无机制防漏。
GENERATOR 事件（7de1818c 由复核发现漏 serializer+rehydrator）是实证。
`GenericTypeDeclaration`（generic.py:50-67）只剩 build+resolve_member，serialize/
restore 环节根本不经过它；restore 因"rehydrator 是独立实现"被判死删除（32ebc54d），
恰好证明两轨已分道。

### 缺陷 G（P2）：序列化/水化多重信息丢失

- `get_references()`（base.py:127-138）默认返回 {}，TypeDef 未覆写 → serializer.py:254
  的"多态收集 *_uid"是**死通道**，rehydrator 的 uid 重建分支（:259/264/272）永久死代码。
- 跨引擎水化缺内层 spec（实测：target 引擎无 list[int] 时 resolve_typeref 返回 None）
  → `is_assignable` 走 `or resolve("any")` → 类型检查静默擦除。
- `_parse_arg_ref`（artifact_rehydrator.py:212-228）只服务 CLASS parent_args/type_args，
  容器实参扁平——**同一类型因"实参位"不同结构不同**（Box[list[int]] 结构化 vs
  list[list[int]] 扁平）。
- type_ref 序列化写入（runtime_serializer.py:242）**从不恢复**（_get_instance 不读）；
  符号 declared_type 反序列化丢弃（_deserialize_symbol 只重建 name/value/is_const）。
- 特化 spec module_path=None 出生即丢（缺陷 A 同源）→ 多模块同名坍缩三层。

### 缺陷 H（P2）：特化名缓存键/序列化 UID/运行时类名三处独立拼接

`candidate_key`（_assignability.py:278）、`specialized_name`（ib_class.py:449）、
`type_uid(module,name)`（serializer.py:158）三处独立。不一致窗口：
- 跨模块实参坍缩：`list[geo.Point]` vs `list[graph.Point]` 同键 `"list[Point]"`。
- multi-type list 排序：factory 对 allowed 名排序（factory.py:110-116）vs candidate_key
  用原始序（:278）→ 缓存永不命中。
- `resolve_specialization` 按 get_base_name() 查声明无 kind 守卫 vs `from_spec` 按 kind
  分派——`class list[T]`（kind=CLASS）被路由到内置 list 声明。

---

## 三、根因链统一叙述

```
地基决策（历史）：
  IbSpec 身份 = (module_path, name) 扁平字符串   [29d144a0]
  TypeRef 作为"并存不替换"的兼容桥引入           [3f2be172]
  TypeDef 存储迁到 TypeRef，但 name 仍是注册表键  [c23f2a5b/871383e8]
  GenericTypeRegistry build 协议仍是字符串接口     [d8145680]

       │
       ▼
缺陷 A：唯一特化创建点把嵌套实参扁平化（TypeRef.of("list[int]")）
       │
       ├──▶ 缺陷 B：descriptor 路径 substitute 失效 → 错误类型静默放行
       ├──▶ 缺陷 G：序列化/水化丢结构 + 跨引擎类型检查擦除
       ├──▶ 缺陷 C：get_base_name() 双轨 → 运行时 _impl_cls 失效
       ├──▶ 缺陷 D/E：值层身份只服务容器路径，句柄无绑定 + sealed 字符串魔法
       ├──▶ 缺陷 F：声明机制半成品，serialize/restore 手写并联表
       └──▶ 缺陷 H：三处独立拼接特化名 → 缓存/UID/类名不一致
```

**真正的最深根因**：类型身份自始就是"扁平字符串名"单一权威，TypeRef 从未真正取代
字符串成为身份唯一模型（原 docstring 明确"并存不替换"）。之后所有泛型机制
（thread、fn_callable、generator、用户类泛型）都在这个双轨上叠加，每次修复都是
"在字符串上补结构"（from_spec / _parse_arg_ref / _bind_container_specialization /
parse_arg_ref 等局部解析器），从未回填根基。GEN-5/GEN-6/spec→TypeRef 收敛/值层
身份收敛（2026-08-13 已修四轮）都是这个意义上的症状层修复。

---

## 四、历史来源时间线

| commit | 事件 | 留下的地基问题 |
|--------|------|---------------|
| 29d144a0 | 建立 spec/ 层，specs 用 `param_type_names` 字符串 | string-based 起点 |
| 3f2be172 | TypeRef M1 引入，"并存不替换" | 双轨从第一天存在 |
| c23f2a5b/871383e8 | TypeDef 存储迁 TypeRef | name 仍是键，双轨未消 |
| 081a8e18 | 具体 Spec 子类统一为 TypeDef | 字段扁平存 TypeRef.of |
| d8145680 | GenericTypeRegistry 统一泛型模型 | build 协议仍是字符串 |
| 648688a0 | chan/slot 纳入统一泛型模型 | 嵌套扁平化问题潜伏 |
| c8b89564 | 阶段5 generator[T] | 新 kind 手工补丁开始 |
| 2026-08-13 四轮 | GEN-5/GEN-6/spec→TypeRef/值层收敛 | 症状层修复（本轮分析确认） |

---

## 五、七项边界 → 根治方向重估

| # | 原交接建议 | 本分析修正 |
|---|-----------|-----------|
| 1/7 | 机制同构水化句柄类 | **正确方向，但须先给句柄值创建点接入 node_to_type 侧表 + rebind 机制**（仅加水化白名单不足） |
| 2 | 补 class_module 联合匹配 | **先修特化 spec module_path 承载**（缺陷 A 同源），否则补了也白补；运行时 IbClass name-only 表是天花板 |
| 3 | create_* 支持结构化 TypeRef | **根治点**：`GenericTypeDeclaration.build` 实参从 List[str] 改 List[TypeRef]，`create_*` 接受结构化（或内置解析器），消除唯一创建点的扁平化 |
| 4 | 元组解包按位置 is_assignable | 方向对，但依赖 ③ 的结构化身份 |
| 5 | 容器字面量自身推断带实参 | 依赖 ③（visit_IbListExpr 需能从结构化 spec 推断） |
| 6 | *expr 元素级缓解 | **真局部**，根本限制成立 |

---

## 六、判定与建议

1. **用户怀疑证实**：7 项表面边界中 6 项（除 #6 语言级限制）同源于"类型身份无单一
   结构化权威模型 + 特化创建点扁平化"这一地基缺陷。这不仅是泛型体系问题，也涉及
   编译器（创建点/descriptor 双真相/推断）与运行时（值层身份/字符串魔法）两侧，以及
   序列化/水化全生命周期。
2. **根治方向（地基层）**：把 `GenericTypeDeclaration.build` 与 `SpecFactory.create_*`
   从"字符串接口"升级为"结构化 TypeRef 接口"，让嵌套实参在创建点结构保真——这是
   单一最深处改动，能同时治愈 B/C/D/G/H 的下游。
3. **当前交接文档 `_HANDOFF_GENERIC_REMAINING.md` 的处理顺序建议更新**：先做 #3
   （结构化构建，根治点）而非 #2（name 匹配，表层补丁）。
4. 本分析**未改动任何代码**；改动方案待后续独立分支实验（分支政策：无法确认边界
   走独立分支，确认零风险直接合并 unsafe-vibe-dev，不触碰 main）。
5. 残留扫描：`generic.py:15-16` docstring 仍把已删的 `restore` 列为声明生命周期操作
   ——文档与实现脱节（随根治一并清理）。
