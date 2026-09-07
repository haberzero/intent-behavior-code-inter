"""
tests/runtime/test_vector_type.py

一等词嵌入向量值类型（PT-FEAT-16 批 ②）判别测试。

纪律：

- 值语义（C5）是与既有容器（dict/list 按引用）显式对立的语义边界——
  T1 双轨断言（vector 与 list 同路径对照）必须锁定；
- 方法面修改操作返回新 vector（T9 类型漂移防护——vtable 返回面锁定
  vector 类型，非 list[float] 漂移）；
- 浮点相等边界（NaN/-0.0）构造期封死（C7）；
- dim 不一致 fail-fast 可定位（C4：EMB_DIMENSION_MISMATCH + ibci 源位置）；
- vector 不作 dict 键（C6：显式违约，非"能哈希但语义危险"的隐式面）；
- 跨层数值对照：vector.cosine 与 embedding 契约层 retrieval.cosine
  对同一对向量逐位一致（机制同构交叉验证）。
"""

import math

import pytest

from core.base.diagnostics.codes import (
    EMB_DIMENSION_MISMATCH,
    EMB_INVALID_INPUT,
)
from core.base.embedding_protocol import cosine as retrieval_cosine
from core.kernel.issue import CompilerError, InterpreterError
from core.runtime.serialization.runtime_serializer import (
    RuntimeDeserializer,
    RuntimeSerializer,
)


def _round_trip_vector(engine, code):
    """运行代码并序列化/反序列化运行时上下文（值保真 round-trip）。"""
    engine.run_string(code, silent=True)
    ec = engine.interpreter.execution_context
    orig_ctx = ec.runtime_context
    data = RuntimeSerializer(engine.registry).serialize_context(
        orig_ctx, include_static=False
    )
    restored = RuntimeDeserializer(
        engine.registry, factory=ec.factory
    ).deserialize_context(data)
    return orig_ctx, restored


def _vector_elements(ctx, name):
    """读取上下文中 vector 变量的原生元素（绕 to_native 违约面——
    直接读 payload 元组，仅测试侧观测用）。"""
    obj = ctx.get_variable(name)
    return tuple(obj.payload)


class TestValueSemantics:
    """C5 值语义：与 dict/list 按引用传递显式对立（T1 双轨断言）。"""

    def test_vector_scale_does_not_mutate_original(self, engine):
        engine.run_string(
            "vector v1 = vec([1.0, 2.0, 3.0])\n"
            "vector v2 = v1\n"
            "vector s = v2.scale(10.0)\n"
        )
        # scale 返回新 vector：v1/v2 不变，s 元素缩放
        v1 = _vector_elements(engine.interpreter.execution_context.runtime_context, "v1")
        v2 = _vector_elements(engine.interpreter.execution_context.runtime_context, "v2")
        s = _vector_elements(engine.interpreter.execution_context.runtime_context, "s")
        assert v1 == (1.0, 2.0, 3.0), "scale 不得变更原 vector"
        assert v2 == (1.0, 2.0, 3.0)
        assert s == (10.0, 20.0, 30.0)

    def test_list_reference_semantics_contrast(self, engine):
        # 对照轨：list 同路径（copy + append）= 引用语义（append 变更原 list）
        engine.run_string(
            "list li1 = [1]\n"
            "list li2 = li1\n"
            "li2.append(99)\n"
        )
        li1 = engine.interpreter.execution_context.runtime_context.get_variable("li1")
        assert len(li1.elements) == 2, "list 引用语义：li2.append 影响 li1（对照基线）"

    def test_vector_equality_exact(self, engine):
        # 逐元素精确相等（-0.0 == 0.0 按 IEEE 754）
        engine.run_string(
            "vector a = vec([1.0, 2.0])\n"
            "vector b = vec([1.0, 2.0])\n"
            "vector c = vec([1.0, 3.0])\n"
            "bool eq1 = (a == b)\n"
            "bool eq2 = (a == c)\n"
        )
        ctx = engine.interpreter.execution_context.runtime_context
        assert ctx.get_variable("eq1").to_native() is True
        assert ctx.get_variable("eq2").to_native() is False

    def test_negative_zero_equality(self):
        from core.runtime.objects.primitives.vector import IbVector

        a = IbVector([-0.0, 1.0], None)
        b = IbVector([0.0, 1.0], None)
        assert a == b, "-0.0 == 0.0（IEEE 754 逐元素相等）"


