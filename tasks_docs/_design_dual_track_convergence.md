# 设计冻结：阶段 B——双轨收敛（方法 spec self 形态 / 特化身份 / 成员单一权威 / auto-init 声明化）

> 承接 `_HANDOFF_KERNEL_PROTOCOLIZATION.md` 阶段 B（P0）+ 事实检查微调（B5 F3 处置）。
> 本文件为设计阶段临时任务文档，阶段落地后按惯例归并清理。**起草中：B1 已冻结，
> B2-B5 随预研推进逐节冻结。**

## 0. 目标与验收

**目标**：消除编译期-运行期边界的双轨形态——同一事实两种形态并存：
1. 方法符号 spec 的 self 形态随编译路径漂移（H5/F1/F2）；
2. 特化身份以字符串名 `"Box[int]"` 为注册键/解析键（H6/F5）；
3. 类成员四表并存（H7）；
4. auto-init 运行时闭包 + 参数数量校验三处并存（H8/F4）；
5. `_pre_evaluate_user_classes` vm.run 重入 + 静默吞异常（F3）。

**验收**：
- spec↔运行期对象身份同构白盒契约测试；
- 字符串特化键/boxed 名桥残留归零（阶段范围内）；
- `_method_declared_spec` 回退桥删除（F2 根治）；
- 全量 pytest 零回归 + 独立复核 + 真实 LLM 复跑（T09+受影响，分类逐例一致）。

## 1. B1 方法符号 spec self 形态统一（设计已冻结）

### 1.1 现状（实证，2026-08-16）

| 产出路径 | 形态 | 位置 |
|----------|------|------|
| symbol_collection_pass（符号池初始） | 不含 self（只遍历 node.args） | symbol_collection_pass.py:404-414 |
| type_checking 回填（create_func） | **含 self**（`param_types.insert(0, current_class)` 后重建 spec 覆盖 sym.spec） | _declaration_visitors.py:393-395, 408-424 |
| 跨模块导入（EXTERNAL_MODULE） | 不含 self（member.spec = MethodMemberSpec） | scheduler.py:665-666 |
| 类成员表（运行期契约校验权威） | 不含 self（MethodMemberSpec.param_types） | ib_class.py:335-345（_init_expected_arity 成员表优先） |
| 运行期 self 注入 | **独立于 spec**：经 `node_to_symbol` 侧表解析 self 符号 UID → `define_variable("self", receiver)` | _shared.py:372-375 |

### 1.2 统一方向：**方法函数 spec 恒不含 self**（决策 B1-D1）

理由：
- 成员表（运行期权威）恒不含 self——统一后成员表与函数 spec 同构（设计语言统一）；
- 运行期 self 注入独立于 spec.param_types（实证 1.1 末行）——统一不影响调用路径；
- `_init_expected_arity` 的"首参 head 与 owner 基名比对"self 偏移启发式（ib_class.py:350-355）
  是形态漂移的规避物——统一后可删除（回归确定性，消 tricky）；
- 跨模块路径已是不含 self 形态——统一即"本模块路径向跨模块路径收敛"（消除单文件特例）。

### 1.3 改动点

1. `_declaration_visitors.py:393-395`：删除类上下文 `param_types.insert(0, self.current_class)`。
2. `_init_expected_arity`（ib_class.py:335-356）：删除 spec 回退路径的 self 偏移启发式
   （成员表优先不变；spec 回退直接 len(param_types)）。
3. **消费点全链审计（已完成，2026-08-16 实证）**：
   - 编译期方法调用参数校验：走 `param_descriptors`（策略一，_expression_visitors.py:602-607）
     与成员表（策略二）——**均不含 self**；用户方法 param_types 含 self 时与 descriptors
     数量不一致（方法场景 descriptor 双真相的又一表现）——统一后同构 ✅；
   - 运行期方法参数绑定：`params_uids` = node_data["args"]（不含 self），self 经
     `define_variable` 单独注入（_shared.py:372-375）✅ 不受影响；
   - LLM 方法 prompt 参数插值：`_get_function_param_names` 读 node_data args（不含
     self）✅ 不受影响；
   - 序列化 round-trip：统一后新旧产物形态一致（消除漂移）✅；
   - `_wrap_function_result` 方法返回包装（owner_class 成员表分支）：成员表不含
     self ✅ 不受影响。
   **结论：param_types 的 self 仅影响 spec 形态本身 + _init_expected_arity 回退，
   统一不含 self 影响面收敛、无运行路径依赖。**

### 1.4 契约测试（B1）

- 方法符号 spec.param_types 恒不含 self（单文件 + 跨模块 + impl 补充三路径断言）；
- `_init_expected_arity` 精确（含 __init__ 传参数量错误消息不变）；
- LLM 方法 prompt 参数插值不含 self；
- spec↔运行期对象身份同构（方法对象 spec = 函数 spec 且不含 self）。

