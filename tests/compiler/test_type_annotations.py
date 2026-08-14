"""
tests/compiler/test_type_annotations.py — 类型标注编译期契约（compile-only）。

编译期语义：

* Optional[T] 类型方法解析与编译期语义
* Optional[T] 空安全编译期校验
* ``fn[(in)->(out)]`` callable 签名
* SpecFactory.create_tuple 直接 API
* Optional[T] / thread artifact 还原（从序列化产物恢复类型 spec）

运行时执行用例见 tests/e2e/test_type_annotations_runtime.py（mixed-concerns 拆分）。
"""
import pytest

from core.kernel.factory import create_default_registry
from core.kernel.spec.base import TypeKind
from core.kernel.spec.registry import SpecFactory
from core.kernel.spec.specs import TypeDef
from core.runtime.loader.artifact_rehydrator import ArtifactRehydrator
from tests.conftest import compile_or_errors


# ---------------------------------------------------------------------------
# 共享 helper（compile-only；基于 conftest 黑盒 compile_or_errors）
# ---------------------------------------------------------------------------

def assert_compiles(code: str):
    artifact, errors = compile_or_errors(code)
    assert artifact is not None
    assert not errors, f"Expected no compiler errors, got: {errors}"


def assert_has_sem003(code: str):
    _, errors = compile_or_errors(code)
    assert "SEM_TYPE_MISMATCH" in errors, f"Expected SEM_TYPE_MISMATCH, got: {errors}"


def assert_error_codes(code: str, *expected_codes: str):
    _, errors = compile_or_errors(code)
    for code_val in expected_codes:
        assert code_val in errors, f"Expected error {code_val!r} but got: {errors}"


################################################################################
# Optional[T] 类型方法解析 + 编译期语义
################################################################################

class TestOptionalMethodResolution:
    def test_unwrap_return_type_is_wrapped_type(self):
        reg = create_default_registry()
        optional_int = reg.resolve_specialization(reg.resolve("Optional"), [reg.resolve("int")])
        unwrap_spec = reg.resolve_member(optional_int, "unwrap")
        assert unwrap_spec is not None
        assert unwrap_spec.return_type.head == "int"

    def test_or_else_signature_is_specialized(self):
        reg = create_default_registry()
        optional_int = reg.resolve_specialization(reg.resolve("Optional"), [reg.resolve("int")])
        or_else_spec = reg.resolve_member(optional_int, "or_else")
        assert or_else_spec is not None
        assert or_else_spec.return_type.head == "int"
        assert [t.head for t in or_else_spec.param_types] == ["int"]


class TestOptionalMethodCompileSemantics:
    @pytest.mark.parametrize("code", [
        pytest.param(
            "Optional[int] x = None\n"
            "int y = x.or_else(3)\n",
            id="or_else_allows_unwrap_to_plain_type",
        ),
        pytest.param(
            "Optional[int] x = 1\n"
            "int y = x.unwrap()\n",
            id="unwrap_allows_assign_to_plain_type",
        ),
    ])
    def test_optional_method_allows_plain_assignment(self, code):
        assert_compiles(code)


################################################################################
# Optional[T] 空安全编译期校验
################################################################################

class TestOptionalNullSafety:
    @pytest.mark.parametrize("code", [
        pytest.param(
            "Optional[int] x = None\n"
            "Optional[int] y = x\n",
            id="optional_int_accepts_none",
        ),
        pytest.param(
            "Optional[int] x = 1\n"
            "Optional[int] y = x\n",
            id="optional_int_accepts_int",
        ),
    ])
    def test_optional_int_accepts_value(self, code):
        assert_compiles(code)

    def test_plain_int_rejects_none(self):
        assert_has_sem003("int x = None\n")

    def test_plain_int_rejects_optional_int(self):
        assert_has_sem003(
            "Optional[int] x = 1\n"
            "int y = x\n"
        )


################################################################################
# callable 签名 fn[(in)->(out)]
################################################################################