class TestConstructionAndDimension:
    """C3 维度固定 / C7 NaN 构造封死 / C15 显式构造。"""

    def test_no_mutation_surface(self, engine):
        # 方法面闭合：无 append/setitem（公理方法面 = dim/dot/norm/cosine/
        # scale/add/sub/下标）——运行时消息违约
        with pytest.raises(InterpreterError):
            engine.run_string(
                "vector v = vec([1.0])\n"
                "v.append(2.0)\n"
            )

    def test_nan_construction_fail_fast(self, engine):
        # (float)"nan" cast → NaN 元素 → 构造期封死（值语义相等未定义域）
        with pytest.raises(InterpreterError) as exc:
            engine.run_string(
                "vector v = vec([(float)\"nan\", 1.0])\n"
            )
        assert exc.value.error_code == EMB_INVALID_INPUT

    def test_inf_construction_fail_fast(self, engine):
        with pytest.raises(InterpreterError) as exc:
            engine.run_string(
                "vector v = vec([(float)\"inf\"])\n"
            )
        assert exc.value.error_code == EMB_INVALID_INPUT

    def test_non_numeric_element_fail_fast(self, engine):
        with pytest.raises(InterpreterError) as exc:
            engine.run_string(
                "vector v = vec([\"x\", 1.0])\n"
            )
        assert exc.value.error_code == EMB_INVALID_INPUT

    def test_list_not_implicitly_converted(self, engine):
        # 字面量 list 不得隐式转 vector（显式 vec() 是唯一构造入口）
        with pytest.raises(CompilerError):
            engine.compile_string(
                "vector v = [1.0, 2.0]\n", silent=True
            )

    def test_dim_immutable_across_ops(self, engine):
        engine.run_string(
            "vector v = vec([1.0, 2.0, 3.0])\n"
            "vector s = v.scale(2.0)\n"
            "vector a = v.add(v)\n"
        )
        ctx = engine.interpreter.execution_context.runtime_context
        for name in ("v", "s", "a"):
            assert len(_vector_elements(ctx, name)) == 3


class TestDimensionMismatch:
    """C4 dim 不一致 fail-fast（可定位 + EMB_ 码）。"""

    @pytest.mark.parametrize("method", ["dot", "cosine", "add", "sub"])
    def test_mismatch_fail_fast(self, engine, method):
        with pytest.raises(InterpreterError) as exc:
            engine.run_string(
                f"vector v = vec([1.0, 2.0])\n"
                f"vector w = vec([1.0, 2.0, 3.0])\n"
                f"v.{method}(w)\n"
            )
        assert exc.value.error_code == EMB_DIMENSION_MISMATCH
        # P0-1 错误定位链：运行期错误携带 ibci 源位置（方法调用行）
        loc = exc.value.location
        assert loc is not None
        assert loc.line == 3

    def test_non_vector_operand_fail_fast(self, engine):
        with pytest.raises(InterpreterError) as exc:
            engine.run_string(
                "vector v = vec([1.0])\n"
                "v.dot(1.0)\n"
            )
        assert exc.value.error_code == EMB_INVALID_INPUT


class TestDictKeyExclusion:
    """C6 vector 不作 dict 键（显式违约——to_native 单一边界）。"""

    def test_vector_as_dict_key_fails(self, engine):
        with pytest.raises(InterpreterError) as exc:
            engine.run_string(
                "vector v = vec([1.0])\n"
                "dict d = {}\n"
                "d[v] = 1\n"
            )
        assert exc.value.error_code == EMB_INVALID_INPUT

    def test_vector_unhashable_python_layer(self):
        from core.runtime.objects.primitives.vector import IbVector

        v = IbVector([1.0, 2.0], None)
        assert v.__hash__ is None, "Python 原生层不可哈希（双保险）"


