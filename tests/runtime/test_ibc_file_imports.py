"""
tests/runtime/test_ibc_file_imports.py
=======================================

IBC 文件跨模块导入（具名 / import-*）回归测试。

背景：该路径此前**完全断裂**（零测试覆盖）——
1. scheduler.py 用裸 `TypeDef`（别名 `ModuleMetadata` 后 NameError → INT_INTERNAL_ERROR）；
2. 文件模块元数据用 Lazy 空描述符，members 恒空 → 具名/星号导入全部 SEM_UNDEFINED_SYMBOL；
3. 运行时 `module_instance.get_variable`（IbModule 无此方法）→ AttributeError。
根治重构（B-D6 断层修复）同时修复了这三层断裂。

同时锁定 import-* 的"精确成员枚举"机制（编译器记录 import_star_members，
运行时据此枚举，不再 dir(package) ∩ 整张模块表）。
"""
import os

from core.engine import IBCIEngine


def _write(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return str(p)


def _run(tmp_path, main_name="main.ibci"):
    engine = IBCIEngine(root_dir=str(tmp_path), auto_sniff=False)
    lines = []
    engine.run(
        str(tmp_path / main_name),
        output_callback=lambda s: lines.append(str(s)),
        silent=True,
    )
    return lines


class TestIbcFileNamedImport:
    """``from <ibci文件> import name`` 具名导入。"""

    def test_named_import_variable(self, tmp_path):
        _write(tmp_path, "helper.ibci", "int answer = 42\n")
        _write(tmp_path, "main.ibci", "from helper import answer\nprint(answer)\n")
        assert _run(tmp_path) == ["42"]

    def test_named_import_function(self, tmp_path):
        _write(
            tmp_path,
            "helper.ibci",
            "func greet() -> str:\n    return \"hi\"\n",
        )
        _write(tmp_path, "main.ibci", "from helper import greet\nprint(greet())\n")
        assert _run(tmp_path) == ["hi"]

    def test_named_import_alias(self, tmp_path):
        _write(tmp_path, "helper.ibci", "int answer = 42\n")
        _write(tmp_path, "main.ibci", "from helper import answer as a\nprint(a)\n")
        assert _run(tmp_path) == ["42"]

    def test_named_import_missing_symbol(self, tmp_path):
        _write(tmp_path, "helper.ibci", "int answer = 42\n")
        _write(tmp_path, "main.ibci", "from helper import missing\n")
        engine = IBCIEngine(root_dir=str(tmp_path), auto_sniff=False)
        try:
            engine.compile(str(tmp_path / "main.ibci"), silent=True)
            raise AssertionError("导入不存在的符号应编译失败")
        except Exception as e:
            codes = {d.code for d in getattr(e, "diagnostics", [])}
            assert "SEM_UNDEFINED_SYMBOL" in codes


class TestIbcFileStarImport:
    """``from <ibci文件> import *`` 精确成员枚举。"""

    def test_star_import_all_members(self, tmp_path):
        _write(
            tmp_path,
            "helper.ibci",
            "int answer = 42\nfunc greet() -> str:\n    return \"hi\"\n",
        )
        _write(
            tmp_path,
            "main.ibci",
            "from helper import *\nprint(answer)\nprint(greet())\n",
        )
        assert _run(tmp_path) == ["42", "hi"]

    def test_star_import_does_not_leak_importing_module_intrinsics(self, tmp_path):
        """import-* 只注入被导入模块声明的成员，不注入当前模块的 int/print 等。"""
        _write(tmp_path, "helper.ibci", "int answer = 42\n")
        _write(
            tmp_path,
            "main.ibci",
            "from helper import *\n"
            "print(type(answer))\n"
            # 内建仍可用且未被 import-* 覆盖
            "print(type(len([1, 2])))\n",
        )
        assert _run(tmp_path) == ["int", "int"]


class TestIbcFileMultiModule:
    """多模块链式导入。"""

    def test_transitive_import(self, tmp_path):
        _write(tmp_path, "a.ibci", "int from_a = 1\n")
        _write(tmp_path, "b.ibci", "int from_b = 2\n")
        _write(tmp_path, "c.ibci", "from a import from_a\nfrom b import from_b\nprint(from_a + from_b)\n")
        assert _run(tmp_path, "c.ibci") == ["3"]

    def test_star_import_multiple_modules(self, tmp_path):
        _write(tmp_path, "a.ibci", "int from_a = 10\n")
        _write(tmp_path, "b.ibci", "int from_b = 20\n")
        _write(tmp_path, "main.ibci", "from a import *\nfrom b import *\nprint(from_a + from_b)\n")
        assert _run(tmp_path) == ["30"]

    def test_import_star_members_recorded_in_artifact(self, tmp_path):
        """编译器把 import-* 的精确成员名记录进 artifact（根治机制的序列化契约）。"""
        _write(
            tmp_path,
            "helper.ibci",
            "int answer = 42\nfunc greet() -> str:\n    return \"hi\"\n",
        )
        main = str(tmp_path / "main.ibci")
        _write(tmp_path, "main.ibci", "from helper import *\n")
        engine = IBCIEngine(root_dir=str(tmp_path), auto_sniff=False)
        artifact = engine.compile(main, silent=True)
        from core.compiler.serialization.serializer import FlatSerializer
        d = FlatSerializer().serialize_artifact(artifact)
        mod = d["modules"][artifact.entry_module]
        star = mod.get("import_star_members", {})
        assert sorted(star.get("helper", [])) == ["answer", "greet"]


class TestIbcFileWholeImport:
    """``import mod`` 整模块导入 + 成员访问（PT-DEBT-26，2026-08-12）。

    此前模块元数据 members 以 Symbol 形态写入，resolve_member 只认
    MemberSpec 形态 → 整模块 import + 成员访问触发 INT_INTERNAL_ERROR
    （FunctionSymbol/VariableSymbol 无 type_ref）。修复=scheduler 写入侧
    统一为 MemberSpec/MethodMemberSpec（_symbol_to_member）。
    """

    def test_whole_import_function_call(self, tmp_path):
        _write(
            tmp_path,
            "helper.ibci",
            "func greet() -> str:\n    return \"hi\"\n",
        )
        _write(tmp_path, "main.ibci", "import helper\nprint(helper.greet())\n")
        assert _run(tmp_path) == ["hi"]

    def test_whole_import_variable_access(self, tmp_path):
        _write(tmp_path, "helper.ibci", "int answer = 42\n")
        _write(tmp_path, "main.ibci", "import helper\nprint((str)helper.answer)\n")
        assert _run(tmp_path) == ["42"]

    def test_whole_import_function_and_variable_mixed(self, tmp_path):
        _write(
            tmp_path,
            "helper.ibci",
            "func double(int x) -> int:\n    return x * 2\nint base = 10\n",
        )
        _write(
            tmp_path,
            "main.ibci",
            "import helper\nint v = helper.double(helper.base)\nprint((str)v)\n",
        )
        assert _run(tmp_path) == ["20"]

    def test_whole_import_consistency_with_named_import_type_check(self, tmp_path):
        """同一符号经 mod.x 与 from mod import x 的类型诊断应一致。

        档2 修复：零参数函数成员此前退化到 any（运行时才报类型错）；
        现在整模块与命名导入一样编译期报 SEM_TYPE_MISMATCH。
        """
        _write(
            tmp_path,
            "helper.ibci",
            "func greet() -> str:\n    return \"hi\"\n",
        )
        # 整模块路径：int x = helper.greet() 必须编译期报错
        _write(
            tmp_path,
            "main_whole.ibci",
            "import helper\nint x = helper.greet()\n",
        )
        engine = IBCIEngine(root_dir=str(tmp_path), auto_sniff=False)
        try:
            engine.compile(str(tmp_path / "main_whole.ibci"), silent=True)
            raise AssertionError("整模块导入的零参数函数类型错应编译期报错")
        except Exception as e:
            codes = {d.code for d in getattr(e, "diagnostics", [])}
            assert "SEM_TYPE_MISMATCH" in codes, codes

        # 命名导入路径对照
        _write(
            tmp_path,
            "main_named.ibci",
            "from helper import greet\nint x = greet()\n",
        )
        engine = IBCIEngine(root_dir=str(tmp_path), auto_sniff=False)
        try:
            engine.compile(str(tmp_path / "main_named.ibci"), silent=True)
            raise AssertionError("命名导入的零参数函数类型错应编译期报错")
        except Exception as e:
            codes = {d.code for d in getattr(e, "diagnostics", [])}
            assert "SEM_TYPE_MISMATCH" in codes, codes


def _write_nested(tmp_path, rel_path, content):
    p = tmp_path / rel_path
    os.makedirs(p.parent, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return str(p)


class TestIbcFileGenericExport:
    """泛型变量经整模块 import 导出的类型保真（GEN-FIX 收敛判别性回归）。

    模块导出符号经 _spec_to_typeref 收敛（委托 TypeRef.from_spec）后，thread[T]/
    chan[T]/fn_callable[T]/用户类特化/多参 tuple 必须结构化保真。
    修复前：thread[int]→thread[any]（读错字段）、chan[str]→扁平、
    fn_callable[int]→fn[__args__()->void]（kind 级腐蚀）、tuple[int,str]→tuple
    （丢位置元素）。
    """

    def _scheduler_typeref(self, spec):
        """经 scheduler._spec_to_typeref 收敛产出 TypeRef（white-box 契约）。"""
        from core.compiler.scheduler import Scheduler
        s = Scheduler(root_dir=".")
        return s._spec_to_typeref(spec).canonical_name

    def test_thread_typeref_structured(self):
        from core.kernel.spec.type_ref import TypeRef
        from core.kernel.spec.base import TypeKind, TypeDef, Provenance, Visibility
        sp = TypeDef(name="thread[int]", kind=TypeKind.THREAD.value, value_type=TypeRef.of("int"),
                     provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE)
        assert self._scheduler_typeref(sp) == "thread[int]"

    def test_chan_typeref_structured(self):
        from core.kernel.spec.type_ref import TypeRef
        from core.kernel.spec.base import TypeKind, TypeDef, Provenance, Visibility
        sp = TypeDef(name="chan[str]", kind=TypeKind.CHANNEL.value, value_type=TypeRef.of("str"),
                     provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE)
        assert self._scheduler_typeref(sp) == "chan[str]"

    def test_fn_callable_typeref_structured(self):
        from core.kernel.spec.type_ref import TypeRef
        from core.kernel.spec.base import TypeKind, TypeDef, Provenance, Visibility
        sp = TypeDef(name="fn_callable[int]", kind=TypeKind.CALLABLE_INSTANCE.value,
                     value_type=TypeRef.of("int"),
                     provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE)
        assert self._scheduler_typeref(sp) == "fn_callable[int]"

    def test_user_generic_typeref_structured(self):
        from core.kernel.spec.type_ref import TypeRef
        from core.kernel.spec.base import TypeKind, TypeDef, Provenance, Visibility
        sp = TypeDef(name="Box[int]", kind=TypeKind.CLASS.value, type_params=["T"],
                     type_args=[TypeRef.of("int")], base_name="Box",
                     provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE)
        assert self._scheduler_typeref(sp) == "Box[int]"

    def test_tuple_positional_typeref_structured(self):
        from core.kernel.spec.type_ref import TypeRef
        from core.kernel.spec.base import TypeKind, TypeDef, Provenance, Visibility
        sp = TypeDef(name="tuple", kind=TypeKind.TUPLE.value,
                     positional_element_types=[TypeRef.of("int"), TypeRef.of("str")],
                     provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE)
        assert self._scheduler_typeref(sp) == "tuple[int,str]"

    def test_function_signature_still_structured(self):
        """FUNCTION kind 保留 fn[(args)->ret] 结构化签名（模块导出函数契约）。"""
        from core.kernel.spec.type_ref import TypeRef
        from core.kernel.spec.base import TypeKind, TypeDef, Provenance, Visibility
        sp = TypeDef(name="double", kind=TypeKind.FUNCTION.value,
                     param_types=[TypeRef.of("int")], return_type=TypeRef.of("int"),
                     provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE)
        assert self._scheduler_typeref(sp) == "fn[__args__[int],int]"

    def test_whole_import_fn_callable_callable(self, tmp_path):
        """fn_callable 导出后可调用（可观察契约）。"""
        _write(
            tmp_path,
            "helper.ibci",
            "fn_callable[int] f = lambda() -> int: 1\n",
        )
        _write(
            tmp_path,
            "main.ibci",
            "import helper\n"
            "print(type(helper.f))\n"
            "int v = helper.f()\n"
            "print((str)v)\n",
        )
        assert _run(tmp_path) == ["fn_callable[()->int]", "1"]

    def test_whole_import_user_generic_value(self, tmp_path):
        """用户泛型导出后字段可访问（可观察契约）。"""
        _write(
            tmp_path,
            "helper.ibci",
            "class Box[T]:\n"
            "    T value\n"
            "    func __init__(self, T value) -> void:\n"
            "        self.value = value\n"
            "Box[int] b = Box[int](42)\n",
        )
        _write(
            tmp_path,
            "main.ibci",
            "import helper\n"
            "print(type(helper.b))\n"
            "print((str)helper.b.value)\n",
        )
        assert _run(tmp_path) == ["Box[int]", "42"]


class TestIbcFileNestedPackageImport:
    """嵌套包 `import subpkg.util` + 成员访问（2026-08-12 根治）。

    此前中间模块符号以原始 Symbol 形态存入 members（无 type_ref）→
    resolve_member 触发 INT_INTERNAL_ERROR；且 visit_IbImport 绑定全名而
    scheduler 只注入根段 → SEM_UNDEFINED_SYMBOL；运行时缺包命名空间绑定。
    修复：嵌套段统一 MemberSpec 形态 + 绑定根段 + 运行时包命名空间。
    """

    def test_nested_import_function_call(self, tmp_path):
        _write_nested(tmp_path, "subpkg/util.ibci", 'func util_fn() -> str:\n    return "util-value"\n')
        _write_nested(tmp_path, "subpkg/__init__.ibci", "")
        _write(tmp_path, "main.ibci", "import subpkg.util\nprint(subpkg.util.util_fn())\n")
        assert _run(tmp_path) == ["util-value"]

    def test_nested_three_level(self, tmp_path):
        _write_nested(tmp_path, "a/b/c.ibci", 'func cf() -> str:\n    return "c-value"\n')
        _write_nested(tmp_path, "a/b/__init__.ibci", "")
        _write_nested(tmp_path, "a/__init__.ibci", "")
        _write(tmp_path, "main.ibci", "import a.b.c\nprint(a.b.c.cf())\n")
        assert _run(tmp_path) == ["c-value"]

    def test_multi_import_same_package_merges(self, tmp_path):
        """同一包多次导入：根包命名空间幂等合并（a.b.c + a.b.d 均可达）。"""
        _write_nested(tmp_path, "a/b/c.ibci", 'func cf() -> str:\n    return "c-value"\n')
        _write_nested(tmp_path, "a/b/d.ibci", 'func df() -> str:\n    return "d-value"\n')
        _write_nested(tmp_path, "a/b/__init__.ibci", "")
        _write_nested(tmp_path, "a/__init__.ibci", "")
        _write(
            tmp_path,
            "main.ibci",
            "import a.b.c\nimport a.b.d\nprint(a.b.c.cf())\nprint(a.b.d.df())\n",
        )
        assert _run(tmp_path) == ["c-value", "d-value"]

    def test_nested_import_alias_and_named_still_work(self, tmp_path):
        _write_nested(tmp_path, "subpkg/util.ibci", 'func util_fn() -> str:\n    return "util-value"\n')
        _write_nested(tmp_path, "subpkg/__init__.ibci", "")
        _write(
            tmp_path,
            "main.ibci",
            "import subpkg.util as m\nfrom subpkg.util import util_fn\n"
            "print(m.util_fn())\nprint(util_fn())\n",
        )
        assert _run(tmp_path) == ["util-value", "util-value"]
