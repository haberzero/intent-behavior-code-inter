"""语言行为层：vector 值语义（R3 阶段 C 迁移——原 tests/runtime/test_vector_type.py
白盒断言 → 可观察断言面[数据面输出 + 诊断码 + 现场位置]；vector = 1D tensor 统一
数据形态）。

**迁移映射**（纪律：契约不留空洞）：
- 值语义（scale 不可变/list 引用对照/相等/-0.0）→ 数据面输出断言；
- 构造封死（NaN/Inf/非数值/dim 不一致/非 vector 操作数/dict 键）→ 诊断码 +
  现场位置断言（Rust 路径 P3 单一权威码）；
- 数学性质（cosine 尺度不变/无隐式归一/返回类型锁定）→ 数据面精确值断言；
- round-trip 保真 = Rust artifact 契约面（full_artifact 差分）+ legacy
  RuntimeSerializer round-trip = ⑦ 终点退场面（不再单独断言）；
- 跨层数值 parity = 契约层 embedding_protocol（本层以精确值断言钉语义）。
"""

from tests.behavior.helpers import assert_error, assert_output


class TestVectorValueSemantics:
    """C5 值语义：与 dict/list 按引用传递显式对立（T1 双轨断言）。"""

    def test_scale_does_not_mutate_original(self):
        # scale 返回新 vector：v1/v2 不变，s 元素缩放（可观察数据面）
        assert_output(
            "vector v1 = vec([1.0, 2.0, 3.0])\n"
            "vector v2 = v1\n"
            "vector s = v2.scale(10.0)\n"
            "print(v1)\n"
            "print(v2)\n"
            "print(s)\n",
            ["vector[3](1, 2, 3)", "vector[3](1, 2, 3)", "vector[3](10, 20, 30)"],
        )

    def test_list_reference_semantics_contrast(self):
        # 对照轨：list 同路径 = 引用语义（append 变更原 list）
        assert_output(
            "list li1 = [1]\n"
            "list li2 = li1\n"
            "li2.append(99)\n"
            "print(li1)\n",
            ["[1, 99]"],
        )

    def test_equality_exact(self):
        # 逐元素精确相等（-0.0 == 0.0 按 IEEE 754）
        assert_output(
            "vector a = vec([1.0, 2.0])\n"
            "vector b = vec([1.0, 2.0])\n"
            "vector c = vec([1.0, 3.0])\n"
            "print(a == b)\n"
            "print(a == c)\n"
            "print(vec([-0.0, 1.0]) == vec([0.0, 1.0]))\n",
            ["True", "False", "True"],
        )

    def test_dim_immutable_across_ops(self):
        assert_output(
            "vector v = vec([1.0, 2.0, 3.0])\n"
            "vector s = v.scale(2.0)\n"
            "vector a = v.add(v)\n"
            "print(v.dim())\n"
            "print(s.dim())\n"
            "print(a.dim())\n",
            ["3", "3", "3"],
        )

    def test_deepcopy_returns_equal_value(self):
        assert_output(
            "vector v = vec([1.0, 2.0])\n"
            "vector c = deepcopy(v)\n"
            "print(c)\n"
            "print(c == v)\n",
            ["vector[2](1, 2)", "True"],
        )

    def test_container_list_of_vector(self):
        # list[vector] 容器特化：索引可用（元素 = vector 值）
        assert_output(
            "vector v1 = vec([1.0])\n"
            "vector v2 = vec([2.0])\n"
            "list[vector] ls = [v1, v2]\n"
            "print(ls[0])\n"
            "print(len(ls))\n",
            ["vector[1](1)", "2"],
        )


class TestVectorConstruction:
    """C3 维度固定 / C7 NaN 构造封死 / C15 显式构造（诊断码 + 现场）。"""

    def test_no_mutation_surface(self):
        # 方法面闭合：无 append（消息违约 = AttributeError 显式）
        assert_error(
            "vector v = vec([1.0])\nv.append(2.0)\n",
            "RUN_ATTRIBUTE_ERROR",
            line=2,
        )

    def test_nan_construction_fail_fast(self):
        assert_error(
            "vector v = vec([(float)\"nan\", 1.0])\n",
            "EMB_INVALID_INPUT",
            line=1,
        )

    def test_inf_construction_fail_fast(self):
        assert_error(
            "vector v = vec([(float)\"inf\"])\n",
            "EMB_INVALID_INPUT",
            line=1,
        )

    def test_non_numeric_element_fail_fast(self):
        assert_error(
            "vector v = vec([\"x\", 1.0])\n",
            "EMB_INVALID_INPUT",
            line=1,
        )

    def test_list_not_implicitly_converted(self):
        # 字面量 list 不得隐式转 vector（显式 vec() 是唯一构造入口）
        from core.kernel.issue import CompilerError

        from tests.behavior.helpers import run

        try:
            run("vector v = [1.0, 2.0]\n")
            raise AssertionError("Expected compile error")
        except CompilerError as e:
            codes = [d.code for d in getattr(e, "diagnostics", [])]
            assert "SEM_TYPE_MISMATCH" in codes, f"diags={codes}"


class TestDimensionMismatch:
    """C4 dim 不一致 fail-fast（可定位 + EMB_ 码）。"""

    def test_mismatch_fail_fast(self):
        for method in ("dot", "cosine", "add", "sub"):
            assert_error(
                "vector v = vec([1.0, 2.0])\n"
                "vector w = vec([1.0, 2.0, 3.0])\n"
                f"v.{method}(w)\n",
                "EMB_DIMENSION_MISMATCH",
                line=3,
            )

    def test_non_vector_operand_fail_fast(self):
        assert_error(
            "vector v = vec([1.0])\nv.dot(1.0)\n",
            "EMB_INVALID_INPUT",
            line=2,
        )


class TestDictKeyExclusion:
    """C6 vector 不作 dict 键（显式违约）。"""

    def test_vector_as_dict_key_fails(self):
        assert_error(
            "vector v = vec([1.0])\ndict d = {}\nd[v] = 1\n",
            "EMB_INVALID_INPUT",
            line=3,
        )


class TestMathProperties:
    """T7 尺度不变 / T8 无隐式归一 / T9 返回类型锁定（精确值钉语义）。"""

    def test_cosine_scale_invariance(self):
        assert_output(
            "vector v = vec([1.0, 2.0, 3.0])\n"
            "vector w = vec([4.0, 5.0, 6.0])\n"
            "print(v.cosine(w))\n"
            "print(v.scale(2.0).cosine(w.scale(3.0)))\n",
            ["0.9746318461970762", "0.9746318461970762"],
        )

    def test_no_implicit_normalization(self):
        assert_output(
            "vector v = vec([3.0, 4.0])\n"
            "print(v.norm())\n"
            "print(v.scale(2.0).norm())\n",
            ["5.0", "10.0"],
        )

    def test_method_returns_vector_type(self):
        # 修改操作返回 vector 类型（类型漂移防护——type() 可观察）
        assert_output(
            "vector v = vec([1.0, 2.0])\n"
            "print(type(v.scale(2.0)))\n"
            "print(type(v.add(v)))\n"
            "print(type(v.sub(v)))\n",
            ["vector", "vector", "vector"],
        )

    def test_zero_norm_cosine_fail_fast(self):
        # 零范数 = 余弦未定义（显式错误——不静默 0）
        assert_error(
            "vector v = vec([0.0, 0.0])\nprint(v.cosine(v))\n",
            "EMB_ZERO_NORM",
            line=2,
        )
