"""
tests/runtime/test_protocol_dispatch_contract.py — receive 协议化分派契约。

判别性契约（白盒）：
- receive 对协议消息经命名处理器分派（_dispatch_<dunder> 存在性）；
- 处理器覆写保持类型特定语义（None 恒等 / Optional 委托 / 类特化下标）；
- 特化类 _impl_cls 沿 spec 基名结构化解析。
"""

import os

import pytest

from core.engine import IBCIEngine

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _engine():
    return IBCIEngine(root_dir=_ROOT)


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

    def test_unexecuted_behavior_to_prompt_preserved(self):
        """未缓存 IbBehavior 的 __to_prompt__ 返回描述。"""
        from core.runtime.objects.primitives.callables import IbBehavior

        engine = _engine()
        engine.run_string("int x = 1\n", silent=True)  # 引擎初始化（类表就绪）
        behavior_cls = engine.registry.get_class("behavior")
        assert behavior_cls is not None
        # 未执行（无 cache）行为对象：__to_prompt__ 应返回描述而非抛错
        behavior = IbBehavior("node-x", None, behavior_cls)
        result = behavior.receive("__to_prompt__", [])
        assert str(result) != "", "未执行行为 __to_prompt__ 应返回描述（非抛错）"

    def test_cast_to_vtable_first_message_level(self):
        """cast_to 消息级：vtable 转换实现先行。"""
        engine = _engine()
        engine.run_string(
            "int i = (int)'123'\n"
            "bool b = (bool)1\n",
            silent=True,
        )
        assert _symbol(engine, "i").to_native() == 123
        assert _symbol(engine, "b").to_native() is True

    def test_user_call_cps_drive_message_level(self):
        """用户类 __call__ 经 _UserCallDrive 消息级分派（CPS 路径保持）。"""
        from core.runtime.objects.kernel.ib_class import _UserCallDrive

        engine = _engine()
        engine.run_string(
            "class Adder:\n"
            "    int n\n"
            "    func __init__(self, int v) -> auto:\n"
            "        self.n = v\n"
            "    func __call__(self, int x) -> int:\n"
            "        return self.n + x\n"
            "Adder a = Adder(10)\n",
            silent=True,
        )
        a = _symbol(engine, "a")
        result = a.receive("__call__", [engine.registry.box(5)])
        # 用户 __call__ 返回 CPSDrivable drive（VM 帧内驱动，非同步执行）
        assert isinstance(result, _UserCallDrive), (
            f"用户 __call__ 应返回 _UserCallDrive，got {type(result)}"
        )

    def test_some_optional_delegation_message_level(self):
        """Some-Optional 容器消息委托内层（消息级契约锁定）。"""
        engine = _engine()
        engine.run_string(
            "Optional[list[int]] ol = [1, 2, 3]\n",
            silent=True,
        )
        ol = _symbol(engine, "ol")
        # len 消息委托内层 list（有值路径）
        assert ol.receive("len", []).to_native() == 3
        # __getitem__ 消息委托内层（有值路径）
        assert ol.receive("__getitem__", [engine.registry.box(0)]).to_native() == 1


class TestImplClsStructuredResolution:
    """特化类 _impl_cls 沿 spec 基名结构化解析。"""

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


