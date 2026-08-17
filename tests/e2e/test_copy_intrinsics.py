"""
tests/e2e/test_copy_intrinsics.py — copy/deepcopy 内建契约（独立候选处置）。

- copy(x) 浅拷贝：容器新建 + 元素引用共享（修改副本不影响原容器）；
- deepcopy(x) 深拷贝：递归独立副本（嵌套容器/用户对象字段独立）；
- 不可克隆值（函数/行为）回退原引用（deep_clone 契约）。
"""

import os

from core.engine import IBCIEngine

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _engine():
    return IBCIEngine(root_dir=_ROOT)


def _run(engine, code):
    out = []
    engine.run_string(code, output_callback=lambda t: out.append(str(t)), silent=True)
    return out


class TestCopyIntrinsics:
    def test_copy_shallow_container_independent(self):
        """copy(list)：容器独立，append 不影响原列表。"""
        engine = _engine()
        out = _run(engine, """
list a = [1, 2, 3]
list b = copy(a)
b.append(4)
print(a.len())
print(b.len())
""")
        assert out == ["3", "4"]

    def test_copy_shallow_nested_shared(self):
        """copy 嵌套容器元素仍共享（浅拷贝语义）。"""
        engine = _engine()
        out = _run(engine, """
list inner = [1]
list a = [inner]
list b = copy(a)
inner.append(2)
print(a[0].len())
print(b[0].len())
""")
        # 浅拷贝：a[0] 与 b[0] 共享同一内层 list
        assert out == ["2", "2"]

    def test_deepcopy_nested_independent(self):
        """deepcopy：嵌套容器独立副本。"""
        engine = _engine()
        out = _run(engine, """
list inner = [1]
list a = [inner]
list c = deepcopy(a)
inner.append(2)
print(a[0].len())
print(c[0].len())
""")
        assert out == ["2", "1"]

    def test_deepcopy_user_object_fields(self):
        """deepcopy：用户对象字段独立副本。"""
        engine = _engine()
        out = _run(engine, """
class Holder:
    list items
    func __init__(self) -> auto:
        self.items = [1]

Holder h = Holder()
Holder h2 = deepcopy(h)
h.items.append(2)
print(h.items.len())
print(h2.items.len())
""")
        assert out == ["2", "1"]

    def test_copy_dict_independent(self):
        """copy(dict)：字典新建（写不影响原字典）。"""
        engine = _engine()
        out = _run(engine, """
dict d = {"a": 1}
dict d2 = copy(d)
d2["b"] = 2
print(d.len())
print(d2.len())
""")
        assert out == ["1", "2"]

    def test_immutable_copy_identity(self):
        """不可变值 copy 返回原值（值语义等价）。"""
        engine = _engine()
        out = _run(engine, """
int x = 5
int y = copy(x)
print(y)
""")
        assert out == ["5"]
