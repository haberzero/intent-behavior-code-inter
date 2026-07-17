"""
tests/e2e/test_e2e_plugin_discovery.py
======================================

ADR-019 §3 plugin 发现优先级的端到端验证：
- ibci.json 中 ``plugin_paths`` 配置的路径能实际被 ``import`` 解析；
- ``global_plugin`` 路径同样能实际被 ``import`` 解析；
- 显式 ``plugin_paths`` 配置会抑制嗅探兜底。

所有插件包均在 ``tmp_path`` 下动态生成，不往仓库提交 fixture。
"""
import json
import os
import pytest

from core.engine import IBCIEngine
from core.kernel.issue import CompilerError


def _ibci_path(path: str) -> str:
    """将原生路径转换为可安全嵌入 IBCI 字符串字面量的正斜杠形式。"""
    return path.replace("\\", "/")


def _write_minimal_plugin(dest_dir: str, module_name: str, funcs: dict) -> None:
    """在 dest_dir 下生成一个最小 IBCI method_module 插件包。

    参数:
        dest_dir: 插件包所在目录（如 ``.../ext_plugin/greet``），
                  其**父目录**应作为 ``plugin_paths``/``global_plugin`` 的搜索路径。
        module_name: 模块逻辑名（用于 ``import <name>``）。
        funcs: 函数签名映射，例如 {"hello": ([], "str")} 表示无参返回 str。
    """
    os.makedirs(dest_dir, exist_ok=True)

    vtable_funcs = {}
    method_defs = []
    for fn_name, (param_types, return_type) in funcs.items():
        vtable_funcs[fn_name] = {
            "param_types": param_types,
            "return_type": return_type,
            "description": f"auto-generated {fn_name}",
        }
        # 生成 Python 方法实现
        method_defs.append(
            f"    def {fn_name}(self{'' if not param_types else ', arg'}):\n"
            f'        return "hello"\n'
        )

    # _spec.py
    spec_path = os.path.join(dest_dir, "_spec.py")
    with open(spec_path, "w", encoding="utf-8") as f:
        f.write(
            "def __ibcext_metadata__():\n"
            f'    return {{"name": "{module_name}", "kind": "method_module", "version": "1.0.0"}}\n\n'
            "def __ibcext_vtable__():\n"
            f"    return {{\"functions\": {json.dumps(vtable_funcs, ensure_ascii=False)}}}\n"
        )

    # core.py
    core_path = os.path.join(dest_dir, "core.py")
    with open(core_path, "w", encoding="utf-8") as f:
        f.write(
            "class PluginCore:\n"
            + "".join(method_defs)
            + "\ndef create_implementation():\n"
            "    return PluginCore()\n"
        )

    # __init__.py
    init_path = os.path.join(dest_dir, "__init__.py")
    with open(init_path, "w", encoding="utf-8") as f:
        f.write("from .core import create_implementation\n")


def _run_ibci_file(entry_file: str, root_dir: str):
    """执行 .ibci 文件并返回 print 输出列表。"""
    out = []
    eng = IBCIEngine(root_dir=root_dir, auto_sniff=False)
    eng.run(entry_file, output_callback=lambda s: out.append(str(s)), silent=True)
    return out


class TestPluginPathsE2E:
    """ibci.json ``plugin_paths`` 能实际加载外部插件。"""

    def test_plugin_paths_e2e_import_resolves(self, tmp_path):
        ext_search = tmp_path / "ext_plugin"
        ext_plugin = ext_search / "greet"
        _write_minimal_plugin(str(ext_plugin), "greet", {"hello": ([], "str")})

        project = tmp_path / "project"
        project.mkdir()
        (project / "ibci.json").write_text(
            json.dumps({"plugin_paths": [_ibci_path(str(ext_search))]}),
            encoding="utf-8",
        )
        main_ibci = project / "main.ibci"
        main_ibci.write_text(
            "import greet\n"
            "print(greet.hello())\n",
            encoding="utf-8",
        )

        out = _run_ibci_file(str(main_ibci), str(project))
        assert any("hello" in line for line in out)

    def test_global_plugin_e2e_import_resolves(self, tmp_path):
        ext_search = tmp_path / "ext_plugin"
        ext_plugin = ext_search / "greet"
        _write_minimal_plugin(str(ext_plugin), "greet", {"hello": ([], "str")})

        project = tmp_path / "project"
        project.mkdir()
        (project / "ibci.json").write_text(
            json.dumps({"global_plugin": [_ibci_path(str(ext_search))]}),
            encoding="utf-8",
        )
        main_ibci = project / "main.ibci"
        main_ibci.write_text(
            "import greet\n"
            "print(greet.hello())\n",
            encoding="utf-8",
        )

        out = _run_ibci_file(str(main_ibci), str(project))
        assert any("hello" in line for line in out)

    def test_explicit_plugin_paths_disables_sniff_e2e(self, tmp_path):
        """配置了 plugin_paths 后，plugins/ 目录不再被嗅探。"""
        ext_search = tmp_path / "ext_plugin"
        ext_plugin = ext_search / "greet"
        _write_minimal_plugin(str(ext_plugin), "greet", {"hello": ([], "str")})

        project = tmp_path / "project"
        sniff_plugin = project / "plugins" / "sniff_only"
        _write_minimal_plugin(str(sniff_plugin), "sniff_only", {"hello": ([], "str")})

        (project / "ibci.json").write_text(
            json.dumps({"plugin_paths": [_ibci_path(str(ext_search))]}),
            encoding="utf-8",
        )
        main_ibci = project / "main.ibci"
        main_ibci.write_text(
            "import sniff_only\n"
            "print(sniff_only.hello())\n",
            encoding="utf-8",
        )

        with pytest.raises(CompilerError) as exc_info:
            _run_ibci_file(str(main_ibci), str(project))
        # 编译期即无法解析 sniff_only 模块
        diagnostics = "\n".join(str(d) for d in exc_info.value.diagnostics)
        assert "sniff_only" in diagnostics