class TestProtocolVTableDataStructure:
    """per-IbClass 协议方法表：消息名键 + 多态 native 解析。"""

    def test_protocol_vtable_is_slots_field(self):
        """IbClass.__slots__ 含 protocol_vtable（数据结构落地）。"""
        from core.runtime.objects.kernel.ib_class import IbClass

        assert "protocol_vtable" in IbClass.__slots__

    def test_protocol_slot_keyed_by_message_name(self):
        """协议方法表按消息名（dunder 方法名）索引，非协议名。"""
        engine = _engine()
        engine.run_string("int x = 1\n", silent=True)
        ic = engine.registry.get_class("int")
        # 协议消息（__to_prompt__ / __call__ / cast_to）→ 建槽
        assert ic.protocol_slot("__to_prompt__") is not None
        assert ic.protocol_slot("__call__") is not None
        assert ic.protocol_slot("cast_to") is not None
        # 多协议共方法按消息名索引：__getattr__ → attribute 协议
        assert ic.protocol_slot("__getattr__") is not None
        # 非协议消息 → None（落普通 vtable 路由）
        assert ic.protocol_slot("len") is None
        assert ic.protocol_slot("toString") is None

    def test_protocol_slot_native_polymorphic_resolution(self):
        """native 处理器按值 Python 类解析（多态安全：callable 宿主 IbFunction 族
        与 IbSuperProxy，各按其 MRO 落 IbObject / 自有 _dispatch_*）。"""
        engine = _engine()
        engine.run_string("int x = 1\n", silent=True)
        callable_cls = engine.registry.get_class("callable")
        slot = callable_cls.protocol_slot("__call__")

        from core.runtime.objects.kernel.functions import (
            IbFunction,
            IbSuperProxy,
            IbNativeFunction,
        )

        # IbFunction 族（无自有 _dispatch_call）→ 经 MRO 落 IbObject._dispatch_call
        nf = IbNativeFunction(lambda *a: 0, ib_class=callable_cls)
        handler = slot.active_handler(nf)
        from core.runtime.objects.kernel.base import IbObject

        assert handler is IbObject._dispatch_call, (
            f"IbFunction 族 native 应落 IbObject._dispatch_call，got {handler}"
        )
        # IbSuperProxy（自有 _dispatch_call）→ 其自身处理器
        proxy = IbSuperProxy.__new__(IbSuperProxy)
        # 仅验证类级解析（避免构造代理依赖）
        assert IbSuperProxy._dispatch_call is not IbObject._dispatch_call

    def test_overlay_default_inactive(self):
        """覆层影子条目默认不参与分派（native 优先，overlay 惰性缺席）。"""
        engine = _engine()
        engine.run_string("int x = 1\n", silent=True)
        ic = engine.registry.get_class("int")
        # __getattr__ 有原生 _dispatch_getattr 处理器（MRO 落 IbObject）——验证
        # 未启用覆层时 active_handler = native（覆盖"查表分派 + 覆层缺省"两语义）。
        slot = ic.protocol_slot("__getattr__")
        assert slot is not None
        assert slot.overlay is None
        assert slot.overlay_enabled is False
        value = engine.registry.box(42)
        from core.runtime.objects.kernel.base import IbObject

        assert slot.active_handler(value) is IbObject._dispatch_getattr

    def test_receive_protocol_dispatch_unaffected(self):
        """查表分派接入后：消息级协议语义保持（判别性回归）。"""
        engine = _engine()
        engine.run_string(
            "bool a = (None == None)\n"
            "bool b = (1 == 1)\n"
            "int c = (int)'123'\n",
            silent=True,
        )
        assert _symbol(engine, "a").to_native() is True
        assert _symbol(engine, "b").to_native() is True
        assert _symbol(engine, "c").to_native() == 123


