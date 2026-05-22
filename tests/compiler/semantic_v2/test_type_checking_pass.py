"""
Regression tests for TypeCheckingPass (Pass 3).

Covers fix: func_type.return_type instead of func_type.ret
"""

import pytest
from core.kernel import ast
from core.kernel.spec import TypeDef
from core.kernel.spec.base import TypeKind
from core.kernel.spec.type_ref import TypeRef
from core.compiler.semantic_v2.passes.type_checking_pass import TypeCheckingPass
from .conftest import make_context


def test_type_checking_func_call_uses_return_type(spec_registry):
    """Function call type inference should use return_type field, not ret."""
    # Define a function and call it
    func_def = ast.IbFunctionDef(
        name="greet",
        args=[],
        body=[],
        returns="str"
    )
    # Call it: greet()
    func_name = ast.IbName(id="greet", ctx="load")
    call = ast.IbCall(func=func_name, args=[], keywords=[])
    module = ast.IbModule(body=[func_def, call])

    context = make_context(module, spec_registry)
    # TypeCheckingPass should not crash on func_type.return_type access
    result = TypeCheckingPass().run(context)
    # Just verify it doesn't throw AttributeError('ret') — pass ran without crash
    assert result is not None