class TestCallableSigParse:
    """Parser accepts fn[(...)→(...)] in type-annotation positions."""

    @pytest.mark.parametrize("code", [
        pytest.param(
            "func apply(fn[() -> int] f) -> int:\n"
            "    return f()\n",
            id="no_params_int_return",
        ),
        pytest.param(
            "func apply(fn[(int) -> int] f, int x) -> int:\n"
            "    return f(x)\n",
            id="single_param",
        ),
        pytest.param(
            "func check(fn[(int, str) -> bool] predicate, int n, str s) -> bool:\n"
            "    return predicate(n, s)\n",
            id="multi_param",
        ),
        pytest.param(
            "func add_one(int n) -> int:\n"
            "    return n + 1\n"
            "\n"
            "fn[(int) -> int] f = add_one\n",
            id="as_variable_declaration_type",
        ),
        pytest.param(
            "func make_adder(int n) -> fn[(int) -> int]:\n"
            "    fn add = lambda(int x) -> auto: n + x\n"
            "    return add\n",
            id="as_return_type_annotation",
        ),
        pytest.param(
            "func double(int n) -> int:\n"
            "    return n * 2\n"
            "\n"
            "fn f = double\n"
            "print((str)f(3))\n",
            id="bare_fn_still_works",
        ),
    ])
    def test_fn_signature_annotation_compiles(self, code):
        assert_compiles(code)


# ─────────────────────────────────────────────────────── call-site checks ──

class TestCallableSigCallSite:
    """Calling a fn[(...)→(...)] parameter: arg-count and type checks."""

    def test_correct_call_no_error(self):
        """Calling fn[(int) -> int] with correct arg type produces no error."""
        assert_compiles("""
func apply(fn[(int) -> int] f, int x) -> int:
    return f(x)
""")

    def test_too_many_args(self):
        """Calling fn[(int) -> int] with 2 args → SEM_ARG_COUNT_MISMATCH."""
        assert_error_codes("""
func apply(fn[(int) -> int] f, int x, int y) -> int:
    return f(x, y)
""", "SEM_ARG_COUNT_MISMATCH")

    def test_too_few_args(self):
        """Calling fn[(int, str) -> bool] with 1 arg → SEM_ARG_COUNT_MISMATCH."""
        assert_error_codes("""
func apply(fn[(int, str) -> bool] pred) -> bool:
    return pred(1)
""", "SEM_ARG_COUNT_MISMATCH")

    def test_wrong_arg_type(self):
        """Calling fn[(int) -> int] with str arg → SEM_TYPE_MISMATCH."""
        assert_error_codes("""
func apply(fn[(int) -> int] f, str s) -> int:
    return f(s)
""", "SEM_TYPE_MISMATCH")


# ──────────────────────────────────────────── declaration-site sig check ──

class TestCallableSigDeclaration:
    """fn[(...)→(...)] variable declaration: structural sig matching on RHS."""

    def test_matching_sig_no_error(self):
        """fn[(int) -> int] f = add_one passes when signatures match."""
        assert_compiles("""
func add_one(int n) -> int:
    return n + 1

fn[(int) -> int] f = add_one
""")

    def test_param_count_mismatch(self):
        """fn[(int, str) -> int] f = add_one (1 param) → SEM_TYPE_MISMATCH."""
        assert_error_codes("""
func add_one(int n) -> int:
    return n + 1

fn[(int, str) -> int] f = add_one
""", "SEM_TYPE_MISMATCH")

    def test_return_type_mismatch(self):
        """fn[(int) -> str] f = add_one (returns int) → SEM_TYPE_MISMATCH."""
        assert_error_codes("""
func add_one(int n) -> int:
    return n + 1

fn[(int) -> str] f = add_one
""", "SEM_TYPE_MISMATCH")


# ────────────────────────────────────────────────────── return type infer ──

class TestCallableSigReturnInference:
    """Return type of calling fn[(...)→T] parameter is inferred as T."""

    @pytest.mark.parametrize("code", [
        pytest.param(
            "func apply(fn[(int) -> int] f, int x) -> int:\n"
            "    int result = f(x)\n"
            "    return result\n",
            id="int_return_inferred",
        ),
        pytest.param(
            "func check(fn[(int, str) -> bool] pred, int n, str s) -> bool:\n"
            "    bool result = pred(n, s)\n"
            "    return result\n",
            id="bool_return_inferred",
        ),
    ])
    def test_call_return_type_inferred(self, code):
        assert_compiles(code)


# ===========================================================================
# 7. SpecFactory.create_tuple 直接 API 测试
# ===========================================================================

