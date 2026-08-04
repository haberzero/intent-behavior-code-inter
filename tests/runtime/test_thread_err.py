"""
err 类型统一测试（任务 D）：TaskError 层次 + cancel 返回 err。

覆盖：
- TaskCancelled / TaskFailed 是 IBCI Exception 子类（用户可见、可继承）
- cancel() 返回 TaskCancelled err（操作状态）
- 线程失败 error() 返回 IBCI 错误对象
- expect() 抛出的错误可被 try/except 按类型捕获（继承链）
- thread_result 容器错误值化
"""

from tests.conftest import run_ibci


def test_cancel_returns_taskcancelled_err():
    code = """
func c() -> int:
    return 1

thread[int] t = thread(callable=c, args=[])
TaskCancelled e = t.cancel()
print(e.message)
"""
    lines = run_ibci(code)
    assert lines == ["Task was cancelled"]


def test_thread_failure_returns_taskfailed_err():
    code = """
func c() -> int:
    raise TaskFailed("boom")

thread[int] t = thread(callable=c, args=[])
thread_result[int] r = t.join()
print(r.status())
print((str)r.is_error())
"""
    lines = run_ibci(code)
    assert lines == ["failed", "True"]


def test_expect_catches_by_taskerror_hierarchy():
    code = """
func c() -> int:
    raise TaskFailed("boom")

thread[int] t = thread(callable=c, args=[])
thread_result[int] r = t.join()
try:
    int x = r.expect()
    print("no error")
except TaskError:
    print("caught TaskError")
except Exception:
    print("caught Exception")
"""
    lines = run_ibci(code)
    assert lines == ["caught TaskError"]


def test_expect_catches_user_defined_llm_error():
    code = """
func c() -> int:
    raise LLMParseError("parse fail")

thread[int] t = thread(callable=c, args=[])
thread_result[int] r = t.join()
print(r.status())
try:
    int x = r.expect()
    print("no error")
except LLMParseError:
    print("caught LLMParseError")
except Exception:
    print("caught Exception")
"""
    lines = run_ibci(code)
    assert lines == ["failed", "caught LLMParseError"]


def test_task_errors_are_exception_subclasses():
    code = """
func c() -> int:
    raise TaskCancelled("stopped")

thread[int] t = thread(callable=c, args=[])
thread_result[int] r = t.join()
print(r.status())
try:
    int x = r.expect()
    print("no error")
except Exception:
    print("caught Exception base")
"""
    lines = run_ibci(code)
    assert lines == ["failed", "caught Exception base"]