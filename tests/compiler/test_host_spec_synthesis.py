"""
tests/compiler/test_host_spec_synthesis.py — 宿主绑定声明 → 成员 spec 合成契约
（core/compiler/host_spec_synthesis 单一权威源）。

**契约**：
- 方法成员（bind f(params) -> ret）：MethodMemberSpec——param_types 逐参数注解、
  return_type 返回注解（无注解 = void）、param_descriptors 与 param_types 同源
  （POSITIONAL_OR_KEYWORD）。
- 属性成员（bind x -> type）：MemberSpec（kind=field）——type_ref 注解（无注解
  = any）。
- 重复 bind 同名成员：首个入表，其余返回结构化校验错误（不入表）。
- 用户侧行为锁定：既有宿主绑定测试（tests/runtime/test_host_binding.py）+ 全量
  零回归覆盖 scheduler 路径（本重构为共享函数提取，用户路径改调同源逻辑）。
"""
from __future__ import annotations

from core.kernel import ast
from core.kernel.spec import MemberSpec, MethodMemberSpec
from core.kernel.spec.type_ref import TypeRef
from core.compiler.host_spec_synthesis import synthesize_host_members


def _name(id_: str) -> ast.IbName:
    return ast.IbName(id=id_, ctx="load")


def _method(name: str, params: list, return_type=None) -> ast.IbHostBinding:
    return ast.IbHostBinding(
        name=name,
        is_method=True,
        params=[
            ast.IbHostBindingParam(name=p_name, annotation=p_ann, lineno=1, col_offset=1)
            for p_name, p_ann in params
        ],
        return_type=return_type,
        lineno=1,
        col_offset=1,
    )


def _field(name: str, type_ann=None) -> ast.IbHostBinding:
    return ast.IbHostBinding(
        name=name,
        is_method=False,
        return_type=type_ann,
        lineno=1,
        col_offset=1,
    )


class TestSynthesizeHostMembers:
    def test_method_member(self):
        """方法成员：param_types / return_type / descriptors 同源结构。"""
        m, dups = synthesize_host_members([
            _method("sqrt", [("x", _name("float"))], _name("float")),
        ])
        assert dups == []
        spec = m["sqrt"]
        assert isinstance(spec, MethodMemberSpec)
        assert spec.kind == "method"
        assert spec.param_types == [TypeRef.of("float")]
        assert spec.return_type == TypeRef.of("float")
        assert [d.name for d in spec.param_descriptors] == ["x"]
        assert all(d.kind == "POSITIONAL_OR_KEYWORD" for d in spec.param_descriptors)
        assert [d.type_ref for d in spec.param_descriptors] == [TypeRef.of("float")]

    def test_method_without_return_defaults_void(self):
        """无返回注解 = void（缺省语义）。"""
        m, dups = synthesize_host_members([_method("set_x", [("x", _name("int"))])])
        assert dups == []
        assert m["set_x"].return_type == TypeRef.of("void")

    def test_field_member(self):
        """属性成员：kind=field，type_ref = 声明注解。"""
        m, dups = synthesize_host_members([_field("pi", _name("float"))])
        assert dups == []
        spec = m["pi"]
        assert isinstance(spec, MemberSpec)
        assert spec.kind == "field"
        assert spec.type_ref == TypeRef.of("float")

    def test_field_without_annotation_defaults_any(self):
        """属性无注解 = any（缺省语义）。"""
        m, dups = synthesize_host_members([_field("opaque")])
        assert dups == []
        assert m["opaque"].type_ref == TypeRef.of("any")

    def test_generic_annotation(self):
        """泛型注解（list[int]）：param_types 持结构化 TypeRef。"""
        sub = ast.IbSubscript(value=_name("list"), slice=_name("int"), ctx="load")
        m, dups = synthesize_host_members([
            _method("collect", [("xs", sub)], sub),
        ])
        assert dups == []
        expected = TypeRef("list", (TypeRef.of("int"),))
        assert m["collect"].param_types == [expected]
        assert m["collect"].return_type == expected

    def test_duplicate_member_structured_error(self):
        """重复 bind 同名：首个入表，其余返回结构化错误（不入表）。"""
        m, dups = synthesize_host_members([
            _method("f", [("x", _name("int"))], _name("int")),
            _method("f", [("y", _name("str"))], _name("str")),
        ])
        assert set(m) == {"f"}
        assert m["f"].param_types == [TypeRef.of("int")]  # 首个声明入表
        assert len(dups) == 1
        assert dups[0].member_name == "f"

    def test_mixed_ordering(self):
        """混合声明序：成员表与重复条目按声明序确定。"""
        m, dups = synthesize_host_members([
            _field("a", _name("int")),
            _method("b", [("x", _name("int"))]),
            _field("a", _name("str")),
            _method("b", [("y", _name("int"))]),
        ])
        assert set(m) == {"a", "b"}
        assert m["a"].type_ref == TypeRef.of("int")
        assert [d.member_name for d in dups] == ["a", "b"]
