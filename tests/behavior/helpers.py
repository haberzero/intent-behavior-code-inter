"""语言行为层（测试体系五层重构——使命 2 / 架构 v2 R3 阶段 A）。

**层定位**：源 → 可观察面（print 数据面 / 错误码+结构化现场 / 状态语义值），
经**公共 engine API**（IBCIEngine.run_string / compile_string）验证，**内核
无关**（Rust/Python 内核皆可过——迁移期双跑差分，迁移后 Rust 单跑）。

**断言面纪律（强制）**：
- 断言可观察面（数据面行 / 诊断码 + 现场位置 / 状态值语义），**不断言实现
  内部形态**（payload 对象类型 / 符号表结构 / VM 内部）。
- 错误断言经**诊断码 + 结构化现场**（``assert_error(code, error_code, line,
  column)``），**不经异常消息子串**（旧 conftest expect_runtime_error 消息
  子串匹配 = 时代错位，本层弃用）。

与差分 harness 的关系：本层 = 内核无关行为断言（显式预期），非双内核对比；
diff_harness 语料/探针为迁移期种子（⑦ 终点差分机制退场，语料正式升格本层）。
"""

from __future__ import annotations

from typing import List, Optional

from tests.conftest import TESTS_ROOT


def run(code: str, *, variables: Optional[dict] = None) -> List[str]:
    """编译 + 执行 IBCI 代码，返回 print 输出行列表（公共 engine API）。

    断言数据面 = 本层最常用断言面（print 行 = 内核无关可观察面）。
    """
    from core.engine import IBCIEngine

    lines: List[str] = []
    engine = IBCIEngine(root_dir=TESTS_ROOT)
    engine.run_string(
        code,
        variables=variables or {},
        output_callback=lambda t: lines.append(str(t)),
        silent=True,
    )
    return lines


def assert_output(code: str, expected: List[str]) -> None:
    """断言数据面输出 == 预期行（内核无关行为）。"""
    actual = run(code)
    assert actual == expected, f"数据面：\n  expected {expected}\n  actual   {actual}"


def assert_error(
    code: str,
    error_code: str,
    *,
    line: Optional[int] = None,
    column: Optional[int] = None,
) -> None:
    """断言运行时错误：诊断码 + 结构化现场位置（P3 typed 错误契约面）。

    替代旧消息子串匹配（expect_runtime_error）——诊断码 + 现场 = 稳定契约面，
    跨内核不变；消息文本 = 不稳定（不断言）。
    """
    from core.kernel.issue import InterpreterError

    try:
        run(code)
    except InterpreterError as e:
        assert e.error_code == error_code, (
            f"诊断码：expected {error_code}, got {e.error_code}"
        )
        loc = getattr(e, "location", None)
        if line is not None:
            assert loc is not None and loc.line == line, (
                f"现场行：expected {line}, got {getattr(loc, 'line', None)}"
            )
        if column is not None:
            assert loc is not None and loc.column == column, (
                f"现场列：expected {column}, got {getattr(loc, 'column', None)}"
            )
        return
    raise AssertionError(f"Expected runtime error {error_code}, but execution succeeded")


def assert_compile_error(code: str, error_code: str) -> None:
    """断言编译错误：诊断码（前端层错误契约面）。"""
    from core.kernel.issue import CompilerError

    from tests.conftest import compile_or_errors

    _, errors = compile_or_errors(code, root_dir=TESTS_ROOT)
    assert error_code in errors, f"编译诊断码：expected {error_code}, got {errors}"
