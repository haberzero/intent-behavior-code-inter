"""
tests/runtime/test_member_single_authority.py — 类成员单一权威契约（阶段 B3）。

B3 契约（spec↔运行期对象身份同构）：
- 成员声明单一权威 = spec.members（编译期）；
- 运行期 member_types 是 spec.members 字段声明的派生缓存（水化时一次性解析），
  与声明一致（键 ⊆ + 解析类型一致）；
- 运行期 default_fields 字段 ⊆ spec.members 字段声明（用户类水化后）；
- 运行期方法表（lookup_method）覆盖 spec.members 方法声明（用户类水化后）。
"""

import os

from core.engine import IBCIEngine

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _engine():
    return IBCIEngine(root_dir=_ROOT, auto_sniff=False)


def _get_class(engine, name, module="__string_exec__"):
    return engine.registry.get_class(name, module=module) or \
        engine.registry.get_class(name)


def _run_class(engine, code: str):
    engine.run_string(code, silent=True)


class TestMemberSingleAuthority:
    def test_member_types_derived_from_spec_members(self):
        """member_types 与 spec.members 字段声明一致（派生缓存契约）。"""
        engine = _engine()
        _run_class(engine, """
class Box:
    int v
    str name
    func get(self) -> int:
        return self.v
""")
        cls = _get_class(engine, "Box")
        spec_reg = engine.registry.get_metadata_registry()
        assert cls is not None and cls.spec is not None
        declared_fields = {
            m_name: m for m_name, m in (cls.spec.members or {}).items()
            if getattr(m, "kind", None) == "field"
        }
        assert declared_fields, "应有字段声明"
        # member_types 键 ⊆ spec.members 字段键
        assert set(cls.member_types) <= set(declared_fields), (
            f"member_types 含未声明字段: {set(cls.member_types) - set(declared_fields)}"
        )
        # 解析类型一致（spec.members 声明 → resolve_typeref == member_types 值）
        for m_name, m in declared_fields.items():
            if m_name not in cls.member_types:
                continue
            declared_spec = spec_reg.resolve_typeref(m.type_ref)
            assert declared_spec is not None
            assert declared_spec is cls.member_types[m_name], (
                f"字段 '{m_name}' member_types 与声明解析不一致"
            )

    def test_default_fields_subset_of_spec_members(self):
        """运行期 default_fields ⊆ spec.members 字段声明（用户类）。"""
        engine = _engine()
        _run_class(engine, """
class Box:
    int v
    int w
    func get(self) -> int:
        return self.v
""")
        cls = _get_class(engine, "Box")
        declared_fields = {
            m_name for m_name, m in (cls.spec.members or {}).items()
            if getattr(m, "kind", None) == "field"
        }
        assert declared_fields
        assert set(cls.default_fields) <= declared_fields, (
            f"default_fields 含未声明字段: {set(cls.default_fields) - declared_fields}"
        )

    def test_method_table_covers_declared_methods(self):
        """运行期方法表覆盖 spec.members 方法声明（用户类水化后）。"""
        engine = _engine()
        _run_class(engine, """
class Box:
    int v
    func get(self) -> int:
        return self.v
    func set(self, int x) -> auto:
        self.v = x
""")
        cls = _get_class(engine, "Box")
        declared_methods = {
            m_name for m_name, m in (cls.spec.members or {}).items()
            if getattr(m, "kind", None) == "method"
        }
        assert {"get", "set"} <= declared_methods
        for m_name in declared_methods:
            method = cls.lookup_method(m_name)
            assert method is not None, f"声明方法 '{m_name}' 无运行期实现"

    def test_field_value_semantics_consistent(self):
        """字段默认值经声明类型包装（Optional 值模型与声明一致）。"""
        engine = _engine()
        _run_class(engine, """
class Holder:
    Optional[int] opt
    int plain
    func __init__(self) -> auto:
        pass
Holder h = Holder()
""")
        rc = engine.interpreter.execution_context.runtime_context
        h = rc.get_symbol("h").value
        # 字段默认值（无默认值声明 → None）经声明类型包装
        assert "opt" in h.fields
        from core.runtime.objects.primitives.optional import IbOptional
        assert isinstance(h.fields["opt"], IbOptional), (
            "Optional 字段应经声明类型包装（统一 Optional 值模型）"
        )
