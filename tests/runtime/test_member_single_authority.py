"""
tests/runtime/test_member_single_authority.py — 类成员单一权威契约。

契约（spec↔运行期对象身份同构）：
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
    return IBCIEngine(root_dir=_ROOT)


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


class TestAutoInitDeclaration:
    """auto-init 声明化：类属性声明 + 成员表权威 + 共享实现。"""

    def test_auto_init_fields_registered(self):
        """auto-init 字段名清单注册到类属性（声明，非闭包捕获）。"""
        engine = _engine()
        _run_class(engine, """
class Dog:
    str name
    int age
Dog d = Dog("Rex", 5)
""")
        cls = _get_class(engine, "Dog")
        assert cls.auto_init_fields == ["name", "age"]

    def test_init_member_declared_in_spec(self):
        """spec.members['__init__'] 声明（成员表权威——数量校验单一来源）。"""
        engine = _engine()
        _run_class(engine, """
class Dog:
    str name
    int age
Dog d = Dog("Rex", 5)
""")
        cls = _get_class(engine, "Dog")
        init_member = (cls.spec.members or {}).get("__init__")
        assert init_member is not None, "auto-init 应有 spec.members['__init__'] 声明"
        assert len(init_member.param_types) == 2

    def test_arity_error_from_single_authority(self):
        """参数数量错误经 _init_expected_arity（成员表）统一拦截。"""
        import pytest

        engine = _engine()
        with pytest.raises(RuntimeError):
            _run_class(engine, """
class Dog:
    str name
    int age
Dog d = Dog("Rex")
""")

    def test_chain_auto_init_inherited_fields(self):
        """继承链 auto-init：父类无默认值字段并入子类构造器（chain-aware）。"""
        engine = _engine()
        _run_class(engine, """
class Base:
    int id
class Sub(Base):
    str tag
Sub s = Sub(1, "x")
""")
        rc = engine.interpreter.execution_context.runtime_context
        s = rc.get_symbol("s").value
        assert s.fields["id"].to_native() == 1
        assert s.fields["tag"].to_native() == "x"
