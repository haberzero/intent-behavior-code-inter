"""
core/runtime/objects/media_storage.py

MediaStorage — 多模态数据存储后端。

Per ADR-007: Phase 3 使用纯内存方案。磁盘卸载推迟到 Phase 5。
Per ADR-012: 多模态类型作为普通类名注册。

MediaStorage 对用户透明（D3），但提供 ``.location`` 属性满足
"运行时可观测性优先"原则。
"""

from __future__ import annotations

from typing import Optional


class MediaStorage:
    """多模态数据存储后端（Phase 3：纯内存）。

    持有原始二进制数据 + 格式信息。Phase 5 将扩展为支持磁盘卸载
    （超过阈值时自动写入临时文件），但接口保持不变。

    属性：
    - ``data``: 原始字节序列（``bytes``）
    - ``format``: 媒体格式（如 ``"wav"``、``"png"``、``"mp4"``）
    - ``mime_type``: MIME 类型（如 ``"audio/wav"``；若未指定则从格式推导）
    - ``location``: 数据存储位置（Phase 3 始终为 ``"memory"``）
    """

    def __init__(self, data: bytes, format: str, mime_type: Optional[str] = None):
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError(f"MediaStorage data must be bytes, got {type(data).__name__}")
        self._data = bytes(data)
        self._format = format
        self._mime_type = mime_type or self._derive_mime_type(format)

    @property
    def data(self) -> bytes:
        """原始字节序列。"""
        return self._data

    @property
    def format(self) -> str:
        """媒体格式（如 'wav'、'png'、'mp4'）。"""
        return self._format

    @property
    def mime_type(self) -> str:
        """MIME 类型。"""
        return self._mime_type

    @property
    def location(self) -> str:
        """数据存储位置（Phase 3 始终为 'memory'）。"""
        return "memory"

    @property
    def size(self) -> int:
        """数据大小（字节）。"""
        return len(self._data)

    def __repr__(self) -> str:
        return f"MediaStorage(format={self._format!r}, size={self.size}, location={self.location!r})"

    def __eq__(self, other) -> bool:
        if not isinstance(other, MediaStorage):
            return False
        return self._data == other._data and self._format == other._format

    def __hash__(self) -> int:
        return hash((self._data, self._format))

    @staticmethod
    def _derive_mime_type(fmt: str) -> str:
        """从格式推导 MIME 类型。"""
        mime_map = {
            "wav": "audio/wav",
            "mp3": "audio/mpeg",
            "ogg": "audio/ogg",
            "flac": "audio/flac",
            "png": "image/png",
            "jpeg": "image/jpeg",
            "jpg": "image/jpeg",
            "gif": "image/gif",
            "webp": "image/webp",
            "mp4": "video/mp4",
            "webm": "video/webm",
            "avi": "video/x-msvideo",
        }
        return mime_map.get(fmt.lower(), f"application/octet-stream")
