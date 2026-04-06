"""
子解释器快照配置选项

为 HostService.snapshot() 和 save_state() 提供细粒度的快照控制能力。
"""
from dataclasses import dataclass, field
from typing import Any, Optional, List, Set


@dataclass
class SnapshotOptions:
    """
    快照配置选项

    用于控制子解释器快照的深度和范围。
    """
    include_static: bool = True
    include_runtime: bool = True
    include_nodes: bool = True
    include_symbols: bool = True
    include_types: bool = True
    include_assets: bool = True
    include_intent_stack: bool = True
    include_global_intents: bool = True
    max_depth: int = 100
    excluded_modules: Set[str] = field(default_factory=set)
    excluded_scopes: Set[str] = field(default_factory=set)
    compression: bool = False
    encrypt: bool = False

    def to_dict(self) -> dict:
        return {
            "include_static": self.include_static,
            "include_runtime": self.include_runtime,
            "include_nodes": self.include_nodes,
            "include_symbols": self.include_symbols,
            "include_types": self.include_types,
            "include_assets": self.include_assets,
            "include_intent_stack": self.include_intent_stack,
            "include_global_intents": self.include_global_intents,
            "max_depth": self.max_depth,
            "excluded_modules": list(self.excluded_modules),
            "excluded_scopes": list(self.excluded_scopes),
            "compression": self.compression,
            "encrypt": self.encrypt,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'SnapshotOptions':
        return cls(
            include_static=data.get("include_static", True),
            include_runtime=data.get("include_runtime", True),
            include_nodes=data.get("include_nodes", True),
            include_symbols=data.get("include_symbols", True),
            include_types=data.get("include_types", True),
            include_assets=data.get("include_assets", True),
            include_intent_stack=data.get("include_intent_stack", True),
            include_global_intents=data.get("include_global_intents", True),
            max_depth=data.get("max_depth", 100),
            excluded_modules=set(data.get("excluded_modules", [])),
            excluded_scopes=set(data.get("excluded_scopes", [])),
            compression=data.get("compression", False),
            encrypt=data.get("encrypt", False),
        )

    @staticmethod
    def minimal() -> 'SnapshotOptions':
        """
        最小快照：仅包含运行时状态，不包含静态信息
        适用于快速状态保存和恢复
        """
        return SnapshotOptions(
            include_static=False,
            include_nodes=False,
            include_symbols=False,
            include_types=False,
            include_assets=False,
        )

    @staticmethod
    def full() -> 'SnapshotOptions':
        """
        完整快照：包含所有可用信息
        适用于完整的运行时存档
        """
        return SnapshotOptions(
            include_static=True,
            include_runtime=True,
            include_nodes=True,
            include_symbols=True,
            include_types=True,
            include_assets=True,
            include_intent_stack=True,
            include_global_intents=True,
        )

    @staticmethod
    def debug() -> 'SnapshotOptions':
        """
        调试快照：包含调试所需的全部信息
        适用于开发调试场景
        """
        return SnapshotOptions(
            include_static=True,
            include_runtime=True,
            include_nodes=True,
            include_symbols=True,
            include_types=True,
            include_assets=True,
            include_intent_stack=True,
            include_global_intents=True,
            max_depth=1000,
        )


class SnapshotManager:
    """
    快照管理器

    提供快照的创建、应用和生命周期管理。
    """
    def __init__(self, options: Optional[SnapshotOptions] = None):
        self.options = options or SnapshotOptions.full()
        self._snapshots: dict = {}

    def create_snapshot(self, context: Any, execution_context: Optional[Any] = None) -> dict:
        """
        使用配置的选项创建快照

        注意：此方法需要与 RuntimeSerializer 配合使用
        """
        return {
            "options": self.options.to_dict(),
            "data": None,
        }

    def apply_snapshot(self, snapshot: dict, context: Any) -> bool:
        """
        应用快照到给定上下文

        注意：此方法需要与 RuntimeDeserializer 配合使用
        """
        if not snapshot or "options" not in snapshot:
            return False
        self.options = SnapshotOptions.from_dict(snapshot["options"])
        return True

    def get_snapshot_info(self, snapshot: dict) -> dict:
        """获取快照元信息"""
        if not snapshot:
            return {}
        options = SnapshotOptions.from_dict(snapshot.get("options", {}))
        return {
            "has_data": "data" in snapshot and snapshot["data"] is not None,
            "include_static": options.include_static,
            "include_runtime": options.include_runtime,
            "compression": options.compression,
            "encrypt": options.encrypt,
        }


def create_snapshot_options(**kwargs) -> SnapshotOptions:
    """工厂函数：创建快照配置"""
    return SnapshotOptions(**kwargs)
