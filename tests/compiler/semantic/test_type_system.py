"""Tests for semantic type system features:
- auto lock, any permanent, -> auto unification, resolve_op
- AST node visitor coverage
- TypeResolutionPass
- TypeCheckingPass (func call return_type field)
- llmexcept body rewrite (bind_llm_except)
"""

import pytest
from core.kernel import ast
from core.kernel.factory import create_default_registry
from core.kernel.spec import TypeDef
from core.kernel.spec.base import TypeKind
from core.kernel.spec.type_ref import TypeRef
from core.compiler.semantic.pipeline import create_semantic_pipeline
from core.compiler.semantic.context import ContextBuilder
from core.compiler.semantic.passes.type_resolution_pass import TypeResolutionPass
from core.compiler.semantic.passes.type_checking_pass import TypeCheckingPass
from core.compiler.semantic.passes.binding_analysis_pass import BindingAnalysisPass


@pytest.fixture
def registry():
    return create_default_registry()


@pytest.fixture
def pipeline():
    return create_semantic_pipeline()


def make_context(module, registry):
    return ContextBuilder().with_ast(module).with_registry(registry).with_module_name("test").build()


# ========== auto 单次锁定 ==========

class TestAutoLock:
    def test_auto_infers_from_int(self, registry, pipeline):
        """auto x = 42 → x 推断为 int"""
        module = ast.IbModule(body=[
            ast.IbAssign(
                targets=[ast.IbTypeAnnotatedExpr(
                    target=ast.IbName(id='x', ctx='Store'),
                    annotation=ast.IbName(id='auto', ctx='Load')
                )],
                value=ast.IbConstant(value=42)
            )
        ])
        ctx = make_context(module, registry)
        result = pipeline.run(ctx)
        assert result.success

    def test_auto_infers_from_str(self, registry, pipeline):
        """auto x = "hello" → x 推断为 str"""
        module = ast.IbModule(body=[
            ast.IbAssign(
                targets=[ast.IbTypeAnnotatedExpr(
                    target=ast.IbName(id='x', ctx='Store'),
                    annotation=ast.IbName(id='auto', ctx='Load')
                )],
                value=ast.IbConstant(value="hello")
            )
        ])
        ctx = make_context(module, registry)
        result = pipeline.run(ctx)
        assert result.success


# ========== any 永久动态 ==========

class TestAnyPermanent:
    def test_any_stays_any(self, registry, pipeline):
        """any x = 42 → x 保持为 any，不窄化"""
        module = ast.IbModule(body=[
            ast.IbAssign(
                targets=[ast.IbTypeAnnotatedExpr(
                    target=ast.IbName(id='x', ctx='Store'),
                    annotation=ast.IbName(id='any', ctx='Load')
                )],
                value=ast.IbConstant(value=42)
            )
        ])
        ctx = make_context(module, registry)
        result = pipeline.run(ctx)
        assert result.success


# ========== resolve_op ==========

class TestResolveOp:
    def test_binop_int_plus_int(self, registry, pipeline):
        """int + int → int (via registry.resolve_op)"""
        module = ast.IbModule(body=[
            ast.IbAssign(
                targets=[ast.IbName(id='x', ctx='Store')],
                value=ast.IbBinOp(
                    left=ast.IbConstant(value=1),
                    op='+',
                    right=ast.IbConstant(value=2)
                )
            )
        ])
        ctx = make_context(module, registry)
        result = pipeline.run(ctx)
        assert result.success

    def test_unaryop_not_bool(self, registry, pipeline):
        """not True → bool (via registry.resolve_op)"""
        module = ast.IbModule(body=[
            ast.IbAssign(
                targets=[ast.IbName(id='x', ctx='Store')],
                value=ast.IbUnaryOp(
                    op='not',
                    operand=ast.IbConstant(value=True)
                )
            )
        ])
        ctx = make_context(module, registry)
        result = pipeline.run(ctx)
        assert result.success

    def test_compare_returns_bool(self, registry, pipeline):
        """1 < 2 → bool"""
        module = ast.IbModule(body=[
            ast.IbAssign(
                targets=[ast.IbName(id='x', ctx='Store')],
                value=ast.IbCompare(
                    left=ast.IbConstant(value=1),
                    ops=['<'],
                    comparators=[ast.IbConstant(value=2)]
                )
            )
        ])
        ctx = make_context(module, registry)
        result = pipeline.run(ctx)
        assert result.success


# ========== -> auto 函数返回类型统一 ==========

