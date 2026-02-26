import time

class TimeLib:
    @staticmethod
    def sleep(seconds: float) -> None:
        time.sleep(seconds)
        
    @staticmethod
    def now() -> float:
        return time.time()

implementation = TimeLib()
