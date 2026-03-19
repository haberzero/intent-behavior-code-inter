import time
from core.extension import ibcext

class TimeLib(ibcext.IbPlugin):
    """
    Time 2.1: 时间处理插件。
    """
    def __init__(self):
        super().__init__()

    @ibcext.method("sleep")
    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    @ibcext.method("now")
    def now(self) -> float:
        return time.time()

def create_implementation():
    return TimeLib()
