"""
tests/e2e/test_retroactive_impl_builtin.py — retroactive implementation
targets extended to built-in types (``impl P for int``).

Covers: full pipeline (compile → hydration → dispatch) for built-in value
types, protocol-satisfaction closure (generic bounds), conflict fail-fast
against the built-in method surface (declared members / axiom operators /
runtime-only vtable entries), and target-validity rejection.

Built-in types are kernel-owned (module_path=None): an impl on a built-in
type is engine-global — its methods are visible to every module of the same
compilation, and the runtime vtable registration is process-global for the
engine instance.
"""

import pytest

from tests.conftest import run_ibci, compile_ibci, expect_compile_error
from core.base.diagnostics.codes import SEM_REDEFINITION, SEM_TYPE_MISMATCH
from core.kernel.issue import CompilerError


class TestImplBuiltinSuppliesMethods:
    def test_impl_supplies_method_on_int(self):
        """impl 为 int 补协议方法；调用经内置 vtable 分派生效。"""
        code = """
protocol Greeter:
    func greet(self) -> str:
        pass

impl Greeter for int:
    func greet(self) -> str:
        return "num " + self.cast_to(str)

print((42).greet())
"""
        assert run_ibci(code) == ["num 42"]

    def test_impl_method_on_str_uses_native_methods(self):
        """impl 方法体内可调用内置类型的原生方法。"""
        code = """
protocol Shouter:
    func shout(self) -> str:
        pass

impl Shouter for str:
    func shout(self) -> str:
        return self.upper() + "!"

print("hey".shout())
"""
        assert run_ibci(code) == ["HEY!"]

    def test_impl_method_on_list(self):
        """内置容器基类型（非泛型裸 list）可作 impl 目标。"""
        code = """
protocol Sized:
    func size(self) -> int:
        pass

impl Sized for list:
    func size(self) -> int:
        return self.len()

print([1, 2, 3].size())
"""
        assert run_ibci(code) == ["3"]

    def test_impl_two_blocks_for_two_protocols_on_builtin(self):
        """同一内置类型多个 impl 块（不同协议）各自补充方法。"""
        code = """
protocol A:
    func a(self) -> str:
        pass

protocol B:
    func b(self) -> str:
        pass

impl A for int:
    func a(self) -> str:
        return "a"

impl B for int:
    func b(self) -> str:
        return "b"

print((5).a() + (5).b())
"""
        assert run_ibci(code) == ["ab"]

    def test_impl_method_usable_as_generic_bound(self):
        """impl 补方法后内置类型满足协议 bound：可作 Box[T: P] 的实参。"""
        code = """
protocol Greeter:
    func greet(self) -> str:
        pass

impl Greeter for int:
    func greet(self) -> str:
        return "hi"

class Box[T: Greeter]:
    T value
    func get(self) -> T:
        return self.value

Box[int] b = Box[int](7)
print(b.get().greet())
"""
        assert run_ibci(code) == ["hi"]

    def test_impl_declaration_only_form_on_builtin(self):
        """空 body 声明式：内置类型已声明的方法满足协议时仅记录。"""
        code = """
protocol B:
    func to_bool(self) -> bool:
        pass

impl B for int:

print(1.to_bool())
"""
        assert run_ibci(code) == ["True"]

    def test_impl_llm_method_on_builtin(self):
        """impl 内 LLM 方法补充内置类型协议方法（与普通方法同构）。"""
        code = """
protocol P:
    func m(self) -> int:
        pass

impl P for int:
    llm func m(self) -> int:
__sys__
你是数字解析器。
__user__
MOCK:INT:42
llmend

print((0).m())
"""
        assert run_ibci(code, ai=True) == ["42"]

    def test_impl_on_builtin_is_engine_global_across_modules(self, tmp_path):
        """内置类型属内核根命名空间（无 module 限定）：一个模块的 impl 对同一
        编译的全部模块可见（成员进共享内置 spec、方法注册进全局运行期 vtable）。
        """
        (tmp_path / "helper.ibci").write_text(
            "protocol Greeter:\n"
            "    func greet(self) -> str:\n"
            "        pass\n"
            "\n"
            "impl Greeter for int:\n"
            "    func greet(self) -> str:\n"
            "        return \"g\" + self.cast_to(str)\n",
            encoding="utf-8",
        )
        (tmp_path / "main.ibci").write_text(
            "import helper\nprint((9).greet())\n",
            encoding="utf-8",
        )
        from core.engine import IBCIEngine

        engine = IBCIEngine(root_dir=str(tmp_path))
        lines = []
        engine.run(
            str(tmp_path / "main.ibci"),
            output_callback=lambda s: lines.append(str(s)),
            silent=True,
        )
        assert lines == ["g9"]


