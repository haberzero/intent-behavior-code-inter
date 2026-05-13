"""
Tests for SymbolCollectionPass
"""

import pytest
from core.kernel import ast
from core.kernel.symbols import SymbolTable, SymbolKind
from core.kernel.spec.registry import SpecRegistry
from core.compiler.semantic_v2.context import SemanticContext
from core.compiler.semantic_v2.metadata import MetadataStore, SymbolTableContext, TypeEnvironment
from core.compiler.semantic_v2.passes.symbol_collection_pass import SymbolCollectionPass


def create_test_context(ast_node):
    """创建测试上下文"""
    registry = SpecRegistry()
    symbol_table = SymbolTable()

    context = SemanticContext(
        ast=ast_node,
        registry=registry,
        module_name="test_module",
        symbol_table=SymbolTableContext(table=symbol_table),
        type_environment=TypeEnvironment(),
        metadata=MetadataStore()
    )
    return context


def test_symbol_collection_pass_empty_module():
    """测试空模块的符号收集"""
    # 创建空模块
    module = ast.IbModule(body=[])
    context = create_test_context(module)

    # 运行 Pass
    pass_instance = SymbolCollectionPass()
    result = pass_instance.run(context)

    # 验证结果
    assert result.success
    assert len(result.diagnostics) == 0


def test_symbol_collection_pass_function_def():
    """测试函数定义的符号收集"""
    # 创建函数定义
    func_def = ast.IbFunctionDef(
        name="test_func",
        args=[],
        body=[],
        returns=None
    )
    module = ast.IbModule(body=[func_def])
    context = create_test_context(module)

    # 运行 Pass
    pass_instance = SymbolCollectionPass()
    result = pass_instance.run(context)

    # 验证结果
    assert result.success
    assert len(result.diagnostics) == 0

    # 验证符号表
    symbol_table = result.context.symbol_table.table
    assert "test_func" in symbol_table.symbols
    sym = symbol_table.symbols["test_func"]
    assert sym.kind == SymbolKind.FUNCTION
    assert sym.name == "test_func"


def test_symbol_collection_pass_class_def():
    """测试类定义的符号收集"""
    # 创建类定义
    class_def = ast.IbClassDef(
        name="TestClass",
        parent=None,
        body=[]
    )
    module = ast.IbModule(body=[class_def])
    context = create_test_context(module)

    # 运行 Pass
    pass_instance = SymbolCollectionPass()
    result = pass_instance.run(context)

    # 验证结果
    assert result.success
    assert len(result.diagnostics) == 0

    # 验证符号表
    symbol_table = result.context.symbol_table.table
    assert "TestClass" in symbol_table.symbols
    sym = symbol_table.symbols["TestClass"]
    assert sym.kind == SymbolKind.CLASS
    assert sym.name == "TestClass"


def test_symbol_collection_pass_variable_assign():
    """测试变量赋值的符号收集"""
    # 创建赋值语句
    name_node = ast.IbName(id="x", ctx="store")
    value_node = ast.IbConstant(value=42)
    assign = ast.IbAssign(targets=[name_node], value=value_node)
    module = ast.IbModule(body=[assign])
    context = create_test_context(module)

    # 运行 Pass
    pass_instance = SymbolCollectionPass()
    result = pass_instance.run(context)

    # 验证结果
    assert result.success
    assert len(result.diagnostics) == 0

    # 验证符号表
    symbol_table = result.context.symbol_table.table
    assert "x" in symbol_table.symbols
    sym = symbol_table.symbols["x"]
    assert sym.kind == SymbolKind.VARIABLE
    assert sym.name == "x"


def test_symbol_collection_pass_duplicate_definition():
    """测试重复定义的错误检测"""
    # 创建两个同名函数
    func1 = ast.IbFunctionDef(name="duplicate", args=[], body=[], returns=None)
    func2 = ast.IbFunctionDef(name="duplicate", args=[], body=[], returns=None)
    module = ast.IbModule(body=[func1, func2])
    context = create_test_context(module)

    # 运行 Pass
    pass_instance = SymbolCollectionPass()
    result = pass_instance.run(context)

    # 验证结果：应该有错误
    assert len(result.diagnostics) > 0
    assert any(d.code == "SEM_002" for d in result.diagnostics)