class TestSpecFactoryCreateTuple:
    def test_create_tuple_with_positional_types(self):
        """factory.create_tuple(positional_element_type_names=[...]) 生成位置类型 spec。"""
        factory = SpecFactory()
        spec = factory.create_tuple(positional_element_type_names=["int", "str"])
        assert spec.kind == TypeKind.TUPLE.value
        assert spec.name == "tuple[int,str]"
        assert len(spec.positional_element_types) == 2
        assert spec.positional_element_types[0].head == "int"
        assert spec.positional_element_types[1].head == "str"

    def test_create_tuple_order_preserved_in_name(self):
        """位置元素的顺序必须体现在 spec.name 中（不要 sort）。"""
        factory = SpecFactory()
        s1 = factory.create_tuple(positional_element_type_names=["int", "str"])
        s2 = factory.create_tuple(positional_element_type_names=["str", "int"])
        assert s1.name != s2.name
        assert s1.name == "tuple[int,str]"
        assert s2.name == "tuple[str,int]"

    def test_create_tuple_single_falls_back_to_element_type(self):
        """单元素时退回 element_type 单字段，不填 positional_element_types。"""
        factory = SpecFactory()
        spec = factory.create_tuple(element_type_name="int")
        assert spec.name == "tuple[int]"
        assert spec.element_type.head == "int"
        assert spec.positional_element_types == []


################################################################################
# Optional[T] artifact 还原
################################################################################

class TestOptionalArtifactRehydrator:
    def test_unsupported_kind_rejected(self):
        registry = create_default_registry()
        type_pool = {
            "type_root.int": {
                "uid": "type_root.int",
                "kind": "primitive",
                "name": "int",
                "module_path": None,
                "provenance": "KERNEL_NATIVE",
                "visibility": "PRELUDE_VISIBLE",
                "storage_model": "MEMORY_BACKED",
            },
            "type_root.Optional[int]": {
                "uid": "type_root.Optional[int]",
                "kind": "TypeDef",
                "name": "Optional[int]",
                "module_path": None,
                "provenance": "KERNEL_NATIVE",
                "visibility": "PRELUDE_VISIBLE",
                "storage_model": "MEMORY_BACKED",
                "wrapped_type_name": "int",
                "wrapped_type_module": None,
            },
        }

        rehydrator = ArtifactRehydrator(type_pool=type_pool, registry=registry)
        with pytest.raises(ValueError, match="unsupported kind"):
            rehydrator.hydrate("type_root.Optional[int]")

    def test_unsupported_kind_rejected_for_other_invalid_token(self):
        registry = create_default_registry()
        type_pool = {
            "type_root.list[int]": {
                "uid": "type_root.list[int]",
                "kind": "ListMetadata",
                "name": "list[int]",
                "module_path": None,
                "provenance": "KERNEL_NATIVE",
                "visibility": "PRELUDE_VISIBLE",
                "storage_model": "MEMORY_BACKED",
                "element_type_uid": "type_root.int",
            },
            "type_root.int": {
                "uid": "type_root.int",
                "kind": "primitive",
                "name": "int",
                "module_path": None,
                "provenance": "KERNEL_NATIVE",
                "visibility": "PRELUDE_VISIBLE",
                "storage_model": "MEMORY_BACKED",
            },
        }

        rehydrator = ArtifactRehydrator(type_pool=type_pool, registry=registry)
        with pytest.raises(ValueError, match="unsupported kind"):
            rehydrator.hydrate("type_root.list[int]")

    def test_hydrate_optional_specialization_new_kind_protocol(self):
        registry = create_default_registry()
        type_pool = {
            "type_root.int": {
                "uid": "type_root.int",
                "kind": "primitive",
                "name": "int",
                "module_path": None,
                "provenance": "KERNEL_NATIVE",
                "visibility": "PRELUDE_VISIBLE",
                "storage_model": "MEMORY_BACKED",
            },
            "type_root.Optional[int]": {
                "uid": "type_root.Optional[int]",
                "kind": "optional",
                "name": "Optional[int]",
                "module_path": None,
                "provenance": "KERNEL_NATIVE",
                "visibility": "PRELUDE_VISIBLE",
                "storage_model": "MEMORY_BACKED",
                "wrapped_type_name": "int",
                "wrapped_type_module": None,
            },
        }

        rehydrator = ArtifactRehydrator(type_pool=type_pool, registry=registry)
        spec = rehydrator.hydrate("type_root.Optional[int]")

        assert isinstance(spec, TypeDef)
        assert spec.kind == "optional"
        assert spec.wrapped_type.head == "int"


################################################################################
# thread/thread_result artifact 还原
################################################################################

