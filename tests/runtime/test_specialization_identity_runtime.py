"""
tests/runtime/test_specialization_identity_runtime.py — 特化身份运行时契约。

判别性测试：
- 跨 module 特化键不坍缩（geo.Box[int] vs main.Box[int] 独立注册）；
- _resolve_type_identifier 两形态（命中已注册特化类 → IbClass；未注册 → boxed 串）
  及 _type_ref_name 消费一致性。
"""

import os

from core.engine import IBCIEngine

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _engine():
    return IBCIEngine(root_dir=_ROOT)


def _symbol(engine, name):
    rc = engine.interpreter.execution_context.runtime_context
    return rc.get_symbol(name).value


class TestModuleQualifiedSpecializationKey:
    def test_cross_module_specialization_not_collapsed(self):
        """geo.Box[int] 与入口模块 Box[int] 特化键独立（module 限定）。"""
        import tempfile
        import pathlib

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "geo.ibci").write_text(
                "class Box[T]:\n"
                "    T value\n"
                "    func __init__(self, T v) -> auto:\n"
                "        self.value = v\n",
                encoding="utf-8",
            )
            engine = IBCIEngine(root_dir=str(root))
            engine.run_string(
                "import geo\n"
                "class Box[T]:\n"
                "    T value\n"
                "    func __init__(self, T v) -> auto:\n"
                "        self.value = v\n"
                "geo.Box[int] g = geo.Box[int](1)\n"
                "Box[int] m = Box[int](2)\n",
                silent=True,
            )
            g = _symbol(engine, "g")
            m = _symbol(engine, "m")
            assert g.ib_class.name == "Box[int]"
            assert m.ib_class.name == "Box[int]"
            # 两特化类独立（module 限定键）
            assert g.ib_class is not m.ib_class, "跨模块同名特化类应独立"


class TestResolveTypeIdentifierDualPath:
    def test_registered_specialization_resolves_to_class(self):
        """嵌套泛型实参命中已注册特化类 → 返回 IbClass（结构化路径）。"""
        from core.kernel.spec.type_ref import TypeRef

        engine = _engine()
        engine.run_string("list[int] li = [1]\nBoxHolder: pass\n", silent=True) if False else None
        engine.run_string("list[int] li = [1]\n", silent=True)
        from core.runtime.vm.handlers._shared import _resolve_type_identifier

        # 预水化特化类（list[int] 出现在编译产物 → loader 预创建）
        arg_ref = TypeRef.parse("list[int]")
        ident = _resolve_type_identifier(engine.interpreter._get_vm_executor(), arg_ref)
        from core.runtime.objects.kernel import IbClass
        assert isinstance(ident, IbClass), (
            f"已注册特化应解析为 IbClass，got {type(ident)}"
        )
        assert ident.name == "list[int]"

    def test_unregistered_falls_back_to_boxed(self):
        """未注册嵌套泛型实参 → 回落 boxed 特化名（职责分离 fallback）。"""
        from core.kernel.spec.type_ref import TypeRef

        engine = _engine()
        engine.run_string("int x = 1\n", silent=True)
        from core.runtime.vm.handlers._shared import _resolve_type_identifier

        # 编译产物中不存在的特化（运行时首遇）——非预创建 → boxed 回落
        arg_ref = TypeRef.parse("list[float]")
        ident = _resolve_type_identifier(engine.interpreter._get_vm_executor(), arg_ref)
        assert isinstance(ident, str) or hasattr(ident, "to_native"), (
            f"未注册特化应回落 boxed 标识，got {type(ident)}"
        )
        native = ident.to_native() if hasattr(ident, "to_native") else ident
        assert native == "list[float]"

    def test_type_ref_name_consumes_both_forms(self):
        """_type_ref_name 对 IbClass 与 boxed 串两形态消费一致。"""
        from core.kernel.spec.type_ref import TypeRef

        engine = _engine()
        engine.run_string("list[int] li = [1]\n", silent=True)
        cls = engine.registry.get_class("list[int]", module=None) or \
            engine.registry.get_class("list[int]")
        assert cls is not None
        from core.runtime.objects.kernel.ib_class import IbClass

        name_from_class = IbClass._type_ref_name(cls)
        assert name_from_class == "list[int]"
        boxed = engine.registry.box("list[int]")
        name_from_boxed = IbClass._type_ref_name(boxed)
        assert name_from_boxed == "list[int]"
