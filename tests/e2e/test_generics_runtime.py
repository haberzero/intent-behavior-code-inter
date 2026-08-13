"""
tests/e2e/test_generics_runtime.py — 泛型运行时黑盒行为。

自 tests/compiler/test_generics.py 拆分（mixed-concerns）：完整程序执行用例归
e2e/（含类内少量 compile-only 校验）；纯编译期契约归 tests/compiler/test_generics.py。
"""
from core.kernel.factory import create_default_registry
from core.kernel.issue import CompilerError
from core.kernel.spec import SpecRegistry, TypeDef
from tests.conftest import compile_ibci, run_ibci


# ---------------------------------------------------------------------------
# 共享 helper（黑盒；diag 为 diagnostics 列表）
# ---------------------------------------------------------------------------

def make_spec_registry() -> SpecRegistry:
    """Create a fully initialized SpecRegistry with all built-in axioms registered."""
    return create_default_registry()


def make_registry():
    return create_default_registry()


def _compile_code(code: str):
    """Compile only; return (artifact_or_None, diagnostics_list)."""
    try:
        return compile_ibci(code), []
    except CompilerError as e:
        return None, list(e.diagnostics)


def _sem_errors(diagnostics):
    return [d for d in diagnostics if d.severity.name == "ERROR"]


# ===========================================================================
# list[T] write method parameter specialization
# ===========================================================================

class TestListWriteMethodSpecialization:
    def test_append_param_specialized_to_element_type(self):
        """list[int].append should have param type 'int', not 'any'."""
        reg = make_spec_registry()
        list_spec = reg.resolve_specialization(reg.resolve("list"), [reg.resolve("int")])
        assert isinstance(list_spec, TypeDef)

        append_spec = reg.resolve_member(list_spec, "append")
        assert append_spec is not None
        assert [t.head for t in append_spec.param_types] == ["int"], (
            f"Expected ['int'], got {[t.head for t in append_spec.param_types]}"
        )

    def test_insert_last_param_specialized(self):
        """list[str].insert should have param types ['int', 'str']."""
        reg = make_spec_registry()
        list_spec = reg.resolve_specialization(reg.resolve("list"), [reg.resolve("str")])
        insert_spec = reg.resolve_member(list_spec, "insert")
        assert insert_spec is not None
        assert [t.head for t in insert_spec.param_types][-1] == "str", (
            f"Expected last param 'str', got {[t.head for t in insert_spec.param_types]}"
        )

    def test_setitem_last_param_specialized(self):
        """list[float].__setitem__ should have value param 'float'."""
        reg = make_spec_registry()
        float_spec = reg.resolve("float")
        list_spec = reg.resolve_specialization(reg.resolve("list"), [float_spec])
        setitem_spec = reg.resolve_member(list_spec, "__setitem__")
        assert setitem_spec is not None
        assert [t.head for t in setitem_spec.param_types][-1] == "float"

    def test_pop_return_type_still_specialized(self):
        """does not regress pop return type specialization."""
        reg = make_spec_registry()
        list_spec = reg.resolve_specialization(reg.resolve("list"), [reg.resolve("int")])
        pop_spec = reg.resolve_member(list_spec, "pop")
        assert pop_spec is not None
        assert pop_spec.return_type.head == "int"

    def test_unspecialized_list_append_stays_any(self):
        """Plain list (element_type=any) append keeps 'any' param."""
        reg = make_spec_registry()
        list_spec = reg.resolve("list")
        append_spec = reg.resolve_member(list_spec, "append")
        assert append_spec is not None
        assert "any" in [t.head for t in append_spec.param_types]

    def test_correct_type_append_no_warning(self, engine):
        """list[int].append(42) compiles cleanly without warnings."""
        engine.compile_string(
            "list[int] nums = [1, 2]\n"
            "nums.append(3)\n",
            silent=True,
        )
        warnings = [d for d in engine.scheduler.issue_tracker.diagnostics
                    if d.code == "SEM_CONTAINER_METHOD_HINT"]
        assert len(warnings) == 0, f"Unexpected warnings: {warnings}"

    def test_wrong_type_append_produces_warning_not_error(self, engine):
        """list[int].append('x') produces a SEM_CONTAINER_METHOD_HINT warning, not a compile error."""
        engine.compile_string(
            "list[int] nums = []\n"
            "nums.append(\"hello\")\n",
            silent=True,
        )
        diagnostics = engine.scheduler.issue_tracker.diagnostics
        # Compilation should succeed (no hard errors about this mismatch)
        errors = [d for d in diagnostics
                  if d.severity.name == "ERROR" and d.code == "SEM_CONTAINER_METHOD_HINT"]
        assert len(errors) == 0, f"mismatch should be a warning, not an error: {errors}"
        # The warning should be present
        warnings = [d for d in diagnostics if d.code == "SEM_CONTAINER_METHOD_HINT"]
        assert len(warnings) > 0, "Expected a SEM_CONTAINER_METHOD_HINT warning for int-list append with str"

    def test_correct_append_runs_and_produces_output(self):
        """list[int] append with correct type runs correctly end-to-end."""
        lines = run_ibci(
            "list[int] nums = [1, 2]\n"
            "nums.append(3)\n"
            "print(nums)\n"
        )
        assert len(lines) == 1
        assert "[1, 2, 3]" in lines[0]


