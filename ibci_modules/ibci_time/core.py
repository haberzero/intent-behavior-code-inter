"""
ibci_time/core.py

IBCI Time 插件实现。非侵入层插件，零内核依赖。
"""
import time


class TimeLib:
    """时间工具，包装 Python time 标准库。"""

    def now(self) -> float:
        """返回当前 Unix 时间戳（秒）。"""
        return time.time()

    def sleep(self, seconds: float) -> None:
        """休眠指定秒数。"""
        time.sleep(seconds)


def create_implementation() -> TimeLib:
    return TimeLib()
