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

    def test_return_callable_declared_rejected_for_nested_func(self):
        """``-> callable: return inner``——callable 是具体可调用类型，函数引用
        赋 callable 槽同样应拦截（与 ``callable f = add`` 一致）。"""
        code = (
            "func outer() -> callable:\n"
            "    func inner() -> int:\n"
            "        return 42\n"
            "    return inner\n"
            "callable g = outer()\n"
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

    def test_return_callable_declared_rejected_for_user_call_class(self):
        """``-> callable: return Adder(10)``（用户类 __call__ 实例）——与直接赋值
        ``callable f = Adder(10)`` 编译期拦截一致（is_assignable 不含 __call__
        类实例放行；``fn`` 动态路径不受影响）。"""
        code = (
            "class Adder:\n"
            "    int base\n"
            "    func __init__(self, int b) -> auto:\n"
            "        self.base = b\n"
            "    func __call__(self, int x) -> int:\n"
            "        return self.base + x\n"
            "func make() -> callable:\n"
            "    return Adder(10)\n"
            "callable f = make()\n"
            "print(f(5))\n"
        )
        assert SEM in _errs(code)

    def test_return_fn_declared_allows_user_call_class(self):
        """``-> fn``（动态）返回用户类 __call__ 实例放行（现有 fn 语义）。"""
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
    """绑定方法返回可调用类型——与直接赋值路径语义一致（F2 复核锁定）。

    编译器把成员访问（``a.calc``）建模为 FUNCTION-kind spec（name=calc），
    BoundMethodAxiom（bound_method IS-A callable）不触发，故绑定方法赋
    callable/fn_callable 槽在直接赋值路径即被拦截（pre-existing，非本修复
    引入）。本测试锁定 return 路径与赋值路径的一致性。
    """

    def test_return_bound_method_to_callable_rejected(self):
        """``-> callable: return a.calc`` 编译期拦截（与 ``callable f = a.calc``
        直接赋值一致——pre-existing 绑定方法建模，非本次修复回归）。"""
        code = (
            "class Adder:\n"
            "    int base\n"
            "    func __init__(self, int b) -> auto:\n"
            "        self.base = b\n"
            "    func calc(self) -> int:\n"
            "        return self.base + 1\n"
            "func make(Adder a) -> callable:\n"
            "    return a.calc\n"
            "callable f = make(Adder(10))\n"
            "print(f())\n"
        )
        assert SEM in _errs(code)

    def test_return_bound_method_to_fn_allowed(self):
        """``-> fn``（动态）返回绑定方法放行（fn 推断哨兵，与赋值一致）。"""
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
