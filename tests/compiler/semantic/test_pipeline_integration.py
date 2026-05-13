"""
Integration tests for the complete semantic analyzer pipeline

Tests the full 6-pass pipeline execution
"""

import pytest
from core.kernel import ast
from core.kernel.symbols import SymbolTable
from core.kernel.registry import KernelRegistry
from core.compiler.semantic.pipeline import create_semantic_pipeline
from core.compiler.semantic.context import SemanticContext
from core.compiler.semantic.metadata import MetadataStore, SymbolTableContext, TypeEnvironment
from core.runtime.bootstrap.builtin_initializer import initialize_builtin_classes


@pytest.fixture
def registry():
    """Create a registry with built-in types"""
    reg = KernelRegistry()
    initialize_builtin_classes(reg)
    return reg


@pytest.fixture
def create_context(registry):
    """Factory for creating semantic contexts"""
    def _create(ast_node):
        symbol_table = SymbolTable()
        return SemanticContext(
            ast=ast_node,
            registry=registry,
            module_name="test_module",
            symbol_table=SymbolTableContext(symbol_table),
            type_environment=TypeEnvironment(),
            metadata=MetadataStore()
        )
    return _create


class TestSemanticPipeline:
    """Integration tests for the complete semantic pipeline"""

    def test_simple_function_pipeline(self, create_context, registry):
        """Test pipeline with a simple function"""
        # Create AST: def add(int a, int b) -> int: return a + b
        params = [
            ast.IbParameter(
                name="a",
                type_annotation=ast.IbName(id="int"),
                default_value=None
            ),
            ast.IbParameter(
                name="b",
                type_annotation=ast.IbName(id="int"),
                default_value=None
            )
        ]
        body = [
            ast.IbReturn(
                value=ast.IbBinOp(
                    left=ast.IbName(id="a"),
                    op=ast.BinOpType.ADD,
                    right=ast.IbName(id="b")
                )
            )
        ]
        func_def = ast.IbFunctionDef(
            name="add",
            params=params,
            body=body,
            returns=registry.resolve("int"),
            decorators=[]
        )
        module = ast.IbModule(body=[func_def], name="test")

        # Create context and pipeline
        context = create_context(module)
        pipeline = create_semantic_pipeline()

        # Run pipeline
        result = pipeline.run(context)

        # Verify success
        assert result.success, f"Pipeline failed with diagnostics: {result.diagnostics}"

        # Verify symbol was collected
        symbol = result.context.symbol_table.current.lookup("add")
        assert symbol is not None
        assert symbol.name == "add"

    def test_simple_class_pipeline(self, create_context, registry):
        """Test pipeline with a simple class"""
        # Create AST: class Point: int x; int y
        class_body = [
            ast.IbAssign(
                targets=[
                    ast.IbTypeAnnotatedExpr(
                        target=ast.IbName(id="x"),
                        annotation=ast.IbName(id="int")
                    )
                ],
                value=ast.IbInteger(value=0)
            ),
            ast.IbAssign(
                targets=[
                    ast.IbTypeAnnotatedExpr(
                        target=ast.IbName(id="y"),
                        annotation=ast.IbName(id="int")
                    )
                ],
                value=ast.IbInteger(value=0)
            )
        ]
        class_def = ast.IbClassDef(
            name="Point",
            bases=[],
            body=class_body,
            decorators=[]
        )
        module = ast.IbModule(body=[class_def], name="test")

        # Create context and pipeline
        context = create_context(module)
        pipeline = create_semantic_pipeline()

        # Run pipeline
        result = pipeline.run(context)

        # Verify success
        assert result.success, f"Pipeline failed with diagnostics: {result.diagnostics}"

        # Verify class symbol
        symbol = result.context.symbol_table.current.lookup("Point")
        assert symbol is not None

    def test_variable_assignment_pipeline(self, create_context, registry):
        """Test pipeline with variable assignments"""
        # Create AST: int x = 42; str y = "hello"
        assigns = [
            ast.IbAssign(
                targets=[
                    ast.IbTypeAnnotatedExpr(
                        target=ast.IbName(id="x"),
                        annotation=ast.IbName(id="int")
                    )
                ],
                value=ast.IbInteger(value=42)
            ),
            ast.IbAssign(
                targets=[
                    ast.IbTypeAnnotatedExpr(
                        target=ast.IbName(id="y"),
                        annotation=ast.IbName(id="str")
                    )
                ],
                value=ast.IbString(value="hello")
            )
        ]
        module = ast.IbModule(body=assigns, name="test")

        # Create context and pipeline
        context = create_context(module)
        pipeline = create_semantic_pipeline()

        # Run pipeline
        result = pipeline.run(context)

        # Verify success
        assert result.success, f"Pipeline failed with diagnostics: {result.diagnostics}"

        # Verify symbols
        x_sym = result.context.symbol_table.current.lookup("x")
        y_sym = result.context.symbol_table.current.lookup("y")
        assert x_sym is not None
        assert y_sym is not None

    def test_type_error_detection(self, create_context, registry):
        """Test that pipeline detects type errors"""
        # Create AST: int x = "hello"  (type mismatch)
        assign = ast.IbAssign(
            targets=[
                ast.IbTypeAnnotatedExpr(
                    target=ast.IbName(id="x"),
                    annotation=ast.IbName(id="int")
                )
            ],
            value=ast.IbString(value="hello")
        )
        module = ast.IbModule(body=[assign], name="test")

        # Create context and pipeline
        context = create_context(module)
        pipeline = create_semantic_pipeline()

        # Run pipeline
        result = pipeline.run(context)

        # Verify error was detected
        # Note: Depending on implementation, this might still succeed but with diagnostics
        assert len(result.diagnostics) > 0

    def test_undefined_symbol_detection(self, create_context, registry):
        """Test that pipeline detects undefined symbols"""
        # Create AST: int x = y  (y is undefined)
        assign = ast.IbAssign(
            targets=[
                ast.IbTypeAnnotatedExpr(
                    target=ast.IbName(id="x"),
                    annotation=ast.IbName(id="int")
                )
            ],
            value=ast.IbName(id="y")
        )
        module = ast.IbModule(body=[assign], name="test")

        # Create context and pipeline
        context = create_context(module)
        pipeline = create_semantic_pipeline()

        # Run pipeline
        result = pipeline.run(context)

        # Verify error was detected
        assert len(result.diagnostics) > 0

    def test_empty_module_pipeline(self, create_context):
        """Test pipeline with empty module"""
        module = ast.IbModule(body=[], name="test")

        # Create context and pipeline
        context = create_context(module)
        pipeline = create_semantic_pipeline()

        # Run pipeline
        result = pipeline.run(context)

        # Verify success
        assert result.success
        assert len(result.diagnostics) == 0

    def test_pipeline_metadata_collection(self, create_context, registry):
        """Test that pipeline collects metadata from all passes"""
        # Simple function
        func_def = ast.IbFunctionDef(
            name="test_func",
            params=[],
            body=[ast.IbPass()],
            returns=registry.resolve("void"),
            decorators=[]
        )
        module = ast.IbModule(body=[func_def], name="test")

        # Create context and pipeline
        context = create_context(module)
        pipeline = create_semantic_pipeline()

        # Run pipeline
        result = pipeline.run(context)

        # Verify metadata was collected from all passes
        assert len(result.metadata) > 0
        # Should have entries for each pass
        assert any("SymbolCollectionPass" in key for key in result.metadata.keys())
        assert any("SymbolResolutionPass" in key for key in result.metadata.keys())
        assert any("TypeCheckingPass" in key for key in result.metadata.keys())

    def test_pipeline_run_until_error(self, create_context, registry):
        """Test run_until_error stops at first error"""
        # Create problematic AST
        assign = ast.IbAssign(
            targets=[
                ast.IbTypeAnnotatedExpr(
                    target=ast.IbName(id="x"),
                    annotation=ast.IbName(id="int")
                )
            ],
            value=ast.IbName(id="undefined_var")  # Will cause error in resolution
        )
        module = ast.IbModule(body=[assign], name="test")

        # Create context and pipeline
        context = create_context(module)
        pipeline = create_semantic_pipeline()

        # Run until error
        result = pipeline.run_until_error(context)

        # Should have stopped at some point
        assert not result.success or len(result.diagnostics) > 0
