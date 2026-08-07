"""
tests_v2/e2e/test_isolation_plugin_inheritance.py
==================================================

隔离继承的端到端验证：
子脚本通过 ``ihost.run_isolated`` 执行时，能解析仅父项目拥有的插件
（经 ``inherited_plugin_paths`` 透传），而不是靠子项目自身嗅探。
"""
import json
import os
import pytest

from core.engine import IBCIEngine


def _ibci_path(path: str) -> str:
    """将原生路径转换为可安全嵌入 IBCI 字符串字面量的正斜杠形式。"""
    return path.replace("\\", "/")


def _write_minimal_plugin(dest_dir: str, module_name: str) -> None:
    """在 dest_dir 下生成一个最小 IBCI method_module 插件包。"""
    os.makedirs(dest_dir, exist_ok=True)

    spec_path = os.path.join(dest_dir, "_spec.py")
    with open(spec_path, "w", encoding="utf-8") as f:
        f.write(
            "def __ibcext_metadata__():\n"
            f'    return {{"name": "{module_name}", "kind": "method_module", "version": "1.0.0"}}\n\n'
            "def __ibcext_vtable__():\n"
            '    return {"functions": {"echo": {"param_types": ["str"], "return_type": "str", "description": "echo"}}}\n'
        )

    core_path = os.path.join(dest_dir, "core.py")
    with open(core_path, "w", encoding="utf-8") as f:
        f.write(
            "class PluginCore:\n"
            '    def echo(self, s):\n'
            '        return s\n\n'
            "def create_implementation():\n"
            "    return PluginCore()\n"
        )

    init_path = os.path.join(dest_dir, "__init__.py")
    with open(init_path, "w", encoding="utf-8") as f:
        f.write("from .core import create_implementation\n")


class TestIsolationPluginInheritance:
    """隔离子环境继承父 plugin search_paths。"""

    def test_child_inherits_parent_plugin_via_isolation(self, tmp_path, monkeypatch, capsys):
        parent_root = tmp_path / "parent_root"
        parent_root.mkdir()

        # 父项目独有的插件目录
        plugin_dir = parent_root / "parent_only_plugins" / "echo"
        _write_minimal_plugin(str(plugin_dir), "echo")

        # 子项目入口，位于父 project_root 内（隔离反转）
        child_root = parent_root / "child_root"
        child_root.mkdir()
        (child_root / "child.ibci").write_text(
            "import echo\n"
            'print(echo.echo("from_child"))\n',
            encoding="utf-8",
        )

        # 父项目配置显式 plugin_paths，关闭嗅探
        (parent_root / "ibci.json").write_text(
            json.dumps({"plugin_paths": ["parent_only_plugins"]}),
            encoding="utf-8",
        )
        parent_ibci = parent_root / "parent.ibci"
        parent_ibci.write_text(
            "import ihost\n"
            'dict policy = {"isolated": True, "registry_isolation": True, "inherit_variables": False}\n'
            f'dict res = ihost.run_isolated("{_ibci_path(str(child_root / "child.ibci"))}", policy)\n'
            'print("parent_done")\n',
            encoding="utf-8",
        )

        # cwd 切到无关目录，确保相对路径基于入口目录（契约）
        other_dir = tmp_path / "elsewhere"
        other_dir.mkdir()
        monkeypatch.chdir(other_dir)

        parent_out = []
        eng = IBCIEngine(root_dir=str(parent_root), auto_sniff=False)
        eng.run(str(parent_ibci), output_callback=lambda s: parent_out.append(str(s)), silent=True)

        captured = capsys.readouterr()
        assert "from_child" in captured.out, (
            f"child did not inherit parent plugin; captured stdout={captured.out!r}, "
            f"parent_out={parent_out!r}"
        )
        assert "parent_done" in parent_out

    def test_child_without_inheritance_fails(self, tmp_path, monkeypatch, capsys):
        """对照：父不配置 plugin_paths 时，子无法通过继承加载 echo。"""
        parent_root = tmp_path / "parent_root2"
        parent_root.mkdir()

        # 插件目录存在，但父 ibci.json 不引用它
        plugin_dir = parent_root / "parent_only_plugins" / "echo"
        _write_minimal_plugin(str(plugin_dir), "echo")

        child_root = parent_root / "child_root"
        child_root.mkdir()
        (child_root / "child.ibci").write_text(
            "import echo\n"
            'print(echo.echo("from_child"))\n',
            encoding="utf-8",
        )

        # 父项目无 plugin_paths，且关闭嗅探
        (parent_root / "ibci.json").write_text(
            json.dumps({}),
            encoding="utf-8",
        )
        parent_ibci = parent_root / "parent.ibci"
        parent_ibci.write_text(
            "import ihost\n"
            'dict policy = {"isolated": True, "registry_isolation": True, "inherit_variables": False}\n'
            f'dict res = ihost.run_isolated("{_ibci_path(str(child_root / "child.ibci"))}", policy)\n'
            'print("parent_done")\n',
            encoding="utf-8",
        )

        other_dir = tmp_path / "elsewhere2"
        other_dir.mkdir()
        monkeypatch.chdir(other_dir)

        with pytest.raises(Exception) as exc_info:
            eng = IBCIEngine(root_dir=str(parent_root), auto_sniff=False)
            eng.run(str(parent_ibci), output_callback=lambda s: None, silent=True)

        # 子编译/运行失败，且失败原因与无法解析 echo 模块相关
        msg = str(exc_info.value)
        assert "Compilation failed" in msg or "echo" in msg, msg
