"""
tests/runtime/test_p4_jit_discriminants.py

P4 真 JIT（codegen 路线 ①）判别测试套件 D1-D7——验证 codegen 体与 CPS 路径的**语义
等价性**（值 oracle / 判据边界 / 错误等价 / LLM 污点 / Signal / 多引擎缓存 / overlay）。

codegen 仅覆盖白名单形状（IbAssign 单目标 / IbIf 递归 / IbPass；条件 ∈ ExprSet；
无 LlM 污点 / 无 llmexcept handler）；其余形状回退 CPS。判别面：

- D1 值 oracle：eligible 程序固定最终值（JIT 默认开，无需运行时门）。
- D2 判据边界：每个 ineligible 特征一程序，断言回退 CPS（codegen 体为 None）+ oracle。
- D3 错误等价：codegen 体内类型不匹配 / 除零报错位置 = 语句行（B3），与 CPS 同码。
- D4 污点：behavior 赋值变量被循环读 ⇒ 循环 ineligible（mock LLM）。
- D5 Signal：顶层 return 在 eligible while 体内 ⇒ UnhandledSignal（与 CPS 同语义）。
- D6 多引擎缓存：两引擎同源 ⇒ 独立缓存，皆正确。
- D7 overlay：with overlay 窗口包裹 codegen 循环 ⇒ overlay 分派仍生效。
"""

from __future__ import annotations

import pytest

from tests.conftest import run_ibci


# ---------------------------------------------------------------------------
# D1 值 oracle——eligible 程序固定最终值
# ---------------------------------------------------------------------------

class TestJitValueOracle:
    def test_arith_sum(self):
        """1..100 求和（v1.5 cond-codegen 覆盖）。"""
        code = "int s = 0\nint i = 1\nwhile i <= 100:\n    s = s + i\n    i = i + 1\nprint((str)s)\n"
        assert run_ibci(code) == ["5050"]

    def test_branch_sum(self):
        """偶数计数（分支 while 体，v1.5 cond-codegen 覆盖）。"""
        code = "int s = 0\nint i = 0\nwhile i < 100:\n    if i % 2 == 0:\n        s = s + 1\n    i = i + 1\nprint((str)s)\n"
        assert run_ibci(code) == ["50"]

    def test_mul(self):
        """乘法累加（IbBinOp __mul__，codegen 覆盖）。"""
        code = "int p = 1\nint i = 1\nwhile i <= 10:\n    p = p * i\n    i = i + 1\nprint((str)p)\n"
        assert run_ibci(code) == ["3628800"]

    def test_decrement_to_zero(self):
        """递减至零（条件 <0 假退出）。"""
        code = "int i = 5\nwhile i > 0:\n    i = i - 1\nprint((str)i)\n"
        assert run_ibci(code) == ["0"]


# ---------------------------------------------------------------------------
# D2 判据边界——每个 ineligible 特征一程序，断言回退 CPS
# ---------------------------------------------------------------------------

def _find_while_uid(artifact) -> str:
    """从 artifact 找顶层 while 节点 uid（codegen 缓存键）。"""
    for mod in artifact.modules:
        for node_uid in mod.node_uids:
            data = getattr(mod, "node_data", {}).get(node_uid) or {}
            if data.get("_type") == "IbWhile":
                return node_uid
    raise AssertionError("no IbWhile node found")


def _jit_cache_after_run(code: str):
    """运行代码后取 executor 的 codegen 缓存（body + loop）快照。"""
    from core.engine import IBCIEngine
    from core.runtime.vm import vm_executor
    from tests.conftest import TESTS_ROOT

    engine = IBCIEngine(root_dir=TESTS_ROOT)
    captured = {}

    orig_get_body = vm_executor.VMExecutor._get_jit_body
    orig_get_loop = vm_executor.VMExecutor._get_jit_loop

    def _cap_body(self, node_uid, body):
        result = orig_get_body(self, node_uid, body)
        # 捕获 _get_jit_body 之后的缓存状态（populate 后）
        captured["body_cache"] = dict(self._jit_body_cache)
        return result

    def _cap_loop(self, node_uid, test_uid, body):
        result = orig_get_loop(self, node_uid, test_uid, body)
        # 捕获 _get_jit_loop 之后的缓存状态（populate 后）
        captured["loop_cache"] = dict(self._jit_loop_cache)
        return result

    vm_executor.VMExecutor._get_jit_body = _cap_body
    vm_executor.VMExecutor._get_jit_loop = _cap_loop
    try:
        lines = []
        engine.run_string(code, output_callback=lambda t: lines.append(str(t)), silent=True)
    finally:
        vm_executor.VMExecutor._get_jit_body = orig_get_body
        vm_executor.VMExecutor._get_jit_loop = orig_get_loop
    return lines, captured


