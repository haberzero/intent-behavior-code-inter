"""
tests/runtime/test_host_binding.py
==================================

宿主绑定（F1）：``import python "pkg" as lib: bind ...``。

验证门（ROADMAP F1）：
1. e2e：``.ibci`` 绑定宿主 callable 并调用成功（方法 + 属性成员）。
2. 显式声明式绑定（非自动穿透）：未声明成员访问 fail-fast。
3. 绑定声明但宿主缺失成员 → 报错。
4. 编译期类型检查：bind 签名约束调用实参/返回类型。
5. 用户 IBCI 类 / ``any`` 字段持 native，方法内调用。
6. 全量 pytest 零回归（由测试套件整体保证）。
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


class TestHostBindingE2E:
    """e2e：绑定宿主 callable 并调用成功。"""

    def test_bind_method_and_attribute(self, tmp_path):
        _write(
            tmp_path,
            "main.ibci",
            """
import python "math" as m:
    bind sqrt(x: float) -> float
    bind pi -> float

func test() -> auto:
    float r = m.sqrt(16.0)
    print((str)r)
    print((str)m.pi)

test()
""",
        )
        assert _run(tmp_path) == ["4.0", "3.141592653589793"]

    def test_bind_multi_param(self, tmp_path):
        _write(
            tmp_path,
            "main.ibci",
            """
import python "math" as m:
    bind pow(x: float, y: float) -> float

func test() -> auto:
    float r = m.pow(2.0, 10.0)
    print((str)r)

test()
""",
        )
        assert _run(tmp_path) == ["1024.0"]

    def test_user_class_holds_native(self, tmp_path):
        """用户 IBCI 类 / any 字段持 IbNativeObject，方法内调用。"""
        _write(
            tmp_path,
            "main.ibci",
            """
import python "math" as m:
    bind sqrt(x: float) -> float

class Calculator:
    any backend

    func __init__(self, any b) -> auto:
        self.backend = b

    func sqrt(self, float x) -> float:
        return self.backend.sqrt(x)

func test() -> auto:
    Calculator c = Calculator(m)
    float r = c.sqrt(25.0)
    print((str)r)

test()
""",
        )
        assert _run(tmp_path) == ["5.0"]

    def test_host_import_without_asname(self, tmp_path):
        """无 asname 时绑定名 = 真实 Python 模块名（与 import json 无别名同构）。"""
        _write(
            tmp_path,
            "main.ibci",
            """
import python "math":
    bind sqrt(x: float) -> float

func test() -> auto:
    float r = math.sqrt(16.0)
    print((str)r)

test()
""",
        )
        assert _run(tmp_path) == ["4.0"]

    def test_cross_module_host_binding(self, tmp_path):
        """含宿主绑定的 .ibci 文件被其他文件导入（宿主 spec 序列化进 artifact）。"""
        _write(
            tmp_path,
            "helper.ibci",
            """
import python "math" as m:
    bind sqrt(x: float) -> float

func hsqrt(float x) -> float:
    return m.sqrt(x)
""",
        )
        _write(
            tmp_path,
            "main.ibci",
            """
from helper import hsqrt

func test() -> auto:
    float r = hsqrt(49.0)
    print((str)r)

test()
""",
        )
        assert _run(tmp_path) == ["7.0"]


class TestHostBindingExplicitOnly:
    """显式声明式绑定（非自动穿透）。"""

    def test_unbound_member_fails(self, tmp_path):
        """未在 bind 声明的成员访问 → fail-fast。"""
        _write(
            tmp_path,
            "main.ibci",
            """
import python "math" as m:
    bind sqrt(x: float) -> float

func test() -> auto:
    print((str)m.cos(1.0))

