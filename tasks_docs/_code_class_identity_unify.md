# 设计：同名类运行时类表宏观根治——统一类身份模型（底层→顶层）

> 2026-08-14 编制。用户授权破坏性重构：从整个架构、底层到顶层、整个宏观体系
> 彻底改善同名类运行时类表相关工作，不留历史包袱、不做兼容性修复、不做
> tricky/快速修复。独立分支 `exp/class-identity-unify` 实验，确认零风险后
> 手动 cherry-pick 更新 unsafe-vibe-dev；不触碰 main；禁 push。

## 一、宏观现状（实证审计）

编译期 spec 身份 = `(module_path, name)`（S5 已 module 化）；运行期类表键 =
`spec.qualified_name`（S5 运行期闭环 6e68329c）。**但宏观模型仍有四处历史
包袱**，形成"统一身份"与"特例并存"的双轨：

1. **入口模块类 module_path=None（裸键）**：`scheduler.py:179`
   `qualify_types=(file_path != entry)` → 入口模块类 `module_path=None`，
   spec.qualified_name = 裸名（"Box"）；被 import 模块类 = 模块限定
   （"geo.Box"）。同一"类身份"概念在入口/导入两端形态不同（设计语言不统一，
   design-philosophy §二）。
2. **get_class 回落裸名依赖**：`registry.py:363-367` module 感知查找 miss 后
   回落裸名键。热路径 `declarations.py:169-171`（每次类定义语句）依赖此回退
   命中入口类（module="main" → miss "main.Box" → 回退 "Box"）。回退是
   "入口裸键"的寄生机制（tricky/隐式约定，工作模式定论 #3）。
3. **双类表**：`KernelRegistry._classes`（A 表，事实权威）+
   `Bootstrapper._class_registry`（B 表，A 的写穿影子 + Enum 缺口——Enum 仅
   注册 A 不经 B，两处 [Enum Hook] 兜底即为此服务）。双表违反单一权威源
   （design-philosophy §一）。
4. **KI-1 线程裂缝**：task_ec 的 `get_side_table` 回调绑定 `interpreter.get_side_table`
   （coordinator.py:213），该方法读**主 interpreter 共享** `current_module_name`
   （interpreter.py:350-352 → `self._execution_context`），忽略 task_ec 任务本地
   切换（_shared.py:261）。**同族第二裂缝**：`interpreter.is_truthy`（coordinator.py:218
   绑定）读主 runtime_context（interpreter.py:860），线程内 LLM 模糊布尔判定
   （llmexcept 帧检测）读错上下文。

## 二、根治方向：统一类身份模型（宏观统一）

**目标模型**：*每一个用户类（含入口模块类）的身份 = `(module_path, name)`，
module_path = 其定义模块名；内置/内核类 module_path=None（根命名空间裸键）。
`get_class` 的 module 感知回落仅用于内置父查找，不再命中入口用户类。*

| 面 | 现状 | 统一后 |
|----|------|--------|
| 入口模块类 spec.module_path | None（裸键 "Box"） | 模块名（"main.Box" / run_string 锚点名） |
| 入口模块类运行期键 | 裸键 | qualified 键（与导入模块对称） |
| get_class 回落 | 命中入口裸键（declarations.py 依赖） | 仅内置/根命名空间（语义收窄为合法回退） |
| `_class_key`（interpreter.py:625-628） | entry→裸名 / 非entry→qualified | 统一 qualified |
| 双类表 | A 表 + B 表影子 + Enum 缺口 | 单表（Bootstrapper 全委托 KernelRegistry） |
| 线程侧表/is_truthy | 读主 interpreter 共享状态 | 读任务本地 EC / ContextVar |

### 2.1 类身份统一（S1-S2）

- **编译期**：`scheduler.py:179` `qualify_types` 恒 True（或删参数化）——所有
  模块（含入口）用户类 module_path = 模块名；`symbol_collection_pass.py:173`
  `class_module = self.context.module_name`。run_string 合成入口需稳定模块名
  锚点（当前临时文件派生名非确定，见 S1）。
