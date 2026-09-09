"""
ibci_time/core.py

时间工具内核实现（模块级函数形态）。零内核依赖。

契约（成员面 + 签名）单一权威源 = 内核契约源（contracts/time.ibci，bind 表达）；
本模块 = 实现面。
"""
import time as _time
import datetime as _datetime

__all__ = [
    "now", "now_ms", "utcnow", "localtime",
    "format", "parse", "date_str", "datetime_str",
    "add_seconds", "add_days", "diff_seconds", "diff_days",
    "sleep", "sleep_ms",
]


def now() -> float:
    """返回当前 Unix 时间戳（秒，含小数）。"""
    return _time.time()


def now_ms() -> int:
    """返回当前 Unix 时间戳（毫秒整数）。"""
    return int(_time.time() * 1000)


def utcnow() -> str:
    """返回当前 UTC 时间的 ISO 8601 字符串（如 '2026-04-16T03:00:00'）。"""
    return _datetime.datetime.now(_datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def localtime() -> str:
    """返回本地时间的格式化字符串（如 '2026-04-16 03:00:00'）。"""
    return _datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def format(timestamp: float, fmt: str) -> str:
    """将 Unix 时间戳格式化为字符串。fmt 使用 Python strftime 格式（如 '%Y-%m-%d'）。"""
    dt = _datetime.datetime.fromtimestamp(timestamp)
    return dt.strftime(fmt)


def parse(time_str: str, fmt: str) -> float:
    """将时间字符串按 fmt 解析为 Unix 时间戳。fmt 使用 Python strptime 格式。"""
    dt = _datetime.datetime.strptime(time_str, fmt)
    return dt.timestamp()


def date_str(timestamp: float) -> str:
    """将 Unix 时间戳格式化为日期字符串 'YYYY-MM-DD'。"""
    return format(timestamp, "%Y-%m-%d")


def datetime_str(timestamp: float) -> str:
    """将 Unix 时间戳格式化为日期时间字符串 'YYYY-MM-DD HH:MM:SS'。"""
    return format(timestamp, "%Y-%m-%d %H:%M:%S")


def add_seconds(timestamp: float, seconds: float) -> float:
    """在 Unix 时间戳上加上指定秒数。"""
    return timestamp + seconds


def add_days(timestamp: float, days: int) -> float:
    """在 Unix 时间戳上加上指定天数。"""
    return timestamp + days * 86400.0


def diff_seconds(ts1: float, ts2: float) -> float:
    """返回两个时间戳的差值（ts1 - ts2，秒）。"""
    return ts1 - ts2


def diff_days(ts1: float, ts2: float) -> float:
    """返回两个时间戳的差值（ts1 - ts2，天）。"""
    return (ts1 - ts2) / 86400.0


def sleep(seconds: float) -> None:
    """休眠指定秒数。"""
    _time.sleep(seconds)


def sleep_ms(milliseconds: int) -> None:
    """休眠指定毫秒数。"""
    _time.sleep(milliseconds / 1000.0)
