"""
tests/e2e/test_instance_call_cps.py
====================================

用户类实例协议方法调用的帧内 CPS 驱动行为。

机制：``obj()``（可调用类实例）与用户类生成器 ``__iter__`` 经帧内 CPS 驱动：
- ``IbObject.receive('__call__')`` 对含用户 ``__call__`` 的类实例返回
  ``_UserCallDrive``（Waitable + CPSDrivable），VM 经 ``cps_drive`` 帧内驱动
  （UserFunctionCall trampoline）：深递归走 trampoline（Python 深度
  恒定），含 Waitable 的 ``__call__`` 可帧内挂起/恢复。
- ``IbUserFunction.call`` 对生成器方法返回 IbGenerator（与 VM 主路径同构）；
  ``resolve_iterable`` 对 ``__iter__`` 返回的 IbGenerator 做 to_list，
  ``yield from <实例>`` 委托产出。
"""

from tests.conftest import run_ibci, AI_MOCK_PREFIX


class TestCallableInstanceCPS:
    """``obj()`` 可调用类实例。"""

    def test_callable_instance_basic(self):
        code = """
class Doubler:
    func __call__(self, int x) -> int:
        return x * 2
Doubler d = Doubler()
int v = d(21)
print((str)v)
"""
        assert run_ibci(code) == ["42"]

    def test_callable_instance_deep_recursion(self):
        """深递归 __call__ 走 trampoline，Python 深度恒定。"""
        code = """
class Rec:
    func __call__(self, int n) -> int:
        if n <= 1:
            return 1
        return self(n - 1) + 1
Rec r = Rec()
int v = r(400)
print((str)v)
"""
        assert run_ibci(code) == ["400"]

    def test_callable_instance_via_fn_reference(self):
        """fn f = instance; f(...) 同样走 CPS 路径。"""
        code = """
class Greeter:
    func __call__(self, str name) -> str:
        return "hi " + name
Greeter g = Greeter()
fn f = g
str r = f("world")
print(r)
"""
        assert run_ibci(code) == ["hi world"]

    def test_callable_instance_with_llm_await(self):
        """__call__ 内 LLM 行为（Waitable）帧内驱动 + auto-yield（真实 MOCK 路径）。"""
        code = AI_MOCK_PREFIX + """
class Chatty:
    func __call__(self, str name) -> str:
        str g = @~ MOCK:STR:greeting ~
        return g + name
Chatty c = Chatty()
str r = c("x")
print(r)
"""
        assert run_ibci(code) == ["greetingx"]

    def test_callable_instance_method_await_chan(self):
        """__call__ 内 await 通道 recv（Waitable）：帧内挂起/恢复，不重入调度器。"""
        code = """
chan c = chan(str, "stream")
c.send("hello")
class Receiver:
    func __call__(self, chan x) -> str:
        str m = await x.recv()
        return m
Receiver r = Receiver()
str out = r(c)
print(out)
"""
        assert run_ibci(code) == ["hello"]


class TestGeneratorIterProtocol:
    """用户类生成器 __iter__。"""

    def test_generator_iter_for_loop(self):
        code = """
class Range:
    func __iter__(self) -> int:
        yield 1
        yield 2
Range r = Range()
for int x in r:
    print("x=" + (str)x)
"""
        assert run_ibci(code) == ["x=1", "x=2"]

    def test_generator_callable_for_loop(self):
        """生成器 __call__ 实例可迭代（for x in gc(...)）。"""
        code = """
class GenCallable:
    func __call__(self, int n) -> int:
        yield 10
        yield n
GenCallable gc = GenCallable()
for int x in gc(5):
    print("x=" + (str)x)
"""
        assert run_ibci(code) == ["x=10", "x=5"]

    def test_yield_from_instance(self):
        """yield from <生成器 __iter__ 实例> 委托产出。"""
        code = """
class Range:
    func __iter__(self) -> int:
        yield 1
        yield 2
func outer(int n) -> int:
    Range r = Range()
    yield from r
    return 0
for int x in outer(1):
    print("x=" + (str)x)
"""
        assert run_ibci(code) == ["x=1", "x=2"]

    def test_generator_iter_type_identity(self):
        """r.__iter__() 直接调用返回 IbGenerator（type=generator）。

        注：生成器方法的静态返回类型是其元素类型（05_functions §5.8），
        运行时值经 VM 主路径包装为 IbGenerator；类型身份经 type() 查询。"""
        code = """
class Range:
    func __iter__(self) -> int:
        yield 1
Range r = Range()
str t = type(r.__iter__())
print(t)
"""
        assert run_ibci(code) == ["generator"]
