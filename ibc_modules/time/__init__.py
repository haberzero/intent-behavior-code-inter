import time
from core.extension import sdk as ibci

class TimeLib(ibci.IbPlugin):
    """
    Time 2.1: 时间处理插件。
    """
    def __init__(self):
        super().__init__()

    @ibci.method("sleep")
    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)
        
    @ibci.method("now")
    def now(self) -> float:
        return time.time()

def create_implementation():
    return TimeLib()
