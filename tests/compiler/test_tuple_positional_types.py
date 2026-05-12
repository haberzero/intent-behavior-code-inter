"""
tests/compiler/test_tuple_positional_types.py
==============================================

NS-7 元组的位置元素类型标注 (`tuple[T1, T2, ...]`)。

覆盖：
1. 编译期：字面量 int 下标的精确位置类型推断；
2. 编译期：错误的目标类型触发 SEM_003；
3. 回退：变量索引或越界回退到 ``any``，不报错；
4. 兼容性：``tuple[A, B]`` 可赋值给裸 ``tuple``；
5. 顺序敏感：``tuple[int, str]`` 与 ``tuple[str, int]`` 是不同类型；
6. 单类型保持向后兼容：``tuple[T]`` 仍走 ``element_type`` 单字段路径。
"""

import pytest

from core.engine import IBCIEngine


ROOT_DIR = "."


def _run(code: str):
    engine = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
    out = []
    engine.run_string(code, output_callback=lambda t: out.append(str(t)), silent=True)
    return out


def _run_expect_compile_error(code: str):
    engine = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
    from core.kernel.issue import CompilerError
    with pytest.raises(CompilerError):
        engine.run_string(code, output_callback=lambda t: None, silent=True)


# ===========================================================================
# 1. 位置元素类型精确推断
# ===========================================================================

class TestTuplePositionalTypeInference:
    def test_int_str_literal_index(self):
        """`tuple[int, str] t = (1, "x"); int a = t[0]; str b = t[1]` 应通过类型检查。"""
        out = _run("""
tuple[int, str] t = (1, "hello")
int a = t[0]
str b = t[1]
print(a)
print(b)
""")
        assert out == ["1", "hello"]

    def test_three_elements_positional(self):
        """三元位置类型 `tuple[int, str, bool]`。"""
        out = _run("""
tuple[int, str, bool] t = (7, "z", True)
int a = t[0]
str b = t[1]
bool c = t[2]
print(a)
print(b)
print(c)
""")
        assert out == ["7", "z", "True"]


# ===========================================================================
# 2. 错误目标类型应触发 SEM_003
# ===========================================================================

class TestTuplePositionalTypeMismatch:
    def test_wrong_target_type_position_0(self):
        """位置 0 是 int，赋给 str 应报错。"""
        _run_expect_compile_error("""
tuple[int, str] t = (1, "hello")
str bad = t[0]
""")

    def test_wrong_target_type_position_1(self):
        """位置 1 是 str，赋给 int 应报错。"""
        _run_expect_compile_error("""
tuple[int, str] t = (1, "hello")
int bad = t[1]
""")


# ===========================================================================
# 3. 非字面量索引/越界 fallback 到 any（不报错）
# ===========================================================================

class TestTuplePositionalFallback:
    def test_variable_index_falls_back_to_any(self):
        """变量索引时回退到通用 fallback 路径。"""
        out = _run("""
tuple[int, str] t = (1, "hello")
int i = 0
any x = t[i]
print(x)
""")
        assert out == ["1"]


# ===========================================================================
# 4. tuple[A, B] 可赋值给裸 tuple
# ===========================================================================

class TestTupleCovariance:
    def test_assign_positional_to_plain_tuple(self):
        """tuple[int, str] → tuple 兼容（已实现的 is_compatible）。"""
        out = _run("""
tuple[int, str] t = (1, "x")
tuple plain = t
print(plain[0])
print(plain[1])
""")
        assert out == ["1", "x"]


# ===========================================================================
# 5. 顺序敏感：tuple[int, str] ≠ tuple[str, int]
# ===========================================================================

class TestTupleOrderSensitivity:
    def test_order_discriminates_specs(self):
        """`tuple[int, str]` 与 `tuple[str, int]` 必须是不同的位置类型。"""
        out = _run("""
tuple[int, str] t1 = (1, "x")
tuple[str, int] t2 = ("y", 2)
int a = t1[0]
str b = t1[1]
str c = t2[0]
int d = t2[1]
print(a)
print(b)
print(c)
print(d)
""")
        assert out == ["1", "x", "y", "2"]

    def test_order_swap_target_type_mismatch(self):
        """对 `tuple[str, int]` 用 int 接 [0] 应失败（验证不被 sorted 缓存污染）。"""
        _run_expect_compile_error("""
tuple[str, int] t = ("y", 2)
int bad = t[0]
""")


# ===========================================================================
# 6. 单类型回退路径保留
# ===========================================================================

class TestTupleSingleTypeBackCompat:
    def test_single_element_type_path(self):
        """`tuple[int]` 走 element_type 单字段路径（不创建 positional_element_types）。"""
        out = _run("""
tuple[int] t = (42,)
int a = t[0]
print(a)
""")
        assert out == ["42"]


# ===========================================================================
# 7. SpecFactory.create_tuple 直接 API 测试
# ===========================================================================

class TestSpecFactoryCreateTuple:
    def test_create_tuple_with_positional_types(self):
        """factory.create_tuple(positional_element_type_names=[...]) 生成位置类型 spec。"""
        from core.kernel.spec.registry import SpecFactory
        from core.kernel.spec.base import TypeKind

        factory = SpecFactory()
        spec = factory.create_tuple(positional_element_type_names=["int", "str"])
        assert spec.kind == TypeKind.TUPLE.value
        assert spec.name == "tuple[int,str]"
        assert len(spec.positional_element_types) == 2
        assert spec.positional_element_types[0].head == "int"
        assert spec.positional_element_types[1].head == "str"

    def test_create_tuple_order_preserved_in_name(self):
        """位置元素的顺序必须体现在 spec.name 中（不要 sort）。"""
        from core.kernel.spec.registry import SpecFactory

        factory = SpecFactory()
        s1 = factory.create_tuple(positional_element_type_names=["int", "str"])
        s2 = factory.create_tuple(positional_element_type_names=["str", "int"])
        assert s1.name != s2.name
        assert s1.name == "tuple[int,str]"
        assert s2.name == "tuple[str,int]"

    def test_create_tuple_single_falls_back_to_element_type(self):
        """单元素时退回 element_type 单字段，不填 positional_element_types。"""
        from core.kernel.spec.registry import SpecFactory

        factory = SpecFactory()
        spec = factory.create_tuple(element_type_name="int")
        assert spec.name == "tuple[int]"
        assert spec.element_type.head == "int"
        assert spec.positional_element_types == []
