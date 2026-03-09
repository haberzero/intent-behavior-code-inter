import time
from core.extension import sdk as ibci

class TimeLib:
    @ibci.method("sleep")
    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)
        
    @ibci.method("now")
    def now(self) -> float:
        return time.time()

implementation = TimeLib()