- **运行期**：
  - `interpreter.py:625-628` `_class_key` 删入口特判 → 恒 `f"{module}.{name}"`。
  - `registry.py:363-367` `get_class` 回落语义收窄：module 且裸名 → 先查
    `{module}.{name}`，miss 回落裸名（仅命中内置/内核类——入口用户类已不再
    注册裸键，回退不再误命中用户类，变成确定性合法回退）。
  - `declarations.py:169-171` 类定义语句 `get_class(name, module=current_module)`
    → 直接命中 qualified 键（回退依赖消除）。
  - `_hydrate_user_classes` `resolved` 键全部 qualified，`"["` 前缀解析
    （"geo.Box[int]" → "geo.Box"）自然对齐。
  - `resolve_class_module`（registry.py:369-390）：入口类 module_path 不再 None，
    "内置/入口不加前缀"语义收缩为"仅内置不加前缀"；父链补全逻辑简化。

### 2.2 单类表（S3）

- `Bootstrapper` 删 `_class_registry` 字段，`register_class`/`get_class`/
  `get_all_classes`/`create_subclass` 全部委托 `KernelRegistry`；`box` 内部
  `get_class` 改读 registry；`primitive_initializer.py:418,515` 改 registry 直查；
  删 bootstrapper.py:188-190 与 registry.py:417-419 的 [Enum Hook] 兜底
  （单表后自动弥合）；注释/docstring 同步。

### 2.3 KI-1 + 同族裂缝（S4）

- **get_side_table module 参数**：`interpreter.get_side_table(table, key,
  module=None)` 增加显式 module 参数；`ExecutionContextImpl.get_side_table`
  （execution_context.py:216-217）透传 `self._current_module_name`——任务本地
  EC 的 current_module_name 是 task_ec 自己的值（_shared.py:261 已切），侧表
  查询以调用方 EC 为准。主 interpreter 场景 module 为空时回落自身
  `self.current_module_name or entry_module`（行为不变）。
- **is_truthy 任务本地化**：`interpreter.is_truthy` 改用
  `get_current_execution_context().runtime_context`（ContextVar 路径，
  coordinator 已 `set_current_execution_context(task_ec)`）替代
  `self.runtime_context`——线程内 llmexcept 帧检测读任务本地上下文。
- **判别性回归**：T05 D1-10 用例（thread + `geo.Box(5).get()` 线程内 405）；
  线程内 `if str_var:` 模糊布尔 llmexcept 判定正确。

## 三、分阶段实施（独立分支 exp/class-identity-unify，每阶段全量零回归门）

| 阶段 | 内容 | 风险 | 判别性回归 |
|------|------|------|-----------|
| **S0** | 基线固化 + 独立分支 | 零 | 全量 2614/1 |
| **S1** | run_string 稳定入口模块名锚点（合成 entry 名固化，消除临时路径名） | 低 | run_string 入口类键稳定可复现 |
| **S2** | 类身份统一：编译期恒 qualify_types + 运行期 `_class_key` 统一 + get_class 回落收窄 | 中 | 入口类 `main.Box` 与 geo.Box 隔离；declarations 直命中；`_class_key` 全 qualified |
| **S3** | 单类表：Bootstrapper 委托 KernelRegistry | 中 | Enum 无 [Enum Hook] 仍正确；全量零回归 |
| **S4** | KI-1 + is_truthy 任务本地化 | 中 | T05 D1-10 线程 worker 405；线程内 llmexcept 模糊布尔 |
| **S5** | 文档治理 + KNOWN_LIMITS §10.2 更新 + 独立复核 + 手动 cherry-pick | 零 | 全量零回归 + 复核放行 |

> 阶段顺序依赖：S1（稳定锚点）是 S2（入口类 qualified 化）的前置（否则入口
> 类键随临时路径名漂移，序列化/round-trip 不可复现）；S2 与 S3 正交可并行但
> 按序更安全（S2 先统一身份，S3 再统一存储）。

## 四、纪律

- 独立分支 `exp/class-identity-unify`；每阶段全量 pytest 零回归 + 判别性回归
  + commit；确认零风险后手动 cherry-pick 更新 unsafe-vibe-dev。
- 逐项 code-workflow Phase 0-5 + 独立复核（general agent）。
- 不触碰 main；禁 push；WORKLOG 详尽记录决策与变化前后。
