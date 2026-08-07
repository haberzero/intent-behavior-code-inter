"""tests_v2/kernel/conftest.py — kernel 层共享 fixture（统一命名，无别名 shim）。

原 tests/kernel/conftest.py 的 ``axiom_registry`` 别名无消费者（遗留），
此处仅保留单一权威命名 ``ax_reg``。
"""

from __future__ import annotations

import pytest

from core.kernel.axioms.primitives import register_core_axioms
from core.kernel.axioms.registry import AxiomRegistry
from core.kernel.spec.registry import (
    SpecFactory,
    SpecRegistry,
    create_default_spec_registry,
)


@pytest.fixture(scope="module")
def ax_reg() -> AxiomRegistry:
    ax = AxiomRegistry()
    register_core_axioms(ax)
    return ax


@pytest.fixture(scope="module")
def spec_reg(ax_reg: AxiomRegistry) -> SpecRegistry:
    return create_default_spec_registry(ax_reg)


@pytest.fixture(scope="module")
def factory(spec_reg: SpecRegistry) -> SpecFactory:
    return spec_reg.factory
