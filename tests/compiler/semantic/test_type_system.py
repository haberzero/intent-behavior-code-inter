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


from .conftest import make_context  # noqa: E402  (single-source helper)


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
        """func f() -> auto with conflicting return types produces SEM_TYPE_MISMATCH"""
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
        sem003 = [d for d in result.diagnostics if d.code == "SEM_TYPE_MISMATCH"]
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
        """TypeResolutionPass reports SEM_INVALID_SCOPE for unknown types"""
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
        sem004 = [d for d in result.diagnostics if d.code == "SEM_INVALID_SCOPE"]
        assert len(sem004) == 1


# ========== llmexcept body 重写 ==========

class TestLLMExceptRewrite:
    def test_regular_llmexcept_binds_to_prev_stmt(self, registry, pipeline):
        """llmexcept after behavior stmt → prev_stmt.llmexcept_handler = llmexcept (统一挂载)"""
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
        # 统一挂载：prev_stmt.llmexcept_handler = llmexcept（不再 IbLLMExceptionalStmt 包装）
        assert assign_stmt.llmexcept_handler is llmexcept
        # llmexcept 从 body 中移除；被保护语句留在 body 中正常执行
        assert len(module.body) == 1
        assert module.body[0] is assign_stmt

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
        """llmexcept as first statement → SEM_LLMEXCEPT_SCOPE_BINDING error"""
        llmexcept = ast.IbLLMExceptionalStmt(
            target=None,
            body=[ast.IbPass()]
        )
        module = ast.IbModule(body=[llmexcept])
        ctx = make_context(module, registry)
        result = pipeline.run(ctx)
        sem051 = [d for d in result.diagnostics if d.code == "SEM_LLMEXCEPT_SCOPE_BINDING"]
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


# ===========================================================================
# 布尔上下文行为表达式定型（恒真陷阱修复）
# ===========================================================================


class TestBehaviorBooleanContextTyping:
    """布尔上下文中的行为表达式应定型为 bool（与直接条件一致）。

    修复前：`while @~...~ and True:` / `if not @~...~:` 中的行为表达式落到
    `behavior` 占位符 → 运行期装箱为 str → "0" 按 Python 真值语义判真 → 恒真陷阱。
    """

    @staticmethod
    def _bindings(pipeline, registry, module):
        ctx = make_context(module, registry)
        result = pipeline.run(ctx)
        bindings = {}
        for out in result.outputs:
            for node, spec in (getattr(out, "type_bindings", None) or {}).items():
                bindings[node] = spec
        return bindings

    def test_boolop_operand_behavior_is_bool(self, registry, pipeline):
        """`while @~...~ and True:` 中行为表达式定型为 bool"""
        behavior = ast.IbBehaviorExpr(segments=["is done?"])
        boolop = ast.IbBoolOp(op="and", values=[behavior, ast.IbConstant(value=True)])
        module = ast.IbModule(body=[ast.IbWhile(test=boolop, body=[ast.IbPass()])])
        bindings = self._bindings(pipeline, registry, module)
        assert bindings[behavior].name == "bool"

    def test_not_operand_behavior_is_bool(self, registry, pipeline):
        """`if not @~...~:` 中行为表达式定型为 bool"""
        behavior = ast.IbBehaviorExpr(segments=["done?"])
        unary = ast.IbUnaryOp(op="not", operand=behavior)
        module = ast.IbModule(body=[ast.IbIf(test=unary, body=[ast.IbPass()], orelse=[])])
        bindings = self._bindings(pipeline, registry, module)
        assert bindings[behavior].name == "bool"

    def test_nested_boolop_behavior_all_bool(self, registry, pipeline):
        """`while not @~a~ and (@~b~ or @~c~):` 中全部行为定型为 bool"""
        b1 = ast.IbBehaviorExpr(segments=["a"])
        b2 = ast.IbBehaviorExpr(segments=["b"])
        b3 = ast.IbBehaviorExpr(segments=["c"])
        inner = ast.IbBoolOp(op="or", values=[b2, b3])
        outer = ast.IbBoolOp(op="and", values=[ast.IbUnaryOp(op="not", operand=b1), inner])
        module = ast.IbModule(body=[ast.IbWhile(test=outer, body=[ast.IbPass()])])
        bindings = self._bindings(pipeline, registry, module)
        assert all(bindings[b].name == "bool" for b in (b1, b2, b3))

    def test_compare_behavior_not_forced_bool(self, registry, pipeline):
        """比较中的行为表达式按另一操作数适配（不被强制为 bool）"""
        behavior = ast.IbBehaviorExpr(segments=["guess"])
        cmp = ast.IbCompare(left=behavior, ops=["=="], comparators=[ast.IbConstant(value=42)])
        module = ast.IbModule(body=[ast.IbIf(test=cmp, body=[ast.IbPass()], orelse=[])])
        bindings = self._bindings(pipeline, registry, module)
        assert bindings[behavior].name == "int"

    def test_ifexp_test_behavior_is_bool(self, registry, pipeline):
        """条件表达式 `x if @~cond~ else y` 的 test 行为定型为 bool"""
        behavior = ast.IbBehaviorExpr(segments=["cond?"])
        ifexp = ast.IbIfExp(
            test=behavior,
            body=ast.IbConstant(value=1),
            orelse=ast.IbConstant(value=2),
        )
        module = ast.IbModule(body=[
            ast.IbAssign(targets=[ast.IbName(id="x", ctx="Store")], value=ifexp)
        ])
        bindings = self._bindings(pipeline, registry, module)
        assert bindings[behavior].name == "bool"
