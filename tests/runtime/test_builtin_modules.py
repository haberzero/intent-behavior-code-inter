# -*- coding: utf-8 -*-
"""
tests/runtime/test_builtin_modules.py
======================================

内置模块（内核原生 5 + 工具 5 + file）构造期预注册验证。
内核原生 5：ai/ihost/idbg/isys/iruntime（kernel-native）。
工具 5：math/json/time/net/schema（内联 spec 构造期预注册，USER_DEFINED）。
"""
import os
import pytest

from core.engine import IBCIEngine
from core.base.enums import Provenance, Visibility
from core.kernel.host_interface import HostInterface
from core.kernel.spec import MethodMemberSpec, TypeRef, TypeDef, TypeKind
from core.runtime.bootstrap.builtin_modules import (
    KERNEL_NATIVE_MODULES,
    BUILTIN_MODULES,
    register_builtin_modules,
)
from tests.conftest import REPO_ROOT


class TestBuiltinRegistration:
    """构造期预注册与元数据标记。"""

    def test_modules_pre_registered_at_init(self):
        """Engine 构造后，内核原生 5 模块已实现+元数据就绪。"""
        eng = IBCIEngine(root_dir=REPO_ROOT)
        for name in KERNEL_NATIVE_MODULES:
            impl = eng.host_interface.get_module_implementation(name)
            assert impl is not None, f"{name} should be pre-registered"

            spec = eng.host_interface.metadata.resolve(name)
            assert spec is not None, f"{name} spec should be registered"
            assert spec.provenance == Provenance.KERNEL_NATIVE
            assert spec.visibility == Visibility.IMPORT_GATED

    def test_tool_modules_pre_registered_at_init(self):
        """工具 5 模块构造期预注册（USER_DEFINED + IMPORT_GATED + 实现就绪）。"""
        eng = IBCIEngine(root_dir=REPO_ROOT)
        for name in ("math", "json", "time", "net", "schema"):
            impl = eng.host_interface.get_module_implementation(name)
            assert impl is not None, f"{name} should be pre-registered"

            spec = eng.host_interface.metadata.resolve(name)
            assert spec is not None, f"{name} spec should be registered"
            assert spec.provenance == Provenance.USER_DEFINED
            assert spec.visibility == Visibility.IMPORT_GATED

    def test_file_pre_registered_kernel_native(self):
        """file 模块自 engine.py 挪入集中注册（fs 模块，KERNEL_NATIVE + exported_types 保留）。"""
        eng = IBCIEngine(root_dir=REPO_ROOT)
        impl = eng.host_interface.get_module_implementation("fs")
        assert impl is not None
        assert eng.host_interface.is_kernel_native("fs")
        spec = eng.host_interface.metadata.resolve("fs")
        assert spec.provenance == Provenance.KERNEL_NATIVE
        assert spec.visibility == Visibility.IMPORT_GATED
        assert spec.exported_types == ["file_handle", "audio", "image", "video"]

    def test_is_kernel_native_query(self):
        """`is_kernel_native` 正确识别 kernel-native 模块。"""
        eng = IBCIEngine(root_dir=REPO_ROOT)
        for name in KERNEL_NATIVE_MODULES:
            assert eng.host_interface.is_kernel_native(name)
        assert not eng.host_interface.is_kernel_native("math")
        assert not eng.host_interface.is_kernel_native("time")

    def test_register_builtin_modules_idempotent(self):
        """`register_builtin_modules` 可重复调用不报错。"""
        host = HostInterface()
        register_builtin_modules(host)
        register_builtin_modules(host)
        for name in KERNEL_NATIVE_MODULES:
            assert host.is_kernel_native(name)

    def test_builtin_spec_contract_details(self):
        """结构等价关键点（生成探针一次性验证，此处固化为契约测试防回归）。"""
        eng = IBCIEngine(root_dir=REPO_ROOT)

        # ai.set_mock_mode：enable 具名默认 True
        ai = eng.host_interface.metadata.resolve("ai")
        d0 = ai.members["set_mock_mode"].param_descriptors[0]
        assert (d0.name, d0.kind, d0.has_default, d0.default_value) == (
            "enable", "POSITIONAL_OR_KEYWORD", True, True,
        )

        # iruntime.configure：VAR_KEYWORD 参数
        ir = eng.host_interface.metadata.resolve("iruntime")
        d1 = ir.members["configure"].param_descriptors[0]
        assert (d1.name, d1.kind) == ("kwargs", "VAR_KEYWORD")
        assert d1.type_ref == TypeRef.of("any")

        # json.__to_prompt__：functions 成员（method），须为 MethodMemberSpec
        json_mod = eng.host_interface.metadata.resolve("json")
        tp = json_mod.members["__to_prompt__"]
        assert isinstance(tp, MethodMemberSpec)

        # math 变量：field + float
        math_mod = eng.host_interface.metadata.resolve("math")
        for v in ("pi", "e", "inf"):
            member = math_mod.members[v]
            assert member.kind == "field"
            assert member.type_ref == TypeRef.of("float")

        # net.get：headers 具名默认 None
        net = eng.host_interface.metadata.resolve("net")
        h = net.members["get"].param_descriptors[1]
        assert (h.name, h.has_default, h.default_value) == ("headers", True, None)


