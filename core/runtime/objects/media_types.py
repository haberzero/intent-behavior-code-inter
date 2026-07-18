"""
core/runtime/objects/media_types.py

IbAudio / IbImage / IbVideo — 多模态运行时对象类。

Per ADR-014/016: 三种 media 类型现在是 ``IbFileHandle`` 的磁盘型子类，
通过 ``FileBacking`` 引用源文件，按需惰性物化字节。

Per ADR-012: 作为普通类名注册（非关键字）。
"""

from __future__ import annotations

import base64
from typing import Any, Dict

from core.base.path import IbPath

from .ib_type_mapping import register_ib_type
from .kernel import IbClass
from .file_handle import IbFileHandle
from .media_backing import FileBacking, MediaBacking


def _format_from_backing(backing: MediaBacking) -> str:
    """从 backing 路径的文件名扩展名推导格式。"""
    name = backing.path.name
    if "." in name:
        return name.rsplit(".", 1)[1].lower()
    return "bin"


def _mime_for_format(fmt: str, default_prefix: str) -> str:
    """根据格式推导 MIME type。"""
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
    return mime_map.get(fmt.lower(), f"{default_prefix}/{fmt}")


@register_ib_type("audio")
class IbAudio(IbFileHandle):
    """``audio`` 类型的 IBCI 运行时对象（磁盘型 file handle）。"""

    __slots__ = ()

    def __init__(self, backing: MediaBacking, ib_class: IbClass):
        super().__init__(backing, ib_class)
        # PT-ARCH-24: format 是 field，从文件名扩展名推导，无 I/O。
        self.fields["format"] = ib_class.registry.box(_format_from_backing(backing))

    def data(self) -> str:
        """返回 base64 编码的音频数据（可观测性/兼容性）。"""
        return base64.b64encode(self.__materialize__()).decode("ascii")

    def duration(self) -> float:
        """占位：当前实现不解析媒体元数据。"""
        return 0.0

    def __path_payload_prompt__(self) -> Dict[str, Any]:
        fmt = _format_from_backing(self.backing)
        b64_data = base64.b64encode(self.__materialize__()).decode("ascii")
        return {
            "type": "input_audio",
            "input_audio": {
                "data": b64_data,
                "format": fmt,
            },
        }

    def __repr__(self) -> str:
        return f"<audio handle format={self.fields['format'].to_native()!r} path={self.backing.path}>"


@register_ib_type("image")
class IbImage(IbFileHandle):
    """``image`` 类型的 IBCI 运行时对象（磁盘型 file handle）。"""

    __slots__ = ()

    def __init__(self, backing: MediaBacking, ib_class: IbClass):
        super().__init__(backing, ib_class)
        # PT-ARCH-24: format 是 field，从文件名扩展名推导，无 I/O。
        self.fields["format"] = ib_class.registry.box(_format_from_backing(backing))

    def data(self) -> str:
        return base64.b64encode(self.__materialize__()).decode("ascii")

    def width(self) -> int:
        return 0

    def height(self) -> int:
        return 0

    def __path_payload_prompt__(self) -> Dict[str, Any]:
        fmt = _format_from_backing(self.backing)
        b64_data = base64.b64encode(self.__materialize__()).decode("ascii")
        mime_type = _mime_for_format(fmt, "image")
        return {
            "type": "image_url",
            "image_url": {
                "url": f"data:{mime_type};base64,{b64_data}",
            },
        }

    def __repr__(self) -> str:
        return f"<image handle format={self.fields['format'].to_native()!r} path={self.backing.path}>"


@register_ib_type("video")
class IbVideo(IbFileHandle):
    """``video`` 类型的 IBCI 运行时对象（磁盘型 file handle）。"""

    __slots__ = ()

    def __init__(self, backing: MediaBacking, ib_class: IbClass):
        super().__init__(backing, ib_class)
        # PT-ARCH-24: format 是 field，从文件名扩展名推导，无 I/O。
        self.fields["format"] = ib_class.registry.box(_format_from_backing(backing))

    def data(self) -> str:
        return base64.b64encode(self.__materialize__()).decode("ascii")

    def duration(self) -> float:
        return 0.0

    def __path_payload_prompt__(self) -> Dict[str, Any]:
        fmt = _format_from_backing(self.backing)
        b64_data = base64.b64encode(self.__materialize__()).decode("ascii")
        return {
            "type": "video",
            "video": {
                "data": b64_data,
                "format": fmt,
            },
        }

    def __repr__(self) -> str:
        return f"<video handle format={self.fields['format'].to_native()!r} path={self.backing.path}>"


# --------------------------------------------------------------------------- #
# PT-ARCH-25: media 静态构造入口：audio.from_file / image.from_file / video.from_file
# --------------------------------------------------------------------------- #

def audio_from_file(ib_class: IbClass, path: str) -> IbAudio:
    """IBCI ``audio.from_file(path)`` 的运行时实现。"""
    backing = FileBacking(IbPath.from_native(path), sandboxed=True)
    return IbAudio(backing, ib_class)


def image_from_file(ib_class: IbClass, path: str) -> IbImage:
    """IBCI ``image.from_file(path)`` 的运行时实现。"""
    backing = FileBacking(IbPath.from_native(path), sandboxed=True)
    return IbImage(backing, ib_class)


def video_from_file(ib_class: IbClass, path: str) -> IbVideo:
    """IBCI ``video.from_file(path)`` 的运行时实现。"""
    backing = FileBacking(IbPath.from_native(path), sandboxed=True)
    return IbVideo(backing, ib_class)