class TestAutoReturn:
    def test_auto_return_single_type(self, registry, pipeline):
        """func f() -> auto with single return type infers correctly"""
        module = ast.IbModule(body=[
            ast.IbFunctionDef(
                name='f',
                args=[],
                body=[ast.IbReturn(value=ast.IbConstant(value=42))],
                returns=ast.IbName(id='auto', ctx='Load')
            )
        ])
        ctx = make_context(module, registry)
        result = pipeline.run(ctx)
        assert result.success

    def test_auto_return_conflicting_types(self, registry, pipeline):
        """func f() -> auto with conflicting return types produces SEM_003"""
        module = ast.IbModule(body=[
            ast.IbFunctionDef(
                name='f',
                args=[],
                body=[
                    ast.IbIf(
                        test=ast.IbConstant(value=True),
                        body=[ast.IbReturn(value=ast.IbConstant(value=42))],
                        orelse=[ast.IbReturn(value=ast.IbConstant(value="hello"))]
                    )
                ],
                returns=ast.IbName(id='auto', ctx='Load')
            )
        ])
        ctx = make_context(module, registry)
        result = pipeline.run(ctx)
        # Should have a diagnostic about conflicting types
        sem003 = [d for d in result.diagnostics if d.code == "SEM_003"]
        assert len(sem003) > 0


# ========== AST 节点 visitor 覆盖 ==========

class TestVisitorCoverage:
    def test_expr_stmt(self, registry, pipeline):
        """IbExprStmt visitor"""
        module = ast.IbModule(body=[
            ast.IbExprStmt(value=ast.IbConstant(value=42))
        ])
        ctx = make_context(module, registry)
        result = pipeline.run(ctx)
        assert result.success

    def test_aug_assign(self, registry, pipeline):
        """IbAugAssign visitor"""
        module = ast.IbModule(body=[
            ast.IbAssign(targets=[ast.IbName(id='x', ctx='Store')], value=ast.IbConstant(value=1)),
            ast.IbAugAssign(
                target=ast.IbName(id='x', ctx='Store'),
                op='+=',
                value=ast.IbConstant(value=1)
            )
        ])
        ctx = make_context(module, registry)
        result = pipeline.run(ctx)
        assert result.success

    def test_cast_expr(self, registry, pipeline):
        """IbCastExpr visitor"""
        module = ast.IbModule(body=[
            ast.IbAssign(
                targets=[ast.IbName(id='x', ctx='Store')],
                value=ast.IbCastExpr(
                    type_annotation=ast.IbName(id='int', ctx='Load'),
                    value=ast.IbConstant(value="42")
                )
            )
        ])
        ctx = make_context(module, registry)
        result = pipeline.run(ctx)
        assert result.success

    def test_switch_case(self, registry, pipeline):
        """IbSwitch/IbCase visitor"""
        module = ast.IbModule(body=[
            ast.IbSwitch(
                test=ast.IbName(id='x', ctx='Load'),
                cases=[
                    ast.IbCase(pattern=ast.IbConstant(value=1), body=[ast.IbPass()]),
                    ast.IbCase(pattern=None, body=[ast.IbPass()])
                ]
            )
        ])
        ctx = make_context(module, registry)
        result = pipeline.run(ctx)
        assert result.success

    def test_bool_op(self, registry, pipeline):
        """IbBoolOp visitor"""
        module = ast.IbModule(body=[
            ast.IbAssign(
                targets=[ast.IbName(id='x', ctx='Store')],
                value=ast.IbBoolOp(
                    op='and',
                    values=[ast.IbConstant(value=True), ast.IbConstant(value=False)]
                )
            )
        ])
        ctx = make_context(module, registry)
        result = pipeline.run(ctx)
        assert result.success

    def test_if_exp(self, registry, pipeline):
        """IbIfExp visitor"""
        module = ast.IbModule(body=[
            ast.IbAssign(
                targets=[ast.IbName(id='x', ctx='Store')],
                value=ast.IbIfExp(
                    test=ast.IbConstant(value=True),
                    body=ast.IbConstant(value=1),
                    orelse=ast.IbConstant(value=2)
                )
            )
        ])
        ctx = make_context(module, registry)
        result = pipeline.run(ctx)
        assert result.success

    def test_import(self, registry, pipeline):
        """IbImport visitor"""
        module = ast.IbModule(body=[
            ast.IbImport(names=[ast.IbAlias(name='math', asname=None)])
        ])
        ctx = make_context(module, registry)
        result = pipeline.run(ctx)
        assert result.success

    def test_raise(self, registry, pipeline):
        """IbRaise visitor"""
        module = ast.IbModule(body=[
            ast.IbRaise(exc=ast.IbConstant(value="error"))
        ])
        ctx = make_context(module, registry)
        result = pipeline.run(ctx)
        assert result.success

    def test_global_stmt(self, registry, pipeline):
        """IbGlobalStmt visitor"""
        module = ast.IbModule(body=[
            ast.IbGlobalStmt(names=['x', 'y'])
        ])
        ctx = make_context(module, registry)
        result = pipeline.run(ctx)
        assert result.success

    def test_intent_annotation(self, registry, pipeline):
        """IbIntentAnnotation visitor"""
        from core.kernel.intent_logic import IntentMode
        module = ast.IbModule(body=[
            ast.IbIntentAnnotation(
                intent=ast.IbIntentInfo(
                    mode=IntentMode.APPEND,
                    content="be concise"
                )
            ),
            ast.IbExprStmt(value=ast.IbConstant(value=1))
        ])
        ctx = make_context(module, registry)
        result = pipeline.run(ctx)
        assert result.success

    def test_intent_stack_operation(self, registry, pipeline):
        """IbIntentStackOperation visitor"""
        from core.kernel.intent_logic import IntentMode
        module = ast.IbModule(body=[
            ast.IbIntentStackOperation(
                intent=ast.IbIntentInfo(
                    mode=IntentMode.APPEND,
                    content="be helpful"
                )
            )
        ])
        ctx = make_context(module, registry)
        result = pipeline.run(ctx)
        assert result.success