# ===========================================================================
# list[T].__getitem__ / 下标运算
# ===========================================================================

class TestListGetitem:
    def test_getitem_return_type_is_element_type(self):
        """list[int].__getitem__ method spec should return 'int', not 'any'."""
        reg = make_registry()
        list_int = reg.resolve_specialization(reg.resolve("list"), [reg.resolve("int")])
        assert isinstance(list_int, TypeDef)

        getitem_spec = reg.resolve_member(list_int, "__getitem__")
        assert getitem_spec is not None
        assert getitem_spec.return_type.head == "int", (
            f"Expected 'int', got '{getitem_spec.return_type.head}'"
        )

    def test_getitem_return_type_for_str_list(self):
        """list[str].__getitem__ should return 'str'."""
        reg = make_registry()
        list_str = reg.resolve_specialization(reg.resolve("list"), [reg.resolve("str")])
        getitem_spec = reg.resolve_member(list_str, "__getitem__")
        assert getitem_spec is not None
        assert getitem_spec.return_type.head == "str"

    def test_unspecialized_list_getitem_stays_any(self):
        """Plain list (element_type=any) __getitem__ keeps 'any' return."""
        reg = make_registry()
        list_spec = reg.resolve("list")
        getitem_spec = reg.resolve_member(list_spec, "__getitem__")
        assert getitem_spec is not None
        assert getitem_spec.return_type.head == "any"

    def test_subscript_operator_returns_element_type(self):
        """list[int] subscript via [] operator returns int at compile time (no SEM_TYPE_MISMATCH)."""
        _, diagnostics = _compile_code(
            "list[int] nums = [1, 2, 3]\n"
            "int x = nums[0]\n"
        )
        errors = _sem_errors(diagnostics)
        assert len(errors) == 0, f"Unexpected errors: {errors}"

    def test_subscript_operator_wrong_type_is_caught(self):
        """list[int] subscript result assigned to str should be SEM_TYPE_MISMATCH."""
        _, diagnostics = _compile_code(
            "list[int] nums = [10, 20]\n"
            "str s = nums[0]\n"
        )
        errors = [d for d in diagnostics
                  if d.severity.name == "ERROR" and d.code == "SEM_TYPE_MISMATCH"]
        assert len(errors) > 0, "Expected SEM_TYPE_MISMATCH for int→str mismatch"

    def test_subscript_e2e_returns_correct_value(self):
        """list[int] subscript runs correctly and returns the element."""
        lines = run_ibci(
            "list[int] nums = [10, 20, 30]\n"
            "int x = nums[1]\n"
            "print(x)\n"
        )
        assert lines == ["20"], f"Expected ['20'], got {lines}"


# ===========================================================================
# 内置泛型特化实参赋值运行时判别（缺陷一：X[int] → X[str] 编译期拦截）
# ===========================================================================

