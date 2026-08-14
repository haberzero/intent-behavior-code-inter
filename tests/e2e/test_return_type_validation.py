"""
tests/compiler/test_return_type_validation.py
==============================================

可调用返回类型兼容校验判别性回归（BOUNDARY-NESTED-FUNC-1 根因根治）。

背景：``visit_IbReturn`` 此前从不比对返回表达式类型与函数声明返回类型——
``-> fn_callable[int]: return inner``（函数引用）编译期放行、运行期
RUN_TYPE_MISMATCH。修复后对**非动态**的可调用返回类型（fn_callable[T] /
callable / behavior[T]）做 is_assignable 校验，与直接赋值路径
（``fn_callable[T] g = inner`` 编译期拦截）语义一致。

锁定语义：
- 具体可调用返回类型 + 不匹配返回 → 编译期 SEM_TYPE_MISMATCH
- 具体可调用返回类型 + 匹配返回 → 放行（正确 lambda）
- 动态声明（``-> fn`` 推断哨兵）→ 跳过校验（返回任意可调用）
- 普通类型返回（``-> int`` 返回 str）保持既有宽松语义（独立问题，不在本修复范围）
"""
from tests.conftest import run_ibci, compile_or_errors

SEM = "SEM_TYPE_MISMATCH"


def _errs(code: str):
    _, errors = compile_or_errors(code)
    return errors


class TestReturnCallableValidation:
    def test_return_nested_func_to_fn_callable_typed_rejected(self):
        """``-> fn_callable[int]: return inner``（函数引用）编译期拦截——与
        ``fn_callable[int] g = inner`` 直接赋值一致。"""
        code = (
            "func outer() -> fn_callable[int]:\n"
            "    func inner() -> int:\n"
            "        return 42\n"
            "    return inner\n"
            "fn_callable[int] g = outer()\n"
            "print(g())\n"
        )
        assert SEM in _errs(code)

    def test_return_lambda_signature_mismatch_rejected(self):
        """``-> fn_callable[int]: return lambda -> str`` 签名不匹配编译期拦截。"""
        code = (
            "func make() -> fn_callable[int]:\n"
            "    return lambda -> str: \"hi\"\n"
            "fn_callable[int] f = make()\n"
            "print(f())\n"
        )
        assert SEM in _errs(code)

    def test_return_matching_lambda_allowed(self):
        """``-> fn_callable[int]: return lambda -> int`` 匹配放行，调用正常。"""
        code = (
            "func make() -> fn_callable[int]:\n"
            "    return lambda -> int: 42\n"
            "fn_callable[int] f = make()\n"
            "print(f())\n"
        )
        assert run_ibci(code) == ["42"]

    def test_return_nested_func_to_bare_fn_allowed(self):
        """``-> fn``（动态推断哨兵）返回嵌套函数放行——现有 HOF 合法路径。"""
        code = (
            "func outer() -> fn:\n"
            "    func inner() -> int:\n"
            "        return 7\n"
            "    return inner\n"
            "fn f = outer()\n"
            "print(f())\n"
        )
        assert run_ibci(code) == ["7"]

    def test_return_lambda_to_bare_fn_allowed(self):
        """``-> fn`` 返回 lambda 放行（现有 test_higher_order 路径回归）。"""
        code = (
            "func make(str greeting) -> fn:\n"
            "    fn greet = lambda(str name) -> auto: greeting + \", \" + name\n"
            "    return greet\n"
            "fn hello = make(\"Hello\")\n"
            "print(hello(\"Alice\"))\n"
        )
        assert run_ibci(code) == ["Hello, Alice"]

    def test_return_callable_internal_type_rejected(self):
        """``-> callable`` 是内部类型名，作为用户返回类型注解报错（方向 A：
        callable 降级为纯内部概念，用户面统一为 fn 族）。"""
        code = (
            "func outer() -> callable:\n"
            "    func inner() -> int:\n"
            "        return 42\n"
            "    return inner\n"
            "fn g = outer()\n"
            "print(g())\n"
        )
        assert "SEM_UNRESOLVED_TYPE" in _errs(code)

    def test_return_fn_allows_nested_func(self):
        """``-> fn: return inner``（动态哨兵）返回嵌套函数放行——fn 是"任意可调用"
        抽象（方向 A 收紧后仍接受函数引用）。"""
        code = (
            "func outer() -> fn:\n"
            "    func inner() -> int:\n"
            "        return 42\n"
            "    return inner\n"
            "fn g = outer()\n"
            "print(g())\n"
        )
        assert run_ibci(code) == ["42"]

    def test_return_fn_sig_mismatch_rejected(self):
        """``-> fn[(...) -> int]`` 签名不匹配（嵌套函数参数数量不符）编译期拦截。"""
        code = (
            "func outer() -> fn[() -> int]:\n"
            "    func inner(int x) -> int:\n"
            "        return x\n"
            "    return inner\n"
            "fn g = outer()\n"
            "print(g())\n"
        )
        assert SEM in _errs(code)

    def test_return_plain_type_still_loose(self):
        """普通类型返回（``-> int`` 返回 str）保持既有宽松语义——不扩大影响面。"""
        code = (
            "func f() -> int:\n"
            "    return \"abc\"\n"
            "print(f())\n"
        )
        # 编译通过（宽松语义保持）；运行期按当前实现执行。
        assert SEM not in _errs(code)

    def test_return_optional_allowed(self):
        """Optional 返回类型不受影响（非可调用 kind，跳过校验）。"""
        code = (
            "func maybe(int n) -> Optional[int]:\n"
            "    if n > 0:\n"
            "        return n\n"
            "    return None\n"
            "Optional[int] r = maybe(5)\n"
            "print(r.is_some())\n"
            "print(r.unwrap())\n"
            "Optional[int] e = maybe(-1)\n"
            "print(e.is_none())\n"
        )
        assert run_ibci(code) == ["True", "5", "True"]

    def test_return_behavior_declared_rejected_for_lambda(self):
        """``-> behavior: return lambda``——lambda 不是 behavior，应拦截。"""
        code = (
            "func make() -> behavior:\n"
            "    return lambda -> int: 1\n"
            "behavior b = make()\n"
            "print(b)\n"
        )
        assert SEM in _errs(code)

    def test_return_callable_internal_type_rejected_for_user_call_class(self):
        """``-> callable`` 内部类型名作为返回注解报错（方向 A）。"""
        code = (
            "class Adder:\n"
            "    int base\n"
            "    func __init__(self, int b) -> auto:\n"
            "        self.base = b\n"
            "    func __call__(self, int x) -> int:\n"
            "        return self.base + x\n"
            "func make() -> callable:\n"
            "    return Adder(10)\n"
            "fn f = make()\n"
            "print(f(5))\n"
        )
        assert "SEM_UNRESOLVED_TYPE" in _errs(code)

    def test_return_fn_declared_allows_user_call_class(self):
        """``-> fn``（动态）返回用户类 __call__ 实例放行（fn 收可调用类实例）。"""
        code = (
            "class Adder:\n"
            "    int base\n"
            "    func __init__(self, int b) -> auto:\n"
            "        self.base = b\n"
            "    func __call__(self, int x) -> int:\n"
            "        return self.base + x\n"
            "func make() -> fn:\n"
            "    return Adder(10)\n"
            "fn f = make()\n"
            "print(f(5))\n"
        )
        assert run_ibci(code) == ["15"]


