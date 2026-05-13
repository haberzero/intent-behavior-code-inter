"""
Unit tests for SymbolCollectionPass

Tests the first pass of semantic_v2 pipeline: symbol collection
"""

import pytest
from core.kernel import ast
from core.kernel.symbols import SymbolTable, SymbolKind
from core.kernel.registry import KernelRegistry
from core.compiler.semantic_v2.passes.symbol_collection_pass import SymbolCollectionPass
from core.compiler.semantic_v2.context import SemanticContext
from core.compiler.semantic_v2.metadata import MetadataStore, SymbolTableContext, TypeEnvironment
from core.runtime.bootstrap.builtin_initializer import initialize_builtin_classes


@pytest.fixture
def registry():
    """Create a registry with built-in types"""
    reg = KernelRegistry()
    initialize_builtin_classes(reg)
    return reg


@pytest.fixture
def base_context(registry):
    """Create a base semantic context for testing"""
    symbol_table = SymbolTable()
    return SemanticContext(
        ast=ast.IbModule(body=[], name="test_module"),
        registry=registry,
        module_name="test_module",
        symbol_table=SymbolTableContext(symbol_table),
        type_environment=TypeEnvironment(),
        metadata=MetadataStore()
    )


class TestSymbolCollectionPass:
    """Tests for SymbolCollectionPass"""

    def test_collect_function_definition(self, base_context, registry):
        """Test collecting a simple function definition"""
        # Create AST: def foo(): pass
        func_def = ast.IbFunctionDef(
            name="foo",
            params=[],
            body=[ast.IbPass()],
            returns=registry.resolve("void"),
            decorators=[]
        )
        module = ast.IbModule(body=[func_def], name="test")

        context = base_context.with_symbol_table(
            base_context.symbol_table.with_current(SymbolTable())
        )
        context = context._replace(ast=module)

        # Run pass
        pass_instance = SymbolCollectionPass()
        result = pass_instance.run(context)

        # Verify
        assert result.success
        assert len(result.diagnostics) == 0

        # Check symbol was added
        symbol = context.symbol_table.current.lookup("foo")
        assert symbol is not None
        assert symbol.name == "foo"
        assert symbol.kind == SymbolKind.FUNCTION

    def test_collect_class_definition(self, base_context, registry):
        """Test collecting a simple class definition"""
        # Create AST: class MyClass: pass
        class_def = ast.IbClassDef(
            name="MyClass",
            bases=[],
            body=[ast.IbPass()],
            decorators=[]
        )
        module = ast.IbModule(body=[class_def], name="test")

        context = base_context.with_symbol_table(
            base_context.symbol_table.with_current(SymbolTable())
        )
        context = context._replace(ast=module)

        # Run pass
        pass_instance = SymbolCollectionPass()
        result = pass_instance.run(context)

        # Verify
        assert result.success

        # Check symbol was added
        symbol = context.symbol_table.current.lookup("MyClass")
        assert symbol is not None
        assert symbol.name == "MyClass"
        assert symbol.kind == SymbolKind.CLASS

    def test_collect_variable_with_type_annotation(self, base_context, registry):
        """Test collecting a variable with type annotation"""
        # Create AST: int x = 42
        assign = ast.IbAssign(
            targets=[
                ast.IbTypeAnnotatedExpr(
                    target=ast.IbName(id="x"),
                    annotation=ast.IbName(id="int")
                )
            ],
            value=ast.IbInteger(value=42)
        )
        module = ast.IbModule(body=[assign], name="test")

        context = base_context.with_symbol_table(
            base_context.symbol_table.with_current(SymbolTable())
        )
        context = context._replace(ast=module)

        # Run pass
        pass_instance = SymbolCollectionPass()
        result = pass_instance.run(context)

        # Verify
        assert result.success

        # Check symbol was added
        symbol = context.symbol_table.current.lookup("x")
        assert symbol is not None
        assert symbol.name == "x"
        assert symbol.kind == SymbolKind.VARIABLE

    def test_collect_multiple_symbols(self, base_context, registry):
        """Test collecting multiple symbols in one module"""
        # Create AST with class, function, and variable
        class_def = ast.IbClassDef(
            name="MyClass",
            bases=[],
            body=[ast.IbPass()],
            decorators=[]
        )
        func_def = ast.IbFunctionDef(
            name="my_func",
            params=[],
            body=[ast.IbPass()],
            returns=registry.resolve("void"),
            decorators=[]
        )
        assign = ast.IbAssign(
            targets=[
                ast.IbTypeAnnotatedExpr(
                    target=ast.IbName(id="my_var"),
                    annotation=ast.IbName(id="int")
                )
            ],
            value=ast.IbInteger(value=10)
        )

        module = ast.IbModule(body=[class_def, func_def, assign], name="test")

        context = base_context.with_symbol_table(
            base_context.symbol_table.with_current(SymbolTable())
        )
        context = context._replace(ast=module)

        # Run pass
        pass_instance = SymbolCollectionPass()
        result = pass_instance.run(context)

        # Verify
        assert result.success

        # Check all symbols were added
        assert context.symbol_table.current.lookup("MyClass") is not None
        assert context.symbol_table.current.lookup("my_func") is not None
        assert context.symbol_table.current.lookup("my_var") is not None

    def test_duplicate_symbol_detection(self, base_context, registry):
        """Test that duplicate symbols generate diagnostics"""
        # Create AST with two functions with same name
        func_def1 = ast.IbFunctionDef(
            name="foo",
            params=[],
            body=[ast.IbPass()],
            returns=registry.resolve("void"),
            decorators=[]
        )
        func_def2 = ast.IbFunctionDef(
            name="foo",
            params=[],
            body=[ast.IbPass()],
            returns=registry.resolve("void"),
            decorators=[]
        )

        module = ast.IbModule(body=[func_def1, func_def2], name="test")

        context = base_context.with_symbol_table(
            base_context.symbol_table.with_current(SymbolTable())
        )
        context = context._replace(ast=module)

        # Run pass
        pass_instance = SymbolCollectionPass()
        result = pass_instance.run(context)

        # Verify diagnostic was generated
        assert len(result.diagnostics) > 0
        # Note: actual behavior depends on implementation
        # This test documents expected behavior

    def test_empty_module(self, base_context):
        """Test collecting from an empty module"""
        module = ast.IbModule(body=[], name="test")
        context = base_context._replace(ast=module)

        # Run pass
        pass_instance = SymbolCollectionPass()
        result = pass_instance.run(context)

        # Verify
        assert result.success
        assert len(result.diagnostics) == 0
