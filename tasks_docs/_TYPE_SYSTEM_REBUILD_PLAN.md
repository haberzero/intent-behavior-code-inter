# 实施规划：类型体系地基根治 S0-S7（文档化任务规划）

> 2026-08-13 启动无人值守前落地。承接 `_TYPE_SYSTEM_REBUILD.md` v2。
> 本文件是各阶段执行清单（含判别性回归锚点）；每阶段实现细节在 WORKLOG 记录。
> 分支：独立分支 `exp/type-identity-rebuild`；每阶段全量 pytest 零回归 + 判别性回归
> + commit；确认零风险后 cherry-pick 更新 unsafe-vibe-dev；不触碰 main。

---

## S0 基线固化 + 独立分支（零风险）

- [x] 基线确认：unsafe-vibe-dev HEAD `51a1d4f8`，全量 2586/1（已实跑验证）
- [x] 建独立分支 `exp/type-identity-rebuild`（自 unsafe-vibe-dev）
- [x] 现状测试快照：`type(list[int]值)=list[int]` 等判别性基线（已探针实证：type_ref
  结构化 TypeRef('list',(int,))、ib_class.name='list[int]'、spec.element_type=TypeRef('int')）
- [x] 禁点清单：`TypeRef.of(泛型名)` 无字面量扁平构造（静态扫描 0 命中）；112 处
  `TypeRef.of(` 中 20 在 factory（合法纯名构造）、18 在 specs（原型常量）、16 在
  engine（跨模块名）、13 在 rehydrator（字符串字段还原）——逐一在 S1 审计扁平风险

## S1 桩1：创建点结构化 TypeRef 接口（P0 根治点）

目标：`list[list[int]]` 的 spec.element_type 变结构化 `TypeRef('list',(int,))`；
`substitute` 可穿透嵌套；descriptor 扁平同源治愈。
**保留物化注册**（特化 spec 仍落注册表）。

判别性回归：
- `Box[int].make(list[list[str]])` 编译期报 SEM_TYPE_MISMATCH ✓
- `type(list[list[int]]值)=list[list[int]]`（运行时身份保真）✓

状态：**已完成（2026-08-13，a8219040，全量 2592/1 零回归）**。
改动：① `TypeRef.parse` 单一权威解析器；② factory.create_* 类型承载字段结构化
（TypeRef.parse + *_ref 入口）；③ `GenericTypeDeclaration.build` 签名 List[str]→
List[TypeRef]；④ resolve_specialization/_specialize_user_class 结构化实参；
⑤ serializer canonical_name 持久化 + rehydrator 结构化重建；⑥ 运行时
_slice_type_objs_for 结构化实参递归解析。
判别性测试 +6（TestNestedGenericStructurePreserved 4 + 白盒 2），历史锚定断言 3 更新。
**待独立复核放行后 cherry-pick 更新 unsafe-vibe-dev。**

## S2 descriptor 双真相收敛（P0 连带）

目标：param_types 与 param_descriptors 单一构造源，结构一致。

判别性回归：`Box[int].make` descriptor 与 param_types 结构一致断言。

改动点：
1. `symbol_collection_pass._annotation_to_typeref`（:426-436）与
   `_declaration_visitors._param_type_ref`（:459-484）两条构造路径收敛为单一权威。
2. `_substitute_members`（_assignability.py:377-423）对两个字段输出一致。

## S3 桩2：get_base_name 单义 + 句柄类值身份物化覆盖（P1）

目标：`type(thread[int]值)=thread[int]`；`thread[int]` vs `thread[str]` 运行时区分。

判别性回归：
- `type(thread[int]值)=thread[int]`
- `thread[int] t = thread_str()` 运行时报 RUN_TYPE_MISMATCH

改动点：
1. `base.py get_base_name()`（:251-254）统一读 base_name 字段优先，消除含方括号全名。
2. `_hydrate_builtin_generic_classes`（artifact_loader.py:53-95）扩展到 THREAD/CHANNEL/
   SLOT/GENERATOR/THREAD_RESULT。
3. 句柄值创建点接入 node_to_type 侧表：comm.py:43/60、thread.py:157、user_functions.py:66、
   ib_class.py:118、leaf.py:373/394。
4. `_check_type`（runtime_context.py:56）句柄实参校验。
5. 删 sealed `_specialize` 字符串魔法回落（ib_class.py:471-481）。

## S4 桩3：特化生命周期声明驱动（P1）

目标：新增泛型类型只改声明一处；嵌套跨引擎 round-trip 结构保真。

判别性回归：嵌套泛型跨引擎 round-trip `element_type` 结构化断言。

改动点：
1. `GenericTypeDeclaration` 增 serialize/restore 钩子（或 kind_fields 驱动）。
2. `get_references()` 实现（base.py:127-138），`*_uid` 通道复活。
3. serializer/rehydrator per-kind 分支收敛为声明驱动。
4. `_parse_arg_ref`（rehydrator:212-228）与 `_build_*` 统一解析语义。

## S5 桩4：module 身份承载（P2）

目标：跨模块同名特化区分。

判别性回归：`list[geo.Point]` vs `list[graph.Point]` 区分。

状态：**已彻底根治（2026-08-13，e849f36d，破坏性 module 化非兼容双轨）**。
用户裁定允许破坏性修复。用户类身份统一 (module_path, name)：被 import 的非入口
模块用户类带 module 限定（geo.Box/graph.Box 独立 spec + 运行时类 + 特化继承 module +
序列化保真），入口/单模块保持根命名空间；SpecRegistry.current_module 上下文使模块
内裸名引用正确解析（finally 重置防污染）；rehydrator CLASS shell 传 module。
判别性测试 +1（TestCrossModuleSameNameClass）。全量 2607/1。

## S6 已知边界重估（独立语言缺口）

目标：元组解包类型检查 + -> auto 泛型实参推断 + *expr 元素级缓解。

判别性回归：每项 1+ 用例。

状态：**已完成（2026-08-13，8330cf51 + e849f36d，全量 2607/1 零回归）**。
① 元组解包类型检查（按位置 is_assignable，拦截错误类型）；② 容器字面量带实参
推断（list[int]/dict[str,int]/tuple[int,int]，auto 推断精确 + type() 内省带实参；
显式裸声明覆盖推断；**-> auto 函数返回容器实证已覆盖**）；③ **\*expr 元素级校验
（e849f36d）**：特化容器展开时元素类型与目标形参可赋值校验（list[str] *-> f(int)
编译期拦截，位置偏移经复核整改），裸容器/动态/数量不足运行期裁决（静态数量
未知本质限制保留）。
判别性测试 +6（TestTupleUnpackTypeChecking 3 + TestStarredElementTypeChecking 3）。
**已复核后 cherry-pick 更新 unsafe-vibe-dev。**

## S7 文档治理（零风险）

- [ ] `generic.py:15-16` docstring restore 残留清理
- [ ] `02_metadata_ast.md` §2.4 "类型身份单点真理"校准（若实现已达）
- [ ] `_code_generic_value_convergence.md` L1-L5 已知边界重估
- [ ] KNOWN_LIMITS 相关条目同步
- [ ] NEXT_STEPS/PENDING_TASKS/HANDOFF/WORKLOG 同步

---

## 纪律提醒

- 每阶段：全量 pytest 零回归（`~/miniconda3/envs/ibci/bin/python -m pytest tests/`）
- 判别性回归写入 tests/（缺陷修复=根因修复+tests/ 回归双交付）
- 独立复核（general agent）后确认零风险才 cherry-pick unsafe-vibe-dev
- 全程本地 commit、禁 push
- subagent 仅 general agent
