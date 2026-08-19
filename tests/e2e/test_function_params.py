"""
函数参数机制运行时 e2e 测试。

覆盖：默认参数 / 具名参数 / 动态参数（*args/**kwargs、splat）在运行时的真实绑定
（用户函数、类方法、behavior、LLM 函数、原生模块函数），以及 vtable 签名升级后
原生函数的具名调用与默认值填充。
"""

import pytest
from tests.conftest import run_ibci, compile_or_errors


class TestUserFunctionRuntime:
    """用户函数：默认 / 具名 / varargs 运行时绑定。"""

    def test_default_fill(self):
        out = run_ibci("""func f(int a = 1) -> int:
    return a
print((str)f())
""")
        assert out == ["1"]

    def test_default_overridden_by_positional(self):
        out = run_ibci("""func f(int a = 1) -> int:
    return a
print((str)f(7))
""")
        assert out == ["7"]

    def test_named_args(self):
        out = run_ibci("""func f(int a, int b) -> int:
    return a + b
print((str)f(a=1, b=2))
print((str)f(b=2, a=1))
""")
        assert out == ["3", "3"]

    def test_mixed_positional_named(self):
        out = run_ibci("""func f(int a, int b) -> int:
    return a + b
print((str)f(1, b=2))
""")
        assert out == ["3"]

    def test_multiple_defaults_named_fill(self):
        out = run_ibci("""func f(int a = 10, int b = 20) -> int:
    return a + b
print((str)f(b=5))
print((str)f())
""")
        assert out == ["15", "30"]

    def test_keyword_only(self):
        out = run_ibci("""func f(int a, *rest, int b = 1) -> int:
    return a + b
print((str)f(1, b=2))
print((str)f(1, 9, 8))
""")
        assert out == ["3", "2"]

    def test_varargs(self):
        out = run_ibci("""func f(*rest) -> list:
    return rest
print((str)f(1, 2, 3))
""")
        assert out == ["[1, 2, 3]"]

    def test_varkw(self):
        out = run_ibci("""func f(**kw) -> dict:
    return kw
print((str)f(x=1))
""")
        assert out == ["{x: 1}"]

    def test_splat_call(self):
        out = run_ibci("""func f(int a, int b) -> int:
    return a + b
list m = [1, 2]
print((str)f(*m))
""")
        assert out == ["3"]

    def test_dstar_call(self):
        out = run_ibci("""func f(int a, int b) -> int:
    return a + b
dict kw = {"a": 1, "b": 2}
print((str)f(**kw))
""")
        assert out == ["3"]

    def test_default_expr_constant(self):
        out = run_ibci("""func f(int a = 2 * 3) -> int:
    return a
print((str)f())
""")
        assert out == ["6"]


class TestClassMethodRuntime:
    """类方法：默认 / 具名参数运行时绑定。"""

    def test_method_default(self):
        out = run_ibci("""class Greeter:
    func greet(str name, str punct = "!") -> str:
        return "hi " + name + punct
Greeter g = Greeter()
print(g.greet("x"))
""")
        assert out == ["hi x!"]

    def test_method_named(self):
        out = run_ibci("""class Calc:
    func add(int a, int b) -> int:
        return a + b
Calc c = Calc()
print((str)c.add(b=2, a=1))
""")
        assert out == ["3"]


class TestNativeModuleRuntime:
    """原生模块函数：具名调用 + 默认值填充（vtable 签名升级）。"""

    def test_native_named_args(self):
        out = run_ibci("""import math
print((str)math.pow(x=2.0, y=10.0))
print((str)math.pow(2.0, y=10.0))
""")
        assert out == ["1024.0", "1024.0"]

    def test_native_clamp_named(self):
        out = run_ibci("""import math
print((str)math.clamp(x=5.0, lo=0.0, hi=3.0))
""")
        assert out == ["3.0"]

    def test_native_default_fill(self):
        # net.get 声明 headers 默认 None；未传时自动填充
        out = run_ibci("""import net
print(net.get(url="http://example.com"))
""")
        assert out == ["[MOCK GET] http://example.com"]

    def test_native_json_named(self):
        out = run_ibci('''import json
print(json.stringify(obj={"a": 1}))
''')
        assert out == ['{"a": 1}']


class TestLLMFunctionRuntime:
    """LLM 可调用类：默认参数（mock provider）。"""

    def test_llm_default(self):
        out = run_ibci("""class Greet:
    func __llm_call__(self, any who = "world") -> dict:
        return {"user_prompt": "hi " + str(who)}
Greet greet = Greet()
str g = greet()
str g2 = greet("ibci")
print(g)
print(g2)
""", ai=True)
        assert out == ["[MOCK] hi world", "[MOCK] hi ibci"]


class TestBehaviorRuntime:
    """参数化 behavior：默认参数（mock provider）。"""

    def test_behavior_default(self):
        out = run_ibci("""fn greet = lambda(str who = "world") -> str: @~ 向 $who 问好，返回"hi $who" ~
print(greet())
print(greet("ibci"))
""", ai=True)
        assert out == ['[MOCK] 向 world 问好，返回"hi "world', '[MOCK] 向 ibci 问好，返回"hi "ibci']


class TestSemanticNegative:
    """编译期负样本：具名/默认/varargs 结构错误。"""

    def test_unknown_keyword(self):
        _, errors = compile_or_errors("""func f(int a) -> int:
    return a
int r = f(z=1)
""")
        assert "SEM_UNKNOWN_KEYWORD" in errors

    def test_missing_required(self):
        _, errors = compile_or_errors("""func f(int a, int b) -> int:
    return a
int r = f(1)
""")
        assert "SEM_MISSING_REQUIRED_ARG" in errors

    def test_duplicate_keyword(self):
        _, errors = compile_or_errors("""func f(int a) -> int:
    return a
int r = f(1, a=2)
""")
        assert "SEM_DUPLICATE_KEYWORD" in errors

    def test_too_many_positional(self):
        _, errors = compile_or_errors("""func f(int a, int b) -> int:
    return a
int r = f(1, 2, 3)
""")
        assert "SEM_TOO_MANY_POSITIONAL" in errors

    def test_default_type_mismatch(self):
        _, errors = compile_or_errors('''func f(int a = "x") -> int:
    return a
int r = f()
''')
        assert "SEM_DEFAULT_TYPE_MISMATCH" in errors

    def test_native_unknown_keyword(self):
        _, errors = compile_or_errors("""import math
float r = math.pow(z=1.0)
""")
        assert "SEM_UNKNOWN_KEYWORD" in errors
