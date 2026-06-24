"""
core/runtime/objects/media_types.py

IbAudio / IbImage / IbVideo — 多模态运行时对象类。

这些类包装 ``MediaStorage`` 实例，通过 ``@register_ib_type`` 注册到
IBCI 类型系统。它们作为 ``IbValue`` 子类，在行为表达式 ``@~ ... $media ... ~``
中通过 ``__payload_prompt__`` 协议参与多模态 LLM 调用。

Per ADR-007: Phase 3 使用纯内存 deep-copy snapshot。
Per ADR-012: 作为普通类名注册（非关键字）。
"""

from __future__ import annotations

from typing import Any, Optional

from .kernel import IbObject, IbValue, IbClass
from .ib_type_mapping import register_ib_type
from .media_storage import MediaStorage


@register_ib_type("audio")
class IbAudio(IbValue):
    """``audio`` 类型的 IBC 运行时对象。

    包装 ``MediaStorage`` 实例（音频数据）。
    在行为表达式中通过 ``__payload_prompt__`` 返回 ``input_audio`` content block。
    """

    __slots__ = ()

    def __init__(self, storage: MediaStorage, ib_class: IbClass):
        super().__init__(ib_class, payload=storage)

    @property
    def storage(self) -> MediaStorage:
        """返回底层 MediaStorage。"""
        return self.value

    def to_native(self, memo=None) -> MediaStorage:
        return self.value

    def to_bool(self) -> IbObject:
        return self.ib_class.registry.box(bool(self.value and self.value.data))

    def __repr__(self) -> str:
        storage = self.value
        if storage:
            return f"IbAudio(format={storage.format!r}, size={storage.size})"
        return "IbAudio(empty)"


@register_ib_type("image")
class IbImage(IbValue):
    """``image`` 类型的 IBC 运行时对象。

    包装 ``MediaStorage`` 实例（图像数据）。
    在行为表达式中通过 ``__payload_prompt__`` 返回 ``image_url`` content block。
    """

    __slots__ = ()

    def __init__(self, storage: MediaStorage, ib_class: IbClass):
        super().__init__(ib_class, payload=storage)

    @property
    def storage(self) -> MediaStorage:
        """返回底层 MediaStorage。"""
        return self.value

    def to_native(self, memo=None) -> MediaStorage:
        return self.value

    def to_bool(self) -> IbObject:
        return self.ib_class.registry.box(bool(self.value and self.value.data))

    def __repr__(self) -> str:
        storage = self.value
        if storage:
            return f"IbImage(format={storage.format!r}, size={storage.size})"
        return "IbImage(empty)"


@register_ib_type("video")
class IbVideo(IbValue):
    """``video`` 类型的 IBC 运行时对象。

    包装 ``MediaStorage`` 实例（视频数据）。
    在行为表达式中通过 ``__payload_prompt__`` 返回 ``video`` content block。
    """

    __slots__ = ()

    def __init__(self, storage: MediaStorage, ib_class: IbClass):
        super().__init__(ib_class, payload=storage)

    @property
    def storage(self) -> MediaStorage:
        """返回底层 MediaStorage。"""
        return self.value

    def to_native(self, memo=None) -> MediaStorage:
        return self.value

    def to_bool(self) -> IbObject:
        return self.ib_class.registry.box(bool(self.value and self.value.data))

    def __repr__(self) -> str:
        storage = self.value
        if storage:
            return f"IbVideo(format={storage.format!r}, size={storage.size})"
        return "IbVideo(empty)"
