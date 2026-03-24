"""
[IES 2.2] Time 时间处理插件

纯 Python 实现，零侵入。
"""
import time


class TimeLib:
    """
    [IES 2.2] Time 2.2: 时间处理插件。
    不继承任何核心类，完全独立。
    """
    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    def now(self) -> float:
        return time.time()


def create_implementation():
    return TimeLib()
