"""
tests/compiler/semantic/test_behavior_return.py
===============================================

``return @~...~`` 编译期拦截的行为契约。

行为表达式不可直接用于 return：`return @~...~` 编译期报 SEM_TYPE_MISMATCH
（visit_IbReturn 镜像 visit_IbAssign 的行为表达式处理）；正确写法
（先赋值有类型局部变量再 return）不受影响。
"""
from tests.conftest import expect_compile_error, run_ibci, AI_MOCK_PREFIX


class TestBehaviorExprInReturn:
    def test_direct_return_behavior_rejected(self):
        """return @~...~ 直接书写 → 编译期 SEM_TYPE_MISMATCH。"""
        code = AI_MOCK_PREFIX + """
func get_reply() -> str:
    return @~ MOCK:STR:ok ~
"""
        expect_compile_error(code, "SEM_TYPE_MISMATCH")

    def test_direct_return_behavior_int_rejected(self):
        """return @~...~（-> int 目标）同样编译期拦截。"""
        code = AI_MOCK_PREFIX + """
func get_num() -> int:
    return @~ MOCK:INT:42 ~
"""
        expect_compile_error(code, "SEM_TYPE_MISMATCH")

    def test_typed_local_variable_then_return_works(self):
        """正确写法：先赋值有类型局部变量再 return——正常执行。"""
        code = AI_MOCK_PREFIX + """
func get_reply() -> str:
    str reply = @~ MOCK:STR:ok ~
    return reply

str r = get_reply()
print(r)
"""
        assert run_ibci(code) == ["ok"]

    def test_plain_return_still_works(self):
        """非行为表达式 return 不受影响。"""
        code = """
func add(int a, int b) -> int:
    return a + b

print((str)add(1, 2))
"""
        assert run_ibci(code) == ["3"]


class TestBooleanLiteralGuidance:
    """小写 true/false/none 未定义时给出引导信息。

    IBCI 布尔/空值字面量大写（True/False/None，与 Python 一致）。
    用户写小写时，在 "Undefined symbol" 之外附带大写形式的引导。
    """

    def _compile_errors(self, code):
        from core.engine import IBCIEngine
        from core.kernel.issue import CompilerError
        from tests.conftest import _default_root

        engine = IBCIEngine(root_dir=_default_root())
        try:
            engine.compile_string(code, silent=True)
            return []
        except CompilerError as e:
            return [d.message for d in e.diagnostics]

    def test_lowercase_true_hints(self):
        msgs = self._compile_errors("bool b = true\n")
        assert any("true" in m and "True" in m for m in msgs), msgs

    def test_lowercase_false_hints(self):
        msgs = self._compile_errors("bool b = false\n")
        assert any("false" in m and "False" in m for m in msgs), msgs

    def test_uppercase_true_still_works(self):
        assert run_ibci("bool b = True\nprint((str)b)\n") == ["True"]
