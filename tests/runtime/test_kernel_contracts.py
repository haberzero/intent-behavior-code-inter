"""
tests/runtime/test_kernel_contracts.py — 内核契约自举（工具契约 bind 表达）契约。

**契约**：
- 工具 4（math/json/time/schema）spec 由契约源合成入元数据注册表：
  provenance=EXTERNAL_MODULE / visibility=IMPORT_GATED / 成员面与契约源一致。
- 契约源 = 声明域文件：非声明语句 / 重复绑定 / 实现成员缺失 = 构造期 fail-fast
  （InterpreterError，引擎不得带缺陷契约启动）。
- per-engine 隔离：同进程多引擎各自独立实现对象（registry 隔离守卫不触发）。
- 用户面不变：import math/json/time/schema 行为与契约源化前一致（既有 e2e
  test_modules 全量锁定）；用户模块不覆盖内置工具（InterOp 优先路径不变）。
"""
from __future__ import annotations

import contextlib
import io

import pytest

from core.engine import IBCIEngine
from core.base.enums import Provenance, Visibility
from core.kernel.host_interface import HostInterface
from core.kernel.issue import InterpreterError
from core.kernel.registry import KernelRegistry
from core.kernel.spec.base import TypeKind
from core.runtime.bootstrap.kernel_contracts import load_tool_contracts

# 契约源声明的成员面（独立期望——契约锁定，漂移即测试失败）
_EXPECTED_TOOL_MEMBERS = {
    "math": 27,
    "json": 10,
    "time": 14,
    "schema": 5,
}
_MATH_MEMBER_NAMES = {
    "sqrt", "pow", "abs", "floor", "ceil", "round", "clamp", "min", "max",
    "exp", "log", "log2", "log10",
    "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
    "degrees", "radians", "random", "randint",
    "pi", "e", "inf",
}


def _fresh_host_interface() -> HostInterface:
    return HostInterface(external_registry=KernelRegistry().get_metadata_registry())


class TestToolSpecsFromContractSources:
    def test_tool_specs_registered(self, tmp_path):
        """引擎构造：工具 4 spec 经契约源合成入元数据注册表（形态 + 成员面）。"""
        e = IBCIEngine(root_dir=str(tmp_path))
        reg = e.registry.get_metadata_registry()
        for name, count in _EXPECTED_TOOL_MEMBERS.items():
            spec = reg.resolve(name)
            assert spec is not None, f"{name}: spec missing"
            assert spec.kind == TypeKind.MODULE.value
            assert spec.provenance == Provenance.EXTERNAL_MODULE
            assert spec.visibility == Visibility.IMPORT_GATED
            assert len(spec.members) == count, f"{name}: member count {len(spec.members)} != {count}"
        assert set(reg.resolve("math").members) == _MATH_MEMBER_NAMES

    def test_kernel_and_net_specs_unchanged(self, tmp_path):
        """内核原生 + net 维持宿主侧字面量（provenance 不变）。"""
        e = IBCIEngine(root_dir=str(tmp_path))
        reg = e.registry.get_metadata_registry()
        for name in ["ai", "ihost", "meta", "idbg", "isys", "iruntime", "fs"]:
            spec = reg.resolve(name)
            assert spec is not None
            assert spec.provenance == Provenance.KERNEL_NATIVE, name
        assert reg.resolve("net").provenance == Provenance.USER_DEFINED

    def test_user_surface_math(self, tmp_path):
        """用户面：import math 成员调用正确（契约源化前后行为一致）。"""
        e = IBCIEngine(root_dir=str(tmp_path))
        code = (
            "import math\n"
            "float r = math.sqrt(16.0)\n"
            "float p = math.pi\n"
            "int f = math.floor(2.9)\n"
            "print((str)r)\n"
            "print((str)f)\n"
        )
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            e.run_string(code, silent=True)
        assert buf.getvalue().split() == ["4.0", "2"]


class TestContractFailFast:
    def test_missing_member_fails_at_construction(self, tmp_path):
        """实现缺失契约声明成员 → 构造期 fail-fast（契约/实现漂移 = 内核缺陷）。"""
        contracts = tmp_path / "contracts"
        contracts.mkdir()
        (contracts / "math.ibci").write_text(
            'import python "ibci_modules.ibci_math" as math:\n'
            "    bind missing_fn(x: int) -> int\n",
            encoding="utf-8",
        )
        with pytest.raises(InterpreterError, match="missing_fn"):
            load_tool_contracts(_fresh_host_interface(), contracts_dir=str(contracts))

    def test_duplicate_binding_fails_at_construction(self, tmp_path):
        """契约源重复绑定同名成员 → 构造期 fail-fast。"""
        contracts = tmp_path / "contracts"
        contracts.mkdir()
        (contracts / "math.ibci").write_text(
            'import python "ibci_modules.ibci_math" as math:\n'
            "    bind sqrt(x: float) -> float\n"
            "    bind sqrt(x: int) -> float\n",
            encoding="utf-8",
        )
        with pytest.raises(InterpreterError, match="duplicate"):
            load_tool_contracts(_fresh_host_interface(), contracts_dir=str(contracts))

    def test_non_declaration_body_fails_at_construction(self, tmp_path):
        """契约源含非声明语句 → 构造期 fail-fast（契约源 = 声明域文件）。"""
        contracts = tmp_path / "contracts"
        contracts.mkdir()
        (contracts / "math.ibci").write_text(
            "int x = 5\n",
            encoding="utf-8",
        )
        with pytest.raises(InterpreterError, match="host-binding import"):
            load_tool_contracts(_fresh_host_interface(), contracts_dir=str(contracts))


class TestPerEngineIsolation:
    def test_two_engines_independent_implementations(self, tmp_path):
        """同进程两引擎：per-engine 实现对象独立（registry 隔离守卫不触发）。"""
        e1 = IBCIEngine(root_dir=str(tmp_path / "a"))
        e2 = IBCIEngine(root_dir=str(tmp_path / "b"))
        impl1 = e1.host_interface.get_module_implementation("math")
        impl2 = e2.host_interface.get_module_implementation("math")
        assert impl1 is not None and impl2 is not None
        assert impl1 is not impl2, "tool implementation must be per-engine"
        # 双引擎用户面皆可用
        for e in (e1, e2):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                e.run_string("import math\nfloat r = math.sqrt(9.0)\nprint((str)r)\n", silent=True)
            assert buf.getvalue().split() == ["3.0"]


class TestShadowingEquivalence:
    def test_user_module_does_not_override_builtin_tool(self, tmp_path):
        """用户模块名与内置工具同名：InterOp 优先路径不变（用户面仍 = 内置实现）。"""
        (tmp_path / "math.ibci").write_text(
            "int shadow_sqrt = 99\n",
            encoding="utf-8",
        )
        e = IBCIEngine(root_dir=str(tmp_path))
        code = "import math\nfloat r = math.sqrt(16.0)\nprint((str)r)\n"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            e.run_string(code, silent=True)
        assert buf.getvalue().split() == ["4.0"], "builtin tool must take precedence"
