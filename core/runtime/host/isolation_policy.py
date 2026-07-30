from typing import List, Optional, Union
from dataclasses import dataclass


@dataclass
class IsolationPolicy:
    """
    隔离级别策略。

    | Level       | Registry | Plugins | Intents | Variables | CallStack |
    |-------------|----------|---------|---------|-----------|-----------|
    | FULL        | 独立克隆 | 全部继承 | 全部继承 | 不继承    | 全部继承  |
    | PARTIAL     | 独立克隆 | 按配置   | 按配置   | 不继承    | 清空      |
    | PLUGIN_ONLY | 共享     | 指定列表 | 清空    | 不继承    | 清空      |
    | MINIMAL     | 共享     | 不继承   | 清空    | 不继承    | 清空      |

    设计决策：变量不跨隔离边界继承--子环境与父环境之间不做隐式内存交互，
    父->子 数据传递应通过显式 file 读写完成。

    inherit_plugins 语义：
        True   = 继承全部插件（默认）
        False  = 不继承任何插件
        ["ai"] = 仅继承指定插件（选择性继承，按插件目录名过滤）

    collect_timeout 语义：
        None = 无界等待（默认，阻塞至子执行完成，严格遵循 ISO-5）
        正数 = collect 的墙钟等待上限（秒）；超时则抛 RuntimeError，
               子线程作为 daemon 孤儿继续运行（Python 无法强杀线程），
               直至自身结束或进程退出。0 表示零等待探测。
    """
    level: str = "PARTIAL"
    inherit_plugins: Union[bool, List[str]] = True
    inherit_intents: bool = False
    inherit_classes: bool = True
    max_call_stack: int = 1000
    max_instructions: int = 10000
    collect_timeout: Optional[float] = None

    @staticmethod
    def full() -> 'IsolationPolicy':
        return IsolationPolicy(
            level="FULL",
            inherit_plugins=True,
            inherit_intents=True,
            inherit_classes=True
        )

    @staticmethod
    def partial(inherit_plugins: Union[bool, List[str]] = True, inherit_intents: bool = True) -> 'IsolationPolicy':
        return IsolationPolicy(
            level="PARTIAL",
            inherit_plugins=inherit_plugins,
            inherit_intents=inherit_intents,
            inherit_classes=True
        )

    @staticmethod
    def plugin_only(inherit_plugins: List[str]) -> 'IsolationPolicy':
        return IsolationPolicy(
            level="PLUGIN_ONLY",
            inherit_plugins=inherit_plugins,
            inherit_intents=False,
            inherit_classes=False
        )

    @staticmethod
    def minimal() -> 'IsolationPolicy':
        return IsolationPolicy(
            level="MINIMAL",
            inherit_plugins=False,
            inherit_intents=False,
            inherit_classes=False
        )

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "inherit_plugins": self.inherit_plugins,
            "inherit_intents": self.inherit_intents,
            "inherit_classes": self.inherit_classes,
            "max_call_stack": self.max_call_stack,
            "max_instructions": self.max_instructions,
            "isolated": self.level in ("FULL", "PARTIAL"),
            "collect_timeout": self.collect_timeout,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'IsolationPolicy':
        return cls(
            level=data.get("level", "PARTIAL"),
            inherit_plugins=data.get("inherit_plugins", True),
            inherit_intents=data.get("inherit_intents", False),
            inherit_classes=data.get("inherit_classes", True),
            max_call_stack=data.get("max_call_stack", 1000),
            max_instructions=data.get("max_instructions", 10000),
            collect_timeout=data.get("collect_timeout", None),
        )
