from typing import List, Optional
from dataclasses import dataclass, field


@dataclass
class IsolationPolicy:
    """
     隔离级别策略。

    | Level       | Registry | Plugins | Intents | Variables | CallStack |
    |-------------|----------|---------|---------|-----------|-----------|
    | FULL        | 独立克隆 | 全部继承 | 全部继承 | 全部继承  | 全部继承  |
    | PARTIAL     | 独立克隆 | 按配置   | 按配置   | 按配置    | 清空      |
    | PLUGIN_ONLY | 共享     | 独立    | 清空    | 清空      | 清空      |
    | MINIMAL     | 共享     | 无      | 清空    | 清空      | 清空      |
    """
    level: str = "PARTIAL"
    inherit_plugins: Optional[List[str]] = None
    inherit_intents: bool = False
    inherit_variables: bool = False
    inherit_classes: bool = True
    max_call_stack: int = 100
    max_instructions: int = 10000

    def __post_init__(self):
        if self.inherit_plugins is None:
            self.inherit_plugins = [] if self.level != "PARTIAL" else True

    @staticmethod
    def full() -> 'IsolationPolicy':
        return IsolationPolicy(
            level="FULL",
            inherit_plugins=True,
            inherit_intents=True,
            inherit_variables=True,
            inherit_classes=True
        )

    @staticmethod
    def partial(inherit_plugins: Optional[List[str]] = None, inherit_intents: bool = True) -> 'IsolationPolicy':
        return IsolationPolicy(
            level="PARTIAL",
            inherit_plugins=inherit_plugins or [],
            inherit_intents=inherit_intents,
            inherit_variables=False,
            inherit_classes=True
        )

    @staticmethod
    def plugin_only(inherit_plugins: List[str]) -> 'IsolationPolicy':
        return IsolationPolicy(
            level="PLUGIN_ONLY",
            inherit_plugins=inherit_plugins,
            inherit_intents=False,
            inherit_variables=False,
            inherit_classes=False
        )

    @staticmethod
    def minimal() -> 'IsolationPolicy':
        return IsolationPolicy(
            level="MINIMAL",
            inherit_plugins=[],
            inherit_intents=False,
            inherit_variables=False,
            inherit_classes=False
        )

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "inherit_plugins": self.inherit_plugins,
            "inherit_intents": self.inherit_intents,
            "inherit_variables": self.inherit_variables,
            "inherit_classes": self.inherit_classes,
            "max_call_stack": self.max_call_stack,
            "max_instructions": self.max_instructions,
            "isolated": self.level in ("FULL", "PARTIAL")
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'IsolationPolicy':
        return cls(
            level=data.get("level", "PARTIAL"),
            inherit_plugins=data.get("inherit_plugins"),
            inherit_intents=data.get("inherit_intents", False),
            inherit_variables=data.get("inherit_variables", False),
            inherit_classes=data.get("inherit_classes", True),
            max_call_stack=data.get("max_call_stack", 100),
            max_instructions=data.get("max_instructions", 10000)
        )
