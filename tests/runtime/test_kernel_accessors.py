"""
tests/runtime/test_kernel_accessors.py
=======================================

内核接口协议化测试：

* ``BoundPlugin`` 容器承载 (implementation, registry_id)，替代向插件实现对象
  注入 ``_ibci_registry_id`` 私有属性。
* ``InterOpImpl.register_package`` 记录 registry_id，``get_registry_id`` 可查。
* ``IbNativeObject`` 携带 registry_id，跨引擎访问时抛 ``RegistryIsolationError``。
* ``RuntimeContextImpl`` 通信域/线程协调器公开访问器（get_* 惰性创建 /
  peek_* 只读返回）。
* ``LLMExecutor`` 在途 Future 只读计数访问器。
"""
from core.runtime.interpreter.interop import BoundPlugin, InterOpImpl
from core.runtime.interpreter.runtime_context import RuntimeContextImpl
from core.runtime.exceptions import RegistryIsolationError
from core.runtime.objects.kernel import IbNativeObject


class TestBoundPluginContainer:
    """BoundPlugin 容器：实现 + registry 身份。"""

    def test_container_carries_implementation_and_registry_id(self):
        impl = object()
        plugin = BoundPlugin(impl, 12345)
        assert plugin.implementation is impl
        assert plugin.registry_id == 12345

    def test_register_package_records_registry_id(self):
        interop = InterOpImpl()
        impl = object()
        interop.register_package("mymod", BoundPlugin(impl, 42))
        assert interop.get_registry_id("mymod") == 42
        assert interop.get_package("mymod") is impl

    def test_register_package_raw_object_has_no_registry_id(self):
        interop = InterOpImpl()
        interop.register_package("mymod", object())
        assert interop.get_registry_id("mymod") is None


class TestIbNativeObjectIsolation:
    """IbNativeObject 跨引擎隔离：registry_id 不匹配即拒绝。"""

    def _make_native(self, registry, registry_id):
        return IbNativeObject(
            object(),
            registry.get_class("Object"),
            registry_id=registry_id,
        )

    def test_matching_registry_id_passes(self, engine):
        engine.run_string("int seed = 1\n", silent=True)
        registry = engine.registry
        native = self._make_native(registry, id(registry))
        # 不抛错即可
        assert native.ib_class.name == "Object"

    def test_mismatched_registry_id_raises(self, engine):
        engine.run_string("int seed = 1\n", silent=True)
        registry = engine.registry
        native = self._make_native(registry, id(registry) + 1)
        try:
            native.receive("__getattr__", [registry.box("anything")])
            raise AssertionError("expected RegistryIsolationError")
        except RegistryIsolationError:
            pass

    def test_no_registry_id_skips_check(self, engine):
        engine.run_string("int seed = 1\n", silent=True)
        registry = engine.registry
        native = self._make_native(registry, None)
        # 不抛错即可（无跨引擎约束）
        assert native.registry_id is None


class TestRuntimeContextCommAccessors:
    """RuntimeContextImpl 通信域访问器：peek 只读 / get 惰性创建。"""

    def test_comm_registry_peek_then_get(self, ctx):
        assert ctx.peek_comm_registry() is None
        reg = ctx.get_comm_registry()
        assert reg is not None
        # 二次取同一实例（惰性创建幂等）
        assert ctx.get_comm_registry() is reg

    def test_config_store_accessors(self, ctx):
        assert ctx.peek_config_store() is None
        store = ctx.get_config_store()
        assert store is not None
        assert ctx.get_config_store() is store
    def test_event_bus_accessors(self, ctx):
        """事件总线为引擎级注入共享实例（engine 装配时 set_event_bus）。

        peek 只读返回注入实例；get 返回同一实例（未注入时 fail-fast）。
        """
        bus = ctx.get_event_bus()
        assert bus is not None
        assert ctx.get_event_bus() is bus
        assert ctx.peek_event_bus() is bus

    def test_event_bus_uninjected_fail_fast(self):
        """未注入事件总线的 registry：peek 返回 None，get 装配错误 fail-fast。

        事件总线是 runtime 观测设施，须由 engine（组装层）注入；未注入即
        调用属装配错误，应明确暴露而非静默降级。
        """
        from core.kernel.registry import KernelRegistry
        from core.runtime.interpreter.runtime_context import RuntimeContextImpl

        registry = KernelRegistry()
        ctx = RuntimeContextImpl(registry=registry)
        assert ctx.peek_event_bus() is None
        try:
            ctx.get_event_bus()
            raise AssertionError("expected RuntimeError for uninjected event bus")
        except RuntimeError as e:
            assert "set_event_bus" in str(e)

    def test_runtime_coordinator_accessors(self, ctx):
        assert ctx.peek_runtime_coordinator() is None
        coord = ctx.get_runtime_coordinator(interpreter=None)
        assert coord is not None
        assert ctx.get_runtime_coordinator() is coord


class TestLLMExecutorPendingCount:
    """LLMExecutor 在途 Future 只读计数访问器。"""

    def test_pending_futures_count_readable(self, engine):
        from tests.conftest import AI_MOCK_PREFIX
        engine.run_string(
            AI_MOCK_PREFIX +
            "str x = @~ MOCK:STR:alpha ~\n"
            "str y = @~ MOCK:STR:beta ~\n",
            silent=True,
        )
        executor = engine.interpreter.service_context.llm_executor
        # 公开访问器可读：返回非负整数（在途 Future 计数契约），读取即经锁切片
        count = executor.pending_futures_count()
        assert isinstance(count, int)
        assert count >= 0
        assert executor.pending_futures_count() == count
