# 反射规避架构缺陷全仓排查 — 扫描记录与修复检查清单

> **状态**：扫描 + subagent 复核已完成（2026-08-02）；组 1/2/3/5/6/7 已完成，组 4 待修复，组 8 已记录待处理。
> **性质**：正式独立任务文档（非临时）。扫描结论已收敛，本文档为后续修复的唯一事实来源与固定检查清单。
> **关联**：下一任务定义见 `NEXT_STEPS.md`；判定基准见 `.opencode/skills/code-quality/SKILL.md`；**用户工作习惯与质询模式见 `tasks_docs/WORK_HABITS.md`**。
> **工作模式定论**：禁止 compat shim / 胶水 / tricky / 过程式硬编码分发；协议驱动；质量优先于速度。

---

## 一、扫描概况

- 范围：`core/` + `ibci_modules/`（256 文件，约 40k 行）。`tests/` 不在本次范围。
- 命中面：`hasattr` 64 文件、`getattr`+default 51 文件、`except` 家族 5+32 文件、`type()`/`isinstance` 辅助面，共约 780 处。
- 方法：6 家族分组，6 个 subagent 并行独立复核（逐点读代码、交叉验证协议/调用方/设置方）。
- **核心结论**：未发现"用反射恶意穿透以绕开架构设计"的案例。核心模式是 **协议声明滞后于实现 + 接口损坏后被迫穿透 + 历史手势残留**，与 PT-HEALTH-1 同族。

### 判定基准（固定）

| 分类 | 含义 | 动作 |
|---|---|---|
| A=职责分离合法 | 协议/能力声明层声明行为规范，调用方按协议分派；或外部异构对象（插件/第三方库）反射 | 保留 |
| B=穿透应修 | 已知类型上探测未声明方法/属性，或穿透私有属性 | 修架构根因（并入协议/补公开接口） |
| C=外部异构合法 | 插件固定命名嗅探、SDK 对象探测、kernel 分层强制的鸭子类型 | 保留 |
| D=合法类型判定 | isinstance/callable/Enum.name/`vars()` 遍历等标准惯用法 | 保留 |
| 死代码/双通道 | 零调用者、双写真相、恒真/恒假探测 | 删除或收敛 |

---

## 二、缺陷组总览

| 缺陷组 | 性质 | 处置方向 | 需上报 |
|---|---|---|---|
| 组 1：LLM 协议声明滞后 | 契约漏声明 → hasattr 探测 | 并入 `ILLMProvider`/`LLMExecutor`/`IILLMExecutor`/`IHostService` 协议 | 是（契约变更，非破坏性）✅ 已完成 |
| 组 2：插件能力注册与模块导入体系 | **复合缺陷**：能力注册双通道（坏入口+死入口+脏数据）+ `import *` 双路径分裂（运行时损坏）+ 隐式契约（私有属性注入）+ 加固层被绕过 | 跨子系统重构（§四 4.1-4.4） | 是（需确认方向） |
| 组 3：异常做能力探测 | 吞 `InterpreterError` 误报"不可迭代" | 协议/类型判定 + 窄捕获 | 否 |
| 组 4：序列化/私有属性穿透 | setattr 私有 + 读 `_uid_to_symbol` + 缺公开接口 | 改公开接口/补缺失方法 | 部分 |
| 组 5：静默兜底掩盖错误 | 吞错后继续产生错误结果 | fail-fast | 否 |
| 死代码/双通道/半接通 | 零调用、双写真相、恒假探测 | 删除或激活 | 否 |
| 组 6：orchestrator 注入双通道 + 生产死参数链 | 构造注入链恒失效，真实注入靠事后 setter 同步 | 收敛单一注入路径 ✅ 已完成（§三-A） | 是（构造签名变更）✅ 已裁决方案 A |
| **组 7：组 1 深度复核新发现**（组 1 修复掩盖的深层缺陷） | hydrate 冗余钩子 + leaf 死分支 + getattr 遗漏 + 协议过度承诺 | 见 §三-B | 部分 |
| **组 8：非 hasattr 反射面重复核**（用户质询"过度聚焦 hasattr"后新增） | 异常字符串嗅探 + 能力名裸字符串契约 + 签名提取静默降级 + `__getattr__` 透传安全矛盾 | 见 §三-C | 部分 |

---

## 三-A、缺陷组 6：orchestrator 注入双通道 + 生产死参数链【已修复】

> **发现背景**：组 1 修复后的自我质询中，`set_orchestrator` 分支曾被误判为"死代码"（质询 14）。用户指出"误判可能暴露设计不一致"，经完整时序追踪确认：**该分支是功能必需代码，但恰好掩盖了 orchestrator 注入链的构造死参数缺陷**。误判本身是设计缺陷的症状信号。
>
> **修复状态**：方案 A 已实施（2026-08-02），全量 pytest 1263 passed / 4 skipped。

