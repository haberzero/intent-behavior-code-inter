"""
tests/e2e/test_callable_unification.py — 普通函数与 llm 可调用类实例：可调用值与渲染。

（llm 函数 → llm 可调用类实例）：
- 旧 `llm g() -> str` 函数值是 "可调用函数值"（可 fn 化、渲染 `func g() -> str`）。
- 新形态 = 实现 ``LLMCallable``（``__llm_call__``）的 llm 可调用**类实例**：一等对象
  （类变量持有 + 直接调用 ``g()``），非 fn 值（fn 只收 lambda/函数）。
  实例经统一 PromptRenderer 渲染为有意义描述（非 repr）。
"""

from tests.conftest import run_ibci


class TestCallableUnification:
    def test_function_and_llm_callable_instance_render_distinctly(self):
        code = """
func f() -> int:
    return 1

class Greet:
    func __llm_call__(self) -> dict:
        return {"user_prompt": "Say hi"}

Greet g = Greet()

print(f)
print(g)
"""
        lines = run_ibci(code)
        # 普通函数渲染为有意义可调用契约；llm 可调用类实例渲染为一等对象描述。
        assert lines == ["func f() -> int", "<Instance of Greet>"]

    def test_normal_function_still_callable(self):
        code = """
func f() -> int:
    return 42

print(f())
"""
        assert run_ibci(code) == ["42"]

    def test_llm_callable_instance_still_callable(self):
        code = """
import ai
ai.set_mock_mode()

class Greet:
    func __llm_call__(self) -> dict:
        return {"user_prompt": "MOCK:STR:hello"}

Greet g = Greet()
print(g())
"""
        assert run_ibci(code) == ["hello"]


class TestCallableAsFirstClassValues:
    def test_function_assignable_to_fn_and_callable_instance_first_class(self):
        code = """
import ai
ai.set_mock_mode()

func f() -> int:
    return 1

class Greet:
    func __llm_call__(self) -> dict:
        return {"user_prompt": "MOCK:STR:hi"}

Greet g = Greet()

fn a = f
print(a)

print(g())
"""
        lines = run_ibci(code)
        # 普通函数是一等 fn 值；llm 可调用类实例是一等对象（类变量持有 + 直接调用）。
        assert lines == ["func f() -> int", "hi"]
