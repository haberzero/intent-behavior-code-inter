"""
[IES 2.1+] 运行时序列化模块

包含：
- RuntimeSerializer: 深度运行时序列化器
- ImmutableArtifact: 不可变产物封装
- SnapshotOptions: 快照配置选项
"""
from .runtime_serializer import RuntimeSerializer, RuntimeDeserializer
from .immutable_artifact import ImmutableArtifact
from .snapshot_options import SnapshotOptions, SnapshotManager, create_snapshot_options

__all__ = [
    "RuntimeSerializer",
    "RuntimeDeserializer",
    "ImmutableArtifact",
    "SnapshotOptions",
    "SnapshotManager",
    "create_snapshot_options",
]