test()
""",
        )
        engine = IBCIEngine(root_dir=str(tmp_path), auto_sniff=False)
        try:
            lines = []
            engine.run(
                str(tmp_path / "main.ibci"),
                output_callback=lambda s: lines.append(str(s)),
                silent=True,
            )
            raise AssertionError("Expected runtime error, but execution succeeded")
        except Exception as e:
            assert "cos" in str(e), f"Expected fail-fast on unbound member, got: {e}"

    def test_binding_missing_member_fails(self, tmp_path):
        """bind 声明但宿主模块无该成员 → 报错（绑定期校验 fail-fast）。"""
        _write(
            tmp_path,
            "main.ibci",
            """
import python "math" as m:
    bind nonexist(x: float) -> float

func test() -> auto:
    print((str)m.nonexist(1.0))

test()
""",
        )
        engine = IBCIEngine(root_dir=str(tmp_path), auto_sniff=False)
        try:
            lines = []
            engine.run(
                str(tmp_path / "main.ibci"),
                output_callback=lambda s: lines.append(str(s)),
                silent=True,
            )
            raise AssertionError("Expected runtime error, but execution succeeded")
        except Exception as e:
            assert "nonexist" in str(e), f"Expected missing-member error, got: {e}"


class TestHostBindingCompileTimeTypeCheck:
    """bind 签名编译期类型检查。"""

    def test_wrong_arg_type_rejected(self, tmp_path):
        from core.kernel.issue import CompilerError

        _write(
            tmp_path,
            "main.ibci",
            """
import python "math" as m:
    bind sqrt(x: float) -> float

func test() -> auto:
    str s = m.sqrt("abc")

test()
""",
        )
        engine = IBCIEngine(root_dir=str(tmp_path), auto_sniff=False)
        try:
            engine.compile(str(tmp_path / "main.ibci"), silent=True)
            raise AssertionError("Expected compilation to fail, but succeeded")
        except CompilerError as e:
            codes = {d.code for d in e.diagnostics}
            assert "SEM_TYPE_MISMATCH" in codes, f"Expected SEM_TYPE_MISMATCH, got: {codes}"


class TestHostBindingParserGuard:
    """复核回归：宿主绑定解析守卫（不误伤真实名为 python 的普通模块导入）。"""

    def test_import_python_without_string_uses_regular_path(self, tmp_path):
        """``import python as p`` 不被劫持为宿主绑定（走普通 import → 模块未找到）。"""
        from core.kernel.issue import CompilerError

        _write(
            tmp_path,
            "main.ibci",
            """
import python as p

func test() -> auto:
    print("x")

test()
""",
        )
        engine = IBCIEngine(root_dir=str(tmp_path), auto_sniff=False)
        try:
            engine.compile(str(tmp_path / "main.ibci"), silent=True)
            raise AssertionError("Expected compilation to fail, but succeeded")
        except CompilerError as e:
            codes = {d.code for d in e.diagnostics}
            # 普通 import 路径：DEP_MODULE_NOT_FOUND；不得是宿主绑定的 PAR_EXPECTED_TOKEN
            assert "DEP_MODULE_NOT_FOUND" in codes, (
                f"Expected regular import path (DEP_MODULE_NOT_FOUND), got: {codes}"
            )
            assert "PAR_EXPECTED_TOKEN" not in codes, (
                f"Should not be hijacked as host import: {codes}"
            )

    def test_duplicate_bind_rejected(self, tmp_path):
        """重复 bind 同名成员 → 编译期 SEM_REDEFINITION。"""
        from core.kernel.issue import CompilerError

        _write(
            tmp_path,
            "main.ibci",
            """
import python "math" as m:
    bind sqrt(x: float) -> float
    bind sqrt(y: float) -> float
""",
        )
        engine = IBCIEngine(root_dir=str(tmp_path), auto_sniff=False)
        try:
            engine.compile(str(tmp_path / "main.ibci"), silent=True)
            raise AssertionError("Expected compilation to fail, but succeeded")
        except CompilerError as e:
            codes = {d.code for d in e.diagnostics}
            assert "SEM_REDEFINITION" in codes, f"Expected SEM_REDEFINITION, got: {codes}"
