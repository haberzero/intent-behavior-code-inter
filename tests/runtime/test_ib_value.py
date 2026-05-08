"""
tests/runtime/test_ib_value.py

Regression tests for the M4 ``IbValue`` runtime value model.
"""

import os

import pytest

from core.engine import IBCIEngine
from core.runtime.factory import RuntimeObjectFactory
from core.runtime.objects.builtins import IbBehavior, IbFnCallable, IbList
from core.runtime.objects.kernel import IbValue


@pytest.fixture(scope="module")
def registry():
    engine = IBCIEngine(
        root_dir=os.path.dirname(os.path.abspath(__file__)),
        auto_sniff=False,
    )
    return engine.registry


def test_boxed_primitives_and_containers_are_ibvalue_backed(registry):
    boxed_int = registry.box(42)
    boxed_list = registry.box([1, 2, 3])
    boxed_none = registry.box(None)

    assert isinstance(boxed_int, IbValue)
    assert isinstance(boxed_list, IbValue)
    assert isinstance(boxed_none, IbValue)

    assert boxed_int.type_ref.head == "int"
    assert boxed_int.payload == 42

    assert isinstance(boxed_list, IbList)
    assert boxed_list.type_ref.head == "list"
    assert boxed_list.payload is boxed_list.elements
    assert [x.to_native() for x in boxed_list.payload] == [1, 2, 3]

    assert boxed_none.type_ref.head == "None"
    assert boxed_none.payload is None


def test_runtime_factory_callable_instances_are_ibvalue_backed(registry):
    factory = RuntimeObjectFactory(registry)

    fn_callable = factory.create_fn_callable("node:fn_callable", capture_mode="snapshot")
    behavior = factory.create_behavior("node:behavior", captured_intents=None, capture_mode="lambda")

    assert isinstance(fn_callable, IbFnCallable)
    assert isinstance(behavior, IbBehavior)
    assert isinstance(fn_callable, IbValue)
    assert isinstance(behavior, IbValue)

    assert fn_callable.type_ref.head == "fn_callable"
    assert fn_callable.payload == "node:fn_callable"
    assert fn_callable.meta["capture_mode"] == "snapshot"

    assert behavior.type_ref.head == "behavior"
    assert behavior.payload == "node:behavior"
    assert behavior.meta["capture_mode"] == "lambda"