class TestSatisfactionDispatchConvergence:
    """判定（``satisfies_protocol``，协议条目数据驱动）与分派（``receive``，per-IbClass
   协议方法表 + vtable）以**协议条目为单一权威**的一致性契约——编译期类型判定与
   运行期消息分派无双表漂移。

    - 用户类声明协议方法 → satisfies True 且 receive 可分派（一致）；
    - 未声明 → satisfies False（协议消费前置门拒绝协议路径）且 receive 对无默认
      实现的协议消息不误分派（AttributeError 显式暴露）；
    - protocol_vtable 惰性建槽（运行期按需注册，不依赖内置 spec 持久化）；
    - 协议条目的 optional 方法（``__intent__``/``__retry__``）不建协议槽，经
      lookup_method 虚表发现（运行时 optional 通道）。
    """

    def _meta(self, engine):
        return engine.registry.get_metadata_registry()

    def test_user_protocol_method_satisfies_and_dispatches(self):
        """用户类声明协议方法（__to_prompt__）：satisfies True 且 receive 可分派。"""
        engine = _engine()
        engine.run_string(
            "class Item:\n"
            "    str name\n"
            "    func __init__(self, str n) -> auto:\n"
            "        self.name = n\n"
            "    func __to_prompt__(self) -> str:\n"
            '        return "item:" + self.name\n'
            "Item it = Item(\"x\")\n",
            silent=True,
        )
        it = _symbol(engine, "it")
        assert self._meta(engine).satisfies_protocol(it.ib_class.spec, "to_prompt") is True
        # 用户类无原生 _dispatch_to_prompt__ 处理器：协议表槽 miss → 落 vtable（lookup_method）
        result = it.receive("__to_prompt__", [])
        assert result.to_native() == "item:x", f"receive 分派结果: {result!r}"

    def test_missing_protocol_method_no_misdispatch(self):
        """未声明协议方法的类：satisfies False（协议消费前置门据此拒绝协议路径）；
        receive 对**无默认实现**的协议消息（__payload_prompt__）不误分派（AttributeError
        显式暴露）。to_prompt 例外说明：Object 根类提供默认实例渲染（vtable 继承）——
        satisfies 仍 False，消费门（PromptRenderer）以 satisfies 为准（协议前置门语义）。"""
        engine = _engine()
        engine.run_string(
            "class Plain:\n"
            "    int v\n"
            "Plain p = Plain(0)\n",
            silent=True,
        )
        p = _symbol(engine, "p")
        spec = p.ib_class.spec
        assert self._meta(engine).satisfies_protocol(spec, "payload_prompt") is False
        with pytest.raises(AttributeError):
            p.receive("__payload_prompt__", [])
        # to_prompt：Object 默认渲染存在但 satisfies 仍 False（门语义契约点）
        assert self._meta(engine).satisfies_protocol(spec, "to_prompt") is False

    def test_protocol_vtable_lazy_slot_creation(self):
        """protocol_vtable 惰性建槽（运行期按需注册）：未分派不建槽，分派后建槽；
        非协议消息（len 普通路由）不建槽。"""
        engine = _engine()
        engine.run_string("list[int] li = [1]\n", silent=True)
        li = _symbol(engine, "li")
        ic = li.ib_class
        assert ic.protocol_vtable == {}, "未分派前不应建槽"
        # len 是普通消息（非协议 dunder）→ 不建协议槽
        _ = li.receive("len", [])
        assert ic.protocol_vtable == {}, "普通消息不应触发协议槽建槽"
        # 协议消息分派 → 惰性建槽
        _ = li.receive("__to_prompt__", [])
        assert "__to_prompt__" in ic.protocol_vtable, "协议消息分派后应建槽"

    def test_llm_callable_optional_methods_not_in_dispatch_table(self):
        """llm_callable 的 optional 方法（__intent__/__retry__）不建协议槽
        （dunder_names 仅 required），经 lookup_method 虚表发现（运行时 optional 通道）；
        required（__llm_call__）建立槽。"""
        engine = _engine()
        engine.run_string(
            "class Agent:\n"
            "    func __intent__(self, dict d) -> dict:\n"
            "        return {}\n"
            "    func __retry__(self) -> dict:\n"
            "        return {}\n"
            "    func __llm_call__(self) -> dict:\n"
            '        return {"user_prompt": "hi"}\n'
            "Agent a = Agent()\n",
            silent=True,
        )
        a = _symbol(engine, "a")
        spec = a.ib_class.spec
        assert self._meta(engine).satisfies_protocol(spec, "llm_callable") is True
        ic = a.ib_class
        # required 方法建立协议槽（dunder_names 含 __llm_call__）
        assert ic.protocol_slot("__llm_call__") is not None
        # optional 方法不建协议槽（不参与 _dispatch_* 协议分派索引）
        assert ic.protocol_slot("__intent__") is None
        assert ic.protocol_slot("__retry__") is None
        # 但经 lookup_method 虚表可发现（运行时 optional 通道）
        assert ic.lookup_method("__intent__") is not None
        assert ic.lookup_method("__retry__") is not None