class TestTaskThreadArtifactRehydrator:
    """TASK kind 还原（task 类型已删除）：一律重建 thread，无幽灵 task 回退。"""

    def test_thread_specialization_hydrates(self):
        registry = create_default_registry()
        type_pool = {
            "type_root.thread[int]": {
                "uid": "type_root.thread[int]",
                "kind": "thread",
                "name": "thread[int]",
                "module_path": None,
                "provenance": "KERNEL_NATIVE",
                "visibility": "PRELUDE_VISIBLE",
                "storage_model": "MEMORY_BACKED",
                "value_type_name": "int",
                "value_type_module": None,
            },
        }
        rehydrator = ArtifactRehydrator(type_pool=type_pool, registry=registry)
        spec = rehydrator.hydrate("type_root.thread[int]")
        assert isinstance(spec, TypeDef)
        assert spec.kind == "thread"
        assert spec.value_type.head == "int"
        assert spec.get_base_name() == "thread"

    def test_thread_result_specialization_hydrates(self):
        registry = create_default_registry()
        type_pool = {
            "type_root.thread_result[int]": {
                "uid": "type_root.thread_result[int]",
                "kind": "thread_result",
                "name": "thread_result[int]",
                "module_path": None,
                "provenance": "KERNEL_NATIVE",
                "visibility": "PRELUDE_VISIBLE",
                "storage_model": "MEMORY_BACKED",
                "value_type_name": "int",
                "value_type_module": None,
            },
        }
        rehydrator = ArtifactRehydrator(type_pool=type_pool, registry=registry)
        spec = rehydrator.hydrate("type_root.thread_result[int]")
        assert isinstance(spec, TypeDef)
        assert spec.kind == "thread_result"
        assert spec.value_type.head == "int"
        assert spec.get_base_name() == "thread_result"


################################################################################
# 函数局部变量声明类型绑定（判别性回归）
################################################################################

class TestFunctionLocalTypeAnnotations:
    """函数作用域局部变量的声明类型必须在编译期绑定并检查。

    函数局部变量声明类型须参与编译期类型检查：重赋值类型不符（``int x = 5;
    x = "abc"``）报 SEM_TYPE_MISMATCH；符号池承载的声明类型使运行时 Optional
    值包装可用。本组锁定此语义。
    """

    def test_function_local_reassign_type_checked(self):
        """函数内带注解局部变量重赋值类型不符 → SEM_TYPE_MISMATCH。"""
        assert_error_codes("""
func work() -> int:
    int x = 5
    x = "abc"
    return x
""", "SEM_TYPE_MISMATCH")

    def test_function_local_first_assign_type_checked(self):
        """函数内带注解局部变量首次赋值类型不符 → SEM_TYPE_MISMATCH。"""
        assert_error_codes("""
func work() -> int:
    int x = "abc"
    return x
""", "SEM_TYPE_MISMATCH")

    def test_function_local_plain_assign_auto_locked(self):
        """函数内无注解裸赋值 auto 首赋值锁定（与模块级一致）。"""
        assert_error_codes("""
func work() -> int:
    x = 5
    x = "abc"
    return x
""", "SEM_TYPE_MISMATCH")

    def test_function_local_optional_type_checked(self):
        """函数内 Optional 局部变量重赋值类型不符 → SEM_TYPE_MISMATCH。"""
        assert_error_codes("""
func work() -> int:
    Optional[int] tag = None
    tag = "abc"
    return tag.unwrap()
""", "SEM_TYPE_MISMATCH")

    def test_function_local_valid_reassignment_compiles(self):
        """函数内合法重赋值（int→int / Optional→int 兼容）编译通过。"""
        assert_compiles("""
func work() -> int:
    int x = 5
    x = 7
    Optional[int] tag = None
    tag = 405
    return tag.unwrap() + x
print(work())
""")

    def test_nested_function_local_type_checked(self):
        """嵌套函数内局部变量重赋值类型检查同样生效。"""
        assert_error_codes("""
func outer() -> int:
    func inner() -> int:
        int y = 1
        y = "abc"
        return y
    return inner()
""", "SEM_TYPE_MISMATCH")

    def test_class_method_local_type_checked(self):
        """类方法内局部变量重赋值类型检查生效。"""
        assert_error_codes("""
class C:
    func run(self) -> int:
        int y = 1
        y = "abc"
        return y
""", "SEM_TYPE_MISMATCH")
