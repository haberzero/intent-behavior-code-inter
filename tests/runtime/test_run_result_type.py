"""
tests/runtime/test_run_result_type.py

run_result 内核原生值类型（meta 层 MVP M1）判别测试：

- 值类型注册：三字段（exit_status/stdout/exception）attribute 访问 + 类型锁；
- 值语义：不可变 record，按三字段值相等（== 经 vtable 派发）；
- to_native：原生三字段结构（序列化/边界消费面）；
- deep_clone：不可变引用复用（同 vector 纪律）；
- 序列化 round-trip：save/load 保真（三字段全保真）；
- cast_to：str/any 转换面（失败显式违约）。

字段访问经 ``_dispatch_getattr`` 实例字段优先命中（Exception.message 先例）；
run_result 仅经 host（ihost.run_file/run_code）产出，无语言级构造字面量。

注：engine fixture 每测试隔离，registry 首次 run 后 seal——``_bootstrap`` 每测试
仅触发一次（后续取类/构造不再 run）。
"""

import pytest

from core.kernel.issue import InterpreterError
from core.runtime.objects.primitives.run_result import IbRunResult
from core.runtime.objects.deep_clone import try_deep_clone
from core.runtime.serialization.runtime_serializer import (
    RuntimeDeserializer,
    RuntimeSerializer,
)


def _bootstrap(engine):
    """触发 bootstrap（每 engine 一次），返回 run_result 内核类引用。"""
    engine.run_string("str _x = '1'", silent=True)
    return engine.registry.get_class("run_result")


def _mk(cls, exit_status="ok", stdout="hi", exception=None):
    """Python 侧构造 IbRunResult（字段装箱经 registry）。"""
    return IbRunResult(cls, exit_status=exit_status, stdout=stdout, exception=exception)


def _field(obj, name):
    """attribute 字段观测（经 __getattr__ 派发；仅测试侧，绕 VM 语义层）。"""
    return obj.receive("__getattr__", [obj.ib_class.registry.box(name)])


class TestFieldAccess:
    def test_three_fields_attribute_access(self, engine):
        cls = _bootstrap(engine)
        r = _mk(cls, exit_status="ok", stdout="out-123",
                exception={"code": "RUN_DIVISION_BY_ZERO",
                           "message": "div by zero",
                           "source": {"file": "f.ibci", "line": 3, "column": 9}})
        assert _field(r, "exit_status").to_native() == "ok"
        assert _field(r, "stdout").to_native() == "out-123"
        ex = _field(r, "exception")
        # 结构化 dict 装箱 IbDict：字段可经下标读取
        assert ex.receive("__getitem__", [ex.ib_class.registry.box("code")]).to_native() \
            == "RUN_DIVISION_BY_ZERO"

    def test_exception_none(self, engine):
        cls = _bootstrap(engine)
        r = _mk(cls, exit_status="ok", stdout="", exception=None)
        ex = _field(r, "exception")
        # None 字段 = 语言层 None（非 dict）
        assert ex.to_native() is None

    def test_unknown_attribute_fail_fast(self, engine):
        cls = _bootstrap(engine)
        r = _mk(cls)
        with pytest.raises(InterpreterError):
            _field(r, "not_a_field")


class TestValueSemantics:
    def test_equality_by_fields(self, engine):
        cls = _bootstrap(engine)
        a = _mk(cls, exit_status="ok", stdout="s", exception=None)
        b = _mk(cls, exit_status="ok", stdout="s", exception=None)
        c = _mk(cls, exit_status="error", stdout="s", exception=None)
        assert a == b
        assert a != c

    def test_not_hashable(self, engine):
        cls = _bootstrap(engine)
        a = _mk(cls)
        assert a.__hash__ is None


class TestToNative:
    def test_to_native_native_structure(self, engine):
        cls = _bootstrap(engine)
        exc = {"code": "RUN_X", "message": "m", "source": {"line": 1}}
        r = _mk(cls, exit_status="error", stdout="o", exception=exc)
        native = r.to_native()
        assert native == {"exit_status": "error", "stdout": "o", "exception": exc}

    def test_to_native_exception_none(self, engine):
        cls = _bootstrap(engine)
        r = _mk(cls, exit_status="ok", stdout="", exception=None)
        assert r.to_native()["exception"] is None


class TestDeepClone:
    def test_immutable_reference_reuse(self, engine):
        # 不可变值类型：deep_clone = 引用复用（同 vector 纪律，identity）
        cls = _bootstrap(engine)
        r = _mk(cls, exit_status="ok", stdout="s",
                exception={"code": "RUN_X", "message": "m", "source": None})
        assert try_deep_clone(r) is r


class TestCastTo:
    def test_cast_to_str(self, engine):
        cls = _bootstrap(engine)
        r = _mk(cls, exit_status="ok", stdout="hello", exception=None)
        str_cls = engine.registry.get_class("str")
        cast = r.cast_to(str_cls)
        assert isinstance(cast.to_native(), str)
        assert "hello" in cast.to_native()

    def test_cast_to_invalid_fail_fast(self, engine):
        cls = _bootstrap(engine)
        r = _mk(cls)
        int_cls = engine.registry.get_class("int")
        with pytest.raises(InterpreterError):
            r.cast_to(int_cls)


class TestSerializationRoundTrip:
    def test_run_code_result_round_trip(self, engine):
        """经 host 产出的 run_result（字符串源成功）save/load 三字段保真。"""
        engine.run_string(
            "import ihost\n"
            'run_result r = ihost.run_code("print(\'roundtrip\')", {})\n',
            silent=True,
        )
        ec = engine.interpreter.execution_context
        orig_ctx = ec.runtime_context
        data = RuntimeSerializer(engine.registry).serialize_context(
            orig_ctx, include_static=False
        )
        restored = RuntimeDeserializer(
            engine.registry, factory=ec.factory
        ).deserialize_context(data)
        orig = orig_ctx.get_variable("r")
        rest = restored.get_variable("r")
        assert isinstance(rest, IbRunResult), "round-trip 后须保真 run_result 实现类"
        assert orig.to_native() == rest.to_native()
        assert rest.to_native() == {
            "exit_status": "ok",
            "stdout": "roundtrip",
            "exception": None,
        }


class TestIbciTypeLock:
    def test_return_type_is_run_result_not_dict(self):
        """类型锁：ihost.run_code 返回 run_result（非 dict）——
        `run_result r =` 编译通过；`dict r =` 编译期类型违约。"""
        from tests.conftest import compile_or_errors

        ok, _ = compile_or_errors(
            "import ihost\n"
            'run_result r = ihost.run_code("str a = \'1\'", {})\n'
        )
        assert ok is not None, "run_result r = ihost.run_code(...) 须编译通过"

        bad, _ = compile_or_errors(
            "import ihost\n"
            'dict bad = ihost.run_code("str a = \'1\'", {})\n'
        )
        assert bad is None, "dict 消费 run_result 返回值须编译期拒绝"
