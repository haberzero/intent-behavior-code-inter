"""
tests/runtime/test_optional_value_model.py
==========================================

统一 Optional 值模型判别性回归（KI-2 根治）。

锁定语义：
- ``Optional[T]`` 空值恒为 ``IbOptional(is_some=False)`` 包装（任何值创建
  路径：局部变量 / 函数参数 / 返回 / 类字段 / 容器元素），不产生裸 ``IbNone``。
- ``is None`` / ``is not None`` 对空 ``Optional`` 返回 True/False（与
  ``== None`` 对齐），``is_none()`` 方法可用。
- 字段 / 容器元素上的 ``is_none()``/``is_some()``/``unwrap()`` 可用
  （修复前裸存路径抛错）。
"""
from tests.conftest import run_ibci


def test_optional_empty_is_none_local():
    """局部变量空 Optional：is None / is_none() / is_some() 对齐。"""
    code = (
        "Optional[int] a = None\n"
        "print(a is None)\n"
        "print(a is not None)\n"
        "print(a.is_none())\n"
        "print(a.is_some())\n"
    )
    assert run_ibci(code) == ["True", "False", "True", "False"]


def test_optional_some_is_none_false():
    """非空 Optional：is None / is_none() 为 False。"""
    code = (
        "Optional[int] b = 5\n"
        "print(b is None)\n"
        "print(b.is_none())\n"
        "print(b == 5)\n"
    )
    assert run_ibci(code) == ["False", "False", "True"]


def test_any_none_unaffected():
    """any 变量 None 保持裸 IbNone：is None 仍 True（不回归）。"""
    code = (
        "any c = None\n"
        "print(c is None)\n"
        "print(c == None)\n"
    )
    assert run_ibci(code) == ["True", "True"]


def test_optional_param_is_none():
    """函数参数 Optional[T] 空值：is None / is_none() 可用（修复前裸存）。"""
    code = (
        "func f(Optional[int] p) -> bool:\n"
        "    return p is None\n"
        "func g(Optional[int] p) -> bool:\n"
        "    return p.is_none()\n"
        "func h(Optional[int] p) -> int:\n"
        "    return p.unwrap()\n"
        "print(f(None))\n"
        "print(f(5))\n"
        "print(g(None))\n"
        "print(g(5))\n"
        "print(h(7))\n"
    )
    assert run_ibci(code) == ["True", "False", "True", "False", "7"]


def test_optional_field_wrapped():
    """类字段 Optional[T] 空值：is_none()/is_some()/type() 对齐（修复前裸存）。"""
    code = (
        "class Box:\n"
        "    Optional[int] field\n"
        "    func __init__(self, Optional[int] field) -> auto:\n"
        "        self.field = field\n"
        "Box b = Box(None)\n"
        "print(b.field is None)\n"
        "print(b.field == None)\n"
        "print(type(b.field))\n"
        "print(b.field.is_none())\n"
        "Box b2 = Box(7)\n"
        "print(b2.field == 7)\n"
        "print(b2.field.is_none())\n"
        "print(b2.field.unwrap())\n"
    )
    assert run_ibci(code) == [
        "True", "True", "Optional[int]", "True",
        "True", "False", "7",
    ]


def test_optional_field_no_default_value():
    """无默认值的 Optional 字段（缺省置空）也应包装（修复前裸存）。"""
    code = (
        "class Box:\n"
        "    Optional[int] field\n"
        "    func __init__(self, Optional[int] field) -> auto:\n"
        "        self.field = field\n"
        "Box b = Box(None)\n"
        "print(b.field is None)\n"
        "print(b.field.is_none())\n"
    )
    assert run_ibci(code) == ["True", "True"]


def test_optional_container_element_wrapped():
    """list[Optional[T]] 元素空值：is None / is_none() 可用（修复前裸存）。"""
    code = (
        "list[Optional[int]] items = [None, 5]\n"
        "print(items[0] is None)\n"
        "print(items[0].is_none())\n"
        "print(items[1] is None)\n"
        "print(items[1].is_none())\n"
        "print(items[1] == 5)\n"
        "items[0] = None\n"
        "print(items[0].is_none())\n"
    )
    assert run_ibci(code) == [
        "True", "True", "False", "False", "True", "True",
    ]


def test_optional_field_reassign_after_construction():
    """字段 Optional 重赋值（None→值 / 值→None）经 __setattr__ 包装。"""
    code = (
        "class Box:\n"
        "    Optional[int] field\n"
        "    func __init__(self, Optional[int] field) -> auto:\n"
        "        self.field = field\n"
        "Box b = Box(3)\n"
        "b.field = None\n"
        "print(b.field is None)\n"
        "print(b.field.is_none())\n"
        "b.field = 9\n"
        "print(b.field == 9)\n"
        "print(b.field.is_none())\n"
    )
    assert run_ibci(code) == ["True", "True", "True", "False"]


