"""
tests/runtime/test_prompt_assembly.py — PromptPart model tests.
"""

from core.runtime.interpreter.llm_executor._prompt_assembly import (
    PromptPart,
    assemble_prompt_parts,
    build_prompt_parts,
    build_behavior_system_prompt,
)


class TestPromptPartModel:
    def test_assemble_skips_empty(self):
        parts = [PromptPart(kind="a", text="hello"), PromptPart(kind="b", text="")]
        assert assemble_prompt_parts(parts) == "hello"

    def test_build_prompt_parts_behavior_discipline(self):
        parts = build_prompt_parts(behavior_discipline=True, intents=["be nice"])
        kinds = [p.kind for p in parts]
        assert kinds == ["discipline", "intent"]

    def test_build_prompt_parts_type_constraint(self):
        parts = build_prompt_parts(type_hint="int", include_generic_type=True)
        assert any(p.kind == "type_constraint" for p in parts)

    def test_behavior_system_prompt_still_contains_sections(self):
        prompt = build_behavior_system_prompt(type_hint="int", intents=["be nice"])
        assert "只输出任务要求的结果数据本身" in prompt
        assert "必须返回一个 int 值" in prompt
        assert "be nice" in prompt
