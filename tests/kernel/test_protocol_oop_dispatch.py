"""
tests/kernel/test_protocol_oop_dispatch.py — OOP 协议化契约（阶段 A）。

阶段 A（dunder 协议注册表化）契约：
- op_constants（VM 运算符映射）与协议注册表 operator 元组一致性（层约束镜像
  以契约测试锁定，code-quality §八处置）；
- dunder 分派索引（协议方法名并集）正确派生且注册新协议后失效重建；
- attribute 协议（__getattr__/__setattr__）在位（属性访问协议化覆盖）。
"""

from core.kernel.factory import create_default_registry
from core.kernel.protocol import ProtocolDef
from core.runtime.shared.op_constants import (
    AST_OP_MAP,
    OP_MAPPING,
    UNARY_OP_MAPPING,
)


class TestOpConstantsConsistency:
    """op_constants 与协议 operator 元组双向一致（层约束镜像契约）。

    kernel 层禁 runtime 导入（用户红线）→ 镜像常量不可代码合并；以契约测试
    取代人工同步：OP_MAPPING/UNARY_OP_MAPPING 的 dunder 值 ⊆ operator 协议
    methods，且 operator methods 只含 op_constants 发出的 dunder（加 VM 固定
    发出点豁免集）。
    """

    def _operator_methods(self) -> tuple:
        reg = create_default_registry()
        op = reg.get_protocol("operator")
        assert op is not None
        return op.methods

    def test_op_mapping_values_subset_of_operator_protocol(self):
        methods = set(self._operator_methods())
        emitted = set(OP_MAPPING.values()) | set(UNARY_OP_MAPPING.values())
        missing = emitted - methods
        assert not missing, (
            f"op_constants 发出的 dunder 不在 operator 协议 methods 中: {sorted(missing)}"
        )

    def test_operator_protocol_methods_covered_by_emitters(self):
        """operator methods 均有发出点（op_constants 或 VM 固定字符串）。"""
        methods = set(self._operator_methods())
        emitted = set(OP_MAPPING.values()) | set(UNARY_OP_MAPPING.values())
        vm_fixed = {"__contains__", "__not__"}
        uncovered = methods - emitted - vm_fixed
        assert not uncovered, (
            f"operator 协议 methods 无发出点覆盖: {sorted(uncovered)}"
        )

    def test_pos_in_operator_protocol(self):
        """一元 ``+``（__pos__）在 UNARY 表且在 operator 元组（双真相补齐）。"""
        assert "__pos__" in UNARY_OP_MAPPING.values()
        assert "__pos__" in self._operator_methods()

    def test_eq_ne_in_operator_protocol(self):
        """``==``/``!=`` 映射与 operator 协议含 __eq__/__ne__（== 空白区闭合）。"""
        assert "__eq__" in OP_MAPPING.values()
        assert "__ne__" in OP_MAPPING.values()
        methods = set(self._operator_methods())
        assert {"__eq__", "__ne__"} <= methods

    def test_ast_op_map_values_covered(self):
        """AST 符号归一化映射的值均为 op_constants 已发出符号。"""
        covered = set(OP_MAPPING) | set(UNARY_OP_MAPPING)
        unknown = set(AST_OP_MAP.values()) - covered
        assert not unknown, f"AST_OP_MAP 值无映射表覆盖: {sorted(unknown)}"


class TestDunderNamesIndex:
    """dunder 分派索引（协议方法名并集）派生与失效。"""

    def test_index_contains_dunder_protocol_methods(self):
        reg = create_default_registry()
        names = reg.dunder_names()
        for expected in (
            "__call__", "__getattr__", "__setattr__", "__getitem__",
            "__iter__", "__eq__", "__ne__", "cast_to",
            "__to_prompt__", "__from_prompt__", "__snapshot__", "__restore__",
        ):
            assert expected in names, f"dunder 索引缺 {expected}"

    def test_index_invalidated_on_new_protocol(self):
        """注册新协议后索引重建（缓存失效）。"""
        reg = create_default_registry()
        assert "__zzz_marker__" not in reg.dunder_names()
        reg.register_protocol(
            ProtocolDef(name="zzz_marker", methods=("__zzz_marker__",))
        )
        assert "__zzz_marker__" in reg.dunder_names()

    def test_index_invalidated_via_direct_registry_register(self):
        """任何注册路径（含 register_from_spec 底层直接 register）均失效索引。

        复核 P2-1 契约：缓存按注册表版本号失效，不依赖 mixin 入口。
        """
        reg = create_default_registry()
        assert "__yyy_marker__" not in reg.dunder_names()
        # 直接经 ProtocolRegistry.register（register_from_spec 同路径）
        reg.protocols.register(
            ProtocolDef(name="yyy_marker", methods=("__yyy_marker__",))
        )
        assert "__yyy_marker__" in reg.dunder_names()

    def test_index_invalidated_via_register_from_spec(self):
        """register_from_spec（用户协议水化路径）后索引失效。"""
        from core.kernel.spec import TypeDef, TypeKind, MethodMemberSpec

        reg = create_default_registry()
        assert "__xxx_marker__" not in reg.dunder_names()
        spec = TypeDef(
            name="xxx_proto",
            kind=TypeKind.PROTOCOL.value,
            provenance="USER_DEFINED",
        )
        spec.members["__xxx_marker__"] = MethodMemberSpec(
            name="__xxx_marker__",
            kind="method",
            return_type=None,
            param_types=[],
        )
        reg.protocols.register_from_spec(spec)
        assert "__xxx_marker__" in reg.dunder_names()

    def test_index_is_frozenset(self):
        reg = create_default_registry()
        assert isinstance(reg.dunder_names(), frozenset)


class TestAttributeProtocol:
    """attribute 协议（属性访问协议化覆盖）。"""

    def test_attribute_protocol_registered(self):
        reg = create_default_registry()
        attr = reg.get_protocol("attribute")
        assert attr is not None
        assert attr.methods == ("__getattr__", "__setattr__")
