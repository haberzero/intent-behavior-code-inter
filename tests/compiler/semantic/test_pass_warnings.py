"""
Tests for intent_context static call warning and cast validation warning.

intent_context.push() / pop() / fork() / merge() / combine() / clear()
called on the class object (not an instance) should emit SEM_INTENT_STATIC_CALL.

(TargetType)source_expr where the target axiom's can_convert_from()
rejects the source type should emit SEM_CAST_NO_CONVERTER.
"""

import pytest
from core.kernel import ast
from core.compiler.semantic.passes.type_checking_pass import TypeCheckingPass
from core.compiler.semantic.pipeline import create_semantic_pipeline
from core.compiler.semantic.result import DiagnosticLevel
from .conftest import make_context


# ============================================================
# intent_context static call warning (SEM_INTENT_STATIC_CALL)
# ============================================================


class TestIntentContextStaticCallWarning:
    """SEM_INTENT_STATIC_CALL: intent_context.<method>() on class is no-op."""

    def _run_intent_context_call(self, method_name, spec_registry, args=None):
        """Helper: build intent_context.<method>(...) call and run pipeline."""
        # intent_context.push("hello")
        receiver = ast.IbName(id="intent_context", ctx="load")
        attr = ast.IbAttribute(value=receiver, attr=method_name, ctx="load")
        call_args = args or [ast.IbConstant(value="hello")]
        call = ast.IbCall(func=attr, args=call_args, keywords=[])
        expr_stmt = ast.IbExprStmt(value=call)
        module = ast.IbModule(body=[expr_stmt])

        context = make_context(module, spec_registry)
        pipeline = create_semantic_pipeline()
        result = pipeline.run(context)
        return result

    def test_push_on_class_emits_sem090(self, spec_registry):
        """intent_context.push("X") should emit SEM_INTENT_STATIC_CALL warning."""
        result = self._run_intent_context_call("push", spec_registry)
        warnings = [d for d in result.diagnostics
                    if d.level == DiagnosticLevel.WARNING and d.code == "SEM_INTENT_STATIC_CALL"]
        assert len(warnings) == 1
        assert "push" in warnings[0].message
        assert "no effect" in warnings[0].message

    def test_pop_on_class_emits_sem090(self, spec_registry):
        """intent_context.pop() should emit SEM_INTENT_STATIC_CALL warning."""
        result = self._run_intent_context_call("pop", spec_registry, args=[])
        warnings = [d for d in result.diagnostics
                    if d.level == DiagnosticLevel.WARNING and d.code == "SEM_INTENT_STATIC_CALL"]
        assert len(warnings) == 1
        assert "pop" in warnings[0].message

    def test_fork_on_class_emits_sem090(self, spec_registry):
        """intent_context.fork() should emit SEM_INTENT_STATIC_CALL warning."""
        result = self._run_intent_context_call("fork", spec_registry, args=[])
        warnings = [d for d in result.diagnostics
                    if d.level == DiagnosticLevel.WARNING and d.code == "SEM_INTENT_STATIC_CALL"]
        assert len(warnings) == 1

    def test_merge_on_class_emits_sem090(self, spec_registry):
        """intent_context.merge(ctx) should emit SEM_INTENT_STATIC_CALL warning."""
        arg = ast.IbName(id="some_ctx", ctx="load")
        result = self._run_intent_context_call("merge", spec_registry, args=[arg])
        warnings = [d for d in result.diagnostics
                    if d.level == DiagnosticLevel.WARNING and d.code == "SEM_INTENT_STATIC_CALL"]
        assert len(warnings) == 1

    def test_combine_on_class_emits_sem090(self, spec_registry):
        """intent_context.combine(ctx) should emit SEM_INTENT_STATIC_CALL warning."""
        arg = ast.IbName(id="some_ctx", ctx="load")
        result = self._run_intent_context_call("combine", spec_registry, args=[arg])
        warnings = [d for d in result.diagnostics
                    if d.level == DiagnosticLevel.WARNING and d.code == "SEM_INTENT_STATIC_CALL"]
        assert len(warnings) == 1

    def test_clear_on_class_emits_sem090(self, spec_registry):
        """intent_context.clear() should emit SEM_INTENT_STATIC_CALL warning."""
        result = self._run_intent_context_call("clear", spec_registry, args=[])
        warnings = [d for d in result.diagnostics
                    if d.level == DiagnosticLevel.WARNING and d.code == "SEM_INTENT_STATIC_CALL"]
        assert len(warnings) == 1

    def test_get_current_on_class_no_warning(self, spec_registry):
        """intent_context.get_current() is safe — no SEM_INTENT_STATIC_CALL."""
        result = self._run_intent_context_call("get_current", spec_registry, args=[])
        warnings = [d for d in result.diagnostics
                    if d.level == DiagnosticLevel.WARNING and d.code == "SEM_INTENT_STATIC_CALL"]
        assert len(warnings) == 0

    def test_use_on_class_no_warning(self, spec_registry):
        """intent_context.use(ctx) is safe — no SEM_INTENT_STATIC_CALL."""
        arg = ast.IbName(id="some_ctx", ctx="load")
        result = self._run_intent_context_call("use", spec_registry, args=[arg])
        warnings = [d for d in result.diagnostics
                    if d.level == DiagnosticLevel.WARNING and d.code == "SEM_INTENT_STATIC_CALL"]
        assert len(warnings) == 0

    def test_clear_inherited_on_class_no_warning(self, spec_registry):
        """intent_context.clear_inherited() is safe — no SEM_INTENT_STATIC_CALL."""
        result = self._run_intent_context_call("clear_inherited", spec_registry, args=[])
        warnings = [d for d in result.diagnostics
                    if d.level == DiagnosticLevel.WARNING and d.code == "SEM_INTENT_STATIC_CALL"]
        assert len(warnings) == 0