class TestBuiltinGenericAssignabilityRuntime:
    """语言层判别：内置泛型特化实参不匹配编译期拦截（compile + e2e 双向）。"""

    def test_list_str_into_list_int_param_rejected(self):
        """list[str] 传 list[int] 参数编译期报 SEM_TYPE_MISMATCH（修复前放行）。"""
        _, errors = _compile_code(
            "func consume(list[int] items) -> void:\n"
            "    return\n"
            "list[str] strs = [\"a\"]\n"
            "consume(strs)\n"
        )
        assert "SEM_TYPE_MISMATCH" in {d.code for d in errors}, (
            f"Expected SEM_TYPE_MISMATCH, got {[d.code for d in errors]}"
        )

    def test_thread_int_into_thread_str_annotation_rejected(self):
        """thread[int] 赋给 thread[str] 变量编译期报 SEM_TYPE_MISMATCH。"""
        _, errors = _compile_code(
            "func compute() -> int:\n"
            "    return 42\n"
            "thread[int] t = thread(callable=compute, args=[])\n"
            "thread[str] t2 = t\n"
        )
        assert "SEM_TYPE_MISMATCH" in {d.code for d in errors}

    def test_list_int_into_list_int_param_ok(self):
        """同家族同实参正常编译运行（不误报）。"""
        lines = run_ibci(
            "func consume(list[int] items) -> void:\n"
            "    print(items)\n"
            "list[int] nums = [1, 2]\n"
            "consume(nums)\n"
        )
        assert lines and "[1, 2]" in lines[0]


# ===========================================================================
# 内置泛型值层类型身份保真（缺陷二：特化 spec 水化为运行时特化类）
# ===========================================================================

class TestBuiltinGenericValueIdentity:
    """内置泛型容器值带特化身份（type() 内省一致 + type_ref 带实参）。

    修复前：list[int] 值运行时用基类 list（擦除），type() 返回 list，
    与用户类泛型 Box[int] 值（Box[int]）双轨分裂。
    修复后：容器字面量经编译期 node_to_type 感知特化，值绑定特化类。
    """

    def test_list_int_value_identity(self):
        lines = run_ibci(
            "list[int] li = [1, 2]\n"
            "print(type(li))\n"
        )
        assert lines == ["list[int]"], f"Expected ['list[int]'], got {lines}"

    def test_list_str_value_identity_distinct(self):
        """list[str] 与 list[int] 值身份区分（值层类型安全）。"""
        lines = run_ibci(
            "list[str] ls = [\"a\"]\n"
            "print(type(ls))\n"
        )
        assert lines == ["list[str]"], f"Expected ['list[str]'], got {lines}"

    def test_dict_tuple_value_identity(self):
        lines = run_ibci(
            "dict[str,int] d = {\"a\": 1}\n"
            "tuple[int,str] t = (1, \"a\")\n"
            "print(type(d))\n"
            "print(type(t))\n"
        )
        assert lines == ["dict[str,int]", "tuple[int,str]"], f"got {lines}"

    def test_nested_generic_value_identity(self):
        lines = run_ibci(
            "list[list[int]] nested = [[1], [2]]\n"
            "print(type(nested))\n"
        )
        assert lines == ["list[list[int]]"], f"got {lines}"

    def test_bare_list_stays_bare(self):
        """裸 list 值保持裸身份（无特化不水化）。"""
        lines = run_ibci(
            "list bare = [1, 2]\n"
            "print(type(bare))\n"
        )
        assert lines == ["list"], f"Expected ['list'], got {lines}"

    def test_value_identity_correct_after_mutation(self):
        """特化值可正常增删元素（实现类沿基类名解析，方法继承可用）。"""
        lines = run_ibci(
            "list[int] li = [1]\n"
            "li.append(2)\n"
            "li.append(3)\n"
            "print(li)\n"
        )
        assert lines and "[1, 2, 3]" in lines[0]


# ===========================================================================
# 值层身份彻底收敛（统一"类型上下文→字面量"传递：函数返回/实参/嵌套/切片/Optional）
# ===========================================================================

