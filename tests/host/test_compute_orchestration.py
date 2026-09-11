"""宿主面层：计算编排协议（R5-2——架构 v2 职责重定位：内核不实现外部引擎
内部数学；compute_engine 网关编排已注册引擎；数据经 to_list/tensor 缓冲交换）。"""

import pytest

from core.engine import IBCIEngine
from core.runtime.modules.compute_impl import NumpyEngine

from tests.behavior.helpers import TESTS_ROOT

IMPORT = "import compute_engine\n"


@pytest.fixture
def compute_engine():
    """已注册 numpy 计算引擎的引擎（首次执行前注册——registry 密封纪律）。"""
    eng = IBCIEngine(root_dir=TESTS_ROOT)
    compute = eng.host_interface.get_module_implementation("compute_engine")
    compute.register_engine("numpy", NumpyEngine())
    return eng


def _run(eng, code):
    lines = []
    eng.run_string(code, output_callback=lambda t: lines.append(str(t)), silent=True)
    return lines


class TestComputeOrchestration:
    def test_engine_registration_and_dispatch(self, compute_engine):
        """引擎注册 + 编排分派（numpy 引擎执行 add/dot）。"""
        lines = _run(
            compute_engine,
            IMPORT
            + "a = tensor([1, 2, 3])\n"
            "b = tensor([10, 20, 30])\n"
            "c = tensor(compute_engine.run('add', [a.to_list(), b.to_list()]))\n"
            "print(c)\n"
            "print(compute_engine.run('dot', [a.to_list(), b.to_list()]))\n",
        )
        assert lines == ["vector[3](11, 22, 33)", "140.0"]

    def test_tensor_interchange(self, compute_engine):
        """Tensor ↔ 原生列表缓冲交换（to_list/tensor——宿主边界数据形态归一）。"""
        lines = _run(
            compute_engine,
            IMPORT
            + "a = tensor([1, 2, 3])\n"
            "print(a.to_list())\n"
            "b = tensor(compute_engine.run('scale', [a.to_list(), 2]))\n"
            "print(b.shape())\n"
            "print(b)\n",
        )
        assert lines == ["[1.0, 2.0, 3.0]", "[3]", "vector[3](2, 4, 6)"]

    def test_no_engine_explicit_error(self):
        """无已注册引擎 = 显式错误（编排协议 fail-fast，非静默回退）。"""
        eng = IBCIEngine(root_dir=TESTS_ROOT)  # 未注册引擎
        try:
            _run(eng, IMPORT + "print(compute_engine.run('add', [[1], [2]]))\n")
            raise AssertionError("Expected no-engine error")
        except Exception as e:
            assert "已注册引擎" in str(e) or "no engine" in str(e).lower()

    def test_registered_engine_failure_propagates(self, compute_engine):
        """引擎执行失败 = 显式传播（shape 不符——不静默）。"""
        try:
            _run(
                compute_engine,
                IMPORT
                + "print(compute_engine.run('add', [[1, 2], [1, 2, 3]]))\n",
            )
            raise AssertionError("Expected shape mismatch error")
        except Exception as e:
            assert "shape mismatch" in str(e) or "维度" in str(e)
