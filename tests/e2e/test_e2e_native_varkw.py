"""
tests/e2e/test_e2e_native_varkw.py
==================================

原生模块函数声明 ``**kwargs``（VAR_KEYWORD）的分传端到端验证。

绑定器把 ``**kwargs`` 归集的 dict 装箱为声明序末位的位置实参，loader 代理
（``create_proxy``）把它分传为 ``**kwargs`` 交给原生实现。覆盖具名 / 位置
混合 / 空 kwargs 三种调用形态，以及"声明 VAR_KEYWORD 但实现不接受 **kwargs"
的契约失败路径（加载即失败）。

注意：插件模块名必须全局唯一——loader 复用 ``sys.modules`` 缓存（同名插件
"先加载者胜"，见架构文档 §8.5），同进程内不同测试的同名插件会互相污染。
"""

import os

import pytest

from core.engine import IBCIEngine


def _write_plugin(project: str, name: str, impl: str, spec: str) -> None:
    dest = os.path.join(project, "plugins", name)
    os.makedirs(dest, exist_ok=True)
    for fname, content in (
        ("__init__.py", "from .core import create_implementation\n"),
        ("core.py", impl),
        ("_spec.py", spec),
    ):
        with open(os.path.join(dest, fname), "w", encoding="utf-8") as f:
            f.write(content)


def _run(project: str, main: str):
    out = []
    eng = IBCIEngine(root_dir=project, auto_sniff=True)
    eng.run(os.path.join(project, main), output_callback=lambda s: out.append(str(s)), silent=True)
    return out


def _echo_spec(name: str) -> str:
    return (
        'def __ibcext_metadata__():\n'
        f'    return {{"name": "{name}", "version": "1.0.0", "description": "kwargs probe"}}\n\n'
        'def __ibcext_vtable__():\n'
        '    return {\n'
        '        "functions": {\n'
        '            "echo": {\n'
        '                "params": [\n'
        '                    {"name": "tag", "type": "str"},\n'
        '                    {"name": "kw", "type": "dict", "kind": "VAR_KEYWORD"},\n'
        '                ],\n'
        '                "return_type": "str",\n'
        '            },\n'
        '        },\n'
        '        "variables": {},\n'
        '    }\n'
    )


_ECHO_IMPL = '''\
class Impl:
    def echo(self, tag, **kw):
        return tag + "|" + ",".join(f"{k}={v}" for k, v in sorted(kw.items()))

def create_implementation():
    return Impl()
'''

_BAD_IMPL = '''\
class Impl:
    def echo(self, tag):
        return tag

def create_implementation():
    return Impl()
'''


class TestNativeVarkwDispatch:
    """原生模块函数 **kwargs 分传。"""

    def test_varkw_named_call(self, tmp_path):
        _write_plugin(str(tmp_path), "kwplug_named", _ECHO_IMPL, _echo_spec("kwplug_named"))
        with open(os.path.join(tmp_path, "main.ibci"), "w", encoding="utf-8") as f:
            f.write(
                'import kwplug_named\n'
                'print(kwplug_named.echo(tag="hi", extra="x", n=3))\n'
            )
        assert _run(str(tmp_path), "main.ibci") == ["hi|extra=x,n=3"]

    def test_varkw_mixed_positional(self, tmp_path):
        _write_plugin(str(tmp_path), "kwplug_mixed", _ECHO_IMPL, _echo_spec("kwplug_mixed"))
        with open(os.path.join(tmp_path, "main.ibci"), "w", encoding="utf-8") as f:
            f.write(
                'import kwplug_mixed\n'
                'print(kwplug_mixed.echo("hi", z=1, a=2))\n'
            )
        assert _run(str(tmp_path), "main.ibci") == ["hi|a=2,z=1"]

    def test_varkw_empty(self, tmp_path):
        _write_plugin(str(tmp_path), "kwplug_empty", _ECHO_IMPL, _echo_spec("kwplug_empty"))
        with open(os.path.join(tmp_path, "main.ibci"), "w", encoding="utf-8") as f:
            f.write(
                'import kwplug_empty\n'
                'print(kwplug_empty.echo("hi"))\n'
            )
        assert _run(str(tmp_path), "main.ibci") == ["hi|"]

    def test_varkw_contract_rejected(self, tmp_path):
        _write_plugin(str(tmp_path), "kwplug_bad", _BAD_IMPL, _echo_spec("kwplug_bad"))
        with open(os.path.join(tmp_path, "main.ibci"), "w", encoding="utf-8") as f:
            f.write(
                'import kwplug_bad\n'
                'print(kwplug_bad.echo("hi"))\n'
            )
        with pytest.raises(Exception) as exc_info:
            _run(str(tmp_path), "main.ibci")
        assert "VAR_KEYWORD param" in str(exc_info.value)
