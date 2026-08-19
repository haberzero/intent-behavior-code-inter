"""
tests/kernel/test_enum_axiom.py
================================

EnumAxiom.from_prompt 解析行为契约。

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


@pytest.fixture
def int_enum_spec():
    """非 str 枚举 spec：members 为 dict，MemberSpec.metadata["value"] 承载成员值。

    镜像真实编译产物形态（symbol_collection_pass 写入 metadata["value"]）。
    """

    class _MS:
        def __init__(self, value):
            self.metadata = {"value": value}

    class _Spec:
        name = "Code"
        members = {"OK": _MS(200), "ERR": _MS(500)}

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


class TestEnumAxiomMemberValueMapping:
    """非 str 枚举 LLM 集成：成员名 → 成员值映射。"""

    def test_int_member_maps_to_value(self, axiom, int_enum_spec):
        ok, val = axiom.from_prompt("OK", int_enum_spec)
        assert ok is True
        assert val == 200

    def test_case_insensitive_maps_to_value(self, axiom, int_enum_spec):
        ok, val = axiom.from_prompt("  err  ", int_enum_spec)
        assert ok is True
        assert val == 500

    def test_str_value_ne_name_maps_to_value(self, axiom):
        class _MS:
            def __init__(self, value):
                self.metadata = {"value": value}

        class _Spec:
            name = "Status"
            members = {"ACTIVE": _MS("a")}

        ok, val = axiom.from_prompt("ACTIVE", _Spec())
        assert ok is True
        assert val == "a"

    def test_member_without_value_falls_back_to_name(self, axiom):
        class _MS:
            metadata = {}

        class _Spec:
            name = "Legacy"
            members = {"X": _MS()}

        ok, val = axiom.from_prompt("X", _Spec())
        assert ok is True
        assert val == "X"

    def test_output_hint_uses_member_names(self, axiom, int_enum_spec):
        hint = axiom.__outputhint_prompt__(int_enum_spec)
        assert "OK" in hint and "ERR" in hint


class TestEnumAxiomIterCap:
    """迭代/数量能力：has_iter_cap + get_method_specs（to_list/len）。"""

    def test_has_iter_cap(self, axiom):
        assert axiom.has_iter_cap is True

    def test_method_specs_declare_to_list_and_len(self, axiom):
        specs = axiom.get_method_specs()
        assert "to_list" in specs
        assert "len" in specs
        assert specs["len"].return_type.head == "int"
