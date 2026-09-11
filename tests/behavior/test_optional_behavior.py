"""语言行为层：统一 Optional 值模型（R3-C6 迁移——原 test_optional_value_model.py，
run+print 可观察面直接升格行为层）。

**打破清单 #2 裁决（2026-09-11）**：Optional 空值 = **None 值语义统一**——空
Optional = 同一空值（Rust 内核权威行为）；`a is b`（两空 Optional）= **True**
（原 Python 包装实例身份 = False——"Python 包装值模型"气味，废弃）。
`is` 对空 Optional = None 语义检测（与 None is None 一致）。optional_instance_
identity 角移除（Rust 处理）。

**契约面**：空 Optional 恒 is None / is_none()=True（任何创建路径：局部/参数/
返回/类字段/容器元素）；`== None` 对齐；unwrap 非空可解；容器委托（len/下标/
迭代/方法）；空容器操作 fail-fast（可捕获）。
"""

from tests.behavior.helpers import assert_output


class TestNoneSemantics:
    def test_optional_empty_is_none_local(self):
        assert_output(
            "Optional[int] a = None\n"
            "print(a is None)\n"
            "print(a is not None)\n"
            "print(a.is_none())\n"
            "print(a.is_some())\n",
            ["True", "False", "True", "False"],
        )

    def test_optional_some_is_none_false(self):
        assert_output(
            "Optional[int] b = 5\n"
            "print(b is None)\n"
            "print(b.is_none())\n"
            "print(b == 5)\n",
            ["False", "False", "True"],
        )

    def test_any_none_unaffected(self):
        assert_output(
            "any c = None\nprint(c is None)\nprint(c == None)\n",
            ["True", "True"],
        )

    def test_optional_param_is_none(self):
        assert_output(
            "func f(Optional[int] p) -> bool:\n    return p is None\n"
            "func g(Optional[int] p) -> bool:\n    return p.is_none()\n"
            "func h(Optional[int] p) -> int:\n    return p.unwrap()\n"
            "print(f(None))\nprint(f(5))\nprint(g(None))\nprint(g(5))\nprint(h(7))\n",
            ["True", "False", "True", "False", "7"],
        )

    def test_none_is_literal_and_identity_preserved(self):
        """is None 对字面量 None 作 None 语义检测；空 Optional = 同一空值。"""
        assert_output(
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
            "print(None is not None)\n",
            ["True", "True", "False", "False", "True", "False", "True", "True", "False"],
        )

    def test_none_eq_empty_optional_symmetric(self):
        assert_output(
            "Optional[int] a = None\n"
            "print(a == None)\n"
            "print(None == a)\n"
            "print(a == a)\n",
            ["True", "True", "True"],
        )

    def test_optional_is_identity_between_optionals(self):
        """空 Optional 之间 is = 值语义（同一空值——打破清单 #2 统一）。"""
        assert_output(
            "Optional[int] a = None\n"
            "Optional[int] b = None\n"
            "print(a is b)\n"
            "print(a is not b)\n"
            "print(a is a)\n"
            "print(a is None)\n"
            "print(a is not None)\n",
            ["True", "False", "True", "True", "False"],
        )

    def test_nested_optional_is_none(self):
        assert_output(
            "Optional[Optional[int]] d = None\n"
            "print(d is None)\n"
            "print(d.is_none())\n"
            "print(type(d))\n",
            ["True", "True", "Optional[Optional[int]]"],
        )


class TestFieldAndContainerWrapping:
    def test_optional_field_wrapped(self):
        assert_output(
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
            "print(b2.field.unwrap())\n",
            ["True", "True", "Optional[int]", "True", "True", "False", "7"],
        )

    def test_optional_field_no_default_value(self):
        assert_output(
            "class Box:\n"
            "    Optional[int] field\n"
            "    func __init__(self, Optional[int] field) -> auto:\n"
            "        self.field = field\n"
            "Box b = Box(None)\n"
            "print(b.field is None)\n"
            "print(b.field.is_none())\n",
            ["True", "True"],
        )

    def test_optional_field_reassign_after_construction(self):
        assert_output(
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
            "print(b.field.is_none())\n",
            ["True", "True", "True", "False"],
        )

    def test_optional_container_element_wrapped(self):
        assert_output(
            "list[Optional[int]] items = [None, 5]\n"
            "print(items[0] is None)\n"
            "print(items[0].is_none())\n"
            "print(items[1] is None)\n"
            "print(items[1].is_none())\n"
            "print(items[1] == 5)\n"
            "items[0] = None\n"
            "print(items[0].is_none())\n",
            ["True", "True", "False", "False", "True", "True"],
        )

    def test_optional_dict_value_setitem_wrapped(self):
        assert_output(
            'dict[str, Optional[int]] di = {"a": None}\n'
            'di["c"] = None\n'
            'print(type(di["c"]))\n'
            'print(di["c"].is_none())\n'
            'di["d"] = 5\n'
            'print(di["d"].is_none())\n'
            'print(di["d"] == 5)\n',
            ["Optional[int]", "True", "False", "True"],
        )

    def test_optional_list_add_mul_elements_wrapped(self):
        assert_output(
            "list[Optional[int]] la = [1]\n"
            "list[Optional[int]] lc = la + [None]\n"
            "print(type(lc[1]))\n"
            "print(lc[1].is_none())\n"
            "list[Optional[int]] lm = la * 2\n"
            "print(type(lm[0]))\n"
            "print(lm[0].is_none())\n",
            ["Optional[int]", "True", "Optional[int]", "False"],
        )

    def test_optional_tuple_elements_wrapped(self):
        assert_output(
            'tuple[Optional[int], str] t = (None, "x")\n'
            "print(t[0] is None)\n"
            "print(t[0].is_none())\n"
            "print(type(t[0]))\n"
            "print(type(t[1]))\n"
            'tuple[Optional[int], str] t2 = (5, "y")\n'
            "print(t2[0].is_none())\n"
            "print(t2[0] == 5)\n",
            ["True", "True", "Optional[int]", "str", "False", "True"],
        )

    def test_optional_return_wrapped(self):
        assert_output(
            "func get_opt() -> Optional[int]:\n"
            "    return None\n"
            "Optional[int] r = get_opt()\n"
            "print(r is None)\n"
            "print(r.is_none())\n",
            ["True", "True"],
        )