class TestValueIdentityConverged:
    """边界场景值层身份保真（缺陷二根治推广）。

    此前边界：函数返回字面量 / 调用实参字面量 / 下标赋值字面量 / 嵌套内层元素 /
    容器切片 / Optional 值身份——值运行时擦除为裸 list/Optional。统一传递机制
    （编译期 _bind_literal_with_type 递归 + 运行时切片/Optional 特化类）后全部保真。
    """

    def test_function_return_literal_identity(self):
        lines = run_ibci(
            "func f() -> list[int]:\n"
            "    return [1, 2]\n"
            "list[int] r = f()\n"
            "print(type(r))\n"
        )
        assert lines == ["list[int]"], f"got {lines}"

    def test_function_return_nested_identity(self):
        lines = run_ibci(
            "func f() -> list[list[int]]:\n"
            "    return [[1], [2]]\n"
            "list[list[int]] r = f()\n"
            "list[int] row = r[0]\n"
            "print(type(r))\n"
            "print(type(row))\n"
        )
        assert lines == ["list[list[int]]", "list[int]"], f"got {lines}"

    def test_call_argument_literal_identity(self):
        lines = run_ibci(
            "func consume(list[int] items) -> void:\n"
            "    print(type(items))\n"
            "consume([1, 2])\n"
        )
        assert lines == ["list[int]"], f"got {lines}"

    def test_subscript_assignment_literal_identity(self):
        lines = run_ibci(
            "list[list[int]] m = [[1], [2]]\n"
            "m[0] = [9]\n"
            "print(type(m[0]))\n"
        )
        assert lines == ["list[int]"], f"got {lines}"

    def test_nested_inner_element_identity(self):
        lines = run_ibci(
            "list[list[int]] n = [[1], [2]]\n"
            "print(type(n))\n"
            "print(type(n[0]))\n"
        )
        assert lines == ["list[list[int]]", "list[int]"], f"got {lines}"

    def test_slice_identity(self):
        lines = run_ibci(
            "list[int] li = [1, 2, 3, 4]\n"
            "print(type(li[0:2]))\n"
            "tuple[int,str] t = (1, \"a\")\n"
            "print(type(t[0:1]))\n"
        )
        assert lines == ["list[int]", "tuple[int,str]"], f"got {lines}"

    def test_optional_value_identity(self):
        lines = run_ibci(
            "Optional[int] o = 5\n"
            "print(type(o))\n"
            "int v = o.unwrap()\n"
            "print(v)\n"
        )
        assert lines == ["Optional[int]", "5"], f"got {lines}"

    def test_deep_nested_triple(self):
        """三层嵌套递归：list[list[list[int]]] 全层身份保真。"""
        lines = run_ibci(
            "list[list[list[int]]] d = [[[1]], [[2]]]\n"
            "print(type(d))\n"
            "list[list[int]] mid = d[0]\n"
            "print(type(mid))\n"
            "list[int] leaf = mid[0]\n"
            "print(type(leaf))\n"
        )
        assert lines == ["list[list[list[int]]]", "list[list[int]]", "list[int]"], f"got {lines}"

    def test_aug_assign_identity(self):
        """复合赋值：list[int] a += [2] 结果保留特化身份。"""
        lines = run_ibci(
            "list[int] a = [1]\n"
            "a += [2]\n"
            "print(type(a))\n"
            "print(a)\n"
        )
        assert lines[0] == "list[int]", f"got {lines}"
        assert "[1, 2]" in lines[1]

    def test_conditional_literal_identity(self):
        """条件表达式：list[int] a = [1] if c else [2] 分支值保真。"""
        lines = run_ibci(
            "list[int] a = [1] if True else [2]\n"
            "print(type(a))\n"
        )
        assert lines == ["list[int]"], f"got {lines}"

    def test_list_concat_identity(self):
        """list + list 运算符：list[int] 结果保留特化身份。"""
        lines = run_ibci(
            "list[int] a = [1, 2]\n"
            "list[int] b = a + [3]\n"
            "print(type(b))\n"
            "print(b)\n"
        )
        assert lines[0] == "list[int]", f"got {lines}"
        assert "[1, 2, 3]" in lines[1]

    def test_list_mul_identity(self):
        """list * int 运算符：list[int] 结果保留特化身份。"""
        lines = run_ibci(
            "list[int] a = [1]\n"
            "list[int] b = a * 3\n"
            "print(type(b))\n"
            "print(b)\n"
        )
        assert lines[0] == "list[int]", f"got {lines}"
        assert "[1, 1, 1]" in lines[1]

    def test_lambda_return_identity(self):
        """lambda 返回：lambda -> list[int]: [1,2] 调用结果保真。"""
        lines = run_ibci(
            "fn f = lambda -> list[int]: [1, 2]\n"
            "list[int] r = f()\n"
            "print(type(r))\n"
        )
        assert lines == ["list[int]"], f"got {lines}"

    def test_default_param_identity(self):
        """函数默认参数：func f(list[int] items=[1,2]) 默认值保真。"""
        lines = run_ibci(
            "func f(list[int] items = [1, 2]) -> void:\n"
            "    print(type(items))\n"
            "f()\n"
        )
        assert lines == ["list[int]"], f"got {lines}"

    def test_generator_yield_container_identity(self):
        """生成器 yield 容器：func gen() -> list[int]: yield [1,2]（标准写法）元素保真。"""
        lines = run_ibci(
            "func gen() -> list[int]:\n"
            "    yield [1, 2]\n"
            "for list[int] row in gen():\n"
            "    print(type(row))\n"
        )
        assert lines == ["list[int]"], f"got {lines}"

    def test_generator_explicit_generic_return_identity(self):
        """生成器 yield 容器：func gen() -> generator[list[int]]（显式标注）元素保真。"""
        lines = run_ibci(
            "func gen() -> generator[list[int]]:\n"
            "    yield [1, 2]\n"
            "for list[int] row in gen():\n"
            "    print(type(row))\n"
        )
        assert lines == ["list[int]"], f"got {lines}"

    def test_for_literal_source_identity(self):
        """for 循环源字面量：for list[int] row in [[1],[2]] 元素保真。"""
        lines = run_ibci(
            "for list[int] row in [[1], [2]]:\n"
            "    print(type(row))\n"
        )
        assert lines == ["list[int]", "list[int]"], f"got {lines}"

    def test_for_nested_literal_source_identity(self):
        """for 嵌套源：for list[list[int]] grid in [[[1]]] 全层保真。"""
        lines = run_ibci(
            "for list[list[int]] grid in [[[1]]]:\n"
            "    print(type(grid))\n"
            "    for list[int] row in grid:\n"
            "        print(type(row))\n"
        )
        assert lines == ["list[list[int]]", "list[int]"], f"got {lines}"

    def test_optional_wrapped_container_identity(self):
        """Optional 包裹容器：Optional[list[int]] o=[1,2] 内层容器保真。"""
        lines = run_ibci(
            "Optional[list[int]] o = [1, 2]\n"
            "list[int] l = o.unwrap()\n"
            "print(type(l))\n"
        )
        assert lines == ["list[int]"], f"got {lines}"


