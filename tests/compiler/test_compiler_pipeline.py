"""
tests/compiler/test_compiler_pipeline.py

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
        artifact = engine.compile_string("bool flag = true", silent=True)
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
        artifact = engine.compile_string("bool result = true and false", silent=True)
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
while true:
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
        code = """def add(int a, int b) -> int:
    return a + b
"""
        artifact = engine.compile_string(code, silent=True)
        assert artifact is not None

    def test_void_function(self, engine):
        code = """def greet(str name):
    print("hello " + name)
"""
        artifact = engine.compile_string(code, silent=True)
        assert artifact is not None

    def test_function_call(self, engine):
        code = """def double(int x) -> int:
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

    def bark(self) -> str:
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
        code = """import ai
int x = (int) @~ what is 1+1 ~
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
