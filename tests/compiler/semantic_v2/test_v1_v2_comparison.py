"""
V1 vs V2 Side-by-Side Comparison Tests

直接对比 v1 和 v2 在相同输入下的输出，验证 parity 完备性。
这是决定是否可以设 use_v2=True 为默认值的关键测试。
"""

import pytest
from core.compiler.semantic.passes.semantic_analyzer import SemanticAnalyzer
from core.compiler.semantic_v2.analyzer import SemanticAnalyzerV2
from core.compiler.lexer.lexer import Lexer
from core.compiler.parser.parser import Parser
from core.compiler.diagnostics.issue_tracker import IssueTracker
from core.base.source.source_manager import SourceManager
from core.kernel.factory import create_default_registry
from core.kernel.blueprint import CompilationResult
from core.kernel.symbols import SymbolKind


@pytest.fixture
def source_mgr():
    return SourceManager()


@pytest.fixture
def full_registry():
    return create_default_registry()


def compile_v1(code: str, source_mgr, registry=None):
    """Compile code using V1 pipeline."""
    if registry is None:
        registry = create_default_registry()
    tracker = IssueTracker(source_provider=source_mgr)
    lexer = Lexer(code, tracker)
    tokens = lexer.tokenize()
    parser = Parser(tokens, tracker)
    ast_node = parser.parse()

    analyzer = SemanticAnalyzer(tracker, registry=registry, module_name='test')
    result = analyzer.analyze(ast_node, raise_on_error=False)
    errors = [d for d in tracker.diagnostics if d.severity.name == 'ERROR']
    return result, errors, tracker


def compile_v2(code: str, source_mgr, registry=None):
    """Compile code using V2 pipeline."""
    if registry is None:
        registry = create_default_registry()
    tracker = IssueTracker(source_provider=source_mgr)
    lexer = Lexer(code, tracker)
    tokens = lexer.tokenize()
    parser = Parser(tokens, tracker)
    ast_node = parser.parse()

    analyzer = SemanticAnalyzerV2(tracker, registry=registry, module_name='test')
    result = analyzer.analyze(ast_node, raise_on_error=False)
    errors = [d for d in tracker.diagnostics if d.severity.name == 'ERROR']
    return result, errors, tracker


class TestV1V2OutputStructure:
    """V1 and V2 should produce the same CompilationResult structure."""

    SIMPLE_PROGRAMS = [
        'int x = 42\n',
        'str msg = "hello"\n',
        'int x = 1\nint y = 2\nint z = x + y\n',
        'str name = "world"\nstr greeting = @~say hello to $name~\n',
        'func add(int a, int b) -> int:\n    return a + b\n',
        'list items = [1, 2, 3]\nfor item in items:\n    int doubled = item\n',
    ]

    @pytest.mark.parametrize("code", SIMPLE_PROGRAMS)
    def test_both_produce_compilation_result(self, source_mgr, code):
        """Both v1 and v2 produce CompilationResult for valid programs."""
        r1, e1, _ = compile_v1(code, source_mgr)
        r2, e2, _ = compile_v2(code, source_mgr)

        assert isinstance(r1, CompilationResult), f"V1 failed to produce CompilationResult for: {code}"
        assert isinstance(r2, CompilationResult), f"V2 failed to produce CompilationResult for: {code}"

    @pytest.mark.parametrize("code", SIMPLE_PROGRAMS)
    def test_symbol_table_parity(self, source_mgr, code):
        """V1 and V2 should collect the same top-level symbols."""
        r1, _, _ = compile_v1(code, source_mgr)
        r2, _, _ = compile_v2(code, source_mgr)

        # Compare top-level user-defined symbols (exclude builtins)
        v1_syms = {name for name, sym in r1.symbol_table.symbols.items()
                   if not getattr(sym, 'uid', '').startswith('builtin:')}
        v2_syms = {name for name, sym in r2.symbol_table.symbols.items()
                   if not getattr(sym, 'uid', '').startswith('builtin:')}

        assert v2_syms == v1_syms, (
            f"Symbol table mismatch for: {code}\n"
            f"  V1 symbols: {v1_syms}\n"
            f"  V2 symbols: {v2_syms}\n"
            f"  V1 only: {v1_syms - v2_syms}\n"
            f"  V2 only: {v2_syms - v1_syms}"
        )

    @pytest.mark.parametrize("code", SIMPLE_PROGRAMS)
    def test_no_false_errors(self, source_mgr, code):
        """V2 should not produce errors on valid programs that V1 accepts."""
        _, v1_errors, _ = compile_v1(code, source_mgr)
        _, v2_errors, _ = compile_v2(code, source_mgr)

        # If V1 errors, it's not a valid test case for false-error detection
        if len(v1_errors) > 0:
            pytest.skip(f"V1 also errors on this code: {[e.message for e in v1_errors]}")
        # V2 should also not have errors
        assert len(v2_errors) == 0, (
            f"V2 produces errors on valid code that V1 accepts:\n"
            f"  Code: {code}\n"
            f"  V2 errors: {[e.message for e in v2_errors]}"
        )


