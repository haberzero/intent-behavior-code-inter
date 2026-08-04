"""
线程结果容器测试（任务 C2）：thread_result[T] 值对象 + 容器方法。

覆盖：
- join 返回容器（成功/失败路径）
- is_success / is_error / status
- expect()（直接取值，失败抛错）
- unwrap_or(default)（失败返回默认）
- unwrap() → Optional[T]
- value() / error() 内省方法
"""

from tests.conftest import run_ibci


def test_result_success_path():
    code = """
func c() -> int:
    return 1

thread[int] t = thread(callable=c, args=[])
thread_result[int] r = t.join()
print((str)r.is_success())
print((str)r.is_error())
print(r.status())
print((str)r.expect())
print((str)r.value())
print(r.unwrap())
"""
    lines = run_ibci(code)
    assert lines == ["True", "False", "done", "1", "1", "1"]


def test_result_failure_unwrap_or():
    code = """
func c() -> int:
    raise LLMParseError("fail")

thread[int] t = thread(callable=c, args=[])
thread_result[int] r = t.join()
print((str)r.is_error())
print((str)r.is_success())
print(r.status())
print((str)r.unwrap_or(99))
"""
    lines = run_ibci(code)
    assert lines == ["True", "False", "failed", "99"]


def test_result_expect_fails_on_error():
    code = """
func c() -> int:
    raise LLMParseError("fail")

thread[int] t = thread(callable=c, args=[])
thread_result[int] r = t.join()
try:
    int x = r.expect()
    print("no error")
except LLMParseError:
    print("caught")
"""
    lines = run_ibci(code)
    assert lines == ["caught"]


def test_result_unwrap_returns_optional():
    code = """
func c() -> int:
    return 7

thread[int] t = thread(callable=c, args=[])
thread_result[int] r = t.join()
Optional[int] o = r.unwrap()
print((str)o.is_some())
print((str)o.unwrap())
"""
    lines = run_ibci(code)
    assert lines == ["True", "7"]