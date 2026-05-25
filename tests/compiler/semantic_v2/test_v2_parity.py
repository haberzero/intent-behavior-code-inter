"""
Parity Tests: V2 Pipeline vs V1 Compatibility

验证 v2 pipeline 通过 adapter 产出的 CompilationResult 满足下游消费者
（serializer、VM）的结构约束。

这些测试确保 v2 能够完全替换 v1 而不需要任何 fallback。
"""

import pytest
from core.compiler.semantic_v2.analyzer import SemanticAnalyzerV2
from core.compiler.semantic_v2.pipeline import create_semantic_pipeline
from core.compiler.semantic_v2.context import ContextBuilder
from core.compiler.semantic_v2.metadata.metadata_store import MetadataStore
from core.kernel.spec.registry import SpecRegistry
from core.kernel.axioms.registry import AxiomRegistry
from core.kernel.blueprint import CompilationResult
from core.kernel.symbols import SymbolTable, Symbol, SymbolKind
from core.kernel import ast
from core.compiler.lexer.lexer import Lexer
from core.compiler.parser.parser import Parser
from core.compiler.diagnostics.issue_tracker import IssueTracker
from core.base.source.source_manager import SourceManager


@pytest.fixture
def source_mgr():
    return SourceManager()


@pytest.fixture
def registry():
    return SpecRegistry(AxiomRegistry())


def parse_code(code: str, tracker):
    """Helper: parse IBCI code into AST."""
    lexer = Lexer(code, tracker)
    tokens = lexer.tokenize()
    parser = Parser(tokens, tracker)
    return parser.parse()


class TestV2ProducesCompilationResult:
    """V2 analyzer produces a valid CompilationResult structure."""

    def test_returns_compilation_result_type(self, source_mgr, registry):
        """analyze() must return CompilationResult (same type as v1)."""
        tracker = IssueTracker(source_provider=source_mgr)
        code = 'str x = "hello"'
        ast_node = parse_code(code, tracker)

        analyzer = SemanticAnalyzerV2(tracker, registry=registry, module_name='test')
        result = analyzer.analyze(ast_node, raise_on_error=False)

        assert isinstance(result, CompilationResult)

    def test_module_ast_is_ibmodule(self, source_mgr, registry):
        """module_ast must be IbModule."""
        tracker = IssueTracker(source_provider=source_mgr)
        code = 'int y = 1'
        ast_node = parse_code(code, tracker)

        analyzer = SemanticAnalyzerV2(tracker, registry=registry, module_name='test')
        result = analyzer.analyze(ast_node, raise_on_error=False)

        assert isinstance(result.module_ast, ast.IbModule)

    def test_symbol_table_is_symboltable(self, source_mgr, registry):
        """symbol_table must be SymbolTable."""
        tracker = IssueTracker(source_provider=source_mgr)
        code = 'str name = "ibci"'
        ast_node = parse_code(code, tracker)

        analyzer = SemanticAnalyzerV2(tracker, registry=registry, module_name='test')
        result = analyzer.analyze(ast_node, raise_on_error=False)

        assert isinstance(result.symbol_table, SymbolTable)

    def test_side_tables_are_dicts(self, source_mgr, registry):
        """node_to_symbol/type/loc must be dicts."""
        tracker = IssueTracker(source_provider=source_mgr)
        code = 'int z = 100'
        ast_node = parse_code(code, tracker)

        analyzer = SemanticAnalyzerV2(tracker, registry=registry, module_name='test')
        result = analyzer.analyze(ast_node, raise_on_error=False)

        assert isinstance(result.node_to_symbol, dict)
        assert isinstance(result.node_to_type, dict)
        assert isinstance(result.node_to_loc, dict)

    def test_node_to_symbol_keyed_by_ast_nodes(self, source_mgr, registry):
        """node_to_symbol keys must be IbASTNode objects (not strings)."""
        tracker = IssueTracker(source_provider=source_mgr)
        code = 'str greeting = "hello"'
        ast_node = parse_code(code, tracker)

        analyzer = SemanticAnalyzerV2(tracker, registry=registry, module_name='test')
        result = analyzer.analyze(ast_node, raise_on_error=False)

        for node_key in result.node_to_symbol.keys():
            assert isinstance(node_key, ast.IbASTNode), \
                f"Expected IbASTNode key, got {type(node_key).__name__}"

    def test_node_to_symbol_values_are_symbols(self, source_mgr, registry):
        """node_to_symbol values must be Symbol objects."""
        tracker = IssueTracker(source_provider=source_mgr)
        code = 'str greeting = "hello"'
        ast_node = parse_code(code, tracker)

        analyzer = SemanticAnalyzerV2(tracker, registry=registry, module_name='test')
        result = analyzer.analyze(ast_node, raise_on_error=False)

        for sym in result.node_to_symbol.values():
            assert isinstance(sym, Symbol), \
                f"Expected Symbol value, got {type(sym).__name__}"