class TestBoundMethodReturn:
    """绑定方法返回可调用类型——BoundMethodAxiom 编译期接线后语义。

    编译器把成员访问（``a.calc``）建模为 BOUND_METHOD kind（携带签名、不含
    self），BoundMethodAxiom（bound_method IS-A callable）编译期生效——
    ``-> fn: return a.calc`` 与直接赋值 ``fn f = a.calc`` 均放行
    （此前无条件 FUNCTION kind 使赋 callable 槽被拒，编译期/运行期身份不对称；
    方向 A 后用户面 callable 类型移除，统一用 ``fn``）。
    """

    def test_return_bound_method_to_fn_allowed(self):
        """``-> fn: return a.calc`` 编译放行，绑定方法调用正确。"""
        code = (
            "class Adder:\n"
            "    int base\n"
            "    func __init__(self, int b) -> auto:\n"
            "        self.base = b\n"
            "    func calc(self) -> int:\n"
            "        return self.base + 1\n"
            "func make(Adder a) -> fn:\n"
            "    return a.calc\n"
            "fn f = make(Adder(10))\n"
            "print(f())\n"
        )
        assert run_ibci(code) == ["11"]

    def test_bound_method_direct_assignment_to_fn_allowed(self):
        """``fn f = a.calc`` 直接赋值放行（与 return 路径语义一致）。"""
        code = (
            "class Adder:\n"
            "    int base\n"
            "    func __init__(self, int b) -> auto:\n"
            "        self.base = b\n"
            "    func calc(self) -> int:\n"
            "        return self.base + 1\n"
            "Adder a = Adder(10)\n"
            "fn f = a.calc\n"
            "print(f())\n"
        )
        assert run_ibci(code) == ["11"]

    def test_bound_method_signature_slot_allowed(self):
        """``fn[(int) -> int] f = a.calc`` 签名匹配放行（bound 签名不含 self）。"""
        code = (
            "class Adder:\n"
            "    int base\n"
            "    func __init__(self, int b) -> auto:\n"
            "        self.base = b\n"
            "    func calc(self, int x) -> int:\n"
            "        return self.base + x\n"
            "Adder a = Adder(10)\n"
            "fn[(int) -> int] f = a.calc\n"
            "print(f(5))\n"
        )
        assert run_ibci(code) == ["15"]

    def test_bound_method_signature_slot_mismatch_rejected(self):
        """``fn[(int, int) -> int] f = a.calc`` 参数数量不匹配编译期拦截。"""
        code = (
            "class Adder:\n"
            "    func calc(self, int x) -> int:\n"
            "        return x\n"
            "Adder a = Adder()\n"
            "fn[(int, int) -> int] f = a.calc\n"
            "print(f(5, 6))\n"
        )
        assert SEM in _errs(code)

    def test_bound_method_type_identity(self):
        """``a.calc`` 编译期类型身份为 BOUND_METHOD（is_callable + 签名保真）。"""
        from core.kernel.factory import create_default_registry
        from core.kernel.spec.base import TypeKind

        reg = create_default_registry()
        # BOUND_METHOD 身份：BoundMethodAxiom 生效（IS-A callable），签名承载。
        bm = reg.factory.create_bound_method(
            receiver_type_name="Adder",
            func_spec_name="calc",
        )
        assert bm.kind == TypeKind.BOUND_METHOD.value
        assert reg.is_callable(bm)
        assert reg.is_assignable(bm, reg.resolve("callable"))
