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
from tests.conftest import expect_compile_error


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


class TestHostClassBindingE2E:
    """F2 e2e：宿主类型绑定（bind class）一等类型全链路。"""

    def test_impl_method_and_protocol(self, tmp_path):
        """宿主类型 + impl 方法 + 协议满足（JSONDecoder + Describable）。"""
        _write(
            tmp_path,
            "main.ibci",
            """
import python "json" as j:
    bind class JSONDecoder:
        bind decode(s: str) -> any

protocol Describable:
    func describe(self) -> str:
        pass

impl Describable for JSONDecoder:
    func describe(self) -> str:
        return "json-decoder"

func test() -> auto:
    JSONDecoder d = JSONDecoder()
    str s = d.describe()
    print(s)

test()
""",
        )
        assert _run(tmp_path) == ["json-decoder"]

    def test_native_bind_method_and_impl(self, tmp_path):
        """bind 方法（原生 decode）+ impl 方法（describe）同实例调用。"""
        _write(
            tmp_path,
            "main.ibci",
            """
import python "json" as j:
    bind class JSONDecoder:
        bind decode(s: str) -> any

protocol Describable:
    func describe(self) -> str:
        pass

impl Describable for JSONDecoder:
    func describe(self) -> str:
        return "json-decoder"

func test() -> auto:
    JSONDecoder d = JSONDecoder()
    any r = d.decode("{\\"a\\": 1}")
    print(d.describe())
    print((str)r)

test()
""",
        )
        assert _run(tmp_path) == ["json-decoder", "{a: 1}"]

    def test_attributes_and_return_rebox(self, tmp_path):
        """bind 属性成员（whitelist）+ 返回宿主实例重包装（datetime.replace）。"""
        _write(
            tmp_path,
            "main.ibci",
            """
import python "datetime" as dt:
    bind class datetime:
        bind year -> int
        bind month -> int
        bind replace(year: int) -> any

func test() -> auto:
    datetime d = datetime(2026, 8, 17)
    print((str)d.year)
    print((str)d.month)
    datetime d2 = d.replace(2027)
    print((str)d2.year)

test()
""",
        )
        assert _run(tmp_path) == ["2026", "8", "2027"]

    def test_shorthand_bind_class(self, tmp_path):
        """bind class Name -> any 简写（仅类型身份，impl 补方法）。"""
        _write(
            tmp_path,
            "main.ibci",
            """
import python "json" as j:
    bind class JSONEncoder -> any

protocol Describable:
    func describe(self) -> str:
        pass

impl Describable for JSONEncoder:
    func describe(self) -> str:
        return "encoder"

func test() -> auto:
    JSONEncoder e = JSONEncoder()
    print(e.describe())

test()
""",
        )
        assert _run(tmp_path) == ["encoder"]

    def test_host_class_as_type_annotation(self, tmp_path):
        """宿主类型作类型注解 + 构造器实参（host 类型推断/调用）。"""
        _write(
            tmp_path,
            "main.ibci",
            """
import python "collections" as c:
    bind class deque:
        bind append(x: any) -> any
        bind popleft() -> any

func test() -> auto:
    deque q = deque()
    q.append(10)
    q.append(20)
    any first = q.popleft()
    print((str)first)

test()
""",
        )
        assert _run(tmp_path) == ["10"]

    def test_instance_attribute_member(self, tmp_path):
        """bind 实例属性成员（__init__ 中 self.x，类上不可见）→ 白名单访问期契约。

        实例属性（如 queue.Queue.maxsize）类上 hasattr 为 False，绑定期不做类级
        存在性校验；白名单访问时经 getattr(实例, name) 强制契约（缺失 → fail-fast）。
        """
        _write(
            tmp_path,
            "main.ibci",
            """
import python "queue" as q:
    bind class Queue:
        bind maxsize -> any
        bind put(x: any) -> any
        bind get() -> any

func test() -> auto:
    Queue qq = Queue()
    qq.put(10)
    qq.put(20)
    any first = qq.get()
    any second = qq.get()
    any ms = qq.maxsize
    print((str)first)
    print((str)second)
    print((str)ms)

test()
""",
        )
        assert _run(tmp_path) == ["10", "20", "0"]


