"""NS-1 regression: LLM call paths flow through the VM CPS scheduling loop.

Verifies that when an ``@~ ... ~`` behavior expression is reached via the
normal VM pipeline (driven by an ``IbExprStmt`` / ``IbCall``), the VMTask
representing the behavior call is **on the frame stack** at the moment the
LLM executor's ``execute_behavior_object`` runs.

The probe is installed by monkey-patching the LLM executor's
``execute_behavior_object``/``execute_llm_function`` entries to capture
``vm.frame_stack_depth`` and ``vm.step_count``.
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


class TestNS1LLMCpsDispatch:
    def test_behavior_call_runs_under_vm_frame(self):
        engine = _make_engine()

        observations = {}

        # Patch the LLM executor's execute_behavior_object_cps (CPS variant
        # used by the VM handler path post-CPS-ification of _evaluate_segments).
        from core.runtime.interpreter.llm_executor import LLMExecutorImpl
        original = LLMExecutorImpl.execute_behavior_object_cps

        def probe(self, behavior, execution_context):
            vm = execution_context.vm_executor
            observations["depth"] = vm.frame_stack_depth
            observations["step_count_at_call"] = vm.step_count
            return (yield from original(self, behavior, execution_context))

        LLMExecutorImpl.execute_behavior_object_cps = probe
        try:
            # ``fn b = lambda: @~...~`` makes ``b`` an IbBehavior; calling it
            # goes through IbCall → _vm_invoke_behavior (NS-1 path).
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

        # NS-1 guarantee: VM frame stack is non-empty (>= 2 frames: at least
        # the IbCall driver task plus the _vm_invoke_behavior task) when the
        # LLM executor fires.
        assert observations.get("depth", 0) >= 2, (
            f"Expected VM frame stack depth >= 2 inside execute_behavior_object_cps, "
            f"got {observations.get('depth')}"
        )
        # And the helper advanced the scheduler.
        assert observations.get("step_count_at_call", 0) > 0

    def test_llm_function_call_runs_under_vm_frame(self):
        engine = _make_engine()

        observations = {}

        from core.runtime.interpreter.llm_executor import LLMExecutorImpl
        original = LLMExecutorImpl.execute_llm_function_cps

        def probe(self, node_uid, execution_context, call_intent=None):
            vm = execution_context.vm_executor
            observations["depth"] = vm.frame_stack_depth
            observations["step_count_at_call"] = vm.step_count
            return (yield from original(self, node_uid, execution_context, call_intent=call_intent))

        LLMExecutorImpl.execute_llm_function_cps = probe
        try:
            engine.run_string(
                _ai_prefix() + (
                    'llm greet(str name) -> str:\n'
                    '__sys__\n'
                    'You are a greeter.\n'
                    '__user__\n'
                    'MOCK:STR:hello\n'
                    'llmend\n'
                    '\n'
                    'str r = greet("Alice")\n'
                ),
                output_callback=lambda _t: None,
                silent=True,
            )
        finally:
            LLMExecutorImpl.execute_llm_function_cps = original

        assert observations.get("depth", 0) >= 2, (
            f"Expected VM frame stack depth >= 2 inside execute_llm_function_cps, "
            f"got {observations.get('depth')}"
        )
        assert observations.get("step_count_at_call", 0) > 0
