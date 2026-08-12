"""
tests/compiler/semantic/test_behavior_return.py
===============================================

``return @~...~`` 编译期拦截回归测试（2026-08-12）。

背景：KNOWN_LIMITS §四 声称"行为表达式不可直接用于 return，报 SEM_TYPE_MISMATCH"，
但 v1 语义重构（afe9644 删除 v1 semantic code）时该拦截未随迁到 v2
（_statement_visitors.py）——文档与实现漂移：直接写 return @~ 编译通过、
运行时按字符串 box（-> int 等具体类型失效，静默类型错流入）。

修复：visit_IbReturn 补全设计意图拦截（镜像 visit_IbAssign 的行为表达式处理），
`return @~...~` 编译期报 SEM_TYPE_MISMATCH；正确写法（先赋值局部变量再 return）
不受影响。
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
    """小写 true/false/none 未定义时的引导信息（2026-08-12）。

    背景：IBCI 布尔/空值字面量大写（True/False/None，与 Python 一致）。
    用户写小写时此前报裸 "Undefined symbol 'true'"（误导）；现加引导。
    """

    def _compile_errors(self, code):
        from core.engine import IBCIEngine
        from core.kernel.issue import CompilerError
        from tests.conftest import _default_root

        engine = IBCIEngine(root_dir=_default_root(), auto_sniff=False)
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
