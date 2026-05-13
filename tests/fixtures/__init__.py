"""
tests/fixtures/__init__.py
===========================

Reusable IBCI code samples for testing.

This module provides fixture collections organized by language concept:
- type_system_samples: Type annotations, Optional, generics, cast
- control_flow_samples: if/for/while/switch/break/continue
- llm_samples: behavior expressions, llmexcept, intent, retry
- edge_cases: Boundary conditions and corner cases

Usage:
    from tests.fixtures import BEHAVIOR_SAMPLES

    @pytest.mark.parametrize("sample_key", ["simple_mock", "with_intent"])
    def test_something(sample_key):
        code = BEHAVIOR_SAMPLES[sample_key]
        result = run_ibci(code)
        ...
"""
