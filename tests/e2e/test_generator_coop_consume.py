"""
tests/e2e/test_generator_coop_consume.py — 生成器协作消费判别测试。

锁定 ``IbGenerator`` 消费路径的**协作让出**模型（消除生成器消费的同步阻塞设计边界）：生成器体内 Waitable（``chan.recv()`` / LLM ``@~`` 行为）经 ``for`` /
``next()`` / ``to_list`` / ``yield from`` 消费时让出给 VM 调度器协作推进，
而非同步阻塞 ``event.result()``。

覆盖：
- 生成器内 ``chan.recv()`` 经 for / generic_next / to_list / yield from 消费（协作 recv Waitable）
- 生成器内 LLM 行为经 for 消费（回归锚点，与 test_to_list_with_mock_llm 互补）
- 空通道协作等待 + 独立线程投递（跨线程不阻塞、正确恢复）

注意：同调度器跨任务投递的死锁场景在用户代码模型下不可构造（thread 独立调度器），
本测试锁定协作路径的正确性与可恢复性。
"""

from tests.conftest import run_ibci


class TestGeneratorChanConsume:
    """生成器内 chan.recv()（Waitable）经各消费路径协作消费。"""

    def test_chan_recv_via_for(self):
        code = """
chan c = chan(int, "stream")
c.send(1)
c.send(2)
func gen() -> int:
    int a = c.recv()
    yield a
    int b = c.recv()
    yield b
for int x in gen():
    print((str)x)
"""
        assert run_ibci(code) == ["1", "2"]

    def test_chan_recv_via_generic_next(self):
        code = """
chan c = chan(int, "stream")
c.send(10)
func gen() -> int:
    int a = c.recv()
    yield a
generator[int] g = gen()
print((str)g.generic_next())
"""
        assert run_ibci(code) == ["10"]

    def test_chan_recv_via_to_list(self):
        code = """
chan c = chan(int, "stream")
c.send(5)
func gen() -> int:
    int a = c.recv()
    yield a
list items = gen().to_list()
print((str)items[0])
"""
        assert run_ibci(code) == ["5"]

    def test_chan_recv_via_yield_from(self):
        """yield from 委托：子生成器内 chan.recv() 协作消费，return 值保留。"""
        code = """
chan c = chan(int, "stream")
c.send(1)
c.send(2)
func inner() -> int:
    int a = c.recv()
    yield a
    return 9
func outer() -> int:
    int r = yield from inner()
    yield r
for int x in outer():
    print((str)x)
"""
        assert run_ibci(code) == ["1", "9"]

    def test_chan_recv_empty_channel_cross_thread_send(self):
        """空通道协作等待：消费方让出，独立线程投递后正确恢复（不阻塞/不死锁）。"""
        code = """
chan c = chan(int, "stream")
func gen() -> int:
    int a = c.recv()
    yield a
func send_it(chan x) -> int:
    x.send(42)
    return 0
thread[int] t = thread(callable=send_it, args=[c])
for int x in gen():
    print((str)x)
thread_result[int] r = t.join()
print((str)r.expect())
"""
        assert run_ibci(code) == ["42", "0"]


class TestGeneratorLLMFor:
    """生成器内 LLM 行为经 for 协作消费（回归锚点）。"""

    def test_llm_behavior_via_for(self):
        code = """
import ai
ai.set_mock_mode()
func gen(int n) -> generator[str]:
    int i = 0
    while i < n:
        str g = @~ MOCK:STR:hi ~
        yield g
        i = i + 1
for str x in gen(2):
    print(x)
"""
        assert run_ibci(code) == ["hi", "hi"]
