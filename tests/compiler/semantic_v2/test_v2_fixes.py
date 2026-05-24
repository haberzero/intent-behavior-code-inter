"""
Tests for semantic_v2 known-issue fixes:
1. SymbolResolutionPass: for-loop target variable registration
2. TypeCheckingPass: node_to_type population with proper registry
3. IntegrityCheckPass: node_to_loc population
"""

import pytest
from core.kernel import ast
from core.kernel.factory import create_default_registry
from core.compiler.semantic_v2.context import ContextBuilder
from core.compiler.semantic_v2.pipeline import create_semantic_pipeline
from core.compiler.semantic_v2.result import DiagnosticLevel


@pytest.fixture
def registry():
    return create_default_registry()


def run_pipeline(module, registry):
    """Helper: build context + run full pipeline."""
    ctx = ContextBuilder().with_ast(module).with_registry(registry).with_module_name("test").build()
    return create_semantic_pipeline().run(ctx)


def get_errors(result):
    """Extract error diagnostics."""
    return [d for d in result.diagnostics if d.level == DiagnosticLevel.ERROR]


# ============================================================
# Fix 1: for-loop variable scope
# ============================================================

class TestForLoopVariableScope:
    """SymbolResolutionPass must register for-loop target variables."""

    def test_for_loop_variable_resolved_in_body(self, registry):
        """Loop variable 'i' should be resolvable inside the loop body."""
        module = ast.IbModule(body=[
            ast.IbAssign(
                targets=[ast.IbTypeAnnotatedExpr(
                    target=ast.IbName(id='items', ctx='Store'),
                    annotation=ast.IbName(id='list', ctx='Load')
                )],
                value=ast.IbListExpr(elts=[ast.IbConstant(value=1)], ctx='Load')
            ),
            ast.IbFor(
                target=ast.IbName(id='i', ctx='Store'),
                iter=ast.IbName(id='items', ctx='Load'),
                body=[
                    ast.IbAssign(
                        targets=[ast.IbName(id='x', ctx='Store')],
                        value=ast.IbName(id='i', ctx='Load')
                    )
                ]
            )
        ])
        result = run_pipeline(module, registry)
        errors = get_errors(result)
        # No SEM_001 "Undefined symbol 'i'"
        sem001_for_i = [e for e in errors if "Undefined symbol 'i'" in e.message]
        assert sem001_for_i == [], f"Expected no SEM_001 for 'i', got: {sem001_for_i}"

    def test_for_loop_variable_bound_to_symbol(self, registry):
        """Loop variable node should have a symbol binding."""
        module = ast.IbModule(body=[
            ast.IbAssign(
                targets=[ast.IbTypeAnnotatedExpr(
                    target=ast.IbName(id='data', ctx='Store'),
                    annotation=ast.IbName(id='list', ctx='Load')
                )],
                value=ast.IbListExpr(elts=[], ctx='Load')
            ),
            ast.IbFor(
                target=ast.IbName(id='item', ctx='Store'),
                iter=ast.IbName(id='data', ctx='Load'),
                body=[ast.IbPass()]
            )
        ])
        result = run_pipeline(module, registry)
        # The for-loop target node should be in node_to_symbol
        for_stmt = module.body[1]
        target_node = for_stmt.target
        assert target_node in result.context.metadata.node_to_symbol

    def test_for_loop_tuple_unpack(self, registry):
        """Tuple unpacking in for-loop should register all variables."""
        module = ast.IbModule(body=[
            ast.IbAssign(
                targets=[ast.IbTypeAnnotatedExpr(
                    target=ast.IbName(id='pairs', ctx='Store'),
                    annotation=ast.IbName(id='list', ctx='Load')
                )],
                value=ast.IbListExpr(elts=[], ctx='Load')
            ),
            ast.IbFor(
                target=ast.IbTuple(
                    elts=[ast.IbName(id='k', ctx='Store'), ast.IbName(id='v', ctx='Store')],
                    ctx='Store'
                ),
                iter=ast.IbName(id='pairs', ctx='Load'),
                body=[
                    ast.IbExprStmt(value=ast.IbName(id='k', ctx='Load')),
                    ast.IbExprStmt(value=ast.IbName(id='v', ctx='Load')),
                ]
            )
        ])
        result = run_pipeline(module, registry)
        errors = get_errors(result)
        sem001 = [e for e in errors if "SEM_001" in e.code]
        # Neither 'k' nor 'v' should produce SEM_001
        assert not any("'k'" in e.message or "'v'" in e.message for e in sem001), \
            f"Unexpected SEM_001 for tuple-unpack vars: {[e.message for e in sem001]}"


# ============================================================
# Fix 2: TypeCheckingPass node_to_type population
# ============================================================

