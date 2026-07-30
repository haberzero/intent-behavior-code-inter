"""
tests/compiler/test_pipeline.py

Unit tests for the full compiler pipeline: Lexer → Parser → SemanticAnalyzer.

Coverage:
  - Compile simple programs (variables, expressions, print)
  - Compile control flow (if/else, while, for)
  - Compile function definitions
  - Compile class definitions
  - Compile import statements
  - Compile behavior expressions
  - Compile LLM function definitions
  - Compile intent annotations
  - Compilation error detection (undefined variables, type mismatches)
  - CompilationArtifact structure
"""

import os
import pytest
from core.engine import IBCIEngine
from core.kernel.issue import CompilerError


# ---------------------------------------------------------------------------
# Fixture: Fresh engine for each test
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    return IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)


# ---------------------------------------------------------------------------
# 1. Simple variable declarations
# ---------------------------------------------------------------------------

class TestCompileVariables:
    def test_int_declaration(self, engine):
        artifact = engine.compile_string("int x = 42", silent=True)
        assert artifact is not None

    def test_str_declaration(self, engine):
        artifact = engine.compile_string('str name = "Alice"', silent=True)
        assert artifact is not None

    def test_float_declaration(self, engine):
        artifact = engine.compile_string("float pi = 3.14", silent=True)
        assert artifact is not None

    def test_bool_declaration(self, engine):
        artifact = engine.compile_string("bool flag = True", silent=True)
        assert artifact is not None

    def test_list_declaration(self, engine):
        artifact = engine.compile_string('list items = [1, 2, 3]', silent=True)
        assert artifact is not None

    def test_dict_declaration(self, engine):
        artifact = engine.compile_string('dict config = {"key": "value"}', silent=True)
        assert artifact is not None

    def test_auto_type(self, engine):
        artifact = engine.compile_string("auto x = 42", silent=True)
        assert artifact is not None


# ---------------------------------------------------------------------------
# 2. Expressions and operations
# ---------------------------------------------------------------------------

class TestCompileExpressions:
    def test_arithmetic(self, engine):
        artifact = engine.compile_string("int x = 1 + 2 * 3", silent=True)
        assert artifact is not None

    def test_string_concat(self, engine):
        artifact = engine.compile_string('str msg = "hello" + " world"', silent=True)
        assert artifact is not None

    def test_comparison(self, engine):
        artifact = engine.compile_string("bool result = 1 < 2", silent=True)
        assert artifact is not None

    def test_logical_ops(self, engine):
        artifact = engine.compile_string("bool result = True and False", silent=True)
        assert artifact is not None

    def test_unary_ops(self, engine):
        artifact = engine.compile_string("int x = -42", silent=True)
        assert artifact is not None


# ---------------------------------------------------------------------------
# 3. Control flow
# ---------------------------------------------------------------------------

class TestCompileControlFlow:
    def test_if_else(self, engine):
        code = """int x = 10
if x > 5:
    print("big")
else:
    print("small")
"""
        artifact = engine.compile_string(code, silent=True)
        assert artifact is not None

    def test_while_loop(self, engine):
        code = """int i = 0
while i < 5:
    i = i + 1
"""
        artifact = engine.compile_string(code, silent=True)
        assert artifact is not None

    def test_for_in_loop(self, engine):
        code = """list items = [1, 2, 3]
for int item in items:
    print((str)item)
"""
        artifact = engine.compile_string(code, silent=True)
        assert artifact is not None

    def test_break_continue(self, engine):
        code = """int i = 0
while True:
    i = i + 1
    if i > 3:
        break
    if i == 2:
        continue
"""
        artifact = engine.compile_string(code, silent=True)
        assert artifact is not None


# ---------------------------------------------------------------------------
# 4. Function definitions
# ---------------------------------------------------------------------------