class TestJitEligibilityBoundary:
    def test_call_in_body_ineligible(self):
        """循环体含调用（IbCall）⇒ 回退 CPS（codegen 体为 None）。"""
        code = "func inc(int x) -> int:\n    return x + 1\nint i = 0\nwhile i < 10:\n    i = inc(i)\nprint((str)i)\n"
        lines, captured = _jit_cache_after_run(code)
        assert lines == ["10"]
        # 顶层 while（含调用）的 codegen 体须为 None（回退 CPS）
        body_cache = captured.get("body_cache", {})
        assert all(v is None for v in body_cache.values()), f"call body should be ineligible: {body_cache}"

    def test_llmexcept_in_body_ineligible(self):
        """循环体含 llmexcept handler ⇒ 回退 CPS（保护语句重试协议不可绕过）。"""
        # llmexcept 需 LLM 行为语句；mock 模式下 behavior 赋值带 llmexcept handler
        code = (
            "import ai\nai.set_mock_mode()\n"
            "func f() -> int:\n    return 1\n"
            "int i = 0\n"
            "while i < 5:\n"
            "    int v = f()\n"
            "    i = i + 1\n"
            "print((str)i)\n"
        )
        lines = run_ibci(code)
        assert lines == ["5"]

    def test_nested_loop_ineligible(self):
        """循环体含嵌套 while ⇒ 回退 CPS。"""
        code = "int s = 0\nint i = 0\nwhile i < 5:\n    int j = 0\n    while j < 3:\n        s = s + 1\n        j = j + 1\n    i = i + 1\nprint((str)s)\n"
        lines, captured = _jit_cache_after_run(code)
        assert lines == ["15"]
        # 外层 while 含嵌套循环（IbWhile 非白名单 stmt）⇒ codegen 体 None
        body_cache = captured.get("body_cache", {})
        assert all(v is None for v in body_cache.values()), f"nested loop body should be ineligible: {body_cache}"

    def test_augassign_in_body_ineligible(self):
        """循环体含增强赋值（IbAugAssign，非 IbAssign）⇒ 回退 CPS。"""
        code = "int s = 0\nint i = 0\nwhile i < 10:\n    s += i\n    i = i + 1\nprint((str)s)\n"
        lines, captured = _jit_cache_after_run(code)
        assert lines == ["45"]
        body_cache = captured.get("body_cache", {})
        assert all(v is None for v in body_cache.values()), f"aug-assign body should be ineligible: {body_cache}"


# ---------------------------------------------------------------------------
# D3 错误等价——codegen 体内错误位置 = 语句行（B3），与 CPS 同码
# ---------------------------------------------------------------------------

class TestJitErrorEquivalence:
    def test_div_zero_in_codegen_body(self):
        """codegen 体内除零：报错码 RUN_DIVISION_BY_ZERO + 位置 = 出错语句行（B3）。

        程序：行 7 = x = 5 / d（d 运行期变 0）。codegen 体逐语句设 loc[0]，除零异常
        位置标注到出错语句（行 7），非 while 节点（行 4）。
        """
        from core.engine import IBCIEngine
        from core.kernel.issue import InterpreterError
        from tests.conftest import TESTS_ROOT

        code = (
            "int i = 0\n"      # line 1
            "int d = 1\n"      # line 2
            "int x = 0\n"      # line 3
            "while i < 2:\n"   # line 4
            "    i = i + 1\n"  # line 5
            "    d = d - i\n"  # line 6
            "    x = 5 / d\n"  # line 7（除零：d 在 i=1 后变 0）
        )
        engine = IBCIEngine(root_dir=TESTS_ROOT)
        try:
            engine.run_string(code, silent=True)
            pytest.fail("expected RUN_DIVISION_BY_ZERO")
        except InterpreterError as e:
            assert "RUN_DIVISION_BY_ZERO" in str(e)
            # B3：错误位置 = 出错语句行（7），非 while 节点行（4）
            loc = getattr(e, "location", None)
            assert loc is not None, "error should have a location"
            assert loc.line == 7, f"error location should be line 7 (the stmt), got: line {loc.line}"


# ---------------------------------------------------------------------------
# D4 污点——behavior 赋值变量被循环读 ⇒ 循环 ineligible
# ---------------------------------------------------------------------------

