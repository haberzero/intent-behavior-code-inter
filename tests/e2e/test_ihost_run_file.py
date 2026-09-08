"""
tests/e2e/test_ihost_run_file.py

ihost.run_file（R-2a：进程内子 run + 结果捕获）E2E 契约（设计：
tasks_docs/_ihost_subenv_design.md §三）：

- 结果记录 {exit_status, stdout, exception}（**错误作值**——子失败不抛穿
  父；与 run_isolated 的错误作异常 + 变量字典互补）；
- stdout 捕获（子 print 不经父 stdout 直接面，经 r["stdout"] 取回）；
- 隔离（子全局变量不泄漏父环境）；
- collect_timeout 防卡死（policy 既有面；超时 = exception 携带 timed out，
  子线程 daemon 孤儿语义既有）。
"""
import os
import tempfile

from tests.conftest import run_ibci

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


class TestRunFile:
    def test_ok_record(self):
        """子 run 成功：exit_status=ok + stdout 捕获 + exception 空。"""
        child = _write_child(
            "print('line-one')\n"
            "print('line-two')\n"
            "str result = 'child-secret'\n"
        )
        try:
            code = (
                "import ihost\n"
                + f'dict r = ihost.run_file("{_ibci_path(child)}", {{}})\n'
                + 'print(r["exit_status"])\n'
                + 'print(r["stdout"])\n'
                + 'print(r["exception"])\n'
            )
            out = run_ibci(code)
            joined = "\n".join(out)
            assert "ok" in out
            assert "line-one" in joined and "line-two" in joined
            # 子全局变量不泄漏父环境（隔离；仅经 stdout 捕获面可见）
            assert "child-secret" not in joined
        finally:
            os.unlink(child)

    def test_error_record(self):
        """子 run 失败：exit_status=error + exception 非空 + 父 run 正常完成
        （错误作值，不抛穿父）。"""
        child = _write_child(
            "int a = 1\n"
            "int b = 0\n"
            "int c = a / b\n"
            "print(c)\n"
        )
        try:
            code = (
                "import ihost\n"
                + f'dict r = ihost.run_file("{_ibci_path(child)}", {{}})\n'
                + 'print(r["exit_status"])\n'
                + 'print(r["exception"])\n'
                + "print('parent-alive')\n"
            )
            out = run_ibci(code)
            joined = "\n".join(out)
            assert "error" in out
            assert "parent-alive" in out  # 父 run 完整
            assert "Isolated execution" in joined  # 异常文本随链保真
            assert "object at 0x" not in joined    # 非裸对象 repr（消息面保真）
        finally:
            os.unlink(child)

    def test_stdout_captured_not_parent_direct(self):
        """子 print 不经父 stdout 直接面——父输出恰为记录字段行。"""
        child = _write_child("print('child-output')\n")
        try:
            code = (
                "import ihost\n"
                + f'dict r = ihost.run_file("{_ibci_path(child)}", {{}})\n'
                + 'print(r["exit_status"])\n'
            )
            out = run_ibci(code)
            # 父 stdout 只有 exit_status 行；child-output 只在 r["stdout"]
            #（本断言取其补面：直接输出中不混入子 print 的裸行）
            assert out == ["ok"]
        finally:
            os.unlink(child)

    def test_collect_timeout_policy(self):
        """防卡死：policy collect_timeout 有限 → 超时 = exception 携带
        timed out（子线程 daemon 孤儿语义既有，不阻断父）。"""
        # 循环规模裁定：须 > collect_timeout(1s) 才触发超时判别；VM 执行
        # 显著慢于 Python（~100k 迭代 ≈ 数秒）——孤儿线程（daemon，collect
        # 超时后继续跑至自然结束）须在套件时间尺度内收尾，不抢 CPU 拖垮套件。
        child = _write_child(
            "int i = 0\n"
            "while i < 100000:\n"
            "    i = i + 1\n"
        )
        try:
            code = (
                "import ihost\n"
                + f'dict r = ihost.run_file("{_ibci_path(child)}", '
                + '{"collect_timeout": 1})\n'
                + 'print(r["exit_status"])\n'
                + 'print(r["exception"])\n'
            )
            out = run_ibci(code)
            joined = "\n".join(out)
            assert "error" in out
            assert "timed out" in joined
        finally:
            os.unlink(child)