# ===========================================================================
# 生成器返回类型/值层身份（双包根治 + 序列化保真 + 类型检查）
# ===========================================================================

class TestGeneratorReturnIdentity:
    """生成器返回类型一致性（预存缺陷根治）。

    - ``-> generator[T]`` 显式标注此前被二次包裹为 generator[generator[T]]
      （c8b89564 预存），致调用点返回类型退化为 any，错误元素类型赋值未拦截。
    - generator[T] 特化 spec 序列化此前丢 value_type（serializer 缺分支），
      rehydrator 恢复为裸 generator。
    """

    def test_explicit_generator_return_type_rejected(self):
        """显式 -> generator[list[int]] 赋 generator[list[str]] 编译期拦截。"""
        _, errors = _compile_code(
            "func gen() -> generator[list[int]]:\n"
            "    yield [1, 2]\n"
            "generator[list[str]] bad = gen()\n"
        )
        assert "SEM_TYPE_MISMATCH" in {d.code for d in errors}, (
            f"Expected SEM_TYPE_MISMATCH, got {[d.code for d in errors]}"
        )

    def test_standard_generator_return_type_rejected(self):
        """标准写法 -> list[int] 赋 generator[list[str]] 编译期拦截。"""
        _, errors = _compile_code(
            "func gen() -> list[int]:\n"
            "    yield [1, 2]\n"
            "generator[list[str]] bad = gen()\n"
        )
        assert "SEM_TYPE_MISMATCH" in {d.code for d in errors}, (
            f"Expected SEM_TYPE_MISMATCH, got {[d.code for d in errors]}"
        )

    def test_generator_correct_type_allowed(self):
        """生成器赋正确类型放行（显式 + 标准两种写法）。"""
        lines = run_ibci(
            "func gen() -> list[int]:\n"
            "    yield [1, 2]\n"
            "generator[list[int]] g = gen()\n"
            "print(type(g))\n"
            "for list[int] row in g:\n"
            "    print(type(row))\n"
        )
        assert lines == ["generator", "list[int]"], f"got {lines}"


