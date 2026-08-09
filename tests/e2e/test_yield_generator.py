"""
tests/e2e/test_yield_generator.py
==================================

阶段 5 ``yield`` 惰性生成器端到端测试（D-08 自标记函数种类）。

覆盖：
- 基础生成器：for 迭代产出、局部状态跨 yield 保留
- 多 yield / 循环内 yield / 条件内 yield
- 生成器体可 await（LLM 行为组合，Waitable 挂起）
- 生成器作为值返回 / 传入
- 消费者 break 提前终止
- 编译期：非函数体内 yield 报错
"""

import pytest

from tests.conftest import run_ibci, compile_or_errors, AI_MOCK_PREFIX


class TestBasicGenerator:
    """基础生成器迭代。"""

    def test_for_iteration(self):
        code = """
func count(int n) -> int:
    int i = 0
    while i < n:
        yield i
        i = i + 1
    return 0

for int x in count(3):
    print(x)
"""
        assert run_ibci(code) == ["0", "1", "2"]

    def test_state_preserved_across_yields(self):
        """局部变量与循环位置跨 yield 保留（单可恢复驱动）。"""
        code = """
func gen() -> int:
    int a = 10
    yield a
    a = 20
    yield a
    return 0

for int x in gen():
    print(x)
"""
        assert run_ibci(code) == ["10", "20"]

    def test_condition_inside_loop(self):
        code = """
func tri(int n) -> int:
    int limit = n * 2
    int i = 0
    while i < limit:
        if i % 2 == 0:
            yield i
        i = i + 1
    return 0

for int x in tri(3):
    print(x)
"""
        assert run_ibci(code) == ["0", "2", "4"]

    def test_nested_loops_with_expression_yield(self):
        """嵌套循环 + yield 表达式（yield 低优先级解析整表达式）。"""
        code = """
func pairs(int n) -> int:
    int a = 0
    while a < n:
        int b = 0
        while b <= a:
            yield a * 10 + b
            b = b + 1
        a = a + 1
    return 0

for int x in pairs(3):
    print(x)
"""
        assert run_ibci(code) == ["0", "10", "11", "20", "21", "22"]

    def test_consumer_break(self):
        """消费者 break 提前终止（生成器不继续推进）。"""
        code = """
func count(int n) -> int:
    int i = 0
    while i < n:
        yield i
        i = i + 1
    return 0

for int x in count(10):
    if x == 3:
        break
    print(x)
"""
        assert run_ibci(code) == ["0", "1", "2"]


class TestGeneratorComposition:
    """生成器与语言特性组合。"""

    def test_generator_returned_as_value(self):
        code = """
func gen() -> int:
    yield 1
    yield 2
    yield 3
    return 0

func make() -> auto:
    return gen

auto g = make()
for int x in g():
    print(x)
"""
        assert run_ibci(code) == ["1", "2", "3"]

    def test_generator_with_llm_behavior(self):
        """生成器体内可 await LLM 行为（Waitable 挂起，与 yield 组合）。"""
        code = AI_MOCK_PREFIX + """
func gains(int n) -> str:
    int i = 0
    while i < n:
        str s = @~ MOCK:REPEAT:STR:hi ~
        yield s
        i = i + 1
    return ""

for str x in gains(2):
    print(x)
"""
        out = run_ibci(code)
        assert len(out) == 2
        assert all("hi" in line for line in out)

    def test_generator_assigned_to_auto(self):
        """生成器调用产出 generator[T] 值，可赋变量后迭代。"""
        code = """
func count(int n) -> int:
    int i = 0
    while i < n:
        yield i
        i = i + 1
    return 0

auto g = count(4)
for int x in g:
    print(x)
"""
        assert run_ibci(code) == ["0", "1", "2", "3"]


class TestNextBuiltin:
    """阶段 5 增量：``next()`` 内建推进惰性生成器。"""

    def test_next_advances_generator(self):
        """next(gen) 逐次推进生成器到产出值。"""
        code = """
func count(int n) -> int:
    int i = 0
    while i < n:
        yield i
        i = i + 1
    return 0

generator[int] g = count(3)
int a = next(g)
int b = next(g)
int c = next(g)
print((str)a)
print((str)b)
print((str)c)
"""
        assert run_ibci(code) == ["0", "1", "2"]

    def test_next_on_list(self):
        """next(iterable) 对其它可迭代对象取首个元素。"""
        code = """
list[int] a = [1, 2, 3]
int first = next(a)
print((str)first)
"""
        assert run_ibci(code) == ["1"]

    def test_next_exhausted_catchable(self):
        """next() 耗尽抛可捕获错误（try/except）。"""
        code = """
func count(int n) -> int:
    int i = 0
    while i < n:
        yield i
        i = i + 1
    return 0

generator[int] g = count(1)
int a = next(g)
int b = 0
try:
    b = next(g)
    print("NOERR")
except:
    print("CAUGHT")
"""
        assert run_ibci(code) == ["CAUGHT"]


