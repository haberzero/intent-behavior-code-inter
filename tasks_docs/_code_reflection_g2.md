# 反射规避架构缺陷修复 — 组 2：能力注册/模块导入体系重构（临时任务文档）

> 临时任务文档，Phase 5 完成后经用户确认删除。
> **状态**：4.1、4.3 完成（1262 passed / 4 skipped）；4.2、4.4 待做。

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
- `IbNativeObject.__init__` 删 getattr 兜底，显式参数
- `IbModule.receive` 改 native/scope 明确分派，Scope 分支仅捕获 KeyError（不吞内部 AttributeError）
- 验证：1262 passed / 4 skipped；`_ibci_*` 零残留

## 4.2 import * 统一（待做）

- Python 路径改按 spec 成员/白名单导出 + 补 uid
- 修复 M2 运行时损坏（RUN_UNDEFINED_VARIABLE）
- 统一两条路径语义
- 补测试

## 4.4 加固层修复（待做）

- import * 走白名单后加固层不再被绕过