**根因**：orchestrator 注入存在"双通道"——生产路径的构造注入链恒失效（死参数），真实注入完全依赖 `set_orchestrator` 事后同步。这违反"双通道被禁止"（code-quality §一.3）与"单点真理"（§五）。

### 完整时序（生产路径）

```
_prepare_interpreter (engine.py:302):
  A. rt_scheduler.spawn()          # rt_scheduler.service_context 此时未 hydrate（None）
     ├ sc = None
     ├ Interpreter(orchestrator=kwargs.get('orchestrator', ...))   # spawn 未传 → None
     │    └ ServiceContextImpl(orchestrator=None)                  # sub_sc._orchestrator = None
     ├ HostService(orchestrator=sc.orchestrator if sc else None)   # sc 是 None → None
     └ sub_sc.set_host_service(host_service)
  B. set_orchestrator(self)         # sub_sc._orchestrator = engine；★真实注入点
     └ 同步 host_service.orchestrator = engine                      # ★同步分支（功能必需，非死代码）
  C. rt_scheduler.hydrate(sub_sc)
```

### 问题点清单（方案 A 已修复 6.1-6.3；6.4 保留为必要同步；6.5 组 1 已处理）

| # | 位置 | 问题 | 处置 |
|---|---|---|---|
| 6.1 | `HostService.__init__` 的 `orchestrator` 参数（`host/service.py:38`） | 生产路径恒传 None，构造注入失效；但测试路径有效（验证 None 守护分支）→ 构造注入与 setter 注入**双通道** | ✅ 删构造参数，`_orchestrator = None` 初始，统一经 `set_orchestrator` 注入 |
| 6.2 | `Interpreter.__init__` 的 `orchestrator` 参数 → `ServiceContextImpl.__init__`（`interpreter.py:127,225` / `service_context.py:29`） | 恒 None（spawn 时 sc 未 hydrate），随后被 `set_orchestrator` 覆盖 → **死参数链** | ✅ 删 Interpreter 构造参数 + ServiceContextImpl 构造参数 |
| 6.3 | `rt_scheduler.py:77` `kwargs.get('orchestrator', getattr(sc, 'orchestrator', None) if sc else None)` | sc 此时恒 None → 恒 None；且 `orchestrator` 已入 ServiceContext 协议，getattr 冗余 | ✅ 删除（rt_scheduler.py:77 与 HostService 构造的 :92） |
| 6.4 | `set_orchestrator`（`service_context.py:121`）承担隐式副作用 | 命名是"set_orchestrator"，实际同时同步 host_service.orchestrator——副作用不透明，造成误判 | ✅ 保留为**唯一注入点**（功能必需）；docstring 明示"唯一注入 + 同步" |
| 6.5 | 本次组 1 U3 的 `IHostService.orchestrator` property + 去 hasattr | 建立在"HostService 有正常注入"的未验证假设上；真实注入机制是误判后才发现的 | ✅ 组 1 处理；方案 A 后注入路径已收敛，假设已证实 |

**影响面**：所有 Engine 实例（含子引擎 request_isolated_run/spawn_isolated 创建的全新 IBCIEngine）都依赖 `set_orchestrator` 事后同步，构造注入链在所有路径下均失效。

**验证**：删除 6.4 同步分支后 `test_run_isolated_still_works` 等 9 测试失败（`Kernel Orchestrator not available`）；恢复后 1263 passed。证明分支功能必需，缺陷在构造链而非同步分支。方案 A 后全量 pytest 1263 passed / 4 skipped。

### 修复方向（已选方案 A）

| 方案 | 做法 | 评价 |
|---|---|---|
| **A（已实施）** | 收敛单一注入：`HostService`/`Interpreter`/`ServiceContextImpl` 构造器删除 orchestrator 参数；orchestrator 统一经 `set_orchestrator` 注入；删除 rt_scheduler.py:77 死值 | ✅ 消除双通道 + 死参数链；测试构造改为 setter 注入 |
| B | 保留构造参数但修复时序：spawn 前先 hydrate rt_scheduler 并设 orchestrator | 循环依赖（Engine→spawn→Interpreter→sc→orchestrator→Engine），架构上不可行 |
| C | 最小修补：仅删 rt_scheduler.py:77 死值 + getattr 冗余，保留双通道 | 不解决根因，双通道残留 |

---

## 三-B、组 7：组 1 深度复核新发现（组 1 修复掩盖的深层缺陷）

> **背景**：用户要求以组 6 的深度复核组 1 的 hasattr 改动——不满足于形式修复，找出被 hasattr 掩盖的架构缺陷。逐点追问"原防御在防什么？被防场景现在怎样？"，用禁用验证/时序追踪确认。

### 7.1 AIPlugin.hydrate 冗余生命周期钩子（死代码）【已根治】

