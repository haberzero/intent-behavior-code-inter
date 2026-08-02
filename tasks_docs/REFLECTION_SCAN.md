# 反射规避架构缺陷全仓排查 — 扫描记录与修复检查清单

> **状态**：扫描 + subagent 复核已完成（2026-08-02）；修复未开始。
> **性质**：正式独立任务文档（非临时）。扫描结论已收敛，本文档为后续修复的唯一事实来源与固定检查清单。
> **关联**：下一任务定义见 `NEXT_STEPS.md`；判定基准见 `.opencode/skills/code-quality/SKILL.md`。
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
| 组 1：LLM 协议声明滞后 | 契约漏声明 → hasattr 探测 | 并入 `ILLMProvider`/`LLMExecutor`/`IILLMExecutor`/`IHostService` 协议 | 是（契约变更，非破坏性） |
| 组 2：插件公开接口损坏 | 参数错位 + 私有穿透 + `dir()` 绕过白名单 | 修公开 API，删穿透 | 是（跨子系统） |
| 组 3：异常做能力探测 | 吞 `InterpreterError` 误报"不可迭代" | 协议/类型判定 + 窄捕获 | 否 |
| 组 4：序列化/私有属性穿透 | setattr 私有 + 读 `_uid_to_symbol` + 缺公开接口 | 改公开接口/补缺失方法 | 部分 |
| 组 5：静默兜底掩盖错误 | 吞错后继续产生错误结果 | fail-fast | 否 |
| 死代码/双通道/半接通 | 零调用、双写真相、恒假探测 | 删除或激活 | 否 |

---

## 三、缺陷组 1：LLM 协议声明滞后于实现（PT-HEALTH-1 同族）

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

## 四、缺陷组 2：插件能力公开接口损坏 → 被迫穿透

**根因**：`PluginCapabilities.expose/revoke` 公开 API 无法正确传 `plugin_id`（`register` 参数错位：priority 被当 plugin_id），ibcext 才不得不穿透 `_capability_registry` 私有字段。

| # | 命中点 | 问题 | 修法 |
|---|---|---|---|
| 2.1 | `extension/ibcext.py:135/147/154` | 穿透 `PluginCapabilities._capability_registry` 私有字段 + hasattr 恒真冗余 | 修 `capabilities.py:24-38` expose/revoke 传 plugin_id；ibcext 改公开方法 |
| 2.2 | `interpreter/module_manager.py:107` | `dir(package)` 全量遍历 → `import *` 泄露，绕过 vtable/whitelist | 改用 `_ibci_whitelist`/声明成员导出 |
| 2.3 | `objects/kernel/native_module.py:22/24` | 私有注入属性携带契约 + 空默认值 | `create_native_object` 显式传 whitelist 参数 |
| 2.4 | `objects/kernel/native_module.py:102-123` | 已知框架类型间 hasattr 分派 + `except AttributeError` 异常流控制 | 改 isinstance；删除异常流控制 |

**连带**：`capabilities.py:24-27` `expose()` 的 register 参数错位 bug 被 ibci_ai/ihost/idbg 使用，修公开 API 时一并修正。

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

1. **组 1 协议并入方向**（推荐：`get_retry`/`resolve`/`dispatch_eager`/`hydrate`/`run_batch` 并入对应协议，非破坏性）。
2. **组 2 处置**：`PluginCapabilities.expose/revoke` 公开 API 修复（含 register 参数错位 bug）；`dir()` 改白名单导出的落地方式。
3. **组 4 序列化访问**：Scope/Context 新增公开接口的边界（UID 枚举、`bind_symbol_by_uid`、loop 栈快照）是否全部纳入本次。