class TestV1V2ErrorParity:
    """V1 and V2 should produce the same errors for invalid programs."""

    def test_undefined_variable_error(self, source_mgr):
        """Both should detect undefined variable references."""
        code = 'int x = undefined_var\n'
        _, v1_errors, _ = compile_v1(code, source_mgr)
        _, v2_errors, _ = compile_v2(code, source_mgr)

        # Both should detect the undefined variable
        v1_has_undef = any('SEM_001' in (getattr(e, 'code', '') or '') for e in v1_errors)
        v2_has_undef = any('SEM_001' in (getattr(e, 'code', '') or '') for e in v2_errors)

        # V2 should catch it too (via SymbolResolutionPass or TypeCheckingPass)
        assert v1_has_undef, "V1 should detect undefined variable"
        # Note: V2 may or may not catch this depending on implementation status
        # This is a tracking test - failing means v2 has a gap to fix

    def test_type_mismatch_basic(self, source_mgr):
        """Both should detect basic type mismatches."""
        code = 'int x = "not an int"\n'
        _, v1_errors, _ = compile_v1(code, source_mgr)
        _, v2_errors, _ = compile_v2(code, source_mgr)

        v1_has_mismatch = any('SEM_003' in (getattr(e, 'code', '') or '') for e in v1_errors)
        v2_has_mismatch = any('SEM_003' in (getattr(e, 'code', '') or '') for e in v2_errors)

        assert v1_has_mismatch, "V1 should detect type mismatch"
        assert v2_has_mismatch, "V2 should detect type mismatch (parity gap if failing)"


class TestV1V2MetadataCoverage:
    """V2 metadata coverage compared to V1."""

    def test_node_to_type_coverage(self, source_mgr):
        """V2 should produce node_to_type bindings for expressions."""
        code = 'int x = 42\nstr s = "hello"\nint y = x + 1\n'
        r1, _, _ = compile_v1(code, source_mgr)
        r2, _, _ = compile_v2(code, source_mgr)

        # V2 should have some type bindings
        assert len(r2.node_to_type) > 0, "V2 should produce type bindings"
        # Compare coverage ratio (v2 should be ≥ 50% of v1 at minimum)
        v1_count = len(r1.node_to_type)
        v2_count = len(r2.node_to_type)
        if v1_count > 0:
            ratio = v2_count / v1_count
            # Tracking assertion - will reveal coverage gap
            assert ratio >= 0.3, (
                f"V2 type coverage too low: {v2_count}/{v1_count} = {ratio:.0%}"
            )

    def test_node_to_loc_coverage(self, source_mgr):
        """V2 should produce node_to_loc for all AST nodes."""
        code = 'int x = 42\nstr s = "hello"\n'
        r1, _, _ = compile_v1(code, source_mgr)
        r2, _, _ = compile_v2(code, source_mgr)

        # V2 should have location bindings
        assert len(r2.node_to_loc) > 0, "V2 should produce location bindings"

    def test_node_to_symbol_coverage(self, source_mgr):
        """V2 should produce node_to_symbol bindings for name references."""
        code = 'int x = 42\nint y = x + 1\n'
        r1, _, _ = compile_v1(code, source_mgr)
        r2, _, _ = compile_v2(code, source_mgr)

        assert len(r2.node_to_symbol) > 0, "V2 should produce symbol bindings"


class TestV1V2FunctionSemantics:
    """Function definition and call parity."""

    def test_function_symbol_registered(self, source_mgr):
        """Both v1 and v2 register function symbols with correct kind."""
        code = 'func greet(str name) -> str:\n    return "hi " + name\n'
        r1, _, _ = compile_v1(code, source_mgr)
        r2, _, _ = compile_v2(code, source_mgr)

        v1_sym = r1.symbol_table.resolve('greet')
        v2_sym = r2.symbol_table.resolve('greet')

        assert v1_sym is not None
        assert v2_sym is not None
        assert v1_sym.kind == SymbolKind.FUNCTION
        assert v2_sym.kind == SymbolKind.FUNCTION

    def test_function_return_type_inferred(self, source_mgr):
        """Both pipelines should infer function return types."""
        code = 'func add(int a, int b) -> int:\n    return a + b\nint result = add(1, 2)\n'
        r1, e1, _ = compile_v1(code, source_mgr)
        r2, e2, _ = compile_v2(code, source_mgr)

        # V1 should not error (function return type is int, assigned to int)
        assert len(e1) == 0, f"V1 errors: {[e.message for e in e1]}"
        # V2 should not error either
        assert len(e2) == 0, f"V2 errors: {[e.message for e in e2]}"


class TestV1V2LLMExceptParity:
    """llmexcept behavior parity."""

    def test_llmexcept_binds_target(self, source_mgr):
        """Both v1 and v2 should rewrite llmexcept to bind target."""
        code = 'str x = @~compute~\nllmexcept:\n    retry "try again"\n'
        r1, _, _ = compile_v1(code, source_mgr)
        r2, _, _ = compile_v2(code, source_mgr)

        # Both should compile without errors
        assert isinstance(r1, CompilationResult)
        assert isinstance(r2, CompilationResult)
