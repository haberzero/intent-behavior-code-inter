from typing import Optional
from dataclasses import dataclass, field


@dataclass
class IsolationPolicy:
    """
    隔离策略。

    字段：
    - ``collect_timeout``：
        None = 无界等待（默认）；正数 = 墙钟等待上限（秒），超时 kill 子进程。
    - ``resource_limits``（可选）：
        dict 形式的 OS 资源限制（进程级隔离下施加于子进程）：
        - ``max_memory_mb``：RLIMIT_AS 上限（MB）
        - ``max_cpu_seconds``：RLIMIT_CPU 上限（秒）
        仅 Linux 有效（POSIX resource 模块）；非 POSIX 平台静默忽略（no-op）。

    设计决策：变量不跨隔离边界继承——子环境与父环境之间不做隐式内存交互，
    父->子 数据传递应通过显式 file 读写完成。
    """
    collect_timeout: Optional[float] = None
    resource_limits: Optional[dict] = None

    @staticmethod
    def full() -> 'IsolationPolicy':
        """默认全量隔离。"""
        return IsolationPolicy()

    def to_dict(self) -> dict:
        result = {
            "collect_timeout": self.collect_timeout,
        }
        if self.resource_limits is not None:
            result["resource_limits"] = self.resource_limits
        return result

    @classmethod
    def from_dict(cls, data: dict) -> 'IsolationPolicy':
        return cls(
            collect_timeout=data.get("collect_timeout", None),
            resource_limits=data.get("resource_limits", None),
        )