class TestGeneratorSemantics:
    """编译期语义。"""

    def test_yield_only_in_function_body(self):
        """yield 只能在函数体内（D-08 自标记函数种类）。"""
        code = """
yield 1
"""
        artifact, errors = compile_or_errors(code)
        # 顶层 yield 应被语义层拒绝（无函数上下文）
        assert errors, "expected yield outside function to be a semantic error"

    def test_yield_from_only_in_function_body(self):
        """yield from 只能在函数体内（与 yield 同，D-08 自标记）。"""
        code = """
yield from g
"""
        artifact, errors = compile_or_errors(code)
        assert errors, "expected yield from outside function to be a semantic error"


class TestYieldFrom:
    """阶段 5 增量：``yield from`` 惰性生成器委托。"""

    def test_basic_delegation(self):
        """yield from 把子生成器产出逐值透传给消费者。"""
        code = """
func inner(int n) -> int:
    yield 1
    yield 2
    return 9

func outer(int n) -> int:
    yield from inner(n)
    return 0

for int x in outer(1):
    print(x)
"""
        assert run_ibci(code) == ["1", "2"]

    def test_delegation_expression_value(self):
        """yield from 表达式值 = 子生成器 return 值（可赋变量）。"""
        code = """
func inner(int n) -> int:
    yield 1
    yield 2
    return 9

func outer(int n) -> int:
    int r = yield from inner(n)
    yield r
    return 0

for int x in outer(1):
    print(x)
"""
        assert run_ibci(code) == ["1", "2", "9"]

    def test_delegate_to_list(self):
        """yield from 序列：逐值透传，表达式值 None。"""
        code = """
func outer(int n) -> int:
    yield from [10, 20, 30]
    return 0

for int x in outer(1):
    print(x)
"""
        assert run_ibci(code) == ["10", "20", "30"]

    def test_nested_delegation(self):
        """嵌套委托：yield from 可链式委托（生成器 → 生成器 → ...）。"""
        code = """
func a(int n) -> int:
    yield 1
    return 0

func b(int n) -> int:
    yield from a(n)
    yield 2
    return 0

func c(int n) -> int:
    yield from b(n)
    return 0

for int x in c(1):
    print(x)
"""
        assert run_ibci(code) == ["1", "2"]

    def test_break_early_termination(self):
        """外层 break 提前终止（for 消费：过滤输出，生成器仍被 to_list 急物化）。"""
        code = """
func inner(int n) -> int:
    int i = 0
    while i < n:
        yield i
        i = i + 1
    return 0

func outer(int n) -> int:
    yield from inner(n)
    return 0

for int x in outer(5):
    if x == 2:
        break
    print(x)
"""
        assert run_ibci(code) == ["0", "1"]

    def test_lazy_next_consumption(self):
        """next() 逐值惰性委托：消费第一个值后子生成器不继续推进。"""
        code = """
func inner(int n) -> int:
    int i = 0
    while i < n:
        yield i
        i = i + 1
    print("EXHAUSTED")
    return 0

func outer(int n) -> int:
    yield from inner(n)
    return 0

generator[int] g = outer(3)
int a = next(g)
print((str)a)
"""
        # next() 推进一个值即停；inner 未跑到耗尽（无 EXHAUSTED 输出）
        assert run_ibci(code) == ["0"]

    def test_delegate_generator_variable(self):
        """yield from 生成器变量（先调用后委托）。"""
        code = """
func inner(int n) -> int:
    yield 5
    yield 6
    return 0

func outer(int n) -> int:
    auto g = inner(n)
    yield from g
    return 0

for int x in outer(1):
    print(x)
"""
        assert run_ibci(code) == ["5", "6"]

    def test_generator_call_inside_generator_body(self):
        """生成器体内调用生成器函数产出 IbGenerator（缺陷修复回归）。"""
        code = """
func inner(int n) -> int:
    yield 1
    yield 2
    return 0

func outer(int n) -> int:
    auto g = inner(n)
    for int v in g:
        yield v
    return 0

for int x in outer(1):
    print(x)
"""
        assert run_ibci(code) == ["1", "2"]

    def test_delegation_with_llm_behavior(self):
        """子生成器体内可 await LLM 行为（与 yield from 组合）。"""
        code = AI_MOCK_PREFIX + """
func inner(int n) -> str:
    str s = @~ MOCK:REPEAT:STR:hi ~
    yield s
    return ""

func outer(int n) -> str:
    yield from inner(n)
    return ""

for str x in outer(1):
    print(x)
"""
        out = run_ibci(code)
        assert len(out) == 1
        assert "hi" in out[0]