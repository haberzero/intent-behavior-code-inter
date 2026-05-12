"""_evaluate_segments CPS regression tests.

Verifies that the CPS-ified ``_evaluate_segments`` integrates with the VM
scheduler so that:

1. Prompt segment sub-evaluations are nested on the **outer** VM frame stack
   (rather than spawning a fresh ``_drive_loop`` via ``vm.run``).
2. The sync ``_evaluate_segments`` entry point still works for non-CPS
   callers (``dispatch_eager`` background thread, legacy tests).
3. Generator semantics are correct: yields node UIDs, accepts results back
   via ``.send``, returns final string via StopIteration.value.
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


class TestEvaluateSegmentsCPSGenerator:
    def test_cps_generator_basic_text(self):
        """No dynamic segments: generator returns plain string without yielding."""
        engine = _make_engine()
        engine.run_string('int _b = 1\n', output_callback=lambda _t: None, silent=True)
        from core.runtime.interpreter.llm_executor import LLMExecutorImpl
        llm_exec = engine.registry.get_llm_executor()
        ec = engine.interpreter._execution_context if hasattr(engine.interpreter, "_execution_context") else engine.interpreter.execution_context

        gen = llm_exec._evaluate_segments_cps(["hello ", "world"], ec)
        try:
            next(gen)
            assert False, "should have raised StopIteration immediately"
        except StopIteration as si:
            assert si.value == "hello world"

    def test_cps_generator_empty(self):
        engine = _make_engine()
        engine.run_string('int _b = 1\n', output_callback=lambda _t: None, silent=True)
        llm_exec = engine.registry.get_llm_executor()
        ec = engine.interpreter._execution_context if hasattr(engine.interpreter, "_execution_context") else engine.interpreter.execution_context

        try:
            next(llm_exec._evaluate_segments_cps(None, ec))
            assert False, "should have raised StopIteration"
        except StopIteration as si:
            assert si.value == ""

    def test_sync_wrapper_preserves_semantics(self):
        """The sync wrapper drives the generator via vm.run; semantics match."""
        engine = _make_engine()
        engine.run_string('int _b = 1\n', output_callback=lambda _t: None, silent=True)
        llm_exec = engine.registry.get_llm_executor()
        ec = engine.interpreter._execution_context if hasattr(engine.interpreter, "_execution_context") else engine.interpreter.execution_context

        # Plain string segments (no dynamic eval) — sync wrapper returns string.
        result = llm_exec._evaluate_segments(["a", "b", "c"], ec)
        assert result == "abc"


class TestEvaluateSegmentsCPSNesting:
    def test_segment_eval_nested_in_outer_vm_frame(self):
        """When a behavior with dynamic prompt segments runs, the inner
        segment-evaluation must be a sub-task of the OUTER VM frame
        (frame_stack_depth observed inside _evaluate_segments_cps reflects
        nesting, not a fresh _drive_loop)."""
        engine = _make_engine()

        from core.runtime.interpreter.llm_executor import LLMExecutorImpl
        observations = {"max_depth": 0, "segment_calls": 0}

        original_cps = LLMExecutorImpl._evaluate_segments_cps

        def probe_cps(self, segments, execution_context, param_names=None):
            observations["segment_calls"] += 1
            vm = execution_context.vm_executor
            if vm is not None:
                d = vm.frame_stack_depth
                if d > observations["max_depth"]:
                    observations["max_depth"] = d
            # Delegate to original (preserve generator semantics with yield from).
            result = yield from original_cps(self, segments, execution_context, param_names)
            return result

        LLMExecutorImpl._evaluate_segments_cps = probe_cps
        try:
            engine.run_string(
                _ai_prefix() + (
                    'fn b = lambda: @~MOCK:STR:hi~\n'
                    'str r = (str)b()\n'
                ),
                output_callback=lambda _t: None,
                silent=True,
            )
        finally:
            LLMExecutorImpl._evaluate_segments_cps = original_cps

        # Segment evaluation occurred under VM scheduling (≥ 1 frame deep).
        assert observations["segment_calls"] >= 1
        assert observations["max_depth"] >= 1, (
            f"Expected segment evaluation to run inside an active VM frame stack, "
            f"got max_depth={observations['max_depth']}"
        )
