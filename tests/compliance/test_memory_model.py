"""
tests/compliance/test_memory_model.py
======================================

IBCI VM 合规测试：内存模型契约（M1/M2 / SPEC §2）。

覆盖 docs/VM_SPEC.md §2 定义的以下契约：
  - 公理 SC-3/SC-4（IbCell）：lambda 通过共享 Cell 访问自由变量，
    外部修改对 lambda 可见（共享引用语义）
  - 公理 SC-3/SC-4（IbCell）：snapshot 通过独立 Cell 副本冻结自由变量，
    外部修改对 snapshot 不可见（值快照语义）
  - 公理 LT-2（Cell 延长生命周期）：外层作用域返回后，lambda 捕获的
    Cell 仍然活跃，lambda 可继续正确调用
  - 公理 LT-3（snapshot 自包含性）：snapshot 的生命周期独立于创建它的
    外层作用域
  - 值类型深拷贝等价：int/str/bool 赋值语义等价于深拷贝（无共享引用副作用）

合规性说明：本文件仅使用 ``IBCIEngine`` 公开 API，可作为未来跨宿主实现
的内存模型合规验证测试集。
"""
import os
import pytest

from core.engine import IBCIEngine


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


def run_code(code: str):
    lines: list = []
    eng = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
    eng.run_string(code, output_callback=lambda s: lines.append(str(s)), silent=True)
    return lines


# ===========================================================================
# SPEC §2.1 — lambda 共享 Cell 语义（公理 SC-3/SC-4）
# ===========================================================================

class TestLambdaSharedCell:
    """SPEC §2.1：lambda 通过共享 IbCell 读取自由变量（SC-3/SC-4）。"""

    def test_lambda_sees_latest_value_after_external_mutation(self):
        """lambda 应读到外部最新写入的值（共享 Cell 引用语义）。"""
        code = """
int x = 10
fn get_x = lambda: x
x = 20
print((str)(int)get_x())
"""
        out = run_code(code)
        assert any("20" in line for line in out), f"Expected '20', got {out}"

    def test_two_lambdas_share_same_cell_value(self):
        """两个 lambda 捕获同一变量，修改对两者均可见（Cell 共享）。"""
        code = """
int counter = 0
fn get_a = lambda: counter
fn get_b = lambda: counter
counter = 42
int va = (int)get_a()
int vb = (int)get_b()
print((str)va)
print((str)vb)
"""
        out = run_code(code)
        assert any("42" in line for line in out), f"Expected '42' in {out}"
        count_42 = sum(1 for l in out if "42" in l)
        assert count_42 == 2, f"Expected both lambdas to return 42, got {out}"

    def test_lambda_captures_multiple_free_vars(self):
        """lambda 可捕获多个自由变量，各变量独立更新互不影响。"""
        code = """
int a = 1
int b = 2
fn sum_ab = lambda: a + b
a = 10
int result = (int)sum_ab()
print((str)result)
"""
        out = run_code(code)
        assert any("12" in line for line in out), f"Expected '12', got {out}"


# ===========================================================================
# SPEC §2.2 — snapshot 值快照语义（公理 SC-3/SC-4）
# ===========================================================================

class TestSnapshotFrozenCell:
    """SPEC §2.2：snapshot 通过独立 Cell 副本冻结自由变量（SC-4 值快照语义）。"""

    def test_snapshot_is_unaffected_by_external_mutation(self):
        """snapshot 定义时冻结自由变量值，外部修改对 snapshot 不可见。"""
        code = """
int x = 10
fn frozen = snapshot: x
x = 99
int result = (int)frozen()
print((str)result)
"""
        out = run_code(code)
        assert any("10" in line for line in out), f"Expected '10' (frozen), got {out}"

    def test_snapshot_and_lambda_differ_after_mutation(self):
        """相同自由变量被 snapshot 和 lambda 同时捕获后，外部修改只影响 lambda。"""
        code = """
int val = 5
fn snap = snapshot: val
fn lam = lambda: val
val = 100
int snap_result = (int)snap()
int lam_result = (int)lam()
print((str)snap_result)
print((str)lam_result)
"""
        out = run_code(code)
        assert any("5" in line for line in out), f"Expected snapshot result 5, got {out}"
        assert any("100" in line for line in out), f"Expected lambda result 100, got {out}"


