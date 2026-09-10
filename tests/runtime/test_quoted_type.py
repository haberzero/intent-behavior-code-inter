"""
tests/runtime/test_quoted_type.py

quoted 内核原生值类型（R-A 数据/命令二元的数据形态）判别测试：

- 值类型注册：单字段（source）attribute 访问 + 类型锁（``quoted q = meta.quote``
  编译通过；``dict q =`` 编译期类型违约）；
- 值语义：不可变值，按 source 逐字节值相等；
- to_native：完整源串（str——边界拆箱/序列化/值通道消费面）；
- deep_clone：不可变引用复用（同 vector/run_result 纪律）；
- 序列化 round-trip：save/load 保真（source 全保真）；
- cast_to：str/any 转换面（str = 完整源串，失败显式违约）；
- __to_prompt__：完整源串（数据面忠实呈现，无截断——截断即失真）。

quoted 仅经 host（meta.quote 验证门）产出，无语言级构造字面量——str→quoted 不经
cast（源串必须经 meta.quote 验证门成为良构值，无隐式转换通道）。

注：engine fixture 每测试隔离，registry 首次 run 后 seal——``_bootstrap`` 每测试
仅触发一次（后续取类/构造不再 run）。
"""

import pytest

from core.kernel.issue import InterpreterError
from core.runtime.objects.primitives.quoted import IbQuoted
from core.runtime.objects.deep_clone import try_deep_clone
from core.runtime.serialization.runtime_serializer import (
    RuntimeDeserializer,
    RuntimeSerializer,
)


def _bootstrap(engine):
    """触发 bootstrap（每 engine 一次），返回 quoted 内核类引用。"""
    engine.run_string("str _x = '1'", silent=True)
    return engine.registry.get_class("quoted")


def _mk(cls, source="1 + 2"):
    """Python 侧构造 IbQuoted（字段装箱经 registry）。"""
    return IbQuoted(cls, source=source)


def _field(obj, name):
    """attribute 字段观测（经 __getattr__ 派发；仅测试侧，绕 VM 语义层）。"""
    return obj.receive("__getattr__", [obj.ib_class.registry.box(name)])


class TestFieldAccess:
    def test_source_field_attribute_access(self, engine):
        cls = _bootstrap(engine)
        q = _mk(cls, source="2 * (3 + 4)")
        assert _field(q, "source").to_native() == "2 * (3 + 4)"

    def test_unknown_attribute_fail_fast(self, engine):
        cls = _bootstrap(engine)
        q = _mk(cls)
        with pytest.raises(InterpreterError):
            _field(q, "not_a_field")


class TestValueSemantics:
    def test_equality_by_source(self, engine):
        cls = _bootstrap(engine)
        a = _mk(cls, source="1 + 2")
        b = _mk(cls, source="1 + 2")
        c = _mk(cls, source="1+2")  # 逐字节不同（空格）→ 不等
        assert a == b
        assert a != c

    def test_not_hashable(self, engine):
        cls = _bootstrap(engine)
        assert _mk(cls).__hash__ is None


class TestToNative:
    def test_to_native_full_source(self, engine):
        """to_native = 完整源串（str，无截断——数据形态的原生表征）。"""
        cls = _bootstrap(engine)
        q = _mk(cls, source="long expression here")
        assert q.to_native() == "long expression here"

    def test_to_prompt_full_source(self, engine):
        """__to_prompt__ = 完整源串（数据面忠实呈现，与 run_result 截断摘要
        纪律不同：quoted 的数据形态**就是**源串）。"""
        cls = _bootstrap(engine)
        q = _mk(cls, source="x = 1")
        assert q.__to_prompt__() == "x = 1"


class TestDeepClone:
    def test_immutable_reference_reuse(self, engine):
        # 不可变值类型：deep_clone = 引用复用（同 vector/run_result 纪律，identity）
        cls = _bootstrap(engine)
        q = _mk(cls, source="1 + 2")
        assert try_deep_clone(q) is q


class TestCastTo:
    def test_cast_to_str_full_source(self, engine):
        cls = _bootstrap(engine)
        q = _mk(cls, source="40 + 2")
        str_cls = engine.registry.get_class("str")
        cast = q.cast_to(str_cls)
        assert cast.to_native() == "40 + 2"

    def test_cast_to_invalid_fail_fast(self, engine):
        cls = _bootstrap(engine)
        q = _mk(cls)
        int_cls = engine.registry.get_class("int")
        with pytest.raises(InterpreterError):
            q.cast_to(int_cls)


class TestSerializationRoundTrip:
    def test_quote_result_round_trip(self, engine):
        """经 meta.quote 产出的 quoted save/load 保真（source 全保真）。"""
        engine.run_string(
            "import meta\n"
            'quoted q = meta.quote("2 * (3 + 4)")\n',
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
        orig = orig_ctx.get_variable("q")
        rest = restored.get_variable("q")
        assert isinstance(rest, IbQuoted), "round-trip 后须保真 quoted 实现类"
        assert orig.to_native() == rest.to_native()
        assert rest.to_native() == "2 * (3 + 4)"


class TestIbciTypeLock:
    def test_return_type_is_quoted(self):
        """类型锁：meta.quote 返回 quoted——``quoted q =`` 编译通过；
        ``dict q =`` 编译期类型违约。"""
        from tests.conftest import compile_or_errors

        ok, _ = compile_or_errors(
            "import meta\n"
            'quoted q = meta.quote("1 + 2")\n'
        )
        assert ok is not None, "quoted q = meta.quote(...) 须编译通过"

        bad, _ = compile_or_errors(
            "import meta\n"
            'dict bad = meta.quote("1 + 2")\n'
        )
        assert bad is None, "dict 消费 meta.quote 返回值须编译期拒绝"

    def test_eval_param_type_is_quoted(self):
        """类型锁：meta.eval 入参须为 quoted 值——str 直调 = 编译期类型违约
        （无隐式转换通道：源串必须经 meta.quote 验证门）。"""
        from tests.conftest import compile_or_errors

        ok, _ = compile_or_errors(
            "import meta\n"
            "meta.eval(meta.quote(\"1 + 2\"))\n"
        )
        assert ok is not None, "meta.eval(quoted) 须编译通过"

        bad, _ = compile_or_errors(
            "import meta\n"
            'meta.eval("1 + 2")\n'
        )
        assert bad is None, "str 直调 meta.eval 须编译期拒绝"

    def test_no_str_to_quoted_cast(self):
        """无 str→quoted 隐式 cast（验证门唯一入口 = meta.quote）：
        ``quoted q = (quoted)s`` 编译期拒绝。"""
        from tests.conftest import compile_or_errors

        bad, _ = compile_or_errors(
            "import meta\n"
            'str s = "1 + 2"\n'
            "quoted q = (quoted)s\n"
        )
        assert bad is None, "str→quoted cast 须编译期拒绝（无隐式转换面）"
