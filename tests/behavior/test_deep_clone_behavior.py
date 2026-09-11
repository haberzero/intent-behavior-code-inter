"""语言行为层：deepcopy 值语义（R3-C9 迁移——原 test_generic_value_identity /
test_storage_model_dispatch 的 deep_clone 内部断言 → 可观察断言面）。

**迁移映射**：深克隆保留特化容器类型身份（list[int]/dict[str,int]）+ 值独立
（克隆修改不污染原值）+ 内存型 list 独立副本 + 磁盘型对象 __clone_ref__ 协议
（内部——协议面，可观察契约 = 磁盘后备值[file_handle/narrow_model] deepcopy
可独立工作，经宿主层测试承接）→ 数据面断言。
"""

from tests.behavior.helpers import assert_output


class TestDeepCloneValueSemantics:
    def test_deep_clone_preserves_list_specialized_identity(self):
        """深克隆特化 list 保留类型身份且值独立（快照/字段默认值路径）。"""
        assert_output(
            "list[int] li = [1, 2]\n"
            "lc = deepcopy(li)\n"
            "print(type(lc))\n"
            "lc.append(99)\n"
            "print(li)\n"
            "print(lc)\n",
            ["list[int]", "[1, 2]", "[1, 2, 99]"],
        )

    def test_deep_clone_preserves_dict_specialized_identity(self):
        """深克隆特化 dict 保留类型身份且值独立。"""
        assert_output(
            'dict[str, int] d = {"a": 1}\n'
            "dc = deepcopy(d)\n"
            "print(type(dc))\n"
            'dc["a"] = 42\n'
            'print(d["a"])\n'
            'print(dc["a"])\n',
            ["dict[str,int]", "1", "42"],
        )

    def test_deep_clone_generic_list_independent(self):
        """内存型 list deepcopy = 独立副本（修改克隆不污染原值）。"""
        assert_output(
            "list a = [1, 2]\n"
            "b = deepcopy(a)\n"
            "b.append(3)\n"
            "print(a)\n"
            "print(b)\n",
            ["[1, 2]", "[1, 2, 3]"],
        )
