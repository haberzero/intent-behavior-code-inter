"""
tests/conftest.py
=================

测试体系**统一基础设施**：fixture、helper、常量。

本文件由 ``docs/TESTS_REORGANIZATION_TASK.md`` §2.2 规约定义，**所有测试文件
必须使用本文件提供的统一形态**，禁止再各自复刻 ``run_and_capture`` /
``make_engine`` / ``make_vm`` / ``ai_setup`` / ``find_node_uid`` 等。

────────────────────────────────────────────────────────────────────────────
Public API（在测试中通过 fixture 或 ``from tests.conftest import ...`` 使用）
────────────────────────────────────────────────────────────────────────────

Fixtures
--------
- ``repo_root``        (session) — 仓库根目录绝对路径
- ``tests_root``       (session) — ``tests/`` 目录绝对路径
- ``engine``           (function) — 全新 IBCIEngine
- ``engine_session``   (session)  — 长寿命引擎（只读 registry 查询用）
- ``ctx``              (function) — 独立裸 ``RuntimeContextImpl``
- ``intent_class``     (session)  — registry.get_class("Intent")
- ``intent_context_class`` (session) — registry.get_class("intent_context")
- ``captured_output``  (function) — ``(lines, callback)`` 元组，用于 print 捕获

Helpers（普通函数，可 import 也可由 fixture ``helpers`` 暴露）
-------------------------------------------------------------
- ``run_ibci(code, *, prefix="", ai=False, root_dir=None) -> List[str]``
- ``compile_ibci(code, *, root_dir=None) -> CompilationArtifact``
- ``compile_or_errors(code, *, root_dir=None) -> Tuple[Artifact|None, Set[str]]``
- ``make_vm(engine) -> VMExecutor``
- ``find_node(engine, node_type, *, predicate=None) -> Tuple[uid, data]``
- ``find_nodes(engine, node_type, *, predicate=None) -> List[Tuple[uid, data]]``
- ``find_node_uid(engine, node_type, *, predicate=None) -> str``
- ``find_node_uids(engine, node_type, *, predicate=None) -> List[str]``
- ``native(obj) -> Any``
- ``make_intent(registry, content, *, mode=APPEND, role=SMEAR, tag=None)``

Constants
---------
- ``AI_MOCK_PREFIX`` — 标准 ``import ai`` + ``set_config(TESTONLY,...)`` 前缀
- ``REPO_ROOT``     — 仓库根目录（path string）
- ``TESTS_ROOT``    — tests 根目录（path string）

────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import os
from typing import Any, Callable, List, Optional, Set, Tuple

import pytest

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

TESTS_ROOT = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TESTS_ROOT)


# ---------------------------------------------------------------------------
# AI mock prefix — single source of truth
# ---------------------------------------------------------------------------

AI_MOCK_PREFIX = 'import ai\nai.set_config("TESTONLY", "TESTONLY", "TESTONLY")\n'


# ---------------------------------------------------------------------------
# Engine helpers
# ---------------------------------------------------------------------------

def _default_root() -> str:
    """tests 根作为 IBCIEngine 的 root_dir 默认值。"""
    return TESTS_ROOT


def run_ibci(
    code: str,
    *,
    prefix: str = "",
    ai: bool = False,
    root_dir: Optional[str] = None,
) -> List[str]:
    """编译 + 执行一段 IBCI 代码，返回 ``print`` 输出的字符串列表。

    Parameters
    ----------
    code     : IBCI 源代码
    prefix   : 在 ``code`` 之前自动拼接的额外前缀（如自定义 import）
    ai       : 是否在最前面自动拼接 ``AI_MOCK_PREFIX``
    root_dir : 自定义 root_dir；默认 ``tests/`` 根
    """
    from core.engine import IBCIEngine  # 局部 import：避免测试启动阶段强依赖

    full = (AI_MOCK_PREFIX if ai else "") + prefix + code
    lines: List[str] = []
    engine = IBCIEngine(root_dir=root_dir or _default_root(), auto_sniff=False)
    engine.run_string(full, output_callback=lambda t: lines.append(str(t)), silent=True)
    return lines


def compile_ibci(code: str, *, root_dir: Optional[str] = None):
    """仅编译；失败抛 ``CompilerError``。返回 CompilationArtifact。"""
    from core.engine import IBCIEngine

    engine = IBCIEngine(root_dir=root_dir or _default_root(), auto_sniff=False)
    return engine.compile_string(code, silent=True)


def compile_or_errors(code: str, *, root_dir: Optional[str] = None) -> Tuple[Any, Set[str]]:
    """编译并返回 ``(artifact_or_None, error_codes_set)``，便于负样本断言。"""
    from core.engine import IBCIEngine
    from core.kernel.issue import CompilerError

    engine = IBCIEngine(root_dir=root_dir or _default_root(), auto_sniff=False)
    try:
        return engine.compile_string(code, silent=True), set()
    except CompilerError as e:
        return None, {d.code for d in e.diagnostics}


# ---------------------------------------------------------------------------
# VM helpers
# ---------------------------------------------------------------------------

def make_vm(engine):
    """构造 ``VMExecutor``（统一参数顺序）。"""
    from core.runtime.vm import VMExecutor

    return VMExecutor(
        engine.interpreter._execution_context,
        interpreter=engine.interpreter,
    )


def find_nodes(
    engine,
    node_type: str,
    *,
    predicate: Optional[Callable[[str, dict], bool]] = None,
) -> List[Tuple[str, dict]]:
    """在 ``engine.interpreter.node_pool`` 中查找所有匹配节点。"""
    out: List[Tuple[str, dict]] = []
    for uid, data in engine.interpreter.node_pool.items():
        if data.get("_type") != node_type:
            continue
        if predicate is None or predicate(uid, data):
            out.append((uid, data))
    return out


def find_node(
    engine,
    node_type: str,
    *,
    predicate: Optional[Callable[[str, dict], bool]] = None,
) -> Tuple[str, dict]:
    """查找单个匹配节点；不存在或多于一个时抛 AssertionError。

    注：历史 ``find_node_uid`` 实际上接受多匹配并返回第一个；为兼容旧用法，
    本函数在 predicate 为 None 时不严格要求唯一，仅返回首个匹配。当 predicate
    存在时仍允许多匹配（返回首个）—— 严格唯一性请用 ``find_nodes`` + 自检。
    """
    nodes = find_nodes(engine, node_type, predicate=predicate)
    if not nodes:
        raise AssertionError(f"No {node_type} node found in node_pool")
    return nodes[0]


def find_node_uid(
    engine,
    node_type: str,
    *,
    predicate: Optional[Callable[[str, dict], bool]] = None,
) -> str:
    """``find_node`` 的便捷形态：只返回 uid。"""
    return find_node(engine, node_type, predicate=predicate)[0]


def find_node_uids(
    engine,
    node_type: str,
    *,
    predicate: Optional[Callable[[str, dict], bool]] = None,
) -> List[str]:
    """``find_nodes`` 的便捷形态：只返回 uid 列表。"""
    return [uid for uid, _ in find_nodes(engine, node_type, predicate=predicate)]


def native(obj) -> Any:
    """将 IBCI 对象转为原生 Python 值；非 IBCI 对象原样返回。"""
    return obj.to_native() if hasattr(obj, "to_native") else obj


# ---------------------------------------------------------------------------
# Intent helpers
# ---------------------------------------------------------------------------

def make_intent(
    registry,
    content: str,
    *,
    mode=None,
    role=None,
    tag: Optional[str] = None,
):
    """构造 ``IbIntent``。

    ``mode`` 默认 ``IntentMode.APPEND``；``role`` 默认 ``IntentRole.SMEAR``。
    在函数体内延迟 import 以避免顶层依赖。
    """
    from core.runtime.objects.intent import IbIntent, IntentMode, IntentRole

    return IbIntent(
        ib_class=registry.get_class("Intent"),
        content=content,
        mode=mode if mode is not None else IntentMode.APPEND,
        role=role if role is not None else IntentRole.SMEAR,
        tag=tag,
    )


# ===========================================================================
# Fixtures
# ===========================================================================


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

    return IBCIEngine(root_dir=TESTS_ROOT, auto_sniff=False)


@pytest.fixture(scope="session")
def engine_session():
    """长寿命 IBCIEngine：仅用于只读查询 registry / kernel 元数据，
    切勿在其中执行用户代码（会污染后续测试）。"""
    from core.engine import IBCIEngine

    return IBCIEngine(root_dir=TESTS_ROOT, auto_sniff=False)


@pytest.fixture(scope="session")
def intent_class(engine_session):
    """``registry.get_class("Intent")``。"""
    return engine_session.registry.get_class("Intent")


@pytest.fixture(scope="session")
def intent_context_class(engine_session):
    """``registry.get_class("intent_context")``。"""
    return engine_session.registry.get_class("intent_context")


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
def helpers():
    """聚合 helper 命名空间，便于 ``helpers.run_ibci(...)`` 风格调用。"""

    class _H:
        run_ibci = staticmethod(run_ibci)
        compile_ibci = staticmethod(compile_ibci)
        compile_or_errors = staticmethod(compile_or_errors)
        make_vm = staticmethod(make_vm)
        find_node = staticmethod(find_node)
        find_nodes = staticmethod(find_nodes)
        find_node_uid = staticmethod(find_node_uid)
        find_node_uids = staticmethod(find_node_uids)
        native = staticmethod(native)
        make_intent = staticmethod(make_intent)
        AI_MOCK_PREFIX = AI_MOCK_PREFIX
        REPO_ROOT = REPO_ROOT
        TESTS_ROOT = TESTS_ROOT

    return _H()
