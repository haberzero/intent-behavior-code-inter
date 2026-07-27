"""
tests/kernel/test_media_axioms.py
=================================

AudioAxiom / ImageAxiom / VideoAxiom 公理层单元测试。

验证多模态类型的注册、能力标志、payload prompt 协议、类型兼容性。
作为普通类名注册。
media 类型是 file_handle 的磁盘型子类；公理层只负责委托。
"""

from core.kernel.axioms.primitives.media import AudioAxiom, ImageAxiom, VideoAxiom
from core.kernel.axioms.primitives.base import BaseAxiom


class _FakeValue:
    """带 receive 协议的假 runtime value，用于测试公理委托。"""

    def __init__(self, return_value):
        self._return_value = return_value

    def receive(self, message, args):
        if message == "__path_payload_prompt__":
            return self._return_value
        raise AttributeError(message)


def _input_audio_block():
    return {"type": "input_audio", "input_audio": {"data": "fake_b64", "format": "wav"}}


def _image_url_block():
    return {"type": "image_url", "image_url": {"url": "data:image/png;base64,fake_b64"}}


def _video_block():
    return {"type": "video", "video": {"data": "fake_b64", "format": "mp4"}}


class TestAudioAxiom:

    def test_name(self):
        assert AudioAxiom().name == "audio"

    def test_has_payload_prompt_cap(self):
        assert AudioAxiom().has_payload_prompt_cap is True

    def test_parent_is_file_handle(self):
        assert AudioAxiom().get_parent_axiom_name() == "file_handle"

    def test_compatible_only_with_audio(self):
        ax = AudioAxiom()
        assert ax.is_compatible("audio")
        assert not ax.is_compatible("str")
        assert not ax.is_compatible("image")
        assert not ax.is_compatible("any")

    def test_can_convert_from_only_audio(self):
        ax = AudioAxiom()
        assert ax.can_convert_from("audio")
        assert not ax.can_convert_from("str")

    def test_method_specs_include_data_and_format(self):
        specs = AudioAxiom().get_method_specs()
        assert "data" in specs
        assert "format" in specs
        assert "duration" in specs
        assert "cast_to" in specs

    def test_payload_prompt_delegates_to_runtime_value(self):
        """__payload_prompt__ 委托给 runtime 的 __path_payload_prompt__。"""
        ax = AudioAxiom()
        result = ax.__payload_prompt__(_FakeValue(_input_audio_block()))
        assert isinstance(result, dict)
        assert result["type"] == "input_audio"
        assert "input_audio" in result
        assert result["input_audio"]["format"] == "wav"

    def test_payload_prompt_with_none_value(self):
        """__payload_prompt__ with no value should return text fallback."""
        ax = AudioAxiom()
        result = ax.__payload_prompt__(None)
        assert isinstance(result, dict)
        assert result["type"] == "text"


class TestImageAxiom:

    def test_name(self):
        assert ImageAxiom().name == "image"

    def test_has_payload_prompt_cap(self):
        assert ImageAxiom().has_payload_prompt_cap is True

    def test_parent_is_file_handle(self):
        assert ImageAxiom().get_parent_axiom_name() == "file_handle"

    def test_compatible_only_with_image(self):
        ax = ImageAxiom()
        assert ax.is_compatible("image")
        assert not ax.is_compatible("audio")
        assert not ax.is_compatible("str")

    def test_payload_prompt_delegates_to_runtime_value(self):
        ax = ImageAxiom()
        result = ax.__payload_prompt__(_FakeValue(_image_url_block()))
        assert isinstance(result, dict)
        assert result["type"] == "image_url"
        assert "url" in result["image_url"]


class TestVideoAxiom:

    def test_name(self):
        assert VideoAxiom().name == "video"

    def test_has_payload_prompt_cap(self):
        assert VideoAxiom().has_payload_prompt_cap is True

    def test_parent_is_file_handle(self):
        assert VideoAxiom().get_parent_axiom_name() == "file_handle"

    def test_compatible_only_with_video(self):
        ax = VideoAxiom()
        assert ax.is_compatible("video")
        assert not ax.is_compatible("audio")
        assert not ax.is_compatible("image")

    def test_payload_prompt_delegates_to_runtime_value(self):
        ax = VideoAxiom()
        result = ax.__payload_prompt__(_FakeValue(_video_block()))
        assert isinstance(result, dict)
        assert result["type"] == "video"
        assert result["video"]["format"] == "mp4"


class TestMediaAxiomRegistration:
    """验证公理注册到 AxiomRegistry 后可被查询。"""

    def test_all_three_axioms_are_base_axiom_subclasses(self):
        assert issubclass(AudioAxiom, BaseAxiom)
        assert issubclass(ImageAxiom, BaseAxiom)
        assert issubclass(VideoAxiom, BaseAxiom)

    def test_names_are_distinct(self):
        names = {AudioAxiom().name, ImageAxiom().name, VideoAxiom().name}
        assert names == {"audio", "image", "video"}
