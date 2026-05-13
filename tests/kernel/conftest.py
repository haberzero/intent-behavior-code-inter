"""tests/kernel/conftest.py — 共享 kernel 层 fixture。

为 ``test_typeref.py`` / ``test_spec_layer.py`` / ``test_axioms.py`` 提供
统一的 ``ax_reg`` / ``axiom_registry`` / ``spec_reg`` / ``factory`` fixture。

注意：历史上不同文件用 ``ax_reg`` 与 ``axiom_registry`` 两种命名。本 conftest
同时暴露两种别名以保持各测试文件零改动即可命中。
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


# 别名：历史上 test_spec_layer.py 使用 ``axiom_registry``，其它文件使用 ``ax_reg``。
@pytest.fixture(scope="module")
def axiom_registry(ax_reg: AxiomRegistry) -> AxiomRegistry:
    return ax_reg


@pytest.fixture(scope="module")
def spec_reg(ax_reg: AxiomRegistry) -> SpecRegistry:
    return create_default_spec_registry(ax_reg)


@pytest.fixture(scope="module")
def factory(spec_reg: SpecRegistry) -> SpecFactory:
    return spec_reg.factory
