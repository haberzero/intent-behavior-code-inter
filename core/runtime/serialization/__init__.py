"""
运行时序列化模块

包含：
- RuntimeSerializer: 深度运行时序列化器
- ImmutableArtifact: 不可变产物封装
"""
from .runtime_serializer import RuntimeSerializer, RuntimeDeserializer
from .immutable_artifact import ImmutableArtifact

__all__ = [
    "RuntimeSerializer",
    "RuntimeDeserializer",
    "ImmutableArtifact",
]