class TestTypeCheckingPopulation:
    """TypeCheckingPass must produce node_to_type entries."""

    def test_constant_gets_type_binding(self, registry):
        """Integer constant should be bound to 'int' type."""
        module = ast.IbModule(body=[
            ast.IbAssign(
                targets=[ast.IbTypeAnnotatedExpr(
                    target=ast.IbName(id='x', ctx='Store'),
                    annotation=ast.IbName(id='int', ctx='Load')
                )],
                value=ast.IbConstant(value=42)
            )
        ])
        result = run_pipeline(module, registry)
        # The constant node should have a type binding
        const_node = module.body[0].value
        bound_type = result.context.metadata.node_to_type.get(const_node)
        assert bound_type is not None, "Constant 42 should have a type binding"
        assert bound_type.name == "int"

    def test_string_constant_gets_type_binding(self, registry):
        """String constant should be bound to 'str' type."""
        module = ast.IbModule(body=[
            ast.IbAssign(
                targets=[ast.IbName(id='s', ctx='Store')],
                value=ast.IbConstant(value="hello")
            )
        ])
        result = run_pipeline(module, registry)
        const_node = module.body[0].value
        bound_type = result.context.metadata.node_to_type.get(const_node)
        assert bound_type is not None, "String constant should have a type binding"
        assert bound_type.name == "str"

    def test_behavior_expr_gets_type_binding(self, registry):
        """BehaviorExpr should be bound to 'behavior' type."""
        module = ast.IbModule(body=[
            ast.IbAssign(
                targets=[ast.IbTypeAnnotatedExpr(
                    target=ast.IbName(id='msg', ctx='Store'),
                    annotation=ast.IbName(id='str', ctx='Load')
                )],
                value=ast.IbBehaviorExpr(segments=["hello world"])
            )
        ])
        result = run_pipeline(module, registry)
        behavior_node = module.body[0].value
        bound_type = result.context.metadata.node_to_type.get(behavior_node)
        assert bound_type is not None, "BehaviorExpr should have a type binding"
        assert bound_type.name == "behavior"

    def test_node_to_type_count_nonzero(self, registry):
        """A non-trivial program should have multiple type bindings."""
        module = ast.IbModule(body=[
            ast.IbAssign(
                targets=[ast.IbTypeAnnotatedExpr(
                    target=ast.IbName(id='a', ctx='Store'),
                    annotation=ast.IbName(id='int', ctx='Load')
                )],
                value=ast.IbConstant(value=1)
            ),
            ast.IbAssign(
                targets=[ast.IbTypeAnnotatedExpr(
                    target=ast.IbName(id='b', ctx='Store'),
                    annotation=ast.IbName(id='str', ctx='Load')
                )],
                value=ast.IbConstant(value="x")
            ),
            ast.IbAssign(
                targets=[ast.IbName(id='c', ctx='Store')],
                value=ast.IbBinOp(
                    left=ast.IbName(id='a', ctx='Load'),
                    op='+',
                    right=ast.IbConstant(value=2)
                )
            ),
        ])
        result = run_pipeline(module, registry)
        assert len(result.context.metadata.node_to_type) >= 5, \
            f"Expected >= 5 type bindings, got {len(result.context.metadata.node_to_type)}"


# ============================================================
# Fix 3: node_to_loc population
# ============================================================

class TestNodeToLocPopulation:
    """IntegrityCheckPass must populate node_to_loc for all AST nodes."""

    def test_all_nodes_get_location(self, registry):
        """Every AST node should have a location binding."""
        module = ast.IbModule(body=[
            ast.IbAssign(
                targets=[ast.IbName(id='x', ctx='Store')],
                value=ast.IbConstant(value=42)
            )
        ])
        result = run_pipeline(module, registry)
        # At minimum: IbModule, IbAssign, IbName, IbConstant = 4 nodes
        assert len(result.context.metadata.node_to_loc) >= 4

    def test_location_has_expected_fields(self, registry):
        """Location bindings should contain file_path, line, column."""
        module = ast.IbModule(body=[
            ast.IbAssign(
                targets=[ast.IbName(id='y', ctx='Store')],
                value=ast.IbConstant(value=0)
            )
        ])
        result = run_pipeline(module, registry)
        # Pick any node and check structure
        for node, loc in result.context.metadata.node_to_loc.items():
            assert "file_path" in loc
            assert "line" in loc
            assert "column" in loc
            break  # one check is enough

    def test_location_count_matches_node_count(self, registry):
        """node_to_loc should have an entry for every AST node."""
        module = ast.IbModule(body=[
            ast.IbAssign(
                targets=[ast.IbTypeAnnotatedExpr(
                    target=ast.IbName(id='a', ctx='Store'),
                    annotation=ast.IbName(id='int', ctx='Load')
                )],
                value=ast.IbConstant(value=1)
            ),
            ast.IbFor(
                target=ast.IbName(id='i', ctx='Store'),
                iter=ast.IbName(id='a', ctx='Load'),
                body=[ast.IbPass()]
            )
        ])
        result = run_pipeline(module, registry)
        # Count all nodes manually
        def count_nodes(node):
            c = 1
            for attr in vars(node):
                child = getattr(node, attr)
                if isinstance(child, list):
                    for item in child:
                        if isinstance(item, ast.IbASTNode):
                            c += count_nodes(item)
                elif isinstance(child, ast.IbASTNode):
                    c += count_nodes(child)
            return c

        total_nodes = count_nodes(module)
        loc_count = len(result.context.metadata.node_to_loc)
        assert loc_count == total_nodes, \
            f"node_to_loc has {loc_count} entries but AST has {total_nodes} nodes"
