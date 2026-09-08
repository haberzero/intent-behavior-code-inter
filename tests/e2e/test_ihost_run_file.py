"""
tests/e2e/test_ihost_run_file.py

ihost.run_file（进程内子 run + 结果捕获）E2E 契约：

- 返回 ``run_result`` 值类型（三字段 ``exit_status``/``stdout``/``exception``，
  attribute 访问）——**错误作值**（子失败不抛穿父；与 run_isolated 的错误作异常
  + 变量字典互补）；
- ``exception`` 字段 = ``None`` 或结构化 dict ``{code, message,
  source{file,line,column,snippet}}``（与 CLI --result-json exception 面同构，
  单一权威源 core/runtime/exception_record.py）；
- stdout 捕获（子 print 不经父 stdout 直接面，经 r.stdout 取回）；
- 隔离（子全局变量不泄漏父环境）；
- collect_timeout 防卡死（policy 既有面；超时 = exception.message 携带
  timed out，子线程 daemon 孤儿语义既有）。
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
                + f'run_result r = ihost.run_file("{_ibci_path(child)}", {{}})\n'
                + 'print(r.exit_status)\n'
                + 'print(r.stdout)\n'
            )
            out = run_ibci(code)
            joined = "\n".join(out)
            assert "ok" in out
            # stdout 捕获（子 print 经 r.stdout 取回，\n 连接）
            assert "line-one" in joined and "line-two" in joined
            # 子全局变量不泄漏父环境（隔离；仅经 stdout 捕获面可见）
            assert "child-secret" not in joined
        finally:
            os.unlink(child)

    def test_error_record_structured(self):
        """子 run 失败：exit_status=error + exception 结构化 dict（code +
        message + source 定位）+ 父 run 正常完成（错误作值，不抛穿父）。"""
        child = _write_child(
            "int a = 1\n"
            "int b = 0\n"
            "int c = a / b\n"
            "print(c)\n"
        )
        try:
            code = (
                "import ihost\n"
                + f'run_result r = ihost.run_file("{_ibci_path(child)}", {{}})\n'
                + 'print(r.exit_status)\n'
                + "dict ex = r.exception\n"
                + 'print(ex["code"])\n'
                + 'print(ex["message"])\n'
                + "print('parent-alive')\n"
            )
            out = run_ibci(code)
            joined = "\n".join(out)
            assert "error" in out
            assert "parent-alive" in out  # 父 run 完整
            assert "RUN_DIVISION_BY_ZERO" in joined  # 结构化 code 面
            # 结构化 message 面（真实错误文本，非裸对象 repr）
            assert "division" in joined.lower()
            assert "object at 0x" not in joined
        finally:
            os.unlink(child)

    def test_stdout_captured_not_parent_direct(self):
        """子 print 不经父 stdout 直接面——父输出恰为 exit_status 字段行。"""
        child = _write_child("print('child-output')\n")
        try:
            code = (
                "import ihost\n"
                + f'run_result r = ihost.run_file("{_ibci_path(child)}", {{}})\n'
                + 'print(r.exit_status)\n'
            )
            out = run_ibci(code)
            # 父 stdout 只有 exit_status 行；child-output 只在 r.stdout
            #（本断言取其补面：直接输出中不混入子 print 的裸行）
            assert out == ["ok"]
        finally:
            os.unlink(child)

    def test_collect_timeout_policy(self):
        """防卡死：policy collect_timeout 有限 → 超时 = exception.message 携带
        timed out（子线程 daemon 孤儿语义既有，不阻断父）。"""
        # 循环规模裁定：VM 实测 ~20000 迭代 ≈ 3.75s（> collect_timeout 1s，触发超时
        # 判别）；孤儿线程（daemon，collect 超时后继续跑至自然结束）总寿命 ~3.75s——
        # 压低套件 GC 收尾的孤儿负载（防看门狗误杀；run_code 超时判别同裁定）。
        child = _write_child(
            "int i = 0\n"
            "while i < 20000:\n"
            "    i = i + 1\n"
        )
        try:
            code = (
                "import ihost\n"
                + f'run_result r = ihost.run_file("{_ibci_path(child)}", '
                + '{"collect_timeout": 1})\n'
                + 'print(r.exit_status)\n'
                + "dict ex = r.exception\n"
                + 'print(ex["message"])\n'
            )
            out = run_ibci(code)
            joined = "\n".join(out)
            assert "error" in out
            assert "timed out" in joined
        finally:
            os.unlink(child)