- **位置**：`ibci_modules/ibci_ai/core.py:74-81` `hydrate`；`core/runtime/bootstrap/kernel_native_modules.py:99` `hasattr(impl, "hydrate")`
- **原 hasattr 防御**：`late_hydrate_kernel_native_modules` 对 kernel-native 模块探测 `hydrate`——但 `hydrate` **未在任何插件协议声明**（`IbPlugin`/`IbStatefulPlugin` 均无），是隐式约定。
- **深层问题**：`AIPlugin.hydrate` 与 `setup`（core.py:69-72）**做完全相同的事**（重新 expose llm_provider）。hydrate 是为 "ADR-020 G2 late-hydrate 窗口" 引入的"重确认"，但 setup 已正确注册（`ModuleLoader` 注入的 `_capability_registry` = engine 的 capability_registry，`engine.capability_registry is sc.capability_registry` 已验证为同一对象）。hydrate 声称的"未来捕获 host_service/llm_executor 供 save/restore"**从未实现**，且 save/restore 已由 `IbStatefulPlugin.save_plugin_state/restore_plugin_state` 覆盖。
- **验证**：临时禁用 hydrate（no-op）→ **1263 passed / 4 skipped 全绿**。证明 hydrate 完全冗余。
- **分类**：死代码（预留接口未激活、无消费者价值）+ 半接通生命周期特性（框架落地、实现空壳、测试固化）
- **处置（已根治 2026-08-02）**：删除 `AIPlugin.hydrate` + `late_hydrate_kernel_native_modules` 函数 + `engine.py` 调用点 + `test_ai_hydrate_called_after_registry_hooks` 测试。插件初始化收敛为**单一 setup 入口**（loader.py:254-260 手动注册循环已覆盖 kernel-native）。同步更新 `docs/architecture/07_kernel_native_modules.md` 与 `docs/ARCHITECTURE.md`（删 late-hydrate 描述，改为"单一 setup 初始化"）。验证：1262 passed（-1 删除的测试）/ 4 skipped，`llm_provider` 仍由 setup 正确注册。

### 7.2 leaf.py LLMFuture 解引用的 else 回退分支是死代码

- **位置**：`core/runtime/vm/handlers/leaf.py:76-80`
- **原 hasattr 防御**：`hasattr(llm_executor, "resolve")` 后 else 回退 `val.get(executor.registry)`——假设"llm_executor 可能缺失/无 resolve"
- **深层问题**：`VMExecutor` 由 interpreter 构造（interpreter.py:467 `interpreter=self`），恒非 None → `executor.service_context` 恒非 None → `sc.llm_executor`（协议非 Optional）恒存在 → **else 回退分支永远不可达**。
- **验证**：全仓 `VMExecutor(` 构造点（interpreter.py:467、conftest.py:213）均传 interpreter。
- **分类**：死代码（双通道残留——"llm_executor 缺失"假设已不存在）
- **处置**：删除 else 回退分支，直接 `llm_executor.resolve(val.node_uid)`

### 7.3 vm_executor.service_context 的 getattr 冗余（组 1 遗漏）

- **位置**：`core/runtime/vm/vm_executor.py:96` `getattr(self._interpreter, "service_context", None)`
- **深层问题**：`Interpreter` 有公开 `service_context` property，构造后恒有。getattr 冗余（组 1 应一并处理）。
- **分类**：冗余防御探测
- **处置**：改直接访问（`self._interpreter.service_context`），保留 `if self._interpreter is not None` 守卫

### 7.4 LLMExecutor 协议过度承诺（dispatch_eager/resolve 是 scheduler 能力）

- **位置**：`core/runtime/interfaces.py` `LLMExecutor` 协议并入 `dispatch_eager`/`resolve`/`run_batch`（组 1 U2）
- **深层问题**：这些是 `_SchedulerMixin`/`_BehaviorMixin` 的能力，非所有 LLMExecutor 的**最小契约**。原 `hasattr(llm_executor, "dispatch_eager")` 暗示设计意图是"可选调度能力"。全部并入后，未来纯同步 executor 被强制实现这些方法。
- **当前影响**：LLMExecutorImpl 是唯一实现且含所有 mixin，无实际破坏。
- **分类**：协议设计风险（非当前缺陷）
- **处置**：评估是否拆分协议（`LLMExecutor` 基础 + `ISchedulingLLMExecutor` 扩展）；当前可保留，记录为设计注意点

### 7.5 关联：capabilities.expose 参数错位（组 2 关联确认）

- `AIPlugin.setup` 调 `capabilities.expose("llm_provider", self)`，默认 priority=0 → `register(name, self, 0)` 把 0 当 plugin_id（组 2 已记录 bug）。当前恰好注册成功（get 按 name 查），但 plugin_id=0 是脏数据。修组 2 时一并处理。

**复核结论**：组 1 的形式修复（协议并入）正确，但**未触及 hasattr 背后的深层问题**——7.1（hydrate 冗余）、7.2（死分支）、7.3（getattr 遗漏）是组 1 修复后仍存在的死代码/冗余，7.4 是协议设计风险。这印证用户判断：hasattr 特征点背后常藏着更深缺陷，需逐一深挖而非停留在形式。

