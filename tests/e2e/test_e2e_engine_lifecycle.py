"""
tests/e2e/test_e2e_engine_lifecycle.py
=======================================

IBCIEngine 生命周期 e2e 测试（PT-TEST-4 area 2）。

验证核心生命周期契约：
1. 新引擎未封印、无解释器
2. ``compile_string`` 不封印注册表（编译无副作用于 seal 状态）
3. ``execute`` 封印注册表（单次执行后不可复用）
4. 封印后再次 ``execute`` 抛 ``PermissionError``（NEXT_STEPS 指定的核心契约）
5. ``compile_string`` → ``execute`` 分步流程可独立工作并产出输出
6. 典型用户路径 ``run_string`` 单次运行后封印引擎

设计约束：每个 Engine 实例只能执行一次（封印后需新建实例），因此每个测试创建独立引擎。
不依赖 LLM（无 ``@~`` 调用），故无需 MOCK 配置。
"""
import pytest

from core.engine import IBCIEngine
from tests.conftest import TESTS_ROOT

# 简单非 LLM 代码：无需 MOCK 即可运行
_SIMPLE_CODE = 'str x = "hello"\nprint(x)\n'


def _new_engine():
    return IBCIEngine(root_dir=TESTS_ROOT, auto_sniff=False)


class TestEngineLifecycle:
    """IBCIEngine 的封印/重入/分步执行契约。"""

    def test_fresh_engine_not_sealed_and_no_interpreter(self):
        """新引擎：注册表未封印，解释器尚未创建（惰性初始化）。"""
        eng = _new_engine()
        assert eng.registry.is_sealed is False
        assert eng.interpreter is None

    def test_compile_does_not_seal_registry(self):
        """compile_string 仅编译，不产生封印副作用。"""
        eng = _new_engine()
        eng.compile_string(_SIMPLE_CODE, silent=True)
        assert eng.registry.is_sealed is False

    def test_execute_seals_registry(self):
        """execute 执行产物后封印注册表（单次执行语义）。"""
        eng = _new_engine()
        artifact = eng.compile_string(_SIMPLE_CODE, silent=True)
        eng.execute(artifact, output_callback=lambda t: None)
        assert eng.registry.is_sealed is True

    def test_sealed_registry_reexecute_raises_permission_error(self):
        """封印后再次 execute 必须抛 PermissionError（核心安全契约）。

        这是 NEXT_STEPS 明确指定的契约：防止在已封印注册表上复用引擎。
        """
        eng = _new_engine()
        artifact = eng.compile_string(_SIMPLE_CODE, silent=True)
        eng.execute(artifact, output_callback=lambda t: None)
        assert eng.registry.is_sealed is True
        with pytest.raises(PermissionError):
            eng.execute(artifact, output_callback=lambda t: None)

    def test_compile_then_execute_produces_output(self):
        """compile_string 返回可执行产物；execute 独立消费它并产出输出。"""
        eng = _new_engine()
        artifact = eng.compile_string(_SIMPLE_CODE, silent=True)
        assert artifact is not None
        lines = []
        eng.execute(artifact, output_callback=lambda t: lines.append(str(t)))
        assert "hello" in lines

    def test_run_string_seals_engine_after_single_run(self):
        """典型用户路径 run_string 单次运行后封印引擎。"""
        eng = _new_engine()
        eng.run_string(_SIMPLE_CODE, silent=True)
        assert eng.registry.is_sealed is True

    def test_engine_instances_are_isolated(self):
        """两个独立引擎实例互不干扰：A 封印不影响 B 独立执行。"""
        eng_a = _new_engine()
        eng_b = _new_engine()
        eng_a.run_string('str a = "A"\nprint(a)\n', silent=True)
        assert eng_a.registry.is_sealed is True
        # A 已封印，B 仍可独立完成完整的 compile→execute 生命周期
        lines_b = []
        eng_b.run_string('str b = "B"\nprint(b)\n', silent=True, output_callback=lambda t: lines_b.append(str(t)))
        assert "B" in lines_b
        assert eng_b.registry.is_sealed is True
