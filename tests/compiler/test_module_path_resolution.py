"""
tests/compiler/test_module_path_resolution.py

C3 用户模块路径解析契约测试（绝对导入两级搜索 + 模块名语义）：

- 绝对导入搜索序：① 导入方文件所在目录（同目录模块——多文件用例的入口
  目录模块可解析，无需 harness 以用例目录为 root）→ ② 项目根（项目级
  模块兜底，既有语义）；
- 模块 artifact 键 = 用户 import 名（运行期 import_module 查询名一致）；
  入口模块按路径派生/显式锚点名（既有语义）；
- 相对导入（``.``/``..`` 前缀）锚定导入方文件目录（既有语义不变）；
- 合成入口载体（tempfile 位于系统临时目录）场景：① 级越界候选跳过
  （沙箱外不报错），回落 ② 级（项目根）。
"""

import pathlib
import tempfile

import pytest

from core.engine import IBCIEngine


@pytest.fixture
def tmp_project():
    with tempfile.TemporaryDirectory() as tmp:
        yield pathlib.Path(tmp)


class TestSameDirectoryModules:
    """绝对导入 ① 级：导入方目录同目录模块可解析（C3 新语义）。"""

    def test_subdir_same_dir_module_with_project_root(self, tmp_project):
        # 多文件用例目录（cases/d02/）置于项目内——入口目录同目录模块
        # 经项目 root 解析（此前须 harness 以用例目录为 root）
        (tmp_project / "cases" / "d02").mkdir(parents=True)
        (tmp_project / "cases" / "d02" / "geo.ibci").write_text(
            "class Box[T]:\n"
            "    T value\n"
            "    func __init__(self, T v) -> auto:\n"
            "        self.value = v\n",
            encoding="utf-8",
        )
        (tmp_project / "cases" / "d02" / "main.ibci").write_text(
            "import geo\n"
            "geo.Box[int] g = geo.Box[int](1)\n"
            "print(\"same-dir-ok\")\n",
            encoding="utf-8",
        )
        eng = IBCIEngine(root_dir=str(tmp_project))
        out = []
        eng.run(str(tmp_project / "cases" / "d02" / "main.ibci"),
                output_callback=out.append, silent=True)
        assert out and "same-dir-ok" in out[0]

    def test_root_level_module_fallback(self, tmp_project):
        # ② 级兜底：项目根模块（既有语义回归）
        (tmp_project / "topmod.ibci").write_text(
            "func hi() -> str:\n    return \"top-hi\"\n", encoding="utf-8")
        (tmp_project / "main.ibci").write_text(
            "import topmod\n"
            "str s = topmod.hi()\n"
            "print(s)\n",
            encoding="utf-8",
        )
        eng = IBCIEngine(root_dir=str(tmp_project))
        out = []
        eng.run(str(tmp_project / "main.ibci"),
                output_callback=out.append, silent=True)
        assert out and "top-hi" in out[0]


class TestNestedImportNames:
    """嵌套导入（多级包路径用户名）模块名一致性（既有语义回归）。"""

    def test_three_segment_package_import(self, tmp_project):
        (tmp_project / "pkg" / "sub").mkdir(parents=True)
        (tmp_project / "pkg" / "__init__.ibci").write_text("", encoding="utf-8")
        (tmp_project / "pkg" / "sub" / "__init__.ibci").write_text("", encoding="utf-8")
        (tmp_project / "pkg" / "sub" / "mod.ibci").write_text(
            "func hi() -> str:\n    return \"mod-hi\"\n", encoding="utf-8")
        (tmp_project / "main.ibci").write_text(
            "import pkg.sub.mod\n"
            "str s = pkg.sub.mod.hi()\n"
            "print(s)\n",
            encoding="utf-8",
        )
        eng = IBCIEngine(root_dir=str(tmp_project))
        out = []
        eng.run(str(tmp_project / "main.ibci"),
                output_callback=out.append, silent=True)
        assert out and "mod-hi" in out[0]


class TestSyntheticEntryCarriers:
    """合成入口载体（tempfile 系统临时目录）场景：① 级越界跳过。"""

    def test_run_string_import_root_module(self, tmp_project):
        # run_string 入口 = tempfile 载体（位于系统临时目录，沙箱外）——
        # ① 级（导入方目录）越界候选跳过，② 级（项目根）命中
        (tmp_project / "geo.ibci").write_text(
            "class Box[T]:\n"
            "    T value\n"
            "    func __init__(self, T v) -> auto:\n"
            "        self.value = v\n",
            encoding="utf-8",
        )
        eng = IBCIEngine(root_dir=str(tmp_project))
        out = []
        eng.run_string(
            "import geo\n"
            "geo.Box[int] g = geo.Box[int](1)\n"
            "print(\"carrier-ok\")\n",
            output_callback=out.append, silent=True)
        assert out and "carrier-ok" in out[0]


class TestModuleNameArtifactKey:
    """模块 artifact 键 = 用户 import 名（跨模块特化键 module 限定）。"""

    def test_cross_module_specialization_keys_independent(self, tmp_project):
        # geo.Box[int] 与入口模块 Box[int] 特化键独立（module 限定——
        # 同目录模块 artifact 键 = 用户 import 名 "geo"）
        (tmp_project / "geo.ibci").write_text(
            "class Box[T]:\n"
            "    T value\n"
            "    func __init__(self, T v) -> auto:\n"
            "        self.value = v\n",
            encoding="utf-8",
        )
        eng = IBCIEngine(root_dir=str(tmp_project))
        out = []
        eng.run_string(
            "import geo\n"
            "class Box[T]:\n"
            "    T value\n"
            "    func __init__(self, T v) -> auto:\n"
            "        self.value = v\n"
            "geo.Box[int] g = geo.Box[int](1)\n"
            "Box[int] m = Box[int](2)\n"
            "print(\"spec-ok\")\n",
            output_callback=out.append, silent=True)
        assert out and "spec-ok" in out[0]
        # 两特化类独立（module 限定键）
        g = eng.interpreter.runtime_context.get_variable("g")
        m = eng.interpreter.runtime_context.get_variable("m")
        assert g.ib_class is not m.ib_class, "跨模块同名特化类应独立"
