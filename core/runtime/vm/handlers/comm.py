"""
core.runtime.vm.handlers.comm — 并发/通信 AST 节点的 CPS handler。

覆盖（运行时多线程主线 PT-MT-*）：
- ``IbChannelExpr``  → 构造 ``IbChannel``（语言层 Channel 值对象）
- ``IbSignalExpr``   → 构造 ``IbSignal``（控制流信号值对象）
- ``IbSlotExpr``     → 构造 ``IbSlot``（共享状态槽值对象）
- ``IbSpawnStmt``    → 派生任务（见 vm_handle_IbSpawnStmt 注释）
- ``IbJoinStmt``     → 等待任务完成
- ``IbCancelStmt``   → 请求取消任务
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from core.runtime.objects.kernel import IbChannel, IbSignal, IbSlot, IbClass, IbUserFunction, IbValue
from core.runtime.shared.comm.channel import ChannelCore
from core.runtime.shared.comm.signal import SignalCore
from core.runtime.shared.comm.slot import SlotCore
from core.runtime.shared.comm.registry import CommRegistry


def _get_comm_registry(executor) -> CommRegistry:
    """获取（或惰性创建）执行器关联的通信注册表。

    注册表挂在 execution_context 上（runtime_context 侧），供广播枚举 / 定向
    查找 / 内省。多个 VM 实例各持一份（per-task 隔离）。
    """
    rc = executor.runtime_context
    reg = getattr(rc, "_comm_registry", None)
    if reg is None:
        reg = CommRegistry()
        try:
            rc._comm_registry = reg
        except Exception:
            pass
    return reg


def _get_coordinator(executor) -> Any:
    """获取（或惰性创建）执行器关联的 RuntimeCoordinator。

    挂在 runtime_context 上（与 CommRegistry 同级）。spawn/join/cancel 共享。
    """
    from core.runtime.coordinator import RuntimeCoordinator

    rc = executor.runtime_context
    coord = getattr(rc, "_runtime_coordinator", None)
    if coord is None:
        interpreter = getattr(executor, "_interpreter", None)
        coord = RuntimeCoordinator(interpreter)
        try:
            rc._runtime_coordinator = coord
        except Exception:
            pass
    return coord


def _emit_event(executor, event_type: str, data: Optional[dict] = None) -> None:
    """向 runtime_context 上的事件总线广播事件（PT-MT-4 内省事件流）。

    受控制层 observability 开关约束（PT-MT-5）：关闭时跳过事件记录。
    无订阅者时为空操作；事件总线失败不阻断执行（可观测性层尽力而为）。
    """
    rc = executor.runtime_context
    store = getattr(rc, "_comm_config_store", None)
    if store is not None:
        try:
            if not store.get("observability"):
                return
        except Exception:
            pass
    bus = getattr(rc, "_comm_event_bus", None)
    if bus is None:
        return
    try:
        bus.emit({"type": event_type, "data": data or {}})
    except Exception:
        pass


def vm_handle_IbChannelExpr(executor, node_uid: str, node_data: Mapping[str, Any]):
    """``chan(T, mode=..., buffer=...)`` 构造 Channel 值对象。"""
    if False:
        yield  # 保持生成器身份（VM CPS 契约：handler 必须为 generator）
    mode = node_data.get("mode", "message")
    buffer = node_data.get("buffer", 0)
    name = node_data.get("name")
    core = ChannelCore(mode=mode, buffer=buffer, name=name)
    cls = executor.registry.get_class("chan")
    obj = IbChannel(ib_class=cls, core=core)
    if name:
        _get_comm_registry(executor).register(name, obj, "chan")
    _emit_event(executor, "chan_created", {"name": name, "mode": mode})
    return obj


def vm_handle_IbSignalExpr(executor, node_uid: str, node_data: Mapping[str, Any]):
    """``signal(kind, target=..., payload=...)`` 构造 Signal 值对象。"""
    kind = node_data.get("kind", "cancel")
    target = None
    if node_data.get("target"):
        target = yield node_data["target"]
    payload = None
    if node_data.get("payload"):
        payload = yield node_data["payload"]
    core = SignalCore(kind=kind, target=target, payload=payload)
    cls = executor.registry.get_class("signal")
    return IbSignal(ib_class=cls, core=core)


def vm_handle_IbSlotExpr(executor, node_uid: str, node_data: Mapping[str, Any]):
    """``slot(name, value)`` 构造 Slot 值对象。"""
    name = node_data.get("name", "")
    value = None
    if node_data.get("value"):
        value = yield node_data["value"]
    core = SlotCore(name=name, initial_value=value)
    cls = executor.registry.get_class("slot")
    obj = IbSlot(ib_class=cls, core=core)
    if name:
        _get_comm_registry(executor).register(name, obj, "slot")
    _emit_event(executor, "slot_updated", {"name": name, "value": value})
    return obj


def vm_handle_IbSpawnStmt(executor, node_uid: str, node_data: Mapping[str, Any]):
    """``spawn fn(...)`` 派生任务。

    两种形态：
    - ``spawn compute("x")`` —— ``func`` 是 ``IbCall`` 节点：提取被调用者
      （callee）与实参，spawn 一个运行 ``compute("x")`` 的任务。
    - ``spawn compute`` / ``spawn fn_var`` —— ``func`` 是可调用对象本身，
      实参来自 ``node_data["args"]``。

    PT-MT-3 阶段：构造协作式延迟任务句柄（IbTask，join 时在当前 VM 线程
    求值）。后台线程 / 轻量 VM 实例的并发执行在 PT-MT-7/8 升级执行路径。
    """
    from core.runtime.objects.task import IbTask
    from core.runtime.vm.handlers._shared import _vm_assign_to_target

    func_uid = node_data.get("func")
    func_data = executor.ec.get_node_data(func_uid) if func_uid else None

    callable_obj = None
    args = []

    if func_data is not None and func_data.get("_type") == "IbCall":
        # 形态 1：func 是调用表达式 → 提取被调用者 + 实参
        callee_uid = func_data.get("func")
        callable_obj = yield callee_uid
        for arg_uid in func_data.get("args", []) or []:
            args.append((yield arg_uid))
        # 具名实参（spawn compute(x=1) 形态）
        for kw in func_data.get("keywords", []) or []:
            kw_val = yield kw.get("value")
            args.append(kw_val)
    else:
        # 形态 2：func 是可调用对象本身 + 独立实参
        callable_obj = yield func_uid if func_uid else None
        for arg_uid in node_data.get("args", []) or []:
            args.append((yield arg_uid))
        for kw in node_data.get("keywords", []) or []:
            kw_val = yield kw.get("value")
            args.append(kw_val)

    coordinator = _get_coordinator(executor)
    task_cls = executor.registry.get_class("task")
    task_obj = IbTask(
        ib_class=task_cls,
        executor=executor,
        coordinator=coordinator,
        callable_obj=callable_obj,
        args=args,
    )
    _emit_event(executor, "task_started", {"node_uid": node_uid})

    target_uid = node_data.get("target")
    if target_uid:
        yield from _vm_assign_to_target(executor, target_uid, task_obj, define_only=True)
    return task_obj


def vm_handle_IbJoinStmt(executor, node_uid: str, node_data: Mapping[str, Any]):
    """``join t`` 等待任务完成并取回结果。

    PT-MT-3 阶段：任务为协作式延迟任务（IbTask），join 直接触发求值并返回
    结果（不经 Waitable 协议——延迟任务未启动时不满足"已完成"前提）。PT-MT-7
    后台线程执行升级后，此处改为对任务 Waitable yield 挂起等待。
    """
    task_uid = node_data.get("task")
    task_obj = yield task_uid if task_uid else None
    result = None
    if task_obj is not None:
        join = getattr(task_obj, "join", None)
        if callable(join):
            result = join()
        else:
            result = task_obj
    _emit_event(executor, "task_done", {"node_uid": node_uid})
    target_uid = node_data.get("target")
    if target_uid:
        from core.runtime.vm.handlers._shared import _vm_assign_to_target
        yield from _vm_assign_to_target(executor, target_uid, result, define_only=True)
    return result


def vm_handle_IbCancelStmt(executor, node_uid: str, node_data: Mapping[str, Any]):
    """``cancel t`` 请求取消任务（协作式）。"""
    task_uid = node_data.get("task")
    task_obj = yield task_uid if task_uid else None
    if task_obj is not None:
        cancel = getattr(task_obj, "cancel", None)
        if callable(cancel):
            cancel()
    _emit_event(executor, "task_cancelled", {"node_uid": node_uid})
    return executor.registry.get_none()