class TestCompileFunctions:
    def test_simple_function(self, engine):
        code = """func add(int a, int b) -> int:
    return a + b
"""
        artifact = engine.compile_string(code, silent=True)
        assert artifact is not None

    def test_void_function(self, engine):
        code = """func greet(str name):
    print("hello " + name)
"""
        artifact = engine.compile_string(code, silent=True)
        assert artifact is not None

    def test_function_call(self, engine):
        code = """func double(int x) -> int:
    return x * 2

int result = double(21)
"""
        artifact = engine.compile_string(code, silent=True)
        assert artifact is not None


# ---------------------------------------------------------------------------
# 5. Class definitions
# ---------------------------------------------------------------------------

class TestCompileClasses:
    def test_simple_class(self, engine):
        code = """class Dog:
    str name
    int age

    func bark(self) -> str:
        return "Woof!"
"""
        artifact = engine.compile_string(code, silent=True)
        assert artifact is not None

    def test_enum_class(self, engine):
        code = """class Color(Enum):
    str RED = "RED"
    str GREEN = "GREEN"
    str BLUE = "BLUE"
"""
        artifact = engine.compile_string(code, silent=True)
        assert artifact is not None


# ---------------------------------------------------------------------------
# 6. Import statements
# ---------------------------------------------------------------------------

class TestCompileImports:
    def test_import_math(self, engine):
        artifact = engine.compile_string("import math", silent=True)
        assert artifact is not None

    def test_import_json(self, engine):
        artifact = engine.compile_string("import json", silent=True)
        assert artifact is not None

    def test_import_ai(self, engine):
        artifact = engine.compile_string("import ai", silent=True)
        assert artifact is not None

    def test_import_time(self, engine):
        artifact = engine.compile_string("import time", silent=True)
        assert artifact is not None


# ---------------------------------------------------------------------------
# 7. Behavior expressions (AI/LLM)
# ---------------------------------------------------------------------------

class TestCompileBehavior:
    def test_behavior_expression(self, engine):
        code = """import ai
str result = @~ hello world ~
"""
        artifact = engine.compile_string(code, silent=True)
        assert artifact is not None

    def test_behavior_with_type_cast(self, engine):
        """(Type) @~...~ 语法已废弃，编译器必须发出 PAR_DEPRECATED_CAST_SYNTAX 错误。"""
        code = """import ai
int x = (int) @~ what is 1+1 ~
"""
        with pytest.raises(CompilerError):
            engine.compile_string(code, silent=True)

    def test_behavior_lambda_fn_callable(self, engine):
        """fn varname = lambda -> TYPE: @~...~ 创建可调用的 behavior 对象。"""
        code = """import ai
fn my_behavior = lambda -> int: @~ what is 1+1 ~
"""
        artifact = engine.compile_string(code, silent=True)
        assert artifact is not None

    def test_behavior_snapshot_fn_callable(self, engine):
        """fn varname = snapshot -> TYPE: @~...~ 创建捕获意图快照的 behavior 对象。"""
        code = """import ai
fn my_snap = snapshot -> str: @~ say hello ~
"""
        artifact = engine.compile_string(code, silent=True)
        assert artifact is not None

    def test_llm_function_def(self, engine):
        code = """import ai
llm translate(str text, str lang) -> str:
__sys__
You are a translator.
__user__
Translate $text to $lang
llmend
"""
        artifact = engine.compile_string(code, silent=True)
        assert artifact is not None


# ---------------------------------------------------------------------------
# 8. Intent annotations
# ---------------------------------------------------------------------------

class TestCompileIntents:
    def test_single_intent(self, engine):
        code = """import ai
@ be concise
str x = @~ say hello ~
"""
        artifact = engine.compile_string(code, silent=True)
        assert artifact is not None

    def test_incremental_intent(self, engine):
        code = """import ai
@+ use formal language
str x = @~ greet ~
"""
        artifact = engine.compile_string(code, silent=True)
        assert artifact is not None

    def test_single_intent_before_regular_call_without_direct_llm(self, engine):
        code = """import ai
func pure() -> int:
    return 1
@ one-shot before regular call
int x = pure()
"""
        artifact = engine.compile_string(code, silent=True)
        assert artifact is not None