---

## 三-C、组 8：非 hasattr 反射面重复核（用户质询"过度聚焦 hasattr"后新增）

> **背景**：用户指出可能过度聚焦 hasattr 单一特征，真正关心的是反射机制滥用的潜在隐患。subagent 独立复核全仓非 hasattr 反射面（签名内省/动态导入/魔术方法/异常分类/字符串契约），发现多个被 hasattr 聚焦掩盖的真实隐患。

### 8.1 异常消息字符串嗅探分类【中高危】

- `core/compiler/scheduler.py:324` `if "Security Error" in str(e)` 分类异常；`resolver.py:53` 把安全违规塞进 message 字符串
- **根因**：`ModuleResolveError` 缺结构化错误码，靠消息字符串耦合决策
- **正确修法**：给异常加 `code` 字段或细分异常子类，由异常对象携带语义

### 8.2 能力名跨层裸字符串契约【中危】

- `CapabilityRegistry.CAP_LLM_PROVIDER` 常量（capability_registry.py:38-45）**零使用**（死常量）；实际 4 处消费方裸字符串 `"llm_provider"`（`_shared.py:449`、`llm_executor/_core.py:111`、`ibci_ai/core.py:72`、`ibci_idbg/core.py:47`）
- **根因**：能力名是跨层字符串契约（插件注册名 ↔ 内核取用名），靠惯例同步
- **附带**：`_get_max_retry` 在 provider 为 None 时静默 `return 3`（组 5 兜底）
- **正确修法**：内核侧消费改用 `CapabilityRegistry.CAP_*` 常量；插件侧能力名登记为可导入契约常量

### 8.3 签名提取静默降级为空契约【中危】

- `core/runtime/module_system/discovery.py:327` `except (ValueError, TypeError): return [], "any"`——签名提取失败（C 内建/动态 callable）伪造空契约，运行时才炸
- **正确修法**：显式返回"无签名"状态让上层决策（fail-fast）

### 8.4 IbNativeFunction.__getattr__ 透传安全矛盾【中危】

- `core/runtime/objects/kernel/functions.py:77-80` `receive('__getattr__')` 以安全名义拦截 py_func 属性泄露，但 line 82-83 `__getattr__` **透传 py_func 所有属性**（`__code__`/`__globals__`），守卫自相矛盾
- **验证**：透传无直接消费者（`.py_func` 读取均显式属性）
- **正确修法**：删除透传

### 8.5 序列化 setattr 穿透私有属性【中低危】

- `runtime_serializer.py:376/408` `setattr(context, '_current_scope'/'_intent_exclusive_depth')` 恢复状态穿透私有
- 组 4 已记录同类，合并处理

### 8.6 AST 访问器动态方法名构造【低危】

- `scoped_visitor.py:82`、`_type_checking_base.py:50`、`symbol_collection_pass.py:93`、`type_resolution_pass.py:78` `getattr(self, f"visit_{cls}")`
- 类名重构会静默落 generic_visit——可显式注册表或命名一致性测试

### 8.7 同源双写真相

- `loader.py:100-143` ↔ `check.py:163-201`（签名校验复制）；`loader.py:207` ↔ `check.py:165`（setup 参数名校验复制）
- `method_missing` 协议零消费者（半接通）

**复核结论**：非 hasattr 反射面中，真正的架构核心隐患是——**异常对象缺结构化错误码导致消息字符串嗅探、能力名跨层字符串契约、签名提取静默伪造空契约、Python 层 `__getattr__` 与消息守卫双通道矛盾**。前两项是典型"用字符串/异常约定掩盖本应显式化的契约"，与 hasattr 轮结论同源同向。

---

## 三、缺陷组 1：LLM 协议声明滞后于实现（PT-HEALTH-1 同族，已完成）

> **组 1 已于 2026-08-02 完成**（commit `01812c2` + 修正 `3e72816`/`d472d44`），全量 pytest 1263 passed / 4 skipped。

**根因**：`ILLMProvider`/`LLMExecutor`/`IILLMExecutor`/`IHostService`/`Scope`/`ServiceContext` 协议已存在且 `@runtime_checkable`，但方法面未随实现演进补全，代码用 `hasattr` 探测未声明方法。修复方向明确且非破坏性（各能力均由唯一实现提供）。

