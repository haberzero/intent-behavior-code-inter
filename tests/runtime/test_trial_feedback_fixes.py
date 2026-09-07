"""
tests/runtime/test_trial_feedback_fixes.py
==========================================

外部试用工程（ibci-trial）反馈缺陷的内核侧判别测试（P9a/P9b）：

- **P9a · len(dict) 函数形态返回 0**：根因 = ``IbDict`` 的
  "payload 与 fields 同一映射" 不变量在构造后被破坏（装箱/水化路径替换
  ``fields`` 后 ``payload`` 滞留空壳）。修复 = ``IbDict.fields`` 经 property
  落在 ``payload`` 上（与 ``IbList``/``IbTuple`` 的 ``elements`` property
  同构的单点真理约定）——双写真相结构上不可能。
- **P9b · 括号内比较被外层比较运算符误并入链式比较**：
  ``(a > b) == (c > d)`` 被解析为 ``a > b == c > d`` 链（左操作数错绑内层
  comparator，求值语义反转）。修复 = grouping 对括号内比较打
  ``_parenthesized`` 标记（解析期消费，不入产物），链式合并以括号为界。
"""

import pytest

from core.kernel.ast import IbCompare
from tests.conftest import compile_ibci, run_ibci


# --------------------------------------------------------------------------- #
# P9a · len(dict)（函数形态与 d.len() 一致）                                   #
# --------------------------------------------------------------------------- #

class TestLenDict:
    def test_dict_literal_len(self):
        lines = run_ibci(
            'dict d = {"x": 1, "y": 2, "z": 3}\n'
            'print("n=" + (str)len(d))\n'
            'print("m=" + (str)d.len())\n'
        )
        assert "n=3" in lines and "m=3" in lines

    def test_dict_growth_len(self):
        lines = run_ibci(
            'dict d = {}\n'
            'd["a"] = 1\n'
            'd["b"] = 2\n'
            'print("n=" + (str)len(d))\n'
            'print("contains=" + (str)d.contains("a"))\n'
        )
        assert "n=2" in lines and "contains=True" in lines

    def test_list_len_unchanged(self):
        lines = run_ibci('list l = [1, 2, 3]\nprint("n=" + (str)len(l))\n')
        assert "n=3" in lines


# --------------------------------------------------------------------------- #
# P9b · 括号比较独立性（求值语义）                                              #
# --------------------------------------------------------------------------- #

class TestParenthesizedCompareSemantics:
    def test_inline_bool_compare_not_inverted(self):
        lines = run_ibci(
            'list x = [1, 2]\n'
            'list y = []\n'
            'bool tt = (x.len() > 0) == (x.len() > 0)\n'
            'bool tf = (x.len() > 0) == (y.len() > 0)\n'
            'print("tt=" + (str)tt)\n'
            'print("tf=" + (str)tf)\n'
        )
        assert "tt=True" in lines and "tf=False" in lines

    def test_chained_compare_without_parens_preserved(self):
        lines = run_ibci(
            'bool c1 = 1 < 2 < 3\n'
            'bool c2 = 1 < 2 < 1\n'
            'print("c1=" + (str)c1)\n'
            'print("c2=" + (str)c2)\n'
        )
        assert "c1=True" in lines and "c2=False" in lines

    def test_chain_inside_parens_then_outer_compare(self):
        lines = run_ibci(
            'bool a = (1 < 2 < 3) == True\n'
            'bool b = (1 < 2 < 1) == False\n'
            'bool m = (2 > 1) == (3 > 2)\n'
            'print("a=" + (str)a)\n'
            'print("b=" + (str)b)\n'
            'print("m=" + (str)m)\n'
        )
        assert "a=True" in lines and "b=True" in lines and "m=True" in lines


# --------------------------------------------------------------------------- #
# P9b · 解析结构（链的边界以括号为界）                                          #
# --------------------------------------------------------------------------- #

def _find_compares(node, out):
    """遍历 AST 收集 IbCompare 节点。"""
    if node is None:
        return
    if isinstance(node, IbCompare):
        out.append(node)
    for attr in ("left", "ops", "comparators", "test", "body", "orelse",
                 "value", "slice", "func", "args", "keywords", "elts",
                 "key", "var", "type_", "items"):
        v = getattr(node, attr, None)
        if isinstance(v, list):
            for item in v:
                _find_compares(item, out)
        else:
            _find_compares(v, out)


def _root_compares(code):
    artifact = compile_ibci(code)
    module = artifact.modules[artifact.entry_module]
    out = []
    _find_compares(module.module_ast, out)
    return out


class TestParenthesizedCompareParse:
    def test_paren_left_operands_not_merged(self):
        """`(1 > 0) == (2 > 1)`：外层 IbCompare ops 仅 ['==']，左右均为独立
        IbCompare（不并入单链）。"""
        compares = _root_compares('bool b = (1 > 0) == (2 > 1)')
        assert len(compares) == 3
        outer = [c for c in compares if c.ops == ["=="]]
        assert len(outer) == 1
        outer = outer[0]
        assert isinstance(outer.left, IbCompare) and outer.left.ops == [">"]
        assert len(outer.comparators) == 1
        comp = outer.comparators[0]
        assert isinstance(comp, IbCompare) and comp.ops == [">"]

    def test_unparenthesized_chain_still_merged(self):
        """`1 > 0 == 2 > 1`（无括号，四操作数）：合并为单 IbCompare（链语义保持）。"""
        compares = _root_compares('bool b = 1 > 0 == 2 > 1')
        assert len(compares) == 1
        assert compares[0].ops == [">", "==", ">"]
        assert len(compares[0].comparators) == 3

    def test_inner_chain_not_affected(self):
        """括号内链式比较仍正常合并：`(1 < 2 < 3)` 内部为单 IbCompare。"""
        compares = _root_compares('bool b = (1 < 2 < 3)')
        inner = [c for c in compares if c.ops == ["<", "<"]]
        assert len(inner) == 1


# --------------------------------------------------------------------------- #
# P9a · 序列化水化路径（save/load_state 后 dict len 保真）                       #
# --------------------------------------------------------------------------- #

class TestDictLenAfterStateRoundtrip:
    def test_dict_len_after_load_state(self, tmp_path):
        """水化路径（_create_container_obj + fields 替换）同受 IbDict 不变量
        约束：load_state 后 len(dict) 与 d.len() 一致。"""
        lines = run_ibci(
            'import ihost\n'
            'dict d = {"a": 1, "b": 2}\n'
            f'ihost.save_state("{tmp_path}/st.json")\n'
            'd = {}\n'
            f'ihost.load_state("{tmp_path}/st.json")\n'
            'print("n=" + (str)len(d))\n'
            'print("m=" + (str)d.len())\n'
        )
        assert "n=2" in lines and "m=2" in lines
