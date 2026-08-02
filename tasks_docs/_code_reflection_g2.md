# 反射规避架构缺陷修复 — 组 2：能力注册/模块导入体系重构（临时任务文档）

> 临时任务文档，Phase 5 完成后经用户确认删除。
> **状态**：4.1-4.4 完成（1265 passed / 4 skipped）；组 2 后复核（hasattr 审视）完成。

## 组 2 后复核：hasattr 审视（用户质询后深查）

**结论**：组 2 修复后残留 hasattr 逐一核查，分三类：

### A. IbModule.scope 鸭子类型判别 → 协议化 ✅ 已修复
- 原 `hasattr(self.scope, 'receive')` 判别 native/scope 两形态
- 根因：`IbModule.scope` 声明为 `Any`，两形态（IbNativeObject 用 receive / ScopeImpl 用 get）无统一契约
- 正确解法（协议驱动）：kernel 层定义 `IModuleScope`（get + receive 两方法）
  - `IbNativeObject` 加 `get(name)`（delegate receive('__getattr__')）
  - `ScopeImpl` 加 `receive(message, args)`（delegate __getattr__→get）
  - `IbModule.receive` 统一经 scope.get / scope.receive，hasattr 消失
  - `IbModule.scope`/`IIbModule.scope`/`create_module` 类型标注统一为 `IModuleScope`
- 为何不能用 isinstance：objects/kernel 引 runtime/interpreter 会循环依赖——协议放 kernel 层解决

### B. `_ibci_registry_id` 隔离标记 → 判定为合理实现，保留
- 深查确认：跨 engine 隔离安全机制（`registry_isolation` 策略，test_e2e_isolation_plugin_inheritance 验证）
- 与 `_ibci_vtable` 不同：vtable 是**模块契约**（应显式传），registry_id 是**对象身份**（跨 IbNativeObject 实例跟随 py_obj）
- 若移到 IbNativeObject 显式属性，隔离校验失去意义（构造它的 registry 恒等于比对的 registry）
- 结论：挂在 py_obj 上的对象身份标记，合理保留

### C. loader.py:241 get_symbol_view 冗余 → 已修复 ✅
- `hasattr(rt_context, 'get_symbol_view')` 改直接调用（rt_context 非 None 时恒有，get_symbol_view 已在 RuntimeContext 协议声明）

## 4.1 能力注册统一 ✅ 已完成

- `PluginCapabilities` 加 `_plugin_id` 字段；`expose`/`revoke` 正确传 plugin_id + priority
- loader `_setup_implementation` 注入 `capabilities._plugin_id = module_name`
- 删 IbPlugin 死代码能力方法组（expose/_do_expose/revoke/revoke_all/get_vtable/get_exposed_capabilities + EXPOSE_* 常量）
- idbg 穿透 `_capability_registry` 改公开 `capabilities.get()`
- 验证：plugin_id 从脏数据 0 → 正确 'ai'/'ihost'/'idbg'；revoke 正常

## 4.3 native_module 契约显式化 ✅ 已完成

- `_validate_and_bind` 返回 `(vtable, whitelist)`，删 `_ibci_vtable`/`_ibci_whitelist` 私有封印
- interop 增 `bind_native_contract`/`get_native_contract` 公开承载
- `create_native_object` 补 whitelist 参数（factory + 接口）
- vtable 值改 `(func, param_meta)` 元组，删 `_ibci_param_meta` getattr
- `IbModule.receive` 改 native/scope 明确分派，Scope 分支仅捕获 KeyError
- 验证：`_ibci_*` 零残留

## 4.2 import * 统一 ✅ 已完成

- 新增 `_import_star_uid_map`：从 artifact scope_pool 读编译器注入的 uid（方案 A，subagent 评估推荐）
- Python 路径：uid_map ∩ dir(package)，`define_variable(uid=...)` 对齐
- IBC 路径：uid_map ∩ get_all_symbols，保留 is_const 过滤 + uid 对齐
- 修复 M2 运行时损坏（RUN_UNDEFINED_VARIABLE，实测复现→修复）
- 修复 4.2.1 泄漏（实测 setup/expose/plugin_id 不再注入）
- 补 3 个测试（uid 对齐 / 不泄漏 / spec 成员齐全）

## 4.4 加固层修复 ✅ 已完成

- import * 只导出 spec 成员后，加固层（whitelist）不再被 dir() 绕过
