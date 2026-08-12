"""
tests/e2e/test_switch_usability.py
===================================

switch/case 易用性回归测试（2026-08-12）。

背景：KNOWN_LIMITS §十一 声称"switch 暂不在生产使用"（过度保守——实测 switch
功能完整）。且 case 内写 `break`（C 语言习惯）此前报 `RUN_GENERIC_ERROR:
Control flow statement used outside of function or loop`——IBCI switch 语义是
"匹配后自动跳出 case"（无 fall-through），break 是冗余但无害，应被接受为 no-op。

修复：
- vm_handle_IbSwitch 消费 case body 的 BREAK Signal（no-op）；
  RETURN/THROW/CONTINUE 透传（CONTINUE 可透传给外层循环）。
- KNOWN_LIMITS §十一 更新为"基本可用 + 使用约束"。
"""
from tests.conftest import run_ibci


class TestSwitchBreak:
    def test_switch_break_noop(self):
        """case 内 break（C 习惯）被接受为 no-op，不报错。"""
        code = """
int x = 2
switch x:
    case 1:
        print("one")
        break
    case 2:
        print("two")
        break
    case 3:
        print("three")
    default:
        print("other")
print("after_switch")
"""
        lines = run_ibci(code)
        assert "two" in lines
        assert "after_switch" in lines
        assert "three" not in lines
        assert "other" not in lines

    def test_switch_continue_propagates_to_outer_loop(self):
        """case 内 continue 透传给外层循环（switch 本身不是循环）。"""
        code = """
for int i in range(3):
    switch i:
        case 0:
            continue
        case 1:
            print("hit_one")
        default:
            print("hit_" + (str)i)
"""
        lines = run_ibci(code)
        assert "hit_one" in lines
        assert "hit_2" in lines
        assert not any("hit_0" in l for l in lines)

    def test_switch_value_string_enum_default(self):
        """switch 全语义：值/字符串/Enum/default/匹配后自动跳过。"""
        code = """
class Color(Enum):
    str RED = "RED"
    str GREEN = "GREEN"

str s = "b"
switch s:
    case "a":
        print("A")
    case "b":
        print("B")
    default:
        print("other")

int y = 99
switch y:
    case 1:
        print("one")
    default:
        print("fallback")

Color c = Color.GREEN
switch c:
    case Color.RED:
        print("red")
    case Color.GREEN:
        print("green")
    default:
        print("color_other")
"""
        lines = run_ibci(code)
        assert "B" in lines
        assert "fallback" in lines
        assert "green" in lines
        assert "A" not in lines
        assert "one" not in lines
