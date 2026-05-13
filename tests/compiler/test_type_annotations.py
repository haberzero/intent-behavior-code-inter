"""
tests/compiler/test_type_annotations.py
=======================================

类型标注综合测试（合并自 5 个历史文件）：

* Optional[T] 类型方法解析与编译期语义
  （原 ``test_m2_optional_methods.py``）
* Optional[T] 空安全编译期校验
  （原 ``test_m2_optional_null_safety.py``）
* ``fn[(in)->(out)]`` callable 签名（D3）
  （原 ``test_d3_callable_sig.py``）
* ``tuple[T1,T2,...]`` 位置类型推断（NS-7）
  （原 ``test_tuple_positional_types.py``）
* Optional[T] artifact 还原（从序列化产物恢复 Optional 类型 spec）
  （原 ``unit/test_m2_optional_artifact_rehydrator.py``）

详见 docs/TESTS_REORGANIZATION_TASK.md Step 8。
"""
import os
from core.kernel.spec.registry import SpecFactory
from core.kernel.spec.base import TypeKind
import pytest

from core.engine import IBCIEngine
from core.kernel.factory import create_default_registry
from core.kernel.issue import CompilerError
from core.kernel.spec.specs import TypeDef
from core.runtime.loader.artifact_rehydrator import ArtifactRehydrator


# ---------------------------------------------------------------------------
# 共享 helper（合并 5 个历史文件的本地副本）
# ---------------------------------------------------------------------------

ROOT_DIR = "."


def make_engine():
    return IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)


def compile_code(code: str):
    """Compile *code*, return (artifact_or_None, error_codes)."""
    engine = make_engine()
    try:
        artifact = engine.compile_string(code, silent=True)
        return artifact, set()
    except CompilerError as e:
        return None, {d.code for d in e.diagnostics}


def assert_compiles(code: str):
    artifact, errors = compile_code(code)
    assert artifact is not None
    assert not errors, f"Expected no compiler errors, got: {errors}"


def assert_has_sem003(code: str):
    _, errors = compile_code(code)
    assert "SEM_003" in errors, f"Expected SEM_003, got: {errors}"


def assert_error_codes(code: str, *expected_codes: str):
    _, errors = compile_code(code)
    for code_val in expected_codes:
        assert code_val in errors, f"Expected error {code_val!r} but got: {errors}"


def run_and_capture(code: str):
    lines = []
    engine = make_engine()
    engine.run_string(code, output_callback=lambda t: lines.append(str(t)), silent=True)
    return lines


# ---------- tuple positional helpers ----------

def _run(code: str):
    engine = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
    out = []
    engine.run_string(code, output_callback=lambda t: out.append(str(t)), silent=True)
    return out


def _run_expect_compile_error(code: str):
    engine = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
    with pytest.raises(CompilerError):
        engine.run_string(code, output_callback=lambda t: None, silent=True)


################################################################################
# MERGED: Optional[T] 类型方法解析 + 编译期语义
# Source: tests/compiler/test_m2_optional_methods.py
################################################################################

class TestM2OptionalMethodResolution:
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


class TestM2OptionalMethodCompileSemantics:
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
# MERGED: Optional[T] 空安全编译期校验
# Source: tests/compiler/test_m2_optional_null_safety.py
################################################################################

class TestM2OptionalNullSafety:
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
# MERGED: callable 签名 fn[(in)->(out)]（D3）
# Source: tests/compiler/test_d3_callable_sig.py
################################################################################

class TestD3Parse:
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
    fn add = lambda(int x): n + x
    return add
""")

    def test_bare_fn_still_works(self):
        """Plain fn f = myfunc (without signature) is unaffected by D3."""
        assert_compiles("""
func double(int n) -> int:
    return n * 2

fn f = double
print((str)f(3))
""")


# ─────────────────────────────────────────────────────── call-site checks ──

class TestD3CallSiteStructural:
    """Calling a fn[(...)→(...)] parameter: arg-count and type checks."""

    def test_correct_call_no_error(self):
        """Calling fn[(int) -> int] with correct arg type produces no error."""
        assert_compiles("""
func apply(fn[(int) -> int] f, int x) -> int:
    return f(x)
""")

    def test_too_many_args(self):
        """Calling fn[(int) -> int] with 2 args → SEM_005."""
        assert_error_codes("""
func apply(fn[(int) -> int] f, int x, int y) -> int:
    return f(x, y)
""", "SEM_005")

    def test_too_few_args(self):
        """Calling fn[(int, str) -> bool] with 1 arg → SEM_005."""
        assert_error_codes("""
func apply(fn[(int, str) -> bool] pred) -> bool:
    return pred(1)
""", "SEM_005")

    def test_wrong_arg_type(self):
        """Calling fn[(int) -> int] with str arg → SEM_003."""
        assert_error_codes("""
func apply(fn[(int) -> int] f, str s) -> int:
    return f(s)