class TestHostClassBindingFailFast:
    """F2 显式声明式绑定：契约外成员 / 缺失宿主类 / 缺失成员 fail-fast。"""

    def _run_expect_fail(self, tmp_path, content, needle):
        _write(tmp_path, "main.ibci", content)
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
            assert needle in str(e), f"Expected '{needle}' in error, got: {e}"

    def test_unbound_attribute_fails(self, tmp_path):
        """契约外属性访问宿主实例 → fail-fast（不自动穿透）。"""
        self._run_expect_fail(
            tmp_path,
            """
import python "json" as j:
    bind class JSONDecoder:
        bind decode(s: str) -> any

func test() -> auto:
    JSONDecoder d = JSONDecoder()
    any x = d.raw_decode("x")

test()
""",
            "raw_decode",
        )

    def test_bind_missing_class_fails(self, tmp_path):
        """bind class 绑定模块中不存在的宿主类 → STAGE 5 fail-fast。"""
        self._run_expect_fail(
            tmp_path,
            """
import python "json" as j:
    bind class DoesNotExist:
        bind foo() -> any

func test() -> auto:
    DoesNotExist d = DoesNotExist()

test()
""",
            "DoesNotExist",
        )

    def test_bind_missing_member_fails(self, tmp_path):
        """bind class 内声明宿主类不存在的成员 → STAGE 5 fail-fast。"""
        self._run_expect_fail(
            tmp_path,
            """
import python "json" as j:
    bind class JSONDecoder:
        bind not_a_method() -> any

func test() -> auto:
    pass

test()
""",
            "not_a_method",
        )


class TestHostClassBindingCompileTimeConflict:
    """F2 显式声明式绑定：bind 成员与 impl 方法 / 重复绑定的编译期冲突 fail-fast。

    冲突判定以目标类权威成员面 spec.members 为准（宿主类 bind 成员只进 members、
    不进合成 owned_scope 符号表）——同名 impl 若未被拦截会静默遮蔽 bind 成员并
    覆写其签名（双写真相漂移），故必须 SEM_REDEFINITION fail-fast。
    """

    def test_bind_impl_same_name_fails(self):
        """bind 方法与 impl 方法同名 → 编译期 SEM_REDEFINITION。"""
        expect_compile_error(
            """
import python "json" as j:
    bind class JSONDecoder:
        bind decode(s: str) -> any

protocol P:
    func decode(self, str s) -> any:
        pass

impl P for JSONDecoder:
    func decode(self, str s) -> any:
        return "impl-decode"

func test() -> auto:
    JSONDecoder d = JSONDecoder()
    print(d.decode("{}"))

test()
""",
            "SEM_REDEFINITION",
        )

    def test_bind_attr_impl_same_name_fails(self):
        """bind 属性成员与 impl 方法同名 → 编译期 SEM_REDEFINITION。"""
        expect_compile_error(
            """
import python "queue" as q:
    bind class Queue:
        bind maxsize -> any

protocol P:
    func maxsize(self) -> int:
        pass

impl P for Queue:
    func maxsize(self) -> int:
        return 99

func test() -> auto:
    Queue qu = Queue()
    print(qu.maxsize)

test()
""",
            "SEM_REDEFINITION",
        )

    def test_bind_class_duplicate_member_fails(self):
        """同一 bind class 块内重复绑定同名成员 → 编译期 SEM_REDEFINITION。"""
        expect_compile_error(
            """
import python "json" as j:
    bind class JSONDecoder:
        bind decode(s: str) -> any
        bind decode(s: str) -> any

func test() -> auto:
    JSONDecoder d = JSONDecoder()
    print(d.decode("{}"))

test()
""",
            "SEM_REDEFINITION",
        )