# ===========================================================================
# SPEC §2.3 — Cell 延长生命周期（公理 LT-2）
# ===========================================================================

class TestCellLifetimeExtension:
    """SPEC §2.3：外层作用域退出后，lambda 捕获的 Cell 仍可访问（LT-2）。"""

    def test_lambda_survives_outer_function_return(self):
        """返回 lambda 的工厂函数：lambda 在工厂作用域销毁后仍然可调用。"""
        code = """
func make_counter(int start) -> fn:
    int n = start
    fn increment = lambda: n + 1
    return increment

fn counter = make_counter(10)
int result = (int)counter()
print((str)result)
"""
        out = run_code(code)
        assert any("11" in line for line in out), f"Expected '11', got {out}"

    def test_closure_captures_correct_value_at_creation_time_for_snapshot(self):
        """snapshot 在创建时捕获值，而非调用时（与 lambda 行为对比）。"""
        code = """
func make_snapshot(int v) -> fn:
    fn snap = snapshot: v
    return snap

fn s = make_snapshot(7)
int result = (int)s()
print((str)result)
"""
        out = run_code(code)
        assert any("7" in line for line in out), f"Expected '7', got {out}"


# ===========================================================================
# SPEC §2.4 — 值类型赋值深拷贝等价（公理 OM-2）
# ===========================================================================

class TestValueTypeSemantics:
    """SPEC §2.4：值类型（int/str/bool）赋值等价于深拷贝，无共享引用副作用。"""

    def test_int_assignment_is_independent(self):
        """int 赋值后，修改原变量不影响副本变量。"""
        code = """
int x = 42
int y = x
x = 100
print((str)y)
"""
        out = run_code(code)
        assert any("42" in line for line in out), f"Expected '42', got {out}"

    def test_str_assignment_is_independent(self):
        """str 赋值后，修改原变量不影响副本变量。"""
        code = """
str s = "hello"
str t = s
s = "world"
print(t)
"""
        out = run_code(code)
        assert any("hello" in line for line in out), f"Expected 'hello', got {out}"

    def test_bool_assignment_is_independent(self):
        """bool 赋值后，修改原变量不影响副本变量。"""
        code = """
bool a = True
bool b = a
a = False
if b:
    print("b_is_true")
else:
    print("b_is_false")
"""
        out = run_code(code)
        assert any("b_is_true" in line for line in out), f"Expected 'b_is_true', got {out}"


# ===========================================================================
# SPEC §2.5 — lambda 作为高阶函数参数传递（公理 SC-4 / M2）
# ===========================================================================

class TestHigherOrderFunctionPassing:
    """SPEC §2.5：lambda 对象可以自由作为高阶函数参数传递（M2 出口契约）。"""

    def test_lambda_passed_to_function_and_called(self):
        """lambda 可作为函数参数传入并在函数内被调用。"""
        code = """
func apply(fn f, int n) -> auto:
    return f(n)

fn double = lambda(int x): x * 2
int result = (int)apply(double, 6)
print((str)result)
"""
        out = run_code(code)
        assert any("12" in line for line in out), f"Expected '12', got {out}"

    def test_lambda_returned_from_function_callable(self):
        """函数返回的 lambda 在外层作用域仍然可调用。"""
        code = """
func make_adder(int base) -> fn:
    fn adder = lambda(int x): base + x
    return adder

fn add5 = make_adder(5)
int result = (int)add5(3)
print((str)result)
"""
        out = run_code(code)
        assert any("8" in line for line in out), f"Expected '8', got {out}"
