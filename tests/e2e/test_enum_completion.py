"""
tests/e2e/test_enum_completion.py

Enum 补全回归测试（PT-FEAT-2）：
* 非 str 枚举 LLM 集成（成员名 → 成员值映射，switch 命中）。
* 迭代 ``for v in Color:``（成员值列表）。
* 数量 ``len(Color)``。
* str 枚举 LLM 集成零回归（值==名）+ 值≠名场景。
"""

from tests.conftest import run_ibci


class TestEnumLLMIntegration:
    def test_int_enum_llm_maps_to_value_and_switch(self):
        code = """class Code(Enum):
    int OK = 200
    int ERR = 500
Code c = @~MOCK:STR:OK~
print((str)c)
switch c:
    case Code.OK:
        print("got-ok")
    default:
        print("other")
"""
        out = run_ibci(code, ai=True)
        assert out == ["200", "got-ok"]

    def test_int_enum_llm_case_insensitive(self):
        code = """class Code(Enum):
    int OK = 200
Code c = @~MOCK:STR:ok~
print((str)c)
print((str)(c == Code.OK))
"""
        out = run_ibci(code, ai=True)
        assert out == ["200", "True"]

    def test_str_enum_value_ne_name_llm(self):
        """str 枚举成员值≠名时 from_prompt 返回成员值（原按名==值碰巧工作）。"""
        code = """class Status(Enum):
    str ACTIVE = "a"
Status c = @~MOCK:STR:ACTIVE~
print((str)c)
print((str)(c == Status.ACTIVE))
"""
        out = run_ibci(code, ai=True)
        assert out == ["a", "True"]

    def test_str_enum_llm_zero_regression(self):
        code = """class Color(Enum):
    str RED = "RED"
    str GREEN = "GREEN"
Color c = @~MOCK:STR:GREEN~
print((str)c)
print((str)(c == Color.GREEN))
"""
        out = run_ibci(code, ai=True)
        assert out == ["GREEN", "True"]

    def test_negative_literal_int_enum_llm(self):
        """负数字面量成员（-1）经一元负号解析，LLM 成员名映射回负数值。"""
        code = """class Code(Enum):
    int OK = 200
    int NEG = -1
Code c = @~MOCK:STR:NEG~
print((str)c)
print((str)(c == Code.NEG))
"""
        out = run_ibci(code, ai=True)
        assert out == ["-1", "True"]


class TestEnumIteration:
    def test_for_iterates_str_member_values(self):
        code = """class Color(Enum):
    str RED = "RED"
    str GREEN = "GREEN"
for v in Color:
    print((str)v)
"""
        out = run_ibci(code)
        assert out == ["RED", "GREEN"]

    def test_for_iterates_int_member_values(self):
        code = """class Code(Enum):
    int OK = 200
    int ERR = 500
for v in Code:
    print((str)v)
"""
        out = run_ibci(code)
        assert out == ["200", "500"]


class TestEnumLen:
    def test_len_returns_member_count(self):
        code = """class Color(Enum):
    str RED = "RED"
    str GREEN = "GREEN"
    str BLUE = "BLUE"
print((str)len(Color))
"""
        out = run_ibci(code)
        assert out == ["3"]

    def test_len_int_enum(self):
        code = """class Code(Enum):
    int OK = 200
    int ERR = 500
print((str)len(Code))
"""
        out = run_ibci(code)
        assert out == ["2"]


class TestEnumRegression:
    def test_member_access_and_comparison(self):
        code = """class Color(Enum):
    str RED = "RED"
    str GREEN = "GREEN"
print((str)Color.RED)
Color c = Color.RED
print((str)(c == Color.RED))
print((str)(c != Color.GREEN))
"""
        out = run_ibci(code)
        assert out == ["RED", "True", "True"]

    def test_switch_still_matches(self):
        code = """class Color(Enum):
    str RED = "RED"
    str BLUE = "BLUE"
Color c = Color.BLUE
switch c:
    case Color.RED:
        print("red")
    case Color.BLUE:
        print("blue")
    default:
        print("other")
"""
        out = run_ibci(code)
        assert out == ["blue"]
