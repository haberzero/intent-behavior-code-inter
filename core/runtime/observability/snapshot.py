"""
core.runtime.observability.snapshot — 运行时快照聚合。

``snapshot(executor)`` 把当前运行时可观测状态聚合为结构化 dict：

- tasks:    在途任务（spawn 句柄状态）
- channels: Channel 列表（mode/qsize/closed）
- slots:    Slot 列表（name/value）
- vms:      VM 实例状态
- vars:     模块级变量（经 state_reader）
- llm:      pending futures / call_info

快照为"尽力一致"（每子快照持锁取一致切片，整体不强求跨对象一致性快照——
设计 §四.1 注明）。
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def _comm_registry(executor: Any):
    """获取执行器关联的通信注册表（无则返回 None）。"""
    rc = getattr(executor, "runtime_context", None)
    if rc is None:
        return None
    return getattr(rc, "_comm_registry", None)


def snapshot(executor: Any) -> Dict[str, Any]:
    """聚合运行时快照。"""

    out: Dict[str, Any] = {}

    # ---- tasks：从执行器侧收集在途任务（TaskScheduler / spawn 句柄）----
    tasks = []
    scheduler = getattr(executor, "_scheduler", None) or getattr(executor, "_task_scheduler", None)
    if scheduler is not None:
        for t in getattr(scheduler, "_ready", []) + getattr(scheduler, "_waiting", []):
            tasks.append({
                "index": getattr(t, "index", None),
                "node_uid": getattr(t, "node_uid", ""),
                "started": getattr(t, "started", False),
                "waiting": getattr(t, "waiting_on", None) is not None,
            })
    # 线程对象（RuntimeCoordinator，任务 C）：快照补充后台线程任务，
    # 消除内省双数据源（F-1：spawn 线程此前在协调器，快照看不到）。
    rc = getattr(executor, "runtime_context", None)
    coordinator = getattr(rc, "_runtime_coordinator", None) if rc is not None else None
    if coordinator is not None:
        tasks.extend(coordinator.snapshot())
    out["tasks"] = tasks

    # ---- channels / slots：从 CommRegistry 收集 ----
    reg = _comm_registry(executor)
    channels = []
    slots = []
    if reg is not None:
        for obj in reg.all("chan"):
            channels.append(obj.core.snapshot() if hasattr(obj, "core") else obj.snapshot())
        for obj in reg.all("slot"):
            slots.append(obj.core.snapshot() if hasattr(obj, "core") else obj.snapshot())
    out["channels"] = channels
    out["slots"] = slots

    # ---- vms：当前解释器实例 ----
    vms = []
    interpreter = getattr(executor, "_interpreter", None)
    if interpreter is not None:
        vms.append({
            "instance_id": getattr(interpreter, "instance_id", None),
            "current_module": getattr(interpreter, "current_module_name", None),
        })
    out["vms"] = vms

    # ---- vars：模块级变量（经 runtime_context）----
    rc = getattr(executor, "runtime_context", None)
    vars_snapshot: Dict[str, Any] = {}
    if rc is not None:
        try:
            for name, val in rc.get_vars_snapshot().items():
                try:
                    native = val.to_native()
                    if not isinstance(native, (str, int, float, bool, list, dict, type(None))):
                        continue
                    vars_snapshot[name] = native
                except Exception:
                    continue
        except Exception:
            pass
    out["vars"] = vars_snapshot

    # ---- llm：pending futures / call_info ----
    llm: Dict[str, Any] = {}
    llm_exec = None
    if interpreter is not None:
        sc = getattr(interpreter, "service_context", None)
        llm_exec = getattr(sc, "llm_executor", None) if sc is not None else None
    if llm_exec is not None:
        pending = getattr(llm_exec, "_pending_futures", None)
        llm["pending_futures"] = len(pending) if pending is not None else 0
        call_info = getattr(llm_exec, "_current_call_info", None)
        llm["last_call_info"] = dict(call_info) if call_info else None
    out["llm"] = llm

    return out
