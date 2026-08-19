"""
tests/e2e/test_await_expr.py
================================

Stage 3 语言级 ``await`` 表达式 E2E 测试。

``await <expr>`` 是显式等待一个 Waitable 完成、返回其结果的语法表面，构建于
统一 ``Waitable`` 地基之上（与数据流自动 await 互补，非双通道）。

覆盖：
- ``await @~...~`` 行为描述表达式：显式等待行为结果，返回其值
- ``await ihost.collect(...)``：显式等待宿主子任务结果（对 collect 的自动等待幂等）
- ``await`` 对非 Waitable 操作数：原样返回（幂等）
"""
import os
import tempfile

from tests.conftest import AI_MOCK_PREFIX, run_ibci

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


def _write_child(code: str) -> str:
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".ibci", delete=False, dir=ROOT_DIR, encoding="utf-8"
    )
    f.write(code)
    f.close()
    return f.name


def _ibci_path(path: str) -> str:
    return path.replace("\\", "/")


class TestAwaitExpr:
    def test_await_behavior_expression(self):
        """``await @~...~`` 显式等待行为结果，返回其值。"""
        code = (
            AI_MOCK_PREFIX
            + "str x = await @~ MOCK:STR:hello-await ~\n"
            + "print(x)\n"
        )
        out = run_ibci(code)
        assert any("hello-await" in line for line in out)

    def test_await_behavior_expression_with_type(self):
        """``await @~...~`` 结果类型由左值决定（适配 int）。"""
        code = (
            AI_MOCK_PREFIX
            + "int x = await @~ MOCK:INT:42 ~\n"
            + "print((str)x)\n"
        )
        out = run_ibci(code)
        assert any("42" in line for line in out)

    def test_await_host_collect_result(self):
        """``await ihost.collect(...)`` 显式等待宿主子任务结果（幂等）。"""
        child = _write_child('str name = "awaited-child"\n')
        try:
            code = (
                "import ihost\n"
                f'str h = ihost.spawn_isolated("{_ibci_path(child)}", {{}})\n'
                "dict r = await ihost.collect(h)\n"
                'print(r["name"])\n'
            )
            out = run_ibci(code)
            assert any("awaited-child" in line for line in out)
        finally:
            os.unlink(child)

    def test_await_non_waitable_idempotent(self):
        """``await`` 对非 Waitable 操作数原样返回（幂等）。"""
        code = (
            "str s = await \"plain\"\n"
            "print(s)\n"
        )
        out = run_ibci(code)
        assert any("plain" in line for line in out)

class TestAwaitAnywhere:
    """普通函数内 await 可用（无需 async 关键字）——CPS VM 所有函数体天然可挂起。"""

    def test_await_channel_recv_inside_user_function(self):
        """用户函数体内 await 通道 recv（Waitable），挂起/恢复正确。"""
        code = """
chan c = chan(str, "stream")
c.send("hello")
func read(chan x) -> str:
    str m = await x.recv()
    return m
str got = read(c)
print(got)
"""
        assert run_ibci(code) == ["hello"]

    def test_await_inside_nested_call_chain(self):
        """await 在多层函数调用链内挂起/恢复。"""
        code = """
chan c = chan(int, "stream")
c.send(21)
func half(chan x) -> int:
    int v = await x.recv()
    return v
func double(chan x) -> int:
    int v = half(x)
    return v * 2
int r = double(c)
print((str)r)
"""
        assert run_ibci(code) == ["42"]