def test_none_is_literal_and_identity_preserved():
    """is None 对字面量 None 作 None 语义检测（双向）；空 Optional 之间仍恒等。

    ``a is None`` / ``None is a``（任一侧为字面量 None）→ True（None 语义检测）；
    ``a is b``（两个不同空 Optional 实例）→ False（保持恒等，实例身份不被
    None 语义放宽吞并）。
    """
    code = (
        "Optional[int] a = None\n"
        "Optional[int] b = None\n"
        "print(a is None)\n"
        "print(None is a)\n"
        "print(a is not None)\n"
        "print(None is not a)\n"
        "print(a is b)\n"
        "print(a is not b)\n"
        "print(a is a)\n"
        "print(None is None)\n"
        "print(None is not None)\n"
    )
    assert run_ibci(code) == [
        "True", "True", "False", "False", "False", "True", "True", "True", "False",
    ]


def test_none_eq_empty_optional_symmetric():
    """None == 空 Optional 对称（修复前 None == x 为 False）。"""
    code = (
        "Optional[int] x = None\n"
        "print(x == None)\n"
        "print(None == x)\n"
        "print(x != None)\n"
        "print(None != x)\n"
        "Optional[int] y = 5\n"
        "print(None == y)\n"
        "print(None != y)\n"
    )
    assert run_ibci(code) == ["True", "True", "False", "False", "False", "True"]


def test_nested_optional_is_none():
    """Optional[Optional[int]] 空值 is None / is_none()（统一包装不双重）。"""
    code = (
        "Optional[Optional[int]] d = None\n"
        "print(d is None)\n"
        "print(d.is_none())\n"
        "print(type(d))\n"
    )
    assert run_ibci(code) == ["True", "True", "Optional[Optional[int]]"]


def test_deep_clone_preserves_optional_is_some():
    """try_deep_clone 对 IbOptional 保留 _is_some（修复前 slot 未初始化）。"""
    from core.engine import IBCIEngine
    from core.runtime.objects.deep_clone import try_deep_clone

    engine = IBCIEngine(root_dir="/tmp/opencode", auto_sniff=False)
    engine.run_string("Optional[int] a = None\nOptional[int] b = 5\n", silent=True)
    ec = engine.interpreter.execution_context
    rc = ec.runtime_context
    a = rc.get_variable("a")
    b = rc.get_variable("b")

    a_clone = try_deep_clone(a)
    assert a_clone is not None
    assert a_clone.is_none().to_native() is True
    assert a_clone.is_some().to_native() is False

    b_clone = try_deep_clone(b)
    assert b_clone is not None
    assert b_clone.is_none().to_native() is False
    assert b_clone.unwrap().to_native() == 5


def test_optional_return_wrapped():
    """函数返回 Optional[T] 空值经返回值绑定包装（is_none 可用）。"""
    code = (
        "func get_opt() -> Optional[int]:\n"
        "    return None\n"
        "Optional[int] r = get_opt()\n"
        "print(r is None)\n"
        "print(r.is_none())\n"
    )
    assert run_ibci(code) == ["True", "True"]


def test_optional_dict_value_setitem_wrapped():
    """dict[str, Optional[int]] 值写入（setitem）按 value_type 包装。

    复核修正：dict spec 的 element_type 恒为 TypeRef("any") 遮蔽 value_type，
    修复前 setitem/update 裸存 None（_element_spec_for 按 kind 分派前）。
    """
    code = (
        "dict[str, Optional[int]] di = {\"a\": None}\n"
        "di[\"c\"] = None\n"
        "print(type(di[\"c\"]))\n"
        "print(di[\"c\"].is_none())\n"
        "di[\"d\"] = 5\n"
        "print(di[\"d\"].is_none())\n"
        "print(di[\"d\"] == 5)\n"
    )
    assert run_ibci(code) == ["Optional[int]", "True", "False", "True"]


def test_optional_is_identity_preserved_between_optionals():
    """空 Optional 之间 is 保持实例恒等（非 None 语义放宽吞并）。"""
    code = (
        "Optional[int] a = None\n"
        "Optional[int] b = None\n"
        "print(a is b)\n"
        "print(a is not b)\n"
        "print(a is a)\n"
        "print(a is None)\n"
        "print(a is not None)\n"
    )
    assert run_ibci(code) == ["False", "True", "True", "True", "False"]


def test_optional_list_add_mul_elements_wrapped():
    """list[Optional[int]] 拼接/重复产物元素保持 IbOptional 包装。

    复核修正：__add__/__mul__ 产物元素未按元素类型规范化，修复前
    ``la + [None]`` 的元素为裸 IbNone。
    """
    code = (
        "list[Optional[int]] la = [1]\n"
        "list[Optional[int]] lc = la + [None]\n"
        "print(type(lc[1]))\n"
        "print(lc[1].is_none())\n"
        "list[Optional[int]] lm = la * 2\n"
        "print(type(lm[0]))\n"
        "print(lm[0].is_none())\n"
    )
    assert run_ibci(code) == ["Optional[int]", "True", "Optional[int]", "False"]