# ===========================================================================
# 元组解包容器身份 + lambda yield 误标记（独立复核发现）
# ===========================================================================

class TestTupleUnpackAndLambdaYield:
    """独立复核（general agent）发现的 B1/B2 修复回归。

    - B1：元组解包 list[int] a, list[str] b = [1,2], ["x"] 各元素值身份保真。
    - B2：lambda 内 yield 不再误标外层函数为生成器（_contains_yield 排除 lambda）。
    """

    def test_tuple_unpack_container_identity(self):
        """元组解包容器字面量：各元素绑各自声明特化类型。"""
        lines = run_ibci(
            "list[int] a, list[str] b = [1, 2], [\"x\"]\n"
            "print(type(a))\n"
            "print(type(b))\n"
        )
        assert lines == ["list[int]", "list[str]"], f"got {lines}"

    def test_tuple_unpack_nested_identity(self):
        """元组解包嵌套：list[list[int]] a, dict[str,int] b 全层保真。"""
        lines = run_ibci(
            "list[list[int]] a, dict[str,int] b = [[1],[2]], {\"k\": 1}\n"
            "print(type(a))\n"
            "print(type(a[0]))\n"
            "print(type(b))\n"
        )
        assert lines == ["list[list[int]]", "list[int]", "dict[str,int]"], f"got {lines}"

    def test_lambda_yield_not_mark_outer_generator(self):
        """lambda 内 yield 不误标外层函数为生成器（修复前返回 generator 实例）。"""
        lines = run_ibci(
            "func f() -> int:\n"
            "    fn g = lambda -> int: yield 5\n"
            "    return 42\n"
            "auto r = f()\n"
            "print(r)\n"
        )
        assert lines == ["42"], f"got {lines}"


# ===========================================================================
# Nested generic subscript — list[list[int]][0] → list[int]
# ===========================================================================

class TestNestedGenerics:
    def test_nested_list_subscript_returns_inner_list_spec(self):
        """list[list[int]] subscript by int returns list[int] spec."""
        reg = make_registry()
        list_int = reg.resolve_specialization(reg.resolve("list"), [reg.resolve("int")])
        list_list_int = reg.resolve_specialization(reg.resolve("list"), [list_int])
        assert isinstance(list_list_int, TypeDef)
        assert list_list_int.element_type.head == "list[int]"

        result = reg.resolve_subscript(list_list_int, reg.resolve("int"))
        assert result is not None
        assert result.name == "list[int]", f"Expected 'list[int]', got '{result.name}'"

    def test_nested_list_compile_no_error(self):
        """list[list[int]] declaration and double-subscript compiles without errors."""
        _, diagnostics = _compile_code(
            "list[list[int]] nested = [[1, 2], [3, 4]]\n"
            "list[int] row = nested[0]\n"
            "int val = row[0]\n"
        )
        errors = _sem_errors(diagnostics)
        assert len(errors) == 0, f"Unexpected errors: {errors}"

    def test_nested_list_e2e(self):
        """list[list[int]] access works end-to-end."""
        lines = run_ibci(
            "list[list[int]] nested = [[10, 20], [30, 40]]\n"
            "list[int] row = nested[1]\n"
            "int val = row[0]\n"
            "print(val)\n"
        )
        assert lines == ["30"], f"Expected ['30'], got {lines}"
