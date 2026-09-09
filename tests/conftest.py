"""
tests/conftest.py — 新测试体系统一基础设施（黑盒 API 层）。

**本文件只承载黑盒 API**（编译/运行/断言/常量/会话 fixtures）。
白盒 helper（``make_vm``/``find_node*``/``native``/``make_intent``）下沉到
``tests/runtime/conftest.py``（runtime 层，允许 internals 访问）。
禁止各测试文件再自行定义 ``run_ibci``/``compile_ibci`` 等（meta 强制）。

Public API
----------
Helpers:
- ``run_ibci(code, *, prefix="", ai=False, root_dir=None) -> List[str]``
- ``compile_ibci(code, *, root_dir=None) -> CompilationArtifact``
- ``compile_or_errors(code, *, root_dir=None) -> Tuple[Artifact|None, Set[str]]``
- ``expect_compile_error(code, error_code, *, root_dir=None)``
- ``expect_runtime_error(code, error_pattern, *, prefix="", ai=False, root_dir=None)``

Constants:
- ``AI_MOCK_PREFIX`` — 标准 ``import ai`` + ``set_mock_mode()`` 前缀（单点真理）
- ``REPO_ROOT`` / ``TESTS_ROOT``

Fixtures:
- ``repo_root`` / ``tests_root``（session）
- ``engine`` / ``engine_session``
- ``ctx`` / ``captured_output`` / ``mock_server``
"""

from __future__ import annotations

import os
import threading
import faulthandler
from typing import Any, Callable, List, Optional, Set, Tuple

import pytest

# ---------------------------------------------------------------------------
# 死锁/卡死防护看门狗（进程级，纯 stdlib，阶段感知）——第二层兜底
# ---------------------------------------------------------------------------
# 双层防护体系（套件自身安全，不依赖外部操作）：
# ① 第一层 = pytest-timeout（pytest.ini：timeout=60 / timeout_method=thread）
#    ——每测试独立 60s 超时，卡死测试自动 FAIL + 输出测试名与全部线程栈
#    （faulthandler dump）——绝大多数卡死场景在此层被定位，无需人工干预；
# ② 第二层（本看门狗）= 框架层（collect/plugin 阶段）180s 兜底——仅 pytest
#    框架层 hang（collect/plugin 死锁，测试级超时不生效的场景）触发：
#    全部线程栈 dump 到 `.tmp_pytest/deadlock_watchdog_dump.txt` 后 os._exit(124)。
# **阶段感知**：``pytest_sessionfinish``（测试执行完毕、进入 teardown）设置
# 事件 → 看门狗解除。teardown（unconfigure 期 GC）慢 ≠ 死锁，且测试级超时
# 已覆盖执行期——看门狗与套件总时长不设竞态（固定时点触发曾与增长中的
# 全量时长竞态：100% 测试完成后在 teardown GC 期被误杀，exit 124 假象）。
# **dump 走显式文件通道（阶段无关）**：pytest 的 fd capture 自 session 启动
# 即活跃——测试执行期之前的 hang（collect 期）其 stderr dump 会被 capture 吞没
# （os._exit 不触发 capture 冲刷）。文件通道不受 pytest capture 影响，任何阶段
# 触发皆可读。exit(124) 信号是权威的，dump 是诊断通道（best effort：写 dump 失败
# 不得吞掉 exit 信号——异常上抛会令看门狗线程静默死亡、进程永不退出 = 兜底失效）。
# 真死锁定位：第一层报告含测试名 + 线程栈；第二层（退出 124）时读
# `.tmp_pytest/deadlock_watchdog_dump.txt` 即全部线程栈。
_DEADLOCK_TIMEOUT_S = 180
_session_finished = threading.Event()
_DEADLOCK_DUMP_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".tmp_pytest", "deadlock_watchdog_dump.txt",
)


def _deadlock_watchdog() -> None:
    """框架层看门狗：sessionfinish 前 180s 无进展 = 框架 hang → dump + exit(124)。"""
    if _session_finished.wait(_DEADLOCK_TIMEOUT_S):
        return  # 测试执行完毕（看门狗职责止于框架层）
    try:
        os.makedirs(os.path.dirname(_DEADLOCK_DUMP_PATH), exist_ok=True)
        with open(_DEADLOCK_DUMP_PATH, "a", encoding="utf-8") as f:
            f.write("\n===== deadlock watchdog fired（框架层 hang，退出 124） =====\n")
            faulthandler.dump_traceback(file=f, all_threads=True)
    except OSError:
        pass  # dump best effort——exit(124) 信号不依赖 dump（见模块头注记）
    os._exit(124)


threading.Thread(target=_deadlock_watchdog, daemon=True).start()

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

TESTS_ROOT = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TESTS_ROOT)


# ---------------------------------------------------------------------------
# pytest_configure — force temp directories under repo root
# ---------------------------------------------------------------------------