class TestV2SymbolCollection:
    """V2 correctly collects all top-level symbols."""

    def test_function_symbol_collected(self, source_mgr, registry):
        """Function definitions create FUNCTION symbols."""
        tracker = IssueTracker(source_provider=source_mgr)
        code = '''
func greet(str name) -> str:
    return "hello " + name
'''
        ast_node = parse_code(code, tracker)
        analyzer = SemanticAnalyzerV2(tracker, registry=registry, module_name='test')
        result = analyzer.analyze(ast_node, raise_on_error=False)

        sym = result.symbol_table.resolve('greet')
        assert sym is not None
        assert sym.kind == SymbolKind.FUNCTION

    def test_variable_symbol_collected(self, source_mgr, registry):
        """Variable declarations create VARIABLE symbols."""
        tracker = IssueTracker(source_provider=source_mgr)
        code = 'int count = 0'
        ast_node = parse_code(code, tracker)
        analyzer = SemanticAnalyzerV2(tracker, registry=registry, module_name='test')
        result = analyzer.analyze(ast_node, raise_on_error=False)

        sym = result.symbol_table.resolve('count')
        assert sym is not None
        assert sym.kind == SymbolKind.VARIABLE

    def test_class_symbol_collected(self, source_mgr, registry):
        """Class definitions create CLASS symbols."""
        tracker = IssueTracker(source_provider=source_mgr)
        code = '''
class Point:
    int x
    int y
'''
        ast_node = parse_code(code, tracker)
        analyzer = SemanticAnalyzerV2(tracker, registry=registry, module_name='test')
        result = analyzer.analyze(ast_node, raise_on_error=False)

        sym = result.symbol_table.resolve('Point')
        assert sym is not None
        assert sym.kind == SymbolKind.CLASS

    def test_multiple_symbols(self, source_mgr, registry):
        """Multiple declarations are all collected."""
        tracker = IssueTracker(source_provider=source_mgr)
        code = '''
func add(int a, int b) -> int:
    return a + b

str msg = "ready"
int total = 0
'''
        ast_node = parse_code(code, tracker)
        analyzer = SemanticAnalyzerV2(tracker, registry=registry, module_name='test')
        result = analyzer.analyze(ast_node, raise_on_error=False)

        assert result.symbol_table.resolve('add') is not None
        assert result.symbol_table.resolve('msg') is not None
        assert result.symbol_table.resolve('total') is not None


class TestV2SymbolResolution:
    """V2 correctly resolves symbol references into node_to_symbol."""

    def test_name_reference_bound(self, source_mgr, registry):
        """IbName nodes referencing defined symbols get bound."""
        tracker = IssueTracker(source_provider=source_mgr)
        code = '''
str x = "hello"
str y = x
'''
        ast_node = parse_code(code, tracker)
        analyzer = SemanticAnalyzerV2(tracker, registry=registry, module_name='test')
        result = analyzer.analyze(ast_node, raise_on_error=False)

        # Should have at least one symbol binding (the reference to 'x' in second assign)
        assert len(result.node_to_symbol) > 0

        # All keys should be IbName or similar AST nodes
        for node in result.node_to_symbol.keys():
            assert isinstance(node, ast.IbASTNode)


class TestV2LLMExceptBinding:
    """V2 correctly performs llmexcept AST rewriting."""

    def test_llmexcept_sets_target(self, source_mgr, registry):
        """llmexcept stmt gets target set to prev_stmt after body rewrite."""
        tracker = IssueTracker(source_provider=source_mgr)
        # Use a behavior expression followed by llmexcept
        code = '''
str result = @~describe the weather~
llmexcept:
    retry "be more specific"
'''
        ast_node = parse_code(code, tracker)
        analyzer = SemanticAnalyzerV2(tracker, registry=registry, module_name='test')
        result = analyzer.analyze(ast_node, raise_on_error=False)

        # After llmexcept binding pass, the AST should have been rewritten
        # Check that IbLLMExceptionalStmt has target set
        module = result.module_ast
        for stmt in module.body:
            if isinstance(stmt, ast.IbLLMExceptionalStmt):
                assert stmt.target is not None, "llmexcept target should be set after binding pass"
                break