| # | 命中点 | 漏声明能力 | 并入协议 | 动作 |
|---|---|---|---|---|
| 1.1 | `vm/handlers/_shared.py:450` `_get_max_retry` | `get_retry` | `ILLMProvider`（AIPlugin 已实现） | 协议调用 + None 守卫；删 `getattr(sc,...)`/`hasattr(cap_reg,"get")` 冗余 |
| 1.2 | `vm/handlers/leaf.py:76` | `resolve` | `IILLMExecutor`/`LLMExecutor` | 协议调用 + None 守卫 |
| 1.3 | `vm/handlers/assignment.py:68` | `dispatch_eager` | 同上 | 协议调用；能力缺失回退同步路径保留（职责分离） |
| 1.4 | `interpreter/interpreter.py:237` | `hydrate` | 同上 | 直接协议调用（必需生命周期步骤） |
| 1.5 | `ibci_modules/ibci_ai/core.py:301` | `run_batch` | 同上 | 协议调用 |
| 1.6 | `interpreter/service_context.py:124` | `orchestrator` | `IHostService` | 并入协议后直用 |
| 1.7 | `rt_scheduler.py:117` | `interpreter` | `ServiceContext` | 并入协议或直用（:77 `orchestrator` 已声明，删 getattr） |
| 1.8 | `runtime_context.py:44,157,191,236` | `assign_by_uid`/`get_symbol_by_uid`/`promote_to_cell`/`_registry` | `Scope` 协议 + 公开 property | UID 方法并入协议；`_registry` 私有改公开接口 |
| 1.9 | `vm/handlers/control_flow.py:277-292` | `elements` | `isinstance(iterable_obj, IIbList)` | 首分支改 isinstance；receive 路由保留（合法异构） |
| 1.10 | `engine.py:349-359` | —（已声明） | — | 机械性去冗余（`host_service` Optional 保留 None 检查） |
| 1.11 | `ibci_ai/core.py:284-301` | —（`kernel_registry`/`get_llm_executor`/`get_current_call_info` 已声明） | — | 冗余探测删除 |

---

## 四、缺陷组 2：插件能力注册与模块导入体系（深度复核，多缺陷复合）

> **深度复核（2026-08-02）**：2-subagent 独立验证 + 实测脚本确认。核心结论：**这不是单一缺陷，而是"能力注册 API 双通道（坏入口+死入口）+ `import *` 双路径分裂（一条运行时损坏）+ 隐式契约（私有属性注入）"的复合缺陷**。已用实测验证每条。

### 4.1 能力注册：坏入口 + 死入口 + 脏数据

| # | 位置 | 问题 | 验证 |
|---|---|---|---|
| 4.1.1 | `capabilities.py:24-27` `PluginCapabilities.expose` | 调 `register(cap_name, provider, priority)` —— **priority 错填到必填 plugin_id 位**；请求的 priority 被丢弃（恒 NORMAL） | ✅ 实测 plugin_id=0（int 脏数据）、priority 恒 NORMAL；显式 priority=75 → plugin_id=75 |
| 4.1.2 | `capabilities.py:29-32` `revoke` | 调 `unregister(cap_name)` **缺必填 plugin_id → 必抛 TypeError** | ✅ 实测 TypeError；当前零调用者（潜伏） |
| 4.1.3 | `ibci_ai/ihost/idbg` setup 用 `capabilities.expose` | 3 个 kernel-native 插件注册时 **plugin_id 全部=0**（实测确认） | ✅ `llm_provider`/`ihost_provider`/`debugger_provider` plugin_id 均 0 |
| 4.1.4 | `ibcext.py:107-161` `IbPlugin.expose/_do_expose/revoke/revoke_all/get_vtable/get_exposed_capabilities` | **全部零使用者死代码**（含穿透私有 `_capability_registry` 的实现）；`_ibcext_vtable_func` 无赋值点恒返 {} | ✅ grep 全仓仅定义处 |
| 4.1.5 | `ibcext.py:135/147/154` hasattr 守卫 | dataclass 字段恒真，冗余 | ✅ 实测恒真 |
| 4.1.6 | `ibci_idbg/core.py:27` 读私有 `_capability_registry` | 因 expose/revoke API 坏而被迫穿透（穿透已成模式） | ✅ 与 4.1.1 因果 |

**本质**：能力注册 API 未统一——插件真实用的入口（PluginCapabilities.expose）坏（产生脏数据），设计好的入口（IbPlugin.expose）死。`get()` 按 name 查故潜伏不炸，但按真实 plugin_id 的 unregister/replace 永不命中。

### 4.2 `import *`：双路径分裂 + 运行时损坏

| # | 位置 | 问题 | 验证 |
|---|---|---|---|
| 4.2.1 | `module_manager.py:107-112` Python 包 `from pkg import *` | `dir(package)` + 非 `_` 过滤全量导出——**无白名单/spec/is_const 过滤**，泄漏 setup/expose/plugin_id/get_vtable 等全部公开方法 | ✅ 实测 `from idbg import *` 注入 60+ 名字含协议方法 |
| 4.2.2 | `module_manager.py:107-112` `*` 分支 `define_variable` 不传 uid | **编译器已为 spec 成员注入带 uid 符号（scheduler.py:521-539），运行时不传 uid → `get_variable_by_uid` 查不到 → `RUN_UNDEFINED_VARIABLE`** | ✅ 实测 `from idbg import *` 后引用 `show_env` 报 RUN_UNDEFINED_VARIABLE——**路径实际损坏** |
| 4.2.3 | `module_manager.py:130-135` IBC 模块 `*` 路径 | 与 Python 路径过滤语义分裂（is_const vs `_` 前缀、符号表 vs dir） | ✅ 语义不一致 |
| 4.2.4 | 无测试覆盖 | `import *` 两条路径零测试 | ✅ grep 无命中 |
| 4.2.5 | `module_manager.py:57-62` `hasattr(package,'receive')` + `getattr(package,'_ibci_vtable')` | 鸭子探测 + 私有属性耦合 | ✅ |

