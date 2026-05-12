"""
tests/compiler/test_chain_subscript.py
========================================

NS-6 链式下标 `(expr)[index]` 语法消歧。

历史问题：解析器在见到 `(IDENT[...]` 形式时进入推测式 cast 路径，把
`nested[0]` 当作 `Type[arg]` 形态的泛型 cast 目标，导致随后的 `[1]` 无法
正确归并为链式下标，报 PAR_001。

NS-6 收口策略：
- 推测块内部的 ``ParseControlFlowError`` 不再在块内被吞掉，改由 with 外侧
  的 try/except 接管，确保 speculate 失败时 ``success=False``、temp_tracker
  不被合并；
- 当类型节点本身是 ``IbSubscript`` 且 RPAREN 之后紧跟 `[` 时，立刻触发
  ParseControlFlowError 回退到分组表达式路径。
"""

import pytest

from core.engine import IBCIEngine


ROOT_DIR = "."


def _run(code: str):
    engine = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
    out = []
    engine.run_string(code, output_callback=lambda t: out.append(str(t)), silent=True)
    return out


# ===========================================================================
# 1. 元组的链式下标
# ===========================================================================

class TestTupleChainSubscript:
    def test_tuple_of_tuple_chain_subscript(self):
        """`(nested[0])[1]` 应解析为对内层元组的二次下标。"""
        out = _run("""
tuple nested = ((1, 2), (3, 4))
print((nested[0])[1])
print((nested[1])[0])
""")
        assert out == ["2", "3"]


# ===========================================================================
# 2. dict / list 嵌套场景的链式下标
# ===========================================================================

class TestDictListChainSubscript:
    def test_dict_value_chain_subscript(self):
        """`(d["key"])[i]` 形式：对 dict 的下标结果再做下标。"""
        out = _run("""
dict d = {"key": [10, 20, 30]}
print((d["key"])[1])
""")
        assert out == ["20"]

    def test_list_of_list_chain_subscript(self):
        """`(matrix[i])[j]` 形式：对 list-of-list 的二次下标。"""
        out = _run("""
list matrix = [[1, 2], [3, 4]]
print((matrix[0])[1])
print((matrix[1])[0])
""")
        assert out == ["2", "3"]


# ===========================================================================
# 3. 回归保护：泛型 cast `(list[int])arr` 仍然有效
# ===========================================================================

class TestGenericCastNotBroken:
    def test_generic_list_cast_still_works(self):
        """`(list[int])arr` 是合法 cast，不应被链式下标修复误伤。"""
        out = _run("""
list arr = [1, 2, 3]
list[int] typed = (list[int])arr
print(typed[0])
""")
        assert out == ["1"]

    def test_simple_primitive_cast_still_works(self):
        """`(int)x` 这种最常见的 cast 形式不应被影响。"""
        out = _run("""
str s = "42"
int n = (int)s
print(n)
""")
        assert out == ["42"]
