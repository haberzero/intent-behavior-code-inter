from typing import Optional, Union
from dataclasses import dataclass


@dataclass
class IsolationPolicy:
    """
    隔离策略（收敛为实际生效的两维）。

    实际参与决策的字段（复核后收敛，删除零消费者字段）：

    - ``inherit_plugins``：是否继承父引擎的插件搜索路径
        True   = 继承全部插件（默认）
        False  = 不继承任何插件
    - ``collect_timeout``：
        None = 无界等待（默认，阻塞至子执行完成，严格遵循 ISO-5）
        正数 = collect 的墙钟等待上限（秒）；超时则抛 RuntimeError，
               子线程作为 daemon 孤儿继续运行（Python 无法强杀线程），
               直至自身结束或进程退出。0 表示零等待探测。

    设计决策：变量不跨隔离边界继承——子环境与父环境之间不做隐式内存交互，
    父->子 数据传递应通过显式 file 读写完成。
    """
    inherit_plugins: bool = True
    collect_timeout: Optional[float] = None

    @staticmethod
    def full() -> 'IsolationPolicy':
        """全量隔离：继承全部插件。"""
        return IsolationPolicy(inherit_plugins=True)

    @staticmethod
    def partial(inherit_plugins: bool = True) -> 'IsolationPolicy':
        """部分隔离：按配置继承插件。"""
        return IsolationPolicy(inherit_plugins=inherit_plugins)

    @staticmethod
    def minimal() -> 'IsolationPolicy':
        """最小隔离：不继承插件。"""
        return IsolationPolicy(inherit_plugins=False)

    def to_dict(self) -> dict:
        return {
            "inherit_plugins": self.inherit_plugins,
            "collect_timeout": self.collect_timeout,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'IsolationPolicy':
        inherit_plugins = data.get("inherit_plugins", True)
        if not isinstance(inherit_plugins, bool):
            # 选择性插件继承（List 形态）未实现——显式拒绝（fail-fast），
            # 不接受静默退化为全量继承（收敛为 bool）。
            raise ValueError(
                "inherit_plugins must be a bool (True=all / False=none); "
                f"got {type(inherit_plugins).__name__}: {inherit_plugins!r}. "
                "Selective plugin inheritance is not supported."
            )
        return cls(
            inherit_plugins=inherit_plugins,
            collect_timeout=data.get("collect_timeout", None),
        )
