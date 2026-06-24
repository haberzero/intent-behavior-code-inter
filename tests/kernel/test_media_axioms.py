"""
tests/kernel/test_media_axioms.py
=================================

AudioAxiom / ImageAxiom / VideoAxiom 公理层单元测试。

验证多模态类型的注册、能力标志、payload prompt 协议、类型兼容性。
Per ADR-012: 作为普通类名注册。Per ADR-007: Phase 3 纯内存。
"""
import base64
import pytest
from core.kernel.axioms.primitives.media import AudioAxiom, ImageAxiom, VideoAxiom
from core.kernel.axioms.primitives.base import BaseAxiom


class TestAudioAxiom:

    def test_name(self):
        assert AudioAxiom().name == "audio"

    def test_has_payload_prompt_cap(self):
        assert AudioAxiom().has_payload_prompt_cap is True

    def test_parent_is_object(self):
        assert AudioAxiom().get_parent_axiom_name() == "Object"

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

    def test_payload_prompt_with_storage(self):
        """__payload_prompt__ should return input_audio content block."""
        ax = AudioAxiom()

        class FakeStorage:
            data = b"fake_audio_data"
            format = "wav"
            mime_type = "audio/wav"

        class FakeIbAudio:
            payload = FakeStorage()
            def to_native(self):
                return FakeStorage()

        result = ax.__payload_prompt__(FakeIbAudio())
        assert isinstance(result, dict)
        assert result["type"] == "input_audio"
        assert "input_audio" in result
        assert result["input_audio"]["format"] == "wav"
        expected_b64 = base64.b64encode(b"fake_audio_data").decode("ascii")
        assert result["input_audio"]["data"] == expected_b64

    def test_payload_prompt_with_none_value(self):
        """__payload_prompt__ with no storage should return text fallback."""
        ax = AudioAxiom()
        result = ax.__payload_prompt__(None)
        assert isinstance(result, dict)
        assert result["type"] == "text"


class TestImageAxiom:

    def test_name(self):
        assert ImageAxiom().name == "image"

    def test_has_payload_prompt_cap(self):
        assert ImageAxiom().has_payload_prompt_cap is True

    def test_compatible_only_with_image(self):
        ax = ImageAxiom()
        assert ax.is_compatible("image")
        assert not ax.is_compatible("audio")
        assert not ax.is_compatible("str")

    def test_payload_prompt_returns_image_url(self):
        ax = ImageAxiom()

        class FakeStorage:
            data = b"fake_image_data"
            format = "png"
            mime_type = "image/png"

        class FakeIbImage:
            payload = FakeStorage()
            def to_native(self):
                return FakeStorage()

        result = ax.__payload_prompt__(FakeIbImage())
        assert isinstance(result, dict)
        assert result["type"] == "image_url"
        assert "url" in result["image_url"]
        assert result["image_url"]["url"].startswith("data:image/png;base64,")


class TestVideoAxiom:

    def test_name(self):
        assert VideoAxiom().name == "video"

    def test_has_payload_prompt_cap(self):
        assert VideoAxiom().has_payload_prompt_cap is True

    def test_compatible_only_with_video(self):
        ax = VideoAxiom()
        assert ax.is_compatible("video")
        assert not ax.is_compatible("audio")
        assert not ax.is_compatible("image")

    def test_payload_prompt_returns_video_block(self):
        ax = VideoAxiom()

        class FakeStorage:
            data = b"fake_video_data"
            format = "mp4"
            mime_type = "video/mp4"

        class FakeIbVideo:
            payload = FakeStorage()
            def to_native(self):
                return FakeStorage()

        result = ax.__payload_prompt__(FakeIbVideo())
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
