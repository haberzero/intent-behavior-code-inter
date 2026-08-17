"""
tests/e2e/test_native_varkw.py
==================================

原生模块函数声明 ``**kwargs``（VAR_KEYWORD）的分传端到端验证。

绑定器把 ``**kwargs`` 归集的 dict 装箱为声明序末位的位置实参，loader 代理
（``create_proxy``）把它分传为 ``**kwargs`` 交给原生实现。覆盖具名 / 位置
混合 / 空 kwargs 三种调用形态，以及"声明 VAR_KEYWORD 但实现不接受 **kwargs"
的契约失败路径（加载即失败）。

F3：用户侧扩展唯一边 = 宿主绑定 bind；但 VAR_KEYWORD 契约绑定的 loader 语义
属内核契约，此处经 HostInterface 手动注册实现 + TypeDef spec（构造期注册 =
内置模块同路径/环 1 绑定），避免依赖已废弃的用户插件磁盘发现。
"""

import os

import pytest

from core.base.enums import Visibility
from core.engine import IBCIEngine
from core.kernel.spec import (
    TypeDef,
    TypeKind,
    MethodMemberSpec,
    ParamDescriptor,
    TypeRef,
)


class _EchoImpl:
    def echo(self, tag, **kw):
        return tag + "|" + ",".join(f"{k}={v}" for k, v in sorted(kw.items()))


class _BadImpl:
    def echo(self, tag):
        return tag


def _echo_type_def(name: str) -> TypeDef:
    return TypeDef(
        name=name,
        kind=TypeKind.MODULE.value,
        visibility=Visibility.IMPORT_GATED,
        members={
            "echo": MethodMemberSpec(
                name="echo",
                kind="method",
                type_ref=TypeRef.of("str"),
                param_types=[TypeRef.of("str"), TypeRef.of("dict")],
                return_type=TypeRef.of("str"),
                param_descriptors=[
                    ParamDescriptor(name="tag", kind="POSITIONAL_OR_KEYWORD", type_ref=TypeRef.of("str")),
                    ParamDescriptor(name="kw", kind="VAR_KEYWORD", type_ref=TypeRef.of("dict")),
                ],
            ),
        },
    )


def _build_engine(name: str, impl) -> IBCIEngine:
    """构造引擎并把模块直接注册进其 host_interface（与内置模块同路径：构造期注册 + 环 1 绑定）。"""
    eng = IBCIEngine(root_dir=os.getcwd())
    eng.host_interface.register_module(
        name, impl, metadata=_echo_type_def(name), discovery_name="user_kwarg_mod",
    )
    return eng


def _run(project: str, main: str, name: str, impl):
    out = []
    eng = _build_engine(name, impl)
    eng.run(os.path.join(project, main), output_callback=lambda s: out.append(str(s)), silent=True)
    return out


class TestNativeVarkwDispatch:
    """原生模块函数 **kwargs 分传（VAR_KEYWORD 契约绑定；F3 经 HostInterface 手动注册）。"""

    def test_varkw_named_call(self, tmp_path):
        with open(os.path.join(str(tmp_path), "main.ibci"), "w", encoding="utf-8") as f:
            f.write(
                'import kwplug_named\n'
                'print(kwplug_named.echo(tag="hi", extra="x", n=3))\n'
            )
        assert _run(str(tmp_path), "main.ibci", "kwplug_named", _EchoImpl()) == ["hi|extra=x,n=3"]

    def test_varkw_mixed_positional(self, tmp_path):
        with open(os.path.join(str(tmp_path), "main.ibci"), "w", encoding="utf-8") as f:
            f.write(
                'import kwplug_mixed\n'
                'print(kwplug_mixed.echo("hi", z=1, a=2))\n'
            )
        assert _run(str(tmp_path), "main.ibci", "kwplug_mixed", _EchoImpl()) == ["hi|a=2,z=1"]

    def test_varkw_empty(self, tmp_path):
        with open(os.path.join(str(tmp_path), "main.ibci"), "w", encoding="utf-8") as f:
            f.write(
                'import kwplug_empty\n'
                'print(kwplug_empty.echo("hi"))\n'
            )
        assert _run(str(tmp_path), "main.ibci", "kwplug_empty", _EchoImpl()) == ["hi|"]

    def test_varkw_contract_rejected(self, tmp_path):
        with open(os.path.join(str(tmp_path), "main.ibci"), "w", encoding="utf-8") as f:
            f.write(
                'import kwplug_bad\n'
                'print(kwplug_bad.echo("hi"))\n'
            )
        with pytest.raises(Exception) as exc_info:
            _run(str(tmp_path), "main.ibci", "kwplug_bad", _BadImpl())
        assert "VAR_KEYWORD param" in str(exc_info.value)