class TestKernelNativeOverrideProtection:
    """KERNEL_NATIVE 模块名不可被覆盖（HostInterface 层守卫）。

    用户插件磁盘发现已删，覆盖保护全在 HostInterface.register_module
    对 KERNEL_NATIVE provenance 元数据的守卫（注册即 auto-reserve）；
    用户侧扩展走宿主绑定 bind，不会产生同名内核模块名。
    """

    def test_registering_plain_module_over_kernel_native_is_rejected(self):
        """在已注册 isys（KERNEL_NATIVE）的 host 上注册同名 USER_DEFINED 模块被忽略并警告。"""
        import warnings
        eng = IBCIEngine(root_dir=REPO_ROOT)
        fake_spec = TypeDef(
            name="isys", kind=TypeKind.MODULE.value,
            provenance=Provenance.USER_DEFINED, visibility=Visibility.IMPORT_GATED,
        )
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            eng.host_interface.register_module(
                "isys", object(), metadata=fake_spec, discovery_name="fake_isys"
            )
        assert any(
            "reserved for kernel-native module" in str(x.message) for x in w
        ), [str(x.message) for x in w]
        # 真实 isys 实现保持
        assert eng.host_interface.is_kernel_native("isys")


class TestKernelNativeImportGating:
    """kernel-native 模块仍须显式 import。"""

    def test_ai_remains_import_gated(self):
        """未 import ai 而直接使用 ai.set_config 应编译/运行失败。"""
        with pytest.raises(Exception) as exc_info:
            IBCIEngine(root_dir=REPO_ROOT).run_string(
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
        eng = IBCIEngine(root_dir=REPO_ROOT)
        out = []
        eng.run_string(
            'from idbg import *\ndict d = vars()\nprint((str)d)\n',
            output_callback=lambda s: out.append(str(s)),
            silent=True,
        )
        assert out, "expected vars() callable via import * (uid 未对齐会 RUN_UNDEFINED_VARIABLE)"
        assert "current_llm" in out[0] and "show_runtime" in out[0], out[0]

    def test_import_star_does_not_leak_protocol_methods(self):
        """import * 只导出 spec 成员，不泄漏 setup/expose/plugin_id 等协议方法。"""
        eng = IBCIEngine(root_dir=REPO_ROOT)
        eng.run_string('from idbg import *\n', silent=True)
        rt = eng.interpreter.runtime_context
        sym_names = set(rt.get_vars().keys())
        for leaked in ("setup", "expose", "revoke", "plugin_id", "get_vtable", "save_plugin_state"):
            assert leaked not in sym_names, f"protocol method leaked via import *: {leaked}"

    def test_import_star_spec_members_present(self):
        """spec 声明的成员经 import * 全部注入。"""
        eng = IBCIEngine(root_dir=REPO_ROOT)
        eng.run_string('from idbg import *\n', silent=True)
        rt = eng.interpreter.runtime_context
        sym_names = set(rt.get_vars().keys())
        for member in ("vars", "runtime", "show_runtime", "current_llm", "print_vars"):
            assert member in sym_names, f"spec member missing via import *: {member}"



