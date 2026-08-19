"""
tests/runtime/test_prompt_assembly.py — 推荐系统提示词组装模板（core.base）测试。

LLM 调用层插件化后，系统提示词组装（"把语义槽变为提示词"）是**推荐实现**，
位于 ``core.base.llm_protocol.recommended``（供应商无关）；本文件锁定其
判别性行为：纪律段落 / 类型约束 / 意图要求 的有序呈现与空值跳过。
"""

from core.base.llm_protocol import (
    IntentBlock,
    OutputContract,
    PromptSlot,
    assemble_system_prompt,
    type_constraint_section,
    intent_section,
)


class TestRecommendedAssembly:
    def test_assemble_skips_empty(self):
        # 空意图/空契约 → 仅有纪律段落（空值跳过，不产生空段）
        prompt = assemble_system_prompt(
            intents=IntentBlock(), output_contract=OutputContract()
        )
        assert prompt is not None
        assert "只输出任务要求的结果数据本身" in prompt

    def test_discipline_then_intent_ordering(self):
        prompt = assemble_system_prompt(
            intents=IntentBlock(merged=["be nice"]),
            output_contract=OutputContract(),
        )
        assert prompt.index("只输出任务要求的结果数据本身") < prompt.index("be nice")

    def test_type_constraint_section(self):
        c = OutputContract(expected_type="int")
        part = type_constraint_section(c)
        assert part is not None
        assert "必须返回一个 int 值" in part

    def test_behavior_system_prompt_still_contains_sections(self):
        prompt = assemble_system_prompt(
            intents=IntentBlock(merged=["be nice"]),
            output_contract=OutputContract(expected_type="int"),
        )
        assert "只输出任务要求的结果数据本身" in prompt
        assert "必须返回一个 int 值" in prompt
        assert "be nice" in prompt

    def test_suppress_type_constraint_omits_type(self):
        prompt = assemble_system_prompt(
            intents=IntentBlock(merged=["be nice"]),
            output_contract=OutputContract(expected_type="bool", suppress_type_constraint=True),
        )
        assert "bool" not in prompt
        assert "be nice" in prompt

    def test_custom_slot_rendered_in_order(self):
        """自定义附加槽（P4c 迁移：user_sys 前置特殊处理删除，任意 kind 自定义槽
        统一走通用呈现路径，机制同构）。"""
        prompt = assemble_system_prompt(
            intents=IntentBlock(),
            output_contract=OutputContract(),
            extra_slots=[PromptSlot(kind="user_sys", text="你是解析器。")],
        )
        assert "你是解析器。" in prompt
        assert "只输出任务要求的结果数据本身" in prompt

    def test_intent_section_helper(self):
        part = intent_section(["a", "b"])
        assert part is not None
        assert "- a" in part and "- b" in part
