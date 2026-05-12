"""
tests/runtime/test_uncertain_str_concat_prohibition.py
=======================================================

NS-4 收紧：禁止 `str + llm_uncertain` 隐式拼接。

覆盖三条关键路径：

1. **llmexcept body 内**：当 LLM 返回不确定值时，目标变量被写入 `IbLLMUncertain`
   哨兵；此时在 body 内做 ``"prefix: " + x`` 拼接应抛 ``LLMParseError``，
   而非静默 coerce 为 ``"prefix: uncertain"``。
2. **`(str)uncertain_var` 显式转换仍可用**：用户主动观察哨兵的合法路径必须保留。
3. **`StrAxiom.resolve_operation_type_name`**：直接询问公理时，`str + llm_uncertain`
   不再返回 ``"str"``（编译期同样不再放行）。
"""

from core.engine import IBCIEngine


ROOT_DIR = "."


def ai_setup():
    return 'import ai\nai.set_config("TESTONLY", "TESTONLY", "TESTONLY")\n'


def make_engine(code: str, output_lines=None):
    engine = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
    cb = (lambda t: output_lines.append(str(t))) if output_lines is not None else (lambda t: None)
    engine.run_string(code, output_callback=cb, silent=True)
    return engine


# ===========================================================================
# 1. llmexcept body 内 `str + uncertain` 应抛 LLMParseError
# ===========================================================================

class TestUncertainConcatRaisesInLlmexceptBody:
    def test_concat_in_llmexcept_body_caught_by_try_except(self):
        """在 llmexcept body 内做 `str + uncertain` 必须可被 try/except LLMParseError 捕获。"""
        lines = []
        # MOCK:REPAIR 第一次返回 uncertain，触发 llmexcept body；body 内尝试
        # `"got: " + x` 现在应抛 LLMParseError，被外层 try/except 捕获。
        code = ai_setup() + """
try:
    str x = @~ MOCK:REPAIR concat_in_body ~
    llmexcept:
        print("got: " + x)
        retry
except LLMParseError as e:
    print("parse_caught")
print("after")
"""
        engine = make_engine(code, lines)
        assert "parse_caught" in lines
        assert "after" in lines
        # 关键反例：旧行为会输出 "got: uncertain"，新行为不应出现
        assert not any("got: uncertain" in line for line in lines)


# ===========================================================================
# 2. `(str)uncertain_var` 显式转换仍可用
# ===========================================================================

class TestExplicitCastStillWorks:
    def test_explicit_cast_uncertain_to_str_returns_uncertain_text(self):
        """`(str)uncertain_var` 显式转换是用户明确意图，必须保留为 \"uncertain\" 文本。"""
        lines = []
        code = ai_setup() + """
try:
    str x = @~ MOCK:REPAIR explicit_cast ~
    llmexcept:
        str s = (str)x
        print("cast: " + s)
        retry
except LLMParseError as e:
    print("should_not_caught")
print("done")
"""
        engine = make_engine(code, lines)
        # (str)uncertain → "uncertain"，参与拼接得到 "cast: uncertain"
        assert "cast: uncertain" in lines
        assert "done" in lines
        assert "should_not_caught" not in lines


# ===========================================================================
# 3. 公理层：StrAxiom.resolve_operation_type_name 不再放行
# ===========================================================================

class TestStrAxiomNoLongerAllowsUncertain:
    def test_str_axiom_rejects_uncertain_for_plus(self):
        """直接询问 StrAxiom：`str + llm_uncertain` 应返回 None（与 SEM_003 一致）。"""
        from core.kernel.axioms.primitives import StrAxiom
        axiom = StrAxiom()
        # 旧行为：返回 "str"；NS-4 收紧后：返回 None
        assert axiom.resolve_operation_type_name("+", "llm_uncertain") is None
        # 反例确认：str + str 仍正确
        assert axiom.resolve_operation_type_name("+", "str") == "str"
