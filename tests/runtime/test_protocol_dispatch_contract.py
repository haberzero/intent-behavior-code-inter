"""
tests/runtime/test_protocol_dispatch_contract.py — receive 协议化分派契约（阶段 A）。

阶段 A 判别性契约（白盒）：
- receive 对协议消息经命名处理器分派（_dispatch_<dunder> 存在性）；
- 处理器覆写保持类型特定语义（None 恒等 / Optional 委托 / 类特化下标）；
- 特化类 _impl_cls 沿 spec 基名结构化解析（A3 契约锁定）。
"""

import os

from core.engine import IBCIEngine

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _engine():
    return IBCIEngine(root_dir=_ROOT, auto_sniff=False)


def _symbol(engine, name):
    rc = engine.interpreter.execution_context.runtime_context
    return rc.get_symbol(name).value


class TestProtocolDispatchHandlers:
    """receive 协议化分派：处理器存在性与语义保持。"""

    def test_base_receive_has_call_handler(self):
        from core.runtime.objects.kernel.base import IbObject

        assert hasattr(IbObject, "_dispatch_call")
        assert hasattr(IbObject, "_dispatch_getattr")
        assert hasattr(IbObject, "_dispatch_cast_to")

    def test_ibnone_eq_dispatch_preserved(self):
        """IbNone == None 恒等经 _dispatch_eq 保持（None 语义空白区闭合）。"""
        engine = _engine()
        engine.run_string("bool a = (None == None)\nbool b = (None == 1)\n", silent=True)
        assert _symbol(engine, "a").to_native() is True
        assert _symbol(engine, "b").to_native() is False

    def test_optional_eq_dispatch_preserved(self):
        """空 Optional == None 经 _dispatch_eq 保持（统一 Optional 值模型）。"""
        engine = _engine()
        engine.run_string(
            "Optional[int] x = None\n"
            "bool a = (x == None)\n"
            "bool b = (x == 1)\n",
            silent=True,
        )
        assert _symbol(engine, "a").to_native() is True
        assert _symbol(engine, "b").to_native() is False

    def test_class_getitem_specialize_dispatch_preserved(self):
        """类对象特化下标经 _dispatch_getitem（Box[int] 特化）保持。"""
        engine = _engine()
        engine.run_string(
            "class Box[T]:\n"
            "    T value\n"
            "    func __init__(self, T v) -> auto:\n"
            "        self.value = v\n"
            "Box[int] b = Box[int](5)\n",
            silent=True,
        )
        assert _symbol(engine, "b").ib_class.name == "Box[int]"

    def test_super_proxy_dispatch_preserved(self):
        """super() 代理 __getattr__/__call__ 处理器语义保持。"""
        engine = _engine()
        engine.run_string(
            "class Base:\n"
            "    func greet(self) -> str:\n"
            "        return 'base'\n"
            "class Sub(Base):\n"
            "    func greet(self) -> str:\n"
            "        return super().greet() + '!' \n"
            "str s = Sub().greet()\n",
            silent=True,
        )
        assert _symbol(engine, "s").to_native() == "base!"

    def test_fn_callable_internal_messages_preserved(self):
        """FnCallable 内部元数据消息（__return_type__ 等）经集中声明保持。"""
        engine = _engine()
        engine.run_string(
            "func make() -> fn[(int) -> int]:\n"
            "    return lambda(int x) -> int: x * 2\n"
            "fn[(int) -> int] f = make()\n",
            silent=True,
        )
        f = _symbol(engine, "f")
        # 未执行函数值可查询签名元数据（原 __return_type__ 分支语义）
        assert f.receive("__return_type__", []).to_native() is not None


class TestImplClsStructuredResolution:
    """特化类 _impl_cls 沿 spec 基名结构化解析（A3 契约）。"""

    def test_specialized_list_impl_cls_resolves_to_base(self):
        from core.runtime.objects.primitives.collections import IbList

        engine = _engine()
        engine.run_string("list[int] li = [1, 2]\n", silent=True)
        li = _symbol(engine, "li")
        assert li.ib_class.name == "list[int]"
        impl = li.ib_class._impl_cls()
        assert impl is not None
        assert issubclass(impl, IbList), f"_impl_cls 未解析到基类实现: {impl}"

    def test_specialized_user_class_impl_cls_falls_back_to_object(self):
        """用户类特化（无 Python 实现注册）_impl_cls 为 None → 默认 IbObject。"""
        engine = _engine()
        engine.run_string(
            "class Box[T]:\n"
            "    T value\n"
            "Box[int] b = Box[int](5)\n",
            silent=True,
        )
        b = _symbol(engine, "b")
        assert b.ib_class._impl_cls() is None
