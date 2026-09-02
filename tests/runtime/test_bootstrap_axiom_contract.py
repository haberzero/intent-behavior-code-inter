"""
tests/runtime/test_bootstrap_axiom_contract.py
==============================================

Bootstrap axiom 声明能力契约校验（PT-DEBT-36）白盒判别测试。

修复背景（2026-08-20）：bootstrap 自动绑定用 ``hasattr(py_impl_cls, magic_name)``
探测运算符/方法——① ``bool.__or__`` 经 Python 元类命中 ``type.__or__``（PEP 604
类型联合运算符），绑定成类对象运算符，``bool | bool`` 运行期报
"expected 1 argument, got 2"；② 公理声明的方法若 impl 类缺失且既非协议分派
又非字段，运行期将神秘 AttributeError（无 bootstrap 期契约校验）。

修复：
- ``_is_impl_method``：用 ``getattr_static`` 取原始描述符并校验类型，排除元类伪影；
- ``_verify_axiom_bindings``：bootstrap 末尾校验公理声明的方法实际可绑定
  （vtable / 协议分派 / 字段承载），契约违约 fail-fast。
"""
import os

from core.engine import IBCIEngine

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _new_engine():
    return IBCIEngine(root_dir=_ROOT)


def test_bool_bitwise_operators_bind_instance_impl():
    """bool 位运算 &/|/^ 全部绑定实例实现（不再误绑元类 type.__or__）。"""
    eng = _new_engine()
    bool_cls = eng.registry.get_class("bool")
    for op in ("__or__", "__and__", "__xor__"):
        m = bool_cls.lookup_method(op)
        assert m is not None, f"bool.{op} 应已绑定"
        # 实例实现：py_func 是 IbBool/继承的方法，而非 method-wrapper（元类伪影）
        py = getattr(m, "py_func", None)
        assert not (
            py is not None and isinstance(py, __import__("types").MethodWrapperType)
        ), f"bool.{op} 不应绑定元类 method-wrapper: {py!r}"


def test_bool_bitwise_or_runtime():
    """回归：``bool | bool`` 运行期正常（修复前 "expected 1 argument, got 2"）。"""
    eng = _new_engine()
    out = []
    eng.run_string(
        "bool a = True\nbool b = False\nbool c = a | b\nprint(c)\n",
        output_callback=lambda s: out.append(str(s)),
        silent=True,
    )
    assert out == ["True"], out


def test_axiom_contract_check_passes_for_builtins():
    """契约校验对真实内置类零误报（全部公理声明方法可绑定/协议/字段）。"""
    eng = _new_engine()  # 若 _verify_axiom_bindings 误报则引擎 ready 失败
    assert eng.registry is not None


def test_verify_axiom_bindings_catches_unbound_method():
    """契约校验能捕获"声明但未绑定"的方法（fail-fast 判别）。

    直接驱动 ``_verify_axiom_bindings``：构造一个声明方法缺失绑定的假公理类
    （方法非字段、非协议分派、无 vtable），应抛 InterpreterError。
    """
    from core.runtime.bootstrap.primitive_initializer import _verify_axiom_bindings
    from core.kernel.issue import InterpreterError
    from core.kernel.spec.member import MethodMemberSpec
    from core.kernel.spec.type_ref import TypeRef

    class FakeAxiom:
        def get_method_specs(self):
            return {
                "ghost_method": MethodMemberSpec(
                    name="ghost_method", kind="method", type_ref=TypeRef.of("int")
                ),
            }

    # 构造一个假 ib_class：lookup_method 恒 None（无 vtable 绑定）
    class FakeIbClass:
        name = "FakeType"

        def __init__(self, spec):
            self.spec = spec

        def lookup_method(self, name):
            return None

    # 假 metadata_registry：get_axiom 返回 FakeAxiom；dunder_names 空（无协议分派）
    class FakeMetaRegistry:
        def get_axiom(self, spec):
            return FakeAxiom()

        def dunder_names(self):
            return frozenset()

    fake_spec = object()
    try:
        _verify_axiom_bindings(
            {"FakeType": FakeIbClass(fake_spec)}, FakeMetaRegistry()
        )
        raise AssertionError("契约校验应捕获未绑定的声明方法")
    except InterpreterError as e:
        assert "ghost_method" in str(e), f"错误应指明缺失方法：{e}"