class TestImplBuiltinValidation:
    def test_missing_method_still_errors(self):
        """impl（含补充）未覆盖全部协议方法 → 编译期错误。"""
        code = """
protocol P:
    func a(self) -> int:
        pass
    func b(self) -> int:
        pass

impl P for int:
    func a(self) -> int:
        return 1
"""
        with pytest.raises(CompilerError):
            compile_ibci(code)

    def test_signature_mismatch_errors(self):
        """impl 补充的方法签名与协议不兼容 → 编译期错误。"""
        code = """
protocol P:
    func m(self, int x) -> int:
        pass

impl P for int:
    func m(self, str s) -> int:
        return 1
"""
        with pytest.raises(CompilerError):
            compile_ibci(code)

    def test_conflict_with_declared_builtin_member_errors(self):
        """impl 方法与内置类型公理声明成员（cast_to）同名 → SEM_REDEFINITION。"""
        code = """
protocol P:
    func cast_to(self, any t) -> any:
        pass

impl P for int:
    func cast_to(self, any t) -> any:
        return 1
"""
        expect_compile_error(code, SEM_REDEFINITION)

    def test_conflict_with_builtin_operator_errors(self):
        """impl 方法与内置类型公理运算符（__add__，运行期自动绑定 vtable）
        同名 → SEM_REDEFINITION。"""
        code = """
protocol P:
    func m(self) -> int:
        pass

impl P for int:
    func m(self) -> int:
        return 1
    func __add__(self, int o) -> int:
        return 0
"""
        expect_compile_error(code, SEM_REDEFINITION)

    def test_conflict_across_two_impl_blocks_on_builtin_errors(self):
        """同一内置类型两个 impl 块提供同名方法 → SEM_REDEFINITION。"""
        code = """
protocol A:
    func m(self) -> int:
        pass

protocol B:
    func n(self) -> int:
        pass

impl A for int:
    func m(self) -> int:
        return 1

impl B for int:
    func m(self) -> int:
        return 2
    func n(self) -> int:
        return 3
"""
        expect_compile_error(code, SEM_REDEFINITION)

    def test_conflict_with_runtime_only_vtable_method_fails_at_hydration(self):
        """impl 方法与内置类型仅运行期注册的 vtable 方法（__to_prompt__，
        不进 spec.members / 公理声明面）同名 → 水化期 fail-fast，禁止静默
        覆写内核方法。"""
        code = """
protocol P:
    func m(self) -> int:
        pass

impl P for int:
    func m(self) -> int:
        return 1
    func __to_prompt__(self) -> str:
        return "x"

print((1).m())
"""
        with pytest.raises(RuntimeError, match="conflicts with an existing vtable method"):
            run_ibci(code)

    def test_init_on_builtin_errors(self):
        """impl 为内置类型定义 __init__ → 编译期错误（内置构造走原生路径，
        永不分派 impl 构造器，收集了即半接通）。"""
        code = """
protocol P:
    func m(self) -> int:
        pass

impl P for int:
    func m(self) -> int:
        return 1
    func __init__(self) -> auto:
        pass
"""
        expect_compile_error(code, SEM_TYPE_MISMATCH)

    def test_dynamic_target_errors(self):
        """any/auto 是动态逃生类型（对一切协议恒满足），不可作 impl 目标。"""
        code = """
protocol P:
    func m(self) -> int:
        pass

impl P for any:
    func m(self) -> int:
        return 1
"""
        expect_compile_error(code, SEM_TYPE_MISMATCH)

    def test_void_target_errors(self):
        """void 无实例，不可作 impl 目标。"""
        code = """
protocol P:
    func m(self) -> int:
        pass

impl P for void:
    func m(self) -> int:
        return 1
"""
        expect_compile_error(code, SEM_TYPE_MISMATCH)

    def test_module_target_errors(self):
        """module 是命名空间而非值类型（无对应运行期类），不可作 impl 目标。"""
        code = """
protocol P:
    func m(self) -> int:
        pass

impl P for module:
    func m(self) -> int:
        return 1
"""
        expect_compile_error(code, SEM_TYPE_MISMATCH)
