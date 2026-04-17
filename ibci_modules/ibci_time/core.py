"""
ibci_time/core.py

IBCI Time 时间工具插件实现。非侵入层插件，零内核依赖。
"""
import time as _time
import datetime as _datetime


class TimeLib:
    """时间工具，包装 Python time / datetime 标准库。"""

    # --- 当前时间 ---

    def now(self) -> float:
        """返回当前 Unix 时间戳（秒，含小数）。"""
        return _time.time()

    def now_ms(self) -> int:
        """返回当前 Unix 时间戳（毫秒整数）。"""
        return int(_time.time() * 1000)

    def utcnow(self) -> str:
        """返回当前 UTC 时间的 ISO 8601 字符串（如 '2026-04-16T03:00:00'）。"""
        return _datetime.datetime.now(_datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    def localtime(self) -> str:
        """返回本地时间的格式化字符串（如 '2026-04-16 03:00:00'）。"""
        return _datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # --- 格式化/解析 ---

    def format(self, timestamp: float, fmt: str) -> str:
        """将 Unix 时间戳格式化为字符串。fmt 使用 Python strftime 格式（如 '%Y-%m-%d'）。"""
        dt = _datetime.datetime.fromtimestamp(timestamp)
        return dt.strftime(fmt)

    def parse(self, time_str: str, fmt: str) -> float:
        """将时间字符串按 fmt 解析为 Unix 时间戳。fmt 使用 Python strptime 格式。"""
        dt = _datetime.datetime.strptime(time_str, fmt)
        return dt.timestamp()

    def date_str(self, timestamp: float) -> str:
        """将 Unix 时间戳格式化为日期字符串 'YYYY-MM-DD'。"""
        return self.format(timestamp, "%Y-%m-%d")

    def datetime_str(self, timestamp: float) -> str:
        """将 Unix 时间戳格式化为日期时间字符串 'YYYY-MM-DD HH:MM:SS'。"""
        return self.format(timestamp, "%Y-%m-%d %H:%M:%S")

    # --- 时间差 ---

    def add_seconds(self, timestamp: float, seconds: float) -> float:
        """在 Unix 时间戳上加上指定秒数。"""
        return timestamp + seconds

    def add_days(self, timestamp: float, days: int) -> float:
        """在 Unix 时间戳上加上指定天数。"""
        return timestamp + days * 86400.0

    def diff_seconds(self, ts1: float, ts2: float) -> float:
        """返回两个时间戳的差值（ts1 - ts2，秒）。"""
        return ts1 - ts2

    def diff_days(self, ts1: float, ts2: float) -> float:
        """返回两个时间戳的差值（ts1 - ts2，天）。"""
        return (ts1 - ts2) / 86400.0

    # --- 休眠 ---

    def sleep(self, seconds: float) -> None:
        """休眠指定秒数。"""
        _time.sleep(seconds)

    def sleep_ms(self, milliseconds: int) -> None:
        """休眠指定毫秒数。"""
        _time.sleep(milliseconds / 1000.0)


def create_implementation() -> TimeLib:
    return TimeLib()
