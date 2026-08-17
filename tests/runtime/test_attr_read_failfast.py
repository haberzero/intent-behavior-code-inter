"""
tests/runtime/test_attr_read_failfast.py
========================================

未声明属性读取 fail-fast 判别性回归。

锁定语义：
- 未声明属性**读取**（``p.y``）报 ``RUN_ATTRIBUTE_ERROR``（属性缺失是程序
  错误，显式报错优于静默返回 None 让错误值流入后续运算）。
- 未声明方法**调用**路径同样报 ``RUN_ATTRIBUTE_ERROR``（既有行为保持）。
- 已声明属性/方法读取不受影响。
"""
from tests.conftest import run_ibci
from core.engine import IBCIEngine
from tests.conftest import _default_root


def _run_err_code(code: str) -> str:
    """运行代码并提取第一个诊断码（格式 [ERROR][CODE]: ...）。"""
    import re

    engine = IBCIEngine(root_dir=_default_root())
    try:
        engine.run_string(code, silent=True)
    except Exception as e:
        m = re.search(r"\[ERROR\]\[([A-Z_]+)\]", str(e))
        if m:
            return m.group(1)
        return "NO_CODE"
    return "NO_ERROR"


def test_missing_attr_read_emits_run_attribute_error():
    """未声明属性读取 → RUN_ATTRIBUTE_ERROR（主线程）。"""
    code = (
        "class Point:\n"
        "    int x\n"
        "    func __init__(self, int x) -> auto:\n"
        "        self.x = x\n"
        "Point p = Point(1)\n"
        "print(p.y)\n"
    )
    assert _run_err_code(code) == "RUN_ATTRIBUTE_ERROR"


def test_missing_attr_read_in_thread_emits_error():
    """未声明属性读取在线程 worker 内同样报错（不静默 None）。

    worker 内异常经线程结果暴露（``t.result()`` 抛错），主线程可捕获。
    """
    code = (
        "class Point:\n"
        "    int x\n"
        "    func __init__(self, int x) -> auto:\n"
        "        self.x = x\n"
        "func work() -> auto:\n"
        "    Point p = Point(1)\n"
        "    print(p.y)\n"
        "thread[int] t = thread(callable=work, args=[])\n"
        "try:\n"
        "    print(t.result())\n"
        "except Exception as e:\n"
        "    print(\"caught\")\n"
    )
    assert run_ibci(code) == ["caught"]


def test_declared_attr_read_unaffected():
    """已声明属性/方法读取不受影响。"""
    code = (
        "class Point:\n"
        "    int x\n"
        "    func __init__(self, int x) -> auto:\n"
        "        self.x = x\n"
        "    func get(self) -> int:\n"
        "        return self.x\n"
        "Point p = Point(7)\n"
        "print(p.x)\n"
        "print(p.get())\n"
    )
    assert run_ibci(code) == ["7", "7"]


def test_missing_method_call_still_emits_error():
    """未声明方法调用路径保持 RUN_ATTRIBUTE_ERROR。"""
    code = (
        "class Point:\n"
        "    int x\n"
        "    func __init__(self, int x) -> auto:\n"
        "        self.x = x\n"
        "Point p = Point(1)\n"
        "print(p.missing())\n"
    )
    assert _run_err_code(code) == "RUN_ATTRIBUTE_ERROR"
