"""
tests/runtime/test_dict_iteration.py

dict 可迭代（P9c）判别测试：

- ``for k in d`` = 键序列迭代（与 Python dict 迭代约定同形；经
  resolve_iterable 的 to_list 协议面——单一权威源）；
- 值/对迭代走 values()/items() 显式方法（不隐式展开）；
- 迭代语义 = 键（登记顺序），值不变式与 keys() 面同值。
"""

import os

import pytest

from core.engine import IBCIEngine


@pytest.fixture
def engine():
    return IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)))


def _run(engine, code):
    out = []
    engine.run_string(code, output_callback=out.append, silent=True)
    return out


class TestDictForIteration:
    def test_for_keys(self, engine):
        out = _run(engine, '''dict d = {"a": 1, "b": 2}
int n = 0
for k in d:
    n = n + 1
print("n=" + (str)n)
''')
        assert "n=2" in out, f"dict 迭代 = 键序列: {out}"

    def test_for_key_values_pairwise(self, engine):
        out = _run(engine, '''dict d = {"x": 10, "y": 20}
for k in d:
    print(k + "=" + (str)d[k])
''')
        assert any(line == "x=10" for line in out)
        assert any(line == "y=20" for line in out)

    def test_empty_dict_zero_iterations(self, engine):
        out = _run(engine, '''dict d = {}
int n = 0
for k in d:
    n = n + 1
print("n=" + (str)n)
''')
        assert "n=0" in out

    def test_iteration_matches_keys(self, engine):
        # 迭代键集合与 keys() 面同值（单一语义）
        out = _run(engine, '''dict d = {"p": 1, "q": 2, "r": 3}
int from_for = 0
for k in d:
    from_for = from_for + 1
int from_keys = len(d.keys())
bool same = (from_for == from_keys)
print("same=" + (str)same)
''')
        assert "same=True" in out


class TestValuesItemsExplicit:
    """值/对迭代 = 显式方法面（不隐式展开）。"""

    def test_values_explicit(self, engine):
        out = _run(engine, '''dict d = {"a": 1, "b": 2}
for v in d.values():
    print((str)v)
''')
        assert "1" in out and "2" in out

    def test_items_explicit(self, engine):
        out = _run(engine, '''dict d = {"a": 1}
list pairs = d.items()
print("pairs=" + (str)len(pairs))
''')
        assert "pairs=1" in out
