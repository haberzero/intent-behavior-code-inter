"""tests/e2e/test_generator_to_list.py — generator.to_list() 用户显式调用行为。

验证 ``to_list``/``generic_next``/``next`` 经 ``__getattr__`` + ``__call__``
链式调用对用户显式调用可达：``gen(3).to_list()`` 等可直接调用。
"""
from tests.conftest import run_ibci


class TestGeneratorToListE2E:
    def test_to_list_plain_generator(self):
        code = """
import ai
ai.set_mock_mode()
func gen(int n) -> generator[int]:
    int i = 0
    while i < n:
        yield i
        i = i + 1
list items = gen(3).to_list()
print((str)items.len())
"""
        assert run_ibci(code) == ["3"]

    def test_to_list_with_mock_llm(self):
        code = """
import ai
ai.set_mock_mode()
func gen(int n) -> generator[str]:
    int i = 0
    while i < n:
        str g = @~ MOCK:STR:hi ~
        yield g
        i = i + 1
list items = gen(2).to_list()
int j = 0
while j < items.len():
    print((str)items[j])
    j = j + 1
"""
        assert run_ibci(code) == ["hi", "hi"]

    def test_generic_next_advances_generator(self):
        code = """
import ai
ai.set_mock_mode()
func gen(int n) -> generator[int]:
    int i = 0
    while i < n:
        yield i
        i = i + 1
generator[int] g = gen(5)
print((str)g.generic_next())
print((str)g.generic_next())
print((str)g.generic_next())
"""
        assert run_ibci(code) == ["0", "1", "2"]