# 反射规避架构缺陷修复 — 组 7：组 1 深度复核处置（临时任务文档）

> 临时任务文档，Phase 5 完成后经用户确认删除。
> **状态**：7.2/7.3 已完成；7.1 待用户裁决。

## 7.1 AIPlugin.hydrate 冗余生命周期钩子【待裁决】

**事实链**：
- `AIPlugin.hydrate`（core.py:74）方法体与 `setup`（core.py:69）完全重复（`expose("llm_provider", self)`）
- hydrate 声称的"未来捕获 host_service/llm_executor 供 save/restore"从未实现；save/restore 已由 IbStatefulPlugin 协议覆盖
- **测试 `test_ai_hydrate_called_after_registry_hooks` 锁定"late_hydrate 必须调用 AIPlugin.hydrate"**（契约存在）
- 禁用 hydrate 方法体（pass）→ 测试仍通过（monkeypatch 记录调用，与方法体无关）
- 禁用 late_hydrate 调用点 → **测试失败**（契约破坏）
- late-hydrate 框架正当性：setup 在 spawn 内（registry hooks 注入前），插件若需访问 hooks 需 late-hydrate

**裁决选项**：
- X 保留现状（框架 + 重复方法体）
- Y 保留框架，hydrate 方法体做真正有意义的事（当前无需求，硬造违过度设计）
- Z 删除整套（含测试），承认设计意图未兑现、setup 已足够

## 7.2 leaf.py LLMFuture else 死分支 ✅ 已完成

- 删 else 回退（`val.get(executor.registry)`）；保留 `if llm_executor is not None` 守卫
- `LLMFuture.get` 保留（公开类方法 API）
- 验证：全量 1263 passed / 4 skipped

## 7.3 vm_executor.py:96 getattr 冗余 ✅ 已完成

- `getattr(self._interpreter, "service_context", None)` → `self._interpreter.service_context`
- 保留 `if self._interpreter is not None` 守卫
- 验证：全量 1263 passed / 4 skipped
