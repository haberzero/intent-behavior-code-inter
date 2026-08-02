# -*- coding: utf-8 -*-
"""
tests/kernel/test_kernel_native_modules.py
==========================================

ai/ihost/idbg/isys 内核原生化验证。
"""
import json
import os
import pytest

from core.engine import IBCIEngine
from core.base.enums import Provenance, Visibility
from core.kernel.host_interface import HostInterface
from core.runtime.bootstrap.kernel_native_modules import (
    KERNEL_NATIVE_MODULES,
    register_kernel_native_modules,
)
from tests.conftest import REPO_ROOT


class TestKernelNativeRegistration:
    """构造期预注册与元数据标记。"""

    def test_modules_pre_registered_at_init(self):
        """Engine 构造后，四个 kernel-native 模块已实现+元数据就绪。"""
        eng = IBCIEngine(root_dir=REPO_ROOT, auto_sniff=False)
        for name in KERNEL_NATIVE_MODULES:
            impl = eng.host_interface.get_module_implementation(name)
            assert impl is not None, f"{name} should be pre-registered"

            spec = eng.host_interface.metadata.resolve(name)
            assert spec is not None, f"{name} spec should be registered"
            assert spec.provenance == Provenance.KERNEL_NATIVE
            assert spec.visibility == Visibility.IMPORT_GATED

    def test_is_kernel_native_query(self):
        """`is_kernel_native` 正确识别 kernel-native 模块。"""
        eng = IBCIEngine(root_dir=REPO_ROOT, auto_sniff=False)
        for name in KERNEL_NATIVE_MODULES:
            assert eng.host_interface.is_kernel_native(name)
        assert not eng.host_interface.is_kernel_native("math")
        assert not eng.host_interface.is_kernel_native("time")

    def test_register_kernel_native_modules_idempotent(self):
        """`register_kernel_native_modules` 可重复调用不报错。"""
        host = HostInterface()
        register_kernel_native_modules(host)
        register_kernel_native_modules(host)
        for name in KERNEL_NATIVE_MODULES:
            assert host.is_kernel_native(name)


class TestKernelNativeOverrideProtection:
    """用户插件不可覆盖 kernel-native 模块。"""

    @staticmethod
    def _write_fake_isys_plugin(dest_dir: str) -> None:
        os.makedirs(dest_dir, exist_ok=True)
        spec_path = os.path.join(dest_dir, "_spec.py")
        with open(spec_path, "w", encoding="utf-8") as f:
            f.write(
                "def __ibcext_metadata__():\n"
                '    return {"name": "isys", "kind": "method_module", "version": "1.0.0"}\n\n'
                "def __ibcext_vtable__():\n"
                '    return {"functions": {"entry_path": {"param_types": [], "return_type": "str"}}}\n'
            )
        core_path = os.path.join(dest_dir, "core.py")
        with open(core_path, "w", encoding="utf-8") as f:
            f.write(
                "class FakeISys:\n"
                '    def entry_path(self):\n'
                '        return "/fake_override"\n\n'
                "def create_implementation():\n"
                "    return FakeISys()\n"
            )
        init_path = os.path.join(dest_dir, "__init__.py")
        with open(init_path, "w", encoding="utf-8") as f:
            f.write("from .core import create_implementation\n")

    def test_user_plugin_cannot_override_kernel_native(self, tmp_path):
        """逻辑名同为 isys 的用户插件不应覆盖 kernel-native 实现。"""
        fake_dir = tmp_path / "fake_isys"
        self._write_fake_isys_plugin(str(fake_dir))

        (tmp_path / "ibci.json").write_text(
            json.dumps({"plugin_paths": [str(fake_dir)]}),
            encoding="utf-8",
        )
        (tmp_path / "main.ibci").write_text(
            "import isys\n"
            "print(isys.entry_path())\n",
            encoding="utf-8",
        )

        out = []
        eng = IBCIEngine(root_dir=str(tmp_path), auto_sniff=False)
        eng.run(str(tmp_path / "main.ibci"), output_callback=lambda s: out.append(str(s)), silent=True)

        # kernel-native isys.entry_path() 返回真实入口路径，不应被 /fake_override 覆盖
        assert not any("/fake_override" in line for line in out), (
            f"kernel-native isys was overridden: {out}"
        )


class TestKernelNativeImportGating:
    """kernel-native 模块仍须显式 import。"""

    def test_ai_remains_import_gated(self):
        """未 import ai 而直接使用 ai.set_config 应编译/运行失败。"""
        with pytest.raises(Exception) as exc_info:
            IBCIEngine(root_dir=REPO_ROOT, auto_sniff=False).run_string(
                'ai.set_config("X", "Y", "Z")\n',
                silent=True,
            )
        err = exc_info.value
        codes = {d.code for d in getattr(err, "diagnostics", [])}
        assert "SEM_UNDEFINED_SYMBOL" in codes or "DEP_MODULE_NOT_FOUND" in codes, (
            f"expected SEM_UNDEFINED_SYMBOL/DEP_MODULE_NOT_FOUND, got codes={codes}, msg={err}"
        )


class TestImportStarContract:
    """``from package import *`` 的 uid 对齐与成员契约（组 2 修复验证）。"""

    def test_import_star_binds_with_uid(self):
        """import * 注入的成员带编译器 uid，使用点可解析（修复 RUN_UNDEFINED_VARIABLE）。"""
        eng = IBCIEngine(root_dir=REPO_ROOT, auto_sniff=False)
        out = []
        eng.run_string(
            'from idbg import *\ndict d = vars()\nprint((str)d)\n',
            output_callback=lambda s: out.append(str(s)),
            silent=True,
        )
        assert out, "expected vars() callable via import * (uid 未对齐会 RUN_UNDEFINED_VARIABLE)"
        assert "current_llm" in out[0] and "show_env" in out[0], out[0]

    def test_import_star_does_not_leak_protocol_methods(self):
        """import * 只导出 spec 成员，不泄漏 setup/expose/plugin_id 等协议方法。"""
        eng = IBCIEngine(root_dir=REPO_ROOT, auto_sniff=False)
        eng.run_string('from idbg import *\n', silent=True)
        rt = eng.interpreter.runtime_context
        sym_names = set(rt.get_vars().keys())
        for leaked in ("setup", "expose", "revoke", "plugin_id", "get_vtable", "save_plugin_state"):
            assert leaked not in sym_names, f"protocol method leaked via import *: {leaked}"

    def test_import_star_spec_members_present(self):
        """spec 声明的成员经 import * 全部注入。"""
        eng = IBCIEngine(root_dir=REPO_ROOT, auto_sniff=False)
        eng.run_string('from idbg import *\n', silent=True)
        rt = eng.interpreter.runtime_context
        sym_names = set(rt.get_vars().keys())
        for member in ("vars", "env", "show_env", "current_llm", "print_vars"):
            assert member in sym_names, f"spec member missing via import *: {member}"



