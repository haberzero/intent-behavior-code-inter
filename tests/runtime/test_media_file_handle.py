"""
tests/runtime/test_media_file_handle.py
=======================================

验证 media 类型（audio/image/video）在 ADR-014/016/020 之后的行为：
- 是 ``IbFileHandle`` 的磁盘型子类。
- ``audio/image/video.from_file(path)`` 返回 ``FileBacking``，不立即读字节（零拷贝）。
- ``__path_payload_prompt__`` 按需物化并生成正确的 content block。
- deep_clone / 序列化只复制路径引用。
"""

from __future__ import annotations

import base64

import pytest

from core.kernel.path import PathValidator
from core.runtime.interpreter.llm_executor import LLMExecutorImpl
from core.runtime.objects.deep_clone import try_deep_clone
from core.runtime.objects.file_handle import IbFileHandle
from core.runtime.objects.media_backing import FileBacking
from core.runtime.objects.media_types import (
    IbAudio, IbImage, IbVideo,
    audio_from_file, image_from_file, video_from_file,
)
from core.runtime.serialization.runtime_serializer import RuntimeSerializer


def _media_class(registry, type_name: str):
    cls = registry.get_class(type_name)
    assert cls is not None
    return cls


def _make_media(tmp_path, registry, type_name: str, filename: str, data: bytes):
    path = tmp_path / filename
    path.write_bytes(data)
    ib_path = PathValidator.canonicalize_for_security(str(path))
    cls = _media_class(registry, type_name)
    if type_name == "audio":
        return IbAudio(FileBacking(ib_path), cls)
    if type_name == "image":
        return IbImage(FileBacking(ib_path), cls)
    return IbVideo(FileBacking(ib_path), cls)


@pytest.fixture
def file_engine(tmp_path):
    """以 tmp_path 为 project_root 的引擎，供需要 FS I/O 的 media 测试使用。"""
    from core.engine import IBCIEngine
    return IBCIEngine(root_dir=str(tmp_path), auto_sniff=False)


class TestMediaFileHandle:
    """media 类型作为 FileHandle 子类的核心契约。"""

    def test_audio_is_file_handle_subclass(self, file_engine, tmp_path):
        # 先运行 import file 以注入 ExecutionContext / PermissionManager。
        file_engine.run_string("import file\n", silent=True)
        obj = _make_media(tmp_path, file_engine.registry, "audio", "a.wav", b"x")
        assert isinstance(obj, IbFileHandle)
        # PT-ARCH-24: format 是 field；IBCI 层通过 fields 字典访问。
        assert obj.fields["format"].to_native() == "wav"

    def test_image_payload_returns_image_url_block(self, file_engine, tmp_path):
        file_engine.run_string("import file\n", silent=True)
        obj = _make_media(tmp_path, file_engine.registry, "image", "i.png", b"pngdata")
        payload = LLMExecutorImpl._obj_to_payload(obj)
        assert payload["type"] == "image_url"
        assert "data:image/png;base64," in payload["image_url"]["url"]

    def test_video_payload_returns_video_block(self, file_engine, tmp_path):
        file_engine.run_string("import file\n", silent=True)
        obj = _make_media(tmp_path, file_engine.registry, "video", "v.mp4", b"mp4data")
        payload = LLMExecutorImpl._obj_to_payload(obj)
        assert payload["type"] == "video"
        assert payload["video"]["format"] == "mp4"

    def test_media_clone_ref_shares_backing(self, engine_session, tmp_path):
        obj = _make_media(tmp_path, engine_session.registry, "audio", "a.wav", b"x")
        clone = try_deep_clone(obj)
        assert clone is not obj
        assert clone.backing is obj.backing

    def test_media_serializer_disk_backed(self, engine_session, tmp_path):
        obj = _make_media(tmp_path, engine_session.registry, "audio", "a.wav", b"x")
        serializer = RuntimeSerializer(engine_session.registry)
        uid = serializer._collect_instance(obj)
        data = serializer.instance_pool[uid]
        assert data["_type"] == "disk_backed"
        assert data["class_name"] == "audio"
        assert data["descriptor"]["backing_type"] == "file"


class TestMediaFromFile:
    """audio/image/video.from_file(path) 返回磁盘型 FileHandle（零拷贝）。"""

    @pytest.fixture
    def file_module(self, file_engine):
        file_engine.run_string("import file\n", silent=True)
        return file_engine.host_interface.get_module_implementation("file")

    def test_audio_from_file_returns_file_handle(self, file_module, tmp_path):
        path = tmp_path / "sample.wav"
        path.write_bytes(b"fake-wav")
        audio_cls = file_module._file_handle_class().registry.get_class("audio")
        audio = audio_from_file(audio_cls, str(path))
        assert isinstance(audio, IbAudio)
        assert audio.backing.path.to_native() == str(path)

    def test_image_from_file_returns_file_handle(self, file_module, tmp_path):
        path = tmp_path / "sample.png"
        path.write_bytes(b"fake-png")
        image_cls = file_module._file_handle_class().registry.get_class("image")
        image = image_from_file(image_cls, str(path))
        assert isinstance(image, IbImage)
        assert image.backing.path.to_native() == str(path)

    def test_video_from_file_returns_file_handle(self, file_module, tmp_path):
        path = tmp_path / "sample.mp4"
        path.write_bytes(b"fake-mp4")
        video_cls = file_module._file_handle_class().registry.get_class("video")
        video = video_from_file(video_cls, str(path))
        assert isinstance(video, IbVideo)
        assert video.backing.path.to_native() == str(path)
