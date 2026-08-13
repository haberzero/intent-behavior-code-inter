"""tests/e2e/test_auto_init_inheritance.py — 自动构造器继承链绑定 + any 逃生阀复查。

G3 修复（chain-aware auto-init）：无显式 ``__init__`` 的类，构造器参数 = 继承链上
全部有效无默认值字段（父类优先、子类同名覆盖）——消除"auto-init 只收自身 body"
导致的父类字段静默丢失（此前 ``class Sub(Base): str tag`` + ``Sub(5)`` 会把 5 绑到
``tag``、``data`` 静默 None）。

Finding C 修复（any 逃生阀复查）：动态 any 类对象赋给用户类变量时运行时强制
``RUN_TYPE_MISMATCH``（对齐 KNOWN_LIMITS §七"any 值用于类型化上下文时运行时强制校验"），
不再静默流入后报困惑的 AttributeError。
"""
from tests.conftest import run_ibci, expect_runtime_error


class TestAutoInitInheritanceChain:
    def test_non_generic_parent_chain_binding(self):
        code = """class Base:
    int data
class Sub(Base):
    str tag
Sub s = Sub(5, "A")
print((str)s.data)
print(s.tag)
"""
        lines = run_ibci(code)
        assert lines == ["5", "A"]

    def test_generic_parent_chain_binding(self):
        # G3 原始场景：继承特化 + 父类无默认值字段经构造器绑定
        code = """class Node[T]:
    T data
    Node[T] next = any
    func get(self) -> T:
        return self.data
class Linked[T](Node[T]):
    str tag
    func describe(self) -> str:
        return self.tag + ":" + (str)self.get()
Linked[int] l1 = Linked[int](5, "A")
print(l1.describe())
"""
        lines = run_ibci(code, ai=True)
        assert lines == ["A:5"]

    def test_multi_level_chain_binding(self):
        code = """class Base:
    int x
class Mid(Base):
    int y
class Leaf(Mid):
    int z
Leaf obj = Leaf(1, 2, 3)
print((str)obj.x + (str)obj.y + (str)obj.z)
"""
        lines = run_ibci(code)
        assert lines == ["123"]

    def test_child_redeclare_with_default_removes_param(self):
        # 子类同名带默认值 → 覆盖父类 decl-only，不再要求该构造器参数
        code = """class Base:
    int data
class Sub(Base):
    int data = 9
    str tag
Sub s = Sub("A")
print((str)s.data)
print(s.tag)
"""
        lines = run_ibci(code)
        assert lines == ["9", "A"]

    def test_no_own_fields_inherits_parent_auto_init(self):
        code = """class Base:
    int data
class Sub(Base):
    pass
Sub s = Sub(5)
print((str)s.data)
"""
        lines = run_ibci(code)
        assert lines == ["5"]

    def test_explicit_init_preferred(self):
        # 显式 __init__ 优先；父字段须经 super（本用例不调用 → data 保持 None）
        code = """class Base:
    int data
class Sub(Base):
    str tag
    func __init__(self, str t) -> auto:
        self.tag = t
Sub s = Sub("A")
print((str)s.data)
print(s.tag)
"""
        lines = run_ibci(code)
        assert lines == ["None", "A"]

    def test_missing_arg_fails_fast(self):
        # 构造器参数 = 全链 decl-only；少传报错（不再静默错误值）
        code = """class Base:
    int data
class Sub(Base):
    str tag
Sub s = Sub(5)
"""
        expect_runtime_error(code, "missing required argument")

    def test_explicit_init_ancestor_bypassed(self):
        # 祖先显式 __init__ + 子类 auto-init：子类 auto-init 接管全链 decl-only 字段，
        # 祖先 init 副作用不执行（KNOWN_LIMITS §六 note：auto-init 不调用祖先 __init__）。
        code = """class Base:
    int data
    func __init__(self, int v) -> auto:
        self.data = v * 2
class Sub(Base):
    str tag
Sub s = Sub(5, "A")
print((str)s.data)
print(s.tag)
"""
        lines = run_ibci(code)
        assert lines == ["5", "A"]


class TestDynamicAnyRecheckUserClass:
    def test_any_class_object_to_user_class_raises(self):
        # Finding C：any 类对象赋给用户类变量 → RUN_TYPE_MISMATCH
        code = """class Node[T]:
    T data
any a = any
Node[int] n = a
"""
        expect_runtime_error(code, "RUN_TYPE_MISMATCH")

    def test_normal_user_class_assignment_ok(self):
        code = """class Node[T]:
    T data
    func get(self) -> T:
        return self.data
Node[int] n1 = Node[int](5)
Node[int] n2 = n1
print((str)n2.get())
"""
        lines = run_ibci(code, ai=True)
        assert lines == ["5"]

    def test_any_holding_concrete_value_to_builtin_ok(self):
        code = """any a = 42
int y = a
print((str)y)
"""
        lines = run_ibci(code)
        assert lines == ["42"]