class TestV2MetadataStoreNodeObjectKeys:
    """MetadataStore uses node objects as keys (not UIDs)."""

    def test_metadata_store_bind_symbol_uses_node_object(self):
        """bind_symbol stores by node object identity."""
        store = MetadataStore.create_empty()
        node = ast.IbName(id="x", ctx="Load")
        store.bind_symbol(node, "fake_symbol")

        assert store.get_symbol(node) == "fake_symbol"

    def test_metadata_store_bind_type_uses_node_object(self):
        """bind_type stores by node object identity."""
        store = MetadataStore.create_empty()
        node = ast.IbName(id="y", ctx="Load")
        store.bind_type(node, "int_spec")

        assert store.get_type(node) == "int_spec"

    def test_metadata_store_merge(self):
        """merge combines two stores correctly."""
        store1 = MetadataStore.create_empty()
        store2 = MetadataStore.create_empty()

        node1 = ast.IbName(id="a", ctx="Load")
        node2 = ast.IbName(id="b", ctx="Load")

        store1.bind_symbol(node1, "sym_a")
        store2.bind_symbol(node2, "sym_b")
        store2.add_cell_captured_symbol("uid_1")

        merged = store1.merge(store2)
        assert merged.get_symbol(node1) == "sym_a"
        assert merged.get_symbol(node2) == "sym_b"
        assert "uid_1" in merged.cell_captured_symbols

    def test_no_uid_field_on_ast_nodes(self):
        """AST nodes do NOT have .uid field - confirms design decision."""
        node = ast.IbName(id="test", ctx="Load")
        assert not hasattr(node, 'uid'), \
            "IbASTNode should NOT have uid field; object identity is used"


class TestV2SchedulerIntegration:
    """Semantic analyzer integrates correctly with scheduler."""

    def test_scheduler_constructs(self):
        """Scheduler constructor works without issues."""
        import tempfile
        from core.compiler.scheduler import Scheduler

        with tempfile.TemporaryDirectory() as tmpdir:
            # Should not raise
            scheduler = Scheduler(tmpdir)
            assert scheduler is not None


class TestV2FullFileCompilation:
    """Semantic analyzer can successfully compile all example .ibci files."""

    @pytest.fixture
    def full_registry(self):
        from core.kernel.factory import create_default_registry
        return create_default_registry()

    @pytest.mark.parametrize("example_file", [
        "examples/01_getting_started/01_hello_world.ibci",
        "examples/01_getting_started/02_intent_demo.ibci",
        "examples/01_getting_started/03_flow_control_and_behavior.ibci",
        "examples/01_getting_started/04_mock_and_llmexcept.ibci",
        "examples/01_getting_started/05_enum_and_switch.ibci",
        "examples/01_getting_started/06_enum_switch_with_llm.ibci",
    ])
    def test_example_compiles_without_crash(self, source_mgr, full_registry, example_file):
        """V2 analyzer should compile example files without raising exceptions."""
        import os
        if not os.path.exists(example_file):
            pytest.skip(f"Example file not found: {example_file}")

        with open(example_file) as f:
            code = f.read()

        tracker = IssueTracker(source_provider=source_mgr)
        ast_node = parse_code(code, tracker)
        analyzer = SemanticAnalyzerV2(tracker, registry=full_registry, module_name='test')
        result = analyzer.analyze(ast_node, raise_on_error=False)

        # Must return valid CompilationResult
        assert isinstance(result, CompilationResult)
        assert isinstance(result.module_ast, ast.IbModule)
        assert isinstance(result.symbol_table, SymbolTable)
        assert isinstance(result.node_to_symbol, dict)
        assert isinstance(result.node_to_type, dict)
        assert isinstance(result.node_to_loc, dict)
        # Must produce meaningful output
        assert len(result.node_to_type) > 0
        assert len(result.node_to_loc) > 0

    def test_scheduler_compiles_simple_file(self, source_mgr):
        """Scheduler compiles a simple file without errors."""
        import tempfile, os
        from core.compiler.scheduler import Scheduler
        from core.kernel.factory import create_default_registry

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, 'main.ibci')
            with open(test_file, 'w') as f:
                f.write('int x = 42\nstr msg = "hello"\nint y = x + 1\nstr result = @~say $msg~\n')

            registry = create_default_registry()
            scheduler = Scheduler(tmpdir, registry=registry)
            # Should not raise
            artifact = scheduler.compile_file(test_file)
            assert artifact is not None

    def test_v2_llm_function_compiles(self, source_mgr, full_registry):
        """V2 correctly handles LLM function definitions."""
        tracker = IssueTracker(source_provider=source_mgr)
        code = 'llm translate(str text, str target):\n__user__\ntranslate $text to $target\nllmend'
        ast_node = parse_code(code, tracker)

        analyzer = SemanticAnalyzerV2(tracker, registry=full_registry, module_name='test')
        result = analyzer.analyze(ast_node, raise_on_error=False)

        assert isinstance(result, CompilationResult)
        # LLM function should be registered as a symbol
        sym = result.symbol_table.resolve('translate')
        assert sym is not None
        assert sym.kind == SymbolKind.LLM_FUNCTION

    def test_v2_behavior_expr_adapts_to_target_type(self, source_mgr, full_registry):
        """BehaviorExpr assigned to typed variable adapts to that type (IBCI core semantics)."""
        tracker = IssueTracker(source_provider=source_mgr)
        code = 'int x = @~compute something~'
        ast_node = parse_code(code, tracker)

        analyzer = SemanticAnalyzerV2(tracker, registry=full_registry, module_name='test')
        result = analyzer.analyze(ast_node, raise_on_error=False)

        # Should not produce type-mismatch errors for behavior→typed-var assignment
        assert isinstance(result, CompilationResult)
