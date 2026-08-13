"""
测试 storage_model 在 deep_clone 与 RuntimeSerializer 中的分发行为。

目标：
- 内存型对象保持既有递归深克隆语义。
- 磁盘型对象通过协议方法浅拷贝路径引用，不物化字节。
"""

from __future__ import annotations

import pytest

from core.base.enums import StorageModel
from core.kernel.path import PathValidator
from core.kernel.spec.base import IbSpec
from core.runtime.objects.deep_clone import try_deep_clone
from core.runtime.objects.kernel import IbValue
from core.runtime.objects.media_backing import FileBacking
from core.runtime.objects.media_types import IbAudio
from core.runtime.objects.primitives.collections import IbList
from core.runtime.serialization.runtime_serializer import RuntimeSerializer


class _FakeRegistry:
    def box(self, value):
        return value

    def get_none(self):
        return None


class _FakeIbClass:
    name = "disk_test"
    qualified_name = "disk_test"
    registry = _FakeRegistry()
    spec = IbSpec(name="disk_test", storage_model=StorageModel.DISK_BACKED)


class _DiskValue(IbValue):
    __slots__ = ()

    def __init__(self):
        super().__init__(_FakeIbClass)


def test_memory_list_deep_clone(engine_session):
    """内存型 list 仍走完整递归深克隆。"""
    registry = engine_session.registry
    list_class = registry.get_class("list")
    original = IbList([registry.box(1), registry.box(2)], list_class)
    cloned = try_deep_clone(original)

    assert cloned is not None
    assert cloned is not original
    assert [e.to_native() for e in cloned.elements] == [1, 2]


def test_disk_backed_clone_uses_protocol(monkeypatch):
    """磁盘型对象调用 ``__clone_ref__`` 而不是递归深克隆。"""
    original = _DiskValue()
    clone = _DiskValue()

    def _fake_receive(self, msg, args):
        return clone if msg == "__clone_ref__" else None

    monkeypatch.setattr(_DiskValue, "receive", _fake_receive)

    result = try_deep_clone(original)
    assert result is clone


def test_memory_media_value_not_lost(engine_session, tmp_path):
    """``type(val) is KernelIbObject`` 的修复：media 等 IbValue 子类不再丢失。"""
    registry = engine_session.registry
    audio_class = registry.get_class("audio")
    tmp_file = tmp_path / "audio.wav"
    tmp_file.write_bytes(b"fake-audio")
    backing = FileBacking(PathValidator.canonicalize_for_security(str(tmp_file)))
    original = IbAudio(backing, audio_class)

    cloned = try_deep_clone(original)
    assert cloned is not None
    assert cloned is not original
    assert cloned.ib_class.name == "audio"
    # disk-backed 子类深拷贝只复制路径引用。
    assert cloned.backing is original.backing


def test_disk_backed_serializer_branch(engine_session, monkeypatch):
    """磁盘型对象序列化为 ``disk_backed`` 描述符，不物化字节。"""
    registry = engine_session.registry
    serializer = RuntimeSerializer(registry)

    obj = _DiskValue()
    descriptor = {"path": "project_root/audio.wav", "format": "wav", "backing": "file"}

    class _DescriptorValue:
        def to_native(self):
            return descriptor

    def _fake_receive(self, msg, args):
        return _DescriptorValue() if msg == "__to_descriptor__" else None

    monkeypatch.setattr(_DiskValue, "receive", _fake_receive)

    uid = serializer._collect_instance(obj)
    data = serializer.instance_pool[uid]

    assert data["_type"] == "disk_backed"
    assert data["class_name"] == "disk_test"
    assert data["descriptor"] == descriptor
