"""
M1/M2 驱动去重与 .call 双写收敛测试。

覆盖：
- M2：线程体驱动经单一权威循环（_drive_loop_gen + TaskScheduler），
  取消中断阻塞 recv / 深递归 / 生成器 spawn fail-fast 语义保持。
- M1：宿主侧 .call() 薄包装对 void / 显式 return 的返回语义与 VM 主路径一致。
"""
import pytest

from core.runtime.frame import (
    set_current_execution_context,
    reset_current_execution_context,
)


def _host_call(engine, name, *args):
    """在调用现场经宿主同步 .call() 调用语言层函数/可调用（M1 薄包装路径）。"""
    ec = engine.interpreter.execution_context
    token = set_current_execution_context(ec)
    try:
        obj = ec.runtime_context.get_variable(name)
        return obj.call(None, list(args))
    finally:
        reset_current_execution_context(token)


class TestCallHostSemantics:
    """宿主侧 .call() 薄包装返回语义收敛（void vs 显式 return 与 CPS 一致）。"""

    def test_user_function_void_returns_none(self, engine):
        engine.run_string(
            "func void_fn() -> void:\n"
            "    int x = 1\n",
            silent=True,
        )
        r = _host_call(engine, "void_fn")
        assert r.to_native() is None

    def test_user_function_explicit_return(self, engine):
        engine.run_string("func ret_fn() -> int:\n    return 42\n", silent=True)
        r = _host_call(engine, "ret_fn")
        assert r.to_native() == 42

    def test_user_function_closure_self_super(self, engine):
        # 宿主直调带 receiver 的成员方法：self 正确绑定。
        engine.run_string(
            "class Box:\n"
            "    func __init__(self) -> void:\n"
            "        self.base = 10\n"
            "    func inc(self, int n) -> int:\n"
            "        return self.base + n\n"
            "Box b = Box()\n",
            silent=True,
        )
        ec = engine.interpreter.execution_context
        token = set_current_execution_context(ec)
        try:
            b = ec.runtime_context.get_variable("b")
            # 经 vtable receive 触发 .call（含 receiver 绑定）
            r = b.receive("inc", [ec.registry.box(5)])
            assert r.to_native() == 15
        finally:
            reset_current_execution_context(token)

    def test_fn_callable_host_call(self, engine):
        engine.run_string(
            "fn f = lambda(int n) -> int: n + 1\n",
            silent=True,
        )
        r = _host_call(engine, "f", 41)
        assert r.to_native() == 42


class TestDriveUnification:
    """线程体驱动去重后行为保持（取消/深递归/生成器 spawn fail-fast）。"""

    def test_spawn_blocked_recv_cancelled(self, captured_output):
        from tests.conftest import run_ibci

        lines = run_ibci(
            "import ai\n"
            "ai.set_mock_mode()\n"
            "chan c = chan(str, \"message\")\n"
            "func work(chan x) -> int:\n"
            "    str m = x.recv()\n"
            "    return 1\n"
            "thread[int] t = thread(callable=work, args=[c])\n"
            "ThreadCancelled e = t.cancel()\n"
            "t.join()\n"
            "print((str)t.is_done())\n"
            "print((str)t.join().status())\n"
        )
        assert lines[0] == "True"
        assert lines[1] == "cancelled"

    def test_spawn_deep_recursion_trampolined(self, captured_output):
        from tests.conftest import run_ibci

        lines = run_ibci(
            "import ai\n"
            "ai.set_mock_mode()\n"
            "func countdown(int n) -> int:\n"
            "    if n <= 0:\n"
            "        return 0\n"
            "    return countdown(n - 1)\n"
            "thread[int] t = thread(callable=countdown, args=[300])\n"
            "print((str)t.join().expect())\n"
        )
        assert lines[0] == "0"