### 4.3 native_module：隐式契约 + 异常流控制

| # | 位置 | 问题 | 验证 |
|---|---|---|---|
| 4.3.1 | `native_module.py:22-24` | vtable/whitelist 显式参数与 `getattr(py_obj, '_ibci_*')` 兜底**双通道**；whitelist 参数生产路径**零调用**（factory.py:38 不传）——死代码，行为依赖是否经 loader 绑定 | ✅ 实测 whitelist 恒走 getattr 兜底 |
| 4.3.2 | `loader.py:196-198` 封印 `_ibci_vtable`/`_ibci_whitelist` 私有属性 | 隐式约定（属性名耦合），违反封装纪律；`native_module.py:21` 注释自称"消除动态属性依赖"却用 getattr 兜底——自相矛盾 | ✅ 三处字符串名硬耦合 |
| 4.3.3 | `native_module.py:62` `getattr(vtable[target], "_ibci_param_meta", None)` | 耦合 loader 实现细节（loader.py:183 设置）；非 loader vtable 静默丢失元数据；本可显式传（IbNativeFunction 有 param_meta 参数） | ✅ |
| 4.3.4 | `native_module.py:102-126` `hasattr(scope,'receive'/'get')` + `except (KeyError, AttributeError): pass` | 鸭子探测应改 isinstance（scope 仅两已知类型）；**`except AttributeError` 吞 scope.receive 内部真实 AttributeError** → 误报"no method" | ✅ 实测构造 vtable 内 raise AttributeError 被吞，替换为误导性错误 |
| 4.3.5 | `native_module.py:71` | AttributeError 兼作"不在契约"与真实错误信号——单一异常双职责，是 4.3.4 吞错根因 | ✅ |

### 4.4 加固层被绕过的安全缺口

`IbNativeObject.receive` 的 whitelist 加固机制（native_module.py:65-68）本身健全，但 **`import *`（4.2.1）在 Python 侧 `dir()` 全量搬移，不经 receive/白名单**——加固层被完全绕过。这是"反射规避"排查的核心命中点。

**处置方向**：4.1 修复 `PluginCapabilities.expose/revoke`（传 plugin_id + priority），删除 IbPlugin 死代码能力方法组；4.2 统一两条 `import *` 路径（用 spec 成员/白名单导出 + 补 uid），修复 M2 运行时损坏；4.3 显式化 vtable/whitelist 传递（`create_native_object` 补 whitelist 参数）、改 isinstance 分派、消除异常流控制吞错。属跨子系统重构，需用户确认方向后实施。

---

## 五、缺陷组 3：用异常做能力探测（隐蔽反射变体，最危险）

| # | 命中点 | 问题 | 修法 |
|---|---|---|---|
| 3.1 | `vm/handlers/control_flow.py:284-291` | `receive("__iter__")` 抛异常当"不可迭代"探测，吞 `InterpreterError` → 用户 `__iter__`/`to_list` 真实错误被误报 | 协议/类型判定 + 窄捕获 |
| 3.2 | `compiler/scheduler.py:320` | `"Security Error" in str(e)` 消息字符串嗅探分类 | 改异常类型/错误码分派 |
| 3.3 | `runtime_context.py:297` | 对返回 None 的 `get_symbol` 包 try/except 冗余探测 | 直接 `is not None` |

---

## 六、缺陷组 4：序列化/私有属性穿透

| # | 命中点 | 问题 | 修法 |
|---|---|---|---|
| 4.1 | `serialization/runtime_serializer.py:375-376` | `setattr(context, '_current_scope', ...)` 有公开 setter 却穿透私有 | 改用 `context.current_scope = ...` |
| 4.2 | `serialization/runtime_serializer.py:122-123` | 直读 `scope._uid_to_symbol`（无公开枚举接口） | 新增 Scope 公开 UID 枚举接口 |
| 4.3 | `serialization/runtime_serializer.py:407-408` | 写不存在的 `_intent_exclusive_depth`（协议半接通 + 死写） | 激活或删除协议成员 |
| 4.4 | `serialization/runtime_serializer.py:489` | `bind_symbol_by_uid` 调用点存在但方法全仓不存在 → uid 恢复静默丢弃 | 补 `Scope.bind_symbol_by_uid` 实现 |
| 4.5 | `serialization/runtime_serializer.py:149-158` | 鸭子类型（含私有 `_smear_queue`），类型已 import | 改 `isinstance` |
| 4.6 | `interpreter/llm_except_frame.py:142,231` | 探测私有 `_loop_stack` | 新增全栈快照/恢复公开方法 |
| 4.7 | `llm_executor/_behavior.py:79,300` | 跨对象读 provider 私有 `_config` | `ILLMProvider` 增公开配置访问方法 |
| 4.8 | `llm_executor/_llm_function.py:139,244` | 私有 `_pending_call_intent` 当传参暂存区 | 改显式参数传递 |
| 4.9 | `runtime_context.py:44` | 兄弟 Scope 间读私有 `_registry` | Scope 协议补 registry 属性 |