def pytest_configure(config):
    basetemp = os.path.join(REPO_ROOT, ".tmp_pytest")
    os.makedirs(basetemp, exist_ok=True)
    config.option.basetemp = basetemp


def pytest_sessionfinish(session, exitstatus):
    """测试执行完毕（进入 teardown）→ 解除死锁看门狗（阶段感知，见模块头注记）。"""
    _session_finished.set()


# ---------------------------------------------------------------------------
# AI mock prefix — single source of truth
# ---------------------------------------------------------------------------

AI_MOCK_PREFIX = 'import ai\nai.set_mock_mode()\n'


# ---------------------------------------------------------------------------
# Black-box engine helpers
# ---------------------------------------------------------------------------

def _default_root() -> str:
    return TESTS_ROOT


def run_ibci(
    code: str,
    *,
    prefix: str = "",
    ai: bool = False,
    root_dir: Optional[str] = None,
) -> List[str]:
    """编译 + 执行一段 IBCI 代码，返回 ``print`` 输出的字符串列表。"""
    from core.engine import IBCIEngine

    full = (AI_MOCK_PREFIX if ai else "") + prefix + code
    lines: List[str] = []
    engine = IBCIEngine(root_dir=root_dir or _default_root())
    engine.run_string(full, output_callback=lambda t: lines.append(str(t)), silent=True)
    return lines


def compile_ibci(code: str, *, root_dir: Optional[str] = None):
    """仅编译；失败抛 ``CompilerError``。返回 CompilationArtifact。"""
    from core.engine import IBCIEngine

    engine = IBCIEngine(root_dir=root_dir or _default_root())
    return engine.compile_string(code, silent=True)


def compile_or_errors(code: str, *, root_dir: Optional[str] = None) -> Tuple[Any, Set[str]]:
    """编译并返回 ``(artifact_or_None, error_codes_set)``，便于负样本断言。"""
    from core.engine import IBCIEngine
    from core.kernel.issue import CompilerError

    engine = IBCIEngine(root_dir=root_dir or _default_root())
    try:
        return engine.compile_string(code, silent=True), set()
    except CompilerError as e:
        return None, {d.code for d in e.diagnostics}


def expect_compile_error(code: str, error_code: str, *, root_dir: Optional[str] = None):
    """期望编译失败并匹配特定错误码。"""
    artifact, errors = compile_or_errors(code, root_dir=root_dir)
    assert artifact is None, f"Expected compilation to fail, but succeeded"
    assert error_code in errors, f"Expected error code {error_code}, but got: {errors}"


def expect_runtime_error(
    code: str,
    error_pattern: str,
    *,
    prefix: str = "",
    ai: bool = False,
    root_dir: Optional[str] = None,
):
    """期望运行时失败并匹配异常信息模式。"""
    from core.engine import IBCIEngine
    import re

    full = (AI_MOCK_PREFIX if ai else "") + prefix + code
    engine = IBCIEngine(root_dir=root_dir or _default_root())

    try:
        lines: List[str] = []
        engine.run_string(full, output_callback=lambda t: lines.append(str(t)), silent=True)
        raise AssertionError(
            f"Expected runtime error matching '{error_pattern}', but execution succeeded"
        )
    except Exception as e:
        if isinstance(e, AssertionError):
            raise
        error_msg = str(e)
        if error_pattern not in error_msg and not re.search(error_pattern, error_msg):
            raise AssertionError(
                f"Expected error matching '{error_pattern}', but got: {error_msg}"
            )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def repo_root() -> str:
    return REPO_ROOT


@pytest.fixture(scope="session")
def tests_root() -> str:
    return TESTS_ROOT


@pytest.fixture
def engine():
    """全新 IBCIEngine（每个 test function 隔离）。"""
    from core.engine import IBCIEngine

    return IBCIEngine(root_dir=TESTS_ROOT)


@pytest.fixture(scope="session")
def engine_session():
    """长寿命 IBCIEngine：仅用于只读查询 registry / kernel 元数据。"""
    from core.engine import IBCIEngine

    return IBCIEngine(root_dir=TESTS_ROOT)


@pytest.fixture
def ctx(engine_session):
    """每个 test function 一份独立的裸 ``RuntimeContextImpl``。"""
    from core.runtime.interpreter.runtime_context import RuntimeContextImpl

    return RuntimeContextImpl(registry=engine_session.registry)


@pytest.fixture
def captured_output():
    """返回 ``(lines, callback)`` 元组用于直接传给 ``engine.run_string``。"""
    lines: List[str] = []

    def callback(text):
        lines.append(str(text))

    return lines, callback


@pytest.fixture
def mock_server():
    """启动一个线程内 MOCK HTTP 服务（function 级，自动停止）。"""
    from ibci_modules.ibci_ai.mock_service import MockServer

    server = MockServer()
    server.start()
    try:
        yield server
    finally:
        server.stop()
