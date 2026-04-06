import time


class TimeLib:
    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    def now(self) -> float:
        return time.time()


def create_implementation():
    return TimeLib()