---

## 七、缺陷组 5：静默兜底掩盖错误结果（应 fail-fast）

| # | 命中点 | 问题 | 修法 |
|---|---|---|---|
| 5.1 | `vm/handlers/_shared.py:306` | 吞导入失败后函数在错误模块上下文（module 名已切、scope 未切）继续运行 | fail-fast，与 `user_functions.py:61,222` 一致 |
| 5.2 | `vm/handlers/_shared.py:684` | 宽捕获把 const 重赋值/类型不匹配降级为 redefine | 窄化捕获，fail-fast |
| 5.3 | `objects/kernel/ib_class.py:131` + `interpreter.py:609` | 字段初始值表达式出错静默置 None | fail-fast 报错 |
| 5.4 | `serialization/runtime_serializer.py:55/68/247` | 快照序列化失败静默丢意图上下文/替换占位字符串 | fail-fast 或显式告警 |
| 5.5 | `compiler/scheduler.py:100` | 解析异常（含安全错误）降级为"模块未找到" | 窄化 + 保留安全错误 |
| 5.6 | `runtime/modules/file_impl.py:151` | `exists()` 把沙箱权限拒绝降级为"文件不存在" | 窄化为 `FileNotFoundError/OSError` |
| 5.7 | `loader/artifact_loader.py:91` | `except ValueError: pass` 静默吞注册失败 | 窄化 + fail-fast |
| 5.8 | `kernel/config.py:42` | 损坏 JSON 静默吞掉 | 区分"文件不存在=空配置"与"损坏=报错" |
| 5.9 | `compiler/semantic/passes/base_pass.py:54` | `safe_run` 把编程错误转编译错误诊断，掩盖 pass 内部 bug | 区分语义错误走结果、编程错误崩溃 |

---

## 八、合法反射（保留，非缺陷）

| 命中点 | 性质 | 依据 |
|---|---|---|
| `auto_discovery.py`/`discovery.py`/`loader.py`/`kernel_native_modules.py` 对外部插件 `__ibcext_metadata__`/`__ibcext_vtable__`/`__ibcext_axiom__`/`create_implementation`/`setup`/`hydrate` 嗅探 | 设计内协议固定命名发现 | `docs/architecture/01_principles.md §7.3` |
| `axioms/primitives/enum.py:104`、`media.py:47` 的 `hasattr(receive/to_native)` | kernel 层禁止依赖 runtime 的分层鸭子类型 | 分层约束强制 |
| `ibci_ai/core.py:226,430` OpenAI SDK `reasoning_content`/`choices` 探测 | 外部第三方库对象 | 外部库反射合法 |
| 各语义 pass `getattr(node, attr)`（`vars()` 遍历） | Python AST 惯用法 | 标准 visitor 模式 |
| `ibci_idbg` 查看内部状态（走公开接口） | IDBG 调试职责 | §3.3 插件职责边界 |
| `_capabilities.py:39` `_get_cap`（flag_attr 协议声明 + 无 default） | 职责分离范式参照 | 唯一符合"协议声明能力、按协议分派" |
| `deep_clone.py:43-109`、`ib_class.py:110-131` `type(val)(...)` | 同类型构造/深克隆专门机制 | 专门接口 |
| `base/serialization.py:31` `__dict__`、`install.py` 包 `__file__`、`ast_view.py` `except KeyError` | 通用序列化/标准惯用法 | 设计如此 |

---

## 九、死代码 / 双通道 / 半接通（处置=删除或激活）

