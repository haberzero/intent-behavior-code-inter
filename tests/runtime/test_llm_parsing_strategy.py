"""
tests/runtime/test_llm_parsing_strategy.py
===========================================

LLM 结果解析责任链（Axiom → VTable → Default）中 Default 兜底策略的语义测试。

DefaultParsingStrategy 的契约：
* 无真实输出契约（空类型名 / auto / any / 行为本体 behavior / fn_callable）
  → 原始字符串 box 为 str（success）。
* 已声明的具体类型却无任何解析能力（无 __from_prompt__/parser）→ uncertain
  （编译期 SEM_BEHAVIOR_OUTPUT_NOT_PARSEABLE 拦截主要路径，此处为运行时兜底）。
* 有解析能力的类型（str/int 等）由 Axiom 策略先行处理，不落入 Default。
"""
from core.runtime.interpreter.llm_parsing_strategy import DefaultParsingStrategy


class TestDefaultParsingStrategy:
    """Default 兜底策略的 box/uncertain 语义。"""

    def _strategy(self, engine):
        return DefaultParsingStrategy(engine.registry)

    def test_empty_type_name_boxes_as_string(self, engine):
        """无类型名（无契约）→ box 为字符串 success。"""
        engine.run_string("int seed = 1\n", silent=True)
        res = self._strategy(engine).parse("raw", "", "n1", None)
        assert not res.is_uncertain
        assert res.value.to_native() == "raw"

    def test_unknown_type_name_boxes_as_string(self, engine):
        """未知类型名（无 descriptor）→ 保守 box 为字符串。"""
        engine.run_string("int seed = 1\n", silent=True)
        res = self._strategy(engine).parse("raw", "TotallyUnknown", "n1", None)
        assert not res.is_uncertain
        assert res.value.to_native() == "raw"

    def test_behavior_marker_boxes_as_string(self, engine):
        """行为本体（-> any 的运行时 type_hint）→ box（无真实输出契约）。"""
        engine.run_string("int seed = 1\n", silent=True)
        for tn in ("behavior", "fn_callable", "any", "auto"):
            res = self._strategy(engine).parse("raw", tn, "n1", None)
            assert not res.is_uncertain, f"{tn} 应 box 为字符串"
            assert res.value.to_native() == "raw"

    def test_declared_unparseable_type_returns_uncertain(self, engine):
        """已声明的具体类型（用户类）无解析能力 → uncertain，携带可读 retry_hint。

        [S2 类身份统一] 入口模块用户类已 module 化（qualified 名），LLM parse
        链的 type_name 为 qualified 名（__string_exec__.Point），策略内
        ``meta_reg.resolve`` 精确命中 qualified 键。
        """
        engine.run_string(
            "class Point:\n"
            "    int x\n"
            "    func __init__(self, int x) -> auto:\n"
            "        self.x = x\n",
            silent=True,
        )
        meta_reg = engine.registry.get_metadata_registry()
        entry_module = engine.interpreter.entry_module
        point = meta_reg.resolve("Point", entry_module)
        assert point is not None and point.module_path == entry_module
        type_name = point.qualified_name
        res = self._strategy(engine).parse("raw", type_name, "n1", None)
        assert res.is_uncertain
        assert "Point" in res.retry_hint

    def test_parseable_type_not_handled_here(self, engine):
        """有解析能力的类型（str）由 Axiom 先行处理；Default 的判定不应误伤。"""
        engine.run_string("int seed = 1\n", silent=True)
        strategy = self._strategy(engine)
        assert strategy._is_declared_unparseable("str") is False