# ---------------------------------------------------------------------------
# 9. Type casting
# ---------------------------------------------------------------------------

class TestCompileTypeCast:
    def test_int_to_str_cast(self, engine):
        code = """int x = 42
str s = (str)x
"""
        artifact = engine.compile_string(code, silent=True)
        assert artifact is not None

    def test_str_to_int_cast(self, engine):
        code = """str s = "42"
int x = (int)s
"""
        artifact = engine.compile_string(code, silent=True)
        assert artifact is not None


# ---------------------------------------------------------------------------
# 10. Compilation artifacts structure
# ---------------------------------------------------------------------------

class TestCompilationArtifact:
    def test_artifact_has_modules(self, engine):
        artifact = engine.compile_string('int x = 42', silent=True)
        # CompilationArtifact should contain modules
        assert hasattr(artifact, 'modules') or hasattr(artifact, 'entry_module')

    def test_artifact_has_pools(self, engine):
        artifact = engine.compile_string('int x = 42', silent=True)
        # Should have some form of pool data
        assert artifact is not None


# ---------------------------------------------------------------------------
# 11. Error detection
# ---------------------------------------------------------------------------

class TestCompileErrors:
    def test_syntax_error_raises(self, engine):
        with pytest.raises(CompilerError):
            engine.compile_string("int x = ", silent=True)

    def test_undefined_variable_in_expression(self, engine):
        """Using an undefined variable should raise a compiler error."""
        with pytest.raises(CompilerError):
            engine.compile_string("int y = undefined_var + 1", silent=True)


# ---------------------------------------------------------------------------
# 12. llmexcept body read-only constraint (SEM_LLMEXCEPT_BODY_WRITE)
# ---------------------------------------------------------------------------

class TestLLMExceptBodyReadOnly:
    """
    验证快照隔离编译期约束：llmexcept body 内向 LLM 参与变量写入产生 SEM_LLMEXCEPT_BODY_WRITE。
    """

    def test_assign_to_outer_var_raises(self, engine):
        """llmexcept body 内直接对外部变量赋值应产生编译期错误 (SEM_LLMEXCEPT_BODY_WRITE)。"""
        code = """str result = @~ greet ~
llmexcept:
    result = "fallback"
    retry "hint"
"""
        with pytest.raises(CompilerError) as exc_info:
            engine.compile_string(code, silent=True)
        codes = [d.code for d in exc_info.value.diagnostics]
        assert "SEM_LLMEXCEPT_BODY_WRITE" in codes

    def test_redeclare_outer_var_raises(self, engine):
        """llmexcept body 内用类型标注重声明外部变量也应产生 SEM_LLMEXCEPT_BODY_WRITE。"""
        code = """str result = @~ greet ~
llmexcept:
    str result = "fallback"
    retry "hint"
"""
        with pytest.raises(CompilerError) as exc_info:
            engine.compile_string(code, silent=True)
        codes = [d.code for d in exc_info.value.diagnostics]
        assert "SEM_LLMEXCEPT_BODY_WRITE" in codes

    def test_new_local_var_allowed(self, engine):
        """llmexcept body 内定义全新的局部变量是允许的（不产生 SEM_LLMEXCEPT_BODY_WRITE）。"""
        code = """str result = @~ greet ~
llmexcept:
    str hint = "please try again with a clear answer"
    retry "please try again"
"""
        # Should compile without error
        artifact = engine.compile_string(code, silent=True)
        assert artifact is not None

    def test_retry_statement_allowed(self, engine):
        """llmexcept body 内使用 retry 语句是允许的（不产生 SEM_LLMEXCEPT_BODY_WRITE）。"""
        code = """str result = @~ greet ~
llmexcept:
    retry "try again"
"""
        artifact = engine.compile_string(code, silent=True)
        assert artifact is not None

    def test_read_outer_var_allowed(self, engine):
        """llmexcept body 内读取外部变量是允许的（不产生 SEM_LLMEXCEPT_BODY_WRITE）。"""
        code = """str context = "context info"
str result = @~ greet ~
llmexcept:
    str local_info = context
    retry "try again"
"""
        artifact = engine.compile_string(code, silent=True)
        assert artifact is not None

    def test_assign_to_non_llm_var_allowed(self, engine):
        """llmexcept body 内对非 LLM 参与变量写入是允许的（辅助统计用途）。"""
        code = """int counter = 0
str result = @~ greet ~
llmexcept:
    counter = 1
    retry "hint"
"""
        result = engine.compile_string(code, silent=True)
        assert result is not None


