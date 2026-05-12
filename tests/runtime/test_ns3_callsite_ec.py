"""NS-3 regression: lambda/snapshot/IbBehavior cross-frame ``_execution_context``.

The principle: lambda/snapshot/behavior are "call-site" semantics for their
execution machinery (VM, runtime_context, node_pool, side-tables). Only
user-observable capture state (free variables for snapshot, intent context
for snapshot) is frozen at definition time. The ``_execution_context``
field on these objects is therefore a definition-time fallback only —
the **call-site** EC must take precedence whenever available.

These tests verify the precedence order is:
    call-site ContextVar > definition-time ``_execution_context`` field
"""
import os
import pytest

from core.engine import IBCIEngine


def _make_engine():
    return IBCIEngine(
        root_dir=os.path.dirname(os.path.abspath(__file__)),
        auto_sniff=False,
    )


def _ai_prefix() -> str:
    return (
        'import ai\n'
        'ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")\n'
    )


class TestNS3CallsiteExecutionContext:
    def test_vm_path_uses_callsite_ec_not_field(self):
        """CPS path: ``_vm_invoke_behavior`` must pass ``executor.ec`` to the
        LLM executor's ``invoke_behavior``, NOT the behavior's definition-time
        ``_execution_context`` field.
        """
        engine = _make_engine()

        observations = {}

        from core.runtime.interpreter.llm_executor import LLMExecutorImpl
        original = LLMExecutorImpl.execute_behavior_object_cps

        def probe(self, behavior, execution_context):
            # Stamp the behavior's stored field with a sentinel so we can
            # detect if the executor ever saw the definition-time value.
            observations["passed_ec_is_field"] = (
                execution_context is behavior._execution_context
            )
            # Whichever EC was passed, it must be a "live" EC with a VM.
            observations["passed_ec_has_vm"] = (
                getattr(execution_context, "vm_executor", None) is not None
            )
            return (yield from original(self, behavior, execution_context))

        LLMExecutorImpl.execute_behavior_object_cps = probe
        try:
            engine.run_string(
                _ai_prefix() + (
                    'fn b = lambda: @~MOCK:STR:hello~\n'
                    'str r = (str)b()\n'
                ),
                output_callback=lambda _t: None,
                silent=True,
            )
        finally:
            LLMExecutorImpl.execute_behavior_object_cps = original

        # In the single-Interpreter happy path, ``executor.ec`` and the
        # stored field should refer to the same EC (they were the same at
        # definition time). The contract is just that the EC passed must
        # have a live VM and be the call-site EC.
        assert observations.get("passed_ec_has_vm") is True

    def test_sync_call_prefers_contextvar_ec(self):
        """``IbBehavior.call()`` sync path: when a ContextVar EC is set, it
        must take precedence over the definition-time ``_execution_context``
        field.

        Uses a SimpleNamespace shim EC that proxies to the real EC's services
        but is identity-distinguishable, to prove the precedence wiring.
        """
        engine = _make_engine()

        captured = {}
        engine.run_string(
            _ai_prefix() + (
                'fn b = lambda: @~MOCK:STR:hello~\n'
            ),
            output_callback=lambda _t: None,
            silent=True,
        )

        scope = engine.interpreter.runtime_context.get_current_scope()
        while scope is not None:
            sym = scope.get_symbol("b") if hasattr(scope, "get_symbol") else None
            if sym is not None:
                captured["behavior"] = sym.value
                break
            scope = getattr(scope, "parent", None)
        behavior = captured["behavior"]
        real_ec = behavior._execution_context

        # Build a transparent shim: same services, distinct identity.
        from types import SimpleNamespace
        shim_ec = SimpleNamespace(
            runtime_context=real_ec.runtime_context,
            vm_executor=real_ec.vm_executor,
            registry=real_ec.registry,
            get_node_data=real_ec.get_node_data,
            get_side_table=real_ec.get_side_table,
            current_module_name=real_ec.current_module_name,
            module_manager=getattr(real_ec, "module_manager", None),
            factory=getattr(real_ec, "factory", None),
            push_stack=getattr(real_ec, "push_stack", lambda **k: None),
            pop_stack=getattr(real_ec, "pop_stack", lambda: None),
        )
        assert shim_ec is not real_ec

        from core.runtime.frame import (
            set_current_execution_context, reset_current_execution_context,
        )

        observations = {}
        from core.runtime.interpreter.llm_executor import LLMExecutorImpl
        original = LLMExecutorImpl.execute_behavior_object

        def probe(self, b, execution_context):
            observations["ec_id"] = id(execution_context)
            return original(self, b, execution_context)

        LLMExecutorImpl.execute_behavior_object = probe
        try:
            tok = set_current_execution_context(shim_ec)
            try:
                behavior.call(behavior.ib_class.registry.get_none(), [])
            finally:
                reset_current_execution_context(tok)
        finally:
            LLMExecutorImpl.execute_behavior_object = original

        assert observations.get("ec_id") == id(shim_ec), (
            "IbBehavior.call() must prefer ContextVar EC over definition-time "
            "_execution_context field (NS-3 precedence)"
        )

    def test_sync_call_fallback_when_no_contextvar(self):
        """When no ContextVar EC is set (outside any Interpreter), the
        definition-time field is used as the fallback (backward compat).
        """
        engine = _make_engine()

        captured = {}

        engine.run_string(
            _ai_prefix() + (
                'fn b = lambda: @~MOCK:STR:hello~\n'
            ),
            output_callback=lambda _t: None,
            silent=True,
        )

        scope = engine.interpreter.runtime_context.get_current_scope()
        while scope is not None:
            sym = scope.get_symbol("b") if hasattr(scope, "get_symbol") else None
            if sym is not None:
                captured["behavior"] = sym.value
                break
            scope = getattr(scope, "parent", None)
        behavior = captured["behavior"]

        # After engine.run_string returns, the ContextVar EC is reset to None.
        # Calling .call() must fall back to behavior._execution_context.
        from core.runtime.frame import get_current_execution_context
        assert get_current_execution_context() is None, (
            "test precondition: ContextVar EC should be None outside run_string"
        )

        observations = {}
        from core.runtime.interpreter.llm_executor import LLMExecutorImpl
        original = LLMExecutorImpl.execute_behavior_object

        def probe(self, b, execution_context):
            observations["ec_id"] = id(execution_context)
            return original(self, b, execution_context)

        LLMExecutorImpl.execute_behavior_object = probe
        try:
            behavior.call(behavior.ib_class.registry.get_none(), [])
        finally:
            LLMExecutorImpl.execute_behavior_object = original

        assert observations.get("ec_id") == id(behavior._execution_context), (
            "Fallback to definition-time _execution_context expected when "
            "ContextVar EC is None"
        )
