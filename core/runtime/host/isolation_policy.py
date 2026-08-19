from typing import Optional
from dataclasses import dataclass


@dataclass
class IsolationPolicy:
    """
    隔离策略（收敛为实际生效的单维）。

    实际参与决策的字段（复核后收敛，删除零消费者字段 inherit_plugins）：

    - ``collect_timeout``：
        None = 无界等待（默认，阻塞至子执行完成，严格遵循 ISO-5）
        正数 = collect 的墙钟等待上限（秒）；超时则抛 RuntimeError，
               子线程作为 daemon 孤儿继续运行（Python 无法强杀线程），
               直至自身结束或进程退出。0 表示零等待探测。

    设计决策：变量不跨隔离边界继承——子环境与父环境之间不做隐式内存交互，
    父->子 数据传递应通过显式 file 读写完成。
    """
    collect_timeout: Optional[float] = None

    @staticmethod
    def full() -> 'IsolationPolicy':
        """默认全量隔离。"""
        return IsolationPolicy()

    def to_dict(self) -> dict:
        return {
            "collect_timeout": self.collect_timeout,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'IsolationPolicy':
        return cls(
            collect_timeout=data.get("collect_timeout", None),
        )
