# _code: kernel→runtime 穿透根治（事件总线 + 诊断发射器依赖注入）

> 用户红线（2026-08-08）：禁止一切可能存在的 kernel→runtime 穿透；穿透长远问题不可忽视。
> 方案：依赖注入——kernel 层声明抽象接口（§4.2"访问接口部分定义为 kernel 层抽象接口"），
> engine（runtime 组装层）创建具体实现并注入。与既有 `register_llm_executor`/`register_host_service`
> 注入模式同构。

## 穿透点（扫描确认，全仓唯一两处）

1. `core/kernel/registry.py:283` —— `get_event_bus` 惰性 import `core.runtime.observability.events.EventBus`
2. `core/kernel/host_interface.py:68` —— `register_module` 函数体惰性 import `kernel_diagnostic`

其他方向扫描干净：base→上层无；compiler→runtime 无；runtime→compiler 无。

## 修改单元

### 1. registry.py 事件总线注入化
- [x] `set_event_bus(bus)` 注入方法（与 `set_execution_context`/`register_llm_executor` 同模式）
- [x] `get_event_bus()` 删惰性 import；返回注入的总线（未注入 fail-fast 抛错：装配错误）
- [x] `peek_event_bus()` 保持只读（None 表示未注入 → emit_runtime_event 已 fail-open）
- [x] `clone()` 同步拷贝事件总线引用（子引擎共享引擎级总线）

### 2. engine.py 注入事件总线
- [x] 构造早期创建 `EventBus()` 并 `self.registry.set_event_bus(bus)`

### 3. host_interface.py 诊断发射器注入化
- [x] 删惰性 import `kernel_diagnostic`；不再依赖 runtime
- [x] kernel 层定义 `DiagnosticEmitter` 抽象（`Callable[[str, dict, str], None]` 回调槽）
- [x] `set_diagnostic_emitter(emitter)` 注入方法（可选，未注入时回退 warnings.warn）
- [x] `register_module` 覆盖站点：经注入的 emitter 发射；未注入 → warnings.warn（fail-open 保持开发者可见性）
- [x] 诊断码常量从 `core/base/diagnostics/codes.py` 导入（KDIAG_POLICY_MODULE_OVERRIDE，kernel→base 允许）

### 4. engine.py 注入诊断发射器
- [x] 构造 host_interface 后 `set_diagnostic_emitter(kernel_diagnostic)`（runtime 层适配，签名兼容）

### 5. 适配调用方
- [x] `ibci_iruntime.emit_event` 改 `peek_event_bus` + None 跳过（观测尽力而为 fail-open）
- [x] `subscribe`/`configure`（用户显式 API）保持 `get_event_bus` fail-fast（主动使用观测，装配错误应暴露）
- [x] interpreter.py:131 独立 KernelRegistry 场景：emit_runtime_event 用 peek fail-open 不受影响

### 6. 测试 + 残留扫描 + 文档
- [x] test_kernel_accessors：事件总线注入语义更新 + 未注入 fail-fast 新测试
- [x] e2e：override 活跃 EC 下注入链路事件+警告双投影新测试
- [x] 残留扫描：core/kernel/ 零 runtime import（仅 enum.py 注释引用，合法）；base/compiler/runtime 方向全净
- [ ] 文档同步：01_principles 附录/09_observability 内核层观测访问段落
- [ ] WORKLOG 记录
- [x] 全量 2023 passed / 1 skipped

## 决策记录
- 事件总线归属：runtime 层观测设施，engine 创建注入；registry 只做"引擎级共享槽"。
- host_interface 诊断：kernel 层不发射事件；经注入的发射器回调（默认 warnings.warn fail-open）。
- get_event_bus 未注入 → fail-fast（装配错误应立即暴露）；peek_event_bus → fail-open（观测尽力而为）。
