"""
core.runtime.observability.snapshot — 运行时快照聚合。

``snapshot(executor)`` 把当前运行时可观测状态聚合为结构化 dict：

- tasks:    在途任务（spawn 句柄状态）
- channels: Channel 列表（mode/qsize/closed）
- slots:    Slot 列表（name/value）
- vms:      VM 实例状态
- vars:     模块级变量（经 state_reader）
- llm:      pending futures / call_info

快照为"尽力一致"（每子快照持锁取一致切片，整体不强求跨对象一致性快照）。
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def _runtime_context(executor: Any) -> Optional[Any]:
    """执行器关联的 runtime_context（无则返回 None）。"""
    return getattr(executor, "runtime_context", None)


def snapshot(executor: Any) -> Dict[str, Any]:
    """聚合运行时快照。"""

    out: Dict[str, Any] = {}

    # ---- tasks：从线程协调器收集在途线程任务 ----
    tasks = []
    # 线程对象（RuntimeCoordinator）：快照收集后台线程任务。
    rc = _runtime_context(executor)
    coordinator = rc.peek_runtime_coordinator() if rc is not None else None
    if coordinator is not None:
        tasks.extend(coordinator.snapshot())
    out["tasks"] = tasks

    # ---- channels / slots：从 CommRegistry 收集 ----
    reg = rc.peek_comm_registry() if rc is not None else None
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

    # ---- vars：模块级变量（经 runtime_context 统一变量视图）----
    vars_snapshot: Dict[str, Any] = {}
    if rc is not None:
        for name, entry in rc.get_vars_snapshot().items():
            native = entry.get("value")
            if not isinstance(native, (str, int, float, bool, list, dict, type(None))):
                continue
            vars_snapshot[name] = native
    out["vars"] = vars_snapshot

    # ---- llm：pending futures / call_info ----
    llm: Dict[str, Any] = {}
    llm_exec = None
    if interpreter is not None:
        sc = getattr(interpreter, "service_context", None)
        llm_exec = getattr(sc, "llm_executor", None) if sc is not None else None
    if llm_exec is not None:
        llm["pending_futures"] = llm_exec.pending_futures_count()
        call_info = llm_exec.get_current_call_info()
        llm["last_call_info"] = dict(call_info) if call_info else None
    out["llm"] = llm

    return out
