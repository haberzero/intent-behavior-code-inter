"""
tests/e2e/test_value_semantics.py — 值语义契约判别测试（核心引用语义）。

锁定 ``docs/syntax/02_variables.md`` §2.8 值语义权威契约中此前**无判别测试**的
核心面：复合对象赋值别名 / 传参共享引用 / 不可变原语赋值独立 / ``is`` vs ``==``
（标量值比较 + 容器默认身份比较）。

其余契约面由既有测试锁定（单点真理，不重复）：
- ``copy`` / ``deepcopy``：tests/e2e/test_copy_intrinsics.py
- snapshot 冻结 / 重入：tests/e2e/test_higher_order.py
- llmexcept 快照 / ``__snapshot__`` 协议：tests/e2e/test_llmexcept.py
- 类字段默认值每实例深克隆：tests/e2e/test_classes.py TestFieldDefaultIndependence
"""

from tests.conftest import run_ibci


class TestAssignmentAlias:
    """复合对象赋值 = 引用复制（别名）：任一名就地修改，另一名可见。"""

    def test_list_assignment_is_alias(self):
        code = """\
list a = [1, 2, 3]
list b = a
b.append(4)
print((str)a.len())
print((str)b.len())
"""
        assert run_ibci(code) == ["4", "4"]

    def test_dict_assignment_is_alias(self):
        code = """\
dict d = {"a": 1}
dict d2 = d
d2["b"] = 2
print((str)d.len())
print((str)d2.len())
"""
        assert run_ibci(code) == ["2", "2"]

    def test_user_object_assignment_is_alias(self):
        code = """\
class Pt:
    int x
    func __init__(self, int v) -> auto:
        self.x = v
Pt a = Pt(1)
Pt b = a
b.x = 5
print((str)a.x)
print((str)b.x)
"""
        assert run_ibci(code) == ["5", "5"]


class TestParamPassingSharedReference:
    """实参按共享引用传入：函数内就地修改可变参数影响调用方；重绑定不影响。"""

    def test_param_list_mutation_affects_caller(self):
        code = """\
func push_one(list b) -> int:
    b.append(1)
    return b.len()
list buf = []
push_one(buf)
print((str)buf.len())
"""
        assert run_ibci(code) == ["1"]

    def test_param_dict_mutation_affects_caller(self):
        code = """\
func add_key(dict d) -> int:
    d["k"] = 1
    return d.len()
dict m = {}
add_key(m)
print((str)m.len())
"""
        assert run_ibci(code) == ["1"]

    def test_param_rebind_does_not_affect_caller(self):
        code = """\
func rebind(list b) -> int:
    b = [9]
    return b.len()
list buf = [1, 2]
rebind(buf)
print((str)buf.len())
"""
        assert run_ibci(code) == ["2"]


class TestImmutablePrimitivesIndependent:
    """不可变原语赋值互不影响（值语义等价，无就地修改）。"""

    def test_int_assignment_independent(self):
        code = """\
int a = 1
int b = a
b = 2
print((str)a)
print((str)b)
"""
        assert run_ibci(code) == ["1", "2"]

    def test_str_assignment_independent(self):
        code = """\
str s1 = "x"
str s2 = s1
s2 = "y"
print(s1)
print(s2)
"""
        assert run_ibci(code) == ["x", "y"]


class TestIsVsEquality:
    """is = 恒身份比较；== 标量按值、容器默认按身份（未覆写 __eq__）。"""

    def test_alias_is_same_object(self):
        code = """\
list a = [1, 2]
list b = a
print((str)(a is b))
print((str)(a == b))
"""
        assert run_ibci(code) == ["True", "True"]

    def test_scalar_eq_is_value(self):
        code = """\
int a = 1
int b = 1
print((str)(a == b))
str s1 = "x"
str s2 = "x"
print((str)(s1 == s2))
"""
        assert run_ibci(code) == ["True", "True"]

    def test_container_eq_defaults_identity(self):
        """独立副本：is 为假，容器 == 亦为假（身份比较，非 Python 逐元素）。"""
        code = """\
list a = [1, 2]
list c = copy(a)
print((str)(a is c))
print((str)(a == c))
"""
        assert run_ibci(code) == ["False", "False"]
