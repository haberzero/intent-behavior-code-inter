"""
tests/e2e/test_method_cps.py

用户方法调用 CPS 化：``obj.method(x)`` 解包 ``IbBoundMethod`` 经 CPS trampoline
调用（与函数调用同构），receiver 作为 ``self`` 注入。方法含 Waitable 时帧内
挂起/恢复，深递归方法 Python 深度恒定。

覆盖：
- 方法内 await 通道 recv（Waitable），挂起/恢复正确（不重入调度器、不死锁）
- 深递归方法调用 Python 深度恒定（trampoline）
- 方法内 LLM 行为组合（await 正交）
- 方法接收者（self）正确绑定
- 惰性生成器方法（含 yield）可迭代
"""

from tests.conftest import AI_MOCK_PREFIX, run_ibci


class TestMethodCPS:
    def test_method_await_channel_recv(self):
        """用户方法体内 await 通道 recv（Waitable），挂起/恢复正确，不重入调度器。"""
        code = """
chan c = chan(str, "stream")
c.send("hello")
class Receiver:
    func read(self, chan x) -> str:
        str m = await x.recv()
        return m
Receiver r = Receiver()
str got = r.read(c)
print(got)
"""
        assert run_ibci(code) == ["hello"]

    def test_method_self_bound(self):
        """方法经 CPS 路径调用时 receiver 正确绑定为 self。"""
        code = """
class Counter:
    int value
    func inc(self, int n) -> int:
        self.value = self.value + n
        return self.value
Counter c = Counter(10)
int a = c.inc(5)
int b = c.inc(7)
print((str)a)
print((str)b)
"""
        assert run_ibci(code) == ["15", "22"]

    def test_deep_recursive_method_no_python_overflow(self):
        """深递归方法经 trampoline 驱动，Python 深度恒定。"""
        code = """
class Recur:
    func f(self, int n) -> int:
        if n <= 1:
            return 1
        return self.f(n - 1) + 1
Recur r = Recur()
print((str)r.f(500))
"""
        assert run_ibci(code) == ["500"]

    def test_method_llm_await_orthogonal(self):
        """方法内调用 LLM 行为（await 组合），与生成器/函数 CPS 一致。"""
        code = AI_MOCK_PREFIX + """
class Worker:
    func compute(self, str s) -> str:
        str v = await @~ MOCK:STR:hello-method ~
        return v
Worker w = Worker()
str got = w.compute("ignored")
print(got)
"""
        assert run_ibci(code) == ["hello-method"]

    def test_generator_method_iterable(self):
        """含 yield 的方法为惰性生成器，解包后经 CPS 驱动可迭代。"""
        code = """
class Gen:
    func seq(self, int n) -> int:
        int i = 0
        while i < n:
            yield i
            i = i + 1
        return 0
Gen g = Gen()
for int v in g.seq(3):
    print((str)v)
"""
        assert run_ibci(code) == ["0", "1", "2"]