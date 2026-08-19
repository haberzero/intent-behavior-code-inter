"""
tests/runtime/test_overlay_concurrency.py — 覆层启用跨根并发隔离契约（白盒层）。

覆层启用状态挂执行上下文（``RuntimeContext`` 计数集合）而非类型共享槽：
并行根（线程任务各自独立任务本地 EC）执行不同 ``with overlay`` 窗口时
彼此隔离——A 根的覆层窗口不污染 B 根的分派结果。
"""

import os
import threading
import time

from core.engine import IBCIEngine

from core.runtime.frame import get_current_execution_context
from core.runtime.interpreter.execution_context import ExecutionContextImpl
from core.runtime.interpreter.runtime_context import RuntimeContextImpl, ScopeImpl

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _engine():
    return IBCIEngine(root_dir=_ROOT)


def _make_task_ec(eng):
    """任务本地 EC（复刻 coordinator 模式）：独立 runtime_context。

    每线程任务独立 ExecutionContextImpl + RuntimeContextImpl，仅共享
    只读回调（node_pool/side_tables/factory 等）。
    """
    interp = eng.interpreter
    main_ec = interp.execution_context
    task_global = ScopeImpl(parent=interp.runtime_context.global_scope, registry=eng.registry)
    task_rt = RuntimeContextImpl(initial_scope=task_global, registry=eng.registry)
    task_ec = ExecutionContextImpl(
        registry=eng.registry,
        factory=main_ec.factory,
        get_node_data_callback=interp.get_node_data,
        get_side_table_callback=interp.get_side_table,
        push_stack_callback=main_ec.push_stack,
        pop_stack_callback=main_ec.pop_stack,
        get_captured_intents_callback=interp.get_captured_intents,
        is_truthy_callback=interp.is_truthy,
        resolve_type_from_symbol_callback=interp._resolve_type_from_symbol,
        extract_name_id_callback=interp._extract_name_id,
        resolve_value_callback=interp._resolve_value,
        module_manager=interp.service_context.module_manager,
        entry_file=main_ec.get_entry_path(),
        entry_dir=main_ec.get_entry_dir(),
        project_root=main_ec.get_project_root(),
    )
    task_ec.runtime_context = task_rt
    return task_ec


class TestOverlayCrossRootIsolation:
    """覆层启用状态经执行上下文隔离：并行根互不污染。"""

    def test_parallel_roots_do_not_pollute_each_other(self):
        """线程 A 进入覆层窗口（enter_overlay）、线程 B 不进入——B 的分派
        不受 A 窗口影响：A 得覆层结果、B 得原生结果（并发下同时成立）。

        回归：本状态原存 ``ProtocolSlot.overlay_enabled`` 类型共享槽，
        跨根并发执行互相污染（B 误命中 A 的覆层）。
        """
        from core.runtime.frame import (
            reset_current_execution_context,
            set_current_execution_context,
        )

        eng = _engine()
        eng.run_string(
            "impl overlay for int:\n"
            "    func __to_prompt__(self) -> str:\n"
            "        return 'overlayed-int'\n"
            "int x = 5\n",
            silent=True,
        )
        v = eng.registry.box(5)
        results: dict = {}

        def root_in_overlay():
            ec = _make_task_ec(eng)
            token = set_current_execution_context(ec)
            ec.runtime_context.enter_overlay("int", "__to_prompt__")
            try:
                time.sleep(0.2)  # 保持启用窗口
                results["in-block"] = v.receive("__to_prompt__", []).to_native()
            finally:
                ec.runtime_context.exit_overlay("int", "__to_prompt__")
                reset_current_execution_context(token)

        def root_outside():
            ec = _make_task_ec(eng)
            token = set_current_execution_context(ec)
            try:
                time.sleep(0.05)  # 保证 A 已进入覆层窗口
                results["outside"] = v.receive("__to_prompt__", []).to_native()
            finally:
                reset_current_execution_context(token)

        t1 = threading.Thread(target=root_in_overlay)
        t2 = threading.Thread(target=root_outside)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        assert results == {"in-block": "overlayed-int", "outside": "5"}

    def test_nested_overlay_windows_are_counted(self):
        """同名覆层嵌套窗口计数式启用：内层退出后外层仍生效。"""
        from core.runtime.frame import (
            reset_current_execution_context,
            set_current_execution_context,
        )

        eng = _engine()
        eng.run_string(
            "impl overlay for int:\n"
            "    func __to_prompt__(self) -> str:\n"
            "        return 'overlayed-int'\n"
            "int x = 5\n",
            silent=True,
        )
        v = eng.registry.box(5)
        ec = _make_task_ec(eng)
        token = set_current_execution_context(ec)
        rc = ec.runtime_context
        try:
            rc.enter_overlay("int", "__to_prompt__")
            rc.enter_overlay("int", "__to_prompt__")  # 嵌套
            assert v.receive("__to_prompt__", []).to_native() == "overlayed-int"
            rc.exit_overlay("int", "__to_prompt__")  # 内层退出
            assert rc.is_overlay_enabled("int", "__to_prompt__")  # 外层仍生效
            assert v.receive("__to_prompt__", []).to_native() == "overlayed-int"
            rc.exit_overlay("int", "__to_prompt__")  # 外层退出
            assert not rc.is_overlay_enabled("int", "__to_prompt__")
            assert v.receive("__to_prompt__", []).to_native() == "5"
        finally:
            reset_current_execution_context(token)

    def test_dispatch_without_active_execution_context_defaults_off(self):
        """宿主侧直调（无活跃执行上下文）按未启用处理：覆层仅经执行窗口生效。"""
        eng = _engine()
        eng.run_string(
            "impl overlay for int:\n"
            "    func __to_prompt__(self) -> str:\n"
            "        return 'overlayed-int'\n"
            "int x = 5\n",
            silent=True,
        )
        assert get_current_execution_context() is None
        v = eng.registry.box(5)
        assert v.receive("__to_prompt__", []).to_native() == "5"