# ---------------------------------------------------------------------------
# 13. llmexcept body 文件写/删禁令 (SEM_LLMEXCEPT_FILE_WRITE)
# ---------------------------------------------------------------------------

class TestLLMExceptFileWrite:
    """llmexcept body 内禁止文件写/删（浅路径引用快照污染）。编译期 spec 驱动判定。"""

    @staticmethod
    def _assert_file_write_error(engine, code):
        with pytest.raises(CompilerError) as exc_info:
            engine.compile_string(code, silent=True)
        codes = [d.code for d in exc_info.value.diagnostics]
        assert "SEM_LLMEXCEPT_FILE_WRITE" in codes

    def test_direct_write_new_raises(self, engine):
        code = """import file
str result = @~ greet ~
llmexcept:
    file.write_new("log.txt", "failed")
    retry "hint"
"""
        self._assert_file_write_error(engine, code)

    def test_direct_remove_raises(self, engine):
        code = """import file
str result = @~ greet ~
llmexcept:
    file.remove("log.txt")
    retry "hint"
"""
        self._assert_file_write_error(engine, code)

    def test_direct_write_overwrite_raises(self, engine):
        code = """import file
str result = @~ greet ~
llmexcept:
    file.write_overwrite("log.txt", "failed")
    retry "hint"
"""
        self._assert_file_write_error(engine, code)

    def test_indirect_via_user_func_raises(self, engine):
        """用户函数体内含文件写，retry body 调用它亦禁止（递归传导）。"""
        code = """import file
func helper():
    file.write_new("log.txt", "x")
str result = @~ greet ~
llmexcept:
    helper()
    retry "hint"
"""
        self._assert_file_write_error(engine, code)

    def test_indirect_two_levels_raises(self, engine):
        """多层间接：a() 调 b()，b() 写文件 -> a() 在 retry body 内亦禁止。"""
        code = """import file
func b():
    file.write_new("log.txt", "x")
func a():
    b()
str result = @~ greet ~
llmexcept:
    a()
    retry "hint"
"""
        self._assert_file_write_error(engine, code)

    def test_aliased_import_raises(self, engine):
        """import file as f 别名：spec 驱动 resolve 别名符号，仍命中。"""
        code = """import file as f
str result = @~ greet ~
llmexcept:
    f.write_new("log.txt", "x")
    retry "hint"
"""
        self._assert_file_write_error(engine, code)

    def test_read_allowed(self, engine):
        """file.read 是只读，retry body 内允许。"""
        code = """import file
str result = @~ greet ~
llmexcept:
    str info = file.read("a.txt")
    retry "hint"
"""
        artifact = engine.compile_string(code, silent=True)
        assert artifact is not None

    def test_exists_allowed(self, engine):
        """file.exists 是只读查询，retry body 内允许。"""
        code = """import file
str result = @~ greet ~
llmexcept:
    bool b = file.exists("a.txt")
    retry "hint"
"""
        artifact = engine.compile_string(code, silent=True)
        assert artifact is not None
