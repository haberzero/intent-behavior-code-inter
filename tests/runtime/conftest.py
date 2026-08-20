"""
tests/runtime/conftest.py — runtime 层白盒 helper（允许访问 internals）。

与根 conftest 的黑盒 API 分层：本层 helper 依赖引擎内部结构
（``execution_context``/``node_pool``），仅 runtime 层测试使用。
"""

from typing import Any, Callable, List, Optional, Tuple

import pytest

from tests.conftest import TESTS_ROOT


def make_vm(engine):
    """构造 ``VMExecutor``（统一参数顺序）。"""
    from core.runtime.vm import VMExecutor

    return VMExecutor(
        engine.interpreter.execution_context,
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
    """查找单个匹配节点；不存在时抛 AssertionError。"""
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
    return find_node(engine, node_type, predicate=predicate)[0]


def find_node_uids(
    engine,
    node_type: str,
    *,
    predicate: Optional[Callable[[str, dict], bool]] = None,
) -> List[str]:
    return [uid for uid, _ in find_nodes(engine, node_type, predicate=predicate)]


def native(obj) -> Any:
    """将 IBCI 对象转为原生 Python 值；非 IBCI 对象原样返回。"""
    return obj.to_native() if hasattr(obj, "to_native") else obj


def make_intent(
    registry,
    content: str,
    *,
    mode=None,
    role=None,
    tag: Optional[str] = None,
):
    """构造 ``IbIntent``。"""
    from core.runtime.objects.intent import IbIntent, IntentMode, IntentRole

    return IbIntent(
        ib_class=registry.get_class("Intent"),
        values=[registry.box(content)],
        mode=mode if mode is not None else IntentMode.APPEND,
        role=role if role is not None else IntentRole.SMEAR,
        tag=tag,
    )


@pytest.fixture
def vm_factory(engine):
    """runtime 层便捷 fixture：返回 ``make_vm``（按需构造 VMExecutor）。"""
    return lambda: make_vm(engine)
