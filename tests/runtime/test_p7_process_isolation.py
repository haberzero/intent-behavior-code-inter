"""
tests/runtime/test_p7_process_isolation.py

P7 进程级隔离判别测试套件：

- 子进程崩溃不杀父（进程边界）
- 变量不跨隔离边界泄漏
- 超时 kill 子进程（可被 OS 强杀，无 daemon 孤儿）
- LLM 继承跨进程（mock 态传递）
- 子进程使用独立 Python 解释器（sys.modules 不共享）
"""
import os
import sys
import json

import pytest

from tests.conftest import run_ibci, TESTS_ROOT
from core.engine import IBCIEngine
from core.runtime.capability_registry import CapabilityRegistry


def _write_child(code: str, name: str = "p7_child") -> str:
    """写子脚本到 tests/ 下（run_ibci 的 project_root 内）。"""
    test_dir = os.path.join(TESTS_ROOT, "_p7_tmp")
    os.makedirs(test_dir, exist_ok=True)
    path = os.path.join(test_dir, f"{name}.ibci")
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    return path


class TestProcessBoundary:
    """进程边界：子进程故障不影响父。"""

    def test_child_compile_error_parent_alive(self):
        """子编译错误 → 父存活（错误作值，不穿透）。"""
        child = "int x = = 5\n"
        path = _write_child(child, "p7_compile_err")
        try:
            code = (
                "import ihost\n"
                f'run_result r = ihost.run_file("{path}", {{}})\n'
                "print(r.exit_status)\n"
                "print('parent-alive')\n"
            )
            out = run_ibci(code)
            assert "error" in out
            assert "parent-alive" in out
        finally:
            os.unlink(path)

    def test_child_runtime_error_parent_alive(self):
        """子运行错误 → 父存活。"""
        child = "int a = 1\nint b = 0\nint c = a / b\n"
        path = _write_child(child, "p7_runtime_err")
        try:
            code = (
                "import ihost\n"
                f'run_result r = ihost.run_file("{path}", {{}})\n'
                "print(r.exit_status)\n"
                "print('parent-alive')\n"
            )
            out = run_ibci(code)
            assert "error" in out
            assert "parent-alive" in out
        finally:
            os.unlink(path)

    def test_child_output_captured(self):
        """子进程 print 输出被捕获（不经父 stdout 泄漏）。"""
        child = 'print("child-output-here")\n'
        path = _write_child(child, "p7_output")
        try:
            code = (
                "import ihost\n"
                f'run_result r = ihost.run_file("{path}", {{}})\n'
                'print(r.stdout)\n'
                "print('parent-done')\n"
            )
            out = run_ibci(code)
            joined = "\n".join(out)
            assert "child-output-here" in joined
            assert "parent-done" in out
        finally:
            os.unlink(path)


class TestVariableIsolation:
    """变量隔离：不跨进程边界。"""

    def test_variables_returned_from_child(self):
        """子进程变量经 JSON 协议正确传回。"""
        child = "int x = 42\nstr name = 'isolated'\nlist items = [1, 2, 3]\n"
        path = _write_child(child, "p7_vars")
        try:
            code = (
                "import ihost\n"
                f'dict r = ihost.run_isolated("{path}", {{}})\n'
                f'print(r["x"])\n'
                f'print(r["name"])\n'
            )
            out = run_ibci(code)
            assert "42" in out
            assert "isolated" in out
        finally:
            os.unlink(path)

    def test_child_cannot_see_parent_vars(self):
        """子进程无父变量（独立 scope）——字符串源 run_code 验证隔离。"""
        code = (
            "import ihost\n"
            "int secret = 999\n"
            'run_result r = ihost.run_code("int child_var = 100\\nprint(child_var)\\n", {})\n'
            "print(r.stdout)\n"
            "print('parent-alive')\n"
        )
        out = run_ibci(code)
        joined = "\n".join(out)
        assert "100" in joined  # 子变量在子 stdout 中
        assert "parent-alive" in out
        # 父变量 999 不出现在子输出中
        assert "999" not in joined


class TestProcessKill:
    """进程 kill：超时强杀（与线程 daemon 孤儿不同）。"""

    def test_timeout_kills_process(self):
        """collect_timeout 有限 → 超时 kill 子进程（RuntimeError）。"""
        # 长时间运行的子代码（循环）
        child = "int i = 0\nwhile True:\n    i = i + 1\n"
        path = _write_child(child, "p7_timeout")
        try:
            engine = IBCIEngine(root_dir=TESTS_ROOT)
            handle = engine.request_spawn_isolated(
                entry_path=path,
                policy={"collect_timeout": 3},  # 3s 超时
            )
            import time
            start = time.time()
            try:
                engine.request_collect(handle)
                pytest.fail("Expected timeout RuntimeError")
            except RuntimeError as e:
                elapsed = time.time() - start
                assert "timed out" in str(e)
                assert elapsed < 10, f"Kill took too long: {elapsed}s"
        finally:
            os.unlink(path)


class TestLlmInheritance:
    """LLM 继承跨进程。"""

    def test_mock_mode_inherited(self):
        """父 mock 态 → 子 LLM 调用经继承 mock 供数。"""
        child = (
            "import ai\n"
            "class Q:\n"
            "    func __llm_call__(self) -> dict:\n"
            '        return {"user_prompt": "MOCK:STR:inherited-result"}\n'
            "Q q = Q()\n"
            "str val = q()\n"
            "print(val)\n"
        )
        path = _write_child(child, "p7_llm_mock")
        try:
            code = (
                "import ai\n"
                "import ihost\n"
                "ai.set_mock_mode()\n"
                f'str h = ihost.spawn_isolated("{path}", {{}})\n'
                "dict r = await ihost.collect(h)\n"
                'print(r["val"])\n'
            )
            out = run_ibci(code)
            assert "inherited-result" in "\n".join(out)
        finally:
            os.unlink(path)

    def test_no_inheritance_clear_error(self):
        """父无 LLM 配置 → 子 LLM 调用清晰失败（不静默）。"""
        child = (
            "import ai\n"
            "class Q:\n"
            "    func __llm_call__(self) -> dict:\n"
            '        return {"user_prompt": "should-fail"}\n'
            "Q q = Q()\n"
            "str val = q()\n"
        )
        path = _write_child(child, "p7_llm_noconf")
        try:
            code = (
                "import ihost\n"
                f'run_result r = ihost.run_file("{path}", {{}})\n'
                "print(r.exit_status)\n"
                "print('parent-alive')\n"
            )
            out = run_ibci(code)
            assert "error" in out
            assert "parent-alive" in out
        finally:
            os.unlink(path)


class TestIndependentInterpreter:
    """独立解释器：子进程 sys.modules 不共享。"""

    def test_child_has_own_python_runtime(self):
        """子进程有独立 Python 解释器（无父模块缓存）。"""
        # 子代码使用 Python 侧功能（证明子有完整 Python 运行时）
        child = (
            "import python \"math\" as m:\n"
            "    bind sqrt(x: float) -> float\n"
            "float v = m.sqrt(16.0)\n"
            "print((str)v)\n"
        )
        path = _write_child(child, "p7_pyruntime")
        try:
            code = (
                "import ihost\n"
                f'run_result r = ihost.run_file("{path}", {{}})\n'
                "print(r.exit_status)\n"
            )
            out = run_ibci(code)
            # 子进程成功运行（有自己的 Python 解释器 + math 模块）
            assert "ok" in out
        finally:
            os.unlink(path)