## 2. B2 特化身份结构化（预研中）

### 2.1 现状（实证）

| 字符串特化名消费点 | 位置 |
|--------------------|------|
| 内置泛型特化缓存键 `f"{base}[{canonical}]"` | _assignability.py:315 |
| 用户类特化名 `f"{spec.name}[{args}]"`（注册键） | _assignability.py:338 |
| `_specialize` 运行期特化名拼接 + boxed 名回落 ×2 | ib_class.py:515, 526-529, 534 |
| `_bind_type_params` boxed 特化名符号桥 | vm/handlers/_shared.py:943+ |
| axiom `is_compatible` 前缀匹配 ×11 | sequences/comm/callable/sentinels/generator |
| 序列化/反序列化 `"[" in name` 判断 | runtime_serializer.py:750/807、artifact_rehydrator.py:23 |
| `_hydrate_user_classes` 特化类共享 AST 节点 `name.split("[")` | interpreter.py:632-633 |
| `_impl_cls` 沿 base_name 解析（已结构化 ✅） | ib_class.py:219-235 |

### 2.2 设计方向（待冻结）

特化身份结构化 = **基 spec 引用 + 实参 TypeRef 列表**（`SpecializationKey`）：
- SpecRegistry 特化注册键/解析键支持结构化查询（`resolve_specialized(base, arg_refs)`），
  字符串 canonical_name 仅作显示/序列化（派生，非权威）；
- axiom `is_compatible` 从"字符串前缀匹配"改结构化比较（family + 实参）；
- `_specialize`/`_bind_type_params` 的 boxed 名桥改结构化传递；
- 序列化 round-trip 保真（type_args/base_name 已结构化，键派生）。

**影响面**：20+ 处。**风险**：注册键/序列化形态属对外契约（artifact 格式）。
**分支政策评估**：影响面大、边界需实验确认 → 独立分支 exp/dual-track-b2 实验 + 复核后
手动更新 unsafe-vibe-dev（按 AGENTS.md 分支政策）。

## 3. B3 成员单一权威（待预研）

- 现状：`spec.members`（编译期）/ `methods`/`default_fields`/`member_types`（运行期，
  ib_class.py:150 四表并存）。
- 方向：成员表（水化驱动）为运行期权威，`methods`/`default_fields`/`member_types`
  收敛为单一成员容器（或明确分层：方法表 + 字段表 + 类型缓存，去重断言）。
- 待核验：水化路径（_hydrate_user_classes）、_wrap_field_value 的 member_types 缓存、
  序列化成员读写。

## 4. B4 auto-init 声明化（待预研）

- 现状：`_make_chain_auto_init` 运行时 Python 闭包（interpreter.py:798-808）+ 参数数量
  校验三处并存（ib_class.py:335/370/450 + 闭包内 :801-804）。
- 方向：编译期生成 auto-init 构造器声明（AST/语义 pass 或描述符），运行期不再闭包；
  数量校验单一权威（成员表）。
- 待核验：auto-init 触发路径（字段无默认值 + 无用户 __init__）、chain-aware 继承链
  字段收集（_collect_chain_decl_only_fields）、CPS 构造路径（_ClassInstantiateDrive）。

## 5. B5 F3 处置（待预研）

- 现状：`_pre_evaluate_user_classes`（interpreter.py:582-614）经 `vm.run` 重入预求值
  字段默认值 + `except Exception: pass` 静默吞异常 + issue_tracker 状态恢复 hack。
- 方向（待决断，候选）：
  a) CPS 化（预求值嵌入帧栈，与 dispatch_eager_cps 同构）；
  b) 保留预求值语义但吞异常改为诊断记录（kernel_diagnostic，不静默）；
  c) 预求值整体移除（实例化时求值——评估性能影响）。
- 待核验：`_eval_field_defaults` 实例化路径是否完整重试（决定 a/b/c）、
  issue_tracker 恢复 hack 的必要性。

## 6. 阶段顺序（B1 → B2 → B3 → B4 → B5）

依赖：B1 独立（编译期）；B2 独立（注册键/序列化）；B3 依赖 B1（成员表与函数 spec
同构后收敛）；B4 独立（编译器+运行时）；B5 独立。每个子项独立验收门
（全量零回归 + 复核 + LLM 复跑）。

## 7. 决策记录

- **B1-D1**：方法函数 spec 恒不含 self（成员表权威同构 + 运行期 self 注入独立
  + 跨模块路径已是不含形态——统一即向既有权威收敛，非新设计）。
- 其余子项决策随预研冻结。

## 8. 非目标（本阶段）

- 不动用户面语法；不改协议注册表结构（阶段 C）；不改 axiom 布尔字段（阶段 C）；
- media/并发/泛型 bound 等（goal 非目标）。
