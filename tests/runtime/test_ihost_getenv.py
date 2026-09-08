"""
tests/runtime/test_ihost_getenv.py

ihost.getenv（宿主 OS 环境变量一等语言面通道）判别测试：

- 已设置变量经语言面读取（ihost.getenv 经插件 → HostService 委托链）；
- 缺失变量返回空串（os.getenv(key, "") 语义——语言层 str 无需空值分支）；
- idbg.env → idbg.runtime 改名回归（运行环境诊断面可用，旧名不再存在）。
"""

import os

import pytest

from core.engine import IBCIEngine


@pytest.fixture
def engine():
    return IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)))


class TestIhostGetenv:
    def test_set_variable(self, engine, monkeypatch):
        monkeypatch.setenv("IBCI_TEST_GETENV", "hello-env")
        out = []
        engine.run_string(
            'import ihost\n'
            'str v = ihost.getenv("IBCI_TEST_GETENV")\n'
            'print("v=" + v)\n',
            output_callback=out.append, silent=True)
        assert out and out[0].strip() == "v=hello-env"

    def test_missing_variable_empty(self, engine, monkeypatch):
        monkeypatch.delenv("IBCI_TEST_MISSING", raising=False)
        out = []
        engine.run_string(
            'import ihost\n'
            'str v = ihost.getenv("IBCI_TEST_MISSING")\n'
            'bool empty = v == ""\n'
            'print("empty=" + (str)empty)\n',
            output_callback=out.append, silent=True)
        assert out and out[0].strip() == "empty=True"

    def test_empty_value_preserved(self, engine, monkeypatch):
        monkeypatch.setenv("IBCI_TEST_EMPTY", "")
        out = []
        engine.run_string(
            'import ihost\n'
            'str v = ihost.getenv("IBCI_TEST_EMPTY")\n'
            'print("v=[" + v + "]")\n',
            output_callback=out.append, silent=True)
        assert out and out[0].strip() == "v=[]"


class TestIdbgRuntimeRename:
    def test_runtime_available(self, engine):
        out = []
        engine.run_string(
            'import idbg\n'
            'dict r = idbg.runtime()\n'
            'print("ok=" + (str)(r.len() >= 0))\n',
            output_callback=out.append, silent=True)
        assert out and "ok=" in out[0]

    def test_old_name_gone(self, engine):
        # 旧名 env 已从语言面移除（改名消歧）——模块成员运行期 fail-fast
        # （编译期模块成员检查为宽面，运行期 RUN_ATTRIBUTE_ERROR 确定性报错）
        import core.kernel.issue as issue
        with pytest.raises(issue.InterpreterError, match="env"):
            engine.run_string(
                'import idbg\ndict e = idbg.env()\n', silent=True)