# ============================================================
# Compile-time cast validation (SEM_CAST_NO_CONVERTER)
# ============================================================


class TestCastValidationWarning:
    """SEM_CAST_NO_CONVERTER: (TargetType)source when can_convert_from rejects source."""

    def _run_cast(self, target_type_name, source_type_name, spec_registry):
        """Helper: build (target_type_name)var and run pipeline with var declared."""
        # Declare source variable: <source_type> x = <default>
        var_target = ast.IbTypeAnnotatedExpr(
            target=ast.IbName(id="x", ctx="store"),
            annotation=ast.IbName(id=source_type_name, ctx="load"),
        )
        default_val = ast.IbConstant(value=0) if source_type_name == "int" else ast.IbConstant(value="hello")
        assign = ast.IbAssign(targets=[var_target], value=default_val)

        # Cast expression: (target_type_name) x
        cast_expr = ast.IbCastExpr(
            type_annotation=ast.IbName(id=target_type_name, ctx="load"),
            value=ast.IbName(id="x", ctx="load"),
        )
        expr_stmt = ast.IbExprStmt(value=cast_expr)
        module = ast.IbModule(body=[assign, expr_stmt])

        context = make_context(module, spec_registry)
        pipeline = create_semantic_pipeline()
        result = pipeline.run(context)
        return result

    def test_int_from_str_no_warning(self, spec_registry):
        """(int)str_var: int can convert from str, no SEM_CAST_NO_CONVERTER."""
        result = self._run_cast("int", "str", spec_registry)
        warnings = [d for d in result.diagnostics
                    if d.level == DiagnosticLevel.WARNING and d.code == "SEM_CAST_NO_CONVERTER"]
        assert len(warnings) == 0

    def test_int_from_float_no_warning(self, spec_registry):
        """(int)float_var: int can convert from float, no SEM_CAST_NO_CONVERTER."""
        result = self._run_cast("int", "float", spec_registry)
        warnings = [d for d in result.diagnostics
                    if d.level == DiagnosticLevel.WARNING and d.code == "SEM_CAST_NO_CONVERTER"]
        assert len(warnings) == 0

    def test_int_from_list_emits_sem091(self, spec_registry):
        """(int)list_var: int cannot convert from list, should SEM_CAST_NO_CONVERTER."""
        result = self._run_cast("int", "list", spec_registry)
        errors = [d for d in result.diagnostics
                    if d.level == DiagnosticLevel.ERROR and d.code == "SEM_CAST_NO_CONVERTER"]
        assert len(errors) == 1
        assert "list" in errors[0].message
        assert "int" in errors[0].message

    def test_float_from_str_no_warning(self, spec_registry):
        """(float)str_var: float can convert from str, no SEM_CAST_NO_CONVERTER."""
        result = self._run_cast("float", "str", spec_registry)
        warnings = [d for d in result.diagnostics
                    if d.level == DiagnosticLevel.WARNING and d.code == "SEM_CAST_NO_CONVERTER"]
        assert len(warnings) == 0

    def test_float_from_list_emits_sem091(self, spec_registry):
        """(float)list_var: float cannot convert from list, should SEM_CAST_NO_CONVERTER."""
        result = self._run_cast("float", "list", spec_registry)
        errors = [d for d in result.diagnostics
                    if d.level == DiagnosticLevel.ERROR and d.code == "SEM_CAST_NO_CONVERTER"]
        assert len(errors) == 1

    def test_list_from_int_emits_sem091(self, spec_registry):
        """(list)int_var: list can only convert from list, should SEM_CAST_NO_CONVERTER."""
        result = self._run_cast("list", "int", spec_registry)
        errors = [d for d in result.diagnostics
                    if d.level == DiagnosticLevel.ERROR and d.code == "SEM_CAST_NO_CONVERTER"]
        assert len(errors) == 1

    def test_bool_from_anything_no_warning(self, spec_registry):
        """(bool)int_var: bool can convert from anything (truthy), no SEM_CAST_NO_CONVERTER."""
        result = self._run_cast("bool", "int", spec_registry)
        warnings = [d for d in result.diagnostics
                    if d.level == DiagnosticLevel.WARNING and d.code == "SEM_CAST_NO_CONVERTER"]
        assert len(warnings) == 0

    def test_same_type_cast_no_warning(self, spec_registry):
        """(int)int_var: same type cast, no SEM_CAST_NO_CONVERTER."""
        result = self._run_cast("int", "int", spec_registry)
        warnings = [d for d in result.diagnostics
                    if d.level == DiagnosticLevel.WARNING and d.code == "SEM_CAST_NO_CONVERTER"]
        assert len(warnings) == 0
