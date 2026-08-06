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
