"""
tests/compliance/conftest.py
============================

合规测试目录的共享 fixture / helper（仅黑盒 ``IBCIEngine`` 公共 API）。

提取自原 3 个文件本地副本：``test_concurrent_llm.py`` / ``test_execution_isolation.py``
/ ``test_memory_model.py``。

详见 docs/TESTS_REORGANIZATION_TASK.md Step 3。
"""
import os

import pytest

from core.engine import IBCIEngine


@pytest.fixture(scope="module")
def compliance_root() -> str:
    """合规测试目录的根路径——供需要写临时子 .ibci 文件的测试使用。"""
    return os.path.dirname(os.path.abspath(__file__))


@pytest.fixture
def make_compliance_engine(compliance_root):
    """工厂 fixture：在合规目录根下构造一个 ``IBCIEngine`` 实例。"""

    def _factory() -> IBCIEngine:
        return IBCIEngine(root_dir=compliance_root, auto_sniff=False)

    return _factory


@pytest.fixture
def run_compliance_code(make_compliance_engine):
    """工厂 fixture：执行 IBCI 源码，返回 ``(engine, output_lines)``。"""

    def _runner(code: str):
        lines: list = []
        eng = make_compliance_engine()
        eng.run_string(code, output_callback=lambda s: lines.append(str(s)), silent=True)
        return eng, lines

    return _runner