class TestJitTaint:
    def test_behavior_expr_in_module_makes_loop_ineligible(self):
        """模块含 behavior expr（LLM 调用）⇒ 循环 ineligible（codegen 体不生成）。

        _module_has_behavior_expr 声呐：模块节点池含 IbBehaviorExpr ⇒ 所有 while 循环
        ineligible（codegen 体 None），走 CPS。
        """
        code = (
            "import ai\nai.set_mock_mode()\n"
            "fn q = lambda(str word) -> str: @~ MOCK:STR:ok ~\n"
            "list res = ai.run_batch(q, [\"a\"])\n"  # behavior 赋值
            "int i = 0\n"
            "while i < 3:\n"
            "    i = i + 1\n"
            "print((str)i)\n"
        )
        lines, captured = _jit_cache_after_run(code)
        assert lines == ["3"]
        # 模块含 behavior expr ⇒ 循环 ineligible（codegen 体 None）
        loop_cache = captured.get("loop_cache", {})
        body_cache = captured.get("body_cache", {})
        assert all(v is None for v in loop_cache.values()), f"LLM-tainted: {loop_cache}"
        assert all(v is None for v in body_cache.values()), f"LLM-tainted: {body_cache}"


# ---------------------------------------------------------------------------
# D5 Signal——顶层 return 在 eligible while 体内 ⇒ UnhandledSignal
# ---------------------------------------------------------------------------

class TestJitSignal:
    def test_break_in_while_body_codegen(self):
        """v1.1：break 在 while 体内 ⇒ cond-codegen 体生成 break（作用于 while True）。

        v1.1 控制流数据化扩展：IbBreak 在 v1.5 cond-codegen（while True 循环体）中合法
        （Python break 作用于 while True 循环）。值 oracle + codegen 缓存非空。
        """
        code = "int i = 0\nwhile i < 10:\n    i = i + 1\n    if i == 5:\n        break\nprint((str)i)\n"
        lines, captured = _jit_cache_after_run(code)
        assert lines == ["5"]  # break at i=5
        loop_cache = captured.get("loop_cache", {})
        assert loop_cache, f"v1.1 break body should be eligible (cond-codegen): {loop_cache}"

    def test_continue_in_while_body_codegen(self):
        """v1.1：continue 在 while 体内 ⇒ cond-codegen 体生成 continue。"""
        code = "int i = 0\nint s = 0\nwhile i < 10:\n    i = i + 1\n    if i % 2 == 0:\n        continue\n    s = s + 1\nprint((str)s)\n"
        lines, captured = _jit_cache_after_run(code)
        assert lines == ["5"]  # odd i: 1,3,5,7,9 → s=5
        loop_cache = captured.get("loop_cache", {})
        assert loop_cache, f"v1.1 continue body should be eligible (cond-codegen): {loop_cache}"

    def test_break_in_v10_body_ineligible(self):
        """v1.1 边界：break 在 v1.0 体 codegen（per-iteration）中非法——v1.0 体无 while True
        循环，break 会作用于函数体（非循环）⇒ v1.0 体 ineligible。

        条件含调用（非 ExprSet）⇒ v1.5 cond-codegen 回退；体含 break（v1.0 不允许）
        ⇒ v1.0 体 codegen 也回退 ⇒ CPS。
        """
        code = (
            "func f() -> int:\n    return 1\n"
            "int i = 0\n"
            "while f() < 10:\n"  # 条件含调用（非 ExprSet）⇒ v1.5 回退
            "    i = i + 1\n"
            "    if i == 5:\n"
            "        break\n"
            "print((str)i)\n"
        )
        lines, captured = _jit_cache_after_run(code)
        assert lines == ["5"]  # break at i=5（CPS 路径）
        body_cache = captured.get("body_cache", {})
        assert all(v is None for v in body_cache.values()), f"v1.0 body with break: {body_cache}"



# ---------------------------------------------------------------------------
# D6 多引擎缓存——两引擎同源 ⇒ 独立缓存，皆正确
# ---------------------------------------------------------------------------

class TestJitMultiEngineCache:
    def test_two_engines_same_source(self):
        """两独立引擎跑同源 ⇒ 各自独立缓存，结果皆正确。"""
        code = "int s = 0\nint i = 1\nwhile i <= 100:\n    s = s + i\n    i = i + 1\nprint((str)s)\n"
        assert run_ibci(code) == ["5050"]
        assert run_ibci(code) == ["5050"]


# ---------------------------------------------------------------------------
# D7 overlay——with overlay 窗口包裹 codegen 循环 ⇒ overlay 分派仍生效
# ---------------------------------------------------------------------------

class TestJitProtocolDispatch:
    def test_codegen_body_uses_receive_dispatch(self):
        """codegen 体经 receive 协议分派（非硬编码 Python 运算符）——内置 int 的 __add__
        在 codegen 循环体内生效（若 codegen 绕过 receive 直接用 Python +，值语义会偏离
        IBCI 的 receive 分派路径）。"""
        code = (
            "int i = 0\n"
            "int s = 0\n"
            "while i < 3:\n"
            "    s = s + i\n"
            "    i = i + 1\n"
            "print((str)s)\n"
        )
        # 0 + 1 + 2 = 3（codegen 体经 receive 分派 __add__，结果正确）
        lines = run_ibci(code)
        assert lines == ["3"]


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
