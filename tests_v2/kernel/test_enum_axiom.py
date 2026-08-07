"""
tests/kernel/test_enum_axiom.py
================================

EnumAxiom.from_prompt 收敛回归测试（PT-ARCH-33）。

覆盖：
* str 契约下枚举成员解析（大小写不敏感）。
* MOCK 哨兵值直通。
* 非 str 输入 fail-fast（不再双轨探测/静默兜底）。
"""
import pytest

from core.kernel.axioms.primitives.enum import EnumAxiom


@pytest.fixture
def axiom():
    return EnumAxiom()


@pytest.fixture
def enum_spec():
    """带成员的枚举 spec（假对象，仅暴露 name/members）。"""

    class _Spec:
        name = "Color"
        members = ["RED", "GREEN", "BLUE"]

    return _Spec()


class TestEnumAxiomFromPrompt:
    def test_parses_member_case_insensitive(self, axiom, enum_spec):
        ok, val = axiom.from_prompt(" green ", enum_spec)
        assert ok is True
        assert val == "GREEN"

    def test_parses_upper_member(self, axiom, enum_spec):
        ok, val = axiom.from_prompt("BLUE", enum_spec)
        assert ok is True
        assert val == "BLUE"

    def test_unmatched_returns_hint(self, axiom, enum_spec):
        ok, val = axiom.from_prompt("purple", enum_spec)
        assert ok is False
        assert "RED" in val

    def test_mock_ambiguous_sentinel_passthrough(self, axiom, enum_spec):
        ok, val = axiom.from_prompt("MAYBE_YES_MAYBE_NO_THIS_IS_AMBIGUOUS", enum_spec)
        assert ok is True

    def test_mock_bool_sentinels_passthrough(self, axiom, enum_spec):
        for raw in ("1", "0", "TRUE", "FALSE"):
            ok, val = axiom.from_prompt(raw, enum_spec)
            assert ok is True, raw

    def test_missing_spec_returns_hint(self, axiom):
        ok, val = axiom.from_prompt("RED", None)
        assert ok is False
        assert "缺少类型信息" in val

    def test_non_str_input_fails_fast(self, axiom, enum_spec):
        """非 str 输入属协议违反：fail-fast 抛 TypeError（不再双轨探测/静默兜底）。"""
        with pytest.raises(TypeError, match="expects str"):
            axiom.from_prompt(object(), enum_spec)