| # | 命中点 | 类型 | 处置 |
|---|---|---|---|
| 9.1 | `kernel/registry.py:376-386` `registry.is_truthy` | 双写真相（与 `interpreter.is_truthy` 双份），零调用 | 删除，收敛到协议版 |
| 9.2 | `bootstrap/primitive_initializer.py:51/56` `_cast_string_to`/`_cast_numeric_to` | 死代码（零绑定） | 删除 |
| 9.3 | `extension/ibcext.py:103` `_ibcext_vtable_func` | 全仓无设置点，`get_vtable()` 恒返 `{}` 零调用者 | 删除 |
| 9.4 | `module_system/discovery.py:107` `export_metadata` | 探测不存在的 `to_dict` 恒假，零调用者 | 删除 |
| 9.5 | `compiler/semantic/passes/integrity_check_pass.py:89` | 探测不存在的 `Symbol.node_uid` 死分支 + pass | 删除 |
| 9.6 | `parser/resolver/resolver.py:133` `is_package_dir` | 零消费者 | 删除或激活 |
| 9.7 | `auto_discovery.py:177-179` `create_plugin` | 零调用者 + 静默 return None | 删除 |
| 9.8 | `kernel/registry.py:283-288` | `hasattr(ib_class,'instantiate')` 后 fallback `ib_class(*args)` 双通道死分支 | 删 fallback 分支 |
| 9.9 | `node.uid` | 基类无字段且全仓无赋值 → `Diagnostic.node_uid` 恒 None 半接通 | 删除死参数或激活 |

---

## 十、冗余防御探测（机械性清理，无架构缺失）

以下为对已知类型/已声明协议成员的恒真/恒假 `hasattr`/`getattr+default`，非架构缺陷，机械简化即可：

- `serializer.py:125-205`：`getattr(sym,'uid')`/`hasattr(sym,'get_content_hash')`/`hasattr(sym.kind,'name')`/`hasattr(sym,'spec'/'def_node'/'owned_scope')`、TypeDef kind 守卫后 getattr（`value_type`/`wrapped_type`/`param_types`/`return_type`/`parent_type`）
- `type_ref.py:129-173`：`hasattr(spec, 'element_type')` 等 hasattr 副守卫——恒真且可能误判（对同名非容器 kind），应改 `spec.kind == TypeKind.X`
- `spec/registry/_inference.py`/`_members.py`/`_assignability.py`：kind 守卫后 getattr 冗余
- `_statement_visitors.py`/`_expression_visitors.py`：`getattr(val_type,'name',str())`/`members`/`param_types` 等基类字段冗余；`_expr:304` 统一入口外返回类型直读（双通道，CLASS 读到 void 默认）
- `binding_analysis_pass.py:339-347`/`symbol_resolution_pass.py:563`：`hasattr(stmt,'body')` 结构探测，应改 isinstance 分派或复用 `vars()` 遍历
- `runtime_serializer.py`：`hasattr(context,...)` 链、`getattr(obj,'mode','+')` Enum 兜底
- 值双轨家族（约 40+ 处 `hasattr(x,'to_native')`/`hasattr(x,'ib_class')` 恒真）：`to_native`/`fields`/`ib_class` 定义在基类 `IbObject`，探测是防御姿态。应统一为 `isinstance(value, IbObject)`（本仓已有示范）+ 引入单一 `unbox()` 边界函数收敛拆箱。

---

## 十一、修复顺序与验证（固定流程）

1. **顺序**：组 1 → 组 2 → 组 3/5 → 组 4 → 死代码清理 → 冗余简化。
2. **组 1、2 先上报确认方向**（契约变更 / 跨子系统取舍），其余可自主。
3. **每批后全量验证**：`conda activate ibci && python -m pytest tests/`，零回归。
4. **残留扫描**：修复后对全仓重跑本次扫描 pattern（信号清单见 `code-odor` §一.A，判定基准见 `code-quality` §二~§五），范围须超出本批改动文件。
5. **文档同步**：新发现的协议/接口变更写入 `docs/architecture/` 对应章节；可复用规则写入 `code-odor`/`code-quality` skill。
6. 完成后从本文件移除条目，更新 `NEXT_STEPS.md`。

---

## 十二、需用户确认项

1. ~~**组 6 orchestrator 注入修复方向**~~（已完成 2026-08-02，方案 A）。
2. ~~**组 1 协议并入方向**~~（已完成 2026-08-02）。
3. ~~**【组 7】组 1 深度复核发现的处置**~~（§三-B，7.1-7.3 已根治 2026-08-02；7.4 协议过度承诺记录为设计注意点，不立即改）：
   - 7.4 LLMExecutor 协议过度承诺——设计风险，建议记录不立即改
4. **【组 2】插件能力注册与模块导入体系重构方向**（§四 4.1-4.4，深度复核已完成）：
   - 4.1 修复 `PluginCapabilities.expose/revoke`（传 plugin_id + priority），删 IbPlugin 死代码能力方法组
   - 4.2 统一两条 `import *` 路径（spec 成员/白名单导出 + 补 uid），修复 M2 运行时损坏（RUN_UNDEFINED_VARIABLE）
   - 4.3 显式化 vtable/whitelist 传递（create_native_object 补 whitelist 参数）、isinstance 分派、消除异常流控制吞错
   - 4.4 修复加固层被 import * 绕过的安全缺口
5. **组 4 序列化访问**：Scope/Context 新增公开接口的边界（UID 枚举、`bind_symbol_by_uid`、loop 栈快照）是否全部纳入本次。
