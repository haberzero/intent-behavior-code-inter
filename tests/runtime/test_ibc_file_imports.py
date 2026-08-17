"""
tests/runtime/test_ibc_file_imports.py
=======================================

IBC 文件跨模块导入（具名 / import-*）行为契约。

该路径须满足：
1. scheduler.py 以 `ModuleMetadata` 别名承载文件模块元数据（不得 NameError → INT_INTERNAL_ERROR）；
2. 文件模块元数据 members 非空 → 具名/星号导入正常解析（不得 SEM_UNDEFINED_SYMBOL）；
3. 运行时 `module_instance.get_variable` 可访问（IbModule 提供此方法，不得 AttributeError）。

同时锁定 import-* 的"精确成员枚举"机制（编译器记录 import_star_members，
运行时据此枚举，不依赖 dir(package) ∩ 整张模块表）。
"""
import os

from core.engine import IBCIEngine


def _write(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return str(p)


def _run(tmp_path, main_name="main.ibci"):
    engine = IBCIEngine(root_dir=str(tmp_path))
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
        engine = IBCIEngine(root_dir=str(tmp_path))
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
        """编译器把 import-* 的精确成员名记录进 artifact（精确成员枚举的序列化契约）。"""
        _write(
            tmp_path,
            "helper.ibci",
            "int answer = 42\nfunc greet() -> str:\n    return \"hi\"\n",
        )
        main = str(tmp_path / "main.ibci")
        _write(tmp_path, "main.ibci", "from helper import *\n")
        engine = IBCIEngine(root_dir=str(tmp_path))
        artifact = engine.compile(main, silent=True)
        from core.compiler.serialization.serializer import FlatSerializer
        d = FlatSerializer().serialize_artifact(artifact)
        mod = d["modules"][artifact.entry_module]
        star = mod.get("import_star_members", {})
        assert sorted(star.get("helper", [])) == ["answer", "greet"]


class TestIbcFileWholeImport:
    """``import mod`` 整模块导入 + 成员访问行为契约。

    模块元数据 members 以 MemberSpec/MethodMemberSpec 形态写入（scheduler
    写入侧经 _symbol_to_member 转换）；resolve_member 按 MemberSpec 解析，
    整模块 import + 成员访问不得触发 INT_INTERNAL_ERROR（Symbol 形态缺 type_ref）。
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

        零参数函数成员保持精确类型（不退化到 any）；整模块与命名导入一样，
        类型不匹配时编译期报 SEM_TYPE_MISMATCH。
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
        engine = IBCIEngine(root_dir=str(tmp_path))
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
        engine = IBCIEngine(root_dir=str(tmp_path))
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
    """泛型变量经整模块 import 导出的类型保真。

    模块导出符号经 _spec_to_typeref 收敛（委托 TypeRef.from_spec）后，thread[T]/
    chan[T]/fn_callable[T]/用户类特化/多参 tuple 必须结构化保真：
    thread[int] 读字段不腐蚀、chan[str] 不扁平化、fn_callable[int] 保留参数
    类型、tuple[int,str] 保留位置元素。
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
    """嵌套包 `import subpkg.util` + 成员访问行为契约。

    中间模块符号以 MemberSpec 形态存入 members（带 type_ref），resolve_member
    不触发 INT_INTERNAL_ERROR；visit_IbImport 绑定全名且 scheduler 注入根段，
    不报 SEM_UNDEFINED_SYMBOL；运行时提供包命名空间绑定。
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


class TestCrossModuleSameNameClass:
    """跨模块同名类身份隔离（编译期 + 运行期 module 化）。

    `geo.Box` 与 `graph.Box` 编译期坍缩为同一 spec、运行期类表 name-only
    坍缩会使方法表按后编译者覆盖（`geo.Box[int](5).get()` 报 int+str 错误）。
    module 限定分离：编译期 spec 独立 + 运行期类表 qualified 键独立。
    """

    def test_same_name_class_compile_time_isolation(self, tmp_path):
        """编译期 + 运行期隔离：方法体语义不串扰（判别性回归）。"""
        _write(
            tmp_path,
            "geo.ibci",
            "class Box[T]:\n"
            "    int v\n"
            "    func get(self) -> int:\n"
            "        return self.v + 100\n",
        )
        _write(
            tmp_path,
            "graph.ibci",
            "class Box[T]:\n"
            "    str name\n"
            "    func get(self) -> str:\n"
            "        return self.name + \"!\"\n",
        )
        _write(
            tmp_path,
            "main.ibci",
            "import geo\n"
            "import graph\n"
            "geo.Box[int] a = geo.Box[int](5)\n"
            "graph.Box[int] b = graph.Box[int](\"hi\")\n"
            "print(a.get())\n"
            "print(b.get())\n"
            "print(type(a.get()))\n"
            "print(type(b.get()))\n",
        )
        # 运行期方法表隔离：geo.get() = v+100 = 105；graph.get() = name+"!" = "hi!"
        # （方法体语义各自独立，互不串扰）
        assert _run(tmp_path) == ["105", "hi!", "int", "str"]

    def test_same_name_class_spec_isolated(self, tmp_path):
        """编译期注册表：geo.Box 与 graph.Box 是独立 spec（module 区分）。"""
        engine = IBCIEngine(root_dir=str(tmp_path))
        _write(
            tmp_path,
            "geo.ibci",
            "class Box[T]:\n"
            "    int v\n",
        )
        _write(
            tmp_path,
            "graph.ibci",
            "class Box[T]:\n"
            "    str name\n",
        )
        _write(
            tmp_path,
            "main.ibci",
            "import geo\n"
            "import graph\n",
        )
        engine.run(str(tmp_path / "main.ibci"), silent=True)
        reg = engine.registry.get_metadata_registry()
        geo_box = reg.resolve("Box", "geo")
        graph_box = reg.resolve("Box", "graph")
        assert geo_box is not None and graph_box is not None
        assert geo_box is not graph_box, (
            "geo.Box 与 graph.Box 应编译期隔离（独立 spec）"
        )
        assert geo_box.module_path == "geo"
        assert graph_box.module_path == "graph"

    def test_same_name_class_runtime_registry_isolated(self, tmp_path):
        """运行期类表：geo.Box / graph.Box 独立 IbClass（qualified 键）。"""
        _write(
            tmp_path,
            "geo.ibci",
            "class Box[T]:\n"
            "    int v\n",
        )
        _write(
            tmp_path,
            "graph.ibci",
            "class Box[T]:\n"
            "    str name\n",
        )
        _write(
            tmp_path,
            "main.ibci",
            "import geo\n"
            "import graph\n",
        )
        engine = IBCIEngine(root_dir=str(tmp_path))
        engine.run(str(tmp_path / "main.ibci"), silent=True)
        geo_box = engine.registry.get_class("geo.Box")
        graph_box = engine.registry.get_class("graph.Box")
        assert geo_box is not None and graph_box is not None
        assert geo_box is not graph_box, (
            "geo.Box 与 graph.Box 应运行期隔离（独立 IbClass，不坍缩）"
        )
        assert geo_box.qualified_name == "geo.Box"
        assert graph_box.qualified_name == "graph.Box"
        # module 感知查找：geo 模块内裸名 Box → geo.Box，graph 内 → graph.Box
        assert engine.registry.get_class("Box", module="geo") is geo_box
        assert engine.registry.get_class("Box", module="graph") is graph_box

    def test_same_name_non_generic_class_isolated(self, tmp_path):
        """跨模块同名**非泛型**类运行期隔离（不依赖特化机制）。"""
        _write(
            tmp_path,
            "geo.ibci",
            "class Wrap:\n"
            "    int v\n"
            "    func get(self) -> int:\n"
            "        return self.v * 2\n",
        )
        _write(
            tmp_path,
            "graph.ibci",
            "class Wrap:\n"
            "    str name\n"
            "    func get(self) -> str:\n"
            "        return self.name.upper()\n",
        )
        _write(
            tmp_path,
            "main.ibci",
            "import geo\n"
            "import graph\n"
            "geo.Wrap a = geo.Wrap(21)\n"
            "graph.Wrap b = graph.Wrap(\"hi\")\n"
            "print(a.get())\n"
            "print(b.get())\n",
        )
        assert _run(tmp_path) == ["42", "HI"]

    def test_generic_inheritance_same_module_parent(self, tmp_path):
        """被 import 模块内泛型继承（Sub[T](Box[T])）特化父链对齐 qualified 键。"""
        _write(
            tmp_path,
            "geo.ibci",
            "class Box[T]:\n"
            "    int v\n"
            "    func base(self) -> str:\n"
            "        return \"geo-base\"\n"
            "class Sub[T](Box[T]):\n"
            "    func sub(self) -> str:\n"
            "        return \"geo-sub\"\n",
        )
        _write(
            tmp_path,
            "graph.ibci",
            "class Box[T]:\n"
            "    str name\n",
        )
        _write(
            tmp_path,
            "main.ibci",
            "import geo\n"
            "import graph\n"
            "geo.Sub[int] s = geo.Sub[int](7)\n"
            "print(s.base())\n"
            "print(s.sub())\n"
            "print(s.v)\n",
        )
        assert _run(tmp_path) == ["geo-base", "geo-sub", "7"]

    def test_builtin_generic_parent_no_module_prefix(self, tmp_path):
        """被 import 模块内继承内置泛型父（MyList[T](list[T])）：父名不加 module 前缀。

        父类权威解析：内置泛型父（module 恒 None）不应被补成 "geo.list[int]"
        （永不注册 → 继承链断裂）；同模块用户父才补全 module。声明路径物化
        特化类后其父链 = 内置 list[int]（裸名键）。
        """
        _write(
            tmp_path,
            "geo.ibci",
            "class MyList[T](list[T]):\n"
            "    func size(self) -> int:\n"
            "        return len(self)\n",
        )
        _write(
            tmp_path,
            "main.ibci",
            "import geo\n"
            "geo.MyList[int] a = geo.MyList[int]([1,2])\n"
            "print(a.size())\n",
        )
        engine = IBCIEngine(root_dir=str(tmp_path))
        try:
            engine.run(str(tmp_path / "main.ibci"), silent=True)
        except Exception:
            # 特化类水化须成功（继承链不因 module 前缀断裂）；实例化经既有
            # auto-init 边界报错（用户泛型继承内置容器无字段），不属本测试范围。
            pass
        # 模板父 = 内置 list（裸名，不加 module 前缀）
        tmpl = engine.registry.get_class("geo.MyList")
        assert tmpl is not None and tmpl.parent.qualified_name == "list", (
            f"模板 MyList 父应为内置 list，got {tmpl.parent.qualified_name}"
        )
        # 特化父 = 内置 list[int]（裸名键），非 "geo.list[int]"
        spec = engine.registry.get_class("geo.MyList[int]")
        assert spec is not None, "特化类应水化成功（继承链不因 module 前缀误配断裂）"
        assert spec.parent.qualified_name == "list[int]", (
            f"MyList[int] 父应为内置 list[int]，got {spec.parent.qualified_name}"
        )

    def test_same_name_class_cross_engine_roundtrip(self, tmp_path):
        """跨引擎 round-trip：geo.Box 实例 class_name qualified 保真。"""
        from core.runtime.serialization.runtime_serializer import (
            RuntimeSerializer,
            RuntimeDeserializer,
        )

        _write(
            tmp_path,
            "geo.ibci",
            "class Box[T]:\n"
            "    int v\n"
            "    func get(self) -> int:\n"
            "        return self.v + 100\n",
        )
        _write(
            tmp_path,
            "graph.ibci",
            "class Box[T]:\n"
            "    str name\n",
        )
        _write(
            tmp_path,
            "main.ibci",
            "import geo\n"
            "import graph\n"
            "geo.Box[int] a = geo.Box[int](5)\n"
            "graph.Box[int] b = graph.Box[int](\"hi\")\n",
        )
        engine_a = IBCIEngine(root_dir=str(tmp_path))
        engine_a.run(str(tmp_path / "main.ibci"), silent=True)
        ec = engine_a.interpreter.execution_context
        data = RuntimeSerializer(engine_a.registry).serialize_context(
            ec.runtime_context, include_static=True, execution_context=ec
        )

        engine_b = IBCIEngine(root_dir=str(tmp_path))
        engine_b.run(str(tmp_path / "main.ibci"), silent=True)
        deser = RuntimeDeserializer(engine_b.registry, factory=engine_b.object_factory)
        restored = deser.deserialize_context(data)
        a = restored.get_variable("a")
        b = restored.get_variable("b")
        # 值对象 ib_class = qualified 类（geo.Box[int] / graph.Box[int]），
        # 方法体语义各自正确（round-trip 后仍可区分）。
        assert a.ib_class.qualified_name == "geo.Box[int]", (
            f"round-trip class_name 应保真 qualified，got {a.ib_class.qualified_name}"
        )
        assert b.ib_class.qualified_name == "graph.Box[int]"

    def test_rehydrate_type_pool_spec_module_matching(self, tmp_path):
        """_rehydrate_type_pool_spec 按 (module_path, name) 联合匹配（修 #2）。

        跨引擎反序列化时 type_pool 含 geo.Box[int] 与 graph.Box[int]（同裸名
        特化名，异 module）；按裸名匹配会误选，联合匹配须各自命中正确 spec。
        注：未编译引擎的完整用户类重建受注册表封印限制（既有边界），本测试
        白盒验证匹配逻辑本身。
        """
        from core.runtime.serialization.runtime_serializer import (
            RuntimeSerializer,
            RuntimeDeserializer,
        )

        _write(
            tmp_path,
            "geo.ibci",
            "class Box[T]:\n"
            "    int v\n",
        )
        _write(
            tmp_path,
            "graph.ibci",
            "class Box[T]:\n"
            "    str name\n",
        )
        _write(
            tmp_path,
            "main.ibci",
            "import geo\n"
            "import graph\n"
            "geo.Box[int] a = geo.Box[int](5)\n"
            "graph.Box[int] b = graph.Box[int](\"hi\")\n",
        )
        engine_a = IBCIEngine(root_dir=str(tmp_path))
        engine_a.run(str(tmp_path / "main.ibci"), silent=True)
        ec = engine_a.interpreter.execution_context
        data = RuntimeSerializer(engine_a.registry).serialize_context(
            ec.runtime_context, include_static=True, execution_context=ec
        )

        engine_b = IBCIEngine(root_dir=str(tmp_path))
        engine_b.run(str(tmp_path / "main.ibci"), silent=True)
        deser = RuntimeDeserializer(engine_b.registry, factory=engine_b.object_factory)
        deser.deserialize_context(data)
        geo_spec = deser._rehydrate_type_pool_spec("geo.Box[int]")
        graph_spec = deser._rehydrate_type_pool_spec("graph.Box[int]")
        assert geo_spec is not None and graph_spec is not None
        assert geo_spec.module_path == "geo" and graph_spec.module_path == "graph"
        assert geo_spec is not graph_spec, (
            "同裸名特化名（Box[int]）异 module 应联合匹配各自 spec，不误选"
        )

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

    def test_imported_module_class_in_thread_worker(self, tmp_path):
        """KI-1 回归：线程 worker 内被 import 模块用户类方法调用成功。

        修复前 task_ec 的 get_side_table 回调读主 interpreter 共享
        current_module_name（忽略任务本地模块切换），imported 方法体在 worker
        内侧表查空报 Symbol UID missing（T05 KERNEL_ISSUE-CROSSMOD-THREAD-1）。
        修复后侧表查询以调用方 EC 的 current_module_name 为准。
        """
        _write(
            tmp_path,
            "geo.ibci",
            "class Box:\n"
            "    int v\n"
            "    func get(self) -> int:\n"
            "        return self.v + 400\n",
        )
        _write(
            tmp_path,
            "main.ibci",
            "import geo\n"
            "func compute() -> int:\n"
            "    return geo.Box(5).get()\n"
            "print(compute())\n"
            "thread[int] t = thread(callable=compute, args=[])\n"
            "print(t.join().expect())\n",
        )
        # 主上下文 405 且线程 worker 内 405（此前线程内抛 ThreadFailed）
        assert _run(tmp_path) == ["405", "405"]

    def test_entry_module_class_in_thread_worker(self, tmp_path):
        """KI-1 回归：入口模块类在线程 worker 内不回归（此前已幸存）。"""
        _write(
            tmp_path,
            "main.ibci",
            "class Box:\n"
            "    int v\n"
            "    func get(self) -> int:\n"
            "        return self.v + 100\n"
            "func compute() -> int:\n"
            "    return Box(5).get()\n"
            "print(compute())\n"
            "thread[int] t = thread(callable=compute, args=[])\n"
            "print(t.join().expect())\n",
        )
        assert _run(tmp_path) == ["105", "105"]

    def test_cross_module_behavior_llm_output_node_to_type(self, tmp_path):
        """CROSSMOD-LLM-1 回归：跨模块用户类作行为表达式目标时，行为节点
        node_to_type 绑定到 module 限定的 spec（而非退化 any/behavior）。

        修复前 ``geo.Counter c = @~...~`` 的 annotation 为 IbAttribute 点号限定，
        ``_resolve_type`` 未解析 → node_to_type 退化 → 运行时 LLM parse 链
        type_hint='behavior' → ``__call__ on None``。
        """
        from core.kernel import ast

        _write(
            tmp_path,
            "geo.ibci",
            "class Counter:\n"
            "    int n\n"
            "    func __from_prompt__(str raw) -> tuple:\n"
            "        return (True, Counter(10))\n"
            "    func value(self) -> int:\n"
            "        return self.n\n",
        )
        _write(
            tmp_path,
            "main.ibci",
            "import geo\n"
            "geo.Counter c = @~ 给一个数字 ~\n"
            "print(c)\n",
        )
        engine = IBCIEngine(root_dir=str(tmp_path))
        artifact = engine.compile(str(tmp_path / "main.ibci"))
        main_mod = artifact.modules.get("main")
        assert main_mod is not None
        behavior_nodes = [
            n for n in main_mod.node_to_type
            if isinstance(n, (ast.IbBehaviorExpr, ast.IbBehaviorInstance))
        ]
        assert behavior_nodes, "main 模块应有行为表达式节点"
        for node in behavior_nodes:
            spec = main_mod.node_to_type[node]
            assert spec is not None
            assert spec.name == "Counter", f"行为节点应绑定 geo.Counter，got {spec.name}"
            assert spec.module_path == "geo", (
                f"行为节点 spec 应携带 module（geo），got {spec.module_path}"
            )

    def test_cross_module_behavior_llm_output_generic_annotation(self, tmp_path):
        """CROSSMOD-LLM-1 泛型形态：模块限定泛型注解 geo.Box[int] 正常解析（不退化 any）。"""
        from core.kernel import ast

        _write(
            tmp_path,
            "geo.ibci",
            "class Box[T]:\n"
            "    int v\n"
            "    func get(self) -> int:\n"
            "        return self.v + 100\n",
        )
        _write(
            tmp_path,
            "main.ibci",
            "import geo\n"
            "geo.Box[int] b = geo.Box[int](5)\n"
            "print(b.get())\n",
        )
        assert _run(tmp_path) == ["105"]

    def test_cross_module_behavior_llm_output_unparseable_fails_fast(self, tmp_path):
        """跨模块用户类无 __from_prompt__ 时编译期 SEM_BEHAVIOR_OUTPUT_NOT_PARSEABLE
        （fail-fast，而非静默退化到运行时崩溃）。"""
        _write(
            tmp_path,
            "geo.ibci",
            "class Point:\n"
            "    int x\n"
            "    func hint(self) -> str:\n"
            "        return \"geo-hint\"\n",
        )
        _write(
            tmp_path,
            "main.ibci",
            "import geo\n"
            "geo.Point p = @~ 给我一个点 ~\n",
        )
        engine = IBCIEngine(root_dir=str(tmp_path))
        try:
            engine.compile(str(tmp_path / "main.ibci"))
        except Exception as exc:
            codes = []
            for diag in getattr(exc, "diagnostics", []):
                codes.append(getattr(diag, "code", ""))
            assert "SEM_BEHAVIOR_OUTPUT_NOT_PARSEABLE" in codes, codes
            return
        raise AssertionError("无 __from_prompt__ 的跨模块类应被编译期拦截")