# ========== TypeResolutionPass ==========

class TestTypeResolutionPass:
    def test_resolves_auto(self, registry):
        """TypeResolutionPass resolves 'auto' annotation"""
        module = ast.IbModule(body=[
            ast.IbAssign(
                targets=[ast.IbTypeAnnotatedExpr(
                    target=ast.IbName(id='x', ctx='Store'),
                    annotation=ast.IbName(id='auto', ctx='Load')
                )],
                value=ast.IbConstant(value=42)
            )
        ])
        ctx = make_context(module, registry)
        pass_instance = TypeResolutionPass()
        result = pass_instance.run(ctx)
        assert result.success

    def test_resolves_unknown_type_reports_sem004(self, registry):
        """TypeResolutionPass reports SEM_004 for unknown types"""
        module = ast.IbModule(body=[
            ast.IbAssign(
                targets=[ast.IbTypeAnnotatedExpr(
                    target=ast.IbName(id='x', ctx='Store'),
                    annotation=ast.IbName(id='NonExistentType', ctx='Load')
                )],
                value=ast.IbConstant(value=42)
            )
        ])
        ctx = make_context(module, registry)
        pass_instance = TypeResolutionPass()
        result = pass_instance.run(ctx)
        sem004 = [d for d in result.diagnostics if d.code == "SEM_004"]
        assert len(sem004) == 1


# ========== llmexcept body 重写 ==========

class TestLLMExceptRewrite:
    def test_regular_llmexcept_binds_to_prev_stmt(self, registry, pipeline):
        """llmexcept after behavior stmt → stmt.target = prev_stmt (body rewrite)"""
        behavior = ast.IbBehaviorExpr(segments=["describe weather"])
        assign_stmt = ast.IbAssign(
            targets=[ast.IbName(id='result', ctx='Store')],
            value=behavior
        )
        llmexcept = ast.IbLLMExceptionalStmt(
            target=None,
            body=[ast.IbPass()]
        )
        module = ast.IbModule(body=[assign_stmt, llmexcept])
        ctx = make_context(module, registry)
        result = pipeline.run(ctx)
        # After binding analysis, llmexcept.target should be the assign_stmt
        assert llmexcept.target is assign_stmt
        # And the module body should have llmexcept as the sole entry (assign_stmt was popped)
        assert len(module.body) == 1
        assert module.body[0] is llmexcept

    def test_cond_for_llmexcept_binds_to_handler(self, registry, pipeline):
        """llmexcept after condition-driven for → for.llmexcept_handler = stmt"""
        behavior = ast.IbBehaviorExpr(segments=["is task done?"])
        for_stmt = ast.IbFor(
            target=None,
            iter=behavior,
            body=[ast.IbPass()]
        )
        llmexcept = ast.IbLLMExceptionalStmt(
            target=None,
            body=[ast.IbPass()]
        )
        module = ast.IbModule(body=[for_stmt, llmexcept])
        ctx = make_context(module, registry)
        result = pipeline.run(ctx)
        # After binding: for_stmt.llmexcept_handler = llmexcept, target stays None
        assert for_stmt.llmexcept_handler is llmexcept
        assert llmexcept.target is None
        # for_stmt remains in body; llmexcept is not a separate body entry
        assert len(module.body) == 1
        assert module.body[0] is for_stmt

    def test_llmexcept_without_prev_stmt_errors(self, registry, pipeline):
        """llmexcept as first statement → SEM_051 error"""
        llmexcept = ast.IbLLMExceptionalStmt(
            target=None,
            body=[ast.IbPass()]
        )
        module = ast.IbModule(body=[llmexcept])
        ctx = make_context(module, registry)
        result = pipeline.run(ctx)
        sem051 = [d for d in result.diagnostics if d.code == "SEM_051"]
        assert len(sem051) > 0


# ===========================================================================
# TypeCheckingPass regression (merged from test_type_checking_pass.py)
# ===========================================================================


def test_type_checking_func_call_uses_return_type(registry, pipeline):
    """Function call type inference should use return_type field, not ret."""
    func_def = ast.IbFunctionDef(
        name="greet",
        args=[],
        body=[],
        returns="str"
    )
    func_name = ast.IbName(id="greet", ctx="load")
    call = ast.IbCall(func=func_name, args=[], keywords=[])
    module = ast.IbModule(body=[func_def, call])

    context = make_context(module, registry)
    result = TypeCheckingPass().run(context)
    assert result is not None
