"""
tests/contracts/test_generator_ibclass.py
==========================================

Contract tests for the dedicated ``generator`` IbClass.

Guards protocol-driven generator dispatch through a properly registered
generator class:

- GEN-1: A dedicated ``generator`` IbClass exists in the kernel registry.
- GEN-2: Its vtable carries ``to_list`` / ``generic_next`` (protocol-driven
  dispatch, no receive special-case).
- GEN-3: A generator value produced by a ``yield`` function carries
  ``ib_class.name == "generator"`` (not the generic ``callable`` class).
- GEN-4: User-explicit ``gen.to_list()`` / ``gen.generic_next()`` dispatch
  through the vtable.
"""

from tests.conftest import run_ibci


class TestGeneratorIbClassRegistry:
    """GEN-1/2：专门 generator IbClass 注册 + vtable 方法。"""

    def test_generator_class_registered_with_vtable(self):
        from core.engine import IBCIEngine

        engine = IBCIEngine(root_dir=None, auto_sniff=False)
        gen_cls = engine.registry.get_class("generator")
        assert gen_cls is not None, "dedicated 'generator' IbClass must exist"
        assert gen_cls.lookup_method("to_list") is not None
        assert gen_cls.lookup_method("generic_next") is not None
        # callable 类不承载生成器方法，生成器方法只挂在 generator 类 vtable 上
        callable_cls = engine.registry.get_class("callable")
        assert callable_cls.lookup_method("to_list") is None
        assert callable_cls.lookup_method("generic_next") is None


class TestGeneratorValueIdentity:
    """GEN-3：生成器值对象持有专门 generator 类。"""

    def test_generator_value_uses_generator_class(self):
        code = """
func gen(int n) -> generator[int]:
    int i = 0
    while i < n:
        yield i
        i = i + 1
print((str)type(gen(3)))
"""
        assert run_ibci(code) == ["generator"]


class TestVtableDispatch:
    """GEN-4：用户显式 to_list()/generic_next() 经 vtable 协议分发可达。"""

    def test_to_list_dispatches_via_vtable(self):
        code = """
func gen(int n) -> generator[int]:
    int i = 0
    while i < n:
        yield i
        i = i + 1
list items = gen(3).to_list()
print((str)items.len())
"""
        assert run_ibci(code) == ["3"]

    def test_generic_next_dispatches_via_vtable(self):
        code = """
func gen(int n) -> generator[int]:
    int i = 0
    while i < n:
        yield i
        i = i + 1
generator[int] g = gen(3)
print((str)g.generic_next())
print((str)g.generic_next())
"""
        assert run_ibci(code) == ["0", "1"]
