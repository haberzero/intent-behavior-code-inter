"""
tests_v2/compiler/test_type_annotations.py — 类型标注编译期契约（compile-only）。

编译期语义：

* Optional[T] 类型方法解析与编译期语义
* Optional[T] 空安全编译期校验
* ``fn[(in)->(out)]`` callable 签名
* SpecFactory.create_tuple 直接 API
* Optional[T] / thread artifact 还原（从序列化产物恢复类型 spec）

运行时执行用例见 tests_v2/e2e/test_type_annotations_runtime.py（mixed-concerns 拆分）。
"""
import pytest

from core.kernel.factory import create_default_registry
from core.kernel.spec.base import TypeKind
from core.kernel.spec.registry import SpecFactory
from core.kernel.spec.specs import TypeDef
from core.runtime.loader.artifact_rehydrator import ArtifactRehydrator
from tests_v2.conftest import compile_or_errors


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
    def test_or_else_allows_unwrap_to_plain_type(self):
        assert_compiles(
            "Optional[int] x = None\n"
            "int y = x.or_else(3)\n"
        )

    def test_unwrap_allows_assign_to_plain_type(self):
        assert_compiles(
            "Optional[int] x = 1\n"
            "int y = x.unwrap()\n"
        )


################################################################################
# Optional[T] 空安全编译期校验
################################################################################

class TestOptionalNullSafety:
    def test_optional_int_accepts_none(self):
        assert_compiles(
            "Optional[int] x = None\n"
            "Optional[int] y = x\n"
        )

    def test_optional_int_accepts_int(self):
        assert_compiles(
            "Optional[int] x = 1\n"
            "Optional[int] y = x\n"
        )

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

    def test_no_params_int_return(self):
        """fn[() -> int] as parameter annotation compiles without errors."""
        assert_compiles("""
func apply(fn[() -> int] f) -> int:
    return f()
""")

    def test_single_param(self):
        """fn[(int) -> int] as parameter annotation compiles without errors."""
        assert_compiles("""
func apply(fn[(int) -> int] f, int x) -> int:
    return f(x)
""")

    def test_multi_param(self):
        """fn[(int, str) -> bool] as parameter annotation compiles without errors."""
        assert_compiles("""
func check(fn[(int, str) -> bool] predicate, int n, str s) -> bool:
    return predicate(n, s)
""")

    def test_as_variable_declaration_type(self):
        """fn[(int) -> int] as variable declaration type compiles without errors."""
        assert_compiles("""
func add_one(int n) -> int:
    return n + 1

fn[(int) -> int] f = add_one
""")

    def test_as_return_type_annotation(self):
        """fn[(int) -> int] as function return type annotation compiles without errors."""
        assert_compiles("""
func make_adder(int n) -> fn[(int) -> int]:
    fn add = lambda(int x) -> auto: n + x
    return add
""")

    def test_bare_fn_still_works(self):
        """Plain fn f = myfunc (without signature) still compiles."""
        assert_compiles("""
func double(int n) -> int:
    return n * 2

fn f = double
print((str)f(3))
""")


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

    def test_int_return_inferred(self):
        """fn[(int) -> int] parameter: calling it produces int."""
        assert_compiles("""
func apply(fn[(int) -> int] f, int x) -> int:
    int result = f(x)
    return result
""")

    def test_bool_return_inferred(self):
        """fn[(int, str) -> bool] parameter: calling it produces bool."""
        assert_compiles("""
func check(fn[(int, str) -> bool] pred, int n, str s) -> bool:
    bool result = pred(n, s)
    return result
""")


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