class TestSerialization:
    """C8 round-trip 保真 / C9 deep_clone / T10 idbg 摘要。"""

    def test_round_trip_fidelity(self, engine):
        orig, rest = _round_trip_vector(
            engine,
            "vector v = vec([-1.5, 2.25, 100.75])\n"
            "vector w = v.scale(2.0)\n",
        )
        assert _vector_elements(orig, "v") == _vector_elements(rest, "v")
        assert _vector_elements(orig, "w") == _vector_elements(rest, "w")

    def test_deepcopy_returns_equal_value(self, engine):
        engine.run_string(
            "vector v = vec([1.0, 2.0])\n"
            "vector c = deepcopy(v)\n"
        )
        assert _vector_elements(
            engine.interpreter.execution_context.runtime_context, "c"
        ) == (1.0, 2.0)

    def test_idbg_summary_view(self):
        from core.runtime.objects.primitives.vector import IbVector

        v = IbVector([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0], None)
        dbg = v.serialize_for_debug()
        assert dbg["type"] == "vector"
        assert dbg["dim"] == 10
        assert len(dbg["preview"]) == 8, "摘要 = 前 8 维（非全量 dump）"

    def test_container_list_of_vector(self, engine):
        # C11 list[vector] 容器特化：遍历/索引可用
        engine.run_string(
            "vector v1 = vec([1.0])\n"
            "vector v2 = vec([2.0])\n"
            "list[vector] ls = [v1, v2]\n"
            "vector first = ls[0]\n"
        )
        ls = engine.interpreter.execution_context.runtime_context.get_variable("ls")
        assert len(ls.elements) == 2
        first = engine.interpreter.execution_context.runtime_context.get_variable("first")
        assert tuple(first.payload) == (1.0,)


class TestMathProperties:
    """T7 尺度不变 / T8 无隐式归一 / T9 返回类型锁定。"""

    def test_cosine_scale_invariance(self, engine):
        engine.run_string(
            "vector v = vec([1.0, 2.0, 3.0])\n"
            "vector w = vec([4.0, 5.0, 6.0])\n"
            "float c1 = v.cosine(w)\n"
            "float c2 = v.scale(2.0).cosine(w.scale(3.0))\n"
        )
        ctx = engine.interpreter.execution_context.runtime_context
        c1, c2 = ctx.get_variable("c1").to_native(), ctx.get_variable("c2").to_native()
        assert abs(c1 - c2) < 1e-9, "cosine(2v, 3w) == cosine(v, w)"

    def test_no_implicit_normalization(self, engine):
        engine.run_string(
            "vector v = vec([3.0, 4.0])\n"
            "float n1 = v.norm()\n"
            "float n2 = v.scale(2.0).norm()\n"
        )
        ctx = engine.interpreter.execution_context.runtime_context
        n1, n2 = ctx.get_variable("n1").to_native(), ctx.get_variable("n2").to_native()
        assert abs(n1 - 5.0) < 1e-9, "非单位向量 norm() != 1（无隐式归一化）"
        assert abs(n2 - 10.0) < 1e-9, "scale 后 norm 线性变化"

    def test_method_returns_vector_type(self, engine):
        # T9 vtable 返回面锁定 vector（非 list[float] 类型漂移）
        engine.run_string(
            "vector v = vec([1.0, 2.0])\n"
            "str t1 = (str)type(v.scale(2.0))\n"
            "str t2 = (str)type(v.add(v))\n"
            "str t3 = (str)type(v.sub(v))\n"
        )
        ctx = engine.interpreter.execution_context.runtime_context
        for name in ("t1", "t2", "t3"):
            assert ctx.get_variable(name).to_native() == "vector", (
                f"{name}: 修改操作须返回 vector 类型（类型漂移防护）"
            )

    def test_cross_layer_numerical_parity(self, engine):
        # 跨层交叉验证：vector.cosine 与契约层 retrieval.cosine 逐位一致
        engine.run_string(
            "vector v = vec([0.1, 0.9, 0.3])\n"
            "vector w = vec([0.9, 0.1, 0.5])\n"
            "float c = v.cosine(w)\n"
        )
        ctx = engine.interpreter.execution_context.runtime_context
        iv = _vector_elements(ctx, "v")
        iw = _vector_elements(ctx, "w")
        lang_cosine = ctx.get_variable("c").to_native()
        assert lang_cosine == retrieval_cosine(iv, iw), "跨层数值须逐位一致"