""", "SEM_003")


# ──────────────────────────────────────────── declaration-site sig check ──

class TestD3DeclarationSite:
    """fn[(...)→(...)] variable declaration: structural sig matching on RHS."""

    def test_matching_sig_no_error(self):
        """fn[(int) -> int] f = add_one passes when signatures match."""
        assert_compiles("""
func add_one(int n) -> int:
    return n + 1

fn[(int) -> int] f = add_one
""")

    def test_param_count_mismatch(self):
        """fn[(int, str) -> int] f = add_one (1 param) → SEM_003."""
        assert_error_codes("""
func add_one(int n) -> int:
    return n + 1

fn[(int, str) -> int] f = add_one
""", "SEM_003")

    def test_return_type_mismatch(self):
        """fn[(int) -> str] f = add_one (returns int) → SEM_003."""
        assert_error_codes("""
func add_one(int n) -> int:
    return n + 1

fn[(int) -> str] f = add_one
""", "SEM_003")


# ────────────────────────────────────────────────────── return type infer ──

class TestD3ReturnTypeInference:
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


# ──────────────────────────────────────────────────────── end-to-end runs ──

class TestD3E2E:
    """Full execution: HOF with fn[(...)→(...)] parameters."""

    def test_apply_double(self):
        """HOF apply(fn[(int) -> int], int) runs correctly."""
        lines = run_and_capture("""func double(int n) -> int:
    return n * 2

func apply(fn[(int) -> int] f, int x) -> int:
    return f(x)

int result = apply(double, 5)
print((str)result)
""")
        assert lines == ["10"]

    def test_apply_with_lambda(self):
        """HOF apply(fn[(int) -> int], int) works with a lambda."""
        lines = run_and_capture("""func apply(fn[(int) -> int] f, int x) -> int:
    return f(x)

fn triple = lambda(int n) -> int: n * 3
int result = apply(triple, 4)
print((str)result)
""")
        assert lines == ["12"]

    def test_multi_param_predicate(self):
        """HOF check(fn[(int, int) -> bool], int, int) works."""
        lines = run_and_capture("""func gt(int a, int b) -> bool:
    return a > b

func check(fn[(int, int) -> bool] pred, int x, int y) -> bool:
    return pred(x, y)

bool r1 = check(gt, 10, 3)
bool r2 = check(gt, 1, 7)
print((str)r1)
print((str)r2)
""")
        assert lines == ["True", "False"]

    def test_no_params_fn_sig(self):
        """HOF with fn[() -> int] parameter works."""
        lines = run_and_capture("""func get_ten() -> int:
    return 10

func call_it(fn[() -> int] f) -> int:
    return f()

int r = call_it(get_ten)
print((str)r)
""")
        assert lines == ["10"]

    def test_fn_sig_variable_callable(self):
        """fn[(int) -> int] variable pointing to a function, then called."""
        lines = run_and_capture("""func square(int n) -> int:
    return n * n

fn[(int) -> int] f = square
int result = f(7)
print((str)result)
""")
        assert lines == ["49"]


################################################################################
# MERGED: tuple[T1,T2,...] 位置类型推断（NS-7）
# Source: tests/compiler/test_tuple_positional_types.py
################################################################################

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
# MERGED: Optional[T] artifact 还原
# Source: tests/unit/test_m2_optional_artifact_rehydrator.py
################################################################################

class TestM2OptionalArtifactRehydrator:
    def test_unsupported_kind_rejected(self):
        registry = create_default_registry()
        type_pool = {
            "type_root.int": {
                "uid": "type_root.int",
                "kind": "primitive",
                "name": "int",
                "module_path": None,
                "is_nullable": False,
                "is_user_defined": False,
            },
            "type_root.Optional[int]": {
                "uid": "type_root.Optional[int]",
                "kind": "TypeDef",
                "name": "Optional[int]",
                "module_path": None,
                "is_nullable": True,
                "is_user_defined": False,
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
                "is_nullable": False,
                "is_user_defined": False,
                "element_type_uid": "type_root.int",
            },
            "type_root.int": {
                "uid": "type_root.int",
                "kind": "primitive",
                "name": "int",
                "module_path": None,
                "is_nullable": False,
                "is_user_defined": False,
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
                "is_nullable": False,
                "is_user_defined": False,
            },
            "type_root.Optional[int]": {
                "uid": "type_root.Optional[int]",
                "kind": "optional",
                "name": "Optional[int]",
                "module_path": None,
                "is_nullable": True,
                "is_user_defined": False,
                "wrapped_type_name": "int",
                "wrapped_type_module": None,
            },
        }

        rehydrator = ArtifactRehydrator(type_pool=type_pool, registry=registry)
        spec = rehydrator.hydrate("type_root.Optional[int]")

        assert isinstance(spec, TypeDef)
        assert spec.kind == "optional"
        assert spec.wrapped_type.head == "int"
