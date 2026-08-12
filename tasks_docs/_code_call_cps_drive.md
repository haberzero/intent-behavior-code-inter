# _code_call_cps_drive.md — O1+I1 合并修复设计（receive→.call 同步路径 CPS 化）

> 2026-08-12。对应 `_FIX_PROPOSAL_CRITICAL_REVIEW_20260812.md` 批次 C。设计冻结后再实现。

## 问题域（共同根因）

`base.receive(protocol)` 对用户类实例的协议方法（`__call__` / `__iter__` 等）走
`lookup_method` → `method.call(receiver, args)` → `IbUserFunction.call` →
`_drive_generator`（新建嵌套 TaskScheduler，**不设 `yield_generator_values`**）：

| 现象 | 用例 | 根因 |
|------|------|------|
| O1 `obj()` 深递归 Python RecursionError（depth~300，普通函数 depth=500 通过） | 可调用类实例 | 嵌套调度器违反 EXEC-1 trampoline；`__call__` 含 Waitable 时同死锁 |
| I1 `for x in obj` 崩溃 `No CPS handler for 'GeneratorYield'` | 用户类生成器 `__iter__` | 嵌套驱动无 generator 模式，GeneratorYield 泄漏 |

**统一根因**：协议方法经 `.call()` 宿主同步包装进入非 generator 模式嵌套调度。
VM 主路径（`vm_handle_IbCall` 的 `IbUserFunction`/`IbBoundMethod` 分支）已正确
yield `UserFunctionCall` / `make_generator_driver`——但 `receive()` 返回的是
同步值，VM 无法感知"这是可挂起的用户方法调用"。

## 修复设计（机制同构 A5 `_ClassInstantiateDrive`）

### O1：`_UserCallDrive`（Waitable + CPSDrivable）

新建 `core/runtime/objects/kernel/user_call_drive.py`（或并入 ib_class.py 同层）：

```python
class _UserCallDrive:
    """用户类协议方法（__call__ 等）的帧内 CPS 驱动 Waitable。

    base.receive('__call__') 对含用户 __call__ 的类实例返回本对象；VM
    vm_handle_IbCall 识别 Waitable + CPSDrivable → yield from cps_drive：
    用户方法经 UserFunctionCall trampoline 压栈帧内驱动（替代 method.call
    新建嵌套 TaskScheduler，EXEC-1 根治 + Waitable 协作挂起）。
    宿主/线程体无活跃 VM 时 try_result/result 走同步 _drive_generator 兜底。
    """
    def __init__(self, method, args, receiver):
        self._method = method; self._args = args; self._receiver = receiver
        self._done = False; self._result = None
    @property
    def is_done(self): return self._done
    def _drive(self):  # 宿主同步兜底（无活跃 VM）
        from core.runtime.coordinator import _drive_generator
        vm = self._method.context.vm_executor
        from core.runtime.vm.handlers._shared import _vm_call_user_function
        self._result = _drive_generator(vm, _vm_call_user_function(vm, self._method, self._receiver, self._args))
        self._done = True
        return self._result
    def cps_drive(self, executor):  # VM 帧内驱动（主路径）
        self._result = yield UserFunctionCall(self._method, self._args, self._receiver)
        self._done = True
        return self._result
    def try_result(self):
        if self._done: return (True, self._result)
        self._drive(); return (True, self._result)
    def result(self): self._drive(); return self._result
    def register_wake(self, event): event.set()
```

**base.py `receive('__call__')` 修改**：call_cap 探测后、非 IbFunction 时，若
`lookup_method('__call__')` 返回 `IbUserFunction` → 返回 `_UserCallDrive(...)`；
否则维持原 `.call()` 兜底（原生 `__call__` 等）。

**VM 侧零改动**：`vm_handle_IbCall` 的 Waitable+CPSDrivable 分支已处理。

### I1：`IbUserFunction.call` 生成器感知

`IbUserFunction.call`（user_functions.py:35-56）在 `_drive_generator` 前加：

```python
if self.is_generator:
    # 宿主同步路径对生成器方法：返回 IbGenerator（不驱动体），
    # 与 VM 主路径 make_generator_driver 同构。消费方（for/迭代）to_list 推进。
    from core.runtime.shared.user_call import UserFunctionCall
    from core.runtime.objects.kernel.generator import IbGenerator
    vm = self.context.vm_executor
    driver = vm.make_generator_driver(UserFunctionCall(self, args, receiver))
    gen_class = vm.registry.get_class("generator")
    return IbGenerator(gen_class, driver)
```

**resolve_iterable 修改**（iterable.py:32-35）：`__iter__` 返回 IbGenerator 时
`to_list`（与顶层 IbGenerator 处理一致），使 `for x in obj` 对生成器 `__iter__`
正常。

## 效果

- `obj()` 深递归走 trampoline（EXEC-1 保证恢复），`__call__` 含 Waitable 协作挂起。
- 用户类 `__iter__` 生成器形式成为一等用法（与顶层生成器一致），消除行为分裂。
- `receive()` 仍是唯一协议分派入口（返回 drive/生成器值），不引入 hasattr 探测。

## 影响面

- `base.receive('__call__')`：仅影响"用户类实例 + 用户 `__call__`"路径；
  原生 `__call__`、类构造（IbClass.receive）不受影响。
- `IbUserFunction.call`：仅生成器函数经宿主 `.call()`（receive 协议 / 序列化 /
  host 同步调用）时返回 IbGenerator——与 VM 主路径语义对齐。
- `resolve_iterable`：仅 `__iter__` 返回 IbGenerator 的新路径。
- 序列化/round-trip：`_UserCallDrive` 是瞬态调用驱动，不入序列化（同
  `_ClassInstantiateDrive`）。

## 测试

- O1：可调用实例深递归 depth=400（此前 RecursionError）；`__call__` 内 LLM 行为
  auto-yield；`fn f = instance; f()` 路径。
- I1：用户类生成器 `__iter__` + `for` 迭代；`yield from <实例>`；对照直接
  `r.__iter__()` 行为一致。
- 回归：类构造 CPS、thread 句柄、slot.update 等既有路径。
- 全量 pytest 零回归。

## 风险与决策

- O1 的 `_UserCallDrive` 使 `receive('__call__')` 对用户类实例返回非值对象
  （Waitable drive）——宿主代码若直接依赖 `receive('__call__')` 返回同步值需
  检查（`functions.py:59` 仅原生 proxy 转发，不受影响）。
- 嵌套生成器 `__iter__`（generator 的 `__iter__`）不涉及（IbGenerator 自带迭代）。
