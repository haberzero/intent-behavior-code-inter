"""
End-to-end tests for snapshot semantics: deep-clone + stateless + reentrant.

User clarification (2026-05-11):
    - lambda 不拷贝任何内容；调用时启用「当前活跃的意图栈」，自由变量经由
      共享 IbCell 引用——读现场。
    - snapshot 包裹并提供完全的深克隆，除调用时实参以外的所有内容都深克隆
      并冻结，作为完全的无状态且可重入的可调用实例存在。

本文件覆盖：
  1. snapshot 对可变容器（list/dict）的定义时深克隆 —— 外部突变不渗透。
  2. snapshot 的可重入性 —— 多次调用之间状态完全独立（每次再克隆种子）。
  3. snapshot 不缓存结果 —— 无参 snapshot 也不再走「首次求值后冻结」路径。
  4. lambda 的对照：仍按引用语义、读现场。
"""

import os
import pytest
from core.engine import IBCIEngine


def run_and_capture(code: str):
    lines = []
    engine = IBCIEngine(
        root_dir=os.path.dirname(os.path.abspath(__file__)),
        auto_sniff=False,
    )
    engine.run_string(
        code,
        output_callback=lambda t: lines.append(str(t)),
        silent=True,
    )
    return lines


# ---------------------------------------------------------------------------
# 1. snapshot 定义时深克隆：可变容器隔离
# ---------------------------------------------------------------------------


class TestSnapshotDeepCloneAtDefinition:
    """snapshot 在定义时对自由变量做深克隆；外部对原容器的就地突变不应影响 snapshot。"""

    def test_snapshot_isolates_list_from_outer_mutation(self):
        """外层在 snapshot 创建后向 list append——snapshot 仍读到定义时刻的列表。"""
        code = """list xs = [1, 2, 3]
fn snap = snapshot: xs.len()
print((str)snap())
xs.append(4)
xs.append(5)
print((str)snap())
"""
        # 旧实现（IbCell 浅包装）会让 snap() 第二次返回 5；
        # 深克隆后 snap() 两次都返回 3。
        assert run_and_capture(code) == ["3", "3"]

    def test_snapshot_isolates_dict_from_outer_mutation(self):
        """外层修改 dict 键值后，snapshot 看到的仍是定义时刻的状态。"""
        code = """dict d = {"k": 1}
fn snap = snapshot: (int)d["k"]
print((str)snap())
d["k"] = 999
print((str)snap())
"""
        assert run_and_capture(code) == ["1", "1"]

    def test_snapshot_with_param_isolates_list(self):
        """有参 snapshot：实参随调用变化，闭包 list 仍冻结。"""
        code = """list base = [10, 20]
fn add_first = snapshot(int x): base[0] + x
print((str)add_first(5))
base.append(999)
base[0] = 777
print((str)add_first(5))
"""
        # base[0] frozen at 10, so 10+5=15 both times.
        assert run_and_capture(code) == ["15", "15"]


# ---------------------------------------------------------------------------
# 2. snapshot 可重入：体内突变不跨调用
# ---------------------------------------------------------------------------


class TestSnapshotReentrancy:
    """snapshot 是无状态可重入的可调用实例：每次调用从冻结种子再深克隆。"""

    def test_snapshot_body_mutation_does_not_persist_across_calls(self):
        """snapshot 体内 append 到闭包 list；下次调用应仍看到原始长度。"""
        code = """func _mutate_count(list b) -> int:
    b.append(99)
    return b.len()

list buf = [1, 2]
fn snap = snapshot: _mutate_count(buf)
print((str)snap())
print((str)snap())
print((str)snap())
"""
        # 若闭包种子被共享，则 3、4、5；若每次重新克隆，则 3、3、3。
        assert run_and_capture(code) == ["3", "3", "3"]

    def test_snapshot_dict_mutation_isolation(self):
        """snapshot 体内修改闭包 dict 的键值；下次调用应仍读到种子原始值。"""
        code = """func _bump(dict d) -> int:
    int n = (int)d["n"] + 1
    d["n"] = n
    return n

dict d = {"n": 0}
fn snap = snapshot: _bump(d)
print((str)snap())
print((str)snap())
print((str)snap())
"""
        # 每次都从种子开始：种子 n=0 → +1 → 1
        assert run_and_capture(code) == ["1", "1", "1"]

    def test_snapshot_with_params_reentrant(self):
        """有参 snapshot：闭包种子在调用间隔保持新鲜，调用之间互不干扰。"""
        code = """func _add(list s, int d) -> int:
    int newv = (int)s[0] + d
    s[0] = newv
    return newv

list shared = [0]
fn snap = snapshot(int delta): _add(shared, delta)
print((str)snap(5))
print((str)snap(7))
print((str)snap(100))
"""
        # 种子 shared=[0]，每次都从 0 起加上 delta
        assert run_and_capture(code) == ["5", "7", "100"]


# ---------------------------------------------------------------------------
# 3. snapshot 无缓存：无参 snapshot 也每次重新求值
# ---------------------------------------------------------------------------


class TestSnapshotNoCache:
    """删除 _cache 短路后，snapshot 不再缓存任何结果。"""

    def test_no_param_snapshot_does_not_pollute_outer_seed(self):
        """无参 snapshot 调用多次，外层的 list 始终不变（深克隆 + 无缓存共同保证）。

        若仍存在旧 _cache，第一次 snap() 调用会让 body 跑一次并把 seed[0] mutate
        为 84；之后所有 snap() 都直接返回 cache 而不重新跑 body，那么 seed 是否
        被外部观测到变化、依赖于初次执行环境——这一路在旧实现下其实也不会污染
        外层（因为定义时已 IbCell(val) 浅包装），所以本测试焦点是：删除 cache
        之后 body 反复执行，外层 seed 仍然纯净——证明每次都是从冻结种子深克隆。
        """
        code = """func _double_first(list s) -> int:
    int v = (int)s[0] * 2
    s[0] = v
    return v

list seed = [42]
fn snap = snapshot: _double_first(seed)
print((str)snap())
print((str)snap())
print((str)seed[0])
print((str)seed.len())
"""
        # snap() 每次都从种子 [42] 深克隆 → 体内 *2 → 返回 84。
        # 外层 seed 始终保持 [42]。
        assert run_and_capture(code) == ["84", "84", "42", "1"]


# ---------------------------------------------------------------------------
# 4. lambda 对照：引用语义保持
# ---------------------------------------------------------------------------


class TestLambdaReferenceSemantics:
    """lambda 不深克隆任何东西——外部突变与体内突变都跨调用可见。"""

    def test_lambda_sees_outer_mutation(self):
        code = """list xs = [1, 2, 3]
fn read = lambda: xs.len()
print((str)read())
xs.append(4)
xs.append(5)
print((str)read())
"""
        # lambda 共享 cell → 第二次读到新长度。
        assert run_and_capture(code) == ["3", "5"]

    def test_lambda_body_mutation_persists(self):
        """lambda 体内对闭包容器的突变应跨调用可见（共享 cell）。"""
        code = """func _push_one(list b) -> int:
    b.append(1)
    return b.len()

list buf = []
fn push = lambda: _push_one(buf)
print((str)push())
print((str)push())
print((str)push())
"""
        assert run_and_capture(code) == ["1", "2", "3"]