class TestFunctionScopeOptional:
    def test_optional_function_local_reassign_unwrap(self):
        assert_output(
            "func work() -> int:\n"
            "    Optional[int] tag = None\n"
            "    tag = 405\n"
            "    return tag.unwrap()\n"
            "print(work())\n",
            ["405"],
        )

    def test_optional_function_local_is_some(self):
        assert_output(
            "func work() -> str:\n"
            "    Optional[int] tag = None\n"
            "    tag = 405\n"
            "    return str(tag.is_some()) + '|' + str(tag.is_none())\n"
            "print(work())\n",
            ["True|False"],
        )

    def test_optional_function_local_empty_is_none(self):
        assert_output(
            "func work() -> str:\n"
            "    Optional[int] tag = None\n"
            "    return str(tag is None) + '|' + str(tag.is_none()) + '|' + str(type(tag))\n"
            "print(work())\n",
            ["True|True|Optional[int]"],
        )

    def test_optional_nested_function_nonlocal_write(self):
        assert_output(
            "func outer() -> int:\n"
            "    Optional[int] x = None\n"
            "    func inner() -> int:\n"
            "        nonlocal x\n"
            "        x = 808\n"
            "        return x.unwrap()\n"
            "    return inner()\n"
            "print(outer())\n",
            ["808"],
        )

    def test_optional_lambda_capture_read(self):
        assert_output(
            "func outer() -> int:\n"
            "    Optional[int] x = 405\n"
            "    fn f = lambda() -> int: x.unwrap()\n"
            "    return f()\n"
            "print(outer())\n",
            ["405"],
        )


class TestContainerDelegation:
    def test_optional_container_len(self):
        assert_output(
            "Optional[list[int]] b = [1, 2, 3]\n"
            "print(b is None)\n"
            "print(len(b))\n",
            ["False", "3"],
        )

    def test_optional_container_subscript(self):
        assert_output(
            "Optional[list[int]] b = [10, 20, 30]\nprint(b[1])\n",
            ["20"],
        )

    def test_optional_container_iterate(self):
        assert_output(
            "Optional[list[int]] b = [1, 2, 3]\n"
            "total = 0\n"
            "for v in b:\n"
            "    total = total + v\n"
            "print(total)\n",
            ["6"],
        )

    def test_optional_container_method_call(self):
        assert_output(
            "Optional[list[int]] b = [1, 2, 3]\nprint(len(b.to_list()))\n",
            ["3"],
        )

    def test_optional_empty_container_op_fails(self):
        assert_output(
            "Optional[list[int]] b = None\n"
            "try:\n"
            "    print(len(b))\n"
            "except Exception as e:\n"
            "    print('caught')\n",
            ["caught"],
        )

    def test_optional_optional_methods_still_work_on_empty(self):
        assert_output(
            "Optional[int] a = None\n"
            "print(a.is_some())\n"
            "print(a.is_none())\n"
            "print(a.or_else(99))\n",
            ["False", "True", "99"],
        )


class TestDeepClone:
    def test_deepcopy_preserves_optional_state(self):
        """deepcopy 对 Optional 保留空/非空状态（可观察：is_none 不变）。"""
        assert_output(
            "Optional[int] a = None\n"
            "Optional[int] b = 5\n"
            "Optional[int] ac = deepcopy(a)\n"
            "Optional[int] bc = deepcopy(b)\n"
            "print(ac.is_none())\n"
            "print(ac.is_some())\n"
            "print(bc.is_none())\n"
            "print(bc.unwrap())\n",
            ["True", "False", "False", "5"],
        )