def test_optional_tuple_elements_wrapped():
    """tuple[Optional[T], ...] 位置元素按声明类型包装。

    复核修正：tuple 不可变（elements 为只读 tuple），原地写元素抛 TypeError
    被 except 吞掉 → 元素裸存。改为重建 tuple 后元素保持 IbOptional。
    """
    code = (
        'tuple[Optional[int], str] t = (None, "x")\n'
        "print(t[0] is None)\n"
        "print(t[0].is_none())\n"
        "print(type(t[0]))\n"
        "print(type(t[1]))\n"
        "tuple[Optional[int], str] t2 = (5, \"y\")\n"
        "print(t2[0].is_none())\n"
        "print(t2[0] == 5)\n"
    )
    assert run_ibci(code) == [
        "True", "True", "Optional[int]", "str", "False", "True",
    ]


# ---------------------------------------------------------------------------
# 函数作用域 Optional 值模型（判别性回归）
# ---------------------------------------------------------------------------

def test_optional_function_local_reassign_unwrap():
    """函数内 Optional 先 None 后赋值，unwrap() 可用（与顶层/lambda/参数
    路径一致——函数普通作用域路径同样返回包装值）。"""
    code = """
func work() -> int:
    Optional[int] tag = None
    tag = 405
    return tag.unwrap()
print(work())
"""
    assert run_ibci(code) == ["405"]


def test_optional_function_local_is_some():
    """函数内 Optional 先 None 后赋值，is_some()/is_none() 可用。"""
    code = """
func work() -> str:
    Optional[int] tag = None
    tag = 405
    return str(tag.is_some()) + "|" + str(tag.is_none())
print(work())
"""
    assert run_ibci(code) == ["True|False"]


def test_optional_function_local_empty_is_none():
    """函数内 Optional 空值保持包装（is None / is_none() 对齐顶层）。"""
    code = """
func work() -> str:
    Optional[int] tag = None
    return str(tag is None) + "|" + str(tag.is_none()) + "|" + str(type(tag))
print(work())
"""
    assert run_ibci(code) == ["True|True|Optional[int]"]


def test_optional_function_local_init_wrapped():
    """函数内 Optional 初始化即包装（type()=Optional[int]）。"""
    code = """
func work() -> str:
    Optional[int] tag = None
    return str(type(tag))
print(work())
"""
    assert run_ibci(code) == ["Optional[int]"]


def test_optional_class_method_local():
    """类方法内 Optional 局部变量（类方法体同样走函数局部路径）。"""
    code = """
class Counter:
    int base
    func __init__(self, int base) -> auto:
        self.base = base
    func compute(self) -> int:
        Optional[int] tag = None
        tag = self.base + 1
        return tag.unwrap()
Counter c = Counter(10)
print(c.compute())
"""
    assert run_ibci(code) == ["11"]


def test_optional_nested_function_nonlocal_write():
    """嵌套函数 nonlocal 写外层 Optional：包装保留（cell 写路径同族修复）。"""
    code = """
func outer() -> int:
    Optional[int] x = None
    func inner() -> int:
        nonlocal x
        x = 808
        return x.unwrap()
    return inner()
print(outer())
"""
    assert run_ibci(code) == ["808"]


def test_optional_lambda_capture_read():
    """lambda 捕获外层 Optional：读取路径包装保留。"""
    code = """
func outer() -> int:
    Optional[int] x = 405
    fn f = lambda() -> int: x.unwrap()
    return f()
print(outer())
"""
    assert run_ibci(code) == ["405"]


# ---------------------------------------------------------------------------
# Optional 容器方法委托（判别性回归）
# ---------------------------------------------------------------------------

def test_optional_container_len():
    """Optional[list[int]] 有值包装 len() 可用（委托内层容器）。"""
    code = """
Optional[list[int]] b = [1, 2, 3]
print(b is None)
print(len(b))
"""
    assert run_ibci(code) == ["False", "3"]


def test_optional_container_subscript():
    """Optional[list[int]] 有值包装下标访问可用。"""
    code = """
Optional[list[int]] b = [10, 20, 30]
print(b[1])
"""
    assert run_ibci(code) == ["20"]


def test_optional_container_iterate():
    """Optional[list[int]] 有值包装可 for 迭代（resolve_iterable 委托）。"""
    code = """
Optional[list[int]] b = [1, 2, 3]
total = 0
for v in b:
    total = total + v
print(total)
"""
    assert run_ibci(code) == ["6"]


def test_optional_container_method_call():
    """Optional[list[int]] 有值包装容器方法调用（to_list 属性路径）。"""
    code = """
Optional[list[int]] b = [1, 2, 3]
print(len(b.to_list()))
"""
    assert run_ibci(code) == ["3"]


def test_optional_empty_container_op_fails():
    """空 Optional 上容器操作 fail-fast（明确报错，不静默）。"""
    code = """
Optional[list[int]] b = None
try:
    print(len(b))
except Exception as e:
    print("caught")
"""
    assert run_ibci(code) == ["caught"]


def test_optional_optional_methods_still_work_on_empty():
    """空 Optional 专属方法（is_some/is_none/unwrap/or_else）保持可用。"""
    code = """
Optional[int] a = None
print(a.is_some())
print(a.is_none())
print(a.or_else(99))
"""
    assert run_ibci(code) == ["False", "True", "99"]
